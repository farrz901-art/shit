"""flagged_section stage 测试 (mode 1 mock, 2026-07-09)."""

from __future__ import annotations

import csv
from contextlib import contextmanager
from io import StringIO
from typing import cast
from unittest.mock import MagicMock, patch

from src.ingest.pre_analysis.stage_context import StageContext


def _make_ctx(doc: MagicMock, output_prefix: str = "local://pre_analysis_outputs/t1") -> StageContext:
    """构造 StageContext, doc/output_prefix 注入."""
    return StageContext(
        task_id="t1",
        pdf_uri="local://x.pdf",
        object_store=MagicMock(),
        task_store=MagicMock(),
        stage_store=MagicMock(),
        start_monotonic=0.0,
        doc=doc,
        config={"keywords": ["注意", "不能"]},
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


def test_flagged_section_happy_path_writes_csv_with_14_columns() -> None:
    """extract_flagged_paragraphs 返 1 行 → 写 CSV 含 14 列 header + 1 行数据 + DB append 1 项."""
    from src.ingest.pre_analysis.flag_extractors.flagged_section import (
        run as flagged_run,
    )

    doc = MagicMock()
    ctx = _make_ctx(doc=doc)
    _patch_db_artifact_session()

    fake_flagged = [
        {
            "matched_keywords": "注意",
            "page": 1,
            "section": "1.1",
            "text": "注意事项",
            "rule_categories": '["warn"]',
            "density": 0.5,
            "is_dense": True,
            "raw_density": 0.4,
            "weighted_density": 0.6,
            "safe_hits": 1,
            "rec_hits": 0,
            "lemmas": '["注意"]',
            "token_count": 10,
            "language": "zh",
        }
    ]
    with patch(
        "src.ingest.pre_analysis.flag_extractors.flagged_section.extract_flagged_paragraphs",
        return_value=fake_flagged,
    ):
        new_ctx, r = flagged_run(ctx)

    assert r.ok
    obj_store = cast("MagicMock", ctx.object_store)
    assert obj_store.put_bytes.call_count == 1
    # CSV 14 列 header
    data_bytes = obj_store.put_bytes.call_args.args[1]
    text = data_bytes.decode("utf-8")
    reader = csv.DictReader(StringIO(text))
    assert reader.fieldnames is not None
    assert len(reader.fieldnames) == 14
    rows = list(reader)
    assert len(rows) == 1
    assert rows[0]["matched_keywords"] == "注意"
    assert rows[0]["language"] == "zh"
    # new_ctx 注入 flagged / flagged_uri
    assert new_ctx.flagged == fake_flagged
    assert new_ctx.flagged_uri == "local://pre_analysis_outputs/t1/flagged_paragraphs.csv"
    stage_store = cast("MagicMock", ctx.stage_store)
    assert stage_store.mark_stage_completed.call_count == 1


def test_flagged_section_missing_field_filled_with_empty_string() -> None:
    """flagged 行缺字段 → 写 CSV 时该列填空字符串 (防御)."""
    from src.ingest.pre_analysis.flag_extractors.flagged_section import (
        run as flagged_run,
    )

    doc = MagicMock()
    ctx = _make_ctx(doc=doc)
    _patch_db_artifact_session()

    # 只给 2 个字段, 缺 12 个
    fake_flagged = [{"matched_keywords": "不能", "page": 2}]
    with patch(
        "src.ingest.pre_analysis.flag_extractors.flagged_section.extract_flagged_paragraphs",
        return_value=fake_flagged,
    ):
        _, r = flagged_run(ctx)

    assert r.ok
    obj_store = cast("MagicMock", ctx.object_store)
    data_bytes = obj_store.put_bytes.call_args.args[1]
    text = data_bytes.decode("utf-8")
    reader = csv.DictReader(StringIO(text))
    row = next(reader)
    assert row["matched_keywords"] == "不能"
    assert row["page"] == "2"
    assert row["section"] == ""  # 缺字段填空
    assert row["language"] == ""


def test_flagged_section_extract_failure() -> None:
    """extract_flagged_paragraphs 抛异常 → 返 ok=False + mark_stage_failed + mark_failed."""
    from src.ingest.pre_analysis.flag_extractors.flagged_section import (
        run as flagged_run,
    )

    doc = MagicMock()
    ctx = _make_ctx(doc=doc)
    _patch_db_artifact_session()

    with patch(
        "src.ingest.pre_analysis.flag_extractors.flagged_section.extract_flagged_paragraphs",
        side_effect=RuntimeError("kw extraction crash"),
    ):
        _, r = flagged_run(ctx)

    assert not r.ok
    assert r.error is not None
    assert "kw extraction crash" in r.error
    assert r.stage_name == "extract_flagged"
    stage_store = cast("MagicMock", ctx.stage_store)
    assert stage_store.mark_stage_failed.call_count == 1
    task_store = cast("MagicMock", ctx.task_store)
    assert task_store.mark_failed.call_count == 1
    obj_store = cast("MagicMock", ctx.object_store)
    assert obj_store.put_bytes.call_count == 0
