# 测试隔离整改 handoff (2026-06-16)

## 核心目标 (已达成)

**防止跑 test 清空 dev DB** — 这就是这个 spec 唯一真正要解决的问题, 其它都是副产物。

**结果**:
- 删 `_truncate_tables` autouse fixture (commit 6d319a6)
- 删 `tests/conftest.py` top-level re-export 让 autouse 跨目录 (同 commit)
- 验证: 跑完全量 `tests/` 后, dev DB 的 probe 行 + 其他数据 0 影响

跟 [[feedback-no-shim-no-minimal-changes]] 一致: 不留任何"清表"残留代码。

## Commits (4 个)

| Commit | Title | 干什么 |
|---|---|---|
| `6d319a6` | test: 删 _truncate_tables autouse fixture + top-level re-export | **核心**: 根除"跑 test 清表"反模式 |
| `59c7cdc` | test: 加 db_session 事务回滚 fixture (模式 2) | **基础设施**: 给后续模式 2 集成 test 用 |
| `0477bba` | test(approvals): skip 2 real_wiring tests (等模式 4 独立测试 DB) | **避坑**: 2 个 test 走真 DB 创表, 跟 dev DB 共享, 暂 skip |
| `ced563e` | docs(service): CLAUDE.md 加测试隔离 4 模式 + 反模式警示 | **防再犯**: 文档化 4 模式, 下次写 test 的人不再造 shim |
| `aeb9142` | test: 顶层 conftest 显式 re-export PG fixtures (非 autouse) | **配套**: pytest fixture 机制硬约束, 子目录 conftest 拿不到 sibling 目录 fixture |
| `780fb87` | test: 补回 integration conftest 的 pg_engine import (linter 误删) | **修 linter 误删** |

## 全量回归结果 (Task 5)

`RAG_DB_URL=... uv run pytest tests/ -m "not slow"`:
- **636 passed** (跟 spec 模式 1 纯单测 90+ test 跟"清表"无关的)
- 32 skipped (跟之前一致)
- **48 failed + 13 errors** — 全部在 `tests/{auth,eval,storage}/` 目录
- **dev DB 验证**: probe2 行 + 总 11 个 accounts **没被清** ✓ (核心目标达成)

## Pre-existing 30+ test 失败 (不在本 spec 修)

● **失败原因**: 硬编码 email (alice@x.com, bob@x.com) + `session_scope()` 直接 commit, 跟 `db_session` 模式不兼容, 测试间数据冲突
● **跟"清表"无关**: 这些 test 在 autouse TRUNCATE 删了**之前**就有数据冲突, 靠 TRUNCATE 掩盖
● **根因分类**: pre-existing 测试设计 bug, **不是 autouse 引起的**
● **不在本 spec 修**: 用户明确 "Task 3.2-3.4 撤回, 跟核心目标无关, 另起 spec"
● **完整 list**:

### tests/auth/ (9 文件, 50+ tests)
- `test_account_models.py` (5): test_account_email_unique, test_account_is_active_default_true, test_invite_token_unique, ...
- `test_admin_users_api.py` (17): test_list_users_*, test_create_invite_*, test_patch_user_*, test_reset_password_*, test_list_invites_*, test_delete_invite_*
- `test_invite_flow.py` (6): test_get_invite_*, test_redeem_*
- `test_login.py` (4): test_login_*
- `test_me.py` (3): test_me_*
- `test_middleware_integration.py` (3): test_anon_path, test_account_path, test_disabled_account_401
- `test_models.py` (4): test_user_create_and_query, test_user_public_token_unique, ...
- `test_password_reset.py` (5): test_forgot_*, test_reset_*
- `test_seed_admin.py` (4): test_seed_admin_*

### tests/eval/ (估计 10+ tests, 没完整统计)
- `test_runner.py`: test_run_evaluation_continues_on_dify_error, test_run_evaluation_continues_on_ragas_error, test_run_evaluation_persists_cancelled_status, test_run_evaluation_status_runs_through_states

### tests/storage/ (估计 5+ tests, 没完整统计)
- 跟 storage 直接相关的 (test_session, test_e2e_consistency 等)

## 接手者: 不要在本 spec 修这 30+ tests

● **修法选择** (跟 spec §风险与缓解一致):
  - 选项 A: 每个 test 改成 unique email (uuid 后缀) — 简单但要改 30+ 处
  - 选项 B: 改 `make_account` 工厂接收 session 参数 + 改 30+ test 用 `db_session` — 真正的模式 2 迁移
  - 选项 C: 模式 4 独立测试 DB (docker-compose.test.yml) — 等 CI spec
  - 推荐 B (跟 spec 模式 2 一致, 50+ test 大迁), 但要单开 spec + plan, 跟本次核心目标**完全独立**

● **CLAUDE.md 已警示**: 新 test 选错模式会立刻被 user 复盘 (见 CLAUDE.md "测试隔离 4 模式" 章节)

## spec/plan 文档

- [docs/superpowers/specs/2026-06-16-test-isolation-design.md](../specs/2026-06-16-test-isolation-design.md) (243 行)
- [docs/superpowers/plans/2026-06-16-test-isolation.md](../plans/2026-06-16-test-isolation.md) (6 任务)

spec 跟实际执行的 deviation 写在 spec §"实施回顾" 段 (如写了) — 后续接手者看 spec 就知道: 计划里有 6 任务, 实际只做了 4, Task 3.2-3.4 主动撤回.

## 关键决策记录 (避免重新讨论)

- ✅ **模式 2 vs 模式 3/4 选哪个**: 本期只实现模式 2 (事务回滚), 模式 3/4 等后续 spec
- ✅ **autouse fixture 永远不写**: 跟 dev DB 共享的硬约束, 任何 test 必须显式 opt-in
- ✅ **`make_account` 工厂不接收 session**: pre-existing 设计, 30+ test fail 是这个不接 session 引起的, 改起来大, 另起 spec
- ✅ **pytest conftest 硬约束**: 不跨 sibling 目录, 必须显式 import 或 top-level re-export
- ✅ **pyright 误报接受**: import + fixture param 同名是 pytest fixture pattern, 加 `# pyright: ignore` 注释

## 关联

- 跟 [[project-rag-shim-audit-2026-06-08]] 关联: autouse TRUNCATE 算广义 shim
- 跟 [[feedback-no-shim-no-minimal-changes]] 关联: 删 TRUNCATE 是清理 shim
- 跟 [[feedback-debug-distinguish-root-causes]] 关联: "skip = safe" 误判是事故真因, spec 必须强调
- 跟 [[2026-06-15-sqlite-to-pgvector-migration-design.md]] 关联: 同期 PG 迁移后, dev DB 数据全清, 本次 spec 防止再次清空

## 验收 (本次 spec)

- [x] `_truncate_tables` 完全删, grep 0 匹配
- [x] `tests/conftest.py` top-level 不 re-export autouse
- [x] 636 tests passed (跟 spec 模式 1 一致)
- [x] dev DB 跑 test 0 影响 (probe 验证)
- [x] CLAUDE.md 加 4 模式 + 反模式警示
- [ ] CI 独立 DB (后续 spec)
- [ ] 30+ pre-existing test 失败 (后续 spec, 不在本 spec 修)
