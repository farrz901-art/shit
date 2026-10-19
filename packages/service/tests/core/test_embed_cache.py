"""EmbedCache 测试 (2026-06-18 redis spec §5.6, 模式 1 mock)"""

from __future__ import annotations

import pytest
from fakeredis import aioredis as fakeredis

from src.core import redis_client
from src.core.embed_cache import (
    TTL,
    _decode,
    _encode,
    _key,
    cache_vector,
    get_cached_vector,
)


@pytest.fixture
def fake_redis(monkeypatch):
    """fakeredis 替代真 redis. 业务侧 get_redis() 返 FakeRedis."""
    fake = fakeredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(redis_client, "get_redis", lambda: fake)
    return fake


@pytest.mark.asyncio
async def test_get_cached_vector_hit(fake_redis):
    """hit 返 list[float], f32 精度 ~1e-5"""
    text = "RAG is a technique"
    vec = [0.1, 0.2, 0.3, -0.4]
    await cache_vector(text, vec)

    cached = await get_cached_vector(text)
    assert cached is not None
    # f32 精度有 ~1e-7 误差
    for a, b in zip(cached, vec):
        assert abs(a - b) < 1e-5


@pytest.mark.asyncio
async def test_get_cached_vector_miss(fake_redis):
    """miss 返 None"""
    assert await get_cached_vector("nonexistent text") is None


@pytest.mark.asyncio
async def test_cache_vector_7d_ttl(fake_redis):
    """7d TTL = 7*86400"""
    text = "test"
    await cache_vector(text, [0.1, 0.2])
    ttl = await fake_redis.ttl(_key(text))
    assert 0 < ttl <= TTL
    assert TTL == 7 * 86400  # 7d
    # key 前缀符合 spec
    assert _key(text).startswith("rag:embed:")


@pytest.mark.asyncio
async def test_long_text_hash_uses_first_512_chars(fake_redis):
    """长文本只 hash 前 512 字符 (text1[:512] == text2[:512] 撞 key)"""
    text1 = "x" * 1000
    text2 = "x" * 600 + "different"  # text2[:512] == text1[:512] == "x"*512
    await cache_vector(text1, [1.0])
    cached = await get_cached_vector(text2)
    assert cached == [1.0]  # 撞 key, 这种极罕见


@pytest.mark.asyncio
async def test_base64_roundtrip():
    """_encode / _decode roundtrip (无 Redis 依赖)"""
    vec = [0.1, -0.2, 0.3, 0.0, 0.5]
    encoded = _encode(vec)
    # base64 比 JSON 紧凑: 5 floats f32 = 20 bytes → base64 28 chars
    assert len(encoded) < 100
    decoded = _decode(encoded)
    for a, b in zip(decoded, vec):
        assert abs(a - b) < 1e-7


@pytest.mark.asyncio
async def test_get_returns_none_on_redis_down(monkeypatch):
    """Redis 挂时 get 返 None, 业务侧直调 OpenAI (fail-open)"""

    class FakeRedisDown:
        async def get(self, *a, **k):
            raise ConnectionError("Redis down")

        async def set(self, *a, **k):
            raise ConnectionError("Redis down")

    monkeypatch.setattr(redis_client, "get_redis", lambda: FakeRedisDown())

    assert await get_cached_vector("any") is None
    await cache_vector("any", [0.1])  # no-op, 不抛
