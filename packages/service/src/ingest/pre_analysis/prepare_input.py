"""Stage 1: prepare_input (2026-07-09).

从 runner.py 抽出来. 职责:
1. object_store.open_local(pdf_uri) → 本地路径
2. pymupdf.open(path) → Document
3. 加载 rule_keywords.yaml (缺失/解析失败 → 兜底默认 5 关键词)
4. 拼 output_prefix (按 object_store backend 选 local:// or s3:// scheme)

返 (new_ctx, StageResult). ctx 注入 doc / config / output_prefix.
"""

from __future__ import annotations

import os
from pathlib import Path

import pymupdf
import yaml
from loguru import logger

from .stage_context import StageContext, StageResult

STAGE_NAME = "prepare_input"

# 兜底默认关键词. 原 runner._load_config 行为: yaml 缺失/解析失败 → 返回这 5 个.
DEFAULT_KEYWORDS = ["注意", "不能", "仅适用", "必须", "禁止"]


def _resolve_keyword_path() -> Path:
    """从 RULE_KEYWORDS_PATH env 找 yaml 路径, 默认 conf/rule_keywords.yaml."""
    env = os.getenv("RULE_KEYWORDS_PATH")
    return Path(env) if env else Path("conf/rule_keywords.yaml")


def _output_prefix_for(backend: str, task_id: str) -> str:
    """原 runner._output_prefix: local 走 local:// scheme, 其他走 s3:// 配 OBJECT_STORE_S3_BUCKET env."""
    if backend == "local":
        return f"local://pre_analysis_outputs/{task_id}"
    bucket = os.getenv("OBJECT_STORE_S3_BUCKET", "rag-ingest")
    return f"s3://{bucket}/pre_analysis_outputs/{task_id}"


def _load_keywords_config() -> dict:
    """原 runner._load_config: yaml 缺失/解析失败 → 兜底默认 (fail-open)."""
    path = _resolve_keyword_path()
    try:
        with path.open(encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception as e:
        logger.warning("rule_keywords.yaml load failed err={}, 兜底默认", e)
        return {"keywords": DEFAULT_KEYWORDS}


def prepare_input(ctx: StageContext) -> tuple[StageContext, StageResult]:
    """Stage 1: 打开 PDF + 加载 yaml + 拼 output_prefix. 失败返 ok=False."""
    ctx.stage_store.mark_stage_started(ctx.task_id, STAGE_NAME)
    try:
        pdf_path = ctx.object_store.open_local(ctx.pdf_uri)
        doc = pymupdf.open(pdf_path)
    except Exception as e:
        ctx.stage_store.mark_stage_failed(ctx.task_id, STAGE_NAME, str(e))
        ctx.task_store.mark_failed(
            ctx.task_id,
            f"open failed: {e}",
            stages_provider=ctx.stage_store.list_stages,
        )
        logger.opt(exception=True).error("pre_analysis open failed task={} uri={}", ctx.task_id, ctx.pdf_uri)
        return ctx, StageResult(ok=False, error=str(e), stage_name=STAGE_NAME)

    config = _load_keywords_config()
    output_prefix = _output_prefix_for(ctx.object_store.backend_name(), ctx.task_id)
    ctx.stage_store.mark_stage_completed(ctx.task_id, STAGE_NAME, progress=100, message="open ok")

    return (
        ctx.replace(doc=doc, config=config, output_prefix=output_prefix),
        StageResult(ok=True, stage_name=STAGE_NAME, message="open ok"),
    )


__all__ = ["prepare_input", "STAGE_NAME"]
