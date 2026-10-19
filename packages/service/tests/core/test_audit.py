"""@audited decorator + AuditContext 测试 (模式 1, mock session_scope)"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi import Request
from sqlalchemy.dialects.postgresql import JSONB

from src.core.audit import AuditContext, _persist_audit, audited


def test_audit_context_set_target_id():
    """AuditContext.set 填 target_id + before/after"""
    ctx = AuditContext(action="test.action", target_type="user")
    ctx.set(target_id="42", before={"a": 1}, after={"a": 2}, reason="test")
    assert ctx.target_id == "42"
    assert ctx.before == {"a": 1}
    assert ctx.after == {"a": 2}
    assert ctx.metadata == {"reason": "test"}


def test_audit_context_default_values():
    """初始化时各字段默认 None / {}"""
    ctx = AuditContext(action="x", target_type="y")
    assert ctx.action == "x"
    assert ctx.target_type == "y"
    assert ctx.target_id is None
    assert ctx.before is None
    assert ctx.after is None
    assert ctx.metadata == {}


@pytest.mark.asyncio
async def test_audited_decorator_success(monkeypatch):
    """@audited 包 endpoint 成功执行 → _persist_audit 调用 result='success'"""
    persist_calls = []
    monkeypatch.setattr("src.core.audit._persist_audit", lambda **kw: persist_calls.append(kw))

    request = MagicMock(spec=Request)
    request.state = MagicMock()
    request.client.host = "1.2.3.4"
    request.headers = {"user-agent": "test-ua"}

    user = MagicMock(id=42, email="a@b.com")

    @audited("account.delete", target_type="user")
    async def fake_endpoint(request, current_user):
        request.state.audit_ctx.set(target_id=str(current_user.id), before={"x": 1})
        return {"ok": True}

    result = await fake_endpoint(request, current_user=user)
    assert result == {"ok": True}
    assert len(persist_calls) == 1
    call = persist_calls[0]
    assert call["result"] == "success"
    assert call["ctx"].action == "account.delete"
    assert call["ctx"].target_id == "42"


@pytest.mark.asyncio
async def test_audited_decorator_failure(monkeypatch):
    """endpoint 抛异常 → _persist_audit 调 result='failure', metadata.error 含 repr"""
    persist_calls = []
    monkeypatch.setattr("src.core.audit._persist_audit", lambda **kw: persist_calls.append(kw))

    request = MagicMock(spec=Request)
    request.state = MagicMock()
    request.client.host = "1.2.3.4"
    request.headers = {"user-agent": "test"}

    @audited("account.delete", target_type="user")
    async def fake_endpoint(request, current_user):
        raise ValueError("boom")

    user = MagicMock(id=42, email="x")

    with pytest.raises(ValueError, match="boom"):
        await fake_endpoint(request, current_user=user)

    assert len(persist_calls) == 1
    call = persist_calls[0]
    assert call["result"] == "failure"
    assert "ValueError" in call["ctx"].metadata.get("error", "")


def test_persist_audit_calls_session_scope_insert(monkeypatch):
    """_persist_audit 调 session_scope().execute INSERT audit_logs"""
    mock_session = MagicMock()
    mock_session.execute = MagicMock()

    class FakeSessionScope:
        def __enter__(self):
            return mock_session

        def __exit__(self, *a):
            return False

    monkeypatch.setattr("src.storage.session_scope", lambda: FakeSessionScope())

    request = MagicMock()
    request.client.host = "1.2.3.4"
    request.headers = {"user-agent": "test"}
    user = MagicMock(id=10, email="x")
    ctx = AuditContext(action="test", target_type="user")
    ctx.set(target_id="10", before={"k": "v"})

    _persist_audit(request=request, user=user, ctx=ctx, result="success")

    assert mock_session.execute.call_count == 1
    sql_call = mock_session.execute.call_args
    params = sql_call[0][1]
    assert params["actor_id"] == 10
    assert params["action"] == "test"
    assert params["target_id"] == "10"
    assert params["result"] == "success"


def test_persist_audit_declares_jsonb_bind_for_dict_columns(monkeypatch):
    """before/after/metadata 列在 SQL 上 bindparam type_=JSONB, 防 psycopg 'cannot adapt dict'.

    根因 (2026-06-22): audit.py:113 之前没绑 JSONB, psycopg/asyncpg 不会自动 dict → JSONB,
    抛 ProgrammingError "cannot adapt type 'dict' using placeholder '%s' (format: AUTO)".
    """
    mock_session = MagicMock()
    mock_session.execute = MagicMock()

    class FakeSessionScope:
        def __enter__(self):
            return mock_session

        def __exit__(self, *a):
            return False

    monkeypatch.setattr("src.storage.session_scope", lambda: FakeSessionScope())

    request = MagicMock()
    request.client.host = "1.2.3.4"
    request.headers = {"user-agent": "test"}
    user = MagicMock(id=10, email="x")
    ctx = AuditContext(action="test", target_type="user")
    ctx.set(target_id="10", before={"k": "v"}, after={"k": "v2"}, reason="x")

    _persist_audit(request=request, user=user, ctx=ctx, result="success")

    assert mock_session.execute.call_count == 1
    # 取出传给 execute 的 SQLAlchemy text object, 验 bind types
    stmt = mock_session.execute.call_args[0][0]
    bind_names = {key: bp.type for key, bp in stmt._bindparams.items()}
    # JSONB 每次实例化新对象, isinstance 验
    assert isinstance(bind_names.get("before"), JSONB)
    assert isinstance(bind_names.get("after"), JSONB)
    assert isinstance(bind_names.get("metadata"), JSONB)


def test_persist_audit_swallows_exceptions(monkeypatch):
    """_persist_audit 写 DB 失败 → logger.critical, 不抛"""

    def boom_session_scope():
        raise RuntimeError("DB down")

    monkeypatch.setattr("src.storage.session_scope", boom_session_scope)

    request = MagicMock()
    request.client.host = "1.2.3.4"
    request.headers = {"user-agent": "test"}
    user = MagicMock(id=1, email="x")
    ctx = AuditContext(action="t", target_type="u")
    ctx.set(target_id="1")

    # 不应抛
    _persist_audit(request=request, user=user, ctx=ctx, result="success")


def test_persist_audit_without_request(monkeypatch):
    """_persist_audit request=None 时 ip/ua 安全 fallback"""
    mock_session = MagicMock()
    mock_session.execute = MagicMock()

    class FakeSessionScope:
        def __enter__(self):
            return mock_session

        def __exit__(self, *a):
            return False

    monkeypatch.setattr("src.storage.session_scope", lambda: FakeSessionScope())

    ctx = AuditContext(action="test", target_type="user")
    ctx.set(target_id="10")

    # request=None → ip 应为 None, ua 应为 ""
    _persist_audit(request=None, user=MagicMock(id=5, email="x"), ctx=ctx, result="success")
    assert mock_session.execute.call_count == 1
    params = mock_session.execute.call_args[0][1]
    assert params["ip"] is None
    assert params["ua"] == ""


@pytest.mark.asyncio
async def test_audited_decorator_request_in_args(monkeypatch):
    """@audited 从 *args 扫描到 request 对象"""
    persist_calls = []
    monkeypatch.setattr("src.core.audit._persist_audit", lambda **kw: persist_calls.append(kw))

    request = MagicMock(spec=Request)
    request.state = MagicMock()
    request.client.host = "1.2.3.4"
    request.headers = {"user-agent": "test-ua"}
    user = MagicMock(id=7, email="u@v.com")

    @audited("test.positional", target_type="user")
    async def fake_endpoint(request, current_user):
        request.state.audit_ctx.set(target_id="7")
        return {"ok": True}

    # 通过 args 而非 kwargs 传 request
    result = await fake_endpoint(request, current_user=user)
    assert result == {"ok": True}
    assert len(persist_calls) == 1
    assert persist_calls[0]["result"] == "success"


@pytest.mark.asyncio
async def test_audited_decorator_no_request(monkeypatch):
    """@audited 无 request 参数时也能安全执行 (ctx 不挂在 state 上)"""
    persist_calls = []
    monkeypatch.setattr("src.core.audit._persist_audit", lambda **kw: persist_calls.append(kw))

    @audited("test.no_request", target_type="user")
    async def fake_endpoint(current_user):
        return {"ok": True}

    user = MagicMock(id=3, email="a@b.com")
    result = await fake_endpoint(current_user=user)
    assert result == {"ok": True}
    assert len(persist_calls) == 1
    # request=None → _persist_audit 内部走 ip=None, ua=""
    assert persist_calls[0]["request"] is None


@pytest.mark.asyncio
async def test_audited_decorator_sync_handler(monkeypatch):
    """@audited 包同步 def handler 时不应 await (否则 TypeError: dict can't be awaited).

    根因: 2026-07-03 真实事故 /api/kg/extract/start → 'dict' object can't be awaited.
    修复: wrapper 走 inspect.isawaitable 区分 sync / async, sync 直接 return func(...).
    回归保护: kg/router.py 的 start_extract / patch_extract_items / commit_extract
    都是同步 def 返回 dict, 必须走这条路径, 不能 await.
    """
    persist_calls = []
    monkeypatch.setattr("src.core.audit._persist_audit", lambda **kw: persist_calls.append(kw))

    request = MagicMock(spec=Request)
    request.state = MagicMock()
    request.client.host = "1.2.3.4"
    request.headers = {"user-agent": "test-ua"}
    user = MagicMock(id=42, email="a@b.com")

    @audited("kg.extract.start", target_type="kg_extract_task")
    def fake_sync_endpoint(request, current_user):
        request.state.audit_ctx.set(target_id="t-1", dataset="motor")
        return {"task_id": "t-1", "state": "queued"}

    # 关键断言: 同步 def 包 @audited 后, await wrapper() 不能炸, 返回值原样
    # pyright 把 fake_sync_endpoint 返值推成 dict[str, str] (非 awaitable), 实际 wrapper 返 Any,
    # 用 Any cast 避免对每个测试加 type: ignore
    result = await fake_sync_endpoint(request, current_user=user)  # type: ignore[reportGeneralTypeIssues]
    assert result == {"task_id": "t-1", "state": "queued"}
    assert len(persist_calls) == 1
    assert persist_calls[0]["result"] == "success"
    assert persist_calls[0]["ctx"].target_id == "t-1"


@pytest.mark.asyncio
async def test_audited_decorator_sync_handler_exception(monkeypatch):
    """@audited 同步 def 抛异常时 → result='failure' 仍要写 audit, 异常仍要冒泡"""
    persist_calls = []
    monkeypatch.setattr("src.core.audit._persist_audit", lambda **kw: persist_calls.append(kw))

    request = MagicMock(spec=Request)
    request.state = MagicMock()
    request.client.host = "1.2.3.4"
    request.headers = {"user-agent": "test"}
    user = MagicMock(id=1, email="x")

    @audited("kg.extract.fail", target_type="kg_extract_task")
    def fake_sync_endpoint(request, current_user):
        raise ValueError("sync boom")

    with pytest.raises(ValueError, match="sync boom"):
        await fake_sync_endpoint(request, current_user=user)  # type: ignore[reportGeneralTypeIssues]

    assert len(persist_calls) == 1
    assert persist_calls[0]["result"] == "failure"
    assert "ValueError" in persist_calls[0]["ctx"].metadata.get("error", "")
