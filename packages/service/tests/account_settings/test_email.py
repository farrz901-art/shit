"""模式 1 纯单测: PATCH /email + POST /email/verify 业务逻辑"""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from src.auth.account_settings_service import request_email_change, verify_email_change


def test_request_email_change_creates_token():
    """请求改邮箱: 校验密码 → 创 EmailChange → 返 verification_url"""
    mock_account = MagicMock(id=1, email="old@x.com", password_hash="h")
    mock_session = MagicMock()
    # query(Account).filter(...).first() = None (新邮箱未被占)
    mock_session.query.return_value.filter.return_value.first.return_value = None
    # add() + flush() 都应被调
    with patch("src.auth.account_settings_service.verify_password", return_value=True):
        result = request_email_change(mock_session, mock_account, "new@x.com", "pw")
    assert result["new_email"] == "new@x.com"
    assert "verification_url" in result
    assert "expires_at" in result
    # verify session.add(EmailChange) was called
    added = mock_session.add.call_args[0][0]
    assert added.new_email == "new@x.com"
    assert added.token  # token 64 字符 hex


def test_request_email_change_rejects_wrong_current_password():
    mock_account = MagicMock(email="old@x.com", password_hash="h")
    mock_session = MagicMock()
    with patch("src.auth.account_settings_service.verify_password", return_value=False):
        with pytest.raises(ValueError, match="invalid current password"):
            request_email_change(mock_session, mock_account, "new@x.com", "wrong")


def test_request_email_change_rejects_duplicate_email():
    """新邮箱已被其他 account 占用 → 拒绝"""
    mock_account = MagicMock(id=1, email="old@x.com", password_hash="h")
    mock_existing = MagicMock(id=99, email="new@x.com")
    mock_session = MagicMock()
    # query(Account).filter(...).first() = mock_existing (邮箱被占)
    mock_session.query.return_value.filter.return_value.first.return_value = mock_existing
    with patch("src.auth.account_settings_service.verify_password", return_value=True):
        with pytest.raises(ValueError, match="email already in use"):
            request_email_change(mock_session, mock_account, "new@x.com", "pw")


def test_verify_email_change_switches_email_and_marks_used():
    """验证 token: 切换 email + 标 used_at"""
    # Distinct child mocks for each query() call (robust to reordering)
    mock_change = MagicMock()
    mock_change.account_id = 1
    mock_change.new_email = "new@x.com"
    mock_change.used_at = None
    mock_change.expires_at = datetime.now() + timedelta(days=7)
    mock_account = MagicMock(id=1, email="old@x.com")

    # First query: EmailChange lookup → with_for_update().one_or_none() (CON-003 防 TOCTOU)
    email_query_mock = MagicMock()
    email_query_mock.filter_by.return_value.with_for_update.return_value.one_or_none.return_value = mock_change
    # Second query: Account uniqueness check → .filter(...).first() = None
    account_query_mock = MagicMock()
    account_query_mock.filter.return_value.first.return_value = None
    # Third query: Account row lock → .filter(...).with_for_update().one_or_none()
    account_lock_mock = MagicMock()
    account_lock_mock.filter.return_value.with_for_update.return_value.one_or_none.return_value = mock_account

    mock_session = MagicMock()
    mock_session.query.side_effect = [email_query_mock, account_query_mock, account_lock_mock]

    result = verify_email_change(mock_session, "token123")
    assert result["email"] == "new@x.com"
    assert mock_account.email == "new@x.com"
    assert mock_change.used_at is not None


def test_verify_email_change_rejects_used_token():
    """token 已 used_at → 拒绝"""
    mock_change = MagicMock(used_at=datetime.now(), expires_at=datetime.now() + timedelta(days=7))
    mock_session = MagicMock()
    mock_session.query.return_value.filter_by.return_value.with_for_update.return_value.one_or_none.return_value = (
        mock_change
    )
    with pytest.raises(ValueError, match="invalid or used token"):
        verify_email_change(mock_session, "token123")


def test_verify_email_change_rejects_expired_token():
    """token 已过期 → 拒绝"""
    mock_change = MagicMock(used_at=None, expires_at=datetime.now() - timedelta(days=1))
    mock_session = MagicMock()
    mock_session.query.return_value.filter_by.return_value.with_for_update.return_value.one_or_none.return_value = (
        mock_change
    )
    with pytest.raises(ValueError, match="token expired"):
        verify_email_change(mock_session, "token123")


def test_verify_email_change_rejects_nonexistent_token():
    """token 不存在 → 拒绝"""
    mock_session = MagicMock()
    mock_session.query.return_value.filter_by.return_value.with_for_update.return_value.one_or_none.return_value = None
    with pytest.raises(ValueError, match="invalid or used token"):
        verify_email_change(mock_session, "nonexistent")
