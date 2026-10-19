"""Mem0Ready 测试 (2026-06-18 redis spec §5.4, 模式 1 mock)

4 场景:
1. mark_ready 后 is_ready 返 True
2. 未 mark 的 user 返 False
3. mark 1h TTL
4. Redis 挂时 is_ready 返 False (fail-open)
"""

from __future__ import annotations

import pytest
from fakeredis import aioredis as fakeredis

from src.core import redis_client
from src.core.mem0_ready import READY_TTL, _key, is_ready, mark_ready


@pytest.fixture
def fake_redis(monkeypatch):
    """fakeredis 替代真 redis. 业务侧 get_redis() 返 FakeRedis."""
    fake = fakeredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(redis_client, "get_redis", lambda: fake)
    monkeypatch.setattr(redis_client, "_pool", None)  # 重置单例
    return fake


@pytest.mark.asyncio
async def test_mark_and_check_ready(fake_redis):
    """mark_ready 后 is_ready 返 True"""
    user_id = "user-123"
    assert await is_ready(user_id) is False  # 初始没标记

    await mark_ready(user_id)
    assert await is_ready(user_id) is True


@pytest.mark.asyncio
async def test_is_ready_false_for_unknown_user(fake_redis):
    """未 mark 的 user 返 False"""
    assert await is_ready("nobody") is False


@pytest.mark.asyncio
async def test_mark_sets_1h_ttl(fake_redis):
    """mark 1h TTL = 3600"""
    user_id = "u1"
    await mark_ready(user_id)

    ttl = await fake_redis.ttl(_key(user_id))
    assert 0 < ttl <= READY_TTL
    assert READY_TTL == 3600  # 1h


@pytest.mark.asyncio
async def test_is_ready_fails_open_on_redis_down(monkeypatch):
    """Redis 挂时 is_ready 返 False (本 worker 自己构造)"""

    class FakeRedisDown:
        async def get(self, *a, **k):
            raise ConnectionError("Redis down")

        async def set(self, *a, **k):
            raise ConnectionError("Redis down")

    monkeypatch.setattr(redis_client, "get_redis", lambda: FakeRedisDown())

    assert await is_ready("any") is False  # fail-open
