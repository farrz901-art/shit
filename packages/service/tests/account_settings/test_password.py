"""模式 1 纯单测: PATCH /password 业务逻辑"""

from unittest.mock import MagicMock, patch

import pytest

from src.auth.account_settings_service import change_password


def test_change_password_hashes_new_password():
    """正常路径: 改密码 → hash → 写 account.password_hash"""
    mock_session = MagicMock()
    mock_account = MagicMock(password_hash="old_hash")
    with patch("src.auth.account_settings_service.verify_password", return_value=True):
        with patch("src.auth.account_settings_service.hash_password", return_value="new_hash") as mock_hash:
            change_password(mock_session, mock_account, "old", "newpass123", "newpass123")
    assert mock_account.password_hash == "new_hash"
    mock_hash.assert_called_once_with("newpass123")
    mock_session.flush.assert_called_once()


def test_change_password_rejects_wrong_current():
    """当前密码错 → 拒绝"""
    mock_session = MagicMock()
    mock_account = MagicMock()
    with patch("src.auth.account_settings_service.verify_password", return_value=False):
        with pytest.raises(ValueError, match="invalid current password"):
            change_password(mock_session, mock_account, "wrong", "newpass123", "newpass123")


def test_change_password_rejects_mismatched_confirm():
    """新密码 != 确认密码 → 拒绝"""
    mock_session = MagicMock()
    mock_account = MagicMock()
    with patch("src.auth.account_settings_service.verify_password", return_value=True):
        with pytest.raises(ValueError, match="passwords do not match"):
            change_password(mock_session, mock_account, "old", "newpass123", "different")


def test_change_password_rejects_too_short():
    """新密码 < 8 字符 → 拒绝"""
    mock_session = MagicMock()
    mock_account = MagicMock()
    with patch("src.auth.account_settings_service.verify_password", return_value=True):
        with pytest.raises(ValueError, match="at least"):
            change_password(mock_session, mock_account, "old", "short", "short")
