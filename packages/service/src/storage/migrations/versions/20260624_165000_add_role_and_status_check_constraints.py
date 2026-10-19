"""add CHECK constraints to accounts.role and buyer_profiles.status (DATA-004 + DATA-006)

accounts.role: 限系统预设 3 角色 (super_admin / admin / user)
buyer_profiles.status: 限 active / archived 两值
无 FK 到 dictionary_items (Phase 3 大重构范围外).
"""

from __future__ import annotations

from alembic import op

revision: str = "20260624_165000"
down_revision: str | None = "20260624_160000"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    """加 CHECK 约束: accounts.role + buyer_profiles.status 限已知枚举值"""
    # accounts.role: 仅 3 系统角色, 不拦自定义角色 (另有 roles 表)
    op.execute("ALTER TABLE accounts ADD CONSTRAINT ck_accounts_role CHECK (role IN ('super_admin', 'admin', 'user'))")
    # buyer_profiles.status: 仅 active / archived
    op.execute(
        "ALTER TABLE buyer_profiles ADD CONSTRAINT ck_buyer_profiles_status CHECK (status IN ('active', 'archived'))"
    )


def downgrade() -> None:
    """回滚: 删两条 CHECK 约束"""
    op.execute("ALTER TABLE accounts DROP CONSTRAINT ck_accounts_role")
    op.execute("ALTER TABLE buyer_profiles DROP CONSTRAINT ck_buyer_profiles_status")
