# packages/service/src/ingest/pre_analysis/chapter_extractors/__init__.py
"""章节提取器工厂 (2026-07-08).

(2026-07-09 PDF 章节树状化) extract_chapters 加 max_level 参数;
后续扩展加新 fallback 文件 (e.g. toc_page.py / font_size.py / llm_refine.py),
跟 table_extractors/ 平级.

runner.py 调顶层 `extract_chapters(doc, ...)`, 业务不直接 import 内部类.
"""

from __future__ import annotations

from typing import Any

import pymupdf
from loguru import logger

from .base import ChapterExtractor
from .outline import OutlineExtractor


def get_chapter_extractor(strategy: str = "outline") -> ChapterExtractor:
    """策略工厂. 当前只支持 outline, 后续扩展加分支.

    Raises:
        ValueError: 未知 strategy.
    """
    if strategy == "outline":
        return OutlineExtractor()
    raise ValueError(f"未知章节策略: {strategy!r}, 当前支持: ['outline']")


def extract_chapters(
    doc: pymupdf.Document,
    strategy: str = "outline",
    max_level: int | None = None,
) -> list[dict]:
    """顶层入口, runner.py 调这个.

    Args:
        doc: pymupdf Document (已 open).
        strategy: 策略名, 默认 'outline'.
        max_level: 最大层级 (1-6), 透传给 extractor.

    Returns:
        list[dict]: 嵌套树节点 [{id, level, title, page_start, page_end, children}, ...].
    """
    extractor = get_chapter_extractor(strategy)
    kwargs: dict[str, Any] = {}
    if max_level is not None:
        kwargs["max_level"] = max_level
    chapters = extractor.extract(doc, **kwargs)
    logger.info("章节提取完成 strategy={} chapters={}", extractor.name, len(chapters))
    return chapters


def count_chapters(chapters: list[dict]) -> int:
    """(2026-07-09) 递归统计所有章节节点数 (含嵌套子章节).

    跟 chapters_section._build_payload.payload.total_chapters 同口径.
    列表 / 详情 / message / index.json / DB summary 都用这个, 避免顶层 vs 嵌套漂移.
    """
    return sum(1 + count_chapters(n["children"]) for n in chapters)


__all__ = [
    "ChapterExtractor",
    "OutlineExtractor",
    "extract_chapters",
    "get_chapter_extractor",
    "count_chapters",
]
