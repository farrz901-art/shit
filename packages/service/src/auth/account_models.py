"""Account / Invite / PasswordReset models — 账号系统 3 张表"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from ..storage import Base
from ..utils.timezone import HKT


class Account(Base):
    """真账号 (email + password) — 跟 User 1:1 可选关联

    v2: role 字段 (str) 替原 is_admin (bool). 默认 'user', super_admin 由 seed 创.

    schema 来源: 20260615_000000_consolidated_pg_init.py (accounts 表) +
                 20260617_000000_add_roles_and_rbac.py (accounts.role 列).
    ORM __table_args__ 的约束 / 索引名跟 migration 严格对齐, 避免 alembic
    autogenerate 产生假 diff (DATA-002 修复).
    """

    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(50), nullable=True)
    role: Mapped[str] = mapped_column(Text, nullable=False, default="user", server_default="user")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(HKT)
    )
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    deletion_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint("email LIKE '%_@_%._%'", name="ck_accounts_email_format"),
        CheckConstraint("role IN ('super_admin', 'admin', 'user')", name="ck_accounts_role"),
        UniqueConstraint("email", name="uq_accounts_email"),
        Index("ix_accounts_email", "email", unique=True),
        Index("ix_accounts_is_active", "is_active"),
    )

    @property
    def is_pending_deletion(self) -> bool:
        """账号是否处于注销宽限期内 (deletion_requested_at 已设) — 派生属性, 不存 DB."""
        return self.deletion_requested_at is not None

    def __repr__(self) -> str:
        return f"<Account id={self.id} email={self.email} role={self.role}>"


class Invite(Base):
    """一次性 invite token, admin 创, user 兑换

    schema 来源: 20260615_000000_consolidated_pg_init.py (invites 表).
    约束 / 索引名跟 migration 对齐 (DATA-002).
    """

    __tablename__ = "invites"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    token: Mapped[str] = mapped_column(String(64), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    invited_by_account_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    redeemed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    account_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("accounts.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(HKT)
    )

    __table_args__ = (
        UniqueConstraint("token", name="uq_invites_token"),
        Index("ix_invites_token", "token", unique=True),
        Index("ix_invites_email", "email"),
    )

    def __repr__(self) -> str:
        return f"<Invite id={self.id} email={self.email} redeemed={self.redeemed_at is not None}>"


class PasswordReset(Base):
    """密码重置一次性 token

    schema 来源: 20260615_000000_consolidated_pg_init.py (password_resets 表).
    约束 / 索引名跟 migration 对齐 (DATA-002).
    """

    __tablename__ = "password_resets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(Integer, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False)
    token: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(HKT)
    )

    __table_args__ = (
        UniqueConstraint("token", name="uq_password_resets_token"),
        Index("ix_password_resets_token", "token", unique=True),
    )

    def __repr__(self) -> str:
        return f"<PasswordReset id={self.id} account_id={self.account_id} used={self.used_at is not None}>"


class EmailChange(Base):
    """邮箱修改一次性 token (7 天过期). new_email 验证成功后切换 Account.email.

    schema 来源: 20260617_120000_account_settings.py (email_changes 表).
    索引名跟 migration 对齐; token 列唯一性靠唯一索引实现, 不再走列级 unique=True
    (避免 alembic 误报新加 UniqueConstraint).
    """

    __tablename__ = "email_changes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(Integer, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False)
    new_email: Mapped[str] = mapped_column(String(255), nullable=False)
    token: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(HKT)
    )

    __table_args__ = (
        Index("idx_email_changes_token", "token", unique=True),
        Index("idx_email_changes_account", "account_id"),
    )

    def __repr__(self) -> str:
        return f"<EmailChange id={self.id} account_id={self.account_id} new_email={self.new_email}>"


class DeletionRestore(Base):
    """注销撤销一次性 token (7 天过期, 跟注销宽限期同步).

    schema 来源: 20260617_120000_account_settings.py (deletion_restores 表) +
                 20260624_000000_add_deletion_restore_used_at_unique.py
                 (uq_deletion_restores_account_id_used_at UNIQUE 约束).
    索引名跟 migration 对齐; token 列唯一性靠唯一索引实现, 不再走列级 unique=True
    (避免 alembic 误报新加 UniqueConstraint).
    """

    __tablename__ = "deletion_restores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(Integer, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False)
    token: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(HKT)
    )

    __table_args__ = (
        Index("idx_deletion_restores_token", "token", unique=True),
        Index("idx_deletion_restores_account", "account_id"),
        UniqueConstraint("account_id", "used_at", name="uq_deletion_restores_account_id_used_at"),
    )

    def __repr__(self) -> str:
        return f"<DeletionRestore id={self.id} account_id={self.account_id} used={self.used_at is not None}>"
