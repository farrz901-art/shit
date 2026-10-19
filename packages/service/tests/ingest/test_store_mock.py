"""ingest/store.py 模式 1 (mock) 单元测试 — 不连 PG, 纯 mock session_scope.

测试 save_task_dict / load_task_dict / list_user_task_dicts 的业务逻辑:
- save: 调用 s.merge
- load: 存在时返 dict, 不存在时返 None
- list: 返回 dict 列表, 空时返 []
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch


def _make_mock_task(task_id="t1", user_hash="h1", state="queued"):
    """构造 IngestTask 对象 (仅 Python 层, 不落库)."""
    from src.ingest.pdf_processing.models import IngestTask

    return IngestTask(
        id=task_id,
        user_hash=user_hash,
        state=state,
        total_files=1,
        processed=0,
        failed=0,
        started_at=None,
        finished_at=None,
        error=None,
        work_dir="/tmp/wd",
        input_files_json="[]",
        output_files_json="[]",
    )


class TestSaveTaskDict:
    """save_task_dict"""

    @patch("src.ingest.pdf_processing.store.session_scope")
    def test_calls_session_merge(self, mock_scope_cls):
        """save_task_dict 调用 s.merge."""
        mock_session = MagicMock()
        mock_scope_cls.return_value.__enter__.return_value = mock_session
        from src.ingest.pdf_processing.store import save_task_dict

        save_task_dict(
            {
                "id": "t1",
                "user_hash": "h1",
                "state": "queued",
                "total_files": 1,
                "processed": 0,
                "failed": 0,
                "started_at": None,
                "finished_at": None,
                "error": None,
                "work_dir": "/tmp/wd",
                "input_files": [],
                "output_files": [],
            }
        )
        mock_session.merge.assert_called_once()

    @patch("src.ingest.pdf_processing.store.session_scope")
    def test_serializes_input_files_to_json(self, mock_scope_cls):
        """save_task_dict 序列化 input_files 为 JSON 字符串."""
        mock_session = MagicMock()
        mock_scope_cls.return_value.__enter__.return_value = mock_session
        from src.ingest.pdf_processing.store import save_task_dict

        save_task_dict(
            {
                "id": "t1",
                "user_hash": "h1",
                "state": "queued",
                "total_files": 1,
                "processed": 0,
                "failed": 0,
                "started_at": None,
                "finished_at": None,
                "error": None,
                "work_dir": "/tmp/wd",
                "input_files": [{"name": "a.pdf", "uri": "s3://b/a.pdf"}],
                "output_files": [],
            }
        )
        args, _ = mock_session.merge.call_args
        task = args[0]
        assert task.input_files_json == '[{"name": "a.pdf", "uri": "s3://b/a.pdf"}]'
        assert task.output_files_json == "[]"


class TestLoadTaskDict:
    """load_task_dict"""

    @patch("src.ingest.pdf_processing.store.session_scope")
    def test_found_returns_dict(self, mock_scope_cls):
        """查到 task 时返 dict."""
        mock_session = MagicMock()
        mock_session.get.return_value = _make_mock_task()
        mock_scope_cls.return_value.__enter__.return_value = mock_session
        from src.ingest.pdf_processing.store import load_task_dict

        result = load_task_dict("t1")
        assert result is not None
        assert result["id"] == "t1"
        assert result["state"] == "queued"

    @patch("src.ingest.pdf_processing.store.session_scope")
    def test_not_found_returns_none(self, mock_scope_cls):
        """无结果时返 None."""
        mock_session = MagicMock()
        mock_session.get.return_value = None
        mock_scope_cls.return_value.__enter__.return_value = mock_session
        from src.ingest.pdf_processing.store import load_task_dict

        result = load_task_dict("t1")
        assert result is None

    @patch("src.ingest.pdf_processing.store.session_scope")
    def test_dict_has_input_output_uris(self, mock_scope_cls):
        """返回的 dict 包含 input_files / output_files 字段, uri 补空."""
        mock_session = MagicMock()
        task = _make_mock_task(task_id="t1")
        task.input_files_json = '[{"name": "a.pdf"}]'
        task.output_files_json = '[{"name": "b.pdf"}]'
        mock_session.get.return_value = task
        mock_scope_cls.return_value.__enter__.return_value = mock_session
        from src.ingest.pdf_processing.store import load_task_dict

        result = load_task_dict("t1")
        assert result is not None
        assert result["input_files"] == [{"name": "a.pdf", "uri": ""}]
        assert result["output_files"] == [{"name": "b.pdf", "uri": ""}]


class TestListUserTaskDicts:
    """list_user_task_dicts"""

    @patch("src.ingest.pdf_processing.store.session_scope")
    def test_returns_list_of_dicts(self, mock_scope_cls):
        """返回 dict 列表."""
        mock_session = MagicMock()
        mock_scope_cls.return_value.__enter__.return_value = mock_session

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [
            _make_mock_task(task_id="t2", user_hash="h1", state="completed"),
            _make_mock_task(task_id="t1", user_hash="h1", state="running"),
        ]
        mock_session.execute.return_value = mock_result

        from src.ingest.pdf_processing.store import list_user_task_dicts

        result = list_user_task_dicts("h1")
        assert len(result) == 2
        assert result[0]["id"] == "t2"
        assert result[0]["state"] == "completed"
        assert result[1]["id"] == "t1"

    @patch("src.ingest.pdf_processing.store.session_scope")
    def test_empty_returns_empty_list(self, mock_scope_cls):
        """无结果时返空列表."""
        mock_session = MagicMock()
        mock_scope_cls.return_value.__enter__.return_value = mock_session

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        from src.ingest.pdf_processing.store import list_user_task_dicts

        result = list_user_task_dicts("nonexistent")
        assert result == []
