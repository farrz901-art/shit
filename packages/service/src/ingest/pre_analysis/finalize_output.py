"""Stage 5: finalize_output (2026-07-09).

从 runner.py 抽出来. 职责:
1. 累计 DB output_files_json (从各 stage append 后的最终列表)
2. 写 index.json (final snapshot, 含 summary + files 列表)
3. db_artifact.append_artifact DB append 1 项 (index 自身)
4. mark_stage_completed + task_store.mark_completed
5. 失败 → mark_stage_failed + mark_failed

返 (new_ctx, StageResult). ctx 注入 index_uri.
"""

from __future__ import annotations

import json
import time

from loguru import logger

from ...storage import session_scope
from .chapter_extractors import count_chapters
from .db_artifact import append_artifact
from .models import PreAnalysisTask
from .stage_context import StageContext, StageResult

STAGE_NAME = "write_outputs"


def run(
    ctx: StageContext,
    table_extraction_config: dict | None = None,
) -> tuple[StageContext, StageResult]:
    """Stage 5: 写 index.json + mark_completed.

    Args:
        ctx: StageContext (要 task_id / pdf_uri / object_store / output_prefix / chapters /
            tables / flagged / cross_page_count / chapter_uri / flagged_uri / start_monotonic).
        table_extraction_config: 透传给 task_store.mark_completed 作 task_config.

    Returns: (new_ctx, StageResult). new_ctx 注入 index_uri.
    """
    if table_extraction_config is None:
        table_extraction_config = {}
    ctx.stage_store.mark_stage_started(ctx.task_id, STAGE_NAME)
    try:
        elapsed_ms = int((time.monotonic() - ctx.start_monotonic) * 1000)
        # 累计 output_files_json 来自 DB
        final_files: list[dict] = []
        with session_scope() as s:
            task = s.get(PreAnalysisTask, ctx.task_id)
            if task is not None:
                final_files = json.loads(task.output_files_json or "[]")
        # 拼 index.json payload
        payload = {
            "task_id": ctx.task_id,
            "pdf_filename": ctx.pdf_uri.rsplit("/", 1)[-1],
            "elapsed_ms": elapsed_ms,
            "summary": {
                # (2026-07-09) 改用递归总数, 跟 chapters_section.message / chapter_structure.json 对齐
                "total_chapters": count_chapters(ctx.chapters) if ctx.chapters else 0,
                "total_tables": len(ctx.tables) if ctx.tables else 0,
                "total_flagged_paragraphs": len(ctx.flagged) if ctx.flagged else 0,
                "cross_page_candidates": ctx.cross_page_count,
            },
            "files": final_files,
        }
        index_uri = f"{ctx.output_prefix}/index.json"
        index_data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        ctx.object_store.put_bytes(index_uri, index_data, "application/json")
        append_artifact(
            ctx.task_id,
            kind="index",
            filename="index.json",
            uri=index_uri,
            size_bytes=len(index_data),
        )

        # 累计 output_files 重新读 (含 index 自身)
        final_output_files = final_files + [
            {
                "kind": "index",
                "filename": "index.json",
                "uri": index_uri,
                "size_bytes": len(index_data),
            }
        ]
        ctx.task_store.mark_completed(
            task_id=ctx.task_id,
            output_files=final_output_files,
            summary={
                "total_chapters": payload["summary"]["total_chapters"],
                "total_tables": payload["summary"]["total_tables"],
                "total_flagged_paragraphs": payload["summary"]["total_flagged_paragraphs"],
                "elapsed_ms": elapsed_ms,
                "cross_page_candidates": payload["summary"]["cross_page_candidates"],
            },
            task_config=table_extraction_config,
        )
        # (2026-07-09) 跟原 runner._write_index 行为对齐: 写完后改 task.current_stage='done' 留 hook
        with session_scope() as s:
            task2 = s.get(PreAnalysisTask, ctx.task_id)
            if task2 is not None:
                task2.current_stage = "done"
    except Exception as e:
        ctx.stage_store.mark_stage_failed(ctx.task_id, STAGE_NAME, str(e))
        ctx.task_store.mark_failed(
            ctx.task_id,
            f"{STAGE_NAME} failed: {e}",
            stages_provider=ctx.stage_store.list_stages,
        )
        logger.opt(exception=True).error("pre_analysis {} failed task={}", STAGE_NAME, ctx.task_id)
        return ctx, StageResult(ok=False, error=str(e), stage_name=STAGE_NAME)

    ctx.stage_store.mark_stage_completed(ctx.task_id, STAGE_NAME, progress=100)
    logger.info(
        "pre_analysis done task={} chapters={} tables={} flagged={} elapsed={}ms",
        ctx.task_id,
        payload["summary"]["total_chapters"],
        payload["summary"]["total_tables"],
        payload["summary"]["total_flagged_paragraphs"],
        elapsed_ms,
    )
    return ctx.replace(index_uri=index_uri), StageResult(ok=True, stage_name=STAGE_NAME, message="done")


__all__ = ["run", "STAGE_NAME"]
