"""批量工具函数：embedding、token 估算、文本截断"""

import asyncio
import inspect
import math
import re
from collections.abc import Iterable, Iterator
from typing import Any


def estimate_tokens(text: str, encoding_name: str = "cl100k_base") -> int:
    """估算 token 数，优先 tiktoken，失败用经验公式"""
    try:
        # 软依赖: tiktoken 未装时降级到经验公式
        import tiktoken  # noqa: E402

        enc = tiktoken.get_encoding(encoding_name)
        return len(enc.encode(text, disallowed_special=()))
    except Exception:
        chinese_chars = len(re.findall(r"[一-鿿]", text))
        other_chars = len(text) - chinese_chars
        return int(math.ceil(chinese_chars / 2.0)) + int(math.ceil(other_chars / 4.0))


def truncate_text(text: str, max_chars: int = 500) -> str:
    """截断超长文本"""
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + f" ... [省略 {len(text) - max_chars} 字符]"


def _batch_iter(items: list[Any], batch_size: int) -> Iterator[list[Any]]:
    for i in range(0, len(items), batch_size):
        yield items[i : i + batch_size]


def batch_embed(
    chunks: Iterable[str],
    embedder: Any,
    batch_size: int = 32,
    show_progress: bool = True,
) -> list[list[float]]:
    """批量 embedding 带进度条"""
    chunk_list = list(chunks)
    if not chunk_list:
        return []

    try:
        # 软依赖: tqdm 未装时降级到 no-op 进度条
        from tqdm import tqdm  # noqa: E402

        has_tqdm = True
    except ImportError:
        has_tqdm = False

    results: list[list[float]] = []
    # tqdm 不实现 Iterator 协议 (__next__), 显式标注会冲突
    # 拆成两个变量: bare_iter (类型干净) + iterator (实际用的, tqdm 或 bare)
    bare_iter: Iterator[list[str]] = _batch_iter(chunk_list, batch_size)

    if has_tqdm and show_progress:
        iterator: Iterator[list[str]] = tqdm(  # type: ignore[assignment]
            bare_iter,
            total=math.ceil(len(chunk_list) / batch_size),
            desc="embedding",
            unit="batch",
        )
    else:
        iterator = bare_iter

    for batch in iterator:
        if (
            hasattr(embedder, "aget_embeddings")
            and callable(embedder.aget_embeddings)
            and inspect.iscoroutinefunction(embedder.aget_embeddings)
        ):
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            batch_results = loop.run_until_complete(embedder.aget_embeddings(batch))
        else:
            batch_results = embedder.get_embeddings(batch)
        results.extend(batch_results)
    return results
