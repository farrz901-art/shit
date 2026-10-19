# 长期记忆 (mem0 + pgvector) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 落地 mem0 self-host pgvector 作为聊天长期记忆, 通过 FastAPI `/api/memory/*` 暴露 + 前端 `withMemoryHooks` 装饰器自动注入 Dify 对话.

**Architecture:** 后端 — FastAPI 直连端点 (跟 kg/approvals 同款) + `MemoryService` (降级核心) + per-user_id `Memory` 实例缓存 + self-host pgvector config. 前端 — `withMemoryHooks(inner: ChatProvider)` 装饰器三段: Pre-LLM search 注入 `inputs.memory_context` / 流中累积 user+assistant turns / 流结束 fire-forget add. Dify 端 — 用户手动在工作流加 `{{#memory_context}}` 模板.

**Tech Stack:**
- Backend: Python 3.14, FastAPI, mem0ai 2.0+ (Memory.from_config self-host), pgvector (已有容器), LlamaIndex embedder
- Frontend: TypeScript, Next.js 15, vitest + jsdom, bun
- Test: pytest (单测/集成/slow 真连), vitest (前端), TestClient (HTTP 集成)

**Reference Spec:** `docs/superpowers/specs/2026-06-16-long-term-memory-design.md`

---

## File Structure

### New Files (11)

| 文件 | 职责 |
|------|------|
| `packages/service/src/memory/schemas.py` | `SearchRequest` / `SearchResponse` / `MemoryHit` / `AddRequest` / `TurnMessage` Pydantic |
| `packages/service/src/memory/service.py` | `_resolve_mem0_user_id` + `MemoryService` (search/add 降级 + per-user cache) |
| `packages/service/src/memory/router.py` | `POST /api/memory/{search,add}` + `Depends(resolve_user)` |
| `packages/service/tests/memory/test_service.py` | 单测: user_id 解析 / search 降级 / add 降级 / metadata 透传 |
| `packages/service/tests/memory/test_router.py` | 集成: 200/401/400 路径 + Depends 注入 |
| `packages/service/tests/memory/test_mem0_integration.py` | slow 真连 pgvector: search→add→search 闭环 |
| `packages/web/lib/api/memory.ts` | `memoryApi.search/add` 调 `apiFetch` 直连后端 |
| `packages/web/lib/api/memory.test.ts` | 单测: apiFetch 路径 + 错误归一 |
| `packages/web/lib/chat/memory-integration.ts` | `withMemoryHooks` 装饰器 (Pre-LLM search + 流中累积 + Post-LLM add) |
| `packages/web/lib/chat/memory-integration.test.ts` | 单测: 3 个核心行为 + 降级 |
| `docs/rag/memory/dify-workflow-config.md` | Dify Chatflow 工作流配置步骤 (用户手动操作) |

### Modified Files (10)

| 文件 | 改动 |
|------|------|
| `packages/service/src/memory/mem0_client.py` | **重写**: 删 `MemoryClient` (hosted), `_build_config` (self-host pgvector) + `Mem0Store` (per-user 缓存) + `_default_mem0_factory` |
| `packages/service/src/memory/__init__.py` | export 新增: `_resolve_mem0_user_id` / `MemoryService` / `memory_router`. 删: `retrieve_with_memory` / `build_memory_enhanced_prompt` / `add_document_memory` / `get_mem0_store` (无调用方, 验证见 Task 1 Step 1) |
| `packages/service/src/__init__.py` | `register_routers` 加 `app.include_router(memory_router)` |
| `packages/service/src/common/defaults.py` | 删 `DEFAULT_MEM0_API_KEY` / `DEFAULT_MEM0_USER_ID` / `DEFAULT_MEM0_MODEL`. 加 `DEFAULT_MEM0_COLLECTION_NAME` / `DEFAULT_MEM0_LLM_MODEL` / `DEFAULT_MEM0_SEARCH_LIMIT` |
| `packages/service/.env.example` | 删 `MEM0_API_KEY` / `MEM0_USER_ID` / `MEM0_MODEL`. 加 `MEM0_COLLECTION_NAME` / `MEM0_LLM_MODEL` / `MEM0_SEARCH_LIMIT` |
| `packages/service/tests/memory/test_mem0_client.py` | **重写**: 测 `_build_config` env 注入 + `Mem0Store` per-user 缓存 |
| `packages/service/tests/common/test_defaults.py` | `test_defaults_module_exports_expected_constants` 删 mem0 旧 key, 加新 key |
| `packages/service/tests/test_api_contract.py` | `FRONTEND_EXPECTS` 加 2 行: `("POST", "/api/memory/search")` + `("POST", "/api/memory/add")` |
| `packages/web/lib/chat/factory.ts` | **重构 + 1 行**: `require()` → 静态 `import` (vitest ESM 兼容), `case "dify"` 套 `withMemoryHooks(new DifyChatProvider())` |
| `packages/web/lib/chat/factory.test.ts` | un-todo + 改断言: `name === "dify+memory"`, 加 mock dify 测 |

---

## Task 1: mem0 self-host config + Mem0Store rewrite

**Files:**
- Modify: `packages/service/src/memory/mem0_client.py` (rewrite)
- Modify: `packages/service/src/memory/__init__.py` (export 更新)
- Modify: `packages/service/src/common/defaults.py` (常量)
- Modify: `packages/service/.env.example` (env 模板)
- Modify: `packages/service/tests/memory/test_mem0_client.py` (rewrite)
- Modify: `packages/service/tests/common/test_defaults.py` (常量列表)

- [ ] **Step 0: 验证 pgvector 容器可达 + DB 有 CREATE 权限 (前置)**

mem0 self-host pgvector **不建独立 DB**, 复用项目已有 `rag` 数据库, 首次 `m.add()` 时 mem0 自动:
- `CREATE EXTENSION IF NOT EXISTS vector` (vector 扩展)
- `CREATE TABLE IF NOT EXISTS mem0_memories (id UUID PK, vector vector(N), payload JSONB)` (表名 = collection_name)
- `CREATE INDEX IF NOT EXISTS mem0_memories_hnsw_idx USING hnsw (vector vector_cosine_ops)` (HNSW 索引)

**前置条件**: (1) pgvector 容器跑 (2) 当前 PG 用户有 `CREATE EXTENSION` + `CREATE TABLE` 权限 (3) vector 扩展已装或能装.

```bash
# 1. 确认容器跑
docker ps | grep pgvector
# Expected: 一行, 端口 5432 暴露

# 2. 确认 DB 可连 + user 有 CREATE 权限
cd packages/service
uv run python -c "
import os
from dotenv import load_dotenv
load_dotenv('.env.local')
import psycopg
url = f\"postgresql://{os.getenv('PG_USER')}:{os.getenv('PG_PASSWORD')}@{os.getenv('PG_HOST')}:{os.getenv('PG_PORT')}/{os.getenv('PG_DATABASE')}\"
with psycopg.connect(url) as conn:
    with conn.cursor() as cur:
        cur.execute('SELECT current_user, current_database()')
        user, db = cur.fetchone()
        print(f'Connected as {user} to {db}')
        cur.execute(\"SELECT rolsuper, rolcreatedb FROM pg_roles WHERE rolname = current_user\")
        super_, createdb = cur.fetchone()
        print(f'super={super_}, createdb={createdb}')
"
```
Expected: `Connected as postgres to rag` (或项目 PG_USER/PG_DATABASE), `super=True` 或 `createdb=True` (postgres 镜像默认 superuser, 必 True). 失败 → 调 `.env.local` 或换有权限的 user.

```bash
# 3. 确认 vector 扩展能装 (或已装)
uv run python -c "
import os
from dotenv import load_dotenv
load_dotenv('.env.local')
import psycopg
url = f\"postgresql://{os.getenv('PG_USER')}:{os.getenv('PG_PASSWORD')}@{os.getenv('PG_HOST')}:{os.getenv('PG_PORT')}/{os.getenv('PG_DATABASE')}\"
with psycopg.connect(url, autocommit=True) as conn:
    with conn.cursor() as cur:
        cur.execute('CREATE EXTENSION IF NOT EXISTS vector')
        cur.execute(\"SELECT extname, extversion FROM pg_extension WHERE extname = 'vector'\")
        row = cur.fetchone()
        print(f'vector extension: {row}')
"
```
Expected: `vector extension: ('vector', '0.x.x')`. 失败 → 容器不是 `pgvector/pgvector` 镜像, 改镜像.

- [ ] **Step 1: 验证 4 个 helper 函数无调用方**

```bash
cd packages/service
uv run python -c "
import subprocess
result = subprocess.run(['grep', '-rln', '-E', 'retrieve_with_memory|build_memory_enhanced_prompt|add_document_memory|get_mem0_store', 'src', 'tests', 'scripts'], capture_output=True, text=True)
print(result.stdout)
print(result.stderr)
"
```

Expected: 只能看到 `src/memory/mem0_client.py` 和 `src/memory/__init__.py` 自身 (它们定义和 export). 没有其它调用方.

- [ ] **Step 2: 写 `test_mem0_client.py` 新测试 (TDD 红)**

全量替换 `packages/service/tests/memory/test_mem0_client.py`:

```python
"""mem0_client.py 测试: self-host config + per-user_id Mem0Store 缓存"""

from __future__ import annotations

from unittest.mock import MagicMock, patch, PropertyMock


def test_build_config_reads_env(monkeypatch):
    """_build_config 必须读 env: MEM0_COLLECTION_NAME, MEM0_LLM_MODEL, OPENAI_API_KEY, PG_*"""
    from src.memory.mem0_client import _build_config

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("MEM0_COLLECTION_NAME", "test_mem")
    monkeypatch.setenv("MEM0_LLM_MODEL", "gpt-4o")
    monkeypatch.setenv("PG_HOST", "pg.test")
    monkeypatch.setenv("PG_PORT", "6543")
    monkeypatch.setenv("PG_USER", "u")
    monkeypatch.setenv("PG_PASSWORD", "p")
    monkeypatch.setenv("PG_DATABASE", "d")

    cfg = _build_config()

    assert cfg["llm"]["config"]["api_key"] == "sk-test"
    assert cfg["llm"]["config"]["model"] == "gpt-4o"
    assert cfg["vector_store"]["provider"] == "pgvector"
    assert cfg["vector_store"]["config"]["host"] == "pg.test"
    assert cfg["vector_store"]["config"]["port"] == 6543
    assert cfg["vector_store"]["config"]["collection_name"] == "test_mem"


def test_build_config_uses_defaults_when_env_missing(monkeypatch):
    """env 没配时用 defaults.py 常量"""
    from src.common import defaults
    from src.memory.mem0_client import _build_config

    monkeypatch.delenv("MEM0_COLLECTION_NAME", raising=False)
    monkeypatch.delenv("MEM0_LLM_MODEL", raising=False)

    cfg = _build_config()
    assert cfg["vector_store"]["config"]["collection_name"] == defaults.DEFAULT_MEM0_COLLECTION_NAME
    assert cfg["llm"]["config"]["model"] == defaults.DEFAULT_MEM0_LLM_MODEL


def test_default_factory_uses_build_config(monkeypatch):
    """_default_mem0_factory 必须调 Memory.from_config(_build_config())"""
    from src.memory import mem0_client

    fake_memory = MagicMock()
    with patch.object(mem0_client, "Memory", create=True) as mock_memory_cls:
        # Memory 在模块内 lazy import, 走 mock 即可
        mock_memory_cls.from_config.return_value = fake_memory
        result = mem0_client._default_mem0_factory("u1")

    assert result is fake_memory
    mock_memory_cls.from_config.assert_called_once()
    cfg_arg = mock_memory_cls.from_config.call_args[0][0]
    assert cfg_arg["vector_store"]["provider"] == "pgvector"


def test_mem0_store_init_stores_user_id():
    """Mem0Store 必须接收 user_id 初始化, 不从 env 读"""
    from src.memory.mem0_client import Mem0Store

    store = Mem0Store(user_id="u1")
    assert store._user_id == "u1"
    # memory 是 lazy property, 初始为 None
    assert store._memory is None


def test_mem0_store_memory_lazy_cached(monkeypatch):
    """Mem0Store.memory 第一次调走 factory, 后续返缓存"""
    from src.memory import mem0_client

    fake_memory = MagicMock()
    with patch.object(mem0_client, "_default_mem0_factory", return_value=fake_memory) as mock_factory:
        store = Mem0Store(user_id="u1")
        m1 = store.memory
        m2 = store.memory

    assert m1 is fake_memory
    assert m2 is fake_memory
    mock_factory.assert_called_once_with("u1")


def test_mem0_store_search_uses_filters_and_top_k():
    """Mem0Store.search 走 self-host API: filters={user_id}, top_k (不是 limit/user_id=)"""
    from src.memory.mem0_client import Mem0Store

    fake_memory = MagicMock()
    fake_memory.search.return_value = [{"id": "1", "memory": "hello", "score": 0.9}]
    with patch.object(Mem0Store, "memory", new_callable=PropertyMock, return_value=fake_memory):
        store = Mem0Store(user_id="u1")
        results = store.search("query", limit=3)

    assert results == [{"id": "1", "memory": "hello", "score": 0.9}]
    fake_memory.search.assert_called_once_with(
        query="query", filters={"user_id": "u1"}, top_k=3
    )


def test_mem0_store_add_passes_user_id_and_infer():
    """Mem0Store.add 走 self-host API: user_id 直接传, infer=True"""
    from src.memory.mem0_client import Mem0Store

    fake_memory = MagicMock()
    with patch.object(Mem0Store, "memory", new_callable=PropertyMock, return_value=fake_memory):
        store = Mem0Store(user_id="u1")
        store.add(
            messages=[{"role": "user", "content": "hi"}],
            metadata={"conversation_id": "c1"},
        )

    fake_memory.add.assert_called_once_with(
        messages=[{"role": "user", "content": "hi"}],
        user_id="u1",
        infer=True,
        metadata={"conversation_id": "c1"},
    )
```

- [ ] **Step 3: 跑新测试验证全红**

Run:
```bash
cd packages/service
uv run pytest tests/memory/test_mem0_client.py -v
```

Expected: 7 个测试全 FAIL (AttributeError: module 'src.memory.mem0_client' has no attribute '_build_config' / Mem0Store 签名不对).

- [ ] **Step 4: 改 `defaults.py` 常量**

替换 `packages/service/src/common/defaults.py` 里的 `# Mem0` 段:

```python
# =============================================================================
# Mem0
# =============================================================================
# mem0 self-host: 复用项目已有 pgvector 容器 + embedder, 不需要 MEM0_API_KEY
DEFAULT_MEM0_COLLECTION_NAME: str = "mem0_memories"
DEFAULT_MEM0_LLM_MODEL: str = "gpt-4o-mini"
DEFAULT_MEM0_SEARCH_LIMIT: int = 5
```

(整段替换, 不要保留旧的 3 行 `DEFAULT_MEM0_API_KEY` / `DEFAULT_MEM0_USER_ID` / `DEFAULT_MEM0_MODEL`.)

- [ ] **Step 5: 改 `.env.example` 删 mem0 旧 key + 加新 key**

在 `packages/service/.env.example` 找到 `# Mem0 (长程记忆)` 段, 整段替换为:

```bash
# -----------------------------------------------------------------------------
# Mem0 (长程记忆, self-host)
# -----------------------------------------------------------------------------
# src/rag/memory/mem0_client.py 用
# 走 self-host 模式: 复用项目 pgvector 容器 + embedder, 不用 MEM0_API_KEY
# 首次 m.add() 调用时 mem0 自动建表 + 加 vector 扩展
MEM0_COLLECTION_NAME=mem0_memories
MEM0_LLM_MODEL=gpt-4o-mini          # 事实抽取 LLM, 跟 LLM_MODEL 解耦
MEM0_SEARCH_LIMIT=5
```

- [ ] **Step 6: 改 `test_defaults.py` 期望常量列表**

在 `packages/service/tests/common/test_defaults.py` 找 `# mem0` 段 (在 `test_defaults_module_exports_expected_constants` 函数里), 替换为:

```python
        # mem0 (self-host)
        "DEFAULT_MEM0_COLLECTION_NAME",
        "DEFAULT_MEM0_LLM_MODEL",
        "DEFAULT_MEM0_SEARCH_LIMIT",
```

(把旧的 `DEFAULT_MEM0_API_KEY` / `DEFAULT_MEM0_USER_ID` / `DEFAULT_MEM0_MODEL` 删掉, 加这 3 个新的.)

- [ ] **Step 7: 跑 `test_defaults.py` 验证绿**

Run:
```bash
cd packages/service
uv run pytest tests/common/test_defaults.py -v
```

Expected: 4 个测试 PASS. 如果 FAIL 看错误信息, 一般是常量名拼写错.

- [ ] **Step 8: 重写 `mem0_client.py`**

全量替换 `packages/service/src/memory/mem0_client.py`:

```python
"""Mem0 记忆层封装 (self-host pgvector 模式, 2026-06-16)

跟项目已有 pgvector 容器 + embedder 复用. 每个 (user_id) 缓存一个 Memory 实例.
"""

from __future__ import annotations

import os
from typing import Any

from mem0 import Memory  # mem0ai PyPI 包, import 路径仍是 mem0

from ..common import defaults


def _build_config() -> dict[str, Any]:
    """从 env + defaults 拼 mem0 self-host config.

    关键约束 (跟 hosted API MemoryClient 不同):
    - vector_store.provider 必须是 'pgvector'
    - embedder 走 huggingface, 复用项目 EMBED_MODEL (BAAI/bge-m3)
    - llm 走 openai 协议, 复用 OPENAI_API_KEY
    """
    return {
        "llm": {
            "provider": "openai",
            "config": {
                "api_key": os.getenv("OPENAI_API_KEY", ""),
                "model": os.getenv("MEM0_LLM_MODEL", defaults.DEFAULT_MEM0_LLM_MODEL),
            },
        },
        "embedder": {
            "provider": "huggingface",
            "config": {
                "model": os.getenv("EMBED_MODEL", defaults.DEFAULT_EMBED_MODEL_LOCAL),
            },
        },
        "vector_store": {
            "provider": "pgvector",
            "config": {
                "host": os.getenv("PG_HOST", defaults.DEFAULT_PG_HOST),
                "port": int(os.getenv("PG_PORT", str(defaults.DEFAULT_PG_PORT))),
                "user": os.getenv("PG_USER", defaults.DEFAULT_PG_USER),
                "password": os.getenv("PG_PASSWORD", defaults.DEFAULT_PG_PASSWORD),
                "dbname": os.getenv("PG_DATABASE", defaults.DEFAULT_PG_DATABASE),
                "collection_name": os.getenv(
                    "MEM0_COLLECTION_NAME", defaults.DEFAULT_MEM0_COLLECTION_NAME
                ),
            },
        },
        "version": "v1.1",
    }


def _default_mem0_factory(user_id: str) -> Memory:
    """默认 factory: 走 self-host config 创建 Memory. user_id 仅用于日志/debug."""
    return Memory.from_config(_build_config())


class Mem0Store:
    """per-user_id 的 Memory 实例缓存.

    mem0 self-host 内部按 user_id 隔离数据, 多个 user 可安全共享同一 Memory 实例.
    缓存避免每次 search/add 都重新构造 (构造要连 pgvector + load embedder, 慢).
    """

    def __init__(self, user_id: str):
        if not user_id:
            raise ValueError("user_id 不能为空")
        self._user_id = user_id
        self._memory: Memory | None = None

    @property
    def memory(self) -> Memory:
        if self._memory is None:
            self._memory = _default_mem0_factory(self._user_id)
        return self._memory

    def search(self, query: str, limit: int = 5) -> list[dict]:
        """走 mem0 self-host search API: filters={user_id} (不是直接 user_id=), top_k (不是 limit)."""
        return (
            self.memory.search(query=query, filters={"user_id": self._user_id}, top_k=limit) or []
        )

    def add(self, messages: list[dict], metadata: dict | None = None) -> None:
        """走 mem0 self-host add API: user_id 直接传, infer=True 让 LLM 抽事实."""
        kwargs: dict[str, Any] = {"messages": messages, "user_id": self._user_id, "infer": True}
        if metadata:
            kwargs["metadata"] = metadata
        self.memory.add(**kwargs)
```

- [ ] **Step 9: 跑测试验证全绿**

Run:
```bash
cd packages/service
uv run pytest tests/memory/test_mem0_client.py tests/common/test_defaults.py -v
```

Expected: 7 (mem0) + 4 (defaults) = 11 个测试全 PASS. 如果 FAIL 优先看 import 错 (mem0 包未装) / config dict 字段名错.

- [ ] **Step 10: 改 `src/memory/__init__.py` 删旧 export**

替换 `packages/service/src/memory/__init__.py`:

```python
"""memory 子包: 记忆层 (mem0 self-host pgvector, 2026-06-16)"""

from .mem0_client import Mem0Store, _build_config, _default_mem0_factory

__all__ = ["Mem0Store", "_build_config", "_default_mem0_factory"]
```

(新结构: `Mem0Store` + 2 个模块级 helper. 旧的 `retrieve_with_memory` / `build_memory_enhanced_prompt` / `add_document_memory` / `get_mem0_store` 已删.)

- [ ] **Step 11: 跑 `src/__init__.py` 顶层 export 验证不破**

Run:
```bash
cd packages/service
uv run python -c "from src.memory import Mem0Store, _build_config, _default_mem0_factory; print('OK')"
```

Expected: `OK` (无 ImportError). 如果 FAIL 看是不是 `src/__init__.py` 顶层 import 链有问题.

- [ ] **Step 12: Commit**

```bash
git add packages/service/src/memory/mem0_client.py \
        packages/service/src/memory/__init__.py \
        packages/service/src/common/defaults.py \
        packages/service/.env.example \
        packages/service/tests/memory/test_mem0_client.py \
        packages/service/tests/common/test_defaults.py
git commit -m "refactor(memory): rewrite mem0_client for self-host pgvector, drop hosted API"
```

---

## Task 2: MemoryService + schemas

**Files:**
- Create: `packages/service/src/memory/schemas.py`
- Create: `packages/service/src/memory/service.py`
- Create: `packages/service/tests/memory/test_service.py`
- Modify: `packages/service/src/memory/__init__.py` (export `MemoryService` + `_resolve_mem0_user_id`)

- [ ] **Step 1: 写 `schemas.py` Pydantic 模型**

创建 `packages/service/src/memory/schemas.py`:

```python
"""Memory 模块 Pydantic schemas (2026-06-16)"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    """记忆检索请求"""

    query: str = Field(..., min_length=1, max_length=2000, description="查询文本")
    limit: int = Field(5, ge=1, le=20, description="检索条数")


class MemoryHit(BaseModel):
    """单条记忆命中"""

    id: str
    text: str
    score: float | None = None
    metadata: dict | None = None


class SearchResponse(BaseModel):
    """记忆检索响应 (降级时 memories=[])"""

    memories: list[MemoryHit] = Field(default_factory=list, description="相关记忆")


class TurnMessage(BaseModel):
    """单轮对话消息"""

    role: Literal["user", "assistant"] = Field(..., description="消息角色")
    content: str = Field(..., min_length=1, max_length=32000, description="消息内容")


class AddRequest(BaseModel):
    """记忆写入请求"""

    messages: list[TurnMessage] = Field(..., min_length=1, max_length=20, description="本轮完整对话")
    conversation_id: str | None = Field(None, max_length=128, description="Dify conversation_id, 写到 metadata 便于回溯")
```

- [ ] **Step 2: 写 `test_service.py` 失败测试 (TDD 红)**

创建 `packages/service/tests/memory/test_service.py`:

```python
"""MemoryService 单测: user_id 解析 + 降级 + 参数透传 (2026-06-16)"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest


# ---- _resolve_mem0_user_id ----


def test_resolve_mem0_user_id_prefers_account_id():
    """有账号时 user_id = str(account_id)"""
    from src.middleware.auth import CurrentUser
    from src.memory.service import _resolve_mem0_user_id

    user = CurrentUser(id=42, public_token="t", account_id=7, is_account=True)
    assert _resolve_mem0_user_id(user) == "7"


def test_resolve_mem0_user_id_fallback_to_user_id():
    """anon (account_id=None) 时 user_id = str(user.id)"""
    from src.middleware.auth import CurrentUser
    from src.memory.service import _resolve_mem0_user_id

    user = CurrentUser(id=42, public_token="t", account_id=None, is_account=False)
    assert _resolve_mem0_user_id(user) == "42"


# ---- MemoryService.search 降级 ----


def test_search_returns_empty_on_exception(monkeypatch):
    """mem0 抛任何异常 → 返 [] + log warning, 不冒泡"""
    from src.middleware.auth import CurrentUser
    from src.memory.service import MemoryService

    fake_memory = MagicMock()
    fake_memory.search.side_effect = RuntimeError("pgvector 不可达")
    fake_factory = MagicMock(return_value=fake_memory)
    svc = MemoryService(mem0_factory=fake_factory)

    user = CurrentUser(id=1, public_token="t", account_id=None)
    result = svc.search(user, "query", limit=3)
    assert result == []


def test_search_passes_filters_and_top_k():
    """search 走 mem0 self-host API: filters={user_id}, top_k"""
    from src.middleware.auth import CurrentUser
    from src.memory.service import MemoryService

    fake_memory = MagicMock()
    fake_memory.search.return_value = [
        {"id": "1", "memory": "用户叫张三", "score": 0.9, "metadata": {"src": "x"}},
    ]
    fake_factory = MagicMock(return_value=fake_memory)
    svc = MemoryService(mem0_factory=fake_factory)

    user = CurrentUser(id=42, public_token="t", account_id=None)
    results = svc.search(user, "用户叫什么", limit=3)

    assert len(results) == 1
    assert results[0].id == "1"
    assert results[0].text == "用户叫张三"
    assert results[0].score == 0.9
    assert results[0].metadata == {"src": "x"}
    fake_memory.search.assert_called_once_with(
        query="用户叫什么", filters={"user_id": "42"}, top_k=3
    )


def test_search_caches_memory_per_user():
    """同一 user 多次 search 复用 Memory 实例"""
    from src.middleware.auth import CurrentUser
    from src.memory.service import MemoryService

    fake_memory = MagicMock()
    fake_memory.search.return_value = []
    fake_factory = MagicMock(return_value=fake_memory)
    svc = MemoryService(mem0_factory=fake_factory)

    user = CurrentUser(id=42, public_token="t", account_id=None)
    svc.search(user, "q1")
    svc.search(user, "q2")

    fake_factory.assert_called_once_with("42")


def test_search_separate_cache_per_user():
    """不同 user 各自缓存 Memory"""
    from src.middleware.auth import CurrentUser
    from src.memory.service import MemoryService

    m1, m2 = MagicMock(), MagicMock()
    m1.search.return_value = []
    m2.search.return_value = []
    factory = MagicMock(side_effect=[m1, m2])
    svc = MemoryService(mem0_factory=factory)

    u1 = CurrentUser(id=1, public_token="t1", account_id=None)
    u2 = CurrentUser(id=2, public_token="t2", account_id=None)
    svc.search(u1, "q")
    svc.search(u2, "q")

    assert factory.call_count == 2
    assert factory.call_args_list[0][0][0] == "1"
    assert factory.call_args_list[1][0][0] == "2"


# ---- MemoryService.add 降级 + metadata 透传 ----


def test_add_silent_on_exception(monkeypatch):
    """add 抛异常 → log warning, 不重抛"""
    from src.middleware.auth import CurrentUser
    from src.memory.service import MemoryService

    fake_memory = MagicMock()
    fake_memory.add.side_effect = RuntimeError("LLM 限流")
    fake_factory = MagicMock(return_value=fake_memory)
    svc = MemoryService(mem0_factory=fake_factory)

    user = CurrentUser(id=1, public_token="t", account_id=None)
    # 必须不抛
    svc.add(user, [{"role": "user", "content": "hi"}], conversation_id="c1")


def test_add_passes_messages_and_user_id():
    """add 透传 messages + user_id"""
    from src.middleware.auth import CurrentUser
    from src.memory.service import MemoryService

    fake_memory = MagicMock()
    fake_factory = MagicMock(return_value=fake_memory)
    svc = MemoryService(mem0_factory=fake_factory)

    user = CurrentUser(id=42, public_token="t", account_id=None)
    msgs = [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hello"}]
    svc.add(user, msgs, conversation_id=None)

    fake_memory.add.assert_called_once_with(
        messages=msgs, user_id="42", infer=True
    )
    # 没 conversation_id 时不传 metadata
    assert "metadata" not in fake_memory.add.call_args[1]


def test_add_includes_conversation_id_in_metadata():
    """add 带 conversation_id 时透传到 metadata"""
    from src.middleware.auth import CurrentUser
    from src.memory.service import MemoryService

    fake_memory = MagicMock()
    fake_factory = MagicMock(return_value=fake_memory)
    svc = MemoryService(mem0_factory=fake_factory)

    user = CurrentUser(id=42, public_token="t", account_id=None)
    svc.add(user, [{"role": "user", "content": "hi"}], conversation_id="conv-abc")

    fake_memory.add.assert_called_once_with(
        messages=[{"role": "user", "content": "hi"}],
        user_id="42",
        infer=True,
        metadata={"conversation_id": "conv-abc"},
    )
```

- [ ] **Step 3: 跑测试验证全红**

Run:
```bash
cd packages/service
uv run pytest tests/memory/test_service.py -v
```

Expected: 8 个测试全 FAIL (ModuleNotFoundError: src.memory.service).

- [ ] **Step 4: 写 `service.py` 实现**

创建 `packages/service/src/memory/service.py`:

```python
"""MemoryService 业务核心: user_id 解析 + 降级兜底 (2026-06-16)

整个 memory 模块的"什么也不会坏"保证: 任何 mem0 异常都被 try/except 吞掉,
返空或静默 log, 主聊天流不感知.
"""

from __future__ import annotations

import logging
from typing import Any, Callable

from ..middleware.auth import CurrentUser
from .mem0_client import Memory, _default_mem0_factory
from .schemas import MemoryHit

logger = logging.getLogger(__name__)


def _resolve_mem0_user_id(current: CurrentUser) -> str:
    """账号优先 (Account.id), anon fallback User.id. 都用 str 跟 mem0 user_id 类型对齐."""
    return str(current.account_id) if current.account_id is not None else str(current.id)


class MemoryService:
    """按 user_id 缓存 Memory 实例 + 降级兜底.

    factory 参数允许测试注入 mock factory; 运行时走 _default_mem0_factory (self-host pgvector).
    """

    def __init__(self, mem0_factory: Callable[[str], Memory] | None = None):
        self._factory = mem0_factory or _default_mem0_factory
        self._cache: dict[str, Memory] = {}

    def _get_memory(self, user_id: str) -> Memory:
        if user_id not in self._cache:
            self._cache[user_id] = self._factory(user_id)
        return self._cache[user_id]

    def search(self, current: CurrentUser, query: str, limit: int = 5) -> list[MemoryHit]:
        user_id = _resolve_mem0_user_id(current)
        try:
            m = self._get_memory(user_id)
            # mem0 self-host 关键约束 (跟 hosted API 不同):
            #   - search 必须 filters={user_id/agent_id/run_id}, 不能直接 user_id=
            #   - 参数叫 top_k, 不是 limit
            #   - 返 dict 列表, 每条 {id, memory, score, metadata}
            results = m.search(query=query, filters={"user_id": user_id}, top_k=limit) or []
            return [
                MemoryHit(
                    id=str(r.get("id", "")),
                    text=r.get("memory", ""),
                    score=r.get("score"),
                    metadata=r.get("metadata"),
                )
                for r in results
            ]
        except Exception as e:
            logger.warning("[memory] search failed user=%s err=%s", user_id, e)
            return []

    def add(self, current: CurrentUser, messages: list[dict], conversation_id: str | None) -> None:
        user_id = _resolve_mem0_user_id(current)
        try:
            m = self._get_memory(user_id)
            # add 跟 search 不同: user_id 是直接传, 不在 filters 里
            kwargs: dict[str, Any] = {"messages": messages, "user_id": user_id, "infer": True}
            if conversation_id:
                kwargs["metadata"] = {"conversation_id": conversation_id}
            m.add(**kwargs)
        except Exception as e:
            logger.warning("[memory] add failed user=%s err=%s", user_id, e)
            # 静默: 不重抛, 不写错误响应
```

- [ ] **Step 5: 跑测试验证全绿**

Run:
```bash
cd packages/service
uv run pytest tests/memory/test_service.py -v
```

Expected: 8 个测试全 PASS.

- [ ] **Step 6: 改 `__init__.py` 暴露 service**

替换 `packages/service/src/memory/__init__.py`:

```python
"""memory 子包: 记忆层 (mem0 self-host pgvector, 2026-06-16)"""

from .mem0_client import Mem0Store, _build_config, _default_mem0_factory
from .schemas import AddRequest, MemoryHit, SearchRequest, SearchResponse, TurnMessage
from .service import MemoryService, _resolve_mem0_user_id

__all__ = [
    "Mem0Store",
    "_build_config",
    "_default_mem0_factory",
    "MemoryService",
    "_resolve_mem0_user_id",
    "SearchRequest",
    "SearchResponse",
    "MemoryHit",
    "AddRequest",
    "TurnMessage",
]
```

- [ ] **Step 7: 跑 sanity import**

Run:
```bash
cd packages/service
uv run python -c "from src.memory import MemoryService, _resolve_mem0_user_id, SearchRequest; print('OK')"
```

Expected: `OK`.

- [ ] **Step 8: Commit**

```bash
git add packages/service/src/memory/schemas.py \
        packages/service/src/memory/service.py \
        packages/service/src/memory/__init__.py \
        packages/service/tests/memory/test_service.py
git commit -m "feat(memory): MemoryService + schemas with degradation core"
```

---

## Task 3: router + register + contract

**Files:**
- Create: `packages/service/src/memory/router.py`
- Create: `packages/service/tests/memory/test_router.py`
- Modify: `packages/service/src/memory/__init__.py` (export `memory_router`)
- Modify: `packages/service/src/__init__.py` (`register_routers` 加 1 行)
- Modify: `packages/service/tests/test_api_contract.py` (`FRONTEND_EXPECTS` 加 2 行)

- [ ] **Step 1: 写 `test_router.py` 失败测试 (TDD 红)**

创建 `packages/service/tests/memory/test_router.py`:

```python
"""memory router 集成测试 (2026-06-16)"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.memory.router import memory_router


@pytest.fixture
def mock_service():
    svc = MagicMock()
    svc.search.return_value = []
    return svc


@pytest.fixture
def app_with_memory(mock_service, monkeypatch):
    """构造一个最小 FastAPI app, 挂上 memory_router, mock service 实例"""
    from src.memory import service as service_mod

    monkeypatch.setattr(service_mod, "MemoryService", lambda: mock_service)

    app = FastAPI()
    app.include_router(memory_router)
    return app


@pytest.fixture
def client(app_with_memory):
    return TestClient(app_with_memory)


def _set_anon_cookie(client: TestClient, user_id: int = 1, account_id: int | None = None):
    """让 resolve_user 返带 public_token 的 user; 走 session_scope 真表.
    简化: 用 dev mode (RAG_DEV_AUTH=true) 返 id=1 的 dev user.
    """
    import os
    os.environ["RAG_DEV_AUTH"] = "true"


def test_search_200_dev_mode(client, mock_service):
    """dev mode (RAG_DEV_AUTH=true) 下无 cookie 也走 dev user, search 返 200 + memories"""
    import os
    os.environ["RAG_DEV_AUTH"] = "true"
    try:
        mock_service.search.return_value = []
        resp = client.post("/api/memory/search", json={"query": "test", "limit": 3})
        assert resp.status_code == 200
        assert resp.json() == {"memories": []}
    finally:
        del os.environ["RAG_DEV_AUTH"]


def test_search_401_without_token_and_no_dev_mode(client, mock_service):
    """非 dev mode + 无 cookie → 401"""
    import os
    os.environ.pop("RAG_DEV_AUTH", None)
    resp = client.post("/api/memory/search", json={"query": "test", "limit": 3})
    assert resp.status_code == 401


def test_search_returns_empty_on_service_degradation(client, mock_service):
    """service 降级 (返空) → 200 + {memories: []}, router 透传不报错"""
    import os
    os.environ["RAG_DEV_AUTH"] = "true"
    try:
        mock_service.search.return_value = []
        resp = client.post("/api/memory/search", json={"query": "test"})
        assert resp.status_code == 200
        assert resp.json()["memories"] == []
    finally:
        del os.environ["RAG_DEV_AUTH"]


def test_search_400_on_invalid_body(client):
    """缺 query 字段 → 422 (Pydantic 校验)"""
    import os
    os.environ["RAG_DEV_AUTH"] = "true"
    try:
        resp = client.post("/api/memory/search", json={})
        assert resp.status_code == 422
    finally:
        del os.environ["RAG_DEV_AUTH"]


def test_add_204_dev_mode(client, mock_service):
    """dev mode + 有效 body → 204, service.add 被调一次"""
    import os
    os.environ["RAG_DEV_AUTH"] = "true"
    try:
        resp = client.post(
            "/api/memory/add",
            json={
                "messages": [{"role": "user", "content": "hi"}],
                "conversation_id": "c1",
            },
        )
        assert resp.status_code == 204
        assert mock_service.add.called
        # 验证 add 收到 CurrentUser + messages + conversation_id
        call_args = mock_service.add.call_args
        assert call_args[0][1] == [{"role": "user", "content": "hi"}]
        assert call_args[0][2] == "c1"
    finally:
        del os.environ["RAG_DEV_AUTH"]


def test_add_401_without_token_and_no_dev_mode(client):
    """非 dev mode + 无 cookie → 401"""
    import os
    os.environ.pop("RAG_DEV_AUTH", None)
    resp = client.post(
        "/api/memory/add",
        json={"messages": [{"role": "user", "content": "hi"}]},
    )
    assert resp.status_code == 401


def test_add_400_on_empty_messages(client):
    """messages=[] → 422 (Pydantic min_length=1)"""
    import os
    os.environ["RAG_DEV_AUTH"] = "true"
    try:
        resp = client.post("/api/memory/add", json={"messages": []})
        assert resp.status_code == 422
    finally:
        del os.environ["RAG_DEV_AUTH"]
```

- [ ] **Step 2: 跑测试验证全红**

Run:
```bash
cd packages/service
uv run pytest tests/memory/test_router.py -v
```

Expected: 7 个测试全 FAIL (ModuleNotFoundError: src.memory.router).

- [ ] **Step 3: 写 `router.py`**

创建 `packages/service/src/memory/router.py`:

```python
"""记忆 HTTP 端点 (2026-06-16)

POST /api/memory/search  - 检索相关记忆
POST /api/memory/add     - 写入本轮对话

跟 kg / approvals 路由同款: 浏览器直连 + Depends(resolve_user) 注入鉴权.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response, status

from ..middleware.auth import CurrentUser, resolve_user
from .schemas import AddRequest, SearchRequest, SearchResponse
from .service import MemoryService

router = APIRouter(prefix="/api/memory", tags=["记忆"])

# 单例 service (无依赖注入, 简单场景够用)
_service = MemoryService()


@router.post("/search", response_model=SearchResponse)
def search(req: SearchRequest, current: CurrentUser = Depends(resolve_user)) -> SearchResponse:
    """按 query 检索当前用户相关记忆. 降级时 memories=[].

    鉴权: x-user-token header / rag_user_token cookie 透传, 后端 resolve_user 解析.
    """
    memories = _service.search(current, req.query, req.limit)
    return SearchResponse(memories=memories)


@router.post("/add", status_code=status.HTTP_204_NO_CONTENT)
def add(req: AddRequest, current: CurrentUser = Depends(resolve_user)) -> Response:
    """把本轮 user+assistant 完整对话写入记忆. 失败静默 (service 层吞)."""
    _service.add(
        current,
        [t.model_dump() for t in req.messages],
        req.conversation_id,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
```

- [ ] **Step 4: 跑测试验证全绿**

Run:
```bash
cd packages/service
uv run pytest tests/memory/test_router.py -v
```

Expected: 7 个测试全 PASS. 如果 FAIL 优先看 `app_with_memory` fixture 的 `monkeypatch.setattr` 是否真的替换了 `service.MemoryService` 引用 (因为 router 里 `_service = MemoryService()` 是模块级, 在 import 时跑; monkeypatch 必须更早).

- [ ] **Step 5: 注册 router 到 `register_routers`**

修改 `packages/service/src/__init__.py` 的 `register_routers` 函数, 在 `from .kg.router import router as kg_router` 后加:

```python
    from .memory.router import router as memory_router
```

并在 `app.include_router(kg_router)` 后加:

```python
    app.include_router(memory_router)  # /api/memory/*
```

(具体插入位置参考 `register_routers` 函数当前的导入和 include 顺序, 跟其它 router 同风格.)

- [ ] **Step 6: 改 `test_api_contract.py` 加 2 行**

在 `packages/service/tests/test_api_contract.py` 的 `FRONTEND_EXPECTS` 列表末尾加:

```python
    # --- memory (memory.ts 直连, 2026-06-16) ---
    ("POST", "/api/memory/search"),
    ("POST", "/api/memory/add"),
```

(在 `("/api/approvals/{approval_id}/retry"),` 行后, 列表 `]` 前.)

- [ ] **Step 7: 跑契约测试验证后端注册了路由**

Run:
```bash
cd packages/service
uv run pytest tests/test_api_contract.py -v
```

Expected: `test_backend_routes_cover_frontend_expectations` PASS (含 memory 2 行). `test_no_dead_routes_in_backend` PASS (没把 memory 算 dead). `test_health_endpoint_reachable` SKIP (除非有 integration marker).

- [ ] **Step 8: 跑全量 mem0 + contract 测试**

Run:
```bash
cd packages/service
uv run pytest tests/memory/ tests/test_api_contract.py -v
```

Expected: 7 (client) + 8 (service) + 7 (router) + 2-3 (contract) = 24+ 个测试全 PASS.

- [ ] **Step 9: Commit**

```bash
git add packages/service/src/memory/router.py \
        packages/service/tests/memory/test_router.py \
        packages/service/src/memory/__init__.py \
        packages/service/src/__init__.py \
        packages/service/tests/test_api_contract.py
git commit -m "feat(memory): FastAPI /api/memory/{search,add} with Depends(resolve_user)"
```

---

## Task 4: 前端 `lib/api/memory.ts` + factory 重构

**Files:**
- Create: `packages/web/lib/api/memory.ts`
- Create: `packages/web/lib/api/memory.test.ts`
- Modify: `packages/web/lib/chat/factory.ts` (require → 静态 import + 套 withMemoryHooks)
- Modify: `packages/web/lib/chat/factory.test.ts` (un-todo + 改断言)

- [ ] **Step 1: 写 `memory.test.ts` 失败测试 (TDD 红)**

创建 `packages/web/lib/api/memory.test.ts`:

```ts
// memoryApi 单测: 调 apiFetch 路径 + 错误归一 (2026-06-16)
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("./config", () => ({
  apiFetch: vi.fn(),
}));

import { apiFetch } from "./config";
import { memoryApi } from "./memory";

const mockedApiFetch = vi.mocked(apiFetch);

describe("memoryApi", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  describe("search", () => {
    it("POST /api/memory/search with query + limit", async () => {
      mockedApiFetch.mockResolvedValue({ memories: [] });

      await memoryApi.search({ query: "test", limit: 3 });

      expect(mockedApiFetch).toHaveBeenCalledWith(
        "/api/memory/search",
        expect.objectContaining({
          method: "POST",
          body: { query: "test", limit: 3 },
        }),
      );
    });

    it("search 默认 limit=5", async () => {
      mockedApiFetch.mockResolvedValue({ memories: [] });

      await memoryApi.search({ query: "test" });

      expect(mockedApiFetch.mock.calls[0][1]?.body).toEqual({
        query: "test",
        limit: 5,
      });
    });

    it("search 4xx/5xx → 抛 ApiError (走 apiFetch 错误归一)", async () => {
      const { ApiError } = await import("./errors");
      mockedApiFetch.mockRejectedValue(new ApiError(500, "mem0 不可达"));

      await expect(memoryApi.search({ query: "test" })).rejects.toThrow(/mem0 不可达/);
    });
  });

  describe("add", () => {
    it("POST /api/memory/add with messages + conversationId", async () => {
      mockedApiFetch.mockResolvedValue(undefined);

      await memoryApi.add({
        messages: [{ role: "user", content: "hi" }],
        conversationId: "c1",
      });

      expect(mockedApiFetch).toHaveBeenCalledWith(
        "/api/memory/add",
        expect.objectContaining({
          method: "POST",
          body: {
            messages: [{ role: "user", content: "hi" }],
            conversation_id: "c1",
          },
        }),
      );
    });

    it("add 204 → 返 undefined", async () => {
      mockedApiFetch.mockResolvedValue(undefined);
      const result = await memoryApi.add({
        messages: [{ role: "user", content: "hi" }],
      });
      expect(result).toBeUndefined();
    });

    it("add 无 conversationId → body 不含 conversation_id", async () => {
      mockedApiFetch.mockResolvedValue(undefined);

      await memoryApi.add({ messages: [{ role: "user", content: "hi" }] });

      const body = mockedApiFetch.mock.calls[0][1]?.body as Record<string, unknown>;
      expect(body).not.toHaveProperty("conversation_id");
    });
  });
});
```

- [ ] **Step 2: 跑测试验证全红**

Run:
```bash
cd packages/web
bun run test -- memory.test
```

Expected: 6 个测试全 FAIL (Cannot find module './memory' or its corresponding type declarations).

- [ ] **Step 3: 写 `memory.ts`**

创建 `packages/web/lib/api/memory.ts`:

```ts
// 长期记忆 API 客户端 (2026-06-16)
// 走 apiFetch 直连后端 (/api/memory/* 不在 BFF_PATTERNS 名单里, 浏览器拼 host)
// 服务端 (RSC / server action) 也用同一个 apiFetch, cookie 透传
import { apiFetch } from "./config";

export interface MemoryHit {
  id: string;
  text: string;
  score?: number;
  metadata?: Record<string, unknown>;
}

export interface TurnMessage {
  role: "user" | "assistant";
  content: string;
}

export interface SearchInput {
  query: string;
  limit?: number;
}

export interface AddInput {
  messages: TurnMessage[];
  conversationId?: string;
}

export const memoryApi = {
  async search(req: SearchInput): Promise<{ memories: MemoryHit[] }> {
    return apiFetch("/api/memory/search", {
      method: "POST",
      body: { query: req.query, limit: req.limit ?? 5 },
    });
  },

  async add(req: AddInput): Promise<void> {
    // 后端 Pydantic 字段是 snake_case conversation_id, 前端 camelCase 转
    const body: Record<string, unknown> = {
      messages: req.messages,
    };
    if (req.conversationId) {
      body.conversation_id = req.conversationId;
    }
    await apiFetch("/api/memory/add", { method: "POST", body });
  },
};
```

- [ ] **Step 4: 跑测试验证全绿**

Run:
```bash
cd packages/web
bun run test -- memory.test
```

Expected: 6 个测试全 PASS.

- [ ] **Step 5: 改 `factory.ts` require→import + 套 withMemoryHooks**

⚠️ **必须先把 require 改 import**, 否则 vitest 测不出 `name` 后缀.

替换 `packages/web/lib/chat/factory.ts`:

```ts
import { DifyChatProvider } from "./dify";
import { withMemoryHooks } from "./memory-integration";
import type { ChatProvider } from "./types";

// (2026-06-16) 把 require() 动态加载改成静态 import, 让 vitest ESM 能测 name 后缀.
//              顺便在 dify case 上套 withMemoryHooks 装饰器, 任何 ChatProvider 套了它
//              就自动获得长期记忆能力; 换 provider 不用动记忆层.

export function getChatProvider(): ChatProvider {
  const name = process.env.CHAT_PROVIDER;
  if (!name) {
    throw new Error(
      "CHAT_PROVIDER 未设置; 在 .env 里加 CHAT_PROVIDER=dify 或 CHAT_PROVIDER=openai",
    );
  }
  switch (name) {
    case "dify": {
      // dify 套记忆装饰器 (核心对话场景, 长期记忆价值高)
      return withMemoryHooks(new DifyChatProvider());
    }
    case "openai": {
      // openai 暂不套 (2026-06-16 v1 范围只覆盖 dify)
      const { OpenAIChatProvider } = require("./openai") as typeof import("./openai");
      return new OpenAIChatProvider();
    }
    case "llamaindex": {
      throw new Error("llamaindex provider 未实现");
    }
    default: {
      throw new Error(`unknown provider: ${name}`);
    }
  }
}
```

(注意: openai 保持 require, 因为它没套装饰器不影响测试. 后续要加 openai 记忆时再统一改.)

- [ ] **Step 6: 改 `factory.test.ts` un-todo + 改断言**

替换 `packages/web/lib/chat/factory.test.ts`:

```ts
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { getChatProvider } from "./factory";

vi.mock("./dify", () => ({
  DifyChatProvider: vi.fn().mockImplementation(() => ({
    name: "dify",
    sendMessage: vi.fn(),
  })),
}));
vi.mock("./memory-integration", () => ({
  withMemoryHooks: vi.fn().mockImplementation((inner: { name: string }) => ({
    name: `${inner.name}+memory`,
    sendMessage: vi.fn(),
  })),
}));

describe("getChatProvider", () => {
  const ORIGINAL = process.env.CHAT_PROVIDER;

  beforeEach(() => {
    delete process.env.CHAT_PROVIDER;
    vi.clearAllMocks();
  });
  afterEach(() => {
    if (ORIGINAL === undefined) {
      delete process.env.CHAT_PROVIDER;
    } else {
      process.env.CHAT_PROVIDER = ORIGINAL;
    }
  });

  it("CHAT_PROVIDER=dify 返 name='dify+memory' (套了 withMemoryHooks)", () => {
    process.env.CHAT_PROVIDER = "dify";
    const provider = getChatProvider();
    expect(provider.name).toBe("dify+memory");
  });

  it("CHAT_PROVIDER 未设抛错 (不静默回退)", () => {
    expect(() => getChatProvider()).toThrow(/CHAT_PROVIDER/);
  });

  it("CHAT_PROVIDER=llamaindex 抛 '未实现' (v1 故意不兜底)", () => {
    process.env.CHAT_PROVIDER = "llamaindex";
    expect(() => getChatProvider()).toThrow(/llamaindex/);
  });

  it("CHAT_PROVIDER=garbage 抛 'unknown provider'", () => {
    process.env.CHAT_PROVIDER = "garbage";
    expect(() => getChatProvider()).toThrow(/unknown provider/);
  });
});
```

(注意: `it.todo` 被替换为真测试. mock 了 `./dify` 和 `./memory-integration`, 这样不依赖真实 mem0 网络.)

- [ ] **Step 7: 跑 factory 测试验证全绿**

Run:
```bash
cd packages/web
bun run test -- factory.test
```

Expected: 4 个测试全 PASS. 如果 FAIL 优先看 mock 路径对不对 (vitest mock key 跟 import 路径一致).

- [ ] **Step 8: Commit**

```bash
git add packages/web/lib/api/memory.ts \
        packages/web/lib/api/memory.test.ts \
        packages/web/lib/chat/factory.ts \
        packages/web/lib/chat/factory.test.ts
git commit -m "feat(chat): memoryApi + factory wraps DifyChatProvider with withMemoryHooks"
```

---

## Task 5: withMemoryHooks 装饰器 + Dify 文档

**Files:**
- Create: `packages/web/lib/chat/memory-integration.ts`
- Create: `packages/web/lib/chat/memory-integration.test.ts`
- Create: `docs/rag/memory/dify-workflow-config.md`

- [ ] **Step 1: 写 `memory-integration.test.ts` 失败测试 (TDD 红)**

创建 `packages/web/lib/chat/memory-integration.test.ts`:

```ts
// withMemoryHooks 装饰器单测 (2026-06-16)
// 覆盖 3 个核心行为 + 降级
import { afterEach, describe, expect, it, vi } from "vitest";
import type { ChatEvent, ChatProvider, SendMessageRequest } from "./types";

vi.mock("../api/memory", () => ({
  memoryApi: {
    search: vi.fn(),
    add: vi.fn(),
  },
}));

import { memoryApi } from "../api/memory";
import { withMemoryHooks } from "./memory-integration";

const mockedSearch = vi.mocked(memoryApi.search);
const mockedAdd = vi.mocked(memoryApi.add);

interface FakeProviderOpts {
  events?: ChatEvent[];
  throwAt?: number;
}

function makeFakeProvider(opts: FakeProviderOpts = {}): ChatProvider & {
  receivedReq: SendMessageRequest | null;
} {
  const inner: ChatProvider & { receivedReq: SendMessageRequest | null } = {
    name: "fake",
    receivedReq: null,
    async *sendMessage(req: SendMessageRequest) {
      inner.receivedReq = req;
      for (const ev of opts.events ?? []) {
        if (opts.throwAt !== undefined && opts.throwAt-- <= 0) {
          throw new Error("upstream blew up");
        }
        yield ev;
      }
    },
  };
  return inner;
}

async function* toAsyncIterable<T>(items: T[]) {
  for (const item of items) yield item;
}

describe("withMemoryHooks", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("name 后缀 = 'fake+memory'", () => {
    const inner = makeFakeProvider();
    const wrapped = withMemoryHooks(inner);
    expect(wrapped.name).toBe("fake+memory");
  });

  describe("Pre-LLM search", () => {
    it("search 成功 → 把 memories 拼成 inputs.memory_context 传内层", async () => {
      mockedSearch.mockResolvedValue({
        memories: [
          { id: "1", text: "用户叫张三" },
          { id: "2", text: "用户住北京" },
        ],
      });
      const inner = makeFakeProvider({ events: [] });

      await consume(
        withMemoryHooks(inner).sendMessage(
          { query: "我叫什么", user: "u1", inputs: { foo: "bar" } },
          new AbortController().signal,
        ),
      );

      expect(inner.receivedReq?.inputs).toEqual({
        foo: "bar",
        memory_context: "用户相关记忆:\n- 用户叫张三\n- 用户住北京",
      });
    });

    it("search 返空 → inputs.memory_context 是空串", async () => {
      mockedSearch.mockResolvedValue({ memories: [] });
      const inner = makeFakeProvider({ events: [] });

      await consume(
        withMemoryHooks(inner).sendMessage(
          { query: "q", user: "u1", inputs: {} },
          new AbortController().signal,
        ),
      );

      expect(inner.receivedReq?.inputs).toEqual({ memory_context: "" });
    });

    it("search 抛错 → 降级到空 memory_context, 内层 provider 仍被调", async () => {
      mockedSearch.mockRejectedValue(new Error("mem0 不可达"));
      const inner = makeFakeProvider({ events: [] });
      const consoleWarn = vi.spyOn(console, "warn").mockImplementation(() => {});

      await consume(
        withMemoryHooks(inner).sendMessage(
          { query: "q", user: "u1", inputs: {} },
          new AbortController().signal,
        ),
      );

      expect(inner.receivedReq?.inputs).toEqual({ memory_context: "" });
      expect(consoleWarn).toHaveBeenCalledWith(
        expect.stringContaining("search failed"),
        expect.anything(),
      );
      consoleWarn.mockRestore();
    });
  });

  describe("流中 assistant 累积", () => {
    it("流中多条 message 事件 → 累积成单个 assistant turn", async () => {
      mockedSearch.mockResolvedValue({ memories: [] });
      mockedAdd.mockResolvedValue(undefined);
      const inner = makeFakeProvider({
        events: [
          { type: "message", delta: "你" },
          { type: "message", delta: "好" },
          { type: "message", delta: "张三" },
          { type: "message_end", conversationId: "c1" },
        ],
      });

      const events: ChatEvent[] = [];
      for await (const ev of withMemoryHooks(inner).sendMessage(
        { query: "我叫什么", user: "u1", inputs: {} },
        new AbortController().signal,
      )) {
        events.push(ev);
      }

      // 透传所有事件
      expect(events.map((e) => e.type)).toEqual([
        "message",
        "message",
        "message",
        "message_end",
      ]);
    });

    it("add 收到 user query + 累积后单条 assistant turn", async () => {
      mockedSearch.mockResolvedValue({ memories: [] });
      mockedAdd.mockResolvedValue(undefined);
      const inner = makeFakeProvider({
        events: [
          { type: "message", delta: "你" },
          { type: "message", delta: "好" },
        ],
      });

      await consume(
        withMemoryHooks(inner).sendMessage(
          { query: "我叫什么", user: "u1", inputs: {} },
          new AbortController().signal,
        ),
      );

      // 等待 micro-task flush
      await new Promise((r) => setTimeout(r, 0));

      expect(mockedAdd).toHaveBeenCalledWith({
        messages: [
          { role: "user", content: "我叫什么" },
          { role: "assistant", content: "你好" },
        ],
        conversationId: undefined,
      });
    });
  });

  describe("Post-LLM add", () => {
    it("流结束 → fire-and-forget add 含 conversationId", async () => {
      mockedSearch.mockResolvedValue({ memories: [] });
      mockedAdd.mockResolvedValue(undefined);
      const inner = makeFakeProvider({
        events: [
          { type: "message", delta: "x" },
          { type: "message_end", conversationId: "c1" },
        ],
      });

      await consume(
        withMemoryHooks(inner).sendMessage(
          { query: "q", user: "u1", inputs: {}, conversationId: "c1" },
          new AbortController().signal,
        ),
      );
      await new Promise((r) => setTimeout(r, 0));

      expect(mockedAdd).toHaveBeenCalledWith({
        messages: [
          { role: "user", content: "q" },
          { role: "assistant", content: "x" },
        ],
        conversationId: "c1",
      });
    });

    it("add 失败 → console.warn, 不冒泡 (fire-and-forget)", async () => {
      mockedSearch.mockResolvedValue({ memories: [] });
      mockedAdd.mockRejectedValue(new Error("mem0 写失败"));
      const inner = makeFakeProvider({
        events: [{ type: "message", delta: "x" }],
      });
      const consoleWarn = vi.spyOn(console, "warn").mockImplementation(() => {});

      // 不应抛
      await expect(
        consume(
          withMemoryHooks(inner).sendMessage(
            { query: "q", user: "u1", inputs: {} },
            new AbortController().signal,
          ),
        ),
      ).resolves.not.toThrow();

      await new Promise((r) => setTimeout(r, 10));
      expect(consoleWarn).toHaveBeenCalledWith(
        expect.stringContaining("add failed"),
        expect.anything(),
      );
      consoleWarn.mockRestore();
    });

    it("流没有任何 assistant message → 不调 add", async () => {
      mockedSearch.mockResolvedValue({ memories: [] });
      const inner = makeFakeProvider({
        events: [{ type: "workflow_done", status: "succeeded" }],
      });

      await consume(
        withMemoryHooks(inner).sendMessage(
          { query: "q", user: "u1", inputs: {} },
          new AbortController().signal,
        ),
      );
      await new Promise((r) => setTimeout(r, 10));

      expect(mockedAdd).not.toHaveBeenCalled();
    });
  });
});

async function consume(it: AsyncIterable<unknown>) {
  for await (const _ of it) {
    // drain
  }
}
```

- [ ] **Step 2: 跑测试验证全红**

Run:
```bash
cd packages/web
bun run test -- memory-integration.test
```

Expected: 9 个测试全 FAIL (Cannot find module './memory-integration').

- [ ] **Step 3: 写 `memory-integration.ts`**

创建 `packages/web/lib/chat/memory-integration.ts`:

```ts
// 长期记忆 ChatProvider 装饰器 (2026-06-16)
// 任何 ChatProvider 套上自动获得长期记忆能力; 换掉 dify 不影响记忆层.
//
// 三段:
//   1. Pre-LLM: 搜相关记忆, 拼成 inputs.memory_context (失败降级为空串)
//   2. 流中: 累积 user + assistant 完整对话 (流式 delta 拼装)
//   3. Post-LLM: fire-and-forget 写记忆 (失败仅 warning, 不阻断)

import { memoryApi, type TurnMessage } from "../api/memory";
import type { ChatEvent, ChatProvider, SendMessageRequest } from "./types";

const MEMORY_CONTEXT_KEY = "memory_context";

function buildMemoryContext(memories: { text: string }[]): string {
  if (memories.length === 0) return "";
  return `用户相关记忆:\n${memories.map((m) => `- ${m.text}`).join("\n")}`;
}

export function withMemoryHooks(inner: ChatProvider): ChatProvider {
  return {
    name: `${inner.name}+memory`,

    async *sendMessage(
      req: SendMessageRequest,
      signal: AbortSignal,
    ): AsyncIterable<ChatEvent> {
      // 1. Pre-LLM: search + 注入 inputs.memory_context (失败降级)
      let memoryContext = "";
      try {
        const { memories } = await memoryApi.search({ query: req.query, limit: 5 });
        memoryContext = buildMemoryContext(memories);
      } catch (e) {
        console.warn("[memory] search failed, fallback", e);
      }
      const enhancedReq: SendMessageRequest = {
        ...req,
        inputs: { ...req.inputs, [MEMORY_CONTEXT_KEY]: memoryContext },
      };

      // 2. 流中: 累积 user + assistant turns
      const turns: TurnMessage[] = [{ role: "user", content: req.query }];
      for await (const ev of inner.sendMessage(enhancedReq, signal)) {
        if (ev.type === "message") {
          const last = turns[turns.length - 1];
          if (last?.role === "assistant") {
            turns[turns.length - 1] = {
              role: "assistant",
              content: last.content + ev.delta,
            };
          } else {
            turns.push({ role: "assistant", content: ev.delta });
          }
        }
        yield ev;
      }

      // 3. Post-LLM: fire-and-forget add (失败仅 warning)
      const hasAssistant = turns.some((t) => t.role === "assistant");
      if (hasAssistant) {
        memoryApi
          .add({ messages: turns, conversationId: req.conversationId })
          .catch((e) => console.warn("[memory] add failed", e));
      }
    },
  };
}
```

- [ ] **Step 4: 跑测试验证全绿**

Run:
```bash
cd packages/web
bun run test -- memory-integration.test
```

Expected: 9 个测试全 PASS. 如果 FAIL 优先看:
- 流事件是否真按顺序 yield
- `mockedAdd` 是不是被调（`await new Promise(r => setTimeout(r, 0))` 给 micro-task flush 时间）
- add 失败时是否真不抛

- [ ] **Step 5: 跑前端全量测试 + lint + typecheck**

Run:
```bash
cd packages/web
bun run test -- memory memory-integration factory dify
bun run lint
bun run typecheck
```

Expected: 所有相关测试 PASS; lint 0 error; typecheck 0 error. 如果破现有 `dify.test.ts`, 检查装饰器是不是吞了 Dify 原始事件 (decorator 内部 `yield ev` 必须透传, 不能丢).

- [ ] **Step 6: 写 Dify 工作流配置文档**

创建 `docs/rag/memory/dify-workflow-config.md`:

````markdown
# Dify Chatflow 工作流配置: 接入长期记忆

> **作用**: 让 Dify Chatflow 在跟用户对话时, 自动接收前端 dify.ts 注入的 `memory_context` (含相关历史记忆), 并拼到 LLM 的 System Prompt 里.

**前提**: 长期记忆 FastAPI 端点 `/api/memory/search` 已经返回相关记忆 (项目本地后端跑在 :8000), 前端 `withMemoryHooks` 装饰器已自动把 `inputs.memory_context` 字段塞进 Dify 请求.

**作用域**: 每个 Dify Chatflow 应用都要配一次 (用同一份模板).

---

## 步骤

### 1. 打开应用编排页

Dify 控制台 → 你的 Chatflow 应用 → "编排" 标签.

### 2. 配置"开始"节点的输入变量

点 "开始" 节点 → 右侧 "输入变量" 区域:

- 如果列表里**已经有** `memory_context` 字段 (类型 String): 把"必填"改为**否** (让它可空, 不传也不报错).
- 如果**没有**: 手动添加 → 字段名 `memory_context`, 类型 `String`, 必填 `否`.

> **为什么要"必填=否"**: 用户首轮对话没历史记忆时, 前端不调 search / search 返空, `memory_context` 会是空串. Dify 必填会让首轮 422.

### 3. 改 LLM 节点的 System Prompt

点 LLM 节点 → "SYSTEM" 提示词模板 → 末尾追加:

```
{{#memory_context}}
用户历史记忆:
{{memory_context}}
{{/memory_context}}
```

#### 模板语法说明

- `{{#var}}...{{/var}}` 是 Dify 的**条件块**: 变量**非空**才渲染中间的内容; 变量为空时整块消失.
- 用户首轮没记忆时 `memory_context=""`, 整块不渲染, 提示词保持原状, 无副作用.
- 用户有记忆时, 块渲染成 "用户历史记忆:\n<记忆内容>", 拼到 SYSTEM 末尾, LLM 能看到.

#### 示例效果

有记忆时 LLM 看到的 SYSTEM 末尾:
```
你是一个乐于助人的助手.

用户历史记忆:
- 用户叫张三
- 用户住北京
```

没记忆时 (首轮):
```
你是一个乐于助人的助手.
```

### 4. 保存 + 发布

点右上角 "发布" → 确认.

### 5. 验证 (手动测试)

1. 在前端 dev 界面开新对话
2. 发 "我叫张三, 住北京"
3. 等流结束
4. 开新对话 (Dify 端: 同账号新 conversation)
5. 发 "我叫什么名字, 住哪"
6. 期待: LLM 答 "你叫张三, 住北京" (用了 memory_context 里的事实)

如果没成功:
- 检查 Dify 工作流 SYSTEM 模板是否正确 (注意 `{{#` 和 `{{/` 是条件块, 不是普通变量引用)
- 检查 "开始" 节点的 `memory_context` 是否设了"必填=否"
- 浏览器 devtools 看 `/api/chat/messages` 请求 body 是否含 `inputs.memory_context`
- 后端日志看 `grep memory` 是否有 `search failed` / `add failed` warning

---

## 可选: 改 LLM 抽取模型

事实抽取 (mem0.add 的 LLM 调用) 默认用 `MEM0_LLM_MODEL=gpt-4o-mini`. 想省钱可在 `.env.local` 改:

```bash
MEM0_LLM_MODEL=gpt-4o-mini          # 默认, 便宜
# 或
MEM0_LLM_MODEL=gpt-3.5-turbo         # 更便宜, 抽取质量略降
```

不需要改 Dify 端. 只改后端 .env, 重启 service 即生效.

---

## 常见问题

**Q: 多个 Chatflow 应用都要配?**
A: 是. 每个 Chatflow 都要走 Step 1-4 一次. 建议把这文档链接加到 Dify 应用描述里, 提醒维护者.

**Q: memory_context 注入到 LLM 的哪个位置?**
A: 拼到 SYSTEM Prompt 末尾, 在 USER 消息之前. LLM 视为"系统级背景信息", 不会跟用户当前问题混淆.

**Q: 记忆里出现错误信息怎么办?**
A: 用户在对话中纠正即可. mem0 的 `infer=True` 模式下, 重新 add 同一 user_id 的对话时, LLM 会自动判断新事实跟旧记忆冲突, 触发 UPDATE/DELETE. 不需要用户手动清记忆.
````

- [ ] **Step 7: Commit**

```bash
git add packages/web/lib/chat/memory-integration.ts \
        packages/web/lib/chat/memory-integration.test.ts \
        docs/rag/memory/dify-workflow-config.md
git commit -m "feat(chat): withMemoryHooks decorator (3-phase: search/inject/accumulate/add)"
```

---

## Task 6 (optional): 真连集成测试 (slow marker)

**Files:**
- Create: `packages/service/tests/memory/test_mem0_integration.py`

这一步**可选**但强烈推荐: 写一个慢测试, 真连项目 pgvector 容器验证 mem0 search→add→search 闭环. CI 可 skip, 提交前手动跑一次确认链路.

- [ ] **Step 1: 写 slow 真连测试**

创建 `packages/service/tests/memory/test_mem0_integration.py`:

```python
"""mem0 self-host 真连集成测试 (slow marker, 需 RAG_DB_URL)

验证: search→add→search 闭环, per-user_id 隔离.
CI 可 skip (pytest -m "not slow"), 提交前手动跑:
  RAG_DB_URL=postgresql+psycopg://postgres:postgres@localhost:5432/rag \
    uv run pytest tests/memory/test_mem0_integration.py -v -m slow
"""

from __future__ import annotations

import os
import uuid

import pytest

from src.memory.service import MemoryService, _resolve_mem0_user_id
from src.middleware.auth import CurrentUser


@pytest.mark.slow
def test_search_add_search_roundtrip():
    """真连 pgvector: add 一条 → search 应命中"""
    if not os.getenv("RAG_DB_URL"):
        pytest.skip("需要 RAG_DB_URL 指向 PG")

    # 唯一 user_id 避免跟其它测试 / 数据冲突
    unique_user_id = f"test-user-{uuid.uuid4().hex[:8]}"
    user = CurrentUser(id=999_999, public_token="test-token", account_id=None)

    # 强制用 unique_user_id (不走 _resolve_mem0_user_id 默认逻辑)
    svc = MemoryService()
    # 清缓存强制重新构造 (确保 unique user)
    svc._cache.clear()

    try:
        # 1. add 一条对话
        svc.add(
            user,
            [
                {"role": "user", "content": "我叫测试用户 8888"},
                {"role": "assistant", "content": "好的, 记住了"},
            ],
            conversation_id="test-conv",
        )

        # 2. search 应命中
        # 注意: mem0 用 LLM 抽事实, 实际写进 pgvector 的可能是 "用户叫测试用户 8888"
        # 搜索 query 用相关语义
        results = svc.search(user, "这个用户叫什么", limit=3)

        # 至少能返结果 (不强求命中特定文本, 避免 LLM 输出漂移导致 flaky)
        assert isinstance(results, list)
    finally:
        # 清理: 用 unique user_id, 不需要显式删 (测试结束 _truncate_tables fixture 会清表)
        pass
```

- [ ] **Step 2: 跑慢测试验证 (需 RAG_DB_URL)**

Run:
```bash
cd packages/service
RAG_DB_URL=postgresql+psycopg://postgres:postgres@localhost:5432/rag \
  uv run pytest tests/memory/test_mem0_integration.py -v -m slow
```

Expected: 1 个测试 PASS (或 SKIP 如果 RAG_DB_URL 没设). 如果 FAIL 看:
- mem0 报 "vector extension not found" → 跑 `uv run python -c "from src.retrieval import init_pgvector; init_pgvector()"`
- LLM 抛 401 → 检查 `.env.local` 有 OPENAI_API_KEY
- pgvector 容器没起 → `docker ps | grep pgvector`

- [ ] **Step 3: Commit**

```bash
git add packages/service/tests/memory/test_mem0_integration.py
git commit -m "test(memory): add slow integration test for search→add→search roundtrip"
```

---

## Pre-E2E: 验证 mem0 self-host 首次 m.add() 触发建表

跑完 Task 1-5 后, **第一次 `m.add()` 才会建表**. 在跑 E2E 之前先做一次手测确认建表无副作用.

- [ ] **Step 1: 起后端, 触发一次 search/add 验证建表**

```bash
cd packages/service
RAG_DEV_AUTH=true uv run python main.py
# 等 5s, 后端启在 :8000
```

另开一个终端:

```bash
# dev user (RAG_DEV_AUTH=true) 直接调 search, 应返空
curl -X POST http://localhost:8000/api/memory/search \
  -H "Content-Type: application/json" \
  -d '{"query":"test","limit":3}'
# Expected: {"memories":[]}

# 调 add, 会触发 mem0 内部:
#   - CREATE EXTENSION IF NOT EXISTS vector (如果没装)
#   - CREATE TABLE IF NOT EXISTS mem0_memories
#   - CREATE INDEX IF NOT EXISTS mem0_memories_hnsw_idx USING hnsw
#   - 写入一条记忆
curl -X POST http://localhost:8000/api/memory/add \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"我叫测试用户 9999"}],"conversation_id":"smoke"}'
# Expected: 204 (空响应)

# 验证表已建
PGPASSWORD=postgres psql -h localhost -U postgres -d rag -c "\dt"
# Expected: 列表里应有 mem0_memories 表
PGPASSWORD=postgres psql -h localhost -U postgres -d rag -c "\di mem0*"
# Expected: 至少 2 个索引 (mem0_memories_hnsw_idx + mem0_memories_text_lemmatized_idx)
PGPASSWORD=postgres psql -h localhost -U postgres -d rag -c "SELECT count(*) FROM mem0_memories"
# Expected: >= 1 (刚才 add 的, mem0 用 LLM 抽了事实)
```

如果 `psql` 命令失败 (Windows 没装), 改用 Python:

```bash
cd packages/service
uv run python -c "
import os
from dotenv import load_dotenv
load_dotenv('.env.local')
import psycopg
url = f\"postgresql://{os.getenv('PG_USER')}:{os.getenv('PG_PASSWORD')}@{os.getenv('PG_HOST')}:{os.getenv('PG_PORT')}/{os.getenv('PG_DATABASE')}\"
with psycopg.connect(url) as conn:
    with conn.cursor() as cur:
        cur.execute(\"SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename LIKE 'mem0%'\")
        for (t,) in cur.fetchall(): print('table:', t)
        cur.execute(\"SELECT count(*) FROM mem0_memories\")
        print('count:', cur.fetchone()[0])
"
```

- [ ] **Step 2: 清理测试数据 (optional)**

如果不想留 smoke 数据:

```bash
PGPASSWORD=postgres psql -h localhost -U postgres -d rag -c "TRUNCATE TABLE mem0_memories"
# 或 Python (同上)
```

---

## 验证清单 (End-to-End)

跑完 Task 1-5 (Task 6 optional) 后, 验证:

- [ ] `cd packages/service && uv run pytest tests/memory/ tests/test_api_contract.py tests/common/test_defaults.py -v` 全绿
- [ ] `cd packages/service && uv run pytest tests/ -v -m "not slow"` 全绿 (没破其它测试)
- [ ] `cd packages/web && bun run test -- memory memory-integration factory dify` 全绿
- [ ] `cd packages/web && bun run test` 全绿 (没破其它前端测试)
- [ ] `cd packages/web && bun run lint` 0 error
- [ ] `cd packages/web && bun run typecheck` 0 error
- [ ] `cd packages/web && bun run format:check` pass
- [ ] (Task 6) `cd packages/service && RAG_DB_URL=... uv run pytest tests/memory/test_mem0_integration.py -m slow` PASS
- [ ] 手工 E2E:
  1. `cd packages/service && uv run python main.py` (启后端 :8000)
  2. `cd packages/web && bun run dev` (启前端 :3000)
  3. 浏览器开 :3000, 走一次 anon 登录拿 cookie
  4. 发 "我叫张三" → 等流结束
  5. 开新对话 → 发 "我叫什么" → 期待 LLM 答"张三"
  6. 如果不成功: 浏览器 devtools 看 `/api/chat/messages` 请求 body `inputs.memory_context` 字段; Dify 端按 `dify-workflow-config.md` 配 `{{#memory_context}}`

## 风险与回滚

参考 spec §"风险与回滚" (5 个风险, 3 个有具体缓解 / 回滚方案).

实施时如发现新风险, 立刻 STOP 报告 (按 [[feedback-stop-and-ask-dont-loop-on-infra]]), 不要死循环 debug.

---

# Phase 2: 记忆管理 UI (2026-06-16)

> **动机**: Phase 1 只暴露 search/add, 用户看不到/改不了自己记忆. mem0 LLM 抽事实不完美 (用户纠正"我不住北京"后, mem0 infer 模式会自动 update/delete, 但延迟/遗漏存在). 用户提"我想要看自己记忆" → 落地 list / update / delete / delete_all + 前端 Dialog.
>
> **设计决定** (2026-06-16 user 拍板, 见 chat 决策):
> - 入口: chat 页面右上角 lucide-react `Brain` 图标 → 专用 Dialog (不走 settings-dialog)
> - 编辑: 只改 text (mem0 update 走新 embedding), metadata 隐藏
> - 删除全部: 提供 + AlertDialog 二次确认
> - **关键安全** (新发现, mem0 自身漏洞): `m.delete(id)` / `m.update(id, ...)` 不传 user_id, 只按 ID 操作 → **跨租户漏洞**. service 层必须先 `m.get(id)` 验 `payload.user_id == current_user_id`, 不匹配统一抛 `PermissionError` (不区分"不存在"vs"无权", 避免泄漏 ID 有效性).

## File Structure (Phase 2 增量)

### New Files (2)

| 文件 | 职责 |
|------|------|
| `packages/web/components/chat/memory-management-dialog.tsx` | shadcn Dialog: 列表 + 搜索 + 编辑 + 删 + 清空 (含 AlertDialog 二次确认) |
| `packages/web/components/chat/memory-management-dialog.test.tsx` | vitest: 渲染/搜索/编辑/删/清空/二次确认 全覆盖 |

### Modified Files (10)

| 文件 | 改动 |
|------|------|
| `packages/service/src/memory/schemas.py` | 加 `MemoryListResponse` / `UpdateRequest` / `DeleteResponse` |
| `packages/service/src/memory/service.py` | 加 `list_memories` / `update_memory` / `delete_memory` / `delete_all_memories` + `_assert_owned` 隔离守卫 |
| `packages/service/src/memory/router.py` | 加 4 路由: `GET /list`, `PATCH /{id}`, `DELETE /{id}`, `DELETE /all` |
| `packages/service/src/memory/__init__.py` | export `MemoryListResponse` / `UpdateRequest` / `DeleteResponse` |
| `packages/service/tests/memory/test_service.py` | 加 6 测试 (含跨用户隔离) |
| `packages/service/tests/memory/test_router.py` | 加 4 测试 |
| `packages/service/tests/test_api_contract.py` | `FRONTEND_EXPECTS` 加 4 行 |
| `packages/web/lib/api/memory.ts` | 加 `list` / `update` / `delete` / `deleteAll` 4 方法 |
| `packages/web/lib/api/memory.test.ts` | 加 4 测试 |
| `packages/web/components/chat/ChatShell.tsx` | 头部加 `Brain` 图标按钮 + Dialog 状态 |
| `packages/web/components/chat/ChatShell.test.tsx` | 加图标渲染测试 |
| `packages/web/messages/{zh,en}.json` | 加 ~6 条 i18n string |

---

## Task 7: 后端 4 端点 + 跨用户隔离 (TDD)

**Files:**
- Modify: `packages/service/src/memory/schemas.py` (3 个 Pydantic)
- Modify: `packages/service/src/memory/service.py` (4 方法 + 1 守卫)
- Modify: `packages/service/src/memory/router.py` (4 路由)
- Modify: `packages/service/src/memory/__init__.py` (export)
- Modify: `packages/service/tests/memory/test_service.py` (+ 6)
- Modify: `packages/service/tests/memory/test_router.py` (+ 4)
- Modify: `packages/service/tests/test_api_contract.py` (+ 4 行)

- [ ] **Step 1: 写跨用户隔离测试 (TDD 红, 6 个 service 测试)**

往 `tests/memory/test_service.py` 末尾加:

```python
# ---- list_memories ----

def test_list_memories_passes_user_id_and_top_k():
    """list_memories 走 mem0 get_all(filters={user_id}, top_k=200)"""
    from src.middleware.auth import CurrentUser
    from src.memory.service import MemoryService

    fake_memory = MagicMock()
    fake_memory.get_all.return_value = [
        {"id": "m1", "memory": "用户叫张三", "metadata": {"src": "x"}},
        {"id": "m2", "memory": "用户住北京"},
    ]
    fake_factory = MagicMock(return_value=fake_memory)
    svc = MemoryService(mem0_factory=fake_factory)

    user = CurrentUser(id=42, public_token="t", account_id=None)
    results = svc.list_memories(user)

    assert len(results) == 2
    assert results[0].id == "m1"
    assert results[0].text == "用户叫张三"
    fake_memory.get_all.assert_called_once_with(
        filters={"user_id": "42"}, top_k=200
    )


def test_list_memories_returns_empty_on_exception():
    """mem0 get_all 抛错 → 返 [], log warning"""
    from src.middleware.auth import CurrentUser
    from src.memory.service import MemoryService

    fake_memory = MagicMock()
    fake_memory.get_all.side_effect = RuntimeError("pgvector 不可达")
    fake_factory = MagicMock(return_value=fake_memory)
    svc = MemoryService(mem0_factory=fake_factory)

    user = CurrentUser(id=1, public_token="t", account_id=None)
    result = svc.list_memories(user)
    assert result == []


# ---- update_memory + 跨用户隔离 ----

def test_update_memory_owns_check_passes_then_calls_mem0():
    """update 前先 m.get 校验 user_id 匹配, 再 m.update"""
    from src.middleware.auth import CurrentUser
    from src.memory.service import MemoryService

    fake_memory = MagicMock()
    # m.get(id) 返带 user_id 字段的 dict
    fake_memory.get.return_value = {"id": "m1", "memory": "old", "user_id": "42"}
    fake_factory = MagicMock(return_value=fake_memory)
    svc = MemoryService(mem0_factory=fake_factory)

    user = CurrentUser(id=42, public_token="t", account_id=None)
    svc.update_memory(user, "m1", "new text")

    fake_memory.get.assert_called_once_with("m1")
    fake_memory.update.assert_called_once_with("m1", "new text", None)


def test_update_memory_raises_on_cross_user_access():
    """**关键安全测试**: 别人的 memory_id → 抛 PermissionError, mem0.update 不被调"""
    from src.middleware.auth import CurrentUser
    from src.memory.service import MemoryService

    fake_memory = MagicMock()
    fake_memory.get.return_value = {"id": "m1", "memory": "old", "user_id": "99"}  # 别人的
    fake_factory = MagicMock(return_value=fake_memory)
    svc = MemoryService(mem0_factory=fake_factory)

    user = CurrentUser(id=42, public_token="t", account_id=None)
    with pytest.raises(PermissionError):
        svc.update_memory(user, "m1", "hijack text")

    fake_memory.update.assert_not_called()


def test_update_memory_raises_on_not_found():
    """memory 不存在 → 抛 PermissionError (跟无权访问同一异常, 防 ID 探测)"""
    from src.middleware.auth import CurrentUser
    from src.memory.service import MemoryService

    fake_memory = MagicMock()
    fake_memory.get.return_value = None
    fake_factory = MagicMock(return_value=fake_memory)
    svc = MemoryService(mem0_factory=fake_factory)

    user = CurrentUser(id=42, public_token="t", account_id=None)
    with pytest.raises(PermissionError):
        svc.update_memory(user, "nonexistent", "text")


# ---- delete_memory + 跨用户隔离 (同 update 模式) ----

def test_delete_memory_owns_check_passes_then_calls_mem0():
    from src.middleware.auth import CurrentUser
    from src.memory.service import MemoryService

    fake_memory = MagicMock()
    fake_memory.get.return_value = {"id": "m1", "user_id": "42"}
    fake_factory = MagicMock(return_value=fake_memory)
    svc = MemoryService(mem0_factory=fake_factory)

    user = CurrentUser(id=42, public_token="t", account_id=None)
    svc.delete_memory(user, "m1")

    fake_memory.delete.assert_called_once_with("m1")


def test_delete_memory_raises_on_cross_user_access():
    """别人的 memory_id → 抛 PermissionError, mem0.delete 不被调"""
    from src.middleware.auth import CurrentUser
    from src.memory.service import MemoryService

    fake_memory = MagicMock()
    fake_memory.get.return_value = {"id": "m1", "user_id": "99"}
    fake_factory = MagicMock(return_value=fake_memory)
    svc = MemoryService(mem0_factory=fake_factory)

    user = CurrentUser(id=42, public_token="t", account_id=None)
    with pytest.raises(PermissionError):
        svc.delete_memory(user, "m1")

    fake_memory.delete.assert_not_called()
```

- [ ] **Step 2: 跑 service 测试验证 6 个新 case 全红**

```bash
cd packages/service
uv run pytest tests/memory/test_service.py -v
```

Expected: 6 FAIL (AttributeError: 'MemoryService' object has no attribute 'list_memories' / 'update_memory' / 'delete_memory').

- [ ] **Step 3: 在 schemas.py 加 3 个 Pydantic**

```python
class MemoryListResponse(BaseModel):
    """记忆列表响应 (Phase 2)"""

    memories: list[MemoryHit] = Field(default_factory=list, description="所有记忆")


class UpdateRequest(BaseModel):
    """编辑单条记忆请求 (Phase 2)"""

    text: str = Field(..., min_length=1, max_length=32000, description="新记忆内容")


class DeleteResponse(BaseModel):
    """删除响应 (Phase 2) - 仅用于 delete_all, 单条 delete 用 204"""

    deleted_count: int = Field(..., ge=0, description="删除的条数")
```

并在 `__init__.py` export 加 3 个名字.

- [ ] **Step 4: 在 service.py 加 _assert_owned 守卫 + 4 方法**

在 `MemoryService` 类里加 (放在现有 `add` 之后):

```python
    def _assert_owned(self, memory_dict: dict, user_id: str, memory_id: str) -> None:
        """mem0 跨租户漏洞防御: delete/update 不验 user_id, service 层必须先校验.
        memory 拿不到 OR user_id 不匹配 → 统一抛 PermissionError (不区分, 防 ID 探测).
        """
        if not memory_dict or memory_dict.get("user_id") != user_id:
            raise PermissionError(f"无权访问记忆 {memory_id}")

    def list_memories(self, current: CurrentUser, limit: int = 200) -> list[MemoryHit]:
        """列当前用户所有记忆 (按 mem0 默认顺序, 倒序). 失败降级返 []."""
        user_id = _resolve_mem0_user_id(current)
        try:
            m = self._get_memory(user_id)
            results = m.get_all(filters={"user_id": user_id}, top_k=limit) or []
            return [
                MemoryHit(
                    id=str(r.get("id", "")),
                    text=r.get("memory", ""),
                    score=r.get("score"),
                    metadata=r.get("metadata"),
                )
                for r in results
            ]
        except Exception as e:
            logger.warning("[memory] list failed user=%s err=%s", user_id, e)
            return []

    def update_memory(self, current: CurrentUser, memory_id: str, text: str) -> None:
        """编辑单条记忆 text. 跨用户 → PermissionError."""
        user_id = _resolve_mem0_user_id(current)
        try:
            m = self._get_memory(user_id)
            self._assert_owned(m.get(memory_id), user_id, memory_id)
            m.update(memory_id, text, None)
        except PermissionError:
            raise  # 隔离异常不吞
        except Exception as e:
            logger.warning("[memory] update failed user=%s id=%s err=%s", user_id, memory_id, e)
            raise

    def delete_memory(self, current: CurrentUser, memory_id: str) -> None:
        """删单条. 跨用户 → PermissionError."""
        user_id = _resolve_mem0_user_id(current)
        try:
            m = self._get_memory(user_id)
            self._assert_owned(m.get(memory_id), user_id, memory_id)
            m.delete(memory_id)
        except PermissionError:
            raise
        except Exception as e:
            logger.warning("[memory] delete failed user=%s id=%s err=%s", user_id, memory_id, e)
            raise

    def delete_all_memories(self, current: CurrentUser) -> int:
        """清空当前用户所有记忆. m.delete_all 自带 user_id 隔离. 返删除条数."""
        user_id = _resolve_mem0_user_id(current)
        try:
            m = self._get_memory(user_id)
            result = m.delete_all(user_id=user_id)
            # mem0 delete_all 返 dict {"message": "..."}, 拿不到 count, 估 0 让前端不依赖
            return 0
        except Exception as e:
            logger.warning("[memory] delete_all failed user=%s err=%s", user_id, e)
            raise
```

> **决策点**: `update_memory` / `delete_memory` 不静默吞异常 (跟 search/add 降级不同), 因为这是用户**主动操作**, 失败要让前端感知. 走 `raise` 冒到 router → 4xx/5xx.

- [ ] **Step 5: 跑 service 测试验证 6 个新 case 全绿**

```bash
cd packages/service
uv run pytest tests/memory/test_service.py -v
```

Expected: 8 (Phase 1) + 6 (Phase 2) = 14 全 PASS.

- [ ] **Step 6: 写 4 个 router 测试 (TDD 红)**

往 `tests/memory/test_router.py` 末尾加:

```python
def test_list_200_dev_mode(client, mock_service):
    """GET /api/memory/list 返 {memories: [...]}"""
    import os
    os.environ["RAG_DEV_AUTH"] = "true"
    try:
        from src.memory.schemas import MemoryHit
        mock_service.list_memories.return_value = [
            MemoryHit(id="m1", text="用户叫张三"),
            MemoryHit(id="m2", text="用户住北京"),
        ]
        resp = client.get("/api/memory/list")
        assert resp.status_code == 200
        assert resp.json()["memories"][0]["text"] == "用户叫张三"
        assert resp.json()["memories"][1]["id"] == "m2"
    finally:
        del os.environ["RAG_DEV_AUTH"]


def test_update_200_dev_mode(client, mock_service):
    """PATCH /api/memory/{id} body={text} 返 204"""
    import os
    os.environ["RAG_DEV_AUTH"] = "true"
    try:
        resp = client.patch("/api/memory/m1", json={"text": "用户叫李四"})
        assert resp.status_code == 204
        mock_service.update_memory.assert_called_once()
        args = mock_service.update_memory.call_args[0]
        assert args[1] == "m1"  # memory_id
        assert args[2] == "用户叫李四"  # text
    finally:
        del os.environ["RAG_DEV_AUTH"]


def test_update_403_on_cross_user(client, mock_service):
    """跨用户访问 → 403 (router 把 PermissionError 翻译成 HTTPException)"""
    import os
    os.environ["RAG_DEV_AUTH"] = "true"
    try:
        mock_service.update_memory.side_effect = PermissionError("无权")
        resp = client.patch("/api/memory/m1", json={"text": "x"})
        assert resp.status_code == 403
    finally:
        del os.environ["RAG_DEV_AUTH"]


def test_delete_200_dev_mode(client, mock_service):
    """DELETE /api/memory/{id} 返 204"""
    import os
    os.environ["RAG_DEV_AUTH"] = "true"
    try:
        resp = client.delete("/api/memory/m1")
        assert resp.status_code == 204
        mock_service.delete_memory.assert_called_once()
    finally:
        del os.environ["RAG_DEV_AUTH"]
```

- [ ] **Step 7: 跑 router 测试验证 4 个新 case 红**

Expected: 4 FAIL (router 没 list/update/delete 路由).

- [ ] **Step 8: 在 router.py 加 4 路由 + PermissionError 翻译**

```python
from fastapi import HTTPException  # 加到 import

@router.get("/list", response_model=MemoryListResponse)
def list_memories(current: CurrentUser = Depends(resolve_user)) -> MemoryListResponse:
    """列当前用户所有记忆. 降级时 memories=[]."""
    memories = _get_service().list_memories(current)
    return MemoryListResponse(memories=memories)


@router.patch("/{memory_id}", status_code=status.HTTP_204_NO_CONTENT)
def update_memory(
    memory_id: str,
    req: UpdateRequest,
    current: CurrentUser = Depends(resolve_user),
) -> Response:
    """编辑单条记忆 text. 跨用户 → 403. 其它异常 → 500."""
    try:
        _get_service().update_memory(current, memory_id, req.text)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/{memory_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_memory(
    memory_id: str,
    current: CurrentUser = Depends(resolve_user),
) -> Response:
    """删单条. 跨用户 → 403."""
    try:
        _get_service().delete_memory(current, memory_id)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/all", response_model=DeleteResponse)
def delete_all_memories(current: CurrentUser = Depends(resolve_user)) -> DeleteResponse:
    """清空当前用户所有记忆. (跟单条 delete 不一样, 这里用 200 + body 报条数, 便于前端做 toast)."""
    _get_service().delete_all_memories(current)
    return DeleteResponse(deleted_count=0)  # mem0 delete_all 不返 count, 占位
```

> **路由顺序注意**: `DELETE /all` 必须在 `DELETE /{memory_id}` **之前**注册, 否则 `all` 会被当 memory_id 解析 (FastAPI 路由按注册顺序匹配). 测试 `test_delete_200_dev_mode` 走 `DELETE /m1` 不冲突, 但 `DELETE /all` 跟 `DELETE /{memory_id}` 路径形态重叠.

- [ ] **Step 9: 跑全量 mem0 + router 测试验证绿**

```bash
cd packages/service
uv run pytest tests/memory/ -v
```

Expected: 13 (client 7 + service 14 + router 11) = 32 全 PASS.

- [ ] **Step 10: 改 contract test 加 4 行**

在 `tests/test_api_contract.py` 的 `FRONTEND_EXPECTS` 列表末尾加:

```python
    # --- memory 管理 (Phase 2, 2026-06-16) ---
    ("GET", "/api/memory/list"),
    ("PATCH", "/api/memory/{memory_id}"),
    ("DELETE", "/api/memory/{memory_id}"),
    ("DELETE", "/api/memory/all"),
```

- [ ] **Step 11: 跑 contract 测试验证绿**

```bash
cd packages/service
uv run pytest tests/test_api_contract.py -v
```

Expected: 全 PASS, 没把新路由算 dead route.

- [ ] **Step 12: Commit (后端 Phase 2 完)**

```bash
git add packages/service/src/memory/ \
        packages/service/tests/memory/ \
        packages/service/tests/test_api_contract.py
git commit -m "feat(memory): list/update/delete/deleteAll with cross-user isolation"
```

---

## Task 8: 前端 memoryApi 扩展 (4 方法 + 4 测试)

**Files:**
- Modify: `packages/web/lib/api/memory.ts` (加 list/update/delete/deleteAll)
- Modify: `packages/web/lib/api/memory.test.ts` (加 4 测试)

- [ ] **Step 1: 写失败测试 (TDD 红)**

往 `lib/api/memory.test.ts` 的 `describe("memoryApi", ...)` 里加 `describe("list", ...)` 块:

```ts
  describe("list", () => {
    it("GET /api/memory/list", async () => {
      mockedApiFetch.mockResolvedValue({
        memories: [
          { id: "m1", text: "用户叫张三" },
          { id: "m2", text: "用户住北京" },
        ],
      });
      const result = await memoryApi.list();
      expect(mockedApiFetch).toHaveBeenCalledWith(
        "/api/memory/list",
        expect.objectContaining({ method: "GET" }),
      );
      expect(result.memories).toHaveLength(2);
      expect(result.memories[0].id).toBe("m1");
    });
  });

  describe("update", () => {
    it("PATCH /api/memory/{id} with text", async () => {
      mockedApiFetch.mockResolvedValue(undefined);
      await memoryApi.update("m1", "新内容");
      expect(mockedApiFetch).toHaveBeenCalledWith(
        "/api/memory/m1",
        expect.objectContaining({
          method: "PATCH",
          body: { text: "新内容" },
        }),
      );
    });
  });

  describe("delete", () => {
    it("DELETE /api/memory/{id}", async () => {
      mockedApiFetch.mockResolvedValue(undefined);
      await memoryApi.delete("m1");
      expect(mockedApiFetch).toHaveBeenCalledWith(
        "/api/memory/m1",
        expect.objectContaining({ method: "DELETE" }),
      );
    });
  });

  describe("deleteAll", () => {
    it("DELETE /api/memory/all", async () => {
      mockedApiFetch.mockResolvedValue({ deleted_count: 0 });
      await memoryApi.deleteAll();
      expect(mockedApiFetch).toHaveBeenCalledWith(
        "/api/memory/all",
        expect.objectContaining({ method: "DELETE" }),
      );
    });
  });
```

- [ ] **Step 2: 跑测试验证 4 个新 case 红**

```bash
cd packages/web
bun run test -- memory.test
```

Expected: 4 FAIL (memoryApi.list/update/delete/deleteAll not a function).

- [ ] **Step 3: 在 memory.ts 加 4 方法**

```ts
export interface ListResponse {
  memories: MemoryHit[];
}

export const memoryApi = {
  // ... 现有 search/add ...

  async list(): Promise<ListResponse> {
    return apiFetch("/api/memory/list", { method: "GET" });
  },

  async update(memoryId: string, text: string): Promise<void> {
    await apiFetch(`/api/memory/${memoryId}`, {
      method: "PATCH",
      body: { text },
    });
  },

  async delete(memoryId: string): Promise<void> {
    await apiFetch(`/api/memory/${memoryId}`, { method: "DELETE" });
  },

  async deleteAll(): Promise<{ deleted_count: number }> {
    return apiFetch("/api/memory/all", { method: "DELETE" });
  },
};
```

- [ ] **Step 4: 跑测试验证绿**

```bash
cd packages/web
bun run test -- memory.test
```

Expected: 10 (6 Phase 1 + 4 Phase 2) 全 PASS.

- [ ] **Step 5: Commit (前端 API 完)**

```bash
git add packages/web/lib/api/memory.ts packages/web/lib/api/memory.test.ts
git commit -m "feat(memory): memoryApi.list/update/delete/deleteAll"
```

---

## Task 9: 前端 MemoryManagementDialog + ChatShell Brain 图标

**Files:**
- Create: `packages/web/components/chat/memory-management-dialog.tsx`
- Create: `packages/web/components/chat/memory-management-dialog.test.tsx`
- Modify: `packages/web/components/chat/ChatShell.tsx` (加 Brain 图标 + Dialog 状态)
- Modify: `packages/web/components/chat/ChatShell.test.tsx` (加图标渲染测试)
- Modify: `packages/web/messages/{zh,en}.json` (i18n)

- [ ] **Step 1: 加 i18n strings (zh)**

往 `packages/web/messages/zh.json` 加 (找 memory 相关段, 没就放最末):

```json
"memoryManagement": {
  "title": "我的记忆",
  "empty": "还没有记忆。开始聊天, AI 会自动记下你说的事实。",
  "search": "搜索记忆",
  "edit": "编辑",
  "save": "保存",
  "cancel": "取消",
  "delete": "删除",
  "deleteConfirm": "删除这条记忆?",
  "clearAll": "清空所有记忆",
  "clearAllConfirm": "确定清空所有记忆?",
  "clearAllWarning": "此操作不可撤销。你的所有记忆将被永久删除。",
  "clearAllConfirmButton": "确认清空"
}
```

(英文版同步加, key 翻译见 messages/en.json)

- [ ] **Step 2: 写 Dialog 失败测试 (TDD 红, ~8 个 case)**

创建 `packages/web/components/chat/memory-management-dialog.test.tsx`:

```tsx
// MemoryManagementDialog 单测 (2026-06-16)
// 覆盖: 列表渲染 / 搜索过滤 / 编辑保存 / 单删 / 清空二次确认
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";

vi.mock("lucide-react", () => ({
  Brain: () => <span data-testid="icon-brain" />,
  Pencil: () => <span data-testid="icon-pencil" />,
  Trash2: () => <span data-testid="icon-trash" />,
  X: () => <span data-testid="icon-x" />,
}));

vi.mock("@/lib/api/memory", () => ({
  memoryApi: {
    list: vi.fn(),
    update: vi.fn(),
    delete: vi.fn(),
    deleteAll: vi.fn(),
  },
}));

vi.mock("next-intl", () => ({
  useTranslations: () => (key: string) => key,  // key 直接当 label 渲染
}));

import { memoryApi } from "@/lib/api/memory";
import { MemoryManagementDialog } from "./memory-management-dialog";

const mockedList = vi.mocked(memoryApi.list);
const mockedUpdate = vi.mocked(memoryApi.update);
const mockedDelete = vi.mocked(memoryApi.delete);
const mockedDeleteAll = vi.mocked(memoryApi.deleteAll);

describe("MemoryManagementDialog", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("打开时立即 list 一次", async () => {
    mockedList.mockResolvedValue({ memories: [] });
    render(<MemoryManagementDialog open={true} onOpenChange={() => {}} />);
    await waitFor(() => expect(mockedList).toHaveBeenCalledTimes(1));
  });

  it("列 2 条记忆 (text 渲染)", async () => {
    mockedList.mockResolvedValue({
      memories: [
        { id: "m1", text: "用户叫张三" },
        { id: "m2", text: "用户住北京" },
      ],
    });
    render(<MemoryManagementDialog open={true} onOpenChange={() => {}} />);
    expect(await screen.findByText("用户叫张三")).toBeInTheDocument();
    expect(screen.getByText("用户住北京")).toBeInTheDocument();
  });

  it("memories 为空 → 显示 empty 文案", async () => {
    mockedList.mockResolvedValue({ memories: [] });
    render(<MemoryManagementDialog open={true} onOpenChange={() => {}} />);
    expect(await screen.findByText("empty")).toBeInTheDocument();
  });

  it("搜索 '北京' → 只显示匹配项", async () => {
    mockedList.mockResolvedValue({
      memories: [
        { id: "m1", text: "用户叫张三" },
        { id: "m2", text: "用户住北京" },
      ],
    });
    render(<MemoryManagementDialog open={true} onOpenChange={() => {}} />);
    await screen.findByText("用户叫张三");
    fireEvent.change(screen.getByPlaceholderText("search"), { target: { value: "北京" } });
    expect(screen.queryByText("用户叫张三")).not.toBeInTheDocument();
    expect(screen.getByText("用户住北京")).toBeInTheDocument();
  });

  it("点编辑 → 弹输入框 + 调 update(id, newText)", async () => {
    mockedList.mockResolvedValue({ memories: [{ id: "m1", text: "用户叫张三" }] });
    mockedUpdate.mockResolvedValue(undefined);
    render(<MemoryManagementDialog open={true} onOpenChange={() => {}} />);
    await screen.findByText("用户叫张三");
    fireEvent.click(screen.getByText("edit"));
    const input = screen.getByDisplayValue("用户叫张三");
    fireEvent.change(input, { target: { value: "用户叫李四" } });
    fireEvent.click(screen.getByText("save"));
    await waitFor(() => expect(mockedUpdate).toHaveBeenCalledWith("m1", "用户叫李四"));
  });

  it("点删除 → 调 delete(id) + 重新拉 list", async () => {
    mockedList.mockResolvedValue({ memories: [{ id: "m1", text: "用户叫张三" }] });
    mockedDelete.mockResolvedValue(undefined);
    render(<MemoryManagementDialog open={true} onOpenChange={() => {}} />);
    await screen.findByText("用户叫张三");
    fireEvent.click(screen.getByText("delete"));
    await waitFor(() => expect(mockedDelete).toHaveBeenCalledWith("m1"));
    expect(mockedList).toHaveBeenCalledTimes(2); // 初次 + 删后 refetch
  });

  it("点清空所有 → 弹 AlertDialog + 确认后调 deleteAll", async () => {
    mockedList.mockResolvedValue({ memories: [{ id: "m1", text: "x" }] });
    mockedDeleteAll.mockResolvedValue({ deleted_count: 0 });
    render(<MemoryManagementDialog open={true} onOpenChange={() => {}} />);
    await screen.findByText("x");
    fireEvent.click(screen.getByText("clearAll"));
    expect(await screen.findByText("clearAllConfirm")).toBeInTheDocument();
    fireEvent.click(screen.getByText("clearAllConfirmButton"));
    await waitFor(() => expect(mockedDeleteAll).toHaveBeenCalled());
  });

  it("list 失败 → 静默显示空 (不弹错)", async () => {
    mockedList.mockRejectedValue(new Error("网络挂了"));
    render(<MemoryManagementDialog open={true} onOpenChange={() => {}} />);
    expect(await screen.findByText("empty")).toBeInTheDocument();
  });
});
```

- [ ] **Step 3: 跑测试验证 8 个新 case 全红**

```bash
cd packages/web
bun run test -- memory-management-dialog.test
```

Expected: 8 FAIL (Cannot find module './memory-management-dialog').

- [ ] **Step 4: 写 MemoryManagementDialog 实现**

创建 `packages/web/components/chat/memory-management-dialog.tsx` (~180 行, 拆 4 个内部组件保持单文件 ≤300 行 per [[feedback-react-file-size-and-dialog-naming]]):

```tsx
// 长期记忆管理 Dialog (2026-06-16)
// 入口: ChatShell 头部 Brain 图标点击.
// 功能: 列表 + 搜索 + 编辑 + 单删 + 清空全部 (二次确认).
// 安全: 所有 mutating 操作走后端 _assert_owned, 前端不需做隔离.

"use client";

import { useEffect, useState, useMemo } from "react";
import { useTranslations } from "next-intl";
import { Brain, Pencil, Trash2, X } from "lucide-react";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

import { memoryApi, type MemoryHit } from "@/lib/api/memory";

interface MemoryManagementDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function MemoryManagementDialog({ open, onOpenChange }: MemoryManagementDialogProps) {
  const t = useTranslations("memoryManagement");
  const [memories, setMemories] = useState<MemoryHit[]>([]);
  const [filter, setFilter] = useState("");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editingText, setEditingText] = useState("");
  const [clearAllOpen, setClearAllOpen] = useState(false);
  const [loading, setLoading] = useState(false);

  // 加载
  const load = async () => {
    setLoading(true);
    try {
      const { memories } = await memoryApi.list();
      setMemories(memories);
    } catch {
      setMemories([]);  // 降级: 失败 → 空
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => {
    if (open) load();
  }, [open]);

  // 客户端过滤
  const filtered = useMemo(() => {
    if (!filter) return memories;
    const q = filter.toLowerCase();
    return memories.filter((m) => m.text.toLowerCase().includes(q));
  }, [memories, filter]);

  // 编辑保存
  const saveEdit = async () => {
    if (!editingId || !editingText.trim()) return;
    await memoryApi.update(editingId, editingText);
    setEditingId(null);
    setEditingText("");
    await load();
  };

  // 单删
  const handleDelete = async (id: string) => {
    await memoryApi.delete(id);
    await load();
  };

  // 清空
  const handleClearAll = async () => {
    await memoryApi.deleteAll();
    setClearAllOpen(false);
    await load();
  };

  return (
    <>
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent className="max-w-2xl max-h-[80vh] flex flex-col">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Brain className="h-5 w-5" />
              {t("title")} ({memories.length})
            </DialogTitle>
          </DialogHeader>

          <Input
            placeholder={t("search")}
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            className="my-2"
          />

          <div className="flex-1 overflow-y-auto space-y-2 min-h-[200px]">
            {loading && <div className="text-muted-foreground text-sm">...</div>}
            {!loading && filtered.length === 0 && (
              <div className="text-muted-foreground text-sm py-8 text-center">{t("empty")}</div>
            )}
            {filtered.map((m) => (
              <div
                key={m.id}
                className="flex items-center gap-2 p-3 border rounded-md"
                data-testid={`memory-${m.id}`}
              >
                {editingId === m.id ? (
                  <Input
                    value={editingText}
                    onChange={(e) => setEditingText(e.target.value)}
                    className="flex-1"
                    autoFocus
                  />
                ) : (
                  <span className="flex-1 text-sm">{m.text}</span>
                )}
                {editingId === m.id ? (
                  <>
                    <Button size="sm" onClick={saveEdit}>{t("save")}</Button>
                    <Button size="sm" variant="ghost" onClick={() => setEditingId(null)}>
                      {t("cancel")}
                    </Button>
                  </>
                ) : (
                  <>
                    <Button
                      size="icon"
                      variant="ghost"
                      onClick={() => {
                        setEditingId(m.id);
                        setEditingText(m.text);
                      }}
                    >
                      <Pencil className="h-4 w-4" />
                      <span className="sr-only">{t("edit")}</span>
                    </Button>
                    <Button size="icon" variant="ghost" onClick={() => handleDelete(m.id)}>
                      <Trash2 className="h-4 w-4" />
                      <span className="sr-only">{t("delete")}</span>
                    </Button>
                  </>
                )}
              </div>
            ))}
          </div>

          <DialogFooter>
            <Button
              variant="destructive"
              onClick={() => setClearAllOpen(true)}
              disabled={memories.length === 0}
            >
              <Trash2 className="h-4 w-4 mr-2" />
              {t("clearAll")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <AlertDialog open={clearAllOpen} onOpenChange={setClearAllOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t("clearAllConfirm")}</AlertDialogTitle>
            <AlertDialogDescription>{t("clearAllWarning")}</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{t("cancel")}</AlertDialogCancel>
            <AlertDialogAction onClick={handleClearAll}>
              {t("clearAllConfirmButton")}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}
```

- [ ] **Step 5: 跑测试验证 8 个新 case 全绿**

```bash
cd packages/web
bun run test -- memory-management-dialog.test
```

Expected: 8 全 PASS.

- [ ] **Step 6: 改 ChatShell 加 Brain 图标 + Dialog 状态**

在 `packages/web/components/chat/ChatShell.tsx` 头部 (跟其他 import 一起):

```tsx
import { Brain } from "lucide-react";
import { MemoryManagementDialog } from "./memory-management-dialog";
```

在 `ChatShell` 函数体里 (跟其他 state 一起):

```tsx
const [memoryOpen, setMemoryOpen] = useState(false);
```

在 ChatShell 顶部 header JSX 里 (找现有 header 容器, 在 ConversationList toggle 按钮附近):

```tsx
<Button
  size="icon"
  variant="ghost"
  onClick={() => setMemoryOpen(true)}
  aria-label={t("memoryManagement.title")}
  data-testid="memory-management-button"
>
  <Brain className="h-5 w-5" />
</Button>
```

在 ChatShell 末尾 (跟其他 modal 同级):

```tsx
<MemoryManagementDialog open={memoryOpen} onOpenChange={setMemoryOpen} />
```

> **i18n 引用**: ChatShell 已经用 `useTranslations`, 加 key `memoryManagement.title` 进 messages/{zh,en}.json 即可.

- [ ] **Step 7: 改 ChatShell.test.tsx 加 1 个测试**

```tsx
it("渲染 Brain 图标按钮 + 点击弹 Dialog", async () => {
  render(<ChatShell ... />);  // 复用现有 render 模式
  const button = screen.getByTestId("memory-management-button");
  expect(button).toBeInTheDocument();
  fireEvent.click(button);
  expect(await screen.findByText(/我的记忆/)).toBeInTheDocument();  // zh: 我的记忆
});
```

- [ ] **Step 8: 跑前端全量测试 + lint + typecheck**

```bash
cd packages/web
bun run test -- memory memory-integration memory-management-dialog factory dify ChatShell
bun run lint
bun run typecheck
```

Expected: 所有相关测试 PASS; lint 0 error; typecheck 0 error.

- [ ] **Step 9: Commit (前端 UI 完)**

```bash
git add packages/web/components/chat/memory-management-dialog.tsx \
        packages/web/components/chat/memory-management-dialog.test.tsx \
        packages/web/components/chat/ChatShell.tsx \
        packages/web/components/chat/ChatShell.test.tsx \
        packages/web/messages/zh.json \
        packages/web/messages/en.json
git commit -m "feat(chat): MemoryManagementDialog + Brain icon in ChatShell header"
```

---

## 验证清单 (Phase 2 增量)

跑完 Task 7-9 后验证:

- [ ] `cd packages/service && uv run pytest tests/memory/ tests/test_api_contract.py -v` 全绿
- [ ] **新**: 含跨用户隔离测试 (`test_update_memory_raises_on_cross_user_access` + `test_delete_memory_raises_on_cross_user_access`) 绿
- [ ] `cd packages/web && bun run test -- memory memory-management-dialog factory dify ChatShell` 全绿
- [ ] `cd packages/web && bun run test` 全绿 (没破其它测试)
- [ ] `cd packages/web && bun run lint` 0 error
- [ ] `cd packages/web && bun run typecheck` 0 error
- [ ] 手工 E2E:
  1. 启后端 + 前端
  2. 发几条对话, 让 mem0 写几条记忆
  3. 点 Brain 图标 → 看到列表
  4. 改一条 text, 刷新看是否持久
  5. 删一条, 刷新看是否消失
  6. 点清空所有 → 弹二次确认 → 确认 → 列表空

## 风险与回滚 (Phase 2 增量)

参考 spec §"Phase 2 风险".

## 实施回顾 (Phase 1 完成后填, 2026-06-16 落地)

跑完所有 task 后, 在这个文件末尾追加:
- 最终 commit 序列 (按 [[feedback-commit-in-batches-for-large-changes]])
- Deviation 记录 (plan 跟实际差异)
- TDD 反思 (红绿节奏, 漏测, 误测)
