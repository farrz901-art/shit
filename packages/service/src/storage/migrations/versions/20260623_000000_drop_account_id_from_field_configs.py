"""drop account_id from profile_field_configs

(2026-06-23) 画像字段配置是全局模板, 所有买家共享同一套字段定义,
不应该按 account_id 隔离. 去掉 FK 和 account_id 列, UNIQUE 改在 code 上.

解决: 前端画像字段配置页空白（seed 因 FK 约束被跳过）的问题.

(2026-06-24 DATA-001 修) downgrade 重写:
- 原本 downgrade 用 server_default="0" 加 account_id 列, 会让所有现有行
  落同一 account_id=0, 然后 UNIQUE(account_id, code) 必冲突 → 必失败.
- 修复策略: 加列 nullable=True, 不回填数据 (account_id 留 NULL), FK 用
  ondelete=SET NULL. 不重建 UNIQUE 约束 (PG UNIQUE 不约束 NULL, 多行
  NULL 是允许的).
- 业务侧确认: profile_field_configs 是全局模板, 多对多到 account 不强
  约束, account_id 留 NULL 可接受.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260623_000000"
down_revision = "20260622_000000"  # 上一个 head
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. 删 FK 约束
    op.drop_constraint("fk_field_configs_account", "profile_field_configs", type_="foreignkey")
    # 2. 删 UNIQUE(account_id, code)
    op.drop_constraint("uq_field_configs_account_code", "profile_field_configs", type_="unique")
    # 3. 删 account_id 列
    op.drop_column("profile_field_configs", "account_id")
    # 4. 加新 UNIQUE(code)
    op.create_unique_constraint("uq_field_configs_code", "profile_field_configs", ["code"])


def downgrade() -> None:
    """回滚 20260623 的 drop account_id.

    关键: 不能用 server_default="0" (会让所有现有行落同一 account_id, 跟 UNIQUE 冲突).
    策略: nullable=True 先加列, 不回填数据 (account_id 留 NULL), 加 FK 用 ondelete=SET NULL.
    不重建 UNIQUE(account_id, code) 约束 (PG UNIQUE 不约束 NULL, 多行 NULL 允许).

    业务侧确认: profile_field_configs 在 buyer_profile 体系下是全局模板,
    多对多到 account 不强约束, account_id 留 NULL 可接受.
    """
    # 1. 删 UNIQUE(code)
    op.drop_constraint("uq_field_configs_code", "profile_field_configs", type_="unique")
    # 2. 加回 account_id 列, nullable=True, 不设 server_default (避免 UNIQUE 冲突)
    op.add_column(
        "profile_field_configs",
        sa.Column("account_id", sa.Integer(), nullable=True),
    )
    # 3. 加回 FK (ondelete=SET NULL: account 删时 account_id 变 NULL, 保留 field_config 记录)
    op.create_foreign_key(
        "fk_field_configs_account",
        "profile_field_configs",
        "accounts",
        ["account_id"],
        ["id"],
        ondelete="SET NULL",
    )
    # 注: 不重建 UNIQUE(account_id, code). PG UNIQUE 不约束 NULL,
    # account_id 全 NULL 的多行仍然允许 (符合"全局模板"业务语义).
