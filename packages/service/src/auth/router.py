"""匿名鉴权路由: /api/auth/anon

客户端首次访问生成随机 token, 落库, 后续请求带 x-user-token 即可.
"""

from __future__ import annotations

import os
import secrets

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

from ..core.audit import audited
from ..storage.session import session_scope
from .models import User

router = APIRouter(prefix="/api/auth", tags=["auth"])

# cookie 名: 前端 P0 任务 8 + BFF 任务 9 都靠这个名读
ANON_COOKIE_NAME = "rag_user_token"
# 灰度期 cookie 寿命: 7 天
ANON_COOKIE_MAX_AGE = 60 * 60 * 24 * 7


class AnonTokenResponse(BaseModel):
    token: str = Field(..., description="32 字节 hex (64 字符), 客户端存 cookie 后续请求带")


class MigrateRequest(BaseModel):
    """migrate 端点请求体: 老用户 localStorage 里的旧 token."""

    token: str = Field(..., min_length=1, description="老 localStorage 里的 rag_user_token, 用于换 Set-Cookie")


@router.post(
    "/migrate",
    summary="老 token → Set-Cookie",
    description=(
        "## 用途\n\n"
        "灰度期: 老用户 localStorage 里有 `rag_user_token` 但没 cookie. 首次访问前端 POST "
        "这个端点, 后端验证旧 token 仍落库有效后 Set-Cookie HttpOnly, 后续前端改读 cookie.\n\n"
        "## 鉴权\n\n"
        "无 (公开端点).\n\n"
        "## 行为\n\n"
        "验证逻辑跟 `middleware/auth.py` 保持一致: 在 `users` 表里查得到 `public_token` 即可. "
        "找不到 → 400 `invalid token`; 空 token → 400 `token required`. "
        "成功 → Set-Cookie `rag_user_token` (HttpOnly, SameSite=Lax, 7 天, prod 加 secure)."
    ),
    responses={
        200: {"description": "Set-Cookie 写入成功, 返 `{ok: true}`"},
        400: {"description": "token 为空 / 老 token 在 users 表查不到"},
    },
)
@audited("api_key.revoke", target_type="api_key")
async def auth_migrate(
    request: Request,
    payload: MigrateRequest,
    response: Response,
):
    request.state.audit_ctx.set(
        target_id=payload.token[:16],
        metadata={"token_prefix": payload.token[:16]},
    )
    legacy_token = payload.token
    if not legacy_token:
        raise HTTPException(status_code=400, detail="token required")

    with session_scope() as s:
        user = s.query(User).filter_by(public_token=legacy_token).first()
    if not user:
        raise HTTPException(status_code=400, detail="invalid token")

    # Set-Cookie: 跟 anon 端点保持一致, 复用 Task 1 提的常量
    response.set_cookie(
        key=ANON_COOKIE_NAME,
        value=legacy_token,
        max_age=ANON_COOKIE_MAX_AGE,
        httponly=True,
        samesite="lax",
        path="/",
        # 直接读 env, 不走 settings 单例 (test 用 monkeypatch.setenv 改 ENV 需 lazy 读)
        secure=os.getenv("ENV", "development") == "production",
    )

    return {"ok": True}


@router.post(
    "/anon",
    response_model=AnonTokenResponse,
    summary="生成匿名 token",
    description=(
        "## 用途\n\n"
        "客户端首次访问生成 32 字节 hex token, 落 `users` 表 (`display_name='anon'`, `account_id=NULL`). "
        "后续请求带 `x-user-token` header 或 `rag_user_token` cookie 即可被 `middleware/auth.py` 识别.\n\n"
        "## 鉴权\n\n"
        "无 (公开端点).\n\n"
        "## 行为\n\n"
        "灰度期: 同时 Set-Cookie `rag_user_token` (HttpOnly, SameSite=Lax, 7 天) "
        "和 body 返 `token` 字段 (兼容老前端, 后续 P4 删除 body). "
        "prod (`ENV=production`) 时 cookie 加 `secure`; dev 用 `http://localhost` 不加. "
        "防御性: 生成后查 `users.public_token` 重复 → 500 重试 (理论不会发生, hex 32 字节碰撞概率极低)."
    ),
    responses={
        200: {"description": "成功, body 返 `{token: <hex>}` + Set-Cookie `rag_user_token`"},
        500: {"description": "token 碰撞 (理论不会发生, 触发后端重试)"},
    },
)
@audited("api_key.create", target_type="api_key")
async def create_anon_token(
    request: Request,
    response: Response,
):
    request.state.audit_ctx.set(
        target_id="pending",
    )
    token = secrets.token_hex(32)

    with session_scope() as s:
        # 检查是否已存在 (理论上不会, 但防御性检查)
        existing = s.query(User).filter_by(public_token=token).first()
        if existing:
            raise HTTPException(status_code=500, detail="token 碰撞, 重试")

        user = User(public_token=token, display_name="anon")
        s.add(user)
        s.flush()

    # Set-Cookie: 灰度期让浏览器自动带 token, HttpOnly 防 XSS
    response.set_cookie(
        key=ANON_COOKIE_NAME,
        value=token,
        max_age=ANON_COOKIE_MAX_AGE,
        httponly=True,
        samesite="lax",
        path="/",
        # 直接读 env, 不走 settings 单例 (test 用 monkeypatch.setenv 改 ENV 需 lazy 读)
        secure=os.getenv("ENV", "development") == "production",
    )

    return AnonTokenResponse(token=token)
