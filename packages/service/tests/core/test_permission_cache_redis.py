"""PermissionCache Redis 共享版测试 (2026-06-18 redis spec §5.1, 模式 1 mock)

测试目标:
- 首次 get: 走 PG 读 + 写 Redis
- 第二次 get: 直接读 Redis, 不调 PG (Redis 优先)
- 未知 role / page_key 返 None (不抛)
- Redis 挂时降级 PG 路径 (fail-open)

测试用 sync `cache.get()` 调用 (跟现有 PermissionCache API 一致),
FakeAsyncRedis 替代真 redis (业务侧 facade 兼容).
"""

from __future__ import annotations

import asyncio
import json
import time

import pytest
from fakeredis import FakeAsyncRedis

from src.core import redis_client
from src.core.permission_cache_redis import CACHE_KEY, PermissionCacheRedis


@pytest.fixture
def fake_redis(monkeypatch):
    """fakeredis 替代真 redis. 业务侧 get_redis() 返 FakeAsyncRedis."""
    fake = FakeAsyncRedis(decode_responses=True)
    monkeypatch.setattr(redis_client, "get_redis", lambda: fake)
    monkeypatch.setattr(redis_client, "_pool", None)  # 重置单例
    return fake


@pytest.fixture
def cache() -> PermissionCacheRedis:
    """每个测试一个独立 cache 实例 (避免 _loaded_at 串扰)."""
    return PermissionCacheRedis()


async def _seed(fake_redis: FakeAsyncRedis, key: str, value: str) -> None:
    """async 写入 fakeredis (FakeAsyncRedis.set 是 async)."""
    await fake_redis.set(key, value, ex=60)


def test_first_get_reads_pg_and_writes_redis(cache, fake_redis, monkeypatch):
    """首次 get: PG 读 + 写 Redis"""
    fake_pg_rows = [
        ("admin", "kg", True),
        ("admin", "chat", True),
        ("user", "kg", False),
    ]

    class FakeSession:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def execute(self, *a, **k):
            class _R:
                def fetchall(self):
                    return fake_pg_rows

            return _R()

    monkeypatch.setattr("src.storage.session.session_scope", lambda: FakeSession())

    result = cache.get("admin", "kg")
    assert result is True
    # 等异步刷 Redis 的 daemon thread 完成 (best-effort ~50ms)
    time.sleep(0.5)
    # Redis 应已写
    raw = asyncio.run(fake_redis.get(CACHE_KEY))
    assert raw is not None
    matrix = json.loads(raw)
    assert matrix["admin"]["kg"] is True
    assert matrix["user"]["kg"] is False


def test_subsequent_get_reads_redis_not_pg(cache, fake_redis, monkeypatch):
    """第二次 get: 直接读 Redis, 不调 PG"""
    # 预设 Redis 已有数据
    matrix = {"admin": {"kg": True}, "user": {"chat": False}}
    asyncio.run(_seed(fake_redis, CACHE_KEY, json.dumps(matrix)))

    # PG 不应被调
    def fake_pg(*a, **k):
        raise AssertionError("PG 不应被调, 应走 Redis")

    monkeypatch.setattr("src.storage.session.session_scope", fake_pg)

    assert cache.get("admin", "kg") is True
    assert cache.get("user", "chat") is False


def test_get_returns_none_for_unknown_role(cache, fake_redis, monkeypatch):
    """未知 role / page_key 返 None (不抛)"""
    asyncio.run(_seed(fake_redis, CACHE_KEY, json.dumps({"admin": {"kg": True}})))

    def fake_pg(*a, **k):
        raise AssertionError("应走 Redis, 不应调 PG")

    monkeypatch.setattr("src.storage.session.session_scope", fake_pg)

    assert cache.get("nobody", "kg") is None
    assert cache.get("admin", "nobody") is None


def test_get_falls_back_to_pg_when_redis_down(cache, monkeypatch):
    """Redis 挂时降级 PG 路径 (fail-open)"""

    class FakeRedisDown:
        async def get(self, *a, **k):
            raise ConnectionError("Redis down")

        async def set(self, *a, **k):
            raise ConnectionError("Redis down")

        async def delete(self, *a, **k):
            raise ConnectionError("Redis down")

    monkeypatch.setattr(redis_client, "get_redis", lambda: FakeRedisDown())

    pg_called = []

    class FakeSession:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def execute(self, *a, **k):
            pg_called.append(1)

            class _R:
                def fetchall(self):
                    return [("admin", "kg", True)]

            return _R()

    monkeypatch.setattr("src.storage.session.session_scope", lambda: FakeSession())

    # 应走 PG 拿到 True
    assert cache.get("admin", "kg") is True
    assert pg_called == [1]
