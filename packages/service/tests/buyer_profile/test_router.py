"""buyer_profile/router.py 测试 (模式 1: mock)

Mock 策略:
- app.dependency_overrides 替换 require_account
- monkeypatch ProfileService 全体方法
- monkeypatch field_config 函数
- FastAPI TestClient 驱动.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture
def mock_ProfileService(monkeypatch):
    """Mock src.buyer_profile.router.ProfileService 为 MagicMock.

    各 test 在 mock_ProfileService.list_profiles.return_value = ... 等设置.
    """
    svc = MagicMock()
    # 默认 list 返回空
    svc.list_profiles.return_value = ([], 0)
    svc.get_profile_by_id.return_value = None
    svc.update_profile_by_id.return_value = False
    svc.soft_delete.return_value = False
    svc.get_changes.return_value = []
    monkeypatch.setattr("src.buyer_profile.router.ProfileService", svc)
    return svc


@pytest.fixture
def mock_field_configs(monkeypatch):
    """Mock field_config 4 个函数."""
    get = MagicMock(return_value=[])
    create = MagicMock(return_value={"id": 1, "code": "test", "label": "Test"})
    update = MagicMock(return_value={"id": 1, "code": "test", "label": "Updated"})
    delete = MagicMock(return_value=True)

    monkeypatch.setattr("src.buyer_profile.router.get_all_configs", get)
    monkeypatch.setattr("src.buyer_profile.router.create_config", create)
    monkeypatch.setattr("src.buyer_profile.router.update_config", update)
    monkeypatch.setattr("src.buyer_profile.router.soft_delete_config", delete)
    return {"get": get, "create": create, "update": update, "delete": delete}


@pytest.fixture
def app(mock_ProfileService, mock_field_configs):
    """构造最小 FastAPI app + buyer_profile router + mocked auth."""
    from src.buyer_profile.router import router

    app = FastAPI()
    app.include_router(router)

    from src.permissions.guards import require_account
    from tests.helpers import mock_current_user

    app.dependency_overrides[require_account] = lambda: mock_current_user(
        id=1,
        role="super_admin",
        is_account=True,
    )
    return app


@pytest.fixture
def client(app):
    return TestClient(app)


# ── 客户画像列表 ─────────────────────────────────────────


def test_list_profiles_empty(client, mock_ProfileService):
    """空列表返回 200 + items=[] total=0."""
    mock_ProfileService.list_profiles.return_value = ([], 0)
    resp = client.get("/api/buyer-profiles/")
    assert resp.status_code == 200
    body = resp.json()
    assert body == {"items": [], "total": 0}


def test_list_profiles_with_data(client, mock_ProfileService):
    """有数据时返回分页结果."""
    mock_ProfileService.list_profiles.return_value = (
        [
            {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "buyer_key": "whatsapp:+234801234567",
                "buyer_name": "ABC Trading",
                "status": "active",
            },
        ],
        1,
    )
    resp = client.get("/api/buyer-profiles/?limit=10&offset=0")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["items"]) == 1
    assert body["total"] == 1
    assert body["items"][0]["buyer_key"] == "whatsapp:+234801234567"


def test_list_profiles_with_status_filter(client, mock_ProfileService):
    """status 过滤参数透传给 service."""
    mock_ProfileService.list_profiles.return_value = ([], 0)
    client.get("/api/buyer-profiles/?status=archived")
    # 验证 service.list_profiles 收到 filters={"status": "archived"}
    _call = mock_ProfileService.list_profiles.call_args
    assert _call is not None
    # list_profiles(account_id, limit, offset, filters)
    filters = _call[0][3]  # 第四个位置参数
    assert filters == {"status": "archived"}


# ── 我的客户画像 (my-profile) ──────────────────────────────


def test_get_my_profile_creates_if_missing(client, mock_ProfileService):
    """profile 不存在时自动创建并返回."""
    mock_ProfileService.get_profile.return_value = None
    created = {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "buyer_key": "1",
        "buyer_name": None,
        "status": "active",
        "profile_data": {},
        "tags": [],
        "notes": None,
        "first_seen_at": None,
        "last_contact_at": None,
    }
    mock_ProfileService.create_or_get_profile.return_value = created

    resp = client.get("/api/buyer-profiles/my-profile")
    assert resp.status_code == 200
    body = resp.json()
    assert body["buyer_key"] == "1"
    # 验证 create_or_get_profile 被调用
    mock_ProfileService.create_or_get_profile.assert_called_once_with(1, "1")


def test_get_my_profile_exists(client, mock_ProfileService):
    """profile 已存在时直接返回."""
    existing = {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "buyer_key": "1",
        "buyer_name": "My Company",
        "status": "active",
        "profile_data": {"country": {"value": "Nigeria"}},
        "tags": ["vip"],
        "notes": "note",
        "first_seen_at": "2026-01-01T00:00:00",
        "last_contact_at": "2026-06-01T00:00:00",
    }
    mock_ProfileService.get_profile.return_value = existing

    resp = client.get("/api/buyer-profiles/my-profile")
    assert resp.status_code == 200
    body = resp.json()
    assert body["buyer_key"] == "1"
    assert body["buyer_name"] == "My Company"
    assert body["profile_data"]["country"]["value"] == "Nigeria"
    # 验证 create_or_get_profile 没有被调用
    mock_ProfileService.create_or_get_profile.assert_not_called()


# ── 客户画像详情 ─────────────────────────────────────────


def test_get_profile_found(client, mock_ProfileService):
    """查询存在的画像返回 200 + 数据."""
    mock_ProfileService.get_profile_by_id.return_value = {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "buyer_key": "whatsapp:+234801234567",
        "buyer_name": "ABC Trading",
        "status": "active",
        "profile_data": {},
    }
    resp = client.get("/api/buyer-profiles/550e8400-e29b-41d4-a716-446655440000")
    assert resp.status_code == 200
    assert resp.json()["buyer_name"] == "ABC Trading"


def test_get_profile_not_found(client, mock_ProfileService):
    """不存在的画像返回 404."""
    mock_ProfileService.get_profile_by_id.return_value = None
    resp = client.get("/api/buyer-profiles/550e8400-e29b-41d4-a716-446655440000")
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"]


# ── 客户画像更新 ─────────────────────────────────────────


def test_update_profile_204(client, mock_ProfileService):
    """更新成功返回 204."""
    mock_ProfileService.update_profile_by_id.return_value = True
    resp = client.patch(
        "/api/buyer-profiles/550e8400-e29b-41d4-a716-446655440000",
        json={"buyer_name": "New Name"},
    )
    assert resp.status_code == 204


def test_update_profile_404(client, mock_ProfileService):
    """更新不存在的画像返回 404."""
    mock_ProfileService.update_profile_by_id.return_value = False
    resp = client.patch(
        "/api/buyer-profiles/550e8400-e29b-41d4-a716-446655440000",
        json={"buyer_name": "New Name"},
    )
    assert resp.status_code == 404


# ── 客户画像归档 ─────────────────────────────────────────


def test_archive_profile_204(client, mock_ProfileService):
    """归档成功返回 204."""
    mock_ProfileService.soft_delete.return_value = True
    resp = client.delete("/api/buyer-profiles/550e8400-e29b-41d4-a716-446655440000")
    assert resp.status_code == 204


def test_archive_profile_404(client, mock_ProfileService):
    """归档不存在的画像返回 404."""
    mock_ProfileService.soft_delete.return_value = False
    resp = client.delete("/api/buyer-profiles/550e8400-e29b-41d4-a716-446655440000")
    assert resp.status_code == 404


# ── 变更日志 ─────────────────────────────────────────────


def test_get_changes_empty(client, mock_ProfileService):
    """无变更时返回空列表."""
    mock_ProfileService.get_changes.return_value = []
    resp = client.get(
        "/api/buyer-profiles/550e8400-e29b-41d4-a716-446655440000/changes",
    )
    assert resp.status_code == 200
    assert resp.json() == []


def test_get_changes_with_data(client, mock_ProfileService):
    """有变更时返回列表."""
    mock_ProfileService.get_changes.return_value = [
        {
            "id": 1,
            "profile_id": "550e8400-e29b-41d4-a716-446655440000",
            "field_code": "country",
            "old_value": "Nigeria",
            "new_value": "Ghana",
            "source": "auto",
            "conv_id": None,
            "created_at": "2026-06-22T00:00:00",
        },
    ]
    resp = client.get(
        "/api/buyer-profiles/550e8400-e29b-41d4-a716-446655440000/changes",
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["field_code"] == "country"


# ── 字段配置 ─────────────────────────────────────────────


def test_list_field_configs_empty(client, mock_field_configs):
    """空字段配置返回 []."""
    mock_field_configs["get"].return_value = []
    resp = client.get("/api/buyer-profiles/fields")
    assert resp.status_code == 200
    assert resp.json() == []


def test_list_field_configs_with_data(client, mock_field_configs):
    """有字段配置时返回列表."""
    mock_field_configs["get"].return_value = [
        {"id": 1, "code": "country", "label": "Country", "field_type": "text"},
    ]
    resp = client.get("/api/buyer-profiles/fields")
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["code"] == "country"


def test_create_field_config_201(client, mock_field_configs):
    """创建字段配置返回 201 + 记录."""
    mock_field_configs["create"].return_value = {
        "id": 1,
        "code": "country",
        "label": "Country",
        "field_type": "select",
    }
    resp = client.post(
        "/api/buyer-profiles/fields",
        json={"code": "country", "label": "Country"},
    )
    assert resp.status_code == 201
    assert resp.json()["code"] == "country"


def test_update_field_config_200(client, mock_field_configs):
    """更新字段配置返回 200 + 更新后记录."""
    mock_field_configs["update"].return_value = {
        "id": 1,
        "code": "country",
        "label": "Updated Country",
    }
    resp = client.patch(
        "/api/buyer-profiles/fields/country",
        json={"label": "Updated Country"},
    )
    assert resp.status_code == 200


def test_update_field_config_404(client, mock_field_configs):
    """更新不存在的字段配置返回 404."""
    mock_field_configs["update"].return_value = None
    resp = client.patch(
        "/api/buyer-profiles/fields/nonexistent",
        json={"label": "X"},
    )
    assert resp.status_code == 404


def test_delete_field_config_204(client, mock_field_configs):
    """删除字段配置成功返回 204."""
    mock_field_configs["delete"].return_value = True
    resp = client.delete("/api/buyer-profiles/fields/country")
    assert resp.status_code == 204


def test_delete_field_config_404(client, mock_field_configs):
    """删除不存在的字段配置返回 404."""
    mock_field_configs["delete"].return_value = False
    resp = client.delete("/api/buyer-profiles/fields/nonexistent")
    assert resp.status_code == 404


# ── 鉴权 ────────────────────────────────────────────────


def test_401_without_auth(app):
    """无有效 token 时所有端点返回 401."""
    from fastapi import HTTPException

    from src.permissions.guards import require_account

    def _raise_401():
        raise HTTPException(401, "missing x-user-token")

    app.dependency_overrides[require_account] = _raise_401
    client = TestClient(app)

    # 测试几个典型端点
    assert client.get("/api/buyer-profiles/").status_code == 401
    assert client.get("/api/buyer-profiles/550e8400-e29b-41d4-a716-446655440000").status_code == 401
    # GET /fields 无需鉴权（全局模板), POST/PATCH/DELETE 仍需登录
    assert client.get("/api/buyer-profiles/fields").status_code == 200
    assert client.post("/api/buyer-profiles/fields", json={"code": "x", "label": "X"}).status_code == 401
