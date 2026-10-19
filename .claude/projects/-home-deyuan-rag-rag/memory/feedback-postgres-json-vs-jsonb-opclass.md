---
name: feedback-postgres-json-vs-jsonb-opclass
description: "sa.JSON() 在 PG 生成 json 类型, 跟 jsonb_path_ops GIN index 不兼容; 必须用 sa.dialects.postgresql.JSONB()"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: b7519910-797a-4626-b12b-7081b672f030
---

# PostgreSQL JSON vs JSONB + GIN opclass

**症状**: alembic migration `sa.Column("profile_data", sa.JSON())` 后接 `op.create_index(..., postgresql_using="gin", postgresql_ops={"profile_data": "jsonb_path_ops"})`, 跑 `alembic upgrade head` 报:

```
psycopg.errors.DatatypeMismatch: operator class "jsonb_path_ops" does not accept data type json
SQL: CREATE INDEX ... USING gin (profile_data jsonb_path_ops)
```

**根因**: `sa.JSON()` 是 sqlalchemy 的通用 JSON 类型, 跨 dialect 都生成 PG 的 `json` 类型 (text-based, 保留原始格式). `jsonb_path_ops` opclass 是 PG 专门为 `jsonb` (binary, 可索引) 实现的 GIN opclass, **只能作用于 `jsonb` 列**. 类型不匹配.

**修法**: `from sqlalchemy.dialects.postgresql import JSONB` + `sa.Column("...", JSONB())`. 业务代码 (raw SQL `::jsonb` cast / ORM `JSONB` 字段) 也要一致用 JSONB.

**教训 (2026-06-23 buyer_profile 实战)**:
1. 任何加 GIN index on JSON 列的 migration, **先确认列类型是 JSONB 不是 JSON**.
2. 业务代码注释写 "JSONB" 但 migration 写成 `sa.JSON()` → 跑 alembic 才暴露, 不是 pyright 能查出来的 (类型层面都接受 dict).
3. **防回归**: 写 AST-parse 的 migration test, 断言所有需要 opclass 的列都用 `JSONB()` 而不是 `sa.JSON()` (模式 1, 0 PG 依赖). 参考 `tests/buyer_profile/test_migration.py::test_jsonb_columns_use_jsonb_not_sa_json`.
4. 自查 grep: `rg "sa\.JSON\(\)" packages/service/src/storage/migrations` 应该只命中纯 JSON 用途的列, 不应命中被 GIN/jsonb_path_ops 引用的列.

**Why**: 这种 bug 不会在单元测试暴露 (mock 跑不到 PG DDL), 只在 `alembic upgrade head` 真跑 PG 才炸, dev DB 漂移 + 测试不规范的项目会一直带着 broken migration.

**How to apply**:
- 写新 migration 加 JSONB 列 + GIN index 时, 直接用 `from sqlalchemy.dialects.postgresql import JSONB`.
- 看到 `sa.JSON()` + GIN `jsonb_path_ops` 混用, 立刻改.
- 改完跑 `alembic upgrade head` 真验证, 别只看代码.