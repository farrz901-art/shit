"""Embedding 向量缓存 (2026-06-18 redis spec §5.6)

embed_texts 每次调 OpenAI 扣 token. 加 7d TTL cache.
- key: rag:embed:{sha256(text[:512])[:16]}  (16 字节前缀, 长文本不重复 hash)
- value: base64(f32[])  (紧凑, 比 JSON 省 50% 空间)
- TTL: 7d
- fail-open: Redis 挂 → 返 None, 直调 OpenAI
"""

from __future__ import annotations

import base64
import hashlib
import os
import struct
from collections.abc import Sequence

from .redis_client import safe_get, safe_set

TTL = int(os.getenv("EMBED_CACHE_TTL", str(7 * 86400)))  # 7d
KEY_PREFIX = "rag:embed:"


def _key(text: str) -> str:
    """只 hash 前 512 字符 (长文本 hash 慢 + key 撞率高)."""
    h = hashlib.sha256(text[:512].encode("utf-8")).hexdigest()[:16]
    return f"{KEY_PREFIX}{h}"


def _encode(vec: Sequence[float]) -> str:
    """f32[] → base64 (紧凑, 比 JSON 省 50% 空间)."""
    return base64.b64encode(struct.pack(f"<{len(vec)}f", *vec)).decode("ascii")


def _decode(raw: str) -> list[float]:
    """base64 → f32[] → list[float]."""
    data = base64.b64decode(raw)
    n = len(data) // 4
    return list(struct.unpack(f"<{n}f", data))


async def get_cached_vector(text: str) -> list[float] | None:
    """查 embedding 缓存. miss / Redis 挂 / 数据损坏都返 None.

    Returns:
        list[float] (cached vector) 或 None (cache miss)
    """
    raw = await safe_get(_key(text))
    if raw is None:
        return None
    try:
        return _decode(raw)
    except Exception:
        # 损坏数据当 miss 处理, 不阻塞业务
        return None


async def cache_vector(text: str, vec: Sequence[float]) -> None:
    """写 embedding 缓存 7d. facade safe_set 内部已 catch + log CRITICAL, 失败不抛.

    Args:
        text: 原始文本
        vec: embedding 向量 (list[float] / tuple[float] / numpy.ndarray 都可, 只要 len() + 迭代)
    """
    await safe_set(_key(text), _encode(vec), ex=TTL)
