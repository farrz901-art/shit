# Pyright Strictness Audit

**Date:** 2026-06-25  
**Scope:** `packages/service` (402 `.py` files, 19-line `pyrightconfig.json`)  
**Method:** Automated L0-L4 incremental testing, restore after each level

---

## L0 基线 (basic + 6 none)

| 指标 | 值 |
|------|-----|
| typeCheckingMode | `basic` |
| 覆盖规则 | reportMissingTypeStubs: none, 5× reportUnknown\*: none |
| Errors | 23 |
| Warnings | 2 |

基线已有 23 error (非 reportUnknown\* 产生). 其中 `tests/kg/test_audit_models.py:39` 的 `reportAttributeAccessIssue` 占主要.

---

## L1: 删 reportUnknown\* none -> warning

逐一将 `"none"` 提升为 `"warning"` (即恢复 basic mode 默认级别), 独立测试, 不累积.

| 规则 | 新增 warnings | 重灾区 (Top 5 文件) |
|------|---------------|-------------------|
| `reportUnknownMemberType` | 2,811 | tests/auth/test_account_settings_router_mock.py (97), tests/chat/test_service_mock.py (94), src/ingest/converters/cad.py (93), tests/buyer_profile/test_router.py (86), scripts/neo4j_import.py (72) |
| `reportUnknownVariableType` | 1,760 | tests/scripts/test_neo4j_import.py (211), src/product_decoders/engine.py (71), scripts/neo4j_import.py (62), src/ingest/pipeline.py (34), src/kg/client.py (31) |
| `reportUnknownArgumentType` | 766 | tests/scripts/test_neo4j_import.py (60), tests/ingest/test_converters.py (38), src/ingest/converters/cad.py (35), scripts/neo4j_import.py (27), tests/ingest/test_archive_handler.py (26) |
| `reportUnknownParameterType` | 1,347 | tests/scripts/test_neo4j_import.py (58), tests/buyer_profile/test_router.py (46), tests/chat/test_service_mock.py (36), tests/storage/test_object_store.py (31), scripts/neo4j_import.py (30) |
| `reportUnknownLambdaType` | 74 | tests/buyer_profile/test_service.py (15), tests/approvals/test_router.py (14), tests/auth/test_admin_users_api.py (8), tests/core/test_redis_client.py (6), tests/conftest.py (5) |

**观察:** 5 条规则均为 `warning` 级别而非 `error`, 因此 errors 保持 23 不变. 总量 ~6,758 条新增 warning, `tests/scripts/test_neo4j_import.py` 和 `scripts/neo4j_import.py` 是多规则交叉重灾区. 建议先集中修 `reportUnknownMemberType` (2811 条) 和 `reportUnknownParameterType` (1347 条) 这两个大户.

---

## L2: typeCheckingMode = "standard"

去除 reportUnknown\* 覆盖, 切换到 standard mode.

| 指标 | 值 |
|------|-----|
| Errors | 28 (+5  vs L0) |
| Warnings | 2 |

Top 10 文件/位置 (按文件聚合):

| 文件 | Errors |
|------|--------|
| tests/auth/test_email_change_concurrency.py | 7 |
| tests/buyer_profile/test_schemas.py | 4 |
| src/orchestration/multi_step_rag.py | 2 |
| tests/auth/test_login.py | 2 |
| src/chat/service.py | 1 |
| src/ingest/converters/kreuzberg.py | 1 |

**分析:** 从 basic 到 standard 仅增加 5 error, 说明项目当前代码与 standard mode 兼容度较高. 新增的 5 error 来自 standard mode 默认开启的更严格规则 (如 `reportInvalidTypeForm` 等).

---

## L3: standard + 逐一加 strict 规则

在 standard mode 基础上, 逐一添加 `"error"` 覆盖.

| 规则 | 新增 errors (vs L2) | 说明 |
|------|-------------------|------|
| `reportOptionalMemberAccess` | 0 | standard mode 默认已启用相同级别 |
| `reportOptionalSubscript` | 0 | 同上 |
| `reportOptionalCall` | 0 | 同上 |

**分析:** standard mode 的 Optional 相关规则已经启用, `"error"` 覆盖不产生增量. 这三条规则在 standard→strict 间不会增加额外成本.

---

## L4: typeCheckingMode = "strict"

| 指标 | 值 |
|------|-----|
| Errors | 8,272 |
| Warnings | 0 |

**Erros > 1000 => too many (>1000).**

Top 重灾区:

| 文件 | Lines with errors |
|------|-------------------|
| src/storage/object_store.py (L461, L519) | 各 11 |
| tests/auth/test_email_change_concurrency.py L30 | 7 |
| src/auth/account_settings_service.py L269 | 5 |
| src/ingest/api.py L92 | 5 |
| tests/buyer_profile/test_field_config.py (L32,46,69,103,114) | 各 5 |

**分析:** strict mode 开启大量额外规则 (`reportUnknown*` 升为 `error`, `reportMissingTypeStubs` 升为 `error`, `reportMissingParameterType`, `reportMissingTypeArgument`, 以及 strict 独有规则). 8,272 errors 意味着全面 strict 在当前代码基上不可行.

---

## 结论与建议

| 级别 | Errors | 可行性 | 建议 |
|------|--------|--------|------|
| **L0** (当前 basic+none) | 23 | -- | 已有 23 error, 需先修复 |
| **L1** (+reportUnknown\* warning) | 23 (+6,758 warnings) | **中等** | 6,758 warnings 可批量修, 建议从 `reportUnknownMemberType` 开始 |
| **L2** (standard mode) | 28 | **推荐** | 仅 +5 error, 成本极低, 立即可用于 CI |
| **L3** (standard + strict rules) | 28 | **推荐** | 三条 Optional 规则零增量, 可直接开启 |
| **L4** (full strict) | 8,272 | **暂缓** | >1000 errors, 需要大型重构 |

**建议路线:**
1. 先修 L0 的 23 error (现有 baseline)
2. 切换到 **standard mode** (L2): 只需修 5 个新 error, 收益/成本比最高
3. 同时开启 `reportOptional*` 三条规则 (L3): 零成本
4. L1 warning 降级: 作为后续持续改进项, 从 `reportUnknownMemberType` 开始逐步消除

**文件:** `packages/service/pyrightconfig.json` (19 lines)
