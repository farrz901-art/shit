"""模式 1 纯单测: 验 update_profile 业务逻辑 (mock session)"""

from unittest.mock import MagicMock

import pytest

from src.auth.account_settings_service import update_profile


def test_update_profile_changes_display_name():
    mock_account = MagicMock()
    mock_account.display_name = "old"
    mock_session = MagicMock()
    update_profile(mock_session, mock_account, display_name="new")
    assert mock_account.display_name == "new"
    mock_session.flush.assert_called_once()


def test_update_profile_rejects_too_long_display_name():
    mock_account = MagicMock()
    mock_session = MagicMock()
    with pytest.raises(ValueError, match="display_name must be 1-50"):
        update_profile(mock_session, mock_account, display_name="x" * 51)


def test_update_profile_rejects_empty_after_strip():
    mock_account = MagicMock()
    mock_session = MagicMock()
    with pytest.raises(ValueError, match="display_name must be 1-50"):
        update_profile(mock_session, mock_account, display_name="   ")


def test_update_profile_strips_whitespace():
    mock_account = MagicMock()
    mock_session = MagicMock()
    update_profile(mock_session, mock_account, display_name="  hello  ")
    assert mock_account.display_name == "hello"
