"""TableExtractor 抽象基类契约测试 (mode 1 mock).

只验证纯接口契约 (frozen dataclass + ABC 抽象 + error class shape),
不连 PG, 不依赖 pymupdf / camelot / pdfplumber.
"""

from __future__ import annotations

import dataclasses

import pytest


def test_table_data_is_frozen_dataclass() -> None:
    """TableData 必须是 frozen dataclass, 防运行时误改字段."""
    from src.ingest.pre_analysis.table_extractors.base import TableData

    td = TableData(page_no=1, table_no=1, rows=[["a", "b"]])
    with pytest.raises(dataclasses.FrozenInstanceError):
        td.page_no = 2  # type: ignore[misc]


def test_table_data_default_field_shapes() -> None:
    """TableData 字段类型强校验 (page_no/table_no int, rows list[list[str]])."""
    from src.ingest.pre_analysis.table_extractors.base import TableData

    td = TableData(page_no=3, table_no=2, rows=[["x"], ["y", "z"]])
    assert td.page_no == 3
    assert td.table_no == 2
    assert td.rows == [["x"], ["y", "z"]]
    assert len(td.rows[1]) == 2


def test_table_extractor_cannot_instantiate_directly() -> None:
    """TableExtractor 是 ABC, 不能直接实例化."""
    from src.ingest.pre_analysis.table_extractors.base import TableExtractor

    with pytest.raises(TypeError):
        TableExtractor()  # type: ignore[abstract]


def test_table_extractor_extract_is_abstract() -> None:
    """TableExtractor.extract 是 abstractmethod, 子类必须实现."""
    from src.ingest.pre_analysis.table_extractors.base import TableExtractor

    assert hasattr(TableExtractor, "extract")
    # `extract` 必须有 __isabstractmethod__ 标志
    assert getattr(TableExtractor.extract, "__isabstractmethod__", False)


def test_backend_not_installed_error_basic() -> None:
    """BackendNotInstalledError 存 backend + install_hint 字段, str() 含两者."""
    from src.ingest.pre_analysis.table_extractors.base import (
        BackendNotInstalledError,
    )

    err = BackendNotInstalledError(
        backend="camelot",
        install_hint="uv add camelot-py",
    )
    assert err.backend == "camelot"
    assert err.install_hint == "uv add camelot-py"
    assert isinstance(err, RuntimeError)
    # str() 含 backend 名 + install_hint
    s = str(err)
    assert "camelot" in s
    assert "uv add camelot-py" in s


def test_backend_not_installed_error_ml_variant() -> None:
    """ml variant 的 error 应该 backend='camelot[ml]', 给 admin 区分装哪个 extra."""
    from src.ingest.pre_analysis.table_extractors.base import (
        BackendNotInstalledError,
    )

    err = BackendNotInstalledError(
        backend="camelot[ml]",
        install_hint="uv add 'camelot-py[ml]'",
    )
    assert err.backend == "camelot[ml]"
    assert "[ml]" in err.install_hint


# (2026-07-09) Camelot/pymupdf/pdfplumber 共用的退化表判定 (TableData.is_valid_table)


def test_is_valid_table_2x2_returns_true() -> None:
    """2 行 2 列是最低有效表格."""
    from src.ingest.pre_analysis.table_extractors.base import TableData

    assert TableData.is_valid_table([["a", "b"], ["1", "2"]]) is True


def test_is_valid_table_3x4_returns_true() -> None:
    """真实跨页合并后的多行多列应通过."""
    from src.ingest.pre_analysis.table_extractors.base import TableData

    rows = [
        ["Prated", "50Hz 2-pole", "50Hz 4-pole", "60Hz 2-pole"],
        ["0.18", "65.9", "69.9", "70.8"],
        ["0.25", "69.7", "73.5", "74.3"],
    ]
    assert TableData.is_valid_table(rows) is True


def test_is_valid_table_1x1_returns_false() -> None:
    """1×1 单格表是退化 (整页被压成一个 cell)."""
    from src.ingest.pre_analysis.table_extractors.base import TableData

    assert TableData.is_valid_table([["some text"]]) is False


def test_is_valid_table_1xN_returns_false() -> None:
    """1×N 是 Camelot stream fallback 的典型故障 case."""
    from src.ingest.pre_analysis.table_extractors.base import TableData

    assert TableData.is_valid_table([["a", "b", "c", "d"]]) is False


def test_is_valid_table_2x1_returns_false() -> None:
    """2×1 纵列表也视为退化 (PDF 表格场景几乎不存在真实纵列表)."""
    from src.ingest.pre_analysis.table_extractors.base import TableData

    assert TableData.is_valid_table([["a"], ["b"]]) is False


def test_is_valid_table_empty_rows_returns_false() -> None:
    """rows=[] 空表视为退化."""
    from src.ingest.pre_analysis.table_extractors.base import TableData

    assert TableData.is_valid_table([]) is False


def test_is_valid_table_single_empty_row_returns_false() -> None:
    """rows=[[]] 单空行视为退化."""
    from src.ingest.pre_analysis.table_extractors.base import TableData

    assert TableData.is_valid_table([[]]) is False


def test_is_valid_table_blank_rows_dont_count() -> None:
    """整行空白不计入有效行数. 前 2 行纯空白 + 1 行真数据 -> 算 1 行有效 -> 退化."""
    from src.ingest.pre_analysis.table_extractors.base import TableData

    rows = [["", ""], ["", ""], ["a", "b"]]
    assert TableData.is_valid_table(rows) is False  # 只有 1 行非空白, < 2


# (2026-07-09) TableData.filter_valid 批量过滤 (3 个 extractor 共用)


def test_filter_valid_drops_degenerate_keeps_order() -> None:
    """退化表丢弃, valid 表顺序保留."""
    from src.ingest.pre_analysis.table_extractors.base import TableData

    tables = [
        TableData(page_no=1, table_no=1, rows=[["only"]]),  # 退化
        TableData(page_no=1, table_no=2, rows=[["a", "b"], ["c", "d"]]),  # valid
        TableData(page_no=2, table_no=1, rows=[["x", "y", "z"]]),  # 退化
        TableData(page_no=2, table_no=2, rows=[["h"], ["v1", "v2"]]),  # valid
    ]
    result = TableData.filter_valid(tables, backend_name="test")
    assert len(result) == 2
    assert result[0].page_no == 1 and result[0].table_no == 2
    assert result[1].page_no == 2 and result[1].table_no == 2


def test_filter_valid_returns_new_list_does_not_mutate_input() -> None:
    """filter_valid 不修改入参."""
    from src.ingest.pre_analysis.table_extractors.base import TableData

    tables = [TableData(page_no=1, table_no=1, rows=[["x"]])]
    result = TableData.filter_valid(tables, backend_name="test")
    assert result == []  # 入参 1 退化表, 出参 []
    assert len(tables) == 1  # 入参未变


def test_filter_valid_logs_warning_per_dropped(caplog) -> None:
    """退化表走 logger.warning, 含 backend_name + page/table/rows/cols.

    filter_valid 内部用 loguru, caplog 通过 propagate 捕获.
    """
    from src.ingest.pre_analysis.table_extractors.base import TableData

    tables = [
        TableData(page_no=3, table_no=1, rows=[["a", "b", "c"]]),  # 1xN 退化
        TableData(page_no=3, table_no=2, rows=[["h1", "h2"], ["v1", "v2"]]),  # valid
    ]
    with caplog.at_level("WARNING"):
        result = TableData.filter_valid(tables, backend_name="pymupdf")

    assert len(result) == 1
    drop_msgs = [r.getMessage() for r in caplog.records if r.levelname == "WARNING"]
    assert any(
        "pymupdf" in m and "page=3" in m and "table=1" in m and "rows=1" in m and "cols=3" in m for m in drop_msgs
    )


def test_filter_valid_empty_input() -> None:
    """空入参返 []."""
    from src.ingest.pre_analysis.table_extractors.base import TableData

    assert TableData.filter_valid([], backend_name="test") == []


# (2026-07-09) bbox 字段, 给 spec 4.6 lattice/ml IoU dedup + C2 同页 strategy dedup 用.


def test_table_data_bbox_default_none() -> None:
    """(2026-07-09) TableData() 不传 bbox → 默认 None, 老调用全兼容."""
    from src.ingest.pre_analysis.table_extractors.base import TableData

    t = TableData(page_no=1, table_no=1, rows=[["a", "b"]])
    assert t.bbox is None


def test_table_data_bbox_can_be_set() -> None:
    """(2026-07-09) .replace(bbox=...) 设值, frozen dataclass 兼容."""
    from src.ingest.pre_analysis.table_extractors.base import TableData

    t = TableData(page_no=1, table_no=1, rows=[["a", "b"]])
    t_with_bbox = t.replace(bbox=(10.0, 20.0, 100.0, 200.0))
    assert t_with_bbox.bbox == (10.0, 20.0, 100.0, 200.0)
    assert t.bbox is None  # 原 t 不动 (frozen)


def test_table_data_bbox_in_equality() -> None:
    """(2026-07-09) frozen dataclass 自动生成 __eq__, bbox 不同时视作不同对象."""
    from src.ingest.pre_analysis.table_extractors.base import TableData

    a = TableData(page_no=1, table_no=1, rows=[["a"]], bbox=None)
    b = a.replace(bbox=(0.0, 0.0, 10.0, 10.0))
    assert a != b
