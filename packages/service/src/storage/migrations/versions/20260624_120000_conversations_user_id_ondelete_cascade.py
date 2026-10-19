"""conversations.user_id FK 加 ondelete=CASCADE

(DATA-003 修复) 原来 FK 用 PG 默认 NO ACTION, 删 user 后 conversations
变孤儿行, 跟 GDPR right to erasure 冲突.

业务决策:
- 选 CASCADE (不是 SET NULL): 跟 chat 软删 cron hard_delete 一致, 真删
  user 时其聊天记录一并清除. 跟 account_settings_service.purge_pending_deletions
  匿名化 User (保留 id) 不冲突 — 该路径不解绑 user.id, conversations 不动.
- messages.conversation_id 已经有 ondelete=CASCADE (consolidated_pg_init
  line 130), 删 conversations 自动级联删 messages. 现在 conversations→user
  也 CASCADE, 形成完整链.

范围:
- 仅改 conversations.user_id FK. messages / ingest_tasks / approvals / evaluations
  跟 user 的 FK 留后续 spec 处理 (Master plan Task 1.7 范围限定).
"""

from __future__ import annotations

from alembic import op

revision = "20260624_120000"
down_revision = "20260624_000000"  # 上一个 head: deletion_restores UNIQUE
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. 删旧 FK (PG 默认名: conversations_user_id_fkey)
    op.drop_constraint(
        "conversations_user_id_fkey",
        "conversations",
        type_="foreignkey",
    )

    # 2. 加新 FK, 显式命名保持一致, 带 ondelete=CASCADE
    op.create_foreign_key(
        "conversations_user_id_fkey",
        "conversations",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    # 1. 删 CASCADE 版 FK
    op.drop_constraint(
        "conversations_user_id_fkey",
        "conversations",
        type_="foreignkey",
    )

    # 2. 恢复原 FK (无 ondelete, PG 默认 NO ACTION)
    op.create_foreign_key(
        "conversations_user_id_fkey",
        "conversations",
        "users",
        ["user_id"],
        ["id"],
    )
