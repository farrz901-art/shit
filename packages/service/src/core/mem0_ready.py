"""Mem0 ready 标记 (2026-06-18 redis spec §5.4)

mem0 self-host Memory 实例不可序列化 (含 pgvector 连接), 进程内存 dict 仍存实例.
Redis 仅存 ready 标记, 跨 worker decorrelation:
- 避免 N 个 worker 同时 warmup 同一 user (warmup 慢 ~5s)
- 失败 fail-open: Redis 挂 → is_ready 返 False, 各 worker 自己构造
"""

from __future__ import annotations

import os

from .redis_client import safe_get, safe_set

READY_TTL = int(os.getenv("MEM0_READY_TTL", "3600"))  # 1h
KEY_PREFIX = "rag:mem0:user:"


def _key(user_id: str) -> str:
    """生成 ready 标记的 Redis key. 格式: rag:mem0:user:{user_id}:ready"""
    return f"{KEY_PREFIX}{user_id}:ready"


async def mark_ready(user_id: str) -> None:
    """worker 构造完 Memory 实例后调, 标记 ready 1h.

    失败 (Redis 挂) 不抛: facade safe_set 内部已 catch + log CRITICAL.
    """
    await safe_set(_key(user_id), "1", ex=READY_TTL)


async def is_ready(user_id: str) -> bool:
    """查询其他 worker 是否已 ready. miss/fail 返 False (本 worker 自己构造).

    Returns:
        bool: True = 已有 worker 完成 warmup, False = 未标记 / Redis 挂.
    """
    val = await safe_get(_key(user_id))
    return val == "1"
