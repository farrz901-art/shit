"""LookupCache 单元测试 (2026-06-19 lookup spec Task 4, 模式 1 mock)

CLAUDE.md 规范: 测试禁止连真 Redis. 这里 mock src.core.redis_client.safe_* 函数,
验证 LookupCache 行为: L1 优先 → L2 (mock safe_get) → DB fallback 路径.

测试矩阵 (6):
1. test_get_all_returns_none_when_redis_empty  — Redis miss → 返 None
2. test_get_all_uses_l1_when_loaded             — L1 命中 → 直接返, 不走 Redis
3. test_set_all_writes_to_redis_and_l1          — set_all 写 L1 + safe_set
4. test_invalidate_clears_l1_and_redis          — invalidate 清 L1 + safe_delete + publish
5. test_get_dict_readonly_returns_flag          — get_dict_readonly 走 L1
6. test_get_dict_version_returns_version        — get_dict_version 走 L1
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.lookups.cache import lookup_cache


def _reset_cache_singleton():
    """重置 LookupCache 单例状态 (每个测试前调, 防 L1 串扰)."""
    lookup_cache.reset_l1()


@pytest.fixture(autouse=True)
def _clean_l1():
    """每个 test 前清 L1, 互不污染."""
    _reset_cache_singleton()
    yield
    _reset_cache_singleton()


@pytest.mark.asyncio
async def test_get_all_returns_none_when_redis_empty():
    """Redis miss → safe_get 返 None → get_all 返 None (业务侧应走 DB)."""
    with patch("src.lookups.cache.safe_get", new=AsyncMock(return_value=None)):
        result = await lookup_cache.get_all()
        assert result is None


@pytest.mark.asyncio
async def test_get_all_uses_l1_when_loaded():
    """L1 命中 → 直接返, safe_get 不应被调 (避免 round trip)."""
    payload = {"foo": {"label_zh": "测试", "version": 1, "items": []}}
    await lookup_cache.set_all(payload)

    # safe_get 被 patch 成 AsyncMock 但不应被调
    with patch("src.lookups.cache.safe_get", new=AsyncMock()) as mock_safe_get:
        result = await lookup_cache.get_all()
        assert result == payload
        mock_safe_get.assert_not_awaited()


@pytest.mark.asyncio
async def test_set_all_writes_to_redis_and_l1():
    """set_all: 写 L1 (后续 get_all 立即命中) + await safe_set (跨进程共享)."""
    payload = {"reject_reason": {"label_zh": "拒绝原因", "version": 1, "items": []}}

    with patch("src.lookups.cache.safe_set", new=AsyncMock(return_value=True)) as mock_safe_set:
        await lookup_cache.set_all(payload)

    # L1 已写
    assert lookup_cache._l1_data == payload

    # safe_set 被调, key/value/TTL 正确
    mock_safe_set.assert_awaited_once()
    args, kwargs = mock_safe_set.call_args
    # signature: safe_set(key, value, ex=ttl) — 用 keyword args 优先
    if "ex" in kwargs:
        ex = kwargs["ex"]
        value = kwargs.get("value") or args[1]
        key = kwargs.get("key") or args[0]
    else:
        key, value, ex = args[0], args[1], args[2]
    assert key == "rag:dict:all"
    assert json.loads(value) == payload
    assert ex == 300  # 5 min TTL


@pytest.mark.asyncio
async def test_invalidate_clears_l1_and_redis():
    """invalidate: 清 L1 + await safe_delete + publish 广播 (Redis 失败可容忍)."""
    # 先写 L1 (有数据)
    await lookup_cache.set_all({"foo": {"label_zh": "x", "version": 1, "items": []}})
    assert lookup_cache._l1_data is not None

    with (
        patch("src.lookups.cache.safe_delete", new=AsyncMock(return_value=1)) as mock_del,
        patch("src.lookups.cache.get_redis") as mock_get_redis,
    ):
        # mock redis publish
        mock_redis = MagicMock()
        mock_redis.publish = AsyncMock()
        mock_get_redis.return_value = mock_redis

        await lookup_cache.invalidate("reject_reason")

    # L1 已清
    assert lookup_cache._l1_data is None

    # safe_delete 被调, key 是 rag:dict:all
    mock_del.assert_awaited_once()
    args = mock_del.call_args.args
    assert "rag:dict:all" in args

    # publish 被调, channel + dict_code 正确
    mock_redis.publish.assert_awaited_once()
    pub_args = mock_redis.publish.call_args.args
    assert pub_args[0] == "rag:dict:invalidate"
    assert pub_args[1] == "reject_reason"


def test_get_dict_readonly_returns_flag():
    """get_dict_readonly 走 L1 (同步), is_readonly=True 时返 True."""
    lookup_cache._l1_data = {
        "readonly_dict": {"label_zh": "x", "version": 1, "is_readonly": True, "items": []},
        "normal_dict": {"label_zh": "y", "version": 1, "is_readonly": False, "items": []},
    }
    assert lookup_cache.get_dict_readonly("readonly_dict") is True
    assert lookup_cache.get_dict_readonly("normal_dict") is False
    # 不存在的字典 → False (默认)
    assert lookup_cache.get_dict_readonly("nonexistent") is False


def test_get_dict_version_returns_version():
    """get_dict_version 走 L1 (同步), 返 int version; 不存在返 0."""
    lookup_cache._l1_data = {
        "v1_dict": {"label_zh": "x", "version": 5, "items": []},
        "v0_dict": {"label_zh": "y", "version": 0, "items": []},
    }
    assert lookup_cache.get_dict_version("v1_dict") == 5
    assert lookup_cache.get_dict_version("v0_dict") == 0
    assert lookup_cache.get_dict_version("nonexistent") == 0
