"""migrate 5 sa.JSON() 历史列 → JSONB (json-jsonb spec Task B1)

背景: 2026-06-15 consolidated_pg_init.py 用 sa.JSON() 给 5 列定义 PG json 类型
(text-based, 不支持 GIN jsonb_path_ops). 这些列虽然没用 JSONB operator, 但跟
psycopg3 v3 adapter 协议交互不稳 — 同源踩坑见
docs/superpowers/handoffs/2026-06-25-postgres-json-jsonb-family-bugs.md

5 列:
  - messages.meta
  - evaluations.avg_metrics
  - evaluation_samples.contexts
  - evaluation_samples.metrics
  - evaluation_samples.sources

注意:
1. dry-run 已验证全部行可 ::jsonb cast (Task 0 Step 2).
2. ALTER 锁表分钟级, 维护窗口跑, 不要在高峰期 upgrade.
3. downgrade 走 ::json cast, 数据语义保留但格式 (空格/键序) 丢失.
"""

from __future__ import annotations

from alembic import op

revision: str = "20260626_000000"
down_revision: str | None = "20260624_170000"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    """5 列 json → jsonb (USING col::jsonb)."""
    op.execute("ALTER TABLE messages ALTER COLUMN meta TYPE jsonb USING meta::jsonb")
    op.execute("ALTER TABLE evaluations ALTER COLUMN avg_metrics TYPE jsonb USING avg_metrics::jsonb")
    op.execute("ALTER TABLE evaluation_samples ALTER COLUMN contexts TYPE jsonb USING contexts::jsonb")
    op.execute("ALTER TABLE evaluation_samples ALTER COLUMN metrics TYPE jsonb USING metrics::jsonb")
    op.execute("ALTER TABLE evaluation_samples ALTER COLUMN sources TYPE jsonb USING sources::jsonb")


def downgrade() -> None:
    """回滚: jsonb → json (USING col::json, 数据保留语义)."""
    op.execute("ALTER TABLE messages ALTER COLUMN meta TYPE json USING meta::json")
    op.execute("ALTER TABLE evaluations ALTER COLUMN avg_metrics TYPE json USING avg_metrics::json")
    op.execute("ALTER TABLE evaluation_samples ALTER COLUMN contexts TYPE json USING contexts::json")
    op.execute("ALTER TABLE evaluation_samples ALTER COLUMN metrics TYPE json USING metrics::json")
    op.execute("ALTER TABLE evaluation_samples ALTER COLUMN sources TYPE json USING sources::json")
