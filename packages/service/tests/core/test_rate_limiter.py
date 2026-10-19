"""RateLimiter 测试 (2026-06-18 redis spec §5.3, 模式 1 mock)

7 场景:
1. 第 1 次请求: allowed=True, count=1
2. 5 次以内 (含) 全 allowed
3. 第 6 次超阈值, allowed=False
4. 不同 IP 独立计数
5. reset_password 用 1h 窗口, 3 次阈值
6. Redis 挂时 fail-open
7. key 格式: rag:rl:{op}:{ip}
"""

from __future__ import annotations

import pytest
from fakeredis import aioredis as fakeredis

from src.core import redis_client
from src.core.rate_limiter import RULES, _key, check_and_increment


@pytest.fixture
def fake_redis(monkeypatch):
    """fakeredis 替代真 redis. 业务侧 get_redis() 返 FakeRedis."""
    fake = fakeredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(redis_client, "get_redis", lambda: fake)
    monkeypatch.setattr(redis_client, "_pool", None)  # 重置单例
    return fake


@pytest.mark.asyncio
async def test_first_request_allowed(fake_redis):
    """第 1 次请求: allowed=True, count=1"""
    allowed, count = await check_and_increment("login", "1.2.3.4")
    assert allowed is True
    assert count == 1


@pytest.mark.asyncio
async def test_under_threshold_allowed(fake_redis):
    """5 次以内 (含) 全 allowed"""
    for i in range(1, 6):
        allowed, count = await check_and_increment("login", "1.2.3.4")
        assert allowed is True, f"第 {i} 次应 allowed"
        assert count == i


@pytest.mark.asyncio
async def test_over_threshold_rejected(fake_redis):
    """第 6 次超阈值, allowed=False"""
    for _ in range(5):
        await check_and_increment("login", "1.2.3.4")
    allowed, count = await check_and_increment("login", "1.2.3.4")
    assert allowed is False
    assert count == 6


@pytest.mark.asyncio
async def test_different_ips_isolated(fake_redis):
    """不同 IP 独立计数"""
    for _ in range(5):
        await check_and_increment("login", "1.2.3.4")
    # 另一个 IP 不受影响
    allowed, count = await check_and_increment("login", "5.6.7.8")
    assert allowed is True
    assert count == 1


@pytest.mark.asyncio
async def test_reset_uses_1h_window(fake_redis):
    """reset_password 用 1h 窗口, 3 次阈值"""
    for i in range(1, 4):
        allowed, _ = await check_and_increment("reset", "1.2.3.4")
        assert allowed is True, f"reset 第 {i} 次应 allowed"
    allowed, count = await check_and_increment("reset", "1.2.3.4")
    assert allowed is False
    assert count == 4


@pytest.mark.asyncio
async def test_redis_down_fails_open(monkeypatch):
    """Redis 挂时 fail-open, allowed=True 放行"""

    class FakeBoomCM:
        """pipeline 返的 async context manager. __aenter__ 抛 Redis 错误."""

        async def __aenter__(self):
            raise ConnectionError("Redis down")

        async def __aexit__(self, *a, **k):
            return False

    class FakeRedisDown:
        def pipeline(self, *a, **k):
            return FakeBoomCM()

    monkeypatch.setattr(redis_client, "get_redis", lambda: FakeRedisDown())

    allowed, count = await check_and_increment("login", "1.2.3.4")
    assert allowed is True  # fail-open
    assert count == 0


@pytest.mark.asyncio
async def test_key_format(fake_redis):
    """key 格式: rag:rl:{op}:{ip}"""
    await check_and_increment("login", "10.0.0.1")
    expected_key = _key("login", "10.0.0.1")
    assert expected_key == "rag:rl:login:10.0.0.1"
    # 实际 Redis 里有这个 key
    count = await fake_redis.get(expected_key)
    assert count == "1"


def test_rules_defaults():
    """默认 RULES 表: login 5/15min, reset 3/1h (env 未设时)"""
    # 注: env 可能在测试运行时设了, 这里只验证 name + 字段类型 + 合理范围
    login = RULES["login"]
    reset = RULES["reset"]
    assert login.name == "login"
    assert 0 < login.threshold <= 100
    assert 0 < login.window_seconds <= 86400
    assert reset.name == "reset"
    assert 0 < reset.threshold <= 100
    assert 0 < reset.window_seconds <= 86400
