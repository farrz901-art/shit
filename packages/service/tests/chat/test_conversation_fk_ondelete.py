"""DATA-003 修复测试: conversations.user_id FK ondelete=CASCADE.

(2026-06-29) 删 2 个真 PG 测试 (test_delete_user_cascades_*), 跟 CLAUDE.md §强制测试隔离
"所有 test 禁直连 PG" 一致 — PG FK ondelete=CASCADE 行为是 DB 层面, 跟 ORM 解耦.
保留 test_orm_declares_ondelete_cascade 验 ORM 声明 (inspect metadata, 不连 DB).

PG FK 行为回归在 CI 模式 2 (tests/integration/...) 走真 PG 集成测.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


def test_orm_declares_ondelete_cascade():
    """ORM Conversation.user_id ForeignKey 必须声明 ondelete=CASCADE.

    验证 ORM 跟 DB schema 一致 (否则 ORM 加载行时会触发 lazy load
    试图找回 user, 跟实际 CASCADE 行为冲突).
    """
    from sqlalchemy import inspect

    from src.chat.models import Conversation

    mapper = inspect(Conversation)
    user_id_col = mapper.columns["user_id"]
    fks = list(user_id_col.foreign_keys)
    assert len(fks) == 1, f"期望 1 个 FK, 实际 {len(fks)}"
    fk = fks[0]
    assert fk.ondelete == "CASCADE", (
        f"Conversation.user_id FK ondelete 应为 CASCADE, 实际 {fk.ondelete!r}. "
        "DATA-003 修复要求改 ORM ForeignKey(..., ondelete='CASCADE')."
    )
