"""add dataset_uri to evaluations (2026-06-16)

C 集成 (Eval CSV 走 ABC): 加 nullable 列, 旧 record 留 None (runner 走本地 fallback).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "20260616_120000"
down_revision: str | None = "20260616_000000"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    """(2026-06-16) 加 dataset_uri 列 (nullable, 旧 record 留 None)"""
    op.add_column("evaluations", sa.Column("dataset_uri", sa.String(500), nullable=True))


def downgrade() -> None:
    """回滚: 删 dataset_uri 列"""
    op.drop_column("evaluations", "dataset_uri")
