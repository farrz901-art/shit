"""prepare_input stage 测试 (mode 1 mock, 2026-07-09)."""

from __future__ import annotations

from io import StringIO
from typing import cast
from unittest.mock import MagicMock, patch

import pymupdf


def _make_ctx(backend: str = "local") -> MagicMock:
    """构造 StageContext mock, 含 open_local mock 返 fake path. backend 默认 'local'."""
    obj = MagicMock()
    obj.open_local.return_value = "/tmp/fake.pdf"
    obj.backend_name.return_value = backend
    return obj


def test_prepare_input_happy_path() -> None:
    """open_local + pymupdf.open + yaml 加载都成功 → 返 ok=True + 新 ctx."""
    from src.ingest.pre_analysis.prepare_input import prepare_input
    from src.ingest.pre_analysis.stage_context import StageContext

    obj = _make_ctx()
    ctx = StageContext(
        task_id="t1",
        pdf_uri="local://x.pdf",
        object_store=obj,
        task_store=MagicMock(),
        stage_store=MagicMock(),
        start_monotonic=0.0,
    )
    # mock pymupdf.open 返 fake doc
    fake_doc = MagicMock(spec=pymupdf.Document)
    with patch("pymupdf.open", return_value=fake_doc):
        # mock Path.open 返 StringIO context manager, 让 yaml.safe_load 能 parse
        fake_file = StringIO("keywords: [a, b]")
        with patch("pathlib.Path.open", return_value=fake_file):
            new_ctx, r = prepare_input(ctx)

    assert r.ok
    assert new_ctx.doc is fake_doc
    assert new_ctx.output_prefix == "local://pre_analysis_outputs/t1"
    assert new_ctx.config == {"keywords": ["a", "b"]}
    stage_store = cast("MagicMock", ctx.stage_store)
    assert stage_store.mark_stage_completed.call_count == 1


def test_prepare_input_open_local_failure() -> None:
    """open_local 抛异常 → 返 ok=False, mark_stage_failed + mark_task_failed."""
    from src.ingest.pre_analysis.prepare_input import prepare_input
    from src.ingest.pre_analysis.stage_context import StageContext

    obj = MagicMock()
    obj.open_local.side_effect = FileNotFoundError("not found")
    ctx = StageContext(
        task_id="t1",
        pdf_uri="local://missing.pdf",
        object_store=obj,
        task_store=MagicMock(),
        stage_store=MagicMock(),
        start_monotonic=0.0,
    )
    _, r = prepare_input(ctx)
    assert not r.ok
    assert r.error is not None
    assert "not found" in r.error
    assert r.stage_name == "prepare_input"
    stage_store = cast("MagicMock", ctx.stage_store)
    assert stage_store.mark_stage_failed.call_count == 1
    task_store = cast("MagicMock", ctx.task_store)
    assert task_store.mark_failed.call_count == 1


def test_prepare_input_pymupdf_open_failure() -> None:
    """pymupdf.open 抛异常 → 返 ok=False."""
    from src.ingest.pre_analysis.prepare_input import prepare_input
    from src.ingest.pre_analysis.stage_context import StageContext

    obj = _make_ctx()
    ctx = StageContext(
        task_id="t1",
        pdf_uri="local://corrupt.pdf",
        object_store=obj,
        task_store=MagicMock(),
        stage_store=MagicMock(),
        start_monotonic=0.0,
    )
    with patch("pymupdf.open", side_effect=RuntimeError("corrupt")):
        _, r = prepare_input(ctx)

    assert not r.ok
    assert r.error is not None
    assert "corrupt" in r.error
    stage_store = cast("MagicMock", ctx.stage_store)
    assert stage_store.mark_stage_failed.call_count == 1
    task_store = cast("MagicMock", ctx.task_store)
    assert task_store.mark_failed.call_count == 1


def test_prepare_input_yaml_missing_fallback_default() -> None:
    """yaml 缺失 → 兜底默认 5 关键词, 仍 ok=True."""
    from src.ingest.pre_analysis.prepare_input import prepare_input
    from src.ingest.pre_analysis.stage_context import StageContext

    obj = _make_ctx()
    ctx = StageContext(
        task_id="t1",
        pdf_uri="local://x.pdf",
        object_store=obj,
        task_store=MagicMock(),
        stage_store=MagicMock(),
        start_monotonic=0.0,
    )
    fake_doc = MagicMock(spec=pymupdf.Document)
    with patch("pymupdf.open", return_value=fake_doc):
        with patch("pathlib.Path.open", side_effect=FileNotFoundError):
            new_ctx, r = prepare_input(ctx)

    assert r.ok
    assert new_ctx.config == {"keywords": ["注意", "不能", "仅适用", "必须", "禁止"]}


def test_prepare_input_yaml_minio_backend_uses_s3_scheme() -> None:
    """object_store backend='minio' → output_prefix 走 s3:// 方案."""
    from src.ingest.pre_analysis.prepare_input import prepare_input
    from src.ingest.pre_analysis.stage_context import StageContext

    obj = MagicMock()
    obj.backend_name.return_value = "minio"
    obj.open_local.return_value = "/tmp/fake.pdf"
    ctx = StageContext(
        task_id="t1",
        pdf_uri="s3://bucket/x.pdf",
        object_store=obj,
        task_store=MagicMock(),
        stage_store=MagicMock(),
        start_monotonic=0.0,
    )
    fake_doc = MagicMock(spec=pymupdf.Document)
    with patch("pymupdf.open", return_value=fake_doc):
        with patch("pathlib.Path.open", side_effect=FileNotFoundError):
            new_ctx, r = prepare_input(ctx)

    assert r.ok
    assert new_ctx.output_prefix is not None
    assert new_ctx.output_prefix.startswith("s3://")
    assert new_ctx.output_prefix.endswith("/pre_analysis_outputs/t1")
