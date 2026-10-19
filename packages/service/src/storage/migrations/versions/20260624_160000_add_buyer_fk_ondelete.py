"""buyer_profiles / profile_change_logs FK 加 ondelete=CASCADE

(DATA-005 修复) 原来 3 个 FK 用 PG 默认 NO ACTION, 删 account / buyer_profile
后 change_logs 变孤儿行:

修复范围:
- buyer_profiles.account_id → accounts.id CASCADE (删 account 级联清画像)
- profile_change_logs.account_id → accounts.id CASCADE (删 account 级联清日志)
- profile_change_logs.profile_id → buyer_profiles.id CASCADE (删画像级联清日志)

profile_field_configs 已有 20260623 migration 处理 (account_id 列已删, 无需修).

业务决策:
- 选 CASCADE 不是 SET NULL: 删 account 意味客户已离站, 画像 / 日志一并清除,
  不留孤行. 跟 GDPR 一致性 (right to erasure) 匹配.
"""

from __future__ import annotations

from alembic import op

revision = "20260624_160000"
down_revision = "20260624_150000"  # current head
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. buyer_profiles.account_id → accounts.id CASCADE
    op.drop_constraint("fk_buyer_profiles_account", "buyer_profiles", type_="foreignkey")
    op.create_foreign_key(
        "fk_buyer_profiles_account",
        "buyer_profiles",
        "accounts",
        ["account_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # 2. profile_change_logs.account_id → accounts.id CASCADE
    op.drop_constraint("fk_change_logs_account", "profile_change_logs", type_="foreignkey")
    op.create_foreign_key(
        "fk_change_logs_account",
        "profile_change_logs",
        "accounts",
        ["account_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # 3. profile_change_logs.profile_id → buyer_profiles.id CASCADE
    op.drop_constraint("fk_change_logs_profile", "profile_change_logs", type_="foreignkey")
    op.create_foreign_key(
        "fk_change_logs_profile",
        "profile_change_logs",
        "buyer_profiles",
        ["profile_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    # 1. 恢复 buyer_profiles FK (NO ACTION)
    op.drop_constraint("fk_buyer_profiles_account", "buyer_profiles", type_="foreignkey")
    op.create_foreign_key(
        "fk_buyer_profiles_account",
        "buyer_profiles",
        "accounts",
        ["account_id"],
        ["id"],
    )

    # 2. 恢复 profile_change_logs account FK
    op.drop_constraint("fk_change_logs_account", "profile_change_logs", type_="foreignkey")
    op.create_foreign_key(
        "fk_change_logs_account",
        "profile_change_logs",
        "accounts",
        ["account_id"],
        ["id"],
    )

    # 3. 恢复 profile_change_logs profile FK
    op.drop_constraint("fk_change_logs_profile", "profile_change_logs", type_="foreignkey")
    op.create_foreign_key(
        "fk_change_logs_profile",
        "profile_change_logs",
        "buyer_profiles",
        ["profile_id"],
        ["id"],
    )
