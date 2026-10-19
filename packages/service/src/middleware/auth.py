"""鉴权: 解析客户端 token / 账号 token → CurrentUser

2 路径:
1. x-user-token 查 users → account_id 关联 → 真账号 (is_account=True + email)
   account_id NULL → anon (is_account=False, is_admin=False)
2. RAG_DEV_AUTH=1 + 无 token → dev user (is_admin=True)

账号 is_active=False → 401.

(2026-06-14) 砍掉 bootstrap admin (x-admin-token 字符串) 路径:
- 业务端点 (health / ingest) 改走 is_admin 字段, 不再需要单独字符串 admin token
- 创 admin 入口 (seed-admin 端点) 仍保留 x-admin-token, 因为是 bootstrap 入口, 没账号时唯一鉴权方式

(2026-06-14) 模块顶部**不** import Account / auth_account_models 等 src.auth.* 子模块:
auth_account_router 顶层 import 了本模块, 而 src/auth/__init__.py eager-imports auth_account_router,
形成循环. Account 改成在函数体内 lazy import.

(2026-06-18) T3 改造:
- resolve_user 改 async, FastAPI Depends 自动 await
- 接入 Redis TokenCache (6h sliding, sha256 hash key, fail-open)
  - 真账号 cache 走快路径 (limited fields, 避免 hot path 走 PG)
  - anon 不进 cache (高频瞬时 token, cache 价值低)
  - PG 写 cache 用 fire-and-forget (asyncio.create_task, 不阻塞响应)
"""

from __future__ import annotations

import asyncio
import os
from datetime import datetime

from fastapi import HTTPException
from pydantic import BaseModel
from starlette.requests import Request

# 故意不顶层 import src.auth.*: src/auth/__init__.py:3 eager-imports auth_account_router,
# 而 auth_account_router:12 顶层 import 本模块 → 循环. 全部 lazy import 在函数体内做.
from ..storage.session import session_scope

_dev_userEnsured = False


def _ensure_dev_user() -> None:
    """开发模式: 确保 users 表有 id=1 的默认用户 (供 FK 约束)"""
    # 防循环: 顶层 from ..auth.models 会触发 auth 模块完整初始化, 启动期引入副作用
    from ..auth.models import User  # noqa: E402

    global _dev_userEnsured
    if _dev_userEnsured:
        return
    with session_scope() as s:
        if not s.query(User).filter_by(id=1).first():
            s.add(User(id=1, public_token="dev-default", display_name="dev"))
            s.flush()
    _dev_userEnsured = True


class CurrentUser(BaseModel):
    """当前请求的鉴权上下文

    - 真账号: id=users.id, is_account=True, email/role/display_name 填
    - anon: id=users.id, is_account=False, email/display_name=None
    - dev user: id=1, role="super_admin" (RAG_DEV_AUTH=true 模式)

    role 字段值参考 src.permissions.cache: user / admin / super_admin / 自定义.
    is_admin 是从 role 派生的 bool 兼容字段, 供旧代码过渡用 (Phase 2 删).
    """

    id: int
    public_token: str
    role: str = "user"  # 替原 is_admin, 从 account.role 派生 (validated against roles 表)
    is_account: bool = False
    account_id: int | None = None
    email: str | None = None
    display_name: str | None = None
    is_active: bool = True
    avatar_url: str | None = None  # (2026-06-17 T2.5) Account.avatar_url, anon 为 None
    is_pending_deletion: bool = False  # (2026-06-17 T2.5) 派生, 跟 Account.is_pending_deletion
    deletion_requested_at: datetime | None = None  # (2026-06-17 T2.5) 真账号字段, anon 为 None

    @property
    def is_admin(self) -> bool:
        """派生: role in ('admin', 'super_admin') 即视为 admin. 供旧代码 (health, eval) 过渡用."""
        return self.role in ("admin", "super_admin")


async def resolve_user(request: Request) -> CurrentUser:
    """FastAPI Depends 用的鉴权函数 (2026-06-18 改造: 加 Redis token 缓存)

    优先级:
    1. x-user-token / rag_user_token cookie → TokenCache 查 (6h sliding)
       - hit + 真账号 → 直接构造 CurrentUser 返 (快路径, 0 PG)
       - miss → 走原 PG 路径 + 异步写 cache
    2. RAG_DEV_AUTH=1 + 无 token → dev user
    3. 都没 → 401
    """
    # 1. user token (header 优先, 降级 cookie)
    user_token = request.headers.get("x-user-token", "")
    if not user_token:
        user_token = request.cookies.get("rag_user_token", "")

    if not user_token:
        if os.getenv("RAG_DEV_AUTH", "").lower() in ("1", "true", "yes"):
            _ensure_dev_user()
            return CurrentUser(
                id=1,
                public_token="dev-default",
                role="super_admin",
                is_account=False,
            )
        raise HTTPException(401, "missing x-user-token")

    # 2. (2026-06-18) TokenCache 查 — 真账号快路径
    # 防循环: token_cache 顶层 import 触发 Redis client init, 中间件模块装载期不引入
    from ..core.token_cache import cache_user_by_token, get_user_by_token  # noqa: E402

    cached = await get_user_by_token(user_token)
    if cached is not None and cached.get("is_account"):
        # cache hit 真账号, 走快路径 (limited fields, 够权限/audit 用)
        if not cached.get("is_active", True):
            raise HTTPException(401, "account disabled")
        return CurrentUser(
            id=cached["user_id"],
            public_token=user_token,
            is_account=True,
            role=cached.get("role", "user"),
            is_active=cached["is_active"],
        )

    # 3. miss / anon → 走原 PG 路径
    # 防循环: 同 _ensure_dev_user, 顶层 from ..auth.models 触发 auth chain
    from ..auth.models import User  # noqa: E402

    with session_scope() as s:
        user = s.query(User).filter_by(public_token=user_token).first()
    if not user:
        raise HTTPException(401, "invalid user token")

    # 1a. anon
    if user.account_id is None:
        # anon 不进 cache (高频瞬时 token, cache 价值低)
        return CurrentUser(
            id=user.id,
            public_token=user_token,
            is_account=False,
            role="user",
            is_active=True,
        )

    # 1b. 真账号
    # 防循环: Account 触发 src.auth.__init__ → auth_account_router 顶层 import 本模块 → 循环
    from ..auth.account_models import Account  # noqa: E402

    with session_scope() as s:
        account = s.get(Account, user.account_id)
    if account is None:
        # FK 防御: account 没了 (理论上不删) → 401
        raise HTTPException(401, "account not found")
    if not account.is_active:
        raise HTTPException(401, "account disabled")

    # 异步写 cache (fire-and-forget, 失败不影响响应, Redis 挂时 safe_set 返 False 不抛)
    asyncio.create_task(
        cache_user_by_token(
            user_token,
            {
                "id": user.id,
                "is_admin": account.role in ("admin", "super_admin"),
                "is_active": account.is_active,
                "email": account.email,
                "is_account": True,
                "role": account.role,
            },
        )
    )

    return CurrentUser(
        id=user.id,
        public_token=user_token,
        is_account=True,
        role=account.role,
        account_id=account.id,
        email=account.email,
        display_name=account.display_name,
        is_active=account.is_active,
        avatar_url=account.avatar_url,  # (2026-06-17 T2.5) 从 Account 同步
        is_pending_deletion=account.is_pending_deletion,  # (2026-06-17 T2.5) 派生属性
        deletion_requested_at=account.deletion_requested_at,  # (2026-06-17 T2.5) 真账号字段
    )
