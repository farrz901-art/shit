"""/api/roles CRUD 测试 (GET/POST/PATCH/DELETE, 100% mock)"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# warm up: 避开 src.auth.__init__ 循环
import src.auth.auth_account_router  # noqa: F401
from src.middleware.auth import CurrentUser
from src.permissions.router import router as permissions_router


@pytest.fixture
def app() -> FastAPI:
    application = FastAPI()
    application.include_router(permissions_router)
    return application


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app)


def _make_user(role: str) -> CurrentUser:
    return CurrentUser(
        id=1,
        public_token=f"tok-{role}",
        role=role,
        is_account=True,
        account_id=1,
    )


# --- GET /api/roles ---


def test_get_roles_requires_super_admin(client: TestClient, app: FastAPI) -> None:
    """非 super_admin 调 → 403"""
    from src.permissions.router import resolve_user

    app.dependency_overrides[resolve_user] = lambda: _make_user("admin")
    resp = client.get("/api/roles", headers={"x-user-token": "x"})
    assert resp.status_code == 403


def test_get_roles_returns_list_with_user_count(client: TestClient, app: FastAPI) -> None:
    """super_admin 调 → 200, 返 roles 列表 + user_count"""
    from src.permissions.router import resolve_user

    app.dependency_overrides[resolve_user] = lambda: _make_user("super_admin")
    with patch("src.permissions.router.session_scope") as mock_sess:
        # roles query → MagicMock 列表
        role_mock_1 = MagicMock(
            name="user",
            label_zh="用户",
            label_en="User",
            is_system=True,
            is_deletable=False,
            created_at=None,
            updated_at=None,
        )
        role_mock_2 = MagicMock(
            name="admin",
            label_zh="管理员",
            label_en="Admin",
            is_system=True,
            is_deletable=False,
            created_at=None,
            updated_at=None,
        )
        # 第 1 次 query 返 roles; 后续 query (count) 返数字
        mock_query = mock_sess.return_value.__enter__.return_value.query.return_value
        mock_query.all.return_value = [role_mock_1, role_mock_2]
        mock_query.filter_by.return_value.count.return_value = 5
        resp = client.get("/api/roles", headers={"x-user-token": "x"})
    assert resp.status_code == 200
    body = resp.json()
    assert "roles" in body
    assert len(body["roles"]) == 2
    for r in body["roles"]:
        assert "user_count" in r
        assert r["user_count"] == 5


# --- POST /api/roles ---


def test_post_role_validates_name_format(client: TestClient, app: FastAPI) -> None:
    """name 格式错 ([a-z0-9_]{2,32}) → 400"""
    from src.permissions.router import resolve_user

    app.dependency_overrides[resolve_user] = lambda: _make_user("super_admin")
    resp = client.post(
        "/api/roles",
        headers={"x-user-token": "x"},
        json={"name": "Bad-Name", "label_zh": "x", "label_en": "x", "permissions": {}},
    )
    assert resp.status_code == 400
    assert "name" in resp.json()["detail"].lower()


def test_post_role_rejects_super_admin_name(client: TestClient, app: FastAPI) -> None:
    """尝试创 super_admin 角色 → 400"""
    from src.permissions.router import resolve_user

    app.dependency_overrides[resolve_user] = lambda: _make_user("super_admin")
    resp = client.post(
        "/api/roles",
        headers={"x-user-token": "x"},
        json={"name": "super_admin", "label_zh": "x", "label_en": "x", "permissions": {}},
    )
    assert resp.status_code == 400
    assert "super_admin" in resp.json()["detail"]


def test_post_role_rejects_duplicate_name(client: TestClient, app: FastAPI) -> None:
    """name 重复 → 409"""
    from src.permissions.router import resolve_user

    app.dependency_overrides[resolve_user] = lambda: _make_user("super_admin")
    with patch("src.permissions.router.session_scope") as mock_sess:
        # role 已存在
        mock_sess.return_value.__enter__.return_value.query.return_value.filter_by.return_value.first.return_value = (
            MagicMock()
        )
        resp = client.post(
            "/api/roles",
            headers={"x-user-token": "x"},
            json={"name": "user", "label_zh": "重复", "label_en": "Dup", "permissions": {}},
        )
    assert resp.status_code == 409
    assert "exists" in resp.json()["detail"].lower() or "重复" in resp.json()["detail"]


def test_post_role_creates_with_permissions(client: TestClient, app: FastAPI) -> None:
    """创角色 + permissions → 201 + cache invalidate"""
    from src.permissions.router import resolve_user

    app.dependency_overrides[resolve_user] = lambda: _make_user("super_admin")
    with (
        patch("src.permissions.router.session_scope") as mock_sess,
        patch("src.permissions.router.permission_cache") as mock_cache,
    ):
        # role 不存在
        mock_sess.return_value.__enter__.return_value.query.return_value.filter_by.return_value.first.return_value = (
            None
        )
        resp = client.post(
            "/api/roles",
            headers={"x-user-token": "x"},
            json={
                "name": "operator",
                "label_zh": "运营",
                "label_en": "Operator",
                "permissions": {"chat": True, "output": True},
            },
        )
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "operator"
    assert body["is_system"] is False
    assert body["is_deletable"] is True
    mock_cache.invalidate.assert_called_once()


# --- PATCH /api/roles/{name} ---


def test_patch_role_updates_labels(client: TestClient, app: FastAPI) -> None:
    """改 label_zh → 200 + cache invalidate"""
    from src.permissions.router import resolve_user

    app.dependency_overrides[resolve_user] = lambda: _make_user("super_admin")
    existing_role = MagicMock(
        name="operator",
        label_zh="运营",
        label_en="Operator",
        is_system=False,
        is_deletable=True,
    )
    with (
        patch("src.permissions.router.session_scope") as mock_sess,
        patch("src.permissions.router.permission_cache") as mock_cache,
    ):
        mock_sess.return_value.__enter__.return_value.query.return_value.filter_by.return_value.first.return_value = (
            existing_role
        )
        resp = client.patch(
            "/api/roles/operator",
            headers={"x-user-token": "x"},
            json={"label_zh": "运营 (新版)"},
        )
    assert resp.status_code == 200
    assert existing_role.label_zh == "运营 (新版)"
    mock_cache.invalidate.assert_called_once()


def test_patch_role_not_found(client: TestClient, app: FastAPI) -> None:
    """role 不存在 → 404"""
    from src.permissions.router import resolve_user

    app.dependency_overrides[resolve_user] = lambda: _make_user("super_admin")
    with patch("src.permissions.router.session_scope") as mock_sess:
        mock_sess.return_value.__enter__.return_value.query.return_value.filter_by.return_value.first.return_value = (
            None
        )
        resp = client.patch(
            "/api/roles/ghost",
            headers={"x-user-token": "x"},
            json={"label_zh": "x"},
        )
    assert resp.status_code == 404


# --- DELETE /api/roles/{name} ---


def test_delete_system_role_rejected(client: TestClient, app: FastAPI) -> None:
    """删系统角色 → 400"""
    from src.permissions.router import resolve_user

    app.dependency_overrides[resolve_user] = lambda: _make_user("super_admin")
    with patch("src.permissions.router.session_scope") as mock_sess:
        mock_sess.return_value.__enter__.return_value.query.return_value.filter_by.return_value.first.return_value = (
            MagicMock(name="user", is_system=True, is_deletable=False)
        )
        resp = client.delete("/api/roles/user", headers={"x-user-token": "x"})
    assert resp.status_code == 400
    assert "system" in resp.json()["detail"].lower()


def test_delete_role_in_use_rejected(client: TestClient, app: FastAPI) -> None:
    """删角色时还有用户 → 409"""
    from src.permissions.router import resolve_user

    app.dependency_overrides[resolve_user] = lambda: _make_user("super_admin")
    with patch("src.permissions.router.session_scope") as mock_sess:
        # 第 1 次 query (filter_by name) 返 role
        # 第 2 次 query (filter_by role) 返 count=3
        mock_query = mock_sess.return_value.__enter__.return_value.query.return_value
        mock_query.filter_by.return_value.first.return_value = MagicMock(
            name="operator", is_system=False, is_deletable=True
        )
        mock_query.filter_by.return_value.count.return_value = 3
        resp = client.delete("/api/roles/operator", headers={"x-user-token": "x"})
    assert resp.status_code == 409
    assert "3" in resp.json()["detail"] or "in use" in resp.json()["detail"].lower()


def test_delete_role_success(client: TestClient, app: FastAPI) -> None:
    """删自定义角色 (0 用户) → 204 + cache invalidate"""
    from src.permissions.router import resolve_user

    app.dependency_overrides[resolve_user] = lambda: _make_user("super_admin")
    role = MagicMock(name="ghost_role", is_system=False, is_deletable=True)
    with (
        patch("src.permissions.router.session_scope") as mock_sess,
        patch("src.permissions.router.permission_cache") as mock_cache,
    ):
        mock_query = mock_sess.return_value.__enter__.return_value.query.return_value
        mock_query.filter_by.return_value.first.return_value = role
        mock_query.filter_by.return_value.count.return_value = 0
        resp = client.delete("/api/roles/ghost_role", headers={"x-user-token": "x"})
    assert resp.status_code == 204
    mock_cache.invalidate.assert_called_once()
