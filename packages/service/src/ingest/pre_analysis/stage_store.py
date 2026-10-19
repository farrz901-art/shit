# packages/service/src/ingest/pre_analysis_stage_store.py
"""pre_analysis_task_stages 状态切换 + 查询 facade (2026-07-03)

跟 src/ingest/pre_analysis_store.py PreAnalysisTaskStore 模式对齐:
- mark_stage_started / mark_stage_completed / mark_stage_failed 三个状态切换
- list_stages / delete_stages_for_retry 两个查询

设计: 独立类而不是函数, 跟 PreAnalysisRunner 接 Protocol 注入 (mode 1 mock)。
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select

from ...storage import session_scope
from .models import PreAnalysisTask
from .stage_models import PreAnalysisStage


class PreAnalysisStageStore:
    """Stage 状态切换 facade."""

    def mark_stage_started(self, task_id: str, stage: str) -> None:
        """新增 1 行 stage (status=started, progress=0). 同时更新 task.current_stage."""
        with session_scope() as s:
            s.add(
                PreAnalysisStage(
                    task_id=task_id,
                    stage=stage,
                    status="started",
                    started_at=datetime.now(UTC),
                    progress=0,
                )
            )
            task = s.get(PreAnalysisTask, task_id)
            if task is not None:
                task.current_stage = stage  # (2026-07-03) 直写 detail stage 名, 跟弹框 5 阶段一致

    def mark_stage_completed(self, task_id: str, stage: str, progress: int = 100, message: str | None = None) -> None:
        """UPDATE 最新 row: status=completed, finished_at=NOW, progress=100, message=message."""
        with session_scope() as s:
            row = s.execute(
                select(PreAnalysisStage)
                .where(PreAnalysisStage.task_id == task_id, PreAnalysisStage.stage == stage)
                .order_by(PreAnalysisStage.started_at.desc())
                .limit(1)
            ).scalar_one_or_none()
            if row is not None:
                row.status = "completed"
                row.finished_at = datetime.now(UTC)
                row.progress = progress
                row.message = message

    def mark_stage_failed(self, task_id: str, stage: str, error: str) -> None:
        """UPDATE 最新 row: status=failed, message=error[-1000:] (stderr tail)."""
        with session_scope() as s:
            row = s.execute(
                select(PreAnalysisStage)
                .where(PreAnalysisStage.task_id == task_id, PreAnalysisStage.stage == stage)
                .order_by(PreAnalysisStage.started_at.desc())
                .limit(1)
            ).scalar_one_or_none()
            if row is not None:
                row.status = "failed"
                row.finished_at = datetime.now(UTC)
                row.message = error[-1000:]

    def list_stages(self, task_id: str) -> list[PreAnalysisStage]:
        """按 started_at ASC 返所有 stages."""
        with session_scope() as s:
            return list(
                s.execute(
                    select(PreAnalysisStage)
                    .where(PreAnalysisStage.task_id == task_id)
                    .order_by(PreAnalysisStage.started_at.asc())
                ).scalars()
            )

    def delete_stages_for_retry(self, task_id: str) -> None:
        """retry 时清空 task 所有 stages."""
        with session_scope() as s:
            s.query(PreAnalysisStage).filter_by(task_id=task_id).delete()


__all__ = ["PreAnalysisStageStore"]
