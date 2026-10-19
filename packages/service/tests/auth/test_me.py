"""GET /api/account/me 测试 — 返当前 CurrentUser (3 种身份)

(2026-06-16) 重写 100% mock. me 端点用 Depends(resolve_user), 用 dependency_overrides
替最干净 (跟 test_router.py 同一套). 0 真实 DB 连接.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.core.app_factory import create_app
from src.middleware.auth import CurrentUser, resolve_user


@pytest.fixture
def client():
    return TestClient(create_app())


def _make_user(
    user_id: int = 1,
    role: str = "user",
    is_account: bool = False,
    account_id: int | None = None,
    email: str | None = None,
    public_token: str = "tok",
) -> CurrentUser:
    """(2026-06-17) 改用 role 字段 (替原 is_admin bool). is_admin 是派生 property."""
    return CurrentUser(
        id=user_id,
        role=role,
        is_account=is_account,
        account_id=account_id,
        email=email,
        is_active=True,
        public_token=public_token,
    )


def test_me_anon_token_returns_is_account_false(client):
    """anon token (users.account_id is null) → is_account=False"""
    anon_user = _make_user(user_id=1, is_account=False, account_id=None, email=None)
    app = client.app
    app.dependency_overrides[resolve_user] = lambda: anon_user
    try:
        r = client.get("/api/account/me", headers={"x-user-token": "anon-tok"})
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 200
    body = r.json()
    assert body["is_account"] is False
    assert body["email"] is None
    assert body["is_admin"] is False


def test_me_account_returns_is_account_true_with_email(client, monkeypatch):
    """账号 token → is_account=True + email + is_admin"""
    monkeypatch.setenv("PASSWORD_BCRYPT_ROUNDS", "4")
    acc_user = _make_user(
        user_id=1,
        is_account=True,
        role="admin",
        account_id=10,
        email="bob@x.com",
    )
    app = client.app
    app.dependency_overrides[resolve_user] = lambda: acc_user
    try:
        r = client.get("/api/account/me", headers={"x-user-token": "acc-tok"})
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 200
    body = r.json()
    assert body["is_account"] is True
    assert body["email"] == "bob@x.com"
    assert body["is_admin"] is True
    assert body["account_id"] == 10


def test_me_no_token_401(client, monkeypatch):
    """无 token + 不在 dev mode → 401"""
    monkeypatch.delenv("RAG_DEV_AUTH", raising=False)
    r = client.get("/api/account/me")
    assert r.status_code == 401
