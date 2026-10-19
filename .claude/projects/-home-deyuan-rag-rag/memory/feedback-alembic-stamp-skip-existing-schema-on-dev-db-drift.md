---
name: feedback-alembic-stamp-skip-existing-schema-on-dev-db-drift
description: "dev DB 是 init_db() 建过 (alembic_version 空但表都在) 时, 不能裸 alembic upgrade head, 必须先 stamp 跳过已存在 revision 再 upgrade"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: f0fa30f9-9387-49ab-ae40-4882cc1720ae
---

dev DB 漂移场景：早期用 `init_db()` 走 `Base.metadata.create_all()` 把 11 张业务表都建上了, 但 `alembic_version` 表是空的 / 跟实际 schema 错位。后来加新 model 写了 migration, 此时**不能裸跑** `alembic upgrade head` —— 会撞 `DuplicateTable` / `DuplicateColumn`。

**Why:** 2026-06-18 真实事故. 用户新加 RBAC (20260617_000000) + account_settings (20260617_120000) 两个 migration 跑 `alembic upgrade head`, 第一步 `20260615_000000` consolidated init 就撞 `relation "accounts" already exists`. 必须先 `alembic stamp 20260615_000000` 告诉 alembic "这一层 schema 已存在, 别重跑", 才能继续 upgrade 后面.

**How to apply:**
1. **拉新代码 / 重置 DB 后跑 alembic 前**, 先探针 (一次性 psycopg 脚本) 列 `alembic_version` 实际值 + `pg_tables` 已有表 + 各 migration 涉及 schema 的存在性.
2. **已存在的部分用 `alembic stamp <rev>` 跳过**, 不要改 migration 加 `IF NOT EXISTS` (污染版本控制, 跟其他环境 drift).
3. **真缺的列/表走正常 upgrade**. 例: `stamp 20260615_000000` (init 表都在) + `stamp 20260616_120000` (dataset_uri 已存在) → `upgrade head` 跑剩下 4 个 migration.
4. **预防**: 项目 README 162 行有"拉新代码 / 重置 DB 后必跑 alembic upgrade head"提醒, 但 dev DB 漂移场景下这条反过来——先查再跑. 跟 [[project-rag-dev-env-recovery]] 互补 (那个是"全空"场景, 这个是"半空"场景).

**根因诊断信号**:
- `alembic current` 输出空 / 不是 head
- `pg_tables` 显示业务表已存在
- `alembic upgrade head` 第一步撞 `DuplicateTable` / `DuplicateColumn`

**禁忌**:
- ❌ `init_db()` / `Base.metadata.create_all()` 跟 alembic 混用 (README 200 行: 生产必须走 alembic, `init_db()` 仅 dev/test, 受 `RAG_AUTO_CREATE_SCHEMA=1` 开关)
- ❌ 改 migration 加 `IF NOT EXISTS` (破坏 alembic 假设, 后续环境 drift)
- ❌ 跳过 alembic 直接靠 ORM model 反推 schema (schema 跟 model 漂移时无法发现)
