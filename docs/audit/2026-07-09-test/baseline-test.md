# Oversize 文件基线报告 (2026-07-09)

> 来源: `c:/doc/Code/rag/docs/audit/2026-07-09-test/oversize-files-audit/.scan-cache.json` (42 文件 / 18669 行)
> 扫描阈值: >300 行的 `.py` / `.ts` / `.tsx`
> 目的: 给每个超大文件出"能否拆 / 怎么拆 / 预计减少多少"的重构建议

## TL;DR

| 维度 | 数字 |
| --- | --- |
| 文件总数 | 42 |
| 总行数 | 18,669 |
| 后端 Python | 24 (16,335 行 / 87.5%) |
| 前端 TS/TSX | 18 (2,334 行 / 12.5%) |
| ≥ 1000 行 | 1 (`kg/router.py`) |
| 800-999 行 | 1 (`camelot_extractor.py`) |
| 500-799 行 | 6 |
| 300-499 行 | 34 |

**最大杠杆点**: 拆 6 个 `router.py` (>3000 行总量) + 2 个 `lib/api/*.ts` (>1000 行) → 预计减少 **~40%** 行数, 拆完平均 200 行/文件。

---

## 拆解原则

1. **垂直拆 (按业务子域)**: `router.py` / `lib/api/*.ts` / Server Action 按 `prefix` (kg/chat/lookup/admin...) 切分到独立 module
2. **水平拆 (按层)**: `router.py` 内 Pydantic schema / 依赖 / handler / helper 拆 4 个文件
3. **提公共 (按 cross-cutting)**: 多处复用的 `validate_upload` / mime 白名单 / `_serialize_task` 提到 `_common/`
4. **不拆**: 已经拆好的 `pdf_processing/router.py` 不能再退; `camelot_extractor.py` 单文件职责清晰, 拆 `_ensure_ml_loaded` 即可

> **铁律 (CLAUDE.md / 根 .claude/)**: 函数 ≤ 100 行 / 单文件 ≤ 300 行 / 拆业务侧抽 AppXxx 复合组件 → 本报告按此目标倒推。

---

## 文件分桶

- **A. 必拆 (5)**: 单文件职责明显杂糅, 拆完价值高
- **B. 建议拆 (8)**: 行数大但有清晰拆点, 可分批进行
- **C. 可选拆 (12)**: 略超阈值, 仅抽 helper / 子模块
- **D. 不拆 (17)**: 已合理, 只做局部清理

---

# A. 必拆 (5 个)

## A1. `packages/service/src/kg/router.py` — **1040 行** (24 endpoint)

**问题**: 单文件塞了 Dify 代理 + Neo4j CRUD + Excel 模板 + KG 抽取 (upload/start/preview/patch/commit/export) + 任务管理。`require_page("kg")` / `require_page("knowledge")` 混用, 拆 4 个子 router 即可清晰分层。

**拆法 (3-2-2-1 = 8 文件, 减 70%)**:
- `router/__init__.py` (re-export `kg_router`): ~30 行
- `router/dify_proxy.py` — stats / health / datasets / segments (proxy Dify, 4 endpoint) ~180 行
- `router/neo4j_crud.py` — nodes / relationships / schemas / schema / products (5 endpoint, Neo4j 直查) ~250 行
- `router/triples.py` — triples / batch / tasks/{id} / kg_datasets / excel_template (5 endpoint) ~250 行
- `router/extract.py` — extract/datasets / extract/extractors / extract/splitters / extract/upload / extract/start / extract/tasks/{id} / extract/preview / extract/items / extract/commit / extract/export (10 endpoint) ~400 行
- `schemas.py` — TripleRowIn / TriplesRequest / TriplesResponse / BatchItem / BatchRequest / BatchResponse / StartExtractRequest / PatchItem / PatchItemsRequest (9 Pydantic model) ~120 行
- `_helpers.py` — `_serialize_task` / `_build_extractor` / `_build_splitter` / `_escape` (4 helper) ~80 行
- `_audit.py` — `_audit_store = _audit.AuditStore(...)` 1 行 + re-export

**预计减少**: 1040 → 平均 130 行/文件, 总行数 -10% (拆得必有 glue), **可维护性 ↑↑, 单文件 < 250 行**。

**注意**: 公开 API path 完全不变, 仅 import 路径在 `__init__.py` 聚合 `APIRouter` 即可。

---

## A2. `packages/service/src/ingest/pdf_processing/router.py` — **743 行** (7 endpoint + dataclass + runner)

**问题**: 文件同时含 `OutputFile/InputFile/IngestTask` 3 个 dataclass + ALLOWED_EXTS/SAFE_NAME 常量 + 7 个 endpoint + `_run_ingest` 后台 runner (43 行, 含 result dict 解析)。

**拆法 (减 50%)**:
- `router.py` — 仅 7 个 endpoint (presign/finalize/upload/list/get/read_file/download_zip) ~350 行
- `models.py` — `OutputFile` / `InputFile` / `IngestTask` dataclass + `_MIME_MAP` + `_mime_for[_name]` ~120 行
- `runner.py` — `_run_ingest` + `_collect_output_files[_legacy]` + `_find_output_file` ~120 行
- `_constants.py` — `ALLOWED_EXTS` / `MAX_UPLOAD_SIZE` / `MAX_FILE_SIZE` / `SAFE_NAME` 30 行
- `_workdir.py` — `_build_workdir_uri` / `_uri_for_backend` 包装 (后者已在 `common`, 这里只留 builder) 30 行

**预计减少**: 743 → 4 个文件, 最大 350 行。

---

## A3. `packages/service/src/storage/object_store.py` — **598 行** (ABC + LocalFS + MinIO + 单例工厂)

**问题**: 14 个抽象方法 + LocalFS impl 14 实现 + MinIO impl 14 实现 (含复杂 `_borrowed` 借用表) + `_is_not_found` 错误嗅探逻辑 4 处重复 + 工厂 + `_reset_object_store`. 1 个 impl 文件 200+ 行是合理的, 但 3 impl 杂糅超标。

**拆法 (减 40%, **不破坏 ABC 14 方法契约**) **:
- `abc.py` (或保持本文件前 160 行) — `ObjectStoreError` / `ObjectNotFound` / `ObjectMeta` / `parse_uri` / `build_uri` / `ObjectStore` ABC + `open_local_ctx` contextmanager ~165 行
- `local_fs.py` — `LocalFSObjectStore` ~95 行
- `minio.py` — `MinioObjectStore` (含 `_borrowed` 借用表 + `_is_not_found` 工具) ~240 行
- `_errors.py` — `_is_not_found(exc: Exception) -> bool` 抽公共 (4 处重复 6 行/处 → 1 处) ~30 行
- `factory.py` — `get_object_store` + `_object_store_singleton` + `_reset_object_store` ~50 行

**预计减少**: 598 → 5 个文件, 最大 240 行。**契约零变化**, 业务 import path 不变 (package `__init__.py` re-export)。

---

## A4. `packages/web/lib/api/pre-analysis.ts` — **585 行**

**问题**: 单文件混合 8 类 (元信息 / stage / 上传 / 列表 / 详情 / 重试 / 文件下载 / chapter+flagged viewer / 表格 viewer) + 14 type/interface. 文件头注释明确"pre-analysis 端点 API wrapper", 但里面还有独立的 `ChapterTreeNode` / `FlaggedParagraphRow` 等 viewer-only 类型。

**拆法 (减 50%)**:
- `pre-analysis/index.ts` (re-export 全部) 30 行
- `pre-analysis/types.ts` — 14 type/interface + 3 常量 (CHAPTER_JSON_FILENAME / FLAG_CSV_FILENAME / ZERO/EMPTY_STRING/ROW_INDEX_BASE / TABLE_FILENAME_PATTERN 等) ~200 行
- `pre-analysis/api.ts` — 8 fetch wrapper (upload/list/get/download/file/stages/retry/chapter/flagged/tables) ~250 行
- `pre-analysis/parse.ts` — `parseTableFilename` + `getPreAnalysisChapterStructure` (含 chapter JSON 解析) + `getPreAnalysisFlaggedParagraphs` (含 CSV papaparse) ~120 行
- `pre-analysis/_internal.ts` — `handleError` + `fetchPreAnalysisFile` 30 行

**预计减少**: 585 → 5 文件, 最大 250 行。**所有现有 import 改从 `@/lib/api/pre-analysis` (重导出) 即可**, 业务代码 0 改。

---

## A5. `packages/web/lib/api/knowledge.ts` — **502 行**

**问题**: 跟 A4 同病, 13 type + 10 kg wrapper + 9 extract wrapper + 4 行 `THREE` import (主搜命中). 注释明确写"knowledge 业务客户端".

**拆法 (减 45%)**:
- `knowledge/index.ts` (re-export 全部) 30 行
- `knowledge/types.ts` — 13 type/interface ~140 行
- `knowledge/kg.ts` — `createTriples` / `fetchBatchStatus` / `fetchDatasets` / `fetchHealth` / `fetchNodes` / `fetchRelations` / `fetchSchema` / `fetchSchemas` / `fetchSegments` / `fetchStats` 10 wrapper ~110 行
- `knowledge/bff.ts` — `retrieveQA` / `startBatch` / `uploadDocument` (走 /api/knowledge/* 专用 BFF) 30 行
- `knowledge/extract.ts` — 9 extract wrapper (datasets/extractors/splitters/upload/start/task/preview/items/commit/export) ~140 行

**预计减少**: 502 → 5 文件, 最大 140 行。

---

# B. 建议拆 (8 个)

## B1. `packages/service/src/ingest/pre_analysis/table_extractors/camelot_extractor.py` — **999 行**

**问题**: 类已 OK, 但 module-level 含 `_LATTICE_KWARGS` / `_STREAM_KWARGS` / `_ML_KWARGS` / `_COMMON_KWARGS` / `_FALLBACK_CHAIN` / `_FLAVOR_DEFAULTS` 6 个 frozenset/dict + `_FACTORY_PARAMS` + `_extract_single_page` / `_unmerge_combined_with_ml` / `_stack_contiguous_in_flavor` 3 个 free function + ml model 加载 + GPU semaphore + nvml 检测 (170 行)。

**拆法 (减 40%, 不破坏 extract 公开方法)**:
- `camelot_extractor.py` — 只剩 `CamelotTableExtractor` 类 (含 `_allowed_kwargs` + `extract` + `extract_with_fallback`) ~340 行
- `_camelot_kwarg_specs.py` — 4 frozenset (`_LATTICE_KWARGS` 等) + `_FLAVOR_DEFAULTS` + `_FACTORY_PARAMS` + `_FALLBACK_CHAIN` ~110 行
- `_camelot_single_page.py` — `_extract_single_page` + `_unmerge_combined_with_ml` + `_stack_contiguous_in_flavor` + `realign_columns` (已是 free func) ~250 行
- `_camelot_ml.py` — `_ML_MODEL` / `_ML_MODEL_LOCK` / `_ensure_ml_loaded` / `_ML_INFERENCE_SEM` / `_ML_SEM_LOCK` / 5 个 VRAM 常量 / `_detect_max_ml_workers` / nvml 调用 ~200 行

**预计减少**: 999 → 4 文件, 最大 340 行。

---

## B2. `packages/service/src/lookups/admin_router.py` — **562 行** (7 endpoint + 1 helper)

**问题**: 1 个文件塞字典/audit/confirm-token 3 类 admin 操作, 模式高度重复 (route → `_guard` → `LookupService` → `invalidate_page_keys_cache` + `rewarm_page_keys_cache` + `audit`). 重复模式是项目规范 ("前端 GET 返的字典级开关, items 仍能查").

**拆法 (减 50%)**:
- `router.py` — 仅 `APIRouter(prefix=...)` + re-export 子 router ~30 行
- `dict_router.py` — POST ``  / PATCH `/{dict_code}` 2 endpoint ~120 行
- `item_router.py` — POST / PATCH / DELETE `/{dict_code}/items[/{key}]` 3 endpoint ~150 行
- `audit_router.py` — POST `/confirm-token` + GET `/{dict_code}/audit` 2 endpoint ~140 行
- `_helpers.py` — `_actor_display` / `_client_ip` / `_guard` 3 helper ~50 行
- `schemas.py` (如未在 `lookups/schemas.py`) — 已存在可复用

**预计减少**: 562 → 6 文件, 最大 150 行。`revalidate_page_keys_cache` 重复调用可下沉到 `LookupService` 减少 3 处。

---

## B3. `packages/service/src/auth/auth_admin_router.py` — **464 行**

**问题**: 7 endpoint (list_users / create_invite / patch_user / reset_password / list_invites / ...) 全在 1 文件 + 多处 inline `from ..permissions.models import Role` (防循环). 模式跟 B2 一样重复 (super_admin 守卫 + 同套 audit_log).

**拆法 (减 35%)**:
- `router.py` — 仅 re-export
- `users_router.py` — GET /users / PATCH /users/{id} / POST /users/{id}/reset-password 3 endpoint ~160 行
- `invites_router.py` — POST /users (创 invite) + GET /invites + DELETE /invites/{token} (略) ~120 行
- `_guard.py` — 自禁 / 自降权 / anon 不接受 role 改 3 守卫 helper ~50 行

**预计减少**: 464 → 4 文件, 最大 160 行。

---

## B4. `packages/service/src/lookups/service.py` — **450 行**

**问题**: `LookupService` 全静态方法类, 6 公开方法 + `_load_all_from_db` + `_lock_for_update` + `audit.log_dict_change` 引用, 写后必 `lookup_cache.invalidate` + `permissions.invalidate_page_keys_cache`. 写方法 3 个结构高度相似 (try/except LookupNotFoundError + LookupSafetyError → HTTPException 翻译), 重复 5 次。

**拆法 (减 30%)**:
- `service.py` — 只保留 `list_all_dicts` + `get` + `get_one` (3 读) ~120 行
- `service_writes.py` — `create_item` / `patch_item` / `patch_dict` / `soft_delete_item` 4 写, 含公共 `_invalidate_caches()` helper ~200 行
- 异常翻译层已在 admin_router `_guard`, service 内不再 raise HTTPException (改 raise `LookupSafetyError`/`LookupNotFoundError`, 已在做)

**预计减少**: 450 → 2 文件, 最大 200 行。

---

## B5. `packages/web/app/[locale]/admin/pre-analysis/_components/pre-analysis-upload-dialog.tsx` — **479 行**

**问题**: 1 文件含 6 个常量数组 + `useUploadState` (5 state hook) + `useUploadHandlers` (4 handler) + `renderParamInput` (export, **当前 unused**) + `<PreAnalysisUploadDialog>` 组件. **`renderParamInput` (40 行) 注释明确"暂时 unused — export 保留"**, 直接删即可。

**拆法 (减 35%)**:
- `pre-analysis-upload-dialog.tsx` — 仅 `<PreAnalysisUploadDialog>` 组件 ~80 行
- `_use-upload-state.ts` — `useUploadState` hook + 6 常量数组 ~110 行
- `_use-upload-handlers.ts` — `useUploadHandlers` hook ~110 行
- 删 `renderParamInput` (40 行 unused dead code) + `BACKEND_PARAMS_KEYS` (5 行, 仅 renderParamInput 用)
- `_use-upload-state.test.ts` 等保留, hooks 测试就近放

**预计减少**: 479 → 3 文件, 最大 110 行, **净减 90 行 dead code**。

---

## B6. `packages/service/scripts/neo4j_import.py` — **499 行**

**问题**: 1 CLI script 混合 `load_yamls` / `yaml_to_graph_data` (135 行 yaml→graph 转换, 含 5 类节点/4 类关系内联) + `dedup_against_neo4j` + `Neo4jClient` class (~100 行 boto3/ssl_context) + `_normalize_uri_for_ssl_context` + `build_cypher` (待读后段). **scripts/ 是 utility, 不是 web router**, 拆脚本内子模块稍轻量, 但 yaml→graph 135 行属 1 个独立子任务。

**拆法 (减 25%, scripts/ 内 package 化)**:
- `neo4j_import.py` — 仅 `argparse` + `main()` CLI 入口 + 子命令路由 ~80 行
- `neo4j_import/yaml_to_graph.py` — `load_yamls` + `yaml_to_graph_data` + `dedup_against_neo4j` ~180 行
- `neo4j_import/client.py` — `Neo4jClient` class + `_normalize_uri_for_ssl_context` ~130 行
- `neo4j_import/cypher_build.py` — `build_cypher` + `_escape` 50 行 (待读后段)

**预计减少**: 499 → 4 文件, 最大 180 行。

---

## B7. `packages/service/src/ingest/pdf_processing/converters/cad.py` — **512 行**

**问题**: 1 文件含 `_read_oda_path_from_env_or_config` / `_apply_oda_path_from_config` / `_resolve_oda_exec_path` / `read_cad_with_oda` ODA 4 helper (110 行) + `OdaNotInstalledError` + `EzdxfConverter` 类 (含 `convert` / `_read` / `_render_svgs` / `_page_from_modelspace` / `_extract_text` / `_record_text` / `_record_mtext` / `_record_dimension` / `_record_leader` / `_record_tolerance` / `_record_insert_attribs` 11 个 method).

**拆法 (减 40%)**:
- `cad.py` — 仅 `EzdxfConverter` 类 (含 `convert` + `_read` + `_render_svgs` + `_page_from_modelspace`) ~190 行
- `cad_text_extractor.py` — `_extract_text` + 7 `_record_*` 方法 (实体→text dict 的纯函数链) ~200 行
- `oda.py` — `_read_oda_path_from_env_or_config` + `_apply_oda_path_from_config` + `_resolve_oda_exec_path` + `read_cad_with_oda` + `OdaNotInstalledError` ~120 行
- 注释 `_apply_oda_path_from_config()` 模块级一次性调用保留在 `oda.py` 末尾

**预计减少**: 512 → 3 文件, 最大 200 行。

---

## B8. `packages/service/src/ingest/pre_analysis/router.py` — **568 行**

**问题**: 1 文件 9 endpoint (upload/get/download/file/tables/pages/tables/page/stages/retry) + `_run_pre_analysis` 后台 runner + `_orphan_cleanup_pre_analysis_tasks`. 模块顶 "PDF 预分析路由".

**拆法 (减 40%)**:
- `router.py` — 仅 `pre_analysis_router` APIRouter + re-export ~30 行
- `upload.py` — POST `/upload` (含 multipart 校验 + chapter_config_json 解析) ~120 行
- `tasks.py` — GET `/tasks` / GET `/tasks/{id}` / POST `/tasks/{id}/retry` 3 endpoint ~130 行
- `download.py` — GET `/tasks/{id}/download` + GET `/tasks/{id}/files/{filename}` (2 个流式下载) ~100 行
- `tables.py` — GET `/tables/pages` + GET `/tables/page/{n}` (含 mime_map) ~110 行
- `stages.py` — GET `/tasks/{id}/stages` 1 endpoint ~30 行
- `_runner.py` — `_run_pre_analysis` + `_orphan_cleanup_pre_analysis_tasks` ~80 行

**预计减少**: 568 → 7 文件, 最大 130 行。

---

# C. 可选拆 (12 个, 简表)

| 文件 | 行数 | 建议 |
| --- | --- | --- |
| `packages/service/src/approvals/router.py` | 459 | 拆 `_db.py` (async session 工厂) + `_schemas.py` (RejectBody/SubmitBody) + `_guards.py` (require_login/require_admin) + router 本身 → 4 文件, 最大 ~150 行 |
| `packages/service/src/chat_share/router.py` | 413 | 拆 `_validators.py` (`_validate_upload` + `_validate_mime_and_size` + 3 mime 白名单常量) + `_files.py` (3 file upload endpoint) + `_shares.py` (4 share endpoint) → 3 文件, 最大 ~180 行 |
| `packages/service/src/auth/account_settings_router.py` | 424 | 拆 `_avatar.py` (POST/DELETE/GET avatar 3 endpoint) + `_email.py` (PATCH/POST email 2 endpoint) + `_password.py` (PATCH password) + `_deletion.py` (3 endpoint) → 5 文件, 最大 ~120 行 |
| `packages/service/src/auth/auth_account_router.py` | 402 | 拆 `_login.py` (login + rate_limit) + `_session.py` (logout + me) + `_seed.py` (seed_admin) + `_password_recovery.py` (forgot/reset) → 4 文件, 最大 ~120 行 |
| `packages/service/src/chat/service.py` | 398 | 仅抽 `_serialize_*` helper 即可, 业务主流程完整, 不强拆 |
| `packages/service/src/product_decoders/engine.py` | 390 | 拆 `_decoder.py` (`decode` 主循环) + `_router.py` (`_build_routing_table` + `route` + `_normalize`) → 2 文件, 最大 ~250 行 |
| `packages/service/src/config/settings.py` | 384 | 拆 `_ingest.py` (Paths/CadConfig/ArchiveConfig) + `_redis.py` + `_dify.py` + `_object_store.py` + `_kg.py` (新) → 5+ 文件 dataclass group |
| `packages/web/components/chat/memory-management-dialog.tsx` | 378 | 拆 `_use-memory-api.ts` + `_use-memory-filter.ts` + `_use-memory-edit.ts` + component → 4 文件, 最大 ~120 行 |
| `packages/service/src/memory/service.py` | 340 | 仅抽 `_repository.py` SQL 集中, 不强拆 |
| `packages/service/src/retrieval/vector_store.py` | 317 | 拆 `_embeddings.py` + `_search.py` + `_schema.py` → 3 文件 |
| `packages/service/src/health/checks.py` | 316 | 每个 check 1 个文件 (`_check_db.py` / `_check_redis.py` / `_check_neo4j.py` / `_check_object_store.py`) + `registry.py` → 5 文件 |
| `packages/service/src/chat/router.py` | 305 | 拆 `_messages.py` + `_conversations.py` + `_stream.py` (SSE) → 3 文件 |

---

# D. 不拆 (17 个, 仅局部清理)

| 文件 | 行数 | 处理 |
| --- | --- | --- |
| `packages/web/lib/date.ts` | 450 | OK, Temporal wrapper 公共 util 不拆 |
| `packages/service/src/ingest/pdf_processing/pipeline.py` | 448 | OK, 业务流水线 1 文件 1 主线; 仅可抽 `_archive_dispatch.py` 解压逻辑 |
| `packages/web/app/[locale]/admin/users/_components/admin-users-table.tsx` | 438 | 列定义 + 行操作, 现状合理; `_hooks/use-user-table.ts` 已抽 |
| `packages/web/app/[locale]/_actions/account.ts` | 435 | 8 server action 模式高度一致, 抽 `_shared.ts` (cookie/auth/error 处理) → 减 80 行 |
| `packages/web/app/[locale]/_actions/account-settings.ts` | 418 | 同上, 抽 `_shared.ts` |
| `packages/web/app/[locale]/admin/pre-analysis/[task_id]/_components/admin-pre-analysis-detail-client.tsx` | 400 | 详情页 (含 tabs), 略复杂但 1 页 1 组件 OK |
| `packages/service/src/auth/account_settings_service.py` | 307 | OK, 8 业务方法各自 < 30 行 |
| `packages/web/app/[locale]/admin/dicts/_components/admin-dicts-client.tsx` | 334 | OK, 页面级 client 整合多 dialog, 模块已拆 |
| `packages/web/lib/chat/use-chat-state.ts` | 331 | OK, 1 个 chat 状态机 hook |
| `packages/web/app/[locale]/knowledge/triples/_components/triples-form.tsx` | 331 | OK, 1 表单组件 |
| `packages/web/components/theme-provider.tsx` | 322 | OK, 自实现 1 provider |
| `packages/web/app/[locale]/decode/page.tsx` | 312 | OK, 1 页面 |
| `packages/web/app/[locale]/_actions/knowledge.ts` | 311 | OK, 1 server action 入口 |
| `packages/web/components/common/table/data-table.tsx` | 308 | OK, 公共 DataTable (近期已拆 PaginationBar) |
| `packages/web/app/[locale]/output/[task_id]/_components/task-detail-client.tsx` | 304 | OK, 1 详情页 |
| `packages/service/src/permissions/router.py` | 370 | 拆 `_pages.py` + `_roles.py` + `_cache.py` → 减 25% |
| `packages/service/src/eval/router.py` | 323 | OK, 6 endpoint + 1 helper |

---

# 落地优先级 (3 sprint)

## Sprint 1 (高杠杆, 立即做)

- **A1** `kg/router.py` 1040 → 8 文件 (~10 行时)
- **A4** `pre-analysis.ts` 585 → 5 文件
- **A5** `knowledge.ts` 502 → 5 文件
- **B5** 删 dead code `renderParamInput` (40 行) + 拆 dialog

预计总减 **~1300 行**, 单文件平均 250 → 130。

## Sprint 2 (业务 router 拆分)

- **A2** `pdf_processing/router.py` 743 → 4 文件
- **A3** `object_store.py` 598 → 5 文件
- **B1** `camelot_extractor.py` 999 → 4 文件
- **B2** `lookups/admin_router.py` 562 → 6 文件
- **B8** `pre_analysis/router.py` 568 → 7 文件

预计总减 **~1100 行**。

## Sprint 3 (脚本 + 业务 service)

- **B3** `auth_admin_router.py` 464 → 4 文件
- **B4** `lookups/service.py` 450 → 2 文件
- **B6** `scripts/neo4j_import.py` 499 → 4 文件
- **B7** `pdf_processing/converters/cad.py` 512 → 3 文件
- **C** 表 12 个简表项目按需取

预计总减 **~900 行**。

---

# 风险与禁忌

1. **公开 API path 不变** — A/B 拆 router 必须走 `router/__init__.py` re-export, 业务 import 0 改; 跑契约测试 `tests/test_api_contract.py` 必绿。
2. **CLAUDE.md 铁律**: 单次 `--fix` 改 > 500 行 → **停下来问用户 review** (本报告合计改 3000+ 行, 必须分 sprint, 每 sprint ≤ 500 行)。
3. **format / lint / pyright / 测试** 顺序不可颠倒 (CLAUDE.md L26-30), 每个 sprint 结束走完整链路。
4. **pre-existing test fail**: 业务测试 mocks 链可能依赖文件位置, 拆 import 后跑 `bun run test -- packages/web/lib/api/` 单文件验证, 不重跑全量 (跟 2026-07-08 pytest 沉淀一致)。
5. **shim 禁止** (用户 2026-06-08 反馈): 拆文件不引入 backward-compat re-export shim, 直接迁引用方 (零技术债)。
6. **删 BFF route 必跑契约测试**: A 类拆 router 不删 endpoint, 删的是 _helper / _schemas, 不涉及契约。

---

# 验证清单 (每个 sprint 结束)

```bash
cd packages/service && uv run ruff format && uv run ruff check && uv run pyright && uv run pytest tests/test_api_contract.py
cd packages/web && bun run format && bun run lint:fix && bun run typecheck && bun run test -- <改动的路径>
```

按 CLAUDE.md 铁律顺序跑, 全绿再开下一个 sprint。
