"""(2026-07-09) C1 _stack_contiguous_in_flavor 测试.

自实现的列数匹配合并, 不依赖 camelot TableList.stack_contiguous() API
(camelot 2.0 API 未在本机验证).
"""

from __future__ import annotations

from src.ingest.pre_analysis.table_extractors.base import TableData
from src.ingest.pre_analysis.table_extractors.camelot_extractor import (
    _stack_contiguous_in_flavor,
)


def test_stack_contiguous_merges_consecutive_same_columns() -> None:
    """2 张相邻页表, 列数相等 → 合并成 1 张, page_no='1+2'."""
    tables = [
        TableData(page_no=1, table_no=1, rows=[["a", "b"], ["1", "2"]]),
        TableData(page_no=2, table_no=1, rows=[["3", "4"], ["5", "6"]]),
    ]
    result = _stack_contiguous_in_flavor(tables)
    assert len(result) == 1, f"应合并成 1 张, 实际 {len(result)}"
    assert result[0].page_no == "1+2", f"page_no 应为 '1+2', 实际 {result[0].page_no}"
    assert result[0].rows == [["a", "b"], ["1", "2"], ["3", "4"], ["5", "6"]]


def test_stack_contiguous_skips_non_consecutive_pages() -> None:
    """2 张非相邻页表 (page 1 和 page 3) → 不合并."""
    tables = [
        TableData(page_no=1, table_no=1, rows=[["a", "b"]]),
        TableData(page_no=3, table_no=1, rows=[["c", "d"]]),
    ]
    result = _stack_contiguous_in_flavor(tables)
    assert len(result) == 2, f"非相邻不应合并, 实际 {len(result)} 张"
    assert result[0].page_no == 1
    assert result[1].page_no == 3


def test_stack_contiguous_skips_different_column_counts() -> None:
    """2 张相邻页表, 列数不等 → 不合并."""
    tables = [
        TableData(page_no=1, table_no=1, rows=[["a", "b", "c"]]),  # 3 列
        TableData(page_no=2, table_no=1, rows=[["d", "e"]]),  # 2 列
    ]
    result = _stack_contiguous_in_flavor(tables)
    assert len(result) == 2, f"列数不等不应合并, 实际 {len(result)}"


def test_stack_contiguous_empty_input() -> None:
    """空输入 → 空输出, 不崩."""
    result = _stack_contiguous_in_flavor([])
    assert result == []


def test_stack_contiguous_skips_already_merged_pages() -> None:
    """page_no 已是 str 的表 (前一轮合并过) → 不再合并."""
    tables = [
        TableData(page_no="1+2", table_no=1, rows=[["a", "b"]]),
        TableData(page_no=3, table_no=1, rows=[["c", "d"]]),
    ]
    result = _stack_contiguous_in_flavor(tables)
    # str page_no 跳过, 不会拼成 "1+2+3"
    assert len(result) == 2
    assert result[0].page_no == "1+2"
    assert result[1].page_no == 3
