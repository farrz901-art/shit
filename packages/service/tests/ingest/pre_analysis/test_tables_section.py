"""tables_section stage 测试 (mode 1 mock, 2026-07-09)."""

from __future__ import annotations

from contextlib import contextmanager
from typing import cast
from unittest.mock import MagicMock, patch

from src.ingest.pre_analysis.stage_context import StageContext


def _make_ctx(doc: MagicMock, output_prefix: str = "local://pre_analysis_outputs/t1") -> StageContext:
    """构造 StageContext, 但 doc/object_store/stage_store/task_store 走真 MagicMock (可 assert)."""
    return StageContext(
        task_id="t1",
        pdf_uri="local://x.pdf",
        object_store=MagicMock(),
        task_store=MagicMock(),
        stage_store=MagicMock(),
        start_monotonic=0.0,
        doc=doc,
        config={"cross_page_detection": {"min_column_match": 0.8, "footer_keywords": ["continued"]}},
        output_prefix=output_prefix,
    )


def _patch_db_artifact_session() -> MagicMock:
    """让 db_artifact.append_artifact 走真逻辑 (mock task.output_files_json = '[]'). 返 task 供 assert."""
    from src.ingest.pre_analysis.models import PreAnalysisTask

    s = MagicMock()
    task = MagicMock(spec=PreAnalysisTask)
    task.output_files_json = "[]"
    s.get.return_value = task

    @contextmanager
    def fake_session_scope():
        yield s

    import src.ingest.pre_analysis.db_artifact as mod

    mod.session_scope = fake_session_scope
    return task


def test_tables_section_happy_path_writes_csv_per_table() -> None:
    """extract_tables 返 2 张表 → 写 2 个 CSV + DB append 2 项 + cross_page_count=0."""
    from src.ingest.pre_analysis.table_extractors.tables_section import (
        run as tables_run,
    )

    doc = MagicMock()
    doc.name = "test.pdf"
    ctx = _make_ctx(doc=doc)
    _patch_db_artifact_session()

    fake_tables = [
        (1, 1, [["h1", "h2"], ["v1", "v2"]]),
        (3, 1, [["h1", "h2"], ["v3", "v4"]]),
    ]
    # mock TableExtractor 工厂 + extract() 返 RawTable 列表
    fake_raw = [
        MagicMock(page_no=1, table_no=1, rows=fake_tables[0][2]),
        MagicMock(page_no=3, table_no=1, rows=fake_tables[1][2]),
    ]
    with patch("src.ingest.pre_analysis.table_extractors.factory.get_table_extractor") as mock_factory:
        mock_extractor = MagicMock()
        mock_extractor.extract.return_value = fake_raw
        mock_factory.return_value = mock_extractor
        new_ctx, r = tables_run(ctx, table_extraction_config={"table_backend": "pymupdf"})

    assert r.ok
    obj_store = cast("MagicMock", ctx.object_store)
    assert obj_store.put_bytes.call_count == 2
    # uri 拼对
    uris = [c.args[0] for c in obj_store.put_bytes.call_args_list]
    assert "local://pre_analysis_outputs/t1/tables/page-1-table-1.csv" in uris
    assert "local://pre_analysis_outputs/t1/tables/page-3-table-1.csv" in uris
    # new_ctx 注入 tables / cross_page_count
    assert new_ctx.tables is not None
    assert len(new_ctx.tables) == 2
    assert new_ctx.cross_page_count == 0


def test_tables_section_cross_page_detection() -> None:
    """2 张表跨页 + footer "continued" → cross_page_count=1."""
    from src.ingest.pre_analysis.table_extractors.tables_section import (
        run as tables_run,
    )

    doc = MagicMock()
    doc.name = "test.pdf"
    ctx = _make_ctx(doc=doc)
    _patch_db_artifact_session()

    # page 1 表格 1 (2 列) + page 2 表格 1 (2 列, footer "continued")
    fake_raw = [
        MagicMock(page_no=1, table_no=1, rows=[["h1", "h2"], ["v1", "v2"]]),
        MagicMock(page_no=2, table_no=1, rows=[["h1", "h2"], ["continued", "more"]]),
    ]
    with patch("src.ingest.pre_analysis.table_extractors.factory.get_table_extractor") as mock_factory:
        mock_extractor = MagicMock()
        mock_extractor.extract.return_value = fake_raw
        mock_factory.return_value = mock_extractor
        new_ctx, r = tables_run(ctx, table_extraction_config={"table_backend": "pymupdf"})

    assert r.ok
    assert new_ctx.cross_page_count == 1


def test_tables_section_extractor_failure() -> None:
    """extractor.extract 抛异常 → 返 ok=False + mark_stage_failed + mark_failed."""
    from src.ingest.pre_analysis.table_extractors.tables_section import (
        run as tables_run,
    )

    doc = MagicMock()
    doc.name = "test.pdf"
    ctx = _make_ctx(doc=doc)
    _patch_db_artifact_session()

    with patch("src.ingest.pre_analysis.table_extractors.factory.get_table_extractor") as mock_factory:
        mock_extractor = MagicMock()
        mock_extractor.extract.side_effect = RuntimeError("extractor crash")
        mock_factory.return_value = mock_extractor
        _, r = tables_run(ctx, table_extraction_config={"table_backend": "pymupdf"})

    assert not r.ok
    assert r.error is not None
    assert "extractor crash" in r.error
    stage_store = cast("MagicMock", ctx.stage_store)
    assert stage_store.mark_stage_failed.call_count == 1
    task_store = cast("MagicMock", ctx.task_store)
    assert task_store.mark_failed.call_count == 1
    obj_store = cast("MagicMock", ctx.object_store)
    assert obj_store.put_bytes.call_count == 0


def test_tables_section_no_tables_still_succeeds() -> None:
    """extractor 返 [] → 写 0 个 CSV, ok=True, cross_page_count=0."""
    from src.ingest.pre_analysis.table_extractors.tables_section import (
        run as tables_run,
    )

    doc = MagicMock()
    doc.name = "test.pdf"
    ctx = _make_ctx(doc=doc)
    _patch_db_artifact_session()

    with patch("src.ingest.pre_analysis.table_extractors.factory.get_table_extractor") as mock_factory:
        mock_extractor = MagicMock()
        mock_extractor.extract.return_value = []
        mock_factory.return_value = mock_extractor
        new_ctx, r = tables_run(ctx, table_extraction_config={"table_backend": "pymupdf"})

    assert r.ok
    obj_store = cast("MagicMock", ctx.object_store)
    assert obj_store.put_bytes.call_count == 0
    assert new_ctx.cross_page_count == 0
    stage_store = cast("MagicMock", ctx.stage_store)
    assert stage_store.mark_stage_completed.call_count == 1
