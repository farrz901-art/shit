"""StageContext + StageResult 测试 (mode 1 mock, 2026-07-09)."""

from __future__ import annotations

from unittest.mock import MagicMock


def test_stage_context_replace_returns_new_instance() -> None:
    """replace() 返回新实例, 原实例不变 (frozen)."""
    from src.ingest.pre_analysis.stage_context import StageContext

    doc = MagicMock()
    original = StageContext(
        task_id="t1",
        pdf_uri="local://x.pdf",
        object_store=MagicMock(),
        task_store=MagicMock(),
        stage_store=MagicMock(),
        start_monotonic=0.0,
    )
    new = original.replace(doc=doc, output_prefix="local://out/t1")
    assert new is not original
    assert new.doc is doc
    assert new.output_prefix == "local://out/t1"
    # 原实例不变 (frozen 验证)
    assert original.doc is None
    assert original.output_prefix is None


def test_stage_context_default_fields_none() -> None:
    """未填充字段默认 None, 数字字段默认 0."""
    from src.ingest.pre_analysis.stage_context import StageContext

    ctx = StageContext(
        task_id="t1",
        pdf_uri="x",
        object_store=MagicMock(),
        task_store=MagicMock(),
        stage_store=MagicMock(),
        start_monotonic=0.0,
    )
    assert ctx.doc is None
    assert ctx.chapters is None
    assert ctx.cross_page_count == 0
    assert ctx.index_uri is None
    assert ctx.tables is None
    assert ctx.flagged is None


def test_stage_result_ok_and_error() -> None:
    """StageResult 默认 ok=False, 显式传 ok=True / error 都能存."""
    from src.ingest.pre_analysis.stage_context import StageResult

    r_fail = StageResult(ok=False, error="boom", stage_name="x")
    assert r_fail.ok is False
    assert r_fail.error == "boom"
    assert r_fail.stage_name == "x"

    r_ok = StageResult(ok=True, stage_name="x", message="done")
    assert r_ok.ok is True
    assert r_ok.message == "done"
