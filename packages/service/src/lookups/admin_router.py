"""/api/admin/dicts/* — 字典写 API (2026-06-19 lookup spec §4.2/§4.3, Task 6)

7 个端点, 全部 require_super_admin:
- POST   /api/admin/dicts                             新建字典
- PATCH  /api/admin/dicts/{dict_code}                 改字典 metadata
- POST   /api/admin/dicts/{dict_code}/items           新增 item
- PATCH  /api/admin/dicts/{dict_code}/items/{key}     改 item
- DELETE /api/admin/dicts/{dict_code}/items/{key}     软删 (confirm token 必传)
- POST   /api/admin/dicts/confirm-token               签发删除二次确认 token
- GET    /api/admin/dicts/{dict_code}/audit           字典变更历史 (audit_logs)

每个写端点都走 SafetyGuard.check_all() (6 层防御), 失败 raise LookupSafetyError,
router 层 try/except 翻译成 HTTPException(http_status, detail).

鉴权: 用 require_super_admin (src.permissions.guards), FastAPI Depends 自动注入.
业务异常:
- LookupSafetyError → 翻译成对应 HTTPException (4xx/429)
- LookupNotFoundError → 404

约束:
- 全部 async def (跟 SafetyGuard / LookupService 异步 API 一致)
- 业务走 LookupService 静态方法 (含字典级 patch_dict), router 不直查 DB
- audit_log 走 src.lookups.audit.log_dict_change (复用 src.db.models.audit_log.AuditLog 表)
- DELETE 端点要求 X-Confirm-Token header (16 字符 hex), safety_guard 校验内容
- 失败 raise HTTPException, 不返 200 + error (跟项目其他 admin 端点一致)
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from typing import Any, Literal, cast

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from loguru import logger
from sqlalchemy import or_, select

from src.core.audit import audited
from src.db.models.audit_log import AuditLog
from src.lookups.audit import log_dict_change
from src.lookups.cache import lookup_cache
from src.lookups.exceptions import LookupNotFoundError, LookupSafetyError
from src.lookups.models import Dictionary
from src.lookups.safety_guard import safety_guard
from src.lookups.schemas import (
    AuditLogEntry,
    AuditLogListResponse,
    ConfirmTokenResponse,
    DictionaryCreateRequest,
    DictionaryPatchRequest,
    DictionarySummaryResponse,
    LookupItemCreateRequest,
    LookupItemPatchRequest,
    LookupItemResponse,
    SoftDeleteItemResponse,
)
from src.lookups.service import LookupService
from src.middleware.auth import CurrentUser
from src.permissions.cache import invalidate_page_keys_cache, rewarm_page_keys_cache
from src.permissions.guards import require_super_admin
from src.storage.session import session_scope

router = APIRouter(prefix="/api/admin/dicts", tags=["admin-lookups"])


# ---- helper: 异常翻译 + actor 提取 ----


def _actor_display(user: CurrentUser) -> str:
    """提取 audit_log 友好显示名 (email 优先, fallback 到 public_token)."""
    return user.email or user.public_token or f"user-{user.id}"


def _client_ip(request: Request) -> str | None:
    """提取客户端 IP (request.client.host)."""
    return request.client.host if request.client else None


async def _guard(
    *,
    action: Literal["create", "patch", "delete"],
    dict_code: str,
    key: str | None,
    user: CurrentUser,
    confirm_token: str | None,
    payload: dict[str, Any],
    force: bool = False,
) -> None:
    """跑 SafetyGuard 6 层防御, 失败 raise HTTPException (跟项目其他 admin 端点一致).

    简化: 不做全局 LookupSafetyError handler (范围内小), router 内 try/except 即可.
    """
    try:
        await safety_guard.check_all(
            action=action,
            dict_code=dict_code,
            key=key,
            user=user,
            confirm_token=confirm_token,
            payload=payload,
            force=force,
        )
    except LookupSafetyError as e:
        raise HTTPException(status_code=e.http_status, detail=e.detail) from e


# ==================== 字典级 (POST/PATCH) ====================


@router.post(
    "",
    response_model=DictionarySummaryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="新建字典",
    description=(
        "## 用途\n\n"
        "新建一个字典定义 (字典本身, 不含 items). items 用 POST `/api/admin/dicts/{code}/items` 后续加.\n\n"
        "## 鉴权\n\n"
        "`require_super_admin` + SafetyGuard 6 层 (含 env readonly 校验).\n\n"
        "## 行为\n\n"
        "- code 格式 `[a-z][a-z0-9_]{1,63}`, UNIQUE 冲突 → 409\n"
        "- 创建后 version=1, is_active=True, is_readonly=False\n"
        "- audit `dictionary.dict.create`, target_id = code"
    ),
    responses={
        201: {"description": "字典创建成功, 返 DictionarySummaryResponse"},
        401: {"description": "未登录"},
        403: {"description": "非 super_admin / DICTIONARY_READONLY=true"},
        409: {"description": "code 已存在"},
        422: {"description": "Pydantic 校验失败 (code 格式错)"},
    },
)
@audited("admin.dict.create", target_type="dictionary")
async def create_dictionary(
    request: Request,
    body: DictionaryCreateRequest,
    user: CurrentUser = Depends(require_super_admin),
):
    """新建字典 (super_admin)."""
    # SafetyGuard: 鉴权 / readonly (字典还未创建, cache miss → False, 只拦 env readonly)
    await _guard(
        action="create",
        dict_code=body.code,
        key=None,
        user=user,
        confirm_token=None,
        payload={},
    )
    # 业务: insert dictionaries 行
    ip = _client_ip(request)
    try:
        with session_scope() as s:
            existing = s.execute(select(Dictionary).where(Dictionary.code == body.code)).scalar_one_or_none()
            if existing:
                raise LookupSafetyError(409, f"dictionary '{body.code}' already exists")
            d = Dictionary(
                code=body.code,
                label_zh=body.label_zh,
                label_en=body.label_en,
                description=body.description,
                version=1,
                is_active=True,
                is_readonly=False,
            )
            s.add(d)
            s.flush()
            new_dict = {
                "code": d.code,
                "label_zh": d.label_zh,
                "label_en": d.label_en,
                "description": d.description,
                "version": d.version,
                "is_active": d.is_active,
                "is_readonly": d.is_readonly,
            }
    except LookupSafetyError as e:
        raise HTTPException(status_code=e.http_status, detail=e.detail) from e

    # 失效 cache + audit
    await lookup_cache.invalidate(body.code)
    # (2026-07-03) 同步失效 + 重建 permissions L1 metadata cache
    # 单纯 invalidate 会让下个 sync 读走 fallback 9 项, 致 buildNavTree orphan
    invalidate_page_keys_cache()
    await rewarm_page_keys_cache()
    log_dict_change(
        actor=_actor_display(user),
        actor_id=user.id,
        action="dict.create",
        target=body.code,
        before=None,
        after=new_dict,
        ip=ip,
    )
    request.state.audit_ctx.set(target_id=body.code, after={"code": body.code})
    return new_dict


@router.patch(
    "/{dict_code}",
    response_model=DictionarySummaryResponse,
    summary="改字典 metadata",
    description=(
        "## 用途\n\n"
        "改字典的 label_zh / label_en / description / is_active / is_readonly. "
        "code 不可改 (URL path 决定). 不传字段不改 (None 跳过).\n\n"
        "## 鉴权\n\n"
        "`require_super_admin` + SafetyGuard 6 层.\n\n"
        "## 行为\n\n"
        "- 字典不存在 → 404\n"
        "- 改 is_active=False: 紧急下线 (前端 GET 返的字典级开关, items 仍能查)\n"
        "- 改 is_readonly=True: 字典级只读 (后续 POST/PATCH/DELETE 被 SafetyGuard 拦)\n"
        "- audit `dictionary.dict.patch`, before/after 含变更字段\n"
        "- 每次 PATCH version + 1 (触发缓存失效)"
    ),
    responses={
        200: {"description": "改成功, 返更新后字典概要"},
        403: {"description": "权限不足 / readonly"},
        404: {"description": "字典不存在"},
        422: {"description": "Pydantic 校验失败"},
    },
)
@audited("admin.dict.patch", target_type="dictionary")
async def patch_dictionary(
    request: Request,
    dict_code: str,
    body: DictionaryPatchRequest,
    user: CurrentUser = Depends(require_super_admin),
):
    """改字典 metadata (super_admin)."""
    payload = body.model_dump(exclude_none=True)
    await _guard(
        action="patch",
        dict_code=dict_code,
        key=None,
        user=user,
        confirm_token=None,
        payload=payload,
    )
    try:
        result = await LookupService.patch_dict(
            dict_code,
            payload,
            actor=_actor_display(user),
            actor_id=user.id,
            ip=_client_ip(request),
        )
    except LookupNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except LookupSafetyError as e:
        raise HTTPException(status_code=e.http_status, detail=e.detail) from e

    request.state.audit_ctx.set(target_id=dict_code)
    return result


# ==================== item 级 (POST/PATCH/DELETE) ====================


@router.post(
    "/{dict_code}/items",
    response_model=LookupItemResponse,
    status_code=status.HTTP_201_CREATED,
    summary="新增 item",
    description=(
        "## 用途\n\n"
        "往指定字典加新 item. 字典必须存在 (不存在 → 404).\n\n"
        "## 鉴权\n\n"
        "`require_super_admin` + SafetyGuard 6 层.\n\n"
        "## 行为\n\n"
        "- key 格式 `[a-z][a-z0-9_]{0,63}` (Pydantic 422)\n"
        "- UNIQUE(dict_code, key) 冲突 → 409\n"
        "- 创建后字典 version + 1 (触发缓存失效)\n"
        "- audit `dictionary.item.create`, target = '<dict_code>:<key>'"
    ),
    responses={
        201: {"description": "item 创建成功"},
        403: {"description": "权限不足 / readonly"},
        404: {"description": "字典不存在"},
        409: {"description": "item 已存在"},
        422: {"description": "Pydantic 校验失败 (key 格式错 / label 越界)"},
    },
)
@audited("admin.dict.item.create", target_type="dictionary_item")
async def create_item(
    request: Request,
    dict_code: str,
    body: LookupItemCreateRequest,
    user: CurrentUser = Depends(require_super_admin),
):
    """新增 item (super_admin)."""
    payload = body.model_dump(exclude_none=True)
    await _guard(
        action="create",
        dict_code=dict_code,
        key=body.key,
        user=user,
        confirm_token=None,
        payload=payload,
    )
    try:
        result = await LookupService.create_item(
            dict_code,
            payload,
            actor=_actor_display(user),
            actor_id=user.id,
            ip=_client_ip(request),
        )
    except LookupNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except LookupSafetyError as e:
        raise HTTPException(status_code=e.http_status, detail=e.detail) from e

    request.state.audit_ctx.set(
        target_id=f"{dict_code}:{body.key}",
        after={"key": body.key, "label_zh": body.label_zh, "label_en": body.label_en},
    )
    return result


@router.patch(
    "/{dict_code}/items/{key}",
    response_model=LookupItemResponse,
    summary="改 item",
    description=(
        "## 用途\n\n"
        "改 item 的 label/sort/description/is_active/metadata_json. "
        "key 不可改 (rename 需 POST 新 + migrate + DELETE 旧).\n\n"
        "## 鉴权\n\n"
        "`require_super_admin` + SafetyGuard 6 层.\n\n"
        "## 行为\n\n"
        "- item 不存在 → 404\n"
        "- payload 含 expected_version 时校验乐观锁 (SafetyGuard 第 5 层) → 412\n"
        "- audit `dictionary.item.patch`, before/after 含全部字段"
    ),
    responses={
        200: {"description": "改成功, 返更新后 item"},
        403: {"description": "权限不足 / readonly"},
        404: {"description": "item 不存在"},
        412: {"description": "version mismatch (乐观锁失败)"},
        422: {"description": "Pydantic 校验失败"},
    },
)
@audited("admin.dict.item.patch", target_type="dictionary_item")
async def patch_item(
    request: Request,
    dict_code: str,
    key: str,
    body: LookupItemPatchRequest,
    user: CurrentUser = Depends(require_super_admin),
):
    """改 item (super_admin)."""
    payload = body.model_dump(exclude_none=True)
    await _guard(
        action="patch",
        dict_code=dict_code,
        key=key,
        user=user,
        confirm_token=None,
        payload=payload,
    )
    try:
        result = await LookupService.patch_item(
            dict_code,
            key,
            payload,
            actor=_actor_display(user),
            actor_id=user.id,
            ip=_client_ip(request),
        )
    except LookupNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except LookupSafetyError as e:
        raise HTTPException(status_code=e.http_status, detail=e.detail) from e

    request.state.audit_ctx.set(target_id=f"{dict_code}:{key}")
    # (2026-07-03) 同步失效 permissions 进程内 L1 cache
    # LookupService.patch_item 内部已 invalidate lookup_cache (Redis L2 dict cache),
    # (2026-07-03) 同步失效 + 重建 permissions 进程内 L1 cache
    # 但 _page_metadata_cache 是 permissions 模块进程内变量, 写完不刷
    # → /api/permissions/me 拿 stale metadata, buildNavTree 报 orphan
    invalidate_page_keys_cache()
    await rewarm_page_keys_cache()
    return result


@router.delete(
    "/{dict_code}/items/{key}",
    response_model=SoftDeleteItemResponse,
    summary="软删 item",
    description=(
        "## 用途\n\n"
        "软删 item: is_active=False + deprecated_at=NOW(). "
        "**必须传 X-Confirm-Token header** (POST `/api/admin/dicts/confirm-token` 拿).\n\n"
        "## 鉴权\n\n"
        "`require_super_admin` + SafetyGuard 6 层 (含二次确认 + 引用检查).\n\n"
        "## 行为\n\n"
        "- 缺 / 错 X-Confirm-Token → 412\n"
        "- 业务表引用>0 (force=false) → 409, 提示加 `?force=true`\n"
        "- `?force=true` 跳过引用检查, audit log 标 `dictionary.item.delete.forced`\n"
        "- item 不存在 → 404\n"
        "- audit `dictionary.item.delete` (force 时 `.forced`)"
    ),
    responses={
        200: {"description": "软删成功, 返 {key, is_active, deprecated_at, forced}"},
        403: {"description": "权限不足 / readonly"},
        404: {"description": "item 不存在"},
        409: {"description": "业务引用未解 (force=false)"},
        412: {"description": "confirm token 缺失或失效"},
    },
)
@audited("admin.dict.item.delete", target_type="dictionary_item")
async def soft_delete_item(
    request: Request,
    dict_code: str,
    key: str,
    force: bool = Query(False, description="跳过引用检查, audit 标 forced"),
    user: CurrentUser = Depends(require_super_admin),
):
    """软删 item (super_admin + confirm token)."""
    confirm_token = request.headers.get("X-Confirm-Token")
    await _guard(
        action="delete",
        dict_code=dict_code,
        key=key,
        user=user,
        confirm_token=confirm_token,
        payload={},
        force=force,
    )
    try:
        result = await LookupService.soft_delete_item(
            dict_code,
            key,
            actor=_actor_display(user),
            actor_id=user.id,
            ip=_client_ip(request),
            force=force,
        )
    except LookupNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except LookupSafetyError as e:
        raise HTTPException(status_code=e.http_status, detail=e.detail) from e

    request.state.audit_ctx.set(
        target_id=f"{dict_code}:{key}",
        after={"is_active": False, "forced": force},
    )
    # (2026-07-03) 同步失效 + 重建 permissions 进程内 L1 cache (跟 patch_item 同因)
    invalidate_page_keys_cache()
    await rewarm_page_keys_cache()
    return result


# ==================== Confirm Token (签发) ====================


@router.post(
    "/confirm-token",
    response_model=ConfirmTokenResponse,
    summary="签发删除二次确认 token",
    description=(
        "## 用途\n\n"
        "给 super_admin 签发一个 16 字符 hex token, 用于 DELETE item 时 "
        "X-Confirm-Token header. token = sha256('dict-admin-confirm:<user_id>:<YYYYMMDDHH>')[:16], "
        "**1 小时有效** (小时桶). 前端在打开删除对话框时调本端点拿 token, "
        "用户确认删除时把 token 放进 header.\n\n"
        "## 鉴权\n\n"
        "`require_super_admin` 守卫.\n\n"
        "## 行为\n\n"
        "- 返 {token, valid_until}: token 用于 X-Confirm-Token header; "
        "valid_until 是 ISO 8601 当前小时末 + 1h 容错 (跟 safety_guard 接受 ±1h 一致)\n"
        "- 同一小时多次调用返相同 token (sha256 幂等)\n"
        "- token 校验由 SafetyGuard 第 3 层统一处理 (router 层不需要二次校验)"
    ),
    responses={
        200: {"description": "返 {token, valid_until}"},
        403: {"description": "非 super_admin"},
    },
)
def issue_confirm_token(
    user: CurrentUser = Depends(require_super_admin),
):
    """签发删除二次确认 token (16 字符 hex, 1h 有效)."""
    now = datetime.now(UTC)
    bucket = now.strftime("%Y%m%d%H")
    secret = f"dict-admin-confirm:{user.id}"
    token = hashlib.sha256(f"{secret}:{bucket}".encode()).hexdigest()[:16]
    # valid_until: 当前小时末 + 1h 容错 (跟 safety_guard._check_confirm_token 接受 ±1h 一致)
    valid_until = (now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=2)).isoformat()
    logger.info(
        "admin.dict.confirm-token 确认令牌已签发 user_id={} valid_until={}",
        user.id,
        valid_until,
    )
    return {"token": token, "valid_until": valid_until}


# ==================== Audit (读) ====================


@router.get(
    "/{dict_code}/audit",
    response_model=AuditLogListResponse,
    summary="字典变更历史",
    description=(
        "## 用途\n\n"
        "返回某字典的所有 audit_logs 行 (跨 item / 字典级变更, 含 `dictionary.*` action 前缀). "
        "供 super_admin 后台审计字典改动历史.\n\n"
        "## 鉴权\n\n"
        "`require_super_admin` 守卫.\n\n"
        "## 行为\n\n"
        "- 查询 audit_logs WHERE action LIKE 'dictionary.%' "
        "AND (target_id LIKE '<dict_code>:%' OR target_id = '<dict_code>')\n"
        "- 按 ts DESC 排序, 默认 limit 100\n"
        "- 不分页 (审计场景一般 < 100 条 / 字典)"
    ),
    responses={
        200: {"description": "返 {entries, total}"},
        403: {"description": "非 super_admin"},
    },
)
def get_dictionary_audit(
    dict_code: str,
    limit: int = Query(100, ge=1, le=500, description="最大返回条数, 1-500"),
    user: CurrentUser = Depends(require_super_admin),  # noqa: ARG001 (鉴权守卫)
):
    """字典变更历史 (审计日志)."""
    with session_scope() as s:
        # 跨 item / 字典级 audit: target_id LIKE 'dict_code:%' OR target_id = 'dict_code'
        # action LIKE 'dictionary.%' (跟 log_dict_change 命名空间一致)
        q = (
            select(AuditLog)
            .where(
                AuditLog.action.like("dictionary.%"),
                or_(
                    AuditLog.target_id.like(f"{dict_code}:%"),
                    AuditLog.target_id == dict_code,
                ),
            )
            .order_by(AuditLog.ts.desc())
            .limit(limit)
        )
        rows = s.execute(q).scalars().all()

    # ORM Column[T] 类型在 select().scalars() 后 pyright 推不出 T 实例, 这里用 cast 防御
    entries = [
        AuditLogEntry(
            id=cast(int, row.id),
            ts=cast(datetime, row.ts),
            actor_id=cast(int, row.actor_id),
            actor_display=(cast(dict, row.meta or {})).get("actor_display"),
            action=cast(str, row.action),
            target_id=cast(str, row.target_id),
            before=cast(dict | None, row.before),
            after=cast(dict | None, row.after),
            # psycopg3 把 PG INET 列反序列化为 IPv4Address 对象, Pydantic v2 不自动 coerce 成 str.
            # 边界 stringify 兜底, 详见 docs/superpowers/handoffs/2026-06-25-postgres-json-jsonb-family-bugs.md
            ip=str(row.ip) if row.ip is not None else None,
        )
        for row in rows
    ]
    return {"entries": entries, "total": len(entries)}
