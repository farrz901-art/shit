"""CON-003 修复测试: verify_email_change 加 SELECT FOR UPDATE 防 TOCTOU.

模式 1 mock: 用 MagicMock 模拟 row-lock 行为, 不连真 PG.
验证 with_for_update() 在 EmailChange 和 Account 查询上都被调用.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any
from unittest.mock import MagicMock

import pytest

from src.auth.account_settings_service import verify_email_change
from src.utils.timezone import HKT


def _make_valid_change(**kwargs: Any) -> MagicMock:
    """造一个有效 EmailChange mock."""
    defaults: dict[str, Any] = dict(
        id=1,
        account_id=42,
        new_email="new@x.com",
        token="valid-token",
        expires_at=datetime.now(HKT) + timedelta(days=1),
        used_at=None,
        created_at=datetime.now(HKT),
    )
    defaults.update(kwargs)
    return MagicMock(**defaults)


def _make_account(**kwargs: Any) -> MagicMock:
    """造一个 Account mock."""
    return MagicMock(
        id=42,
        email="old@x.com",
        **kwargs,
    )


# --- with_for_update 存在性验证 ---


def test_verify_email_change_locks_email_change_row():
    """verify_email_change 必须 SELECT ... FOR UPDATE 锁 email_change 行.

    验证: session.query(EmailChange) 之后 .with_for_update() 被调用.
    """
    change = _make_valid_change()
    account = _make_account()

    mock_change_query = MagicMock()
    mock_change_query.filter_by.return_value.with_for_update.return_value.one_or_none.return_value = change

    mock_dup_query = MagicMock()
    mock_dup_query.filter.return_value.first.return_value = None

    mock_account_query = MagicMock()
    mock_account_query.filter.return_value.with_for_update.return_value.one_or_none.return_value = account

    mock_session = MagicMock()
    mock_session.query.side_effect = [mock_change_query, mock_dup_query, mock_account_query]

    verify_email_change(mock_session, "valid-token")

    # 验证 EmailChange 查询用了 with_for_update()
    mock_change_query.filter_by.return_value.with_for_update.assert_called_once()


def test_verify_email_change_locks_account_row():
    """verify_email_change 必须 SELECT ... FOR UPDATE 锁 account 行.

    验证: session.query(Account) 锁 new_email dup 后 .with_for_update() 在 account 查询上被调用.
    """
    change = _make_valid_change()
    account = _make_account()

    mock_change_query = MagicMock()
    mock_change_query.filter_by.return_value.with_for_update.return_value.one_or_none.return_value = change

    mock_dup_query = MagicMock()
    mock_dup_query.filter.return_value.first.return_value = None

    mock_account_query = MagicMock()
    mock_account_query.filter.return_value.with_for_update.return_value.one_or_none.return_value = account

    mock_session = MagicMock()
    mock_session.query.side_effect = [mock_change_query, mock_dup_query, mock_account_query]

    verify_email_change(mock_session, "valid-token")

    # 验证 Account 查询 (第二个 session.query(Account)) 用了 with_for_update()
    mock_account_query.filter.return_value.with_for_update.assert_called_once()


def test_verify_email_change_lock_not_skip_locked():
    """verify_email_change 的单行锁不应该传 skip_locked (非批量操作)."""
    change = _make_valid_change()
    account = _make_account()

    mock_change_query = MagicMock()
    mock_change_query.filter_by.return_value.with_for_update.return_value.one_or_none.return_value = change

    mock_dup_query = MagicMock()
    mock_dup_query.filter.return_value.first.return_value = None

    mock_account_query = MagicMock()
    mock_account_query.filter.return_value.with_for_update.return_value.one_or_none.return_value = account

    mock_session = MagicMock()
    mock_session.query.side_effect = [mock_change_query, mock_dup_query, mock_account_query]

    verify_email_change(mock_session, "valid-token")

    # EmailChange 锁不应有 skip_locked
    change_kwargs = mock_change_query.filter_by.return_value.with_for_update.call_args.kwargs
    assert "skip_locked" not in change_kwargs or change_kwargs["skip_locked"] is False

    # Account 锁不应有 skip_locked
    account_kwargs = mock_account_query.filter.return_value.with_for_update.call_args.kwargs
    assert "skip_locked" not in account_kwargs or account_kwargs["skip_locked"] is False


# --- 并发场景行为验证 ---


def test_verify_two_concurrent_requests_first_wins():
    """并发 verify 同一 token, 第一个成功, 第二个看到 used_at 已设 → 拒绝.

    场景: 请求 A 已持锁改完 + commit, 请求 B 等锁后读到 used_at 有值.
    """
    # 模拟第二次请求: 锁后读到 change.used_at 已设 (另一请求已改完)
    used_change = _make_valid_change(used_at=datetime.now(HKT))

    mock_change_query = MagicMock()
    mock_change_query.filter_by.return_value.with_for_update.return_value.one_or_none.return_value = used_change

    mock_session = MagicMock()
    mock_session.query.return_value = mock_change_query

    with pytest.raises(ValueError, match="invalid or used"):
        verify_email_change(mock_session, "valid-token")


def test_verify_expired_token_still_fails_after_lock():
    """过期 token 即使拿到锁也应拒绝."""
    expired_change = _make_valid_change(
        expires_at=datetime.now(HKT) - timedelta(hours=1),
    )

    mock_change_query = MagicMock()
    mock_change_query.filter_by.return_value.with_for_update.return_value.one_or_none.return_value = expired_change

    mock_session = MagicMock()
    mock_session.query.return_value = mock_change_query

    with pytest.raises(ValueError, match="token expired"):
        verify_email_change(mock_session, "expired-token")


def test_verify_account_not_found_after_lock_raises():
    """锁住 email_change 后 account 不存在 → 拒绝."""
    change = _make_valid_change()

    mock_change_query = MagicMock()
    mock_change_query.filter_by.return_value.with_for_update.return_value.one_or_none.return_value = change

    mock_dup_query = MagicMock()
    mock_dup_query.filter.return_value.first.return_value = None

    mock_account_query = MagicMock()
    mock_account_query.filter.return_value.with_for_update.return_value.one_or_none.return_value = None

    mock_session = MagicMock()
    mock_session.query.side_effect = [mock_change_query, mock_dup_query, mock_account_query]

    with pytest.raises(ValueError, match="account not found"):
        verify_email_change(mock_session, "valid-token")


def test_verify_email_change_success_normal_path():
    """正常路径: 有锁 + 有效 token + 有效 account → 切换 email + 标 used_at.

    验证 email 被改, used_at 被标, session.flush 被调.
    """
    change = _make_valid_change()
    account = _make_account()

    mock_change_query = MagicMock()
    mock_change_query.filter_by.return_value.with_for_update.return_value.one_or_none.return_value = change

    mock_dup_query = MagicMock()
    mock_dup_query.filter.return_value.first.return_value = None

    mock_account_query = MagicMock()
    mock_account_query.filter.return_value.with_for_update.return_value.one_or_none.return_value = account

    mock_session = MagicMock()
    mock_session.query.side_effect = [mock_change_query, mock_dup_query, mock_account_query]

    result = verify_email_change(mock_session, "valid-token")

    assert result == {"email": account.email}
    assert account.email == "new@x.com"
    assert change.used_at is not None
    mock_session.flush.assert_called_once()


def test_verify_email_change_invalid_token():
    """无效 token (不存在) → 拒绝."""
    mock_change_query = MagicMock()
    mock_change_query.filter_by.return_value.with_for_update.return_value.one_or_none.return_value = None

    mock_session = MagicMock()
    mock_session.query.return_value = mock_change_query

    with pytest.raises(ValueError, match="invalid or used"):
        verify_email_change(mock_session, "nonexistent-token")


def test_verify_email_change_dup_email_race():
    """new_email 已被其他 account 占用 → 拒绝.

    模拟: 发起 email_change 时 new_email 可用, verify 时已被占.
    """
    change = _make_valid_change()
    existing_account = MagicMock(id=99, email="new@x.com")

    mock_change_query = MagicMock()
    mock_change_query.filter_by.return_value.with_for_update.return_value.one_or_none.return_value = change

    mock_dup_query = MagicMock()
    mock_dup_query.filter.return_value.first.return_value = existing_account

    mock_session = MagicMock()
    mock_session.query.side_effect = [mock_change_query, mock_dup_query]

    with pytest.raises(ValueError, match="email already in use"):
        verify_email_change(mock_session, "valid-token")
