"""CON-002 修复测试: cancel_deletion 加锁 + purge_pending_deletions 防并发误删.

模式 1 mock: 用 MagicMock 模拟 row-lock 行为, 不连真 PG.
配合 db_session (模式 2) 真并发场景由集成测试覆盖 — 本文件锁 SKIP LOCKED 行为
SQL 行为级测试, 单元测试专注业务逻辑.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from src.auth.account_settings_service import cancel_deletion, purge_pending_deletions

# --- cancel_deletion 加锁场景 ---


def test_cancel_deletion_acquires_row_lock_on_account():
    """cancel_deletion 必须 SELECT ... FOR UPDATE 锁住 account 行.

    验证: session.query(Account) 之后 .with_for_update() 被调用.
    """
    mock_account = MagicMock(
        id=42,
        is_active=False,
        is_pending_deletion=True,
        deletion_requested_at=datetime.now(),
    )

    mock_account_query = MagicMock()
    mock_account_query.filter.return_value.with_for_update.return_value.one_or_none.return_value = mock_account

    mock_restore_query = MagicMock()
    mock_restore_query.filter_by.return_value.all.return_value = []

    mock_session = MagicMock()
    mock_session.query.side_effect = [mock_account_query, mock_restore_query]

    with patch("src.auth.account_settings_service.verify_password", return_value=True):
        cancel_deletion(mock_session, mock_account, "pw")

    # 验证 with_for_update() 被调用过 (行锁)
    mock_account_query.filter.return_value.with_for_update.assert_called_once()
    # 验证未传 skip_locked (cancel 是单行锁, 不要 skip)
    call_kwargs = mock_account_query.filter.return_value.with_for_update.call_args.kwargs
    assert "skip_locked" not in call_kwargs or call_kwargs["skip_locked"] is False


def test_cancel_deletion_rejects_when_account_deleted_by_cron_while_waiting():
    """CON-002: 锁内重读返回 None (cron 已 DELETE) → 拒绝 + 不改任何状态.

    场景: cancel 请求进入 → 等锁 → cron 先持锁跑完 + commit + 删 account → 我们再查 → None
    → 拒绝 'account not found (concurrent deletion)'. 这是 race 已被 cron 抢走的信号.
    """
    # 初始 view (用户视角): 还在 pending
    mock_account_view = MagicMock(
        id=99,
        is_active=False,
        is_pending_deletion=True,
        deletion_requested_at=datetime.now() - timedelta(days=31),
    )

    # 锁后: 没了 (cron 已 DELETE 完)
    mock_account_query = MagicMock()
    mock_account_query.filter.return_value.with_for_update.return_value.one_or_none.return_value = None

    mock_session = MagicMock()
    mock_session.query.return_value = mock_account_query

    with patch("src.auth.account_settings_service.verify_password", return_value=True):
        with pytest.raises(ValueError, match="concurrent deletion"):
            cancel_deletion(mock_session, mock_account_view, "pw")

    # 状态不应被改, 不应 flush
    mock_session.flush.assert_not_called()


def test_cancel_deletion_rejects_when_account_lock_returns_none():
    """锁查询返 None (account 不存在) → 拒绝 + 不改任何状态."""
    mock_account = MagicMock(
        id=404,
        is_active=False,
        is_pending_deletion=True,
        deletion_requested_at=datetime.now(),
    )

    mock_account_query = MagicMock()
    mock_account_query.filter.return_value.with_for_update.return_value.one_or_none.return_value = None

    mock_session = MagicMock()
    mock_session.query.return_value = mock_account_query

    with patch("src.auth.account_settings_service.verify_password", return_value=True):
        with pytest.raises(ValueError, match="not found"):
            cancel_deletion(mock_session, mock_account, "pw")


def test_cancel_deletion_rejects_when_locked_account_not_pending():
    """锁内二次 check is_pending_deletion — 防 TOCTOU (锁前 pending=True, 锁后变 False)."""
    mock_account_view = MagicMock(id=1, is_active=False, is_pending_deletion=True)

    # 锁后: 不在 pending (cron 删了 → FK CASCADE → 实际不存在, 但模拟 race)
    mock_locked_account = MagicMock(
        id=1,
        is_active=True,  # 已不在 pending (cleanup 走完)
        is_pending_deletion=False,
        deletion_requested_at=None,
    )

    mock_account_query = MagicMock()
    mock_account_query.filter.return_value.with_for_update.return_value.one_or_none.return_value = mock_locked_account

    mock_session = MagicMock()
    mock_session.query.return_value = mock_account_query

    with patch("src.auth.account_settings_service.verify_password", return_value=True):
        with pytest.raises(ValueError, match="not pending deletion"):
            cancel_deletion(mock_session, mock_account_view, "pw")


# --- purge_pending_deletions 加 skip_locked 场景 ---


def test_purge_uses_skip_locked_to_avoid_blocking_cancel():
    """CON-002: purge_pending_deletions 必须 with_for_update(skip_locked=True).

    验证: SELECT ... FOR UPDATE SKIP LOCKED 被调用 — 让 cancel 持锁时 cron 跳过这行.
    """
    mock_account_query = MagicMock()
    mock_account_query.filter.return_value.filter.return_value.with_for_update.return_value.all.return_value = []

    mock_session = MagicMock()
    mock_session.query.return_value = mock_account_query

    purge_pending_deletions(mock_session)

    # 验证 skip_locked=True 被传
    call_kwargs = mock_account_query.filter.return_value.filter.return_value.with_for_update.call_args.kwargs
    assert call_kwargs.get("skip_locked") is True


def test_purge_skips_accounts_cancelled_after_select():
    """CON-002: cron 拉到 victim 后, 二次校验 is_pending_deletion 仍是 True + is_active=False.

    场景 (理论): cron SELECT → user cancel 抢锁 (但 cancel 已持锁, SKIP LOCKED 会跳过)
    → 防 cancel 走完后 cron 又删 → 二次 check 拦截.
    """
    # 模拟一个"cancelled" account (cancel 已把状态改了, 但这行进了 cron 候选集)
    # 实际 SKIP LOCKED 不会让这种行进 cron; 但作为防御性 check, 也验证二次校验
    cancelled_account = MagicMock(
        id=1,
        deletion_requested_at=datetime.now() - timedelta(days=8),
        is_pending_deletion=False,  # cancel 已清
        is_active=True,  # cancel 已激活
    )

    mock_account_query = MagicMock()
    mock_account_query.filter.return_value.filter.return_value.with_for_update.return_value.all.return_value = [
        cancelled_account
    ]

    mock_session = MagicMock()
    mock_session.query.return_value = mock_account_query

    count = purge_pending_deletions(mock_session)
    assert count == 0
    mock_session.delete.assert_not_called()
    mock_session.flush.assert_not_called()


def test_purge_deletes_accounts_with_lock_skipped():
    """正常路径: cron 拿到 victim + 二次校验通过 → anonymize + delete."""
    mock_account = MagicMock(
        id=1,
        deletion_requested_at=datetime.now() - timedelta(days=8),
        is_pending_deletion=True,
        is_active=False,
    )
    mock_user = MagicMock(
        id=10,
        account_id=1,
        public_token="old_token",
        display_name="Alice",
    )

    mock_account_query = MagicMock()
    mock_account_query.filter.return_value.filter.return_value.with_for_update.return_value.all.return_value = [
        mock_account
    ]

    mock_user_query = MagicMock()
    mock_user_query.filter_by.return_value.first.return_value = mock_user

    mock_session = MagicMock()
    mock_session.query.side_effect = [mock_account_query, mock_user_query]

    count = purge_pending_deletions(mock_session)
    assert count == 1
    mock_session.delete.assert_called_once_with(mock_account)
    # user 应被 anonymize
    assert mock_user.account_id is None
    assert "已注销" in mock_user.display_name
