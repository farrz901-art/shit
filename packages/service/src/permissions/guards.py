"""FastAPI Depends 守卫: page-level (require_page) + resource-level (require_super_admin, require_account)

- require_page("knowledge"): 查 cache 验 role × page 权限, super_admin 短路
- require_super_admin: 严验 role == "super_admin", 用于 admin/permissions/health 等
- require_account: 禁 anon (is_account=False), 用于 /api/memory/*
"""

from __future__ import annotations

from fastapi import Depends, HTTPException

from ..middleware.auth import CurrentUser, resolve_user
from .cache import permission_cache


def require_page(page_key: str):
    """工厂: 返 FastAPI Depends 闭包"""

    def _dep(user: CurrentUser = Depends(resolve_user)) -> CurrentUser:
        if user.role == "super_admin":
            return user  # meta 豁免
        if not permission_cache.get(user.role, page_key):
            raise HTTPException(
                status_code=403,
                detail=f"page '{page_key}' not allowed for role '{user.role}'",
            )
        return user

    return _dep


def require_super_admin(user: CurrentUser = Depends(resolve_user)) -> CurrentUser:
    if user.role != "super_admin":
        raise HTTPException(status_code=403, detail="super_admin required")
    return user


def require_account(user: CurrentUser = Depends(resolve_user)) -> CurrentUser:
    """记忆端点用, 禁 anon"""
    if not user.is_account:
        raise HTTPException(status_code=403, detail="login required")
    return user


def require_active_account(user: CurrentUser = Depends(require_account)) -> CurrentUser:
    """require_account + 校验 is_active=True + 非 pending_deletion. 写操作路由用这个.

    pending_deletion 期间禁用所有写操作 (除 DELETE /deletion 撤销自己 — 走 require_account).
    详情见 spec §5.2 行为表.
    """
    if not user.is_active:
        raise HTTPException(status_code=403, detail="account disabled")
    if user.is_pending_deletion:
        raise HTTPException(status_code=403, detail="account is pending deletion")
    return user
