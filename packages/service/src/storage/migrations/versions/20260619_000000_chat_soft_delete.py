"""chat soft delete: conversations/messages 加 deleted_at 列 + partial index

(2026-06-19 chat spec §3) 软删 30d + cron hard-delete (GDPR).

设计:
- 加 conversations.deleted_at + messages.deleted_at (TIMESTAMPTZ NULL)
- 新增 2 个 partial index (WHERE deleted_at IS NULL), 跟原有全表索引共存:
  - idx_conversations_user_updated_partial: (user_id, updated_at DESC) WHERE deleted_at IS NULL
  - idx_messages_conv_created_partial:    (conversation_id, created_at) WHERE deleted_at IS NULL
  (partial index 比全表索引更小更快, 软删行不进索引)
- 原 ix_conversations_user_updated / ix_messages_conv_created 不动, 给旧查询路径兜底.
- down_revision = "20260617_120000" (account_settings, 当前 head)
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260619_000000"
# 当前 head 是 20260617000000 (create_log_tables), 而不是按时间序更晚的 20260617_120000
# (account_settings) — 那是 create_log_tables 的 base. 链在 head 上避免多 head.
down_revision = "20260617_120000"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # conversations: 加 deleted_at + partial index
    op.add_column(
        "conversations",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "idx_conversations_user_updated_partial",
        "conversations",
        ["user_id", sa.text("updated_at DESC")],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    # messages: 加 deleted_at + partial index
    op.add_column(
        "messages",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "idx_messages_conv_created_partial",
        "messages",
        ["conversation_id", "created_at"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )


def downgrade() -> None:
    # 反向操作: drop index → drop column
    op.drop_index("idx_messages_conv_created_partial", table_name="messages")
    op.drop_column("messages", "deleted_at")

    op.drop_index("idx_conversations_user_updated_partial", table_name="conversations")
    op.drop_column("conversations", "deleted_at")
