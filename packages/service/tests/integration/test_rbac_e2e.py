"""RBAC 端到端测试: 4 身份 × 7 页面 矩阵

不走真 DB (本地无 PG), 用 permission_cache mock 模拟 role × page 矩阵.
跑 require_page 装饰器链 + /api/permissions/me 端点, 验证:
- 4 身份 (anon / user / admin / super_admin) × 7 页面 (chat / output / knowledge /
  evaluate / submissions / decode / health)
- super_admin 永远通过 (meta 豁免)
- user / admin 走 cache 校验
- anon 调 /me 返 200 (anon role="user")
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# warm up: 避开 src.auth.__init__ 循环
import src.auth.auth_account_router  # noqa: F401
from src.middleware.auth import CurrentUser
from src.permissions.cache import ALL_PAGE_KEYS
from src.permissions.guards import require_page, require_super_admin
from src.permissions.router import router as permissions_router

# 4 身份 × 7 页面 矩阵 (true=允许访问, false=拒绝)
# anon → 当作 role="user" 处理 (resolve_user 走 anon 路径)
ROLE_PAGE_MATRIX: dict[str, dict[str, bool]] = {
    "user": {
        "chat": True,
        "output": True,
        "decode": True,
        "knowledge": False,
        "evaluate": False,
        "submissions": False,
        "health": False,
    },
    "admin": {
        "chat": True,
        "output": True,
        "knowledge": True,
        "evaluate": True,
        "submissions": True,
        "decode": True,
        "health": False,  # admin 不能看 health
    },
    "super_admin": {page: True for page in ALL_PAGE_KEYS},  # 全部允许 (meta 豁免)
}


def _make_user(role: str) -> CurrentUser:
    return CurrentUser(
        id=1,
        public_token=f"tok-{role}",
        role=role,
        is_account=True,
        account_id=1,
    )


def _make_anon() -> CurrentUser:
    """anon 用户: is_account=False"""
    return CurrentUser(
        id=1,
        public_token="tok-anon",
        role="user",  # anon role 默认 user
        is_account=False,
        account_id=None,
    )


@pytest.fixture
def app() -> FastAPI:
    application = FastAPI()
    application.include_router(permissions_router)
    return application


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app)


# --- /api/permissions/me 端点验证 (4 身份 × 7 页面) ---


@pytest.mark.parametrize(
    "role,page,expected_in_allowed",
    [
        # user: chat/output/decode 允许; knowledge/evaluate/submissions/health 不允许
        ("user", "chat", True),
        ("user", "output", True),
        ("user", "decode", True),
        ("user", "knowledge", False),
        ("user", "evaluate", False),
        ("user", "submissions", False),
        ("user", "health", False),
        # admin: 除 health 外都允许
        ("admin", "chat", True),
        ("admin", "output", True),
        ("admin", "knowledge", True),
        ("admin", "evaluate", True),
        ("admin", "submissions", True),
        ("admin", "decode", True),
        ("admin", "health", False),
        # super_admin: 全部允许
        ("super_admin", "chat", True),
        ("super_admin", "output", True),
        ("super_admin", "knowledge", True),
        ("super_admin", "evaluate", True),
        ("super_admin", "submissions", True),
        ("super_admin", "decode", True),
        ("super_admin", "health", True),
    ],
)
def test_role_page_matrix_via_me_endpoint(
    client: TestClient, app: FastAPI, role: str, page: str, expected_in_allowed: bool
) -> None:
    """4 身份 × 7 页面 → 调 /me 端点, 验证 allowed 列表包含/不包含 page"""
    from src.permissions.router import resolve_user

    app.dependency_overrides[resolve_user] = lambda: _make_user(role)
    # mock permission_cache 让 get(role, page) 返矩阵值 (同时 patch service + cache 入口)
    fake_cache = MagicMock()
    fake_cache.get.side_effect = lambda r, p: ROLE_PAGE_MATRIX.get(r, {}).get(p)
    with (
        patch("src.permissions.service.permission_cache", fake_cache),
        patch("src.permissions.cache.permission_cache", fake_cache),
    ):
        resp = client.get("/api/permissions/me", headers={"x-user-token": "x"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["role"] == role
    if expected_in_allowed:
        assert page in body["allowed"], f"role={role} 应能访问 page={page}"
    else:
        assert page not in body["allowed"], f"role={role} 不应能访问 page={page}"


# --- /api/permissions/me anon 也能调 ---


def test_anon_can_call_me_endpoint(client: TestClient, app: FastAPI) -> None:
    """anon (无 account) 调 /me → 200, 拿 user 角色的 allowed 列表"""
    from src.permissions.router import resolve_user

    app.dependency_overrides[resolve_user] = lambda: _make_anon()
    fake_cache = MagicMock()
    fake_cache.get.side_effect = lambda r, p: ROLE_PAGE_MATRIX.get(r, {}).get(p)
    with (
        patch("src.permissions.service.permission_cache", fake_cache),
        patch("src.permissions.cache.permission_cache", fake_cache),
    ):
        resp = client.get("/api/permissions/me", headers={"x-user-token": "x"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["role"] == "user"
    assert "chat" in body["allowed"]  # anon role=user 能访 chat
    assert "health" not in body["allowed"]


# --- require_page 端到端矩阵 (4 身份 × 7 页面) ---


@pytest.mark.parametrize(
    "role,page,expected_pass",
    [
        # anon 当作 user
        ("user", "chat", True),
        ("user", "decode", True),
        ("user", "knowledge", False),
        ("user", "health", False),
        # admin
        ("admin", "knowledge", True),
        ("admin", "evaluate", True),
        ("admin", "health", False),
        # super_admin (meta 豁免)
        ("super_admin", "chat", True),
        ("super_admin", "health", True),
        ("super_admin", "knowledge", True),
    ],
)
def test_require_page_e2e_matrix(role: str, page: str, expected_pass: bool) -> None:
    """require_page 装饰器 + mock cache: 4 身份 × 7 页面 矩阵"""
    user = _make_user(role)
    if role == "super_admin":
        # meta 豁免, 不查 cache
        dep = require_page(page)
        assert dep(user) is user
        return
    # 其他角色走 cache
    with patch("src.permissions.guards.permission_cache") as mock_cache:
        mock_cache.get.return_value = ROLE_PAGE_MATRIX[role][page]
        dep = require_page(page)
        if expected_pass:
            assert dep(user) is user
        else:
            import pytest as _pytest
            from fastapi import HTTPException

            with _pytest.raises(HTTPException) as exc:
                dep(user)
            assert exc.value.status_code == 403


# --- require_super_admin 端到端 ---


@pytest.mark.parametrize(
    "role,expected_pass",
    [
        ("super_admin", True),
        ("admin", False),
        ("user", False),
    ],
)
def test_require_super_admin_e2e(role: str, expected_pass: bool) -> None:
    """require_super_admin 装饰器: 3 身份 (super_admin / admin / user)"""
    from fastapi import HTTPException

    user = _make_user(role)
    if expected_pass:
        assert require_super_admin(user) is user
    else:
        with pytest.raises(HTTPException) as exc:
            require_super_admin(user)
        assert exc.value.status_code == 403
        assert "super_admin required" in str(exc.value.detail)
