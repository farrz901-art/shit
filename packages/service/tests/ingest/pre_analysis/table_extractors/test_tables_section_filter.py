"""tables_section.run() 退化表过滤集成测试 (mode 1 mock, 无 PG).

(2026-07-09) 验证:
- 退化表不进 ObjectStore / db_artifact
- 每丢弃一条有 logger.warning
- StageResult.message 格式 'N 表 / K 跨页候选' (2026-07-09 删 M 丢弃字段)
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock

import pytest

from src.ingest.pre_analysis.stage_context import StageContext, StageResult


def _make_ctx(
    *,
    raw_tables: list,
    task_id: str = "pa_test_task_001",
) -> tuple[StageContext, MagicMock, MagicMock]:
    """构造最小 StageContext, mock object_store + task_store + stage_store + doc.

    raw_tables: list[TableData] 注入到 mock extractor.extract()
    """

    # mock doc + config + output_prefix
    doc = MagicMock()
    doc.name = "fake.pdf"

    object_store = MagicMock()
    task_store = MagicMock()
    stage_store = MagicMock()

    ctx = StageContext(
        task_id=task_id,
        pdf_uri="local://input/fake.pdf",
        object_store=object_store,
        task_store=task_store,
        stage_store=stage_store,
        start_monotonic=time.monotonic(),
        doc=doc,
        config={"cross_page_detection": {}},
        output_prefix="local://test/prefix",
    )

    # 替换 extractor: 直接返 raw_tables (绕开 PDF 解析)
    extractor = MagicMock()
    extractor.extract.return_value = raw_tables

    return ctx, extractor, object_store


def _table(page_no: int, table_no: int, rows: list[list[str]]):
    from src.ingest.pre_analysis.table_extractors.base import TableData

    return TableData(page_no=page_no, table_no=table_no, rows=rows)


def test_run_filters_degenerate_tables(monkeypatch: pytest.MonkeyPatch) -> None:
    """混合表输入: 1×1 退化 + 1×3 退化 + 3×2 有效 -> 只 valid 表写 CSV + append_artifact."""
    raw_tables = [
        _table(1, 1, [["only text"]]),  # 1×1 -> 丢
        _table(1, 2, [["a", "b", "c"]]),  # 1×N -> 丢
        _table(2, 1, [["h1", "h2"], ["v1", "v2"], ["v3", "v4"]]),  # 3×2 -> 留
    ]
    ctx, extractor, object_store = _make_ctx(raw_tables=raw_tables)

    import src.ingest.pre_analysis.table_extractors.factory as factory_mod
    from src.ingest.pre_analysis.table_extractors import tables_section

    original_get = factory_mod.get_table_extractor
    factory_mod.get_table_extractor = lambda backend, params: extractor
    monkeypatch.setattr(tables_section, "append_artifact", MagicMock())
    try:
        new_ctx, result = tables_section.run(ctx)
    finally:
        factory_mod.get_table_extractor = original_get

    # 只 valid 表 (3×2) 进了 put_bytes
    assert object_store.put_bytes.call_count == 1, (
        f"期望 1 次 put_bytes (valid 表), 实际 {object_store.put_bytes.call_count}"
    )
    put_uri = object_store.put_bytes.call_args[0][0]
    assert "page-2-table-1" in put_uri

    # new_ctx.tables 只含 valid 表
    assert new_ctx.tables is not None  # type: ignore[unreachable]  # run() 后必填
    assert len(new_ctx.tables) == 1
    assert new_ctx.tables[0][0] == 2
    assert new_ctx.tables[0][1] == 1


def test_run_logs_warning_per_dropped(caplog, monkeypatch: pytest.MonkeyPatch) -> None:
    """每个丢弃的退化表都有 logger.warning, 含 page/table/rows/cols."""
    import logging

    raw_tables = [
        _table(5, 1, [["x"]]),  # 1×1
        _table(5, 2, [["a", "b", "c", "d"]]),  # 1×N
    ]
    ctx, extractor, _ = _make_ctx(raw_tables=raw_tables)

    import src.ingest.pre_analysis.table_extractors.factory as factory_mod
    from src.ingest.pre_analysis.table_extractors import tables_section

    original_get = factory_mod.get_table_extractor
    factory_mod.get_table_extractor = lambda backend, params: extractor
    monkeypatch.setattr(tables_section, "append_artifact", MagicMock())
    try:
        with caplog.at_level(logging.WARNING):
            _, result = tables_section.run(ctx)
    finally:
        factory_mod.get_table_extractor = original_get

    warnings = [r for r in caplog.records if r.levelname == "WARNING"]
    msgs = [r.getMessage() for r in warnings]
    # 2 个退化表 -> 至少 2 条 warning 含 "丢弃退化表"
    drop_warnings = [m for m in msgs if "丢弃退化表" in m]
    assert len(drop_warnings) == 2, f"期望 2 条丢弃 warning, 实际 {len(drop_warnings)}: {drop_warnings}"
    assert any("page=5 table=1 rows=1 cols=1" in m for m in drop_warnings)
    assert any("page=5 table=2 rows=1 cols=4" in m for m in drop_warnings)


def test_run_stage_result_message_format(monkeypatch: pytest.MonkeyPatch) -> None:
    """StageResult.message 格式: '1 表 / 0 跨页候选' (2026-07-09 删 M 丢弃字段).

    退化表数量不再报给前端 (extractor 层 filter_valid 后永远是 0,
    暴露给用户会误解). 退化表过滤逻辑保留作双层防御, 但不进 message.
    """
    raw_tables = [
        _table(1, 1, [["only"]]),  # 退化
        _table(2, 1, [["h1", "h2"], ["v1", "v2"]]),  # valid
        _table(3, 1, [["x", "y", "z"]]),  # 退化
    ]
    ctx, extractor, _ = _make_ctx(raw_tables=raw_tables)

    import src.ingest.pre_analysis.table_extractors.factory as factory_mod
    from src.ingest.pre_analysis.table_extractors import tables_section

    original = factory_mod.get_table_extractor
    factory_mod.get_table_extractor = lambda backend, params: extractor
    monkeypatch.setattr(tables_section, "append_artifact", MagicMock())
    try:
        _, result = tables_section.run(ctx)
    finally:
        factory_mod.get_table_extractor = original

    assert isinstance(result, StageResult)
    assert result.ok is True
    # (2026-07-09) 简化: 不再含 M 丢弃字段
    assert result.message == "1 表 / 0 跨页候选"
    assert result.stage_name == "extract_tables"
