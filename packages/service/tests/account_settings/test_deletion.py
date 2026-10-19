"""模式 1 纯单测: 注销 + 撤销 + 查状态 业务逻辑"""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from src.auth.account_settings_service import (
    DELETION_GRACE_DAYS,
    cancel_deletion,
    get_deletion_status,
    request_deletion,
)


def test_request_deletion_marks_account_pending():
    """申请注销: 校验密码 + confirm_text → is_active=False, deletion_requested_at=now, 创 DeletionRestore"""
    mock_account = MagicMock(id=1, is_active=True, is_pending_deletion=False, deletion_requested_at=None)
    mock_session = MagicMock()
    with patch("src.auth.account_settings_service.verify_password", return_value=True):
        result = request_deletion(mock_session, mock_account, "pw", "我要注销")
    assert mock_account.is_active is False
    assert mock_account.deletion_requested_at is not None
    assert "restore_url" in result
    assert "deletion_requested_at" in result
    assert "expires_at" in result
    # 验证 session.add(DeletionRestore) was called
    added = mock_session.add.call_args[0][0]
    assert added.account_id == 1
    assert added.token  # 64 hex chars
    # 验证 session.flush
    mock_session.flush.assert_called_once()


def test_request_deletion_rejects_wrong_password():
    mock_account = MagicMock()
    with patch("src.auth.account_settings_service.verify_password", return_value=False):
        with pytest.raises(ValueError, match="invalid current password"):
            request_deletion(MagicMock(), mock_account, "wrong", "我要注销")


def test_request_deletion_rejects_bad_confirm_text():
    """confirm_text 必须字面等于 '我要注销'"""
    mock_account = MagicMock()
    with patch("src.auth.account_settings_service.verify_password", return_value=True):
        with pytest.raises(ValueError, match="confirm text"):
            request_deletion(MagicMock(), mock_account, "pw", "我同意")


def test_request_deletion_rejects_already_pending():
    """已 pending 状态 → 拒绝 (避免重置 deletion_requested_at)"""
    mock_account = MagicMock(is_pending_deletion=True)
    with patch("src.auth.account_settings_service.verify_password", return_value=True):
        with pytest.raises(ValueError, match="already pending"):
            request_deletion(MagicMock(), mock_account, "pw", "我要注销")


def test_cancel_deletion_restores_active():
    """撤销注销: 校验密码 + 必须在 pending 状态 → is_active=True, deletion_requested_at=None, 标 DeletionRestore.used_at.

    CON-002 修复: session.query 被调 2 次 — 1st: Account.with_for_update() 锁行,
    2nd: DeletionRestore.filter_by().all() 标 used_at. mock chain 按调用顺序 dispatch.
    """
    mock_account = MagicMock(
        id=1,
        is_active=False,
        is_pending_deletion=True,
        deletion_requested_at=datetime.now(),
    )
    mock_session = MagicMock()

    # 1st call: session.query(Account).filter(Account.id == ...).with_for_update().one_or_none()
    # → 返 locked_account (复用 mock_account MagicMock 模拟同一行)
    mock_account_query = MagicMock()
    mock_account_query.filter.return_value.with_for_update.return_value.one_or_none.return_value = mock_account

    # 2nd call: session.query(DeletionRestore).filter_by(account_id=..., used_at=None).all() → 2 个未用 token
    mock_token1 = MagicMock(used_at=None)
    mock_token2 = MagicMock(used_at=None)
    mock_restore_query = MagicMock()
    mock_restore_query.filter_by.return_value.all.return_value = [mock_token1, mock_token2]

    # 按调用顺序 dispatch
    mock_session.query.side_effect = [mock_account_query, mock_restore_query]

    with patch("src.auth.account_settings_service.verify_password", return_value=True):
        cancel_deletion(mock_session, mock_account, "pw")
    assert mock_account.is_active is True
    assert mock_account.deletion_requested_at is None
    assert mock_token1.used_at is not None
    assert mock_token2.used_at is not None
    mock_session.flush.assert_called_once()


def test_cancel_deletion_rejects_not_pending():
    """不在 pending 状态 → 拒绝"""
    mock_account = MagicMock(is_pending_deletion=False)
    with patch("src.auth.account_settings_service.verify_password", return_value=True):
        with pytest.raises(ValueError, match="not pending"):
            cancel_deletion(MagicMock(), mock_account, "pw")


def test_cancel_deletion_rejects_wrong_password():
    mock_account = MagicMock(is_pending_deletion=True)
    with patch("src.auth.account_settings_service.verify_password", return_value=False):
        with pytest.raises(ValueError, match="invalid current password"):
            cancel_deletion(MagicMock(), mock_account, "wrong")


def test_get_deletion_status_when_not_pending():
    """未申请 → pending=False"""
    mock_account = MagicMock(is_pending_deletion=False)
    result = get_deletion_status(mock_account)
    assert result == {"pending": False}


def test_get_deletion_status_when_pending():
    """已申请 → pending=True + deletion_requested_at + expires_at (跟 deletion_requested_at 差 DELETION_GRACE_DAYS)"""
    now = datetime.now()
    mock_account = MagicMock(
        is_pending_deletion=True,
        deletion_requested_at=now,
    )
    result = get_deletion_status(mock_account)
    assert result["pending"] is True
    assert result["deletion_requested_at"] == now
    # expires_at = deletion_requested_at + DELETION_GRACE_DAYS (具体值, 不是只 in)
    assert result["expires_at"] == now + timedelta(days=DELETION_GRACE_DAYS)


def test_request_deletion_rejects_whitespace_padded_confirm_text():
    """confirm_text 必须是字面 '我要注销', 不接受前后空格 (per spec '字面等于')"""
    mock_account = MagicMock()
    with patch("src.auth.account_settings_service.verify_password", return_value=True):
        with pytest.raises(ValueError, match="confirm text"):
            request_deletion(MagicMock(), mock_account, "pw", "  我要注销  ")
