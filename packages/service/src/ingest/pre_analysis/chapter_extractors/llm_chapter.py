"""LLM 章节工具 (2026-07-09, PDF 章节树状化+LLM增强).

(2026-07-09 spec) 2 个能力:
- llm_refine_chapters(): outline/toc_pages 都失败时, 用 LLM 拿前 30 页文本推断章节.
- llm_summarize_chapters(): 为选中 level 的章节生 2-3 句中文摘要, 分批跑.

不依赖 DB / ObjectStore — 仅依赖 pymupdf doc + LLM 包装.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from loguru import logger

from .chapter_config import ChapterExtractionConfig
from .llm_schemas import LLMChapterOutput, SummaryItem, SummaryOutput

# 默认 LLM 输入文本上限 (字符数), 超长截断防 prompt 溢出
_MAX_INPUT_CHARS = 30000
_MAX_PER_CHAPTER_CHARS = 2000

# 分批大小 (按 provider 控制并发)
_BATCH_OPENAI = 25
_BATCH_OLLAMA = 10

# 前置扫描前 N 页 (页面太多 prompt 装不下)
_SCAN_PAGES = 30

REFINE_PROMPT = (
    "你是 PDF 章节结构提取助手. 根据下方前 {n_pages} 页文本 (--- Page N --- 分隔), "
    "推断章节列表. 输出 JSON, 字段 schema:\n"
    "- chapters: list[{{level: int (1-6), title: str, page_start: int}}]\n"
    "level 1 = 一级章, 缩进=1 子; 严格按文本中出现的标题层级. 不要写没出现的章节.\n\n"
    "{text}\n"
)

SUMMARY_PROMPT = (
    "你是章节摘要助手. 对下列章节各写 2-3 句中文摘要, JSON 输出.\n"
    "schema: {{summaries: list[{{chapter_id: str, summary: str (≤ 500 字)}}]}}\n"
    "按入参列表顺序输出. 没把握就写 '内容不足, 跳过'.\n\n"
    "章节内容:\n{text}\n"
)

# (2026-07-09 retry-on-missing) 重试时追加的提示, 让 LLM 知道哪些章节被遗漏, 必须补齐.
# 不改主 prompt 模板, 只在缺漏时叠加, 避免污染正常 batch.
_MISSING_HINT_SUFFIX = (
    "\n\n[系统校正] 上次回答遗漏以下 chapter_id: {missing_ids}. 本次必须输出, 不能漏. 仍无内容就写 '内容不足, 跳过'.\n"
)


def _slice_pages(doc: Any, n_pages: int) -> str:
    """取 doc 前 n_pages 页纯文本, 用 '--- Page N ---' 分隔, 限 _MAX_INPUT_CHARS 字符."""
    pieces: list[str] = []
    total = 0
    page_count = min(n_pages, len(doc))
    for idx in range(page_count):
        text = (doc[idx].get_text() or "").strip()
        if not text:
            continue
        piece = f"--- Page {idx + 1} ---\n{text}"
        pieces.append(piece)
        total += len(piece)
        if total >= _MAX_INPUT_CHARS:
            break
    return "\n\n".join(pieces)


def _get_llm(provider: str) -> Any:
    """按 provider 返 OpenAILLM / LocalLLM 实例 (重依赖 lazy).

    用 'src.generation.llm' 而非相对 import: 跟项目其它模块 (e.g. buyer_profile/extractor.py)
    一致, 方便测试 monkeypatch; lazy 是为了不冷启动 langchain_openai (~800ms).
    """
    from src.generation.llm import LocalLLM, OpenAILLM  # noqa: PLC0415

    if provider == "ollama":
        return LocalLLM()
    return OpenAILLM()


def _invoke_structured(llm: Any, schema: type, prompt_text: str) -> Any:
    """走 LLM.with_structured_output + json_mode invoke 1 次, 返 Pydantic 实例.

    不走 LCEL '|' operator (测试不易 mock 整个 chain), 改直接 invoke structured chain.
    """
    structured = llm.with_structured_output(schema, method="json_mode")
    return structured.invoke(prompt_text)


def llm_refine_chapters(doc: Any, config: ChapterExtractionConfig) -> list[tuple[int, str, int]]:
    """PDF 无 outline / toc 时, 用 LLM 推断章节 (M3a).

    Args:
        doc: pymupdf Document (已 open).
        config: 章节配置 (用 config.llm_provider 决定走 openai/ollama).

    Returns:
        list[(level, title, page_start), ...] — 可喂 build_chapter_tree.
        失败 (LLM 抛错 / Pydantic 验证失败) → 返 [], 不阻断主流程.
    """
    text = _slice_pages(doc, _SCAN_PAGES)
    if not text:
        logger.warning("llm_refine: 前 {} 页无文本, 跳过", _SCAN_PAGES)
        return []
    from langchain_core.prompts import ChatPromptTemplate  # noqa: PLC0415

    prompt_template = ChatPromptTemplate.from_template(REFINE_PROMPT)
    prompt_text = prompt_template.format(n_pages=_SCAN_PAGES, text=text)
    llm = _get_llm(config.llm_provider)
    try:
        result = _invoke_structured(llm.llm, LLMChapterOutput, prompt_text)
    except Exception as e:
        logger.opt(exception=True).warning("llm_refine: LLM 抛错, 返空 fallback: {}", e)
        return []

    return [(e.level, e.title, e.page_start) for e in result.chapters]  # type: ignore[union-attr]  # result.chapters 是 list


def _iter_chapter_texts(
    doc: Any,
    chapters: list[dict],
    config: ChapterExtractionConfig,
) -> Iterable[tuple[str, str]]:
    """为每个 (level <= max_level) 的 chapter 取前 N 页文本.

    Yields:
        (chapter_id, text) — text 截断到 _MAX_PER_CHAPTER_CHARS.
    """
    n_pages = config.llm_summary_per_chapter_pages
    total_pages = len(doc)
    for ch in chapters:
        if ch["level"] > config.llm_summary_max_level:
            continue
        start = max(0, ch["page_start"] - 1)
        end = min(total_pages, start + n_pages)
        pieces: list[str] = []
        for page_idx in range(start, end):
            pieces.append((doc[page_idx].get_text() or "").strip())
        text = "\n\n".join(p for p in pieces if p)[:_MAX_PER_CHAPTER_CHARS]
        yield (ch["id"], text)


def _summarize_batch(
    llm_instance: Any,
    items: list[tuple[str, str]],
    expected_ids: set[str] | None = None,
) -> list[SummaryItem]:
    """单 batch 摘要: 把多个 chapter 拼成 1 个 prompt, 缺漏时自动重试 1 次.

    Args:
        llm_instance: structured output chain 实例 (OpenAILLM().llm 或 LocalLLM().llm).
        items: [(chapter_id, text), ...] — 单批章节.
        expected_ids: 期望覆盖的 chapter_id 集合. 传 None 时退化为 "items 里所有 id"
            (兼容老调用). 传 set 时按 set 算 missing, 即使 items 含空 text 也算期望.

    (2026-07-09 retry-on-missing) LLM 偶发丢 chapter_id / 截断 JSON. 重试策略:
    - 第 1 次失败 (LLM 抛错) → log warning, 返 [], 整批丢 (旧行为)
    - 第 1 次返了部分 → missing 非空 → 追加 missing 提示重试 1 次
    - 重试仍缺 → log warning, 返现有的 (不完整) 结果, 不再重试
    - 重试成功覆盖全部 → 返完整结果
    """
    if not items:
        return []
    if expected_ids is None:
        expected_ids = {cid for cid, _ in items}
    from langchain_core.prompts import ChatPromptTemplate  # noqa: PLC0415

    text_block = "\n\n".join(f"[chapter_id={cid}]\n{t}" for cid, t in items if t)
    if not text_block:
        return []
    prompt_template = ChatPromptTemplate.from_template(SUMMARY_PROMPT)

    # 第 1 次调用
    prompt_text = prompt_template.format(text=text_block)
    try:
        result = _invoke_structured(llm_instance, SummaryOutput, prompt_text)
        summaries = list(result.summaries)  # type: ignore[union-attr]
    except Exception as e:
        logger.opt(exception=True).warning("llm_summarize: batch 失败, 跳过该批: {}", e)
        return []

    # (2026-07-09) 缺漏校验: 入参期望的 chapter_id 集合 vs 实际返回, 差集重试 1 次
    got_ids = {s.chapter_id for s in summaries}
    missing = expected_ids - got_ids
    if not missing:
        return summaries
    logger.info(
        "llm_summarize: batch 缺 {} 章 (got={}/expected={}), 重试 1 次",
        len(missing),
        len(got_ids),
        len(expected_ids),
    )
    retry_prompt = prompt_text + _MISSING_HINT_SUFFIX.format(missing_ids=sorted(missing))
    try:
        retry_result = _invoke_structured(llm_instance, SummaryOutput, retry_prompt)
        retry_summaries = list(retry_result.summaries)  # type: ignore[union-attr]
    except Exception as e:
        logger.opt(exception=True).warning(
            "llm_summarize: 重试仍失败, 返不完整结果 ({} 章): {}",
            len(summaries),
            e,
        )
        return summaries
    # 合并: 优先用 retry 覆盖同 id (retry 更准), 没覆盖的保留第 1 次
    by_id: dict[str, SummaryItem] = {s.chapter_id: s for s in summaries}
    for s in retry_summaries:
        by_id[s.chapter_id] = s
    final = list(by_id.values())
    final_missing = expected_ids - {s.chapter_id for s in final}
    if final_missing:
        logger.warning(
            "llm_summarize: 重试后仍缺 {} 章, 跳过: {}",
            len(final_missing),
            sorted(final_missing),
        )
    return final


def llm_summarize_chapters(
    doc: Any,
    chapters: list[dict],
    config: ChapterExtractionConfig,
) -> dict[str, str]:
    """为 chapter 生成摘要, 分批.

    Args:
        doc: pymupdf Document (已 open).
        chapters: 嵌套树 list[dict] (来自 chapters_section).
        config: 章节配置.

    Returns:
        {chapter_id: summary} — 部分失败不会影响其他章节, dict 只含成功项.
        (2026-07-09) 缺漏章节会触发单批重试, 重试后仍缺的仅 log warning.
    """
    if not chapters:
        return {}
    llm = _get_llm(config.llm_provider)
    batch_size = _BATCH_OLLAMA if config.llm_provider == "ollama" else _BATCH_OPENAI
    items = list(_iter_chapter_texts(doc, chapters, config))
    summaries: dict[str, str] = {}
    for i in range(0, len(items), batch_size):
        batch = items[i : i + batch_size]
        # (2026-07-09) 传 expected_ids 让 _summarize_batch 能算 missing 触发重试
        expected_ids = {cid for cid, _ in batch}
        for item in _summarize_batch(llm.llm, batch, expected_ids):
            summaries[item.chapter_id] = item.summary
    return summaries


__all__ = [
    "llm_refine_chapters",
    "llm_summarize_chapters",
]
