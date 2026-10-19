"""ConversationService 单元测试 (2026-06-19 chat spec, 模式 1 mock)

CLAUDE.md 规范: 测试禁止连真 PG / Redis 等数据库. 此处 mock
src.chat.service.session_scope 返 MagicMock session, 模拟 SQL 执行
(service 内的 SQL 用 text() + session.execute(), mock session 的
execute 返预设结果即可).

6 测试: CRUD + 软删 + get after soft delete + 30d hard_delete 边界.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch


def _mock_session_scope(session: MagicMock):
    """构造 context manager: yield mock session 后 commit (no-op on MagicMock)."""

    @contextmanager
    def _cm():
        yield session

    return _cm()


def _conv_row(
    id_: str = "c1",
    title: str = "t1",
    message_count: int = 0,
    created_at: datetime | None = None,
    updated_at: datetime | None = None,
) -> MagicMock:
    """构造模拟 conv row (有 .id / .title / .message_count / .created_at / .updated_at)."""
    if created_at is None:
        created_at = datetime(2026, 6, 19, tzinfo=UTC)
    if updated_at is None:
        updated_at = datetime(2026, 6, 19, tzinfo=UTC)
    row = MagicMock()
    row.id = id_
    row.title = title
    row.message_count = message_count
    row.created_at = created_at
    row.updated_at = updated_at
    return row


# ---- CRUD 基础 ----


def test_create_and_list():
    """create_conversation + list_conversations 往返一致 (mock execute 返预设行)."""
    from src.chat import service as svc

    mock_session = MagicMock()
    # create: execute().first() 返 conv row
    # list: execute().fetchall() 返 [conv row]
    create_result = MagicMock()
    create_result.first.return_value = _conv_row(id_="c1", title="t1")
    list_result = MagicMock()
    list_result.fetchall.return_value = [_conv_row(id_="c1", title="t1")]

    # 顺序: create → list
    mock_session.execute.side_effect = [create_result, list_result]

    with patch("src.chat.service.session_scope", lambda: _mock_session_scope(mock_session)):
        c = svc.create_conversation(user_id=1, title="t1")
        assert c["id"] == "c1"
        assert c["title"] == "t1"
        assert c["message_count"] == 0

        convs = svc.list_conversations(user_id=1)
        assert len(convs) == 1
        assert convs[0]["id"] == "c1"

    # 验证 SQL 确实走了 (2 次 execute: INSERT + SELECT)
    assert mock_session.execute.call_count == 2


# ---- 软删 ----


def test_soft_delete_hides_in_list():
    """软删后 list_conversations 返空 (排除软删行) — mock execute 模拟."""
    from src.chat import service as svc

    mock_session = MagicMock()
    # 1) create → first() 返新 row
    # 2) soft_delete → first() 返 row (成功)
    # 3) list → fetchall() 返 [] (软删后)
    create_result = MagicMock()
    create_result.first.return_value = _conv_row(id_="c1", title="t1")
    delete_result = MagicMock()
    delete_result.first.return_value = _conv_row(id_="c1", title="t1")
    list_result = MagicMock()
    list_result.fetchall.return_value = []

    mock_session.execute.side_effect = [create_result, delete_result, list_result]

    with patch("src.chat.service.session_scope", lambda: _mock_session_scope(mock_session)):
        c = svc.create_conversation(user_id=1, title="t1")
        assert svc.soft_delete_conversation(1, c["id"]) is True
        assert svc.list_conversations(1) == []


def test_soft_delete_nonexistent_returns_false():
    """软删不存在的 conv → False (mock execute.first() 返 None)."""
    from src.chat import service as svc

    mock_session = MagicMock()
    delete_result = MagicMock()
    delete_result.first.return_value = None
    mock_session.execute.return_value = delete_result

    with patch("src.chat.service.session_scope", lambda: _mock_session_scope(mock_session)):
        result = svc.soft_delete_conversation(1, "00000000-0000-0000-0000-000000000000")
        assert result is False


def test_get_conversation_after_soft_delete_returns_none():
    """get_conversation 软删后返 None (router 翻译 404) — mock conv 查不到."""
    from src.chat import service as svc

    mock_session = MagicMock()
    # service get_conversation: 2 次 execute — conv 查不到返 None
    conv_result = MagicMock()
    conv_result.first.return_value = None
    mock_session.execute.return_value = conv_result

    with patch("src.chat.service.session_scope", lambda: _mock_session_scope(mock_session)):
        result = svc.get_conversation(1, "00000000-0000-0000-0000-000000000000")
        assert result is None


def test_update_nonexistent_returns_none():
    """update_conversation 不存在 → None — mock execute.first() 返 None."""
    from src.chat import service as svc

    mock_session = MagicMock()
    update_result = MagicMock()
    update_result.first.return_value = None
    mock_session.execute.return_value = update_result

    with patch("src.chat.service.session_scope", lambda: _mock_session_scope(mock_session)):
        result = svc.update_conversation(1, "00000000-0000-0000-0000-000000000000", "new")
        assert result is None


# ---- 30d hard_delete (cron 真删验证) ----


def test_hard_delete_old_soft_deleted_removes_30d_old():
    """30d 前软删的 conv 应被 hard_delete 删掉 — mock rowcount 返预设值.

    验证两点:
    1. service.hard_delete_old_soft_deleted 返 dict {conversations, messages}
    2. SQL 用了 cutoff 参数 (NOW() - 30d)
    """
    from src.chat import service as svc

    mock_session = MagicMock()
    # 2 次 execute: DELETE messages (rowcount=5) + DELETE conversations (rowcount=1)
    msg_delete = MagicMock()
    msg_delete.rowcount = 5
    conv_delete = MagicMock()
    conv_delete.rowcount = 1
    mock_session.execute.side_effect = [msg_delete, conv_delete]

    with patch("src.chat.service.session_scope", lambda: _mock_session_scope(mock_session)):
        result = svc.hard_delete_old_soft_deleted(days=30)
        assert result == {"conversations": 1, "messages": 5}

    # 验证: cutoff 用了 (NOW() - 30d), 2 次 execute 都有 cutoff 参数
    assert mock_session.execute.call_count == 2
    # SQLAlchemy execute(text, params) — params 是 positional arg
    first_params = mock_session.execute.call_args_list[0].args[1]
    second_params = mock_session.execute.call_args_list[1].args[1]
    # cutoff 应是 ~30d 前的 datetime
    now = datetime.now(UTC)
    assert "cutoff" in first_params
    assert "cutoff" in second_params
    cutoff = first_params["cutoff"]
    expected = now - timedelta(days=30)
    # 允许 1 秒误差 (测试运行时差)
    assert abs((cutoff - expected).total_seconds()) < 2


# ---- append_message (2026-06-24 chat-message-persistence) ----


def _msg_row(
    id_: int = 1,
    role: str = "user",
    content: str = "hi",
    meta_str: str | None = None,
) -> MagicMock:
    """构造模拟 message row (有 .id / .role / .content / .meta / .created_at)."""
    row = MagicMock()
    row.id = id_
    row.role = role
    row.content = content
    row.meta = meta_str
    row.created_at = datetime(2026, 6, 24, tzinfo=UTC)
    return row


def test_append_message_user_increments_count():
    """role='user' → INSERT message + UPDATE conv.message_count += 1."""
    from src.chat import service as svc

    mock_session = MagicMock()
    # 1. SELECT conv: 返存在
    select_result = MagicMock()
    select_result.first.return_value = _conv_row(id_="c1", title="t1", message_count=0)
    # 2. INSERT messages: 返 inserted row
    insert_result = MagicMock()
    insert_result.first.return_value = _msg_row(id_=1, role="user", content="hello")
    # 3. UPDATE conversations: rowcount (不读, 但 execute 返 MagicMock 即可)
    update_result = MagicMock()
    mock_session.execute.side_effect = [select_result, insert_result, update_result]

    with patch("src.chat.service.session_scope", return_value=_mock_session_scope(mock_session)):
        result = svc.append_message(user_id=1, conv_id="c1", role="user", content="hello")

    assert result is not None
    assert result["role"] == "user"
    assert result["content"] == "hello"
    # 3 次 execute: SELECT + INSERT + UPDATE
    assert mock_session.execute.call_count == 3
    # 第 3 次 (UPDATE) 的 SQL 含 message_count = message_count + 1
    third_call_sql = str(mock_session.execute.call_args_list[2].args[0])
    assert "message_count" in third_call_sql.lower()


def test_append_message_assistant_no_count_change():
    """role='assistant' → INSERT + UPDATE conv.updated_at, 不增 count."""
    from src.chat import service as svc

    mock_session = MagicMock()
    select_result = MagicMock()
    select_result.first.return_value = _conv_row(id_="c1", message_count=5)
    insert_result = MagicMock()
    insert_result.first.return_value = _msg_row(id_=2, role="assistant", content="answer")
    update_result = MagicMock()
    mock_session.execute.side_effect = [select_result, insert_result, update_result]

    with patch("src.chat.service.session_scope", return_value=_mock_session_scope(mock_session)):
        result = svc.append_message(user_id=1, conv_id="c1", role="assistant", content="answer")

    assert result is not None
    assert result["role"] == "assistant"
    third_call_sql = str(mock_session.execute.call_args_list[2].args[0])
    # UPDATE 只 set updated_at, 不含 message_count
    assert "message_count" not in third_call_sql.lower()
    assert "updated_at" in third_call_sql.lower()


def test_append_message_conv_not_found_returns_none():
    """conv 不存在 / 越权 / 已软删 → SELECT 返 None → 整个函数返 None, 0 INSERT."""
    from src.chat import service as svc

    mock_session = MagicMock()
    select_result = MagicMock()
    select_result.first.return_value = None  # conv 不存在
    mock_session.execute.side_effect = [select_result]

    with patch("src.chat.service.session_scope", return_value=_mock_session_scope(mock_session)):
        result = svc.append_message(user_id=1, conv_id="missing", role="user", content="x")

    assert result is None
    # 只跑 SELECT, 没 INSERT / UPDATE
    assert mock_session.execute.call_count == 1


def test_append_message_meta_serialized_as_json():
    """meta=dict → INSERT 时序列化为 JSON 字符串."""
    from src.chat import service as svc

    mock_session = MagicMock()
    select_result = MagicMock()
    select_result.first.return_value = _conv_row(id_="c1")
    insert_result = MagicMock()
    insert_result.first.return_value = _msg_row(meta_str='{"finish_reason": "stop"}')
    update_result = MagicMock()
    mock_session.execute.side_effect = [select_result, insert_result, update_result]

    with patch("src.chat.service.session_scope", return_value=_mock_session_scope(mock_session)):
        result = svc.append_message(
            user_id=1, conv_id="c1", role="assistant", content="x", meta={"finish_reason": "stop"}
        )

    assert result is not None
    # INSERT 调用的第 2 个参数 (params dict) 含 meta key, value 是 JSON 字符串
    insert_params = mock_session.execute.call_args_list[1].args[1]
    assert "meta" in insert_params
    assert insert_params["meta"] == '{"finish_reason": "stop"}'
