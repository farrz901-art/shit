"""验证 /api/auth/anon 响应设置 HttpOnly cookie (2026-06-16 重写 100% mock)

100% mock 模式:
- patch src.auth.router.session_scope (anon handler 创 user 用)
- patch src.middleware.auth.session_scope (_ensure_dev_user 用, no token + RAG_DEV_AUTH)
- patch secrets.token_hex 拿可预测 token

0 真实 DB 连接, 0 dev DB writes.
"""

from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.auth.models import User
from src.core.app_factory import create_app


@contextmanager
def _patch_anon_session(mock_session: MagicMock):
    """同时 patch anon endpoint 和 middleware 的 session_scope

    anon handler 调 src.auth.router.session_scope 创 user;
    resolve_user 调 src.middleware.auth.session_scope (_ensure_dev_user).
    两端都 mock 到同一个 session.
    """
    with (
        patch("src.auth.router.session_scope") as router_p,
        patch("src.middleware.auth.session_scope") as mw_p,
    ):
        for p in (router_p, mw_p):
            p.return_value.__enter__.return_value = mock_session
            p.return_value.__exit__.return_value = False
        yield mock_session


@pytest.fixture
def client():
    """TestClient, 不设 RAG_DEV_AUTH (anon 不需要 token)"""
    return TestClient(create_app())


def test_anon_sets_http_only_cookie(client):
    """POST /api/auth/anon 必须 Set-Cookie HttpOnly + SameSite=Lax + Path=/ + Max-Age=7d."""
    mock_session = MagicMock()
    # query(User).filter_by(public_token=...).first() → None (token 未碰撞)
    mock_session.query.return_value.filter_by.return_value.first.return_value = None

    with _patch_anon_session(mock_session):
        with patch("src.auth.router.secrets.token_hex", return_value="a" * 64):
            res = client.post("/api/auth/anon")

    assert res.status_code == 200
    set_cookie = res.headers.get("set-cookie", "")
    assert "rag_user_token=" in set_cookie
    # RFC 6265 Set-Cookie 属性名大小写不敏感, 用 lower 比对
    set_cookie_lower = set_cookie.lower()
    assert "httponly" in set_cookie_lower
    assert "samesite=lax" in set_cookie_lower
    assert "path=/" in set_cookie_lower
    assert "max-age=604800" in set_cookie_lower
    # session.add 被调 (创 User)
    assert mock_session.add.called
    added = mock_session.add.call_args[0][0]
    assert isinstance(added, User)
    assert added.public_token == "a" * 64


def test_anon_secure_cookie_in_production(monkeypatch):
    """ENV=production 时 cookie 必须带 secure 属性"""
    monkeypatch.setenv("ENV", "production")
    mock_session = MagicMock()
    mock_session.query.return_value.filter_by.return_value.first.return_value = None

    with _patch_anon_session(mock_session):
        with patch("src.auth.router.secrets.token_hex", return_value="b" * 64):
            # os.getenv("ENV") 在 set_cookie 调用时求值, monkeypatch 已设 production
            app = create_app()
            c = TestClient(app)
            res = c.post("/api/auth/anon")

    assert res.status_code == 200
    set_cookie_lower = res.headers.get("set-cookie", "").lower()
    assert "secure" in set_cookie_lower


def test_anon_response_body_still_returns_token_for_legacy(client):
    """灰度期 body 仍返 token, 后续 P4 删除."""
    mock_session = MagicMock()
    mock_session.query.return_value.filter_by.return_value.first.return_value = None

    with _patch_anon_session(mock_session):
        with patch("src.auth.router.secrets.token_hex", return_value="c" * 64):
            res = client.post("/api/auth/anon")

    body = res.json()
    assert "token" in body
    assert body["token"] == "c" * 64
    assert len(body["token"]) == 64
