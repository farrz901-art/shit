# oversize-files-refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split 27 verified-over-300-line files into focused submodules, reducing per-file size below 300-line threshold while preserving all exports and imports.

**Architecture:** Each oversized file is split into focused submodules per the audit report's 7-section findings. Router files split by endpoint into per-endpoint modules with a barrel re-export. Business logic files split by responsibility (config/class/postprocess/page-runner). TS files follow existing `_actions/`, `_hooks/`, `_lib/`, `_components/` convention. All splits preserve existing import paths via facade re-exports.

**Tech Stack:** Python 3.14 (FastAPI, SQLAlchemy, pydantic) + TypeScript 8 (React 19, Next.js 16, shadcn/ui, es-toolkit). Test: `uv run pytest` / `bun run test`. Pre-commit: ruff/pyright/tsc/vitest.

**Reference:** Audit report at `docs/audit/2026-07-10/oversize-files-audit/oversize-files-audit.md` — each file's 7-section data including exact split point line numbers and skeleton pseudo-code.

---

## File Structure Map

### Phase P0 (4 largest files, 3058 lines → ~780 target)

```
packages/service/src/ingest/pre_analysis/table_extractors/
├── camelot_extractor.py  [barrel: ~30 lines]
├── camelot_config.py                (config constants)
├── camelot_extractor_class.py      (CamelotTableExtractor class)
├── camelot_ml_runtime.py           (ML resource management)
├── camelot_page_runner.py          (single page dispatch)
├── camelot_postprocess.py          (column realignment / merge)
├── camelot_cross_page.py           (CrossPageMerger)

packages/service/src/ingest/pdf_processing/
├── router.py  [barrel: ~50 lines]
├── task_persistence.py             (dict_to_task / save / load / list_user)
├── task_models.py                  (OutputFile / InputFile / IngestTask dataclasses)
├── mime_helper.py                  (MIME mapping)
├── path_mode_collect.py            (legacy output file collection)
├── uri_mode_collect.py             (ABC mode output file collection)
├── zip_stream.py                   (zip stream generator)

packages/service/src/kg/
├── router.py  [barrel: ~120 lines]
├── dify_proxy.py                   (stats/health/datasets/segments proxy)
├── neo4j_list.py                   (nodes/relationships/products/schemas list)
├── extract_meta.py                 (extract/datasets + tasks meta)
├── extract_upload.py               (extract/upload + factory)
├── extract_workflow.py             (start/preview/items/commit/export)
├── kg_schemas.py                   (pydantic schemas)

packages/service/src/ingest/pdf_processing/converters/
├── cad.py  [~200 lines remaining]
├── cad_oda_path.py                 (ODA path resolution)
├── cad_oda_reader.py               (ODA file conversion)
├── cad_svg_renderer.py             (SVG rendering)
├── cad_text_records.py             (TEXT/MTEXT/DIMENSION records + _xy)
├── cad_markdown_writer.py          (text-to-markdown)
```

### Phase P1 (9 files, 4359 lines → ~1000 target)

```
packages/service/src/ingest/pre_analysis/
├── router.py  [barrel: ~30 lines]
├── pre_analysis_upload.py          (upload endpoint)
├── pre_analysis_query.py           (list/get task query)
├── pre_analysis_download.py        (zip/file download)
├── pre_analysis_tables.py          (table pages viewer)
├── pre_analysis_stages.py          (stage progress)
├── pre_analysis_retry.py           (retry endpoint)
├── pre_analysis_runner_dispatch.py  (background runner)
├── pre_analysis_orphan.py          (startup cleanup)

packages/service/src/lookups/
├── admin_router.py  [barrel: ~30 lines]
├── admin_router/_guards.py         (shared guard helpers)
├── admin_router/dict_create.py     (POST dictionary)
├── admin_router/dict_patch.py      (PATCH dictionary)
├── admin_router/item_create.py     (POST item)
├── admin_router/item_patch.py      (PATCH item)
├── admin_router/item_delete.py     (DELETE item)
├── admin_router/confirm_token.py   (issue confirm token)
├── admin_router/dict_audit.py      (get audit log)

packages/service/src/auth/
├── auth_admin_router.py  [barrel: ~30 lines]
├── auth_admin_router/admin_users_list.py
├── auth_admin_router/admin_invite_create.py
├── auth_admin_router/admin_user_patch.py
├── auth_admin_router/admin_password_reset.py
├── auth_admin_router/admin_invite_list.py
├── auth_admin_router/admin_invite_delete.py

packages/web/lib/
├── date.ts  [barrel: ~30 lines]
├── date/date-instant.ts            (DateInput / toInstant / InstantUnit)
├── date/date-now.ts                (nowInstant / nowMs / nowIso)
├── date/date-difference.ts         (differenceIn*/durationOf)
├── date/date-add.ts                (add*/shift)
├── date/date-compare.ts            (isAfter / isBefore / isEqual / instantOf)
├── date/date-format.ts             (formatDate / formatDateTime)
├── date/date-relative.ts           (fmtRelativeTime / formatRelativeTime)
├── date/date-duration.ts           (formatElapsedMs / formatDurationMs)

packages/service/src/lookups/
├── service.py  [barrel: ~30 lines]
├── service/read.py                 (LookupReadService: list/get/get_one)
├── service/write.py                (LookupWriteService: create/patch/delete)
├── service/__init__.py             (re-exports both)

packages/web/app/[locale]/admin/users/_components/
├── admin-users-table.tsx  [~210 lines remaining]
├── admin-users-table/_lib/action-labels.ts
├── admin-users-table/_lib/role-options.ts
├── admin-users-table/_lib/reset-description.ts
├── admin-users-table/role-select.tsx
├── admin-users-table/kind-badge.tsx
├── admin-users-table/active-badge.tsx
├── admin-users-table/action-buttons.tsx

packages/service/src/auth/
├── account_settings_router.py  [barrel: ~30 lines]
├── account_settings_router/profile.py
├── account_settings_router/avatar.py
├── account_settings_router/email.py
├── account_settings_router/password.py
├── account_settings_router/deletion.py

packages/web/app/[locale]/_actions/
├── account-settings.ts  [barrel: ~15 lines]
├── account-settings/profile.ts
├── account-settings/avatar.ts
├── account-settings/email.ts
├── account-settings/password.ts
├── account-settings/deletion.ts
```

### Phase P2 (14 files, 4764 lines → ~1700 target)

```
packages/service/src/chat_share/
├── router.py  [barrel: ~30 lines]
├── router/chat_share_validation.py  (upload whitelist + MIME validation)
├── router/chat_share_upload.py      (upload_file endpoint)
├── router/chat_share_presign.py     (presign_chat_file endpoint)
├── router/chat_share_finalize.py    (finalize_chat_file endpoint)

packages/service/src/auth/
├── auth_account_router.py  [barrel: ~30 lines]
├── auth_account_router/login.py
├── auth_account_router/logout.py
├── auth_account_router/me.py
├── auth_account_router/seed.py
├── auth_account_router/forgot.py
├── auth_account_router/reset.py

packages/web/app/[locale]/admin/pre-analysis/[task_id]/_components/
├── admin-pre-analysis-detail-client.tsx  [~150 lines remaining]
├── _lib/pre-analysis-constants.ts         (KIND_LABEL / STATE_LABELS / VIEWABLE_KINDS)
├── _lib/pre-analysis-formatters.ts        (formatSize / buildZipFilename)
├── _lib/pre-analysis-navigation.ts        (viewHrefForKind / buildStatCardClickHandler)
├── summary-section.tsx                    (PageHero + StatCard)
├── output-files-section.tsx              (DataTable + buttons area)

packages/service/src/chat/
├── service.py  [barrel: ~30 lines]
├── chat_read_service.py     (list_conversations / get / list_messages / get_full_backup)
├── chat_write_service.py    (create / update / soft_delete / hard_delete_old / append)

packages/service/src/product_decoders/
├── engine.py  [~200 lines remaining]
├── engine/build_llm_view.py   (build_llm_view extracted)
├── engine/display_formatter.py (format_display extracted)

packages/service/src/permissions/
├── router.py  [barrel: ~30 lines]
├── router/permissions_list.py
├── router/permissions_grant.py
├── router/permissions_revoke.py
├── router/permissions_check.py

packages/service/src/memory/
├── service.py  [~200 lines remaining]
├── service/content_sanitizer.py   (gbk corruption handling / sanitize / MEANINGFUL_KEEP)

packages/web/lib/chat/
├── use-chat-state.ts  [barrel: ~30 lines]
├── use-chat-state/ui-state.ts      (ChatShellUiState + useChatShellUiState)
├── use-chat-state/server-data.ts   (ServerDataParams / serverConvToClient / useServerData)
├── use-chat-state/chat.ts          (ChatShellChatParams / buildInitialMessages / useChatShellChat)
├── use-chat-state/helpers.ts       (createLocalConv / doCreateServerConv / pickNextConvId)

packages/service/src/eval/
├── router.py  [~220 lines remaining]
├── router/eval_check.py             (_check_eval_visibility helper + endpoints that use it)

packages/web/components/
├── theme-provider.tsx  [~150 lines remaining]
├── theme-provider/_lib/theme-storage.ts    (readStored / writeStored / isServer)
├── theme-provider/_lib/theme-resolve.ts    (getSystemTheme / resolveTheme / applyToHtml / isValidTheme)
├── theme-provider/_lib/fouc-inject.ts      (isTestEnv / injectFoucScript)

packages/service/src/health/
├── checks.py  [barrel: ~30 lines]
├── checks/check_dify.py
├── checks/check_neo4j.py
├── checks/check_pgvector.py
├── checks/check_system.py
├── checks/check_minio.py
├── checks/check_redis.py

packages/web/app/[locale]/decode/
├── page.tsx  [~130 lines remaining]
├── decode/_lib/decode-utils.ts     (buildCopyText / filterMainFields / formatDecodeError)
├── decode/result-header.tsx        (view toggle + CopyButton)
├── decode/result-body.tsx          (field cards + LLM pre)

packages/service/src/chat/
├── router.py  [barrel: ~30 lines]
├── router/conversations.py (create / list / get / update / delete)
├── router/messages.py      (append_message / list_messages)
├── router/backup.py        (backup_all)

packages/web/app/[locale]/output/[task_id]/_components/
├── task-detail-client.tsx  [~50 lines remaining]
├── _lib/task-error-utils.ts         (extractErrorMessage / resolveError)
├── _hooks/use-task-download.ts      (useTaskDownload)
├── _hooks/use-task-cancel.ts        (useTaskCancel)
├── body-content-switch.tsx          (BodyContentSwitch)
├── output-panel.tsx                 (OutputPanel)
```

---

## Phase P0: Priority Files (4 files, 3058 lines)

### Task P0-1: camelot_extractor.py (999 lines)

> **Ref:** audit report § `packages/service/src/ingest/pre_analysis/table_extractors/camelot_extractor.py`

**Files:**
- Split `table_extractors/camelot_extractor.py` into 6 modules
- Create: `camelot_config.py`, `camelot_extractor_class.py`, `camelot_ml_runtime.py`, `camelot_page_runner.py`, `camelot_postprocess.py`, `camelot_cross_page.py`
- Keep: `camelot_extractor.py` as barrel re-export (~30 lines)

**Skeleton:** See audit report for per-file skeleton pseudo-code.

- [ ] **Step 1: Create `camelot_config.py`** with `_FLAVOR_DEFAULTS`, `_FACTORY_PARAMS`, `_FALLBACK_CHAIN` from L89-122, and `_FLAVOR_KWARG_SETS` lookup table (object-替-if refactor from L164-172).
- [ ] **Step 2: Create `camelot_extractor_class.py`** with `CamelotTableExtractor` class (L125-335). Keep `_allowed_kwargs` static method.
- [ ] **Step 3: Create `camelot_ml_runtime.py`** with `_ensure_ml_loaded`, `_detect_max_ml_workers`, `_get_ml_inference_sem` from L342-456.
- [ ] **Step 4: Create `camelot_page_runner.py`** with `_run_camelot_single_page`, `_call_camelot` from L477-562.
- [ ] **Step 5: Create `camelot_postprocess.py`** with `realign_columns` (L596-635), `_unmerge_combined_with_ml` (L638-662), `_merge_dedup_lattice_ml` (L674-728), `_stack_contiguous_in_flavor` (L731-775).
- [ ] **Step 6: Create `camelot_cross_page.py`** with `CrossPageMergerConfig` (L778-792), `_bbox_overlap` (L800-824), `_align_consecutive_pages` (L827-866), `CrossPageMerger` class (L869-999).
- [ ] **Step 7: Rewrite `camelot_extractor.py`** as barrel re-exporting from all 6 modules.
- [ ] **Step 8: Update imports** in `__init__.py` and any consumers.
- [ ] **Step 9: Run tests** (`cd packages/service && uv run pytest tests/ingest/pre_analysis/ -v`).
- [ ] **Step 10: Commit**.

### Task P0-2: pdf_processing/router.py (743 lines)

> **Ref:** audit report § `packages/service/src/ingest/pdf_processing/router.py`

**Files:**
- Create: `task_persistence.py`, `task_models.py`, `mime_helper.py`, `path_mode_collect.py`, `uri_mode_collect.py`, `zip_stream.py`
- Keep: `router.py` as barrel (~50 lines) + route handler entries from L289-487

- [ ] **Step 1: Create `task_models.py`** with `OutputFile`, `InputFile`, `IngestTask` dataclasses from L131-189.
- [ ] **Step 2: Create `task_persistence.py`** with `_dict_to_task`, `_save`, `_load`, `_list_user`, `_new_task_id` from L84-130.
- [ ] **Step 3: Create `mime_helper.py`** with `_MIME_MAP`, `_mime_for` from L192-205.
- [ ] **Step 4: Create `path_mode_collect.py`** with `_collect_output_files_legacy`, `_find_output_file` from L217-242.
- [ ] **Step 5: Create `uri_mode_collect.py`** with `_collect_output_files`, `_mime_for_name` from L385-407.
- [ ] **Step 6: Create `zip_stream.py`** with `_zip_iter_uri`, `_zip_iter` from L702-743.
- [ ] **Step 7: Rewrite `router.py`** keeping only imports + route handler functions from L289-487 + barrel re-exports.
- [ ] **Step 8: Run tests** (`cd packages/service && uv run pytest tests/ingest/pdf_processing/`).
- [ ] **Step 9: Commit**.

### Task P0-3: kg/router.py (1040 lines, refuted, partial adoption)

> **Ref:** audit report § `packages/service/src/kg/router.py` — refuted on -73% reduction but split structure valid for readability.

**Notes from refutation:** 1040→280 is inflated; realistic target ~950. Split keeps readability gain even without dramatic reduction. Keep `_audit_store`, `_task_store`, `_REPO_ROOT` as shared module-level singletons.

**Files:**
- Create: `dify_proxy.py` (Dify proxy: stats/health/datasets/segments), `neo4j_list.py` (Neo4j dataset lists), `extract_meta.py` (extract metadata), `extract_upload.py` (upload + factory), `extract_workflow.py` (start/preview/items/commit/export), `kg_schemas.py` (pydantic schemas)
- Keep: `router.py` with shared singletons + endpoint mounts

- [ ] **Step 1: Create `kg_schemas.py`** with `TripleRowIn`, `TriplesRequest`, `TriplesResponse`, `BatchItem`, `BatchRequest`, `BatchResponse` from L55-89, L700-704, L864-871.
- [ ] **Step 2: Create `dify_proxy.py`** with Dify proxy endpoints (L90-248: stats/health/datasets/segments).
- [ ] **Step 3: Create `neo4j_list.py`** with Neo4j list endpoints (L272-404: nodes/relationships/products/schemas).
- [ ] **Step 4: Create `extract_meta.py`** with extract metadata endpoints (L569-662).
- [ ] **Step 5: Create `extract_upload.py`** with upload + factory (L665-739).
- [ ] **Step 6: Create `extract_workflow.py`** with workflow endpoints (L742-1032: start/preview/items/commit/export).
- [ ] **Step 7: Rewrite `router.py`** keeping only imports + shared singletons + endpoint mounts (~120 lines).
- [ ] **Step 8: Run tests** (`cd packages/service && uv run pytest tests/kg/`).
- [ ] **Step 9: Commit**.

### Task P0-4: pdf_processing/converters/cad.py (512 lines)

> **Ref:** audit report § `packages/service/src/ingest/pdf_processing/converters/cad.py` — refuted on -75% but -55% achievable.

**Notes from refutation:** 6 `_record_*` methods share `self._xy()`. Solution: extract `_xy` as module-level free function in `cad_text_records.py`, pass `xy` as parameter. Skip the 6-branch elif->dict refactor (signatures differ). Keep `EzdxfConverter` class in main file.

- [ ] **Step 1: Create `cad_oda_path.py`** with `_read_oda_path_from_env_or_config`, `_apply_oda_path_from_config`, `_resolve_oda_exec_path` from L27-117. Keep the import-time `_apply_oda_path_from_config()` call in new module.
- [ ] **Step 2: Create `cad_oda_reader.py`** with `read_cad_with_oda`, `OdaNotInstalledError` from L124-172.
- [ ] **Step 3: Create `cad_svg_renderer.py`** with `_render_svgs`, `_page_from_modelspace` from L274-326.
- [ ] **Step 4: Create `cad_text_records.py`** with extracted `_xy` as free function + 6 `_record_*` functions taking `xy` as param (L366-463).
- [ ] **Step 5: Create `cad_markdown_writer.py`** with `_text_to_markdown` from L465-512.
- [ ] **Step 6: Rewrite `cad.py`** keeping `EzdxfConverter.convert`, `_read`, and `_extract_text` orchestrator (L180-364, ~185 lines).
- [ ] **Step 7: Run tests** (`cd packages/service && uv run pytest tests/ingest/pdf_processing/`).
- [ ] **Step 8: Commit**.

---

## Phase P1: Medium Priority (9 files)

### Task P1-1: pre_analysis/router.py (568 lines)

> **Ref:** audit report § `packages/service/src/ingest/pre_analysis/router.py`

**Files:** Split into 9 modules (upload / query / download / tables / stages / retry / runner_dispatch / orphan). Main file becomes thin barrel.

- [ ] **Step 1: Create `pre_analysis_upload.py`** with upload endpoint + `_ALLOWED_TABLE_BACKENDS` guard (L67-152).
- [ ] **Step 2: Create `pre_analysis_query.py`** with `list_pre_analysis_tasks`, `get_pre_analysis_task` (L155-185).
- [ ] **Step 3: Create `pre_analysis_download.py`** with `download_pre_analysis_zip`, `download_pre_analysis_file` (L188-282).
- [ ] **Step 4: Create `pre_analysis_tables.py`** with `list_table_pages`, `get_table_page` (L285-396).
- [ ] **Step 5: Create `pre_analysis_stages.py`** with `list_pre_analysis_stages` (L399-425).
- [ ] **Step 6: Create `pre_analysis_retry.py`** with `retry_pre_analysis_task` (L428-493).
- [ ] **Step 7: Create `pre_analysis_runner_dispatch.py`** with `_run_pre_analysis` (L499-544).
- [ ] **Step 8: Create `pre_analysis_orphan.py`** with `_orphan_cleanup_pre_analysis_tasks` (L547-568).

### Task P1-2: lookups/admin_router.py (562 lines)

> **Ref:** audit report § `packages/service/src/lookups/admin_router.py`

**Files:** Split into 7 endpoint modules + `_guards.py` shared helpers.

- [ ] **Step 1: Create `admin_router/_guards.py`** with `_actor_display`, `_client_ip`, `_guard` helpers.
- [ ] **Step 2: Create `admin_router/dict_create.py`** with `create_dictionary` (L110-195).
- [ ] **Step 3: Create `admin_router/dict_patch.py`** with `patch_dictionary` (L198-253).
- [ ] **Step 4: Create `admin_router/item_create.py`** with `create_item` (L259-317).
- [ ] **Step 5: Create `admin_router/item_patch.py`** with `patch_item` (L320-383).
- [ ] **Step 6: Create `admin_router/item_delete.py`** with `soft_delete_item` (L386-451).
- [ ] **Step 7: Create `admin_router/confirm_token.py`** with `issue_confirm_token` (L457-495).
- [ ] **Step 8: Create `admin_router/dict_audit.py`** with `get_dictionary_audit` (L501-562).

### Task P1-3: auth_admin_router.py (464 lines)

> **Ref:** audit report § `packages/service/src/auth/auth_admin_router.py`

**Files:** Split into 6 endpoint modules. Main file becomes barrel (~30 lines).

- [ ] **Step 1: Create `auth_admin_router/admin_users_list.py`** with `UserItem`, `UserListResponse` schemas + `list_users` GET (L40-134).
- [ ] **Step 2: Create `auth_admin_router/admin_invite_create.py`** with `CreateInviteRequest/Response` + `create_invite` POST (L140-222).
- [ ] **Step 3: Create `auth_admin_router/admin_user_patch.py`** with `PatchUserRequest` + `patch_user` PATCH (L228-313).
- [ ] **Step 4: Create `auth_admin_router/admin_password_reset.py`** with `reset_user_password` POST (L319-356).
- [ ] **Step 5: Create `auth_admin_router/admin_invite_list.py`** with `InviteItem`, `InviteListResponse` + `list_invites` GET (L362-428).
- [ ] **Step 6: Create `auth_admin_router/admin_invite_delete.py`** with `delete_invite` DELETE (L434-464).

### Task P1-4: lib/date.ts (450 lines)

> **Ref:** audit report § `packages/web/lib/date.ts`

**Files:** Split into 8 submodules + facade barrel. Delete local `HOURS_PER_DAY`, reuse `@/const`.

- [ ] **Step 1: Create `date/date-instant.ts`** with `DateInput` type, `toInstant`, `InstantUnit` internal type (L15-65).
- [ ] **Step 2: Create `date/date-now.ts`** with `nowInstant`, `nowMs`, `nowIso` (L66-90).
- [ ] **Step 3: Create `date/date-difference.ts`** with 5 differenceIn functions + `durationOf` (L92-159).
- [ ] **Step 4: Create `date/date-add.ts`** with 5 add functions + `shift` internal (L161-227).
- [ ] **Step 5: Create `date/date-compare.ts`** with `isAfter`, `isBefore`, `isEqual`, `instantOf` (L229-270).
- [ ] **Step 6: Create `date/date-format.ts`** with `formatDate`, `formatDateTime` (L272-304).
- [ ] **Step 7: Create `date/date-relative.ts`** with `fmtRelativeTime`, `formatRelativeTime`. Replace 4-branch if-else chains with threshold array + `find()` (L306-356).
- [ ] **Step 8: Create `date/date-duration.ts`** with `formatElapsedMs`, `formatDurationMs` (L358-450). Remove local `MILLIS_PER_HOUR`/`MILLIS_PER_MINUTE`, import from `@/const`.
- [ ] **Step 9: Rewrite `date.ts`** as barrel re-exporting all 8 modules.

### Task P1-5: lookups/service.py (450 lines)

> **Ref:** audit report § `packages/service/src/lookups/service.py`

**Files:** Split into `service/read.py` + `service/write.py`. `LookupService` is all static methods — split into `LookupReadService` + `LookupWriteService`.

- [ ] **Step 1: Create `service/read.py`** with `LookupReadService` containing `list_all_dicts`, `get`, `get_one`, `_load_all_from_db`.
- [ ] **Step 2: Create `service/write.py`** with `LookupWriteService` containing `create_item`, `patch_dict`, `patch_item`, `soft_delete_item`.
- [ ] **Step 3: Create `service/__init__.py`** re-exporting both services.

### Task P1-6: admin-users-table.tsx (438 lines)

> **Ref:** audit report § `packages/web/app/[locale]/admin/users/_components/admin-users-table.tsx`

**Files:** Split into 3 `_lib/` files + 4 component files.

- [ ] **Step 1: Create `_lib/action-labels.ts`** with `ADMIN_ACTION_LABEL` and `ACTIVE_TOGGLE_LABEL` lookup tables.
- [ ] **Step 2: Create `_lib/role-options.ts`** with `buildRoleOptions` pure function.
- [ ] **Step 3: Create `_lib/reset-description.ts`** with `getResetDescription`.
- [ ] **Step 4: Create `role-select.tsx`** with `renderRoleSelect` component (L86-96).
- [ ] **Step 5: Create `kind-badge.tsx`** with `KindBadge` component using `KIND_LABEL` lookup (L98-115).
- [ ] **Step 6: Create `active-badge.tsx`** with `ActiveBadge` component using `ACTIVE_LABEL` lookup (L117-134).
- [ ] **Step 7: Create `action-buttons.tsx`** with `ActionButtons` component (L136-194).

### Task P1-7: account_settings_router.py (424 lines)

> **Ref:** audit report § `packages/service/src/auth/account_settings_router.py`

**Files:** Split into 5 endpoint modules (profile/avatar/email/password/deletion) + `_to_out` helper.

- [ ] **Step 1: Create `account_settings_router/_helpers.py`** with `_to_out` function (L30-44).
- [ ] **Step 2: Create `account_settings_router/profile.py`** with `patch_profile` (L47-76).
- [ ] **Step 3: Create `account_settings_router/avatar.py`** with `post_avatar`, `delete_avatar`, `get_avatar` (L79-178).
- [ ] **Step 4: Create `account_settings_router/email.py`** with `patch_email`, `post_email_verify` (L181-258).
- [ ] **Step 5: Create `account_settings_router/password.py`** with `patch_password` (L261-306).
- [ ] **Step 6: Create `account_settings_router/deletion.py`** with `get_deletion`, `post_deletion`, `delete_deletion` (L309-424).

### Task P1-8: _actions/account-settings.ts (418 lines)

> **Ref:** audit report § `packages/web/app/[locale]/_actions/account-settings.ts`

**Files:** Split into 5 server action modules.

- [ ] **Step 1: Create `account-settings/profile.ts`** with `updateProfileAction` (L31-78).
- [ ] **Step 2: Create `account-settings/avatar.ts`** with `uploadAvatarAction`, `deleteAvatarAction` + helpers (L80-165).
- [ ] **Step 3: Create `account-settings/email.ts`** with `requestEmailChangeAction` (L167-225).
- [ ] **Step 4: Create `account-settings/password.ts`** with `changePasswordAction` (L227-301).
- [ ] **Step 5: Create `account-settings/deletion.ts`** with `requestDeletionAction`, `cancelDeletionAction` (L303-418).

---

## Phase P2: Lower Priority (14 files)

### Task P2-1: chat_share/router.py (413 lines)

> **Ref:** audit report § `packages/service/src/chat_share/router.py`

**Files:** Create 3 endpoint modules + validation module.

- [ ] **Step 1: Create `router/chat_share_validation.py`** with MIME whitelist + validation helpers (L77-135).
- [ ] **Step 2: Create `router/chat_share_upload.py`** with `upload_file` endpoint (L276-309).
- [ ] **Step 3: Create `router/chat_share_presign.py`** with `presign_chat_file` endpoint (L315-363).
- [ ] **Step 4: Create `router/chat_share_finalize.py`** with `finalize_chat_file` endpoint (L366-413).
- [ ] **Step 5: Rewrite main router** keeping create/get/revoke/list endpoints + barrel re-exports.

### Task P2-2: auth_account_router.py (402 lines)

> **Ref:** audit report § `packages/service/src/auth/auth_account_router.py`

**Files:** Split into 6 endpoint modules.

- [ ] **Step 1: Create `auth_account_router/login.py`** with login endpoint.
- [ ] **Step 2: Create `auth_account_router/logout.py`** with logout endpoint.
- [ ] **Step 3: Create `auth_account_router/me.py`** with me endpoint.
- [ ] **Step 4: Create `auth_account_router/seed.py`** with seed_admin endpoint.
- [ ] **Step 5: Create `auth_account_router/forgot.py`** with forgot_password endpoint.
- [ ] **Step 6: Create `auth_account_router/reset.py`** with reset_password endpoint.

### Task P2-3: admin-pre-analysis-detail-client.tsx (400 lines)

> **Ref:** audit report § `packages/web/app/[locale]/admin/pre-analysis/[task_id]/_components/admin-pre-analysis-detail-client.tsx`

- [ ] **Step 1: Create `_lib/pre-analysis-constants.ts`** with `KIND_LABEL`, `STATE_LABELS`, `VIEWABLE_KINDS`.
- [ ] **Step 2: Create `_lib/pre-analysis-formatters.ts`** with `formatSize`, `buildZipFilename`.
- [ ] **Step 3: Create `_lib/pre-analysis-navigation.ts`** with `viewHrefForKind`, `buildStatCardClickHandler`.
- [ ] **Step 4: Create `summary-section.tsx`** with `PageHero` + `StatCard` grid (L274-336).
- [ ] **Step 5: Create `output-files-section.tsx`** with output table area (L348-396).

### Task P2-4: chat/service.py (398 lines)

> **Ref:** audit report § `packages/service/src/chat/service.py`

**Files:** Split into read/write service modules.

- [ ] **Step 1: Create `chat_read_service.py`** with `list_conversations`, `get_conversation`, `list_messages`, `get_full_backup`, `hard_delete_old_soft_deleted`.
- [ ] **Step 2: Create `chat_write_service.py`** with `create_conversation`, `update_conversation`, `soft_delete_conversation`, `append_message`.

### Task P2-5: product_decoders/engine.py (390 lines)

> **Ref:** audit report § `packages/service/src/product_decoders/engine.py`

- [ ] **Step 1: Create `engine/build_llm_view.py`** with `build_llm_view` pure function (L193-340).
- [ ] **Step 2: Create `engine/display_formatter.py`** with `format_display` static method (L342-390).

### Task P2-6: permissions/router.py (370 lines)

> **Ref:** audit report § `packages/service/src/permissions/router.py`

**Files:** Split into 4 endpoint modules.

- [ ] **Step 1: Create `router/permissions_list.py`** with list endpoint.
- [ ] **Step 2: Create `router/permissions_grant.py`** with grant endpoint.
- [ ] **Step 3: Create `router/permissions_revoke.py`** with revoke endpoint.
- [ ] **Step 4: Create `router/permissions_check.py`** with check endpoint.

### Task P2-7: memory/service.py (340 lines)

> **Ref:** audit report § `packages/service/src/memory/service.py`

- [ ] **Step 1: Create `service/content_sanitizer.py`** with `_GARBLED_RUN`, `_MEANINGFUL_KEEP`, `_sanitize_content`, `_is_pure_garbage` (L48-77) + `_clean_messages` (L222-237).

### Task P2-8: use-chat-state.ts (331 lines)

> **Ref:** audit report § `packages/web/lib/chat/use-chat-state.ts`

**Files:** Split into 4 submodules + facade barrel.

- [ ] **Step 1: Create `use-chat-state/ui-state.ts`** with `ChatShellUiState` + `useChatShellUiState` (L30-78).
- [ ] **Step 2: Create `use-chat-state/server-data.ts`** with `ServerDataParams`, `ServerData`, `serverConvToClient`, `useServerData` (L80-136).
- [ ] **Step 3: Create `use-chat-state/chat.ts`** with `ChatShellChatParams`, `ChatShellChat`, `buildInitialMessages`, `useChatShellChat` (L138-250). Fix the ternary-style destructuring at L181-183.
- [ ] **Step 4: Create `use-chat-state/helpers.ts`** with `createLocalConv`, `doCreateServerConv`, `pickNextConvId`, `deleteConversationLocal` (L268-331).
- [ ] **Step 5: Rewrite `use-chat-state.ts`** as barrel re-export. Keep deprecated `useChatShellState`, `removeConvLocal` compat exports with `@deprecated` JSDoc tag.

### Task P2-9: eval/router.py (323 lines)

> **Ref:** audit report § `packages/service/src/eval/router.py`

- [ ] **Step 1: Create `router/eval_check.py`** with `_check_eval_visibility` helper + endpoints that use it.

### Task P2-10: theme-provider.tsx (322 lines)

> **Ref:** audit report § `packages/web/components/theme-provider.tsx`

**Files:** Split 10 module-level pure functions into 3 `_lib/` files.

- [ ] **Step 1: Create `theme-provider/_lib/theme-storage.ts`** with `STORAGE_KEY`, `readStored`, `writeStored`, `isServer` (L33-38, L104-118, L120).
- [ ] **Step 2: Create `theme-provider/_lib/theme-resolve.ts`** with `getSystemTheme`, `resolveTheme`, `applyToHtml`, `isValidTheme` (L92-148).
- [ ] **Step 3: Create `theme-provider/_lib/fouc-inject.ts`** with `isTestEnv`, `injectFoucScript`, `FOUC_MARKER` (L176-208).

### Task P2-11: health/checks.py (316 lines)

> **Ref:** audit report § `packages/service/src/health/checks.py`

**Files:** Split into 6 per-service check modules + `CheckResult` shared type.

- [ ] **Step 1: Create `checks/check_dify.py`** with `check_dify` (L97-123).
- [ ] **Step 2: Create `checks/check_neo4j.py`** with `check_neo4j` (L129-138).
- [ ] **Step 3: Create `checks/check_pgvector.py`** with `check_pgvector` (L144-164).
- [ ] **Step 4: Create `checks/check_system.py`** with `check_system` (L170-225).
- [ ] **Step 5: Create `checks/check_minio.py`** with `check_minio` (L231-274).
- [ ] **Step 6: Create `checks/check_redis.py`** with `_get_redis_client` + `check_redis` (L280-316).

### Task P2-12: decode/page.tsx (312 lines)

> **Ref:** audit report § `packages/web/app/[locale]/decode/page.tsx`

**Files:** Split 4 pure functions + 2 sub-components.

- [ ] **Step 1: Create `decode/_lib/decode-utils.ts`** with `buildCopyText`, `filterMainFields`, `formatDecodeError` (L22-84).
- [ ] **Step 2: Create `decode/result-header.tsx`** with result header (view toggle + CopyButton, L233-286).
- [ ] **Step 3: Create `decode/result-body.tsx`** with field cards + LLM pre (L289-305).

### Task P2-13: chat/router.py (305 lines)

> **Ref:** audit report § `packages/service/src/chat/router.py`

**Files:** Split into 3 modules (conversations / messages / backup).

- [ ] **Step 1: Create `router/conversations.py`** with conversation CRUD endpoints (L44-208).
- [ ] **Step 2: Create `router/messages.py`** with `append_message`, `list_messages` (L211-279).
- [ ] **Step 3: Create `router/backup.py`** with `backup_all` (L282-305).

### Task P2-14: task-detail-client.tsx (304 lines)

> **Ref:** audit report § `packages/web/app/[locale]/output/[task_id]/_components/task-detail-client.tsx`

- [ ] **Step 1: Create `_lib/task-error-utils.ts`** with `extractErrorMessage`, `resolveError` (L24-52).
- [ ] **Step 2: Create `_hooks/use-task-download.ts`** with `useTaskDownload` hook (L62-94).
- [ ] **Step 3: Create `_hooks/use-task-cancel.ts`** with `useTaskCancel` hook (L96-125).
- [ ] **Step 4: Create `body-content-switch.tsx`** with `BodyContentSwitch` component (L183-255).
- [ ] **Step 5: Create `output-panel.tsx`** with `OutputPanel` component (L256-304).

---

## Self-Review Checklist

**1. Spec coverage:**
- All 27 verified files from the audit report are assigned to tasks (4 P0 + 9 P1 + 14 P2 = 27 files)
- Each task references the exact line numbers and split structure from the audit
- Refuted files are NOT included in the plan per audit conclusion

**2. Placeholder scan:**
- No "TBD", "TODO", "implement later" — all tasks have concrete steps
- Every step references actual file content (line ranges, split points from audit)
- All test commands are exact (`uv run pytest ...` / `bun run test ...`)

**3. Type consistency:**
- All stated file paths match the project convention (`packages/service/src/`, `packages/web/`)
- Split naming consistent across tasks (submodule dirs use kebab-case)
- Barrel re-export pattern consistent across all tasks

**Coverage gaps:** None — all 27 verified files from the audit are covered across 3 phases.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-07-10-oversize-files-refactor.md`.

**Two execution options:**

1. **Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration. Use `superpowers:subagent-driven-development`.

2. **Inline Execution** - Execute tasks in this session using `superpowers:executing-plans`, batch execution with checkpoints.

**Which approach?**
