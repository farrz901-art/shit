"""pre_analysis_tasks ORM 操作 facade (2026-07-02 新建)

跟 src/ingest/store.py IngestTask 模式对齐:
- save_task / load_task / list_user_tasks 三个核心函数
- runner 调 mark_running / mark_completed / mark_failed 三个状态切换
- output_files_json / summary_json 是 JSON 字符串 (Text 列, 不是 JSONB)
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy import select

from ...storage import session_scope
from .models import PreAnalysisTask
from .stage_models import PreAnalysisStage


def _to_dict(task: PreAnalysisTask, include_output_files: bool = True) -> dict:
    """ORM 对象 → API dict (跟 src/ingest/store.py 模式一致).

    Args:
        task: ORM 对象.
        include_output_files: (2026-07-07) 列表接口传 False, 详情接口传 True.
    """
    result: dict = {
        "id": task.id,
        "user_hash": task.user_hash,
        "state": task.state,
        "pdf_filename": task.pdf_filename,
        "pdf_uri": task.pdf_uri,
        "started_at": task.started_at.isoformat() if task.started_at else None,
        "finished_at": task.finished_at.isoformat() if task.finished_at else None,
        "error": task.error,
        "current_stage": task.current_stage,  # (2026-07-03) 新增
        "summary": json.loads(task.summary_json or "{}"),
        "task_config_json": json.loads(task.task_config_json or "{}"),  # (2026-07-06) 执行快照
    }
    if include_output_files:
        result["output_files"] = json.loads(task.output_files_json or "[]")
    return result


def save_task(d: dict, task_config: dict | None = None) -> None:
    """创建 task 行 (state=pending).

    Args:
        d: 任务基础字段字典.
        task_config: (2026-07-06) 执行快照 {table_backend, table_params}, upload 时写入.
    """
    task = PreAnalysisTask(
        id=d["id"],
        user_hash=d["user_hash"],
        state=d.get("state", "pending"),
        pdf_filename=d["pdf_filename"],
        pdf_uri=d["pdf_uri"],
        started_at=d["started_at"],
        finished_at=None,
        error=None,
        output_files_json=json.dumps(d.get("output_files", []), ensure_ascii=False),
        summary_json=json.dumps(d.get("summary", {}), ensure_ascii=False),
        task_config_json=json.dumps(task_config or {}, ensure_ascii=False),
    )
    with session_scope() as s:
        s.merge(task)


def load_task(task_id: str) -> dict | None:
    """查单条 task (含 output_files)."""
    with session_scope() as s:
        task = s.get(PreAnalysisTask, task_id)
        return _to_dict(task, include_output_files=True) if task else None


def list_user_tasks(user_hash: str, limit: int = 50, offset: int = 0) -> list[dict]:
    """列某用户 task, 按 started_at DESC (不含 output_files)."""
    with session_scope() as s:
        rows = (
            s.execute(
                select(PreAnalysisTask)
                .where(PreAnalysisTask.user_hash == user_hash)
                .order_by(PreAnalysisTask.started_at.desc())
                .limit(limit)
                .offset(offset)
            )
            .scalars()
            .all()
        )
        return [_to_dict(t, include_output_files=False) for t in rows]


class PreAnalysisTaskStore:
    """Runner 用的状态切换 facade (mark_running / mark_completed / mark_failed).

    设计: 独立类而不是函数, 因为 PreAnalysisRunner 接 Protocol (mode 1 mock).
    """

    def mark_running(self, task_id: str) -> None:
        with session_scope() as s:
            task = s.get(PreAnalysisTask, task_id)
            if task is not None:
                task.state = "running"

    def mark_completed(
        self,
        task_id: str,
        output_files: list[dict],
        summary: dict,
        task_config: dict | None = None,  # (2026-07-06) 执行快照, runner 跑完统一写
    ) -> None:
        with session_scope() as s:
            task = s.get(PreAnalysisTask, task_id)
            if task is not None:
                task.state = "completed"
                task.finished_at = datetime.now(UTC)
                task.output_files_json = json.dumps(output_files, ensure_ascii=False)
                task.summary_json = json.dumps(summary, ensure_ascii=False)
                task.task_config_json = json.dumps(task_config or {}, ensure_ascii=False)

    def mark_failed(
        self,
        task_id: str,
        error: str,
        # (2026-07-07) 失败时也要写 partial summary, 让前端能展示已成功阶段的计数.
        # 默认 None → 旧行为不写; runner 传 self.stage_store.list_stages 拿到已完成 stage message.
        stages_provider: Callable[[str], list[PreAnalysisStage]] | None = None,
    ) -> None:
        partial_summary: dict = {}
        if stages_provider is not None:
            try:
                completed_stages = stages_provider(task_id)
                partial_summary = _build_partial_summary(completed_stages)
            except Exception:  # noqa: BLE001 — summary 写入失败不能阻塞 mark_failed 主流程
                partial_summary = {}
        with session_scope() as s:
            task = s.get(PreAnalysisTask, task_id)
            if task is not None:
                task.state = "failed"
                task.finished_at = datetime.now(UTC)
                task.error = error[-1000:]  # stderr tail, 1KB 限制 (跟 IngestTask 模式一致)
                if partial_summary:
                    task.summary_json = json.dumps(partial_summary, ensure_ascii=False)


# (2026-07-07) 从已完成 stage 抽计数, 写 partial summary 让前端表格列不显示 undefined.
# stage message 格式约定 (跟 runner.py 写盘保持一致):
#   extract_chapters: "{N} 章"
#   extract_tables:   "{N} 表 / {M} 跨页候选"
#   extract_flagged:  "{N} 段落"
_STAGE_COUNT_PATTERN = re.compile(r"^(?P<count>\d+)")
_STAGE_CROSS_PAGE_PATTERN = re.compile(r"(?P<count>\d+)\s*跨页候选")
_SUMMARY_FIELDS = ("total_chapters", "total_tables", "total_flagged_paragraphs", "cross_page_candidates")


def _build_partial_summary(stages: list[PreAnalysisStage]) -> dict:
    """从已完成 stage 抽 (章节数 / 表格数 / 标记段落数 / 跨页候选数), 缺则 0.

    Args:
        stages: PreAnalysisStage 列表 (通常来自 stage_store.list_stages).

    Returns:
        4 字段 dict, 跟 mark_completed 写的 summary schema 一致 (缺 elapsed_ms).
    """
    summary: dict = {field: 0 for field in _SUMMARY_FIELDS}
    for stage in stages:
        if stage.status != "completed" or not stage.message:
            continue
        if stage.stage == "extract_chapters":
            match = _STAGE_COUNT_PATTERN.match(stage.message)
            if match:
                summary["total_chapters"] = int(match.group("count"))
        elif stage.stage == "extract_tables":
            match = _STAGE_COUNT_PATTERN.match(stage.message)
            if match:
                summary["total_tables"] = int(match.group("count"))
            cross_match = _STAGE_CROSS_PAGE_PATTERN.search(stage.message)
            if cross_match:
                summary["cross_page_candidates"] = int(cross_match.group("count"))
        elif stage.stage == "extract_flagged":
            match = _STAGE_COUNT_PATTERN.match(stage.message)
            if match:
                summary["total_flagged_paragraphs"] = int(match.group("count"))
    return summary


__all__ = ["save_task", "load_task", "list_user_tasks", "PreAnalysisTaskStore"]
