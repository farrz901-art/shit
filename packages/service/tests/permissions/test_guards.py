"""3 个守卫装饰器测试: 4 身份 × 7 页面 矩阵 (parametrize)

CurrentUser 走 MagicMock 模拟 (Task 5 加 role 字段后, 这里改回真实构造).
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from src.permissions.guards import require_account, require_page, require_super_admin


def _make_user(role: str = "user", is_account: bool = True) -> MagicMock:
    """构造 CurrentUser-形态 mock: role/is_account/account_id 3 字段 guard 读."""
    u = MagicMock()
    u.role = role
    u.is_account = is_account
    u.account_id = 1 if is_account else None
    return u


# 1. require_super_admin
def test_require_super_admin_super_admin() -> None:
    user = _make_user("super_admin")
    assert require_super_admin(user) is user


@pytest.mark.parametrize("role", ["user", "admin", "operator"])
def test_require_super_admin_rejects_non_super(role: str) -> None:
    user = _make_user(role)
    with pytest.raises(HTTPException) as exc:
        require_super_admin(user)
    assert exc.value.status_code == 403
    assert "super_admin required" in str(exc.value.detail)


# 2. require_account
def test_require_account_passes_for_account() -> None:
    user = _make_user("user", is_account=True)
    assert require_account(user) is user


def test_require_account_rejects_anon() -> None:
    user = _make_user("user", is_account=False)
    with pytest.raises(HTTPException) as exc:
        require_account(user)
    assert exc.value.status_code == 403
    assert "login required" in str(exc.value.detail)


# 3. require_page: 4 身份 × 7 页面 矩阵
@pytest.mark.parametrize("page_key", ["chat", "output", "knowledge", "evaluate", "submissions", "decode", "health"])
def test_require_page_super_admin_bypasses_all(page_key: str) -> None:
    """super_admin 永远通过 (meta 豁免)"""
    user = _make_user("super_admin")
    with patch("src.permissions.guards.permission_cache") as mock_cache:
        dep = require_page(page_key)
        assert dep(user) is user
        mock_cache.get.assert_not_called()


@pytest.mark.parametrize(
    "page_key,expected",
    [
        ("chat", True),
        ("decode", True),
        ("output", False),
        ("knowledge", False),
        ("evaluate", False),
        ("submissions", False),
        ("health", False),
    ],
)
def test_require_page_user_role(page_key: str, expected: bool) -> None:
    user = _make_user("user")
    with patch("src.permissions.guards.permission_cache") as mock_cache:
        mock_cache.get.return_value = expected
        dep = require_page(page_key)
        if expected:
            assert dep(user) is user
        else:
            with pytest.raises(HTTPException) as exc:
                dep(user)
            assert exc.value.status_code == 403


@pytest.mark.parametrize(
    "page_key,expected",
    [
        ("chat", True),
        ("output", True),
        ("knowledge", True),
        ("evaluate", True),
        ("submissions", True),
        ("decode", True),
        ("health", False),
    ],
)
def test_require_page_admin_role(page_key: str, expected: bool) -> None:
    user = _make_user("admin")
    with patch("src.permissions.guards.permission_cache") as mock_cache:
        mock_cache.get.return_value = expected
        dep = require_page(page_key)
        if expected:
            assert dep(user) is user
        else:
            with pytest.raises(HTTPException):
                dep(user)


def test_require_page_custom_role() -> None:
    """自定义角色 (例 operator) 走 cache 校验"""
    user = _make_user("operator")
    with patch("src.permissions.guards.permission_cache") as mock_cache:
        mock_cache.get.return_value = True
        dep = require_page("output")
        assert dep(user) is user
        mock_cache.get.assert_called_once_with("operator", "output")
