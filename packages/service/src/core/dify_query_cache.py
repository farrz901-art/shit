"""Dify 检索响应缓存 (2026-06-18 redis spec §5.5)

Dify 检索每次扣 token, 重复 query 重复扣. 加 10min TTL cache.

2 类缓存 (同 module, 共享 TTL/前缀命名):
1. 检索响应 (list[dict]): spec 设计的接口, 留作未来直接 search 用
   - key: rag:dify:q:{sha256(dataset_id:top_k:query)[:16]}
   - value: JSON list[dict]
2. Chat 响应 (dict): 现有 dify.achat() 实际返的形状, 业务侧常用
   - key: rag:dify:chat:{sha256(query)[:16]}
   - value: JSON dict (answer/contexts/sources/...)

共同约定:
- TTL: 10min 纯 TTL (ingest 后最多 10min 旧结果, 业务可接受)
- fail-open: Redis 挂 → 返 None, 业务侧直调 Dify
"""

from __future__ import annotations

import hashlib
import json
import os
from typing import Any

from loguru import logger

from .redis_client import safe_get, safe_set

TTL = int(os.getenv("DIFY_QUERY_CACHE_TTL", "600"))  # 10min
KEY_PREFIX = "rag:dify:q:"
CHAT_KEY_PREFIX = "rag:dify:chat:"


def _key(query: str, dataset_id: str, top_k: int) -> str:
    """生成 Redis key. 格式: rag:dify:q:{sha256(dataset_id:top_k:query)[:16]}

    不同 top_k 独立 cache, 避免 5 跟 10 撞. 用 sha256[:16] 16 字节 = 64 bit 空间,
    撞概率 ~1/2^64, 业务上可忽略.
    """
    raw = f"{dataset_id}:{top_k}:{query}"
    h = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    return f"{KEY_PREFIX}{h}"


def _chat_key(query: str) -> str:
    """生成 chat cache key. 格式: rag:dify:chat:{sha256(query)[:16]}

    chat 接口 (dify.achat) 走的是工作流, dataset / top_k 在 Dify 端配置,
    业务侧调用方只有 query, 所以 key 只 hash query.
    """
    h = hashlib.sha256(query.encode("utf-8")).hexdigest()[:16]
    return f"{CHAT_KEY_PREFIX}{h}"


async def get_cached_response(query: str, dataset_id: str, top_k: int) -> list[dict] | None:
    """查检索响应缓存. miss / Redis 挂 / JSON 损坏 / 数据非 list 都返 None.

    Args:
        query: 用户问题
        dataset_id: Dify dataset id
        top_k: 检索 top k

    Returns:
        list[dict] (cached response) 或 None (cache miss)
    """
    key = _key(query, dataset_id, top_k)
    raw = await safe_get(key)
    if raw is None:
        return None
    try:
        result = json.loads(raw)
        if not isinstance(result, list):
            logger.warning("dify query cache 数据格式非 list key={}, 当 miss 处理", key)
            return None
        return result
    except json.JSONDecodeError:
        logger.warning("dify query cache JSON 损坏 key={}, 当 miss 处理", key)
        return None


async def cache_response(query: str, dataset_id: str, top_k: int, response: list[dict]) -> None:
    """写检索响应缓存 10min. facade safe_set 内部已 catch + log CRITICAL, 失败不抛.

    Args:
        query: 用户问题
        dataset_id: Dify dataset id
        top_k: 检索 top k
        response: dify 检索响应 (list[dict])
    """
    key = _key(query, dataset_id, top_k)
    await safe_set(key, json.dumps(response), ex=TTL)


async def get_cached_chat_response(query: str) -> dict[str, Any] | None:
    """查 chat 响应缓存 (dify.achat 实际返的 dict 形状). miss 返 None.

    Args:
        query: 用户问题

    Returns:
        dict (含 answer/contexts/sources/raw/...) 或 None (cache miss)
    """
    key = _chat_key(query)
    raw = await safe_get(key)
    if raw is None:
        return None
    try:
        result = json.loads(raw)
        if not isinstance(result, dict):
            logger.warning("dify chat cache 数据格式非 dict key={}, 当 miss 处理", key)
            return None
        return result
    except json.JSONDecodeError:
        logger.warning("dify chat cache JSON 损坏 key={}, 当 miss 处理", key)
        return None


async def cache_chat_response(query: str, response: dict[str, Any]) -> None:
    """写 chat 响应缓存 10min. 失败不抛 (safe_set 内部已 catch).

    Args:
        query: 用户问题
        response: dify.achat() 返回的 dict
    """
    key = _chat_key(query)
    await safe_set(key, json.dumps(response), ex=TTL)
