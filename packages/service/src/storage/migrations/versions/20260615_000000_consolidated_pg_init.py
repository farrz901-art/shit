"""consolidated pg init (2026-06-15)

把 4 个旧 migration (1f49 / a3b8 / 2a3b / b7c4) 合并成 1 个 fresh init.
down_revision = None (起点). 包含所有业务表 + ingest_tasks + kg_audit.

为啥不沿用 4 个旧 migration: SQLite migration 用 sa.JSON() 在 PG 上创建 JSON 列
(不是 JSONB), 且 SQLite batch_alter_table 在 PG 上是 noop. 一次性 fresh init
确保 schema 干净, 跑一次 alembic upgrade head 就到 head.

字段定义跟现有 ORM model 1:1 对齐, 这样 SQLAlchemy ORM 跑读写时不会类型冲突.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260615_000000"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """升级到 consolidated PG schema: 11 张业务表 + 索引.

    表创建顺序按 FK 依赖排: accounts 先 (无依赖), users 引用 accounts (FK inline).
    旧 plan 文档里 "users 在 accounts 之前" 的写法在 PG 上会撞 'relation accounts
    does not exist', 这里调换顺序.
    """
    # === 1. accounts (先建, users.account_id FK 引用它) ===
    op.create_table(
        "accounts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("display_name", sa.String(length=50), nullable=True),
        sa.Column("is_admin", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("email LIKE '%_@_%._%'", name="ck_accounts_email_format"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email", name="uq_accounts_email"),
    )
    op.create_index(op.f("ix_accounts_email"), "accounts", ["email"], unique=True)
    op.create_index(op.f("ix_accounts_is_active"), "accounts", ["is_active"], unique=False)

    # === 2. users (FK inline 引用 accounts) ===
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("public_token", sa.String(length=64), nullable=False),
        sa.Column("display_name", sa.String(length=50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["accounts.id"],
            name=op.f("fk_users_account_id_accounts"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_last_seen_at"), "users", ["last_seen_at"], unique=False)
    op.create_index(op.f("ix_users_public_token"), "users", ["public_token"], unique=True)
    op.create_index(op.f("ix_users_account_id"), "users", ["account_id"], unique=False)

    # === 3. invites ===
    op.create_table(
        "invites",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("token", sa.String(length=64), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("invited_by_account_id", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("redeemed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("account_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["invited_by_account_id"], ["accounts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token", name="uq_invites_token"),
    )
    op.create_index(op.f("ix_invites_token"), "invites", ["token"], unique=True)
    op.create_index(op.f("ix_invites_email"), "invites", ["email"], unique=False)

    # === 4. password_resets ===
    op.create_table(
        "password_resets",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("token", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token", name="uq_password_resets_token"),
    )
    op.create_index(op.f("ix_password_resets_token"), "password_resets", ["token"], unique=True)

    # === 5. conversations ===
    op.create_table(
        "conversations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("message_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_conversations_updated_at"), "conversations", ["updated_at"], unique=False)
    op.create_index(op.f("ix_conversations_user_id"), "conversations", ["user_id"], unique=False)
    op.create_index("ix_conversations_user_updated", "conversations", ["user_id", "updated_at"], unique=False)

    # === 6. messages ===
    op.create_table(
        "messages",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("conversation_id", sa.String(length=36), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("meta", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_messages_conv_created", "messages", ["conversation_id", "created_at"], unique=False)
    op.create_index(op.f("ix_messages_conversation_id"), "messages", ["conversation_id"], unique=False)

    # === 7. evaluations ===
    op.create_table(
        "evaluations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("dataset_name", sa.String(length=200), nullable=False),
        sa.Column("dataset_path", sa.String(length=500), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("total_samples", sa.Integer(), nullable=False),
        sa.Column("successful", sa.Integer(), nullable=False),
        sa.Column("failed", sa.Integer(), nullable=False),
        sa.Column("concurrency", sa.Integer(), nullable=False),
        sa.Column("avg_metrics", sa.JSON(), nullable=True),
        sa.Column("duration_seconds", sa.Float(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_evaluations_created_at"), "evaluations", ["created_at"], unique=False)
    op.create_index(op.f("ix_evaluations_status"), "evaluations", ["status"], unique=False)
    op.create_index("ix_evaluations_user_created", "evaluations", ["user_id", "created_at"], unique=False)
    op.create_index(op.f("ix_evaluations_user_id"), "evaluations", ["user_id"], unique=False)

    # === 8. evaluation_samples (含 sources 列) ===
    op.create_table(
        "evaluation_samples",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("evaluation_id", sa.Integer(), nullable=False),
        sa.Column("index", sa.Integer(), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("ground_truth", sa.Text(), nullable=True),
        sa.Column("answer", sa.Text(), nullable=True),
        sa.Column("contexts", sa.JSON(), nullable=True),
        sa.Column("metrics", sa.JSON(), nullable=True),
        sa.Column("sources", sa.JSON(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["evaluation_id"], ["evaluations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_evaluation_samples_evaluation_id"), "evaluation_samples", ["evaluation_id"], unique=False)
    op.create_index("ix_samples_eval_index", "evaluation_samples", ["evaluation_id", "index"], unique=False)

    # === 9. approvals ===
    op.create_table(
        "approvals",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("payload", sa.Text(), nullable=False),
        sa.Column("review_status", sa.String(length=20), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("apply_status", sa.String(length=20), nullable=False, server_default=sa.text("'none'")),
        sa.Column("submitter_id", sa.Integer(), nullable=False),
        sa.Column("reviewer_id", sa.Integer(), nullable=True),
        sa.Column("rejection_reason", sa.String(length=40), nullable=True),
        sa.Column("rejection_note", sa.Text(), nullable=True),
        sa.Column("error_msg", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["submitter_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reviewer_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_approvals_kind"), "approvals", ["kind"], unique=False)
    op.create_index(op.f("ix_approvals_review_status"), "approvals", ["review_status"], unique=False)
    op.create_index(op.f("ix_approvals_apply_status"), "approvals", ["apply_status"], unique=False)
    op.create_index(op.f("ix_approvals_submitter_id"), "approvals", ["submitter_id"], unique=False)
    op.create_index(op.f("ix_approvals_reviewer_id"), "approvals", ["reviewer_id"], unique=False)
    op.create_index(op.f("ix_approvals_created_at"), "approvals", ["created_at"], unique=False)
    op.create_index("idx_approvals_review_created", "approvals", ["review_status", "created_at"], unique=False)
    op.create_index("idx_approvals_apply_created", "approvals", ["apply_status", "created_at"], unique=False)
    op.create_index("idx_approvals_submitter_created", "approvals", ["submitter_id", "created_at"], unique=False)

    # === 10. ingest_tasks (新) ===
    # 设计匿名, 接受无 FK — 不关联 user 表, 仅存 user_hash 做隔离
    op.create_table(
        "ingest_tasks",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_hash", sa.String(length=64), nullable=False),
        sa.Column("state", sa.String(length=20), nullable=False),
        sa.Column("total_files", sa.Integer(), nullable=False),
        sa.Column("processed", sa.Integer(), nullable=False),
        sa.Column("failed", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("work_dir", sa.String(length=500), nullable=True),
        sa.Column("input_files_json", sa.Text(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("output_files_json", sa.Text(), nullable=False, server_default=sa.text("'[]'")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_ingest_tasks_user_hash"), "ingest_tasks", ["user_hash"], unique=False)
    op.create_index(
        "ix_ingest_tasks_user_started",
        "ingest_tasks",
        ["user_hash", "started_at"],
        unique=False,
    )

    # === 11. kg_audit (新) ===
    # 设计匿名, 接受无 FK — 纯审计日志, 不关联 entity 表
    op.create_table(
        "kg_audit",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("ts", sa.Float(), nullable=False),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("actor", sa.String(length=100), nullable=True),
        sa.Column("target", sa.String(length=200), nullable=True),
        sa.Column("result", sa.String(length=20), nullable=False),
        sa.Column("detail", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_kg_audit_ts"), "kg_audit", ["ts"], unique=False)


def downgrade() -> None:
    """倒序删除所有表."""
    op.drop_table("kg_audit")
    op.drop_table("ingest_tasks")
    op.drop_table("approvals")
    op.drop_table("evaluation_samples")
    op.drop_table("evaluations")
    op.drop_table("messages")
    op.drop_table("conversations")
    op.drop_table("password_resets")
    op.drop_table("invites")
    op.drop_table("accounts")
    op.drop_table("users")
