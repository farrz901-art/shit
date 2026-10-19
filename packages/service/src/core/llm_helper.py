"""LLM 工具: 跨页续表重复 header 检测 (2026-07-09).

(2026-07-09 评审调整 #2) 同步函数, 因为调用链全 sync (extract() → merge()).
(2026-07-09 评审调整 #3) 复用 src/generation/llm.py 已有 OpenAILLM / LocalLLM,
不硬编码 qwen2.5-coder:7b, 走 env LLM_MODEL 默认, LLM_TRIM_HEADER_MODEL 显式覆盖.
"""

from __future__ import annotations

import hashlib
import json
import os
from functools import lru_cache

from .errors import LLMParsingError, LLMUnavailableError

# (2026-07-09) prompt 模板: 让 LLM 判断 curr 表头是否 prev 重复
PROMPT = """你是一个 PDF 表格分析助手. 下面是两张相邻页的表格片段, 判断下表 (current) 的表头是不是上表 (previous) 的表头重复.

Previous 表头 (含):
{prev_rows}

Current 表头 (前 5 行):
{curr_rows}

如果 Current 表头是 Previous 表头的重复 (只是因为跨页拆开), 告诉我 "is_repeated=true" 并指出需跳过的行数.
如果 Current 表头是新的 (例如 "Selection table continued" 标识行 + 真表头), 告诉我 "is_repeated=false".

严格按 JSON 格式返:
{{"is_repeated": true/false, "rows_to_skip": N}}

不要解释. 只返 JSON."""


def _get_llm_client(llm_model: str | None):
    """(2026-07-09) 取 LLM 客户端, 复用 src/generation/llm.py.

    优先用 env LLM_TRIM_HEADER_MODEL, 否则 LLM_MODEL.
    客户端不可用 (没装 ollama / openai key 没配) → 抛 LLMUnavailableError.

    Returns:
        一个有 .invoke(prompt) -> AIMessage 接口的对象 (langchain BaseChatModel).

    Raises:
        LLMUnavailableError: 客户端初始化失败
    """
    model = llm_model or os.getenv("LLM_TRIM_HEADER_MODEL") or os.getenv("LLM_MODEL")
    # 重依赖 lazy: langchain_ollama 冷启动 ~600ms, 非 ollama 路径不需要
    try:
        from src.generation.llm import LocalLLM, OpenAILLM  # noqa: PLC0415
    except ImportError as e:
        raise LLMUnavailableError(f"src.generation.llm import failed: {e}") from e

    # 探测 provider: 优先 ollama (env OLLAMA_BASE_URL 配了), 否则 openai
    if os.getenv("OLLAMA_BASE_URL"):
        try:
            return LocalLLM(model=model).llm
        except Exception as e:  # noqa: BLE001  # 业务故意 broad: 客户端初始化失败统一捕获
            raise LLMUnavailableError(f"Ollama 客户端初始化失败: {e}", backend="ollama") from e
    try:
        return OpenAILLM(model=model).llm
    except Exception as e:  # noqa: BLE001
        raise LLMUnavailableError(f"OpenAI 客户端初始化失败: {e}", backend="openai") from e


def _header_signature(rows: list[list[str]]) -> str:
    """(2026-07-09) 取 rows 前 3 行做 sha256[:16] 签名, 给 LRU cache key 用."""
    head = "\n".join("|".join(row) for row in rows[:3])
    return hashlib.sha256(head.encode()).hexdigest()[:16]


def _trim_repeated_header_uncached(
    prev_rows: list[list[str]],
    curr_rows: list[list[str]],
    page_a: int,
    page_b: int,
    llm_model: str | None,
) -> tuple[bool, int]:
    """(2026-07-09) 实际调 LLM 的内部函数, 外面套 lru_cache."""
    client = _get_llm_client(llm_model)
    prompt = PROMPT.format(
        prev_rows=json.dumps(prev_rows, ensure_ascii=False),
        curr_rows=json.dumps(curr_rows[:5], ensure_ascii=False),
    )
    try:
        resp = client.invoke(prompt)
    except Exception as e:  # noqa: BLE001  # 业务故意 broad: 网络 / 超时都接
        raise LLMUnavailableError(f"LLM invoke 失败: {e}") from e

    content = getattr(resp, "content", str(resp))
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as e:
        raise LLMParsingError(f"LLM 返 invalid JSON: {content[:200]}", raw_response=content) from e

    is_repeated = bool(parsed.get("is_repeated", False))
    rows_to_skip = int(parsed.get("rows_to_skip", 0))
    return (is_repeated, rows_to_skip)


# (2026-07-09) LRU cache by (prev_page, curr_page, prev_sig, curr_sig).
# maxsize=128 跨进程不共享 (本期不接 Redis).
@lru_cache(maxsize=128)
def _trim_repeated_header_cached(
    prev_sig: str,
    curr_sig: str,
    page_a: int,
    page_b: int,
    llm_model: str | None,
    prev_rows_tuple: tuple,
    curr_rows_tuple: tuple,
) -> tuple[bool, int]:
    """(2026-07-09) LRU cache wrapper. 用 signature 而非完整 rows 当 key 节省内存."""
    prev_rows = [list(r) for r in prev_rows_tuple]
    curr_rows = [list(r) for r in curr_rows_tuple]
    return _trim_repeated_header_uncached(prev_rows, curr_rows, page_a, page_b, llm_model)


def trim_repeated_header(
    prev_rows: list[list[str]],
    curr_rows: list[list[str]],
    *,
    page_a: int = 0,
    page_b: int = 0,
    llm_model: str | None = None,
) -> tuple[bool, int]:
    """(2026-07-09) 调 LLM 判 curr 表头是否 prev 重复 (sync, LRU cache).

    Args:
        prev_rows: 上 1 页表的全部 rows (含表头).
        curr_rows: 下 1 页表的全部 rows (含表头).
        page_a: 上 1 页页码 (给 cache key 用).
        page_b: 下 1 页页码 (给 cache key 用).
        llm_model: LLM 模型名. None → env LLM_TRIM_HEADER_MODEL / LLM_MODEL.

    Returns:
        (is_repeated, rows_to_skip) — is_repeated=True 时返需跳过的行数.

    Raises:
        LLMUnavailableError: LLM 客户端不可用 / invoke 失败.
        LLMParsingError: LLM 返 invalid JSON.
    """
    # rows 转 tuple 才能 hash 给 lru_cache
    prev_rows_tuple = tuple(tuple(r) for r in prev_rows)
    curr_rows_tuple = tuple(tuple(r) for r in curr_rows)
    return _trim_repeated_header_cached(
        _header_signature(prev_rows),
        _header_signature(curr_rows),
        page_a,
        page_b,
        llm_model,
        prev_rows_tuple,
        curr_rows_tuple,
    )


__all__ = ["trim_repeated_header", "LLMUnavailableError", "LLMParsingError"]
