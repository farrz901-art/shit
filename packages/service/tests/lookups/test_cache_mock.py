"""lookups/cache.py 单元测试 (mode 1, mock redis)"""

from unittest.mock import AsyncMock, patch

import pytest

from src.lookups.cache import lookup_cache


@pytest.fixture(autouse=True)
def reset_cache():
    lookup_cache.reset_l1()
    yield
    lookup_cache.reset_l1()


@pytest.mark.asyncio
async def test_get_all_l1_hit():
    """L1 命中直接返"""
    lookup_cache._l1_data = {"status": {"label_zh": "状态"}}
    result = await lookup_cache.get_all()
    assert result is not None
    assert result["status"]["label_zh"] == "状态"


@pytest.mark.asyncio
async def test_get_all_l2_hit():
    """L2 命中写入 L1"""
    with patch("src.lookups.cache.safe_get", return_value='{"code": {"label_zh": "编码"}}'):
        result = await lookup_cache.get_all()
        assert result is not None
        assert result["code"]["label_zh"] == "编码"
        assert lookup_cache._l1_data is not None


@pytest.mark.asyncio
async def test_get_all_miss():
    """L1+L2 都 miss"""
    with patch("src.lookups.cache.safe_get", return_value=None):
        result = await lookup_cache.get_all()
        assert result is None


@pytest.mark.asyncio
async def test_set_all():
    """写入 L1+L2"""
    with patch("src.lookups.cache.safe_set", return_value=True):
        await lookup_cache.set_all({"s": {"label_zh": "S"}})
        l1 = lookup_cache._l1_data
    assert l1 is not None
    assert l1["s"]["label_zh"] == "S"


@pytest.mark.asyncio
async def test_invalidate():
    """清 L1 + DEL Redis"""
    lookup_cache._l1_data = {"old": {}}
    with (
        patch("src.lookups.cache.safe_delete", return_value=True),
        patch("src.lookups.cache.get_redis") as mock_get_redis,
    ):
        mock_redis = AsyncMock()
        mock_get_redis.return_value = mock_redis
        await lookup_cache.invalidate()
        assert lookup_cache._l1_data is None
        mock_redis.publish.assert_called_once()


def test_get_dict_readonly():
    """查字典只读状态"""
    lookup_cache._l1_data = {"dict1": {"is_readonly": True}}
    assert lookup_cache.get_dict_readonly("dict1") is True
    assert lookup_cache.get_dict_readonly("dict2") is False


def test_get_dict_version():
    """查字典版本号"""
    lookup_cache._l1_data = {"dict1": {"version": 3}}
    assert lookup_cache.get_dict_version("dict1") == 3
    assert lookup_cache.get_dict_version("dict2") == 0


def test_reset_l1():
    """重置 L1"""
    lookup_cache._l1_data = {"x": {}}
    lookup_cache.reset_l1()
    assert lookup_cache._l1_data is None
