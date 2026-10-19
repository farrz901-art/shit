"""/api/permissions GET + PATCH + /me 端点测试 (100% mock)"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# warm up: 避开 src.auth.__init__ 循环 (跟 src.middleware/auth.py 文档一致)
import src.auth.auth_account_router  # noqa: F401
from src.middleware.auth import CurrentUser
from src.permissions.router import router as permissions_router


@pytest.fixture
def app() -> FastAPI:
    """每个 test 一个新 app, 避免 dependency_overrides 跨 test 污染."""
    application = FastAPI()
    application.include_router(permissions_router)
    return application


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app)


def _make_user(role: str, is_account: bool = True) -> CurrentUser:
    """构造 CurrentUser (用真类避免 MagicMock 在 Pydantic 路径上崩)."""
    return CurrentUser(
        id=1,
        public_token=f"tok-{role}",
        role=role,
        is_account=is_account,
        account_id=1 if is_account else None,
    )


# --- GET /api/permissions ---


def test_get_permissions_requires_super_admin(client: TestClient, app: FastAPI) -> None:
    """非 super_admin 调 GET /api/permissions → 403"""
    app.dependency_overrides[__import__("src.permissions.router", fromlist=["resolve_user"]).resolve_user] = lambda: (
        _make_user("user")
    )
    resp = client.get("/api/permissions", headers={"x-user-token": "x"})
    assert resp.status_code == 403


def test_get_permissions_returns_matrix(client: TestClient, app: FastAPI) -> None:
    """super_admin 调 → 200, 返 roles + matrix + pages"""
    from src.permissions.router import resolve_user

    app.dependency_overrides[resolve_user] = lambda: _make_user("super_admin")
    with (
        patch("src.permissions.router.session_scope") as mock_sess,
        patch("src.permissions.service.session_scope") as mock_sess_svc,
        patch("src.permissions.service.permission_cache"),
    ):
        # router 查 roles + service 查 roles + perms
        # 模拟两层: 进入 contextmanager 时 query(...).all() 返 roles, service 的两层 query 返 ([])
        ctx_renderer = mock_sess.return_value.__enter__.return_value
        ctx_renderer.query.return_value.all.return_value = [
            MagicMock(name="user", label_zh="用户", label_en="User", is_system=True, is_deletable=False),
            MagicMock(name="admin", label_zh="管理员", label_en="Admin", is_system=True, is_deletable=False),
        ]
        ctx_service = mock_sess_svc.return_value.__enter__.return_value
        ctx_service.query.return_value.all.return_value = []
        resp = client.get("/api/permissions", headers={"x-user-token": "x"})
    assert resp.status_code == 200
    body = resp.json()
    assert "matrix" in body
    assert "roles" in body
    assert "pages" in body
    # 长度跟 ALL_PAGE_KEYS 一致; 加 page 不需要改此 test
    from src.permissions.cache import ALL_PAGE_KEYS

    assert len(body["pages"]) == len(ALL_PAGE_KEYS)


# --- GET /api/permissions/me ---


def test_get_my_permissions_for_regular_user(client: TestClient, app: FastAPI) -> None:
    """普通 user 调 /me → 200, 返 role + allowed 列表"""
    from src.permissions.router import resolve_user

    app.dependency_overrides[resolve_user] = lambda: _make_user("user")
    # 替换 permission_cache 实例 (避免 cache.get 触发 _refresh 走真 DB)
    from src.permissions.cache import PermissionCache

    fake_cache = MagicMock(spec=PermissionCache)

    def cache_get(role: str, page: str) -> bool | None:
        allow = {"chat": True, "output": True, "decode": True}
        return allow.get(page, False)

    fake_cache.get.side_effect = cache_get

    with (
        patch("src.permissions.service.permission_cache", fake_cache),
        patch("src.permissions.cache.permission_cache", fake_cache),
    ):
        resp = client.get("/api/permissions/me", headers={"x-user-token": "x"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["role"] == "user"
    assert "allowed" in body
    assert "chat" in body["allowed"]
    # account_id 字段必须存在 (从 CurrentUser 透传)
    assert "account_id" in body
    assert body["account_id"] == 1


def test_get_my_permissions_for_anon_returns_null_account_id(
    client: TestClient,
    app: FastAPI,
) -> None:
    """匿名用户 (anon) 调 /me → account_id 为 None"""
    from src.permissions.router import resolve_user

    app.dependency_overrides[resolve_user] = lambda: _make_user("user", is_account=False)
    # 替换 permission_cache 实例
    from src.permissions.cache import PermissionCache

    fake_cache = MagicMock(spec=PermissionCache)
    fake_cache.get.return_value = True
    with (
        patch("src.permissions.service.permission_cache", fake_cache),
        patch("src.permissions.cache.permission_cache", fake_cache),
    ):
        resp = client.get("/api/permissions/me", headers={"x-user-token": "x"})
    assert resp.status_code == 200
    body = resp.json()
    assert "account_id" in body
    assert body["account_id"] is None


def test_get_my_permissions_super_admin_returns_all(client: TestClient, app: FastAPI) -> None:
    """super_admin 调 /me → 返所有 page"""
    from src.permissions.router import resolve_user

    app.dependency_overrides[resolve_user] = lambda: _make_user("super_admin")
    resp = client.get("/api/permissions/me", headers={"x-user-token": "x"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["role"] == "super_admin"
    # super_admin 返所有 page; 长度跟 ALL_PAGE_KEYS 一致
    from src.permissions.cache import ALL_PAGE_KEYS

    assert len(body["allowed"]) == len(ALL_PAGE_KEYS)
    # account_id 字段必须存在
    assert "account_id" in body
    assert body["account_id"] == 1


# --- PATCH /api/permissions ---


def test_patch_permissions_updates_cell(client: TestClient, app: FastAPI) -> None:
    """super_admin 改 cell → 200"""
    from src.permissions.router import resolve_user

    app.dependency_overrides[resolve_user] = lambda: _make_user("super_admin")
    with (
        patch("src.permissions.router.update_permissions") as mock_update,
        patch("src.permissions.router.session_scope") as mock_sess,
    ):
        # role 存在
        mock_sess.return_value.__enter__.return_value.query.return_value.filter_by.return_value.first.return_value = (
            MagicMock()
        )
        mock_update.return_value = 1
        resp = client.patch(
            "/api/permissions",
            headers={"x-user-token": "x"},
            json={"updates": [{"role_name": "user", "page_key": "output", "allowed": True}]},
        )
    assert resp.status_code == 200
    assert resp.json()["updated"] == 1
    # update_permissions 被调, 内部会 invalidate cache
    mock_update.assert_called_once()


def test_patch_permissions_rejects_unknown_role(client: TestClient, app: FastAPI) -> None:
    """未知 role → 400"""
    from src.permissions.router import resolve_user

    app.dependency_overrides[resolve_user] = lambda: _make_user("super_admin")
    with patch("src.permissions.router.session_scope") as mock_sess:
        # role 查询返 None (不存在)
        mock_sess.return_value.__enter__.return_value.query.return_value.filter_by.return_value.first.return_value = (
            None
        )
        resp = client.patch(
            "/api/permissions",
            headers={"x-user-token": "x"},
            json={"updates": [{"role_name": "ghost", "page_key": "chat", "allowed": True}]},
        )
    assert resp.status_code == 400
    assert "unknown role" in resp.json()["detail"]


def test_patch_permissions_rejects_super_admin(client: TestClient, app: FastAPI) -> None:
    """改 super_admin 行 → 400"""
    from src.permissions.router import resolve_user

    app.dependency_overrides[resolve_user] = lambda: _make_user("super_admin")
    resp = client.patch(
        "/api/permissions",
        headers={"x-user-token": "x"},
        json={"updates": [{"role_name": "super_admin", "page_key": "chat", "allowed": False}]},
    )
    assert resp.status_code == 400
    assert "super_admin" in resp.json()["detail"]


def test_patch_permissions_rejects_unknown_page(client: TestClient, app: FastAPI) -> None:
    """未知 page_key → 400"""
    from src.permissions.router import resolve_user

    app.dependency_overrides[resolve_user] = lambda: _make_user("super_admin")
    resp = client.patch(
        "/api/permissions",
        headers={"x-user-token": "x"},
        json={"updates": [{"role_name": "user", "page_key": "nonexistent", "allowed": True}]},
    )
    assert resp.status_code == 400
    assert "unknown page_key" in resp.json()["detail"]


def test_patch_permissions_requires_super_admin(client: TestClient, app: FastAPI) -> None:
    """非 super_admin 调 PATCH → 403"""
    from src.permissions.router import resolve_user

    app.dependency_overrides[resolve_user] = lambda: _make_user("user")
    resp = client.patch(
        "/api/permissions",
        headers={"x-user-token": "x"},
        json={"updates": [{"role_name": "user", "page_key": "chat", "allowed": True}]},
    )
    assert resp.status_code == 403
