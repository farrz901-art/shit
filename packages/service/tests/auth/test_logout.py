"""POST /api/account/logout 测试"""

from __future__ import annotations

from fastapi.testclient import TestClient

from src.core.app_factory import create_app


def test_logout_clears_cookie():
    client = TestClient(create_app())
    client.cookies.set("rag_user_token", "any-token")
    r = client.post("/api/account/logout")
    assert r.status_code == 200
    assert r.json() == {"ok": True}
    # Set-Cookie 头应该清空
    assert r.headers.get("set-cookie", "").startswith("rag_user_token=")
    assert "Max-Age=0" in r.headers.get("set-cookie", "")


def test_logout_idempotent():
    """没 cookie 调 → 200 (不 401)"""
    client = TestClient(create_app())
    r = client.post("/api/account/logout")
    assert r.status_code == 200
