"""Stage 3: tables_section (2026-07-09).

从 runner.py 抽出来. 职责:
1. 调 table_extractors.factory.get_table_extractor(backend, params) → 拿 extractor
2. extractor.extract(doc.name, _pymupdf_doc=doc) → 返 raw_tables
3. _detect_cross_page 启发式扫描跨页候选
4. 每张表写 CSV + db_artifact.append_artifact

返 (new_ctx, StageResult). ctx 注入 tables / cross_page_count.
"""

from __future__ import annotations

import csv
import io
from collections.abc import Sequence

from loguru import logger

from ..db_artifact import append_artifact
from ..stage_context import StageContext, StageResult
from .base import TableData

STAGE_NAME = "extract_tables"


def _detect_cross_page(
    # (2026-07-09) page_no 可 str (跨页合并后是 "5+6"); 后续守卫跳过
    # Sequence 协变兼容 list[tuple[int, ...]] (老调用) + list[tuple[int | str, ...]] (跨页合并后)
    tables: Sequence[tuple[int | str, int, Sequence[Sequence[str]]]],
    config: dict,
) -> int:
    """(2026-07-07 v3) 跨页表候选 + seen_footers 去重 (spec §4.6 / spec 矛盾 C5).

    (2026-07-09) page_no 是 str (已合并跨页表) 时跳过 — 启发式只对未合并表有意义.

    Returns: 跨页候选计数 (去重后).
    seen_footers: set[str] 用来 dedup 多列表格重复 footer (每列底都写 "continued" 时不重复触发).
    """
    cross_config = config.get("cross_page_detection", {}) or {}
    col_match = cross_config.get("min_column_match", 0.8)
    footer_kws = cross_config.get("footer_keywords", []) or []
    prev_table: tuple[int, int] | None = None
    cross_page = 0
    seen_footers: set[str] = set()
    for page_no, table_no, rows in tables:
        # (2026-07-09) 跳过已合并跨页表 (page_no 是 str 如 "5+6")
        if isinstance(page_no, str):
            prev_table = None  # 重置, 合并表后面可能接新未合并表
            continue
        if prev_table is not None and table_no == 1:
            prev_page, prev_cols = prev_table
            cur_cols = len(rows[0]) if rows else 0
            if prev_page == page_no - 1 and cur_cols >= prev_cols * col_match:
                # 末行第一列作为 footer 候选 (跟表格 reader 约定)
                last_row_first = (rows[-1][0] if rows and rows[-1] else "") or ""
                if last_row_first in seen_footers:
                    continue
                if any(kw in last_row_first for kw in footer_kws):
                    seen_footers.add(last_row_first)
                    cross_page += 1
                    logger.warning("跨页表候选 page={} -> page={}", prev_page, page_no)
        prev_table = (page_no, len(rows[0]) if rows else 0)
    return cross_page


def _write_one_table(
    object_store,
    prefix: str,
    # (2026-07-09) page_no 可 str: 跨页合并表编码 "5+6", URI 拼出 "page-5+6-table-1.csv" 可读
    # (2026-07-09) rows: Sequence 而非 list, 跟 _detect_cross_page 一致, 避免 line 151 list() 转换
    page_no: int | str,
    table_no: int,
    rows: Sequence[Sequence[str]],
    task_id: str,
) -> None:
    """(2026-07-06) 写单表 CSV, 立即 append 到 DB output_files_json."""
    uri = f"{prefix}/tables/page-{page_no}-table-{table_no}.csv"
    buf = io.StringIO()
    writer = csv.writer(buf)
    for row in rows:
        writer.writerow(row)
    data = buf.getvalue().encode("utf-8")
    object_store.put_bytes(uri, data, "text/csv")
    append_artifact(
        task_id,
        kind="table",
        filename=f"tables/page-{page_no}-table-{table_no}.csv",
        uri=uri,
        size_bytes=len(data),
    )


def run(
    ctx: StageContext,
    table_extraction_config: dict | None = None,
) -> tuple[StageContext, StageResult]:
    """Stage 3: 提取表 + 写 CSV + DB append + 跨页候选检测.

    Args:
        ctx: StageContext (要 doc / config / output_prefix).
        table_extraction_config: {table_backend, table_params}. None → 默认 pymupdf + 空 params.

    Returns: (new_ctx, StageResult). new_ctx 注入 tables / cross_page_count.
    """
    if table_extraction_config is None:
        table_extraction_config = {"table_backend": "pymupdf", "table_params": {}}
    backend = table_extraction_config.get("table_backend", "pymupdf")
    params = table_extraction_config.get("table_params", {})

    ctx.stage_store.mark_stage_started(ctx.task_id, STAGE_NAME)
    try:
        from .factory import get_table_extractor  # noqa: PLC0415 局部 import 避免重 import 链

        doc = ctx.doc
        assert doc is not None  # type: ignore[unreachable]  # stage 1 成功后 ctx.doc 必填
        config = ctx.config
        assert config is not None  # type: ignore[unreachable]  # 同上
        output_prefix = ctx.output_prefix
        assert output_prefix is not None  # type: ignore[unreachable]  # 同上

        extractor = get_table_extractor(backend, params)
        # (2026-07-09) 所有后端都传 doc, camelot C2 (CrossPageMerger) 需要 PyMuPDF bbox.
        # 原实现 `_doc = doc if backend == "pymupdf" else None` 导致 camelot C2 永远被跳过.
        raw_tables = extractor.extract(
            doc.name or "",
            _pymupdf_doc=doc,
        )
        tables = [(t.page_no, t.table_no, t.rows) for t in raw_tables]

        # (2026-07-09) 过滤退化表 (1×1 / 1×N / 全空白行), 必须放在 _detect_cross_page 之前,
        # 否则 cross_page 候选会包含 1×1 假表. 抽到 TableData.is_valid_table 让 3 个 extractor 可复用.
        valid_tables: list[tuple[int | str, int, Sequence[Sequence[str]]]] = []
        skipped_count = 0
        for page_no, table_no, rows in tables:
            if not TableData.is_valid_table(rows):
                skipped_count += 1
                logger.warning(
                    "丢弃退化表 page={} table={} rows={} cols={}",
                    page_no,
                    table_no,
                    len(rows),
                    max((len(r) for r in rows), default=0),
                )
                continue
            valid_tables.append((page_no, table_no, rows))
        tables = valid_tables

        cross_page = _detect_cross_page(tables, config)

        for page_no, table_no, rows in tables:
            _write_one_table(ctx.object_store, output_prefix, page_no, table_no, rows, ctx.task_id)
    except Exception as e:
        ctx.stage_store.mark_stage_failed(ctx.task_id, STAGE_NAME, str(e))
        ctx.task_store.mark_failed(
            ctx.task_id,
            f"{STAGE_NAME} failed: {e}",
            stages_provider=ctx.stage_store.list_stages,
        )
        logger.opt(exception=True).error("pre_analysis {} failed task={}", STAGE_NAME, ctx.task_id)
        return ctx, StageResult(ok=False, error=str(e), stage_name=STAGE_NAME)

    ctx.stage_store.mark_stage_completed(
        ctx.task_id,
        STAGE_NAME,
        progress=100,
        # (2026-07-09) M 丢弃字段删除 — extractor 层已 filter_valid (退化表 0 张), 再统计会让用户看到 0 误解.
        # 退化表信息保留在 logger.warning + 双层防御 (tables_section 兜底), message 不暴露.
        message=f"{len(tables)} 表 / {cross_page} 跨页候选",
    )
    return ctx.replace(tables=tables, cross_page_count=cross_page), StageResult(
        ok=True,
        stage_name=STAGE_NAME,
        message=f"{len(tables)} 表 / {cross_page} 跨页候选",
    )


__all__ = ["run", "STAGE_NAME"]
