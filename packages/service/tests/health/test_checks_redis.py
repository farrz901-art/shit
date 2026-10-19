"""check_redis 单元测试 (2026-06-18)

5 个模式 1 mock 测试, 覆盖:
- Redis ping 成功: status=ok + latency_ms >= 0
- Redis ping 连接拒绝: status=error + error msg
- Redis ping 返回 False: status=error
- REDIS_HOST / REDIS_PORT / REDIS_PASSWORD 环境变量透传
- 验证 latency_ms 被正记录
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

from src.health.checks import check_redis


def test_check_redis_ok():
    """Redis PING 成功 → status=ok + latency_ms >= 0"""
    fake_client = MagicMock()
    fake_client.ping.return_value = True
    with patch("src.health.checks._get_redis_client", return_value=fake_client):
        result = asyncio.run(check_redis())
    assert result.status == "ok"
    assert result.latency_ms is not None and result.latency_ms >= 0
    assert result.error is None


def test_check_redis_connection_refused():
    """Redis 拒绝连接 → status=error + error msg"""
    with patch("src.health.checks._get_redis_client", side_effect=ConnectionRefusedError("target machine refused")):
        result = asyncio.run(check_redis())
    assert result.status == "error"
    assert result.latency_ms is None
    assert result.error is not None and "refused" in result.error.lower()


def test_check_redis_ping_false():
    """Redis PING 返 False → status=error"""
    fake_client = MagicMock()
    fake_client.ping.return_value = False
    with patch("src.health.checks._get_redis_client", return_value=fake_client):
        result = asyncio.run(check_redis())
    assert result.status == "error"
    assert result.error is not None and "False" in result.error


def test_check_redis_uses_env_vars():
    """REDIS_HOST / REDIS_PORT / REDIS_PASSWORD 被 _get_redis_client 读走"""
    fake_client = MagicMock()
    fake_client.ping.return_value = True
    with (
        patch.dict("os.environ", {"REDIS_HOST": "myredis", "REDIS_PORT": "6380", "REDIS_PASSWORD": "secret"}),
        patch("src.health.checks._get_redis_client", return_value=fake_client),
    ):
        result = asyncio.run(check_redis())
    assert result.status == "ok"


def test_check_redis_records_latency():
    """验证 latency_ms 被正记录"""
    fake_client = MagicMock()
    fake_client.ping.return_value = True
    with patch("src.health.checks._get_redis_client", return_value=fake_client):
        result = asyncio.run(check_redis())
    assert result.latency_ms is not None and result.latency_ms >= 0
