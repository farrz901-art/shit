---
name: feedback-alembic-bulk-insert-psycopg3-needs-datetime-not-func-now
description: "alembic op.bulk_insert 传 sa.func.now() 在 psycopg3 + SQLAlchemy 2.0 executemany 路径下 broken, 改 datetime.utcnow() 或用列上 server_default"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: f0fa30f9-9387-49ab-ae40-4882cc1720ae
---

`alembic.op.bulk_insert(table, rows)` 里的 `rows[*]['created_at']` 用 `sa.func.now()` 传值, 在 **psycopg3 + SQLAlchemy 2.0** 的 `executemany` 路径下会报:

```
sqlalchemy.exc.ProgrammingError: (psycopg.ProgrammingError) cannot adapt type 'now' using placeholder '%s' (format: AUTO)
```

**Why:** SQLAlchemy 1.4 + psycopg2 时代 `sa.func.now()` 在 bulk_insert 里能渲染成 SQL `NOW()`, 但 2.0 + psycopg3 走 `executemany` 把 rows 当 bind param 传, `sa.func` 对象无法被 psycopg adapt. 2026-06-18 真实事故: 跑 20260617_000000_add_roles_and_rbac migration 撞这个错, 卡 3 次重试才定位 (还因为缩进不同 replace_all 没一次到位).

**How to apply:**

**方案 A (最小改动, 跟原 migration 兼容)**: 改 `sa.func.now()` 为 `datetime.utcnow()`, 加 `from datetime import datetime` import.
```python
{
    "created_at": datetime.utcnow(),  # 不是 sa.func.now()
    "updated_at": datetime.utcnow(),
}
```

**方案 B (更干净, 推荐给新 migration)**: 列定义加 `server_default=sa.func.now()`, bulk_insert 不传时间戳列, DB 端自动填.
```python
sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
# bulk_insert rows 里不传这 2 列
```

**方案 C (纯 SQL 路径, 适合含特殊值的 seed)**: 用 `op.execute("INSERT INTO ... VALUES (..., NOW(), NOW())")` 跳过 SA 的 bulk_insert. 注意 Windows console 写中文会 GBK 乱码, 用文件 I/O 写 SQL.

**避坑**:
- `replace_all` 是字面替换, 缩进不同的相同代码块要分别替换 (我栽过一次: 16 缩进替换了, 20 缩进还在, 多花一次重试)
- `uv run` 不带 `--no-sync` 会触发 dep sync, 拉不到 spaCy 模型 (en-core-web-sm) 时 exit 1, 用 `uv run --no-sync alembic ...` (README 188 行)
- alembic 跑失败自动事务回滚, 但**不**自动清掉 `alembic_version`, 已成功的 stamp 还在

**跟 [[feedback-alembic-stamp-skip-existing-schema-on-dev-db-drift]] 配套**: 那个是 dev DB 漂移诊断, 这个是 migration 写 bug 修复. 同一次 dev DB 漂移事故里两个错都撞了, 顺序是先 DuplicateTable (走 stamp) → 再 DuplicateColumn (走 stamp) → 再 bulk_insert now broken (走 datetime.utcnow).
