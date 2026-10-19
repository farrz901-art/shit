"""buyer_profile/router.py: HTTP 端点 (2026-06-22)

9 个端点:
- GET    /api/buyer-profiles/              列表 (分页 + status 过滤)
- GET    /api/buyer-profiles/{id}           详情
- PATCH  /api/buyer-profiles/{id}           更新 (204, audited)
- DELETE /api/buyer-profiles/{id}           归档 (204, audited)
- GET    /api/buyer-profiles/{id}/changes   变更日志
- GET    /api/buyer-profiles/fields         字段配置列表
- POST   /api/buyer-profiles/fields         创建字段配置
- PATCH  /api/buyer-profiles/fields/{code}  更新字段配置
- DELETE /api/buyer-profiles/fields/{code}  软删字段配置

鉴权: 全量 require_account (禁用 anon).
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from loguru import logger

from ..core.audit import audited
from ..middleware.auth import CurrentUser
from ..permissions.guards import require_account
from .field_config import (
    create_config,
    get_all_configs,
    soft_delete_config,
    update_config,
)
from .schemas import (
    BuyerProfileListResponse,
    BuyerProfileResponse,
    BuyerProfileUpdate,
    ChangeLogResponse,
    ProfileFieldConfigCreate,
    ProfileFieldConfigResponse,
    ProfileFieldConfigUpdate,
)
from .service import ProfileService

router = APIRouter(prefix="/api/buyer-profiles", tags=["buyer_profiles"])


# ── 字段配置 (放前面避免跟 {profile_id} 冲突) ─────────────────────────


@router.get(
    "/fields",
    response_model=list[ProfileFieldConfigResponse],
    summary="字段配置列表",
    description="返回所有字段配置 (含已停用), 按 sort_order 排序.",
)
async def list_field_configs() -> list[dict]:
    return get_all_configs()


@router.post(
    "/fields",
    response_model=ProfileFieldConfigResponse,
    status_code=status.HTTP_201_CREATED,
    summary="创建字段配置",
    description="创建新的画像字段定义, code 必须唯一.",
)
async def create_field_config(
    body: ProfileFieldConfigCreate,
    current_user: CurrentUser = Depends(require_account),
) -> dict:
    result = create_config(body.model_dump())
    logger.info("buyer_profile.field_config.created 字段配置已创建 code={}", body.code)
    return result


@router.patch(
    "/fields/{code}",
    response_model=ProfileFieldConfigResponse,
    summary="更新字段配置",
    description="按 code 更新字段配置, 返回更新后记录.",
)
async def update_field_config(
    code: str,
    body: ProfileFieldConfigUpdate,
    current_user: CurrentUser = Depends(require_account),
) -> dict:
    result = update_config(code, body.model_dump(exclude_none=True))
    if not result:
        raise HTTPException(status_code=404, detail="field config not found")
    logger.info("buyer_profile.field_config.updated 字段配置已更新 code={}", code)
    return result


@router.delete(
    "/fields/{code}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="软删字段配置",
    description="按 code 软删字段配置 (is_active = false).",
)
@audited("buyer_profile.field_config.delete", target_type="profile_field_config")
async def delete_field_config(
    code: str,
    request: Request,
    current_user: CurrentUser = Depends(require_account),
) -> None:
    request.state.audit_ctx.set(target_id=code)
    ok = soft_delete_config(code)
    if not ok:
        raise HTTPException(status_code=404, detail="field config not found")


# ── 我的客户画像 ──────────────────────────────────────────────


@router.get(
    "/my-profile",
    response_model=BuyerProfileResponse,
    summary="我的客户画像",
    description="获取当前登录账户的客户画像, 不存在时自动创建.",
)
async def get_my_profile(
    current_user: CurrentUser = Depends(require_account),
) -> dict:
    aid = current_user.account_id
    assert aid is not None  # require_account 确保已登录
    buyer_key = str(aid)
    profile = ProfileService.get_profile(aid, buyer_key)
    if not profile:
        profile = ProfileService.create_or_get_profile(aid, buyer_key)
        if not profile:
            raise HTTPException(status_code=500, detail="failed to create profile")
    return profile


# ── 客户画像 CRUD ────────────────────────────────────────────


@router.get(
    "/",
    response_model=BuyerProfileListResponse,
    summary="客户画像列表",
    description="分页列出客户画像, 支持 status 过滤.",
)
async def list_profiles(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    status: str | None = None,
    current_user: CurrentUser = Depends(require_account),
) -> dict:
    aid = current_user.account_id
    assert aid is not None  # require_account 确保已登录
    filters = {"status": status} if status else None
    items, total = ProfileService.list_profiles(aid, limit, offset, filters)
    logger.info("buyer_profile.list 查询已处理 aid={} total={}", aid, total)
    return {"items": items, "total": total}


@router.get(
    "/{profile_id}",
    response_model=BuyerProfileResponse,
    summary="客户画像详情",
    description="按 UUID id 查询单个画像详情.",
)
async def get_profile(
    profile_id: UUID,
    current_user: CurrentUser = Depends(require_account),
) -> dict:
    aid = current_user.account_id
    assert aid is not None  # require_account 确保已登录
    result = ProfileService.get_profile_by_id(aid, profile_id)
    if not result:
        raise HTTPException(status_code=404, detail="profile not found")
    return result


@router.patch(
    "/{profile_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="更新客户画像",
    description="按 id 更新客户画像字段, 只更新非 None 字段.",
)
@audited("buyer_profile.update", target_type="buyer_profile")
async def update_profile(
    profile_id: UUID,
    body: BuyerProfileUpdate,
    request: Request,
    current_user: CurrentUser = Depends(require_account),
) -> None:
    aid = current_user.account_id
    assert aid is not None  # require_account 确保已登录
    request.state.audit_ctx.set(target_id=str(profile_id))
    ok = ProfileService.update_profile_by_id(aid, profile_id, body)
    if not ok:
        raise HTTPException(status_code=404, detail="profile not found")


@router.delete(
    "/{profile_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="归档客户画像",
    description="软删 (status = 'archived'), data 保留可按 buyer_key 重建.",
)
@audited("buyer_profile.delete", target_type="buyer_profile")
async def archive_profile(
    profile_id: UUID,
    request: Request,
    current_user: CurrentUser = Depends(require_account),
) -> None:
    aid = current_user.account_id
    assert aid is not None  # require_account 确保已登录
    request.state.audit_ctx.set(target_id=str(profile_id))
    ok = ProfileService.soft_delete(aid, profile_id)
    if not ok:
        raise HTTPException(status_code=404, detail="profile not found")


@router.get(
    "/{profile_id}/changes",
    response_model=list[ChangeLogResponse],
    summary="变更日志",
    description="返回指定画像的字段变更历史, 按 created_at DESC 排序.",
)
async def get_changes(
    profile_id: UUID,
    current_user: CurrentUser = Depends(require_account),
) -> list[dict]:
    aid = current_user.account_id
    assert aid is not None  # require_account 确保已登录
    return ProfileService.get_changes(aid, profile_id)
