"""ingest task 元数据存储 (ORM 重写, 2026-06-15).

替原 sqlite3 raw 实现. 走 SQLAlchemy ORM (src.ingest.models.IngestTask) +
session_scope() 事务. 现有 save_task_dict / load_task_dict / list_user_task_dicts /
reset_for_test 接口签名 1:1 保留, 调用方 (src/ingest/api.py) 0 改动.
"""

from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import select, text

from ...storage import session_scope
from .models import IngestTask


def _to_dt(value: str | datetime | None) -> datetime | None:
    """ISO 字符串 / datetime / None → datetime (or None)."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(value)


def _to_dict(task: IngestTask) -> dict:
    """ORM 对象 → IngestTask 构造 dict (跟原 sqlite3 _row_to_dict 字段 1:1)."""
    return {
        "id": task.id,
        "user_hash": task.user_hash,
        "state": task.state,
        "total_files": task.total_files,
        "processed": task.processed,
        "failed": task.failed,
        "started_at": task.started_at.isoformat() if task.started_at else None,
        "finished_at": task.finished_at.isoformat() if task.finished_at else None,
        "error": task.error,
        "work_dir": task.work_dir,
        "input_files": _ensure_input_uris(json.loads(task.input_files_json or "[]")),
        "output_files": _ensure_output_uris(json.loads(task.output_files_json or "[]")),
    }


def _ensure_input_uris(records: list[dict]) -> list[dict]:
    """(2026-06-16) 旧 record 无 uri 字段, 加载时给空串 (前端不依赖)."""
    for r in records:
        r.setdefault("uri", "")
    return records


def _ensure_output_uris(records: list[dict]) -> list[dict]:
    """(2026-06-16) 旧 record 无 uri 字段, 加载时给空串 (前端不依赖)."""
    for r in records:
        r.setdefault("uri", "")
    return records


def reset_for_test() -> None:
    """测试用: 清空 ingest_tasks 表."""
    with session_scope() as s:
        s.execute(text("DELETE FROM ingest_tasks"))


def save_task_dict(d: dict) -> None:
    """d 必须含 IngestTask.to_dict() 的所有字段. INSERT OR REPLACE (upsert)."""
    task = IngestTask(
        id=d["id"],
        user_hash=d["user_hash"],
        state=d["state"],
        total_files=d["total_files"],
        processed=d.get("processed", 0),
        failed=d.get("failed", 0),
        started_at=_to_dt(d["started_at"]),
        finished_at=_to_dt(d.get("finished_at")),
        error=d.get("error"),
        work_dir=d.get("work_dir"),
        input_files_json=json.dumps(d.get("input_files", []), ensure_ascii=False),
        output_files_json=json.dumps(d.get("output_files", []), ensure_ascii=False),
    )
    with session_scope() as s:
        s.merge(task)


def load_task_dict(task_id: str) -> dict | None:
    """查单条 task, 返 IngestTask 构造 dict (None = 不存在)."""
    with session_scope() as s:
        task = s.get(IngestTask, task_id)
        return _to_dict(task) if task else None


def list_user_task_dicts(user_hash: str) -> list[dict]:
    """列某用户所有 task, 按 started_at DESC (新的在前)."""
    with session_scope() as s:
        rows = (
            s.execute(
                select(IngestTask).where(IngestTask.user_hash == user_hash).order_by(IngestTask.started_at.desc())
            )
            .scalars()
            .all()
        )
        return [_to_dict(t) for t in rows]


# 向后兼容导出
__all__ = ["save_task_dict", "load_task_dict", "list_user_task_dicts", "reset_for_test"]
