"""POST /api/account/seed-admin — 首次创 admin 账号 (RAG_ADMIN_TOKEN 鉴权)

(2026-06-16) 重写 100% mock. 跟 test_login.py 同一套: TestClient + patch session_scope
+ MagicMock query/add. 0 真实 DB 连接, 跟 CLAUDE.md 强制规则一致.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.auth.account_models import Account
from src.auth.account_service import hash_password
from src.auth.models import User
from src.core.app_factory import create_app
from src.utils.timezone import HKT


@pytest.fixture
def client():
    return TestClient(create_app())


def _make_mock_account(
    email: str = "existing@x.com",
    password: str = "longpassword",
    role: str = "super_admin",
) -> MagicMock:
    a = MagicMock(spec=Account)
    a.id = 1
    a.email = email
    a.password_hash = hash_password(password)
    a.role = role
    a.display_name = "existing"
    a.created_at = datetime.now(HKT)
    return a


@contextmanager
def _patch_session_scope(mock_session):
    with patch("src.auth.auth_account_router.session_scope") as patched:
        patched.return_value.__enter__.return_value = mock_session
        patched.return_value.__exit__.return_value = False
        yield patched


def test_seed_admin_creates_account_and_user(client, monkeypatch):
    """首次: 创 account (role=super_admin) + 绑 user 行"""
    monkeypatch.setenv("RAG_ADMIN_TOKEN", "env-secret")
    monkeypatch.setenv("PASSWORD_BCRYPT_ROUNDS", "4")

    mock_session = MagicMock()
    # 1) query(role=super_admin).first() → None (无 admin)
    # 2) query(email=req.email).first() → None (邮箱未占)
    admin_query = MagicMock()
    admin_query.filter_by.return_value.first.return_value = None
    email_query = MagicMock()
    email_query.filter_by.return_value.first.return_value = None
    mock_session.query.side_effect = [admin_query, email_query]
    # router 用 local `account` 变量构造响应, 不是 session.add() 的返回值.
    # mock s.refresh(account) 触发后设 id, 模拟 DB autoincrement.
    mock_session.refresh.side_effect = lambda obj: setattr(obj, "id", 42)

    with _patch_session_scope(mock_session):
        r = client.post(
            "/api/account/seed-admin",
            json={"email": "first@x.com", "password": "longpassword", "display_name": "Boss"},
            headers={"x-admin-token": "env-secret"},
        )

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["email"] == "first@x.com"
    assert body["account_id"] == 42
    # 验证 router 调了 session.add(account) + session.add(user)
    assert mock_session.add.call_count == 2
    added_account = mock_session.add.call_args_list[0][0][0]
    added_user = mock_session.add.call_args_list[1][0][0]
    assert isinstance(added_account, Account)
    assert isinstance(added_user, User)
    assert added_user.account_id == 42


def test_seed_admin_blocked_when_admin_exists(client, monkeypatch):
    """已经有 super_admin account → 409"""
    monkeypatch.setenv("RAG_ADMIN_TOKEN", "env-secret")
    monkeypatch.setenv("PASSWORD_BCRYPT_ROUNDS", "4")

    mock_session = MagicMock()
    existing_admin = _make_mock_account(email="existing@x.com", role="super_admin")
    admin_query = MagicMock()
    admin_query.filter_by.return_value.first.return_value = existing_admin
    mock_session.query.return_value = admin_query

    with _patch_session_scope(mock_session):
        r = client.post(
            "/api/account/seed-admin",
            json={"email": "second@x.com", "password": "longpassword"},
            headers={"x-admin-token": "env-secret"},
        )

    assert r.status_code == 409
    assert "initialized" in r.json()["detail"]


def test_seed_admin_wrong_token_401(client, monkeypatch):
    """RAG_ADMIN_TOKEN 不匹配 → 401"""
    monkeypatch.setenv("RAG_ADMIN_TOKEN", "env-secret")
    r = client.post(
        "/api/account/seed-admin",
        json={"email": "x@x.com", "password": "longpassword"},
        headers={"x-admin-token": "WRONG"},
    )
    assert r.status_code == 401


def test_seed_admin_duplicate_email_409(client, monkeypatch):
    """email 已被非 admin 占用 → 409 (避免覆盖)"""
    monkeypatch.setenv("RAG_ADMIN_TOKEN", "env-secret")
    monkeypatch.setenv("PASSWORD_BCRYPT_ROUNDS", "4")

    mock_session = MagicMock()
    # 1) query(role=super_admin).first() → None (无 admin)
    # 2) query(email=req.email).first() → existing dup account (409)
    admin_query = MagicMock()
    admin_query.filter_by.return_value.first.return_value = None
    existing_dup = _make_mock_account(email="dup@x.com", role="user")
    email_query = MagicMock()
    email_query.filter_by.return_value.first.return_value = existing_dup
    mock_session.query.side_effect = [admin_query, email_query]

    with _patch_session_scope(mock_session):
        r = client.post(
            "/api/account/seed-admin",
            json={"email": "dup@x.com", "password": "longpassword"},
            headers={"x-admin-token": "env-secret"},
        )

    assert r.status_code == 409
