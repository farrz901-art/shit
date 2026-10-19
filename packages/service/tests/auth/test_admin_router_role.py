"""admin router 改 super_admin 守 + role 字段测试

(2026-06-17) v2 RBAC:
- require_admin 替成 require_super_admin (走 imports alias)
- invite body 加 role, 拒 super_admin
- PATCH body 加 role
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.auth.auth_admin_router import (
    CreateInviteRequest,
    PatchUserRequest,
    require_admin,
)
from src.core.app_factory import create_app
from src.middleware.auth import CurrentUser
from src.permissions.guards import require_super_admin


def _admin_user() -> CurrentUser:
    return CurrentUser(
        id=99,
        public_token="admin-tok",
        role="super_admin",
        is_account=True,
        account_id=99,
        email="admin@x.com",
        is_active=True,
    )


def test_require_admin_alias_points_to_require_super_admin() -> None:
    """require_admin 别名指 super_admin guard (v2: 仅 super_admin 可访 admin 后台)"""
    assert require_admin is require_super_admin


def test_create_invite_request_accepts_role() -> None:
    """CreateInviteRequest body 接受 role 字段"""
    # pyright basic 看不到 display_name=None 默认值
    req = CreateInviteRequest(email="x@y.com", role="admin")  # pyright: ignore[reportCallIssue]
    assert req.role == "admin"


def test_create_invite_request_default_role_is_user() -> None:
    """CreateInviteRequest 默认 role='user'"""
    req = CreateInviteRequest(email="x@y.com")  # pyright: ignore[reportCallIssue]
    assert req.role == "user"


def test_create_invite_rejects_super_admin_role(client) -> None:
    """POST invite body role=super_admin → 400"""
    app = client.app
    app.dependency_overrides[require_admin] = lambda: _admin_user()
    try:
        r = client.post("/api/admin/users", json={"email": "x@y.com", "role": "super_admin"})
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 400
    assert "super_admin invite" in r.json()["detail"]


def test_create_invite_unknown_role_400(client) -> None:
    """POST invite body role=ghost → 400 (role 不在 roles 表)"""
    mock_session = MagicMock()
    # Role query 返 None (role 不存在)
    role_q = MagicMock()
    role_q.filter_by.return_value.first.return_value = None
    mock_session.query.return_value = role_q

    with patch("src.auth.auth_admin_router.session_scope") as p:
        p.return_value.__enter__.return_value = mock_session
        p.return_value.__exit__.return_value = False
        app = client.app
        app.dependency_overrides[require_admin] = lambda: _admin_user()
        try:
            r = client.post("/api/admin/users", json={"email": "x@y.com", "role": "ghost"})
        finally:
            app.dependency_overrides.clear()

    assert r.status_code == 400
    assert "unknown role" in r.json()["detail"]


def test_patch_user_request_accepts_role() -> None:
    """PatchUserRequest body 接受 role 字段"""
    # pyright basic 看不到 is_active / display_name 默认值
    req = PatchUserRequest(role="admin")  # pyright: ignore[reportCallIssue]
    assert req.role == "admin"


@pytest.fixture
def client():
    return TestClient(create_app())
