"""kg.tasks 红测试

TaskStore (in-memory) 管理后台任务状态:
  queued → running → {done, partial, failed, cancelled}
"""

import time

import pytest

from src.kg.exceptions import TaskNotFoundError
from src.kg.tasks import TaskStore


class TestSubmit:
    def test_submit_returns_task_id(self):
        store = TaskStore()
        tid = store.submit("kg_triples", {"rows": []})
        assert isinstance(tid, str) and len(tid) > 0

    def test_submit_starts_as_queued(self):
        store = TaskStore()
        tid = store.submit("kg_triples", {})
        status = store.get(tid)
        assert status.state == "queued"
        assert status.kind == "kg_triples"

    def test_submit_prefix_by_kind(self):
        """kg_extract → kge_ 前缀; kg_batch → kgb_ 前缀"""
        store = TaskStore()
        extract_id = store.submit("kg_extract", {})
        batch_id = store.submit("kg_batch", {})
        assert extract_id.startswith("kge_"), f"应 kge_ 前缀: {extract_id}"
        assert batch_id.startswith("kgb_"), f"应 kgb_ 前缀: {batch_id}"


class TestStateTransitions:
    def test_mark_running(self):
        store = TaskStore()
        tid = store.submit("kg_batch", {})
        store.mark_running(tid)
        assert store.get(tid).state == "running"

    def test_mark_done(self):
        store = TaskStore()
        tid = store.submit("kg_batch", {})
        store.mark_running(tid)
        store.mark_done(tid, success=10, failed=0)
        status = store.get(tid)
        assert status.state == "done"
        assert status.success == 10
        assert status.finished_at is not None

    def test_mark_partial(self):
        store = TaskStore()
        tid = store.submit("kg_batch", {})
        store.mark_running(tid)
        store.mark_partial(tid, success=8, failed=2, errors=["x"])
        status = store.get(tid)
        assert status.state == "partial"
        assert status.failed == 2
        assert status.errors == ["x"]

    def test_mark_failed(self):
        store = TaskStore()
        tid = store.submit("kg_batch", {})
        store.mark_running(tid)
        store.mark_failed(tid, error="boom")
        assert store.get(tid).state == "failed"
        assert store.get(tid).errors == ["boom"]

    def test_mark_cancelled(self):
        store = TaskStore()
        tid = store.submit("kg_batch", {})
        store.mark_cancelled(tid)
        assert store.get(tid).state == "cancelled"


class TestGet:
    def test_get_unknown_raises(self):
        store = TaskStore()
        with pytest.raises(TaskNotFoundError):
            store.get("nope")

    def test_list_recent(self):
        store = TaskStore()
        a = store.submit("kg_triples", {})
        time.sleep(0.01)
        b = store.submit("kg_batch", {})
        recent = store.list_recent(limit=10)
        assert len(recent) == 2
        # 最新的在前面
        assert recent[0].task_id == b
        assert recent[1].task_id == a
