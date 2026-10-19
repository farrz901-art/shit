"""记忆 HTTP 端点 (2026-06-16)

POST   /api/memory/search    - 检索相关记忆
POST   /api/memory/add       - 写入本轮对话
GET    /api/memory/list      - 列当前用户所有记忆 (Phase 2)
PATCH  /api/memory/{id}      - 编辑单条记忆 text (Phase 2)
DELETE /api/memory/{id}      - 删单条 (Phase 2)
DELETE /api/memory/all       - 清空所有 (Phase 2)

跟 kg / approvals 路由同款: 浏览器直连 + Depends(require_account) 注入鉴权.

**Phase 2 安全**: mem0 self-host 的 m.update / m.delete 不传 user_id, service 层 _assert_owned 守卫.
PermissionError 在 router 翻译为 403 (不区分 not-found / forbidden, 防 ID 探测).

日志约定 (2026-06-17): router 记入口 (传参) + 出口 (命中条数), service 不重复记,
service 仅在异常 / LLM 拒抽 (add) 时 WARNING. 0 INFO 表示无 warning 级别问题.
"""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response, status
from loguru import logger

from ..core.audit import audited
from ..middleware.auth import CurrentUser
from ..permissions.guards import require_account
from . import service as _service_mod
from .schemas import (
    AddRequest,
    DeleteResponse,
    MemoryListResponse,
    SearchRequest,
    SearchResponse,
    UpdateRequest,
)

router = APIRouter(prefix="/api/memory", tags=["memory"])
# 别名: 跟 plan 约定, register_routers / test_router 引用 memory_router
memory_router = router


def _get_service():
    """工厂方法: 每次返回新的 MemoryService 实例, 避免线程安全问题.

    走 `service.get_memory_service` 属性访问 (不是模块顶 import), 让 test 用
    `monkeypatch.setattr(service_mod, "get_memory_service", ...)` 替换生效.
    """
    return _service_mod.get_memory_service()


@router.post(
    "/search",
    response_model=SearchResponse,
    summary="检索相关记忆",
    description=(
        "## 用途\n\n"
        "按 query 文本检索与当前用户相关的历史记忆, 返回按相似度排序的列表. "
        "供 chat / recommend 链路在做答前注入相关上下文.\n\n"
        "## 鉴权\n\n"
        "`require_account` 守卫: 必须登录, 注入 `current.id` 作为 mem0 user_id.\n\n"
        "## 行为\n\n"
        "调 mem0 `m.search(query, user_id=current.id, limit=req.limit)`. "
        "降级: Mem0 不可达 → service 吞异常 + log, 直接返 `memories=[]`. "
        "mem0 自身按 user_id 过滤, 无跨用户风险."
    ),
    responses={
        200: {"description": "命中列表 (可能为空)"},
        401: {"description": "未登录 / token 无效"},
        422: {"description": "Pydantic 校验失败 (query / limit 范围)"},
    },
)
def search(req: SearchRequest, current: CurrentUser = Depends(require_account)) -> SearchResponse:
    memories = _get_service().search(current, req.query, req.limit)
    logger.info(
        "search user_id={} query_len={} limit={} 命中={}", current.id, len(req.query or ""), req.limit, len(memories)
    )
    return SearchResponse(memories=memories)


@router.post(
    "/add",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="写入本轮对话",
    description=(
        "## 用途\n\n"
        "把本轮 user + assistant 完整对话作为一条记忆写入 mem0, 供后续 search 召回. "
        "chat 链路在 assistant 答完一轮后调用, 让用户跨会话保持上下文.\n\n"
        "## 鉴权\n\n"
        "`require_account` 守卫: 必须登录, 注入 `current.id` 作为 mem0 user_id.\n\n"
        "## 行为\n\n"
        "调 mem0 `m.add(messages, user_id=current.id, conversation_id=req.conversation_id)`. "
        "**失败静默吞**: service 捕获异常 + WARNING log, router 仍返 204. "
        "msgs 1-20 条 (Pydantic 边界)."
    ),
    responses={
        204: {"description": "写入完成 (即便 service 内部失败, 静默吞)"},
        401: {"description": "未登录 / token 无效"},
        422: {"description": "Pydantic 校验失败 (messages 数量 1-20 / conversation_id 格式)"},
    },
)
def add(
    req: AddRequest,
    background_tasks: BackgroundTasks,
    current: CurrentUser = Depends(require_account),
) -> Response:
    msg_dicts = [t.model_dump() for t in req.messages]
    logger.info("memory.add 消息已添加 user_id={} msgs={} conv={}", current.id, len(msg_dicts), req.conversation_id)
    _get_service().add(current, msg_dicts, req.conversation_id)

    # fire-and-forget: 如果有 buyer_key, 异步提取客户画像字段
    if req.buyer_key and current.account_id:
        # 重依赖 lazy: buyer_profile.service 内部触发 src.storage.session 装载,
        # 非 buyer_key 路径 (memory 普通 CRUD) 不需要付出这层开销
        from src.buyer_profile.service import ProfileService  # noqa: E402

        background_tasks.add_task(
            ProfileService.try_extract,
            account_id=current.account_id,
            buyer_key=req.buyer_key,
            messages=msg_dicts,
        )

    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---- Phase 2 (2026-06-16): 记忆管理 ----


@router.get(
    "/list",
    response_model=MemoryListResponse,
    summary="列当前用户所有记忆",
    description=(
        "## 用途\n\n"
        "列出当前用户的所有记忆, 用于管理 UI (查看 / 编辑 / 删除) 场景. "
        "chat 链路不调用, 仅供前端 /admin/memory 类页面使用.\n\n"
        "## 鉴权\n\n"
        "`require_account` 守卫: 必须登录, 注入 `current.id` 作为 mem0 user_id.\n\n"
        "## 行为\n\n"
        "调 mem0 `m.get_all(user_id=current.id)`. "
        "降级: Mem0 不可达 → service 吞异常 + log, 直接返 `memories=[]`. "
        "mem0 get_all 自身带 `filters={user_id}` 隔离, 无 PermissionError 风险."
    ),
    responses={
        200: {"description": "记忆列表 (可能为空)"},
        401: {"description": "未登录 / token 无效"},
    },
)
def list_memories(current: CurrentUser = Depends(require_account)) -> MemoryListResponse:
    memories = _get_service().list_memories(current)
    logger.info("list user_id={} 命中={}", current.id, len(memories))
    return MemoryListResponse(memories=memories)


# 注意路由顺序: /all 必须在 /{memory_id} 之前注册, 否则 "all" 会被当 memory_id 解析
@router.delete(
    "/all",
    response_model=DeleteResponse,
    summary="清空当前用户所有记忆",
    description=(
        "## 用途\n\n"
        "一键清空当前用户的所有记忆, 用于 reset / 隐私擦除场景.\n\n"
        "## 鉴权\n\n"
        "`require_account` 守卫: 必须登录, 注入 `current.id` 作为 mem0 user_id.\n\n"
        "## 行为\n\n"
        "调 mem0 `m.delete_all(user_id=current.id)`, 自带 user_id 隔离, 不需要 `_assert_owned` 守卫. "
        "**返 `{deleted_count: 0}` 占位**: mem0 delete_all 不返 count, 用 0 保持 schema 稳定. "
        "前端拿到 0 时按'操作成功但数量未知'处理."
    ),
    responses={
        200: {"description": "清空完成 (deleted_count 永远为 0, mem0 不返 count)"},
        401: {"description": "未登录 / token 无效"},
    },
)
@audited("memory.purge_all", target_type="memory")
async def delete_all_memories(
    request: Request,
    current: CurrentUser = Depends(require_account),
) -> DeleteResponse:
    request.state.audit_ctx.set(
        target_id=str(current.id),
    )
    _get_service().delete_all_memories(current)
    return DeleteResponse(deleted_count=0)


@router.patch(
    "/{memory_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="编辑单条记忆",
    description=(
        "## 用途\n\n"
        "编辑指定 ID 的单条记忆 text 字段. 用户在管理 UI 修正 LLM 抽错的事实.\n\n"
        "## 鉴权\n\n"
        "`require_account` 守卫: 必须登录, service 层 `_assert_owned` 校验 `memory_id` 归属.\n\n"
        "## 行为\n\n"
        "调 mem0 `m.update(memory_id, text=...)` (mem0 self-host 不传 user_id, 必须 service 层守). "
        "**跨用户 → 403**: service 抛 `PermissionError`, router 翻译为 403. "
        "**不区分 404 / 403**: 即便 memory_id 不存在也走 403 分支, 防 ID 探测. "
        "其它异常 → 500."
    ),
    responses={
        204: {"description": "编辑完成"},
        401: {"description": "未登录 / token 无效"},
        403: {"description": "记忆不属于当前用户 (或不存在, 防 ID 探测)"},
        422: {"description": "Pydantic 校验失败 (text 长度等)"},
    },
)
def update_memory(
    memory_id: str,
    req: UpdateRequest,
    current: CurrentUser = Depends(require_account),
) -> Response:
    try:
        _get_service().update_memory(current, memory_id, req.text)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete(
    "/{memory_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="删单条记忆",
    description=(
        "## 用途\n\n"
        "删除指定 ID 的单条记忆. 用户在管理 UI 撤回某条不愿保留的事实.\n\n"
        "## 鉴权\n\n"
        "`require_account` 守卫: 必须登录, service 层 `_assert_owned` 校验 `memory_id` 归属.\n\n"
        "## 行为\n\n"
        "调 mem0 `m.delete(memory_id)` (mem0 self-host 不传 user_id, 必须 service 层守). "
        "**跨用户 → 403**: service 抛 `PermissionError`, router 翻译为 403. "
        "**不区分 404 / 403**: 即便 memory_id 不存在也走 403 分支, 防 ID 探测. "
        "其它异常 → 500."
    ),
    responses={
        204: {"description": "删除完成"},
        401: {"description": "未登录 / token 无效"},
        403: {"description": "记忆不属于当前用户 (或不存在, 防 ID 探测)"},
    },
)
@audited("memory.delete", target_type="memory")
async def delete_memory(
    request: Request,
    memory_id: str,
    current: CurrentUser = Depends(require_account),
) -> Response:
    request.state.audit_ctx.set(
        target_id=str(memory_id),
    )
    try:
        _get_service().delete_memory(current, memory_id)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e
    return Response(status_code=status.HTTP_204_NO_CONTENT)
