"""/api/admin/* 路由: list/create/patch users, reset password, invite mgmt

(2026-06-17) v2 RBAC:
- require_admin 替成 require_super_admin (更严, admin 看不到 admin 后台)
- invite + PATCH body 加 role 字段 (替原 is_admin)
- AccountOut 返 role 字段
"""

from __future__ import annotations

import os
import secrets
from datetime import datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import or_

from ..core.audit import audited
from ..middleware.auth import CurrentUser
from ..permissions.guards import require_super_admin
from ..storage.session import session_scope
from ..utils.timezone import HKT
from . import account_service
from .account_models import Account, Invite
from .models import User

router = APIRouter(prefix="/api/admin", tags=["admin"])


# require_admin = require_super_admin (v2: admin 后台仅 super_admin 可访)
# 保留别名供现有测试 + router 引用.
require_admin = require_super_admin


# --- GET /api/admin/users ---


class UserItem(BaseModel):
    id: int = Field(..., description="User 主键")
    email: str | None = Field(None, description="账号邮箱; 匿名用户为 null")
    display_name: str | None = Field(None, description="显示名")
    role: str = Field(..., description="角色名; 匿名用户固定 'user'")  # (2026-06-17) 替原 is_admin
    is_admin: bool = Field(..., description="派生: role in ('admin', 'super_admin')")  # 派生 (兼容旧前端)
    is_active: bool = Field(..., description="是否启用; 匿名用户永远 True")
    kind: Literal["account", "anon"] = Field(..., description="'account' = 正式账号, 'anon' = 匿名 token 用户")
    account_id: int | None = Field(None, description="关联 Account.id; 匿名用户为 null")
    created_at: datetime = Field(..., description="ISO 8601 时间字符串")
    last_seen_at: datetime = Field(..., description="ISO 8601 时间字符串")
    last_login_at: datetime | None = Field(None, description="最近登录时间; 匿名用户为 null")


class UserListResponse(BaseModel):
    items: list[UserItem] = Field(..., description="列表, 元素是 UserItem 对象")
    total: int = Field(..., description="满足过滤条件的总条数 (受分页影响前)")
    page: int = Field(..., ge=1, description="当前页码, 1-based")
    page_size: int = Field(..., ge=1, le=100, description="每页条数")


@router.get(
    "/users",
    response_model=UserListResponse,
    summary="列所有用户",
    description=(
        "## 用途\n\n"
        "列出所有 `users` 行 + 关联 `Account` 信息 (anon user 无 email/role), 支持搜索/分页/过滤. "
        "用于 super_admin 后台用户管理.\n\n"
        "## 鉴权\n\n"
        "`require_super_admin` (v2: admin 后台仅 super_admin 可访; admin role 会被 403). "
        "**alias 兼容**: 函数名仍是 `require_admin` (内部 = `require_super_admin`).\n\n"
        "## 行为\n\n"
        "**kind / is_active 下推到 SQL WHERE** (在 LIMIT 前), 避免真实 bug: page 1 LIMIT 20 撞到全是 anon, "
        "后置过滤返空 items 但 `total` 仍含全部. 真案: 49 用户, page_size=20 时第一页 20 条全是 anon, "
        "`kind=account` 返 0 条但 `total=49`. "
        "搜索: email / display_name LIKE 匹配. "
        "anon 永远 `is_active=True`; account 看 `Account.is_active`. "
        "排序: `User.id DESC`, 分页 `page/page_size` (page_size 1-100)."
    ),
    responses={
        200: {"description": "成功, 返 `{items, total, page, page_size}`"},
        403: {"description": "非 super_admin 角色 (admin role 也会被拒, v2 RBAC)"},
    },
)
def list_users(
    user: CurrentUser = Depends(require_admin),
    search: str | None = None,
    kind: Literal["account", "anon"] | None = None,
    is_active: bool | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    with session_scope() as s:
        # JOIN users + accounts 拿全信息
        q = s.query(User, Account).outerjoin(Account, User.account_id == Account.id)
        if search:
            like = f"%{search}%"
            q = q.filter(or_(Account.email.like(like), User.display_name.like(like)))
        # kind 下推到 SQL (anon user 的 User.account_id IS NULL)
        if kind == "account":
            q = q.filter(User.account_id.isnot(None))
        elif kind == "anon":
            q = q.filter(User.account_id.is_(None))
        # is_active 下推到 SQL (anon 永远 True, account 看 Account.is_active)
        if is_active is True:
            q = q.filter(or_(Account.is_active.is_(True), User.account_id.is_(None)))
        elif is_active is False:
            q = q.filter(User.account_id.isnot(None), Account.is_active.is_(False))
        # 总数
        total = q.count()
        # 排序 + 分页
        q = q.order_by(User.id.desc()).offset((page - 1) * page_size).limit(page_size)
        rows = q.all()

        items: list[UserItem] = []
        for u, a in rows:
            row_kind: Literal["account", "anon"] = "account" if a is not None else "anon"
            role = a.role if a else "user"
            items.append(
                UserItem(
                    id=u.id,
                    email=a.email if a else None,
                    display_name=u.display_name,
                    role=role,
                    is_admin=role in ("admin", "super_admin"),
                    is_active=a.is_active if a else True,
                    kind=row_kind,
                    account_id=a.id if a else None,
                    created_at=u.created_at,
                    last_seen_at=u.last_seen_at,
                    last_login_at=a.last_login_at if a else None,
                )
            )
    return UserListResponse(items=items, total=total, page=page, page_size=page_size)


# --- POST /api/admin/users (创 invite) ---


class CreateInviteRequest(BaseModel):
    email: str = Field(..., max_length=254, description="被邀请人邮箱")
    role: str = Field(
        "user", description="邀请关联的角色名, 必须是 roles 表里存在的; 不能是 'super_admin'"
    )  # (2026-06-17) 替原 is_admin bool
    display_name: str | None = Field(None, description="可选显示名, 写入 Account.display_name")


class CreateInviteResponse(BaseModel):
    invite_token: str = Field(..., description="邀请 token, 拼到 /invite/{token} 链接")
    invite_url: str = Field(..., description="完整邀请 URL: /zh/invite/{invite_token}")
    email: str = Field(..., description="被邀请人邮箱")
    role: str = Field(..., description="邀请关联的角色名, 返 role (替原 is_admin)")  # 返 role (替原 is_admin)
    is_admin: bool = Field(..., description="派生: role in ('admin', 'super_admin')")  # 派生 (兼容)


@router.post(
    "/users",
    response_model=CreateInviteResponse,
    summary="创建邀请",
    description=(
        "## 用途\n\n"
        "super_admin 创 invite 行 (不创 account, 兑换时由 `/api/invites/{token}/redeem` 创). "
        "返 invite_token + invite_url, admin 复制手工发给被邀请人.\n\n"
        "## 鉴权\n\n"
        "`require_super_admin`. **拒绝 `admin` role** (v2 RBAC).\n\n"
        "## 行为\n\n"
        "**守卫**: `role='super_admin'` 拒绝 (400, 防越权创超级管理员). "
        "未知 role (不在 `roles` 表) → 400 `unknown role: <name>`. "
        "email 已注册 → 409 `email already registered`. "
        "已有未用 invite (redeemed_at IS NULL 且未过期) → 409 `pending invite exists`. "
        "**成功**: 创 `Invite` 行 (token 32 字节, expires_at 默认 7 天由 env `INVITE_EXPIRES_DAYS` 控制). "
        "返 `{invite_token, invite_url, email, role, is_admin 派生}`."
    ),
    responses={
        200: {"description": "成功, 返 `{invite_token, invite_url, email, role, is_admin}`"},
        400: {"description": "拒绝创 super_admin invite / role 不在 roles 表"},
        403: {"description": "非 super_admin 角色"},
        409: {"description": "email 已注册 / 已有未用 invite"},
    },
)
def create_invite(
    req: CreateInviteRequest,
    admin: CurrentUser = Depends(require_admin),
):
    # 拒绝创 super_admin invite (防越权)
    if req.role == "super_admin":
        raise HTTPException(status_code=400, detail="cannot create super_admin invite")
    # 防循环: Role 顶层 import 触发 permissions 整模块装载 (含 cache 子模块)
    from ..permissions.models import Role  # noqa: E402

    with session_scope() as s:
        if not s.query(Role).filter_by(name=req.role).first():
            raise HTTPException(status_code=400, detail=f"unknown role: {req.role}")
        # 重复 email
        if s.query(Account).filter_by(email=req.email).first() is not None:
            raise HTTPException(status_code=409, detail="email already registered")
        # 已有未用 invite
        now_naive = datetime.now(HKT).replace(tzinfo=None)
        existing = (
            s.query(Invite).filter_by(email=req.email, redeemed_at=None).filter(Invite.expires_at > now_naive).first()
        )
        if existing is not None:
            raise HTTPException(status_code=409, detail="pending invite exists")

        inviter_id = admin.account_id or 0
        token = account_service.generate_token()
        invite = Invite(
            token=token,
            email=req.email,
            invited_by_account_id=inviter_id,
            expires_at=now_naive + timedelta(days=int(os.getenv("INVITE_EXPIRES_DAYS", "7"))),
            created_at=now_naive,
        )
        s.add(invite)
        s.flush()
    return CreateInviteResponse(
        invite_token=token,
        invite_url=f"/zh/invite/{token}",
        email=req.email,
        role=req.role,
        is_admin=req.role in ("admin", "super_admin"),
    )


# --- PATCH /api/admin/users/{user_id} ---


class PatchUserRequest(BaseModel):
    is_active: bool | None = Field(None, description="新启用状态; 自禁 → 400")
    role: str | None = Field(
        None, description="新角色; 改自己降权 → 400; anon user 不接受"
    )  # (2026-06-17) 替原 is_admin
    display_name: str | None = Field(None, max_length=64, description="新显示名")


@router.patch(
    "/users/{user_id}",
    summary="修改用户字段",
    description=(
        "## 用途\n\n"
        "改 user 或关联 account 字段 (`is_active` / `role` / `display_name`). 批量更新用户状态/权限用.\n\n"
        "## 鉴权\n\n"
        "`require_super_admin`. 拒绝 `admin` role (v2 RBAC).\n\n"
        "## 行为\n\n"
        "**守卫**:\n"
        "- `user_id` 不存在 → 404 `user not found`\n"
        "- 自禁 (`is_active=false` 且 admin.id == target.id`) → 400 `cannot disable self`\n"
        "- 改自己 role 为非 `super_admin` (admin.id == target.id) → 400 `cannot demote self from super_admin` (防降权锁死)\n"
        "- 未知 role (不在 `roles` 表) → 400 `unknown role: <name>`\n"
        "- anon user (`account_id IS NULL`) 改 `role` 字段 → 400 `anon user cannot have role`\n"
        "- `Account` 行缺失 (data inconsistency) → 500 `account not found`\n\n"
        "**字段语义**: `is_active` 改 `Account.is_active`; `role` 改 `Account.role`; `display_name` 改 `User.display_name`."
    ),
    responses={
        200: {"description": "成功, 返 `{id, ok: true}`"},
        400: {"description": "自禁 / 自降权 / 未知 role / anon user 改 role"},
        403: {"description": "非 super_admin 角色"},
        404: {"description": "user_id 不存在"},
        500: {"description": "Account 行缺失 (data inconsistency)"},
    },
)
@audited("role.change", target_type="user")
@audited("account.disable", target_type="user")
@audited("account.enable", target_type="user")
async def patch_user(
    request: Request,
    user_id: int,
    req: PatchUserRequest,
    admin: CurrentUser = Depends(require_admin),
):
    request.state.audit_ctx.set(
        target_id=str(user_id),
    )
    with session_scope() as s:
        target = s.get(User, user_id)
        if target is None:
            raise HTTPException(status_code=404, detail="user not found")

        # 自禁守卫
        if req.is_active is False and admin.id == target.id:
            raise HTTPException(status_code=400, detail="cannot disable self")

        # 改 users.display_name
        if req.display_name is not None:
            target.display_name = req.display_name

        # 改 account 字段
        if target.account_id is not None:
            account = s.get(Account, target.account_id)
            if account is None:
                raise HTTPException(status_code=500, detail="account not found")

            if req.is_active is not None:
                account.is_active = req.is_active
            if req.role is not None:
                # 拒绝改自己为非 super_admin
                if admin.id == target.id and req.role != "super_admin":
                    raise HTTPException(status_code=400, detail="cannot demote self from super_admin")
                # 校验 role 在 roles 表
                # 防循环: 同上, Role 顶层 import 触发 permissions 全装载
                from ..permissions.models import Role  # noqa: E402

                if not s.query(Role).filter_by(name=req.role).first():
                    raise HTTPException(status_code=400, detail=f"unknown role: {req.role}")
                account.role = req.role
        else:
            # anon user 不允许改 role
            if req.role is not None:
                raise HTTPException(status_code=400, detail="anon user cannot have role")

        s.flush()

    return {"id": user_id, "ok": True}


# --- POST /api/admin/users/{user_id}/reset-password ---


@router.post(
    "/users/{user_id}/reset-password",
    summary="admin 重置用户密码",
    description=(
        "## 用途\n\n"
        "super_admin 替 user 重设密码, 返临时密码 (admin 复制手工发给用户, 无邮件服务). "
        "用户下次登录需用此临时密码, 建议提示用户登录后改密码.\n\n"
        "## 鉴权\n\n"
        "`require_super_admin`. 拒绝 `admin` role (v2 RBAC).\n\n"
        "## 行为\n\n"
        "**守卫**: `user_id` 不存在 → 400 `user has no account`; "
        "anon user (`account_id IS NULL`) → 400 `user has no account` (anon 无密码概念). "
        "Account 行缺失 (data inconsistency) → 404 `account not found`. "
        "**临时密码**: 12 字节 `secrets.token_urlsafe(12)`, URL-safe base64 编码, "
        "**body 直接返明文**: 一次性明文, 不存盘, 不发邮件, admin 复制后即丢, 重置可再生新临时密码."
    ),
    responses={
        200: {"description": "成功, 返 `{temp_password: <明文临时密码>}` (一次性, 不存盘)"},
        400: {"description": "user 不存在 / anon user 无 account"},
        403: {"description": "非 super_admin 角色"},
        404: {"description": "Account 行缺失 (data inconsistency)"},
    },
)
def reset_user_password(
    user_id: int,
    admin: CurrentUser = Depends(require_admin),
):
    with session_scope() as s:
        target = s.get(User, user_id)
        if target is None or target.account_id is None:
            raise HTTPException(status_code=400, detail="user has no account")
        account = s.get(Account, target.account_id)
        if account is None:
            raise HTTPException(status_code=404, detail="account not found")
        temp = secrets.token_urlsafe(12)
        account.password_hash = account_service.hash_password(temp)
        s.flush()
    return {"temp_password": temp}


# --- GET /api/admin/invites (邀列表 + status 过滤) ---


class InviteItem(BaseModel):
    id: int = Field(..., description="Invite 主键")
    token: str = Field(..., description="邀请 token, 用于 /api/admin/invites/{token} 撤销")
    email: str = Field(..., description="被邀请人邮箱")
    invited_by_account_id: int = Field(..., description="发起邀请的 super_admin account_id")
    expires_at: datetime = Field(..., description="ISO 8601 时间字符串")
    redeemed_at: datetime | None = Field(None, description="兑换时间; 未兑换为 null")
    created_at: datetime = Field(..., description="ISO 8601 时间字符串")


class InviteListResponse(BaseModel):
    items: list[InviteItem] = Field(..., description="列表, 元素是 InviteItem 对象")
    total: int = Field(..., description="满足 status 过滤的总条数")


@router.get(
    "/invites",
    response_model=InviteListResponse,
    summary="列邀请",
    description=(
        "## 用途\n\n"
        "列 invite 行 + status 过滤. 用于 super_admin 后台审计 invite 状态.\n\n"
        "## 鉴权\n\n"
        "`require_super_admin`. 拒绝 `admin` role (v2 RBAC).\n\n"
        "## 行为\n\n"
        "**status 过滤语义**:\n"
        "- `pending`: `redeemed_at IS NULL AND expires_at > now` (未用且未过期)\n"
        "- `redeemed`: `redeemed_at IS NOT NULL` (已用, 含过期)\n"
        "- `expired`: `redeemed_at IS NULL AND expires_at <= now` (未用但过期)\n"
        "- `all`: 不过滤, 默认\n\n"
        "**limit 200**: 硬编码 `LIMIT 200` (按 `Invite.id DESC`). 不支持分页参数. "
        "返 `{items, total}` (total 是过滤后总数, 不受 LIMIT 影响). "
        "兼容 naive/aware datetime: 统一 `now.replace(tzinfo=None)` 后比."
    ),
    responses={
        200: {"description": "成功, 返 `{items, total}` (按 `status` 过滤后)"},
        403: {"description": "非 super_admin 角色"},
    },
)
def list_invites(
    admin: CurrentUser = Depends(require_admin),
    status: Literal["pending", "redeemed", "expired", "all"] = "all",
):
    with session_scope() as s:
        q = s.query(Invite)
        now_naive = datetime.now(HKT).replace(tzinfo=None)
        if status == "pending":
            q = q.filter(Invite.redeemed_at.is_(None), Invite.expires_at > now_naive)
        elif status == "redeemed":
            q = q.filter(Invite.redeemed_at.isnot(None))
        elif status == "expired":
            q = q.filter(Invite.redeemed_at.is_(None), Invite.expires_at <= now_naive)
        total = q.count()
        rows = q.order_by(Invite.id.desc()).limit(200).all()
        items = [
            InviteItem(
                id=r.id,
                token=r.token,
                email=r.email,
                invited_by_account_id=r.invited_by_account_id,
                expires_at=r.expires_at,
                redeemed_at=r.redeemed_at,
                created_at=r.created_at,
            )
            for r in rows
        ]
    return InviteListResponse(items=items, total=total)


# --- DELETE /api/admin/invites/{token} (撤销未 redeem 的 invite) ---


@router.delete(
    "/invites/{token}",
    summary="撤销未 redeem 邀请",
    description=(
        "## 用途\n\n"
        "撤销 (硬删) 未 redeem 的 invite. 已 redeem 的 invite 保留作审计, 不允许删.\n\n"
        "## 鉴权\n\n"
        "`require_super_admin`. 拒绝 `admin` role (v2 RBAC).\n\n"
        "## 行为\n\n"
        "**守卫**: `token` 不存在 → 404 `invite not found`. "
        "**已 redeem (`redeemed_at IS NOT NULL`) → 400 `invite already redeemed`**: 保留审计链, 防止 admin 误删已兑换的 invite 抹掉谁接受了邀请的记录. "
        "**成功**: `s.delete(inv)` + flush, 返 `{ok: true}`. "
        "匿名撤销 (不是 admin 触发) 不可行, 必须 super_admin token."
    ),
    responses={
        200: {"description": "成功, 返 `{ok: true}`"},
        400: {"description": "invite 已 redeem (保留审计, 不允许删)"},
        403: {"description": "非 super_admin 角色"},
        404: {"description": "token 不存在"},
    },
)
def delete_invite(token: str, admin: CurrentUser = Depends(require_admin)):
    with session_scope() as s:
        inv = s.query(Invite).filter_by(token=token).first()
        if inv is None:
            raise HTTPException(status_code=404, detail="invite not found")
        if inv.redeemed_at is not None:
            raise HTTPException(status_code=400, detail="invite already redeemed")
        s.delete(inv)
        s.flush()
    return {"ok": True}
