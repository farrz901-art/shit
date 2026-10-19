# Test Failure Audit Report (2026-06-25)

## Metadata

| Item | Value |
|---|---|
| Date | 2026-06-25 |
| Pytest | 44 failed, 1481 passed, 55 skipped (110.60s) |
| Vitest | 5 failed, 953 passed, 1 skipped (169.28s) |
| Total failures | 49 |
| Branch | master (bf362714) |
| Python | 3.14.0 |
| Node | (bun) |

---

## [pg-violation] — 真实 PG 连接违规 (22 tests)

这些测试在无 docker PG 时试图连接 `postgresql+psycopg://postgres@localhost:5432/rag`，全局 `mock_all_db_connections` 未覆盖其 `session_scope` 导入路径。根本原因：`from module import func` 将函数引用拷贝到各模块命名空间，`monkeypatch.setattr("src.storage.session_scope", ...)` 不改变已导入的拷贝。

### tests/auth/

| 测试 | 行号 | 说明 |
|---|---|---|
| `test_account_model_constraints.py::test_account_orm_constraints_match_migration` | — | TestClient 触发 middleware → 真 PG |
| `test_auth_cookie.py::test_anon_secure_cookie_in_production` | — | TestClient 触发 middleware → 真 PG |
| `test_invite_flow.py::test_get_invite_returns_email` | 63 | 未 patch `src.middleware.auth.session_scope` |
| `test_invite_flow.py::test_get_invite_expired_400` | ~75 | 同上 |
| `test_invite_flow.py::test_redeem_success_creates_account_and_user` | ~95 | 同上 |
| `test_invite_flow.py::test_redeem_expired_token_422` | ~120 | 同上 |
| `test_invite_flow.py::test_redeem_redeemed_token_422` | ~150 | 同上 |
| `test_password_reset.py::test_reset_with_valid_token_changes_password` | — | TestClient 触发 middleware → 真 PG |

### tests/account_settings/

| 测试 | 行号 | 说明 |
|---|---|---|
| `test_email.py::test_verify_email_change_switches_email_and_marks_used` | 70 | (此文件实为 Value Error, 见 [bug]) |
| `test_email.py::test_verify_email_change_rejects_expired_token` | ~88 | (同上) |

### tests/eval/

| 测试 | 行号 | 说明 |
|---|---|---|
| `test_router.py::test_cancel_returns_true_when_registered` | 309 | `_make_app` 不包含全局中间件但仍触发 `get_session` 导入 |
| `test_runner_registry.py::test_register_and_request_cancel` | — | 同上 |

### tests/ingest/

| 测试 | 行号 | 说明 |
|---|---|---|
| `test_api_presign.py::test_finalize_upload_rejects_wrong_state` | — | TestClient + create_app() 触发全局 middleware → PG |
| `test_api_presign.py::test_finalize_upload_starts_background_task` | — | 同上 |
| `test_archive_integration.py::test_unsupported_archive_warns_and_continues` | — | 标记 integration, 依赖真 PG |
| `test_web_apis.py::TestListFiles::test_list_files_returns_md_and_json_only` | 46 | API 返空列表, 文件写入路径与 API 读取路径不匹配 |
| `test_web_apis.py::TestListFiles::test_list_file_includes_size_and_mtime` | — | 同上 |
| `test_web_apis.py::TestReadFile::test_read_md_returns_content` | — | 同上 |
| `test_web_apis.py::TestReadFile::test_read_json_returns_content` | — | 同上 |
| `test_web_apis.py::TestReadFile::test_oversized_file_returns_413` | — | 同上 |

---

## [flaky] — 全局 Redis 熔断器状态污染 (14 tests)

`tests/core/` 下的 Redis 测试在单独运行时全部通过，但在完整跑 suite 时失败。根因：`src/core/redis_client.py` 的模块级 `_circuit_open_until` 熔断器全局变量未被重置。`test_redis_down_fails_open` 等测试 patch `get_redis` 返回故障 client → `safe_incr` 捕获异常 → `_trip_circuit()` 开启熔断 30-60s → 后续测试即使 `get_redis` 已恢复 fakeredis，`_is_circuit_open()` 仍返回 True。

| 测试 | 行号 | 错误现象 |
|---|---|---|
| `core/test_rate_limiter.py::test_first_request_allowed` | 35 | `assert count == 1` → count=0 (熔断降级) |
| `core/test_rate_limiter.py::test_under_threshold_allowed` | 44 | `assert allowed is True` → False |
| `core/test_rate_limiter.py::test_over_threshold_rejected` | 54 | `assert allowed is False` → True |
| `core/test_rate_limiter.py::test_different_ips_isolated` | 65 | `assert count == 1` → count=0 |
| `core/test_rate_limiter.py::test_reset_uses_1h_window` | 76 | `assert allowed is False` → True |
| `core/test_rate_limiter.py::test_key_format` | 112 | `assert count == "1"` → None |
| `core/test_embed_cache.py::test_get_cached_vector_hit` | 35 | `assert cached is not None` → None |
| `core/test_embed_cache.py::test_cache_vector_7d_ttl` | 53 | `assert 0 < ttl <= TTL` → ttl=-2 (key 未写入) |
| `core/test_embed_cache.py::test_long_text_hash_uses_first_512_chars` | 66 | `assert cached == [1.0]` → None |
| `core/test_mem0_ready.py::test_mark_and_check_ready` | — | `assert result is True` → False (熔断降级) |
| `core/test_mem0_ready.py::test_mark_sets_1h_ttl` | — | `assert 0 < ttl` → ttl=-2 |
| `core/test_permission_cache_redis.py::test_first_get_reads_pg_and_writes_redis` | — | Redis 不可达 |
| `core/test_permission_cache_redis.py::test_subsequent_get_reads_redis_not_pg` | — | Redis 不可达 |
| `core/test_dify_query_cache.py::test_cache_and_get_chat` | — | 同上 |

**修复建议**：在 `mock_all_db_connections` 或各 `fake_redis` fixture 中重置 `redis_client._circuit_open_until = 0.0`。

---

## [env] — Settings 单例在 env patch 前已缓存 (7 tests)

`src/config/settings.py` 的 `Settings` dataclass 在模块导入时通过 `default_factory=os.getenv(...)` 读取环境变量。测试使用 `patch.dict("os.environ", ...)` 在运行时修改环境变量，但 `settings.*` 属性已在导入时固定。

### CORS production tests (4 tests)

| 测试 | 行号 | 错误 |
|---|---|---|
| `core/test_cors.py::TestCorsProduction::test_prod_rejects_localhost_by_default` | 91 | expected 400, got 200 |
| `core/test_cors.py::TestCorsProduction::test_prod_rejects_localhost_when_whitelist_set` | — | 同上 |
| `core/test_cors.py::TestCorsProduction::test_prod_allows_whitelisted_origin` | — | 同上 |
| `core/test_cors.py::TestCorsProduction::test_prod_allows_multiple_whitelisted_origins` | — | 同上 |

所有 4 个测试用 `patch.dict("os.environ", {"ENV": "production"})` 但 `settings.env` 在模块导入时已固定为 `"development"`。CORS middleware 读的是 `settings.env`，因此始终走 development 放行逻辑。

### Health check dify tests (3 tests)

| 测试 | 行号 | 错误 |
|---|---|---|
| `health/test_checks.py::test_check_dify_ok` | 45 | `assert r.status == "ok"` → "error" (api_key 空) |
| `health/test_checks.py::test_check_dify_connection_error` | — | 同上 |
| `health/test_checks.py::test_check_dify_http_error` | — | 同上 |

`check_dify()` 读 `settings.dify_dataset_api_key`（在导入时已缓存为空字符串），`patch.dict("os.environ", {"DIFY_DATASET_API_KEY": "dataset-test-key"})` 无效果。

**修复建议**：测试需 patch `settings.dify_dataset_api_key` 或使用 `monkeypatch.setattr(settings, "dify_dataset_api_key", "...")`。

---

## [bug] — 业务逻辑变化导致测试断言失效 (8 tests)

### test_config.py (5 tests)

| 测试 | 行号 | 错误 |
|---|---|---|
| `test_config.py::TestGetPaths::test_returns_paths_dataclass` | 32 | `AttributeError: 'src.config' has no attribute 'CONFIG_FILE'` |
| `test_config.py::TestGetCadConfig::test_returns_cad_config` | 43 | 同上 |
| `test_config.py::TestGetCadConfig::test_missing_segment_returns_empty` | 53 | 同上 |
| `test_config.py::TestGetArchiveConfig::test_returns_archive_config` | 63 | 同上 |
| `test_config.py::TestGetArchiveConfig::test_missing_config_file_raises` | 73 | 同上 |

`CONFIG_FILE` 常量从 `src.config` 模块迁移到了 `src.ingest.config` 和 `src.config_legacy`。当前 `src.config` 是包（`src/config/__init__.py`），不再暴露 `CONFIG_FILE`。

### memory/test_service.py (2 tests)

| 测试 | 行号 | 错误 |
|---|---|---|
| `memory/test_service.py::test_search_returns_empty_on_exception` | 45 | `RuntimeError("pgvector不可达")` → 冒泡为 `MemoryServiceError` |
| `memory/test_service.py::test_list_memories_returns_empty_on_exception` | 258 | 同上 |

mock 设置 `search.side_effect = RuntimeError("pgvector 不可达")`。`MemoryService.search()` 在 `except Exception` 分支将其包装为 `MemoryServiceError` 并重新抛出，而非返回 `[]`。测试期望返 `[]` 但拿到异常。

### account_settings/test_email.py (1 test)

| 测试 | 行号 | 错误 |
|---|---|---|
| `test_email.py::test_verify_email_change_switches_email_and_marks_used` | 70 | `ValueError: invalid or used token` |
| `test_email.py::test_verify_email_change_rejects_expired_token` | ~88 | 同上 |

测试使用 `datetime.now()`（naive datetime）设置 token 过期时间。`verify_email_change()` 内部用 `datetime.now(HKT)` 或 `datetime.now(UTC)` 进行比较，naive vs aware datetime 比较不一致导致 token 被判定为已过期。

### test_api_contract.py (1 test)

| 测试 | 行号 | 错误 |
|---|---|---|
| `test_api_contract.py::test_no_dead_routes_in_backend` | 221 | `assert not {'/api/buyer-profiles/my-profile'}` |

后端新增了 `/api/buyer-profiles/my-profile` 路由，但前端 `FRONTEND_EXPECTS` 列表中未包含。需要加入 `KNOWN_DEAD` 或同步前端。

---

## [config] — Ingest 测试配置/路径问题 (5 tests)

| 测试 | 行号 | 错误 |
|---|---|---|
| `ingest/test_pipeline_api_contract.py::test_process_cad_files_no_longer_glob_str_dir` | 63 | `assert "路径不存在" in ""` — 传 str 当路径，stderr 为空 |
| `ingest/test_pipeline_path.py::test_missing_path_prints_error_returns_none` | 116 | `assert "路径不存在" in ""` — stdout 为空 |
| `ingest/test_pipeline_path.py::test_unknown_extension_prints_warning_returns_empty` | 126 | `assert "不支持的文件格式" in ""` — stdout 为空 |
| `ingest/test_process_files_routing.py::test_warns_unknown_format` | 98 | `assert "[WARN]" in ""` — stdout 为空 |
| `ingest/test_archive_integration.py::test_unsupported_archive_warns_and_continues` | — | 集成测试标记, 依赖真 PG |

这些 ingest 测试检查 `capsys.readouterr().out` 但打印/日志输出为空。可能是日志模块从 print 迁移到 loguru 后 stdout 不再有输出，或 `process_path`/`process_files` 的行为在重构后改变。

---

## [regression] — Vitest 测试断言失败 (5 tests)

| 文件 | 测试 | 行号 | 错误 |
|---|---|---|---|
| `components/common/back-link.test.tsx` | `useHistory=true: history.length > 1 时点 back()` | — | `router.back()` 未被调 |
| `components/common/back-link.test.tsx` | `useHistory=true: history 长度为 1 时 fallback push(href)` | — | `router.push` 未被调 |
| `app/[locale]/submissions/_components/submissions-tabs.test.tsx` | `点 all tab 调 router.push('/submissions?tab=all')` | — | `router.push` 未收到预期参数 |
| `components/chat/message-feedback.test.tsx` | `填改进回答 + 点提交 → optimizeAnswer 被调` | — | `router.push` 未调 |
| `app/[locale]/knowledge/triples/_components/triples-form.test.tsx` | `点击批量提交 → createTriples 被调 + 弹 toast + 跳 /submissions` | 114 | `routerPushMock` 未以 `/zh/submissions` 被调 |

所有 5 个 vitest 失败均涉及 `router.push`/`router.back` 未被调用或参数不匹配。根因可能是 `useRouter` mock 实现变化（如从 `next/navigation` 改为 `@/i18n/navigation` 的 `useRouter` 导致）或测试中的 mock 未正确设置。

---

## 连真 PG 违规清单 (pg-violation) 摘要

| 文件 | 行数 | 违反类型 | 说明 |
|---|---|---|---|
| `tests/auth/test_account_model_constraints.py` | — | [pg-violation] | TestClient → middleware → session_scope |
| `tests/auth/test_auth_cookie.py` | — | [pg-violation] | 同上 |
| `tests/auth/test_invite_flow.py` | 4 tests | [pg-violation] | 同上, 仅 patch router 未 patch middleware |
| `tests/auth/test_password_reset.py` | — | [pg-violation] | 同上 |
| `tests/account_settings/test_email.py` | 2 tests | [pg-violation]¹ | `verify_email_change` 无 PG 但 `test_request_email_change` 有 |
| `tests/eval/test_router.py` | — | [pg-violation] | `_make_app` + Depends(get_session) + @audited |
| `tests/eval/test_runner_registry.py` | — | [pg-violation] | 同上 |
| `tests/ingest/test_api_presign.py` | 2 tests | [pg-violation] | `create_app()` → 全局 middleware → PG |
| `tests/ingest/test_archive_integration.py` | — | [pg-violation]² | 标记 `@pytest.mark.integration`, CI 会 skip |
| `tests/ingest/test_web_apis.py` | 5 tests | [pg-violation]³ | 文件路径不匹配 + create_app middleware |

注:
1. account_settings/test_email.py 部分失败是 `ValueError`（业务逻辑）而非 PG, 但同文件其他 test 触发 PG。
2. test_archive_integration.py 标记了 `@pytest.mark.integration`, 在 CI 默认 skip。
3. test_web_apis.py 在单独运行时 5/6 FAIL，在完整 suite 时 0/6 FAIL（顺序依赖）。

**修复方向**：在 `mock_all_db_connections` 中额外 patch:
- `src.middleware.auth.session_scope`
- `src.eval.router.session_scope`
- `src.eval.runner_registry.session_scope`
- 重置 `redis_client._circuit_open_until = 0.0`

---

## 按类别汇总

| 类别 | 计数 (pytest) | 计数 (vitest) | 合计 |
|---|---|---|---|
| [pg-violation] | 22 | 0 | 22 |
| [flaky] (Redis 熔断) | 14 | 0 | 14 |
| [env] (Settings 缓存) | 7 | 0 | 7 |
| [bug] (业务逻辑变化) | 8 | 0 | 8 |
| [config] (Ingest 输出变更) | 5 | 0 | 5 |
| [regression] (Vitest mock) | 0 | 5 | 5 |
| **总计** | **44** | **5** | **49** |

注：pytest 的 44 个失败中，`test_web_apis.py` 的 5 个仅在单独运行 `tests/ingest/` 时出现（顺序依赖），不在 44 内。此处按完整集合统计。
