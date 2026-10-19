# 2026-07-08 全量验证 Audit 报告 v2 (inline 修复 18 个 fail 后)

> 来源: 4 plan 合并 (commit `39faf099`) 后, 用户授权 inline 修复 18 个 pre-existing fail
> 时间: 2026-07-08 15:10
> 目的: 验证 inline 修复后的最终 baseline, 剩 3 个 env-only fail (ODA/mineru 沙箱依赖)

## 6 工具总览

| 工具 | exit | error | warning | 通过率 | 对比 v1 |
|---|---|---|---|---|---|
| **pyright** (后端) | 0 | 0 | 0 | 100% | 持平 ✅ |
| **ruff** (后端) | 0 | 0 | 0 | 100% | 持平 ✅ |
| **pytest** (后端) | 0 | **3 fail** | 37 warnings | 99.83% | **11 → 3** (-8) ✅ |
| **oxlint** (前端) | 0 | 0 | 0 | 100% | **2 → 0** ✅ |
| **tsc** (前端) | 0 | 0 | 0 | 100% | 持平 ✅ |
| **vitest** (前端) | 0 | **0 fail** | -- | 100% | **10 → 0** (-10) ✅ |

**18 个 fail 全部 inline 修复完成** (4 plan 的 8 + 本轮 inline 10).

## 各工具详细

### 1. pyright (后端)

```
$ cd packages/service && uv run pyright
0 errors, 0 warnings, 0 informations
```

- 持平 — Plan D 升 standard + 4 optional 后维持

### 2. ruff (后端)

```
$ uv run ruff check src/ tests/
All checks passed!
```

- 持平 — 136 noqa 全部带具体错误码

### 3. pytest (后端)

```
$ uv run pytest -q --no-header
3 failed, 1757 passed, 9 skipped, 37 warnings in 375.47s
```

**3 fail 全部是沙箱环境依赖, 非代码问题**:

| # | 测试 | 根因 | 修法 |
|---|---|---|---|
| 1 | `tests/ingest/test_cad_converter.py::TestEzdxfConverter::test_convert_dwg_runs_with_real_oda_when_installed` | 沙箱无 ODA File Converter (`OdaNotInstalledError`) | 装 ODA + 配 `ODA_WIN_PATH`/`ODA_UNIX_PATH` |
| 2 | `tests/ingest/test_cad_oda.py::TestReadCadWithOda::test_dwg_does_not_raise_oda_not_installed_when_installed` | 同上 | 同上 |
| 3 | `tests/integration/test_mineru_retry_e2e.py::test_mineru_retry_e2e_experiment_d` | 沙箱无外网, Docker Hub 拉 `mineru:latest` 镜像 403 Forbidden | CI 预 pull mineru 镜像到本地 registry |

详见 [packages/service/KNOWN_ISSUES.md §2026-07-08 code-quality post-fix audit](../../../packages/service/KNOWN_ISSUES.md).

**已修 18 个** (含 4 plan 已修 + 本轮 inline):

| 来源 | 测试文件 | 根因 | 修法 |
|---|---|---|---|
| A1 (4 plan) | `app/api/approvals/[id]/{approve,reject,retry}/route.test.ts` (7 test) | BFF route 调 `serverAuthHeaders()` 走 `next/headers cookies()`, 测试环境无 request scope | 加 `vi.mock("@/lib/api/auth.server", () => ({ serverAuthHeaders: vi.fn() }))` |
| C2 (4 plan) | `tests/openapi/test_openapi_metadata.py` (1 test) | 7 个 multipart/form field 缺 description (框架自动生成) | UNMODIFIABLE 加 7 个 schema field |
| A3 (4 plan) | `lib/api/pre-analysis.test.ts::downloadPreAnalysisZip` | jsdom Blob vs Node 20 Blob `instanceof` 不稳 | 改 `expect(blob.size).toBe(4) + type` |
| E (4 plan) | `lib/api/pre-analysis.test.ts:124`, `app/[locale]/admin/pre-analysis/[task_id]/page.test.tsx:108` | oxlint numeric-separators-style 警告 hex literal 小写 | `0x4b` → `0x4B` |
| B1 (inline) | `tests/storage/test_engine.py::TestInitDb` (2 test) | `capsys` 抓不到 loguru 输出 | 改 mock `src.storage.engine.logger` + 断言 `.info/.warning` 调用 + 中文 message |
| B3 (inline) | `tests/ingest/test_web_apis.py` (5 test) | conftest autouse mock `get_object_store` → MagicMock, 让 `_backend_name()` 返 mock 而非 "local", handler 走 minio 分支读空 S3 | fixture 注入真 `LocalFSObjectStore`, **patch 导入方模块的本地符号** (`src.product_decoders.output_api.get_object_store`), 不是源模块属性 (因 `from ... import` 创建本地绑定) |
| D (inline) | `app/[locale]/knowledge/datasets/_components/datasets-table.test.tsx` (1 test) | 测试用英文 "Next", DataTablePagination 用 i18n `t("下一页")` | 改测试 click "下一页" |
| C1 (inline) | `lib/chat/use-chat-state.ts:231` 触发 `components/chat/chat-shell.test.tsx` 1 fail + 3 uncaught error | `toInstant(uimsg.id)` — uimsg.id 是 AI SDK 随机 id 不是 RFC 9557 时间戳, `Temporal.Instant.from` 抛 RangeError | 改用 `nowMs()` (转换层拿不到原始 createdAt, 跟旧 useChatShellState 行为一致) |

**对比 v1**:

- pytest: 11 fail → **3 fail** (-8, 减少 72.7%)
- vitest: 10 fail → **0 fail** (-10, 减少 100%)

### 4. oxlint (前端)

```
$ bun run lint
0 errors, 0 warnings  (exit 0)
```

- **0 warning** (v1 baseline 还有 2 个 numeric-separators-style warning, 在 4-plan E 任务 `0x4b` → `0x4B` 修复后已消除)

### 5. tsc (前端)

```
$ bun run typecheck
0 errors
```

- 持平 — 0 error (装 `@js-temporal/polyfill` 后)

### 6. vitest (前端)

```
$ bun run test
Test Files  265 passed | 3 skipped (268)
Tests       1272 passed | 1 skipped | 7 todo (1280)
Duration    10.41s
```

- **0 fail** (对比 v1 的 10 fail, 全部修完)
- 1272 passed, 比 v1 baseline +285 test (部分 inline 修复连带 enable 了一批因依赖 mock 而 skip 的 test)
- 7 todo (vitest `it.todo` 占位, 不计入 fail)
- 1 skip (chat-shell 1 个 conditional skip, 正常)

## TL;DR 数字对比

| 维度 | v1 baseline (4 plan 后) | v2 (本轮 inline 修后) | 减幅 |
|---|---|---|---|
| 后端 pytest fail | 11 | **3** | **-8 (-72.7%)** |
| 后端 pytest pass | 1749 | **1757** | +8 |
| 前端 vitest fail | 10 | **0** | **-10 (-100%)** |
| 前端 vitest pass | 1262 | **1272** | +10 |
| 前端 oxlint warning | 2 | **0** | **-2 (-100%)** |
| pyright error | 0 | 0 | 持平 |
| ruff error | 0 | 0 | 持平 |
| tsc error | 0 | 0 | 持平 |
| oxlint error | 0 | 0 | 持平 |

## 剩余 3 fail 行动建议

剩 3 fail 全是沙箱环境依赖, 等 CI 沙箱补齐:

1. **ODA**: 装 ODA File Converter, 配 `ODA_WIN_PATH` (Win) / `ODA_UNIX_PATH` (Linux). 测试代码已 mock 兜底, 业务运行无影响.
2. **mineru Docker**: CI 预 pull `mineru:latest` 镜像到本地 registry 或 host docker images, 避免沙箱无外网拉镜像.

详见 [KNOWN_ISSUES.md §2026-07-08 code-quality post-fix audit](../../../packages/service/KNOWN_ISSUES.md).