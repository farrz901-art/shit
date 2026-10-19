"""chat_router: 已登录用户的聊天历史 CRUD (2026-06-19 chat spec §5)

跟 chat_share_router 区分:
- chat_share_router: 公开 share 链接 (anon 可读)
- chat_router: 账号私有历史 (登录用户 CRUD + 软删 + 备份)

7 端点:
- POST   /conversations          创建 (title 默认 '新对话')
- GET    /conversations          列表 (分页 20/页, 按 updated_at DESC)
- GET    /conversations/{id}     详情 (含 messages)
- PATCH  /conversations/{id}     重命名 (audit 'chat.conv.rename')
- DELETE /conversations/{id}     软删 (audit 'chat.conv.delete', 30d cron hard-delete)
- GET    /conversations/{id}/messages  单 conv 消息分页 (50/页)
- GET    /backup                 全量导出 JSON (GDPR)

鉴权: 全端点走 resolve_user (登录用户; anon 401)
跨用户: 返 404 (防 ID 探测, 跟 chat_share 一致)
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from loguru import logger

from ..core.audit import audited
from ..middleware.auth import CurrentUser, resolve_user
from . import service as svc
from .schemas import (
    BackupResponse,
    ConversationCreate,
    ConversationDetailResponse,
    ConversationResponse,
    ConversationUpdate,
    MessageCreate,
    MessageResponse,
)

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post(
    "/conversations",
    response_model=ConversationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="创建会话",
    description=(
        "## 用途\n\n"
        "登录用户创建一条新会话, 后端生成 UUID id. 跟 ChatGPT/Claude 一致, "
        "title 不传默认 '新对话' (前端可立即 PATCH 重命名).\n\n"
        "## 鉴权\n\n"
        "`resolve_user` 守卫, 必须登录.\n\n"
        "## 行为\n\n"
        "audit `chat.conv.create` (target_id 设为 '<new>', after 填 title). "
        "返 `ConversationResponse` 含 id/title/message_count/created_at/updated_at. "
        "空 body / 缺 title → 默认 '新对话'."
    ),
    responses={
        201: {"description": "会话创建成功, 返 ConversationResponse"},
        401: {"description": "未登录 / token 无效"},
        422: {"description": "Pydantic 校验失败 (title 越界)"},
    },
)
@audited("chat.conv.create", target_type="conversation")
async def create_conversation(
    request: Request,
    body: ConversationCreate | None = None,
    current_user: CurrentUser = Depends(resolve_user),
):
    """创建新 conv, title 默认 '新对话'."""
    title = body.title if body and body.title else "新对话"
    request.state.audit_ctx.set(target_id="<new>", after={"title": title})
    return svc.create_conversation(current_user.id, title)


@router.get(
    "/conversations",
    response_model=list[ConversationResponse],
    summary="会话列表",
    description=(
        "## 用途\n\n"
        "登录用户的所有活跃会话 (排除软删), 按 updated_at DESC 排, 分页 20/页.\n\n"
        "## 鉴权\n\n"
        "`resolve_user` 守卫, 必须登录. 跨用户隔离: 仅返当前 user 自己的.\n\n"
        "## 行为\n\n"
        "查询走 partial index `idx_conversations_user_updated_partial` "
        "(user_id, updated_at DESC) WHERE deleted_at IS NULL. "
        "支持游标分页: `?limit=20&cursor_before=2026-06-24T12:00:00&cursor_id=abc-123`.\n\n"
        "首次请求不传 cursor_*, 取最新 N 条. 下一页传上一页最后一条的 updated_at + id."
    ),
    responses={
        200: {"description": "返会话列表 (空时返 `[]`)"},
        401: {"description": "未登录 / token 无效"},
        422: {"description": "Pydantic 校验失败 (limit/cursor 格式)"},
    },
)
async def list_conversations(
    limit: int = Query(20, ge=1, le=100, description="分页大小, 1-100"),
    cursor_before: str | None = Query(None, description="游标时间 (上一页最后一条的 updated_at, ISO8601)"),
    cursor_id: str | None = Query(None, description="游标 ID (上一页最后一条的 id, 配合 cursor_before 做 tiebreaker)"),
    current_user: CurrentUser = Depends(resolve_user),
):
    """按 updated_at DESC, id DESC 游标分页列表 (排除软删)."""
    cursor: dict[str, Any] | None = None
    if cursor_before and cursor_id:
        cursor = {"updated_at": datetime.fromisoformat(cursor_before), "id": cursor_id}
    return svc.list_conversations(current_user.id, limit, cursor)


@router.get(
    "/conversations/{conv_id}",
    response_model=ConversationDetailResponse,
    summary="会话详情 (含消息)",
    description=(
        "## 用途\n\n"
        "单条会话的元数据 + 全部消息 (按 created_at ASC 排). 适合初次进入会话时拉全量.\n\n"
        "## 鉴权\n\n"
        "`resolve_user` 守卫. 越权 / 不存在 / 已软删 → 统一 404 (防 ID 探测).\n\n"
        "## 行为\n\n"
        "service 一次拉 conv + messages (N+1 防御, 跟 list_messages 端点配合做无限滚动)."
    ),
    responses={
        200: {"description": "返 ConversationDetailResponse (含 messages[])"},
        401: {"description": "未登录 / token 无效"},
        404: {"description": "conv 不存在 / 越权 / 已软删 (统一 404 防 ID 探测)"},
    },
)
async def get_conversation(
    conv_id: str,
    current_user: CurrentUser = Depends(resolve_user),
):
    """详情 + 消息列表. 越权/不存在/软删 返 404."""
    result = svc.get_conversation(current_user.id, conv_id)
    if result is None:
        raise HTTPException(status_code=404, detail="conversation not found")
    return result


@router.patch(
    "/conversations/{conv_id}",
    response_model=ConversationResponse,
    summary="重命名会话",
    description=(
        "## 用途\n\n"
        "修改会话 title. 跟 ChatGPT/Claude 一致, LWW (last write wins) 跨设备.\n\n"
        "## 鉴权\n\n"
        "`resolve_user` 守卫. 越权 / 不存在 / 已软删 → 404.\n\n"
        "## 行为\n\n"
        "audit `chat.conv.rename` (target_id=conv_id, after 填新 title). "
        "updated_at = NOW()."
    ),
    responses={
        200: {"description": "重命名成功, 返 ConversationResponse"},
        401: {"description": "未登录 / token 无效"},
        404: {"description": "conv 不存在 / 越权 / 已软删"},
        422: {"description": "Pydantic 校验失败 (title 长度 1-200)"},
    },
)
@audited("chat.conv.rename", target_type="conversation")
async def update_conversation(
    conv_id: str,
    body: ConversationUpdate,
    request: Request,
    current_user: CurrentUser = Depends(resolve_user),
):
    """重命名 title. 越权/不存在 返 404."""
    request.state.audit_ctx.set(target_id=conv_id, after={"title": body.title})
    result = svc.update_conversation(current_user.id, conv_id, body.title)
    if result is None:
        raise HTTPException(status_code=404, detail="conversation not found")
    return result


@router.delete(
    "/conversations/{conv_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="软删会话",
    description=(
        "## 用途\n\n"
        "软删 (deleted_at = NOW()), UI 立即隐藏. 30d 后 cron `chat_hard_delete_30d` "
        "真删 (GDPR right to erasure).\n\n"
        "## 鉴权\n\n"
        "`resolve_user` 守卫. 越权 / 不存在 / 已软删 → 404 (防 ID 探测).\n\n"
        "## 行为\n\n"
        "audit `chat.conv.delete` (target_id=conv_id, 不填 after). "
        "返 204 No Content."
    ),
    responses={
        204: {"description": "软删成功 (cron 30d 后真删)"},
        401: {"description": "未登录 / token 无效"},
        404: {"description": "conv 不存在 / 越权 / 已软删 (统一 404 防 ID 探测)"},
    },
)
@audited("chat.conv.delete", target_type="conversation")
async def delete_conversation(
    conv_id: str,
    request: Request,
    current_user: CurrentUser = Depends(resolve_user),
):
    """软删 (deleted_at = NOW()), cron 30d 后 hard-delete."""
    request.state.audit_ctx.set(target_id=conv_id)
    if not svc.soft_delete_conversation(current_user.id, conv_id):
        raise HTTPException(status_code=404, detail="conversation not found")
    logger.info("chat.soft_delete 会话已软删除 conv_id={} user_id={}", conv_id, current_user.id)
    # 204 No Content: router 自动空 body
    return None


@router.post(
    "/conversations/{conv_id}/messages",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
    summary="追加消息",
    description=(
        "## 用途\n\n"
        "登录用户在指定 conv 追加一条消息. role=user 会让 message_count += 1; "
        "role=assistant/system 仅刷新 updated_at.\n\n"
        "## 鉴权\n\n"
        "`resolve_user` 守卫. 越权 / conv 不存在 / 已软删 → 404 (防 ID 探测).\n\n"
        "## 行为\n\n"
        "audit `chat.msg.append` (target_id=conv_id, after 填 {role}). "
        "service 单事务: SELECT conv FOR UPDATE → INSERT message → UPDATE conv."
    ),
    responses={
        201: {"description": "返 MessageResponse"},
        401: {"description": "未登录"},
        404: {"description": "conv 不存在 / 越权 / 已软删"},
        422: {"description": "Pydantic 校验失败 (role 非法 / content 越界)"},
    },
)
@audited("chat.msg.append", target_type="message")
async def append_message(
    conv_id: str,
    body: MessageCreate,
    request: Request,
    current_user: CurrentUser = Depends(resolve_user),
):
    """追加消息. user 累加 count, 其他只刷 updated_at. 越权/不存在 返 404."""
    request.state.audit_ctx.set(target_id=conv_id, after={"role": body.role})
    result = svc.append_message(current_user.id, conv_id, body.role, body.content, body.meta)
    if result is None:
        raise HTTPException(status_code=404, detail="conversation not found")
    return result


@router.get(
    "/conversations/{conv_id}/messages",
    response_model=list[MessageResponse],
    summary="单 conv 消息分页",
    description=(
        "## 用途\n\n"
        "单条会话的消息分页 (50/页, 无限滚动用). 比 GET /conversations/{id} 轻量, "
        "适合已加载过详情后只拉新消息.\n\n"
        "## 鉴权\n\n"
        "`resolve_user` 守卫. 越权 / 不存在 / 已软删 → 404.\n\n"
        "## 行为\n\n"
        "service 校验 conv 归属 + 拉 messages (分页). "
        "支持 `?limit=50&offset=0`."
    ),
    responses={
        200: {"description": "返消息列表 (空时返 `[]`)"},
        401: {"description": "未登录 / token 无效"},
        404: {"description": "conv 不存在 / 越权 / 已软删"},
        422: {"description": "Pydantic 校验失败 (limit/offset 越界)"},
    },
)
async def list_messages(
    conv_id: str,
    limit: int = Query(50, ge=1, le=200, description="分页大小, 1-200"),
    offset: int = Query(0, ge=0, description="分页偏移"),
    current_user: CurrentUser = Depends(resolve_user),
):
    """单 conv 消息列表 (分页 50/页, 无限滚动用). 越权/不存在 返 404."""
    result = svc.list_messages(current_user.id, conv_id, limit, offset)
    if result is None:
        raise HTTPException(status_code=404, detail="conversation not found")
    return result


@router.get(
    "/backup",
    response_model=BackupResponse,
    summary="全量导出 JSON (GDPR)",
    description=(
        "## 用途\n\n"
        "把当前用户所有活跃会话 + 全部消息导出成 JSON, 供用户本地备份 / GDPR "
        "'right to data portability' 用. 排除软删的 conv.\n\n"
        "## 鉴权\n\n"
        "`resolve_user` 守卫, 必须登录.\n\n"
        "## 行为\n\n"
        "service 一次拉 convs + msgs (按 conv 聚合), 返 `BackupResponse` "
        "{exported_at, conversations[]}."
    ),
    responses={
        200: {"description": "返 BackupResponse (exported_at + conversations[]+messages[])"},
        401: {"description": "未登录 / token 无效"},
    },
)
async def backup_all(
    current_user: CurrentUser = Depends(resolve_user),
):
    """全量导出 JSON (用户手动备份 / GDPR 导出)."""
    return svc.get_full_backup(current_user.id)
