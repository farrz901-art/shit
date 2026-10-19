"""后台任务管理 (in-memory TaskStore)

v1: 内存 dict, 单 worker 假设; 重启 dev server 任务丢
v2: Redis / SQLite 持久化 (本期不做)
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field

from ..common.task_id import (
    TASK_PREFIX_KG_BATCH,
    TASK_PREFIX_KG_EXTRACT,
    make_task_id,
)
from .exceptions import TaskNotFoundError


@dataclass
class TaskStatus:
    task_id: str
    kind: str
    state: str
    payload: dict
    success: int = 0
    failed: int = 0
    errors: list[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    started_at: float | None = None
    finished_at: float | None = None


class TaskStore:
    """任务状态存储 (in-memory, 线程安全)"""

    def __init__(self):
        self._lock = threading.Lock()
        self._tasks: dict[str, TaskStatus] = {}

    def submit(self, kind: str, payload: dict) -> str:
        # 按 kind 选前缀: kg_batch → kgb_, 其余 (kg_extract) → kge_
        prefix = TASK_PREFIX_KG_BATCH if kind == "kg_batch" else TASK_PREFIX_KG_EXTRACT
        task_id = make_task_id(prefix)
        with self._lock:
            self._tasks[task_id] = TaskStatus(task_id=task_id, kind=kind, state="queued", payload=payload)
        return task_id

    def get(self, task_id: str) -> TaskStatus:
        with self._lock:
            if task_id not in self._tasks:
                raise TaskNotFoundError(f"任务不存在: {task_id}")
            return self._tasks[task_id]

    def mark_running(self, task_id: str) -> None:
        with self._lock:
            t = self._require(task_id)
            t.state = "running"
            t.started_at = time.time()

    def mark_done(self, task_id: str, success: int, failed: int = 0) -> None:
        with self._lock:
            t = self._require(task_id)
            t.state = "done" if failed == 0 else "partial"
            t.success = success
            t.failed = failed
            t.finished_at = time.time()

    def mark_partial(self, task_id: str, success: int, failed: int, errors: list[str]) -> None:
        with self._lock:
            t = self._require(task_id)
            t.state = "partial"
            t.success = success
            t.failed = failed
            t.errors = errors
            t.finished_at = time.time()

    def mark_failed(self, task_id: str, error: str) -> None:
        with self._lock:
            t = self._require(task_id)
            t.state = "failed"
            t.errors = [error]
            t.finished_at = time.time()

    def mark_cancelled(self, task_id: str) -> None:
        with self._lock:
            t = self._require(task_id)
            t.state = "cancelled"
            t.finished_at = time.time()

    def list_recent(self, limit: int = 50) -> list[TaskStatus]:
        with self._lock:
            items = sorted(self._tasks.values(), key=lambda t: t.created_at, reverse=True)
            return items[:limit]

    def _require(self, task_id: str) -> TaskStatus:
        if task_id not in self._tasks:
            raise TaskNotFoundError(f"任务不存在: {task_id}")
        return self._tasks[task_id]
