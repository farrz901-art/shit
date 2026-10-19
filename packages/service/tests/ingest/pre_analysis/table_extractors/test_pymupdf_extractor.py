"""PymupdfTableExtractor 测试 (mode 1 mock doc + 真 PDF fixture).

覆盖:
- 复用已开 doc (`_pymupdf_doc` 传入) → 不重开, 走 page.find_tables
- 自身开 doc (`_pymupdf_doc=None`) → 走 pymupdf.open
"""

from __future__ import annotations

from pathlib import Path

import pymupdf

FIXTURE_PDF = Path(__file__).resolve().parents[2] / "fixtures" / "d81_dummy.pdf"


def test_extract_with_injected_doc_returns_table_data() -> None:
    """复用已开 doc 路径."""
    from src.ingest.pre_analysis.table_extractors.pymupdf_extractor import (
        PymupdfTableExtractor,
    )

    doc = pymupdf.open(str(FIXTURE_PDF))
    try:
        extractor = PymupdfTableExtractor({})
        result = extractor.extract(str(FIXTURE_PDF), _pymupdf_doc=doc)
        # d81_dummy.pdf 第 3 页有 1 表格
        assert isinstance(result, list)
        for td in result:
            # (2026-07-09) page_no 跨页合并后是 str (e.g. "5+6"), 只对 int 守卫
            if isinstance(td.page_no, int):
                assert td.page_no >= 1
            assert td.table_no >= 1
            assert isinstance(td.rows, list)
            assert all(isinstance(row, list) for row in td.rows)
    finally:
        doc.close()


def test_extract_without_doc_opens_file() -> None:
    """不传 _pymupdf_doc → pymupdf.open(pdf_path)."""
    from src.ingest.pre_analysis.table_extractors.pymupdf_extractor import (
        PymupdfTableExtractor,
    )

    extractor = PymupdfTableExtractor({})
    result = extractor.extract(str(FIXTURE_PDF))
    assert isinstance(result, list)


def test_extract_with_mock_doc_only_1_table_in_d81() -> None:
    """d81_dummy.pdf fixture 已知含 1 表, 验证实际拿到 1 条 TableData."""
    from src.ingest.pre_analysis.table_extractors.pymupdf_extractor import (
        PymupdfTableExtractor,
    )

    doc = pymupdf.open(str(FIXTURE_PDF))
    try:
        extractor = PymupdfTableExtractor({})
        result = extractor.extract(str(FIXTURE_PDF), _pymupdf_doc=doc)
        # d81_dummy 在 page 3 有 1 表格
        assert len(result) >= 1
        # 第 1 个表格是 page 3 table 1
        assert result[0].page_no == 3
        assert result[0].table_no == 1
        # 至少 1 行
        assert len(result[0].rows) >= 1
    finally:
        doc.close()


# (2026-07-09) extract() 内部退化表过滤


def test_extract_filters_degenerate_tables(monkeypatch) -> None:
    """mock page.find_tables 返 1xN 退化表 + 2x2 有效表 -> 只返有效表.

    退化表 (1xN / 1x1 / 2x1) 全部在 extract() 内部被 TableData.is_valid_table 过滤.
    """
    from unittest.mock import MagicMock

    from src.ingest.pre_analysis.table_extractors.pymupdf_extractor import (
        PymupdfTableExtractor,
    )

    # 构造 mock doc: 1 页, find_tables().tables 返 3 个 table: 退化 + 退化 + 有效
    fake_table_degenerate_1xn = MagicMock()
    fake_table_degenerate_1xn.extract.return_value = [["a", "b", "c"]]  # 1xN 退化

    fake_table_degenerate_2x1 = MagicMock()
    fake_table_degenerate_2x1.extract.return_value = [["x"], ["y"]]  # 2x1 退化

    fake_table_valid = MagicMock()
    fake_table_valid.extract.return_value = [["h1", "h2"], ["v1", "v2"]]  # 2x2 有效

    fake_page = MagicMock()
    fake_page.find_tables.return_value.tables = [
        fake_table_degenerate_1xn,
        fake_table_degenerate_2x1,
        fake_table_valid,
    ]

    fake_doc = MagicMock()
    fake_doc.__iter__ = lambda self: iter([fake_page])  # doc 只 1 页

    extractor = PymupdfTableExtractor({})
    result = extractor.extract("fake.pdf", _pymupdf_doc=fake_doc)

    # 只 valid 表 (2x2) 进了结果
    assert len(result) == 1
    assert result[0].page_no == 1
    assert result[0].table_no == 3  # 退化表虽丢弃, table_no 仍递增
    assert result[0].rows == [["h1", "h2"], ["v1", "v2"]]
