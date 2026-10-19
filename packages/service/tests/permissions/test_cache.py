"""PermissionCache 行为测试: TTL, invalidate, 并发安全 (100% mock DB session)

(2026-06-18 redis) PermissionCache 现为 PermissionCacheRedis 的薄包装,
Redis 部分 mock 掉, 仅测 sync 路径 (PG → 本地 cache).
"""

from unittest.mock import AsyncMock, patch

import pytest

from src.core.permission_cache_redis import PermissionCacheRedis
from src.permissions.cache import (
    ALL_PAGE_KEYS,
    PAGE_METADATA,
    PermissionCache,
)


def _disable_redis(monkeypatch):
    """让 PermissionCacheRedis 的 Redis 调用走 fail-open, 仅测 PG 路径."""

    class FakeRedisDown:
        async def get(self, *a, **k):
            raise ConnectionError("redis down")

        async def set(self, *a, **k):
            raise ConnectionError("redis down")

        async def delete(self, *a, **k):
            raise ConnectionError("redis down")

    monkeypatch.setattr("src.core.redis_client.get_redis", lambda: FakeRedisDown())


def test_all_page_keys_constant() -> None:
    """ALL_PAGE_KEYS 包含 8+ 元素 (admin + chat + health + ...), 长度按 ALL_PAGE_KEYS 实际值"""
    assert len(ALL_PAGE_KEYS) >= 8
    assert "admin" in ALL_PAGE_KEYS
    assert "chat" in ALL_PAGE_KEYS
    assert "health" in ALL_PAGE_KEYS


def test_page_metadata_length() -> None:
    """PAGE_METADATA 跟 ALL_PAGE_KEYS 长度一致"""
    assert len(PAGE_METADATA) == len(ALL_PAGE_KEYS)
    for entry in PAGE_METADATA:
        assert "key" in entry
        assert "label_zh" in entry
        assert "label_en" in entry
        assert "path" in entry


def test_get_returns_none_when_role_not_in_cache(monkeypatch) -> None:
    """未加载时 get 触发 _refresh, role 不在矩阵 → None"""
    _disable_redis(monkeypatch)
    cache = PermissionCache()
    with patch("src.storage.session.session_scope") as mock_sess:
        mock_sess.return_value.__enter__.return_value.execute.return_value.fetchall.return_value = []
        result = cache.get("unknown_role", "chat")
    assert result is None


def test_all_page_keys_is_eight():
    """ALL_PAGE_KEYS 至少 8 元素 (admin + 7 业务 page); 加新 page 不需要改此 test"""
    from src.permissions.cache import ALL_PAGE_KEYS

    assert len(ALL_PAGE_KEYS) >= 8
    assert "admin" in ALL_PAGE_KEYS


def test_metadata_length_matches_keys():
    """PAGE_METADATA 跟 ALL_PAGE_KEYS 长度一致"""
    from src.permissions.cache import ALL_PAGE_KEYS, PAGE_METADATA

    assert len(PAGE_METADATA) == len(ALL_PAGE_KEYS)


def test_fallback_keys_when_not_warmed():
    """未 warmup 时返 fallback"""
    from src.permissions.cache import (
        ALL_PAGE_KEYS_FALLBACK,
        get_all_page_keys_sync,
        invalidate_page_keys_cache,
    )

    invalidate_page_keys_cache()
    keys = get_all_page_keys_sync()
    assert keys == ALL_PAGE_KEYS_FALLBACK


def test_get_returns_correct_value(monkeypatch) -> None:
    """role × page 在矩阵里 → 返 allowed 值"""
    _disable_redis(monkeypatch)
    cache = PermissionCache()
    with patch("src.storage.session.session_scope") as mock_sess:
        mock_sess.return_value.__enter__.return_value.execute.return_value.fetchall.return_value = [
            ("user", "chat", True),
            ("user", "decode", True),
            ("user", "output", False),
        ]
        # 第 1 次触发 refresh
        result_chat = cache.get("user", "chat")
        result_decode = cache.get("user", "decode")
        result_output = cache.get("user", "output")
    assert result_chat is True
    assert result_decode is True
    assert result_output is False


def test_invalidate_forces_refresh(monkeypatch) -> None:
    """invalidate 后下次 get 触发 _refresh (mock 验 fetchall 调用次数)"""
    _disable_redis(monkeypatch)
    cache = PermissionCache()
    with patch("src.storage.session.session_scope") as mock_sess:
        mock_sess.return_value.__enter__.return_value.execute.return_value.fetchall.return_value = [
            ("user", "chat", True),
        ]
        cache.get("user", "chat")  # 触发 1 次 refresh
        cache.invalidate()
        cache.get("user", "chat")  # 触发 2 次 refresh
        # session_scope 进入 __enter__ 2 次
        assert mock_sess.call_count == 2


def test_ttl_triggers_refresh(monkeypatch) -> None:
    """TTL 过期后 get 触发 _refresh"""
    _disable_redis(monkeypatch)
    cache = PermissionCacheRedis()
    with patch("src.storage.session.session_scope") as mock_sess:
        mock_sess.return_value.__enter__.return_value.execute.return_value.fetchall.return_value = [
            ("user", "chat", True),
        ]
        # 第一次: _loaded_at=0 (未加载) 触发 refresh
        cache.get("user", "chat")
        # 第二次: 模拟 _loaded_at 远在过去 (超过 CACHE_TTL) → 触发 refresh
        cache._loaded_at = 0.0  # 等同未加载
        cache.get("user", "chat")
        # 至少 2 次 refresh
        assert mock_sess.call_count >= 2


@pytest.mark.asyncio
async def test_get_all_page_keys_returns_keys():
    """get_all_page_keys 从 LookupService 拉 keys"""
    from src.permissions.cache import get_all_page_keys

    with patch(
        "src.lookups.service.LookupService.get",
        AsyncMock(
            return_value={
                "code": "page_key",
                "items": [{"key": "admin"}, {"key": "chat"}],
            }
        ),
    ):
        keys = await get_all_page_keys()
        assert "admin" in keys
        assert "chat" in keys


@pytest.mark.asyncio
async def test_get_all_page_keys_fallback():
    """LookupService 挂时退到 fallback"""
    from src.permissions.cache import ALL_PAGE_KEYS_FALLBACK, get_all_page_keys

    with patch("src.lookups.service.LookupService.get", AsyncMock(side_effect=Exception("DB down"))):
        keys = await get_all_page_keys()
        assert keys == ALL_PAGE_KEYS_FALLBACK


@pytest.mark.asyncio
async def test_get_all_page_metadata_returns_items():
    """get_all_page_metadata 返元数据列表"""
    from src.permissions.cache import get_all_page_metadata

    with patch(
        "src.lookups.service.LookupService.get",
        AsyncMock(
            return_value={
                "code": "page_key",
                "items": [
                    {"key": "admin", "label_zh": "管理", "label_en": "Admin", "metadata_json": {"path": "/admin"}}
                ],
            }
        ),
    ):
        items = await get_all_page_metadata()
        assert items[0]["key"] == "admin"
        assert items[0]["path"] == "/admin"


@pytest.mark.asyncio
async def test_get_all_page_metadata_fallback():
    """LookupService 挂时退到 fallback"""
    from src.permissions.cache import ALL_PAGE_KEYS, get_all_page_metadata

    with patch("src.lookups.service.LookupService.get", AsyncMock(side_effect=Exception("DB down"))):
        items = await get_all_page_metadata()
        # 长度跟 ALL_PAGE_KEYS 一致 (fallback 用同样的元组); 加 page 不需要改
        assert len(items) == len(ALL_PAGE_KEYS)


# ── 以下为 2026-07-02 nav spec §2.2: metadata_json 透传测试 ──


@pytest.fixture
def fake_page_keys() -> list[dict]:
    return [
        {
            "key": "admin",
            "label_zh": "管理中心",
            "label_en": "Admin",
            "metadata_json": {"path": "/admin", "is_group": True, "icon": "shield"},
            "is_active": True,
        },
        {
            "key": "admin_users",
            "label_zh": "用户管理",
            "label_en": "Users",
            "metadata_json": {"path": "/admin/users", "parent_id": "admin"},
            "is_active": True,
        },
        {
            "key": "chat",
            "label_zh": "对话",
            "label_en": "Chat",
            "metadata_json": {"path": "/chat"},
            "is_active": True,
        },
        {
            "key": "knowledge_extract",
            "label_zh": "知识图谱抽取",
            "label_en": "KG Extract",
            "metadata_json": {"path": "/knowledge/extract", "parent_id": "knowledge"},
            "is_active": True,
        },
    ]


@pytest.mark.asyncio
async def test_get_all_page_metadata_passes_through_metadata_block(fake_page_keys):
    """get_all_page_metadata() 必须把整块 metadata_json 透传到 'metadata' 字段."""
    from src.permissions import cache

    fake_dict = {"items": fake_page_keys}

    with patch("src.lookups.service.LookupService") as mock_svc:
        mock_svc.get = AsyncMock(return_value=fake_dict)
        result = await cache.get_all_page_metadata()

    # admin (顶级 + is_group)
    admin_entry = next(r for r in result if r["key"] == "admin")
    assert admin_entry["metadata"] == {"path": "/admin", "is_group": True, "icon": "shield"}
    assert admin_entry["path"] == "/admin"
    assert admin_entry["label_zh"] == "管理中心"

    # admin_users (子页 + parent_id)
    users_entry = next(r for r in result if r["key"] == "admin_users")
    assert users_entry["metadata"] == {"path": "/admin/users", "parent_id": "admin"}
    assert users_entry["path"] == "/admin/users"

    # chat (顶级, 无 is_group)
    chat_entry = next(r for r in result if r["key"] == "chat")
    assert chat_entry["metadata"] == {"path": "/chat"}
    assert "is_group" not in chat_entry["metadata"]


@pytest.mark.asyncio
async def test_get_all_page_metadata_handles_missing_metadata_json():
    """历史数据 metadata_json 为 None → 'metadata' 字段为空 dict."""
    from src.permissions import cache

    fake_dict = {
        "items": [
            {
                "key": "legacy",
                "label_zh": "老页面",
                "label_en": "Legacy",
                "metadata_json": None,
                "is_active": True,
            }
        ]
    }

    with patch("src.lookups.service.LookupService") as mock_svc:
        mock_svc.get = AsyncMock(return_value=fake_dict)
        result = await cache.get_all_page_metadata()

    legacy = result[0]
    assert legacy["metadata"] == {}
    # 缺 metadata_json.path 时仍兜底成 /<key>
    assert legacy["path"] == "/legacy"


@pytest.mark.asyncio
async def test_get_all_page_metadata_fallback_on_lookup_failure():
    """LookupService 抛异常 → 返 _PAGE_METADATA_FALLBACK (R1 兼容)."""
    from src.permissions import cache

    with patch("src.lookups.service.LookupService") as mock_svc:
        mock_svc.get = AsyncMock(side_effect=RuntimeError("DB down"))
        result = await cache.get_all_page_metadata()

    # fallback 至少含 admin / chat / knowledge
    keys = [r["key"] for r in result]
    assert "admin" in keys
    assert "chat" in keys
    assert "knowledge" in keys
