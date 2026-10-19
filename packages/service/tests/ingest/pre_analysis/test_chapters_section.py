"""chapters_section stage 测试 (mode 1 mock, 2026-07-09, tree payload + chapter_config).

(2026-07-09 PDF 章节树状化) payload 改树状, 加 max_level/total_chapters 嵌套计数/toc_source/llm_summary_enabled.
覆盖:
- 默认 config (向后兼容)
- chapter_config.max_level 截断
- 无 outline → toc_source='empty'
- extract_chapters 抛异常 → mark_stage_failed
"""

from __future__ import annotations

import json
from contextlib import contextmanager
from typing import cast
from unittest.mock import MagicMock, patch

from src.ingest.pre_analysis.stage_context import StageContext


def _make_ctx(doc: MagicMock, output_prefix: str = "local://pre_analysis_outputs/t1") -> StageContext:
    """构造 StageContext, doc/object_store/stage_store/task_store 走 MagicMock 供 assert."""
    return StageContext(
        task_id="t1",
        pdf_uri="local://x.pdf",
        object_store=MagicMock(),
        task_store=MagicMock(),
        stage_store=MagicMock(),
        start_monotonic=0.0,
        doc=doc,
        output_prefix=output_prefix,
    )


def _patch_db_artifact_session() -> MagicMock:
    """db_artifact.append_artifact 走 mock session (无真 DB)."""
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


class TestChaptersSectionRun:
    def test_default_config_compat(self) -> None:
        """不传 chapter_config → 走默认 + payload 含新字段."""
        from src.ingest.pre_analysis.chapter_extractors.chapters_section import (
            run as chapters_run,
        )

        doc = MagicMock()
        doc.configure_mock(**{"__len__.return_value": 10})
        doc.get_toc.return_value = [[1, "章1", 1], [2, "1.1", 2]]
        ctx = _make_ctx(doc=doc)
        _patch_db_artifact_session()

        _, r = chapters_run(ctx)

        assert r.ok
        obj_store = cast("MagicMock", ctx.object_store)
        data_bytes = obj_store.put_bytes.call_args.args[1]
        payload = json.loads(data_bytes.decode("utf-8"))
        assert payload["max_level"] == 3  # 默认 DEFAULT_CHAPTER_MAX_LEVEL
        assert payload["total_pages"] == 10
        assert payload["total_chapters"] == 2  # 树状: 1 L1 + 1 L2
        assert payload["toc_source"] == "pdf_outline"
        assert payload["llm_summary_enabled"] is False  # (2026-07-09) 默认 config 关 LLM, payload 反映"未跑"
        assert "extracted_at" in payload
        # 嵌套树第一个节点应有 children
        assert isinstance(payload["chapters"], list)
        assert len(payload["chapters"]) == 1
        assert payload["chapters"][0]["title"] == "章1"
        assert payload["chapters"][0]["children"][0]["title"] == "1.1"
        # (2026-07-09) 默认 config 不开 LLM → chapters 不应有 summary 字段
        for n in payload["chapters"]:
            assert "summary" not in n
            for c in n["children"]:
                assert "summary" not in c

    def test_chapter_config_max_level(self) -> None:
        """传 chapter_config(max_level=1) → 树只含 L1, 没子节点."""
        from src.ingest.pre_analysis.chapter_extractors.chapter_config import (
            ChapterExtractionConfig,
        )
        from src.ingest.pre_analysis.chapter_extractors.chapters_section import (
            run as chapters_run,
        )

        doc = MagicMock()
        doc.configure_mock(**{"__len__.return_value": 10})
        doc.get_toc.return_value = [
            [1, "章1", 1],
            [2, "1.1", 2],
            [2, "1.2", 3],
            [1, "章2", 5],
        ]
        ctx = _make_ctx(doc=doc)
        _patch_db_artifact_session()
        # (2026-07-09) enable_llm_refinement=True 但 mock llm_summarize_chapters 返空,
        # 验证 llm_summary_enabled 反映"真跑了" (此处没跑成功, 仍应 False).
        cfg = ChapterExtractionConfig(chapter_max_level_for_display=1, enable_llm_refinement=True)

        with patch(
            "src.ingest.pre_analysis.chapter_extractors.chapters_section.llm_summarize_chapters",
            return_value={},
        ):
            _, r = chapters_run(ctx, chapter_config=cfg)

        assert r.ok
        obj_store = cast("MagicMock", ctx.object_store)
        payload = json.loads(obj_store.put_bytes.call_args.args[1].decode("utf-8"))
        assert payload["max_level"] == 1
        # (2026-07-09) llm_summary_enabled 反映"真跑了" — 这次 mock 返空 dict, 算没跑
        assert payload["llm_summary_enabled"] is False
        # L2 全截断, 只 2 个 L1
        assert payload["total_chapters"] == 2
        for n in payload["chapters"]:
            assert n["level"] == 1
            assert n["children"] == []

    def test_empty_outline_marks_empty_source(self) -> None:
        """无 outline → toc_source='empty', chapters=[]."""
        from src.ingest.pre_analysis.chapter_extractors.chapter_config import (
            ChapterExtractionConfig,
        )
        from src.ingest.pre_analysis.chapter_extractors.chapters_section import (
            run as chapters_run,
        )

        doc = MagicMock()
        doc.configure_mock(**{"__len__.return_value": 5})
        doc.get_toc.return_value = []
        ctx = _make_ctx(doc=doc)
        _patch_db_artifact_session()
        cfg = ChapterExtractionConfig(enable_llm_refinement=True)  # 即便开 LLM, 无章节就不调

        _, r = chapters_run(ctx, chapter_config=cfg)

        assert r.ok
        obj_store = cast("MagicMock", ctx.object_store)
        payload = json.loads(obj_store.put_bytes.call_args.args[1].decode("utf-8"))
        assert payload["toc_source"] == "empty"
        assert payload["chapters"] == []
        assert payload["total_chapters"] == 0
        assert payload["llm_summary_enabled"] is False  # 无章节 → 没 LLM

    def test_extract_chapters_failure(self) -> None:
        """extract_chapters 抛异常 → mark_stage_failed + ok=False."""
        from src.ingest.pre_analysis.chapter_extractors.chapter_config import (
            ChapterExtractionConfig,
        )
        from src.ingest.pre_analysis.chapter_extractors.chapters_section import (
            run as chapters_run,
        )

        doc = MagicMock()
        ctx = _make_ctx(doc=doc)
        _patch_db_artifact_session()

        with patch(
            "src.ingest.pre_analysis.chapter_extractors.chapters_section.extract_chapters",
            side_effect=RuntimeError("toc error"),
        ):
            _, r = chapters_run(ctx, chapter_config=ChapterExtractionConfig())

        assert not r.ok
        assert "toc error" in (r.error or "")
        assert r.stage_name == "extract_chapters"
        stage_store = cast("MagicMock", ctx.stage_store)
        assert stage_store.mark_stage_failed.call_count == 1
        # 失败不写产物
        obj_store = cast("MagicMock", ctx.object_store)
        assert obj_store.put_bytes.call_count == 0


class TestBuildPayloadCounting:
    """_build_payload 直接验证 total_chapters 嵌套计数."""

    def test_total_chapters_counts_all_nested_nodes(self) -> None:
        from src.ingest.pre_analysis.chapter_extractors.chapter_config import (
            ChapterExtractionConfig,
        )
        from src.ingest.pre_analysis.chapter_extractors.chapters_section import (
            _build_payload,
        )

        doc = MagicMock()
        doc.__len__.return_value = 10
        chapters = [
            {
                "id": "ch_1",
                "level": 1,
                "title": "章1",
                "page_start": 1,
                "page_end": 5,
                "children": [
                    {"id": "ch_2", "level": 2, "title": "1.1", "page_start": 1, "page_end": 3, "children": []},
                    {"id": "ch_3", "level": 2, "title": "1.2", "page_start": 4, "page_end": 5, "children": []},
                ],
            },
            {"id": "ch_4", "level": 1, "title": "章2", "page_start": 6, "page_end": 10, "children": []},
        ]
        payload = _build_payload(
            doc,
            chapters,
            ChapterExtractionConfig(),
            toc_source="pdf_outline",
            llm_summary_ran=False,
        )
        assert payload["total_chapters"] == 4

    def test_toc_source_value_propagated(self) -> None:
        from src.ingest.pre_analysis.chapter_extractors.chapter_config import (
            ChapterExtractionConfig,
        )
        from src.ingest.pre_analysis.chapter_extractors.chapters_section import (
            _build_payload,
        )

        doc = MagicMock()
        doc.__len__.return_value = 10
        for src in ("pdf_outline", "toc_pages", "llm_refined", "empty"):
            payload = _build_payload(
                doc,
                [],
                ChapterExtractionConfig(),
                toc_source=src,
                llm_summary_ran=False,
            )
            assert payload["toc_source"] == src

    def test_llm_summary_enabled_reflects_actual_run(self) -> None:
        """(2026-07-09) llm_summary_enabled 不再复读 config, 反映 llm_summary_ran 入参."""
        from src.ingest.pre_analysis.chapter_extractors.chapter_config import (
            ChapterExtractionConfig,
        )
        from src.ingest.pre_analysis.chapter_extractors.chapters_section import (
            _build_payload,
        )

        doc = MagicMock()
        doc.__len__.return_value = 10
        # enable_llm_refinement=True 但 llm_summary_ran=False → payload 应该 False (不复读)
        payload = _build_payload(
            doc,
            [],
            ChapterExtractionConfig(enable_llm_refinement=True),
            toc_source="pdf_outline",
            llm_summary_ran=False,
        )
        assert payload["llm_summary_enabled"] is False
        # 反过来: enable_llm_refinement=False 但 llm_summary_ran=True (不可能但 schema 接受) → True
        payload = _build_payload(
            doc,
            [],
            ChapterExtractionConfig(enable_llm_refinement=False),
            toc_source="pdf_outline",
            llm_summary_ran=True,
        )
        assert payload["llm_summary_enabled"] is True


class TestLlmSummaryWiring:
    """(2026-07-09) enable_llm_refinement=true 调 llm_summarize_chapters + summary 回写."""

    def test_enable_llm_refinement_writes_summaries_into_tree(self) -> None:
        """enable_llm_refinement=True + LLM 返 {ch_1: 'sum1', ch_2: 'sum2'} → payload chapters 含 summary."""
        from src.ingest.pre_analysis.chapter_extractors.chapter_config import (
            ChapterExtractionConfig,
        )
        from src.ingest.pre_analysis.chapter_extractors.chapters_section import (
            run as chapters_run,
        )

        doc = MagicMock()
        doc.configure_mock(**{"__len__.return_value": 10})
        doc.get_toc.return_value = [
            [1, "章1", 1],
            [2, "1.1", 2],
            [1, "章2", 5],
        ]
        ctx = _make_ctx(doc=doc)
        _patch_db_artifact_session()
        cfg = ChapterExtractionConfig(
            chapter_max_level_for_display=3,
            enable_llm_refinement=True,
            llm_summary_max_level=2,
        )

        # mock LLM 摘要: 顶层章1 (ch_1) + 子节 1.1 (ch_2) + 章2 (ch_3) 都给摘要
        fake_summaries = {
            "ch_1": "章1摘要",
            "ch_2": "1.1摘要",
            "ch_3": "章2摘要",
        }
        with patch(
            "src.ingest.pre_analysis.chapter_extractors.chapters_section.llm_summarize_chapters",
            return_value=fake_summaries,
        ) as mock_summarize:
            _, r = chapters_run(ctx, chapter_config=cfg)

        assert r.ok
        # (2026-07-09) 关键回归: llm_summarize_chapters 必须被调, chapters 必须被改 in-place
        assert mock_summarize.call_count == 1
        obj_store = cast("MagicMock", ctx.object_store)
        payload = json.loads(obj_store.put_bytes.call_args.args[1].decode("utf-8"))
        assert payload["llm_summary_enabled"] is True
        # 章1 (顶层) 有 summary
        ch1 = next(n for n in payload["chapters"] if n["title"] == "章1")
        assert ch1["summary"] == "章1摘要"
        # 1.1 (章1 的 children) 有 summary
        ch_11 = next(c for c in ch1["children"] if c["title"] == "1.1")
        assert ch_11["summary"] == "1.1摘要"
        # 章2 (顶层) 有 summary
        ch2 = next(n for n in payload["chapters"] if n["title"] == "章2")
        assert ch2["summary"] == "章2摘要"

    def test_llm_raised_does_not_fail_stage(self) -> None:
        """(2026-07-09) llm_summarize_chapters 抛错 → 跳过摘要, stage 仍 ok, llm_summary_enabled=False."""
        from src.ingest.pre_analysis.chapter_extractors.chapter_config import (
            ChapterExtractionConfig,
        )
        from src.ingest.pre_analysis.chapter_extractors.chapters_section import (
            run as chapters_run,
        )

        doc = MagicMock()
        doc.configure_mock(**{"__len__.return_value": 10})
        doc.get_toc.return_value = [[1, "章1", 1], [1, "章2", 5]]
        ctx = _make_ctx(doc=doc)
        _patch_db_artifact_session()
        cfg = ChapterExtractionConfig(enable_llm_refinement=True)

        with patch(
            "src.ingest.pre_analysis.chapter_extractors.chapters_section.llm_summarize_chapters",
            side_effect=RuntimeError("openai 502"),
        ):
            _, r = chapters_run(ctx, chapter_config=cfg)

        assert r.ok  # LLM 错不阻断 stage
        obj_store = cast("MagicMock", ctx.object_store)
        payload = json.loads(obj_store.put_bytes.call_args.args[1].decode("utf-8"))
        # (2026-07-09) LLM 抛错 → 没真跑成功 → llm_summary_enabled=False
        assert payload["llm_summary_enabled"] is False
        # chapters 不应有 summary 字段
        for n in payload["chapters"]:
            assert "summary" not in n

    def test_enable_llm_refinement_false_skips_llm_call(self) -> None:
        """enable_llm_refinement=False → llm_summarize_chapters 0 次调用."""
        from src.ingest.pre_analysis.chapter_extractors.chapter_config import (
            ChapterExtractionConfig,
        )
        from src.ingest.pre_analysis.chapter_extractors.chapters_section import (
            run as chapters_run,
        )

        doc = MagicMock()
        doc.configure_mock(**{"__len__.return_value": 10})
        doc.get_toc.return_value = [[1, "章1", 1]]
        ctx = _make_ctx(doc=doc)
        _patch_db_artifact_session()
        cfg = ChapterExtractionConfig(enable_llm_refinement=False)

        with patch(
            "src.ingest.pre_analysis.chapter_extractors.chapters_section.llm_summarize_chapters",
        ) as mock_summarize:
            _, r = chapters_run(ctx, chapter_config=cfg)

        assert r.ok
        assert mock_summarize.call_count == 0
        obj_store = cast("MagicMock", ctx.object_store)
        payload = json.loads(obj_store.put_bytes.call_args.args[1].decode("utf-8"))
        assert payload["llm_summary_enabled"] is False
