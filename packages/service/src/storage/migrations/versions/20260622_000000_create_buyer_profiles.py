"""create buyer_profiles / profile_field_configs / profile_change_logs

(2026-06-22 buyer-profile spec) 买家结构化画像系统, 独立于 mem0.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

# 注意: profile_data / profile_meta / options / notify_on_change / old_value /
# new_value 都用 JSONB. (2026-06-23 修) 之前用 sa.JSON() 生成 PG json 类型,
# 但 GIN index idx_buyer_profiles_data 用 jsonb_path_ops opclass 要求 JSONB,
# 报错 "operator class jsonb_path_ops does not accept data type json".
# service.py:107 也写 profile_data = :data::jsonb, 业务按 JSONB 用.
revision = "20260622_000000"
down_revision = "20260619_120000"  # current head (dictionary tables)
branch_labels = None
depends_on = None


def upgrade() -> None:
    # buyer_profiles: 每个买家一条
    op.create_table(
        "buyer_profiles",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("buyer_key", sa.String(128), nullable=False),
        sa.Column("buyer_name", sa.String(256), nullable=True),
        sa.Column("status", sa.String(32), server_default="active", nullable=False),
        sa.Column("profile_data", JSONB(), nullable=False, server_default="{}"),
        sa.Column("profile_meta", JSONB(), nullable=False, server_default="{}"),
        sa.Column("tags", sa.ARRAY(sa.String()), nullable=True, server_default="{}"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("assignee_id", sa.Integer(), nullable=True),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_contact_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("account_id", "buyer_key", name="uq_buyer_profiles_account_key"),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], name="fk_buyer_profiles_account"),
    )
    op.create_index("idx_buyer_profiles_account", "buyer_profiles", ["account_id"])
    op.create_index("idx_buyer_profiles_status", "buyer_profiles", ["account_id", "status"])
    op.create_index("idx_buyer_profiles_updated", "buyer_profiles", ["account_id", sa.text("updated_at DESC")])
    op.create_index(
        "idx_buyer_profiles_data",
        "buyer_profiles",
        ["profile_data"],
        postgresql_using="gin",
        postgresql_ops={"profile_data": "jsonb_path_ops"},
    )

    # profile_field_configs: 画像字段定义
    op.create_table(
        "profile_field_configs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("label", sa.String(128), nullable=False),
        sa.Column("field_type", sa.String(32), server_default="text", nullable=False),
        sa.Column("extraction_prompt", sa.Text(), nullable=True),
        sa.Column("options", JSONB(), nullable=True, server_default="[]"),
        sa.Column("is_required", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("notify_on_change", JSONB(), nullable=True, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("account_id", "code", name="uq_field_configs_account_code"),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], name="fk_field_configs_account"),
    )

    # profile_change_logs: 字段变更日志
    op.create_table(
        "profile_change_logs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("profile_id", sa.Uuid(), nullable=False),
        sa.Column("field_code", sa.String(64), nullable=False),
        sa.Column("old_value", JSONB(), nullable=True),
        sa.Column("new_value", JSONB(), nullable=True),
        sa.Column("source", sa.String(32), server_default="auto", nullable=False),
        sa.Column("conv_id", sa.String(128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], name="fk_change_logs_account"),
        sa.ForeignKeyConstraint(["profile_id"], ["buyer_profiles.id"], name="fk_change_logs_profile"),
    )
    op.create_index("idx_change_logs_profile", "profile_change_logs", ["profile_id", sa.text("created_at DESC")])


def downgrade() -> None:
    op.drop_table("profile_change_logs")
    op.drop_table("profile_field_configs")
    op.drop_table("buyer_profiles")
