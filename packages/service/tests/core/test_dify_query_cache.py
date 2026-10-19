"""DifyQueryCache 测试 (2026-06-18 redis spec §5.5, 模式 1 mock)

5 场景:
- hit 返 list[dict]
- miss 返 None
- 10min TTL
- 不同 top_k 独立 cache
- Redis 挂 fail-open
"""

from __future__ import annotations

import pytest
from fakeredis import aioredis as fakeredis

from src.core import redis_client
from src.core.dify_query_cache import (
    KEY_PREFIX,
    TTL,
    _key,
    cache_response,
    get_cached_response,
)


@pytest.fixture
def fake_redis(monkeypatch):
    """fakeredis 替代真 redis. 业务侧 get_redis() 返 FakeRedis."""
    fake = fakeredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(redis_client, "get_redis", lambda: fake)
    return fake


@pytest.mark.asyncio
async def test_get_cached_response_hit(fake_redis):
    """hit 返 list[dict]"""
    query = "What is RAG?"
    dataset_id = "ds-1"
    response = [{"id": "1", "content": "answer", "score": 0.9}]
    await cache_response(query, dataset_id, top_k=5, response=response)

    cached = await get_cached_response(query, dataset_id, top_k=5)
    assert cached == response


@pytest.mark.asyncio
async def test_get_cached_response_miss(fake_redis):
    """miss 返 None"""
    result = await get_cached_response("nonexistent", "ds-1", top_k=5)
    assert result is None


@pytest.mark.asyncio
async def test_cache_response_10min_ttl(fake_redis):
    """10min TTL = 600"""
    await cache_response("q", "ds-1", top_k=5, response=[])
    key = _key("q", "ds-1", 5)
    ttl = await fake_redis.ttl(key)
    assert 0 < ttl <= TTL
    assert TTL == 600  # 10min
    # key 前缀符合 spec
    assert key.startswith(KEY_PREFIX)


@pytest.mark.asyncio
async def test_different_topk_different_cache(fake_redis):
    """不同 top_k 独立 cache (避免 5 跟 10 撞)"""
    await cache_response("q", "ds-1", top_k=5, response=[{"a": 1}])
    await cache_response("q", "ds-1", top_k=10, response=[{"b": 2}])

    assert await get_cached_response("q", "ds-1", top_k=5) == [{"a": 1}]
    assert await get_cached_response("q", "ds-1", top_k=10) == [{"b": 2}]
    # 同一 query+dataset 不同 top_k, key 必须不同
    assert _key("q", "ds-1", 5) != _key("q", "ds-1", 10)


@pytest.mark.asyncio
async def test_get_returns_none_on_redis_down(monkeypatch):
    """Redis 挂时 get 返 None, cache_response 不抛 (fail-open)"""

    class FakeRedisDown:
        async def get(self, *a, **k):
            raise ConnectionError("Redis down")

        async def set(self, *a, **k):
            raise ConnectionError("Redis down")

    monkeypatch.setattr(redis_client, "get_redis", lambda: FakeRedisDown())

    # get 返 None, 业务侧直调 Dify
    assert await get_cached_response("q", "ds-1", 5) is None
    # cache_response 也不应抛 (facade safe_set 内部 catch)
    await cache_response("q", "ds-1", 5, [{"a": 1}])


@pytest.mark.asyncio
async def test_cache_and_get_chat(fake_redis):
    """cache_chat_response + get_cached_chat_response hit"""
    from src.core.dify_query_cache import cache_chat_response, get_cached_chat_response

    await cache_chat_response("你好", {"answer": "hello", "sources": []})
    result = await get_cached_chat_response("你好")
    assert result == {"answer": "hello", "sources": []}


@pytest.mark.asyncio
async def test_get_cached_chat_response_miss(fake_redis):
    """miss 返 None"""
    from src.core.dify_query_cache import get_cached_chat_response

    result = await get_cached_chat_response("nonexistent")
    assert result is None


@pytest.mark.asyncio
async def test_get_cached_chat_response_returns_none_on_redis_down(monkeypatch):
    """Redis 挂时 chat get 返 None, chat cache 不抛"""
    from src.core import redis_client
    from src.core.dify_query_cache import cache_chat_response, get_cached_chat_response

    class FakeRedisDown:
        async def get(self, *a, **k):
            raise ConnectionError("Redis down")

        async def set(self, *a, **k):
            raise ConnectionError("Redis down")

    monkeypatch.setattr(redis_client, "get_redis", lambda: FakeRedisDown())

    assert await get_cached_chat_response("q") is None
    await cache_chat_response("q", {"answer": "test"})


@pytest.mark.asyncio
async def test_get_cached_response_json_decode_error(fake_redis):
    """JSON 损坏时返 None 并打 warning"""
    from src.core.dify_query_cache import get_cached_response

    await fake_redis.set("rag:dify:q:badkey", "not valid json")
    # 补一个正常 key 避免 hash 撞不上
    result = await get_cached_response("irrelevant", "ds-1", 5)
    # 因为 key 不一致, 实际是 miss; 我们直接注入坏数据
    from src.core.dify_query_cache import _key

    await fake_redis.set(_key("badjson", "ds-1", 5), "{invalid")
    result = await get_cached_response("badjson", "ds-1", 5)
    assert result is None


@pytest.mark.asyncio
async def test_get_cached_response_non_list(fake_redis):
    """缓存数据非 list 时返 None"""
    from src.core.dify_query_cache import _key, get_cached_response

    await fake_redis.set(_key("notlist", "ds-1", 5), '{"answer": "obj"}')
    result = await get_cached_response("notlist", "ds-1", 5)
    assert result is None


@pytest.mark.asyncio
async def test_get_cached_chat_response_json_decode_error(fake_redis):
    """chat JSON 损坏时返 None"""
    from src.core.dify_query_cache import _chat_key, get_cached_chat_response

    await fake_redis.set(_chat_key("badchat"), "{invalid")
    result = await get_cached_chat_response("badchat")
    assert result is None


@pytest.mark.asyncio
async def test_get_cached_chat_response_non_dict(fake_redis):
    """chat 缓存数据非 dict 时返 None"""
    from src.core.dify_query_cache import _chat_key, get_cached_chat_response

    await fake_redis.set(_chat_key("notdict"), '["list"]')
    result = await get_cached_chat_response("notdict")
    assert result is None
