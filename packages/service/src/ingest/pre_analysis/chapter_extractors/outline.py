# packages/service/src/ingest/pre_analysis/chapter_extractors/outline.py
"""OutlineExtractor: pymupdf get_toc() → 嵌套章节树 (2026-07-08 + 2026-07-09).

(2026-07-09 PDF 章节树状化) 加 max_level 参数支持层级截断.
PDF 无 outline 时返 [], 上层决定是否走 fallback.
"""

from __future__ import annotations

from typing import Any

import pymupdf
from loguru import logger

from .base import ChapterExtractor
from .chapter_tree import build_chapter_tree


class OutlineExtractor(ChapterExtractor):
    """pymupdf get_toc() → 嵌套章节树. max_level 截断层级.

    PDF 无 outline → 返 [] (上层决定 fallback, 当前没 fallback 链就走 empty).
    """

    name = "pdf_outline"

    def extract(self, doc: pymupdf.Document, max_level: int | None = None) -> list[dict]:
        """调 doc.get_toc(), 转嵌套树. max_level None → 默认 6.

        Args:
            doc: pymupdf Document (已 open).
            max_level: 最大层级 (1-6), None 时用 build_chapter_tree 默认 6.

        Returns:
            list[dict] 嵌套树节点 [{id, level, title, page_start, page_end, children}, ...].
        """
        toc_raw: list[list[Any]] = doc.get_toc()
        if not toc_raw:
            logger.warning("PDF 无 outline (get_toc 返空), chapter_structure 标空")
            return []
        # PyMuPDF get_toc 返 list[list[Any]], 转 tuple 喂 build_chapter_tree
        flat: list[tuple[int, str, int]] = [(int(r[0]), str(r[1]), int(r[2])) for r in toc_raw]
        total_pages = len(doc)
        kwargs: dict[str, Any] = {"raw_toc": flat, "total_pages": total_pages}
        if max_level is not None:
            kwargs["max_level"] = max_level
        return build_chapter_tree(**kwargs)
