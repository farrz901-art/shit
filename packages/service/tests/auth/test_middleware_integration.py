"""resolve_user 集成测试 — 3 身份路径 (2026-06-16 重写 100% mock)

跟 test_seed_admin 同一套: patch src.middleware.auth.session_scope 替 mock session,
mock query 结果. 0 真实 DB 连接, 跟 CLAUDE.md 强制规则一致.
"""

from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from src.auth.account_models import Account
from src.auth.models import User
from src.middleware.auth import CurrentUser, resolve_user


@pytest.fixture
def app():
    a = FastAPI()

    @a.get("/whoami")
    def whoami(user: CurrentUser = Depends(resolve_user)):
        return {
            "id": user.id,
            "is_admin": user.is_admin,
            "is_account": user.is_account,
            "account_id": user.account_id,
            "email": user.email,
            "is_active": user.is_active,
        }

    return a


def _make_user(public_token: str, account_id: int | None = None) -> MagicMock:
    u = MagicMock(spec=User)
    u.id = 1
    u.public_token = public_token
    u.account_id = account_id
    u.display_name = "anon" if account_id is None else "bob"
    return u


def _make_account(email: str = "bob@x.com", is_active: bool = True) -> MagicMock:
    a = MagicMock(spec=Account)
    a.id = 10
    a.email = email
    a.role = "super_admin"  # (2026-06-17) 替原 is_admin=True
    a.is_active = is_active
    a.display_name = "bob"
    # (2026-06-17 T2.5) 新加字段同步, 否则 spec 不含时 resolve_user 拿到 MagicMock
    a.avatar_url = None
    a.deletion_requested_at = None
    a.is_pending_deletion = False  # @property, MagicMock(spec) 不会自动派生
    return a


@contextmanager
def _patch_resolve_user_session(mock_session):
    """patch src.middleware.auth.session_scope 返 mock_session (resolve_user 用同一个 session_scope).

    注: resolve_user 内 2 次 query, 第 1 次查 User, 第 2 次查 Account.
    """
    with patch("src.middleware.auth.session_scope") as patched:
        patched.return_value.__enter__.return_value = mock_session
        patched.return_value.__exit__.return_value = False
        yield patched


def test_anon_path(app):
    """anon token (user.account_id is null) → is_account=False"""
    anon_user = _make_user(public_token="anon-t", account_id=None)
    mock_session = MagicMock()
    mock_session.query.return_value.filter_by.return_value.first.return_value = anon_user

    with _patch_resolve_user_session(mock_session):
        c = TestClient(app)
        r = c.get("/whoami", headers={"x-user-token": "anon-t"})

    assert r.status_code == 200
    body = r.json()
    assert body["is_account"] is False
    assert body["is_admin"] is False
    assert body["email"] is None


def test_account_path(app, monkeypatch):
    """真账号 → is_account=True + email + is_admin"""
    monkeypatch.setenv("PASSWORD_BCRYPT_ROUNDS", "4")
    acc_user = _make_user(public_token="acc-t", account_id=10)
    acc_account = _make_account(email="bob@x.com", is_active=True)
    mock_session = MagicMock()
    # 1) User query → acc_user; 2) Account.get(id=10) → acc_account
    user_query = MagicMock()
    user_query.filter_by.return_value.first.return_value = acc_user
    account_session = MagicMock()
    account_session.get.return_value = acc_account
    mock_session.query.return_value = user_query
    mock_session.get.return_value = acc_account
    # resolve_user 调 2 次 session_scope (User query + Account.get), 2 次都返 mock_session

    with _patch_resolve_user_session(mock_session):
        c = TestClient(app)
        r = c.get("/whoami", headers={"x-user-token": "acc-t"})

    assert r.status_code == 200
    body = r.json()
    assert body["is_account"] is True
    assert body["is_admin"] is True
    assert body["email"] == "bob@x.com"
    assert body["account_id"] == 10


def test_disabled_account_401(app, monkeypatch):
    """is_active=False 账号 → 401 'account disabled'"""
    monkeypatch.setenv("PASSWORD_BCRYPT_ROUNDS", "4")
    acc_user = _make_user(public_token="acc-t", account_id=10)
    disabled_account = _make_account(email="x@x.com", is_active=False)
    mock_session = MagicMock()
    user_query = MagicMock()
    user_query.filter_by.return_value.first.return_value = acc_user
    mock_session.query.return_value = user_query
    mock_session.get.return_value = disabled_account

    with _patch_resolve_user_session(mock_session):
        c = TestClient(app)
        r = c.get("/whoami", headers={"x-user-token": "acc-t"})

    assert r.status_code == 401
    assert r.json()["detail"] == "account disabled"
