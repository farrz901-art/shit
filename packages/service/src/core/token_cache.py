"""Auth token Redis 缓存 (2026-06-18 redis spec §5.2)

resolve_user 每请求查 PG 拿 user. 改 Redis 缓存 6h sliding, hot path 0 PG.
- key: rag:auth:tok:{sha256(token)[:32]} (不存原 token, 防 dump 泄露)
- value: JSON {user_id, is_admin, is_active, email_hash}
- TTL: 6h, 每次访问 set 刷新 (sliding)
- fail-open: Redis 挂 → 返 None, 业务侧走原 PG 路径
"""

from __future__ import annotations

import hashlib
import json
import os
from typing import Any

from loguru import logger

from .redis_client import safe_delete, safe_get, safe_set

CACHE_TTL = int(os.getenv("TOKEN_CACHE_TTL", "21600"))  # 6h
TOKEN_KEY_PREFIX = "rag:auth:tok:"


def _token_hash(token: str) -> str:
    """sha256(token)[:32] hex. 不存原 token."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()[:32]


def _cache_key(token: str) -> str:
    return f"{TOKEN_KEY_PREFIX}{_token_hash(token)}"


async def get_user_by_token(token: str) -> dict[str, Any] | None:
    """查 token 对应 user. miss 返 None (业务侧走 PG).

    Returns:
        dict {user_id, is_admin, is_active, email_hash} 或 None
    """
    key = _cache_key(token)
    raw = await safe_get(key)
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("token cache 损坏 key={}, 当 miss 处理", key)
        return None


async def cache_user_by_token(token: str, user_obj: Any) -> None:
    """缓存 user 6h (sliding, 每次 set 刷新 TTL).

    Args:
        token: 原始 token 字符串
        user_obj: ORM User 对象 或 dict {"id":..., "is_admin":..., "is_active":..., "email":...}
    """

    def _get(obj, key, default=None):
        if isinstance(obj, dict):
            return obj.get(key, default)
        return getattr(obj, key, default)

    payload = json.dumps(
        {
            "user_id": _get(user_obj, "id"),
            "is_admin": _get(user_obj, "is_admin", False),
            "is_active": _get(user_obj, "is_active", True),
            "email_hash": hashlib.sha256((_get(user_obj, "email", "") or "").encode()).hexdigest()[:16],
        }
    )
    await safe_set(_cache_key(token), payload, ex=CACHE_TTL)


async def invalidate_token(token: str) -> None:
    """登出 / 改密时踢缓存."""
    await safe_delete(_cache_key(token))
