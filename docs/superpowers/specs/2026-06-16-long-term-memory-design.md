# 长期记忆 (mem0 + pgvector) 设计

**日期**: 2026-06-16
**状态**: Phase 1 已落地, Phase 2 (管理 UI) 2026-06-16 加入设计
**作者**: 设计对话沉淀 (基于 [[../rag/memory/长期记忆.md]])

## Context

[长期记忆.md](../../rag/memory/长期记忆.md) 提出"Dify + Mem0 + pgvector"方案. 项目现状已经有部分代码 ([`src/memory/mem0_client.py`](../../../packages/service/src/memory/mem0_client.py)), 但只是 hosted API 客户端, 没 HTTP 端点, 没前端集成, 没多租户. 本 spec 落地完整链路.

### 现状盘点

**已有**:
- [`mem0ai>=2.0.5`](../../../packages/service/pyproject.toml) 已装
- [`src/memory/mem0_client.py`](../../../packages/service/src/memory/mem0_client.py) `Mem0Store` 封装: `add` / `search` / `delete` / `get_all` / `update` / `clear`
- [`src/memory/__init__.py`](../../../packages/service/src/memory/__init__.py) 暴露便捷函数 `retrieve_with_memory` / `build_memory_enhanced_prompt`
- 6 个单测 (mock `MemoryClient`, 不真连)
- FastAPI 鉴权链路: 浏览器 `rag_user_token` cookie → 服务端 `x-user-token` header → `resolve_user` → `CurrentUser`
- `Account` 表 ([`src/auth/account_models.py`](../../../packages/service/src/auth/account_models.py)) 账号体系已上线, `CurrentUser.account_id` 已能取到

**缺**:
- `Mem0Store` 是单租户: `user_id` 从 env 读默认 "default", 没按请求 user 区分
- 走 hosted API (MemoryClient + MEM0_API_KEY), 跟项目"本地化优先"理念冲突, 跟已有 pgvector 容器不跟
- 没 FastAPI router 暴露 mem0 端点
- 前端 `dify.ts` 链路不感知记忆

### 决策记录 (用户 2026-06-16)

- **Q1: mem0 实际走哪个后端?** → 切换 self-host pgvector (跟项目已有 `pgvector/pgvector:pg18` 容器复用, 数据本地化)
- **Q2: 长期记忆用什么 user_id?** → 账号优先 (`Account.id`), anon fallback 到 `User.id` (项目已有 Account 表, 账号体系上线)
- **Q3: 集成层?** → 全在 `dify.ts` 客户端 (前端 FastAPI 直连, Dify 工作流零改动, 单一接入点)
- **Q4: 失败时行为?** → 全部降级 (search/add 失败不阻断聊天, 仅 warning 日志)
- **Q5: 鉴权链路?** → 浏览器直连后端 (cookie 透传) + FastAPI `Depends(resolve_user)` 注入, 跟 `kg` / `approvals` 路由同款
- **Q6: dify.ts 怎么改?** → 不改 dify.ts, 抽 `withMemoryHooks` 装饰器套任意 `ChatProvider`, 在 `lib/chat/factory.ts` 套 1 行

## 目标

1. **FastAPI 暴露 2 个端点** (`/api/memory/search`, `/api/memory/add`), 跟 `kg` / `approvals` 一致直连 + `Depends(resolve_user)`
2. **mem0 self-host pgvector**: 重写 `mem0_client.py` 用 `Memory.from_config()`, 复用项目已有 pgvector 容器 + `BAAI/bge-m3` embedder
3. **多租户 user_id 解析**: 账号 `Account.id` 优先, anon `User.id` fallback, 单点 `_resolve_mem0_user_id` 函数
4. **前端装饰器**: `withMemoryHooks(inner: ChatProvider)` 抽记忆逻辑, `dify.ts` 零改动, 后期换 provider 不影响记忆层
5. **降级策略**: search/add 任何异常 → 返空 / 静默 log, 主聊天流不感知
6. **Dify 端配合文档**: 用户去 Dify Chatflow 工作流加 `{{#memory_context}}...{{/memory_context}}` 模板 (写到外部文档, 不写代码)
7. **测试覆盖**: 后端 4 个测试文件 (client 单测 / service 单测 / router 集成 / 真连 integration), 前端 2 个 (装饰器 + API)

## 非目标 (YAGNI)

- **不实现 E2E (Playwright)**: 跨 session 验证留到 post-MVP; 单测 + 集成测试已覆盖关键路径
- **不写 Dify 端配置代码**: Dify Chatflow 工作流模板由用户去控制台手配, 文档化步骤
- **不替换 chat BFF (`/api/chat/messages`)**: 该 BFF 有 SSE 流 + `x-chat-token` 特殊处理, `/api/memory/*` 没这需求, 走直连
- **不动 `dify.ts`**: 装饰器在 `factory.ts` 套, 保持 DifyChatProvider 现有 SSE 双发射防御 + `seenMessageRef` 守卫
- **不实现跨设备记忆合并**: 单 `user_id` = 单 `account_id` 隔离, 换 device 不并表 (Mem0 自身会按 user_id 隔离, 但跨 device 同步是平台层功能, 我们不实现)
- **不写数据迁移脚本**: mem0 self-host 自动建表, 首次 `m.add()` 时在 pgvector 里 `CREATE TABLE` + 加 `vector` 扩展; 老 hosted API 记忆数据不迁 (项目当前没人用 hosted, 没有迁移成本)
- **不引入情节记忆 / Neo4j**: 跟 [长期记忆.md §4.3](../../rag/memory/长期记忆.md) 一致, 等基本长期记忆跑顺再加
- **不实现记忆管理 UI (Phase 1)**: Phase 1 范围 (MVP) 用户不能在前端看/删/编辑自己的记忆, 只通过对话间接增删
- **不限制单 user 记忆数量 / 大小**: mem0 自身有 `mem.add()` 去重, 暂不加 quota (Postgres 撑得住小规模)

## 架构总览

```
┌────────────────────────────────────────────────────────────────────┐
│ 浏览器                                                            │
│   │                                                                │
│   ├─ /api/chat/messages (BFF, 现有)  ──Dify SSE 流──>  返回给 UI  │
│   │                                                                │
│   ├─ /api/memory/search (FastAPI 直连) <── 装饰器 Pre-LLM 调        │
│   └─ /api/memory/add    (FastAPI 直连) <── 装饰器 Post-LLM 调       │
│                                                                       │
│ packages/web/lib/chat/                                                │
│   ├─ dify.ts                  ← 不动                                  │
│   ├─ factory.ts               ← 改 1 行: 套 withMemoryHooks            │
│   ├─ memory-integration.ts    ← 新: withMemoryHooks 装饰器             │
│   └─ types.ts                 ← 不动                                  │
│                                                                       │
│ FastAPI (packages/service)                                            │
│   ├─ /api/memory/search ─┐                                            │
│   ├─ /api/memory/add    ─┴─→ memory/router.py                        │
│   │                          ├─ service.py  (降级 + user_id 解析)     │
│   │                          └─ mem0_client.py (重写 self-host)        │
│   │                              └─ Memory.from_config()              │
│   │                                  ├─ LLM: OpenAI / 本地 ollama      │
│   │                                  ├─ Embedder: BAAI/bge-m3          │
│   │                                  └─ vector_store: pgvector         │
│   ▼                                                                    │
│ PostgreSQL pgvector 容器 (已有, 跟 RAG 共享)                            │
└────────────────────────────────────────────────────────────────────┘
```

**关键设计点**:
- `withMemoryHooks` 是纯装饰器, 套任何 `ChatProvider` 都能获得长期记忆能力; 换 LangGraph / 自建 RAG 不动记忆层
- 装饰器内部三段: Pre-LLM search 注入 `inputs.memory_context` / 流中累积 user+assistant turns / 流结束 fire-forget add
- `MemoryService` 集中降级逻辑, router 只做参数校验 + 调 service
- `_resolve_mem0_user_id` 单点 user_id 解析 (账号 → anon fallback)
- 降级粒度: mem0 配置缺失 / 调用异常 / pgvector 不可达 / LLM 限流 全走 `try/except` 兜住

## 文件清单

### 新增

| 文件 | 职责 |
|------|------|
| `packages/service/src/memory/schemas.py` | `SearchRequest` / `SearchResponse` / `AddRequest` Pydantic schemas |
| `packages/service/src/memory/service.py` | `_resolve_mem0_user_id` + `MemoryService` (search/add 降级核心) |
| `packages/service/src/memory/router.py` | `POST /api/memory/search` + `POST /api/memory/add`, `Depends(resolve_user)` |
| `packages/service/tests/memory/test_service.py` | 单测: user_id 解析 / search 降级 / add 降级 / metadata 透传 |
| `packages/service/tests/memory/test_router.py` | 集成: 200/401 路径 / Depends 注入 / 透传到 service |
| `packages/service/tests/memory/test_mem0_integration.py` | 真连 pgvector: search→add→search 闭环 (slow marker) |
| `packages/web/lib/api/memory.ts` | `memoryApi.search/add` 调 `apiFetch` (直连后端) |
| `packages/web/lib/api/memory.test.ts` | 单测: apiFetch 路径 + 错误归一 |
| `packages/web/lib/chat/memory-integration.ts` | `withMemoryHooks` 装饰器 |
| `packages/web/lib/chat/memory-integration.test.ts` | 单测: search 降级 / 流中累积 / add 失败不阻断 |
| `docs/rag/memory/dify-workflow-config.md` | Dify Chatflow 工作流配置步骤 (用户手动操作) |

### 修改

| 文件 | 改动 |
|------|------|
| `packages/service/src/memory/mem0_client.py` | **重写**: 删 `MemoryClient` (hosted), 改 `Memory.from_config()` (self-host pgvector); `Mem0Store` 改成 per-user_id 缓存 |
| `packages/service/src/memory/__init__.py` | export 新增 `MemoryService` / `router` |
| `packages/service/src/__init__.py::register_routers` | 加 `app.include_router(memory_router)` |
| `packages/service/src/common/defaults.py` | 删 `DEFAULT_MEM0_API_KEY` / `DEFAULT_MEM0_USER_ID` / `DEFAULT_MEM0_MODEL`; 加 `DEFAULT_MEM0_COLLECTION_NAME` / `DEFAULT_MEM0_LLM_MODEL` / `DEFAULT_MEM0_SEARCH_LIMIT` |
| `packages/service/.env.example` | 删 `MEM0_API_KEY` / `MEM0_USER_ID`; 加 `MEM0_COLLECTION_NAME` / `MEM0_LLM_MODEL` / `MEM0_SEARCH_LIMIT` |
| `packages/service/tests/memory/test_mem0_client.py` | 改写: `_build_config` env 注入 + per-user_id 缓存复用 |
| `packages/service/tests/common/test_defaults.py` | `test_defaults_module_exports_expected_constants` 删 mem0 旧 key, 加新 key |
| `packages/web/lib/chat/factory.ts` | `getChatProvider` 返 `withMemoryHooks(new DifyChatProvider())` |
| `packages/web/lib/chat/factory.test.ts` | 加测: 返的 provider 是装饰器套过的 (`name` 含 `+memory` 后缀) |
| `packages/web/lib/api/config.ts` | `BFF_PATTERNS` 删 `/api/memory/*` 路径 (走直连) — **等等, BFF_PATTERNS 是 BFF 名单, 走直连意味着不在 BFF_PATTERNS 里就自动走直连, 不需要加** |
| `packages/service/tests/test_api_contract.py` | `FRONTEND_EXPECTS` 加 `/api/memory/search` + `/api/memory/add` |

## API 设计

### 后端

```python
# src/memory/schemas.py
class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000, description="查询文本")
    limit: int = Field(5, ge=1, le=20, description="检索条数")

class MemoryHit(BaseModel):
    id: str
    text: str
    score: float | None = None
    metadata: dict | None = None

class SearchResponse(BaseModel):
    memories: list[MemoryHit] = Field(default_factory=list, description="相关记忆; 降级时为 []")

class TurnMessage(BaseModel):
    role: Literal["user", "assistant"] = Field(..., description="消息角色")
    content: str = Field(..., min_length=1, max_length=32000, description="消息内容")

class AddRequest(BaseModel):
    messages: list[TurnMessage] = Field(..., min_length=1, max_length=20, description="本轮完整对话")
    conversation_id: str | None = Field(None, max_length=128, description="Dify conversation_id, 写到 metadata 便于回溯")
```

```python
# src/memory/router.py
router = APIRouter(prefix="/api/memory", tags=["记忆"])

@router.post("/search", response_model=SearchResponse)
def search(req: SearchRequest, current: CurrentUser = Depends(resolve_user)):
    """按 query 检索当前用户相关记忆; 降级时 memories=[]"""
    return SearchResponse(memories=memory_service.search(current, req.query, req.limit))

@router.post("/add", status_code=204)
def add(req: AddRequest, current: CurrentUser = Depends(resolve_user)):
    """把本轮 user+assistant 完整对话写入记忆; 失败静默"""
    memory_service.add(current, [t.model_dump() for t in req.messages], req.conversation_id)
    return Response(status_code=204)
```

```python
# src/memory/service.py
def _resolve_mem0_user_id(current: CurrentUser) -> str:
    """账号优先, anon fallback User.id; 都用 str 跟 mem0 user_id 类型对齐"""
    return str(current.account_id) if current.account_id is not None else str(current.id)

class MemoryService:
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
            return [MemoryHit(id=str(r.get("id", "")), text=r.get("memory", ""),
                              score=r.get("score"), metadata=r.get("metadata")) for r in results]
        except Exception as e:
            logger.warning("[memory] search failed user=%s err=%s", user_id, e)
            return []

    def add(self, current: CurrentUser, messages: list[dict], conversation_id: str | None) -> None:
        user_id = _resolve_mem0_user_id(current)
        try:
            m = self._get_memory(user_id)
            # add 跟 search 不同: user_id 是直接传, 不在 filters 里
            kwargs = {"messages": messages, "user_id": user_id, "infer": True}
            if conversation_id:
                kwargs["metadata"] = {"conversation_id": conversation_id}
            m.add(**kwargs)
        except Exception as e:
            logger.warning("[memory] add failed user=%s err=%s", user_id, e)
            # 静默: 不重抛, 不写错误响应
```

```python
# src/memory/mem0_client.py (重写)
def _build_config() -> dict:
    return {
        "llm": {"provider": "openai", "config": {
            "api_key": os.getenv("OPENAI_API_KEY", ""),
            "model": os.getenv("MEM0_LLM_MODEL", "gpt-4o-mini"),
        }},
        "embedder": {"provider": "huggingface", "config": {
            "model": os.getenv("EMBED_MODEL", "BAAI/bge-m3"),
        }},
        "vector_store": {"provider": "pgvector", "config": {
            "host": os.getenv("PG_HOST", "localhost"),
            "port": int(os.getenv("PG_PORT", "5432")),
            "user": os.getenv("PG_USER", "postgres"),
            "password": os.getenv("PG_PASSWORD", ""),
            "dbname": os.getenv("PG_DATABASE", "rag"),
            "collection_name": os.getenv("MEM0_COLLECTION_NAME", "mem0_memories"),
        }},
        "version": "v1.1",
    }

def _default_mem0_factory(user_id: str) -> Memory:
    from mem0 import Memory  # lazy import 避循环
    return Memory.from_config(_build_config())

class Mem0Store:
    """保留兼容老调用方 (tests/memory 现有 6 个 test)"""
    def __init__(self, user_id: str):
        self._user_id = user_id
        self._memory: Memory | None = None

    @property
    def memory(self) -> Memory:
        if self._memory is None:
            self._memory = _default_mem0_factory(self._user_id)
        return self._memory

    def search(self, query: str, limit: int = 5) -> list[dict]:
        # 走 mem0 self-host API: filters + top_k
        return self.memory.search(query=query, filters={"user_id": self._user_id}, top_k=limit) or []

    def add(self, messages: list[dict], metadata: dict | None = None) -> None:
        kwargs = {"messages": messages, "user_id": self._user_id, "infer": True}
        if metadata:
            kwargs["metadata"] = metadata
        self.memory.add(**kwargs)
```

### 前端

```typescript
// lib/api/memory.ts
export const memoryApi = {
  search(req: { query: string; limit?: number }): Promise<{ memories: MemoryHit[] }> {
    return apiFetch("/api/memory/search", { method: "POST", body: req });
  },
  add(req: { messages: TurnMessage[]; conversationId?: string }): Promise<void> {
    return apiFetch("/api/memory/add", { method: "POST", body: req });
  },
};

export interface MemoryHit { id: string; text: string; score?: number; metadata?: Record<string, unknown>; }
export interface TurnMessage { role: "user" | "assistant"; content: string; }
```

```typescript
// lib/chat/memory-integration.ts
export function withMemoryHooks(inner: ChatProvider): ChatProvider {
  return {
    name: `${inner.name}+memory`,
    async *sendMessage(req: SendMessageRequest, signal: AbortSignal): AsyncIterable<ChatEvent> {
      // 1. Pre-LLM: 搜相关记忆, 拼成 inputs.memory_context (失败降级为空串)
      let memoryContext = "";
      try {
        const { memories } = await memoryApi.search({ query: req.query, limit: 5 });
        memoryContext = memories.length
          ? `用户相关记忆:\n${memories.map((m) => `- ${m.text}`).join("\n")}`
          : "";
      } catch (e) {
        console.warn("[memory] search failed, fallback", e);
      }
      const enhancedReq: SendMessageRequest = {
        ...req,
        inputs: { ...req.inputs, memory_context: memoryContext },
      };

      // 2. 累积本轮 user + assistant 完整对话 (流式 delta 拼装)
      const turns: TurnMessage[] = [{ role: "user", content: req.query }];
      for await (const ev of inner.sendMessage(enhancedReq, signal)) {
        if (ev.type === "message") {
          const last = turns[turns.length - 1];
          if (last?.role === "assistant") {
            turns[turns.length - 1] = { role: "assistant", content: last.content + ev.delta };
          } else {
            turns.push({ role: "assistant", content: ev.delta });
          }
        }
        yield ev;
      }

      // 3. Post-LLM: fire-and-forget 写记忆 (失败仅 warning, 不阻断)
      const hasAssistant = turns.some((t) => t.role === "assistant");
      if (hasAssistant) {
        memoryApi.add({ messages: turns, conversationId: req.conversationId })
          .catch((e) => console.warn("[memory] add failed", e));
      }
    },
  };
}
```

```typescript
// lib/chat/factory.ts (改 1 行)
export function getChatProvider(): ChatProvider {
  return withMemoryHooks(new DifyChatProvider());
}
```

## 数据契约

**后端 → 前端**:
- `SearchResponse.memories` 永远是数组, 降级时 `[]`; 元素含 `id` / `text` / `score?` / `metadata?`
- `POST /api/memory/add` 成功返 204, 失败返 401 / 500 (跟现有 router 一致); 业务异常被 service 层吞掉, 路由层不感知

**前端 → 后端**:
- `POST /api/memory/search` body: `{ query: string, limit?: int=5 }`
- `POST /api/memory/add` body: `{ messages: [{ role, content }], conversation_id?: string }`
- 走浏览器自动带 `rag_user_token` cookie, 后端 `Depends(resolve_user)` 解析

**mem0 → pgvector**:
- 表由 mem0 self-host 自动建 (首次 `m.add()` 触发 `CREATE TABLE` + `CREATE EXTENSION IF NOT EXISTS vector`)
- 隔离: `user_id` 字段过滤, 单 collection 内多 user 共存 (跟 mem0 默认行为一致)

## 测试策略

### 1. 后端单测 (`tests/memory/test_mem0_client.py` 改写)

```python
def test_build_config_reads_env(monkeypatch):  # _build_config env 注入
def test_default_factory_passes_user_id():  # 验证 user_id 传给 Memory
def test_mem0_store_caches_memory_instance():  # per-user 缓存复用
```

### 2. 后端 service 单测 (`test_service.py` 新)

```python
def test_resolve_mem0_user_id_prefers_account():  # 账号优先
def test_resolve_mem0_user_id_fallback_to_user_id():  # anon fallback
def test_search_returns_empty_on_exception(monkeypatch):  # mem0 抛错 → []
def test_add_silent_on_exception(monkeypatch):  # mem0 抛错 → 不重抛
def test_search_passes_limit_and_query():  # 参数透传
def test_add_includes_conversation_id_in_metadata():  # metadata 透传
```

### 3. 后端 router 集成 (`test_router.py` 新)

```python
def test_search_200_with_token(client, mock_service):  # cookie 鉴权通过
def test_search_401_without_token(client):  # 无 cookie 401
def test_search_returns_empty_memories_on_service_error(client, mock_service):  # 降级透传
def test_add_204_on_success(client, mock_service):
def test_add_401_without_token(client):
def test_add_400_on_invalid_body(client):
def test_resolve_user_dependency_injected(client, mock_service):  # 验证 Depends 拿 CurrentUser
```

### 4. 后端真连 (`test_mem0_integration.py` 新, slow marker)

```python
@pytest.mark.slow
def test_search_add_search_roundtrip(real_mem0_service):  # 真 pgvector
    # 1. add 一条 "用户叫张三"
    # 2. search "这个用户叫什么" → 应命中
    # 3. 用 unique user_id 隔离, 测试结束清理
```

### 5. 前端单测

```typescript
// lib/api/memory.test.ts
describe("memoryApi", () => {
  it("search → apiFetch POST /api/memory/search");
  it("search 4xx/5xx → 抛 ApiError");
  it("add → apiFetch POST /api/memory/add");
  it("add 204 → 返 undefined");
});

// lib/chat/memory-integration.test.ts
describe("withMemoryHooks", () => {
  it("search 失败 → 降级到空 memory_context, 内层 provider 仍被调");
  it("search 成功 → 把 memories 拼成 inputs.memory_context 传内层");
  it("流中 message delta → 累积成单个 assistant turn");
  it("流中多条 message 事件 → 追加到同一 assistant turn");
  it("流结束 → fire-and-forget add, 含 user+assistant turns");
  it("add 失败 → console.warn, 不冒泡");
  it("name 后缀 = 'dify+memory'");
});

// lib/chat/factory.test.ts (加测, 不破现有)
it("getChatProvider 返的 provider 套了 withMemoryHooks", () => {
  const p = getChatProvider();
  expect(p.name).toBe("dify+memory");
});
```

### 6. 契约测试 (`test_api_contract.py`)

按 [CLAUDE.md](../../../.claude/CLAUDE.md) "前端直连路由必须同步更新 FRONTEND_EXPECTS" 规则, 加:

```python
"/api/memory/search",  # POST
"/api/memory/add",     # POST
```

## Dify 端配合 (用户手动操作, 不写代码)

新建 [`docs/rag/memory/dify-workflow-config.md`](../../rag/memory/dify-workflow-config.md), 5 步:

1. 打开 Dify Chatflow 应用 → 编排页
2. 选 "开始" 节点 → "输入变量" 确认有 `memory_context` 字段 (String, required=false); 没有就手动加
3. 选 LLM 节点 → System Prompt 模板末尾加条件块:
   ```
   {{#memory_context}}
   用户历史记忆:
   {{memory_context}}
   {{/memory_context}}
   ```
   (`{{#var}}...{{/var}}` 是 Dify 条件块语法, 变量空时不渲染)
4. 测试: 发"我叫张三" → 新对话 → 发"我叫什么" → 期待答"张三"
5. (可选) `MEM0_LLM_MODEL` 改成便宜模型 (事实抽取不需 GPT-4)

## 验证清单 (粗粒度, 实施切片见 plan)

- [ ] `cd packages/service && uv run pytest tests/memory -v` 全绿 (含 slow 真连测试, 跑时启动 pgvector)
- [ ] `cd packages/service && uv run pytest tests/test_api_contract.py -v` 全绿
- [ ] `cd packages/web && bun run test -- memory-integration memory factory dify` 全绿
- [ ] `cd packages/web && bun run lint` 0 error
- [ ] `cd packages/web && bun run typecheck` 0 error
- [ ] `cd packages/web && bun run format:check` pass
- [ ] `cd packages/service && uv run python main.py` 启动后 `curl -X POST http://localhost:8000/api/memory/search -b "rag_user_token=<dev_token>" -H "Content-Type: application/json" -d '{"query":"test","limit":3}'` 返 `{"memories":[]}` (dev user 真连 pgvector 查得空)
- [ ] 手工端到端: 浏览器开 dev server, 发"我叫张三" → 新对话 → 发"我叫什么" → 看到 Dify 答"张三" (验证 Dify 工作流已配 `{{#memory_context}}`)

## 风险与回滚

**风险 1**: mem0 self-host 首次 `m.add()` 触发建表, pgvector 容器没 `vector` 扩展会失败
- **缓解**: `init_pgvector()` ([`src/retrieval/__init__.py`](../../../packages/service/src/retrieval/__init__.py)) 已有 `CREATE EXTENSION IF NOT EXISTS vector` 逻辑, 启动时跑一次
- **回滚**: 不删 mem0_router, 只 revert `mem0_client.py` 重写

**风险 2**: 流中断 (AbortError) 时 `assistantTurns` 没累积到, `add` 调用带不完整对话
- **影响**: 偶发情况下记忆库里有"半句话", mem0 抽取会忽略 (LLM 看到不完整对话不抽事实)
- **决策**: 接受, 不补 abort 路径

**风险 3**: 前端 `withMemoryHooks` 装饰器跟 DifyChatProvider 流式行为不匹配 (SSE 双发射 / seenMessageRef 守卫)
- **缓解**: 装饰器只透传 `ev` 不解析, DifyChatProvider 双发射防御在内部已就位 ([`dify.ts:62-77`](../../../packages/web/lib/chat/dify.ts#L62-L77)); `factory.test.ts` 加测验证 provider 套了装饰器
- **回滚**: revert `factory.ts` 1 行改动

**风险 4**: `MEM0_LLM_MODEL` 配 `gpt-4o-mini` 走 OpenAI, 但项目可能想用本地 ollama 节省成本
- **缓解**: 配置走 env var, 改 `.env` 即可; 默认值用 `gpt-4o-mini` 跟项目其它 LLM 调用一致
- **回滚**: 不改 .env.example 默认

**风险 5**: pgvector 容器挂了 / 限流, search/add 全部失败, 用户不知道
- **影响**: 临时无记忆, 聊天照常; warning 日志可见, 但前端不暴露
- **决策**: 接受 (跟降级策略一致), 真要监控走 Langfuse (已有) 加 `memory.search.failed` 事件

## 实施切片 (见 plan, 不在本 spec)

按依赖分 5 个 task, 写 `plans/2026-06-16-long-term-memory.md` 时细化:

1. mem0_client.py self-host 重写 + 改 test
2. service.py + schemas + 单测
3. router.py + register_routers + 契约测试
4. 前端 `lib/api/memory.ts` + factory 套装饰器
5. `withMemoryHooks` 装饰器 + 流式累积 + add fire-forget 单测

每 task 走 TDD 红→绿, commit 前跑 lint-staged + 后端 pytest --picked.

---

# Phase 2: 记忆管理 UI (2026-06-16)

**日期**: 2026-06-16
**状态**: 设计中 (追加到 Phase 1 spec)
**触发**: 用户提"我想看自己记忆" → 落地 list / update / delete / delete_all + 前端 Dialog

## Context

Phase 1 只暴露 search/add 端点, 用户无法在 UI 上看/改/删自己的记忆. mem0 的 LLM 抽取 (`infer=True`) 不完美——用户的纠正"我不住北京"可能延迟数轮才被 mem0 自动 update/delete, 中间用户会看到错误事实. 给用户一个"我的记忆"列表 + 手动纠正入口, 是 B2B 邀请制产品 (用户对自己的数据有审计需求) 的合理 UX.

### 关键安全发现 (2026-06-16 调研 mem0 源码)

mem0 self-host 的 `Memory.delete(memory_id)` / `Memory.update(memory_id, data)` **不传 user_id**, 只按 ID 操作. `m.delete_all(user_id=...)` 才有隔离, `m.get_all(filters={...})` 也带 filters, 但 `delete` / `update` 都不带. **这是跨租户漏洞**——用户 A 拿到用户 B 的 memory_id 就能删/改 B 的记忆.

**对策** (service 层强制隔离):
- `update` / `delete` 前先调 `m.get(memory_id)` (返 dict 含 `user_id` 字段, mem0 暴露在 promoted_payload_keys)
- 校验 `dict["user_id"] == current_user_id`
- 不匹配 OR memory 不存在 → 统一抛 `PermissionError` (不区分, 防 ID 探测泄漏)
- 走 `m.update` / `m.delete` 前必过这个守卫, 漏一个就是漏洞

## 目标 (Phase 2)

1. **后端 4 端点**: `GET /list` / `PATCH /{id}` / `DELETE /{id}` / `DELETE /all`, 全部 `Depends(resolve_user)`
2. **跨用户隔离**: service 层 `_assert_owned` 守卫, 失败 → 403, 不区分 not-found / forbidden
3. **前端 memoryApi 扩展**: list / update / delete / deleteAll 4 方法
4. **MemoryManagementDialog 组件**: shadcn Dialog, 列表 + 客户端搜索 + 编辑 + 单删 + 清空 (含 AlertDialog 二次确认)
5. **ChatShell 头部 Brain 图标入口**: lucide-react `Brain`, 点击 → 弹 Dialog
6. **i18n**: zh + en 同步加 memoryManagement 块
7. **完整测试**: 后端 6 service + 4 router + 4 contract; 前端 4 memoryApi + 8 dialog + 1 ChatShell

## 非目标 (Phase 2 YAGNI)

- **不实现记忆搜索 (后端 search 端点)**: 复用 Phase 1 的 search, 不为管理 UI 重复暴露
- **不实现记忆分组 / 标签**: mem0 metadata 支持但 UI 不暴露, v1 简单列表
- **不实现导出 / 导入**: GDPR 通常要求, 但项目当前没用户提, 留待后续
- **不实现审计日志**: 单次操作记日志 (后端 `logger.warning`), 不持久化
- **不实现管理员看所有用户记忆**: 严格隔离, 跟 Phase 1 一致

## 架构 (Phase 2 增量)

```
┌──────────────────────────────────────────────────────────────────┐
│ 浏览器                                                            │
│   │                                                                │
│   ├─ /api/memory/list (FastAPI 直连, GET)  <── Dialog 打开时调     │
│   ├─ /api/memory/{id}  (FastAPI 直连, PATCH) <── 编辑保存时调      │
│   ├─ /api/memory/{id}  (FastAPI 直连, DELETE) <── 单条删除时调     │
│   └─ /api/memory/all   (FastAPI 直连, DELETE) <── 清空时调         │
│                                                                       │
│ packages/web/components/chat/                                          │
│   ├─ ChatShell.tsx  ← 头部加 Brain 图标 + 状态                        │
│   └─ memory-management-dialog.tsx  ← 新 (列表/编辑/删/清空)            │
│                                                                       │
│ FastAPI (packages/service)                                            │
│   ├─ GET /list              ─┐                                          │
│   ├─ PATCH /{id}           ─┤                                          │
│   ├─ DELETE /{id}          ─┼─→ memory/router.py                     │
│   └─ DELETE /all            ─┘   ├─ service.py  (新增 4 方法 + 隔离)  │
│                                  └─ mem0_client.py (复用 Phase 1)     │
│                                       └─ Memory.get_all/update/delete │
│                                          (delete/update 自身不隔离,    │
│                                           靠 service 层补)             │
```

## 文件清单 (Phase 2 增量)

### 新增 (2)

| 文件 | 职责 |
|------|------|
| `packages/web/components/chat/memory-management-dialog.tsx` | shadcn Dialog + AlertDialog: 列表 + 搜索 + 编辑 + 单删 + 清空 (含二次确认) |
| `packages/web/components/chat/memory-management-dialog.test.tsx` | vitest: 8 个 case 覆盖核心交互 |

### 修改 (10)

| 文件 | 改动 |
|------|------|
| `packages/service/src/memory/schemas.py` | 加 `MemoryListResponse` / `UpdateRequest` / `DeleteResponse` |
| `packages/service/src/memory/service.py` | 加 `list_memories` / `update_memory` / `delete_memory` / `delete_all_memories` + `_assert_owned` 守卫 |
| `packages/service/src/memory/router.py` | 加 4 路由, `PermissionError` 翻译为 403 |
| `packages/service/src/memory/__init__.py` | export 3 个新 schema |
| `packages/service/tests/memory/test_service.py` | +6 测试 (含 2 个跨用户隔离核心 case) |
| `packages/service/tests/memory/test_router.py` | +4 测试 |
| `packages/service/tests/test_api_contract.py` | `FRONTEND_EXPECTS` +4 行 |
| `packages/web/lib/api/memory.ts` | +4 方法 (list / update / delete / deleteAll) |
| `packages/web/lib/api/memory.test.ts` | +4 测试 |
| `packages/web/components/chat/ChatShell.tsx` | 头部加 Brain 图标 + Dialog 状态 |
| `packages/web/components/chat/ChatShell.test.tsx` | +1 图标渲染测试 |
| `packages/web/messages/{zh,en}.json` | +memoryManagement 块 (~10 字符串) |

## API 设计 (Phase 2 增量)

### 后端 4 端点

```python
# GET /api/memory/list → MemoryListResponse
class MemoryListResponse(BaseModel):
    memories: list[MemoryHit] = []  # 失败/空时 []

# PATCH /api/memory/{memory_id} body={text} → 204 / 403
class UpdateRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=32000)

# DELETE /api/memory/{memory_id} → 204 / 403
# (无 body)

# DELETE /api/memory/all → DeleteResponse
class DeleteResponse(BaseModel):
    deleted_count: int = 0  # mem0 delete_all 不返 count, 占位
```

```python
# service.py 关键方法签名
class MemoryService:
    def list_memories(self, current: CurrentUser, limit: int = 200) -> list[MemoryHit]:
        """降级: 失败 → []. mem0 get_all(filters={user_id}, top_k=limit)"""

    def update_memory(self, current: CurrentUser, memory_id: str, text: str) -> None:
        """跨用户 → PermissionError (router 翻译 403). 其它异常 → 上抛 500."""

    def delete_memory(self, current: CurrentUser, memory_id: str) -> None:
        """跨用户 → PermissionError. 其它异常 → 上抛."""

    def delete_all_memories(self, current: CurrentUser) -> int:
        """m.delete_all(user_id=user_id) 自带隔离. 失败 → 上抛."""

    def _assert_owned(self, memory_dict: dict | None, user_id: str, memory_id: str) -> None:
        """mem0 delete/update 不验 user_id, service 层必须先校验.
        memory 拿不到 OR user_id 不匹配 → 统一抛 PermissionError.
        """
        if not memory_dict or memory_dict.get("user_id") != user_id:
            raise PermissionError(f"无权访问记忆 {memory_id}")
```

```python
# router.py 新增 (注意路由顺序: /all 必须在 /{id} 之前注册)
@router.get("/list", response_model=MemoryListResponse)
def list_memories(...): ...

@router.patch("/{memory_id}", status_code=204)
def update_memory(...):
    try:
        _get_service().update_memory(...)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e

@router.delete("/{memory_id}", status_code=204)
def delete_memory(...):  # 同上 PermissionError 处理

@router.delete("/all", response_model=DeleteResponse)
def delete_all_memories(...):  # 不抛 PermissionError (自带 user_id 隔离)
```

### 前端 memoryApi 扩展

```typescript
// lib/api/memory.ts 新增
export const memoryApi = {
  // ... 现有 search/add ...

  async list(): Promise<{ memories: MemoryHit[] }> {
    return apiFetch("/api/memory/list", { method: "GET" });
  },

  async update(memoryId: string, text: string): Promise<void> {
    await apiFetch(`/api/memory/${memoryId}`, { method: "PATCH", body: { text } });
  },

  async delete(memoryId: string): Promise<void> {
    await apiFetch(`/api/memory/${memoryId}`, { method: "DELETE" });
  },

  async deleteAll(): Promise<{ deleted_count: number }> {
    return apiFetch("/api/memory/all", { method: "DELETE" });
  },
};
```

### 前端 Dialog 交互

| 行为 | 触发 | 后续 |
|------|------|------|
| 打开 Dialog | ChatShell 头部 Brain 图标 | `memoryApi.list()` 拉全部 |
| 搜索 | 顶部 Input, onChange | 客户端 `filter(text.includes(q))` |
| 编辑 | 行内 Pencil 图标 → Input + Save/Cancel | `memoryApi.update(id, newText)` + refetch |
| 单删 | 行内 Trash 图标 (无二次确认) | `memoryApi.delete(id)` + refetch |
| 清空 | 底部"清空所有记忆"红色按钮 | 弹 AlertDialog → "确认清空" → `memoryApi.deleteAll()` + refetch |

## 数据契约 (Phase 2 增量)

**后端 → 前端**:
- `GET /list` 返 `{memories: MemoryHit[]}`, 降级时 `memories=[]`
- `PATCH /{id}` 成功 204, 跨用户 403, body 校验失败 422
- `DELETE /{id}` 成功 204, 跨用户 403
- `DELETE /all` 成功 200 + `{deleted_count: 0}` (mem0 不返 count, 占位)

**前端 → 后端**:
- `GET /list`: 无 body
- `PATCH /{id}`: `{text: string}` (min 1, max 32000 字符)
- `DELETE /{id}`: 无 body
- `DELETE /all`: 无 body

**错误归一**:
- 401: 鉴权失败 (跟 Phase 1 一致)
- 403: 跨用户访问 (新)
- 404: 不会返 (统一走 403, 防 ID 探测)
- 422: Pydantic 校验 (空 text, 超长)
- 500: 其它 (PG 挂了等) — **不静默**, 让前端弹错

## 测试策略 (Phase 2 增量)

### 后端 service (`test_service.py` +6)

```python
# list_memories (2)
test_list_memories_passes_user_id_and_top_k    # filters={user_id} + top_k=200
test_list_memories_returns_empty_on_exception  # 降级

# update_memory (3) - 含跨用户隔离
test_update_memory_owns_check_passes_then_calls_mem0
test_update_memory_raises_on_cross_user_access    # **关键安全测试**
test_update_memory_raises_on_not_found            # 不存在 → 同一异常

# delete_memory (2) - 同 update
test_delete_memory_owns_check_passes_then_calls_mem0
test_delete_memory_raises_on_cross_user_access    # **关键安全测试**
```

### 后端 router (`test_router.py` +4)

```python
test_list_200_dev_mode          # 返 200 + memories 数组
test_update_200_dev_mode        # 返 204 + update_memory 被调
test_update_403_on_cross_user   # PermissionError → 403
test_delete_200_dev_mode        # 返 204 + delete_memory 被调
```

### 后端契约 (`test_api_contract.py` +4)

```python
("GET", "/api/memory/list"),
("PATCH", "/api/memory/{memory_id}"),
("DELETE", "/api/memory/{memory_id}"),
("DELETE", "/api/memory/all"),
```

### 前端 (`memory.test.ts` +4, `memory-management-dialog.test.tsx` +8, `ChatShell.test.tsx` +1)

| 测试 | 覆盖 |
|------|------|
| `memoryApi.list` 调 GET | 路径 + method |
| `memoryApi.update` 调 PATCH | 路径 + body.text |
| `memoryApi.delete` 调 DELETE | 路径 |
| `memoryApi.deleteAll` 调 DELETE | /all 路径 |
| Dialog 打开立即 list | useEffect |
| Dialog 列 N 条 | 渲染 |
| Dialog 空时显示 empty | UI 降级 |
| Dialog 搜索过滤 | 客户端 filter |
| Dialog 编辑保存 | update 调用 + refetch |
| Dialog 单删 | delete 调用 + refetch |
| Dialog 清空二次确认 | AlertDialog → deleteAll |
| Dialog list 失败 → 静默空 | 降级 |
| ChatShell 渲染 Brain + 点击弹 Dialog | 集成 |

## 风险与回滚 (Phase 2 增量)

**风险 6**: mem0 跨租户漏洞 (核心安全)
- **缓解**: service `_assert_owned` 守卫 + 6 个测试覆盖 (含 2 跨用户核心 case)
- **回归风险**: 后续若加新方法绕过守卫 = 漏洞, code review 重点看
- **回滚**: 删 4 路由 + 还原 service.py, memory 功能退回 Phase 1

**风险 7**: Dialog 在 list 200+ 条记忆时卡顿
- **影响**: 单 user 不太可能有 200+ 条; 业务量小, 接受
- **决策**: 不分页不虚拟滚动, 简化
- **回滚**: 加分页 (但要动 schema 加 page/size)

**风险 8**: Dialog 在编辑中点 Delete/Close → 状态丢失 / 错删
- **影响**: 用户体验差, 但不会损坏数据 (update 调成空会被 mem0 拒, delete 调成错的 memory_id 被隔离挡)
- **决策**: 接受 (简单方案); 后续可加 unsaved changes 提示

**风险 9**: 删全部时 mem0 delete_all 静默失败 (返 dict 但不抛) → 用户以为删了实际没删
- **影响**: 罕见 (mem0 删整表一般不会静默失败), 但影响"清空"这个核心操作
- **缓解**: router 走 try/except 抛 500, 前端 refetch 后应看到空 (验证真删)
- **决策**: 接受, 不二次确认后查 list

## 实施切片 (Phase 2 增量, 见 plan)

Phase 2 加 3 个 task 进 plan `2026-06-16-long-term-memory.md` (Task 7-9):

1. **Task 7**: 后端 4 端点 + 跨用户隔离 (含 service + router + 契约测试)
2. **Task 8**: 前端 `memoryApi` 扩展 4 方法
3. **Task 9**: 前端 `MemoryManagementDialog` + ChatShell Brain 图标

每 task 走 TDD 红→绿, commit 前跑 lint-staged + 后端 pytest --picked. 总共预计 3 个 commit (跟 [[feedback-commit-in-batches-for-large-changes]] 一致).

## 参考

- [长期记忆.md](../../rag/memory/长期记忆.md) — 用户原始方案. **注: 第 2.2 节建议"建一个专用库 (比如 mem0)"是错的** — mem0 self-host pgvector **复用项目已有 `rag` 数据库**, 首次 `m.add()` 时自动建表 (表名 = `MEM0_COLLECTION_NAME`). 详见 plan Step 0 前置验证.
- [mem0_client.py](../../../packages/service/src/memory/mem0_client.py) — 现有 hosted 实现
- [test_mem0_client.py](../../../packages/service/tests/memory/test_mem0_client.py) — 现有 6 个 mock 测试
- [defaults.py](../../../packages/service/src/common/defaults.py) — 项目"无魔法字符串"规范
- [test_defaults.py](../../../packages/service/tests/common/test_defaults.py) — 校验 src 路径下无硬编码
- [middleware/auth.py](../../../packages/service/src/middleware/auth.py) — `CurrentUser` + `resolve_user` 来源
- [account_models.py](../../../packages/service/src/auth/account_models.py) — `Account` 表 schema
- [register_routers](../../../packages/service/src/__init__.py) — router 统一注册点
- [kg/router.py](../../../packages/service/src/kg/router.py) — 现有直连 + Depends 模式参考
- [dify.ts](../../../packages/web/lib/chat/dify.ts) — 装饰器套的内层, 不动
- [factory.ts](../../../packages/web/lib/chat/factory.ts) — 装饰器接入点
- [config.ts BFF_PATTERNS](../../../packages/web/lib/api/config.ts) — 验证 /api/memory/* 不在 BFF 名单 (走直连)
- [chat-sse-refactor-design.md](2026-06-15-chat-sse-refactor-design.md) — 最近的 diffy.ts 改造 spec 格式参考
- [feedback-no-shim-no-minimal-changes](../../../.claude/projects/c--doc-Code-worktrees-rag-refactor/memory/feedback-no-shim-no-minimal-changes.md) — 严禁 shim, 装饰器是真装饰不是 fallback
- [feedback-debug-search-before-loop](../../../.claude/projects/c--doc-Code-worktrees-rag-refactor/memory/feedback-debug-search-before-loop.md) — mem0 集成前先查官方文档确认 self-host API
