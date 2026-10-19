"""LLM 章节输出 Pydantic schema (2026-07-09, PDF 章节树状化+LLM增强).

给 LLM with_structured_output() 用, 强制 JSON shape.
- ChapterEntry: 单个章节 (level, title, page_start)
- LLMChapterOutput: llm_refine_chapters 输出 (chapters: list[ChapterEntry])
- SummaryItem: 单章摘要 (chapter_id, summary)
- SummaryOutput: llm_summarize_chapters 输出 (summaries: list[SummaryItem])
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ChapterEntry(BaseModel):
    """LLM 推断的单条章节."""

    level: int = Field(ge=1, le=6, description="1-6, 1 是顶层章")
    title: str = Field(min_length=1, max_length=200, description="章节标题")
    page_start: int = Field(ge=1, description="起始页 (1-based)")


class LLMChapterOutput(BaseModel):
    """llm_refine_chapters 输出: LLM 推断的章节列表."""

    chapters: list[ChapterEntry] = Field(
        default_factory=list,
        description="推断出的章节, 按 PDF 顺序, 层级一致地展开",
    )


class SummaryItem(BaseModel):
    """单章摘要 (回写 chapter 时用 chapter_id 关联)."""

    chapter_id: str = Field(min_length=1, description="对应章节的 id (ch_N)")
    summary: str = Field(min_length=1, max_length=500, description="2-3 句中文摘要")


class SummaryOutput(BaseModel):
    """llm_summarize_chapters 输出: 一批章节摘要."""

    summaries: list[SummaryItem] = Field(
        default_factory=list,
        description="章节摘要列表, 单 batch 内全部章节",
    )


__all__ = ["ChapterEntry", "LLMChapterOutput", "SummaryItem", "SummaryOutput"]
