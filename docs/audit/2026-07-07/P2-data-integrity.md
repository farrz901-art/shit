# P2 — 数据完整性 修复 spec 草稿 (2026-07-07)

> ⚠️ 草稿, 未实施. 来源: [AUDIT-REPORT.md §D4](../AUDIT-REPORT.md)

## 范围
- **DATA-001** (high, verified) — pre_analysis_tasks 3 JSON 列用 sa.Text
- **DATA-002** (high, verified) — 3 枚举轴硬编 CheckConstraint 不走 lookup
- D4 其余 5 条 (DATA-003/004/005/006/007)

## 修复策略

### 1. JSONB 迁移 (DATA-001 + DATA-006)
- 新 migration 把 `pre_analysis_tasks.output_files_json`, `summary_json`, `task_config_json` 3 列从 `sa.Text` 改 `sa.dialects.postgresql.JSONB()`
- 同步把代码里 `json.dumps/loads` 模式改成 `jsonb_set` / `jsonb ||` 原生操作
- 验证: `tests/migrations/test_json_jsonb_policy.py` 加 case

### 2. 枚举转 lookup (DATA-002)
- 3 个新枚举轴进 `configs/dictionaries_seed.yaml`:
  - `pre_analysis_state` (pending/running/completed/failed)
  - `pre_analysis_task_stage_status` (started/completed/failed/skipped)
  - `pre_analysis_stage` (5 detail stages)
- `current_stage` (overall) 也加 CheckConstraint 或注册到 lookup
- migration 删除 hardcoded CheckConstraint, 改 lookup 校验

### 3. FK ondelete 补齐 (DATA-003/004)
- `evaluations.user_id`, `approvals.*` 加 `ondelete="CASCADE"` (跟 conversations 对齐)

### 4. JSONB 类型漂移防御 (DATA-006/007)
- 全局禁 `sa.JSON()` (改用 `JSONB()`)
- `_REFERENCE_MAP` 监控新枚举, 缺则 dev 启动期警告

## 不在本文范围
- 实施代码
- 历史列 5 个已转 JSONB 列的 recheck
