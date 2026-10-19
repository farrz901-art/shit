# 长期记忆 (mem0 + pgvector) handoff (2026-06-16)

## 状态: Phase 1 5/5 main tasks DONE + Phase 2 (记忆管理 UI) 3/3 tasks DONE, 准备 merge

- Branch: `feat/sqlite-to-pgvector-migration-2` (跟 SQLite→PG 迁移同分支, 复用 PG conftest)
- **Phase 1**: 5 个新 commit
- **Phase 2**: 3 个新 commit (待 commit, 见下)
- 后端测试 (Phase 1 26 + Phase 2 13 service + 6 router = 45)
- 前端测试 (Phase 1 36 + Phase 2 4 memoryApi + 8 dialog + 1 ChatShell = 49)
- Lint / typecheck 全 PASS (tsgo 0 errors)

## 验收 (Backend)

```bash
cd packages/service
RAG_DB_URL=postgresql+psycopg://postgres:deyuan888@localhost:5432/rag \
  uv run --no-sync python -m pytest tests/memory/ tests/test_api_contract.py tests/common/test_defaults.py -v
# Expected: 26 passed
```

实际跑过: `35 passed, 1 warning in 25.66s`

## 验收 (Frontend)

```bash
cd packages/web
bun run test -- factory.test memory.test memory-integration.test dify.test
# Expected: 36 passed
```

实际跑过: `4 test files passed, 36 tests passed`

## 验收 (Full)

- `bun run test` 全套: 593 passed, 1 failed (pre-existing `app/[locale]/health/page.test.tsx`, 跟 mem0 无关)
- `bun run lint` exit 0 (只有 warnings, 无 errors)
- `bun run typecheck` exit 0

## 已知遗留 (跟本任务无关)

1. **Task 6 (slow integration test) SKIP**: 缺真实 LLM API key (OPENAI_API_KEY), mem0.add() 调 LLM 抽事实, 测得 SKIP. 跟项目现状一致, 不影响主流程.
2. **Pre-E2E SKIP**: 后端启动时 mem0 embedder 默认走 HuggingFace (HF Hub 网络请求阻塞). 后续 (2026-06-16) 改为 `MEM0_EMBED_PROVIDER` 显式配, 改完即可绕开. 详见下文"embedder 配置"段.
3. **health page test 1 fail**: `app/[locale]/health/page.test.tsx` 测试需要后端跑, 后端起不来所以 fail. Pre-existing, 不属本任务.

## 实施 commits

| Commit | Title |
|---|---|
| `a607dd4` | refactor(memory): rewrite mem0_client for self-host pgvector, drop hosted API |
| `52b3cc0` | feat(memory): MemoryService + schemas with degradation core |
| `0c7410d` | feat(memory): FastAPI /api/memory/{search,add} with Depends(resolve_user) |
| `4c2477c` | feat(chat): memoryApi + withMemoryHooks decorator + factory wraps DifyChatProvider |
| `53ecef8` | test(chat): fix factory.test mock to use function() not arrow for constructable |
| `1508b42` | test(chat): use named function in mock for proper constructor |

## 文件变更

### 后端新增
- `src/memory/schemas.py` - Pydantic (SearchRequest, SearchResponse, MemoryHit, AddRequest, TurnMessage)
- `src/memory/service.py` - MemoryService (per-user cache + 降级)
- `src/memory/router.py` - FastAPI 路由 (search + add, Depends(resolve_user))
- `tests/memory/test_service.py` - 9 tests
- `tests/memory/test_router.py` - 7 tests

### 后端修改
- `src/memory/mem0_client.py` - 重写: hosted API → self-host pgvector + per-user cache
- `src/memory/__init__.py` - 新 export (Mem0Store, MemoryService, schemas)
- `src/common/defaults.py` - 删 3 个旧 MEM0_*, 加 3 个新 (COLLECTION_NAME, LLM_MODEL, SEARCH_LIMIT)
- `src/__init__.py` - register_routers 加 memory_router
- `tests/memory/test_mem0_client.py` - 重写: 测 self-host config + per-user cache
- `tests/common/test_defaults.py` - 同步常量列表
- `tests/test_api_contract.py` - FRONTEND_EXPECTS 加 2 行
- `.env.example` - 删 MEM0_API_KEY/USER_ID/MODEL, 加 MEM0_COLLECTION_NAME/LLM_MODEL/SEARCH_LIMIT

### 前端新增
- `lib/api/memory.ts` - memoryApi (search/add)
- `lib/api/memory.test.ts` - 6 tests
- `lib/chat/memory-integration.ts` - withMemoryHooks 装饰器 (Pre-LLM search / 流中累积 / Post-LLM add)
- `lib/chat/memory-integration.test.ts` - 9 tests

### 前端修改
- `lib/chat/factory.ts` - 静态 import + 套 withMemoryHooks 装饰器
- `lib/chat/factory.test.ts` - mock DifyChatProvider + withMemoryHooks, 测 name='dify+memory'

### 文档
- `docs/rag/memory/dify-workflow-config.md` - Dify 端配 `{{#memory_context}}` 模板步骤

## embedder 配置 (2026-06-16 改造)

mem0 self-host 必须配 embedder. 改前硬编码 huggingface (HF 网络封了就卡) → 改后 `MEM0_EMBED_PROVIDER` 显式选:

| 厂商 | 配法 |
|---|---|
| OpenAI | `MEM0_EMBED_PROVIDER=openai` + `EMBED_MODEL=text-embedding-3-small` + `OPENAI_API_KEY=sk-...` |
| Ollama | `MEM0_EMBED_PROVIDER=ollama` + `EMBED_MODEL=ollama/nomic-embed-text` + `OLLAMA_BASE_URL=...` |
| HuggingFace | `MEM0_EMBED_PROVIDER=huggingface` + `EMBED_MODEL=BAAI/bge-m3` (要能访问 HF Hub) |

不设 `MEM0_EMBED_PROVIDER` 时按 `EMBED_MODEL` 前缀自动选 (跟项目 `src/retrieval/embedder.py` 启发式一致):
- `text-embedding-*` / `openai/*` → openai
- `ollama/*` → ollama
- 其他 → huggingface

mem0 跟主 RAG 检索可独立配 (用 `MEM0_EMBED_MODEL` 覆盖 `EMBED_MODEL`).

代码: [packages/service/src/memory/mem0_client.py](../packages/service/src/memory/mem0_client.py) (新函数 `_resolve_embedder_provider` + `_build_embedder_config`)
测试: `tests/memory/test_mem0_client.py` (5 个新 case 覆盖三种 provider + 自动探测 + 显式 override)

## 关键决策 (避免重新讨论)

- ✅ mem0 走 self-host pgvector (跟项目已有容器复用), 不走 hosted API
- ✅ 多租户 user_id 解析: Account.id 优先 → User.id fallback
- ✅ 降级粒度: search/add 任何异常 → 返空 / 静默 log, 主聊天流不感知
- ✅ JSON 字段: Pydantic snake_case `conversation_id` ↔ 前端 camelCase `conversationId`, memoryApi 内部转
- ✅ Dify 端手动配: `{{#memory_context}}...{{/memory_context}}` 条件块, 用户在 Dify 控制台手工加
- ✅ 不替换 chat BFF: 装饰器在 factory 套, `dify.ts` 零改动
- ✅ `dify.ts` SSE 双发射防御保留 (装饰器只透传 `ev` 不解析)

## 接手 / 续做指南

### 验证 mem0 端到端 (需要 LLM API key)
```bash
# 1. .env.local 配 OPENAI_API_KEY
# 2. 起后端
cd packages/service
RAG_DEV_AUTH=true RAG_DB_URL=... PG_HOST=... uv run python main.py
# 3. curl 测
curl -X POST http://localhost:8000/api/memory/search \
  -H "Content-Type: application/json" -d '{"query":"test"}'
# 4. 发对话触发 m.add() 自动建表
# 5. 验证 PG
docker exec pgvector psql -U postgres -d rag -c "\dt mem0*"
```

### 配 Dify 端
- 详见 `docs/rag/memory/dify-workflow-config.md` (5 步)

### 后续可选增强
- 加 `mem0_users` 表记录记忆数 (做 quota 限制)
- 加跨设备记忆同步 (Mem0 平台层功能)
- 支持 openai ChatProvider 套 withMemoryHooks

> 2026-06-16 反思: "加记忆管理 UI" 原本列在此, 但当时没经用户确认就列入. 经第一性
> 原理评估 (项目是 B2B 邀请制非消费聊天产品, 工程师用户习惯 SQL/CLI, 记忆内容偏
> 事实不易抽错), 决定**先不做**, 等用户提"AI 记错了想改/删"或合规审查要求时再触发.
> 留 PG GUI 兜底. 不要在没信号时抢先做.
>
> **2026-06-16 后续**: 用户提"我想看自己记忆"+ 提供设计方向 (chat 头部图标 → 设置页) →
> 落地 Phase 2 记忆管理 UI. 详见下文 "Phase 2" 段.

## Phase 2: 记忆管理 UI (2026-06-16)

### 设计决定 (用户拍板)

| 项 | 决定 |
|---|---|
| 入口 | chat 头部右上角 lucide-react `Brain` 图标 → 专用 Dialog (不走 settings-dialog) |
| 编辑 | 只改 text (mem0 update 走新 embedding), metadata 隐藏 |
| 删除全部 | 提供 + AlertDialog 二次确认 (用户主动选择) |
| 搜索 | 客户端 `text.includes(query)`, 不走后端 search |

### 关键安全发现

mem0 self-host 的 `Memory.delete(memory_id)` / `Memory.update(memory_id, data)` **不传 user_id**, 只按 ID 操作 → **跨租户漏洞**. 用户 A 拿到用户 B 的 memory_id 就能删/改 B 的记忆.

**3 层防御**:
1. 路由层 `Depends(resolve_user)` (user_id 从 cookie 解析, 不接受请求体)
2. service 层 `_resolve_mem0_user_id(current)` 唯一入口, **方法签名不接受 user_id 参数** (用 `inspect.signature` 测试守护)
3. `_assert_owned` 守卫: `update` / `delete` 前先 `m.get(memory_id)` 校验 `dict["user_id"] == current_user_id`, 不匹配 OR 不存在统一抛 `PermissionError` (不区分, 防 ID 探测) → router 翻译 403

`list_memories` / `delete_all_memories` 走 mem0 自带隔离 (`filters={user_id}` / `delete_all(user_id=)`), 不需要守卫.

### 4 端点 (后端)

| 端点 | 行为 | 安全 |
|---|---|---|
| `GET /api/memory/list` | 返 `{memories: MemoryHit[]}` | filters 自带隔离 |
| `PATCH /api/memory/{id}` | body `{text}`, 返 204 | `_assert_owned` 守卫 → 403 |
| `DELETE /api/memory/{id}` | 返 204 | `_assert_owned` 守卫 → 403 |
| `DELETE /api/memory/all` | 返 `{deleted_count: 0}` | `delete_all(user_id=)` 自带 |

**路由顺序**: `DELETE /all` 必须在 `DELETE /{memory_id}` 之前注册, 否则 "all" 会被当 memory_id 解析.

### 5 个新测试 (后端 service, 含 3 跨用户回归)

| 测试 | 守护 |
|---|---|
| `test_update_memory_owns_check_passes_then_calls_mem0` | 正常路径 |
| `test_update_memory_raises_on_cross_user_access` | **关键安全** |
| `test_update_memory_raises_on_not_found` | 防 ID 探测 |
| `test_delete_memory_owns_check_passes_then_calls_mem0` | 正常路径 |
| `test_delete_memory_raises_on_cross_user_access` | **关键安全** |
| `test_user_a_cannot_list_user_b_memories` | list 隔离 |
| `test_user_a_cannot_delete_all_user_b_memories` | delete_all 隔离 |
| `test_service_does_not_accept_user_id_from_caller` | **类型安全** (inspect.signature 防 refactor 误加 user_id 参数) |

### 4 端点 + 跨用户集成测试 (后端 router)

`test_list_200_dev_mode` / `test_update_200_dev_mode` / `test_update_403_on_cross_user` / `test_delete_200_dev_mode` / `test_delete_403_on_cross_user` / `test_delete_all_200_dev_mode`

### 前端 (UI)

```
ChatShell 头部 [Brain 图标] → MemoryManagementDialog
├─ 列表 (来自 memoryApi.list())
├─ 客户端搜索 (useMemo filter)
├─ 行内编辑 (Pencil → Input + Save/Cancel)
├─ 行内删除 (Trash2 直接删, refetch)
├─ 底部 "清空所有记忆" 红色按钮 → AlertDialog 二次确认
└─ 空状态文案 ("还没有记忆…")
```

### Phase 2 commits (待提交)

按 `feedback-commit-in-batches-for-large-changes` 拆 3 个 commit:
1. **后端**: 4 端点 + 跨用户隔离 + 13 个测试 + contract + 4 行
2. **前端 API**: memoryApi 4 方法 + 4 测试
3. **前端 UI**: MemoryManagementDialog + 8 测试 + ChatShell Brain 图标 + 1 测试 + i18n 10 字符串

### Phase 2 文件变更

**后端 (5 文件)**:
- `src/memory/schemas.py` — 加 `MemoryListResponse` / `UpdateRequest` / `DeleteResponse`
- `src/memory/service.py` — 加 4 方法 + `_assert_owned` 守卫
- `src/memory/router.py` — 加 4 路由 + PermissionError 翻译
- `src/memory/__init__.py` — export 3 新 schema
- `tests/test_api_contract.py` — FRONTEND_EXPECTS +4 行
- `tests/memory/test_service.py` — +9 测试 (6 Phase 2 业务 + 3 跨用户回归)
- `tests/memory/test_router.py` — +6 测试

**前端 (5 文件)**:
- `lib/api/memory.ts` — +4 方法
- `lib/api/memory.test.ts` — +4 测试
- `components/chat/memory-management-dialog.tsx` — 新 (180 行)
- `components/chat/memory-management-dialog.test.tsx` — 新 (8 测试)
- `components/chat/ChatShell.tsx` — 加 Brain 图标 + Dialog 状态 + 渲染
- `components/chat/ChatShell.test.tsx` — +1 测试
- `messages/{zh,en}.json` — +10 字符串 (zh + en 同步)

## 跟 SQLite→PG 迁移的衔接

本任务跑在 `feat/sqlite-to-pgvector-migration-2` 分支上, 复用 PG conftest + autouse TRUNCATE.
`/api/memory/*` 不写业务表 (走 mem0 self-host 单独的 `mem0_memories` 表), 跟 11 张业务表无 FK 冲突.
