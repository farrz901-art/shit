"""/api/invites/<token> 路由: GET 查 + POST 兑换"""

from __future__ import annotations

import secrets
from datetime import datetime

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import select

from ..core.audit import audited
from ..storage.session import session_scope
from ..utils.timezone import HKT
from . import account_service
from .account_models import Account, Invite
from .auth_account_router import COOKIE_MAX_AGE, COOKIE_NAME, COOKIE_SECURE, AccountOut
from .models import User

router = APIRouter(prefix="/api/invites", tags=["invite"])


class InviteInfo(BaseModel):
    expires_at: datetime = Field(..., description="过期时间")
    email: str = Field(..., description="被邀请人邮箱 (展示用)")


class RedeemRequest(BaseModel):
    display_name: str = Field(..., min_length=1, max_length=50, description="账号显示名")
    password: str = Field(..., min_length=8, description="密码, ≥ 8 字符")


class RedeemResponse(BaseModel):
    token: str = Field(..., description="兑换后的 32 字节 hex token")
    email: str = Field(..., description="被邀请人邮箱")
    account: AccountOut = Field(..., description="账号信息对象, 见 AccountOut schema")


def _validate_invite(token: str) -> Invite:
    """未过期未redeem 的 invite 才返; 否则 400."""
    with session_scope() as s:
        inv = s.query(Invite).filter_by(token=token).first()
    if not inv:
        raise HTTPException(status_code=400, detail="invite token invalid")
    if inv.redeemed_at is not None:
        raise HTTPException(status_code=400, detail="invite token invalid")
    # SQLite 返 naive datetime, 去掉 tz 后比较
    expires_naive = inv.expires_at.replace(tzinfo=None) if inv.expires_at.tzinfo else inv.expires_at
    now_naive = datetime.now(HKT).replace(tzinfo=None)
    if expires_naive < now_naive:
        raise HTTPException(status_code=400, detail="invite token invalid")
    return inv


def _lock_invite_in_session(s, token: str) -> Invite:
    """在已开的事务 s 内锁 invite 行 (SELECT ... FOR UPDATE), 验状态后返.

    CON-001: 双重 session 并发 redeem 同一 invite 行的 TOCTOU 修复关键.
    PG 行锁在事务结束 (commit / rollback) 时释放, 第二个并发 redeem 阻塞到
    第一个事务结束 → 此时 redeemed_at 已被标 → 第二个返 400, 不会双创账号.
    返回的 invite 仍 detached, 但已绑定到 s 可后续 add 修改.
    """
    # (CON-001) SELECT ... FOR UPDATE 锁 invite 行; PG row-level lock
    inv = (
        s.execute(
            select(Invite)
            .where(Invite.token == token, Invite.redeemed_at.is_(None))
            # PG 行锁, 防双重 session 同一 invite 行并发兑换
            .with_for_update()
        )
        .scalars()
        .first()
    )
    if inv is None:
        # 区分: 不存在 / 已用 / 过期 — 统一 400 防探测 (跟 get_invite 一致)
        raise HTTPException(status_code=400, detail="invite token invalid")
    # SQLite 返 naive datetime, 去掉 tz 后比较
    expires_naive = inv.expires_at.replace(tzinfo=None) if inv.expires_at.tzinfo else inv.expires_at
    now_naive = datetime.now(HKT).replace(tzinfo=None)
    if expires_naive < now_naive:
        raise HTTPException(status_code=400, detail="invite token invalid")
    return inv


@router.get(
    "/{token}",
    response_model=InviteInfo,
    summary="查 invite 详情",
    description=(
        "## 用途\n\n"
        "公开端点: 查 invite 详情 (expires_at), 让被邀请人知道邀请何时过期. "
        "前端在 `/zh/invite/{token}` 页面调此端点展示邀请信息.\n\n"
        "## 鉴权\n\n"
        "无 (anon OK, 未登录也能查).\n\n"
        "## 行为\n\n"
        "**统一 400 防探测**: token 不存在 / 已 redeem (`redeemed_at IS NOT NULL`) / 已过期 → "
        "统一返 400 `invite token invalid` (msg 一致, 防止外部探测哪些 token 有效). "
        "兼容 naive/aware datetime: SQLite 返 naive, 去掉 tz 后再跟 now 比. "
        "成功 → 返 `{expires_at, email}` (email 仅展示用, 不用于鉴权)."
    ),
    responses={
        200: {"description": "成功, 返 `{expires_at}`"},
        400: {"description": "token 不存在 / 已 redeem / 已过期 (msg 统一为 `invite token invalid`)"},
    },
)
def get_invite(token: str):
    inv = _validate_invite(token)
    return InviteInfo(expires_at=inv.expires_at, email=inv.email)


@router.post(
    "/{token}/redeem",
    response_model=RedeemResponse,
    summary="兑换 invite 创账号",
    description=(
        "## 用途\n\n"
        "被邀请人提交 `display_name` + `password`, 兑换 invite: 创 `Account` + 绑 `User` + 标 `Invite.redeemed_at`. "
        "成功返 token + Set-Cookie (用户立即登录态).\n\n"
        "## 鉴权\n\n"
        "无 (anon OK, invite token 本身就是凭证).\n\n"
        "## 行为\n\n"
        "**守卫 (前置, 在事务内锁 invite 行)**: (CON-001 修) "
        "用 `SELECT ... FOR UPDATE` 锁 invite 行, 双重 session 并发 redeem 同一 token 时第二个阻塞等第一个 commit → "
        "返回时 redeemed_at 已设 → 统一 400 `invite token invalid` (msg 统一防探测). "
        "覆盖 token 不存在 / 已 redeem / 已过期.\n\n"
        "**守卫 (后置)**:\n"
        "- `email` 已注册 (race condition: invite 创完 → 用户用别的方式注册了) → 409 `email already registered`\n"
        "- `display_name` < 1 字符或 > 50 字符 → 422 (Pydantic `min_length=1, max_length=50`)\n"
        "- `password` < 8 字符 → 422 (Pydantic `min_length=8`)\n\n"
        "**成功**: 创 `Account` (`role` 来自 invite 默认 `user`; **注**: 当前实现不读 `Invite.role` 字段, 全是 `user`, "
        "如需 role-aware redeem, 看后续 spec) + `User(public_token=32B hex)` + 标 `Invite.redeemed_at = now(HKT)` + `Invite.account_id`. "
        "Set-Cookie `rag_user_token` (HttpOnly, SameSite=Lax, 7 天, prod 加 secure). "
        "body 返 `{token, email, account: AccountOut}` (8 字段)."
    ),
    responses={
        200: {"description": "成功, body 返 `{token, email, account}` + Set-Cookie 登录态"},
        400: {"description": "token 不存在 / 已用 / 已过期 (msg 统一为 `invite token invalid`)"},
        409: {"description": "email 已注册"},
        422: {"description": "display_name 不在 1-50 字符 / password < 8 字符"},
    },
)
@audited("user.invite", target_type="user")
async def redeem_invite(
    request: Request,
    token: str,
    req: RedeemRequest,
    response: Response,
):
    # CON-001: 锁 invite 行 + 创 account + 标 redeemed_at 必须在同一事务里.
    # 旧实现分两步: 先 _validate_invite (独立 session), 再起新 session 创账号 — TOCTOU 漏洞.
    # 现在用 with_for_update 行锁, 双重并发 redeem 同一 token 必一胜一败.
    with session_scope() as s:
        # 1. 锁 invite 行 + 验状态 (不存 / 已用 / 过期 都 400, 防探测)
        inv = _lock_invite_in_session(s, token)
        # invite 表的 email (RedeemRequest 不含 email, 来自 token 邀请). 走 **metadata kwargs 展开
        request.state.audit_ctx.set(
            target_id=token,
            email=inv.email,
        )
        if s.query(Account).filter_by(email=inv.email).first() is not None:
            raise HTTPException(status_code=409, detail="email already registered")

        account = Account(
            email=inv.email,
            password_hash=account_service.hash_password(req.password),
            display_name=req.display_name,
            created_at=datetime.now(HKT),
        )
        s.add(account)
        s.flush()
        s.refresh(account)

        user = User(
            public_token=secrets.token_hex(32),
            display_name=req.display_name,
            account_id=account.id,
        )
        s.add(user)
        s.flush()

        # 标 invite 已用 (锁内 update, commit 时跟 account / user 一起原子提交)
        inv.redeemed_at = datetime.now(HKT)
        inv.account_id = account.id
        s.flush()
        token_out = user.public_token
        account_id_out = account.id
        account_email_out = account.email
        account_display_name_out = account.display_name
        account_role_out = account.role  # (2026-06-17) 替原 is_admin

    response.set_cookie(
        key=COOKIE_NAME,
        value=token_out,
        max_age=COOKIE_MAX_AGE,
        httponly=True,
        samesite="lax",
        path="/",
        secure=COOKIE_SECURE,
    )
    return RedeemResponse(
        token=token_out,
        email=account_email_out,
        account=AccountOut(
            id=account_id_out,
            email=account_email_out,
            display_name=account_display_name_out,
            role=account_role_out,
            is_admin=account_role_out in ("admin", "super_admin"),
        ),
    )
