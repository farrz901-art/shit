"""memory router 集成测试 (2026-06-16)"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture
def mock_service():
    svc = MagicMock()
    svc.search.return_value = []
    return svc


@pytest.fixture
def app_with_memory(mock_service, monkeypatch):
    """构造一个最小 FastAPI app, 挂上 memory_router, mock service 实例 + 鉴权"""
    from src.memory import service as service_mod

    monkeypatch.setattr(service_mod, "MemoryService", lambda: mock_service)

    app = FastAPI()
    from src.memory.router import memory_router

    app.include_router(memory_router)

    # override require_account 守卫 — 注入一个 has_account 的 mock current user
    from src.permissions.guards import require_account
    from tests.helpers import mock_current_user

    app.dependency_overrides[require_account] = lambda: mock_current_user(
        id=1,
        role="super_admin",
        is_account=True,
    )

    return app


@pytest.fixture
def client(app_with_memory):
    return TestClient(app_with_memory)


def test_search_200_dev_mode(client, mock_service):
    """dev mode (RAG_DEV_AUTH=true) 下无 cookie 也走 dev user, search 返 200 + memories"""
    import os

    os.environ["RAG_DEV_AUTH"] = "true"
    try:
        mock_service.search.return_value = []
        resp = client.post("/api/memory/search", json={"query": "test", "limit": 3})
        assert resp.status_code == 200
        assert resp.json() == {"memories": []}
    finally:
        del os.environ["RAG_DEV_AUTH"]


def test_search_401_without_token_and_no_dev_mode(client, app_with_memory, mock_service):
    """非 dev mode + 无 cookie → 401"""
    import os

    from fastapi import HTTPException

    from src.permissions.guards import require_account

    # 覆写 require_account 模拟无 token 401
    def _raise_401():
        raise HTTPException(401, "missing x-user-token")

    app_with_memory.dependency_overrides[require_account] = _raise_401
    os.environ.pop("RAG_DEV_AUTH", None)
    resp = client.post("/api/memory/search", json={"query": "test", "limit": 3})
    assert resp.status_code == 401


def test_search_returns_empty_on_service_degradation(client, mock_service):
    """service 降级 (返空) → 200 + {memories: []}, router 透传不报错"""
    import os

    os.environ["RAG_DEV_AUTH"] = "true"
    try:
        mock_service.search.return_value = []
        resp = client.post("/api/memory/search", json={"query": "test"})
        assert resp.status_code == 200
        assert resp.json()["memories"] == []
    finally:
        del os.environ["RAG_DEV_AUTH"]


def test_search_400_on_invalid_body(client):
    """缺 query 字段 → 422 (Pydantic 校验)"""
    import os

    os.environ["RAG_DEV_AUTH"] = "true"
    try:
        resp = client.post("/api/memory/search", json={})
        assert resp.status_code == 422
    finally:
        del os.environ["RAG_DEV_AUTH"]


def test_add_204_dev_mode(client, mock_service):
    """dev mode + 有效 body → 204, service.add 被调一次"""
    import os

    os.environ["RAG_DEV_AUTH"] = "true"
    try:
        resp = client.post(
            "/api/memory/add",
            json={
                "messages": [{"role": "user", "content": "hi"}],
                "conversation_id": "c1",
            },
        )
        assert resp.status_code == 204
        assert mock_service.add.called
        # 验证 add 收到 CurrentUser + messages + conversation_id
        call_args = mock_service.add.call_args
        assert call_args[0][1] == [{"role": "user", "content": "hi"}]
        assert call_args[0][2] == "c1"
    finally:
        del os.environ["RAG_DEV_AUTH"]


def test_add_401_without_token_and_no_dev_mode(client, app_with_memory):
    """非 dev mode + 无 cookie → 401"""
    import os

    from fastapi import HTTPException

    from src.permissions.guards import require_account

    def _raise_401():
        raise HTTPException(401, "missing x-user-token")

    app_with_memory.dependency_overrides[require_account] = _raise_401
    os.environ.pop("RAG_DEV_AUTH", None)
    resp = client.post(
        "/api/memory/add",
        json={"messages": [{"role": "user", "content": "hi"}]},
    )
    assert resp.status_code == 401


def test_add_400_on_empty_messages(client):
    """messages=[] → 422 (Pydantic min_length=1)"""
    import os

    os.environ["RAG_DEV_AUTH"] = "true"
    try:
        resp = client.post("/api/memory/add", json={"messages": []})
        assert resp.status_code == 422
    finally:
        del os.environ["RAG_DEV_AUTH"]


# =============================================================================
# Phase 2 (2026-06-16): 记忆管理 4 端点
# =============================================================================


def test_list_200_dev_mode(client, mock_service):
    """GET /api/memory/list 返 200 + memories 数组"""
    import os

    from src.memory.schemas import MemoryHit

    os.environ["RAG_DEV_AUTH"] = "true"
    try:
        mock_service.list_memories.return_value = [
            # pyright basic 看不到 score=None / metadata=None 默认值
            MemoryHit(id="m1", text="用户叫张三"),  # pyright: ignore[reportCallIssue]
            MemoryHit(id="m2", text="用户住北京"),  # pyright: ignore[reportCallIssue]
        ]
        resp = client.get("/api/memory/list")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["memories"]) == 2
        assert body["memories"][0]["id"] == "m1"
        assert body["memories"][0]["text"] == "用户叫张三"
        assert body["memories"][1]["text"] == "用户住北京"
        mock_service.list_memories.assert_called_once()
    finally:
        del os.environ["RAG_DEV_AUTH"]


def test_update_200_dev_mode(client, mock_service):
    """PATCH /api/memory/{id} body={text} 返 204 + update_memory 被调"""
    import os

    os.environ["RAG_DEV_AUTH"] = "true"
    try:
        resp = client.patch("/api/memory/m1", json={"text": "用户叫李四"})
        assert resp.status_code == 204
        mock_service.update_memory.assert_called_once()
        args = mock_service.update_memory.call_args[0]
        # (current, memory_id, text)
        assert args[1] == "m1"
        assert args[2] == "用户叫李四"
    finally:
        del os.environ["RAG_DEV_AUTH"]


def test_update_403_on_cross_user(client, mock_service):
    """**关键**: PermissionError → 403 (防跨用户篡改)"""
    import os

    os.environ["RAG_DEV_AUTH"] = "true"
    try:
        mock_service.update_memory.side_effect = PermissionError("无权访问记忆 m1")
        resp = client.patch("/api/memory/m1", json={"text": "hijack"})
        assert resp.status_code == 403
        assert "无权" in resp.json()["detail"]
    finally:
        del os.environ["RAG_DEV_AUTH"]


def test_delete_200_dev_mode(client, mock_service):
    """DELETE /api/memory/{id} 返 204 + delete_memory 被调"""
    import os

    os.environ["RAG_DEV_AUTH"] = "true"
    try:
        resp = client.delete("/api/memory/m1")
        assert resp.status_code == 204
        mock_service.delete_memory.assert_called_once()
        args = mock_service.delete_memory.call_args[0]
        assert args[1] == "m1"
    finally:
        del os.environ["RAG_DEV_AUTH"]


def test_delete_403_on_cross_user(client, mock_service):
    """**关键**: delete 跨用户 → 403"""
    import os

    os.environ["RAG_DEV_AUTH"] = "true"
    try:
        mock_service.delete_memory.side_effect = PermissionError("无权访问记忆 m1")
        resp = client.delete("/api/memory/m1")
        assert resp.status_code == 403
    finally:
        del os.environ["RAG_DEV_AUTH"]


def test_delete_all_200_dev_mode(client, mock_service):
    """DELETE /api/memory/all 返 200 + {deleted_count: 0} (mem0 不返 count, 占位)"""
    import os

    os.environ["RAG_DEV_AUTH"] = "true"
    try:
        resp = client.delete("/api/memory/all")
        assert resp.status_code == 200
        assert resp.json() == {"deleted_count": 0}
        mock_service.delete_all_memories.assert_called_once()
    finally:
        del os.environ["RAG_DEV_AUTH"]
