"""pre_analysis table_view 业务逻辑测试 (模式 1 mock, 0 PG/Redis).

纯函数测: parse_table_filename + extract_table_pages + build_table_page_response.
router 只做 HTTP 装, 业务逻辑拆到纯函数便于单测不连 PG / ObjectStore.
"""

from __future__ import annotations

from src.ingest.pre_analysis.table_view import (
    build_table_page_response,
    extract_table_pages,
    parse_table_filename,
)


def test_parse_table_filename_normal() -> None:
    """'tables/page-9-table-1.csv' → page 9, table 1."""
    assert parse_table_filename("tables/page-9-table-1.csv") == (9, 1)


def test_parse_table_filename_multi_digit_page() -> None:
    """页号/表号支持多位数."""
    assert parse_table_filename("tables/page-123-table-45.csv") == (123, 45)


def test_parse_table_filename_invalid_raises() -> None:
    """非法格式抛 ValueError."""
    import pytest

    with pytest.raises(ValueError, match="Invalid table filename"):
        parse_table_filename("chapters.json")
    with pytest.raises(ValueError, match="Invalid table filename"):
        parse_table_filename("tables/page-9.csv")  # 缺 -table-M
    with pytest.raises(ValueError, match="Invalid table filename"):
        parse_table_filename("tables/page-x-table-1.csv")  # 非数字


def test_extract_table_pages_unique_sorted() -> None:
    """从 output_files 提取去重 + 排序 + total."""
    output_files = [
        {"kind": "table", "filename": "tables/page-9-table-1.csv"},
        {"kind": "table", "filename": "tables/page-9-table-2.csv"},  # 同页 2 张表
        {"kind": "table", "filename": "tables/page-3-table-1.csv"},
        {"kind": "table", "filename": "tables/page-21-table-1.csv"},
        {"kind": "chapter_structure", "filename": "chapters.json"},  # 非 table, 跳过
        {"kind": "flagged_paragraphs", "filename": "flagged.csv"},  # 非 table, 跳过
    ]
    pages, total = extract_table_pages(output_files)
    assert pages == [3, 9, 21]  # 去重 + 排序
    assert total == 4  # 4 个 table 文件


def test_extract_table_pages_empty() -> None:
    """空 output_files → ([], 0)."""
    assert extract_table_pages([]) == ([], 0)
    assert extract_table_pages([{"kind": "chapter_structure", "filename": "x"}]) == ([], 0)


def test_extract_table_pages_skips_invalid_filenames() -> None:
    """非法 filename 跳过 (e.g. runner 写错格式)."""
    output_files = [
        {"kind": "table", "filename": "tables/page-9-table-1.csv"},
        {"kind": "table", "filename": "bad.csv"},  # 非法, 跳过
    ]
    pages, total = extract_table_pages(output_files)
    assert pages == [9]
    assert total == 1


def test_build_table_page_response_filters_and_parses() -> None:
    """build_table_page_response: 过滤该页 CSV + csv.DictReader 解析."""
    task = {
        "output_files": [
            {
                "kind": "table",
                "filename": "tables/page-9-table-1.csv",
                "uri": "s3://x/tables/page-9-table-1.csv",
                "size_bytes": 100,
            },
            {
                "kind": "table",
                "filename": "tables/page-9-table-2.csv",
                "uri": "s3://x/tables/page-9-table-2.csv",
                "size_bytes": 200,
            },
            {
                "kind": "table",
                "filename": "tables/page-3-table-1.csv",  # 其它页, 跳过
                "uri": "s3://x/tables/page-3-table-1.csv",
                "size_bytes": 50,
            },
            {
                "kind": "chapter_structure",
                "filename": "chapters.json",  # 非 table, 跳过
                "uri": "s3://x/chapters.json",
                "size_bytes": 1000,
            },
        ],
    }
    csv_1 = b"col_a,col_b\nv1,v2\nv3,v4\n"
    csv_2 = b"col_x\nfoo\nbar\n"
    csv_contents = {
        "tables/page-9-table-1.csv": csv_1,
        "tables/page-9-table-2.csv": csv_2,
    }

    resp = build_table_page_response(task, 9, csv_contents)

    assert resp["page"] == 9
    assert len(resp["tables"]) == 2
    # 按 table_index 升序
    assert resp["tables"][0]["table_index"] == 1
    assert resp["tables"][0]["filename"] == "tables/page-9-table-1.csv"
    assert resp["tables"][0]["columns"] == ["col_a", "col_b"]
    assert resp["tables"][0]["rows"] == [
        {"col_a": "v1", "col_b": "v2"},
        {"col_a": "v3", "col_b": "v4"},
    ]
    assert resp["tables"][1]["table_index"] == 2
    assert resp["tables"][1]["rows"] == [{"col_x": "foo"}, {"col_x": "bar"}]


def test_build_table_page_response_no_tables_raises_keyerror() -> None:
    """指定页没表格 → KeyError."""
    task = {"output_files": [{"kind": "table", "filename": "tables/page-3-table-1.csv"}]}
    import pytest

    with pytest.raises(KeyError, match="No tables found for page 99"):
        build_table_page_response(task, 99, {})
