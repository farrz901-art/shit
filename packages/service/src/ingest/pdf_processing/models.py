"""ingest 子包 ORM model (2026-06-15).

替原 src/ingest/store.py 里的 sqlite3 raw table. 字段跟旧 schema 1:1 对齐,
保证 save_task_dict / load_task_dict 行为不变.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ...storage import Base


class IngestTask(Base):
    """ingest task 元数据.

    字段顺序 + 类型跟原 data/ingest_tasks.db schema 一致:
    - id: 业务 UUID 字符串 (不是 DB 自增)
    - user_hash: 用户标识 (cookie hash)
    - state: pending / running / completed / failed
    - total_files / processed / failed: 进度计数
    - started_at / finished_at: 时间戳
    - input_files_json / output_files_json: 列表的 JSON 字符串 (跟原 SQLite 一致, 不用 JSONB)

    (2026-06-16) work_dir 语义变: 不再是本地 Path, 改 URI 字符串
    例: 's3://rag-ingest/inputs/20260616-.../' 或 'local://inputs/20260616-.../'
    注意: work_dir 是 input prefix, output prefix 由常量推: 's3://rag-ingest/outputs/{task_id}/'
    """

    __tablename__ = "ingest_tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    state: Mapped[str] = mapped_column(String(20), nullable=False)
    total_files: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    processed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    work_dir: Mapped[str | None] = mapped_column(String(500), nullable=True)
    input_files_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    output_files_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")

    __table_args__ = (Index("ix_ingest_tasks_user_started", "user_hash", "started_at"),)

    def __repr__(self) -> str:
        return f"<IngestTask id={self.id} state={self.state} {self.processed}/{self.total_files}>"
