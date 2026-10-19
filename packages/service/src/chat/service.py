"""ConversationService: 纯 DB CRUD + 软删 (2026-06-19 chat spec §5)

不带 HTTP 关注 (无 FastAPI Request / Depends). router 调用本 service.
所有查询必带 `WHERE deleted_at IS NULL`, 软删 30d 后由 hard_delete_old_soft_deleted cron 清理.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from loguru import logger
from sqlalchemy import text

from ..storage.session import session_scope


def _parse_meta(meta: Any) -> dict | None:
    """messages.meta 读出兜底 (向后兼容).

    历史背景 (2026-06-24): SA 2.0 + psycopg3 + sa.JSON() 读 PG json 列可能给 dict 或 str.
    2026-06-26 migration 已把列迁到 JSONB, psycopg3 一致返 dict.

    本函数保留作向后兼容:
    - 历史脏数据 (迁移前残留为 str 的边角 case)
    - 单测 mock 给 dict / str 都跑通
    - 防回归 (未来某天再退回 json 类型时不立刻炸)
    """
    if meta is None:
        return None
    if isinstance(meta, dict):
        return meta
    if isinstance(meta, str):
        try:
            return json.loads(meta)
        except json.JSONDecodeError:
            logger.warning("meta JSON 解析失败, 当 None 处理")
            return None
    return None


def create_conversation(user_id: int, title: str = "新对话") -> dict[str, Any]:
    """创建 conv, 返 dict 含 id/title/message_count/created_at/updated_at.

    Args:
        user_id: 所属 user.id
        title: 会话标题, 路由层默认 '新对话'

    Returns:
        {id, title, message_count, created_at, updated_at}

    Note:
        id 用 uuid4() 服务端生成 (跟 PG 列 String(36) 对齐, 跟前端 crypto.randomUUID() 兼容).
    """
    conv_id = str(uuid.uuid4())
    with session_scope() as s:
        row = s.execute(
            text("""
                INSERT INTO conversations (id, user_id, title, message_count, created_at, updated_at)
                VALUES (:id, :uid, :title, 0, NOW(), NOW())
                RETURNING id, title, message_count, created_at, updated_at
            """),
            {"id": conv_id, "uid": user_id, "title": title},
        ).first()
    # INSERT...RETURNING 必有一行, 这里只为 pyright narrow 类型
    assert row is not None
    return {
        "id": str(row.id),
        "title": row.title,
        "message_count": row.message_count,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


def list_conversations(
    user_id: int,
    limit: int = 20,
    cursor_before: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """按 updated_at DESC, id DESC 游标分页列表 (排除软删).

    cursor_before: {"updated_at": datetime, "id": str} — 上一页最后一条, 用于构造 WHERE 条件.
        None 表示第一页.

    Returns:
        [{id, title, message_count, created_at, updated_at}, ...]
    """
    with session_scope() as s:
        if cursor_before:
            rows = s.execute(
                text("""
                    SELECT id, title, message_count, created_at, updated_at
                    FROM conversations
                    WHERE user_id = :uid AND deleted_at IS NULL
                      AND (updated_at < :cursor_updated_at
                           OR (updated_at = :cursor_updated_at AND id < :cursor_id))
                    ORDER BY updated_at DESC, id DESC
                    LIMIT :limit
                """),
                {
                    "uid": user_id,
                    "limit": limit,
                    "cursor_updated_at": cursor_before["updated_at"],
                    "cursor_id": cursor_before["id"],
                },
            ).fetchall()
        else:
            rows = s.execute(
                text("""
                    SELECT id, title, message_count, created_at, updated_at
                    FROM conversations
                    WHERE user_id = :uid AND deleted_at IS NULL
                    ORDER BY updated_at DESC, id DESC
                    LIMIT :limit
                """),
                {"uid": user_id, "limit": limit},
            ).fetchall()
    return [
        {
            "id": str(r.id),
            "title": r.title,
            "message_count": r.message_count,
            "created_at": r.created_at,
            "updated_at": r.updated_at,
        }
        for r in rows
    ]


def get_conversation(user_id: int, conv_id: str) -> dict[str, Any] | None:
    """详情 + 消息列表. 返 None 当不存在 / 软删 / 越权 (router 翻译 404)."""
    with session_scope() as s:
        conv = s.execute(
            text("""
                SELECT id, title, message_count, created_at, updated_at
                FROM conversations
                WHERE id = :id AND user_id = :uid AND deleted_at IS NULL
            """),
            {"id": conv_id, "uid": user_id},
        ).first()
        if not conv:
            return None
        msgs = s.execute(
            text("""
                SELECT id, role, content, meta, created_at
                FROM messages
                WHERE conversation_id = :cid AND deleted_at IS NULL
                ORDER BY created_at ASC
            """),
            {"cid": conv_id},
        ).fetchall()
    return {
        "id": str(conv.id),
        "title": conv.title,
        "message_count": conv.message_count,
        "created_at": conv.created_at,
        "updated_at": conv.updated_at,
        "messages": [
            {
                "id": str(m.id),
                "role": m.role,
                "content": m.content,
                # (2026-06-24) Bug fix: 见 _parse_meta — SA 2.0 + psycopg3 + sa.JSON() 读出可能是 dict 不是 str.
                "meta": _parse_meta(m.meta),
                "created_at": m.created_at,
            }
            for m in msgs
        ],
    }


def update_conversation(user_id: int, conv_id: str, title: str) -> dict[str, Any] | None:
    """重命名. 返 None 当越权 / 不存在 / 已软删."""
    with session_scope() as s:
        row = s.execute(
            text("""
                UPDATE conversations
                SET title = :title, updated_at = NOW()
                WHERE id = :id AND user_id = :uid AND deleted_at IS NULL
                RETURNING id, title, message_count, created_at, updated_at
            """),
            {"id": conv_id, "uid": user_id, "title": title},
        ).first()
    if not row:
        return None
    return {
        "id": str(row.id),
        "title": row.title,
        "message_count": row.message_count,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


def soft_delete_conversation(user_id: int, conv_id: str) -> bool:
    """软删 (deleted_at = NOW()). 返 True 当成功删除, False 当不存在 / 越权 / 已软删.

    30d 后由 hard_delete_old_soft_deleted cron 真删 (GDPR right to erasure).
    """
    with session_scope() as s:
        row = s.execute(
            text("""
                UPDATE conversations
                SET deleted_at = NOW()
                WHERE id = :id AND user_id = :uid AND deleted_at IS NULL
                RETURNING id
            """),
            {"id": conv_id, "uid": user_id},
        ).first()
    return row is not None


def list_messages(user_id: int, conv_id: str, limit: int = 50, offset: int = 0) -> list[dict[str, Any]] | None:
    """单 conv 消息列表 (分页 50/页, 无限滚动用). 返 None 当越权 / conv 不存在 / 已软删."""
    with session_scope() as s:
        conv = s.execute(
            text("""
                SELECT 1 FROM conversations
                WHERE id = :id AND user_id = :uid AND deleted_at IS NULL
            """),
            {"id": conv_id, "uid": user_id},
        ).first()
        if not conv:
            return None
        msgs = s.execute(
            text("""
                SELECT id, role, content, meta, created_at
                FROM messages
                WHERE conversation_id = :cid AND deleted_at IS NULL
                ORDER BY created_at ASC
                LIMIT :limit OFFSET :offset
            """),
            {"cid": conv_id, "limit": limit, "offset": offset},
        ).fetchall()
    return [
        {
            "id": str(m.id),
            "role": m.role,
            "content": m.content,
            "meta": _parse_meta(m.meta),
            "created_at": m.created_at,
        }
        for m in msgs
    ]


def get_full_backup(user_id: int) -> dict[str, Any]:
    """全量导出 JSON (用户手动备份 / GDPR 导出). 排除软删."""
    with session_scope() as s:
        convs = s.execute(
            text("""
                SELECT id, title, message_count, created_at, updated_at
                FROM conversations
                WHERE user_id = :uid AND deleted_at IS NULL
                ORDER BY created_at ASC
            """),
            {"uid": user_id},
        ).fetchall()
        msgs = s.execute(
            text("""
                SELECT m.conversation_id, m.role, m.content, m.meta, m.created_at
                FROM messages m
                JOIN conversations c ON c.id = m.conversation_id
                WHERE c.user_id = :uid AND m.deleted_at IS NULL AND c.deleted_at IS NULL
                ORDER BY m.created_at ASC
            """),
            {"uid": user_id},
        ).fetchall()
    msgs_by_conv: dict[str, list[dict[str, Any]]] = {}
    for m in msgs:
        msgs_by_conv.setdefault(str(m.conversation_id), []).append(
            {
                "role": m.role,
                "content": m.content,
                "meta": _parse_meta(m.meta),
                "created_at": m.created_at.isoformat(),
            }
        )
    return {
        "exported_at": datetime.now(UTC).isoformat(),
        "conversations": [
            {
                "id": str(c.id),
                "title": c.title,
                "message_count": c.message_count,
                "created_at": c.created_at.isoformat(),
                "updated_at": c.updated_at.isoformat(),
                "messages": msgs_by_conv.get(str(c.id), []),
            }
            for c in convs
        ],
    }


def hard_delete_old_soft_deleted(days: int = 30) -> dict[str, int]:
    """30d 软删的 conv + 关联 msgs hard-delete (GDPR cron, spec §8).

    先删 messages (无 FK 反向) 再删 conversations, 跟生产 ON DELETE CASCADE 兼容.
    """
    cutoff = datetime.now(UTC) - timedelta(days=days)
    with session_scope() as s:
        # .rowcount 是 SQLAlchemy CursorResult 属性, Result 泛型擦除后 pyright 看不到
        msg_count = s.execute(
            text("""
                DELETE FROM messages
                WHERE deleted_at IS NOT NULL AND deleted_at < :cutoff
            """),
            {"cutoff": cutoff},
        ).rowcount  # type: ignore[attr-defined]
        conv_count = s.execute(
            text("""
                DELETE FROM conversations
                WHERE deleted_at IS NOT NULL AND deleted_at < :cutoff
            """),
            {"cutoff": cutoff},
        ).rowcount  # type: ignore[attr-defined]
    logger.info(
        "chat 硬删除完成: {} 个会话, {} 条消息 (超过 {} 天)",
        conv_count,
        msg_count,
        days,
    )
    return {"conversations": conv_count, "messages": msg_count}


def append_message(
    user_id: int,
    conv_id: str,
    role: str,
    content: str,
    meta: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """追加一条消息到指定 conv. 返 message dict; None 当 conv 不存在/越权/软删.

    单事务: SELECT conv (FOR UPDATE) → INSERT message → UPDATE conv 计数+时间.
    - role='user' 累加 message_count + 刷新 updated_at
    - role='assistant'/'system' 仅刷新 updated_at

    Args:
        user_id: 当前登录用户
        conv_id: 目标会话 ID
        role: 'user' / 'assistant' / 'system' (路由层 Literal 校验, 这里假定合法)
        content: 消息文本
        meta: 可选 JSON (finish_reason / error_code / citations 等), 透传不强 schema

    Returns:
        {id, role, content, meta, created_at} 或 None (conv 不存在/越权/软删)
    """
    # FOR UPDATE 防并发 append 同 conv 时 message_count 串
    meta_json = json.dumps(meta) if meta is not None else None
    with session_scope() as s:
        # 1. SELECT conv (FOR UPDATE 防并发)
        conv = s.execute(
            text("""
                SELECT id FROM conversations
                WHERE id = :cid AND user_id = :uid AND deleted_at IS NULL
                FOR UPDATE
            """),
            {"cid": conv_id, "uid": user_id},
        ).first()
        if not conv:
            return None
        # 2. INSERT message
        # JSONB 写法跟 buyer_profile/service.py:144 注释一致 (CAST 形式避免 ::jsonb 歧义)
        msg = s.execute(
            text("""
                INSERT INTO messages (conversation_id, role, content, meta, created_at)
                VALUES (:cid, :role, :content, CAST(:meta AS jsonb), NOW())
                RETURNING id, role, content, meta, created_at
            """),
            {"cid": conv_id, "role": role, "content": content, "meta": meta_json},
        ).first()
        assert msg is not None  # INSERT...RETURNING 必有一行
        # 3. UPDATE conv: user 累加 count, 其他只刷 updated_at
        if role == "user":
            s.execute(
                text("""
                    UPDATE conversations
                    SET message_count = message_count + 1, updated_at = NOW()
                    WHERE id = :cid
                """),
                {"cid": conv_id},
            )
        else:
            s.execute(
                text("UPDATE conversations SET updated_at = NOW() WHERE id = :cid"),
                {"cid": conv_id},
            )
    return {
        "id": str(msg.id),
        "role": msg.role,
        "content": msg.content,
        "meta": _parse_meta(msg.meta),
        "created_at": msg.created_at,
    }
