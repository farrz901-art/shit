"""chat_router 7 端点测试 (2026-06-19 chat spec, 模式 1 mock)

CLAUDE.md 规范: 测试禁止连真 PG / Redis 等数据库. 此处 mock
src.chat.router.resolve_user (鉴权) + src.chat.service.* 8 函数 (业务),
FastAPI TestClient 不依赖真 PG.

12 测试: 7 端点 + 鉴权 + 软删 + 跨用户 404 + 备份 + 消息分页

注: @audited decorator 内部走 _persist_audit → session_scope 写 audit_logs,
此处在 autouse fixture 里 patch 掉, 跟项目其他 chat 测试一致.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# ---- helpers ----


def _make_user(id_: int = 1) -> Any:
    """构造 mock CurrentUser (id_ 决定 ownership, 跨用户测试用不同 id_)."""
    from src.middleware.auth import CurrentUser

    return CurrentUser(
        id=id_,
        public_token=f"tok-{id_}",
        is_account=True,
        role="user",
        email=f"u{id_}@x.com",
    )


def _conv_dict(
    id_: str = "c1",
    title: str = "t1",
    message_count: int = 0,
    created_at: datetime | None = None,
    updated_at: datetime | None = None,
) -> dict[str, Any]:
    """构造 mock conv dict (router 期望的返参格式)."""
    if created_at is None:
        created_at = datetime(2026, 6, 19, tzinfo=UTC)
    if updated_at is None:
        updated_at = datetime(2026, 6, 19, tzinfo=UTC)
    return {
        "id": id_,
        "title": title,
        "message_count": message_count,
        "created_at": created_at,
        "updated_at": updated_at,
    }


def _msg_dict(
    id_: int = 1,
    role: str = "user",
    content: str = "hello",
    created_at: datetime | None = None,
) -> dict[str, Any]:
    """构造 mock msg dict."""
    if created_at is None:
        created_at = datetime(2026, 6, 19, tzinfo=UTC)
    return {
        "id": str(id_),
        "role": role,
        "content": content,
        "meta": None,
        "created_at": created_at,
    }


@pytest.fixture(autouse=True)
def _patch_audit_persist():
    """autouse: 屏蔽 @audited decorator 的 audit_logs 写入 (避免真 PG).

    @audited 调 _persist_audit, 内部 `from src.storage import session_scope`
    再 `with session_scope() as s:` 写 audit_logs. 这里 patch
    src.storage.session.session_scope 成 no-op context manager, 让 audit
    装饰器跑通但不真写库. 跟项目其他 chat 测试一致.
    """
    noop_session = MagicMock()

    @contextmanager
    def _cm():
        yield noop_session

    def _fake_session_scope():
        return _cm()

    with patch("src.storage.session.session_scope", _fake_session_scope):
        yield


# ==================== 7 端点 + 鉴权 ====================


def test_create_conversation_default_title():
    """POST /conversations 缺 body/title → 默认 '新对话'."""
    from src.chat import service as svc
    from src.chat.router import router as chat_router
    from src.middleware.auth import resolve_user

    expected = _conv_dict(id_="c1", title="新对话")
    with patch.object(svc, "create_conversation", return_value=expected) as mock_create:
        app = FastAPI()
        app.include_router(chat_router)
        app.dependency_overrides[resolve_user] = lambda: _make_user(id_=1)

        client = TestClient(app)
        resp = client.post("/api/chat/conversations", json={})

    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "新对话"
    assert data["message_count"] == 0
    assert "id" in data
    # 验证 service 收到 user_id=1 + title='新对话'
    assert mock_create.call_args.args[0] == 1
    assert mock_create.call_args.args[1] == "新对话"


def test_create_conversation_with_title():
    """POST /conversations 带 title → 返新 title."""
    from src.chat import service as svc
    from src.chat.router import router as chat_router
    from src.middleware.auth import resolve_user

    expected = _conv_dict(id_="c2", title="我的项目")
    with patch.object(svc, "create_conversation", return_value=expected):
        app = FastAPI()
        app.include_router(chat_router)
        app.dependency_overrides[resolve_user] = lambda: _make_user(id_=1)

        client = TestClient(app)
        resp = client.post("/api/chat/conversations", json={"title": "我的项目"})

    assert resp.status_code == 201
    assert resp.json()["title"] == "我的项目"


def test_list_conversations_empty():
    """空列表 → 返 []."""
    from src.chat import service as svc
    from src.chat.router import router as chat_router
    from src.middleware.auth import resolve_user

    with patch.object(svc, "list_conversations", return_value=[]):
        app = FastAPI()
        app.include_router(chat_router)
        app.dependency_overrides[resolve_user] = lambda: _make_user(id_=1)

        client = TestClient(app)
        resp = client.get("/api/chat/conversations")

    assert resp.status_code == 200
    assert resp.json() == []


def test_list_conversations_pagination():
    """limit=2 返 2 个 (mock service 返 3 个 → router 透传)."""
    from src.chat import service as svc
    from src.chat.router import router as chat_router
    from src.middleware.auth import resolve_user

    mock_list = [
        _conv_dict(id_="c1", title="c1"),
        _conv_dict(id_="c2", title="c2"),
        _conv_dict(id_="c3", title="c3"),
    ]
    with patch.object(svc, "list_conversations", return_value=mock_list) as mock_l:
        app = FastAPI()
        app.include_router(chat_router)
        app.dependency_overrides[resolve_user] = lambda: _make_user(id_=1)

        client = TestClient(app)
        resp = client.get("/api/chat/conversations?limit=2")

    assert resp.status_code == 200
    assert len(resp.json()) == 3  # router 透传 mock, 不分页 (分页是 service 做的)
    # 验证 router 把 limit/cursor 透传给 service
    assert mock_l.call_args.args[0] == 1  # user_id
    assert mock_l.call_args.args[1] == 2  # limit
    assert mock_l.call_args.args[2] is None  # cursor_before (首次请求无游标)


def test_list_conversations_cursor():
    """cursor_before + cursor_id → service 收到 cursor dict."""
    from src.chat import service as svc
    from src.chat.router import router as chat_router
    from src.middleware.auth import resolve_user

    mock_list = [_conv_dict(id_="c2", title="c2")]
    with patch.object(svc, "list_conversations", return_value=mock_list) as mock_l:
        app = FastAPI()
        app.include_router(chat_router)
        app.dependency_overrides[resolve_user] = lambda: _make_user(id_=1)

        client = TestClient(app)
        resp = client.get("/api/chat/conversations?limit=2&cursor_before=2026-06-02T00:00:00&cursor_id=c1")

    assert resp.status_code == 200
    assert mock_l.call_args.args[2] is not None
    assert mock_l.call_args.args[2]["id"] == "c1"


def test_get_conversation_not_found():
    """不存在的 conv_id → 404 (防 ID 探测)."""
    from src.chat import service as svc
    from src.chat.router import router as chat_router
    from src.middleware.auth import resolve_user

    with patch.object(svc, "get_conversation", return_value=None):
        app = FastAPI()
        app.include_router(chat_router)
        app.dependency_overrides[resolve_user] = lambda: _make_user(id_=1)

        client = TestClient(app)
        resp = client.get("/api/chat/conversations/00000000-0000-0000-0000-000000000000")

    assert resp.status_code == 404


def test_get_conversation_detail_with_messages():
    """GET /conversations/{id} 返详情 + messages."""
    from src.chat import service as svc
    from src.chat.router import router as chat_router
    from src.middleware.auth import resolve_user

    expected = _conv_dict(id_="c1", title="test")
    expected["messages"] = [_msg_dict(id_=1, content="hello")]
    with patch.object(svc, "get_conversation", return_value=expected) as mock_get:
        app = FastAPI()
        app.include_router(chat_router)
        app.dependency_overrides[resolve_user] = lambda: _make_user(id_=1)

        client = TestClient(app)
        resp = client.get("/api/chat/conversations/c1")

    assert resp.status_code == 200
    data = resp.json()
    assert data["title"] == "test"
    assert len(data["messages"]) == 1
    assert data["messages"][0]["content"] == "hello"
    # 验证 router 把 (user_id, conv_id) 透传给 service
    assert mock_get.call_args.args[0] == 1
    assert mock_get.call_args.args[1] == "c1"


def test_rename_conversation():
    """PATCH /conversations/{id} 改 title + updated_at."""
    from src.chat import service as svc
    from src.chat.router import router as chat_router
    from src.middleware.auth import resolve_user

    expected = _conv_dict(id_="c1", title="new")
    with patch.object(svc, "update_conversation", return_value=expected) as mock_upd:
        app = FastAPI()
        app.include_router(chat_router)
        app.dependency_overrides[resolve_user] = lambda: _make_user(id_=1)

        client = TestClient(app)
        resp = client.patch(
            "/api/chat/conversations/c1",
            json={"title": "new"},
        )

    assert resp.status_code == 200
    assert resp.json()["title"] == "new"
    # 验证 router 透传 (user_id, conv_id, title) 给 service
    assert mock_upd.call_args.args == (1, "c1", "new")


def test_soft_delete_conversation():
    """DELETE 软删 → 返 204; 后续 GET 返 404 (mock 两次 service)."""
    from src.chat import service as svc
    from src.chat.router import router as chat_router
    from src.middleware.auth import resolve_user

    with (
        patch.object(svc, "soft_delete_conversation", return_value=True) as mock_soft,
        patch.object(svc, "get_conversation", return_value=None) as mock_get,
    ):
        app = FastAPI()
        app.include_router(chat_router)
        app.dependency_overrides[resolve_user] = lambda: _make_user(id_=1)

        client = TestClient(app)
        resp = client.delete("/api/chat/conversations/c1")

        # 软删后 GET 返 404
        resp2 = client.get("/api/chat/conversations/c1")

    assert resp.status_code == 204
    assert resp2.status_code == 404
    # 验证 router 透传 (user_id, conv_id) 给 soft_delete_conversation
    assert mock_soft.call_args.args == (1, "c1")
    # get_conversation 被调 (router 翻译 404)
    assert mock_get.call_args.args == (1, "c1")


def test_soft_delete_other_user_conv_404():
    """跨用户删别人 conv → 404 (mock soft_delete 返 False, router 翻 404)."""
    from src.chat import service as svc
    from src.chat.router import router as chat_router
    from src.middleware.auth import resolve_user

    with patch.object(svc, "soft_delete_conversation", return_value=False) as mock_soft:
        app = FastAPI()
        app.include_router(chat_router)
        app.dependency_overrides[resolve_user] = lambda: _make_user(id_=1)

        client = TestClient(app)
        resp = client.delete("/api/chat/conversations/c2")

    assert resp.status_code == 404
    # 验证 router 透传 (user_id=1, conv_id='c2') — 跨用户场景 mock 返 False 模拟
    # 越权 (service 内部 WHERE user_id 不命中)
    assert mock_soft.call_args.args == (1, "c2")


def test_list_messages_pagination():
    """GET /conversations/{id}/messages 分页 2/页 (mock 返 5 条)."""
    from src.chat import service as svc
    from src.chat.router import router as chat_router
    from src.middleware.auth import resolve_user

    mock_msgs = [_msg_dict(id_=i, content=f"msg{i}") for i in range(5)]
    with patch.object(svc, "list_messages", return_value=mock_msgs) as mock_lm:
        app = FastAPI()
        app.include_router(chat_router)
        app.dependency_overrides[resolve_user] = lambda: _make_user(id_=1)

        client = TestClient(app)
        resp = client.get("/api/chat/conversations/c1/messages?limit=2&offset=0")

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 5  # router 透传 mock, 不分页
    assert data[0]["content"] == "msg0"
    assert data[1]["content"] == "msg1"
    # 验证 router 透传 (user_id, conv_id, limit, offset) 给 service
    assert mock_lm.call_args.args == (1, "c1", 2, 0)


def test_backup_all():
    """GET /backup 返全量 JSON (exported_at + conversations[]+messages[])."""
    from src.chat import service as svc
    from src.chat.router import router as chat_router
    from src.middleware.auth import resolve_user

    conv = _conv_dict(id_="c1", title="backup test")
    mock_backup = {
        "exported_at": datetime.now(UTC).isoformat(),
        "conversations": [
            {
                "id": conv["id"],
                "title": conv["title"],
                "message_count": conv["message_count"],
                "created_at": conv["created_at"].isoformat(),
                "updated_at": conv["updated_at"].isoformat(),
                "messages": [
                    {
                        "role": "assistant",
                        "content": "response",
                        "meta": None,
                        "created_at": datetime(2026, 6, 19, tzinfo=UTC).isoformat(),
                    }
                ],
            }
        ],
    }
    with patch.object(svc, "get_full_backup", return_value=mock_backup):
        app = FastAPI()
        app.include_router(chat_router)
        app.dependency_overrides[resolve_user] = lambda: _make_user(id_=1)

        client = TestClient(app)
        resp = client.get("/api/chat/backup")

    assert resp.status_code == 200
    data = resp.json()
    assert "exported_at" in data
    assert len(data["conversations"]) == 1
    assert data["conversations"][0]["title"] == "backup test"
    assert len(data["conversations"][0]["messages"]) == 1


def test_anon_unauthorized_401(monkeypatch):
    """无 override + 无 cookie + 关 RAG_DEV_AUTH → resolve_user 抛 401."""
    from src.chat.router import router as chat_router

    # 关 dev auth 模式 (默认 .env.local 开了), 让真 resolve_user 跑 401 路径
    monkeypatch.setenv("RAG_DEV_AUTH", "")

    app = FastAPI()
    app.include_router(chat_router)
    anon_client = TestClient(app)
    resp = anon_client.get("/api/chat/conversations")
    assert resp.status_code == 401


# ==================== append_message (2026-06-24 chat-message-persistence) ====================


def test_append_message_201_user_role():
    """POST /conversations/{id}/messages role=user → 201, service 收 (uid, cid, role, content, meta)."""
    from src.chat import service as svc
    from src.chat.router import router as chat_router
    from src.middleware.auth import resolve_user

    expected = _msg_dict(id_=1, role="user", content="hello")
    with patch.object(svc, "append_message", return_value=expected) as mock_append:
        app = FastAPI()
        app.include_router(chat_router)
        app.dependency_overrides[resolve_user] = lambda: _make_user(id_=1)

        client = TestClient(app)
        resp = client.post(
            "/api/chat/conversations/c1/messages",
            json={"role": "user", "content": "hello"},
        )

    assert resp.status_code == 201
    body = resp.json()
    assert body["role"] == "user"
    assert body["content"] == "hello"
    # 验证透传: (user_id=1, conv_id='c1', role='user', content='hello', meta=None)
    assert mock_append.call_args.args == (1, "c1", "user", "hello", None)


def test_append_message_with_meta():
    """meta dict 透传到 service."""
    from src.chat import service as svc
    from src.chat.router import router as chat_router
    from src.middleware.auth import resolve_user

    expected = _msg_dict(id_=2, role="assistant", content="ok")
    with patch.object(svc, "append_message", return_value=expected) as mock_append:
        app = FastAPI()
        app.include_router(chat_router)
        app.dependency_overrides[resolve_user] = lambda: _make_user(id_=1)

        client = TestClient(app)
        resp = client.post(
            "/api/chat/conversations/c1/messages",
            json={
                "role": "assistant",
                "content": "ok",
                "meta": {"finish_reason": "stop", "citations": []},
            },
        )

    assert resp.status_code == 201
    # 验证 meta 透传 (Pydantic 不做 schema 校验)
    assert mock_append.call_args.args[4] == {"finish_reason": "stop", "citations": []}


def test_append_message_conv_not_found_404():
    """svc 返 None (conv 不存在/越权/软删) → router 翻 404."""
    from src.chat import service as svc
    from src.chat.router import router as chat_router
    from src.middleware.auth import resolve_user

    with patch.object(svc, "append_message", return_value=None):
        app = FastAPI()
        app.include_router(chat_router)
        app.dependency_overrides[resolve_user] = lambda: _make_user(id_=1)

        client = TestClient(app)
        resp = client.post(
            "/api/chat/conversations/missing/messages",
            json={"role": "user", "content": "x"},
        )

    assert resp.status_code == 404
    assert resp.json()["detail"] == "conversation not found"


def test_append_message_invalid_role_422():
    """role='admin' 非 Literal 之一 → Pydantic 422."""
    from src.chat.router import router as chat_router
    from src.middleware.auth import resolve_user

    app = FastAPI()
    app.include_router(chat_router)
    app.dependency_overrides[resolve_user] = lambda: _make_user(id_=1)

    client = TestClient(app)
    resp = client.post(
        "/api/chat/conversations/c1/messages",
        json={"role": "admin", "content": "x"},
    )
    assert resp.status_code == 422


def test_append_message_empty_content_422():
    """content='' 违反 min_length=1 → 422."""
    from src.chat.router import router as chat_router
    from src.middleware.auth import resolve_user

    app = FastAPI()
    app.include_router(chat_router)
    app.dependency_overrides[resolve_user] = lambda: _make_user(id_=1)

    client = TestClient(app)
    resp = client.post(
        "/api/chat/conversations/c1/messages",
        json={"role": "user", "content": ""},
    )
    assert resp.status_code == 422
