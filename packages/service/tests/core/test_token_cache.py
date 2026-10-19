"""TokenCache 测试 (2026-06-18 redis spec §5.2, 模式 1 mock)

7 场景:
1. hit 返 user dict
2. miss 返 None
3. 6h sliding (每次 set 刷新 TTL)
4. cache 接受 ORM/dict 两种
5. token 存 sha256 不存原值
6. invalidate 删 key
7. Redis 挂时 fail-open 返 None
"""

from __future__ import annotations

import hashlib
import json
from unittest.mock import MagicMock

import pytest
from fakeredis import aioredis as fakeredis

from src.core import redis_client
from src.core.token_cache import (
    CACHE_TTL,
    _cache_key,
    _token_hash,
    cache_user_by_token,
    get_user_by_token,
    invalidate_token,
)


@pytest.fixture
def fake_redis(monkeypatch):
    """fakeredis 替代真 redis. 业务侧 get_redis() 返 FakeRedis."""
    fake = fakeredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(redis_client, "get_redis", lambda: fake)
    monkeypatch.setattr(redis_client, "_pool", None)  # 重置单例
    return fake


@pytest.mark.asyncio
async def test_get_user_by_token_hit(fake_redis):
    """hit 返 user dict"""
    token = "abc123"
    key = _cache_key(token)
    payload = json.dumps({"user_id": 42, "is_admin": True, "is_active": True, "email_hash": "x" * 16})
    await fake_redis.set(key, payload, ex=CACHE_TTL)

    user = await get_user_by_token(token)
    assert user == {"user_id": 42, "is_admin": True, "is_active": True, "email_hash": "x" * 16}


@pytest.mark.asyncio
async def test_get_user_by_token_miss(fake_redis):
    """miss 返 None"""
    assert await get_user_by_token("nonexistent") is None


@pytest.mark.asyncio
async def test_cache_user_by_token_6h_sliding(fake_redis):
    """cache 6h TTL, 每次 set 刷新"""
    token = "abc"
    user_obj = MagicMock(id=42, is_admin=True, is_active=True, email="a@b.com")

    await cache_user_by_token(token, user_obj)
    ttl1 = await fake_redis.ttl(_cache_key(token))
    assert 0 < ttl1 <= CACHE_TTL

    # 模拟时间过 0.1s, 再 set 应刷新 TTL (sliding)
    # sliding 语义: 每次 cache_user 覆盖时刷新到 ~6h (不靠过期自然衰减)
    import asyncio

    await asyncio.sleep(0.1)
    await cache_user_by_token(token, user_obj)
    ttl2 = await fake_redis.ttl(_cache_key(token))
    # 第 2 次写完 TTL 仍应贴近 6h (sliding 核心: 不衰减)
    assert ttl2 >= CACHE_TTL - 5  # fakeredis 允许 1s 误差


@pytest.mark.asyncio
async def test_cache_user_accepts_dict(fake_redis):
    """cache 接受 dict 形式 (兼容 ORM / dict 调用)"""
    token = "abc"
    user_dict = {"id": 10, "is_admin": False, "is_active": True, "email": "x@y.com"}

    await cache_user_by_token(token, user_dict)

    cached = json.loads(await fake_redis.get(_cache_key(token)))
    assert cached["user_id"] == 10
    assert cached["is_admin"] is False
    # email 存 hash, 不存原值
    expected_hash = hashlib.sha256(b"x@y.com").hexdigest()[:16]
    assert cached["email_hash"] == expected_hash


@pytest.mark.asyncio
async def test_token_hash_uses_sha256_not_raw():
    """token 存 sha256, 不存原值 (防 Redis dump 泄露)"""
    token = "supersecret_raw_token_xyz"
    h = _token_hash(token)
    assert h != token
    assert len(h) == 32  # sha256 hex[:32]
    # 验证可重现
    assert h == hashlib.sha256(token.encode()).hexdigest()[:32]


@pytest.mark.asyncio
async def test_invalidate_token(fake_redis):
    """invalidate 删 key"""
    token = "abc"
    await fake_redis.set(_cache_key(token), "{}", ex=CACHE_TTL)

    await invalidate_token(token)
    assert await fake_redis.get(_cache_key(token)) is None


@pytest.mark.asyncio
async def test_get_returns_none_on_redis_down(monkeypatch):
    """Redis 挂时 get 返 None, 不抛 (fail-open)"""

    class FakeRedisDown:
        async def get(self, *a, **k):
            raise ConnectionError("Redis down")

    monkeypatch.setattr(redis_client, "get_redis", lambda: FakeRedisDown())

    result = await get_user_by_token("any")
    assert result is None  # fail-open, 业务侧走 PG
