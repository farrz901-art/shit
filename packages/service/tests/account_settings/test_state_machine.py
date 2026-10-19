"""模式 1 纯单测: require_active_account 守卫 + 状态机集成"""

from datetime import datetime, timedelta
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from src.auth.account_settings_service import purge_pending_deletions
from src.permissions.guards import require_active_account


def test_require_active_account_rejects_inactive_user():
    """is_active=False → 403 'account disabled' (跟 pending_deletion 区分)"""
    mock_user = MagicMock(is_active=False, is_pending_deletion=False)
    with pytest.raises(HTTPException) as exc_info:
        require_active_account(user=mock_user)
    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "account disabled"


def test_require_active_account_rejects_pending_deletion():
    """is_pending_deletion=True → 403"""
    mock_user = MagicMock(is_active=True, is_pending_deletion=True)
    with pytest.raises(HTTPException) as exc_info:
        require_active_account(user=mock_user)
    assert exc_info.value.status_code == 403


def test_require_active_account_allows_normal_user():
    """is_active=True + not pending → 返 user"""
    mock_user = MagicMock(is_active=True, is_pending_deletion=False)
    result = require_active_account(user=mock_user)
    assert result is mock_user


def test_require_active_account_rejects_both_inactive_and_pending():
    """is_active=False + is_pending_deletion=True → 403"""
    mock_user = MagicMock(is_active=False, is_pending_deletion=True)
    with pytest.raises(HTTPException) as exc_info:
        require_active_account(user=mock_user)
    assert exc_info.value.status_code == 403


def test_purge_anonymizes_user_and_deletes_account():
    """T5.1: 7 天到期的 pending_deletion → anonymize User + 删 Account (CASCADE).

    CON-002 修复: 加 with_for_update(skip_locked=True) + 锁内 is_pending_deletion/is_active 二次校验.
    """
    # 8 天前申请的 account (超 7 天宽限期)
    # 显式设 is_pending_deletion=True + is_active=False 满足新防御性 check
    mock_account = MagicMock(
        id=1,
        deletion_requested_at=datetime.now() - timedelta(days=8),
        is_pending_deletion=True,
        is_active=False,
    )
    # 关联 user: 解绑 + 重置 token + 匿名化 display_name
    mock_user = MagicMock(
        id=10,
        account_id=1,
        public_token="old_token",
        display_name="Alice",
    )

    # query chain (CON-002): query(Account).filter(...).filter(...).with_for_update(skip_locked=True).all()
    # → [mock_account]
    mock_account_query = MagicMock()
    mock_account_query.filter.return_value.filter.return_value.with_for_update.return_value.all.return_value = [
        mock_account
    ]

    # query(User).filter_by(account_id=...).first() → mock_user
    mock_user_query = MagicMock()
    mock_user_query.filter_by.return_value.first.return_value = mock_user

    # 按调用顺序 dispatch: 1st query(Account), 2nd query(User)
    mock_session = MagicMock()
    mock_session.query.side_effect = [mock_account_query, mock_user_query]

    count = purge_pending_deletions(mock_session)
    assert count == 1
    # 验证 anonymize: 解绑 + token 重置 + display_name 匿名化
    assert mock_user.account_id is None
    assert mock_user.public_token != "old_token"
    assert len(mock_user.public_token) == 64  # 32 字节 hex
    assert "已注销" in mock_user.display_name
    assert "#10" in mock_user.display_name
    # 验证删 account (CASCADE 由 FK 触发, 业务层只删 Account)
    mock_session.delete.assert_called_once_with(mock_account)
    mock_session.flush.assert_called_once()


def test_purge_no_victims_returns_zero():
    """T5.1: 没到期账号 → 返 0, 不动 user, 不删 account."""
    # 空 victim 列表
    mock_account_query = MagicMock()
    mock_account_query.filter.return_value.filter.return_value.with_for_update.return_value.all.return_value = []

    mock_session = MagicMock()
    mock_session.query.return_value = mock_account_query

    count = purge_pending_deletions(mock_session)
    assert count == 0
    mock_session.delete.assert_not_called()
    mock_session.flush.assert_not_called()


def test_purge_account_without_associated_user_is_silent():
    """T5.1: 账号无关联 user (老匿名场景) → 静默删 account, 不抛错."""
    mock_account = MagicMock(
        id=99,
        deletion_requested_at=datetime.now() - timedelta(days=10),
        is_pending_deletion=True,
        is_active=False,
    )

    mock_account_query = MagicMock()
    mock_account_query.filter.return_value.filter.return_value.with_for_update.return_value.all.return_value = [
        mock_account
    ]

    # query(User).filter_by(...).first() → None
    mock_user_query = MagicMock()
    mock_user_query.filter_by.return_value.first.return_value = None

    mock_session = MagicMock()
    mock_session.query.side_effect = [mock_account_query, mock_user_query]

    count = purge_pending_deletions(mock_session)
    assert count == 1
    # account 仍然被删 (FK ON DELETE SET NULL 让 user 解绑, 不抛错)
    mock_session.delete.assert_called_once_with(mock_account)
    mock_session.flush.assert_called_once()
