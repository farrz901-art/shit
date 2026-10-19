"""add roles, role_permissions, accounts.role

v2: 完整 RBAC (N 角色权限组 + 7 页面权限点 + 30s cache).
- 删 accounts.is_admin (迁到 role 字符串)
- 创 roles (预设 user/admin/super_admin)
- 创 role_permissions (user + admin 各 7 页面初始)
- super_admin 不入库, 代码层 meta 豁免
"""

from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "20260617_000000"
down_revision = "20260616_120000"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. accounts 加 role 列, 默认 user
    op.add_column(
        "accounts",
        sa.Column("role", sa.Text(), nullable=False, server_default="user"),
    )
    # 2. 旧 is_admin=TRUE → super_admin
    op.execute("UPDATE accounts SET role = 'super_admin' WHERE is_admin = TRUE")
    # 3. 删 is_admin
    op.drop_column("accounts", "is_admin")

    # 4. 创 roles 表
    op.create_table(
        "roles",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("name", sa.Text(), nullable=False, unique=True),
        sa.Column("label_zh", sa.Text(), nullable=False),
        sa.Column("label_en", sa.Text(), nullable=False),
        sa.Column("is_system", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("is_deletable", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("idx_roles_name", "roles", ["name"], unique=True)

    # 5. 插 3 个预设角色
    op.bulk_insert(
        sa.table(
            "roles",
            sa.column("name", sa.Text),
            sa.column("label_zh", sa.Text),
            sa.column("label_en", sa.Text),
            sa.column("is_system", sa.Boolean),
            sa.column("is_deletable", sa.Boolean),
            sa.column("created_at", sa.DateTime),
            sa.column("updated_at", sa.DateTime),
        ),
        [
            {
                "name": "user",
                "label_zh": "用户",
                "label_en": "User",
                "is_system": True,
                "is_deletable": False,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
            },
            {
                "name": "admin",
                "label_zh": "管理员",
                "label_en": "Admin",
                "is_system": True,
                "is_deletable": False,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
            },
            {
                "name": "super_admin",
                "label_zh": "超级管理员",
                "label_en": "Super Admin",
                "is_system": True,
                "is_deletable": False,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
            },
        ],
    )

    # 6. 创 role_permissions 表
    op.create_table(
        "role_permissions",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("role_name", sa.Text(), nullable=False),
        sa.Column("page_key", sa.Text(), nullable=False),
        sa.Column("allowed", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("role_name", "page_key", name="uq_role_perm"),
    )
    op.create_index("idx_role_perms_name", "role_permissions", ["role_name"])

    # 7. 插 8 行 (user 2 + admin 6, super_admin 不入库)
    op.bulk_insert(
        sa.table(
            "role_permissions",
            sa.column("role_name", sa.Text),
            sa.column("page_key", sa.Text),
            sa.column("allowed", sa.Boolean),
            sa.column("created_at", sa.DateTime),
            sa.column("updated_at", sa.DateTime),
        ),
        [
            # user: chat, decode = true
            *[
                {
                    "role_name": "user",
                    "page_key": k,
                    "allowed": True,
                    "created_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow(),
                }
                for k in ("chat", "decode")
            ],
            # user: 其余 5 个 = false
            *[
                {
                    "role_name": "user",
                    "page_key": k,
                    "allowed": False,
                    "created_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow(),
                }
                for k in ("output", "knowledge", "evaluate", "submissions", "health")
            ],
            # admin: 6 个 = true, health = false
            *[
                {
                    "role_name": "admin",
                    "page_key": k,
                    "allowed": True,
                    "created_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow(),
                }
                for k in ("chat", "output", "knowledge", "evaluate", "submissions", "decode")
            ],
            {
                "role_name": "admin",
                "page_key": "health",
                "allowed": False,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
            },
        ],
    )


def downgrade() -> None:
    op.drop_table("role_permissions")
    op.drop_table("roles")
    op.add_column(
        "accounts",
        sa.Column("is_admin", sa.Boolean, nullable=False, server_default=sa.false()),
    )
    op.execute("UPDATE accounts SET is_admin = TRUE WHERE role = 'super_admin'")
    op.drop_column("accounts", "role")
