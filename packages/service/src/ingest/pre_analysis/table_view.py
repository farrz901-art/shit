"""pre_analysis 表格视图业务逻辑 (2026-07-09 新增).

提供 3 个纯函数:
- `parse_table_filename(filename)` → `(page_num, table_index)` 元组
- `extract_table_pages(output_files)` → `(pages: list[int], total: int)`
- `build_table_page_response(task, page_num, csv_contents)` → 表格数据响应 dict

跟 HTTP 解耦, router 直接 import 调用, 单测不依赖 FastAPI / PG / ObjectStore.
"""

from __future__ import annotations

import csv
import io
import re
from typing import Any

_TABLE_FILENAME_RE = re.compile(r"^tables/page-(\d+)-table-(\d+)\.csv$")


def parse_table_filename(filename: str) -> tuple[int, int]:
    """从表格 CSV 文件名提取 (页号, 表索引).

    Args:
        filename: 产物文件名 (e.g. "tables/page-9-table-1.csv")

    Returns:
        (page_num, table_index) 元组.

    Raises:
        ValueError: 文件名不符合 `tables/page-{N}-table-{M}.csv` 格式.
    """
    match = _TABLE_FILENAME_RE.match(filename)
    if not match:
        raise ValueError(f"Invalid table filename: {filename!r} (expected 'tables/page-{{N}}-table-{{M}}.csv')")
    return int(match.group(1)), int(match.group(2))


def extract_table_pages(output_files: list[dict[str, Any]]) -> tuple[list[int], int]:
    """从 output_files 提取去重 + 排序后的有表格页号列表.

    只看 `kind == "table"` 条目. 非法 filename 静默跳过 (runner 异常产物
    不应阻断整个 pages 接口).

    Args:
        output_files: PreAnalysisTask.output_files 列表.

    Returns:
        (pages, total): pages 是排序去重的页号数组; total 是表格文件总数
            (含同页多张表).
    """
    pages: set[int] = set()
    total = 0
    for f in output_files:
        if f.get("kind") != "table":
            continue
        filename = f.get("filename", "")
        try:
            page_num, _ = parse_table_filename(filename)
        except ValueError:
            continue
        pages.add(page_num)
        total += 1
    return sorted(pages), total


def build_table_page_response(
    task: dict[str, Any],
    page_num: int,
    csv_contents: dict[str, bytes],
) -> dict[str, Any]:
    """构造指定页的表格数据响应 JSON.

    Args:
        task: PreAnalysisTask dict (含 output_files).
        page_num: PDF 页号.
        csv_contents: filename → CSV 字节内容 dict (调用方负责从 ObjectStore 读).

    Returns:
        {"page": int, "tables": [TableItem, ...]} 格式 dict.

    Raises:
        KeyError: 该页没有任何表格条目.
    """
    tables_for_page = []
    for f in task["output_files"]:
        if f.get("kind") != "table":
            continue
        try:
            f_page, f_idx = parse_table_filename(f["filename"])
        except ValueError:
            continue
        if f_page != page_num:
            continue
        csv_bytes = csv_contents[f["filename"]]
        # python stdlib csv.DictReader — 不引第三方
        text = csv_bytes.decode("utf-8")
        reader = csv.DictReader(io.StringIO(text))
        rows = [dict(r) for r in reader]  # materialize (reader 是一次性的)
        columns = reader.fieldnames or []
        tables_for_page.append(
            {
                "table_index": f_idx,
                "filename": f["filename"],
                "size_bytes": f.get("size_bytes", 0),
                "columns": list(columns),
                "rows": rows,
            }
        )

    if not tables_for_page:
        raise KeyError(f"No tables found for page {page_num}")

    # 按 table_index 升序
    tables_for_page.sort(key=lambda t: t["table_index"])
    return {"page": page_num, "tables": tables_for_page}


__all__ = [
    "parse_table_filename",
    "extract_table_pages",
    "build_table_page_response",
]
