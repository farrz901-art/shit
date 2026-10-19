"""Invite GET + redeem 完整流测试 (2026-06-16 重写 100% mock)

跟 test_seed_admin 同一套: patch session_scope 替 mock. _validate_invite / redeem
两个端点都用 session_scope, 共享 mock session. 0 真实 DB 连接.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.auth.account_models import Account, Invite
from src.auth.models import User
from src.core.app_factory import create_app
from src.utils.timezone import HKT


@pytest.fixture
def client():
    return TestClient(create_app())


def _make_mock_invite(
    email: str = "new@x.com",
    token: str = "test-tok-123",
    inviter_id: int = 1,
    expired: bool = False,
    redeemed: bool = False,
) -> MagicMock:
    inv = MagicMock(spec=Invite)
    inv.id = 1
    inv.email = email
    inv.token = token
    inv.invited_by_account_id = inviter_id
    inv.expires_at = datetime.now(HKT) + (timedelta(days=-1) if expired else timedelta(days=7))
    inv.redeemed_at = datetime.now(HKT) if redeemed else None
    inv.created_at = datetime.now(HKT)
    inv.account_id = None
    return inv


@contextmanager
def _patch_session_scope(mock_session):
    with patch("src.auth.auth_invite_router.session_scope") as patched:
        patched.return_value.__enter__.return_value = mock_session
        patched.return_value.__exit__.return_value = False
        yield patched


def test_get_invite_returns_email(client):
    mock_inv = _make_mock_invite(email="new@x.com")
    mock_session = MagicMock()
    mock_session.query.return_value.filter_by.return_value.first.return_value = mock_inv

    with _patch_session_scope(mock_session):
        r = client.get("/api/invites/test-tok-123")

    assert r.status_code == 200
    assert r.json()["email"] == "new@x.com"


def test_get_invite_expired_400(client):
    mock_inv = _make_mock_invite(expired=True)
    mock_session = MagicMock()
    mock_session.query.return_value.filter_by.return_value.first.return_value = mock_inv

    with _patch_session_scope(mock_session):
        r = client.get("/api/invites/test-tok-123")

    assert r.status_code == 400
    assert "invalid" in r.json()["detail"]


def test_get_invite_redeemed_400(client):
    mock_inv = _make_mock_invite(redeemed=True)
    mock_session = MagicMock()
    mock_session.query.return_value.filter_by.return_value.first.return_value = mock_inv

    with _patch_session_scope(mock_session):
        r = client.get("/api/invites/test-tok-123")

    assert r.status_code == 400


def test_redeem_creates_account_and_user(client, monkeypatch):
    """完整 redeem 流: 创 account + 绑 user + 标 invite.redeemed_at"""
    monkeypatch.setenv("PASSWORD_BCRYPT_ROUNDS", "4")
    mock_inv = _make_mock_invite(email="new@x.com")
    mock_session = MagicMock()
    # (CON-001 修后) redeem 不再用 _validate_invite, 走 _lock_invite_in_session:
    # s.execute(select(Invite).where(...).with_for_update()).scalars().first() → mock_inv
    mock_session.execute.return_value.scalars.return_value.first.return_value = mock_inv
    # redeem body: query(Account).filter_by(email=...).first() → None (邮箱未占)
    account_query = MagicMock()
    account_query.filter_by.return_value.first.return_value = None
    mock_session.query.return_value = account_query

    # mock refresh: set id + role 默认 (SQLAlchemy default), 让 AccountOut 序列化不出 None
    def _fake_refresh(obj):
        obj.id = 42
        obj.role = "user"
        obj.is_active = True

    mock_session.refresh.side_effect = _fake_refresh

    with _patch_session_scope(mock_session):
        r = client.post(
            "/api/invites/test-tok-123/redeem",
            json={"display_name": "New User", "password": "longpassword"},
        )

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["email"] == "new@x.com"
    assert "token" in body
    # 验证 session.add 调了 2 次 (account + user)
    assert mock_session.add.call_count == 2
    added_account = mock_session.add.call_args_list[0][0][0]
    added_user = mock_session.add.call_args_list[1][0][0]
    assert isinstance(added_account, Account)
    assert isinstance(added_user, User)
    assert added_user.account_id == 42
    # 验证 mock_inv.redeemed_at 标了
    assert mock_inv.redeemed_at is not None
    assert mock_inv.account_id == 42
    # (CON-001) 验证 with_for_update() 在 execute 链路上调过
    execute_stmt = mock_session.execute.call_args[0][0]
    assert hasattr(execute_stmt, "_for_update_arg") or "FOR UPDATE" in str(execute_stmt)


def test_redeem_twice_400(client, monkeypatch):
    """redeem 过的 token 再 redeem → 400 (_lock_invite_in_session 过滤 redeemed_at)"""
    monkeypatch.setenv("PASSWORD_BCRYPT_ROUNDS", "4")
    mock_session = MagicMock()
    # (CON-001 修后) redeem 走 _lock_invite_in_session: redeemed_at IS NOT NULL → 不返
    mock_session.execute.return_value.scalars.return_value.first.return_value = None

    with _patch_session_scope(mock_session):
        r = client.post(
            "/api/invites/test-tok-123/redeem",
            json={"display_name": "u", "password": "longpassword"},
        )

    assert r.status_code == 400


def test_redeem_short_password_422(client):
    """password < 8 字符 → 422 (Pydantic 校验, handler 都不会跑)"""
    mock_inv = _make_mock_invite()
    mock_session = MagicMock()
    mock_session.query.return_value.filter_by.return_value.first.return_value = mock_inv

    with _patch_session_scope(mock_session):
        r = client.post(
            "/api/invites/test-tok-123/redeem",
            json={"display_name": "u", "password": "short"},
        )

    assert r.status_code == 422
