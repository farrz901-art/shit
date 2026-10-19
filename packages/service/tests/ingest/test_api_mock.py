"""ingest/api.py 纯函数测试 (mode 1, 不测路由 auth)"""

from pathlib import Path

from src.ingest.pdf_processing.router import InputFile, OutputFile, _dict_to_task, _new_task_id


def test_dict_to_task_full():
    d = {
        "id": "t1",
        "user_hash": "h1",
        "state": "queued",
        "total_files": 1,
        "processed": 0,
        "failed": 0,
        "started_at": "2026-06-01T00:00:00",
        "finished_at": "2026-06-01T01:00:00",
        "error": None,
        "work_dir": "/tmp/wd",
        "input_files": [{"name": "f.pdf", "size": 100, "mime": "application/pdf", "uri": ""}],
        "output_files": [{"name": "f.md", "size": 50, "mime": "text/markdown", "uri": ""}],
    }
    task = _dict_to_task(d)
    assert task.id == "t1"
    assert task.state == "queued"
    assert task.work_dir == Path("/tmp/wd")
    assert len(task.input_files) == 1


def test_dict_to_task_minimal():
    d = {
        "id": "t1",
        "user_hash": "h1",
        "state": "queued",
        "total_files": 0,
        "processed": 0,
        "failed": 0,
        "started_at": "2026-06-01T00:00:00",
        "finished_at": None,
        "error": None,
        "work_dir": None,
        "input_files": [],
        "output_files": [],
    }
    task = _dict_to_task(d)
    assert task.finished_at is None
    assert task.work_dir is None
    assert task.input_files == []


def test_new_task_id_unique():
    ids = {_new_task_id() for _ in range(100)}
    assert len(ids) == 100


class TestInputFile:
    def test_fields(self):
        f = InputFile(name="f.pdf", size=100, mime="application/pdf")
        assert f.name == "f.pdf"
        assert f.size == 100


class TestOutputFile:
    def test_fields(self):
        f = OutputFile(name="f.md", size=50, mime="text/markdown")
        assert f.name == "f.md"
        assert f.size == 50
