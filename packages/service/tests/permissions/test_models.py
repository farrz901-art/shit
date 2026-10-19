"""Role + RolePermission 表结构 + 约束测试 (100% mock, 0 真实 DB)"""

from src.permissions.models import Role, RolePermission


def test_role_required_fields() -> None:
    """Role 表必须含字段: name(unique), label_zh, label_en, is_system, is_deletable, created_at, updated_at"""
    columns = set(Role.__table__.columns.keys())
    assert {"name", "label_zh", "label_en", "is_system", "is_deletable", "created_at", "updated_at"} <= columns
    # name 列必须 unique
    name_col = Role.__table__.columns["name"]
    assert name_col.unique is True


def test_role_permission_required_fields() -> None:
    """RolePermission 表必须含字段: role_name, page_key, allowed, created_at, updated_at"""
    columns = set(RolePermission.__table__.columns.keys())
    assert {"role_name", "page_key", "allowed", "created_at", "updated_at"} <= columns
    # allowed 列必须 nullable=False
    allowed_col = RolePermission.__table__.columns["allowed"]
    assert allowed_col.nullable is False


def test_role_permission_unique_constraint() -> None:
    """unique(role_name, page_key) 约束 (uq_role_perm)

    走 __table_args__ 拿所有声明的约束, 按 class 名带 "UniqueConstraint" 即视为 unique 约束.
    """
    table_args = RolePermission.__table_args__
    uc_list = list(table_args) if isinstance(table_args, tuple) else [table_args]
    names = {c.name for c in uc_list if "UniqueConstraint" in type(c).__name__}
    assert "uq_role_perm" in names
