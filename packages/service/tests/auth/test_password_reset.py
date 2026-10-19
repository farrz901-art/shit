"""forgot/reset password 流程测试 (2026-06-16 重写 100% mock)

跟 test_seed_admin 同一套: patch session_scope 替 mock. 0 真实 DB 连接.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.auth.account_models import Account, PasswordReset
from src.auth.account_service import hash_password, verify_password
from src.core.app_factory import create_app
from src.utils.timezone import HKT


@pytest.fixture
def client():
    return TestClient(create_app())


def _make_mock_account(
    account_id: int = 10,
    email: str = "x@x.com",
    password: str = "oldpassword",
) -> MagicMock:
    a = MagicMock(spec=Account)
    a.id = account_id
    a.email = email
    a.password_hash = hash_password(password)
    a.is_admin = False
    a.is_active = True
    a.display_name = "x"
    a.created_at = datetime.now(HKT)
    return a


def _make_mock_reset(
    account_id: int = 10,
    token: str = "rst-1",
    expires_at: datetime | None = None,
    used_at: datetime | None = None,
) -> MagicMock:
    rs = MagicMock(spec=PasswordReset)
    rs.id = 1
    rs.account_id = account_id
    rs.token = token
    rs.expires_at = expires_at or datetime.now(HKT) + timedelta(hours=1)
    rs.used_at = used_at
    rs.created_at = datetime.now(HKT)
    return rs


@contextmanager
def _patch_session_scope(mock_session):
    with patch("src.auth.auth_account_router.session_scope") as patched:
        patched.return_value.__enter__.return_value = mock_session
        patched.return_value.__exit__.return_value = False
        yield patched


def test_forgot_existing_email_returns_reset_url(client, monkeypatch):
    """存在 email → 200 + 返 reset_token + reset_url"""
    monkeypatch.setenv("PASSWORD_BCRYPT_ROUNDS", "4")
    mock_account = _make_mock_account()
    mock_session = MagicMock()
    # s.query(Account).filter_by(email=...).first() → mock_account
    mock_session.query.return_value.filter_by.return_value.first.return_value = mock_account

    with _patch_session_scope(mock_session):
        r = client.post("/api/account/forgot-password", json={"email": "x@x.com"})

    assert r.status_code == 200
    body = r.json()
    assert "reset_token" in body
    assert "reset_url" in body
    # 验证 router 调了 session.add(PasswordReset(...))
    assert mock_session.add.called
    added_reset = mock_session.add.call_args[0][0]
    assert isinstance(added_reset, PasswordReset)
    assert added_reset.account_id == 10


def test_forgot_unknown_email_returns_generic(client):
    """不存在 email → 200 (不暴露邮箱存在)"""
    mock_session = MagicMock()
    mock_session.query.return_value.filter_by.return_value.first.return_value = None

    with _patch_session_scope(mock_session):
        r = client.post("/api/account/forgot-password", json={"email": "nobody@x.com"})

    assert r.status_code == 200
    body = r.json()
    assert body.get("reset_url") is None
    assert body.get("reset_token") is None


def test_reset_with_valid_token_changes_password(client, monkeypatch):
    """valid token → 200, account.password_hash 更新, rs.used_at 标"""
    monkeypatch.setenv("PASSWORD_BCRYPT_ROUNDS", "4")
    mock_account = _make_mock_account(password="oldpassword")
    mock_reset = _make_mock_reset(token="rst-1")
    mock_session = MagicMock()
    # 1) s.query(PasswordReset).filter_by(token=...).first() → mock_reset
    # 2) s.get(Account, 10) → mock_account
    # 3) s.query(User).filter_by(account_id=...).first() → mock_user (token cache invalidation)
    mock_user = MagicMock(public_token="utok-1")
    pwreset_query = MagicMock()
    pwreset_query.filter_by.return_value.first.return_value = mock_reset
    user_query = MagicMock()
    user_query.filter_by.return_value.first.return_value = mock_user
    mock_session.query.side_effect = [pwreset_query, user_query]
    mock_session.get.return_value = mock_account

    with _patch_session_scope(mock_session):
        r = client.post(
            "/api/account/reset-password",
            json={"token": "rst-1", "new_password": "newpassword"},
        )

    assert r.status_code == 200
    # 验证 account.password_hash 变了 (用真 verify 跟 mock 上设的值比)
    assert mock_account.password_hash != hash_password("oldpassword")
    assert verify_password("newpassword", mock_account.password_hash) is True
    # 验证 rs.used_at 标了
    assert mock_reset.used_at is not None


def test_reset_expired_token_400(client, monkeypatch):
    """expired token → 400 'reset token invalid'"""
    monkeypatch.setenv("PASSWORD_BCRYPT_ROUNDS", "4")
    mock_reset = _make_mock_reset(
        token="rst-exp",
        expires_at=datetime.now(HKT) - timedelta(hours=1),  # 已过期
    )
    mock_session = MagicMock()
    mock_session.query.return_value.filter_by.return_value.first.return_value = mock_reset

    with _patch_session_scope(mock_session):
        r = client.post(
            "/api/account/reset-password",
            json={"token": "rst-exp", "new_password": "newpassword"},
        )

    assert r.status_code == 400
    assert "invalid" in r.json()["detail"]


def test_reset_used_token_400(client, monkeypatch):
    """used token (rs.used_at 已有值) → 400"""
    monkeypatch.setenv("PASSWORD_BCRYPT_ROUNDS", "4")
    mock_reset = _make_mock_reset(
        token="rst-used",
        expires_at=datetime.now(HKT) + timedelta(hours=1),
        used_at=datetime.now(HKT),  # 已用过
    )
    mock_session = MagicMock()
    mock_session.query.return_value.filter_by.return_value.first.return_value = mock_reset

    with _patch_session_scope(mock_session):
        r = client.post(
            "/api/account/reset-password",
            json={"token": "rst-used", "new_password": "newpassword"},
        )

    assert r.status_code == 400
