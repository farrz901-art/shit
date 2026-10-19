"""pre_analysis_tasks: 加 task_config_json 列 (执行快照, 2026-07-06).

设计决策: 不在 upload 时持久化 config, runner 跑完统一写 1 次.
列名 task_config_json (不是 table_extraction_config_json) 留通用性, 未来其他模块也能复用.
nullable=False + server_default='{}' → existing rows 0 迁移风险.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260706_000000"
down_revision = "20260703_000000"  # pre_analysis_task_stages (上一条迁移)
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "pre_analysis_tasks",
        sa.Column(
            "task_config_json",
            sa.Text,
            nullable=False,
            server_default="{}",
        ),
    )


def downgrade() -> None:
    op.drop_column("pre_analysis_tasks", "task_config_json")
