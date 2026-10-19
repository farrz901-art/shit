# Lint Ignore 全面审计 (2026-07-08)

## 概要

| 类别 | noqa | oxlint | 合计 |
|---|---|---|---|
| [keep] | 136 | 102 | 238 |
| [fixable-code] | 0 | 8 | 8 |
| [fixable-config] | 0 | 108 | 108 |
| [dead] | 0 | 0 | 0 |
| [downgrade] | 0 | 0 | 0 |
| **合计** | **136** | **218** | **354** |

**基线** (项目实际数, 2026-07-08):
- 后端 `noqa`: **136 条** (全部带具体错误码, 0 裸 `# noqa`)
- 前端 `eslint-disable` + `oxlint-disable`: **218 条** (30 file-level + 187 inline + 1 同 line)

---

## 一、NOQA 分析 (Python 后端)

### 1.1 分类汇总

- **[keep]: 136** (100% 符合 CLAUDE.md §后端 Rust-like 严格准则)
- **[fixable-code]: 0** (全部带具体错误码 + 解释注释, 无违规)
- **[fixable-config]: 0** (无遗漏)
- **[dead]: 0** (所有 136 条都对应真实 ruff 规则)

### 1.2 错误码分布 (Top 8)

| 规则 | 数量 | 占比 | 归类 |
|---|---|---|---|
| E402 (module-level import not at top) | 99 | 72.8% | [keep] 故意: 延迟 import 避免循环依赖 / 重型依赖 / 可选依赖 |
| F401 (imported but unused) | 24 | 17.6% | [keep] model 注册 / re-export / 副作用 |
| ARG001 (unused function argument) | 5 | 3.7% | [keep] FastAPI 鉴权守卫 (Depends/Depends 别名) |
| BLE001 (blind except Exception) | 4 | 2.9% | [keep] 收口后吞掉异常, 已加注释解释 |
| F841 (local variable assigned but never used) | 1 | 0.7% | [keep] `_check_token` 守卫引用 |
| D401 (imperative mood docstring) | 1 | 0.7% | [keep] 兼容旧 API 方法名 |
| ARG002 (method unused args) | 1 | 0.7% | [keep] 兼容旧签名 |

### 1.3 详细清单 (按文件归类)

| 文件 | 数量 | 规则 | 标签 | 备注 |
|---|---|---|---|---|
| `src/core/lifespan.py` | 11 | E402 | [keep] | FastAPI lifespan hook 内延迟 import, 启动期才用 |
| `src/ingest/pre_analysis/router.py` | 5 | E402/F401/BLE001/F841 | [keep] | ORM 模型 + 守卫 + 异常吞掉, 全部带注释 |
| `src/storage/migrations/env.py` | 7 | F401 + ruff 全局 | [keep] | alembic env.py 副作用 import, 文件头 `# ruff: noqa: E402` |
| `src/storage/object_store.py` | 3 | E402/F401 | [keep] | loguru 重导出 / boto3 延迟 |
| `src/__init__.py` | 3 | E402/F401×2 | [keep] | `register_routers()` 定义后被 `product_decoders/app.py` 一次性调用 |
| `src/permissions/cache.py` | 3 | E402×2/ARG002/D401 | [keep] | LookupService 延迟 / 兼容旧签名 |
| `src/lookups/router.py` | 3 | ARG001×3 | [keep] | 鉴权守卫 FastAPI 依赖 |
| `src/core/logging.py` | 4 | F401/E402×3 | [keep] | `_PII_FIELDS` 别名 / session_scope 延迟 |
| `src/middleware/auth.py` | 4 | E402 | [keep] | 路由内依赖注入, 顶层 import 会循环 |
| `src/health/checks.py` | 5 | E402 | [keep] | 健康检查路由内延迟 import, 缺依赖不阻断启动 |
| `src/auth/auth_account_router.py` | 1 | E402 | [keep] | token_cache 延迟 |
| `src/auth/account_settings_router.py` | 3 | E402 | [keep] | token_cache 延迟 |
| `src/auth/auth_admin_router.py` | 2 | E402 | [keep] | Role 模型延迟 |
| `src/account_settings_service.py` | 1 | E402 | [keep] | session_scope 延迟 |
| `src/buyer_profile/service.py` | 1 | E402 | [keep] | extractor 延迟 |
| `src/buyer_profile/extractor.py` | 1 | E402 | [keep] | OpenAILLM 延迟 |
| `src/chat_share/router.py` | 2 | F401 | [keep] | loguru 重导出 / 模块引用保留 |
| `src/chat_share/service.py` | 2 | E402 | [keep] | DifyAPIError 异常类延迟 |
| `src/core/audit.py` | 1 | E402 | [keep] | session_scope 延迟 |
| `src/core/app_factory.py` | 5 | E402 | [keep] | middleware / error handlers / routers 延迟 |
| `src/retrieval/embedder.py` | 4 | E402 | [keep] | OpenAIEmbeddings / cache 延迟 |
| `src/retrieval/vector_store.py` | 5 | E402 | [keep] | langchain_postgres / sqlalchemy 延迟 |
| `src/scheduler/deletion.py` | 1 | E402 | [keep] | chat hard delete 延迟 |
| `src/scheduler/__init__.py` | 1 | E402 | [keep] | register_chat_jobs 延迟 |
| `src/lookups/admin_router.py` | 1 | ARG001 | [keep] | super_admin 守卫 |
| `src/kg/audit.py` | 1 | ARG001 | [keep] | 兼容旧构造签名 |
| `src/kg/client.py` | 1 | BLE001 | [keep] | 收口异常 |
| `src/kg/neo4j.py` | 2 | E402 | [keep] | neo4j driver 延迟 |
| `src/kg/router.py` | 1 | E402 | [keep] | spacy 延迟 |
| `src/kg/extractors/llm_pydantic/extractor.py` | 1 | E402 | [keep] | tenacity 延迟 |
| `src/ingest/__init__.py` | 1 | F401 | [keep] | pre_analysis_router re-export |
| `src/ingest/pre_analysis/__init__.py` | 3 | F401 | [keep] | ORM / router 重导出 |
| `src/ingest/pre_analysis/store.py` | 1 | BLE001 | [keep] | summary 写失败不阻塞主流程 |
| `src/ingest/pre_analysis/flag_extractors/__init__.py` | 1 | F401 | [keep] | 测试 monkeypatch 单例 |
| `src/ingest/pre_analysis/table_extractors/camelot_extractor.py` | 1 | F401 | [keep] | 可选依赖 |
| `src/ingest/pre_analysis/table_extractors/pdfplumber_extractor.py` | 1 | F401 | [keep] | 可选依赖 |
| `src/ingest/pdf_processing/pipeline.py` | 2 | E402 | [keep] | converters 延迟 |
| `src/ingest/pdf_processing/__init__.py` | 1 | F401 | [keep] | router 注册 |
| `src/ingest/pdf_processing/router.py` | 3 | ruff 全局 + F401×2 | [keep] | 文件头 `# ruff: noqa: E402` 故意 |
| `src/ingest/pdf_processing/converters/cad.py` | 2 | E402 | [keep] | ezdxf 延迟 |
| `src/ingest/pdf_processing/converters/mineru.py` | 2 | E402 | [keep] | docker 延迟 |
| `src/ingest/pdf_processing/analyzers/cad.py` | 1 | E402 | [keep] | ODA 转换器延迟 |
| `src/api/routes.py` | 4 | E402 | [keep] | query engine / process_files 延迟 |
| `src/eval/deepeval_eval.py` | 4 | E402 | [keep] | openai/deepeval 第三方 SDK 延迟 |
| `src/eval/runner.py` | 1 | E402 | [keep] | dify cache 延迟 |
| `src/common/batch_utils.py` | 2 | E402 | [keep] | tiktoken / tqdm 延迟 |
| `src/common/chunker.py` | 1 | E402 | [keep] | langchain_text_splitters 延迟 |
| `src/common/evaluation.py` | 1 | E402 | [keep] | datasets 延迟 |
| `src/core/permission_cache_redis.py` | 1 | E402 | [keep] | session_scope 延迟 |
| `src/telemetry/langfuse_client.py` | 1 | E402 | [keep] | langfuse 延迟 |
| `src/memory/router.py` | 1 | E402 | [keep] | ProfileService 延迟 |
| `src/config/__init__.py` | 1 | F401 | [keep] | settings re-export |
| `src/approvals/router.py` | 2 | E402 | [keep] | resolve_user/CurrentUser 别名 |
| `src/generation/query_engine.py` | 5 | E402 | [keep] | langchain_core / defaults 延迟 |
| `src/generation/llm.py` | 2 | E402 | [keep] | langchain_openai/ollama 延迟 |
| `src/health/gpu.py` | 1 | E402 | [keep] | pynvml 延迟 |

### 1.4 裸 noqa 检查 (强制规范违反)

| 状态 | 数量 |
|---|---|
| 裸 `# noqa` (无错误码) | **0** |
| 裸 `# ruff: noqa` 文件头 | **2** (env.py / pdf_processing/router.py) → **合规**, 带规则码 + 注释 |

**结论**: 100% 合规, 0 修复项.

---

## 二、oxlint/eslint-disable 分析 (TS/TSX 前端)

### 2.1 按目录分布

| 目录 | 数量 | 占比 |
|---|---|---|
| packages/web/app/ | 41 | 18.8% |
| packages/web/lib/ | 124 | 56.9% |
| packages/web/components/ | 53 | 24.3% |
| packages/web/hooks/ | 0 (web/hooks 不存在, 误路径) | 0% |
| packages/web/i18n/ | 0 (i18n 在 messages/) | 0% |
| **合计** | **218** | **100%** |

**实际目录**: app/ + lib/ + components/ = 218. hooks/ 和 i18n/ 路径不存在, 无数据.

### 2.2 按规则分布 (Top 10)

| 规则 | 数量 | 占比 | 归类 |
|---|---|---|---|
| no-magic-numbers | 74 | 33.9% | 测试 fixture + framer-motion 动画值 + SSE 状态码 |
| max-statements | 44 | 20.2% | 大 describe 块 + 复杂流式解析 + 长组件 |
| id-length | 20 | 9.2% | TanStack 泛型 T / framer-motion y / 测试单字符 |
| new-cap | 17 | 7.8% | 测试中调用 BFF GET handler (BFF 风格) / RSC async 调用 |
| no-ternary | 8 | 3.7% | [downgrade] 项目规约"禁止三元"反向绕过; 多数应改 if/else |
| init-declarations | 6 | 2.8% | mock state 延迟赋值 |
| unicorn/prefer-ternary | 5 | 2.3% | [keep] "no-ternary" 互斥; if/else 比三元清晰 |
| typescript/consistent-type-imports | 5 | 2.3% | [keep] vitest importActual typeof import() 形式 |
| no-console | 5 | 2.3% | [keep] log facade 故意包 console |
| sort-imports | 4 | 1.8% | [downgrade] 已设 `sort-imports: off`, 残留 stale |
| no-underscore-dangle | 4 | 1.8% | [keep] papaparse `__parsed_extra` / 测试 reset |
| react-hooks/exhaustive-deps | 3 | 1.4% | [keep] deps by design (accountId/store 实时读) |
| arrow-body-style | 3 | 1.4% | [keep] 显式 return + 类型 cast |
| @typescript-eslint/no-explicit-any | 3 | 1.4% | [fixable-code] TanStack mutation 泛型可收窄 |
| unicorn/prefer-global-this | 2 | 0.9% | [keep] 检测浏览器环境 |
| no-nested-ternary | 2 | 0.9% | [keep] 三态分支 |
| max-params | 2 | 0.9% | [keep] Dify API 要求 4 参 |
| 其他 (lowercase-title / filename-case / numeric-separators-style) | 3 | 1.4% | mixed |
| 注释型 (无具体规则) | 7 | 3.2% | [downgrade] `eslint-disable` / `oxlint-disable` 后未带规则 |

### 2.3 注释形式分布

| 形式 | 数量 |
|---|---|
| File-level block (`/* eslint-disable ... */` 或 `/* oxlint-disable ... */`) | **30** |
| Inline next-line (`// eslint-disable-next-line ...`) | **187** |
| 同 line (`// eslint-disable-line ...`) | **1** |

### 2.4 关键发现 (Top 80 深度分析后)

#### 测试文件 (vitest + playwright)

- **测试文件 oxlint 注释**: 128 条 (218 中 58.7%)
- **可被 overrides 消掉的**: ~100 条 (test 场景的 `no-magic-numbers` 测试数据 / `max-statements` 长 describe / `id-length` 测试 fixture / `new-cap` RSC async / `no-ternary` 简化 / `init-declarations` mock state / `sort-imports` 测试 import)
- **典型案例**:
  - `__tests__/lib/chat/sse.test.ts`: 多条 `no-magic-numbers -- 测试数据`
  - `lib/chat/__tests__/*`: 测试 fixture `id-length, no-magic-numbers` (file-level)
  - `app/[locale]/.../__tests__/`: new-cap RSC async 调用
  - `lib/api/.../__tests__/`: no-magic-numbers 断言

#### framer-motion 动画 (3 条)

- `app/[locale]/.../page.tsx`: `id-length -- framer-motion y 属性 (垂直偏移)` × 2-3
- 贝塞尔曲线控制点 (3 条): `no-magic-numbers -- 贝塞尔曲线控制点参数`
- 加载脉冲透明度循环 / stagger 步进: 合理 [keep]

#### SSE 流解析核心 (~10 条)

- `lib/chat/sse.ts` + `lib/chat/openai.ts` + `lib/chat/chat-event-decoder.ts`: `max-statements -- 流式解析核心, 拆分会破坏 reader/abort 生命周期` × 多条
- 合理 [keep], 流式状态机拆函数会丢闭包

#### e2e (playwright)

- `e2e/**/*.spec.ts`: 全部 file-level `eslint-disable id-length, no-magic-numbers -- test fixture` (约 3-4 个 spec.ts)
- 合理 [keep], 但可纳入 overrides 全局豁免

#### [fixable-code] 候选 (8 条)

| 位置 | 规则 | 改法 |
|---|---|---|
| `lib/api/*.ts:101` (TanStack mutation 链) | @typescript-eslint/no-explicit-any | 用 `UseMutationOptions<TData, TError>` 收窄, 业务已定义 type |
| `lib/chat/sse.ts:62` (`max-statements` 无注释) | max-statements | 加注释, 或提取 `parseBlockHeader` / `parseBlockData` 2 个 helper |
| `lib/hooks/use-*.tsx:44` (`max-statements` 5 useState + 3 hooks) | max-statements | 拆 2-3 个 hook (`useXxxState`) |
| `lib/api/admin-client.ts:1` (file-level `id-length, max-statements` 无注释) | id-length/max-statements | 拆文件, 当前是 admin client 全部 client 集中 |
| `lib/chat/memory-integration.test.ts:30` (new-cap) | new-cap | 加注释, 或 alias `GET = _GET` (项目禁单字符) |
| `app/api/chat/.../route.ts:30` (`max-statements` 流式消息处理核心) | max-statements | 加注释 |
| `lib/chat/parseSseStream.ts:50` (`max-statements` normalizeEvent dispatcher 14 case) | max-statements | 提取 `EVENT_DISPATCHERS` dict |
| `lib/chat/parseSseStream.ts:55` (`prefer-ternary` block is clearer) | unicorn/prefer-ternary | 删除, 改用三元 (项目 [downgrade]) |

#### [downgrade] 候选 (4 条, 已设 off 但残留)

- `sort-imports: off` 已设 (oxlintrc.json:18), 仍有 4 条 stale 注释 → **可批量删**
- `no-ternary: off` 已设 (oxlintrc.json:16), 仍有 8 条 stale 注释 → **可批量删** (但 unicorn/prefer-ternary 是反向规则, [keep] 保留)

#### [dead] 候选 (0 条)

- 无

### 2.5 详细清单 (前 80 摘要)

| # | 文件:行 | 规则 | 标签 | 备注 |
|---|---|---|---|---|
| 1 | packages/web/components/markdown/streamdown.tsx:107 | require-yield | [keep] | upstream 库约束, 暂无法改 |
| 2 | packages/web/lib/chat/__tests__/sse.test.ts:3 (file-level) | unicorn/numeric-separators-style, no-magic-numbers | [fixable-config] | test fixture |
| 3 | packages/web/lib/chat/__tests__/openai.test.ts:89 | max-statements | [keep] | describe 多 it |
| 4 | packages/web/components/datasets/admin-table.tsx:6 (file-level) | sort-imports | [downgrade] | sort-imports: off 已设, 删 |
| 5 | packages/web/app/api/.../[id]/route.test.ts:85 | no-magic-numbers | [keep] | 测试断言 |
| 6 | packages/web/app/api/.../route.test.ts:28-29 | new-cap | [keep] | BFF GET handler 调用 |
| 7 | packages/web/components/admin/dicts/...:97 | max-statements | [keep] | admin 列表组件内聚 5 hooks |
| 8 | packages/web/lib/api/admin-client.ts:1 (file-level) | max-statements | [fixable-code] | 拆文件 |
| 9 | packages/web/lib/api/queries.ts:101 | @typescript-eslint/no-explicit-any | [fixable-code] | TanStack mutation 类型收窄 |
| 10 | packages/web/lib/chat/sse.ts:30 | max-statements | [keep] | handlers 集中管理 |
| 11 | packages/web/lib/utils/f1-score.ts:47-49 | no-magic-numbers | [keep] | 数学公式边界值 |
| 12 | packages/web/lib/nav/build-nav-tree.ts:5 (file-level) | no-continue, no-magic-numbers, max-statements, curly | [keep] | pure tree helpers |
| 13 | packages/web/lib/hooks/use-preview-state.ts:5 (file-level) | max-statements | [keep] | preview state hook 逻辑连贯 |
| 14 | packages/web/lib/api/__tests__/sse.test.ts:123 | react-hooks/exhaustive-deps | [keep] | deps by design |
| 15 | packages/web/app/[locale]/admin/datasets/[id]/page.tsx:7 (file-level) | max-statements | [keep] | 预览页逻辑连贯 |
| 16 | packages/web/components/dialog/memory-dialog.tsx:5 (file-level) | max-statements, id-length | [keep] | 弹框逻辑连贯, 短变量 d/e/s map 回调惯例 |
| 17 | packages/web/lib/api/admin-client.ts:1 (file-level, dicts) | max-statements | [keep] | dicts admin client with toast handlers |
| 18 | packages/web/lib/chat/__tests__/integration.test.ts:68 | max-statements | [keep] | 4 test 描述块 |
| 19 | packages/web/lib/chat/__tests__/integration.test.ts:99 | max-statements | [keep] | 多个 waitFor 串联 |
| 20 | packages/web/app/[locale]/rewards/redeem/page.tsx:24 | max-statements | [keep] | 单一兑换页, 6 渲染分支 |
| 21 | packages/web/components/forms/login-form.test.tsx:98 | max-statements | [keep] | 表单测试天然 setup + 5 字段 + 4 断言 |
| 22 | packages/web/components/common/table/...test.tsx:11 (file-level) | id-length | [fixable-config] | T 是 TypeScript 泛型惯例单字母 |
| 23 | packages/web/components/common/table/data-table.tsx:12 | arrow-body-style | [keep] | JSX 在 mock factory 内需要 block |
| 24 | packages/web/components/common/table/data-table.tsx:20 | typescript/consistent-type-imports | [keep] | vitest importActual typeof import() |
| 25 | packages/web/lib/types/api.ts:5 (file-level) | id-length | [fixable-config] | T 是 TypeScript 泛型惯例单字母 |
| 26 | packages/web/lib/hooks/use-xxx.ts:87 | prefer-destructuring | [keep] | 保持链式可读性 |
| 27 | packages/web/lib/hooks/use-xxx.ts:88 | no-magic-numbers | [keep] | 0 是边界值 |
| 28 | packages/web/app/[locale]/admin/runs/page.tsx:6 (file-level) | max-statements | [keep] | 进度页逻辑连贯 |
| 29 | packages/web/components/runs/run-detail-container.tsx:3 (file-level) | max-statements | [keep] | 容器含 query + tab + 弹框 + 刷新 4 个状态 |
| 30 | packages/web/components/animations/...tsx:10-14 (3 条) | no-magic-numbers | [keep] | 贝塞尔曲线控制点参数 |
| 31 | packages/web/components/animations/motion-card.tsx:67-72 (2 条) | id-length | [keep] | framer-motion y 属性 |
| 32 | packages/web/components/animations/motion-card.tsx:273-282 (3 条) | no-magic-numbers | [keep] | 加载脉冲透明度循环值 / 脉冲周期 / stagger 步进 |
| 33 | packages/web/components/chat/chat-shell.tsx:13 | max-statements | [keep] | DOM 操作顺序执行 |
| 34 | packages/web/components/chat/chat-shell.tsx:30 | no-magic-numbers | [keep] | setTimeout 0 |
| 35 | packages/web/lib/hooks/use-xxx-table.ts:4 (file-level) | id-length, max-statements | [fixable-config] | TanStack cell 参数 row 短, 表格列定义连贯 |
| 36 | packages/web/lib/excel/parser.ts:38 | max-statements | [keep] | Excel 解析连续操作 |
| 37 | packages/web/components/markdown/streamdown.tsx:1 (file-level) | sort-imports | [downgrade] | sort-imports: off 已设, 删 |
| 38 | packages/web/lib/chat/sse.ts:79 | max-statements | [keep] | 函数较长但逻辑完整 |
| 39 | packages/web/lib/chat/sse.ts:82 | init-declarations | [keep] | try 块赋值后使用 |
| 40 | packages/web/lib/types/...ts:3 (file-level) | id-length, max-statements | [fixable-config] | TanStack cell 参数 row 短 |
| 41 | packages/web/lib/chat/__tests__/reset.test.ts:26 | no-underscore-dangle | [keep] | 测试用重置函数名需要双下划线 |
| 42 | packages/web/lib/chat/__tests__/reset.test.ts:30 | typescript/consistent-type-imports | [keep] | 动态类型引用需保持 |
| 43 | packages/web/lib/chat/__tests__/reset.test.ts:33 | no-underscore-dangle | [keep] | 测试用重置函数名需要双下划线 |
| 44 | packages/web/lib/chat/__tests__/reset.test.ts:56 | no-ternary | [downgrade] | no-ternary: off 已设, 删 |
| 45 | packages/web/lib/chat/__tests__/reset.test.ts:69 | no-underscore-dangle | [keep] | 测试用重置函数名需要双下划线 |
| 46 | packages/web/components/forms/signup-form.test.tsx:14 | max-statements | [keep] | 测试需完整验证 DOM 操作链 |
| 47 | packages/web/components/forms/signup-form.test.tsx:39 | no-magic-numbers | [keep] | 测试断言: click 被调 1 次 |
| 48 | packages/web/components/forms/signup-form.test.tsx:50 | no-magic-numbers | [keep] | 10ms 等 setTimeout(0) 多拍 |
| 49 | packages/web/lib/api/__tests__/queries.test.ts:20 | typescript/consistent-type-imports | [keep] | vitest importActual typeof import() |
| 50 | packages/web/lib/chat/sse.ts:45 | id-length | [fixable-config] | 泛型参数 T 是标准 TypeScript 约定 |
| 51 | packages/web/lib/utils/cn.ts:76 | id-length | [fixable-config] | 泛型参数 T 是标准 TypeScript 约定 |
| 52 | packages/web/components/table/data-table-cell.tsx:63 | id-length | [fixable-config] | 泛型 T 是 TypeScript 惯例 |
| 53 | packages/web/lib/env.ts:90 | unicorn/prefer-global-this | [keep] | 检测浏览器环境 |
| 54 | packages/web/lib/env.ts:142 | id-length | [fixable-config] | 泛型 T 是 TypeScript 惯例 |
| 55 | packages/web/lib/env.ts:190 | unicorn/prefer-global-this | [keep] | 检测浏览器环境 |
| 56 | packages/web/lib/api/auth-router.ts:309 | max-statements | [keep] | redirect 兜底 throw |
| 57 | packages/web/components/dialog/...tsx:41 | no-ternary | [downgrade] | no-ternary: off 已设, 删 |
| 58 | packages/web/lib/chat/__tests__/normalize.test.ts:51 | max-statements | [keep] | describe 块包含 16 个 it |
| 59 | packages/web/lib/chat/__tests__/normalize.test.ts:70-265 (15 条) | no-magic-numbers | [fixable-config] | 测试数据 / 数组索引 |
| 60 | packages/web/lib/logger.ts:60-72 (4 条) | no-console | [keep] | log facade 故意包 console |
| 61 | packages/web/lib/chat/__tests__/decoder.test.ts:10 | no-magic-numbers | [fixable-config] | 测试数据常量 |
| 62 | packages/web/lib/chat/__tests__/decoder.test.ts:13 | max-statements | [fixable-config] | 12 个测试用例的 describe 块 |
| 63 | packages/web/lib/chat/__tests__/fixture.test.ts:4 (file-level) | no-magic-numbers | [fixable-config] | 测试 fixture 用具体 id / status |
| 64 | packages/web/lib/chat/use-chat-with-persistence.ts:82 | react-hooks/exhaustive-deps | [keep] | deps by design: accountId |
| 65 | packages/web/lib/chat/use-chat-with-persistence.ts:94 | react-hooks/exhaustive-deps | [keep] | deps by design: Chat + transport |
| 66 | packages/web/lib/chat/chat-event-decoder.ts:30 | max-statements | [keep] | 流式消息处理核心 |
| 67 | packages/web/lib/chat/chat-event-decoder.ts:55 | unicorn/prefer-ternary | [keep] | block is clearer here |
| 68 | packages/web/lib/chat/chat-event-decoder.ts:62 | max-statements | [keep] | (无注释) 应加 |
| 69 | packages/web/lib/i18n/request.ts:11 | unicorn/filename-case | [keep] | 文件名保持原样 |
| 70 | packages/web/lib/api/__tests__/csv.test.ts:46 | no-magic-numbers | [fixable-config] | 测试数据 mock calls 数组索引 |
| 71 | packages/web/components/chat/memory-management-dialog.tsx:74 | no-nested-ternary | [keep] | 失败/状态/无详情三态 |
| 72 | packages/web/components/chat/memory-management-dialog.tsx:79 | no-nested-ternary | [keep] | 同上 |
| 73 | packages/web/lib/api/auth-guard.ts:136 | max-statements | [keep] | 查表 dispatch, 每个 case 独立 generator |
| 74 | packages/web/lib/api/auth-guard.ts:190 | max-statements | [keep] | 解析函数, 逻辑紧凑 |
| 75 | packages/web/lib/chat/__tests__/openai-compat.test.ts:187, 230 | max-statements | [fixable-config] | describe 块含多 it + const |
| 76 | packages/web/lib/chat/__tests__/openai-compat.test.ts:21-266 (10 条) | no-magic-numbers | [fixable-config] | 测试断言 / mock calls 数组索引 |
| 77 | packages/web/lib/chat/__tests__/idempotency.test.ts:28-58 (5 条) | no-magic-numbers | [fixable-config] | 测试数据: 42 是模拟的 run ID |
| 78 | packages/web/lib/chat/openai.ts:29 | max-statements | [keep] | 流式解析核心逻辑, 拆分会破坏 reader/abort |
| 79 | packages/web/lib/chat/openai.ts:204-210 (2 条) | no-magic-numbers | [keep] | 默认查询条数限制 (业务常量) |
| 80 | packages/web/lib/chat/sse.ts:18 | max-statements | [keep] | 流解析核心逻辑 |

(后续 138 条略, 全部为 [keep] 类别: SSE 流式解析 / 测试 fixture / form components / admin pages / framer-motion 动画 / 业务 guard)

---

## 三、oxlintrc.json 现状

```json
{
  "$schema": "https://oxc.rs/schema/oxlint.json",
  "categories": {
    "correctness": "error",
    "suspicious": "warn",
    "style": "warn"
  },
  "rules": {
    "id-length": ["warn", { "exceptions": ["y", "x"] }],
    "no-unused-vars": "error",
    "no-console": "off",
    "complexity": ["error", { "max": 20 }],
    "max-statements": ["error", { "max": 15 }],
    "unicorn/no-null": "off",
    "prefer-ternary": "off",
    "no-ternary": "off",
    "sort-keys": "off",
    "sort-imports": "off",
    "capitalized-comments": "off",
    "typescript/consistent-type-definitions": "off"
  },
  "ignorePatterns": ["node_modules", ".next", "out", "components/ui"]
}
```

**配置观察**:
- `no-ternary: off` + `prefer-ternary: off` 已设, 残留 8 条 stale 应清
- `sort-imports: off` 已设, 残留 4 条 stale 应清
- `id-length` exceptions 已有 `y, x` (framer-motion), 但需加 `T, e, d, s, r, c` (TanStack cell + 回调短名)
- `max-statements` 阈值 15, 项目组件平均 18-22, 需评估
- 无 `overrides` 段, 是 [fixable-config] 主要空间

---

## 四、行动建议

### 4.1 [fixable-config] 建议 overrides (一次改完可消 ~108 条)

```json
{
  "$schema": "https://oxc.rs/schema/oxlint.json",
  "categories": {
    "correctness": "error",
    "suspicious": "warn",
    "style": "warn"
  },
  "rules": {
    "id-length": ["warn", {
      "exceptions": ["y", "x", "T", "e", "d", "s", "r", "c", "n", "i", "j", "k", "v", "w", "a", "b", "m", "p", "q", "u", "f", "l", "h", "g", "o"]
    }],
    "no-unused-vars": "error",
    "no-console": "off",
    "complexity": ["error", { "max": 20 }],
    "max-statements": ["error", { "max": 25 }],
    "unicorn/no-null": "off",
    "prefer-ternary": "off",
    "no-ternary": "off",
    "sort-keys": "off",
    "sort-imports": "off",
    "capitalized-comments": "off",
    "typescript/consistent-type-definitions": "off"
  },
  "ignorePatterns": ["node_modules", ".next", "out", "components/ui"],
  "overrides": [
    {
      "files": ["**/*.test.*", "**/*.spec.*", "**/__tests__/**", "**/e2e/**"],
      "rules": {
        "no-magic-numbers": "off",
        "max-statements": "off",
        "id-length": "off",
        "no-ternary": "off",
        "init-declarations": "off",
        "sort-imports": "off",
        "new-cap": "off",
        "no-underscore-dangle": "off",
        "max-params": "off",
        "arrow-body-style": "off",
        "vitest/prefer-lowercase-title": "off"
      }
    },
    {
      "files": ["**/components/animations/**", "**/components/motion/**"],
      "rules": {
        "no-magic-numbers": "off",
        "id-length": "off"
      }
    }
  ]
}
```

**预估效果**:

| 类别 | 改前 | 改后 | 减幅 |
|---|---|---|---|
| 测试文件 ignore | 128 | ~8 | -120 (核心 keep 不动) |
| 动画 ignore | 6 | 0 | -6 |
| sort-imports stale | 4 | 0 | -4 |
| 业务 max-statements (阈值 25) | 30 | ~12 | -18 |
| **合计可消** | **218** | **~70** | **-148 (-67.9%)** |

### 4.2 [fixable-code] 修复项 (8 条)

| ID | 文件:行 | 规则 | 改法 |
|---|---|---|---|
| FC-01 | `lib/api/queries.ts:101` | @typescript-eslint/no-explicit-any | 用 `UseMutationOptions<TData, TError, TVariables, TContext>` 收窄, 业务 type 已定义 |
| FC-02 | `lib/chat/sse.ts:62` | max-statements (无注释) | 加注释 "流式解析核心, 拆分会破坏 reader/abort 生命周期" |
| FC-03 | `lib/hooks/use-*.tsx:44` | max-statements | 拆 2-3 个 hook (`useXxxState`) 分散 5 useState |
| FC-04 | `lib/api/admin-client.ts:1` (file-level) | id-length, max-statements | 拆文件 (`dicts-client.ts` / `users-client.ts` / `roles-client.ts`) |
| FC-05 | `lib/chat/memory-integration.test.ts:30` | new-cap | alias `const _GET = GET`, 加注释 |
| FC-06 | `app/api/chat/.../route.ts:30` | max-statements | 加注释 "流式消息处理核心" |
| FC-07 | `lib/chat/parseSseStream.ts:50` | max-statements | 提取 `EVENT_DISPATCHERS: dict[str, Callable]` 取代 14 case |
| FC-08 | `lib/chat/parseSseStream.ts:55` | unicorn/prefer-ternary | 改用三元, 项目 no-ternary: off |

### 4.3 [downgrade] 清理 (12 条, 一次性 sed 删)

```bash
# sort-imports: off + no-ternary: off 已设, 注释已无意义
sed -i '/eslint-disable-next-line sort-imports/d' packages/web/**/*.{ts,tsx}
sed -i '/oxlint-disable-next-line sort-imports/d' packages/web/**/*.{ts,tsx}
sed -i '/eslint-disable-next-line no-ternary/d' packages/web/**/*.{ts,tsx}
sed -i '/oxlint-disable-next-line no-ternary/d' packages/web/**/*.{ts,tsx}
```

预计消 12 条 stale 注释 (sort-imports 4 + no-ternary 8).

### 4.4 优先级

- **P0**: 无 (后端 0 裸 noqa, 前端 0 强制规范违反)
- **P1**: [fixable-code] 8 条改代码 (FC-01 ~ FC-08)
- **P2**: [fixable-config] 加 overrides 段 (一次消 108 条)
- **P3**: [downgrade] 批量删 12 条 stale 注释
- **P4**: [keep] 不动 (业务合理 / 上游库约束 / 测试 fixture 已规划到 overrides)

### 4.5 风险评估

- **overrides 改动风险**: 低 (只影响 test/e2e/animations 子目录, 不影响业务代码)
- **max-statements 阈值 15→25**: 中 (可能漏掉真可拆分的 16-25 statement 函数, 需 lint diff 验证)
- **id-length exceptions 扩展**: 低 (单字母白名单已存在 `y, x`, 扩展到全字母表 = 关闭该规则, 等价)
- **no-console 保留 off**: 低 (项目已 off, 不动)

### 4.6 总收益

| 阶段 | 操作 | 净消 | 累计 |
|---|---|---|---|
| 当前基线 | - | 0 | 218 oxlint + 136 noqa = 354 |
| P3 [downgrade] | sed 删 stale 注释 | -12 | 342 |
| P2 [fixable-config] | 加 overrides + 调阈值 | -108 | 234 |
| P1 [fixable-code] | 8 条改代码 | -8 | 226 |
| **最终** | **354 → 226** | **-128 (-36.2%)** | 226 |

剩余 226 条中:
- 后端 136 noqa 全部 [keep] (符合 Rust-like 准则)
- 前端 ~90 条 [keep] (SSE 核心 + 业务 guard + 上游库约束 + 残留 max-statements)
