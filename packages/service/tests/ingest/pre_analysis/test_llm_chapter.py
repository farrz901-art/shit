"""llm_chapter.py 测试 (mode 1 mock, 2026-07-09).

覆盖 llm_refine_chapters + llm_summarize_chapters:
- mock _get_llm → OpenAILLM().llm.with_structured_output().invoke() 链
- LLM 抛错 → 返 [] / {} 不阻断
- 章节筛选 (level > max_level 跳过)
- 分批大小 (OpenAI 25 / Ollama 10)
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from pydantic import ValidationError


def _make_doc(pages_text: list[str]) -> MagicMock:
    """构造 doc mock, doc[idx].get_text() 顺序返每页文本."""
    pages = []
    for t in pages_text:
        p = MagicMock()
        p.get_text.return_value = t
        pages.append(p)
    doc = MagicMock()
    doc.__len__.return_value = len(pages)
    doc.__getitem__ = MagicMock(side_effect=lambda idx: pages[idx])
    return doc


def _setup_llm_structured_mock(return_value: object | None = None, raise_exc: Exception | None = None) -> MagicMock:
    """构造 OpenAILLM 包装: llm.with_structured_output(schema, method='json_mode') 返 chain.

    chain.invoke(arg) → 返 return_value (真 Pydantic instance) 或抛 raise_exc.
    注意: return_value 必须是真对象 (Pydantic instance / dict), MagicMock 会让 .chapters 等
    属性自动 mock → 测试环走不到真业务逻辑.

    设计: 直接 mock `with_structured_output` 的 .invoke 方法 (实际生产代码调用路径).
    """
    mock_llm_wrapper = MagicMock()
    mock_llm_instance = mock_llm_wrapper.llm  # mock_llm_wrapper.llm 才是 _invoke_structured 接收的
    mock_structured = MagicMock()
    # 关键: structured.invoke 直接 mock, 不再 structured() chain
    if raise_exc is not None:
        mock_structured.invoke.side_effect = raise_exc
    else:
        mock_structured.invoke.return_value = return_value
    mock_llm_instance.with_structured_output.return_value = mock_structured
    return mock_llm_wrapper


class TestLlmRefineChapters:
    def test_happy_path_returns_triples(self) -> None:
        """mock LLM 返 2 章 → [(1, "章1", 1), (2, "1.1", 2)]."""
        from src.ingest.pre_analysis.chapter_extractors.chapter_config import ChapterExtractionConfig
        from src.ingest.pre_analysis.chapter_extractors.llm_chapter import llm_refine_chapters
        from src.ingest.pre_analysis.chapter_extractors.llm_schemas import LLMChapterOutput

        parsed = LLMChapterOutput.model_validate(
            {
                "chapters": [
                    {"level": 1, "title": "章1", "page_start": 1},
                    {"level": 2, "title": "1.1", "page_start": 2},
                ]
            }
        )
        mock_llm = _setup_llm_structured_mock(parsed)
        doc = _make_doc(["前置内容..."])
        cfg = ChapterExtractionConfig(llm_provider="openai", enable_llm_refinement=True)

        with patch(
            "src.ingest.pre_analysis.chapter_extractors.llm_chapter._get_llm",
            return_value=mock_llm,
        ):
            result = llm_refine_chapters(doc, cfg)

        assert result == [(1, "章1", 1), (2, "1.1", 2)]
        # with_structured_output 用 json_mode
        call_kwargs = mock_llm.llm.with_structured_output.call_args.kwargs
        assert call_kwargs.get("method") == "json_mode"

    def test_empty_text_returns_empty_list(self) -> None:
        """前 N 页无文本 → 返 [], 不调 LLM."""
        from src.ingest.pre_analysis.chapter_extractors.chapter_config import ChapterExtractionConfig
        from src.ingest.pre_analysis.chapter_extractors.llm_chapter import llm_refine_chapters

        doc = _make_doc([""] * 35)
        cfg = ChapterExtractionConfig()

        with patch(
            "src.ingest.pre_analysis.chapter_extractors.llm_chapter._get_llm",
        ) as mock_get:
            result = llm_refine_chapters(doc, cfg)

        assert result == []
        mock_get.assert_not_called()

    def test_llm_exception_returns_empty(self) -> None:
        """LLM 抛 ConnectionError → 返 [], 不阻断."""
        from src.ingest.pre_analysis.chapter_extractors.chapter_config import ChapterExtractionConfig
        from src.ingest.pre_analysis.chapter_extractors.llm_chapter import llm_refine_chapters

        mock_llm = _setup_llm_structured_mock(raise_exc=ConnectionError("ollama down"))
        doc = _make_doc(["page text"])
        cfg = ChapterExtractionConfig()

        with patch(
            "src.ingest.pre_analysis.chapter_extractors.llm_chapter._get_llm",
            return_value=mock_llm,
        ):
            result = llm_refine_chapters(doc, cfg)

        assert result == []


class TestLlmSummarizeChapters:
    def _chapters(self) -> list[dict]:
        return [
            {"id": "ch_1", "level": 1, "title": "章1", "page_start": 1, "page_end": 10, "children": []},
            {"id": "ch_2", "level": 1, "title": "章2", "page_start": 11, "page_end": 20, "children": []},
            {
                "id": "ch_3",
                "level": 2,
                "title": "1.1",
                "page_start": 2,
                "page_end": 5,
                "children": [],  # level 2 > max_level=1, 跳过
            },
        ]

    def test_filters_chapters_by_max_level(self) -> None:
        """只筛 level <= max_level 的 chapter, 返的 dict 不含 ch_3."""
        from src.ingest.pre_analysis.chapter_extractors.chapter_config import ChapterExtractionConfig
        from src.ingest.pre_analysis.chapter_extractors.llm_chapter import llm_summarize_chapters
        from src.ingest.pre_analysis.chapter_extractors.llm_schemas import SummaryOutput

        parsed = SummaryOutput.model_validate(
            {
                "summaries": [
                    {"chapter_id": "ch_1", "summary": "本章介绍..."},
                    {"chapter_id": "ch_2", "summary": "本章方法..."},
                ]
            }
        )
        mock_llm = _setup_llm_structured_mock(parsed)
        doc = _make_doc(["第一章内容"] * 5 + ["第二章内容"] * 5 + ["1.1内容"] * 3)
        cfg = ChapterExtractionConfig(llm_provider="openai", llm_summary_max_level=1)

        with patch(
            "src.ingest.pre_analysis.chapter_extractors.llm_chapter._get_llm",
            return_value=mock_llm,
        ):
            result = llm_summarize_chapters(doc, self._chapters(), cfg)

        assert result == {"ch_1": "本章介绍...", "ch_2": "本章方法..."}

    def test_uses_openai_batch_size_25(self) -> None:
        """OpenAI provider → batch_size=25 → 30 章 = 2 批."""
        from src.ingest.pre_analysis.chapter_extractors.chapter_config import ChapterExtractionConfig
        from src.ingest.pre_analysis.chapter_extractors.llm_chapter import llm_summarize_chapters
        from src.ingest.pre_analysis.chapter_extractors.llm_schemas import SummaryOutput

        # (2026-07-09 retry-on-missing) mock 返完整覆盖 (summaries 含 30 章) → 不触发重试,
        # invoke 调用数 = batch 数. 老版本返空 dict 会触发重试, 跟"测 batch 数"语义冲突.
        parsed = SummaryOutput.model_validate(
            {"summaries": [{"chapter_id": f"ch_{i}", "summary": f"s{i}"} for i in range(30)]}
        )
        mock_llm = _setup_llm_structured_mock(parsed)
        doc = _make_doc(["x"] * 100)
        chapters = [
            {"id": f"ch_{i}", "level": 1, "title": f"章{i}", "page_start": 1, "page_end": 5, "children": []}
            for i in range(30)
        ]

        with patch(
            "src.ingest.pre_analysis.chapter_extractors.llm_chapter._get_llm",
            return_value=mock_llm,
        ):
            cfg = ChapterExtractionConfig(llm_provider="openai", llm_summary_max_level=1)
            llm_summarize_chapters(doc, chapters, cfg)

        assert mock_llm.llm.with_structured_output.return_value.invoke.call_count == 2

    def test_uses_ollama_batch_size_10(self) -> None:
        """Ollama provider → batch_size=10 → 30 章 = 3 批."""
        from src.ingest.pre_analysis.chapter_extractors.chapter_config import ChapterExtractionConfig
        from src.ingest.pre_analysis.chapter_extractors.llm_chapter import llm_summarize_chapters
        from src.ingest.pre_analysis.chapter_extractors.llm_schemas import SummaryOutput

        # (2026-07-09 retry-on-missing) 完整覆盖 → 不重试, invoke = batch 数.
        # ollama batch=10, 30 章 → 3 批, 每批返 10 章.
        def make_batch_parsed(start: int) -> SummaryOutput:
            return SummaryOutput.model_validate(
                {"summaries": [{"chapter_id": f"ch_{i}", "summary": f"s{i}"} for i in range(start, start + 10)]}
            )

        mock_llm = _setup_llm_structured_mock(make_batch_parsed(0))
        mock_llm.llm.with_structured_output.return_value.invoke.side_effect = [
            make_batch_parsed(0),
            make_batch_parsed(10),
            make_batch_parsed(20),
        ]
        doc = _make_doc(["x"] * 100)
        chapters = [
            {"id": f"ch_{i}", "level": 1, "title": f"章{i}", "page_start": 1, "page_end": 5, "children": []}
            for i in range(30)
        ]

        with patch(
            "src.ingest.pre_analysis.chapter_extractors.llm_chapter._get_llm",
            return_value=mock_llm,
        ):
            cfg = ChapterExtractionConfig(llm_provider="ollama", llm_summary_max_level=1)
            llm_summarize_chapters(doc, chapters, cfg)

        assert mock_llm.llm.with_structured_output.return_value.invoke.call_count == 3

    def test_batch_failure_skips_that_batch(self) -> None:
        """单 batch 抛错 → 其他 batch 仍成功, dict 只含成功的."""
        from src.ingest.pre_analysis.chapter_extractors.chapter_config import ChapterExtractionConfig
        from src.ingest.pre_analysis.chapter_extractors.llm_chapter import llm_summarize_chapters
        from src.ingest.pre_analysis.chapter_extractors.llm_schemas import SummaryOutput

        # ch_1 + ch_2 必须分批: 用 ollama batch_size=10 但 page_end 不覆盖到 (必然 2 批)
        # 实际 batch_size=ollama=10, 2 章同一批, 走 side_effect 只 1 次 — 改用 openai batch_size=1
        # 走自然的 2 章 2 批 (mock side_effect list 2 个值).
        # 直接构造: 用 page_end=1 让 _iter_chapter_texts 把每个 ch 当 1 页, 但仍同 batch 触发.
        # 改 batch=1 via _BATCH_OPENAI override 太 hack; 改用 26 章让 openai 分 2 批.
        parsed_ok = SummaryOutput.model_validate({"summaries": [{"chapter_id": "ch_26", "summary": "本章方法..."}]})
        mock_llm = _setup_llm_structured_mock(parsed_ok)
        # 1 批抛错, 2 批返 ch_26 成功 (openai batch=25, 26 章 → 2 批)
        mock_llm.llm.with_structured_output.return_value.invoke.side_effect = [
            ConnectionError("ollama 504"),
            parsed_ok,
        ]

        doc = _make_doc(["x"] * 30)
        chapters = [
            {"id": f"ch_{i}", "level": 1, "title": f"章{i}", "page_start": 1, "page_end": 2, "children": []}
            for i in range(1, 27)
        ]

        with patch(
            "src.ingest.pre_analysis.chapter_extractors.llm_chapter._get_llm",
            return_value=mock_llm,
        ):
            cfg = ChapterExtractionConfig(llm_provider="openai", llm_summary_max_level=1)
            result = llm_summarize_chapters(doc, chapters, cfg)

        assert result == {"ch_26": "本章方法..."}

    def test_validation_error_returns_empty_dict(self) -> None:
        """LLM 返非 Pydantic 兼容 shape → ValidationError 被 except 兜 → dict 空."""
        from src.ingest.pre_analysis.chapter_extractors.chapter_config import ChapterExtractionConfig
        from src.ingest.pre_analysis.chapter_extractors.llm_chapter import llm_summarize_chapters

        exc = ValidationError.from_exception_data(
            "SummaryOutput", [{"type": "missing", "loc": ("summaries",), "input": {}, "ctx": {}}]
        )
        mock_llm = _setup_llm_structured_mock(raise_exc=exc)

        doc = _make_doc(["x"] * 5)
        chapters = [{"id": "ch_1", "level": 1, "title": "章1", "page_start": 1, "page_end": 5, "children": []}]

        with patch(
            "src.ingest.pre_analysis.chapter_extractors.llm_chapter._get_llm",
            return_value=mock_llm,
        ):
            result = llm_summarize_chapters(doc, chapters, ChapterExtractionConfig())

        assert result == {}


class TestRetryOnMissing:
    """(2026-07-09) LLM 摘要缺 chapter_id → 自动重试 1 次, 仍缺仅 log warning."""

    def test_partial_missing_triggers_retry_with_missing_hint(self) -> None:
        """第 1 次 invoke 返 3/5 → 触发重试, 第 2 次 invoke prompt 包含 missing 提示."""
        from src.ingest.pre_analysis.chapter_extractors.chapter_config import (
            ChapterExtractionConfig,
        )
        from src.ingest.pre_analysis.chapter_extractors.llm_chapter import (
            llm_summarize_chapters,
        )
        from src.ingest.pre_analysis.chapter_extractors.llm_schemas import SummaryOutput

        # 第 1 次: 返 ch_1/ch_2/ch_3 (缺 ch_4/ch_5); 第 2 次: 补齐 ch_4/ch_5
        first = SummaryOutput.model_validate(
            {
                "summaries": [
                    {"chapter_id": "ch_1", "summary": "s1"},
                    {"chapter_id": "ch_2", "summary": "s2"},
                    {"chapter_id": "ch_3", "summary": "s3"},
                ]
            }
        )
        second = SummaryOutput.model_validate(
            {
                "summaries": [
                    {"chapter_id": "ch_4", "summary": "s4"},
                    {"chapter_id": "ch_5", "summary": "s5"},
                ]
            }
        )
        mock_llm = _setup_llm_structured_mock(first)
        mock_llm.llm.with_structured_output.return_value.invoke.side_effect = [first, second]

        doc = _make_doc(["x"] * 10)
        chapters = [
            {"id": f"ch_{i}", "level": 1, "title": f"章{i}", "page_start": 1, "page_end": 5, "children": []}
            for i in range(1, 6)
        ]

        with patch(
            "src.ingest.pre_analysis.chapter_extractors.llm_chapter._get_llm",
            return_value=mock_llm,
        ):
            result = llm_summarize_chapters(doc, chapters, ChapterExtractionConfig())

        # 重试补齐, 5 章全有 summary
        assert result == {"ch_1": "s1", "ch_2": "s2", "ch_3": "s3", "ch_4": "s4", "ch_5": "s5"}
        # invoke 调了 2 次 (第 1 次 + 重试)
        assert mock_llm.llm.with_structured_output.return_value.invoke.call_count == 2
        # 第 2 次 prompt 必须包含 missing 提示 + ch_4 + ch_5
        retry_prompt = mock_llm.llm.with_structured_output.return_value.invoke.call_args_list[1].args[0]
        assert "[系统校正]" in retry_prompt
        assert "ch_4" in retry_prompt
        assert "ch_5" in retry_prompt

    def test_retry_still_missing_returns_partial_with_warning(self) -> None:
        """重试后仍缺 1 章 → log warning, 返现有 (不完整) 结果, 不再重试."""
        from src.ingest.pre_analysis.chapter_extractors.chapter_config import (
            ChapterExtractionConfig,
        )
        from src.ingest.pre_analysis.chapter_extractors.llm_chapter import (
            llm_summarize_chapters,
        )
        from src.ingest.pre_analysis.chapter_extractors.llm_schemas import SummaryOutput

        first = SummaryOutput.model_validate(
            {"summaries": [{"chapter_id": "ch_1", "summary": "s1"}, {"chapter_id": "ch_2", "summary": "s2"}]}
        )
        # 第 2 次只补 ch_3, ch_4 仍缺
        second = SummaryOutput.model_validate({"summaries": [{"chapter_id": "ch_3", "summary": "s3"}]})
        mock_llm = _setup_llm_structured_mock(first)
        mock_llm.llm.with_structured_output.return_value.invoke.side_effect = [first, second]

        doc = _make_doc(["x"] * 10)
        chapters = [
            {"id": f"ch_{i}", "level": 1, "title": f"章{i}", "page_start": 1, "page_end": 5, "children": []}
            for i in range(1, 5)
        ]

        with patch(
            "src.ingest.pre_analysis.chapter_extractors.llm_chapter._get_llm",
            return_value=mock_llm,
        ):
            result = llm_summarize_chapters(doc, chapters, ChapterExtractionConfig())

        # ch_4 仍缺, dict 只含 3 章, 但不抛错
        assert result == {"ch_1": "s1", "ch_2": "s2", "ch_3": "s3"}
        assert mock_llm.llm.with_structured_output.return_value.invoke.call_count == 2

    def test_all_missing_triggers_retry_then_returns_what_got(self) -> None:
        """第 1 次返 0 章 → 触发重试, 重试仍 0 → 返 {} 不抛错."""
        from src.ingest.pre_analysis.chapter_extractors.chapter_config import (
            ChapterExtractionConfig,
        )
        from src.ingest.pre_analysis.chapter_extractors.llm_chapter import (
            llm_summarize_chapters,
        )
        from src.ingest.pre_analysis.chapter_extractors.llm_schemas import SummaryOutput

        empty = SummaryOutput.model_validate({"summaries": []})
        mock_llm = _setup_llm_structured_mock(empty)
        mock_llm.llm.with_structured_output.return_value.invoke.side_effect = [empty, empty]

        doc = _make_doc(["x"] * 5)
        chapters = [
            {"id": "ch_1", "level": 1, "title": "章1", "page_start": 1, "page_end": 5, "children": []},
            {"id": "ch_2", "level": 1, "title": "章2", "page_start": 1, "page_end": 5, "children": []},
        ]

        with patch(
            "src.ingest.pre_analysis.chapter_extractors.llm_chapter._get_llm",
            return_value=mock_llm,
        ):
            result = llm_summarize_chapters(doc, chapters, ChapterExtractionConfig())

        assert result == {}
        # 重试 1 次 (跟有部分缺失一样, missing 非空都触发)
        assert mock_llm.llm.with_structured_output.return_value.invoke.call_count == 2

    def test_retry_exception_returns_partial_first_attempt(self) -> None:
        """重试 invoke 抛错 → 返第 1 次的不完整结果 (不抛错)."""
        from src.ingest.pre_analysis.chapter_extractors.chapter_config import (
            ChapterExtractionConfig,
        )
        from src.ingest.pre_analysis.chapter_extractors.llm_chapter import (
            llm_summarize_chapters,
        )
        from src.ingest.pre_analysis.chapter_extractors.llm_schemas import SummaryOutput

        first = SummaryOutput.model_validate({"summaries": [{"chapter_id": "ch_1", "summary": "s1"}]})
        mock_llm = _setup_llm_structured_mock(first)
        # 第 1 次返 1/3 (缺 ch_2/ch_3), 第 2 次抛错
        mock_llm.llm.with_structured_output.return_value.invoke.side_effect = [
            first,
            ConnectionError("openai 502"),
        ]

        doc = _make_doc(["x"] * 5)
        chapters = [
            {"id": f"ch_{i}", "level": 1, "title": f"章{i}", "page_start": 1, "page_end": 5, "children": []}
            for i in range(1, 4)
        ]

        with patch(
            "src.ingest.pre_analysis.chapter_extractors.llm_chapter._get_llm",
            return_value=mock_llm,
        ):
            result = llm_summarize_chapters(doc, chapters, ChapterExtractionConfig())

        # 返第 1 次结果, ch_2/ch_3 缺失但不抛错
        assert result == {"ch_1": "s1"}
        assert mock_llm.llm.with_structured_output.return_value.invoke.call_count == 2

    def test_happy_path_no_retry(self) -> None:
        """完整覆盖 → 不触发重试, 只调 1 次 LLM (regression)."""
        from src.ingest.pre_analysis.chapter_extractors.chapter_config import (
            ChapterExtractionConfig,
        )
        from src.ingest.pre_analysis.chapter_extractors.llm_chapter import (
            llm_summarize_chapters,
        )
        from src.ingest.pre_analysis.chapter_extractors.llm_schemas import SummaryOutput

        parsed = SummaryOutput.model_validate(
            {
                "summaries": [
                    {"chapter_id": "ch_1", "summary": "s1"},
                    {"chapter_id": "ch_2", "summary": "s2"},
                    {"chapter_id": "ch_3", "summary": "s3"},
                ]
            }
        )
        mock_llm = _setup_llm_structured_mock(parsed)

        doc = _make_doc(["x"] * 10)
        chapters = [
            {"id": f"ch_{i}", "level": 1, "title": f"章{i}", "page_start": 1, "page_end": 5, "children": []}
            for i in range(1, 4)
        ]

        with patch(
            "src.ingest.pre_analysis.chapter_extractors.llm_chapter._get_llm",
            return_value=mock_llm,
        ):
            result = llm_summarize_chapters(doc, chapters, ChapterExtractionConfig())

        assert result == {"ch_1": "s1", "ch_2": "s2", "ch_3": "s3"}
        # (2026-07-09) 完整覆盖 → 不重试
        assert mock_llm.llm.with_structured_output.return_value.invoke.call_count == 1
        # prompt 不含 missing 提示
        first_prompt = mock_llm.llm.with_structured_output.return_value.invoke.call_args.args[0]
        assert "[系统校正]" not in first_prompt
