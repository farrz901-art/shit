"""lookups_router 3 端点测试 (2026-06-19 lookup spec Task 5, 模式 1 mock)

CLAUDE.md 规范: 测试禁止连真 PG / Redis. 这里:
- patch LookupService 静态方法 (不连 PG, 不连 Redis)
- TestClient + dependency_overrides[resolve_user] 模拟登录用户
- LookupNotFoundError 模拟 404 路径
- 不实例化真实 DB session / Redis 连接

测试矩阵 (6):
1. test_list_all_dicts_returns_200_with_codes — GET /api/lookups 返 {dictionaries: [...]}
2. test_list_all_dicts_requires_authentication — 无 token 401 (走 resolve_user)
3. test_get_dict_returns_items — GET /api/lookups/reject_reason 返 items[]
4. test_get_dict_404_for_missing_code — 404 (LookupNotFoundError → HTTPException)
5. test_get_dict_filters_only_active — ?only_active=false 返全部 (含 inactive)
6. test_get_one_item_returns_dict — GET /api/lookups/reject_reason/duplicate 返 item
"""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

# ---- helpers ----


def _make_user(id_: int = 1) -> Any:
    """构造 mock CurrentUser (鉴权用)."""
    from src.middleware.auth import CurrentUser

    return CurrentUser(
        id=id_,
        public_token=f"tok-{id_}",
        is_account=True,
        role="user",
        email=f"u{id_}@x.com",
    )


def _make_dict_summary(code: str = "reject_reason", version: int = 1) -> dict[str, Any]:
    """构造 DictionarySummary dict (LookupService.list_all_dicts 返参格式)."""
    return {
        "code": code,
        "label_zh": "拒绝原因",
        "label_en": "Reject Reason",
        "version": version,
        "is_active": True,
    }


def _make_dict_with_items(
    code: str = "reject_reason",
    items: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """构造 DictionaryResponse dict (LookupService.get 返参格式)."""
    if items is None:
        items = [
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
                "is_active": True,
                "description": None,
                "metadata_json": None,
                "effective_at": None,
                "deprecated_at": None,
            },
        ]
    return {
        "code": code,
        "label_zh": "拒绝原因",
        "label_en": "Reject Reason",
        "version": 1,
        "items": items,
    }


def _make_item(
    key: str = "duplicate",
    label_zh: str = "重复",
    label_en: str = "Duplicate",
    sort: int = 1,
    is_active: bool = True,
) -> dict[str, Any]:
    """构造 LookupItem dict (LookupService.get_one 返参格式)."""
    return {
        "key": key,
        "label_zh": label_zh,
        "label_en": label_en,
        "sort": sort,
        "is_active": is_active,
        "description": None,
        "metadata_json": None,
        "effective_at": None,
        "deprecated_at": None,
    }


def _build_app_with_user(user_id: int = 1) -> tuple[TestClient, Any]:
    """构造 FastAPI app + TestClient + mock user 注入, 返 (client, mock_user)."""
    from src.lookups.router import router as lookups_router
    from src.middleware.auth import resolve_user

    mock_user = _make_user(id_=user_id)
    app = FastAPI()
    app.include_router(lookups_router)
    app.dependency_overrides[resolve_user] = lambda: mock_user
    return TestClient(app), mock_user


# ==================== 3 端点 + 鉴权 + 404 ====================


def test_list_all_dicts_returns_200_with_codes():
    """GET /api/lookups 返 {dictionaries: [{code, label_*, version, is_active}, ...]}."""
    from src.lookups.service import LookupService

    mock_summary = [
        _make_dict_summary(code="reject_reason", version=1),
        _make_dict_summary(code="approval_review_status", version=2),
    ]

    with patch.object(LookupService, "list_all_dicts", return_value=mock_summary) as mock_list:
        client, _ = _build_app_with_user()
        resp = client.get("/api/lookups")

    assert resp.status_code == 200
    data = resp.json()
    assert "dictionaries" in data
    assert len(data["dictionaries"]) == 2
    assert data["dictionaries"][0]["code"] == "reject_reason"
    assert data["dictionaries"][0]["label_zh"] == "拒绝原因"
    assert data["dictionaries"][1]["code"] == "approval_review_status"
    assert data["dictionaries"][1]["version"] == 2
    # 验证 router 调的是 static method (无 args, 只 1 次)
    assert mock_list.call_count == 1


def test_list_all_dicts_requires_authentication():
    """无 token → 401 (resolve_user 抛 HTTPException 401).

    用 dependency_overrides 让 resolve_user 直接抛 401, 不走真鉴权链路
    (真链路会触 get_engine() 连真 PG, 违反 模式 1 mock 规范).
    """
    from fastapi import HTTPException

    from src.lookups.router import router as lookups_router
    from src.middleware.auth import resolve_user

    app = FastAPI()
    app.include_router(lookups_router)

    def _reject():
        raise HTTPException(status_code=401, detail="Unauthorized")

    app.dependency_overrides[resolve_user] = _reject

    client = TestClient(app)
    resp = client.get("/api/lookups")

    assert resp.status_code == 401


def test_get_dict_returns_items():
    """GET /api/lookups/reject_reason 返字典元数据 + items[]."""
    from src.lookups.service import LookupService

    expected = _make_dict_with_items(code="reject_reason")

    captured: dict[str, Any] = {}

    def _fake_get(dict_code, *, only_active=True, lang="both"):
        captured["dict_code"] = dict_code
        captured["only_active"] = only_active
        captured["lang"] = lang
        return expected

    with patch.object(LookupService, "get", side_effect=_fake_get):
        client, _ = _build_app_with_user()
        resp = client.get("/api/lookups/reject_reason")

    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == "reject_reason"
    assert data["label_zh"] == "拒绝原因"
    assert data["label_en"] == "Reject Reason"
    assert data["version"] == 1
    assert len(data["items"]) == 2
    assert data["items"][0]["key"] == "duplicate"
    assert data["items"][0]["label_zh"] == "重复"
    assert data["items"][1]["key"] == "other"
    # 验证 router 把 (dict_code, only_active, lang) 透传给 service
    assert captured == {"dict_code": "reject_reason", "only_active": True, "lang": "both"}


def test_get_dict_404_for_missing_code():
    """GET /api/lookups/nonexistent → 404 (LookupNotFoundError → HTTPException)."""
    from src.lookups.exceptions import LookupNotFoundError
    from src.lookups.service import LookupService

    def _fake_get(dict_code, *, only_active=True, lang="both"):
        raise LookupNotFoundError(f"dictionary '{dict_code}' not found")

    with patch.object(LookupService, "get", side_effect=_fake_get):
        client, _ = _build_app_with_user()
        resp = client.get("/api/lookups/nonexistent")

    assert resp.status_code == 404
    assert "nonexistent" in resp.json()["detail"]


def test_get_dict_filters_only_active():
    """?only_active=false → 返 inactive 项 (router 透传 only_active 给 service)."""
    from src.lookups.service import LookupService

    items_with_inactive = [
        _make_item(key="duplicate", is_active=True),
        _make_item(key="deprecated_old", is_active=False, sort=100),
    ]
    expected = _make_dict_with_items(code="reject_reason", items=items_with_inactive)

    captured: dict[str, Any] = {}

    def _fake_get(dict_code, *, only_active=True, lang="both"):
        captured["dict_code"] = dict_code
        captured["only_active"] = only_active
        captured["lang"] = lang
        return expected

    with patch.object(LookupService, "get", side_effect=_fake_get):
        client, _ = _build_app_with_user()
        resp = client.get("/api/lookups/reject_reason?only_active=false")

    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) == 2
    assert data["items"][1]["key"] == "deprecated_old"
    assert data["items"][1]["is_active"] is False
    # 验证 router 把 only_active=False 透传给 service
    assert captured["only_active"] is False
    assert captured["dict_code"] == "reject_reason"


def test_get_one_item_returns_dict():
    """GET /api/lookups/reject_reason/duplicate 返单 item."""
    from src.lookups.service import LookupService

    expected = _make_item(key="duplicate", label_zh="重复", label_en="Duplicate")

    captured: dict[str, Any] = {}

    def _fake_get_one(dict_code, key):
        captured["dict_code"] = dict_code
        captured["key"] = key
        return expected

    with patch.object(LookupService, "get_one", side_effect=_fake_get_one):
        client, _ = _build_app_with_user()
        resp = client.get("/api/lookups/reject_reason/duplicate")

    assert resp.status_code == 200
    data = resp.json()
    assert data["key"] == "duplicate"
    assert data["label_zh"] == "重复"
    assert data["label_en"] == "Duplicate"
    assert data["sort"] == 1
    assert data["is_active"] is True
    # 验证 router 把 (dict_code, key) 透传给 service
    assert captured == {"dict_code": "reject_reason", "key": "duplicate"}
