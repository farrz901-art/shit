# RAG 聊天历史存储 Design Spec (2026-06-19)

> **For agentic workers:** 后续 plan / 实施按本 spec 落地, 不偏离. 改 spec 需新 brainstorm + commit.

**Goal**: 把当前全用户都用 localStorage 改成 "anon → IDB, 登录 → 服务端 PG". 登录后 IDB 自动清, 跟 ChatGPT/Claude/Gemini/Poe/Perplexity 5 标杆 100% 一致 (A 丢弃策略). 软删 30d 兜底 GDPR.

**Architecture**: 客户端 `lib/chat/api.ts` facade 包 7 个 REST 端点. 业务侧 `isAccount` 二元分支: `false` → IndexedDB via Dexie, `true` → REST API. 匿名模式本地 SSE 直调 Dify chatflow, 登录后通过后端转发 (token 鉴权 + 限流 + audit). 迁移触发点: 登录成功跳转回 /chat 时检测 `isAccount=true` + IDB 有数据, 弹 toast 让用户下载备份或确认清除.

**Tech Stack**: Dexie.js 4.x (~12KB gzipped, IndexedDB wrapper), TanStack Query 5.x (60s staleTime + window focus refetch), shadcn/ui Sonner toast, next-intl 4.x (zh/en 2 语), 跟现有 ChatShell + ConversationList + storage.ts 兼容.

---

## 1. 用户决策记录 (2026-06-19 brainstorming)

| 决策点 | 用户选择 | 备注 |
|---|---|---|
| 迁移策略 | A 丢弃 (登录后清 IDB) | 跟 5 标杆 100% 一致 |
| 客户端存储 | IndexedDB + Dexie | 容量无限, 替换 localStorage |
| 提示形式 | Toast (轻, 不拦截) | 弹 "N 段聊天将清除" + 下载/知道 |
| 登录后首次进 /chat | 空状态 + 开始新对话 | 跟 ChatGPT 模式一致 |
| 已登录用户管理 | 服务端完整列表 (重命名/删除/搜索) | 主流做法 |
| 删除策略 | 软删 30d (cron hard-delete) | GDPR 合规 |
| 跨设备冲突 | LWW (last write wins) | 简单, 跟 Notion 一致 |
| i18n | zh + en (2 语) | 跟项目 i18n 配置一致 |
| 触发点 | 登录后返回 /chat (明触发) | 显式触发, 用户明确知道 |
| 离线模式 | 不支持 (登录用户必须在线) | 100% 数据一致性 |

**Why**: 用户 2026-06-19 决定让 anon 走 IDB, 登录走数据库. 行业 2026 调研 5 标杆 100% 用 A 丢弃策略, 用户决策跟行业一致, 工程量最小 (1 天核心逻辑 + 4 天 E2E/i18n).

---

## 2. 架构总览

```
┌──────────────────────────────────────────────────────────────┐
│ 浏览器 (Web 端)                                              │
│                                                                │
│ ┌─────────────────────┐    ┌─────────────────────┐              │
│ │ anon 路径            │    │ 已登录路径           │              │
│ │ (isAccount=false)    │    │ (isAccount=true)     │              │
│ │                     │    │                     │              │
│ │ IndexedDB (Dexie)   │    │ TanStack Query      │              │
│ │  ┌──────────────┐   │    │  staleTime=60s      │              │
│ │  │ conversations│   │    │  refetchOnFocus     │              │
│ │  │ messages     │   │    │                     │              │
│ │  └──────────────┘   │    │  IDB 5 min cache    │              │
│ │        ↑            │    │  (read-through)     │              │
│ │        │ 直调        │    │        ↑            │              │
│ │        ↓            │    │        │            │              │
│ │ ┌──────────────┐   │    │        ↓            │              │
│ │ │Dify Chatflow │   │    │ ┌──────────────┐   │              │
│ │ │(SSE 直接)    │   │    │ │ REST API     │   │              │
│ │ └──────────────┘   │    │ │/api/chat/*   │   │              │
│ └─────────────────────┘    │ └──────┬───────┘   │              │
│                             └────────┼──────────┘              │
│                                      │                         │
└──────────────────────────────────────┼──────────────────────────┘
                                       ↓
┌──────────────────────────────────────────────────────────────┐
│ FastAPI 后端                                                  │
│                                                                │
│  chat_router (新增, 已有 chat_share_router 保留)               │
│  POST   /api/chat/conversations            → 创建              │
│  GET    /api/chat/conversations            → 列表 (分页 20)    │
│  GET    /api/chat/conversations/{id}       → 详情              │
│  PATCH  /api/chat/conversations/{id}       → 重命名            │
│  DELETE /api/chat/conversations/{id}       → 软删 (30d purge)  │
│  GET    /api/chat/conversations/{id}/msgs  → 消息列表           │
│  POST   /api/chat/conversations/{id}/msgs  → 新消息 (Dify 转发)│
│  GET    /api/chat/backup                  → JSON 全量导出      │
│                                                                │
│  cron (scheduler/deletion.py 加):                                │
│  每天 03:00 → DELETE FROM conversations                          │
│                WHERE deleted_at < NOW() - INTERVAL '30 days'    │
│                                                                │
│  Redis (复用 2026-06-18 spec):                                  │
│  - 端点受 Token cache 6h (auth)                                 │
│  - GET /conversations 列表走 Redis 60s cache (per user)         │
│  - POST /messages 走 RateLimiter 5/15min (per IP)              │
└──────────────────────────────────────────────────────────────┘
                            ↓
┌──────────────────────────────────────────────────────────────┐
│ Postgres                                                       │
│  conversations (已有, 增 deleted_at 列)                         │
│    id, user_id, title, message_count, created_at,             │
│    updated_at, deleted_at                                       │
│  messages (已有, 增 deleted_at 列)                             │
│    id, conv_id, role, content, meta JSONB, created_at,        │
│    deleted_at                                                  │
│  chat_shares (已有, 公开 share 机制保留)                        │
│                                                                │
│  indexes (增量):                                                │
│    idx_conversations_user_updated                               │
│      ON conversations (user_id, updated_at DESC)               │
│      WHERE deleted_at IS NULL                                   │
│    idx_messages_conv_created                                    │
│      ON messages (conv_id, created_at)                          │
│      WHERE deleted_at IS NULL                                   │
└──────────────────────────────────────────────────────────────┘
```

**5 大设计原则** (跟项目对齐):
1. **Facade 模式**: 跟 logging / redis_client 一致, 客户端 `lib/chat/api.ts` 包 REST
2. **二元分支清晰**: `isAccount` 决定走 IDB 还是 REST, ChatShell 内聚分支
3. **永不阻塞 Dify 流**: SSE 用 `parseSseStream` (项目已有 lib/chat/sse.ts)
4. **软删 + 30d cron**: 跟 ChatGPT/Claude 一致, GDPR 合规
5. **i18n 全覆盖**: 7 个端点消息 + 3 个 toast + ConversationList 操作, 全部 zh/en

---

## 3. 文件结构 (新增 + 改)

### 新建

| 文件 | 行数 | 用途 |
|---|---|---|
| `packages/web/lib/chat/db.ts` | ~80 | Dexie schema: `conversations` + `messages` 表, version 1 |
| `packages/web/lib/chat/api.ts` | ~150 | REST API facade: 7 端点, TanStack Query hooks |
| `packages/web/lib/chat/migration.ts` | ~60 | `clearLocalChat()` + 检测 anon → login 切换 |
| `packages/web/components/chat/login-migration-dialog.tsx` | ~80 | shadcn Sonner toast 包装, "本地 N 段聊天将清除" + 下载/知道 |
| `packages/web/lib/chat/api.test.ts` | ~150 | 8 测试: 7 端点 mock + error handle (vitest 模式 1) |
| `packages/web/lib/chat/db.test.ts` | ~100 | 5 测试: Dexie CRUD + clear (vitest + fake-indexeddb) |
| `packages/web/lib/chat/migration.test.ts` | ~50 | 3 测试: 检测 IDB 非空 + 清除 (vitest) |
| `packages/web/e2e/chat-history.spec.ts` | ~150 | E2E: anon 聊 → 登录 → toast → 清空 → 拉服务端 (Playwright) |
| `packages/web/messages/en.json` (改) | +20 | 增 7 端点消息 + 3 toast 文案 |
| `packages/web/messages/zh.json` (改) | +20 | 同上 |
| `packages/service/src/chat/router.py` | ~200 | chat_router 7 端点 (FastAPI) |
| `packages/service/src/chat/service.py` | ~150 | ConversationService (CRUD + soft delete) |
| `packages/service/src/chat/schemas.py` | ~80 | Pydantic Conversation / Message / Backup |
| `packages/service/src/storage/migrations/versions/20260619_000000_chat_soft_delete.py` | ~40 | alembic: 加 deleted_at 列 + 索引 |
| `packages/service/tests/chat/test_router.py` | ~200 | 12 测试: 7 端点 + 鉴权 + 软删 (db_session 模式 2) |
| `packages/service/tests/chat/test_service.py` | ~100 | 6 测试: CRUD + 软删 + cron (db_session) |
| `docs/superpowers/specs/2026-06-19-chat-history-storage-design.md` | 本文件 | spec |
| `docs/superpowers/plans/2026-06-19-chat-history-storage.md` | 待写 | plan |
| `docs/superpowers/handoffs/2026-06-19-chat-history-storage.md` | 待写 | handoff |
| `docs/operations/chat-storage.md` | ~120 | 运维查询 (PG 监控 / cron / 备份) |

### 改

| 文件 | 改动 |
|---|---|
| `packages/web/lib/chat/storage.ts` | 改为 IndexedDB via Dexie (替换 localStorage 逻辑) |
| `packages/web/components/chat/ChatShell.tsx` | 加 `isAccount` 分支 + useConversations (TanStack Query) + 登录迁移 toast |
| `packages/web/components/chat/ConversationList.tsx` | 列表数据源: IDB (anon) / REST (login), 重命名/删除走对应路径 |
| `packages/web/components/chat/MessageList.tsx` | 消息数据源同上 |
| `packages/web/components/chat/Composer.tsx` | 发送消息: IDB 直写 (anon) / POST REST (login) |
| `packages/web/app/[locale]/chat/page.tsx` | 已有 isAccount 传参, 不变 |
| `packages/web/lib/api/config.ts` | 增 `apiFetch` 跟 TanStack Query 集成 (可能需要 react-query 包装) |
| `packages/web/package.json` | 加 `dexie@^4`, `@tanstack/react-query@^5` |
| `packages/web/CLAUDE.md` | 增补 "聊天历史存储约定" 章节 |
| `packages/service/CLAUDE.md` | 增补 "chat_router" 章节 |
| `packages/service/src/api/routes.py` | include chat_router |
| `packages/service/src/scheduler/deletion.py` | 加 chat_hard_delete job (03:00 daily) |

**注**: 实施前 implementer 必须 `grep -rn "storage\.ts\|STORAGE_KEY\|MESSAGES_KEY\|isAccount" packages/web/` 验证现有用法.

---

## 4. Dexie Schema (packages/web/lib/chat/db.ts)

```typescript
// IndexedDB schema 替原 localStorage (2026-06-19 chat spec §4)

import Dexie, { type Table } from "dexie";
import type { Conversation, Message } from "./types";

export interface LocalConversation extends Conversation {
  // 跟 Conversation 相同, 但加 owner 标记 (防止 anon/login 切换串)
  owner: "anon" | "imported";
  // 软删 (本地, 跟服务端对齐)
  deletedAt?: number;
}

export interface LocalMessage extends Message {
  // 跟 Message 相同
  owner: "anon" | "imported";
}

export class ChatDB extends Dexie {
  conversations!: Table<LocalConversation, string>;
  messages!: Table<LocalMessage, string>;

  constructor() {
    super("rag-chat");
    this.version(1).stores({
      // primary key + 索引
      // convId 跟 Message.conversationId 字段名一致 (跟 lib/chat/types.ts Message schema 对齐)
      conversations: "id, owner, updatedAt, deletedAt",
      messages: "id, conversationId, createdAt, owner, [conversationId+createdAt]",
    });
  }
}

export const db = new ChatDB();

// ── 跟旧 storage.ts 兼容的 facade ──
// 字段名 conversationId 跟现有 types.Message.conversationId 对齐
// (旧 storage.ts:loadMessages(convId) 参数叫 convId, 实施时改成 conversationId)

export async function loadConversations(): Promise<LocalConversation[]> {
  return db.conversations.where("owner").equals("anon").and(c => !c.deletedAt).toArray();
}

export async function saveConversations(items: LocalConversation[]): Promise<void> {
  await db.conversations.bulkPut(items.map(c => ({ ...c, owner: "anon" })));
}

export async function deleteConversation(id: string): Promise<void> {
  await db.transaction("rw", db.conversations, db.messages, async () => {
    await db.conversations.delete(id);
    await db.messages.where("conversationId").equals(id).delete();
  });
}

export async function loadMessages(convId: string): Promise<LocalMessage[]> {
  return db.messages
    .where("[conversationId+createdAt]")
    .between([convId, 0], [convId, Number.MAX_SAFE_INTEGER])
    .toArray();
}

export async function saveMessages(convId: string, messages: LocalMessage[]): Promise<void> {
  await db.messages.bulkPut(messages.map(m => ({ ...m, conversationId: convId, owner: "anon" })));
}

export async function clearLocalChat(): Promise<void> {
  // 登录后清 anon 数据 (保留 imported, 留好未来扩展)
  await db.transaction("rw", db.conversations, db.messages, async () => {
    await db.conversations.where("owner").equals("anon").delete();
    await db.messages.where("owner").equals("anon").delete();
  });
}
```

**关键点**:
- `owner: "anon" | "imported"` 字段, 留好未来 C/D 模式扩展 (A 模式目前只用 `anon`)
- 复合索引 `[conversationId+createdAt]` 加速单 conv 按时间排序
- `clearLocalChat()` 只清 anon, 保留 imported (未来模式)

---

## 5. REST API 设计 (packages/service/src/chat/router.py)

```python
"""chat_router: 已登录用户的聊天历史 CRUD (2026-06-19 chat spec §5)

跟 chat_share_router 区分: chat_share 是公开分享 URL, chat_router 是账号私有历史.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import text
from ..core.audit import audited
from ..middleware.auth import CurrentUser, resolve_user
from ..storage.session import session_scope
from .schemas import (
    ConversationCreate, ConversationResponse, ConversationDetailResponse,
    ConversationUpdate, MessageResponse, BackupResponse,
)

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("/conversations", response_model=ConversationResponse)
@audited("chat.conv.create", target_type="conversation")
async def create_conversation(
    request: Request,
    body: ConversationCreate | None = None,
    current_user: CurrentUser = Depends(resolve_user),
):
    """创建新 conv. title 默认 '新对话' (跟 ChatShell 行为一致)."""
    title = body.title if body and body.title else "新对话"
    with session_scope() as s:
        row = s.execute(text("""
            INSERT INTO conversations (user_id, title, message_count, created_at, updated_at)
            VALUES (:uid, :title, 0, NOW(), NOW())
            RETURNING id, title, message_count, created_at, updated_at
        """), {"uid": current_user.id, "title": title}).first()
    return ConversationResponse(
        id=str(row.id), title=row.title, message_count=row.message_count,
        created_at=row.created_at, updated_at=row.updated_at,
    )


@router.get("/conversations", response_model=list[ConversationResponse])
async def list_conversations(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: CurrentUser = Depends(resolve_user),
):
    """按 updated_at DESC 列表. 仅返未软删."""
    with session_scope() as s:
        rows = s.execute(text("""
            SELECT id, title, message_count, created_at, updated_at
            FROM conversations
            WHERE user_id = :uid AND deleted_at IS NULL
            ORDER BY updated_at DESC
            LIMIT :limit OFFSET :offset
        """), {"uid": current_user.id, "limit": limit, "offset": offset}).fetchall()
    return [
        ConversationResponse(
            id=str(r.id), title=r.title, message_count=r.message_count,
            created_at=r.created_at, updated_at=r.updated_at,
        ) for r in rows
    ]


@router.get("/conversations/{conv_id}", response_model=ConversationDetailResponse)
async def get_conversation(
    conv_id: str,
    current_user: CurrentUser = Depends(resolve_user),
):
    """详情 + 消息列表."""
    with session_scope() as s:
        conv = s.execute(text("""
            SELECT id, title, message_count, created_at, updated_at
            FROM conversations
            WHERE id = :id AND user_id = :uid AND deleted_at IS NULL
        """), {"id": conv_id, "uid": current_user.id}).first()
        if not conv:
            raise HTTPException(404, "conversation not found")
        msgs = s.execute(text("""
            SELECT id, role, content, meta, created_at
            FROM messages
            WHERE conversation_id = :cid AND deleted_at IS NULL
            ORDER BY created_at ASC
        """), {"cid": conv_id}).fetchall()
    return ConversationDetailResponse(
        id=str(conv.id), title=conv.title, message_count=conv.message_count,
        created_at=conv.created_at, updated_at=conv.updated_at,
        messages=[
            MessageResponse(
                id=str(m.id), role=m.role, content=m.content,
                meta=json.loads(m.meta) if m.meta else None,
                created_at=m.created_at,
            ) for m in msgs
        ],
    )


@router.patch("/conversations/{conv_id}", response_model=ConversationResponse)
@audited("chat.conv.rename", target_type="conversation")
async def update_conversation(
    conv_id: str,
    body: ConversationUpdate,
    request: Request,
    current_user: CurrentUser = Depends(resolve_user),
):
    """重命名 title."""
    request.state.audit_ctx.set(target_id=conv_id, after={"title": body.title})
    with session_scope() as s:
        row = s.execute(text("""
            UPDATE conversations
            SET title = :title, updated_at = NOW()
            WHERE id = :id AND user_id = :uid AND deleted_at IS NULL
            RETURNING id, title, message_count, created_at, updated_at
        """), {"id": conv_id, "uid": current_user.id, "title": body.title}).first()
    if not row:
        raise HTTPException(404, "conversation not found")
    return ConversationResponse(
        id=str(row.id), title=row.title, message_count=row.message_count,
        created_at=row.created_at, updated_at=row.updated_at,
    )


@router.delete("/conversations/{conv_id}", status_code=204)
@audited("chat.conv.delete", target_type="conversation")
async def delete_conversation(
    conv_id: str,
    request: Request,
    current_user: CurrentUser = Depends(resolve_user),
):
    """软删 (deleted_at=NOW()), cron 30d 后 hard-delete."""
    request.state.audit_ctx.set(target_id=conv_id)
    with session_scope() as s:
        row = s.execute(text("""
            UPDATE conversations
            SET deleted_at = NOW()
            WHERE id = :id AND user_id = :uid AND deleted_at IS NULL
            RETURNING id
        """), {"id": conv_id, "uid": current_user.id}).first()
    if not row:
        raise HTTPException(404, "conversation not found")


@router.get("/conversations/{conv_id}/messages", response_model=list[MessageResponse])
async def list_messages(
    conv_id: str,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: CurrentUser = Depends(resolve_user),
):
    """单 conv 消息列表 (分页 50/页, 无限滚动用)."""
    with session_scope() as s:
        # 鉴权: conv 必须是当前 user 的
        conv = s.execute(text("""
            SELECT 1 FROM conversations
            WHERE id = :id AND user_id = :uid AND deleted_at IS NULL
        """), {"id": conv_id, "uid": current_user.id}).first()
        if not conv:
            raise HTTPException(404, "conversation not found")
        msgs = s.execute(text("""
            SELECT id, role, content, meta, created_at
            FROM messages
            WHERE conversation_id = :cid AND deleted_at IS NULL
            ORDER BY created_at ASC
            LIMIT :limit OFFSET :offset
        """), {"cid": conv_id, "limit": limit, "offset": offset}).fetchall()
    return [
        MessageResponse(
            id=str(m.id), role=m.role, content=m.content,
            meta=json.loads(m.meta) if m.meta else None,
            created_at=m.created_at,
        ) for m in msgs
    ]


@router.get("/backup", response_model=BackupResponse)
async def backup_all(
    current_user: CurrentUser = Depends(resolve_user),
):
    """全量导出 JSON (用户备份/迁移用)."""
    with session_scope() as s:
        convs = s.execute(text("""
            SELECT id, title, message_count, created_at, updated_at
            FROM conversations
            WHERE user_id = :uid AND deleted_at IS NULL
            ORDER BY created_at ASC
        """), {"uid": current_user.id}).fetchall()
        msgs = s.execute(text("""
            SELECT conversation_id, role, content, meta, created_at
            FROM messages m
            JOIN conversations c ON c.id = m.conversation_id
            WHERE c.user_id = :uid AND m.deleted_at IS NULL AND c.deleted_at IS NULL
            ORDER BY m.created_at ASC
        """), {"uid": current_user.id}).fetchall()
    # 拼 JSON
    msgs_by_conv: dict[str, list] = {}
    for m in msgs:
        msgs_by_conv.setdefault(str(m.conversation_id), []).append({
            "role": m.role, "content": m.content, "meta": json.loads(m.meta) if m.meta else None,
            "created_at": m.created_at.isoformat(),
        })
    return BackupResponse(
        exported_at=datetime.now(timezone.utc).isoformat(),
        conversations=[
            {
                "id": str(c.id), "title": c.title,
                "message_count": c.message_count,
                "created_at": c.created_at.isoformat(),
                "updated_at": c.updated_at.isoformat(),
                "messages": msgs_by_conv.get(str(c.id), []),
            } for c in convs
        ],
    )
```

**7 端点 OK 吗？**

---

## 6. 前端 Facade (packages/web/lib/chat/api.ts)

```typescript
// REST API facade 替原 storage.ts 直调 localStorage (2026-06-19 chat spec §6)

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api/config";

// ── Types ──
export interface ServerConversation {
  id: string;
  title: string;
  message_count: number;
  created_at: string;
  updated_at: string;
}

export interface ServerMessage {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  meta?: Record<string, unknown> | null;
  created_at: string;
}

export interface ServerConversationDetail extends ServerConversation {
  messages: ServerMessage[];
}

// ── Query Keys ──
const KEYS = {
  conversations: () => ["chat", "conversations"] as const,
  conversation: (id: string) => ["chat", "conversations", id] as const,
};

// ── Hooks ──

export function useConversations() {
  return useQuery({
    queryKey: KEYS.conversations(),
    queryFn: () => apiFetch<ServerConversation[]>("/api/chat/conversations"),
    staleTime: 60_000,                                // 跟 redis 60s 对齐
    refetchOnWindowFocus: true,
  });
}

export function useConversation(id: string | null) {
  return useQuery({
    queryKey: id ? KEYS.conversation(id) : ["chat", "conversation", "none"],
    queryFn: () => apiFetch<ServerConversationDetail>(`/api/chat/conversations/${id}`),
    enabled: !!id,
    staleTime: 60_000,
  });
}

export function useCreateConversation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (title?: string) =>
      apiFetch<ServerConversation>("/api/chat/conversations", {
        method: "POST",
        body: JSON.stringify({ title }),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: KEYS.conversations() }),
  });
}

export function useRenameConversation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, title }: { id: string; title: string }) =>
      apiFetch<ServerConversation>(`/api/chat/conversations/${id}`, {
        method: "PATCH",
        body: JSON.stringify({ title }),
      }),
    onSuccess: (_, vars) => {
      qc.invalidateQueries({ queryKey: KEYS.conversations() });
      qc.invalidateQueries({ queryKey: KEYS.conversation(vars.id) });
    },
  });
}

export function useDeleteConversation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      apiFetch<void>(`/api/chat/conversations/${id}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: KEYS.conversations() }),
  });
}

export function useBackup() {
  return useMutation({
    mutationFn: () => apiFetch<unknown>("/api/chat/backup"),
  });
}

// ── 备份下载 trigger ──
// ChatShell 在 isAccount=true 时挂 "下载备份" 按钮 (Header 菜单),
// 调 useBackup 后拿 JSON, 浏览器端 createObjectURL + a.click() 下载.
// 不在本 spec 自动触发, 避免误下载跟 UX 噪音.
```

**Facade OK 吗？**

---

## 7. 迁移触发逻辑 (packages/web/lib/chat/migration.ts)

```typescript
// 登录后清 IDB + toast 提示 (2026-06-19 chat spec §7)

import { useEffect } from "react";
import { toast } from "sonner";
import { useTranslations } from "next-intl";
import { db, clearLocalChat } from "./db";

export function useAnonToLoginMigration(isAccount: boolean) {
  const t = useTranslations();

  useEffect(() => {
    if (!isAccount) return;             // 仅登录态触发

    (async () => {
      // 1. 检查 IDB 是否有 anon 数据
      const anonConvs = await db.conversations
        .where("owner")
        .equals("anon")
        .count();

      if (anonConvs === 0) return;      // 干净, 无需迁移

      // 2. 弹 toast
      const promise = new Promise<"download" | "dismiss">((resolve) => {
        toast(t("本地 {count} 段聊天将清除"), {
          description: t("登录后历史会从服务器同步, 本地数据不再保留"),
          action: {
            label: t("下载 JSON 备份"),
            onClick: () => resolve("download"),
          },
          cancel: {
            label: t("知道了"),
            onClick: () => resolve("dismiss"),
          },
          duration: Infinity,           // 不自动消失, 需用户操作
        });
      });

      const result = await promise;
      if (result === "download") {
        // 触发浏览器下载
        await downloadLocalBackup();
      }

      // 3. 清 IDB (无论选啥)
      await clearLocalChat();

      // 4. 提示完成
      toast.success(t("本地聊天已清除"));
    })();
  }, [isAccount, t]);
}


async function downloadLocalBackup(): Promise<void> {
  const convs = await db.conversations.where("owner").equals("anon").toArray();
  const msgs = await db.messages.where("owner").equals("anon").toArray();
  const payload = {
    exported_at: new Date().toISOString(),
    conversations: convs,
    messages_by_conv: msgs.reduce<Record<string, typeof msgs>>((acc, m) => {
      (acc[m.conversationId] ??= []).push(m);
      return acc;
    }, {}),
  };
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `rag-chat-backup-${Date.now()}.json`;
  a.click();
  URL.revokeObjectURL(url);
}
```

**触发逻辑 OK 吗？**

---

## 8. cron hard-delete (packages/service/src/scheduler/deletion.py 增量)

```python
# 在现有 register_deletion_jobs 加 chat_hard_delete (2026-06-19 chat spec §8)

def register_chat_jobs(scheduler):
    @scheduler.scheduled_job("cron", hour=3, minute=0, timezone="Asia/Hong_Kong")
    async def chat_hard_delete():
        """30d 软删的 conv + 关联 messages hard-delete (GDPR)."""
        from sqlalchemy import text
        from src.storage.session import session_scope

        cutoff = datetime.now(timezone.utc) - timedelta(days=30)
        with session_scope() as s:
            # 1. 删 messages
            msg_count = s.execute(text("""
                DELETE FROM messages
                WHERE deleted_at IS NOT NULL AND deleted_at < :cutoff
            """), {"cutoff": cutoff}).rowcount
            # 2. 删 conv
            conv_count = s.execute(text("""
                DELETE FROM conversations
                WHERE deleted_at IS NOT NULL AND deleted_at < :cutoff
            """), {"cutoff": cutoff}).rowcount
        logger.info(
            "chat_hard_delete done deleted {} convs, {} msgs older than 30d",
            conv_count, msg_count,
        )
```

**cron OK 吗？**

---

## 9. i18n 文案 (zh.json + en.json 增量)

```json
// zh.json (增量)
"本地 {count} 段聊天将清除": "本地 {count} 段聊天将清除",
"登录后历史会从服务器同步, 本地数据不再保留": "登录后历史会从服务器同步, 本地数据不再保留",
"下载 JSON 备份": "下载 JSON 备份",
"知道了": "知道了",
"本地聊天已清除": "本地聊天已清除",
"新对话": "新对话",
"重命名": "重命名",
"删除对话": "删除对话",
"确定删除这段对话?": "确定删除这段对话?",

// en.json (增量)
"本地 {count} 段聊天将清除": "{count} local chats will be cleared",
"登录后历史会从服务器同步, 本地数据不再保留": "After login, history syncs from server. Local data will no longer be kept.",
"下载 JSON 备份": "Download JSON backup",
"知道了": "Got it",
"本地聊天已清除": "Local chats cleared",
"新对话": "New chat",
"重命名": "Rename",
"删除对话": "Delete chat",
"确定删除这段对话?": "Confirm delete this chat?",
```

**i18n 文案 OK 吗？**

---

## 10. 测试策略 (CLAUDE.md 4 模式)

| 文件 | 模式 | 覆盖 |
|---|---|---|
| `packages/web/lib/chat/db.test.ts` (5) | 1 vitest + fake-indexeddb | Dexie CRUD / clear / owner filter |
| `packages/web/lib/chat/api.test.ts` (8) | 1 vitest mock apiFetch | 7 hook + error handle |
| `packages/web/lib/chat/migration.test.ts` (3) | 1 vitest | IDB 计数 / clear / backup download |
| `packages/service/tests/chat/test_router.py` (12) | 2 db_session (FastAPI TestClient) | 7 端点 + 鉴权 + 软删 + 不存在的 conv |
| `packages/service/tests/chat/test_service.py` (6) | 2 db_session | CRUD + soft delete + 30d cron SQL |
| `packages/web/e2e/chat-history.spec.ts` (4) | 4 Playwright (E2E) | anon 聊 → 登录 → toast → 清空 → 拉服务端 |

**总测试**: 38 个新增 (CLAUDE.md TDD)

---

## 11. 不在本期范围 (YAGNI 明确)

- ❌ **跨设备 LWW 实时同步** (本期仅 LWW on save, 不做 conflict UI)
- ❌ **服务端全文搜索** (title LIKE 客户端, 后期上 tsvector)
- ❌ **离线模式** (登录用户必须在线)
- ❌ **E2EE 加密** (服务端明文 + TLS, 跟 ChatGPT 一样)
- ❌ **7d grace + 撤销** (软删 30d, 简单)
- ❌ **自动迁移 (B/C/D 模式)** (方案 1 锁定, 留好 `owner` 字段)
- ❌ **多模态消息 (image/audio 文件)** (本期纯文本)
- ❌ **聊天导出为 PDF** (只 JSON)
- ❌ **分享/导出/Import from other AI** (本期不接, 已有 chat_shares)
- ❌ **多设备 conflict 解决 UI** (LWW on save, 后续设备刷新覆盖)

---

## 12. 风险 + 决策记录

| 风险 | 缓解 |
|---|---|
| 用户感知 "聊天没了" 投诉 | Toast 提示 + JSON 备份按钮 (一键下载) |
| Dify chatflow 的 conversation_id 怎么映射 | 已登录用户: 服务端 conv.id 当 Dify conversation_id, 已有 chat_share 机制参考 |
| IndexedDB 5MB 上限 (浏览器 quota) | Dexie 用 IndexedDB (Chrome 通常可到 60% 磁盘), 远大于 localStorage 5MB |
| 软删 30d 后 hard-delete 跟 GDPR "right to erasure" | cron 每天 03:00 跑, 用户删了 30d 后真删, 合规 |
| 多设备 LWW 数据丢失 | 简单接受 (Notion 同款), 文档说明; 后期接 WebSocket 实时同步 |
| TanStack Query 引入新依赖 (~12KB) | 跟未来扩展 (realtime / optimistic update) 兼容 |
| 登录后跨 IDB 跟服务端 ID 不一致 (UUID vs int) | conv_id 全部改 str (服务端 PG bigserial → str(uuid) 或保持 bigint 字符串化, schema 统一) |
| i18n 文案漏改 → MISSING_MESSAGE 报错 | 增 20 行 zh + en, 跟项目 CLAUDE.md i18n sync 流程 |
| 登录后第一次 GET 列表延迟 | Redis 60s cache (2026-06-18 spec 复用) + 客户端 staleTime 60s |
| 已登录用户也用 IDB 作 cache, 写入冲突 | 5 min read-through cache, 写后 invalidate, 极简 |

**决策记录**:
- ✅ 范围: 4 任务 5 天
- ✅ A 丢弃 + IndexedDB + Toast + 空状态 + 服务端完整列表 + 软删 30d + LWW + zh+en + 登录返回 /chat + 不离线

---

## 13. 验收清单

**功能验收**:
- [ ] anon 用户聊天存 IndexedDB (Dexie), 刷新不丢
- [ ] 登录后 IDB 检测到 anon 数据, 弹 toast
- [ ] 用户可下载 JSON 备份
- [ ] 确认后 IDB 清空, 跳转服务端列表
- [ ] 登录用户 7 端点全可用 (CRUD + 重命名 + 软删 + 导出)
- [ ] 软删后 30d cron hard-delete (job 跑通)
- [ ] i18n zh/en 全部覆盖

**质量验收**:
- [ ] 38 测试全绿
- [ ] ruff + pyright + ESLint 0 error
- [ ] 现有 250+ 测试 0 break
- [ ] Playwright E2E 4 场景通过 (anon → login 迁移)

**文档验收**:
- [ ] `docs/operations/chat-storage.md` (PG 监控 + cron 验证)
- [ ] `packages/web/CLAUDE.md` 增补 "聊天历史存储约定"
- [ ] `packages/service/CLAUDE.md` 增补 "chat_router" 章节
- [ ] `docs/superpowers/handoffs/2026-06-19-chat-history-storage.md` (handoff)

**集成验收**:
- [ ] docker compose up + alembic upgrade (加 deleted_at 列 + 索引)
- [ ] 端到端: 浏览器 anon 聊 3 条 → 登录 → toast → 下载 → 清 → 看到空状态
- [ ] 切 zh/en 验证提示文案

---

**Spec OK 吗? 你 review 完确认 → 写 plan → subagent 实施.**
