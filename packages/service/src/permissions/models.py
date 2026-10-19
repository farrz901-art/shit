"""Role + RolePermission models

v2 RBAC: roles 是 N 个 (3 预设 + super-admin 创建), role_permissions 是 role × page 矩阵.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, Text, UniqueConstraint

from ..storage.base import Base


class Role(Base):
    """角色: 3 预设 (user/admin/super_admin) + super-admin 创建的自定义角色

    - name 唯一, 2-32 字符 [a-z0-9_]
    - is_system: 系统内置 (不删)
    - is_deletable: 可被 super_admin 删 (自定义 TRUE, 系统 FALSE)
    """

    __tablename__ = "roles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(Text, nullable=False, unique=True)
    label_zh = Column(Text, nullable=False)
    label_en = Column(Text, nullable=False)
    is_system = Column(Boolean, nullable=False, default=False)
    is_deletable = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(UTC))
    updated_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )


class RolePermission(Base):
    """role × page_key 权限矩阵 (super_admin 不入库, 走代码 meta 豁免)"""

    __tablename__ = "role_permissions"
    __table_args__ = (UniqueConstraint("role_name", "page_key", name="uq_role_perm"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    role_name = Column(Text, nullable=False)
    page_key = Column(Text, nullable=False)
    allowed = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(UTC))
    updated_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
