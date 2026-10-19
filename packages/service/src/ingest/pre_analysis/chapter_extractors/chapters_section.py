"""Stage 2: chapters_section (2026-07-09).

从 runner.py 抽出来. 职责:
1. 调 chapter_extractors.extract_chapters(doc, max_level=...) → 嵌套树 list[dict]
2. (2026-07-09 LLM 摘要) enable_llm_refinement=true → 调 llm_summarize_chapters + 递归回写 summary
3. 拼 chapter_structure.json payload (max_level/total_chapters/toc_source/chapters/llm_summary_enabled)
4. object_store.put_bytes 写产物
5. db_artifact.append_artifact DB append 1 项

(2026-07-09 PDF 章节树状化) payload 加 max_level / toc_source / llm_summary_enabled 字段.
(2026-07-09 LLM 摘要) llm_summary_enabled 反映"实际跑过 LLM + 至少 1 章有 summary" (不再复读 config).

返 (new_ctx, StageResult). ctx 注入 chapters / chapter_uri.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from loguru import logger

from ..db_artifact import append_artifact
from ..stage_context import StageContext, StageResult
from . import count_chapters, extract_chapters
from .chapter_config import ChapterExtractionConfig
from .llm_chapter import llm_summarize_chapters

STAGE_NAME = "extract_chapters"


def _flatten_for_summary(chapters: list[dict], max_level: int) -> list[dict]:
    """递归展平嵌套章节, 只留 level<=max_level (跟 llm_chapter._iter_chapter_texts 行为对齐).

    LLM 函数用 ch['id'] 寻址, 所以 caller 必须传扁平 list (子节点也要走 LLM 摘要).
    """
    out: list[dict] = []
    for ch in chapters:
        if ch["level"] <= max_level:
            out.append(ch)
        children = ch.get("children") or []
        if children:
            out.extend(_flatten_for_summary(children, max_level))
    return out


def _attach_summaries(chapters: list[dict], summaries: dict[str, str]) -> None:
    """递归把 summary 写到匹配的 chapter 节点 (in-place mutate).

    只写 ch['id'] 在 summaries 里的; 没匹配的保持原样 (不删字段, 让 schema 稳定).
    """
    for ch in chapters:
        if ch["id"] in summaries:
            ch["summary"] = summaries[ch["id"]]
        children = ch.get("children") or []
        if children:
            _attach_summaries(children, summaries)


def _build_payload(
    doc: Any,
    chapters: list[dict],
    chapter_config: ChapterExtractionConfig,
    toc_source: str,
    llm_summary_ran: bool,
) -> dict:
    """拼 chapter_structure.json.

    Shape (2026-07-09):
    {
      "max_level": int,  # 配置的截断层
      "total_pages": int,
      "total_chapters": int,  # 截断后所有节点数 (含嵌套)
      "extracted_at": iso8601,
      "toc_source": str,  # "pdf_outline" | "toc_pages" | "llm_refined" | "empty"
      "llm_summary_enabled": bool,  # 实际跑了 LLM 摘要 + 至少 1 章有 summary (不复读 config)
      "chapters": list[dict]  # 嵌套树节点 (每个节点可选 summary 字段)
    }
    """

    return {
        "max_level": chapter_config.chapter_max_level_for_display,
        "total_pages": len(doc),
        "total_chapters": count_chapters(chapters),
        "extracted_at": datetime.now(UTC).isoformat(),
        "toc_source": toc_source,
        "llm_summary_enabled": llm_summary_ran,
        "chapters": chapters,
    }


def run(
    ctx: StageContext,
    chapter_config: ChapterExtractionConfig | None = None,
) -> tuple[StageContext, StageResult]:
    """Stage 2: 提取章节 + 写 chapter_structure.json + DB append.

    Args:
        ctx: stage 上下文.
        chapter_config: 章节提取配置, None → 走默认 ChapterExtractionConfig().
    """
    if chapter_config is None:
        chapter_config = ChapterExtractionConfig()
    ctx.stage_store.mark_stage_started(ctx.task_id, STAGE_NAME)
    try:
        doc = ctx.doc
        assert doc is not None  # type: ignore[unreachable]  # stage 1 成功后 ctx.doc 必填
        chapters = extract_chapters(doc, max_level=chapter_config.chapter_max_level_for_display)
        toc_source = "pdf_outline" if chapters else "empty"
        # (2026-07-09 LLM 摘要) enable_llm_refinement=true + 实际有章节 → 调 LLM 摘要 + 回写.
        # llm_summary_ran 反映"真跑了", payload 用它, 不复读 config (避免 ui 误信).
        llm_summary_ran = False
        if chapter_config.enable_llm_refinement and chapters:
            flat = _flatten_for_summary(chapters, chapter_config.llm_summary_max_level)
            if flat:
                try:
                    summaries = llm_summarize_chapters(doc, flat, chapter_config)
                except Exception as e:  # noqa: BLE001  # LLM 任何错都不阻断主流程
                    logger.opt(exception=True).warning(
                        "chapters_section: llm_summarize_chapters 抛错, 跳过摘要: {}",
                        e,
                    )
                    summaries = {}
                if summaries:
                    _attach_summaries(chapters, summaries)
                    llm_summary_ran = True
                    logger.info(
                        "chapters_section: LLM 摘要 task={} summaries={}/{}",
                        ctx.task_id,
                        len(summaries),
                        len(flat),
                    )
        payload = _build_payload(doc, chapters, chapter_config, toc_source, llm_summary_ran)
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        uri = f"{ctx.output_prefix}/chapter_structure.json"
        ctx.object_store.put_bytes(uri, data, "application/json")
        append_artifact(
            ctx.task_id,
            kind="chapter_structure",
            filename="chapter_structure.json",
            uri=uri,
            size_bytes=len(data),
        )
    except Exception as e:
        ctx.stage_store.mark_stage_failed(ctx.task_id, STAGE_NAME, str(e))
        ctx.task_store.mark_failed(
            ctx.task_id,
            f"{STAGE_NAME} failed: {e}",
            stages_provider=ctx.stage_store.list_stages,
        )
        logger.opt(exception=True).error("pre_analysis {} failed task={}", STAGE_NAME, ctx.task_id)
        return ctx, StageResult(ok=False, error=str(e), stage_name=STAGE_NAME)

    # (2026-07-09) message 用递归总数, 跟 payload.total_chapters 一致 (含嵌套子章节)
    total_chapters = count_chapters(chapters)
    ctx.stage_store.mark_stage_completed(ctx.task_id, STAGE_NAME, progress=100, message=f"{total_chapters} 章")
    return ctx.replace(chapters=chapters, chapter_uri=uri), StageResult(
        ok=True, stage_name=STAGE_NAME, message=f"{total_chapters} 章"
    )


__all__ = ["run", "STAGE_NAME", "_build_payload"]
