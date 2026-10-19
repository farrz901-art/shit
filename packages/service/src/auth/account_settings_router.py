"""/api/account/{profile,avatar,email,password,deletion} 端点 (8 个) + 头像代理路由"""

from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends, File, HTTPException, Request, Response, UploadFile

from ..core.audit import audited
from ..middleware.auth import CurrentUser
from ..permissions.guards import require_account, require_active_account  # 复用 RBAC v2 守卫
from ..storage import ObjectNotFound, get_object_store
from ..storage.session import session_scope
from . import account_settings_service as svc
from .account_models import Account
from .account_settings_schemas import (
    AccountOutExtended,
    DeletionCancel,
    DeletionRequest,
    EmailChangeRequest,
    EmailVerifyRequest,
    PasswordChangeRequest,
    ProfileUpdate,
)
from .account_settings_service import DELETION_GRACE_DAYS

router = APIRouter(prefix="/api/account", tags=["account"])


def _to_out(account: Account) -> AccountOutExtended:
    """Account ORM → AccountOutExtended (含派生字段)."""
    deletion_expires_at = None
    if account.is_pending_deletion and account.deletion_requested_at is not None:
        deletion_expires_at = account.deletion_requested_at + timedelta(days=DELETION_GRACE_DAYS)
    return AccountOutExtended(
        id=account.id,
        email=account.email,
        display_name=account.display_name,
        role=account.role,
        is_admin=account.role in ("admin", "super_admin"),
        avatar_url=account.avatar_url,
        is_pending_deletion=account.is_pending_deletion,
        deletion_expires_at=deletion_expires_at,
    )


@router.patch(
    "/profile",
    summary="更新昵称",
    description=(
        "## 用途\n\n"
        "改当前账号的 display_name (昵称). 1-50 字符, 自动 trim.\n\n"
        "## 鉴权\n\n"
        "`require_active_account` 守卫 (T2.5), 仅登录 + 未注销账号可调.\n\n"
        "## 行为\n\n"
        "Pydantic Field min_length=1 max_length=50 校验. trim 后空字符串 → 422. "
        "成功后返 {account: AccountOutExtended} (含新 display_name)."
    ),
    responses={
        200: {"description": "成功, 返 {account: AccountOutExtended}"},
        401: {"description": "未登录 / token 无效"},
        403: {"description": "非登录账号 (anon)"},
        422: {"description": "Pydantic 校验失败 (display_name 空 / 超过 50 字符)"},
    },
)
def patch_profile(
    req: ProfileUpdate,
    user: CurrentUser = Depends(require_active_account),
):
    with session_scope() as s:
        account = s.get(Account, user.account_id)
        if account is None:
            raise HTTPException(status_code=404, detail="account not found")
        svc.update_profile(s, account, display_name=req.display_name)
        s.flush()
        return {"account": _to_out(account)}


@router.post(
    "/avatar",
    summary="上传头像",
    description=(
        "## 用途\n\n"
        "multipart 上传头像文件, 服务端 PIL 校验 + resize 256x256 + WebP 转码 + 存 ObjectStore.\n\n"
        "## 鉴权\n\n"
        "`require_active_account` 守卫 (T2.5), 仅登录 + 未注销账号可调.\n\n"
        "## 行为\n\n"
        "接受 image/png, image/jpeg, image/webp. 上限 2MB. "
        "PIL 校验后转 256x256 WebP (quality=85), 存 s3://<bucket>/avatars/<account_id>.<hash>.webp (或 local:// 回退). "
        "avatar_url 写入 Account 表, 返 {avatar_url: str}."
    ),
    responses={
        200: {"description": "成功, 返 {avatar_url}"},
        401: {"description": "未登录 / token 无效"},
        403: {"description": "非登录账号"},
        422: {"description": "mime 不支持 / 文件过大 / 损坏的图像"},
    },
)
async def post_avatar(
    file: UploadFile = File(...),
    user: CurrentUser = Depends(require_active_account),
):
    if file.content_type not in {"image/png", "image/jpeg", "image/webp"}:
        raise HTTPException(status_code=422, detail=f"unsupported mime: {file.content_type}")
    data = await file.read()
    with session_scope() as s:
        account = s.get(Account, user.account_id)
        if account is None:
            raise HTTPException(status_code=404, detail="account not found")
        try:
            uri = svc.store_avatar(s, account, data)
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e)) from e
        return {"avatar_url": uri}


@router.delete(
    "/avatar",
    summary="删除头像",
    description=(
        "## 用途\n\n"
        "清空当前账号的 avatar_url 字段, 头像恢复为默认.\n\n"
        "## 鉴权\n\n"
        "`require_active_account` 守卫 (T2.5), 仅登录 + 未注销账号可调.\n\n"
        "## 行为\n\n"
        "只清空 DB 字段, 不删 ObjectStore 文件 (保留历史 + 避免 race). "
        "返 {ok: true}."
    ),
    responses={
        200: {"description": "成功, 返 {ok: true}"},
        401: {"description": "未登录 / token 无效"},
        403: {"description": "非登录账号"},
    },
)
@audited("avatar.delete", target_type="avatar")
async def delete_avatar(request: Request, user: CurrentUser = Depends(require_active_account)):
    request.state.audit_ctx.set(
        target_id=str(user.id),
    )
    with session_scope() as s:
        account = s.get(Account, user.account_id)
        if account is None:
            raise HTTPException(status_code=404, detail="account not found")
        svc.delete_avatar(s, account)
        return {"ok": True}


@router.get(
    "/avatar/{account_id}",
    summary="获取头像 (代理)",
    description=(
        "## 用途\n\n"
        "ObjectStore 代理路由: 查 Account.avatar_url → ObjectStore.get_bytes → 返 image/webp 字节流.\n\n"
        "## 鉴权\n\n"
        "无需鉴权 (头像公开). 仅 cache 1h.\n\n"
        "## 行为\n\n"
        "Cache-Control: public, max-age=3600. 头像不存在 → 404."
    ),
    responses={
        200: {"description": "成功, 返 image/webp 字节流"},
        404: {"description": "account 不存在 / avatar_url 为空"},
    },
)
def get_avatar(account_id: int):
    with session_scope() as s:
        account = s.get(Account, account_id)
        if account is None or account.avatar_url is None:
            raise HTTPException(status_code=404, detail="avatar not found")
        store = get_object_store()
        try:
            data = store.get_bytes(account.avatar_url)
        except ObjectNotFound as e:
            raise HTTPException(status_code=404, detail=f"avatar file missing: {e}") from e
    return Response(
        content=data,
        media_type="image/webp",
        headers={"Cache-Control": "public, max-age=3600"},
    )


@router.patch(
    "/email",
    summary="申请改邮箱",
    description=(
        "## 用途\n\n"
        "改邮箱走双重验证: 当前密码二次确认 + 验证新邮箱 token.\n\n"
        "## 鉴权\n\n"
        "`require_active_account` 守卫 (T2.5), 仅登录 + 未注销账号可调.\n\n"
        "## 行为\n\n"
        "校验 current_password 正确, new_email 格式合法且未被其他 account 占用. "
        "创 EmailChange 行 (token 64 字节 hex, 默认 7 天过期), 返 {verification_url, new_email, expires_at}. "
        "前端引导用户去邮箱点链接 (dev: 链接 = /verify-email?token=xxx; prod: 应接邮件服务, 本期不接). "
        "EmailChange 不立即切换 email — 验证后才切. 旧邮箱收不到改邮箱通知 (本期不接邮件服务, 列下个 spec)."
    ),
    responses={
        200: {"description": "成功, 返 {new_email, expires_at, verification_url}"},
        400: {"description": "当前密码错 / 新邮箱已被占用"},
        401: {"description": "未登录 / token 无效"},
        403: {"description": "非登录账号"},
        422: {"description": "Pydantic 校验失败 (新邮箱超长 / current_password 空)"},
    },
)
@audited("email.change", target_type="user")
async def patch_email(
    request: Request,
    req: EmailChangeRequest,
    user: CurrentUser = Depends(require_active_account),
):
    request.state.audit_ctx.set(
        target_id=str(user.id),
        before={"old_email": user.email},
        after={"new_email": req.new_email},
    )
    with session_scope() as s:
        account = s.get(Account, user.account_id)
        if account is None:
            raise HTTPException(status_code=404, detail="account not found")
        try:
            return svc.request_email_change(s, account, req.new_email, req.current_password)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e


@router.post(
    "/email/verify",
    summary="验证邮箱改 token",
    description=(
        "## 用途\n\n"
        "用 request_email_change 拿到的 token 确认邮箱改. 成功后 Account.email 切换到新邮箱, EmailChange 标 used_at.\n\n"
        "## 鉴权\n\n"
        "`require_active_account` 守卫 (T2.5), 仅登录 + 未注销账号可调 (防止 token 泄露后被他人用).\n\n"
        "## 行为\n\n"
        "校验 token 存在 + 未 used + 未过期. 二次校验 new_email 仍可用 (防 race). "
        "成功后切换 email + 标 used_at, 返 {email: str}."
    ),
    responses={
        200: {"description": "成功, 返 {email: 新邮箱}"},
        400: {"description": "token 不存在 / 已用 / 已过期 / 新邮箱已被占"},
        401: {"description": "未登录 / token 无效"},
        403: {"description": "非登录账号"},
    },
)
async def post_email_verify(
    req: EmailVerifyRequest,
    user: CurrentUser = Depends(require_active_account),
):
    with session_scope() as s:
        try:
            result = svc.verify_email_change(s, req.token)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e

    # CON-008: 改邮箱后删 Redis token cache, 避免脏读旧 email
    # 推迟副作用: token_cache 顶层 import 触发 Redis client 初始化, auth 路由启动期不能依赖 Redis
    from src.core.token_cache import invalidate_token  # noqa: E402

    await invalidate_token(user.public_token)
    return result


@router.patch(
    "/password",
    summary="改密码",
    description=(
        "## 用途\n\n"
        "改当前账号的密码. 需提供当前密码二次确认 (防止 session 失窃后改密码).\n\n"
        "## 鉴权\n\n"
        "`require_active_account` 守卫 (T2.5), 仅登录 + 未注销账号可调.\n\n"
        "## 行为\n\n"
        "校验 current_password 正确. new_password ≥ 8 字符 (Pydantic Field min_length=8 校验). "
        "new == confirm 字面一致. 成功 → bcrypt hash 新密码 → 写 Account.password_hash. "
        "**不踢出当前 session** (用户在自己设备操作, 改完继续可用). "
        "**其他设备的 session 不在本期范围** (1 token per user 当前设计, 暂不需要多 session 管理)."
    ),
    responses={
        200: {"description": "成功, 返 {ok: true}"},
        400: {"description": "当前密码错 / 新密码 != 确认密码 / 新密码 < 8 字符"},
        401: {"description": "未登录 / token 无效"},
        403: {"description": "非登录账号"},
        422: {"description": "Pydantic 校验失败 (新密码 < 8 字符)"},
    },
)
@audited("password.change", target_type="user")
async def patch_password(
    request: Request,
    req: PasswordChangeRequest,
    user: CurrentUser = Depends(require_active_account),
):
    request.state.audit_ctx.set(
        target_id=str(user.id),
    )
    with session_scope() as s:
        account = s.get(Account, user.account_id)
        if account is None:
            raise HTTPException(status_code=404, detail="account not found")
        try:
            svc.change_password(s, account, req.current_password, req.new_password, req.confirm)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e

    # CON-008: 改密码后删 Redis token cache, 避免旧缓存被继续使用
    # 推迟副作用: 同上, token_cache 顶层 import 触发 Redis init
    from src.core.token_cache import invalidate_token  # noqa: E402

    await invalidate_token(user.public_token)
    return {"ok": True}


@router.get(
    "/deletion",
    summary="查注销状态",
    description=(
        "## 用途\n\n"
        "查当前账号的注销状态 (pending / not pending) + 倒计时.\n\n"
        "## 鉴权\n\n"
        "`require_account` 守卫, 仅登录账号可调.\n\n"
        "## 行为\n\n"
        "未申请: 返 {pending: false}. "
        "已申请: 返 {pending: true, deletion_requested_at, expires_at}. "
        "**不返 restore_token** (防泄漏 — token 只在 POST /deletion 响应里返一次)."
    ),
    responses={
        200: {"description": "成功, 返 {pending: bool, deletion_requested_at?, expires_at?}"},
        401: {"description": "未登录 / token 无效"},
        403: {"description": "非登录账号"},
    },
)
def get_deletion(user: CurrentUser = Depends(require_account)):
    with session_scope() as s:
        account = s.get(Account, user.account_id)
        if account is None:
            raise HTTPException(status_code=404, detail="account not found")
        return svc.get_deletion_status(account)


@router.post(
    "/deletion",
    summary="申请注销",
    description=(
        "## 用途\n\n"
        "申请注销账号, 进入 7 天宽限期. 期间 is_active=False, 横幅提示, 可撤销.\n\n"
        "## 鉴权\n\n"
        "`require_active_account` 守卫 (T2.5), 仅登录 + 未注销账号可调 (申请注销本身需 active 状态).\n\n"
        "## 行为\n\n"
        "校验 current_password 正确 + confirm_text 字面等于 '我要注销' (防误操作). "
        "立即 is_active=False + deletion_requested_at=now. 创 DeletionRestore token (7 天有效), "
        "返 {deletion_requested_at, expires_at, restore_url}. "
        "前端引导用户访问 /account/restore 或邮件链接 (本期不接邮件服务, 列下个 spec) 撤销. "
        "**7 天后** APScheduler 跑硬删 + 数据 anonymize (见 T5.1). "
        "重复申请 (已 pending) → 400."
    ),
    responses={
        200: {"description": "成功, 返 {deletion_requested_at, expires_at, restore_url}"},
        400: {"description": "当前密码错 / confirm_text 不匹配 / 已 pending"},
        401: {"description": "未登录 / token 无效"},
        403: {"description": "非登录账号"},
        422: {"description": "Pydantic 校验失败"},
    },
)
@audited("account.delete", target_type="user")
async def post_deletion(
    request: Request,
    req: DeletionRequest,
    user: CurrentUser = Depends(require_active_account),
):
    request.state.audit_ctx.set(
        target_id=str(user.id),
    )
    with session_scope() as s:
        account = s.get(Account, user.account_id)
        if account is None:
            raise HTTPException(status_code=404, detail="account not found")
        try:
            result = svc.request_deletion(s, account, req.current_password, req.confirm_text)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e

    # CONC-003 (2026-06-26): 注销后立即失效 Redis token cache, 防止已注销账号
    # 在 cache TTL (6h) 内继续访问. 对齐 verify_email_change / change_password 模式.
    # 推迟副作用: 同上, token_cache 顶层 import 触发 Redis init
    from src.core.token_cache import invalidate_token  # noqa: E402

    await invalidate_token(user.public_token)
    return result


@router.delete(
    "/deletion",
    summary="撤销注销",
    description=(
        "## 用途\n\n"
        "撤销注销申请, 重置 is_active=True, 标 DeletionRestore.used_at. 账号恢复正常.\n\n"
        "## 鉴权\n\n"
        "`require_account` 守卫, 仅登录账号可调.\n\n"
        "## 行为\n\n"
        "校验 current_password 正确 + 必须在 pending 状态. "
        "重置 is_active=True + deletion_requested_at=None. 标所有未用 DeletionRestore token.used_at = now. "
        "返 {ok: true}."
    ),
    responses={
        200: {"description": "成功, 返 {ok: true}"},
        400: {"description": "当前密码错 / 账号未申请注销"},
        401: {"description": "未登录 / token 无效"},
        403: {"description": "非登录账号"},
    },
)
@audited("deletion.cancel", target_type="user")
async def delete_deletion(
    request: Request,
    req: DeletionCancel,
    user: CurrentUser = Depends(require_account),
):
    request.state.audit_ctx.set(
        target_id=str(user.id),
    )
    with session_scope() as s:
        account = s.get(Account, user.account_id)
        if account is None:
            raise HTTPException(status_code=404, detail="account not found")
        try:
            svc.cancel_deletion(s, account, req.current_password)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
    return {"ok": True}
