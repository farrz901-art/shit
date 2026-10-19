"""Evaluation + EvaluationSample models: 评估批/评估条"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..storage import Base
from ..utils.timezone import HKT


class Evaluation(Base):
    """一次评估任务 (元数据)

    - status: pending / running / completed / failed / cancelled
    - avg_metrics: {faithfulness, answer_relevancy, context_precision, context_recall}
    - (user_id, created_at DESC) 复合索引, 历史列表
    """

    __tablename__ = "evaluations"
    __table_args__ = (Index("ix_evaluations_user_created", "user_id", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    dataset_name: Mapped[str] = mapped_column(String(200), nullable=False)
    dataset_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # (2026-06-16) 新增: 走 ABC 后, dataset 存 MinIO, 这里存 URI
    # 例: 's3://rag-ingest/eval/{run_id}/dataset.csv' 或 'local://eval/{run_id}/dataset.csv'
    # 旧 record 此字段为 None, runner 走本地 fallback (F1 决策)
    dataset_uri: Mapped[str | None] = mapped_column(String(500), nullable=True)

    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    total_samples: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    successful: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    concurrency: Mapped[int] = mapped_column(Integer, nullable=False, default=5)

    # 列类型 jsonb (2026-06-26 migration), psycopg3 读直接返 dict
    avg_metrics: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    cancel_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(HKT), index=True
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    samples: Mapped[list[EvaluationSample]] = relationship(
        back_populates="evaluation",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __repr__(self) -> str:
        return f"<Evaluation id={self.id} status={self.status}>"


class EvaluationSample(Base):
    """评估批里的一条样本

    - question/answer/ground_truth/contexts 全文存, 详情页能复原
    - metrics 存 JSON dict (4 指标)
    - (evaluation_id, index) 复合索引, 按序展示
    """

    __tablename__ = "evaluation_samples"
    __table_args__ = (Index("ix_samples_eval_index", "evaluation_id", "index"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    evaluation_id: Mapped[int] = mapped_column(
        ForeignKey("evaluations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    index: Mapped[int] = mapped_column(Integer, nullable=False)

    question: Mapped[str] = mapped_column(Text, nullable=False)
    ground_truth: Mapped[str | None] = mapped_column(Text, nullable=True)
    answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 列类型 jsonb (2026-06-26 migration), psycopg3 读直接返 dict/list
    contexts: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    # (2026-06-11 Task C) 召回到的文件元数据: [{name, position, score, snippet}, ...]
    # nullable=True 让旧评估行 (没这个字段) 兼容; 新评估由 runner 写入
    sources: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB, nullable=True)
    metrics: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    evaluation: Mapped[Evaluation] = relationship(back_populates="samples")

    def __repr__(self) -> str:
        return f"<EvaluationSample id={self.id} eval={self.evaluation_id} idx={self.index}>"
