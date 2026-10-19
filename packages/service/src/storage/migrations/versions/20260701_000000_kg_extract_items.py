"""kg_extract_items: 临时存储抽取结果 (2026-07-01 v3)

字段设计:
- payload JSONB: 原始抽取结果 (entity: {text, label, span, confidence}
                  / relation: {head, rel_type, tail, rule_type, confidence})
- corrected_payload JSONB: 用户在 preview 页编辑后版本 (NULL = 未改)
- confirmed_at TIMESTAMPTZ: 用户校对时间 (NULL = 未校对)
- dataset: 写哪个 Neo4j dataset label (env 白名单 KG_ALLOWED_DATASETS)
- 7d cron 自动清理: DELETE WHERE created_at < NOW() - INTERVAL '7 days'

索引设计:
- (task_id, dataset): 主查询 (preview / commit / export 都走此 WHERE)
- (dataset, created_at DESC): 列表查询
- (dataset, confirmed_at) WHERE confirmed_at IS NOT NULL: 部分索引, 校对率统计

JSONB 说明:
- payload 用 JSONB 而非 JSON (CLAUDE.md §JSONB 使用规范: 新列必须 JSONB)
- psycopg3 v3 注册了 jsonb loader, 读 JSONB 列自动返 dict

v3 关键: 加 dataset 字段 (Pydantic schema 跟原 spec v1 一致, dataset 校验走 KG_ALLOWED_DATASETS 白名单)
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "20260701_000000"
down_revision = "20260629_000000"  # lc_pgvector_schema (上一条迁移)
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "kg_extract_items",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("task_id", sa.Text, nullable=False),
        sa.Column("dataset", sa.Text, nullable=False),  # 2026-07-01 v3: 写哪个 dataset
        sa.Column("extractor", sa.Text, nullable=False),
        sa.Column("splitter", sa.Text, nullable=False),
        sa.Column("kind", sa.Text, nullable=False),
        sa.Column("payload", JSONB, nullable=False),
        sa.Column("selected", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("chunk_id", sa.Text),
        sa.Column("corrected_payload", JSONB),
        sa.Column("confirmed_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.CheckConstraint("kind IN ('entity', 'relation')", name="ck_kg_extract_items_kind"),
        sa.CheckConstraint(
            "dataset ~ '^[A-Za-z_][A-Za-z0-9_]*$'",
            name="ck_kg_extract_items_dataset_format",
        ),
    )
    op.create_index("ix_kg_extract_items_task_dataset", "kg_extract_items", ["task_id", "dataset"])
    op.create_index(
        "ix_kg_extract_items_dataset_created",
        "kg_extract_items",
        ["dataset", sa.text("created_at DESC")],
    )
    op.create_index(
        "ix_kg_extract_items_dataset_confirmed",
        "kg_extract_items",
        ["dataset", "confirmed_at"],
        postgresql_where=sa.text("confirmed_at IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_kg_extract_items_dataset_confirmed", table_name="kg_extract_items")
    op.drop_index("ix_kg_extract_items_dataset_created", table_name="kg_extract_items")
    op.drop_index("ix_kg_extract_items_task_dataset", table_name="kg_extract_items")
    op.drop_table("kg_extract_items")
