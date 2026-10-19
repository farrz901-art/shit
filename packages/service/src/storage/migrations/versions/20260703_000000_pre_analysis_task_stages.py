"""pre_analysis_task_stages 表 + pre_analysis_tasks.current_stage 列 (2026-07-03)

新表记录 task 每个 detail stage 的 lifecycle,
pre_analysis_tasks 加 current_stage 列 (冗余, 列表 API quick 拿)。
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260703_000000"
down_revision = "20260702_000000"  # pre_analysis_tasks (上一条迁移)
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pre_analysis_task_stages",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column(
            "task_id",
            sa.String(36),
            sa.ForeignKey("pre_analysis_tasks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("stage", sa.String(32), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("progress", sa.SmallInteger, nullable=False, server_default="0"),
        sa.Column("message", sa.Text, nullable=True),
        sa.CheckConstraint(
            "status IN ('started', 'completed', 'failed', 'skipped')",
            name="ck_pre_analysis_task_stages_status",
        ),
        sa.CheckConstraint(
            "stage IN ('load_config', 'extract_chapters', 'extract_tables', 'extract_flagged', 'write_outputs')",
            name="ck_pre_analysis_task_stages_stage",
        ),
    )
    op.create_index(
        "ix_task_stages_task_started",
        "pre_analysis_task_stages",
        ["task_id", "started_at"],
    )
    op.add_column(
        "pre_analysis_tasks",
        sa.Column("current_stage", sa.String(32), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("pre_analysis_tasks", "current_stage")
    op.drop_index("ix_task_stages_task_started", "pre_analysis_task_stages")
    op.drop_table("pre_analysis_task_stages")
