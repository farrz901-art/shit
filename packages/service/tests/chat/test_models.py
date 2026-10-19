"""Conversation + Message model 测试

(2026-07-01 fix) 原 4 个 test 走真 PG 直 commit → dev DB 累积 78 行污染 user + 54 个污染
conversation. 改走模式 1 (mock), 不连 PG, 不污染 dev DB.

FK / CASCADE 这类 SQL 行为测试留给后续 tmp_pg_schema spec (见 packages/service/CLAUDE.md
§测试隔离 4 模式). 本文件只验 ORM 模型字段 / 关系 / `__repr__`, 不依赖 SQL 行为.
"""

from __future__ import annotations

import pytest


def test_conversation_orm_fields():
    """Conversation 表字段定义正确 (类型 / nullable / FK)."""
    from src.chat.models import Conversation

    # 主键 + 标题 + user_id FK + message_count 默认
    assert Conversation.__tablename__ == "conversations"
    assert Conversation.id.type.__class__.__name__ == "String"
    assert Conversation.user_id.nullable is False
    assert Conversation.title.nullable is False
    assert Conversation.message_count.default.arg == 0


def test_conversation_repr():
    """Conversation.__repr__ 包含 id + title."""
    from src.chat.models import Conversation

    c = Conversation(id="abc-123", user_id=1, title="测试会话")
    r = repr(c)
    assert "abc-123" in r
    assert "测试会话" in r


def test_message_orm_fields():
    """Message 表字段定义正确."""
    from src.chat.models import Message

    assert Message.__tablename__ == "messages"
    assert Message.role.nullable is False
    assert Message.content.nullable is False
    # meta 是 JSONB 列, 列类型走 PG dialect
    assert Message.meta.type.__class__.__name__ == "JSONB"


def test_message_repr():
    """Message.__repr__ 包含 conversation_id + role."""
    from src.chat.models import Message

    m = Message(conversation_id="conv-1", role="user", content="hi")
    r = repr(m)
    assert "conv-1" in r
    assert "user" in r


# ---------------------------------------------------------------------------
# 留给后续 tmp_pg_schema spec 的 SQL 行为测试 (FK 约束 / CASCADE 删除)
# 跟 CLAUDE.md §测试隔离 4 模式 → 模式 2 (事务回滚) 一致, 本期不实现
# ---------------------------------------------------------------------------
@pytest.mark.skip(reason="FK / CASCADE 是 SQL 行为, 留给后续 tmp_pg_schema spec (模式 2 集成测)")
def test_conversation_user_id_fk_required():
    """Conversation.user_id 必须有 (FK). 真 PG 才验得了."""


@pytest.mark.skip(reason="FK / CASCADE 是 SQL 行为, 留给后续 tmp_pg_schema spec (模式 2 集成测)")
def test_message_create_and_cascade_delete():
    """Message 基础创建 + Conversation 删时 CASCADE. 真 PG + 事务回滚才验得了."""


@pytest.mark.skip(reason="FK / CASCADE 是 SQL 行为, 留给后续 tmp_pg_schema spec (模式 2 集成测)")
def test_message_role_required():
    """Message.role NOT NULL. 真 PG 才验得了."""
