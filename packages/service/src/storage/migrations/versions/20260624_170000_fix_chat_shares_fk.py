"""fix chat_shares conv_id/user_id 类型/长度 + FK CASCADE (DATA-007)

conv_id → String(36) + FK conversations.id (原 String(128), 无 FK)
user_id → Integer + FK users.id (原 String(64), 无 FK)

前置: 20260624_165000_add_role_and_status_check_constraints
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260624_170000"
down_revision: str | None = "20260624_165000"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    """alter chat_shares: conv_id → String(36) + FK, user_id → Integer + FK."""
    # --- user_id: String(64) → Integer + FK users.id ---

    # 删旧索引 (含 user_id 的), 重建时自动含新列
    op.drop_index(op.f("ix_chat_shares_user_id"), table_name="chat_shares")
    op.drop_index(op.f("ix_chat_shares_conv_id_user_id"), table_name="chat_shares")

    # 先改 user_id 类型 (String → Integer). PG 会隐式转换: 先删 default/not null.
    # 如果现有数据里 user_id 全是合法数字字符串, ALTER 到位.
    # 如果含非数字串 → 需先手工清理 (本 spec 假设无脏数据, 否则加 USING 子句).
    op.alter_column(
        "chat_shares",
        "user_id",
        existing_type=sa.String(64),
        type_=sa.Integer(),
        postgresql_using="user_id::integer",
        nullable=False,
    )
    op.create_foreign_key(
        "fk_chat_shares_user_id",
        "chat_shares",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # --- conv_id: String(128) → String(36) + FK conversations.id ---
    op.alter_column(
        "chat_shares",
        "conv_id",
        existing_type=sa.String(128),
        type_=sa.String(36),
        nullable=False,
    )
    op.create_foreign_key(
        "fk_chat_shares_conv_id",
        "chat_shares",
        "conversations",
        ["conv_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # 重建索引 (在改完类型后的列上)
    op.create_index(op.f("ix_chat_shares_user_id"), "chat_shares", ["user_id"], unique=False)
    op.create_index(
        op.f("ix_chat_shares_conv_id_user_id"),
        "chat_shares",
        ["conv_id", "user_id"],
        unique=False,
    )


def downgrade() -> None:
    """回滚: 删 FK + 恢复类型 + 重建旧索引."""
    # 删 FK
    op.drop_constraint("fk_chat_shares_user_id", "chat_shares", type_="foreignkey")
    op.drop_constraint("fk_chat_shares_conv_id", "chat_shares", type_="foreignkey")

    # 删索引 (含 user_id 的)
    op.drop_index(op.f("ix_chat_shares_user_id"), table_name="chat_shares")
    op.drop_index(op.f("ix_chat_shares_conv_id_user_id"), table_name="chat_shares")

    # user_id: Integer → String(64)
    op.alter_column(
        "chat_shares",
        "user_id",
        existing_type=sa.Integer(),
        type_=sa.String(64),
        nullable=False,
    )

    # conv_id: String(36) → String(128)
    op.alter_column(
        "chat_shares",
        "conv_id",
        existing_type=sa.String(36),
        type_=sa.String(128),
        nullable=False,
    )

    # 重建旧索引
    op.create_index(op.f("ix_chat_shares_user_id"), "chat_shares", ["user_id"], unique=False)
    op.create_index(
        op.f("ix_chat_shares_conv_id_user_id"),
        "chat_shares",
        ["conv_id", "user_id"],
        unique=False,
    )
