"""PreAnalysisTaskStore 单测 + _to_dict 字段透传 (mode 1 mock, 2026-07-06).

覆盖:
- _to_dict 必须含 task_config_json 字段
- task_config_json 默认空字符串反序列化为空 dict
- mark_completed 接 task_config 入参, 写 task_config_json 到 DB 行
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch


def test_to_dict_includes_task_config_json_when_present() -> None:
    """_to_dict 把 task_config_json 字符串反序列化为 dict (非空场景)."""
    from src.ingest.pre_analysis.models import PreAnalysisTask
    from src.ingest.pre_analysis.store import _to_dict

    task = PreAnalysisTask(
        id="pa-test-001",
        user_hash="h",
        state="completed",
        pdf_filename="x.pdf",
        pdf_uri="local://x.pdf",
        started_at=datetime.now(UTC),
        task_config_json='{"table_backend": "camelot", "table_params": {"flavor": "stream"}}',
    )
    result = _to_dict(task)
    assert result["task_config_json"] == {
        "table_backend": "camelot",
        "table_params": {"flavor": "stream"},
    }


def test_to_dict_task_config_json_default_empty() -> None:
    """task_config_json 空字符串反序列化为空 dict (默认 server_default='{}' 落库场景)."""
    from src.ingest.pre_analysis.models import PreAnalysisTask
    from src.ingest.pre_analysis.store import _to_dict

    task = PreAnalysisTask(
        id="pa-test-002",
        user_hash="h",
        state="running",
        pdf_filename="x.pdf",
        pdf_uri="local://x.pdf",
        started_at=datetime.now(UTC),
        task_config_json="",
    )
    result = _to_dict(task)
    assert result["task_config_json"] == {}


def test_mark_completed_writes_task_config_json() -> None:
    """mark_completed 接 task_config={dict}, 内部 json.dumps 写到 DB 行 task_config_json 字段."""
    fake_sess = MagicMock()
    fake_task = MagicMock()
    fake_task.state = "running"
    fake_task.finished_at = None
    fake_task.output_files_json = "[]"
    fake_task.summary_json = "{}"
    fake_task.task_config_json = "{}"
    fake_sess.get.return_value = fake_task

    captured: dict = {}

    class _FakeJsonDumps:
        @staticmethod
        def dumps(obj, **_kw):
            captured["dumped"] = obj
            return "<<serialized>>"

    with patch("src.ingest.pre_analysis.store.session_scope") as mock_scope:
        mock_scope.return_value.__enter__.return_value = fake_sess
        mock_scope.return_value.__exit__.return_value = False
        with patch("src.ingest.pre_analysis.store.json") as mock_json:
            mock_json.dumps.side_effect = _FakeJsonDumps.dumps
            from src.ingest.pre_analysis import PreAnalysisTaskStore

            store = PreAnalysisTaskStore()
            store.mark_completed(
                task_id="pa-test-003",
                output_files=[{"kind": "chapter_structure", "uri": "x", "filename": "x", "size_bytes": 1}],
                summary={
                    "total_chapters": 1,
                    "total_tables": 0,
                    "total_flagged_paragraphs": 0,
                    "elapsed_ms": 100,
                    "cross_page_candidates": 0,
                },
                task_config={"table_backend": "pymupdf", "table_params": {}},
            )

    # task_config_json 字段被赋值, 值是 dumps(task_config) 的结果
    assert fake_task.task_config_json == "<<serialized>>"
    # dumps 输入是 task_config dict
    assert captured["dumped"] == {"table_backend": "pymupdf", "table_params": {}}
    # state 转 completed
    assert fake_task.state == "completed"


def test_mark_completed_task_config_default_empty_dict() -> None:
    """mark_completed 不传 task_config → 写空 dict (等价上传未指定后端)."""
    fake_sess = MagicMock()
    fake_task = MagicMock()
    fake_task.task_config_json = "old"
    fake_sess.get.return_value = fake_task

    captured: dict = {}

    class _FakeJsonDumps:
        @staticmethod
        def dumps(obj, **_kw):
            captured["dumped"] = obj
            return "<<empty>>"

    with patch("src.ingest.pre_analysis.store.session_scope") as mock_scope:
        mock_scope.return_value.__enter__.return_value = fake_sess
        mock_scope.return_value.__exit__.return_value = False
        with patch("src.ingest.pre_analysis.store.json") as mock_json:
            mock_json.dumps.side_effect = _FakeJsonDumps.dumps
            from src.ingest.pre_analysis import PreAnalysisTaskStore

            store = PreAnalysisTaskStore()
            store.mark_completed(
                task_id="pa-test-004",
                output_files=[],
                summary={},
                # task_config 不传
            )

    assert fake_task.task_config_json == "<<empty>>"
    assert captured["dumped"] == {}


# (2026-07-07) partial summary 写入 — 修复"任务失败时 summary 字段 undefined"问题


def _make_stage(stage: str, status: str, message: str | None) -> MagicMock:
    """造一个 stage ORM mock, 只填 _build_partial_summary 关心的字段."""
    s = MagicMock()
    s.stage = stage
    s.status = status
    s.message = message
    return s


def test_mark_failed_without_stages_provider_does_not_write_summary() -> None:
    """mark_failed 不传 stages_provider (旧调用方) → summary_json 字段不被改写."""
    fake_sess = MagicMock()
    fake_task = MagicMock()
    fake_task.summary_json = "<<untouched>>"
    fake_sess.get.return_value = fake_task

    with patch("src.ingest.pre_analysis.store.session_scope") as mock_scope:
        mock_scope.return_value.__enter__.return_value = fake_sess
        mock_scope.return_value.__exit__.return_value = False
        from src.ingest.pre_analysis import PreAnalysisTaskStore

        PreAnalysisTaskStore().mark_failed("pa-test-005", "boom")

    assert fake_task.state == "failed"
    assert fake_task.error == "boom"
    # summary_json 没被覆盖 (旧行为兼容)
    assert fake_task.summary_json == "<<untouched>>"


def test_mark_failed_writes_partial_summary_from_completed_stages() -> None:
    """mark_failed 传 stages_provider → 从已完成 stage message 抽计数写 summary_json."""
    fake_sess = MagicMock()
    fake_task = MagicMock()
    fake_task.summary_json = "<<old>>"
    fake_sess.get.return_value = fake_task

    # 模拟: extract_chapters 已完成 (5 章), extract_tables 已完成 (3 表 / 1 跨页候选),
    # extract_flagged 失败 (message="error..." 不带数字)
    stages = [
        _make_stage("load_config", "completed", "open ok"),
        _make_stage("extract_chapters", "completed", "5 章"),
        _make_stage("extract_tables", "completed", "3 表 / 1 跨页候选"),
        _make_stage("extract_flagged", "failed", "value error"),
    ]
    stages_provider = MagicMock(return_value=stages)

    captured: dict = {}

    class _FakeJsonDumps:
        @staticmethod
        def dumps(obj, **_kw):
            captured["dumped"] = obj
            return "<<partial>>"

    with patch("src.ingest.pre_analysis.store.session_scope") as mock_scope:
        mock_scope.return_value.__enter__.return_value = fake_sess
        mock_scope.return_value.__exit__.return_value = False
        with patch("src.ingest.pre_analysis.store.json") as mock_json:
            mock_json.dumps.side_effect = _FakeJsonDumps.dumps
            from src.ingest.pre_analysis import PreAnalysisTaskStore

            PreAnalysisTaskStore().mark_failed(
                "pa-test-006",
                "extract_flagged failed: value error",
                stages_provider=stages_provider,
            )

    # stages_provider 拿过 task_id
    stages_provider.assert_called_once_with("pa-test-006")
    # summary_json 被覆盖为 partial summary
    assert fake_task.summary_json == "<<partial>>"
    # dumps 的 dict 含 4 字段
    assert captured["dumped"] == {
        "total_chapters": 5,
        "total_tables": 3,
        "total_flagged_paragraphs": 0,  # 失败 stage 不抽
        "cross_page_candidates": 1,
    }


def test_mark_failed_stages_provider_exception_falls_back_to_no_summary() -> None:
    """stages_provider 抛异常 → 不写 summary_json, 也不阻塞 mark_failed 主流程."""
    fake_sess = MagicMock()
    fake_task = MagicMock()
    fake_task.summary_json = "<<untouched>>"
    fake_sess.get.return_value = fake_task

    def boom(_task_id: str) -> list:
        raise RuntimeError("DB down")

    with patch("src.ingest.pre_analysis.store.session_scope") as mock_scope:
        mock_scope.return_value.__enter__.return_value = fake_sess
        mock_scope.return_value.__exit__.return_value = False
        from src.ingest.pre_analysis import PreAnalysisTaskStore

        PreAnalysisTaskStore().mark_failed("pa-test-007", "boom", stages_provider=boom)

    # 状态正常切 failed, error 正常写
    assert fake_task.state == "failed"
    assert fake_task.error == "boom"
    # summary_json 没被覆盖 (provider 炸了)
    assert fake_task.summary_json == "<<untouched>>"
