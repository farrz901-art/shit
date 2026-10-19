"""finalize_output stage 测试 (mode 1 mock, 2026-07-09)."""

from __future__ import annotations

import json
from contextlib import contextmanager
from typing import cast
from unittest.mock import MagicMock, patch

from src.ingest.pre_analysis.stage_context import StageContext


def _make_ctx(
    chapter_uri: str = "local://pre_analysis_outputs/t1/chapter_structure.json",
    flagged_uri: str = "local://pre_analysis_outputs/t1/flagged_paragraphs.csv",
    output_prefix: str = "local://pre_analysis_outputs/t1",
    chapters: list | None = None,
    tables: list | None = None,
    flagged: list | None = None,
    cross_page_count: int = 0,
) -> StageContext:
    """构造 StageContext, 注入 stage 1-4 产物 (chapter_uri / flagged_uri / tables / flagged / chapters)."""
    return StageContext(
        task_id="t1",
        pdf_uri="local://x.pdf",
        object_store=MagicMock(),
        task_store=MagicMock(),
        stage_store=MagicMock(),
        start_monotonic=100.0,  # 跟 finalize 内部 time.monotonic mock 配
        doc=MagicMock(),
        config={},
        output_prefix=output_prefix,
        chapters=chapters or [],
        chapter_uri=chapter_uri,
        tables=tables or [],
        cross_page_count=cross_page_count,
        flagged=flagged or [],
        flagged_uri=flagged_uri,
    )


def _patch_db_artifact_session() -> MagicMock:
    """让 db_artifact.append_artifact + finalize_output 内部 session_scope 走 mock task (含 output_files_json).

    conftest autouse mock_all_db_connections patch `src.storage.session_scope`, 但 finalize_output 用
    `from ...storage import session_scope` (不同 import 路径), conftest 不覆盖. 显式 patch.
    """
    from src.ingest.pre_analysis.models import PreAnalysisTask

    s = MagicMock()
    task = MagicMock(spec=PreAnalysisTask)
    # index 阶段: 已累计 3 个产物 (chapter_structure + 1 table + flagged_paragraphs)
    existing = [
        {"kind": "chapter_structure", "filename": "chapter_structure.json", "uri": "x1", "size_bytes": 100},
        {"kind": "table", "filename": "tables/p1-t1.csv", "uri": "x2", "size_bytes": 50},
        {"kind": "flagged_paragraphs", "filename": "flagged_paragraphs.csv", "uri": "x3", "size_bytes": 80},
    ]
    task.output_files_json = json.dumps(existing)
    s.get.return_value = task

    @contextmanager
    def fake_session_scope():
        yield s

    # patch db_artifact.session_scope (for append_artifact) + finalize_output.session_scope
    import src.ingest.pre_analysis.db_artifact as mod
    import src.ingest.pre_analysis.finalize_output as mod2

    mod.session_scope = fake_session_scope
    mod2.session_scope = fake_session_scope
    return task


def test_finalize_output_happy_path_writes_index_and_marks_completed() -> None:
    """write_outputs: 写 index.json + db_artifact.append_artifact + mark_stage_completed."""
    from src.ingest.pre_analysis.finalize_output import run as finalize_run

    ctx = _make_ctx(
        # (2026-07-09) 章节 dict 加 children 字段 (跟 outline extractor 输出一致), count_chapters 递归读 children
        chapters=[{"title": "c1", "children": []}],
        tables=[(1, 1, [["a"]])],
        flagged=[{"matched_keywords": "注意"}],
        cross_page_count=0,
    )
    _patch_db_artifact_session()

    # patch time.monotonic 让 elapsed_ms 可控
    with patch("time.monotonic", return_value=100.5):
        new_ctx, r = finalize_run(ctx, table_extraction_config={"table_backend": "pymupdf"})

    assert r.ok
    obj_store = cast("MagicMock", ctx.object_store)
    # put_bytes 调 1 次写 index.json
    assert obj_store.put_bytes.call_count == 1
    call_args = obj_store.put_bytes.call_args
    assert call_args.args[0] == "local://pre_analysis_outputs/t1/index.json"
    assert call_args.args[2] == "application/json"
    # ctx 注入 index_uri
    assert new_ctx.index_uri == "local://pre_analysis_outputs/t1/index.json"
    # stage_store mark_completed
    stage_store = cast("MagicMock", ctx.stage_store)
    assert stage_store.mark_stage_completed.call_count == 1
    assert stage_store.mark_stage_failed.call_count == 0
    # task_store mark_completed 调一次 (final)
    task_store = cast("MagicMock", ctx.task_store)
    assert task_store.mark_completed.call_count == 1


def test_finalize_output_index_payload_summary() -> None:
    """index.json payload 含 task_id / pdf_filename / summary / files / elapsed_ms."""
    from src.ingest.pre_analysis.finalize_output import run as finalize_run

    ctx = _make_ctx(
        # (2026-07-09) 章节 dict 加 children 字段, count_chapters 递归读 children
        chapters=[
            {"title": "c1", "children": [{"title": "c1.1", "children": []}]},
            {"title": "c2", "children": []},
        ],
        tables=[(1, 1, []), (3, 1, [])],
        flagged=[{"k": 1}],
        cross_page_count=2,
    )
    _patch_db_artifact_session()

    with patch("time.monotonic", return_value=100.123):
        _, r = finalize_run(ctx, table_extraction_config={})

    assert r.ok
    obj_store = cast("MagicMock", ctx.object_store)
    data_bytes = obj_store.put_bytes.call_args.args[1]
    payload = json.loads(data_bytes.decode("utf-8"))
    assert payload["task_id"] == "t1"
    assert payload["pdf_filename"] == "x.pdf"
    # (2026-07-09) 递归总数: 2 顶层 + 1 子 = 3 (跟 chapter_structure.json.payload.total_chapters 一致)
    assert payload["summary"]["total_chapters"] == 3
    assert payload["summary"]["total_tables"] == 2
    assert payload["summary"]["total_flagged_paragraphs"] == 1
    assert payload["summary"]["cross_page_candidates"] == 2
    # files 从 DB 累计 3 项 (chapter_structure + table + flagged_paragraphs)
    assert len(payload["files"]) == 3
    # elapsed_ms: 100.123 - 100.0 = 0.123s = 123ms
    assert payload["elapsed_ms"] == 123


def test_finalize_output_index_appends_itself_to_db() -> None:
    """index.json 自身也被 db_artifact.append_artifact append 1 项 (final 累计 4 项)."""
    from src.ingest.pre_analysis.finalize_output import run as finalize_run

    ctx = _make_ctx()
    task = _patch_db_artifact_session()

    with patch("time.monotonic", return_value=100.0):
        _, r = finalize_run(ctx, table_extraction_config={})

    assert r.ok
    # 初始 3 项 + index 1 项 = 4
    files = json.loads(task.output_files_json)
    assert len(files) == 4
    assert files[-1]["kind"] == "index"
    assert files[-1]["filename"] == "index.json"


def test_finalize_output_failure_propagates() -> None:
    """put_bytes 抛异常 → 返 ok=False + mark_stage_failed + mark_failed."""
    from src.ingest.pre_analysis.finalize_output import run as finalize_run

    ctx = _make_ctx()
    _patch_db_artifact_session()

    obj_store = cast("MagicMock", ctx.object_store)
    obj_store.put_bytes.side_effect = RuntimeError("disk full")

    _, r = finalize_run(ctx, table_extraction_config={})

    assert not r.ok
    assert r.error is not None
    assert "disk full" in r.error
    assert r.stage_name == "write_outputs"
    stage_store = cast("MagicMock", ctx.stage_store)
    assert stage_store.mark_stage_failed.call_count == 1
    task_store = cast("MagicMock", ctx.task_store)
    assert task_store.mark_failed.call_count == 1
