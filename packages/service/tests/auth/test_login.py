"""POST /api/account/login 测试 (2026-06-16 重写 100% mock)

CLAUDE.md 强制: 0 真实 DB 连接, 包括 db_session 事务回滚.
用 mock 替 session_scope 内部 + Account.query, 跟 test_router.py 同一套.

Pattern:
- TestClient(create_app()) 真创建 FastAPI app (轻量, 不连 DB)
- app.dependency_overrides[...] 替 auth / get_current_user 依赖
- patch("src.auth.auth_account_router.session_scope") 替 session_scope
- AsyncMock / MagicMock 替 Account / User 对象
"""

from __future__ import annotations

import secrets
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.auth.account_models import Account
from src.auth.account_service import hash_password
from src.core.app_factory import create_app


@pytest.fixture
def client():
    return TestClient(create_app())


def _make_mock_account(
    email: str = "alice@x.com",
    password: str = "secretpassword",
    is_active: bool = True,
    is_admin: bool = False,
    display_name: str = "alice",
) -> MagicMock:
    """Mock Account 对象, 字段跟 SQLAlchemy 一致. 不连 DB.

    (2026-06-17) is_admin 兼容旧测试, 内部转 role.
    """
    a = MagicMock(spec=Account)
    a.id = 1
    a.email = email
    a.password_hash = hash_password(password)
    a.role = "super_admin" if is_admin else "user"
    a.is_active = is_active
    a.display_name = display_name
    a.last_login_at = None
    return a


def _make_mock_user(account_id: int = 1, public_token: str | None = None) -> MagicMock:
    """Mock User 对象. public_token 默认 64-char hex 跟真路由生成一致."""
    u = MagicMock()
    u.id = 1
    u.public_token = public_token or secrets.token_hex(32)
    u.account_id = account_id
    u.display_name = "alice"
    return u


@contextmanager
def _patch_session_scope(mock_session):
    """patch src.auth.auth_account_router.session_scope 返 mock_session."""
    with patch("src.auth.auth_account_router.session_scope") as patched:
        patched.return_value.__enter__.return_value = mock_session
        patched.return_value.__exit__.return_value = False
        yield patched


def test_login_success_returns_token_and_cookie(client, monkeypatch):
    """正确凭据 → 200 + body.token + Set-Cookie rag_user_token"""
    monkeypatch.setenv("PASSWORD_BCRYPT_ROUNDS", "4")
    mock_account = _make_mock_account()
    mock_user = _make_mock_user(account_id=1)
    # session.query(Account).filter_by(email=...).first() → mock_account
    # session.query(User).filter_by(account_id=...).first() → mock_user
    # 注: MagicMock(first=MagicMock(...)) 会让 first() 返 MagicMock 而非 mock, 必须 first.return_value = X
    account_query = MagicMock()
    account_query.filter_by.return_value.first.return_value = mock_account
    user_query = MagicMock()
    user_query.filter_by.return_value.first.return_value = mock_user
    mock_session = MagicMock()
    mock_session.query.side_effect = [account_query, user_query]

    with _patch_session_scope(mock_session):
        r = client.post("/api/account/login", json={"email": "alice@x.com", "password": "secretpassword"})

    assert r.status_code == 200, r.text
    body = r.json()
    assert "token" in body
    assert len(body["token"]) == 64  # 32 bytes hex
    assert body["account"]["email"] == "alice@x.com"
    assert r.cookies.get("rag_user_token") == body["token"]


def test_login_wrong_password_401(client, monkeypatch):
    """错密码 → 401 'invalid credentials'"""
    monkeypatch.setenv("PASSWORD_BCRYPT_ROUNDS", "4")
    mock_account = _make_mock_account(password="differentpassword")
    mock_session = MagicMock()
    mock_session.query.return_value.filter_by.return_value.first.return_value = mock_account

    with _patch_session_scope(mock_session):
        r = client.post("/api/account/login", json={"email": "alice@x.com", "password": "wrongpassword!"})

    assert r.status_code == 401
    assert r.json()["detail"] == "invalid credentials"


def test_login_unknown_email_401(client):
    """不存在 email → 401 (跟错密码同 message, 防探测)"""
    mock_session = MagicMock()
    mock_session.query.return_value.filter_by.return_value.first.return_value = None

    with _patch_session_scope(mock_session):
        r = client.post("/api/account/login", json={"email": "nobody@x.com", "password": "whateverpw"})

    assert r.status_code == 401
    assert r.json()["detail"] == "invalid credentials"


def test_login_disabled_account_401(client, monkeypatch):
    """is_active=False 账号 → 401 'account disabled'"""
    monkeypatch.setenv("PASSWORD_BCRYPT_ROUNDS", "4")
    mock_account = _make_mock_account(is_active=False)
    mock_session = MagicMock()
    mock_session.query.return_value.filter_by.return_value.first.return_value = mock_account

    with _patch_session_scope(mock_session):
        r = client.post("/api/account/login", json={"email": "alice@x.com", "password": "secretpassword"})

    assert r.status_code == 401
    assert r.json()["detail"] == "account disabled"


def test_login_creates_user_row_for_new_account(client, monkeypatch):
    """新账号登录 → users 表创新行 + account_id 关联"""
    from src.auth.models import User

    monkeypatch.setenv("PASSWORD_BCRYPT_ROUNDS", "4")
    mock_account = _make_mock_account()
    mock_session = MagicMock()
    # 第一次 query(Account) 返 mock_account; 第二次 query(User) 返 None (创新)
    account_query = MagicMock()
    account_query.filter_by.return_value.first.return_value = mock_account
    user_query = MagicMock()
    user_query.filter_by.return_value.first.return_value = None
    mock_session.query.side_effect = [account_query, user_query]

    with _patch_session_scope(mock_session):
        r = client.post("/api/account/login", json={"email": "alice@x.com", "password": "secretpassword"})

    assert r.status_code == 200
    token = r.json()["token"]
    # 验证 router 调了 session.add(new_user) 创 user 行
    assert mock_session.add.called
    added_obj = mock_session.add.call_args[0][0]
    assert isinstance(added_obj, User)
    assert added_obj.account_id == 1
    assert added_obj.public_token == token


def test_login_rate_limited_after_threshold(client, monkeypatch):
    """(2026-06-18) 同一 IP 15min 内第 6 次登录 → 429
    限流前置, 不查 DB (account=None 也不会查, 直接被 429 拒).
    用 fake_redis 让计数真生效, 不走 fail-open 路径.
    """
    from fakeredis import aioredis as fakeredis

    from src.core import redis_client

    fake = fakeredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(redis_client, "get_redis", lambda: fake)
    monkeypatch.setattr(redis_client, "_pool", None)
    # env 兜底: 阈值 5, 窗口 15min
    monkeypatch.setenv("RL_LOGIN_THRESHOLD", "5")
    monkeypatch.setenv("RL_LOGIN_WINDOW", "900")

    # mock session_scope, 5 次应被限流 (前 5 次通过, 第 6 次拒)
    # 实际上限流在 session_scope 之前, 所以 session 不被调用, 这里 patch 仅为保险
    with patch("src.auth.auth_account_router.session_scope") as patched:
        # 前 5 次: redis 计数从 1 到 5, 业务走到 session_scope (会因 mock 返回异常)
        # 为了测限流, 把前 5 次也通过 patch 兜住: 让其返 401
        account_query = MagicMock()
        account_query.filter_by.return_value.first.return_value = None
        mock_session = MagicMock()
        mock_session.query.return_value.filter_by.return_value.first.return_value = None
        patched.return_value.__enter__.return_value = mock_session
        patched.return_value.__exit__.return_value = False

        statuses = []
        r = None
        for _ in range(7):
            r = client.post("/api/account/login", json={"email": "x@x.com", "password": "wrong"})
            statuses.append(r.status_code)
        # 前 5 次: 401 (错密码). 第 6 次起: 429 (限流)
        assert statuses[:5] == [401, 401, 401, 401, 401]
        assert statuses[5] == 429
        assert statuses[6] == 429
        assert r is not None and ("频繁" in r.json()["detail"] or "15" in r.json()["detail"])
