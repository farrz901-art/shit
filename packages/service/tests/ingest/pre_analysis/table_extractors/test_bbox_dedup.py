"""bbox dedup 测试 (mode 1 mock).

(2026-07-09) spec 4.6: lattice ∪ ml 同页结果用 bbox IoU 去重, 留 lattice.
helper `_merge_dedup_lattice_ml` 落地供未来 v2 集成 (本期不接 extract).
"""

from __future__ import annotations

import logging

import pytest

from src.ingest.pre_analysis.table_extractors.base import TableData
from src.ingest.pre_analysis.table_extractors.camelot_extractor import (
    _bbox_overlap,
    _merge_dedup_lattice_ml,
)

# (2026-07-09) _bbox_overlap IoU 计算 (Task 5 已实现, 此处独立建档)


def test_bbox_overlap_full() -> None:
    """_bbox_overlap 完全重合 → IoU = 1.0."""
    assert _bbox_overlap((0.0, 0.0, 100.0, 100.0), (0.0, 0.0, 100.0, 100.0)) == 1.0


def test_bbox_overlap_partial() -> None:
    """_bbox_overlap 部分重合 → IoU ≈ 1/3."""
    # 重叠 50×100, 2 个 bbox 各 100×100 → IoU = 5000 / 15000 ≈ 0.333
    assert _bbox_overlap((0.0, 0.0, 100.0, 100.0), (50.0, 0.0, 150.0, 100.0)) == pytest.approx(1 / 3)


def test_bbox_overlap_none() -> None:
    """_bbox_overlap 完全不重叠 → IoU = 0.0."""
    assert _bbox_overlap((0.0, 0.0, 10.0, 10.0), (100.0, 100.0, 200.0, 200.0)) == 0.0


def test_bbox_overlap_none_input_returns_zero() -> None:
    """_bbox_overlap 任一输入为 None → 返 0.0, 不抛."""
    assert _bbox_overlap(None, (0.0, 0.0, 10.0, 10.0)) == 0.0
    assert _bbox_overlap((0.0, 0.0, 10.0, 10.0), None) == 0.0
    assert _bbox_overlap(None, None) == 0.0


# (2026-07-09) _merge_dedup_lattice_ml IoU 双档 (spec 4.6)


def test_dedup_lattice_and_ml_iou_07_drops_ml_silently() -> None:
    """IoU > 0.7 高置信重复 → 丢 ml, 不打 log (高频正常情况)."""
    lattice = [
        TableData(
            page_no=1,
            table_no=1,
            rows=[["a", "b"]],
            bbox=(10.0, 100.0, 200.0, 200.0),
        ),
    ]
    ml = [
        TableData(
            page_no=1,
            table_no=1,
            rows=[["a", "b"]],
            bbox=(10.0, 102.0, 200.0, 198.0),  # IoU ≈ 0.94
        ),
    ]

    result = _merge_dedup_lattice_ml(lattice, ml)

    assert len(result) == 1
    assert result[0] is lattice[0]  # 留 lattice, ml 丢


def test_dedup_lattice_and_ml_iou_05_drops_ml_with_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """IoU ∈ (0.5, 0.7] 灰区 → 丢 ml + log warning (保留 lattice, 可观察)."""
    lattice = [
        TableData(
            page_no=1,
            table_no=1,
            rows=[["a", "b"]],
            bbox=(0.0, 0.0, 100.0, 100.0),
        ),
    ]
    # 2 bbox 重叠 80×100 / (10000 + 10000 - 8000) = 8000/12000 ≈ 0.667
    ml = [
        TableData(
            page_no=1,
            table_no=1,
            rows=[["a", "b"]],
            bbox=(20.0, 0.0, 120.0, 100.0),
        ),
    ]

    with caplog.at_level(logging.WARNING):
        result = _merge_dedup_lattice_ml(lattice, ml)

    assert len(result) == 1
    assert result[0] is lattice[0]
    assert any("IoU" in record.message for record in caplog.records)


def test_dedup_lattice_and_ml_iou_below_05_keeps_both() -> None:
    """IoU < 0.5 不同表 → 都保留."""
    lattice = [
        TableData(
            page_no=1,
            table_no=1,
            rows=[["a", "b"]],
            bbox=(0.0, 0.0, 50.0, 50.0),
        ),
    ]
    ml = [
        TableData(
            page_no=1,
            table_no=2,
            rows=[["c", "d"]],
            bbox=(100.0, 100.0, 200.0, 200.0),
        ),
    ]

    result = _merge_dedup_lattice_ml(lattice, ml)

    assert len(result) == 2
    assert lattice[0] in result
    assert ml[0] in result


def test_dedup_ml_no_bbox_kept() -> None:
    """ml 表无 bbox (老 camelot) → 保守全留, 不丢."""
    lattice = [
        TableData(
            page_no=1,
            table_no=1,
            rows=[["a", "b"]],
            bbox=(0.0, 0.0, 100.0, 100.0),
        ),
    ]
    ml = [TableData(page_no=1, table_no=1, rows=[["a", "b"]], bbox=None)]

    result = _merge_dedup_lattice_ml(lattice, ml)

    assert len(result) == 2  # 都留


def test_dedup_empty_ml_returns_lattice() -> None:
    """ml 无结果 → 返 lattice 不动."""
    lattice = [TableData(page_no=1, table_no=1, rows=[["a", "b"]])]

    result = _merge_dedup_lattice_ml(lattice, [])

    assert result == lattice


def test_dedup_none_ml_returns_lattice() -> None:
    """ml=None → 返 lattice (None 当 [] 处理)."""
    lattice = [TableData(page_no=1, table_no=1, rows=[["a", "b"]])]

    result = _merge_dedup_lattice_ml(lattice, None)

    assert result == lattice


def test_dedup_multiple_ml_each_checked_against_all_lattice() -> None:
    """多张 ml 表, 每张跟 lattice 全集比较, 独立判重."""
    lattice = [
        TableData(page_no=1, table_no=1, rows=[["a", "b"]], bbox=(0.0, 0.0, 50.0, 50.0)),
        TableData(page_no=1, table_no=2, rows=[["c", "d"]], bbox=(100.0, 0.0, 150.0, 50.0)),
    ]
    ml = [
        # 跟 lattice[0] 高重复 (IoU = 1.0)
        TableData(page_no=1, table_no=1, rows=[["a", "b"]], bbox=(0.0, 0.0, 50.0, 50.0)),
        # 新表
        TableData(page_no=1, table_no=3, rows=[["e", "f"]], bbox=(0.0, 100.0, 50.0, 150.0)),
    ]

    result = _merge_dedup_lattice_ml(lattice, ml)

    # 期望: lattice[0] 留, lattice[1] 留, ml[0] 丢, ml[1] 留
    assert len(result) == 3
    assert lattice[0] in result
    assert lattice[1] in result
    assert ml[1] in result
    # ml[0] 被去重 → result 不应含 ml[0] 的引用 (lattice[0] 字段跟 ml[0] 一样但不是同一对象)
    assert not any(r is ml[0] for r in result), "ml[0] 应被高置信去重, 不应出现"
