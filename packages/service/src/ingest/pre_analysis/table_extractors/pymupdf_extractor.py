"""PymupdfTableExtractor (2026-07-06).

默认后端, 复用 pymupdf find_tables().
"""

from __future__ import annotations

import pymupdf

from .base import TableData, TableExtractor


class PymupdfTableExtractor(TableExtractor):
    """pymupdf find_tables() 适配器.

    优先复用已打开 pymupdf.Document (避免重新打开 PDF, 节省 IO + 内存).

    pymupdf 后端无调参 (find_tables() 内部自适应), params 忽略.
    """

    def __init__(self, params: dict) -> None:
        self._params = params

    def extract(
        self,
        pdf_path: str,
        *,
        _pymupdf_doc: object | None = None,
        **params: object,
    ) -> list[TableData]:
        """提取所有表格. PDF 无表格 → 返 [].

        Args:
            pdf_path: PDF 文件路径 (当 _pymupdf_doc 缺时, 自己开).
            _pymupdf_doc: 已打开 pymupdf.Document (推荐传, runner 已开过).
            **params: 预留, pymupdf 后端无调参.

        Returns:
            list[TableData] 表格列表.
        """
        own_doc = _pymupdf_doc is None
        doc: pymupdf.Document = _pymupdf_doc if _pymupdf_doc is not None else pymupdf.open(pdf_path)  # type: ignore[arg-type]
        try:
            raw: list[TableData] = []
            for page_idx, page in enumerate(doc):  # type: ignore[arg-type]
                for table_idx, table in enumerate(page.find_tables().tables):  # type: ignore[union-attr]
                    rows: list[list[str]] = [list(r) for r in table.extract()]
                    raw.append(TableData(page_no=page_idx + 1, table_no=table_idx + 1, rows=rows))
            # (2026-07-09) 抽到 TableData.filter_valid, 3 个 extractor 共用
            return TableData.filter_valid(raw, backend_name="pymupdf")
        finally:
            if own_doc:
                doc.close()
