"""extract() 并发 + 拆合并测试 (mode 1 mock).

(2026-07-09) 验证:
- _unmerge_combined_with_ml 触发条件 + ml 重识别替换
- CamelotTableExtractor.extract 改为按页并行 (4 worker)
- realign_columns 在结果输出前 per-table 应用
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from src.ingest.pre_analysis.table_extractors.base import TableData
from src.ingest.pre_analysis.table_extractors.camelot_extractor import (
    CamelotTableExtractor,
    _unmerge_combined_with_ml,
)

# (2026-07-09) _unmerge_combined_with_ml 触发条件


def test_unmerge_combined_with_ml_merges_replace() -> None:
    """current_tables 含 1×1 长文本 → 调 ml → 返 ml 结果替换."""
    current = [TableData(page_no=1, table_no=1, rows=[["longtext " * 30 + "\n" * 10]])]
    expected_ml = [
        TableData(page_no=1, table_no=1, rows=[["col1", "col2"], ["val1", "val2"]]),
        TableData(page_no=1, table_no=2, rows=[["col1", "col2"], ["val3", "val4"]]),
    ]

    with patch(
        "src.ingest.pre_analysis.table_extractors.camelot_extractor._run_camelot_single_page",
        return_value=expected_ml,
    ) as mock_run:
        result = _unmerge_combined_with_ml("/tmp/fake.pdf", page=1, current_tables=current, params={})

    assert len(result) == 2
    assert result[0].rows == [["col1", "col2"], ["val1", "val2"]]
    mock_run.assert_called_once()
    call_args = mock_run.call_args
    assert call_args.kwargs.get("flavor") == "ml" or call_args.args[2] == "ml"


def test_unmerge_combined_with_ml_no_merged_returns_current() -> None:
    """current_tables 全是正常表 → 不调 ml, 返 current."""
    current = [
        TableData(page_no=1, table_no=1, rows=[["a", "b"], ["1", "2"]]),
        TableData(page_no=1, table_no=2, rows=[["c", "d"], ["3", "4"]]),
    ]
    with patch(
        "src.ingest.pre_analysis.table_extractors.camelot_extractor._run_camelot_single_page",
    ) as mock_run:
        result = _unmerge_combined_with_ml("/tmp/fake.pdf", page=1, current_tables=current, params={})
    assert result == current
    mock_run.assert_not_called()


def test_unmerge_combined_with_ml_ml_no_result_returns_current() -> None:
    """触发但 ml 无结果 → 返 current (不丢失已有数据)."""
    current = [TableData(page_no=1, table_no=1, rows=[["longtext " * 30 + "\n" * 10]])]
    with patch(
        "src.ingest.pre_analysis.table_extractors.camelot_extractor._run_camelot_single_page",
        return_value=[],
    ):
        result = _unmerge_combined_with_ml("/tmp/fake.pdf", page=1, current_tables=current, params={})
    assert result == current


# (2026-07-09) extract 并发 (ThreadPoolExecutor 4 worker)


def _mock_pymupdf_doc_with_pages(page_count: int) -> object:
    """构造 pymupdf doc 桩: 报 page_count + 任意 page_ok load_page."""

    n = page_count  # (2026-07-09) 局部变量, 避免 class body 内 page_count 形参名跟 class 属性同名导致 NameError

    class _MockDoc:
        page_count = n

        def load_page(self, page_idx: int) -> object:  # noqa: ARG002
            return _MockPage()

    class _MockPage:
        def find_tables(self, strategy: str) -> list:  # noqa: ARG002
            return []  # 后续 task 接管 strategy="text" 增强, 此处先返 []

    return _MockDoc()


def test_extract_runs_pages_in_parallel(monkeypatch: pytest.MonkeyPatch) -> None:
    """extract 调度 4 worker 跑 4 页, 不串行."""
    import time

    call_times: list[float] = []

    def fake_extract_single_page(path: str, page: int, params: dict) -> list[TableData]:  # noqa: ARG001
        call_times.append(time.time())
        time.sleep(0.1)  # 每页 100ms
        return []

    monkeypatch.setattr(
        "src.ingest.pre_analysis.table_extractors.camelot_extractor._extract_single_page",
        fake_extract_single_page,
    )

    doc = _mock_pymupdf_doc_with_pages(page_count=4)
    extractor = CamelotTableExtractor({"flavor": "lattice"})
    start = time.time()
    result = extractor.extract("/tmp/fake.pdf", _pymupdf_doc=doc)
    elapsed = time.time() - start

    # 4 页 × 100ms 串行 = 400ms; 4 并发 ≈ 100ms + 开销, 应 < 250ms
    assert elapsed < 0.25
    assert result == []
    assert len(call_times) == 4


def test_extract_applies_realign_columns(monkeypatch: pytest.MonkeyPatch) -> None:
    """extract 后处理: per-table 调 realign_columns."""

    def fake_extract_single_page(path: str, page: int, params: dict) -> list[TableData]:  # noqa: ARG001
        return [TableData(page_no=page, table_no=1, rows=[["A", "B"], ["1"]])]
        # ← 2 列 × 1 行, 触发补空

    monkeypatch.setattr(
        "src.ingest.pre_analysis.table_extractors.camelot_extractor._extract_single_page",
        fake_extract_single_page,
    )

    doc = _mock_pymupdf_doc_with_pages(page_count=1)
    extractor = CamelotTableExtractor({"flavor": "lattice"})
    result = extractor.extract("/tmp/fake.pdf", _pymupdf_doc=doc)

    assert len(result) == 1
    assert result[0].rows == [["A", "B"], ["1", ""]]  # 已补空


def test_extract_unmerge_triggered_replaces_with_ml(monkeypatch: pytest.MonkeyPatch) -> None:
    """某页有 1×1 长文本 → 该页触发 ml 重识别替换."""
    merged_table = TableData(
        page_no=1,
        table_no=1,
        rows=[["longtext " * 30 + "\n" * 10]],
    )

    def fake_extract_single_page(path: str, page: int, params: dict) -> list[TableData]:
        if page == 1:
            return [merged_table]
        return []

    def fake_unmerge(path: str, page: int, current: list[TableData], params: dict) -> list[TableData]:
        if page == 1:
            return [
                TableData(page_no=1, table_no=1, rows=[["c1", "c2"], ["v1", "v2"]]),
                TableData(page_no=1, table_no=2, rows=[["c1", "c2"], ["v3", "v4"]]),
            ]
        return current

    monkeypatch.setattr(
        "src.ingest.pre_analysis.table_extractors.camelot_extractor._extract_single_page",
        fake_extract_single_page,
    )
    monkeypatch.setattr(
        "src.ingest.pre_analysis.table_extractors.camelot_extractor._unmerge_combined_with_ml",
        fake_unmerge,
    )

    doc = _mock_pymupdf_doc_with_pages(page_count=1)
    extractor = CamelotTableExtractor({"flavor": "lattice"})
    result = extractor.extract("/tmp/fake.pdf", _pymupdf_doc=doc)

    assert len(result) == 2
    assert result[0].rows == [["c1", "c2"], ["v1", "v2"]]
    assert result[1].rows == [["c1", "c2"], ["v3", "v4"]]
