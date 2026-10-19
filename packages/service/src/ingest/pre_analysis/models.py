"""pre_analysis_tasks ORM model (2026-07-02 新建表).

跟 src.ingest.models.IngestTask 解耦, admin 列表清晰, 不混产.
字段顺序 + 类型跟 migration 1:1 对齐 (用户决策 2026-07-02).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ...storage import Base


class PreAnalysisTask(Base):
    """pre_analysis task 元数据.

    字段语义:
    - id: 业务 UUID 字符串 (跟 IngestTask 一致 String(36))
    - user_hash: 用户标识 (从 token 派生, 跟 IngestTask.user_hash 一致)
    - state: pending / running / completed / failed
    - pdf_filename: 原 PDF 文件名 (admin UI 显示)
    - pdf_uri: ObjectStore URI (s3://rag-ingest/pre_analysis_inputs/{id}/input/{file})
    - started_at / finished_at: 时间戳
    - error: 失败时 stderr tail (NULL = 未失败)
    - output_files_json: JSON 字符串数组, 4 类产物清单 [{kind, filename, size_bytes, uri}, ...]
    - summary_json: JSON 字符串, 跑完后的统计 {total_chapters, total_tables, total_flagged_paragraphs, elapsed_ms, cross_page_candidates}
    - task_config_json: 执行快照, runner 跑完统一写 1 次 (2026-07-06); upload 时不写
    """

    __tablename__ = "pre_analysis_tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    state: Mapped[str] = mapped_column(String(20), nullable=False)
    pdf_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    pdf_uri: Mapped[str] = mapped_column(String(500), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    output_files_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    summary_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    # (2026-07-06) 执行快照: not persist at upload, runner 后台跑完写 1 次
    task_config_json: Mapped[str] = mapped_column(Text, nullable=False, server_default="{}", default="{}")
    # (2026-07-03) 当前 overall stage (parse_pdf / extract / write_outputs / done), 冗余便于列表 API quick 拿
    current_stage: Mapped[str | None] = mapped_column(String(32), nullable=True)

    __table_args__ = (Index("ix_pre_analysis_tasks_user_started", "user_hash", "started_at"),)

    def __repr__(self) -> str:
        return f"<PreAnalysisTask id={self.id} state={self.state} filename={self.pdf_filename}>"
