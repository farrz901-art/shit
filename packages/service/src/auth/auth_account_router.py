"""/api/account/* 路由: login, logout, me, seed-admin, forgot-password, reset-password"""

from __future__ import annotations

import os
import secrets
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

from ..core.audit import audited
from ..core.rate_limiter import check_and_increment
from ..middleware.auth import CurrentUser, resolve_user
from ..storage.session import session_scope
from ..utils.timezone import HKT
from . import account_service
from .account_models import Account, PasswordReset
from .models import User

router = APIRouter(prefix="/api/account", tags=["account"])

# cookie 名: 跟现有 anon 共用
COOKIE_NAME = "rag_user_token"
COOKIE_MAX_AGE = 60 * 60 * 24 * 7  # 7 天
COOKIE_SECURE = os.getenv("ENV") == "production"


class LoginRequest(BaseModel):
    email: str = Field(..., max_length=254, description="账号邮箱, 例: admin@rag.local")
    password: str = Field(..., min_length=1, description="明文密码, 服务端 bcrypt 校验")


class AccountOut(BaseModel):
    id: int = Field(..., description="Account 主键")
    email: str = Field(..., description="账号邮箱")
    display_name: str | None = Field(None, description="显示名, 可空")
    role: str = Field(..., description="角色名, 例: 'user' / 'admin' / 'super_admin' (2026-06-17 替原 is_admin)")
    is_admin: bool = Field(..., description="派生: role in ('admin', 'super_admin') (兼容旧前端)")


class LoginResponse(BaseModel):
    token: str = Field(..., description="32 字节 hex, 客户端用此换 cookie")
    account: AccountOut = Field(..., description="账号信息对象, 见 AccountOut schema")
    pending_deletion: bool = Field(False, description="(T2.5 新加) 账号处于 pending_deletion 状态, 前端跳注销横幅")
    deletion_expires_at: datetime | None = Field(
        None, description="(T2.5 新加) 注销到期时间 (deletion_requested_at + 7d), pending=True 时填"
    )


@router.post(
    "/login",
    response_model=LoginResponse,
    summary="账号登录",
    description=(
        "## 用途\n\n"
        "email + password 验证, 成功返 token + Set-Cookie; 错密码/账号禁用/账号不存在 → 统一 401 (防探测).\n\n"
        "## 鉴权\n\n"
        "无 (公开端点).\n\n"
        "## 行为\n\n"
        "成功路径: 找/创 `users` 行 (`account_id` 关联), 写 `last_login_at` (HKT), "
        "Set-Cookie `rag_user_token` (HttpOnly, SameSite=Lax, 7 天, prod 加 secure). "
        "body 同时返 `token` + `account` 5 字段 (id/email/display_name/role/is_admin 派生). "
        "**T2.5 新增 (2026-06-17)**: body 额外返 `pending_deletion: bool` + `deletion_expires_at: ISO 8601 | null` "
        "(= `deletion_requested_at + 7d`, 仅 pending=True 时填). 前端用这 2 字段在登录后立即显示注销横幅. "
        "**错误合并**: 不存在和错密码都返 `invalid credentials`; 禁用返 `account disabled` (msg 不同但 status 都 401). "
        "首次登录时若 `users` 行未绑 account, 自动创一行 (`public_token` 32 字节 hex)."
    ),
    responses={
        200: {
            "description": "登录成功, body 返 `{token, account, pending_deletion, deletion_expires_at}` + Set-Cookie"
        },
        401: {"description": "email 不存在 / 密码错 / 账号被禁用 (统一 401 防探测)"},
        429: {"description": "(2026-06-18) 同一 IP 15min 内登录超过 5 次, 触发限流"},
    },
)
async def login(req: LoginRequest, response: Response, request: Request):
    # (2026-06-18) IP 限流, 防拤. login 5 次/15min. 超阈值返 429
    client_ip = request.client.host if request.client else "unknown"
    allowed, _ = await check_and_increment("login", client_ip)
    if not allowed:
        raise HTTPException(status_code=429, detail="登录请求过于频繁, 请 15 分钟后再试")
    with session_scope() as s:
        account = s.query(Account).filter_by(email=req.email).first()
        if not account:
            # 不存在 → 跟错密码同 message (防探测)
            raise HTTPException(status_code=401, detail="invalid credentials")
        if not account.is_active:
            raise HTTPException(status_code=401, detail="account disabled")
        if not account_service.verify_password(req.password, account.password_hash):
            raise HTTPException(status_code=401, detail="invalid credentials")

        # 找/创 users 行
        user = s.query(User).filter_by(account_id=account.id).first()
        if user is None:
            user = User(
                public_token=secrets.token_hex(32),
                display_name=account.display_name or account.email.split("@")[0],
                account_id=account.id,
            )
            s.add(user)
            s.flush()
        token = user.public_token

        # 更新 last_login_at (同一 session, 避免 SQLite "database is locked")
        account.last_login_at = datetime.now(HKT)

        # 序列化需要的字段 (s.flush 后属性已加载)
        account_payload = AccountOut(
            id=account.id,
            email=account.email,
            display_name=account.display_name,
            role=account.role,
            is_admin=account.role in ("admin", "super_admin"),
        )

    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        max_age=COOKIE_MAX_AGE,
        httponly=True,
        samesite="lax",
        path="/",
        secure=COOKIE_SECURE,
    )
    # T2.5 (2026-06-17): 检查 pending_deletion, 返前端跳注销横幅用
    if account.is_pending_deletion and account.deletion_requested_at is not None:
        return LoginResponse(
            token=token,
            account=account_payload,
            pending_deletion=True,
            deletion_expires_at=account.deletion_requested_at + timedelta(days=7),
        )
    return LoginResponse(
        token=token,
        account=account_payload,
        pending_deletion=False,
        deletion_expires_at=None,
    )


@router.post(
    "/logout",
    summary="登出 (清 cookie)",
    description=(
        "## 用途\n\n"
        "软登出: 清掉浏览器侧的 `rag_user_token` cookie, `users` 行不动 (不删 public_token, 不改 is_active).\n\n"
        "## 鉴权\n\n"
        "无 (公开端点, 即使没 cookie 也返 200, idempotent).\n\n"
        "## 行为\n\n"
        "调 `response.delete_cookie(COOKIE_NAME, path='/')` 触发浏览器删除 cookie. "
        "返 `{ok: true}`. 即使 client 没带 cookie 也 OK (浏览器侧删除是 idempotent 操作)."
    ),
    responses={
        200: {"description": "成功, 返 `{ok: true}` + Set-Cookie 删除指令"},
    },
)
def logout(response: Response):
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"ok": True}


@router.get(
    "/me",
    summary="查当前用户",
    description=(
        "## 用途\n\n"
        "返当前 `CurrentUser` 序列化的 11 字段 (`id`, `role`, `is_admin` 派生, `is_account`, "
        "`account_id`, `email`, `display_name`, `is_active`, `avatar_url`, `is_pending_deletion`, "
        "`deletion_expires_at`). 前端用此接口判登录态 + RBAC + 注销状态横幅.\n\n"
        "## 鉴权\n\n"
        "`resolve_user` (anon OK): 从 cookie 或 `x-user-token` header 解析 user; 解析失败仍返匿名 user.\n\n"
        "## 行为\n\n"
        "**字段演进 (2026-06-17)**: 加 `role` 字段替原 `is_admin` 为权威值, `is_admin` 改派生 (role in [admin, super_admin]). "
        "**T2.5 新增 (2026-06-17)**: `avatar_url` (头像 URI, 可能为 null), "
        "`is_pending_deletion` (bool, 派生自 `deletion_requested_at`), "
        "`deletion_expires_at` (ISO 8601 string, `deletion_requested_at + 7d`, pending=True 时填). "
        "**已删除**: `is_bootstrap_admin` (2026-06-14 业务侧不再区分 bootstrap admin / 真账号 admin). "
        "anon user 返 `role='user'`, `email=null`, `account_id=null`, `avatar_url=null`, "
        "`is_pending_deletion=false`, `deletion_expires_at=null`."
    ),
    responses={
        200: {"description": "成功, body 返 CurrentUser 字段 (anon 也返 200)"},
    },
)
def me(user: CurrentUser = Depends(resolve_user)):
    # T2.5 (2026-06-17): 计算 deletion_expires_at = deletion_requested_at + 7d
    deletion_expires_at: datetime | None = None
    if user.deletion_requested_at is not None:
        deletion_expires_at = user.deletion_requested_at + timedelta(days=7)
    return {
        "id": user.id,
        "role": user.role,
        "is_admin": user.is_admin,  # 派生 from role
        "is_account": user.is_account,
        "account_id": user.account_id,
        "email": user.email,
        "display_name": user.display_name,
        "is_active": user.is_active,
        "avatar_url": user.avatar_url,  # T2.5 新
        "is_pending_deletion": user.is_pending_deletion,  # T2.5 新
        "deletion_expires_at": deletion_expires_at,  # T2.5 新
    }


class SeedAdminRequest(BaseModel):
    email: str = Field(
        ..., max_length=254, description="首个 super_admin 邮箱"
    )  # 用 str 不用 EmailStr (避免 email-validator 依赖)
    password: str = Field(..., min_length=8, description="明文密码")
    display_name: str | None = Field(None, description="显示名, 默认取 email @ 前")


@router.post(
    "/seed-admin",
    summary="创建首个 super_admin",
    description=(
        "## 用途\n\n"
        "首次部署: 用环境变量 `RAG_ADMIN_TOKEN` 鉴权, 创首个 `super_admin` 账号 + 绑 `users` 行. "
        "已有 `super_admin` → 409, 重复 email → 409. 仅在初始化阶段可调.\n\n"
        "## 鉴权\n\n"
        "请求 header `x-admin-token` 必须等于环境变量 `RAG_ADMIN_TOKEN` (运维手工配). "
        "env 缺失或 token 不匹配 → 401.\n\n"
        "## 行为\n\n"
        "守卫: 已有 `role='super_admin'` 账号 → 409 `admin already initialized`. "
        "email 已注册 → 409 `email already registered`. "
        "成功 → 创 `Account(role='super_admin')` + `User(public_token=32B hex, account_id=...)` (同一事务). "
        "**body 不返 token**: seed-admin 完事后 admin 应走 `/api/account/login` 走正常登录拿 cookie."
    ),
    responses={
        200: {"description": "成功, body 返 `{account_id, email}`"},
        401: {"description": "env `RAG_ADMIN_TOKEN` 缺失 / header `x-admin-token` 不匹配"},
        409: {"description": "已存在 super_admin / email 已注册"},
    },
)
def seed_admin(req: SeedAdminRequest, request: Request):
    expected = os.getenv("RAG_ADMIN_TOKEN", "")
    if not expected or request.headers.get("x-admin-token") != expected:
        raise HTTPException(status_code=401, detail="invalid x-admin-token")

    with session_scope() as s:
        if s.query(Account).filter_by(role="super_admin").first() is not None:
            raise HTTPException(status_code=409, detail="admin already initialized")
        if s.query(Account).filter_by(email=req.email).first() is not None:
            raise HTTPException(status_code=409, detail="email already registered")

        account = Account(
            email=req.email,
            password_hash=account_service.hash_password(req.password),
            display_name=req.display_name or req.email.split("@")[0],
            role="super_admin",  # (2026-06-17) 替原 is_admin=True
            created_at=datetime.now(HKT),
        )
        s.add(account)
        s.flush()
        s.refresh(account)

        user = User(
            public_token=secrets.token_hex(32),
            display_name=account.display_name,
            account_id=account.id,
        )
        s.add(user)
        s.flush()
        account_id = account.id
        account_email = account.email

    return {"account_id": account_id, "email": account_email}


class ForgotPasswordRequest(BaseModel):
    email: str = Field(..., description="申请重置的邮箱; 邮箱不存在时仍返 200")


class ForgotPasswordResponse(BaseModel):
    reset_token: str | None = Field(None, description="重置 token; 邮箱不存在时为 null")
    reset_url: str | None = Field(None, description="重置 URL: /reset-password?token=...")


@router.post(
    "/forgot-password",
    response_model=ForgotPasswordResponse,
    summary="申请密码重置",
    description=(
        "## 用途\n\n"
        "申请重置: email 存在则创 `PasswordReset` 行 (含 token + expires_at), 返 reset_token + url; "
        "email 不存在也返 200 + null (不暴露邮箱是否注册).\n\n"
        "## 鉴权\n\n"
        "无 (公开端点, 用户没登录也能调).\n\n"
        "## 行为\n\n"
        "**统一响应**: 不论 email 是否存在都返 200 (响应体差异仅在 `reset_token`/`reset_url` 是否为 null). "
        "防止探测邮箱注册情况. token 寿命由 env `PASSWORD_RESET_EXPIRES_HOURS` 控制 (默认 1h). "
        "返的 url 形式 `/reset-password?token={token}`, admin 复制手工发给用户 (无邮件服务). "
        "**已用 token 不影响**: 用户可以反复申请, 旧 token 仍有效直到 expires_at."
    ),
    responses={
        200: {"description": "成功, body 返 `{reset_token, reset_url}` (不存在时为 null)"},
        429: {"description": "(2026-06-24) 同一 IP 15min 内申请超过 5 次, 触发限流"},
    },
)
async def forgot_password(request: Request, req: ForgotPasswordRequest):
    # (2026-06-24) IP 限流, 防邮箱枚举 / 骚扰. forgot_password 5 次/15min. 超阈值返 429
    client_ip = request.client.host if request.client else "unknown"
    allowed, _ = await check_and_increment("forgot_password", client_ip)
    if not allowed:
        raise HTTPException(status_code=429, detail="申请重置过于频繁, 请 15 分钟后再试")
    with session_scope() as s:
        account = s.query(Account).filter_by(email=req.email).first()
        if account is None:
            return ForgotPasswordResponse(reset_token=None, reset_url=None)
        token = account_service.generate_token()
        # SQLite 存 naive datetime, .replace(tzinfo=None) 防止 aware vs naive 比较报错
        expires_at = (datetime.now(HKT) + timedelta(hours=int(os.getenv("PASSWORD_RESET_EXPIRES_HOURS", "1")))).replace(
            tzinfo=None
        )
        s.add(
            PasswordReset(
                account_id=account.id,
                token=token,
                expires_at=expires_at,
                created_at=datetime.now(HKT),
            )
        )
        s.flush()
    # 返 URL 路径, admin 复制手工发
    return ForgotPasswordResponse(
        reset_token=token,
        reset_url=f"/reset-password?token={token}",
    )


class ResetPasswordRequest(BaseModel):
    token: str = Field(..., description="forgot-password 返的 reset_token")
    new_password: str = Field(..., min_length=8, description="新密码, ≥ 8 字符")


@router.post(
    "/reset-password",
    summary="用 token 重置密码",
    description=(
        "## 用途\n\n"
        "用 `/api/account/forgot-password` 拿到的 token 改密码, 同时标 `PasswordReset.used_at` "
        "防止 token 重复使用. 成功后用户可用新密码登录.\n\n"
        "## 鉴权\n\n"
        "无 (公开端点, 用户没登录也能调, token 本身就是凭证).\n\n"
        "## 行为\n\n"
        "**守卫**: token 不存在 / 已 used_at / 已过期 → 统一 400 `reset token invalid` (msg 统一防探测). "
        "`new_password` 必须 ≥ 8 字符 (Pydantic Field min_length=8, 否则 422). "
        "兼容 naive/aware datetime: 统一转 HKT 后跟 now 比, 避免 PG UTC 存 + HKT now 混比出错. "
        "成功 → 更新 `Account.password_hash` + 标 `used_at = now(HKT)`, 返 `{ok: true}`."
    ),
    responses={
        200: {"description": "成功, 返 `{ok: true}`, 密码已更新"},
        400: {"description": "token 不存在 / 已用过 / 已过期 (msg 统一为 `reset token invalid`)"},
        422: {"description": "`new_password` < 8 字符 (Pydantic 校验失败)"},
        429: {"description": "(2026-06-18) 同一 IP 1h 内重置超过 3 次, 触发限流"},
    },
)
@audited("password.reset", target_type="user")
async def reset_password(
    request: Request,
    req: ResetPasswordRequest,
):
    # (2026-06-18) IP 限流, 防邮箱枚举. reset 3 次/1h. 超阈值返 429
    client_ip = request.client.host if request.client else "unknown"
    allowed, _ = await check_and_increment("reset", client_ip)
    if not allowed:
        raise HTTPException(status_code=429, detail="重置请求过于频繁, 请 1 小时后再试")
    with session_scope() as s:
        rs = s.query(PasswordReset).filter_by(token=req.token).first()
        if rs is None or rs.used_at is not None:
            raise HTTPException(status_code=400, detail="reset token invalid")
        # 兼容 naive / aware: 统一到 HKT 后比, 避免 PG UTC 存储 + HKT now 混比出错
        if rs.expires_at.tzinfo is None:
            expires_aware = rs.expires_at.replace(tzinfo=HKT)
        else:
            expires_aware = rs.expires_at.astimezone(HKT)
        if expires_aware < datetime.now(HKT):
            raise HTTPException(status_code=400, detail="reset token invalid")
        account = s.get(Account, rs.account_id)
        assert account is not None
        account.password_hash = account_service.hash_password(req.new_password)
        rs.used_at = datetime.now(HKT)
        s.flush()

        # 获取用户 token 用于 Redis 缓存失效
        user_obj = s.query(User).filter_by(account_id=account.id).first()
        user_token = user_obj.public_token if user_obj else None

    # CON-008: 改密码后删 Redis token cache, 避免旧缓存被继续使用
    # 推迟副作用: token_cache 顶层 import 触发 Redis client init, auth 路由启动期不能依赖 Redis
    from src.core.token_cache import invalidate_token as _invalidate_token  # noqa: E402

    if user_token:
        await _invalidate_token(user_token)

    # (2026-06-18 fix) 之前用 req.email 报 AttributeError, 改用实际查到的 account.email
    request.state.audit_ctx.set(
        target_id=str(account.id),
        metadata={"email": account.email},
    )
    return {"ok": True}
