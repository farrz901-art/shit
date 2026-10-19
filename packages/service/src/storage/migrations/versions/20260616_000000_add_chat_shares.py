"""add chat_shares (2026-06-16)

存储 chat 对话分享快照, anon 公开读, 所有者撤销.
接在 20260615_000000 consolidated_pg_init 之后.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260616_000000"
down_revision: str | None = "20260615_000000"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    """新增 chat_shares 表 (1 张): 短 ID 主键 + conv/user 索引 + JSON 消息快照."""
    op.create_table(
        "chat_shares",
        sa.Column("share_id", sa.String(length=12), nullable=False),  # nanoid 12 字符
        sa.Column("conv_id", sa.String(length=128), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),  # 所有者
        sa.Column("title", sa.String(length=200), nullable=True),
        sa.Column("messages_json", sa.Text(), nullable=False),  # 快照 JSON
        sa.Column("model", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("share_id"),
    )
    op.create_index(op.f("ix_chat_shares_conv_id"), "chat_shares", ["conv_id"], unique=False)
    op.create_index(op.f("ix_chat_shares_user_id"), "chat_shares", ["user_id"], unique=False)
    op.create_index(
        op.f("ix_chat_shares_conv_id_user_id"),
        "chat_shares",
        ["conv_id", "user_id"],
        unique=False,
    )


def downgrade() -> None:
    """回滚: 删索引 + 删表."""
    op.drop_index(op.f("ix_chat_shares_conv_id_user_id"), table_name="chat_shares")
    op.drop_index(op.f("ix_chat_shares_user_id"), table_name="chat_shares")
    op.drop_index(op.f("ix_chat_shares_conv_id"), table_name="chat_shares")
    op.drop_table("chat_shares")
