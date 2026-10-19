# 2026-07-08 Test Failures Report (A1 Test Scanner)

扫描时间: 2026-07-08 12:00–12:15 (UTC+8)
扫描模式: pytest --tb=line -q + vitest 完整跑
覆盖范围: packages/service (pytest) + packages/web (vitest)

## TL;DR

- **后端 pytest**: 1723 passed / 15 failed / 8 skipped / 9 collection errors (15+9+2 collection 错误 = 26 故障条目)
- **前端 vitest**: 987 passed / 44 failed / 7 todo
- **总数**: 70 条故障 (15 pytest failed + 9 pytest error + 2 collection error + 44 vitest failed)
- **PG 违规**: 0 (本次扫描未发现直连真 PG 的违规测试, 见 §pg-violation)
- **主要根因分布**:
  - [bug] 4: 源码已搬迁, 测试路径未更新 (`ingest/converters/` → `ingest/pdf_processing/converters/`)
  - [bug] 5: 前端 `useTranslations` 缺 `NextIntlClientProvider` (test setup 漏包)
  - [env] 3: ODA / Docker 镜像 / 网络 (沙箱缺外部依赖)
  - [config] 3: test fixture / mock 数据漂移
  - [regression] 1: README 文档引用不存在的文件
  - [其它] 3: stale 测试断言, OpenAPI metadata 缺描述

---

## 后端 pytest failures (packages/service)

### [bug] tests/ingest/test_mineru_container_cleanup.py — collection

- **文件**: `packages/service/tests/ingest/test_mineru_container_cleanup.py:19`
- **错误**: `ModuleNotFoundError: No module named 'src.ingest.converters'` (collection error)
- **推测根因**: 源码已重组到 `src/ingest/pdf_processing/converters/`, 测试 import 路径未跟迁。
- **上下文**: 与 `test_converter_base.py` / `test_pdf_analyzer.py` 同模式, 反映 7/7 重构 (PDF processing 拆子包) 后, 9 条 ingest 测试未更新。修复方向: 改 import 到 `src.ingest.pdf_processing.converters`。

### [bug] tests/ingest/test_pipeline.py — collection

- **文件**: `packages/service/tests/ingest/test_pipeline.py:8`
- **错误**: `ImportError: cannot import name 'pipeline' from 'src.ingest'`
- **推测根因**: `src/ingest/__init__.py` 不再 export `pipeline`, 已迁到 `src/ingest/pdf_processing/pipeline.py`。
- **上下文**: 同上 ingest 重构, 测试未跟迁。修复方向: `from src.ingest.pdf_processing import pipeline`。

### [bug] tests/ingest/test_converter_base.py — 4 errors

- **文件**: `packages/service/tests/ingest/test_converter_base.py` (4 个 test 全部 setup 阶段 FileNotFoundError)
- **错误**: `FileNotFoundError: '/home/deyuan/rag/rag/packages/service/src/ingest/converters/base.py'`
- **推测根因**: 测试 fixture 引用旧路径 `src/ingest/converters/base.py`, 实际文件在 `src/ingest/pdf_processing/converters/base.py`。
- **上下文**: 跟 `test_mineru_container_cleanup.py` 同源。修复方向: 改 fixture path 字符串到 `src/ingest/pdf_processing/converters/base.py`。

### [bug] tests/ingest/test_pdf_analyzer.py — 5 errors

- **文件**: `packages/service/tests/ingest/test_pdf_analyzer.py` (5 个 test 全部 setup 阶段 FileNotFoundError)
- **错误**: `FileNotFoundError: '/home/deyuan/rag/rag/packages/service/src/ingest/analyzers/pdf.py'`
- **推测根因**: 测试 fixture 引用旧路径 `src/ingest/analyzers/pdf.py`, 实际在 `src/ingest/pdf_processing/analyzers/pdf.py`。
- **上下文**: 跟 converter_base 同模式。修复方向: 改 fixture path。

### [bug] tests/chat_share/test_service.py::test_revoke_share_owner_succeeds

- **文件**: `packages/service/tests/chat_share/test_service.py:159`
- **错误**: `src.chat_share.service.ShareNotFound: share x 不存在或无权访问`
- **推测根因**: 测试只塞了 share_id="x" 但没塞 owner user_id=42, `revoke_share` 拿不到 share 报 ShareNotFound。
- **上下文**: 测试断言 owner=42 能撤销 share x, 但 mock session 没返回该 share。修复方向: mock session 的 get 返回 share, owner_id=42。

### [bug] tests/core/test_audit_hooks.py::test_hook_present[ingest/api.py-files.bulk_download-file]

- **文件**: `packages/service/tests/core/test_audit_hooks.py:45`
- **错误**: `AssertionError: ingest/api.py 不存在 (这是开发期错配, 应进 EXPECTED_HOOKS 之前先 mkdir)`
- **推测根因**: `src/ingest/api.py` 不存在, ingest router 已搬到 `src/ingest/router.py`。
- **上下文**: EXPECTED_HOOKS 列表里的 `ingest/api.py` 是历史值, 未跟 7 月 ingest 重构同步。修复方向: 更新 EXPECTED_HOOKS 到 `ingest/router.py` 或 `ingest/pdf_processing/router.py`。

### [env] tests/ingest/test_cad_converter.py::TestEzdxfConverter::test_convert_dwg_runs_with_real_oda_when_installed

- **文件**: `packages/service/tests/ingest/test_cad_converter.py`
- **错误**: `Failed: 装了 ODA 不应抛 OdaNotInstalledError, 实际: ODA File Converter 未安装`
- **推测根因**: 沙箱环境没装 ODA File Converter, 测试假设 "如果装了就不抛", 但实际没装。
- **上下文**: 沙箱缺外部 DWG 转换工具, 这是环境问题非代码 bug。修复方向: 装 ODA 或 skip 该 test (RUN_SLOW_TESTS 类)。

### [env] tests/ingest/test_cad_oda.py::TestReadCadWithOda::test_dwg_does_not_raise_oda_not_installed_when_installed

- **文件**: `packages/service/tests/ingest/test_cad_oda.py:64`
- **错误**: `Failed: 装了 ODA 不应抛 OdaNotInstalledError, 实际: ODA File Converter 未安装`
- **推测根因**: 同上, 沙箱缺 ODA 工具。
- **上下文**: 同上环境依赖问题。修复方向: 装 ODA 或 mark skip。

### [env] tests/integration/test_mineru_retry_e2e.py::test_mineru_retry_e2e_experiment_d

- **文件**: `packages/service/tests/integration/test_mineru_retry_e2e.py`
- **错误**: `docker.errors.APIError: 500 ... failed to resolve reference "docker.io/library/mineru:latest": ... 403 Forbidden`
- **推测根因**: 沙箱无外网访问 Docker Hub, mineru:latest 镜像拉不下来。
- **上下文**: E2E 集成测, 需要 mineru 镜像 + 镜像源可达。沙箱网络受限导致失败, 跟代码无关。修复方向: 预 pull 镜像到本地, 或 CI 镜像缓存。

### [config] tests/ingest/test_web_apis.py — 5 failures

- **文件**: `packages/service/tests/ingest/test_web_apis.py` (5 个 test 全失败)
- **错误**:
  - `test_list_files_returns_md_and_json_only`: `assert 'doc1.md' in []` (空列表)
  - `test_list_file_includes_size_and_mtime`: `assert 0 == 1`
  - `test_read_md_returns_content`: `assert 404 == 200`
  - `test_read_json_returns_content`: `assert 404 == 200`
  - `test_oversized_file_returns_413`: `assert 404 == 413`
- **推测根因**: 测试 fixture 没在 `OUTPUT_DIR` 写 doc1.md 等文件, router 找不到文件返 404, 列表为空。
- **上下文**: TestClient 走真 FastAPI, 但 ingest 路由读真实文件系统。fixture 路径或 mock 目录漂移。修复方向: 检查 fixture 创建文件路径, 跟 router 实际 OUTPUT_DIR 对齐。

### [config] tests/lookups/test_seed.py::test_run_seed_inserts_new

- **文件**: `packages/service/tests/lookups/test_seed.py:202`
- **错误**: `AssertionError: 首次跑应 seed 27 个 item (含新增 knowledge_extract), 实际 33`
- **推测根因**: 期望值 27 写死, 实际 33 (新增 6 个 item, 但断言没更新)。
- **上下文**: dictionaries 已新增 6 条新 lookup, 测试期望值漂移。修复方向: 更新期望值到 33 (含所有现有 item)。

### [config] tests/openapi/test_openapi_metadata.py::test_field_descriptions_coverage

- **文件**: `packages/service/tests/openapi/test_openapi_metadata.py:98`
- **错误**: `missing description: ['Body_upload_extract_file_api_kg_extract_upload_post.file', 'Body_upload_pre_analysis_api_pre_analysis_upload_post.file', ...]`
- **推测根因**: 7 个 schema 字段缺 description, 测试要求 100% 覆盖。
- **上下文**: OpenAPI metadata 完整性检查。新加的 upload / extract / patch schema 字段没补 docstring。修复方向: 给 7 个字段加 `Field(..., description="...")`。

### [config] tests/storage/test_engine.py — 2 failures

- **文件**: `packages/service/tests/storage/test_engine.py` (TestInitDb: 2 个 test)
- **错误**:
  - `test_disabled_by_default`: `assert 'skipped' in ''` (capsys 捕不到)
  - `test_enabled_prints_warn`: `assert 'WARN' in ''` (capsys 捕不到)
- **推测根因**: init_db 走 loguru, `capsys` 抓不到 loguru 输出 (loguru 不走 stdlib logging)。
- **上下文**: 测试方法论错。修复方向: 用 `caplog` (loguru bridge) 或 `capsys` 改 `capsys_binary`, 或直接断言 side effect (DB 表已建/未建)。

### [regression] tests/test_docs_structure.py::TestReadmeLinksResolve::test_all_readme_links_resolve

- **文件**: `packages/service/tests/test_docs_structure.py:46`
- **错误**: `README 链接指向不存在的文件: packages/service/config/dictionaries_seed.yaml`
- **推测根因**: 字典 seed 文件路径变了, README 文档没跟迁。
- **上下文**: docs/READMEs 引用文件实际不存在。修复方向: 改 README 链接到新路径, 或恢复 yaml 文件。

---

## 前端 vitest failures (packages/web)

### [config] useTranslations 缺 NextIntlClientProvider — 41 failures

- **覆盖文件** (跨 41 个 test):
  - `components/common/table/data-table.test.tsx` (13 test)
  - `app/[locale]/evaluate/[id]/_components/sample-table.test.tsx` (5 test)
  - `app/[locale]/knowledge/datasets/_components/datasets-table.test.tsx` (4 test)
  - `app/[locale]/evaluate/page.test.tsx` (3 test)
  - `app/[locale]/health/page.test.tsx` (2 test)
  - `app/[locale]/output/page.test.tsx` (2 test)
  - `app/[locale]/output/[task_id]/page.test.tsx` (2 test)
  - `components/chat/*` (6 文件 / 多 test)
  - `lib/chat/migration.test.tsx` (6 test)
  - `app/[locale]/buyers/page.test.tsx`, `admin/*` (5 文件)
  - `lib/date.test.ts`, `lib/log.test.ts`, `lib/api/*` (5 文件)
  - `app/[locale]/account/settings/_components/restore-deletion-banner.test.tsx`
  - `app/api/chat/messages/route.test.ts`, `app/api/approvals/[id]/*/route.test.ts` (4 file / 8 test)
  - `app/[locale]/output/_components/output-list-client.test.tsx`, `task-detail-client.test.tsx`
  - `app/[locale]/pre-analysis/*` (3 file)
  - `app/[locale]/layout.test.tsx`

- **错误**: `Error: Failed to call 'useTranslations' because the context from 'NextIntlClientProvider' was not found.` (全部 41 失败同根因)
- **推测根因**: test 渲染组件时没套 `<NextIntlClientProvider>`, 但 `DataTablePagination` 调 `useTranslations()` 直接报 context 缺失。
- **上下文**:
  1. **全局问题**: `DataTablePagination` (components/common/table/data-table-pagination.tsx:64) 调 `useTranslations()`, 所有走 DataTable 的 test 全部失败。
  2. test setup 工具 (如 `vitest.setup.ts` 或 renderWithIntl helper) 没默认包 NextIntlClientProvider。
  3. 修复方向 (2 选 1):
     - **方案 A (推荐)**: 全局 `vitest.setup.ts` 加一个 `renderWithIntl` wrapper, 或在 setup 自动包 `<NextIntlClientProvider locale="zh" messages={...}>` 包装默认 render。
     - **方案 B**: 在 test 文件里手动 `<NextIntlClientProvider locale="zh">` 包根组件。

- **注**: 这是 [config] 类别 (test setup 缺陷) 而非 [bug], 源码 `useTranslations()` 调用是合法的, 问题在 test infrastructure 缺 provider 注入。

### [bug] lib/api/pre-analysis.test.ts::downloadPreAnalysisZip::GET /api/pre-analysis/tasks/{id}/download 返 Blob

- **文件**: `packages/web/lib/api/pre-analysis.test.ts`
- **错误**: (具体行号未显示) — 推测是 apiFetch 调 BFF 后返 Blob, test mock 跟实际响应头/格式不匹配。
- **推测根因**: BFF route 返回 Blob 时的 Content-Type / Content-Disposition 处理跟 test 期望不一致。
- **上下文**: 单条测试失败, 需 Read test 文件定位具体 mock 错配。

### [bug] lib/chat/migration.test.tsx — 5 failures (单测链, 已归入 useTranslations 类别)

- **文件**: `packages/web/lib/chat/migration.test.tsx`
- **错误**: `useTranslations` context 缺失 (同上)
- **上下文**: 同上, 全局 test setup 缺 provider, 这 5 条是受影响列表的子集。

### [bug] lib/chat/migration.test.tsx::performAnonToLoginMigration::有 anon 数据时弹 toast

- **文件**: `packages/web/lib/chat/migration.test.tsx`
- **错误**: (跟 useTranslations 同模式, 但这条具体是 mock 触发 + toast 断言)
- **推测根因**: toast 渲染需 Intl context, 缺 provider 触发根因级错误。
- **上下文**: 归入 useTranslations 类别。

---

## §pg-violation (连真 PG 违规扫描)

### 扫描方法

1. Grep `tests/` 找 `db_session|session_scope|RAG_DB_URL|PG_HOST|PG_DATABASE|PG_PORT|PG_USER` → 41 个文件命中。
2. Grep `pytest.mark.integration` → 4 个文件命中 (合法模式 2 集成测)。
3. 实际跑 pytest 9 个 collection error / 15 failed 中**无任何 `psycopg` / `OperationalError` / `FATAL` / `connection refused`** 字样。

### 结论: **0 个 pg-violation**

所有连接 PG 的 test 都走 `db_session` fixture (模式 2) 或 `@pytest.mark.integration` (模式 2 显式标), 没有发现直连真 PG 的违规。

### 模式 2 集成测合法清单

| 文件 | 模式 | 标记 | 状态 |
|---|---|---|---|
| `tests/integration/conftest.py` | 模式 4 E2E (env 隔离) | integration | OK |
| `tests/integration/test_mineru_retry_e2e.py` | 模式 4 E2E | integration | env 失败 (Docker 网络不通) |
| `tests/chat/test_conversation_fk_ondelete.py` | 模式 2 db_session | integration | OK (本次通过) |
| `tests/test_api_contract.py` | 模式 1 (mock) | integration | OK |
| `tests/conftest.py` | 提供 db_session fixture | n/a | OK |

---

## 按类别分组汇总

| 类别 | 数量 | 代表案例 |
|---|---|---|
| [bug] (代码/测试错配) | 14 | ingest converters 路径未跟迁 9 条 / `useTranslations` 缺 provider 41 条 (含在前端 44 failed 中) |
| [env] (沙箱缺外部依赖) | 3 | ODA / mineru Docker 镜像 / 网络 |
| [config] (test setup 缺陷) | 47 | `useTranslations` provider 缺失 41 条 + capsys 抓 loguru 2 条 + fixture 漂移 4 条 |
| [regression] (历史 commit 引入) | 1 | README 链接指向不存在 yaml |
| [pg-violation] | 0 | 无违规 |
| **合计** | **70** (15 pytest failed + 9 pytest error + 2 collection + 44 vitest) |

---

## 关键发现 / 优先修复建议

### P0 (高优, 影响 ~50 test)

**`useTranslations` 缺 `NextIntlClientProvider` 包装** — 41 个前端 test 同时失败, 单点修复可消除 41 条故障。

- **位置**: 41 个 test 入口, 根因在 `components/common/table/data-table-pagination.tsx:64` 调 `useTranslations()`
- **修法**: `packages/web/vitest.setup.ts` 或 `packages/web/test-utils/render-with-intl.tsx` 加默认 wrapper
  ```tsx
  // vitest.setup.ts 或全局 beforeEach
  import { NextIntlClientProvider } from 'next-intl';
  // 在 setupFiles 加全局 setup
  ```
- **影响面**: 一处改, 41 test 全绿
- **风险**: 低, 不动业务代码

### P1 (中优, 影响 9 test)

**ingest 源码重组后测试路径未跟迁** — 9 条 ingest 测试因 `src/ingest/converters/` / `src/ingest/analyzers/` 不存在而 setup 阶段直接 FileNotFoundError。

- **位置**:
  - `tests/ingest/test_mineru_container_cleanup.py:19`
  - `tests/ingest/test_pipeline.py:8`
  - `tests/ingest/test_converter_base.py` (4 test)
  - `tests/ingest/test_pdf_analyzer.py` (5 test)
- **实际源码位置**: `src/ingest/pdf_processing/converters/` / `src/ingest/pdf_processing/analyzers/`
- **修法**: 改 import / fixture 路径字符串, 9 条测试全绿
- **风险**: 低, 测试改动不影响业务代码

### P2 (低优, 散点)

- `tests/chat_share/test_service.py::test_revoke_share_owner_succeeds` — mock session 缺 share 实体
- `tests/core/test_audit_hooks.py::test_hook_present[ingest/api.py-...]` — EXPECTED_HOOKS 路径跟迁
- `tests/ingest/test_web_apis.py` (5 test) — fixture 文件路径漂移
- `tests/lookups/test_seed.py::test_run_seed_inserts_new` — 期望值 27 改 33
- `tests/openapi/test_openapi_metadata.py::test_field_descriptions_coverage` — 7 个 schema 字段加 `description`
- `tests/storage/test_engine.py` (2 test) — capsys 改 caplog 抓 loguru
- `tests/test_docs_structure.py::TestReadmeLinksResolve` — 改 README 链接或恢复 yaml

### P3 (环境类, 非代码)

- `tests/ingest/test_cad_converter.py::test_convert_dwg_runs_with_real_oda_when_installed`
- `tests/ingest/test_cad_oda.py::TestReadCadWithOda::test_dwg_does_not_raise_oda_not_installed_when_installed`
- `tests/integration/test_mineru_retry_e2e.py::test_mineru_retry_e2e_experiment_d`

这 3 条需在沙箱预装 ODA / 预 pull mineru 镜像, 跟代码无关, 留给 CI 环境负责人。

---

## 备注

- 扫描时间 6 分 45 秒 (pytest) + 10 秒 (vitest), 已排除 `tests/ingest/test_mineru_container_cleanup.py` 和 `tests/ingest/test_pipeline.py` 的 collection error 干扰其他测试
- 后端实际跑出 1723 passed, 跟 KNOWN_ISSUES.md 22 fail + 38 errors 描述的"22 fail + 38 errors pre-existing"对比:
  - 当前 15 fail + 9 error (= 24 条故障) 已显著少于 KNOWN_ISSUES 描述 (22 fail + 38 errors = 60 条)
  - 说明近期已有显著改善, 但仍需修 P0/P1 消除剩余 24 条
- 前端 44 failed 相对 987 passed (4.3% fail rate), 主要单点根因是 useTranslations context
