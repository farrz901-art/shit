"""pre_analysis_task_stages ORM (2026-07-03 新增)

记录 PDF 预分析 task 每个 detail stage 的生命周期 (started/completed/failed/skipped)。
一对多: 1 个 task → N 个 stage (按时间顺序)。

stage 枚举:
- prepare_input: 打开 PDF + 加载 rule_keywords.yaml + 拼 output_prefix
- extract_chapters: TOC 提取
- extract_tables: 表格提取 + 跨页检测
- extract_flagged: 关键词段落标记
- write_outputs: 写产物 (聚合 4 个 _write_xxx)

overall stage (current_stage 列冗余在 pre_analysis_tasks, 4 选 1):
- parse_pdf / extract / write_outputs / done
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, SmallInteger, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ...storage import Base


class PreAnalysisStage(Base):
    __tablename__ = "pre_analysis_task_stages"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    task_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("pre_analysis_tasks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    stage: Mapped[str] = mapped_column(String(32), nullable=False)  # 5 个 detail stage 字符串
    status: Mapped[str] = mapped_column(String(16), nullable=False)  # started/completed/failed/skipped
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    progress: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (Index("ix_task_stages_task_started", "task_id", "started_at"),)

    def __repr__(self) -> str:
        return f"<PreAnalysisStage id={self.id} task={self.task_id} stage={self.stage} status={self.status}>"
