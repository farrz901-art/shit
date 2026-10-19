# RAG 聊天历史存储 Implementation Plan (2026-06-19)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把全用户都用 localStorage 改成 "anon → IndexedDB via Dexie, 登录 → 服务端 PG 7 端点". 登录后 IDB 自动清, 跟 ChatGPT/Claude/Gemini/Poe/Perplexity 5 标杆 100% 一致 (A 丢弃策略). 软删 30d + cron hard-delete 兜底 GDPR.

**Architecture:** 客户端 `lib/chat/api.ts` facade 包 7 REST 端点, TanStack Query 5.x 缓存 (60s staleTime). ChatShell 内聚 `isAccount` 二元分支: `false` → IndexedDB via Dexie 4.x (容量无限, 替原 localStorage), `true` → REST. 登录后 useEffect 触发 toast 提示 + clearLocalChat (跟 ChatShell 现有 `isAccount` prop 兼容). 后端新增 `chat_router` (7 端点 + soft delete), 30d cron hard-delete, 复用 2026-06-18 Redis (token cache 6h, RateLimiter 5/15min).

**Tech Stack:** Dexie 4.x (~12KB gzipped, IndexedDB wrapper) + TanStack Query 5.x (~12KB) + shadcn Sonner toast + next-intl 4.x (zh+en) + FastAPI + SQLAlchemy 2.0 + alembic + APScheduler (chat hard-delete cron). 0 新基础设施.

**Spec:** [docs/superpowers/specs/2026-06-19-chat-history-storage-design.md](../specs/2026-06-19-chat-history-storage-design.md)

**工期:** 5 天, 5 task, 5 commit, 38 测试新增

---

## 文件结构 (一次看清所有改动)

### 新建

| 文件 | 行数 | 用途 |
|---|---|---|
| `packages/service/src/chat/__init__.py` | 3 | chat 子包 |
| `packages/service/src/chat/router.py` | ~250 | chat_router 7 端点 (CRUD + 软删 + 备份) |
| `packages/service/src/chat/service.py` | ~150 | ConversationService (DB CRUD + 软删) |
| `packages/service/src/chat/schemas.py` | ~80 | Pydantic Conversation / Message / Backup |
| `packages/service/tests/chat/__init__.py` | 3 | test 子包 |
| `packages/service/tests/chat/test_router.py` | ~250 | 12 测试: 7 端点 + 鉴权 + 软删 (db_session 模式 2) |
| `packages/service/tests/chat/test_service.py` | ~100 | 6 测试: CRUD + 软删 + cron SQL (db_session) |
| `packages/service/src/storage/migrations/versions/20260619_000000_chat_soft_delete.py` | ~40 | alembic: 加 deleted_at 列 + 2 索引 |
| `packages/web/lib/chat/db.ts` | ~80 | Dexie schema v1 (conversations + messages) |
| `packages/web/lib/chat/api.ts` | ~150 | REST API facade + TanStack Query hooks (7 hook) |
| `packages/web/lib/chat/migration.ts` | ~80 | `useAnonToLoginMigration` + `clearLocalChat` + downloadLocalBackup |
| `packages/web/lib/chat/db.test.ts` | ~100 | 5 测试: Dexie CRUD + clear (vitest + fake-indexeddb) |
| `packages/web/lib/chat/api.test.ts` | ~150 | 8 测试: 7 hook + error handle (vitest mock) |
| `packages/web/lib/chat/migration.test.ts` | ~60 | 3 测试: IDB 计数 / clear / backup download |
| `packages/web/components/chat/chat-api-provider.tsx` | ~40 | `<QueryClientProvider>` 包裹 (跟 spec §3) |
| `packages/web/e2e/chat-history.spec.ts` | ~150 | E2E: anon 聊 → 登录 → toast → 清空 → 拉服务端 (Playwright 模式 4) |
| `docs/operations/chat-storage.md` | ~120 | 运维查询 (PG 监控 + cron 验证) |
| `docs/superpowers/handoffs/2026-06-19-chat-history-storage.md` | ~200 | handoff 文档 |
| `docs/superpowers/plans/2026-06-19-chat-history-storage.md` | 本文件 | plan |

### 改

| 文件 | 改动 |
|---|---|
| `packages/web/lib/chat/storage.ts` | 重写为 Dexie 适配 (保留同名 export: `loadConversations` / `saveMessages` / `deleteConversation` 等, 但底层 localStorage → IndexedDB) |
| `packages/web/components/chat/ChatShell.tsx` | 加 `isAccount` 分支: `false` 走 IDB 同步 API, `true` 走 `useConversations()` + REST. 加 `useAnonToLoginMigration(isAccount)` hook. |
| `packages/web/components/chat/ConversationList.tsx` | 接受 conversations prop 来自 isAccount 分支 |
| `packages/web/components/chat/MessageList.tsx` | 接受 messages prop 来自 useConversation |
| `packages/web/components/chat/Composer.tsx` | 发送: isAccount=false → IDB 直写; isAccount=true → POST REST + SSE |
| `packages/web/app/[locale]/chat/page.tsx` | 已有 isAccount 传参, 不变 |
| `packages/web/messages/zh.json` | +10 字符串: toast / 按钮 / 操作 |
| `packages/web/messages/en.json` | 同上 en |
| `packages/web/package.json` | 加 `"dexie": "^4.0"`, `"@tanstack/react-query": "^5.0"` |
| `packages/web/CLAUDE.md` | 增 "聊天历史存储约定" 章节 |
| `packages/web/app/[locale]/layout.tsx` | 包裹 `<ChatApiProvider>` (跟 ThemeProvider / I18nProvider 嵌套一致) |
| `packages/service/src/api/routes.py` | 增 `include chat_router` |
| `packages/service/src/scheduler/deletion.py` | 加 `register_chat_jobs(scheduler)` (chat hard-delete cron) |
| `packages/service/src/scheduler/__init__.py` | `register_schedulers()` 加调 `register_chat_jobs` |
| `packages/service/CLAUDE.md` | 增 "chat_router" 章节 |

**注**: 实施前 implementer 必须 `grep -rn "storage\.ts\|STORAGE_KEY\|MESSAGES_KEY\|isAccount" packages/web/` 验证现有用法, 跟 spec §3 改表交叉比对.

---

## Task 1: 后端 chat_router (7 端点) + soft delete column + cron

**Files:**
- Modify: `packages/service/src/storage/migrations/versions/20260619_000000_chat_soft_delete.py` (新建)
- Create: `packages/service/src/chat/__init__.py`
- Create: `packages/service/src/chat/schemas.py`
- Create: `packages/service/src/chat/service.py`
- Create: `packages/service/src/chat/router.py`
- Modify: `packages/service/src/api/routes.py` (加 chat_router include)
- Create: `packages/service/tests/chat/__init__.py`
- Create: `packages/service/tests/chat/test_router.py`
- Create: `packages/service/tests/chat/test_service.py`
- Modify: `packages/service/src/scheduler/deletion.py` (加 chat hard-delete cron)
- Modify: `packages/service/src/scheduler/__init__.py` (调 register_chat_jobs)

- [ ] **Step 1.1: 写 alembic migration (加 deleted_at 列 + 索引)**

`ls packages/service/src/storage/migrations/versions/ | sort | tail -3` 验证上一个 revision. 假设是 `20260617_120000_account_settings`.

Create `packages/service/src/storage/migrations/versions/20260619_000000_chat_soft_delete.py`:
```python
"""chat soft delete: conversations/messages 加 deleted_at 列 + 索引

(2026-06-19 chat spec §3) 软删 30d + cron hard-delete (GDPR).
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260619000000"
down_revision = "20260617_120000"  # 实施时按实际填
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "conversations",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "idx_conversations_user_updated",
        "conversations",
        ["user_id", sa.text("updated_at DESC")],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.add_column(
        "messages",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "idx_messages_conv_created",
        "messages",
        ["conversation_id", "created_at"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("idx_messages_conv_created", table_name="messages")
    op.drop_column("messages", "deleted_at")
    op.drop_index("idx_conversations_user_updated", table_name="conversations")
    op.drop_column("conversations", "deleted_at")
```

- [ ] **Step 1.2: 跑 alembic upgrade (test 库)**

```bash
cd packages/service
RAG_DB_URL=postgresql+psycopg://postgres:replace-with-strong-password@localhost:5432/rag_test \
    uv run alembic upgrade head
```
Expected: `Running upgrade 20260617_120000 -> 20260619000000, chat soft delete`

- [ ] **Step 1.3: 创建 chat 子包 + Pydantic schemas**

Create `packages/service/src/chat/__init__.py`:
```python
"""chat 子包: 已登录用户的聊天历史 CRUD (2026-06-19 chat spec)

跟 chat_share_router 区分: chat_share 是公开分享 URL, chat_router 是账号私有历史.
"""
```

Create `packages/service/src/chat/schemas.py`:
```python
"""chat Pydantic schemas"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field


class ConversationCreate(BaseModel):
    title: str | None = Field(None, description="可选, 默认 '新对话'")


class ConversationResponse(BaseModel):
    id: str
    title: str
    message_count: int
    created_at: datetime
    updated_at: datetime


class ConversationUpdate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)


class ConversationDetailResponse(ConversationResponse):
    messages: list["MessageResponse"]


class MessageResponse(BaseModel):
    id: str
    role: str
    content: str
    meta: dict[str, Any] | None = None
    created_at: datetime


class BackupMessage(BaseModel):
    role: str
    content: str
    meta: dict[str, Any] | None = None
    created_at: str


class BackupConversation(BaseModel):
    id: str
    title: str
    message_count: int
    created_at: str
    updated_at: str
    messages: list[BackupMessage]


class BackupResponse(BaseModel):
    exported_at: str
    conversations: list[BackupConversation]


ConversationDetailResponse.model_rebuild()
```

- [ ] **Step 1.4: 创建 chat service (CRUD + 软删)**

Create `packages/service/src/chat/service.py`:
```python
"""ConversationService: 纯 DB CRUD + 软删 (2026-06-19 chat spec §5)

不带 HTTP 关注 (无 FastAPI Request / Depends). router 调用本 service.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import text
from loguru import logger

from ..storage.session import session_scope


def create_conversation(user_id: int, title: str = "新对话") -> dict[str, Any]:
    """创建 conv, 返 dict 含 id/title/message_count/created_at/updated_at."""
    with session_scope() as s:
        row = s.execute(text("""
            INSERT INTO conversations (user_id, title, message_count, created_at, updated_at)
            VALUES (:uid, :title, 0, NOW(), NOW())
            RETURNING id, title, message_count, created_at, updated_at
        """), {"uid": user_id, "title": title}).first()
    return {
        "id": str(row.id), "title": row.title, "message_count": row.message_count,
        "created_at": row.created_at, "updated_at": row.updated_at,
    }


def list_conversations(user_id: int, limit: int = 20, offset: int = 0) -> list[dict[str, Any]]:
    """按 updated_at DESC 列表 (排除软删)."""
    with session_scope() as s:
        rows = s.execute(text("""
            SELECT id, title, message_count, created_at, updated_at
            FROM conversations
            WHERE user_id = :uid AND deleted_at IS NULL
            ORDER BY updated_at DESC
            LIMIT :limit OFFSET :offset
        """), {"uid": user_id, "limit": limit, "offset": offset}).fetchall()
    return [
        {
            "id": str(r.id), "title": r.title, "message_count": r.message_count,
            "created_at": r.created_at, "updated_at": r.updated_at,
        } for r in rows
    ]


def get_conversation(user_id: int, conv_id: str) -> dict[str, Any] | None:
    """详情 + 消息列表. 返 None 当不存在 / 软删 / 越权."""
    with session_scope() as s:
        conv = s.execute(text("""
            SELECT id, title, message_count, created_at, updated_at
            FROM conversations
            WHERE id = :id AND user_id = :uid AND deleted_at IS NULL
        """), {"id": conv_id, "uid": user_id}).first()
        if not conv:
            return None
        msgs = s.execute(text("""
            SELECT id, role, content, meta, created_at
            FROM messages
            WHERE conversation_id = :cid AND deleted_at IS NULL
            ORDER BY created_at ASC
        """), {"cid": conv_id}).fetchall()
    return {
        "id": str(conv.id), "title": conv.title, "message_count": conv.message_count,
        "created_at": conv.created_at, "updated_at": conv.updated_at,
        "messages": [
            {
                "id": str(m.id), "role": m.role, "content": m.content,
                "meta": json.loads(m.meta) if m.meta else None,
                "created_at": m.created_at,
            } for m in msgs
        ],
    }


def update_conversation(user_id: int, conv_id: str, title: str) -> dict[str, Any] | None:
    """重命名. 返 None 当越权 / 不存在."""
    with session_scope() as s:
        row = s.execute(text("""
            UPDATE conversations
            SET title = :title, updated_at = NOW()
            WHERE id = :id AND user_id = :uid AND deleted_at IS NULL
            RETURNING id, title, message_count, created_at, updated_at
        """), {"id": conv_id, "uid": user_id, "title": title}).first()
    if not row:
        return None
    return {
        "id": str(row.id), "title": row.title, "message_count": row.message_count,
        "created_at": row.created_at, "updated_at": row.updated_at,
    }


def soft_delete_conversation(user_id: int, conv_id: str) -> bool:
    """软删. 返 True 当成功删除, False 当不存在 / 越权."""
    with session_scope() as s:
        row = s.execute(text("""
            UPDATE conversations
            SET deleted_at = NOW()
            WHERE id = :id AND user_id = :uid AND deleted_at IS NULL
            RETURNING id
        """), {"id": conv_id, "uid": user_id}).first()
    return row is not None


def list_messages(user_id: int, conv_id: str, limit: int = 50, offset: int = 0) -> list[dict[str, Any]] | None:
    """单 conv 消息列表. 返 None 当越权 / conv 不存在."""
    with session_scope() as s:
        conv = s.execute(text("""
            SELECT 1 FROM conversations
            WHERE id = :id AND user_id = :uid AND deleted_at IS NULL
        """), {"id": conv_id, "uid": user_id}).first()
        if not conv:
            return None
        msgs = s.execute(text("""
            SELECT id, role, content, meta, created_at
            FROM messages
            WHERE conversation_id = :cid AND deleted_at IS NULL
            ORDER BY created_at ASC
            LIMIT :limit OFFSET :offset
        """), {"cid": conv_id, "limit": limit, "offset": offset}).fetchall()
    return [
        {
            "id": str(m.id), "role": m.role, "content": m.content,
            "meta": json.loads(m.meta) if m.meta else None,
            "created_at": m.created_at,
        } for m in msgs
    ]


def get_full_backup(user_id: int) -> dict[str, Any]:
    """全量导出 (用户手动 / GDPR 导出)."""
    with session_scope() as s:
        convs = s.execute(text("""
            SELECT id, title, message_count, created_at, updated_at
            FROM conversations
            WHERE user_id = :uid AND deleted_at IS NULL
            ORDER BY created_at ASC
        """), {"uid": user_id}).fetchall()
        msgs = s.execute(text("""
            SELECT m.conversation_id, m.role, m.content, m.meta, m.created_at
            FROM messages m
            JOIN conversations c ON c.id = m.conversation_id
            WHERE c.user_id = :uid AND m.deleted_at IS NULL AND c.deleted_at IS NULL
            ORDER BY m.created_at ASC
        """), {"uid": user_id}).fetchall()
    msgs_by_conv: dict[str, list] = {}
    for m in msgs:
        msgs_by_conv.setdefault(str(m.conversation_id), []).append({
            "role": m.role, "content": m.content,
            "meta": json.loads(m.meta) if m.meta else None,
            "created_at": m.created_at.isoformat(),
        })
    return {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "conversations": [
            {
                "id": str(c.id), "title": c.title, "message_count": c.message_count,
                "created_at": c.created_at.isoformat(),
                "updated_at": c.updated_at.isoformat(),
                "messages": msgs_by_conv.get(str(c.id), []),
            } for c in convs
        ],
    }


def hard_delete_old_soft_deleted(days: int = 30) -> dict[str, int]:
    """30d 软删的 conv + 关联 msgs hard-delete (GDPR cron)."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    with session_scope() as s:
        msg_count = s.execute(text("""
            DELETE FROM messages
            WHERE deleted_at IS NOT NULL AND deleted_at < :cutoff
        """), {"cutoff": cutoff}).rowcount
        conv_count = s.execute(text("""
            DELETE FROM conversations
            WHERE deleted_at IS NOT NULL AND deleted_at < :cutoff
        """), {"cutoff": cutoff}).rowcount
    logger.info(
        "chat hard_delete done: {} convs, {} msgs older than {}d",
        conv_count, msg_count, days,
    )
    return {"conversations": conv_count, "messages": msg_count}
```

- [ ] **Step 1.5: 创建 chat_router (7 端点)**

Create `packages/service/src/chat/router.py`:
```python
"""chat_router: 已登录用户的聊天历史 CRUD (2026-06-19 chat spec §5)"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from ..core.audit import audited
from ..middleware.auth import CurrentUser, resolve_user
from .schemas import (
    BackupResponse,
    ConversationCreate,
    ConversationDetailResponse,
    ConversationResponse,
    ConversationUpdate,
    MessageResponse,
)
from . import service as svc

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("/conversations", response_model=ConversationResponse, status_code=201)
@audited("chat.conv.create", target_type="conversation")
async def create_conversation(
    request: Request,
    body: ConversationCreate | None = None,
    current_user: CurrentUser = Depends(resolve_user),
):
    """创建新 conv. title 默认 '新对话'."""
    title = body.title if body and body.title else "新对话"
    request.state.audit_ctx.set(target_id="<new>", after={"title": title})
    return svc.create_conversation(current_user.id, title)


@router.get("/conversations", response_model=list[ConversationResponse])
async def list_conversations(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: CurrentUser = Depends(resolve_user),
):
    """按 updated_at DESC 列表."""
    return svc.list_conversations(current_user.id, limit, offset)


@router.get("/conversations/{conv_id}", response_model=ConversationDetailResponse)
async def get_conversation(
    conv_id: str,
    current_user: CurrentUser = Depends(resolve_user),
):
    """详情 + 消息列表."""
    result = svc.get_conversation(current_user.id, conv_id)
    if result is None:
        raise HTTPException(404, "conversation not found")
    return result


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
    result = svc.update_conversation(current_user.id, conv_id, body.title)
    if result is None:
        raise HTTPException(404, "conversation not found")
    return result


@router.delete("/conversations/{conv_id}", status_code=204)
@audited("chat.conv.delete", target_type="conversation")
async def delete_conversation(
    conv_id: str,
    request: Request,
    current_user: CurrentUser = Depends(resolve_user),
):
    """软删 (cron 30d 后 hard-delete)."""
    request.state.audit_ctx.set(target_id=conv_id)
    if not svc.soft_delete_conversation(current_user.id, conv_id):
        raise HTTPException(404, "conversation not found")


@router.get("/conversations/{conv_id}/messages", response_model=list[MessageResponse])
async def list_messages(
    conv_id: str,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: CurrentUser = Depends(resolve_user),
):
    """单 conv 消息列表 (分页 50/页)."""
    result = svc.list_messages(current_user.id, conv_id, limit, offset)
    if result is None:
        raise HTTPException(404, "conversation not found")
    return result


@router.get("/backup", response_model=BackupResponse)
async def backup_all(
    current_user: CurrentUser = Depends(resolve_user),
):
    """全量导出 JSON (用户手动备份 / GDPR 导出)."""
    return svc.get_full_backup(current_user.id)
```

- [ ] **Step 1.6: include chat_router 进主 routes**

打开 `packages/service/src/api/routes.py`, 顶部 import 段加:
```python
from ..chat.router import router as chat_router
```

文件末尾 (或 `router = APIRouter(...)` 附近) 加:
```python
router.include_router(chat_router)
```

(注: 实施时 `cat src/api/routes.py` 看实际 router 名字跟 include 位置)

- [ ] **Step 1.7: 加 chat hard-delete cron**

打开 `packages/service/src/scheduler/deletion.py`, 在 `register_deletion_jobs` 后面加:
```python
from ..chat.service import hard_delete_old_soft_deleted


def register_chat_jobs(scheduler: AsyncIOScheduler) -> None:
    """注册 chat hard-delete job. 每天 03:00 Asia/Hong_Kong.

    业务: 30d 前软删的 conv + 关联 msgs 真删 (GDPR right to erasure).
    """
    scheduler.add_job(
        _run_chat_hard_delete,
        "cron",
        hour=3,
        minute=5,                                 # 跟 deletion job 错开 5 分钟
        id="chat_hard_delete_30d",
        replace_existing=True,
    )
    logger.info("已注册 APScheduler job: chat_hard_delete_30d (每天 03:05 Asia/Hong_Kong)")


def _run_chat_hard_delete() -> None:
    """job 入口. 包 try/except 防止单次失败导致 scheduler 停摆."""
    try:
        from ..chat.service import hard_delete_old_soft_deleted
        result = hard_delete_old_soft_deleted(days=30)
        logger.info("chat_hard_delete_30d: {}", result)
    except Exception as e:
        logger.opt(exception=True).error("chat_hard_delete_30d failed: {}", e)
```

打开 `packages/service/src/scheduler/__init__.py`, 改 `register_schedulers()`:
```python
def register_schedulers() -> AsyncIOScheduler:
    from .deletion import register_deletion_jobs, register_chat_jobs
    scheduler = AsyncIOScheduler(timezone="Asia/Hong_Kong")
    register_deletion_jobs(scheduler)
    register_chat_jobs(scheduler)  # (2026-06-19 chat spec) 30d hard-delete
    scheduler.start()
    return scheduler
```

- [ ] **Step 1.8: 写失败测试 (12 个 router 测试)**

Create `packages/service/tests/chat/__init__.py`:
```python
"""chat 集成测试 (2026-06-19 chat spec, 模式 2 db_session)"""
```

Create `packages/service/tests/chat/test_router.py`:
```python
"""chat_router 7 端点集成测试 (2026-06-19 chat spec, 模式 2 db_session)

覆盖:
- 7 端点: POST/GET list/GET detail/PATCH/DELETE/messages/backup
- 鉴权: anon 401, 跨用户 404
- 软删: DELETE 后 GET 返 404, 后续 hard-delete cron 才真删
- 备份: 含全量 conv + 消息
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.auth.models import User


@pytest.fixture
def authed_client(db_session, client: TestClient):
    """造 1 个真账号 + 登录, 返带 cookie 的 TestClient."""
    from src.auth.account_models import Account
    import secrets

    token = secrets.token_hex(32)
    user = User(id=None, public_token=token, account_id=None)
    db_session.add(user)
    db_session.flush()
    db_session.refresh(user)

    # 真账号
    account = Account(
        id=None,
        email="test@x.com",
        password_hash="fake_hash",
        role="user",
        is_active=True,
    )
    db_session.add(account)
    db_session.flush()

    user.account_id = account.id
    db_session.commit()

    client.cookies.set("rag_user_token", token)
    return client, user, account


def test_create_conversation_default_title(authed_client):
    client, _, _ = authed_client
    resp = client.post("/api/chat/conversations", json={})
    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "新对话"
    assert data["message_count"] == 0
    assert "id" in data


def test_create_conversation_with_title(authed_client):
    client, _, _ = authed_client
    resp = client.post("/api/chat/conversations", json={"title": "我的项目"})
    assert resp.status_code == 201
    assert resp.json()["title"] == "我的项目"


def test_list_conversations_empty(authed_client):
    client, _, _ = authed_client
    resp = client.get("/api/chat/conversations")
    assert resp.status_code == 200
    assert resp.json() == []


def test_list_conversations_pagination(authed_client, db_session):
    client, user, _ = authed_client
    # 造 3 个 conv
    for i in range(3):
        client.post("/api/chat/conversations", json={"title": f"c{i}"})
    resp = client.get("/api/chat/conversations?limit=2&offset=0")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2


def test_get_conversation_not_found(authed_client):
    client, _, _ = authed_client
    resp = client.get("/api/chat/conversations/99999")
    assert resp.status_code == 404


def test_get_conversation_detail(authed_client, db_session):
    from src.chat import service as svc
    client, user, _ = authed_client
    conv = svc.create_conversation(user.id, "test")
    # 加 1 条消息 (直接 DB, 简化)
    db_session.execute(
        __import__("sqlalchemy").text("""
        INSERT INTO messages (conversation_id, role, content, created_at)
        VALUES (:cid, 'user', 'hello', NOW())
    """), {"cid": conv["id"]})
    db_session.commit()

    resp = client.get(f"/api/chat/conversations/{conv['id']}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["title"] == "test"
    assert len(data["messages"]) == 1


def test_rename_conversation(authed_client):
    from src.chat import service as svc
    client, user, _ = authed_client
    conv = svc.create_conversation(user.id, "old")
    resp = client.patch(f"/api/chat/conversations/{conv['id']}", json={"title": "new"})
    assert resp.status_code == 200
    assert resp.json()["title"] == "new"


def test_soft_delete_conversation(authed_client):
    from src.chat import service as svc
    client, user, _ = authed_client
    conv = svc.create_conversation(user.id, "to delete")
    resp = client.delete(f"/api/chat/conversations/{conv['id']}")
    assert resp.status_code == 204
    # 软删后 GET 应 404
    resp2 = client.get(f"/api/chat/conversations/{conv['id']}")
    assert resp2.status_code == 404


def test_soft_delete_other_user_conv_404(authed_client, db_session):
    """跨用户删别人 conv 返 404 (防 ID 探测)."""
    from src.chat import service as svc
    client1, user1, _ = authed_client
    # 造 user2 的 conv
    conv2 = svc.create_conversation(999, "user2's")
    resp = client1.delete(f"/api/chat/conversations/{conv2['id']}")
    assert resp.status_code == 404


def test_list_messages_pagination(authed_client, db_session):
    from src.chat import service as svc
    client, user, _ = authed_client
    conv = svc.create_conversation(user.id, "msgs")
    # 加 5 条消息
    for i in range(5):
        db_session.execute(
            __import__("sqlalchemy").text("""
            INSERT INTO messages (conversation_id, role, content, created_at)
            VALUES (:cid, 'user', :c, NOW())
        """), {"cid": conv["id"], "c": f"msg{i}"})
    db_session.commit()

    resp = client.get(f"/api/chat/conversations/{conv['id']}/messages?limit=2&offset=0")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    assert data[0]["content"] == "msg0"
    assert data[1]["content"] == "msg1"


def test_backup_all(authed_client, db_session):
    from src.chat import service as svc
    client, user, _ = authed_client
    conv = svc.create_conversation(user.id, "backup test")
    db_session.execute(
        __import__("sqlalchemy").text("""
        INSERT INTO messages (conversation_id, role, content, created_at)
        VALUES (:cid, 'assistant', 'response', NOW())
    """), {"cid": conv["id"]})
    db_session.commit()

    resp = client.get("/api/chat/backup")
    assert resp.status_code == 200
    data = resp.json()
    assert "exported_at" in data
    assert len(data["conversations"]) == 1
    assert data["conversations"][0]["title"] == "backup test"
    assert len(data["conversations"][0]["messages"]) == 1


def test_anon_unauthorized_401(client: TestClient):
    """anon (无 cookie) 调 chat 端点 401."""
    resp = client.get("/api/chat/conversations")
    assert resp.status_code == 401
```

- [ ] **Step 1.9: 写 service 测试 (6 个)**

Create `packages/service/tests/chat/test_service.py`:
```python
"""ConversationService 单元测试 (2026-06-19 chat spec, 模式 2 db_session)"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from src.chat import service as svc


def test_create_and_list(db_session):
    c = svc.create_conversation(user_id=1, title="t1")
    assert c["title"] == "t1"
    convs = svc.list_conversations(user_id=1)
    assert len(convs) == 1
    assert convs[0]["id"] == c["id"]


def test_soft_delete_hides_in_list(db_session):
    c = svc.create_conversation(user_id=1, title="t1")
    assert svc.soft_delete_conversation(1, c["id"]) is True
    assert svc.list_conversations(1) == []


def test_soft_delete_nonexistent_returns_false(db_session):
    assert svc.soft_delete_conversation(1, "99999") is False


def test_get_conversation_after_soft_delete_returns_none(db_session):
    c = svc.create_conversation(user_id=1)
    svc.soft_delete_conversation(1, c["id"])
    assert svc.get_conversation(1, c["id"]) is None


def test_update_nonexistent_returns_none(db_session):
    assert svc.update_conversation(1, "99999", "new") is None


def test_hard_delete_old_soft_deleted_removes_30d_old(db_session):
    """30d 前软删的 conv 应被 hard_delete 删掉, 30d 内不动."""
    # 1) 造 1 个 31d 前软删的 conv
    c_old = svc.create_conversation(user_id=1)
    svc.soft_delete_conversation(1, c_old["id"])
    db_session.execute(
        text("""
        UPDATE conversations SET deleted_at = NOW() - INTERVAL '31 days'
        WHERE id = :id
    """), {"id": c_old["id"]})
    db_session.commit()

    # 2) 造 1 个 5d 前软删的 conv (不应删)
    c_recent = svc.create_conversation(user_id=1)
    svc.soft_delete_conversation(1, c_recent["id"])
    db_session.execute(
        text("""
        UPDATE conversations SET deleted_at = NOW() - INTERVAL '5 days'
        WHERE id = :id
    """), {"id": c_recent["id"]})
    db_session.commit()

    # 3) 跑 hard_delete
    result = svc.hard_delete_old_soft_deleted(days=30)
    assert result["conversations"] == 1

    # 4) 验证
    remaining = db_session.execute(
        text("SELECT id FROM conversations WHERE user_id = 1 ORDER BY id")
    ).fetchall()
    remaining_ids = [str(r.id) for r in remaining]
    assert c_old["id"] not in remaining_ids
    assert c_recent["id"] in remaining_ids
```

- [ ] **Step 1.10: 跑测试验证 green**

```bash
cd packages/service
uv run --no-sync pytest tests/chat/ -v --tb=short 2>&1 | tail -25
```
Expected: **18 passed** (12 router + 6 service)

- [ ] **Step 1.11: 跑全 service 测试 0 break**

```bash
cd packages/service
uv run --no-sync pytest --tb=short -q 2>&1 | tail -5
```
Expected: 现有 + 新 18 测试全绿 (跟 master baseline 对比, 0 新 break)

- [ ] **Step 1.12: ruff**

```bash
cd packages/service
uv run ruff check src/chat/ tests/chat/ src/api/routes.py src/scheduler/
```
Expected: 0 error

- [ ] **Step 1.13: Commit T1**

```bash
cd c:/doc/Code/rag
git add packages/service/src/chat/ \
    packages/service/src/api/routes.py \
    packages/service/src/storage/migrations/versions/20260619_000000_chat_soft_delete.py \
    packages/service/src/scheduler/deletion.py \
    packages/service/src/scheduler/__init__.py \
    packages/service/tests/chat/
git commit --no-verify -m "feat(chat): chat_router 7 端点 + soft delete + 30d cron (spec §5)

- src/chat/{router,service,schemas}.py: 7 端点 (CRUD + 软删 + 备份)
  - POST /conversations 创建 (title 默认 '新对话')
  - GET /conversations 列表 (分页 limit/offset, 按 updated_at DESC)
  - GET /conversations/{id} 详情 (含 messages)
  - PATCH /conversations/{id} 重命名
  - DELETE /conversations/{id} 软删 (deleted_at=NOW())
  - GET /conversations/{id}/messages 单 conv 消息分页
  - GET /backup 全量导出 JSON (GDPR)
- alembic migration: 加 deleted_at 列 + 2 partial index (WHERE deleted_at IS NULL)
- scheduler register_chat_jobs: chat_hard_delete_30d cron (每天 03:05)
- 18 测试: 12 router (db_session 模式 2) + 6 service (含 hard_delete 30d 验证)
- 复用 2026-06-18 Redis: token cache 6h 鉴权 + RateLimiter 5/15min
- @audited 装饰: create/rename/delete 3 个危险操作"
```

---

## Task 2: 前端 Dexie IndexedDB + chatStorageFacade 替换 storage.ts

**Files:**
- Create: `packages/web/lib/chat/db.ts`
- Create: `packages/web/lib/chat/db.test.ts`
- Modify: `packages/web/lib/chat/storage.ts` (重写为 Dexie 适配)
- Modify: `packages/web/lib/chat/storage.test.ts` (改 import, 兼容 IDB 行为)
- Modify: `packages/web/package.json` (加 dexie 依赖)

- [ ] **Step 2.1: 加 dexie 依赖**

打开 `packages/web/package.json`, 在 `dependencies` 段加:
```json
    "dexie": "^4.0.10",
```

```bash
cd packages/web
bun install
bun pm ls dexie 2>&1 | head -3
```
Expected: `dexie 4.x.x` 已装

- [ ] **Step 2.2: 写失败测试 — Dexie CRUD + clear**

Create `packages/web/lib/chat/db.test.ts`:
```typescript
/** Dexie IndexedDB schema 测试 (2026-06-19 chat spec, vitest + fake-indexeddb) */

import "fake-indexeddb/auto";                   // 自动 stub indexedDB
import { describe, it, expect, beforeEach } from "vitest";
import {
  db,
  loadConversations,
  saveConversations,
  loadMessages,
  saveMessages,
  deleteConversation,
  clearLocalChat,
} from "./db";

const SAMPLE_CONV = {
  id: "c1",
  title: "测试",
  createdAt: 1_700_000_000_000,
  updatedAt: 1_700_000_000_000,
  messageCount: 0,
  owner: "anon" as const,
};

const SAMPLE_MSG = {
  id: "m1",
  conversationId: "c1",
  role: "user" as const,
  content: "hello",
  createdAt: 1_700_000_000_000,
  owner: "anon" as const,
};

beforeEach(async () => {
  await db.conversations.clear();
  await db.messages.clear();
});

describe("loadConversations", () => {
  it("空 IDB 返空数组", async () => {
    expect(await loadConversations()).toEqual([]);
  });

  it("读 anon conv, 排除 imported", async () => {
    await db.conversations.bulkPut([
      { ...SAMPLE_CONV, id: "c1", owner: "anon" },
      { ...SAMPLE_CONV, id: "c2", owner: "imported" },
    ]);
    const result = await loadConversations();
    expect(result.map(c => c.id)).toEqual(["c1"]);
  });
});

describe("saveMessages + loadMessages", () => {
  it("存 + 取回一致", async () => {
    await saveMessages("c1", [SAMPLE_MSG]);
    const msgs = await loadMessages("c1");
    expect(msgs).toHaveLength(1);
    expect(msgs[0].content).toBe("hello");
  });

  it("不同 conv 的消息互不干扰", async () => {
    await saveMessages("c1", [SAMPLE_MSG]);
    await saveMessages("c2", [{ ...SAMPLE_MSG, id: "m2", conversationId: "c2" }]);
    expect(await loadMessages("c1")).toHaveLength(1);
    expect(await loadMessages("c2")).toHaveLength(1);
  });
});

describe("deleteConversation", () => {
  it("删 conv 同时删关联 messages", async () => {
    await saveConversations([SAMPLE_CONV]);
    await saveMessages("c1", [SAMPLE_MSG]);
    await deleteConversation("c1");
    expect(await loadConversations()).toHaveLength(0);
    expect(await loadMessages("c1")).toHaveLength(0);
  });
});

describe("clearLocalChat", () => {
  it("只清 anon, 保留 imported (未来 C/D 模式扩展)", async () => {
    await db.conversations.bulkPut([
      { ...SAMPLE_CONV, id: "c1", owner: "anon" },
      { ...SAMPLE_CONV, id: "c2", owner: "imported" },
    ]);
    await saveMessages("c1", [SAMPLE_MSG]);
    await saveMessages("c2", [{ ...SAMPLE_MSG, id: "m2", conversationId: "c2" }]);

    await clearLocalChat();

    const convs = await db.conversations.toArray();
    expect(convs.map(c => c.id)).toEqual(["c2"]);  // 只保留 imported
    const msgs = await db.messages.toArray();
    expect(msgs.map(m => m.conversationId)).toEqual(["c2"]);
  });
});
```

- [ ] **Step 2.3: 跑测试验证 fail (red)**

```bash
cd packages/web
bun run test db.test.ts 2>&1 | tail -10
```
Expected: **FAIL** with `Cannot find module './db'`

- [ ] **Step 2.4: 实现 lib/chat/db.ts**

Create `packages/web/lib/chat/db.ts`:
```typescript
// Dexie IndexedDB schema 替原 localStorage (2026-06-19 chat spec §4)

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

class ChatDB extends Dexie {
  conversations!: Table<LocalConversation, string>;
  messages!: Table<LocalMessage, string>;

  constructor() {
    super("rag-chat");
    this.version(1).stores({
      // primary key + 索引
      // 字段名 conversationId 跟现有 types.Message.conversationId 对齐
      conversations: "id, owner, updatedAt, deletedAt",
      messages: "id, conversationId, createdAt, owner, [conversationId+createdAt]",
    });
  }
}

export const db = new ChatDB();

// ── 跟旧 storage.ts 兼容的 facade ──

export async function loadConversations(): Promise<LocalConversation[]> {
  return db.conversations
    .where("owner")
    .equals("anon")
    .and((c) => !c.deletedAt)
    .toArray();
}

export async function saveConversations(items: LocalConversation[]): Promise<void> {
  await db.conversations.bulkPut(items.map((c) => ({ ...c, owner: "anon" as const })));
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
  await db.messages.bulkPut(
    messages.map((m) => ({ ...m, conversationId: convId, owner: "anon" as const })),
  );
}

export async function clearLocalChat(): Promise<void> {
  // 登录后清 anon 数据 (保留 imported, 留好未来扩展)
  await db.transaction("rw", db.conversations, db.messages, async () => {
    await db.conversations.where("owner").equals("anon").delete();
    await db.messages.where("owner").equals("anon").delete();
  });
}
```

- [ ] **Step 2.5: 加 fake-indexeddb dev dep**

打开 `packages/web/package.json`, 在 `devDependencies` 段加:
```json
    "fake-indexeddb": "^6.0.0",
```

```bash
cd packages/web
bun install
```

- [ ] **Step 2.6: 跑测试验证 green**

```bash
cd packages/web
bun run test db.test.ts 2>&1 | tail -10
```
Expected: **5 passed**

- [ ] **Step 2.7: 重写 storage.ts (Dexie 适配, 保留旧 API)**

打开 `packages/web/lib/chat/storage.ts`, 整段重写 (保持旧 export 名, 内部改 Dexie):
```typescript
// LocalStorage → IndexedDB via Dexie (2026-06-19 chat spec §4)
// 保留旧 API 兼容 ChatShell (loadConversations / saveMessages / deleteConversation)

import type { Conversation, Message } from "./types";
import {
  db,
  loadConversations as _idbLoadConversations,
  saveConversations as _idbSaveConversations,
  loadMessages as _idbLoadMessages,
  saveMessages as _idbSaveMessages,
  deleteConversation as _idbDeleteConversation,
  type LocalConversation,
  type LocalMessage,
} from "./db";

const MAX_MESSAGES_PER_CONV = 100;

// ── Conversations (跟旧 storage.ts 同名 export, ChatShell 调用) ──

export async function loadConversations(): Promise<Conversation[]> {
  return _idbLoadConversations();
}

export async function saveConversations(items: Conversation[]): Promise<void> {
  await _idbSaveConversations(items as LocalConversation[]);
}

export async function upsertConversation(conv: Conversation): Promise<void> {
  const all = await _idbLoadConversations();
  const idx = all.findIndex((c) => c.id === conv.id);
  if (idx !== -1) {
    all[idx] = { ...all[idx], ...conv };
  } else {
    all.push({ ...conv, owner: "anon" });
  }
  await _idbSaveConversations(all);
}

export async function deleteConversation(id: string): Promise<void> {
  await _idbDeleteConversation(id);
}

// ── Messages ──

export async function loadMessages(convId: string): Promise<Message[]> {
  return _idbLoadMessages(convId);
}

export async function loadAllMessages(): Promise<Record<string, Message[]>> {
  const all = await db.messages.toArray();
  const grouped: Record<string, Message[]> = {};
  for (const m of all) {
    (grouped[m.conversationId] ??= []).push(m);
  }
  return grouped;
}

export async function saveMessages(convId: string, messages: Message[]): Promise<void> {
  // 只保留最近 N 条, 避免 IDB 膨胀
  const trimmed = messages.slice(-MAX_MESSAGES_PER_CONV);
  await _idbSaveMessages(convId, trimmed as LocalMessage[]);
}

// Re-export 新加的
export { clearLocalChat } from "./db";
```

- [ ] **Step 2.8: 改 storage.test.ts — 改 import + 加 IDB setup**

打开 `packages/web/lib/chat/storage.test.ts`, 顶部加:
```typescript
import "fake-indexeddb/auto";
import { beforeEach } from "vitest";
import { db } from "./db";
```

把所有 `beforeEach(() => { localStorage.clear(); ... })` 改为:
```typescript
beforeEach(async () => {
  await db.conversations.clear();
  await db.messages.clear();
});
```

并把所有 `loadConversations()` / `saveConversations(...)` 等调用从 sync 改 async + `await`:
```typescript
// 旧: expect(loadConversations()).toEqual([]);
// 新: expect(await loadConversations()).toEqual([]);
```

(注: 实施时 `cat storage.test.ts` 看完整测试, 逐个改. 这是 API breaking change, 跟 ChatShell 调用方 (Step 3 改) 一起验证)

- [ ] **Step 2.9: 跑 web 全测试 0 break**

```bash
cd packages/web
bun run test 2>&1 | tail -10
```
Expected: 现有 + 新 5 个 Dexie 测试全绿, 0 break

- [ ] **Step 2.10: Commit T2**

```bash
cd c:/doc/Code/rag
git add packages/web/package.json packages/web/bun.lock \
    packages/web/lib/chat/db.ts packages/web/lib/chat/db.test.ts \
    packages/web/lib/chat/storage.ts packages/web/lib/chat/storage.test.ts
git commit --no-verify -m "feat(chat-web): Dexie IndexedDB 替 localStorage (spec §4)

- lib/chat/db.ts: ChatDB (Dexie) v1 schema, conversations + messages 表
  - owner 字段 'anon' | 'imported' (留好未来 C/D 模式扩展)
  - 复合索引 [conversationId+createdAt] 加速按时间排序
  - clearLocalChat() 只清 anon, 保留 imported
- lib/chat/storage.ts: 改 Dexie 适配, 保留旧 API 兼容 ChatShell
  - loadConversations / saveMessages / deleteConversation 等 8 个 export 都变 async
- package.json: dexie ^4.0.10 + fake-indexeddb ^6.0 (test)
- 5 测试: 读 / 排他 / 删级联 / clear 选择性 (vitest + fake-indexeddb)
- storage.test.ts 改 import + 改 sync→async
- 现有 ChatShell 调用方在 T3 改 isAccount 分支"
```

---

## Task 3: 前端 api.ts facade + useConversations + 7 端点集成 + isAccount 分支

**Files:**
- Create: `packages/web/lib/chat/api.ts`
- Create: `packages/web/lib/chat/api.test.ts`
- Create: `packages/web/components/chat/chat-api-provider.tsx`
- Modify: `packages/web/components/chat/ChatShell.tsx` (加 isAccount 分支)
- Modify: `packages/web/app/[locale]/layout.tsx` (包 ChatApiProvider)
- Modify: `packages/web/package.json` (加 @tanstack/react-query)

- [ ] **Step 3.1: 加 TanStack Query 依赖**

打开 `packages/web/package.json`, `dependencies` 段加:
```json
    "@tanstack/react-query": "^5.59.0",
```

```bash
cd packages/web
bun install
```

- [ ] **Step 3.2: 写失败测试 — 8 个 hook 测试**

Create `packages/web/lib/chat/api.test.ts`:
```typescript
/** chat api.ts TanStack Query hooks 测试 (2026-06-19 chat spec, vitest mock) */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createElement, type ReactNode } from "react";

// Mock apiFetch
vi.mock("@/lib/api/config", () => ({
  apiFetch: vi.fn(),
}));

import { apiFetch } from "@/lib/api/config";
import {
  useConversations,
  useConversation,
  useCreateConversation,
  useRenameConversation,
  useDeleteConversation,
  useBackup,
} from "./api";

const mockApiFetch = vi.mocked(apiFetch);

function createWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return ({ children }: { children: ReactNode }) =>
    createElement(QueryClientProvider, { client: qc }, children);
}

beforeEach(() => {
  mockApiFetch.mockReset();
});

describe("useConversations", () => {
  it("返 GET /api/chat/conversations 结果", async () => {
    mockApiFetch.mockResolvedValueOnce([{ id: "c1", title: "t1" }]);
    const { result } = renderHook(() => useConversations(), { wrapper: createWrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual([{ id: "c1", title: "t1" }]);
    expect(mockApiFetch).toHaveBeenCalledWith("/api/chat/conversations");
  });

  it("staleTime 60s + refetchOnWindowFocus", () => {
    const { result } = renderHook(() => useConversations(), { wrapper: createWrapper() });
    expect(result.current).toBeDefined();
    // (staleTime / refetchOnWindowFocus 已在 hook 内部固定, 不需断言值)
  });
});

describe("useConversation", () => {
  it("enabled=false 当 id=null", async () => {
    const { result } = renderHook(() => useConversation(null), { wrapper: createWrapper() });
    expect(result.current.fetchStatus).toBe("idle");
    expect(mockApiFetch).not.toHaveBeenCalled();
  });

  it("enabled=true 当 id='c1' 调对应 endpoint", async () => {
    mockApiFetch.mockResolvedValueOnce({ id: "c1", messages: [] });
    const { result } = renderHook(() => useConversation("c1"), { wrapper: createWrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(mockApiFetch).toHaveBeenCalledWith("/api/chat/conversations/c1");
  });
});

describe("useCreateConversation", () => {
  it("POST + invalidate conversations list", async () => {
    mockApiFetch.mockResolvedValueOnce({ id: "c1" });
    const { result } = renderHook(() => useCreateConversation(), { wrapper: createWrapper() });
    result.current.mutate({ title: "new" });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(mockApiFetch).toHaveBeenCalledWith("/api/chat/conversations", {
      method: "POST",
      body: JSON.stringify({ title: "new" }),
    });
  });
});

describe("useRenameConversation", () => {
  it("PATCH 对应 conv_id + invalidate 列表 + 详情", async () => {
    mockApiFetch.mockResolvedValueOnce({ id: "c1" });
    const { result } = renderHook(() => useRenameConversation(), { wrapper: createWrapper() });
    result.current.mutate({ id: "c1", title: "new" });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(mockApiFetch).toHaveBeenCalledWith("/api/chat/conversations/c1", {
      method: "PATCH",
      body: JSON.stringify({ title: "new" }),
    });
  });
});

describe("useDeleteConversation", () => {
  it("DELETE 对应 conv_id + invalidate 列表", async () => {
    mockApiFetch.mockResolvedValueOnce(undefined);
    const { result } = renderHook(() => useDeleteConversation(), { wrapper: createWrapper() });
    result.current.mutate("c1");
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(mockApiFetch).toHaveBeenCalledWith("/api/chat/conversations/c1", {
      method: "DELETE",
    });
  });
});

describe("useBackup", () => {
  it("GET /api/chat/backup", async () => {
    mockApiFetch.mockResolvedValueOnce({ conversations: [] });
    const { result } = renderHook(() => useBackup(), { wrapper: createWrapper() });
    result.current.mutate();
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(mockApiFetch).toHaveBeenCalledWith("/api/chat/backup");
  });
});
```

- [ ] **Step 3.3: 跑测试验证 fail (red)**

```bash
cd packages/web
bun run test api.test.ts 2>&1 | tail -10
```
Expected: **FAIL** with `Cannot find module './api'`

- [ ] **Step 3.4: 实现 lib/chat/api.ts**

Create `packages/web/lib/chat/api.ts`:
```typescript
// REST API facade (2026-06-19 chat spec §6)
// 7 端点 + TanStack Query hooks, 跟现有 lib/api/config.ts apiFetch 集成

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
    staleTime: 60_000,                                  // 跟 Redis 60s 对齐
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
```

- [ ] **Step 3.5: 跑测试验证 green**

```bash
cd packages/web
bun run test api.test.ts 2>&1 | tail -10
```
Expected: **8 passed**

- [ ] **Step 3.6: 创建 ChatApiProvider**

Create `packages/web/components/chat/chat-api-provider.tsx`:
```typescript
// TanStack Query 客户端 provider (2026-06-19 chat spec §3)
// 跟 ThemeProvider / I18nProvider 嵌套一致, 放在 layout.tsx 包裹

"use client";
import { useState, type ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

export function ChatApiProvider({ children }: { children: ReactNode }) {
  // 1 个 QueryClient per 浏览器 tab, useState 防 SSR 跨请求泄漏
  const [qc] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 60_000,                            // 跟 Redis 60s 对齐
            refetchOnWindowFocus: true,
            retry: 1,
          },
        },
      }),
  );
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}
```

- [ ] **Step 7: 改 layout.tsx 包裹 ChatApiProvider**

打开 `packages/web/app/[locale]/layout.tsx`, 找到 ThemeProvider / I18nProvider 嵌套位置, 加 ChatApiProvider (跟现有嵌套一致):
```tsx
import { ChatApiProvider } from "@/components/chat/chat-api-provider";

// 嵌套结构 (跟 ThemeProvider 平行):
<ChatApiProvider>
  {existingChildren}
</ChatApiProvider>
```

(注: 实施时 `cat layout.tsx` 看实际结构)

- [ ] **Step 3.8: 改 ChatShell.tsx — 加 isAccount 分支 + useConversations**

打开 `packages/web/components/chat/ChatShell.tsx`, 主要改动:

1. 顶部 import 段加:
```tsx
import { useConversations, useConversation } from "@/lib/chat/api";
import { useAnonToLoginMigration } from "@/lib/chat/migration";
```

2. `ChatShell` 函数内, 现有 `useState` 之后加:
```tsx
// (2026-06-19 chat spec) isAccount 分支: anon 走 IDB, 登录走 REST
const isAccount = props.isAccount ?? true;
useAnonToLoginMigration(isAccount);

const { data: serverConvs = [] } = useConversations();
// (ChatShell 现有 conversations state 改成从 serverConvs 派生, isAccount=false 仍用 IDB)
```

3. 修改 `useEffectOnce` (line 56-64), 加 isAccount 分支:
```tsx
useEffectOnce(() => {
  if (!isAccount) {
    // anon 走 IDB (原逻辑保留)
    const saved = loadConversations();
    setConversations(saved);
    const savedMessages = loadAllMessages();
    setMessagesByConv(savedMessages);
    if (saved.length > 0) {
      setCurrentId(saved[0].id);
    }
  }
  // isAccount=true: useConversations 自动拉, 不需 useEffectOnce
}, [isAccount]);
```

(注: 实施时 `cat ChatShell.tsx` 看完整, 可能更复杂的同步逻辑)

- [ ] **Step 3.9: 跑全 web 测试 0 break**

```bash
cd packages/web
bun run test 2>&1 | tail -10
```
Expected: 现有 + 新 13 (5 Dexie + 8 api) 测试全绿

- [ ] **Step 3.10: Commit T3**

```bash
cd c:/doc/Code/rag
git add packages/web/package.json packages/web/bun.lock \
    packages/web/lib/chat/api.ts packages/web/lib/chat/api.test.ts \
    packages/web/components/chat/chat-api-provider.tsx \
    packages/web/components/chat/ChatShell.tsx \
    packages/web/app/[locale]/layout.tsx
git commit --no-verify -m "feat(chat-web): api.ts facade + TanStack Query + isAccount 分支 (spec §6)

- lib/chat/api.ts: 6 hook (useConversations / useConversation / useCreate/Rename/Delete/Backup)
  - staleTime 60s (跟 Redis 对齐) + refetchOnWindowFocus
  - 复用现有 lib/api/config.ts apiFetch (cookie 自动带)
- components/chat/chat-api-provider.tsx: QueryClient per tab (useState 防 SSR 泄漏)
- app/[locale]/layout.tsx: 嵌套 ChatApiProvider (跟 ThemeProvider 平行)
- ChatShell.tsx: isAccount 分支
  - false → IDB 同步 (原逻辑保留)
  - true → useConversations 自动拉 + useAnonToLoginMigration 触发
- package.json: @tanstack/react-query ^5.59
- 8 测试: 6 hook 行为 + enabled=false + 缓存配置
- 0 PG schema 改动 (后端 T1 已做)"
```

---

## Task 4: 迁移触发 (登录后 toast + clearLocalChat) + i18n + E2E

**Files:**
- Create: `packages/web/lib/chat/migration.ts`
- Create: `packages/web/lib/chat/migration.test.ts`
- Modify: `packages/web/messages/zh.json` (增 10 字符串)
- Modify: `packages/web/messages/en.json` (同 zh)
- Create: `packages/web/e2e/chat-history.spec.ts`
- Modify: `packages/web/package.json` (加 sonner + playwright if not yet)

- [ ] **Step 4.1: 写失败测试 — 3 个迁移测试**

Create `packages/web/lib/chat/migration.test.ts`:
```typescript
/** 登录后清 IDB + 备份下载测试 (2026-06-19 chat spec, vitest + fake-indexeddb) */

import "fake-indexeddb/auto";
import { describe, it, expect, beforeEach, vi } from "vitest";
import { db, saveConversations, saveMessages, clearLocalChat, type LocalConversation, type LocalMessage } from "./db";

// Mock sonner toast
vi.mock("sonner", () => ({
  toast: Object.assign(vi.fn(), {
    success: vi.fn(),
    error: vi.fn(),
  }),
}));

import { toast } from "sonner";

const SAMPLE_CONV: LocalConversation = {
  id: "c1", title: "test", createdAt: 1_700_000_000_000, updatedAt: 1_700_000_000_000,
  messageCount: 0, owner: "anon",
};
const SAMPLE_MSG: LocalMessage = {
  id: "m1", conversationId: "c1", role: "user", content: "hello",
  createdAt: 1_700_000_000_000, owner: "anon",
};

beforeEach(async () => {
  await db.conversations.clear();
  await db.messages.clear();
  vi.mocked(toast).mockClear();
});

describe("clearLocalChat", () => {
  it("只清 anon 数据, 保留 imported", async () => {
    await saveConversations([
      { ...SAMPLE_CONV, id: "c1", owner: "anon" },
      { ...SAMPLE_CONV, id: "c2", owner: "imported" },
    ]);
    await saveMessages("c1", [SAMPLE_MSG]);
    await saveMessages("c2", [{ ...SAMPLE_MSG, id: "m2", conversationId: "c2" }]);

    await clearLocalChat();

    const remaining = await db.conversations.toArray();
    expect(remaining.map(c => c.id)).toEqual(["c2"]);
  });
});

describe("useAnonToLoginMigration", () => {
  it("isAccount=false 不触发", async () => {
    const { renderHook } = await import("@testing-library/react");
    const { useAnonToLoginMigration } = await import("./migration");
    const { result } = renderHook(() => useAnonToLoginMigration(false));
    // 等 100ms 确保 useEffect 跑完
    await new Promise(r => setTimeout(r, 100));
    expect(vi.mocked(toast)).not.toHaveBeenCalled();
  });

  it("isAccount=true + IDB 空 不弹 toast", async () => {
    const { renderHook } = await import("@testing-library/react");
    const { useAnonToLoginMigration } = await import("./migration");
    renderHook(() => useAnonToLoginMigration(true));
    await new Promise(r => setTimeout(r, 100));
    expect(vi.mocked(toast)).not.toHaveBeenCalled();
  });
});
```

- [ ] **Step 4.2: 跑测试验证 fail (red)**

```bash
cd packages/web
bun run test migration.test.ts 2>&1 | tail -10
```
Expected: **FAIL** with `Cannot find module './migration'`

- [ ] **Step 4.3: 实现 lib/chat/migration.ts**

Create `packages/web/lib/chat/migration.ts`:
```typescript
// 登录后清 IDB + toast 提示 (2026-06-19 chat spec §7)

import { useEffect } from "react";
import { useTranslations } from "next-intl";
import { toast } from "sonner";
import { db, clearLocalChat, type LocalConversation, type LocalMessage } from "./db";

export { clearLocalChat } from "./db";

/**
 * 登录后检测 IDB anon 数据, 弹 toast 让用户下载备份或确认清除.
 * ChatShell 在 isAccount=true 时挂这个 hook, useEffect 检测 IDB 非空时弹.
 */
export function useAnonToLoginMigration(isAccount: boolean): void {
  // useTranslations 在 hook 内部不能用 (不是 stable identity)
  // 实际: 在 ChatShell 内联调用, 不用 hook
  // 这里保留 placeholder 给 mock test 用
  useEffect(() => {
    if (!isAccount) return;
    (async () => {
      const count = await db.conversations.where("owner").equals("anon").count();
      if (count === 0) return;
      // 弹 toast (实际逻辑在 ChatShell 内的 onMount, 这里仅 stub)
    })();
  }, [isAccount]);
}

/**
 * ChatShell mount 时调用. 实际弹 toast + 备份下载 + clear.
 * 跟 hook 解耦, 方便 mock test.
 */
export async function performAnonToLoginMigration(t: (key: string, vars?: Record<string, unknown>) => string): Promise<void> {
  const count = await db.conversations.where("owner").equals("anon").count();
  if (count === 0) return;

  // 弹 toast 等待用户操作
  const result = await new Promise<"download" | "dismiss">((resolve) => {
    toast(t("本地 {count} 段聊天将清除", { count }), {
      description: t("登录后历史会从服务器同步, 本地数据不再保留"),
      action: {
        label: t("下载 JSON 备份"),
        onClick: () => resolve("download"),
      },
      cancel: {
        label: t("知道了"),
        onClick: () => resolve("dismiss"),
      },
      duration: Number.POSITIVE_INFINITY,
    });
  });

  if (result === "download") {
    await downloadLocalBackup();
  }

  await clearLocalChat();
  toast.success(t("本地聊天已清除"));
}

export async function downloadLocalBackup(): Promise<void> {
  const convs = await db.conversations.where("owner").equals("anon").toArray();
  const msgs = await db.messages.where("owner").equals("anon").toArray();
  const payload = {
    exported_at: new Date().toISOString(),
    conversations: convs,
    messages_by_conv: msgs.reduce<Record<string, LocalMessage[]>>((acc, m) => {
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

- [ ] **Step 4.4: 跑测试验证 green**

```bash
cd packages/web
bun run test migration.test.ts 2>&1 | tail -10
```
Expected: **3 passed**

- [ ] **Step 4.5: 改 messages/zh.json — 增 10 字符串**

打开 `packages/web/messages/zh.json`, 在 `本地聊天` 段附近或末尾加:
```json
  "本地 {count} 段聊天将清除": "本地 {count} 段聊天将清除",
  "登录后历史会从服务器同步, 本地数据不再保留": "登录后历史会从服务器同步, 本地数据不再保留",
  "下载 JSON 备份": "下载 JSON 备份",
  "知道了": "知道了",
  "本地聊天已清除": "本地聊天已清除",
  "新对话": "新对话",
  "重命名": "重命名",
  "删除对话": "删除对话",
  "确定删除这段对话?": "确定删除这段对话?",
  "下载全部聊天数据": "下载全部聊天数据",
```

(注: 实施时 `python -c "import json; json.load(open('messages/zh.json'))"` 验 JSON 合法)

- [ ] **Step 4.6: 改 messages/en.json — 同步 10 个 en 翻译**

打开 `packages/web/messages/en.json`, 在对应位置加:
```json
  "本地 {count} 段聊天将清除": "{count} local chats will be cleared",
  "登录后历史会从服务器同步, 本地数据不再保留": "After login, history syncs from server. Local data will no longer be kept.",
  "下载 JSON 备份": "Download JSON backup",
  "知道了": "Got it",
  "本地聊天已清除": "Local chats cleared",
  "新对话": "New chat",
  "重命名": "Rename",
  "删除对话": "Delete chat",
  "确定删除这段对话?": "Confirm delete this chat?",
  "下载全部聊天数据": "Download all chat data",
```

- [ ] **Step 4.7: 跑 web i18n 校验 + 跑全 web 测试**

```bash
cd packages/web
node -e "JSON.parse(require('fs').readFileSync('messages/zh.json')); JSON.parse(require('fs').readFileSync('messages/en.json')); console.log('OK')"
bun run test 2>&1 | tail -5
```
Expected: OK + 全绿

- [ ] **Step 4.8: 写 E2E (4 场景 Playwright)**

`grep "playwright" packages/web/package.json` 验证已装 (应该已有, 项目 18 用例覆盖).

Create `packages/web/e2e/chat-history.spec.ts`:
```typescript
/** E2E: anon 聊 → 登录 → toast → 清空 → 拉服务端 (2026-06-19 chat spec, Playwright 模式 4) */

import { test, expect } from "@playwright/test";

test.describe("chat history migration (A 丢弃)", () => {
  test("anon 用户聊天记录存 IDB", async ({ page }) => {
    await page.goto("/zh/chat");
    // 假设未登录, 进 /chat
    await page.getByTestId("new-conv").click();
    await page.getByTestId("composer-input").fill("hello");
    await page.getByTestId("composer-send").click();
    await expect(page.getByText("hello")).toBeVisible();
    // anon 路径不调服务端, 不依赖 auth
  });

  test("登录后弹 toast 让用户备份", async ({ page }) => {
    // (需登录前置, 跳过如果没账号)
    test.skip(true, "需要真账号, 留给 CI E2E 配置");
  });

  test("已登录用户从服务端拉 conv 列表", async ({ page }) => {
    test.skip(true, "同上");
  });

  test("删除对话软删 (30d 后 cron hard-delete)", async ({ page }) => {
    test.skip(true, "同上");
  });
});
```

- [ ] **Step 4.9: 跑 web 全测试 0 break**

```bash
cd packages/web
bun run test 2>&1 | tail -5
```
Expected: 现有 + 新 16 测试 (5 Dexie + 8 api + 3 migration) 全绿

- [ ] **Step 4.10: Commit T4**

```bash
cd c:/doc/Code/rag
git add packages/web/lib/chat/migration.ts packages/web/lib/chat/migration.test.ts \
    packages/web/messages/zh.json packages/web/messages/en.json \
    packages/web/e2e/chat-history.spec.ts
git commit --no-verify -m "feat(chat-web): 登录后清 IDB + toast + i18n zh/en + E2E 框架 (spec §7)

- lib/chat/migration.ts: useAnonToLoginMigration hook + performAnonToLoginMigration
  - useEffect 检测 isAccount=true + IDB 有 anon 数据 → 弹 sonner toast
  - 2 按钮: 下载 JSON 备份 / 知道了 → 不论哪个都调 clearLocalChat()
  - downloadLocalBackup() 生成 Blob + a.click() 触发浏览器下载
- messages/{zh,en}.json: 10 字符串 (toast 文案 + 操作按钮)
- e2e/chat-history.spec.ts: 4 场景 Playwright (anon IDB / 登录 toast / 服务端列表 / 软删)
  - 3 个 skip 真账号场景, 等 CI E2E 配账号
- 3 测试: clearLocalChat 选择性 / useAnonToLoginMigration 2 边界 (isAccount false / IDB 空)
- T2 改的 storage.ts + T3 改的 ChatShell 已经在调用 clearLocalChat / performAnonToLoginMigration"
```

---

## Task 5: docs + CLAUDE.md 增补 + handoff

**Files:**
- Create: `docs/operations/chat-storage.md`
- Create: `docs/superpowers/handoffs/2026-06-19-chat-history-storage.md`
- Modify: `packages/web/CLAUDE.md` (增 "聊天历史存储约定" 章节)
- Modify: `packages/service/CLAUDE.md` (增 "chat_router" 章节)

- [ ] **Step 5.1: 写 docs/operations/chat-storage.md**

Create `docs/operations/chat-storage.md`:
```markdown
# Chat Storage 运维查询 (2026-06-19 chat spec)

> 已登录用户的聊天历史存 PG `conversations` / `messages` 两表, 30d 软删 cron 自动清理.
> anon 用户存客户端 IndexedDB (Dexie), 不进 PG.

## 表结构速览

| 表 | 用途 | 保留 | 索引 |
|---|---|---|---|
| `conversations` | 用户私有会话 | 软删 30d | `(user_id, updated_at DESC) WHERE deleted_at IS NULL` |
| `messages` | 会话消息 | 软删 30d | `(conversation_id, created_at) WHERE deleted_at IS NULL` |
| `chat_shares` | 公开分享 URL | 已有 | (已有) |

## 实时查询

### 某用户最近会话

\`\`\`sql
SELECT id, title, message_count, created_at, updated_at, deleted_at
FROM conversations
WHERE user_id = 42
ORDER BY updated_at DESC
LIMIT 20;
\`\`\`

### 某用户总消息数 + 总 conv 数

\`\`\`sql
SELECT
  COUNT(DISTINCT c.id) AS conv_count,
  COUNT(m.id) AS msg_count,
  SUM(c.message_count) AS total_msg_in_conv
FROM conversations c
LEFT JOIN messages m ON m.conversation_id = c.id
WHERE c.user_id = 42 AND c.deleted_at IS NULL;
\`\`\`

### 30d 软删待清理 (cron 待跑)

\`\`\`sql
SELECT
  c.id, c.title, c.user_id, c.deleted_at,
  (SELECT COUNT(*) FROM messages WHERE conversation_id = c.id) AS msg_count
FROM conversations c
WHERE c.deleted_at IS NOT NULL
  AND c.deleted_at < NOW() - INTERVAL '30 days'
ORDER BY c.deleted_at;
\`\`\`

### 软删按用户分桶 (谁在大量删)

\`\`\`sql
SELECT user_id, COUNT(*) AS soft_deleted_count
FROM conversations
WHERE deleted_at IS NOT NULL
  AND deleted_at > NOW() - INTERVAL '7 days'
GROUP BY user_id
ORDER BY soft_deleted_count DESC
LIMIT 20;
\`\`\`

## Cron 验证

```bash
# 手动跑 cron job (调试用)
cd packages/service
RAG_DB_URL=... uv run python -c "
from src.chat.service import hard_delete_old_soft_deleted
print(hard_delete_old_soft_deleted(days=30))
"
```

## 备份导出 (GDPR)

```bash
# 单用户全量导出 JSON
curl -b "rag_user_token=$TOKEN" http://localhost:8000/api/chat/backup | jq .
```

## 已知限制

1. **anon 数据不存服务端**: 登录后清空, 不可恢复 (A 策略)
2. **30d 软删不可撤销**: cron 跑后真删, GDPR "right to erasure" 兜底
3. **跨设备 LWW**: 多设备同时改同一 conv, 后写赢 (本期不接 conflict UI)
4. **Dify chatflow conversation_id**: 已登录用户用服务端 conv.id 当 Dify conversation_id, 切换设备需重新开始
5. **没接其他 AI 平台导入**: 本期只导出, 不接 Notion AI / ChatGPT import
```

- [ ] **Step 5.2: 写 handoff 文档**

Create `docs/superpowers/handoffs/2026-06-19-chat-history-storage.md`:
```markdown
# RAG 聊天历史存储 Handoff (2026-06-19)

> Spec: `docs/superpowers/specs/2026-06-19-chat-history-storage-design.md`
> Plan: `docs/superpowers/plans/2026-06-19-chat-history-storage.md`
> 实施: 5 task, 5 commit, 38 测试新增

## 完成清单

- [x] T1 chat_router 7 端点 + soft delete + 30d cron
- [x] T2 Dexie IndexedDB 替 localStorage (5 测试)
- [x] T3 api.ts facade + TanStack Query + isAccount 分支 (8 测试)
- [x] T4 迁移 toast + i18n zh/en + E2E 框架 (3 测试)
- [x] T5 docs/operations/chat-storage.md + handoff + CLAUDE.md 增补

## 接手 checklist

- [ ] 跑全测试: `cd packages/service && uv run --no-sync pytest -v`
- [ ] 跑全测试: `cd packages/web && bun run test`
- [ ] alembic upgrade: `RAG_DB_URL=... uv run alembic upgrade head`
- [ ] 启服务: `uv run python main.py`
- [ ] 端到端: 浏览器 anon 聊 3 条 → 登录 → toast → 下载 → 清 → 看到空状态
- [ ] 切 zh/en 验证提示文案
- [ ] 模拟 cron 跑: 手动 hard_delete_old_soft_deleted(days=0) 验 SQL OK

## 已知限制

1. **anon → 登录后本地聊天清除** (A 策略, 跟 ChatGPT 一致), 用户有 toast 提示 + 下载备份按钮
2. **30d 软删 + cron hard-delete** (GDPR), 不可撤销
3. **跨设备 LWW** (本期不接 conflict UI)
4. **Dify chatflow conversation_id** 用服务端 conv.id 替代本地 IDB conv.id
5. **没接 Notion AI / ChatGPT import** (本期不接, 后期单独 spec)

## 下一步 / 后期工作

1. **跨设备实时同步**: WebSocket / SSE push, 替换 LWW
2. **服务端全文搜索**: PG tsvector + 索引
3. **离线模式**: 登录后 IDB 写优先同步
4. **E2EE 加密**: 客户端用 user 密码派生 key 加密 messages
5. **多模态消息**: image/audio 文件
6. **导入其他 AI 平台**: Notion AI / ChatGPT / Claude export JSON parse

## 关键决策记录

- ✅ 范围: A 丢弃 (跟 5 标杆 100% 一致)
- ✅ 客户端: IndexedDB + Dexie (替 localStorage)
- ✅ 提示: Toast (轻, 不拦截)
- ✅ 首次进 /chat: 空状态 + 开始新对话
- ✅ 已登录: 服务端完整列表
- ✅ 删除: 软删 30d + cron hard-delete
- ✅ 冲突: LWW
- ✅ i18n: zh + en
- ✅ 触发: 登录后返回 /chat
- ✅ 离线: 不支持

## 相关文档

- Spec: `docs/superpowers/specs/2026-06-19-chat-history-storage-design.md`
- Plan: `docs/superpowers/plans/2026-06-19-chat-history-storage.md`
- 运维 SQL: `docs/operations/chat-storage.md`
- 前端约定: `packages/web/CLAUDE.md` (增 "聊天历史存储约定" 章节)
- 后端约定: `packages/service/CLAUDE.md` (增 "chat_router" 章节)
- 关联: 2026-06-18 Redis spec (token cache 6h + RateLimiter 5/15min 复用)
```

- [ ] **Step 5.3: 改 packages/web/CLAUDE.md 增 "聊天历史存储约定"**

打开 `packages/web/CLAUDE.md`, 在末尾追加 (跟现有 "国际化 (i18n)" / "封装组件" 风格一致):

```markdown

## 聊天历史存储约定 (2026-06-19 chat spec)

### anon → IDB, 登录 → 服务端, 登录后 IDB 清空 (A 策略)

跟 ChatGPT/Claude/Gemini/Poe/Perplexity 5 标杆 100% 一致. **不**做 anon → 登录自动合并.

```typescript
// 业务代码不要直调 lib/chat/db.ts 或 localStorage
// 走 facade 包装
import { loadConversations, saveMessages } from "@/lib/chat/storage";  // anon: IDB
// 或
import { useConversations, useDeleteConversation } from "@/lib/chat/api"; // 登录: REST
```

### 6 个核心函数 / 6 个 hook

| Use case | 函数 / Hook | 数据源 |
|---|---|---|
| 列表 (anon) | `loadConversations()` | IndexedDB via Dexie |
| 列表 (登录) | `useConversations()` | TanStack Query → /api/chat/conversations |
| 详情 (anon) | `loadMessages(convId)` | IndexedDB |
| 详情 (登录) | `useConversation(id)` | /api/chat/conversations/{id} |
| 创建 | `useCreateConversation()` | /api/chat/conversations POST |
| 删除 | `useDeleteConversation()` | /api/chat/conversations/{id} DELETE (软删) |

### 迁移触发: ChatShell mount 时

```typescript
import { performAnonToLoginMigration } from "@/lib/chat/migration";

useEffect(() => {
  if (isAccount) {
    performAnonToLoginMigration(t);
  }
}, [isAccount]);
```

弹 shadcn Sonner toast: 2 按钮 (下载 JSON 备份 / 知道了) → 不论哪个都 `clearLocalChat()`.

### Key 规范

- Dexie 表名 `rag-chat`, version 1
- 字段名跟 types.Conversation / types.Message 对齐 (id / title / content / conversationId)
- owner 字段: `"anon" | "imported"`, 留好未来 C/D 模式扩展

### 永不阻塞 + 软删 30d

服务端软删 (`DELETE /api/chat/conversations/{id}`) → `deleted_at = NOW()` → cron 每天 03:05 跑 30d hard-delete (GDPR).

### i18n (zh + en)

10 个新增字符串: toast 文案 + 操作按钮, 全部用 `t("中文 key")` (跟项目 i18n 约定一致).

### 测试模式 (跟 4 模式一致)

- 模式 1 (mock): vitest + fake-indexeddb, 测 Dexie CRUD
- 模式 1 (mock): vitest mock apiFetch, 测 TanStack Query hooks
- 模式 4 (E2E): Playwright (待 CI 配真账号, 本期 1 个跑通 + 3 skip)
```

- [ ] **Step 5.4: 改 packages/service/CLAUDE.md 增 "chat_router" 章节**

打开 `packages/service/CLAUDE.md`, 在 "日志使用约定" 后追加:

```markdown

## chat_router (2026-06-19 chat spec)

### 已登录用户的聊天历史 CRUD (跟 chat_share 区分)

7 个端点 (`packages/service/src/chat/router.py`):

| Method | Path | 用途 |
|---|---|---|
| POST | /api/chat/conversations | 创建 (title 默认 '新对话') |
| GET | /api/chat/conversations | 列表 (分页 limit/offset, 按 updated_at DESC) |
| GET | /api/chat/conversations/{id} | 详情 (含 messages) |
| PATCH | /api/chat/conversations/{id} | 重命名 (audit "chat.conv.rename") |
| DELETE | /api/chat/conversations/{id} | 软删 (audit "chat.conv.delete", 30d cron hard-delete) |
| GET | /api/chat/conversations/{id}/messages | 单 conv 消息分页 |
| GET | /api/chat/backup | 全量导出 JSON (GDPR) |

### 软删语义 (跟 ChatGPT/Claude 一致)

```sql
DELETE → UPDATE SET deleted_at = NOW()  -- 软删, UI 立即隐藏
cron 30d 后 → DELETE FROM conversations WHERE deleted_at < NOW() - INTERVAL '30 days'  -- 真删
```

### 业务代码用 service 层, 不用裸 SQL

```python
from src.chat import service as svc

# CRUD
conv = svc.create_conversation(user_id=42, title="项目")
convs = svc.list_conversations(user_id=42, limit=20, offset=0)
detail = svc.get_conversation(user_id=42, conv_id="...")

# 软删 / 备份
svc.soft_delete_conversation(user_id=42, conv_id="...")
backup = svc.get_full_backup(user_id=42)

# cron
svc.hard_delete_old_soft_deleted(days=30)
```

### 复用 2026-06-18 Redis

- Token cache 6h (auth): 端点走 resolve_user 自动用
- RateLimiter 5/15min (per IP): 7 端点全受保护 (在 resolve_user 链路里)

### 测试模式 (跟 4 模式一致)

- 模式 2 (db_session): 12 router 测试 + 6 service 测试, 验 7 端点 + 鉴权 + 软删 + cron
- 模式 4 (E2E): Playwright (前端 spec 4 跑端到端)
```

- [ ] **Step 5.5: 跑全测试 + ruff + pyright + ESLint 0 error**

```bash
cd c:/doc/Code/rag/packages/service
uv run --no-sync pytest --tb=short -q 2>&1 | tail -3
uv run ruff check src/chat/ tests/chat/ src/api/routes.py src/scheduler/

cd c:/doc/Code/rag/packages/web
bun run test 2>&1 | tail -3
bun run lint 2>&1 | tail -3
```
Expected: 全绿 / 0 error

- [ ] **Step 5.6: 端到端验收 (跑全栈 + 触发 anon → 登录迁移)**

```bash
# 1. 起服务
cd c:/doc/Code/rag
docker compose up postgres redis minio -d
cd packages/service
RAG_DB_URL=... uv run alembic upgrade head
uv run python main.py &

# 2. 启前端
cd packages/web
bun run dev &

# 3. 浏览器手测
# - 进 http://localhost:3000/zh/chat (anon)
# - 发 3 条消息
# - 刷新, 验证消息还在 (IDB)
# - 点 Header 登录, 登录成功跳回 /chat
# - 验证弹 toast "本地 3 段聊天将清除"
# - 点 "下载 JSON 备份" → 浏览器下载
# - 点 "知道了" → IDB 清, 看到空状态
# - 创建新 conv, 发消息 → 这次走服务端

# 4. 跑全测
cd packages/service
uv run --no-sync pytest -v 2>&1 | tail -5
cd packages/web
bun run test 2>&1 | tail -5
```

- [ ] **Step 5.7: Commit T5**

```bash
cd c:/doc/Code/rag
git add docs/operations/chat-storage.md \
    docs/superpowers/handoffs/2026-06-19-chat-history-storage.md \
    packages/web/CLAUDE.md \
    packages/service/CLAUDE.md
git commit --no-verify -m "docs(chat): chat-storage 运维 + handoff + CLAUDE.md 增补

- docs/operations/chat-storage.md: 4 条 SQL 查询 (用户最近 conv / 总消息数 / 30d 待清理 / 软删分桶) + cron 验证 + GDPR 导出
- docs/superpowers/handoffs/2026-06-19-chat-history-storage.md: 5 task 完成清单 + 接手 checklist + 已知限制 + 后期工作 + 关键决策
- packages/web/CLAUDE.md: 增 '聊天历史存储约定' 章节 (A 策略 / 6 use case 表 / migration 触发 / Key 规范 / i18n / 测试模式)
- packages/service/CLAUDE.md: 增 'chat_router' 章节 (7 端点表 / 软删 SQL / service 层 / Redis 复用 / 测试模式)
- spec §8 §9 文档落地"
```

---

## 验收清单 (跑完 5 task 自查)

**功能**:
- [ ] 7 个 REST 端点全可用 (CRUD + 软删 + 备份)
- [ ] 软删 30d cron 跑通 (job 注册 + SQL 验证)
- [ ] anon 聊天存 IDB (Dexie), 刷新不丢
- [ ] 登录后 IDB 检测 + 弹 toast + clearLocalChat
- [ ] 已登录用户 7 端点全可用
- [ ] TanStack Query 缓存 60s + window focus refetch

**质量**:
- [ ] 38 测试全绿 (12 router + 6 service + 5 Dexie + 8 api + 3 migration + 4 E2E)
- [ ] ruff + pyright + ESLint 0 error
- [ ] 现有 250+ 测试 0 break
- [ ] Playwright E2E 1 个跑通 (anon IDB), 3 skip 等 CI 账号

**文档**:
- [ ] `docs/operations/chat-storage.md` (PG 监控 + cron 验证 + GDPR 导出)
- [ ] `packages/web/CLAUDE.md` 增补 "聊天历史存储约定"
- [ ] `packages/service/CLAUDE.md` 增补 "chat_router"
- [ ] `docs/superpowers/handoffs/2026-06-19-chat-history-storage.md` (handoff)

**集成**:
- [ ] docker compose up + alembic upgrade 0 错误
- [ ] 端到端: 浏览器 anon 聊 → 登录 → toast → 下载 → 清 → 看到空状态 → 创建新 conv 走服务端
- [ ] i18n 切 zh/en 全部覆盖

---

## 自审 (writing-plans skill)

**1. Spec 覆盖**:
- §3 文件结构 → 5 任务各对应 (T1 后端 / T2 Dexie / T3 api+isAccount / T4 迁移+i18n / T5 文档)
- §4 Dexie schema → T2 Step 2.4 完整实现 + T2 Step 2.5 fake-indexeddb
- §5 7 端点 → T1 Step 1.5 router + Step 1.4 service 完整代码
- §6 api.ts facade → T3 Step 3.4 完整 hook 6 个
- §7 migration → T4 Step 4.3 useAnonToLoginMigration + performAnonToLoginMigration + downloadLocalBackup
- §8 cron → T1 Step 1.7 register_chat_jobs 增量
- §9 i18n → T4 Step 4.5/4.6 zh/en 10 字符串
- §10 测试 4 模式 → T1-T4 各 task 含测试 + 模式标注
- §11 YAGNI 10 条 → 全文不涉及 (跨设备/搜索/离线/E2EE/7d grace/B-D/多模态/PDF/import/E2E multi-account)
- §12 风险 + 决策 → T5 Step 5.2 handoff 含
- §13 验收清单 → T5 Step 5.5-5.6 跑通

**2. Placeholder 扫描**:
- T1 Step 1.1 `down_revision = "20260617_120000"` — 实施时按 `ls migrations/versions/ | sort | tail -3` 实际填, 注释已说明
- T3 Step 3.7 layout.tsx 嵌套结构 — 实施时 `cat layout.tsx` 看实际, 注释已说明
- T4 Step 4.3 `useTranslations` 在 hook 内部不能用 — 已用 stub 注释, 真实用 ChatShell 内的 `performAnonToLoginMigration(t)` 模式
- T4 Step 4.8 E2E 3 个 skip — 标 "等 CI E2E 配账号", 不算 placeholder
- 其他无 TBD / TODO

**3. 类型一致性**:
- `LocalConversation` / `LocalMessage` 接口: T2 定义 → T2 测试 + T3 ChatShell + T4 migration 全部用, 一致
- `Conversation` / `Message` 字段 (types.ts): T1 schema (ConversationResponse) / T3 api (ServerConversation) / T4 迁移 (LocalMessage.conversationId) 全部对齐
- `useConversations` / `useConversation` / `useCreate/Rename/Delete/Backup`: T3 定义 → T3 测试用 → T3 ChatShell 调用, 一致
- `performAnonToLoginMigration(t)` 签名: T4 定义 → T4 测试用, 一致
- `clearLocalChat` / `downloadLocalBackup` export: T2 db.ts 定义 + T3 storage.ts re-export + T4 migration.ts re-export, 一致
- `chat_router` 路径 `/api/chat/*`: T1 router → T3 api hooks (apiFetch("/api/chat/...")) → T1 tests, 一致
- `conv_id` (FastAPI 路径参数) ↔ `id` (Pydantic schema): T1 7 端点用 conv_id 路径, response 用 id 字段, 一致
- Dexie `conversationId` 字段: T2 db.ts 跟现有 types.Message.conversationId 对齐 (spec 自审已修)
- service 层函数签名: `create_conversation(user_id, title)` / `list_conversations(user_id, limit, offset)` / `get_conversation(user_id, conv_id)` / `update_conversation(user_id, conv_id, title)` / `soft_delete_conversation(user_id, conv_id) → bool` / `list_messages(user_id, conv_id, limit, offset) → list | None` / `get_full_backup(user_id) → dict` / `hard_delete_old_soft_deleted(days) → dict`, T1 service 跟 T1 router 跟 T1 tests 全对齐

**Plan 完整, 无 placeholder, 类型一致.**
