"""/api/permissions + /api/permissions/me + /api/roles/* 端点"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import cast

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..auth.account_models import Account
from ..middleware.auth import CurrentUser, resolve_user
from ..storage.session import session_scope
from .cache import (
    get_all_page_keys_sync,
    get_all_page_metadata_sync,
    permission_cache,
)
from .guards import require_super_admin
from .models import Role, RolePermission
from .service import get_full_matrix, get_my_permissions, update_permissions

router = APIRouter(prefix="/api", tags=["permissions"])


# ============================================================
# /api/permissions
# ============================================================


class PermissionUpdate(BaseModel):
    role_name: str = Field(..., description="角色名, 必须是 `roles` 表里存在的, 例: 'admin' / 'user' / 自定义")
    page_key: str = Field(
        ..., description="页面 key, 7 选 1: dashboard / knowledge / chat / memory / evaluate / submissions / admin"
    )
    allowed: bool = Field(..., description="true=允许访问, false=拒绝")


class PermissionsPatchRequest(BaseModel):
    updates: list[PermissionUpdate] = Field(..., description="批量更新项, 一次 commit 全部生效")


@router.get(
    "/permissions",
    summary="查询完整权限矩阵",
    description=(
        "## 用途\n\n"
        "返回所有非 super_admin 角色 + role×page 权限矩阵 + 页面元数据, 供 super_admin 后台管理权限.\n\n"
        "## 鉴权\n\n"
        "`require_super_admin` 守卫, 仅 super_admin 可调.\n\n"
        "## 行为\n\n"
        "super_admin 行代码层过滤掉 (meta 豁免, 永远全权限). "
        "PermissionCache.invalidate() 强制刷新以反映最近的 PATCH/POST/DELETE. "
        "返回结构: {roles[], matrix{role_name: {page_key: bool}}, pages[]}."
    ),
    responses={
        200: {"description": "返回 {roles[], matrix{}, pages[]}"},
        401: {"description": "未登录 / token 无效"},
        403: {"description": "非 super_admin"},
    },
)
def get_permissions(user: CurrentUser = Depends(require_super_admin)):
    with session_scope() as s:
        roles = [
            {
                "name": r.name,
                "label_zh": r.label_zh,
                "label_en": r.label_en,
                "is_system": r.is_system,
                "is_deletable": r.is_deletable,
            }
            for r in s.query(Role).all()
            if cast(str, r.name) != "super_admin"
        ]
    matrix = get_full_matrix()
    return {
        "roles": roles,
        "matrix": matrix,
        "pages": get_all_page_metadata_sync(),
    }


@router.patch(
    "/permissions",
    summary="批量更新权限矩阵",
    description=(
        "## 用途\n\n"
        "一次 commit 批量更新多个 (role, page_key) 的 allowed 状态, 供 super_admin 后台调整权限矩阵.\n\n"
        "## 鉴权\n\n"
        "`require_super_admin` 守卫, 仅 super_admin 可调.\n\n"
        "## 行为\n\n"
        "拒绝改 super_admin 行 (meta 豁免) → 400. 拒绝未知 page_key → 400. "
        "拒绝未知 role_name → 400. 全部 pre-check 通过后一次事务提交, "
        "PermissionCache.invalidate() 强制刷新."
    ),
    responses={
        200: {"description": "返回 {updated: int} (实际更新条数)"},
        400: {"description": "试图改 super_admin 行 / page_key 未知 / role_name 不存在"},
        401: {"description": "未登录 / token 无效"},
        403: {"description": "非 super_admin"},
        422: {"description": "Pydantic 校验失败 (字段类型错 / 长度越界)"},
    },
)
def patch_permissions(
    req: PermissionsPatchRequest,
    user: CurrentUser = Depends(require_super_admin),
):
    for u in req.updates:
        if u.role_name == "super_admin":
            raise HTTPException(status_code=400, detail="cannot modify super_admin permissions")
        if u.page_key not in get_all_page_keys_sync():
            raise HTTPException(status_code=400, detail=f"unknown page_key: {u.page_key}")
        with session_scope() as s:
            if not s.query(Role).filter_by(name=u.role_name).first():
                raise HTTPException(status_code=400, detail=f"unknown role: {u.role_name}")
    updated = update_permissions([u.model_dump() for u in req.updates])
    return {"updated": updated}


@router.get(
    "/permissions/me",
    summary="查询当前用户权限",
    description=(
        "## 用途\n\n"
        "返回当前用户的角色 + 可访问的 page_key 列表 + 页面元数据, 供前端侧边栏 / 路由守卫动态渲染.\n\n"
        "## 鉴权\n\n"
        "`resolve_user` 守卫, 匿名 (anon token) 也可调.\n\n"
        "## 行为\n\n"
        "anon (is_account=False) role 默认 `user`, 拿到 user 角色的 allowed 列表. "
        "登录用户用其 account.role 查矩阵. "
        "返回结构: {role: str, allowed: list[page_key], pages[]}."
    ),
    responses={
        200: {"description": "返回 {role, allowed[], pages[]}"},
    },
)
def my_permissions(user: CurrentUser = Depends(resolve_user)):
    return {
        "role": user.role,
        "account_id": user.account_id,
        "allowed": get_my_permissions(user.role),
        "pages": get_all_page_metadata_sync(),
    }


# ============================================================
# /api/roles
# ============================================================

# role name 格式: 2-32 字符 [a-z0-9_]
ROLE_NAME_PATTERN = re.compile(r"^[a-z0-9_]{2,32}$")


class CreateRoleRequest(BaseModel):
    name: str = Field(..., description="角色标识, 例: 'reviewer' / 'editor' (小写字母数字下划线)")
    label_zh: str = Field(..., description="中文显示名, 例: '审核员'")
    label_en: str = Field(..., description="英文显示名, 例: 'Reviewer'")
    permissions: dict[str, bool] = Field(
        default_factory=dict, description="初始权限矩阵, key 为 page_key, value 为 allowed; 未知 key 跳过"
    )


class UpdateRoleRequest(BaseModel):
    label_zh: str | None = Field(None, description="新中文 label; 传 null 不改")
    label_en: str | None = Field(None, description="新英文 label; 传 null 不改")


@router.get(
    "/roles",
    summary="列所有角色",
    description=(
        "## 用途\n\n"
        "列出全部角色 (含 system / 自定义) + 占用此角色的 user_count, 供 super_admin 后台管理角色.\n\n"
        "## 鉴权\n\n"
        "`require_super_admin` 守卫, 仅 super_admin 可调.\n\n"
        "## 行为\n\n"
        "user_count 通过 `Account.role = name` 实时统计, 无分页. "
        "返回结构: {roles: [{name, label_zh, label_en, is_system, is_deletable, user_count, created_at, updated_at}]}. "
        "PermissionCache.invalidate() 强制刷新以反映最近的 PATCH/POST/DELETE."
    ),
    responses={
        200: {"description": "返回 {roles[]} (含 user_count + 时间戳)"},
        401: {"description": "未登录 / token 无效"},
        403: {"description": "非 super_admin"},
    },
)
def get_roles(user: CurrentUser = Depends(require_super_admin)):
    with session_scope() as s:
        result = []
        for r in s.query(Role).all():
            count = s.query(Account).filter_by(role=r.name).count()
            result.append(
                {
                    "name": r.name,
                    "label_zh": r.label_zh,
                    "label_en": r.label_en,
                    "is_system": r.is_system,
                    "is_deletable": r.is_deletable,
                    "user_count": count,
                    "created_at": r.created_at.isoformat() if bool(r.created_at) else None,
                    "updated_at": r.updated_at.isoformat() if bool(r.updated_at) else None,
                }
            )
    return {"roles": result}


@router.post(
    "/roles",
    status_code=201,
    summary="创建自定义角色",
    description=(
        "## 用途\n\n"
        "创建自定义角色 + 初始权限矩阵, 供 super_admin 扩展 RBAC 配置.\n\n"
        "## 鉴权\n\n"
        "`require_super_admin` 守卫, 仅 super_admin 可调.\n\n"
        "## 行为\n\n"
        "name 必须 match `[a-z0-9_]{2,32}`. 拒绝保留名 `super_admin` (meta 豁免) → 400. "
        "重复 name → 409. 初始 permissions 中未知 page_key 自动跳过, 不报错. "
        "创建后 PermissionCache.invalidate() 强制刷新. "
        "返回结构: {name, label_zh, label_en, is_system: false, is_deletable: true}."
    ),
    responses={
        201: {"description": "创建成功, 返回角色对象"},
        400: {"description": "name 格式不匹配 / name 保留为 'super_admin'"},
        401: {"description": "未登录 / token 无效"},
        403: {"description": "非 super_admin"},
        409: {"description": "role name 已存在"},
        422: {"description": "Pydantic 校验失败"},
    },
)
def create_role(
    req: CreateRoleRequest,
    user: CurrentUser = Depends(require_super_admin),
):
    if not ROLE_NAME_PATTERN.match(req.name):
        raise HTTPException(status_code=400, detail="name must match [a-z0-9_]{2,32}")
    if req.name == "super_admin":
        raise HTTPException(status_code=400, detail="cannot create role 'super_admin'")
    with session_scope() as s:
        if s.query(Role).filter_by(name=req.name).first():
            raise HTTPException(status_code=409, detail=f"role name '{req.name}' exists")
        # 创 Role
        now = datetime.now(UTC)
        role = Role(
            name=req.name,
            label_zh=req.label_zh,
            label_en=req.label_en,
            is_system=False,
            is_deletable=True,
            created_at=now,
            updated_at=now,
        )
        s.add(role)
        s.flush()
        # 创 role_permissions (跳过未知 page_key)
        for page_key, allowed in req.permissions.items():
            if page_key not in get_all_page_keys_sync():
                continue
            s.add(
                RolePermission(
                    role_name=req.name,
                    page_key=page_key,
                    allowed=allowed,
                    created_at=now,
                    updated_at=now,
                )
            )
        s.flush()
    # (2026-06-18 redis) invalidate 内部已 DEL Redis key, 跨 worker 生效
    permission_cache.invalidate()
    return {
        "name": role.name,
        "label_zh": role.label_zh,
        "label_en": role.label_en,
        "is_system": role.is_system,
        "is_deletable": role.is_deletable,
    }


@router.patch(
    "/roles/{name}",
    summary="修改角色 label",
    description=(
        "## 用途\n\n"
        "修改角色的中英文显示名 (label), 供 super_admin 本地化角色展示.\n\n"
        "## 鉴权\n\n"
        "`require_super_admin` 守卫, 仅 super_admin 可调.\n\n"
        "## 行为\n\n"
        "name (URL path) 不可改. 仅修改 label_zh / label_en (传 null 不改). "
        "系统角色 (is_system=True) 也能改 label, 但不能删 (受 DELETE 守卫). "
        "不存在 → 404. 修改后 PermissionCache.invalidate() 强制刷新. "
        "返回结构: {name, label_zh, label_en, is_system, is_deletable}."
    ),
    responses={
        200: {"description": "修改成功, 返回最新角色对象"},
        401: {"description": "未登录 / token 无效"},
        403: {"description": "非 super_admin"},
        404: {"description": "role name 不存在"},
        422: {"description": "Pydantic 校验失败"},
    },
)
def update_role(
    name: str,
    req: UpdateRoleRequest,
    user: CurrentUser = Depends(require_super_admin),
):
    with session_scope() as s:
        role = s.query(Role).filter_by(name=name).first()
        if role is None:
            raise HTTPException(status_code=404, detail="role not found")
        if req.label_zh is not None:
            role.label_zh = req.label_zh  # type: ignore[assignment]
        if req.label_en is not None:
            role.label_en = req.label_en  # type: ignore[assignment]
        role.updated_at = datetime.now(UTC)  # type: ignore[assignment]
        s.flush()
    # (2026-06-18 redis) invalidate 内部已 DEL Redis key, 跨 worker 生效
    permission_cache.invalidate()
    return {
        "name": role.name,
        "label_zh": role.label_zh,
        "label_en": role.label_en,
        "is_system": role.is_system,
        "is_deletable": role.is_deletable,
    }


@router.delete(
    "/roles/{name}",
    status_code=204,
    summary="删除自定义角色",
    description=(
        "## 用途\n\n"
        "删除自定义角色及其关联的 role_permissions 行, 供 super_admin 清理不再使用的角色.\n\n"
        "## 鉴权\n\n"
        "`require_super_admin` 守卫, 仅 super_admin 可调.\n\n"
        "## 行为\n\n"
        "系统角色 (is_deletable=False, e.g. `user` / `admin` / `super_admin`) → 400. "
        "还有用户占用 (Account.role = name) → 409. 不存在 → 404. "
        "删除后 PermissionCache.invalidate() 强制刷新. "
        "返回 204 No Content."
    ),
    responses={
        204: {"description": "删除成功, 无 body"},
        400: {"description": "系统角色不可删 (is_deletable=False)"},
        401: {"description": "未登录 / token 无效"},
        403: {"description": "非 super_admin"},
        404: {"description": "role name 不存在"},
        409: {"description": "角色仍被 N 个用户占用"},
    },
)
def delete_role(name: str, user: CurrentUser = Depends(require_super_admin)):
    with session_scope() as s:
        role = s.query(Role).filter_by(name=name).first()
        if role is None:
            raise HTTPException(status_code=404, detail="role not found")
        if not bool(role.is_deletable):
            raise HTTPException(status_code=400, detail=f"cannot delete system role '{name}'")
        # 校验 user_count
        count = s.query(Account).filter_by(role=name).count()
        if count > 0:
            raise HTTPException(status_code=409, detail=f"role in use by {count} users")
        # 删 role + 关联 role_permissions
        s.query(RolePermission).filter_by(role_name=name).delete()
        s.delete(role)
        s.flush()
    # (2026-06-18 redis) invalidate 内部已 DEL Redis key, 跨 worker 生效
    permission_cache.invalidate()
    return None
