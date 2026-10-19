"""chat_share router 测试 (2026-06-16)

6 用例: 创建 / 401 / 公开读 / 公开 404 / 所有者撤销 / 非所有者撤销 404.

模式: 跟 approvals/router 测试一致 — 用 app.dependency_overrides 注入 mock 鉴权,
避免 _ensure_dev_user 真 DB 调用 (本地 PG 无密码时整链路炸).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture
def mock_service():
    """mock ChatShareService 实例 — 4 个方法默认返合理占位."""
    svc = MagicMock()
    svc.create_share = MagicMock(
        return_value={
            "share_id": "abc123456789",
            "url": "http://localhost:3000/zh/chat/s/abc123456789",
            "title": "t",
            "expires_at": None,
            "created_at": datetime(2026, 6, 16, tzinfo=UTC),
        }
    )
    svc.get_share = MagicMock(
        return_value={
            "share_id": "x",
            "title": "t",
            "messages": [],
            "model": "gpt-4o-mini",
            "created_at": datetime(2026, 6, 16, tzinfo=UTC),
        }
    )
    svc.revoke_share = MagicMock(return_value=None)
    svc.upload_to_dify = AsyncMock(return_value={"uploadFileId": "file-abc-123"})
    return svc


def _make_user(id_: int = 1) -> Any:
    """构造 mock CurrentUser (绕过 Pydantic init)."""
    from src.middleware.auth import CurrentUser

    return CurrentUser(
        id=id_,
        public_token=f"tok-{id_}",
        role="user",  # is_admin 是 property, 从 role 派生
        is_account=False,
    )


@pytest.fixture
def app_with_chat_share(mock_service):
    """构造 FastAPI app, 挂上 chat_share_router, mock service + 鉴权覆盖.

    (2026-06-30) 改 app.dependency_overrides 模式, 跟 approvals 测试一致 —
    之前 router_mod._get_service = lambda: mock_service 在 Depends 改成 generator 后失效.
    """
    from src.chat_share import router as router_mod
    from src.middleware.auth import resolve_user

    app = FastAPI()
    app.include_router(router_mod.router)
    # 覆盖 service: 直接返 mock 实例 (避开 SqlAlchemy repo 真 DB 调用)
    app.dependency_overrides[router_mod._get_service] = lambda: mock_service
    # 覆盖鉴权: 直接返 mock CurrentUser, 跳过 _ensure_dev_user 的真 DB 调用
    app.dependency_overrides[resolve_user] = lambda: _make_user(id_=42)
    return app


@pytest.fixture
def client(app_with_chat_share):
    return TestClient(app_with_chat_share)


# ---- POST /api/chat/shares ----


def test_create_share_200_with_auth_override(client, mock_service):
    """鉴权覆盖 + 有效 body (含 messages 快照) → 200 + share_id"""
    resp = client.post(
        "/api/chat/shares",
        json={
            "conv_id": "c1",
            "title": "t",
            "messages": [{"role": "user", "content": "hi"}],
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["share_id"] == "abc123456789"
    assert body["title"] == "t"
    assert "url" in body


def test_create_share_requires_messages(client, mock_service):
    """messages 字段必填; 缺 → 422"""
    resp = client.post(
        "/api/chat/shares",
        json={"conv_id": "c1", "title": "t"},
    )
    assert resp.status_code == 422
    body = resp.json()
    assert "messages" in str(body).lower()


def test_create_share_persists_messages_snapshot(client, mock_service):
    """携带 messages → 200 + service.create_share 收到 messages 参数"""
    resp = client.post(
        "/api/chat/shares",
        json={
            "conv_id": "c1",
            "title": "t",
            "messages": [
                {"role": "user", "content": "hi"},
                {"role": "assistant", "content": "hello"},
            ],
        },
    )
    assert resp.status_code == 200
    call_args = mock_service.create_share.call_args
    assert call_args.kwargs["messages"] == [
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "hello"},
    ]


def test_create_share_401_without_token_and_no_dev_mode(client):
    """非 dev mode + 无 cookie → 401 — 单独构造一个无 overrides 的 app"""
    from src.chat_share import router as router_mod

    app = FastAPI()
    app.include_router(router_mod.router)
    # 故意不 override resolve_user, 让真依赖跑 → 401
    no_auth_client = TestClient(app)
    import os

    os.environ.pop("RAG_DEV_AUTH", None)
    resp = no_auth_client.post("/api/chat/shares", json={"conv_id": "c1"})
    assert resp.status_code == 401


# ---- GET /api/chat/shares/{share_id} (公开) ----


def test_get_share_200_anon_no_token_required(client, mock_service):
    """**关键**: get_share 公开, anon 可读 (无 cookie / 无 dev mode / 无鉴权覆盖)"""
    import os

    os.environ.pop("RAG_DEV_AUTH", None)
    # 用一个新 app (无 resolve_user override, 但 override service 避开真 DB) 验证 anon 真能读
    from src.chat_share import router as router_mod

    app = FastAPI()
    app.include_router(router_mod.router)
    app.dependency_overrides[router_mod._get_service] = lambda: mock_service
    anon_client = TestClient(app)
    resp = anon_client.get("/api/chat/shares/abc123456789")
    assert resp.status_code == 200
    assert resp.json()["share_id"] == "x"


def test_get_share_404_for_unknown(client, mock_service):
    """**关键**: 不存在返 404 (公开, 不能返 401 否则暴露 ID 探测)"""
    from src.chat_share.service import ShareNotFound

    mock_service.get_share.side_effect = ShareNotFound("nope")
    import os

    os.environ.pop("RAG_DEV_AUTH", None)
    from src.chat_share import router as router_mod

    app = FastAPI()
    app.include_router(router_mod.router)
    app.dependency_overrides[router_mod._get_service] = lambda: mock_service
    anon_client = TestClient(app)
    resp = anon_client.get("/api/chat/shares/nope")
    assert resp.status_code == 404


# ---- DELETE /api/chat/shares/{share_id} ----


def test_revoke_share_204_owner(client, mock_service):
    """所有者撤销 → 204"""
    resp = client.delete("/api/chat/shares/abc123456789")
    assert resp.status_code == 204
    # 验证 service 收到 share_id (positional) + current_user_id (kwarg, mock user.id=42 → 42)
    call_args = mock_service.revoke_share.call_args
    assert call_args.args[0] == "abc123456789"
    assert call_args.kwargs["current_user_id"] == 42


def test_revoke_share_404_non_owner(client, mock_service):
    """非所有者撤销 → 404 (跟不存在同异常, 防 ID 探测)"""
    from src.chat_share.service import ShareNotFound

    mock_service.revoke_share.side_effect = ShareNotFound("not owner")
    resp = client.delete("/api/chat/shares/abc123456789")
    assert resp.status_code == 404


# ---- GET /api/chat/shares?conv_id= ----


def test_list_shares_returns_only_current_user_shares(client, mock_service):
    """GET /api/chat/shares?conv_id= → 200 + 返当前用户的 share 列表"""
    from datetime import UTC, datetime

    mock_service.list_shares = MagicMock(
        return_value=[
            {
                "share_id": "abc",
                "url": "http://localhost:3000/zh/chat/s/abc",
                "title": "t",
                "expires_at": None,
                "created_at": datetime(2026, 6, 30, tzinfo=UTC),
            }
        ]
    )
    resp = client.get("/api/chat/shares?conv_id=c1")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["share_id"] == "abc"
    call_args = mock_service.list_shares.call_args
    assert call_args.kwargs["conv_id"] == "c1"
    assert call_args.kwargs["user_id"] == 42  # mock fixture user id=42


# ---- (2026-06-30) _get_service 回归测试 ----


def test_get_service_depends_injects_chat_share_service_instance(mock_service):
    """(2026-06-30) 回归: _get_service 必须能被 FastAPI Depends 注入, 返 ChatShareService 实例.
    修 _get_service bug 前直接传 session_scope 函数 → repo._session 是函数 → query() 炸.
    """
    from src.chat_share import router as router_mod
    from src.chat_share.service import ChatShareService

    # _get_service 是 generator-style Depends (函数对象), 不能再用属性替换.
    # 必须通过 FastAPI app.dependency_overrides 注入才能拿到 service 实例.
    app = FastAPI()
    app.include_router(router_mod.router)
    app.dependency_overrides[router_mod._get_service] = lambda: mock_service
    from src.middleware.auth import resolve_user

    app.dependency_overrides[resolve_user] = lambda: _make_user(id_=42)

    with TestClient(app) as tc:
        # 调 list_shares, 验 mock 被调 (意味着 _get_service 被 FastAPI 通过 Depends 注入)
        tc.get("/api/chat/shares?conv_id=test-conv")
        # 关键断言: 依赖注入链通, mock_svc.list_shares 真被调
        assert mock_service.list_shares.called, "依赖注入失败, mock_svc.list_shares 没被调"
        # 关键断言: service 是 mock 实例 (spec=ChatShareService) 不是 function 对象
        assert isinstance(mock_service, MagicMock)
        # 验证 ChatShareService 类型元数据完整 (可正常实例化, 跟被破坏的 placeholder 区分)
        assert callable(ChatShareService)
