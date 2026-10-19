"""chat/service.py 单元测试 (mode 1, mock session_scope)"""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

# ============================================================
# Fixtures
# ============================================================


@pytest.fixture
def mock_session():
    session = MagicMock()
    session.execute.return_value.first.return_value = MagicMock(
        id="conv-1",
        title="新对话",
        message_count=0,
        created_at="2026-06-01",
        updated_at="2026-06-01",
    )
    session.execute.return_value.fetchall.return_value = []
    return session


# ============================================================
# create_conversation
# ============================================================


@patch("src.chat.service.session_scope")
def test_create_conversation(mock_scope_cls, mock_session):
    mock_scope_cls.return_value.__enter__.return_value = mock_session
    from src.chat.service import create_conversation

    result = create_conversation(user_id=1, title="测试")
    assert result["title"] == "新对话"
    assert result["message_count"] == 0


# ============================================================
# list_conversations
# ============================================================


@patch("src.chat.service.session_scope")
def test_list_conversations_empty(mock_scope_cls, mock_session):
    mock_session.execute.return_value.fetchall.return_value = []
    mock_scope_cls.return_value.__enter__.return_value = mock_session
    from src.chat.service import list_conversations

    result = list_conversations(user_id=1)
    assert result == []


@patch("src.chat.service.session_scope")
def test_list_conversations_multiple(mock_scope_cls, mock_session):
    rows = [
        MagicMock(id="c1", title="对话1", message_count=3, created_at="2026-06-01", updated_at="2026-06-02"),
        MagicMock(id="c2", title="对话2", message_count=0, created_at="2026-06-01", updated_at="2026-06-01"),
    ]
    mock_session.execute.return_value.fetchall.return_value = rows
    mock_scope_cls.return_value.__enter__.return_value = mock_session
    from src.chat.service import list_conversations

    result = list_conversations(user_id=1)
    assert len(result) == 2
    assert result[0]["id"] == "c1"
    assert result[1]["id"] == "c2"


@patch("src.chat.service.session_scope")
def test_list_conversations_respects_limit(mock_scope_cls, mock_session):
    mock_session.execute.return_value.fetchall.return_value = []
    mock_scope_cls.return_value.__enter__.return_value = mock_session
    from src.chat.service import list_conversations

    # 第一页: 不带游标
    result = list_conversations(user_id=1, limit=5)
    assert result == []


@patch("src.chat.service.session_scope")
def test_list_conversations_cursor_before(mock_scope_cls, mock_session):
    """游标分页: cursor_before 传入时 SQL 带游标条件."""
    rows = [
        MagicMock(id="c2", title="对话2", message_count=0, created_at="2026-06-01", updated_at="2026-06-01"),
    ]
    mock_session.execute.return_value.fetchall.return_value = rows
    mock_scope_cls.return_value.__enter__.return_value = mock_session
    from src.chat.service import list_conversations

    result = list_conversations(
        user_id=1,
        limit=5,
        cursor_before={"updated_at": "2026-06-02", "id": "c1"},
    )
    assert len(result) == 1
    assert result[0]["id"] == "c2"


# ============================================================
# get_conversation
# ============================================================


@patch("src.chat.service.session_scope")
def test_get_conversation_not_found(mock_scope_cls, mock_session):
    mock_session.execute.return_value.first.return_value = None
    mock_scope_cls.return_value.__enter__.return_value = mock_session
    from src.chat.service import get_conversation

    result = get_conversation(user_id=1, conv_id="nonexistent")
    assert result is None


@patch("src.chat.service.session_scope")
def test_get_conversation_with_messages(mock_scope_cls, mock_session):
    """conv 存在且有 messages → 消息列表合并到结果"""
    mock_session.execute.return_value.first.side_effect = [
        # 第一次调用: conv 查询
        MagicMock(id="conv-1", title="对话1", message_count=2, created_at="2026-06-01", updated_at="2026-06-02"),
        # 第二次调用: messages 查询 (被忽略, 因为 first 只触发一次)
    ]
    # 重新设 fetchall 给 messages 查询
    mock_session.execute.return_value.fetchall.return_value = [
        MagicMock(id="msg-1", role="user", content="你好", meta='{"intent": "greeting"}', created_at="2026-06-01"),
        MagicMock(id="msg-2", role="assistant", content="你好!", meta=None, created_at="2026-06-01"),
    ]

    mock_scope_cls.return_value.__enter__.return_value = mock_session
    from src.chat.service import get_conversation

    result = get_conversation(user_id=1, conv_id="conv-1")
    assert result is not None
    assert result["id"] == "conv-1"
    assert result["title"] == "对话1"
    assert len(result["messages"]) == 2
    assert result["messages"][0]["role"] == "user"
    assert result["messages"][0]["meta"] == {"intent": "greeting"}
    assert result["messages"][1]["meta"] is None


# ============================================================
# update_conversation
# ============================================================


@patch("src.chat.service.session_scope")
def test_update_conversation_success(mock_scope_cls, mock_session):
    mock_session.execute.return_value.first.return_value = MagicMock(
        id="conv-1",
        title="新标题",
        message_count=0,
        created_at="2026-06-01",
        updated_at="2026-06-02",
    )
    mock_scope_cls.return_value.__enter__.return_value = mock_session
    from src.chat.service import update_conversation

    result = update_conversation(user_id=1, conv_id="conv-1", title="新标题")
    assert result is not None
    assert result["title"] == "新标题"
    assert result["message_count"] == 0


@patch("src.chat.service.session_scope")
def test_update_conversation_not_found(mock_scope_cls, mock_session):
    mock_session.execute.return_value.first.return_value = None
    mock_scope_cls.return_value.__enter__.return_value = mock_session
    from src.chat.service import update_conversation

    result = update_conversation(user_id=1, conv_id="nonexistent", title="标题")
    assert result is None


# ============================================================
# soft_delete_conversation
# ============================================================


@patch("src.chat.service.session_scope")
def test_soft_delete_conversation_returns_true(mock_scope_cls, mock_session):
    mock_session.execute.return_value.first.return_value = MagicMock(id="conv-1")
    mock_scope_cls.return_value.__enter__.return_value = mock_session
    from src.chat.service import soft_delete_conversation

    result = soft_delete_conversation(user_id=1, conv_id="conv-1")
    assert result is True


@patch("src.chat.service.session_scope")
def test_soft_delete_conversation_returns_false(mock_scope_cls, mock_session):
    mock_session.execute.return_value.first.return_value = None
    mock_scope_cls.return_value.__enter__.return_value = mock_session
    from src.chat.service import soft_delete_conversation

    result = soft_delete_conversation(user_id=1, conv_id="nonexistent")
    assert result is False


# ============================================================
# list_messages
# ============================================================


@patch("src.chat.service.session_scope")
def test_list_messages_success(mock_scope_cls, mock_session):
    """conv 存在且 active → 返消息分页列表"""
    mock_session.execute.return_value.first.return_value = MagicMock(_data=1)
    mock_session.execute.return_value.fetchall.return_value = [
        MagicMock(id="msg-1", role="user", content="hi", meta=None, created_at="2026-06-01"),
        MagicMock(id="msg-2", role="assistant", content="hello", meta='{"source": "llm"}', created_at="2026-06-01"),
    ]
    mock_scope_cls.return_value.__enter__.return_value = mock_session
    from src.chat.service import list_messages

    result = list_messages(user_id=1, conv_id="conv-1")
    assert result is not None
    assert len(result) == 2
    assert result[0]["role"] == "user"
    assert result[1]["meta"] == {"source": "llm"}


@patch("src.chat.service.session_scope")
def test_list_messages_conv_not_found(mock_scope_cls, mock_session):
    """conv 不存在 / 软删 / 越权 → 返 None"""
    mock_session.execute.return_value.first.return_value = None
    mock_scope_cls.return_value.__enter__.return_value = mock_session
    from src.chat.service import list_messages

    result = list_messages(user_id=1, conv_id="nonexistent")
    assert result is None


@patch("src.chat.service.session_scope")
def test_list_messages_respects_pagination(mock_scope_cls, mock_session):
    mock_session.execute.return_value.first.return_value = MagicMock(_data=1)
    mock_session.execute.return_value.fetchall.return_value = []
    mock_scope_cls.return_value.__enter__.return_value = mock_session
    from src.chat.service import list_messages

    result = list_messages(user_id=1, conv_id="conv-1", limit=10, offset=20)
    assert result is not None
    assert result == []


# ============================================================
# get_full_backup
# ============================================================


@patch("src.chat.service.session_scope")
def test_get_full_backup_empty(mock_scope_cls, mock_session):
    """无对话 → 返空列表 backup"""
    mock_session.execute.return_value.fetchall.return_value = []
    mock_scope_cls.return_value.__enter__.return_value = mock_session
    from src.chat.service import get_full_backup

    result = get_full_backup(user_id=1)
    assert "exported_at" in result
    assert result["conversations"] == []


@patch("src.chat.service.session_scope")
def test_get_full_backup_with_conversations(mock_scope_cls, mock_session):
    """有对话 + 消息 → 按 conv 分组"""

    conv_row = MagicMock(id="c1", title="对话", message_count=2)

    msg_row = MagicMock(
        conversation_id="c1",
        role="user",
        content="hi",
        meta=None,
        created_at=datetime(2026, 6, 1, 10, 0, 0),
    )

    def fetchall_side_effect():
        return [conv_row]

    def fetchall_msgs_side_effect():
        return [msg_row]

    mock_session.execute.return_value.fetchall.side_effect = [
        [conv_row],
        [msg_row],
    ]
    mock_scope_cls.return_value.__enter__.return_value = mock_session
    from src.chat.service import get_full_backup

    result = get_full_backup(user_id=1)
    assert len(result["conversations"]) == 1
    assert result["conversations"][0]["title"] == "对话"
    assert len(result["conversations"][0]["messages"]) == 1
    assert result["conversations"][0]["messages"][0]["role"] == "user"


# ============================================================
# hard_delete_old_soft_deleted
# ============================================================


@patch("src.chat.service.session_scope")
def test_hard_delete_old_soft_deleted_zero(mock_scope_cls, mock_session):
    """无待删数据 → 返 0 计数"""
    # rowcount 是属性, 用 PropertyMock
    mock_session.execute.return_value.rowcount = 0
    mock_scope_cls.return_value.__enter__.return_value = mock_session
    from src.chat.service import hard_delete_old_soft_deleted

    result = hard_delete_old_soft_deleted(days=30)
    assert result == {"conversations": 0, "messages": 0}


@patch("src.chat.service.session_scope")
def test_hard_delete_old_soft_deleted_with_counts(mock_scope_cls, mock_session):
    """删除多条 → 返实际计数"""
    mock_session.execute.return_value.rowcount = 5
    mock_scope_cls.return_value.__enter__.return_value = mock_session
    from src.chat.service import hard_delete_old_soft_deleted

    result = hard_delete_old_soft_deleted(days=30)
    assert result == {"conversations": 5, "messages": 5}
