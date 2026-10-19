"""realign_columns 测试 (mode 1 mock).

(2026-07-09) 列重对齐单元测试. 解决 Camelot 各 flavor 输出列数不固定导致列错位.
"""

from __future__ import annotations

from src.ingest.pre_analysis.table_extractors.base import TableData
from src.ingest.pre_analysis.table_extractors.camelot_extractor import realign_columns


def test_realign_columns_less_cols_appends_empty() -> None:
    """body 行列数 < 表头 → 末尾补空字符串."""
    t = TableData(
        page_no=1,
        table_no=1,
        rows=[["A", "B", "C", "D"], ["1", "2"], ["3", "4"]],
    )
    result = realign_columns(t)
    assert result.rows == [
        ["A", "B", "C", "D"],
        ["1", "2", "", ""],
        ["3", "4", "", ""],
    ]
    # 不修改入参 (frozen)
    assert result is not t


def test_realign_columns_more_cols_merges_to_last() -> None:
    """body 行列数 > 表头 → 多余 cell 拼到最后 1 列表头列."""
    t = TableData(
        page_no=1,
        table_no=1,
        rows=[["A", "B", "C", "D"], ["1", "2", "3", "extra1", "extra2"]],
    )
    result = realign_columns(t)
    assert result.rows == [
        ["A", "B", "C", "D"],
        ["1", "2", "3", "extra1 extra2"],
    ]


def test_realign_columns_equal_no_change() -> None:
    """body 行列数 = 表头 → 原样保留."""
    t = TableData(
        page_no=1,
        table_no=1,
        rows=[["A", "B"], ["1", "2"], ["3", "4"]],
    )
    result = realign_columns(t)
    assert result.rows == [["A", "B"], ["1", "2"], ["3", "4"]]


def test_realign_columns_empty_header_uses_max() -> None:
    """表头全空白 → header_cols 用 max 行宽, 不强制 0."""
    t = TableData(
        page_no=1,
        table_no=1,
        rows=[["", "", ""], ["1", "2", "3"], ["4", "5"]],
    )
    result = realign_columns(t)
    # header 表头 = 全空白 → header_cols = 3 (max)
    assert result.rows == [
        ["", "", ""],
        ["1", "2", "3"],
        ["4", "5", ""],
    ]


def test_realign_columns_single_col_returns_unchanged() -> None:
    """单列表 (1 列 < 2) → filter_valid 会过滤, 此处不重对齐."""
    t = TableData(page_no=1, table_no=1, rows=[["a"], ["b"], ["c"]])
    result = realign_columns(t)
    # header_cols=1 < 2 → 直接返原 t (无新对象)
    assert result.rows == t.rows


def test_realign_columns_empty_rows_returns_unchanged() -> None:
    """空表 → 返原 t."""
    t = TableData(page_no=1, table_no=1, rows=[])
    result = realign_columns(t)
    assert result.rows == []


def test_realign_columns_partial_blank_header_uses_it() -> None:
    """表头有任意非空 cell → 用表头列数."""
    t = TableData(
        page_no=1,
        table_no=1,
        rows=[["A", "", ""], ["1", "2", "3"]],  # 表头 3 列 (其中 2 个空)
    )
    result = realign_columns(t)
    assert result.rows == [["A", "", ""], ["1", "2", "3"]]  # 已是 3 列, 无变化
