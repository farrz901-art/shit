"""FastAPI 路由 — 8 端点: 提交/列表/我的/详情/统计 + 批准/拒绝/重试.

鉴权分层:
- 提交 (POST) / 我的 (GET me) / 详情 (GET {id}) → 任意登录用户
- 列表 (GET) / 统计 (GET stats) / 批准/拒绝/重试 (POST * ) → admin only

依赖项: ApprovalService + SqlAlchemyApprovalRepo (AsyncSession, 跟 service.py Protocol).

模块加载策略: resolve_user 在依赖函数体内 lazy import, 避免循环
(src.middleware.auth 顶层会 import src.auth.account_models → src.auth.__init__ →
 auth_account_router → src.middleware.auth (部分) → CRASH).
"""

from __future__ import annotations

import json
from collections.abc import AsyncGenerator
from typing import Annotated, Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from ..common.db_url import get_rag_db_url
from .executor import apply_approval
from .models import Approval, ApprovalKind, RejectReason
from .repo import SqlAlchemyApprovalRepo
from .service import (
    ApprovalNotFoundError,
    ApprovalService,
    InvalidStateError,
)

router = APIRouter(prefix="/api/approvals", tags=["approvals"])


# --- 鉴权依赖 (lazy import 避开 src.auth 循环) ---


def _resolve_user(request: Request) -> Any:
    """FastAPI 鉴权依赖 — lazy import 拿 src.middleware.auth.resolve_user, 真调它返 CurrentUser.

    ⚠️ 必须传 request (FastAPI 自动注入); 内部调真 resolve_user 拿 CurrentUser 实例
    (不能返函数本身, 否则 Depends 注入的是函数, 端点取 user.id 会 AttributeError).
    """
    # 防循环: middleware.auth 顶层 import 触发 auth chain
    from ..middleware.auth import resolve_user as _ru  # noqa: E402

    return _ru(request)


# 测试用: dependency_overrides 必须 override 这个函数本身 (router 注册的依赖是它, 不是
# src.middleware.auth.resolve_user)
resolve_user_dep = _resolve_user


def _current_user_cls():
    """lazy import 拿 CurrentUser 类型 (用于 isinstance 守卫)."""
    # 防循环: 同 _resolve_user, middleware.auth 顶层 import 触发 auth chain
    from ..middleware.auth import CurrentUser as _CU  # noqa: E402

    return _CU


def require_login(user: Any = Depends(_resolve_user)) -> Any:
    """任意登录用户 (resolve_user 失败时已 401)."""
    return user


def require_admin(user: Any = Depends(_resolve_user)) -> Any:
    """admin-only: 拿不到 admin 身份 → 403."""
    CU = _current_user_cls()
    if not isinstance(user, CU) or not user.is_admin:
        raise HTTPException(status_code=403, detail="admin required")
    return user


# --- 异步 DB session 依赖 (repo 要 AsyncSession) ---


def _to_async_url(url: str) -> str:
    """PG-only: sync URL (psycopg) → async URL (asyncpg)."""
    if url.startswith("postgresql+psycopg://"):
        return url.replace("postgresql+psycopg://", "postgresql+asyncpg://", 1)
    return url


def _get_async_engine() -> Any:
    """懒构造 async engine.

    注: 不缓存. asyncpg 跟 pytest-asyncio event loop 冲突 (TestClient 自己也管 loop).
    生产用 _async_engine_cache 单例没问题, 但测试会撞 "Event loop is closed".
    """
    url = _to_async_url(get_rag_db_url())
    return create_async_engine(
        url,
        pool_pre_ping=True,
        echo=False,
    )


# 保留 module-level 引用让测试可以清理 (avoid 弃用警告, 但实际不 cache)
_async_engine_cache: dict[str, Any] = {}


def _make_async_sessionmaker() -> async_sessionmaker[AsyncSession]:
    """懒构造: 每次拿当前 engine 重建 (跟 storage.session._make_session 风格一致)."""
    return async_sessionmaker(bind=_get_async_engine(), expire_on_commit=False)


async def _get_session() -> AsyncGenerator[AsyncSession]:
    """FastAPI Depends: 每个请求一个 AsyncSession, 用完 close."""
    Session = _make_async_sessionmaker()
    session = Session()
    try:
        yield session
    finally:
        await session.close()


async def _get_repo(session: AsyncSession = Depends(_get_session)) -> SqlAlchemyApprovalRepo:
    """构造 repo (绑定本请求 session)."""
    return SqlAlchemyApprovalRepo(session)


async def _get_svc(repo: SqlAlchemyApprovalRepo = Depends(_get_repo)) -> ApprovalService:
    """构造 service (绑定本请求 repo)."""
    return ApprovalService(repo=repo)


# --- 请求体 ---


class RejectBody(BaseModel):
    """reject 请求体: reason 必填, reason=other 时 note 必填."""

    reason: RejectReason = Field(..., description="拒绝原因枚举: invalid / duplicate / outdated / other")
    note: str | None = Field(default=None, max_length=500, description="备注; reason=other 时必填, 其他情况可选")


class SubmitBody(BaseModel):
    """submit 请求体: kind + payload (任意 dict, 落库前 json.dumps)."""

    kind: ApprovalKind = Field(..., description="审核类型枚举, 决定 apply 阶段用哪个 executor")
    payload: dict[str, Any] = Field(..., description="自由 JSON, 落库前 json.dumps; 业务侧 schema 由 kind 决定")


# --- 端点 ---


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="提交审核项",
    description=(
        "## 用途\n\n"
        "登录用户提交一个待审核项; 服务端写库 (kind + payload), 创建后 review_status 默认 pending.\n\n"
        "## 鉴权\n\n"
        "`require_login` — 任意已登录用户.\n\n"
        "## 行为\n\n"
        "body 含 `kind` (枚举, e.g. `kg_upsert` / `kg_delete` / `config_change`) 和 `payload` (任意 dict, 落库前 json.dumps). "
        "成功返 201 + `{id, kind, review_status, apply_status}`. "
        "**后续**: admin 通过 `POST /api/approvals/{id}/approve` 批准后, 后台 task 调 executor 跑 apply, 写 `apply_status`."
    ),
    responses={
        201: {"description": "已创建, body 返 `{id, kind, review_status, apply_status}`"},
        401: {"description": "未登录 / token 无效"},
        422: {"description": "Pydantic 校验失败 (kind 枚举 / payload 类型)"},
    },
)
async def submit(
    body: SubmitBody,
    svc: Annotated[ApprovalService, Depends(_get_svc)],
    user: Annotated[Any, Depends(require_login)],
) -> dict[str, Any]:
    approval = await svc.submit(body.kind, body.payload, user)
    return {
        "id": approval.id,
        "kind": approval.kind,
        "review_status": approval.review_status,
        "apply_status": approval.apply_status,
    }


@router.get(
    "",
    summary="admin 列审核项",
    description=(
        "## 用途\n\n"
        "管理员视角的审核项列表; 支持按 `review` (pending/approved/rejected) 和 `apply` (pending/applied/failed) 过滤.\n\n"
        "## 鉴权\n\n"
        "`require_admin` — admin only.\n\n"
        "## 行为\n\n"
        "分页 `skip` / `limit` (limit 1-100, 默认 20). "
        "返 list, 每个元素通过 `_serialize` 序列化 (不带 payload, 防列表响应过大); "
        "想看 payload 调 `GET /api/approvals/{id}` 或传 `include_payload=true` (本端点暂不暴露, 走详情接口)."
    ),
    responses={
        200: {"description": "返审核项 list (无 payload 字段)"},
        401: {"description": "未登录 / token 无效"},
        403: {"description": "非 admin 角色"},
        422: {"description": "limit 越界 (>100 或 <1)"},
    },
)
async def list_all(
    repo: Annotated[SqlAlchemyApprovalRepo, Depends(_get_repo)],
    _admin: Annotated[Any, Depends(require_admin)],
    review: str | None = Query(default=None),
    apply: str | None = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
) -> list[dict[str, Any]]:
    items = await repo.list(review=review, apply=apply, skip=skip, limit=limit)
    return [_serialize(a) for a in items]


@router.get(
    "/me",
    summary="列当前用户提交",
    description=(
        "## 用途\n\n"
        "当前登录用户自己提交过的审核项 (服务端自动按 `user_id` 过滤, 不接受外部传 submitter_id).\n\n"
        "## 鉴权\n\n"
        "`require_login` — 任意已登录用户.\n\n"
        "## 行为\n\n"
        "支持 `review` / `apply` 过滤 + `skip` / `limit` 分页. "
        "返 list (无 payload 字段), 跨用户记录不可见, 不存在/越权统一 list (空或过滤后), 不会泄露他人信息."
    ),
    responses={
        200: {"description": "返当前用户提交过的审核项 list (无 payload)"},
        401: {"description": "未登录 / token 无效"},
        422: {"description": "limit 越界"},
    },
)
async def list_mine(
    repo: Annotated[SqlAlchemyApprovalRepo, Depends(_get_repo)],
    user: Annotated[Any, Depends(require_login)],
    review: str | None = Query(default=None),
    apply: str | None = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
) -> list[dict[str, Any]]:
    items = await repo.list(
        review=review,
        apply=apply,
        submitter_id=user.id,
        skip=skip,
        limit=limit,
    )
    return [_serialize(a) for a in items]


@router.get(
    "/stats",
    summary="admin 概览",
    description=(
        "## 用途\n\n"
        "管理员 dashboard 用的概览数字 — pending (待审核) / applied (已应用) / failed (应用失败) 三个计数.\n\n"
        "## 鉴权\n\n"
        "`require_admin` — admin only.\n\n"
        "## 行为\n\n"
        "实现为 3 次 `repo.list(limit=1000)` 计数; 上限 1000 防止极大量时拉全表. "
        "返 `{pending: int, applied: int, failed: int}`. "
        "注意: `pending` 数的是 `review_status=pending` (未审核), `applied` / `failed` 数的是 `apply_status` (执行结果)."
    ),
    responses={
        200: {"description": "返 `{pending, applied, failed}` 三个 int 计数"},
        401: {"description": "未登录 / token 无效"},
        403: {"description": "非 admin 角色"},
    },
)
async def stats(
    repo: Annotated[SqlAlchemyApprovalRepo, Depends(_get_repo)],
    _admin: Annotated[Any, Depends(require_admin)],
) -> dict[str, int]:
    return {
        "pending": len(await repo.list(review="pending", limit=1000)),
        "applied": len(await repo.list(apply="applied", limit=1000)),
        "failed": len(await repo.list(apply="failed", limit=1000)),
    }


@router.get(
    "/{approval_id}",
    summary="查单条详情",
    description=(
        "## 用途\n\n"
        "查单条审核项的完整字段; 默认包含 payload (审批人需要看提交内容才能决策).\n\n"
        "## 鉴权\n\n"
        "`require_login` — 任意已登录用户, **但有所有权校验**.\n\n"
        "## 行为\n\n"
        "`approval_id` 不存在 → 404 `not found`. "
        "存在但不是 submitter 本人且非 admin → 403 `forbidden` (防越权读别人 payload). "
        "admin 可看任意. 返的 payload 默认包含 (与列表接口的 strip 行为不同, 详情接口要全部展示)."
    ),
    responses={
        200: {"description": "返完整记录 (含 payload, json.loads 反序列化)"},
        401: {"description": "未登录 / token 无效"},
        403: {"description": "不是 submitter 且非 admin"},
        404: {"description": "approval_id 不存在"},
    },
)
async def get_detail(
    approval_id: int,
    repo: Annotated[SqlAlchemyApprovalRepo, Depends(_get_repo)],
    user: Annotated[Any, Depends(require_login)],
) -> dict[str, Any]:
    approval = await repo.get(approval_id)
    if approval is None:
        raise HTTPException(status_code=404, detail="not found")
    if approval.submitter_id != user.id and not user.is_admin:
        raise HTTPException(status_code=403, detail="forbidden")
    return _serialize(approval, include_payload=True)


@router.post(
    "/{approval_id}/approve",
    summary="批准 + 触发后台",
    description=(
        "## 用途\n\n"
        "admin 批准一个 pending 审核项; 服务端把 `review_status` 改成 `approved` 并落 reviewer_id/时间, "
        "再用 `BackgroundTasks` 异步跑 apply (写业务表 / Neo4j 等).\n\n"
        "## 鉴权\n\n"
        "`require_admin` — admin only.\n\n"
        "## 行为\n\n"
        "`approval_id` 不存在 → 404 `not found`. "
        "当前 `review_status` 不是 `pending` (e.g. 已 approved / 已 rejected) → 409 `InvalidStateError`. "
        "成功: 写 approved + `BackgroundTasks.add_task(apply_approval, ...)`. "
        "BGTask 跟 FastAPI 进程同生命周期, 用完即弃; apply 状态变更由 executor 自行负责. "
        "返序列化后的最新 approval (此时 apply_status 通常仍 pending, apply 是异步跑)."
    ),
    responses={
        200: {"description": "已批准, 返最新 approval; apply 后台异步跑"},
        401: {"description": "未登录 / token 无效"},
        403: {"description": "非 admin 角色"},
        404: {"description": "approval_id 不存在"},
        409: {"description": "当前 review_status 不是 pending (状态冲突)"},
    },
)
async def approve(
    approval_id: int,
    background: BackgroundTasks,
    svc: Annotated[ApprovalService, Depends(_get_svc)],
    repo: Annotated[SqlAlchemyApprovalRepo, Depends(_get_repo)],
    admin: Annotated[Any, Depends(require_admin)],
) -> dict[str, Any]:
    try:
        approval = await svc.approve(approval_id, admin)
    except ApprovalNotFoundError:
        raise HTTPException(status_code=404, detail="not found")
    except InvalidStateError as e:
        raise HTTPException(status_code=409, detail=str(e))

    # BGTask 跟 FastAPI 进程同生命周期, 用完即弃
    background.add_task(apply_approval, approval_id, svc, repo=repo)
    return _serialize(approval)


@router.post(
    "/{approval_id}/reject",
    summary="拒绝",
    description=(
        "## 用途\n\n"
        "admin 拒绝一个 pending 审核项; 写 `review_status=rejected` + `rejection_reason` + 可选 `rejection_note`.\n\n"
        "## 鉴权\n\n"
        "`require_admin` — admin only.\n\n"
        "## 行为\n\n"
        "body 必填字段: `reason` (枚举: `duplicate` / `inappropriate` / `wrong_format` / `other`); "
        "`reason=other` 时 `note` 也必填 (否则 422). "
        "`approval_id` 不存在 → 404; 当前 `review_status` 不是 `pending` → 409. "
        "成功返序列化后的 approval (review_status=rejected, 含 rejection_reason/note)."
    ),
    responses={
        200: {"description": "已拒绝, 返最新 approval (含 rejection_reason/note)"},
        401: {"description": "未登录 / token 无效"},
        403: {"description": "非 admin 角色"},
        404: {"description": "approval_id 不存在"},
        409: {"description": "当前 review_status 不是 pending (状态冲突)"},
        422: {"description": "reason=other 时 note 为空 / Pydantic 校验失败"},
    },
)
async def reject(
    approval_id: int,
    body: RejectBody,
    svc: Annotated[ApprovalService, Depends(_get_svc)],
    admin: Annotated[Any, Depends(require_admin)],
) -> dict[str, Any]:
    if body.reason == RejectReason.OTHER and not body.note:
        raise HTTPException(status_code=422, detail="reason=other 时 note 必填")
    try:
        approval = await svc.reject(approval_id, body.reason, body.note, admin)
    except ApprovalNotFoundError:
        raise HTTPException(status_code=404, detail="not found")
    except InvalidStateError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return _serialize(approval)


@router.post(
    "/{approval_id}/retry",
    summary="重试失败的",
    description=(
        "## 用途\n\n"
        "admin 重试一个已批准但应用失败的审核项 — `review_status=approved` + `apply_status=failed` 是唯一可重试的组合.\n\n"
        "## 鉴权\n\n"
        "`require_admin` — admin only.\n\n"
        "## 行为\n\n"
        "`approval_id` 不存在 → 404; 状态组合不匹配 (e.g. 还在 pending, 或 apply 已成功, 或 review 被 reject) → 409 `InvalidStateError`. "
        "成功后清空 `apply_status` (回 pending) + 重新挂 `BackgroundTasks.add_task(apply_approval, ...)`. "
        "返序列化后的最新 approval."
    ),
    responses={
        200: {"description": "已重试, 返最新 approval; apply 后台异步跑"},
        401: {"description": "未登录 / token 无效"},
        403: {"description": "非 admin 角色"},
        404: {"description": "approval_id 不存在"},
        409: {"description": "状态不满足 (review != approved 或 apply != failed)"},
    },
)
async def retry(
    approval_id: int,
    background: BackgroundTasks,
    svc: Annotated[ApprovalService, Depends(_get_svc)],
    repo: Annotated[SqlAlchemyApprovalRepo, Depends(_get_repo)],
    admin: Annotated[Any, Depends(require_admin)],
) -> dict[str, Any]:
    try:
        approval = await svc.retry(approval_id, admin)
    except ApprovalNotFoundError:
        raise HTTPException(status_code=404, detail="not found")
    except InvalidStateError as e:
        raise HTTPException(status_code=409, detail=str(e))

    background.add_task(apply_approval, approval_id, svc, repo=repo)
    return _serialize(approval)


# --- helper ---


def _serialize(a: Approval, include_payload: bool = False) -> dict[str, Any]:
    """Approval → JSON dict. 不带 include_payload 时省略 (避免列表响应过大)."""
    d = {
        "id": a.id,
        "kind": a.kind,
        "review_status": a.review_status,
        "apply_status": a.apply_status,
        "submitter_id": a.submitter_id,
        "reviewer_id": a.reviewer_id,
        "rejection_reason": a.rejection_reason,
        "rejection_note": a.rejection_note,
        "error_msg": a.error_msg,
        "created_at": a.created_at.isoformat() if a.created_at else None,
        "reviewed_at": a.reviewed_at.isoformat() if a.reviewed_at else None,
        "applied_at": a.applied_at.isoformat() if a.applied_at else None,
    }
    if include_payload:
        d["payload"] = json.loads(a.payload) if a.payload else None
    return d
