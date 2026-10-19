"""llm_schemas.py 测试 (2026-07-09).

Pydantic v2 覆盖:
- ChapterEntry: 正常 / level 越界 / title 空
- LLMChapterOutput: list 解析 / 空
- SummaryItem: 正常
- SummaryOutput: batch 解析
"""

from __future__ import annotations

from pydantic import ValidationError


class TestChapterEntry:
    def test_normal(self) -> None:
        """正常字段."""
        from src.ingest.pre_analysis.chapter_extractors.llm_schemas import ChapterEntry

        e = ChapterEntry(level=1, title="第1章", page_start=1)
        assert e.level == 1
        assert e.title == "第1章"
        assert e.page_start == 1

    def test_level_out_of_range(self) -> None:
        """level < 1 或 > 6 → ValidationError."""
        from src.ingest.pre_analysis.chapter_extractors.llm_schemas import ChapterEntry

        try:
            ChapterEntry(level=0, title="x", page_start=1)
        except ValidationError:
            pass
        else:
            raise AssertionError("expected ValidationError for level=0")

        try:
            ChapterEntry(level=7, title="x", page_start=1)
        except ValidationError:
            pass
        else:
            raise AssertionError("expected ValidationError for level=7")

    def test_empty_title(self) -> None:
        """title 空 → ValidationError."""
        from src.ingest.pre_analysis.chapter_extractors.llm_schemas import ChapterEntry

        try:
            ChapterEntry(level=1, title="", page_start=1)
        except ValidationError:
            pass
        else:
            raise AssertionError("expected ValidationError for empty title")

    def test_page_start_invalid(self) -> None:
        """page_start < 1 → ValidationError."""
        from src.ingest.pre_analysis.chapter_extractors.llm_schemas import ChapterEntry

        try:
            ChapterEntry(level=1, title="x", page_start=0)
        except ValidationError:
            pass
        else:
            raise AssertionError("expected ValidationError for page_start=0")


class TestLLMChapterOutput:
    def test_normal(self) -> None:
        """list 解析."""
        from src.ingest.pre_analysis.chapter_extractors.llm_schemas import LLMChapterOutput

        out = LLMChapterOutput.model_validate(
            {
                "chapters": [
                    {"level": 1, "title": "第1章", "page_start": 1},
                    {"level": 2, "title": "1.1节", "page_start": 2},
                ]
            }
        )
        assert len(out.chapters) == 2
        assert out.chapters[0].title == "第1章"

    def test_empty(self) -> None:
        """空 list 默认."""
        from src.ingest.pre_analysis.chapter_extractors.llm_schemas import LLMChapterOutput

        out = LLMChapterOutput.model_validate({})
        assert out.chapters == []


class TestSummaryItem:
    def test_normal(self) -> None:
        """正常字段."""
        from src.ingest.pre_analysis.chapter_extractors.llm_schemas import SummaryItem

        s = SummaryItem(chapter_id="ch_1", summary="本章介绍...")
        assert s.chapter_id == "ch_1"
        assert s.summary == "本章介绍..."

    def test_too_long_summary(self) -> None:
        """summary > 500 字 → ValidationError."""
        from src.ingest.pre_analysis.chapter_extractors.llm_schemas import SummaryItem

        try:
            SummaryItem(chapter_id="ch_1", summary="x" * 501)
        except ValidationError:
            pass
        else:
            raise AssertionError("expected ValidationError for summary too long")


class TestSummaryOutput:
    def test_normal(self) -> None:
        """批量解析."""
        from src.ingest.pre_analysis.chapter_extractors.llm_schemas import SummaryOutput

        out = SummaryOutput.model_validate(
            {
                "summaries": [
                    {"chapter_id": "ch_1", "summary": "本章介绍..."},
                    {"chapter_id": "ch_2", "summary": "本章方法..."},
                ]
            }
        )
        assert len(out.summaries) == 2
        assert out.summaries[0].chapter_id == "ch_1"

    def test_empty(self) -> None:
        """空 batch."""
        from src.ingest.pre_analysis.chapter_extractors.llm_schemas import SummaryOutput

        out = SummaryOutput.model_validate({})
        assert out.summaries == []
