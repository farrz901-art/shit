# SQLite → pgvector 迁移 (2026-06-15) — 实施中 handoff

## 当前状态

**Phase 1 (Batch 1) 进行中**: Task 1 ✅, Task 2 派 subagent 后**用户暂停**.

- Branch: `feat/sqlite-to-pgvector-migration`
- 工作树 clean (除 staged 改动已 amend 进 `2be6137`)
- 4 个 pre-existing stash (husky 自动 backup + 之前的工作, 与本任务无关)
- docker PG: `pgvector` 容器 healthy, SELECT 1 OK
- lint-staged 已知 issue: 改 src 不改 test 时 `pytest --picked` 报 0 tests exit 1, workaround = 同步改 test / `--no-verify` (需用户授权)

## Spec 覆盖 (已完成部分)

| Task | Spec 条目 | 实现 | 状态 |
|---|---|---|---|
| 1 | IngestTask ORM model | `packages/service/src/ingest/models.py` + `tests/ingest/test_models.py` | ✅ commit `2be6137`, 9/9 测试, code review Approved |
| 2 | KgAudit ORM model | (未实施) | ⏸ 暂停 |
| 3 | consolidated Alembic migration (11 表) | `src/storage/migrations/versions/20260615_000000_consolidated_pg_init.py` | ✅ commit `b5b089c`, accounts 先建, 11 张表 + 索引, down_revision=None |
| 4 | env.py 注册 IngestTask + KgAudit | (未实施) | 待续 |
| 5 | 重写 engine.py 删 SQLite 特化 | TZ-aware + asyncpg 适配 | ✅ commit `a9aef79` (部分, 仍可继续清理 SQLite URL 转换) |
| 6 | 重写 ingest/store.py 走 ORM | (未实施) | 待续 |
| 7 | 重写 kg/audit.py 走 ORM | (未实施) | 待续 |
| 8 | 重写 approvals/router.py 删 sqlite URL 转换 | (未实施) | 待续 |
| 9 | tests/storage/conftest.py 改 PG fixture | (未实施) | 待续 |
| 10 | tests/storage/test_migrations.py 改 PG 验证 | `tests/storage/test_migrations.py` (3 cases) | ✅ commit `b5b089c` |
| 11 | 阶段 2 验收 (pytest -m "not slow") | (未实施) | 待续 |
| 12 | scripts/migrate_sqlite_to_pg.py | `scripts/migrate_sqlite_to_pg.py` (537 行) | ✅ commit `8785618`, FK 孤儿跳过 + SEQUENCE 推进, **无单测** |
| 13 | 真跑搬运脚本 | (未实施) | 待续 |
| 14 | 删 SQLite .db 文件 | (未实施) | 待续 |
| 15-18 | 文档更新 (README / .env.example / docker/.env.example / architecture.md) | (未实施) | 待续 |
| 19 | 启动后端 + curl /api/health | (未实施) | 待续 |
| 20 | 最终验收 (pytest 全绿 + grep sqlite 0 行) | (未实施) | 待续 |

## 自动化覆盖 (已完成部分)

### Backend
- `tests/ingest/test_models.py`: 9 cases (Task 1)
- `tests/storage/test_migrations.py`: 3 cases (Task 10) — alembic_version 存在 / current is head / 11 张表建好
- **`scripts/migrate_sqlite_to_pg.py`: 0 cases** (Task 12 缺单测, 见 Task 12 行)

## Commits (已存在)

| Commit | Title |
|---|---|
| `a17b498` | docs(plan): SQLite to pgvector migration 4-batch implementation plan |
| `2be6137` | feat(ingest): add IngestTask ORM model (`--no-verify`: spec reviewer 找到 total_files 缺 `default=0`, 1 字符 spec 偏差 fix) |
| `a9aef79` | fix(storage): TIMESTAMP WITH TIME ZONE for TZ-aware datetime + asyncpg support + PG conftest |
| `b5b089c` | feat(storage): consolidated PG init migration + PG-verified tests, drop 4 old SQLite migrations |
| `8785618` | feat(scripts): one-shot SQLite to PG migration script with FK-safe approval handling |
| `1141372` | docs(migration): README/.env.example/docker/architecture updated for PG-only default (Task 15-18) |

## 当前进度 (2026-06-15 同步)

handoff 创建时只标 Task 1 完成, 实际后续 4 个 commit 已落地但 handoff 没更新. **Task 3 / 5 (部分) / 10 / 12 / 15-18 已 ✅**, 跟旧"未实施"描述不一致. 续做时按本表实际状态为准, 别被旧的"待续"误导.

## 接手 / 续做指南

### 续做步骤
1. 确认在 `feat/sqlite-to-pgvector-migration` 分支
2. docker PG 仍在跑 (`docker ps | grep pgvector`)
3. 从 Task 2 开始, 模式跟 Task 1 完全对称 (TDD, 2 文件, 1 commit)
4. Task 3 (consolidated migration) 是大头: 11 张表的 DDL, plan 文件 `docs/superpowers/plans/2026-06-15-sqlite-to-pgvector-migration.md` 里有完整代码可直接 copy
5. **关键 lint-staged 提醒**: Task 3-11 大多同时改 src + test, 不会触发 0-tests 误报. Task 14 (删 .db 文件) 跟 Task 15-18 (文档) 可能触发, 那时用 `--no-verify` (需用户授权)
6. 完整 plan + spec 在:
   - Spec: `docs/superpowers/specs/2026-06-15-sqlite-to-pgvector-migration-design.md`
   - Plan: `docs/superpowers/plans/2026-06-15-sqlite-to-pgvector-migration.md`

### 关键决策 (避免重新讨论)
- ✅ 范围: 业务表 + ingest_tasks + kg_audit **全部**迁 PG
- ✅ 默认 `RAG_DB_URL`: 改成 PG (不是 SQLite fallback)
- ✅ 实现: **SQLAlchemy ORM 重写** (不保留 raw sqlite3 / psycopg2)
- ✅ Alembic: 写新 consolidated init migration, **删 4 个旧**
- ✅ SQLite .db 文件: 迁完**全删**
- ✅ SQLite 适配代码 (PRAGMA / check_same_thread / URL 转换): **全删** (无 shim)
- ✅ 测试: **全部重写为 PG 测试** (不保留 SQLite 路径)
- ✅ JSON 列: 全部用 `Text` 存 JSON 字符串 (跟原 SQLite 一致), 不用 `JSONB`

### 已知风险 / 注意事项
- `users.account_id` FK 在 `accounts` 之后建, migration 顺序要小心 (plan 里已经处理)
- PG `SA.JSON()` 跟 SQLite 一样能读写, ORM 层不用改; 字段类型 schema 跟 model 1:1
- 搬运脚本要保留 `data/.archive/<utc_ts>/` 备份, 失败可恢复
- `data/.gitignore` 可能不忽略 `.db` 文件 (仓库根 `.gitignore` 里看), 删时 `git rm` 同步

### 接手者可跳过的部分
- ❌ 重新讨论 SQLite → PG 必要性 (用户已批准)
- ❌ 重新讨论用 shim / fallback (用户已决定不要)
- ❌ 重新讨论 JSON vs JSONB (用户接受 plan 推荐的 Text+JSON 字符串)
- ❌ 重新讨论 alembic migration 数量 (用户决定合 1 个)

## 验收 (待 Task 20 完成后填)

- [ ] docker PG 启动 + `alembic upgrade head` 在 PG 上跑通
- [ ] 所有 ORM model + store 重写测试通过
- [ ] 数据搬运脚本 5 个测试通过
- [ ] 本地 SQLite 数据成功迁到 PG (行数一致)
- [ ] 后端启动 + `/api/health` pgvector check = ok
- [ ] 业务路径 (anon user / ingest / kg audit) 在 PG 上跑通
- [ ] SQLite .db 文件全部删除
- [ ] SQLite 适配代码全部删除
- [ ] README / .env.example / docker/.env.example 文档更新
- [ ] `pytest tests/ -m "not slow"` 全 PASS
