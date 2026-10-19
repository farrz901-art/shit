"""add cancel_requested_at to evaluations (2026-06-24)

CON-005: 持久化取消请求, 支持进程重启恢复。
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "20260624_150000"
down_revision: str | None = "20260624_120000"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    """加 cancel_requested_at 列 (nullable, 旧 record 留 None)"""
    op.add_column("evaluations", sa.Column("cancel_requested_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    """回滚: 删 cancel_requested_at 列"""
    op.drop_column("evaluations", "cancel_requested_at")
