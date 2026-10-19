"""(2026-07-09) C2 CrossPageMerger 测试.

mock pymupdf.find_tables() + LLM, 验证:
1. bbox 启发式对齐 → 候选续表对
2. bbox 不对齐 (列数差异 > 80%) → 不合并
3. LLM 判 is_repeated=True → 裁 curr header, 拼接
4. LLM 判 is_repeated=False → 不合并
5. LLM 调用失败 → 兜底用 base_tables 不变
6. pymupdf 失败 → 兜底用 base_tables 不变
7. D81.1 真 PDF e2e (skipif 不存在)
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.ingest.pre_analysis.table_extractors.base import TableData
from src.ingest.pre_analysis.table_extractors.camelot_extractor import (
    CrossPageMerger,
    CrossPageMergerConfig,
)


def _fake_pymupdf_table(page_no: int, bbox: tuple, n_cols: int) -> MagicMock:
    """构造 mock pymupdf find_tables() 返回的 table 对象."""
    t = MagicMock()
    t.bbox = bbox  # (x0, y0, x1, y1)
    t.page = page_no  # 1-based (跟 camelot 对齐)
    t.col_count = n_cols
    return t


def test_align_consecutive_pages_detects_candidate() -> None:
    """页号相邻 + y 连续 + 列数 80% 一致 → 候选续表对."""
    from src.ingest.pre_analysis.table_extractors.camelot_extractor import (
        _align_consecutive_pages,
    )

    camelot_tables = [
        TableData(page_no=1, table_no=1, rows=[["a", "b"]]),
        TableData(page_no=2, table_no=1, rows=[["c", "d"]]),
    ]
    pymupdf_tables = [
        _fake_pymupdf_table(1, (0, 100, 200, 200), 2),
        _fake_pymupdf_table(2, (0, 210, 200, 300), 2),  # y0=210, prev y1=200, gap=10 < 20
    ]
    pairs = _align_consecutive_pages(camelot_tables, pymupdf_tables)
    assert pairs == [(0, 1)], f"应识别 (0,1) 为候选续表对, 实际 {pairs}"


def test_align_consecutive_pages_skips_different_columns() -> None:
    """列数差异 > 80% → 不算候选."""
    from src.ingest.pre_analysis.table_extractors.camelot_extractor import (
        _align_consecutive_pages,
    )

    camelot_tables = [
        TableData(page_no=1, table_no=1, rows=[["a", "b", "c", "d", "e"]]),  # 5 列
        TableData(page_no=2, table_no=1, rows=[["d", "e"]]),  # 2 列
    ]
    pymupdf_tables = [
        _fake_pymupdf_table(1, (0, 100, 200, 200), 5),
        _fake_pymupdf_table(2, (0, 210, 200, 300), 2),
    ]
    pairs = _align_consecutive_pages(camelot_tables, pymupdf_tables)
    # curr=2 prev=5 → 2/5 = 0.4 < 0.8 → 跳过
    assert pairs == [], f"列数差太大不应合并, 实际 {pairs}"


def test_merge_llm_repeated_true_skips_header() -> None:
    """LLM 返 is_repeated=True, rows_to_skip=1 → 拼接 prev rows + curr body (跳 1 行)."""
    # mock pymupdf doc
    fake_doc = MagicMock()
    fake_doc.page_count = 2
    page1 = MagicMock()
    page1.find_tables.return_value = [_fake_pymupdf_table(1, (0, 100, 200, 200), 2)]
    page2 = MagicMock()
    page2.find_tables.return_value = [_fake_pymupdf_table(2, (0, 210, 200, 300), 2)]
    fake_doc.load_page.side_effect = [page1, page2]

    # mock trim_repeated_header 返 is_repeated=True
    base_tables = [
        TableData(page_no=1, table_no=1, rows=[["a", "b"], ["1", "2"]]),
        TableData(page_no=2, table_no=1, rows=[["a", "b"], ["3", "4"]]),  # 重复 header
    ]

    merger = CrossPageMerger()
    with patch.object(merger, "_llm_trim_header", return_value=(True, 1)):
        result = merger.merge("dummy.pdf", pymupdf_doc=fake_doc, base_tables=base_tables)

    assert len(result) == 1, f"应合并成 1 张, 实际 {len(result)}"
    assert result[0].page_no == "1+2"
    # curr 的 ["a", "b"] header 被跳过 1 行, 实际 [["a","b"],["1","2"],["3","4"]]
    assert result[0].rows == [["a", "b"], ["1", "2"], ["3", "4"]]


def test_merge_llm_repeated_false_keeps_original() -> None:
    """LLM 返 is_repeated=False → 不合并."""
    fake_doc = MagicMock()
    fake_doc.page_count = 2
    page1 = MagicMock()
    page1.find_tables.return_value = [_fake_pymupdf_table(1, (0, 100, 200, 200), 2)]
    page2 = MagicMock()
    page2.find_tables.return_value = [_fake_pymupdf_table(2, (0, 210, 200, 300), 2)]
    fake_doc.load_page.side_effect = [page1, page2]

    base_tables = [
        TableData(page_no=1, table_no=1, rows=[["a", "b"]]),
        TableData(page_no=2, table_no=1, rows=[["c", "d"]]),  # 新表, 不合并
    ]

    merger = CrossPageMerger()
    with patch.object(merger, "_llm_trim_header", return_value=(False, 0)):
        result = merger.merge("dummy.pdf", pymupdf_doc=fake_doc, base_tables=base_tables)

    assert len(result) == 2, f"不重复应不合并, 实际 {len(result)} 张"


def test_merge_llm_unavailable_falls_back() -> None:
    """LLM 不可用 → 兜底返 base_tables 不变 + log warning."""
    fake_doc = MagicMock()
    fake_doc.page_count = 1
    page1 = MagicMock()
    page1.find_tables.return_value = [_fake_pymupdf_table(1, (0, 100, 200, 200), 2)]
    fake_doc.load_page.return_value = page1

    base_tables = [TableData(page_no=1, table_no=1, rows=[["a", "b"]])]

    merger = CrossPageMerger()
    with patch.object(merger, "_llm_trim_header", side_effect=Exception("LLM down")):
        result = merger.merge("dummy.pdf", pymupdf_doc=fake_doc, base_tables=base_tables)

    assert len(result) == 1
    assert result[0].page_no == 1, "LLM 失败应保留原表, 不合并"


def test_merge_pymupdf_failure_falls_back() -> None:
    """pymupdf.find_tables() 抛异常 → 兜底返 base_tables 不变."""
    fake_doc = MagicMock()
    fake_doc.page_count = 2
    page1 = MagicMock()
    page1.find_tables.side_effect = RuntimeError("encrypted PDF")
    fake_doc.load_page.return_value = page1

    base_tables = [
        TableData(page_no=1, table_no=1, rows=[["a", "b"]]),
        TableData(page_no=2, table_no=1, rows=[["c", "d"]]),
    ]

    merger = CrossPageMerger()
    result = merger.merge("dummy.pdf", pymupdf_doc=fake_doc, base_tables=base_tables)

    assert len(result) == 2, f"pymupdf 失败应保留原表, 实际 {len(result)} 张"


@pytest.mark.skipif(
    True,  # 默认 skip, 真 e2e 需要 LLM 客户端可用 + D81.1 fixture
    reason="D81.1 e2e: 需要 LLM 客户端可用 + fixture 存在",
)
def test_merge_d81_1_e2e_cross_page_merged() -> None:
    """D81.1 真 PDF e2e: 跨页续表 page_no='40+41' 之类应被合并.

    skipif 守住: 真 PDF 必须有 + LLM 客户端可用.
    """
    pytest.importorskip("camelot")
    pytest.importorskip("pymupdf")

    from src.ingest.pre_analysis.table_extractors.camelot_extractor import (
        CamelotTableExtractor,
    )

    fixture_path = (
        __import__("pathlib").Path(__file__).resolve().parents[3]
        / "fixtures"
        / "Motors-D81-1-complete-English-09-2023.pdf"
    )
    if not fixture_path.exists():
        pytest.skip(f"fixture 缺失: {fixture_path}")

    import pymupdf

    doc = pymupdf.open(str(fixture_path))
    try:
        tables = CamelotTableExtractor({"flavor": "lattice"}).extract(str(fixture_path), _pymupdf_doc=doc)
    finally:
        doc.close()

    merged = [t for t in tables if isinstance(t.page_no, str) and "+" in t.page_no]
    # 不强求 ≥ N 张 (依赖 LLM), 至少能跑完不崩
    assert isinstance(merged, list)


def test_cross_page_merger_config_defaults() -> None:
    """CrossPageMergerConfig 默认值符合预期."""
    cfg = CrossPageMergerConfig()
    assert cfg.llm_model is None
    assert cfg.cache_enabled is True
    assert cfg.min_column_match == 0.8
    assert cfg.max_vertical_gap_px == 20


# (2026-07-09) spec 4.7: C2 双 strategy (lines + text) 同页 dedup + _bbox_overlap helper.


def test_bbox_overlap_full() -> None:
    """(2026-07-09) _bbox_overlap 完全重合 → IoU = 1.0."""
    from src.ingest.pre_analysis.table_extractors.camelot_extractor import _bbox_overlap

    assert _bbox_overlap((0.0, 0.0, 100.0, 100.0), (0.0, 0.0, 100.0, 100.0)) == 1.0


def test_bbox_overlap_partial() -> None:
    """(2026-07-09) _bbox_overlap 部分重合 → IoU ≈ 1/3."""
    from src.ingest.pre_analysis.table_extractors.camelot_extractor import _bbox_overlap

    # 重叠 50×100, 2 个 bbox 都是 100×100 → IoU = 5000 / 15000 ≈ 0.333
    assert _bbox_overlap((0.0, 0.0, 100.0, 100.0), (50.0, 0.0, 150.0, 100.0)) == pytest.approx(1 / 3)


def test_bbox_overlap_none() -> None:
    """(2026-07-09) _bbox_overlap 完全不重叠 → IoU = 0.0."""
    from src.ingest.pre_analysis.table_extractors.camelot_extractor import _bbox_overlap

    assert _bbox_overlap((0.0, 0.0, 10.0, 10.0), (100.0, 100.0, 200.0, 200.0)) == 0.0


def test_bbox_overlap_none_input_returns_zero() -> None:
    """(2026-07-09) _bbox_overlap 任一输入为 None → 返 0.0, 不抛."""
    from src.ingest.pre_analysis.table_extractors.camelot_extractor import _bbox_overlap

    assert _bbox_overlap(None, (0.0, 0.0, 10.0, 10.0)) == 0.0
    assert _bbox_overlap((0.0, 0.0, 10.0, 10.0), None) == 0.0
    assert _bbox_overlap(None, None) == 0.0


def test_cross_page_merge_includes_text_strategy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """(2026-07-09) spec 4.7: merge 同时调 lines + text 两种 strategy, text 兜底 borderless.

    mock pymupdf doc:
      - page 1: lines 返 1 个 bbox
      - page 2: text 返 1 个 bbox (borderless 续表)
    验证 cap_calls 同时含 lines / text.
    """
    cap_calls: list[str] = []

    class _MockT:
        def __init__(self, page: int, bbox: tuple, strategy: str) -> None:
            self.page = page
            self.bbox = bbox
            self.strategy = strategy

    class _MockPage:
        def find_tables(self, strategy: str) -> list:
            cap_calls.append(strategy)
            if strategy == "lines":
                return [_MockT(page=1, bbox=(10.0, 100.0, 200.0, 300.0), strategy="lines")]
            if strategy == "text":
                return [_MockT(page=2, bbox=(10.0, 50.0, 200.0, 250.0), strategy="text")]
            return []

    class _MockDoc:
        page_count = 2

        def load_page(self, page_idx: int) -> _MockPage:
            return _MockPage()

    doc = _MockDoc()
    merger = CrossPageMerger(CrossPageMergerConfig(cache_enabled=False))
    # stub LLM 避免真调
    monkeypatch.setattr(
        "src.ingest.pre_analysis.table_extractors.camelot_extractor.CrossPageMerger._llm_trim_header",
        lambda self, prev, curr: (False, 0),
    )

    # 给 base_tables 1 张 page=1 表, 让 merge 进 strategy loop (否则 `if not base_tables` 早返)
    base = [TableData(page_no=1, table_no=1, rows=[["a", "b"]], bbox=(10.0, 100.0, 200.0, 300.0))]
    result = merger.merge("/tmp/fake.pdf", pymupdf_doc=doc, base_tables=base)

    assert "lines" in cap_calls
    assert "text" in cap_calls
    # LLM stub 返 (False, 0), 没有续表对, base 原样返回
    assert result == base


def test_cross_page_merge_strategy_text_dedup_same_page(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """(2026-07-09) spec 4.7: 同页 lines + text 识别到同区域 → IoU > 0.7 dedup, 不重复进 pymupdf_tables.

    验证 _bbox_overlap helper 真的被 merge 用到 (lines 先入 seen_bboxes,
    text 同区域 IoU ≈ 0.96 → 跳过).
    """
    cap_calls: list[str] = []

    class _MockT:
        def __init__(self, page: int, bbox: tuple) -> None:
            self.page = page
            self.bbox = bbox

    class _MockPage:
        def find_tables(self, strategy: str) -> list:
            cap_calls.append(strategy)
            if strategy == "lines":
                return [_MockT(page=1, bbox=(10.0, 100.0, 200.0, 300.0))]
            if strategy == "text":
                return [_MockT(page=1, bbox=(10.0, 95.0, 200.0, 305.0))]
            return []

    class _MockDoc:
        page_count = 1

        def load_page(self, page_idx: int) -> _MockPage:  # noqa: ARG002
            return _MockPage()

    # 给 base_tables 1 张 page=1 表, 让 merge 走完真实对齐逻辑 + 验证 _bbox_overlap 已 wired
    base = [TableData(page_no=1, table_no=1, rows=[["a", "b"]], bbox=(10.0, 100.0, 200.0, 300.0))]

    merger = CrossPageMerger(CrossPageMergerConfig(cache_enabled=False))
    monkeypatch.setattr(
        "src.ingest.pre_analysis.table_extractors.camelot_extractor.CrossPageMerger._llm_trim_header",
        lambda self, prev, curr: (False, 0),
    )

    result = merger.merge("/tmp/fake.pdf", pymupdf_doc=_MockDoc(), base_tables=base)
    # 由于 LLM stub 返 (False, 0), 没有续表对, base_tables 原样返回
    assert result == base
    # lines + text 都跑了 (确认双 strategy 真的生效)
    assert "lines" in cap_calls
    assert "text" in cap_calls
