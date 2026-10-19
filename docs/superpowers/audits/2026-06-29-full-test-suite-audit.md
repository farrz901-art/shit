# Audit 2026-06-29: 前后端全量 Test 扫描

> 跑 `bunx vitest run` (web) + `uv run pytest tests/` (service), 收集所有 fail + error, 做根因聚类 + 修复建议.
>
> **范围**: 当前 working tree (branch: `feat/langchain-replace-llamaindex`, 含 2026-06-19~29 大改动: LlamaIndex 替换 LC / T1~T7 / code quality cleanup)
>
> **数据采集**:
> - 前端: 140.24s, `bunx vitest run --no-color` (直接绕过 bun runtime 异常)
> - 后端: 47.05s, `uv run pytest --tb=short --no-cov --no-header -rfE -q`

---

## 1. 总览

| 套件           | passed  | failed | error | total files | 时长    | 状态               |
| -------------- | ------- | ------ | ----- | ----------- | ------- | ------------------ |
| 前端 vitest    | 737     | **3**  | **86**| 157 (150 passed) | 140s | 3 真 fail + 86 Bun runtime panic |
| 后端 pytest    | 1498    | **54** | 0     | —           | 47s     | 54 fail            |
| **合计**       | 2235    | **57** | **86**| —           | —       | **143 红**         |

> 前端 86 "errors" = Bun v1.3.14 在 Windows 主线程 panic (`Illegal instruction at address 0x7FF6FBA5351B`) 引起 16 次 + 33 次 worker `Failed to terminate forks worker` + 33 次 `Timeout terminating forks worker`. 不是代码 bug, 是 Bun runtime 在 Windows 上的崩溃 (已知 bug). 报告前 vitest 自身也注明 "Resolve unhandled errors to make sure your tests are not affected" — 实际只有 3 fail, 其他 worker 是被 Bun 强杀的, 没法判断真伪, 应单独分类.

---

## 2. 前端 3 真 fail (按文件)

### FE-1. `app/[locale]/knowledge/layout.test.tsx:46` — DomainSwitcher testid 漂移

```
FAIL  app/[locale]/knowledge/layout.test.tsx > KnowledgeLayout
       > /knowledge/graph → 渲染 DomainSwitcher
TestingLibraryElementError: Unable to find an element by: [data-testid="domain-switcher"]

DOM dump 显示实际渲染:
  <button data-testid="dataset-switcher" role="combobox">选择数据集</button>
  <nav data-testid="knowledge-tabs">...tab-documents / tab-graph...</nav>
```

- **期望**: `data-testid="domain-switcher"`
- **实际**: `data-testid="dataset-switcher"` (dataset 才是当前业务术语)
- **根因**: 测试用了旧术语 `domain`, 组件已统一改名为 `dataset-switcher` ([project-代码质量铁律 § "禁止 emoji / 业务术语统一"]() 落地). 测试未跟随重命名.
- **修复方向**: `layout.test.tsx:46` 把 `getByTestId("domain-switcher")` 改 `getByTestId("dataset-switcher")`. 或者反向 — 在组件里加 `data-testid="domain-switcher"` 别名 (不推荐, 增加 shim).

### FE-2. `app/[locale]/knowledge/batch/page.test.tsx:35` — BackLink testid 漂移

```
FAIL  app/[locale]/knowledge/batch/page.test.tsx > BatchPage
       > hero 含 BackLink → /knowledge/graph
TestingLibraryElementError: Unable to find an element by: [data-testid="back-link"]

DOM dump 显示实际渲染:
  <a data-testid="page-hero-back-link" href="/zh/knowledge/graph">返回知识图谱</a>
```

- **期望**: `data-testid="back-link"`
- **实际**: `data-testid="page-hero-back-link"` (PageHero 子组件统一用 `page-hero-back-link`)
- **根因**: 测试用了旧简写 `back-link`, PageHero 组件已统一前缀 `page-hero-*`.
- **修复方向**: `page.test.tsx:35` 改 `getByTestId("page-hero-back-link")`. 也可以在 PageHero 导出 `back-link` 别名 testid (但违背 [[feedback-no-shim-no-minimal-changes]], 别加).

### FE-3. `app/[locale]/knowledge/graph/page.test.tsx:92` — RSC 预取 mock 数据不匹配

```
FAIL  app/[locale]/knowledge/graph/page.test.tsx > GraphPage (RSC)
       > 渲染 RSC 预取的 stats (neo4j.nodes/relations)
AssertionError: expected '...节点数0...关系数0...' to contain '100'
```

- **期望**: stats 数字包含 `100` (节点) + `250` (关系)
- **实际**: 渲染显示 `节点数 0` / `关系数 0`
- **根因**: GraphPage 是 RSC, 测试用 mock fetch 返回 `nodes=100, relations=250`, 但 mock 没生效 (或者 fetch 的不是测试期望的 URL), RSC 走真实 fetch, 真实 fetch 拿到的是空 stats (0 节点 0 关系). 共 2 个怀疑:
  1. 测试 mock 的 URL 跟 GraphPage 实际 fetch 的 URL 不一致 (前后端路径错位)
  2. 测试 mock 设置时机过晚, RSC 在 import 时已经 fetch 完
- **修复方向**: 读 `app/[locale]/knowledge/graph/page.tsx` 看实际 fetch URL, 对齐 mock; 或者把 mock 改成 `vi.mock("@/lib/api", ...)` 拦截模块级 fetch.

---

## 3. 前端 86 errors — Bun v1.3.14 Windows 主线程 panic (非代码 bug)

### 3.1 现象

```
============================================================
Bun v1.3.14 (0d9b296a) Windows x64
panic(main thread): Illegal instruction at address 0x7FF6FBA5351B
oh no: Bun has crashed. This indicates a bug in Bun, not your code.
============================================================
```

- 16 次 `panic(main thread)` 在 vitest run 期间触发
- 33 次 `Failed to terminate forks worker` + 33 次 `Timeout terminating forks worker` 是 panic 后续效应 (vitest 试图清理但 worker 已死)
- 受影响的 test files (33 个):
  - `components/common/confirm/app-confirm.test.tsx`
  - `app/[locale]/output/[task_id]/_components/task-detail-client.test.tsx`
  - `app/[locale]/admin/permissions/_components/create-role-dialog.test.tsx`
  - `app/[locale]/submissions/_components/reject-dialog.test.tsx`
  - `app/[locale]/buyers/page.test.tsx`
  - `app/[locale]/knowledge/documents/_components/documents-entry.test.tsx`
  - `app/[locale]/admin/dicts/_components/dict-list.test.tsx`
  - `app/[locale]/admin/invites/page.test.tsx`
  - `components/ui/sonner.test.tsx`
  - `components/common/feedback/app-error-banner-static.test.tsx`
  - `app/[locale]/account/settings/_components/avatar-uploader.test.tsx`
  - `app/[locale]/account/settings/_components/deletion-section.test.tsx`
  - `app/[locale]/account/settings/_components/restore-deletion-banner.test.tsx`
  - `components/chat/shared-chat-view.test.tsx`
  - `components/chat/citation-panel.test.tsx`
  - `components/common/feedback/app-error-boundary.test.tsx`
  - `app/[locale]/evaluate/[id]/_components/metric-bar.test.tsx`
  - `components/ui/toggle-group.test.tsx`
  - `app/[locale]/admin/users/page.test.tsx`
  - `app/[locale]/account/restore/page.test.tsx`
  - `app/[locale]/chat/page.test.tsx`
  - `components/common/display/app-breathing-dot.test.tsx`
  - `components/common/form/app-submit.test.tsx`
  - `components/ui/switch.test.tsx`
  - `components/ui/avatar.test.tsx`
  - `components/ui/button.test.tsx`
  - `components/ui/table.test.tsx`

### 3.2 根因(部分查证, 部分待查)

- **Panic 现象是真实的**: 16 次 `panic(main thread): Illegal instruction at address 0x7FF6FBA5351B`, 33 次 worker tear down
- **进程归属未明**: 项目跑测试走 `bun run test` → `vitest run` ( [package.json#L11](packages/web/package.json#L11) ), 主进程是 PowerShell 启动的 bun.exe, **不是 Git Bash (MINGW64)**
- **我之前归因到 [Bun issue #28451](https://github.com/oven-sh/bun/issues/28451) 是误套**: 那个 issue 是 "Git Bash 启动 standalone Bun binary" 场景, 跟当前 "PowerShell 启动 bun 跑 vitest" 不是同一路径
- **真正根因待查**: 可能性 3 个
  1. vitest forks worker 在 Windows 上启动器 (`.cmd` shim) 走了 Git Bash, 触发 Bun SIGILL
  2. vitest forks worker 本身在 Windows + Node 上的 fork 路径有 bug, 跟 Bun 无关
  3. Bun v1.3.14 在某些 argv 长度 / import 路径下稳定 panic, 跟 shell 无关
- **判断根因的方法**: 1) 看 vitest worker 启动堆栈; 2) 单跑 1 个测试文件 + `--pool=forks --poolOptions.forks.singleFork=true` 看是否仍 panic; 3) `bun --bun run vitest` vs `node node_modules/vitest/vitest.mjs` 二分

### 3.3 修复方向 (根因未明, 先 §7.3 诊断再选)

1. **`vitest.config.ts` 改 `pool: 'threads'` 替代 'forks'**: 走 Node worker_threads 不经 Git Bash 派生, 应可绕过 ([Bun issue #28451](https://github.com/oven-sh/bun/issues/28451) workaround 反向应用)
2. **`package.json` 改 `"test": "npx vitest run"`**: 完全跳过 bun runtime, 走 Node + vitest 二进制. 跟 [[feedback-no-shim-no-minimal-changes]] 一致, 不绕弯
3. **报告 Bun upstream bug**: 持续跟 [Bun issue #28451](https://github.com/oven-sh/bun/issues/28451) (Open since 2026-03-23, 无 PR)
4. **升级 Bun**: 当前 1.3.14 已是最新, **无 1.4.x 可升** — 此选项作废

---

## 4. 后端 54 fail 按根因分 11 类

| #  | 类别                          | 数量 | 严重度    | 根因                                                    |
| -- | ----------------------------- | ---- | --------- | ------------------------------------------------------- |
| BE-1 | monkeypatch env 没生效       | 6    | HIGH      | LLM/mem0 embedder 启动时直接读真 .env                    |
| BE-2 | fixture 串数据 / 事务未隔离   | 3    | HIGH      | chat public_token 跨 test 唯一冲突                       |
| BE-3 | 业务异常未归一化              | 5    | HIGH      | email/password reset/memory service 抛裸异常未吞       |
| BE-4 | CORS / cookie 配置错         | 5    | HIGH      | 生产 secure flag 缺失 + localhost 放行                   |
| BE-5 | logger 改造后 capfd 失效     | 4    | MEDIUM    | ingest pipeline 切 logging 后 stdout capture fixture 没跟 |
| BE-6 | Health check / settings 缺配置 | 3    | MEDIUM   | DIFY_DATASET_API_KEY 未注入 dev env                     |
| BE-7 | mock 不严 / state 转换错     | 2    | MEDIUM    | finalize 走 404 而非 409                                 |
| BE-8 | Schema 漂移                  | 7    | MEDIUM    | ORM vs migration / config 模块 API 不同步               |
| BE-9 | Audit row 没写                | 3    | MEDIUM    | KG audit 模块写入未生效                                  |
| BE-10 | API contract 漂移            | 1    | LOW       | buyer-profiles/my-profile 后端独有                       |
| BE-11 | 限流 / cache / TTL mock 错   | 14   | MEDIUM    | TTL 算负、cache 命中返 None, mock/redis fixture 未起     |

### BE-1. monkeypatch env 没生效 (6 项)

```
tests/generation/test_llm.py
  TestLLMEnvOverride::test_openai_llm_reads_settings
    assert 'deepseek-v4-flash' == 'gpt-4o'        # settings 注入错模型
  TestLLMEnvOverride::test_openai_llm_uses_api_key_from_settings
    assert 'sk-c993c75ae...e8baa1c3b623a' == 'sk-env'   # 真 .env 抢走
  TestLLMEnvOverride::test_local_llm_reads_settings
    assert 'deepseek-v4-flash' == 'qwen2.5:7b'
  TestOpenAILLMProperty::test_openai_llm_no_base_url
    assert 'https://api.deepseek.com/beta' == ''  # base_url 应当空却拿到 deepseek

tests/memory/test_mem0_client.py
  test_embedder_config_openai_provider_when_text_embedding
    assert 'sk-musixarqy...gbmwbnrlyexne' == 'sk-test'   # 期望 env 'sk-test' 拿到 SiliconFlow 真 key
    assert 'https://api.siliconflow.cn/v1' == 'https://proxy.example.com/v1'
  test_embedder_config_openai_provider_with_explicit_base_url
    # 同上, siliconflow key 漏 mock
```

- **根因**:
  - `ChatOpenAI` / mem0 embedder 在 **模块导入时** 就读了 `.env` 并缓存 `api_key` / `base_url`, 测试用 `monkeypatch.setenv` 在 import 后改环境变量已晚.
  - 进一步深挖: `langchain_openai.ChatOpenAI.__init__` 读 `OPENAI_API_KEY` 等 env vars; 项目 `src/generation/llm.py` 在 module 级做了 `ChatOpenAI(...)` 构造, 整个对象模块级 singleton, pytest 启动就 freeze.
- **修复方向**:
  1. `src/generation/llm.py` 改成 **lazy init**: `get_llm()` 函数按调用时刻读 env, 不在 module 顶层构造.
  2. 测试用 `pytest.MonkeyPatch.setenv` 在 **conftest fixture 入口** (autouse, `import src.generation.llm` 之前) 设 env, 或者直接 `monkeypatch.setattr(src.generation.llm, "_cached_client", None)`.
  3. mem0 embedder 同理: `src/memory/embedder.py` 改成 lazy `get_embedder()`.
  4. 或者: 测试用 `pytest.fixture(scope="module", autouse=True)` 在 `import src.generation.llm` 之前 patch `os.environ`.
- **关联**: 跟 [[feedback-test-real-code-path-not-just-mock-mock]] 同源 (mock 隐藏了 import 期副作用).

### BE-2. fixture 串数据 / 事务未隔离 (3 项)

```
tests/chat/test_models.py
  test_conversation_create
    psycopg.errors.UniqueViolation: Key (public_token)=(tok-conv) already exists
  test_message_create_and_cascade_delete
    Key (public_token)=(tok-msg) already exists
  test_message_role_required
    Key (public_token)=(tok-role) already exists
```

- **根因**: `users.public_token` 唯一约束跨 test 复用. `db_session` fixture 应该 rollback 但 chat model 测试可能没走标准 fixture, 或 fixture scope 错 (session-scoped 而非 function-scoped).
- **修复方向**:
  1. 查 `tests/chat/conftest.py` 是否用 `db_session` (标准 rollback fixture)
  2. `public_token` 测试值加 `uuid4()` 后缀, 防止硬编码冲突
  3. 或者 `db_session` 加 `autouse=True` 强制隔离

### BE-3. 业务异常未归一化 (5 项)

```
tests/account_settings/test_email.py
  test_verify_email_change_switches_email_and_marks_used
    ValueError: invalid or used token            # token 二次提交被拒
  test_verify_email_change_rejects_expired_token
    Regex pattern 'token expired' did not match  # 期望 'token expired', 实际 'invalid or used token'

tests/auth/test_password_reset.py
  test_reset_with_valid_token_changes_password
    ValueError: invalid or used token            # 同上

tests/memory/test_service.py
  test_search_returns_empty_on_exception
    MemoryServiceError: search failed: pgvector 不可达  # 期望 service 吞异常返 []
  test_list_memories_returns_empty_on_exception
    MemoryServiceError: list failed: pgvector 不可达
```

- **根因**:
  - email / password reset: verify 路径抛 `ValueError("invalid or used token")`, 业务层应区分 "used" / "expired" / "invalid", 测试期望过期有独立文案.
  - memory service: pgvector 不可达时应该 catch + 返空 (测试已 mock 抛异常), 实现却直接 raise `MemoryServiceError` 上抛.
- **修复方向**:
  1. `src/account_settings/email.py` `verify_email_change` 加 expired 分支: `EmailChange.verify` 检查 `expires_at < now` → 抛 `EmailTokenExpired("token expired")`.
  2. `src/auth/password_reset.py` 同理, `PasswordReset.verify` 区分 expired / used / invalid.
  3. `src/memory/service.py` `search` / `list_memories` 在 `except Exception` 路径返 `[]` 而非 raise.
- **关联**: [[feedback-rag-admin-token-bootstrap-only]] 同族 (业务异常归一化).

### BE-4. CORS / cookie 配置错 (5 项)

```
tests/core/test_cors.py
  TestCorsProduction::test_prod_rejects_localhost_by_default         # 200 应 403
  TestCorsProduction::test_prod_rejects_localhost_when_whitelist_set # 200 应 403
  TestCorsProduction::test_prod_allows_whitelisted_origin            # 400 应 200
  TestCorsProduction::test_prod_allows_multiple_whitelisted_origins  # 400 应 200

tests/auth/test_auth_cookie.py
  test_anon_secure_cookie_in_production
    assert 'secure' in 'rag_user_token=...; httponly; max-age=604800; path=/; samesite=lax'
```

- **根因**:
  - CORS: 生产配置 `allow_origins=["*"]` 或匹配逻辑反转 — 应当默认拒绝 localhost, 仅白名单放行; 实际全放.
  - cookie: 生产环境 `secure` flag 缺失, Set-Cookie 头缺 `Secure`.
- **修复方向**:
  1. `src/core/cors.py` (或类似) 修 `is_production` 分支: 严格匹配 `allow_origins` 白名单, localhost 不在白名单.
  2. `src/auth/cookie.py` `set_anon_cookie()` 生产环境加 `secure=True`.
- **关联**: 安全风险, HIGH 严重度.

### BE-5. logger 改造后 capfd 失效 (4 项)

```
tests/ingest/test_archive_integration.py
  TestProcessFilesArchiveIntegration::test_unsupported_archive_warns_and_continues
    AssertionError: assert '[WARN]' in ''  # capfd.stdout 为空

tests/ingest/test_pipeline_api_contract.py
  test_process_cad_files_no_longer_glob_str_dir  # 同根因, 紧邻 [WARN]

tests/ingest/test_pipeline_path.py
  TestProcessPathErrors::test_missing_path_prints_error_returns_none
    AssertionError: assert 'CAD 文件不存在' in ''
  TestProcessPathErrors::test_unknown_extension_prints_warning_returns_empty
    AssertionError: assert '不支持的文件格式' in ''

tests/ingest/test_process_files_routing.py
  TestProcessFilesRouting::test_warns_unknown_format
    AssertionError: assert '路径不存在' in ''
```

- **根因**: ingest pipeline 之前用 `print()` 输出, 测试用 `capfd` (capture file descriptor) 抓 stdout. 改造后用 `logger.warning(...)`, logger 默认走 stderr (或不输出到 captured fd), capfd 抓不到.
- **修复方向**:
  1. 测试改用 `caplog` (pytest 内置 capture logging handler) 替代 `capfd`.
  2. 或者在 conftest 加 `caplog.set_level("WARNING")` autouse fixture.
- **关联**: 跟 [[feedback-no-shim-no-minimal-changes]] 不冲突 — 这是测试 fixture 升级.

### BE-6. Health check / settings 缺配置 (3 项)

```
tests/health/test_checks.py
  test_check_dify_ok
    assert 'error' == 'ok'
  test_check_dify_connection_error
    # 期望 error message 含 'timeout', 实际 'DIFY_DATASET_API_KEY 未配置'
  test_check_dify_http_error
    # 同上
```

- **根因**: DIFY_DATASET_API_KEY 在 dev/test env 未注入, health check 调 Dify API 立即 401/未配置错, 测试期望 mock OK / mock timeout 场景.
- **修复方向**:
  1. `tests/health/conftest.py` 加 `monkeypatch.setenv("DIFY_DATASET_API_KEY", "test-key")` autouse.
  2. health check mock Dify response 而不是真调 API.
  3. 或者 fixture 提供 `_mock_dify_ok` / `_mock_dify_timeout` 工厂.
- **关联**: [[feedback-audit-env-changes-introduce]] — 新增 env 必须主动列影响面.

### BE-7. mock 不严 / state 转换错 (2 项)

```
tests/ingest/test_api_presign.py
  test_finalize_upload_rejects_wrong_state
    AssertionError: assert 404 == 409
    HTTPException(status_code=404, detail='任务不存在或已过期').status_code
  test_finalize_upload_starts_background_task
    HTTPException: 404: 任务不存在或已过期  # finalize 后查 task 应存在
```

- **根因**: finalize upload 业务逻辑:
  - 期望: task 存在但 state 错 → 409 Conflict
  - 实际: task 不存在 / 已过期 → 404 Not Found
  - 测试 fixture 准备 task 时设置错了状态, 或者 finalize 实现把 "wrong state" 和 "task not found" 混为 404.
- **修复方向**:
  1. `src/ingest/api.py` `finalize_upload` 拆 2 个分支: `task is None` → 404; `task.state != expected` → 409.
  2. 测试 fixture 创建 task 时确保 `state` 字段正确.

### BE-8. Schema 漂移 (7 项)

```
tests/auth/test_account_model_constraints.py
  test_account_orm_constraints_match_migration
    AssertionError: Account CheckConstraint name 不一致:
      ORM=['ck_accounts_role', 'ck_accounts_email_format']
      migration=['ck_accounts_email_format']

tests/test_config.py (6 项)
  TestGetPaths::test_returns_paths_dataclass
    AttributeError: module 'src.config' has no attribute 'CONFIG_FILE'
  TestGetCadConfig::test_returns_cad_config        # 同上
  TestGetCadConfig::test_missing_segment_returns_empty  # 同上
  TestGetArchiveConfig::test_returns_archive_config     # 同上
  TestGetArchiveConfig::test_missing_config_file_raises # 同上
  TestGetCadConfig::test_missing_config_file_raises     # 同上 (推断)
```

- **根因**:
  1. ORM 多声明了 `ck_accounts_role` check constraint, 但 migration 没生成对应 DDL. SA 2.0 `__table_args__` 改了.
  2. `src/config.py` 之前暴露 `CONFIG_FILE` 常量, 现在已删/改名 (大概率 refactor 成 `get_paths()` factory 函数), 测试还引用旧名.
- **修复方向**:
  1. `src/auth/models.py` 检查 `Account.__table_args__`, 把 `ck_accounts_role` 加上 (业务上是否要 role 校验?), 或删掉 ORM 声明 (跟 migration 对齐).
  2. `tests/test_config.py` 改成 `from src.config import get_paths` / `get_paths().config_file`, 而不是 `from src.config import CONFIG_FILE`.
  3. 或者 `src/config.py` 重新导出 `CONFIG_FILE = get_paths().config_file` 兼容别名 (但 [[feedback-no-shim-no-minimal-changes]] 反对).

### BE-9. Audit row 没写 (3 项)

```
tests/kg/test_kg_audit.py
  test_record_inserts_row            # assert 0 == 1
  test_list_recent_ordered_desc      # assert 0 == 3
  test_list_recent_limit             # assert 0 == 2
```

- **根因**: KG audit 模块写入未生效. 可能:
  1. `db_session` 事务 rollback 了 audit insert (fixture 顺序错)
  2. 测试 fixture 没建 `kg_audit` 表 (schema 漏迁移)
  3. `record()` 函数被 mock 了但 mock 没生效
- **修复方向**:
  1. 跑 `uv run alembic upgrade head` 确认 schema 完整.
  2. 加 `Base.metadata.create_all` 在 kg audit 测试 conftest 起表.
  3. 检查 `src/kg/audit.py` `record()` 是不是 lazy connection, 而不是 with-context.

### BE-10. API contract 漂移 (1 项)

```
tests/test_api_contract.py
  test_no_dead_routes_in_backend
    AssertionError: 后端有 1 个 /api/* 路由但前端未使用:
      /api/buyer-profiles/my-profile
```

- **根因**: 后端挂了 `/api/buyer-profiles/my-profile` 但前端 BFF / lib/api 未声明. 要么删后端 (没人用), 要么加前端.
- **修复方向**:
  1. 短期: 加 `KNOWN_DEAD` 例外 (跟 2026-06-14 audit 同模式).
  2. 长期: 决策这条路由做什么 — buyer profile 是 B2B 邀请制的产物, 应当有前端页面; 加 BFF + 前端 client.

### BE-11. 限流 / cache / TTL mock 错 (14 项)

```
tests/core/test_rate_limiter.py (6)
  test_first_request_allowed        # assert 0 == 1 (首次应允许)
  test_under_threshold_allowed      # assert 0 == 1
  test_over_threshold_rejected      # assert True is False
  test_different_ips_isolated       # assert True is False
  test_reset_uses_1h_window         # assert True is False
  test_key_format

tests/core/test_embed_cache.py (3)
  test_get_cached_vector_hit        # assert None == [1.0]
  test_cache_vector_7d_ttl          # assert 0 < -2  (TTL 算负)
  test_long_text_hash_uses_first_512_chars

tests/core/test_mem0_ready.py (2)
  test_mark_and_check_ready         # assert False is True
  test_mark_sets_1h_ttl             # assert 0 < -2

tests/core/test_dify_query_cache.py (1)
  test_cache_and_get_chat           # assert None == {'answer': 'hello', ...}

tests/core/test_permission_cache_redis.py (2)
  test_first_get_reads_pg_and_writes_redis  # assert None == '1'
  test_subsequent_get_reads_redis_not_pg    # assert None is True
```

- **根因**:
  - rate_limiter: 测试用 in-memory mock, mock 实现跟业务实现逻辑不匹配 (mock 是真 limiter 还是 stub?). 共 6 项全是 "mock 不工作".
  - cache / TTL: `cache_*_7d_ttl` 计算返负值 — unit 错配 (秒 vs 毫秒), 或 fixture 没注入.
  - permission_cache_redis: 测试期望 redis 命中返 `'1'`, 实际返 None — redis fixture 没起 / mock 错.
- **修复方向**:
  1. rate_limiter: 用 `fakeredis` 或 in-memory dict 真模拟 Redis, 不要 mock 业务函数.
  2. cache TTL: 检查 `seconds=86400*7` 计算, 别用 `timedelta` 跟 `int` 混.
  3. permission_cache_redis: 加 `fakeredis` fixture 或真 redis (testcontainers).
- **关联**: [[feedback-asyncio-sem-needs-peak-test]] 提到 mock 漏测并发 — 本类同根.

---

## 5. 修复优先级

### P0 (HIGH 安全 / 鉴权 / 数据)

- **BE-4** CORS / cookie (5 项): 生产配置错配, 真部署会被 SSRF / cookie 偷
- **BE-1** LLM env 注入 (6 项): 测试 mock 失效, 真部署可能拿错 API key

### P1 (HIGH 业务)

- **BE-3** 异常归一化 (5 项): 业务异常冒到 API 层, 用户体验差
- **BE-2** fixture 隔离 (3 项): 数据污染, 后续测试不稳定
- **FE-1 / FE-2 / FE-3** 前端 testid / RSC mock (3 项): 阻塞后续知识图谱页开发
- **BE-10** API contract drift (1 项): 持续腐烂, 现在不修 contract gate 永远失效

### P2 (MEDIUM 工具链 / 配置)

- **BE-5** capfd → caplog (4 项): 测试 fixture 升级, 不改业务
- **BE-6** DIFY env 注入 (3 项): conftest 加 fixture
- **BE-7** finalize state 分支 (2 项): API 设计修正
- **BE-8** Schema 漂移 (7 项): ORM/migration 同步
- **BE-9** Audit row (3 项): transaction 排查
- **BE-11** cache / rate limit mock (14 项): 真 fakeredis fixture

### P3 (LOW / 基础设施)

- 前端 Bun runtime panic (86 项): 工具链问题, **不在 PR 范围, 需要用户决策 (升级 Bun / 换 npx / 改 pool config)** — 报 BLOCKED

---

## 6. 推荐修复顺序 (单 PR 不超过 500 行)

1. **PR-1 (P0 安全)**: BE-4 CORS/cookie — 单文件, ~50 行
2. **PR-2 (P1 业务异常)**: BE-3 + BE-1 — 改 `src/memory/service.py` + `src/generation/llm.py` lazy init
3. **PR-3 (P1 测试)**: BE-2 + BE-5 + BE-6 + BE-9 fixture 升级 — conftest + 14 个测试 fixture
4. **PR-4 (P1 前端 + contract)**: FE-1 / FE-2 / FE-3 (前端 testid 漂移 + RSC mock) + BE-10 (contract 加 KNOWN_DEAD) — 4 文件, ~30 行
5. **PR-5 (P2 schema)**: BE-8 + BE-7 — ORM 修正 + finalize API 分支
6. **PR-6 (P2 mock)**: BE-11 — fakeredis fixture, 14 测试

---

## 7. 阻塞项 (根因未明, 需先诊断再决策修法)

**前端 Bun v1.3.14 Windows 主线程 panic (86 项 worker tear down)**:

### 7.1 现象(已确认)

- 16 次 `panic(main thread): Illegal instruction at address 0x7FF6FBA5351B`
- 33 次 worker tear down (`Failed to terminate forks worker` + `Timeout terminating forks worker`)
- 33 个 test files 受影响, 无法验证真伪

### 7.2 根因(我之前误判, 已撤回)

- 我先归因到 [Bun issue #28451](https://github.com/oven-sh/bun/issues/28451) "Git Bash 派生" — **错误归因, 已撤回**
- 真实情况: 项目 [package.json#L11](packages/web/package.json#L11) 是 `"test": "vitest run"`, 主进程是 PowerShell 启动的 bun.exe, **不是 Git Bash (MINGW64)**
- issue #28451 是 "Git Bash 启动 standalone Bun binary" 场景, 跟当前 "PowerShell 启动 bun 跑 vitest" 不是同一路径
- 真正根因**待诊断**, 3 个可能性:
  1. vitest forks worker 启动器 (`.cmd` shim) 走了 Git Bash
  2. vitest forks worker 自身在 Windows + Bun runtime 上 fork 路径有 bug
  3. Bun v1.3.14 在某些 argv / import 路径下稳定 panic (跟 shell 无关)

### 7.3 先诊断再修 (3 步)

1. 看 panic 完整堆栈, 提取 `bun.report/...` URL (log 里有), 上 GitHub 搜同 stack trace
2. 二分: `bun --bun run test` vs `node node_modules/vitest/vitest.mjs run` 看是否都 panic
3. 单跑 1 个测试 + `vitest run --pool=threads` 看是否还 panic

### 7.4 诊断后, 修法 3 选 1

1. **`vitest.config.ts` 改 `pool: 'threads'` 替代 'forks'`**: 走 Node worker_threads, 不走 fork 派生
2. **`package.json` 改 `"test": "node node_modules/vitest/vitest.mjs run"`**: 彻底绕开 bun runtime
3. **持续跟踪 Bun upstream**: 报告 issue 上传 panic URL 等修复

### 7.5 推荐

**先做 §7.3 诊断 (30 分钟)**, 不要直接猜修法. 根因不同修法可能完全相反.

⚠️ **本节根因描述之前归因到 #28451 是错的**, 已撤回, 不要据此行动.

## 8. 已知未列入 (pre-existing KNOWN_ISSUES)

参考 `packages/service/KNOWN_ISSUES.md` 中已登记的 22 fail + 38 errors. 本次新增的 54 fail + 3 frontend fail 应追加到 KNOWN_ISSUES 或本审计报告, 用户决策.

---

## 9. 跟项目已有规约的关联

- [[feedback-no-shim-no-minimal-changes]]: BE-8 schema 漂移 / BE-1 env 注入 / FE-1/2 testid 漂移 都不能用 "兼容别名" 兜底, 必须改测试或改代码对齐.
- [[feedback-test-real-code-path-not-just-mock-mock]]: BE-11 cache/rate_limit 全是 mock 错配, 应写真 fakeredis.
- [[feedback-debug-distinguish-root-causes]]: 86 frontend errors ≠ 86 真 bug, 必须区分 Bun runtime 引起 vs 代码.
- [[feedback-audit-env-changes-introduce]]: BE-1 / BE-6 都是 env 改动没同步, 跟 mem0 HF 教训同源.
- [[feedback-stop-and-ask-dont-loop-on-infra]]: 前端 Bun runtime panic 不要每 blocker 都自己 debug, 应报告 BLOCKED 让用户决策.

---

**报告完成时间**: 2026-06-29
**工具版本**: pytest 8.x / vitest 4.1.9 / Bun v1.3.14
**下次 audit 触发**: 任意 P0/P1 修复完成时, 重跑同命令验证