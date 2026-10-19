"""pre_analysis_tasks: PDF 预分析 task 元数据 (2026-07-02 新建表)

设计决策 (跟 ingest_tasks 解耦, admin 列表清晰):
- id: 业务 UUID (跟 IngestTask 一致 String(36))
- user_hash: 从 token 派生 (跟 IngestTask.user_hash 一致 String(64))
- state: pending / running / completed / failed (跟 IngestTask 一致)
- pdf_filename: 原 PDF 文件名 (admin UI 显示, ≤ 255 字符)
- pdf_uri: ObjectStore URI (s3://rag-ingest/pre_analysis_inputs/{id}/input/{file})
- started_at / finished_at: 时间戳
- error: 失败时 stderr tail (NULL = 未失败)
- output_files_json: JSON 字符串数组 [{kind, filename, size_bytes, uri}, ...]
- summary_json: JSON 字符串 {total_chapters, total_tables, total_flagged_paragraphs, elapsed_ms, cross_page_candidates}

索引:
- (user_hash, started_at): 列表查询 (跟 IngestTask 索引模式一致)
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260702_000000"
down_revision = "20260701_000000"  # kg_extract_items (上一条迁移)
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pre_analysis_tasks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_hash", sa.String(64), nullable=False, index=True),
        sa.Column("state", sa.String(20), nullable=False),
        sa.Column("pdf_filename", sa.String(255), nullable=False),
        sa.Column("pdf_uri", sa.String(500), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("output_files_json", sa.Text, nullable=False, server_default="[]"),
        sa.Column("summary_json", sa.Text, nullable=False, server_default="{}"),
        sa.CheckConstraint(
            "state IN ('pending', 'running', 'completed', 'failed')",
            name="ck_pre_analysis_tasks_state",
        ),
    )
    op.create_index(
        "ix_pre_analysis_tasks_user_started",
        "pre_analysis_tasks",
        ["user_hash", "started_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_pre_analysis_tasks_user_started", "pre_analysis_tasks")
    op.drop_table("pre_analysis_tasks")
