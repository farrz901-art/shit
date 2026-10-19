"""Stage 4: flagged_section (2026-07-09).

从 runner.py 抽出来. 职责:
1. 调 flag_extractors.extract_flagged_paragraphs(doc, config) → list[dict]
2. 14 列 CSV 写 flagged_paragraphs.csv
3. db_artifact.append_artifact DB append 1 项

返 (new_ctx, StageResult). ctx 注入 flagged / flagged_uri.

14 列顺序与 spec §3.1 一致. 旧 DictReader 读前 4 列仍 OK (matched_keywords / page / section / text).
"""

from __future__ import annotations

import csv
import io

from loguru import logger

from ..stage_context import StageContext, StageResult
from . import extract_flagged_paragraphs

STAGE_NAME = "extract_flagged"

# 14 列 CSV header (跟 spec §3.1 一致, 保持兼容旧 DictReader 读前 4 列)
CSV_FIELDNAMES = [
    "matched_keywords",
    "page",
    "section",
    "text",  # 旧 4 (DictReader 兼容)
    "rule_categories",
    "density",
    "is_dense",  # v2 新增 3
    "raw_density",
    "weighted_density",  # v2 新增 2
    "safe_hits",
    "rec_hits",  # v2 新增 2
    "lemmas",
    "token_count",
    "language",  # v3 新增 3 (spacy + tiktoken)
]


def run(ctx: StageContext) -> tuple[StageContext, StageResult]:
    """Stage 4: 提取关键词段落 + 写 14 列 CSV + DB append.

    Args:
        ctx: StageContext (要 doc / config / output_prefix).

    Returns: (new_ctx, StageResult). new_ctx 注入 flagged / flagged_uri.
    """
    ctx.stage_store.mark_stage_started(ctx.task_id, STAGE_NAME)
    try:
        doc = ctx.doc
        assert doc is not None  # type: ignore[unreachable]  # stage 1 成功后 ctx.doc 必填
        config = ctx.config
        assert config is not None  # type: ignore[unreachable]  # 同上
        output_prefix = ctx.output_prefix
        assert output_prefix is not None  # type: ignore[unreachable]  # 同上

        flagged = extract_flagged_paragraphs(doc, config)

        # 写 14 列 CSV + DB append (复用 write_flagged_csv)
        uri, _size = write_flagged_csv(ctx.object_store, output_prefix, flagged, ctx.task_id)
    except Exception as e:
        ctx.stage_store.mark_stage_failed(ctx.task_id, STAGE_NAME, str(e))
        ctx.task_store.mark_failed(
            ctx.task_id,
            f"{STAGE_NAME} failed: {e}",
            stages_provider=ctx.stage_store.list_stages,
        )
        logger.opt(exception=True).error("pre_analysis {} failed task={}", STAGE_NAME, ctx.task_id)
        return ctx, StageResult(ok=False, error=str(e), stage_name=STAGE_NAME)

    ctx.stage_store.mark_stage_completed(ctx.task_id, STAGE_NAME, progress=100, message=f"{len(flagged)} 段落")
    return ctx.replace(flagged=flagged, flagged_uri=uri), StageResult(
        ok=True, stage_name=STAGE_NAME, message=f"{len(flagged)} 段落"
    )


__all__ = ["run", "STAGE_NAME", "CSV_FIELDNAMES"]


def write_flagged_csv(
    object_store,
    prefix: str,
    flagged: list[dict],
    task_id: str,
) -> tuple[str, int]:
    """(2026-07-09) 14 列 CSV 写 + db_artifact.append_artifact. 供 runner thin wrapper 复用.

    Args:
        object_store: 写入用的 ObjectStore (ctx.object_store 或 runner.object_store).
        prefix: URI 前缀, 拼 {prefix}/flagged_paragraphs.csv.
        flagged: list[dict] 14 列数据行.
        task_id: DB append 用.

    Returns: (uri, size_bytes).
    """
    from ..db_artifact import append_artifact  # noqa: PLC0415

    uri = f"{prefix}/flagged_paragraphs.csv"
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=CSV_FIELDNAMES)
    writer.writeheader()
    for row in flagged:
        clean_row = {k: row.get(k, "") for k in CSV_FIELDNAMES}
        writer.writerow(clean_row)
    data = buf.getvalue().encode("utf-8")
    object_store.put_bytes(uri, data, "text/csv")
    append_artifact(
        task_id,
        kind="flagged_paragraphs",
        filename="flagged_paragraphs.csv",
        uri=uri,
        size_bytes=len(data),
    )
    return uri, len(data)
