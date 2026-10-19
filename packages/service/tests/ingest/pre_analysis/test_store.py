# packages/service/tests/ingest/test_pre_analysis.stage_store.py
"""Pre-analysis stage store 单测 (mode 1 mock).

覆盖 mark_started / mark_completed / mark_failed / list_stages / delete_stages_for_retry.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def fake_session() -> MagicMock:
    s = MagicMock()
    s.__enter__.return_value = s
    s.__exit__.return_value = False
    return s


# (2026-07-03) 简短单测 — 验证 facade 函数被调, 行为由 SQLAlchemy session_scope 真实承担
def test_mark_stage_started_calls_session_add() -> None:
    with patch("src.ingest.pre_analysis.stage_store.session_scope") as mock_scope:
        mock_scope.return_value.__enter__.return_value = MagicMock()
        mock_scope.return_value.__exit__.return_value = False
        from src.ingest.pre_analysis import PreAnalysisStageStore

        store = PreAnalysisStageStore()
        store.mark_stage_started("pa-1", "load_config")
        # session_scope 必须被调
        assert mock_scope.called
        # s.add 必须在 session 里调
        assert mock_scope.return_value.__enter__.return_value.add.called


def test_mark_stage_completed_resolves_latest_row() -> None:
    fake_sess = MagicMock()
    fake_row = MagicMock()
    fake_sess.execute.return_value.scalar_one_or_none.return_value = fake_row
    with patch("src.ingest.pre_analysis.stage_store.session_scope") as mock_scope:
        mock_scope.return_value.__enter__.return_value = fake_sess
        mock_scope.return_value.__exit__.return_value = False
        from src.ingest.pre_analysis import PreAnalysisStageStore

        store = PreAnalysisStageStore()
        store.mark_stage_completed("pa-1", "extract_chapters", progress=100, message="5 章")
        # row 必须被 mark completed + progress + finished_at
        assert fake_row.status == "completed"
        assert fake_row.progress == 100
        assert fake_row.message == "5 章"
        assert fake_row.finished_at is not None


def test_mark_stage_failed_truncates_long_error() -> None:
    fake_sess = MagicMock()
    fake_row = MagicMock()
    fake_sess.execute.return_value.scalar_one_or_none.return_value = fake_row
    with patch("src.ingest.pre_analysis.stage_store.session_scope") as mock_scope:
        mock_scope.return_value.__enter__.return_value = fake_sess
        mock_scope.return_value.__exit__.return_value = False
        from src.ingest.pre_analysis import PreAnalysisStageStore

        store = PreAnalysisStageStore()
        long_error = "x" * 2000
        store.mark_stage_failed("pa-1", "extract_tables", long_error)
        # message 必须截到 1000 字符
        assert len(fake_row.message) == 1000
        assert fake_row.status == "failed"


def test_list_stages_returns_ordered() -> None:
    fake_sess = MagicMock()
    fake_rows = [MagicMock(stage="load_config"), MagicMock(stage="extract_chapters")]
    fake_sess.execute.return_value.scalars.return_value = fake_rows
    with patch("src.ingest.pre_analysis.stage_store.session_scope") as mock_scope:
        mock_scope.return_value.__enter__.return_value = fake_sess
        mock_scope.return_value.__exit__.return_value = False
        from src.ingest.pre_analysis import PreAnalysisStageStore

        store = PreAnalysisStageStore()
        result = store.list_stages("pa-1")
        assert result == fake_rows


def test_delete_stages_for_retry_calls_delete() -> None:
    fake_sess = MagicMock()
    with patch("src.ingest.pre_analysis.stage_store.session_scope") as mock_scope:
        mock_scope.return_value.__enter__.return_value = fake_sess
        mock_scope.return_value.__exit__.return_value = False
        from src.ingest.pre_analysis import PreAnalysisStageStore

        store = PreAnalysisStageStore()
        store.delete_stages_for_retry("pa-1")
        # delete 必须被调
        assert fake_sess.query.return_value.filter_by.return_value.delete.called
