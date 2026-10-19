"""core/redis_client.py facade 测试 (2026-06-18 redis spec §4, §7, 模式 1 mock)

测试目标:
- get_redis() lazy init + 模块级单例
- safe_get / safe_set / safe_incr 在 fakeredis 上的基本行为
- ConnectionError 时 fail-open (返 None, 不抛)
- shutdown_redis() 清空 _pool
"""

from __future__ import annotations

import pytest
from fakeredis import FakeAsyncRedis

from src.core import redis_client


@pytest.fixture
def fake_redis(monkeypatch):
    """fakeredis 替代真 redis. 业务侧 get_redis() 返 FakeAsyncRedis."""
    fake = FakeAsyncRedis(decode_responses=True)
    monkeypatch.setattr(redis_client, "get_redis", lambda: fake)
    monkeypatch.setattr(redis_client, "_pool", None)  # 重置单例
    return fake


def test_get_redis_lazy_init(monkeypatch):
    """get_redis() 第一次调时建 pool, 后续复用.

    用 monkeypatch 拦截 _build_pool, 验证 lazy 调用.
    (2026-06-19) phase2: conftest autouse 把 get_redis mock 成 fakeredis 直返 lambda,
    本测试要测真 get_redis(), 需先 undo 掉那个 mock — 用 importlib.reload 或反向 setattr.
    """
    # Undo conftest 的 get_redis mock — 走真 get_redis 实现 (它会调 _build_pool)
    import importlib

    importlib.reload(redis_client)
    monkeypatch.setattr(redis_client, "_pool", None)

    captured = {}

    class FakePool:
        """占位 pool, 暴露 connection_kwargs / max_connections 让 logger.info 不抛."""

        connection_kwargs = {"host": "fake"}
        max_connections = 99

    def fake_build_pool():
        captured["called"] = True
        return FakePool()

    monkeypatch.setattr(redis_client, "_build_pool", fake_build_pool)
    # 模拟 aioredis.Redis 接受任意 connection_pool
    import redis.asyncio as aioredis

    monkeypatch.setattr(aioredis, "Redis", lambda connection_pool: {"pool": connection_pool})

    redis_client.get_redis()
    assert captured.get("called") is True
    # 第二次调不重建
    captured["called"] = False
    redis_client.get_redis()
    assert captured.get("called") is False


async def test_safe_get_hit(fake_redis):
    """safe_get: hit 返 value, miss 返 None."""
    await fake_redis.set("test:key", "value", ex=60)
    assert await redis_client.safe_get("test:key") == "value"
    assert await redis_client.safe_get("test:miss") is None


async def test_safe_set_with_ttl(fake_redis):
    """safe_set: 写 key + 设 TTL."""
    ok = await redis_client.safe_set("test:key", "value", ex=60)
    assert ok is True
    ttl = await fake_redis.ttl("test:key")
    assert 0 < ttl <= 60


async def test_safe_incr_with_expire_nx(fake_redis):
    """safe_incr: INCR + EXPIRE NX (仅首次设过期)."""
    count = await redis_client.safe_incr("test:counter", ex_seconds=15)
    assert count == 1
    # 第二次 INCR, TTL 不应被覆盖
    count2 = await redis_client.safe_incr("test:counter", ex_seconds=15)
    assert count2 == 2
    ttl = await fake_redis.ttl("test:counter")
    assert ttl <= 15  # 不会重置


async def test_safe_get_on_redis_down(monkeypatch):
    """safe_get: ConnectionError 时返 None, 不抛 (fail-open)."""

    class BoomClient:
        async def get(self, key):
            raise ConnectionError("Redis down")

    monkeypatch.setattr(redis_client, "get_redis", lambda: BoomClient())
    # 不抛, 返 None
    result = await redis_client.safe_get("test:key")
    assert result is None


async def test_safe_incr_on_event_loop_closed(monkeypatch):
    """safe_incr: pipe.execute 抛 RuntimeError (event loop closed) 返 None, 不抛.

    根因 (2026-06-22): redis-py 内部在 event loop 关闭后抛 AttributeError → RuntimeError,
    safe_incr 之前只捕 RedisError / ConnectionError / TimeoutError, 漏这两个 → 500.
    """

    class BoomPipeline:
        """模拟 pipeline, execute 抛 RuntimeError('Event loop is closed')"""

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return None

        def incr(self, key):
            pass

        def expire(self, key, ex, nx=False):
            pass

        async def execute(self):
            raise RuntimeError("Event loop is closed")

    class BoomClient:
        def pipeline(self, transaction=False):
            return BoomPipeline()

    monkeypatch.setattr(redis_client, "get_redis", lambda: BoomClient())
    # 不抛, 返 None
    result = await redis_client.safe_incr("test:counter", ex_seconds=15)
    assert result is None


async def test_safe_incr_on_attribute_error(monkeypatch):
    """safe_incr: pipe.execute 抛 AttributeError (NoneType.send) 返 None, 不抛."""

    class BoomPipeline:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return None

        def incr(self, key):
            pass

        def expire(self, key, ex, nx=False):
            pass

        async def execute(self):
            raise AttributeError("'NoneType' object has no attribute 'send'")

    class BoomClient:
        def pipeline(self, transaction=False):
            return BoomPipeline()

    monkeypatch.setattr(redis_client, "get_redis", lambda: BoomClient())
    result = await redis_client.safe_incr("test:counter", ex_seconds=15)
    assert result is None


async def test_shutdown_redis_clears_pool():
    """shutdown_redis() 清空 _pool (避免 uvicorn reload 残留)."""
    redis_client._pool = None
    await redis_client.shutdown_redis()
    assert redis_client._pool is None


def test_get_redis_resets_pool_on_loop_change(monkeypatch):
    """get_redis() 检测 loop 变化, 重建 pool 防 'attached to a different loop'.

    根因 (2026-06-22): uvicorn worker 在 lifespan hook 跟 request handler 用不同 event loop,
    aioredis ConnectionPool 创建时绑定首个 loop, 跨 loop 复用 → permission_cache_redis
    实测 warning 'got Future attached to a different loop'.
    """
    import asyncio
    import importlib

    importlib.reload(redis_client)
    monkeypatch.setattr(redis_client, "_pool", None)
    monkeypatch.setattr(redis_client, "_pool_loop", None)

    build_calls: list[int] = []

    class FakePool:
        connection_kwargs = {"host": "fake"}
        max_connections = 99

    def fake_build_pool():
        build_calls.append(1)
        return FakePool()

    monkeypatch.setattr(redis_client, "_build_pool", fake_build_pool)

    import redis.asyncio as aioredis

    monkeypatch.setattr(aioredis, "Redis", lambda connection_pool: {"pool": connection_pool})

    # asyncio.new_event_loop() 返的对象支持 weakref, 模拟不同 loop
    loop_1 = asyncio.new_event_loop()
    loop_2 = asyncio.new_event_loop()
    monkeypatch.setattr(redis_client, "_get_current_loop", lambda: loop_1)
    redis_client.get_redis()
    assert len(build_calls) == 1

    # 切到第二个 loop (e.g. uvicorn lifespan vs request handler)
    monkeypatch.setattr(redis_client, "_get_current_loop", lambda: loop_2)
    redis_client.get_redis()
    assert len(build_calls) == 2  # pool 被重建
    loop_1.close()
    loop_2.close()


def test_get_redis_reuses_pool_same_loop(monkeypatch):
    """loop 没变时 pool 复用, 不重建."""
    import asyncio
    import importlib

    importlib.reload(redis_client)
    monkeypatch.setattr(redis_client, "_pool", None)
    monkeypatch.setattr(redis_client, "_pool_loop", None)

    build_calls: list[int] = []

    class FakePool:
        connection_kwargs = {"host": "fake"}
        max_connections = 99

    def fake_build_pool():
        build_calls.append(1)
        return FakePool()

    monkeypatch.setattr(redis_client, "_build_pool", fake_build_pool)

    import redis.asyncio as aioredis

    monkeypatch.setattr(aioredis, "Redis", lambda connection_pool: {"pool": connection_pool})

    loop = asyncio.new_event_loop()
    monkeypatch.setattr(redis_client, "_get_current_loop", lambda: loop)
    redis_client.get_redis()
    redis_client.get_redis()
    redis_client.get_redis()
    assert len(build_calls) == 1  # 始终复用
    loop.close()
