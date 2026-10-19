"""LookupService 单元测试 (2026-06-19 lookup spec Task 4, 模式 1 mock)

CLAUDE.md 规范: 测试禁止连真 PG / Redis. 这里:
- mock session_scope 返 MagicMock session, 模拟 SQL 执行
- mock lookup_cache (L1 dict) 模拟缓存命中/失效路径

测试矩阵 (10):
1. test_list_all_dicts_returns_codes           — 列出全部字典概要
2. test_list_all_dicts_uses_cache_when_available — L1 命中直接返
3. test_get_dict_returns_items_with_only_active_filter — only_active 过滤
4. test_get_dict_filters_lang                  — lang=zh/en/both
5. test_get_one_returns_single_item            — get_one 命中
6. test_get_one_raises_not_found               — get_one 不存在 404
7. test_create_item_inserts_and_invalidates_cache — 新增 + cache 失效
8. test_create_item_raises_409_on_duplicate    — 重复 key 409
9. test_patch_item_updates_and_invalidates_cache — 改 item + cache 失效
10. test_soft_delete_item_sets_deprecated_at   — 软删设 is_active=False
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# 提前 import 真实 src.lookups.* 模块并锁住 sys.modules 引用.
# 原因: tests/lookups/test_seed.py 会在 test_run_seed_* 里用
# `sys.modules["src.lookups"] = types.ModuleType("src.lookups")` 覆盖 fake module,
# 没收尾 (没有 finalizer 还原), 导致后续 test_service 的
# `from src.lookups.service import ...` 走到 fake module 而报错
# "'src.lookups' is not a package" (fake module 没 __path__).
#
# 解决: 这里在 module-level 提前 import, 拿到真实 module object, 即使 sys.modules
# 被覆盖, 我们持有的 _SVC / _CACHE / _EXC / _AUDIT 引用仍是真模块. 业务侧直接用
# 这几个 reference, 不用再走 sys.modules["src.lookups"].X 属性查找.
from src.lookups import audit as _AUDIT  # noqa: F401
from src.lookups import cache as _CACHE  # noqa: F401
from src.lookups import exceptions as _EXC  # noqa: F401
from src.lookups import service as _SVC  # noqa: F401
from src.lookups.service import LookupService


def _mock_session_scope(session: MagicMock):
    """构造 sync context manager, yield mock session 后 commit (MagicMock no-op)."""

    @contextmanager
    def _cm():
        yield session

    return _cm()


def _make_dict_row(code: str = "reject_reason", version: int = 1, is_active: bool = True) -> MagicMock:
    """构造 Dictionary mock 行."""
    row = MagicMock()
    row.code = code
    row.label_zh = "拒绝原因"
    row.label_en = "Reject Reason"
    row.description = None
    row.version = version
    row.is_active = is_active
    row.is_readonly = False
    return row


def _make_item_row(
    dict_code: str = "reject_reason",
    key: str = "duplicate",
    label_zh: str = "重复",
    label_en: str = "Duplicate",
    sort: int = 1,
    is_active: bool = True,
    description: str | None = None,
    metadata_json: dict | None = None,
) -> MagicMock:
    """构造 DictionaryItem mock 行."""
    row = MagicMock()
    row.id = 1
    row.dict_code = dict_code
    row.key = key
    row.label_zh = label_zh
    row.label_en = label_en
    row.description = description
    row.sort = sort
    row.is_active = is_active
    row.effective_at = None
    row.deprecated_at = None
    row.metadata_json = metadata_json
    row.created_at = datetime(2026, 6, 19)
    row.updated_at = datetime(2026, 6, 19)
    return row


def _make_l1_data() -> dict[str, dict[str, Any]]:
    """构造 L1 缓存数据 (dict[code] = {label_*, version, is_active, is_readonly, items})."""
    return {
        "reject_reason": {
            "label_zh": "拒绝原因",
            "label_en": "Reject Reason",
            "version": 1,
            "is_active": True,
            "is_readonly": False,
            "items": [
                {
                    "key": "duplicate",
                    "label_zh": "重复",
                    "label_en": "Duplicate",
                    "sort": 1,
                    "is_active": True,
                    "description": None,
                    "metadata_json": None,
                    "effective_at": None,
                    "deprecated_at": None,
                },
                {
                    "key": "other",
                    "label_zh": "其他",
                    "label_en": "Other",
                    "sort": 99,
                    "is_active": False,  # 软删过
                    "description": None,
                    "metadata_json": None,
                    "effective_at": None,
                    "deprecated_at": None,
                },
            ],
        },
    }


# ---- 读路径 ----


@pytest.mark.asyncio
async def test_list_all_dicts_returns_codes():
    """list_all_dicts 返 [{code, label_zh, label_en, version, is_active}, ...]."""

    _CACHE.lookup_cache.reset_l1()
    await _CACHE.lookup_cache.set_all(_make_l1_data())

    result = await LookupService.list_all_dicts()

    assert len(result) == 1
    assert result[0]["code"] == "reject_reason"
    assert result[0]["label_zh"] == "拒绝原因"
    assert result[0]["label_en"] == "Reject Reason"
    assert result[0]["version"] == 1
    assert result[0]["is_active"] is True


@pytest.mark.asyncio
async def test_list_all_dicts_uses_cache_when_available():
    """L1 命中时不走 DB (验证 _load_all_from_db 未调)."""

    _CACHE.lookup_cache.reset_l1()
    await _CACHE.lookup_cache.set_all(_make_l1_data())

    # patch _load_all_from_db → 如果调了就抛 (确保 cache miss 路径不触发)
    with patch.object(
        LookupService,
        "_load_all_from_db",
        side_effect=AssertionError("should not load from DB when cache hit"),
    ):
        result = await LookupService.list_all_dicts()
        assert len(result) == 1


@pytest.mark.asyncio
async def test_get_dict_returns_items_with_only_active_filter():
    """get(only_active=True) 默认过滤 is_active=False 的 item."""

    _CACHE.lookup_cache.reset_l1()
    await _CACHE.lookup_cache.set_all(_make_l1_data())

    # 默认 only_active=True → "other" (is_active=False) 应被过滤
    result = await LookupService.get("reject_reason")
    keys = [i["key"] for i in result["items"]]
    assert keys == ["duplicate"]

    # only_active=False → 含 "other"
    result_all = await LookupService.get("reject_reason", only_active=False)
    keys_all = [i["key"] for i in result_all["items"]]
    assert sorted(keys_all) == ["duplicate", "other"]


@pytest.mark.asyncio
async def test_get_dict_filters_lang():
    """get(lang="zh") 不返 label_en; lang="en" 不返 label_zh; both 都返."""

    _CACHE.lookup_cache.reset_l1()
    await _CACHE.lookup_cache.set_all(_make_l1_data())

    # lang="zh"
    zh = await LookupService.get("reject_reason", lang="zh")
    assert all("label_en" not in i for i in zh["items"])
    assert all("label_zh" in i for i in zh["items"])

    # lang="en"
    en = await LookupService.get("reject_reason", lang="en")
    assert all("label_zh" not in i for i in en["items"])
    assert all("label_en" in i for i in en["items"])

    # lang="both" (默认)
    both = await LookupService.get("reject_reason", lang="both")
    assert all("label_zh" in i and "label_en" in i for i in both["items"])


@pytest.mark.asyncio
async def test_get_one_returns_single_item():
    """get_one(code, key) 命中返单 item dict."""

    _CACHE.lookup_cache.reset_l1()
    await _CACHE.lookup_cache.set_all(_make_l1_data())

    item = await LookupService.get_one("reject_reason", "duplicate")
    assert item["key"] == "duplicate"
    assert item["label_zh"] == "重复"


@pytest.mark.asyncio
async def test_get_one_raises_not_found():
    """get_one 不存在的 key 抛 _EXC.LookupNotFoundError."""

    _CACHE.lookup_cache.reset_l1()
    await _CACHE.lookup_cache.set_all(_make_l1_data())

    with pytest.raises(_EXC.LookupNotFoundError) as exc:
        await LookupService.get_one("reject_reason", "nonexistent")
    assert "nonexistent" in str(exc.value)

    # 不存在的字典
    with pytest.raises(_EXC.LookupNotFoundError):
        await LookupService.get_one("nonexistent_dict", "foo")


# ---- 写路径 ----


@pytest.mark.asyncio
async def test_create_item_inserts_and_invalidates_cache():
    """create_item: INSERT 新 item + version+1 + 失效 cache + audit 写."""

    _CACHE.lookup_cache.reset_l1()
    await _CACHE.lookup_cache.set_all(_make_l1_data())

    # mock session.execute: 字典存在 (scalar_one_or_none → dict_row) + key 不重复 (None)
    mock_session = MagicMock()
    dict_row = _make_dict_row(code="reject_reason", version=1)
    select_dict_result = MagicMock()
    select_dict_result.scalar_one_or_none.return_value = dict_row
    # create_item 内两次 SELECT (字典存在性 + key 重复检查), 都返 mock
    select_item_result = MagicMock()
    select_item_result.scalar_one_or_none.return_value = None  # 不重复
    mock_session.execute.side_effect = [select_dict_result, select_item_result]

    with (
        patch("src.lookups.service.session_scope", lambda: _mock_session_scope(mock_session)),
        patch("src.lookups.service.lookup_cache.invalidate", new=AsyncMock()) as mock_invalidate,
        patch("src.lookups.service.log_dict_change") as mock_audit,
    ):
        result = await LookupService.create_item(
            "reject_reason",
            {"key": "new_one", "label_zh": "新原因", "label_en": "New Reason", "sort": 50},
            actor="admin@example.com",
            actor_id=42,
            ip="127.0.0.1",
        )

    # 1. return 新 item (含 is_active=True)
    assert result["key"] == "new_one"
    assert result["is_active"] is True

    # 2. INSERT: s.add() 被调一次 (新 item)
    assert mock_session.add.call_count == 1

    # 3. cache.invalidate(dict_code) 被调一次
    mock_invalidate.assert_awaited_once_with("reject_reason")

    # 4. audit log_dict_change 被调一次, action=item.create
    mock_audit.assert_called_once()
    kwargs = mock_audit.call_args.kwargs
    assert kwargs["action"] == "item.create"
    assert kwargs["actor_id"] == 42
    assert kwargs["target"] == "reject_reason:new_one"
    assert kwargs["ip"] == "127.0.0.1"

    # 5. 字典 version + 1 (mock dict_row.version)
    assert dict_row.version == 2


@pytest.mark.asyncio
async def test_create_item_raises_409_on_duplicate():
    """create_item 重复 key → 409 _EXC.LookupSafetyError, 不写 DB."""

    _CACHE.lookup_cache.reset_l1()
    await _CACHE.lookup_cache.set_all(_make_l1_data())

    mock_session = MagicMock()
    dict_row = _make_dict_row(code="reject_reason")
    # 1st select (dict 存在) → dict_row; 2nd select (key 重复) → existing item
    select_dict = MagicMock()
    select_dict.scalar_one_or_none.return_value = dict_row
    select_dup = MagicMock()
    select_dup.scalar_one_or_none.return_value = _make_item_row(dict_code="reject_reason", key="duplicate")
    mock_session.execute.side_effect = [select_dict, select_dup]

    with patch("src.lookups.service.session_scope", lambda: _mock_session_scope(mock_session)):
        with pytest.raises(_EXC.LookupSafetyError) as exc:
            await LookupService.create_item(
                "reject_reason",
                {"key": "duplicate", "label_zh": "重复", "label_en": "Duplicate"},
                actor="admin@example.com",
                actor_id=42,
                ip="127.0.0.1",
            )
    assert exc.value.http_status == 409
    assert "already exists" in exc.value.detail


@pytest.mark.asyncio
async def test_patch_item_updates_and_invalidates_cache():
    """patch_item: 更新 label_zh + version+1 + 失效 cache + audit 写 before/after."""

    _CACHE.lookup_cache.reset_l1()
    await _CACHE.lookup_cache.set_all(_make_l1_data())

    mock_session = MagicMock()
    # patch_item: 第一次 SELECT item, 第二次 SELECT dict (version + 1)
    item_row = _make_item_row(dict_code="reject_reason", key="duplicate", label_zh="重复", sort=1)
    dict_row = _make_dict_row(code="reject_reason", version=1)
    select_item = MagicMock()
    select_item.scalar_one_or_none.return_value = item_row
    select_dict = MagicMock()
    select_dict.scalar_one.return_value = dict_row
    mock_session.execute.side_effect = [select_item, select_dict]

    with (
        patch("src.lookups.service.session_scope", lambda: _mock_session_scope(mock_session)),
        patch("src.lookups.service.lookup_cache.invalidate", new=AsyncMock()) as mock_invalidate,
        patch("src.lookups.service.log_dict_change") as mock_audit,
    ):
        result = await LookupService.patch_item(
            "reject_reason",
            "duplicate",
            {"label_zh": "重复 (重命名)", "sort": 10},
            actor="admin@example.com",
            actor_id=42,
            ip="127.0.0.1",
        )

    # 1. return 含新 label_zh / sort
    assert result["key"] == "duplicate"
    assert result["label_zh"] == "重复 (重命名)"
    assert result["sort"] == 10

    # 2. 字段已 set
    assert item_row.label_zh == "重复 (重命名)"
    assert item_row.sort == 10

    # 3. dict version + 1
    assert dict_row.version == 2

    # 4. cache invalidate
    mock_invalidate.assert_awaited_once_with("reject_reason")

    # 5. audit before/after 都含 label_zh
    kwargs = mock_audit.call_args.kwargs
    assert kwargs["before"]["label_zh"] == "重复"
    assert kwargs["after"]["label_zh"] == "重复 (重命名)"
    assert kwargs["before"]["sort"] == 1
    assert kwargs["after"]["sort"] == 10


@pytest.mark.asyncio
async def test_soft_delete_item_sets_deprecated_at():
    """soft_delete_item: is_active=False + deprecated_at + version+1 + audit forced."""

    _CACHE.lookup_cache.reset_l1()
    await _CACHE.lookup_cache.set_all(_make_l1_data())

    mock_session = MagicMock()
    item_row = _make_item_row(dict_code="reject_reason", key="duplicate", is_active=True)
    dict_row = _make_dict_row(code="reject_reason", version=1)
    select_item = MagicMock()
    select_item.scalar_one_or_none.return_value = item_row
    select_dict = MagicMock()
    select_dict.scalar_one.return_value = dict_row
    mock_session.execute.side_effect = [select_item, select_dict]

    with (
        patch("src.lookups.service.session_scope", lambda: _mock_session_scope(mock_session)),
        patch("src.lookups.service.lookup_cache.invalidate", new=AsyncMock()) as mock_invalidate,
        patch("src.lookups.service.log_dict_change") as mock_audit,
    ):
        result = await LookupService.soft_delete_item(
            "reject_reason",
            "duplicate",
            actor="admin@example.com",
            actor_id=42,
            ip="127.0.0.1",
            force=True,  # 测试 force 路径, audit 标 forced=True
        )

    # 1. return 含 is_active=False
    assert result["key"] == "duplicate"
    assert result["is_active"] is False
    assert "deprecated_at" in result

    # 2. row 字段已改
    assert item_row.is_active is False
    assert item_row.deprecated_at is not None

    # 3. version + 1
    assert dict_row.version == 2

    # 4. invalidate
    mock_invalidate.assert_awaited_once_with("reject_reason")

    # 5. audit forced=True (因为我们传了 force=True)
    kwargs = mock_audit.call_args.kwargs
    assert kwargs["forced"] is True
    assert kwargs["action"] == "item.delete"
    assert kwargs["actor_id"] == 42
