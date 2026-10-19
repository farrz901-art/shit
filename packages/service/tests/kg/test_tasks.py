"""kg/tasks.py 单元测试"""

import re

import pytest

from src.kg.exceptions import TaskNotFoundError
from src.kg.tasks import TaskStatus, TaskStore


class TestTaskStatus:
    def test_defaults(self):
        t = TaskStatus(task_id="t1", kind="batch", state="queued", payload={})
        assert t.success == 0
        assert t.failed == 0
        assert t.errors == []


class TestTaskStore:
    def test_submit_returns_id(self):
        store = TaskStore()
        tid = store.submit("batch", {"dataset_id": "ds1"})
        # 新格式: {prefix}_{14位时间戳}_{6hex}; kind 非 kg_batch 走 kge_ 前缀
        assert re.match(r"^kge_\d{14}_[0-9a-f]{6}$", tid), f"格式不符: {tid}"

    def test_get_returns_task(self):
        store = TaskStore()
        tid = store.submit("batch", {})
        task = store.get(tid)
        assert task.state == "queued"

    def test_get_raises_for_missing(self):
        store = TaskStore()
        with pytest.raises(TaskNotFoundError):
            store.get("nonexistent")

    def test_mark_running(self):
        store = TaskStore()
        tid = store.submit("batch", {})
        store.mark_running(tid)
        assert store.get(tid).state == "running"

    def test_mark_done_partial(self):
        store = TaskStore()
        tid = store.submit("batch", {})
        store.mark_done(tid, success=5, failed=1)
        assert store.get(tid).state == "partial"

    def test_mark_failed(self):
        store = TaskStore()
        tid = store.submit("batch", {})
        store.mark_failed(tid, "error msg")
        assert store.get(tid).state == "failed"

    def test_mark_cancelled(self):
        store = TaskStore()
        tid = store.submit("batch", {})
        store.mark_cancelled(tid)
        assert store.get(tid).state == "cancelled"

    def test_list_recent(self):
        store = TaskStore()
        store.submit("batch", {})
        store.submit("batch", {})
        recent = store.list_recent()
        assert len(recent) == 2

    def test_list_recent_limited(self):
        store = TaskStore()
        for _ in range(10):
            store.submit("batch", {})
        recent = store.list_recent(limit=3)
        assert len(recent) == 3

    def test_require_raises_for_missing(self):
        store = TaskStore()
        with pytest.raises(TaskNotFoundError):
            store._require("missing")
