"""账号设置: Account 加 avatar_url / deletion_requested_at, 新表 email_changes / deletion_restores"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260617_120000"
down_revision = "20260617_001000"  # log_tables migration, latest before this
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("accounts", sa.Column("avatar_url", sa.String(500), nullable=True))
    op.add_column(
        "accounts",
        sa.Column("deletion_requested_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "email_changes",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "account_id",
            sa.Integer,
            sa.ForeignKey("accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("new_email", sa.String(255), nullable=False),
        sa.Column("token", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
    )
    op.create_index("idx_email_changes_token", "email_changes", ["token"], unique=True)
    op.create_index("idx_email_changes_account", "email_changes", ["account_id"])

    op.create_table(
        "deletion_restores",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "account_id",
            sa.Integer,
            sa.ForeignKey("accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("token", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
    )
    op.create_index("idx_deletion_restores_token", "deletion_restores", ["token"], unique=True)
    op.create_index("idx_deletion_restores_account", "deletion_restores", ["account_id"])


def downgrade() -> None:
    op.drop_index("idx_deletion_restores_account", "deletion_restores")
    op.drop_index("idx_deletion_restores_token", "deletion_restores")
    op.drop_table("deletion_restores")
    op.drop_index("idx_email_changes_account", "email_changes")
    op.drop_index("idx_email_changes_token", "email_changes")
    op.drop_table("email_changes")
    op.drop_column("accounts", "deletion_requested_at")
    op.drop_column("accounts", "avatar_url")
