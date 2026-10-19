"""deletion_restores 加 UNIQUE(account_id, used_at) 防 restore token 重放

(CON-002 修复配套)

修复点:
- 原来 DeletionRestore.used_at 只标单个 token 的使用时间, 但 cancel_deletion
  流程会扫所有 (account_id, used_at IS NULL) 标 used_at = now().
  异常场景: cancel 后用户又触发第二次 cancel (例如双击按钮 + 重试),
  业务允许 (幂等). 但若两个不同 token 在同一秒被 mark used, 不应让两条
  used_at NOT NULL 的 token 来自同一个 account.
- 防重放语义: 每个 account 至多一条 DeletionRestore 记录有 used_at.
- 实现: UNIQUE(account_id, used_at). 因 PG UNIQUE 不约束 NULL, 多条
  used_at IS NULL 仍允许, 但两条 used_at NOT NULL 即冲突 (符合预期).
- downgrade 直接 drop_constraint.

注意: 表名 deletion_restores 跟 account_models.DeletionRestore.__tablename__ 一致.
"""

from __future__ import annotations

from alembic import op

revision = "20260624_000000"
down_revision = "20260623_000000"  # 上一个 head: drop account_id from field_configs
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. 先清掉异常重复行: 同一 (account_id, used_at NOT NULL) 多于 1 条 → 留最早一条 (id 最小)
    #    理论不该有, 但保险起见, 防止历史脏数据导致加 UNIQUE 失败.
    op.execute(
        """
        DELETE FROM deletion_restores a
        USING deletion_restores b
        WHERE a.id > b.id
          AND a.account_id = b.account_id
          AND a.used_at IS NOT NULL
          AND b.used_at IS NOT NULL
          AND a.used_at = b.used_at
        """
    )

    # 2. 加 UNIQUE 约束: (account_id, used_at)
    #    PG UNIQUE 不约束 NULL, 多条 used_at IS NULL 仍允许.
    #    但同一 account 至多一条 used_at NOT NULL 行 (防 restore token 重放).
    op.create_unique_constraint(
        "uq_deletion_restores_account_id_used_at",
        "deletion_restores",
        ["account_id", "used_at"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_deletion_restores_account_id_used_at",
        "deletion_restores",
        type_="unique",
    )
