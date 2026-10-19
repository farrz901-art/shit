# packages/service/src/ingest/pre_analysis/chapter_extractors/base.py
"""章节提取策略接口 (2026-07-08).

(2026-07-09 PDF 章节树状化) extract() 加 max_level 参数支持层级截断.
后续每个 fallback 1 个实现 (outline / toc_page / font_size), 都在 chapter_extractors/ 加新文件.
"""

from __future__ import annotations

import abc

import pymupdf


class ChapterExtractor(abc.ABC):
    """PDF 章节提取策略.

    Attributes:
        name: 策略名, 用于日志 + chapter_structure.json 的 toc_source 字段.
              当前实现必须保持跟 toc_source 字符串一致 (e.g. 'pdf_outline').
    """

    name: str

    @abc.abstractmethod
    def extract(self, doc: pymupdf.Document, max_level: int | None = None) -> list[dict]:
        """从 PDF 提取章节.

        Args:
            doc: pymupdf Document (已 open, 由调用方负责 close).
            max_level: 最大层级 (1-6), None 走实现默认.

        Returns:
            list[dict]: 嵌套树节点 [{id, level, title, page_start, page_end, children}, ...].
            返 [] 表示该策略不适用 (不抛异常), 由上层决定是否 fallback.
        """
