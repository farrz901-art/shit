"""Account / Invite / PasswordReset / EmailChange / DeletionRestore ORM 约束名跟 migration 对齐

DATA-002 修复验证:
- Alembic autogenerate 在 ORM 跟 migration 名字一致时才报 0 drift
- 此测试用 AST 解析 migration 源码 + introspect ORM __table_args__, 双侧对齐断言
- 模式 1 mock: 不连 PG, 纯静态对比

覆盖:
- Account: ck_accounts_email_format + uq_accounts_email + ix_accounts_email + ix_accounts_is_active
- Invite: uq_invites_token + ix_invites_token + ix_invites_email
- PasswordReset: uq_password_resets_token + ix_password_resets_token
- EmailChange: idx_email_changes_token (唯一索引)
- DeletionRestore: idx_deletion_restores_token (唯一索引) + uq_deletion_restores_account_id_used_at

任何一边漏掉/多出 名字都会失败, 防止后续 refactor 再漂移.
"""

from __future__ import annotations

import ast
from pathlib import Path

from sqlalchemy import CheckConstraint, UniqueConstraint

# ---- helpers ----


def _migrations_dir() -> Path:
    """alembic migration 目录"""
    return Path(__file__).parent.parent.parent / "src" / "storage" / "migrations" / "versions"


def _load_orm_constraint_names(model_cls: type) -> dict[str, list[str]]:
    """从 ORM __table_args__ 提取约束名, 按类型分组.

    Returns:
        {"check": [...], "unique": [...], "index": [...]} - 每组是约束名列表.
    """
    result: dict[str, list[str]] = {"check": [], "unique": [], "index": []}
    table = model_cls.__table__
    for constraint in table.constraints:
        if isinstance(constraint, CheckConstraint):
            # constraint.name 类型是 _ConstraintNameArgument (含 _NoneName 哨兵),
            # 实际值是 str 或 _NoneName; 这里只用 str 走分支.
            cname_raw = constraint.name
            cname = cname_raw if isinstance(cname_raw, str) else None
            if cname:
                result["check"].append(cname)
        elif isinstance(constraint, UniqueConstraint):
            cname_raw = constraint.name
            cname = cname_raw if isinstance(cname_raw, str) else None
            if cname:
                result["unique"].append(cname)
    for index in table.indexes:
        iname_raw = index.name
        iname = iname_raw if isinstance(iname_raw, str) else None
        if iname:
            result["index"].append(iname)
    return result


def _call_first_str_arg(call: ast.Call) -> str | None:
    """提取 op.create_table('name', ...) / op.create_index('name', ...) 第一个 str arg"""
    if not call.args:
        return None
    first = call.args[0]
    if isinstance(first, ast.Constant) and isinstance(first.value, str):
        return first.value
    return None


def _extract_op_calls_from_func(func_node: ast.FunctionDef) -> list[ast.Call]:
    """从 upgrade() / downgrade() 函数体里提取所有 op.* 调用."""
    calls: list[ast.Call] = []
    for node in ast.walk(func_node):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name):
                if node.func.value.id == "op":
                    calls.append(node)
    return calls


def _get_create_table_for(func_node: ast.FunctionDef, table_name: str) -> ast.Call | None:
    """找 upgrade() 里 op.create_table(<table_name>, ...) 调用."""
    for call in _extract_op_calls_from_func(func_node):
        if isinstance(call.func, ast.Attribute) and call.func.attr == "create_table":
            if _call_first_str_arg(call) == table_name:
                return call
    return None


def _get_unique_constraints_in_table(create_table_call: ast.Call) -> list[str]:
    """从 op.create_table(...) 的 positional args 提取 sa.UniqueConstraint 的 name 列表."""
    names: list[str] = []
    for arg in create_table_call.args:
        if isinstance(arg, ast.Call) and isinstance(arg.func, ast.Attribute):
            if arg.func.attr == "UniqueConstraint":
                # name=... keyword arg
                for kw in arg.keywords:
                    if kw.arg == "name":
                        if isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
                            names.append(kw.value.value)
                        break
    return names


def _get_check_constraints_in_table(create_table_call: ast.Call) -> list[str]:
    """从 op.create_table(...) 的 positional args 提取 sa.CheckConstraint 的 name 列表."""
    names: list[str] = []
    for arg in create_table_call.args:
        if isinstance(arg, ast.Call) and isinstance(arg.func, ast.Attribute):
            if arg.func.attr == "CheckConstraint":
                for kw in arg.keywords:
                    if kw.arg == "name":
                        if isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
                            names.append(kw.value.value)
                        break
    return names


def _get_alter_table_check_constraints_for(func_node: ast.FunctionDef, table_name: str) -> list[str]:
    """扫 op.execute('ALTER TABLE <table> ADD CONSTRAINT <name> CHECK ...') 字面量, 返 constraint 名列表.

    用于覆盖 op.create_table 之后通过 op.execute 加的 CHECK 约束 (例: 20260624_165000 加 ck_accounts_role).
    跨 migration 文件链 ORM 跟 alembic 应当对得上, 单一 migration 文件 AST 扫不到的也算 'migration 已声明'.
    """
    import re

    names: list[str] = []
    pattern = re.compile(
        r"ALTER\s+TABLE\s+" + re.escape(table_name) + r"\s+ADD\s+CONSTRAINT\s+(\w+)\s+CHECK",
        re.IGNORECASE,
    )
    for call in _extract_op_calls_from_func(func_node):
        if isinstance(call.func, ast.Attribute) and call.func.attr == "execute":
            if call.args and isinstance(call.args[0], ast.Constant) and isinstance(call.args[0].value, str):
                match = pattern.search(call.args[0].value)
                if match:
                    names.append(match.group(1))
    return names


def _get_create_indexes_for_table(func_node: ast.FunctionDef, table_name: str) -> list[str]:
    """找 upgrade() 里对 <table_name> 的所有 op.create_index 名 (按出现顺序)."""
    names: list[str] = []
    for call in _extract_op_calls_from_func(func_node):
        if isinstance(call.func, ast.Attribute) and call.func.attr == "create_index":
            # op.create_index(op.f("name"), "table_name", ...) 形式 → 第一个 arg 是 op.f(...)
            # 也可能是 op.create_index("name", "table_name", ...) 直接字符串
            first = call.args[0] if call.args else None
            index_name: str | None = None
            if isinstance(first, ast.Constant) and isinstance(first.value, str):
                index_name = first.value
            elif isinstance(first, ast.Call) and isinstance(first.func, ast.Attribute):
                # op.f("name") 形式
                if first.func.attr == "f" and first.args:
                    inner = first.args[0]
                    if isinstance(inner, ast.Constant) and isinstance(inner.value, str):
                        index_name = inner.value
            # table_name 通常在第二个 positional arg 或 table_name kwarg
            target_table: str | None = None
            if len(call.args) >= 2 and isinstance(call.args[1], ast.Constant) and isinstance(call.args[1].value, str):
                target_table = call.args[1].value
            if target_table is None:
                for kw in call.keywords:
                    if kw.arg == "table_name":
                        if isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
                            target_table = kw.value.value
                        break
            if index_name and target_table == table_name:
                names.append(index_name)
    return names


def _get_create_unique_constraints_for_table(
    func_node: ast.FunctionDef, table_name: str, constraint_name: str
) -> ast.Call | None:
    """找 op.create_unique_constraint(constraint_name, table_name, ...) 调用."""
    for call in _extract_op_calls_from_func(func_node):
        if isinstance(call.func, ast.Attribute) and call.func.attr == "create_unique_constraint":
            if _call_first_str_arg(call) == constraint_name:
                # 验证 table_name 匹配
                if len(call.args) >= 2 and isinstance(call.args[1], ast.Constant):
                    if call.args[1].value == table_name:
                        return call
    return None


def _load_migration_func(migration_filename: str, func_name: str) -> ast.FunctionDef:
    """加载 migration 源码, 提取指定函数 AST."""
    path = _migrations_dir() / migration_filename
    assert path.exists(), f"migration 文件不存在: {path}"
    source = path.read_text(encoding="utf-8")
    module = ast.parse(source)
    func = next(
        (n for n in module.body if isinstance(n, ast.FunctionDef) and n.name == func_name),
        None,
    )
    assert func is not None, f"{migration_filename} 缺 {func_name}()"
    return func


# ---- Account ----


def test_account_orm_constraints_match_migration():
    """Account ORM __table_args__ 跟 migration 一致 (DATA-002 修复验证).

    Account 的 CHECK 约束跨两个 migration:
    - 20260615_000000 create_table 加 ck_accounts_email_format
    - 20260624_165000 op.execute ALTER TABLE 加 ck_accounts_role (后续 migration 补的)
    扫两边合并比, 跟 ORM 当前快照对齐.
    """
    from src.auth.account_models import Account

    orm_names = _load_orm_constraint_names(Account)
    upgrade = _load_migration_func("20260615_000000_consolidated_pg_init.py", "upgrade")
    create_accounts = _get_create_table_for(upgrade, "accounts")
    assert create_accounts is not None, "migration 缺 accounts create_table"

    # CheckConstraint: create_table 内部 + 后续 ALTER TABLE ADD CONSTRAINT (跨 migration 合并)
    migration_check = _get_check_constraints_in_table(create_accounts)
    upgrade_role_ck = _load_migration_func("20260624_165000_add_role_and_status_check_constraints.py", "upgrade")
    migration_check += _get_alter_table_check_constraints_for(upgrade_role_ck, "accounts")
    assert sorted(orm_names["check"]) == sorted(migration_check), (
        f"Account CheckConstraint name 不一致: ORM={orm_names['check']} migration={migration_check}"
    )
    assert "ck_accounts_email_format" in orm_names["check"], (
        f"Account ORM 缺 ck_accounts_email_format, 实际 {orm_names['check']}"
    )
    assert "ck_accounts_role" in orm_names["check"], f"Account ORM 缺 ck_accounts_role, 实际 {orm_names['check']}"

    # UniqueConstraint
    migration_unique = _get_unique_constraints_in_table(create_accounts)
    assert sorted(orm_names["unique"]) == sorted(migration_unique), (
        f"Account UniqueConstraint name 不一致: ORM={orm_names['unique']} migration={migration_unique}"
    )
    assert "uq_accounts_email" in orm_names["unique"]

    # Index (含 create_table 外的 op.create_index)
    migration_index = _get_create_indexes_for_table(upgrade, "accounts")
    assert sorted(orm_names["index"]) == sorted(migration_index), (
        f"Account Index name 不一致: ORM={orm_names['index']} migration={migration_index}"
    )
    assert "ix_accounts_email" in orm_names["index"], f"Account ORM 缺 ix_accounts_email, 实际 {orm_names['index']}"
    assert "ix_accounts_is_active" in orm_names["index"]


def test_account_orm_no_legacy_email_format_constraint_name():
    """DATA-002 regression guard: ORM 不能残留旧名 'email_format'."""
    from src.auth.account_models import Account

    orm_names = _load_orm_constraint_names(Account)
    assert "email_format" not in orm_names["check"], (
        "Account ORM 还残留旧 CheckConstraint name='email_format', 应为 'ck_accounts_email_format'"
    )


def test_account_orm_no_idx_prefix_index_names():
    """DATA-002 regression guard: ORM 不能用 idx_ 前缀 (migration 用 op.f ix_ 前缀)."""
    from src.auth.account_models import Account

    orm_names = _load_orm_constraint_names(Account)
    for name in orm_names["index"]:
        assert not name.startswith("idx_"), f"Account ORM Index '{name}' 用 idx_ 前缀, migration 用 ix_ 前缀 (op.f)"


def test_account_orm_email_column_no_legacy_unique_key():
    """DATA-002 regression guard: email 列不能有 unique=True (会隐式生成 accounts_email_key)."""
    from src.auth.account_models import Account

    email_col = Account.__table__.c.email
    assert email_col.unique is False or email_col.unique is None, (
        "Account.email 列不能设 unique=True, 会生成 SQLAlchemy 自动命名 accounts_email_key, "
        "跟 migration 的 uq_accounts_email 撞名. 应在 __table_args__ 用显式 UniqueConstraint(name='uq_accounts_email')."
    )


# ---- Invite ----


def test_invite_orm_constraints_match_migration():
    """Invite ORM __table_args__ 跟 migration 一致 (DATA-002 修复验证)."""
    from src.auth.account_models import Invite

    orm_names = _load_orm_constraint_names(Invite)
    upgrade = _load_migration_func("20260615_000000_consolidated_pg_init.py", "upgrade")
    create_invites = _get_create_table_for(upgrade, "invites")
    assert create_invites is not None

    # UniqueConstraint
    migration_unique = _get_unique_constraints_in_table(create_invites)
    assert sorted(orm_names["unique"]) == sorted(migration_unique), (
        f"Invite UniqueConstraint name 不一致: ORM={orm_names['unique']} migration={migration_unique}"
    )
    assert "uq_invites_token" in orm_names["unique"]

    # Index
    migration_index = _get_create_indexes_for_table(upgrade, "invites")
    assert sorted(orm_names["index"]) == sorted(migration_index), (
        f"Invite Index name 不一致: ORM={orm_names['index']} migration={migration_index}"
    )
    assert "ix_invites_token" in orm_names["index"]
    assert "ix_invites_email" in orm_names["index"]


def test_invite_orm_token_column_no_legacy_unique_key():
    """Invite.token 列不能有 unique=True (会生成 invites_token_key 撞 uq_invites_token)."""
    from src.auth.account_models import Invite

    token_col = Invite.__table__.c.token
    assert token_col.unique is False or token_col.unique is None, (
        "Invite.token 列不能设 unique=True, 应在 __table_args__ 用显式 UniqueConstraint(name='uq_invites_token')."
    )


# ---- PasswordReset ----


def test_password_reset_orm_constraints_match_migration():
    """PasswordReset ORM __table_args__ 跟 migration 一致."""
    from src.auth.account_models import PasswordReset

    orm_names = _load_orm_constraint_names(PasswordReset)
    upgrade = _load_migration_func("20260615_000000_consolidated_pg_init.py", "upgrade")
    create_pwresets = _get_create_table_for(upgrade, "password_resets")
    assert create_pwresets is not None

    migration_unique = _get_unique_constraints_in_table(create_pwresets)
    assert sorted(orm_names["unique"]) == sorted(migration_unique)
    assert "uq_password_resets_token" in orm_names["unique"]

    migration_index = _get_create_indexes_for_table(upgrade, "password_resets")
    assert sorted(orm_names["index"]) == sorted(migration_index)
    assert "ix_password_resets_token" in orm_names["index"]


def test_password_reset_orm_token_column_no_legacy_unique_key():
    """PasswordReset.token 列不能有 unique=True."""
    from src.auth.account_models import PasswordReset

    token_col = PasswordReset.__table__.c.token
    assert token_col.unique is False or token_col.unique is None, (
        "PasswordReset.token 列不能设 unique=True, 应走显式 UniqueConstraint + 唯一 Index."
    )


# ---- EmailChange ----


def test_email_change_orm_constraints_match_migration():
    """EmailChange ORM __table_args__ 跟 migration 一致 (DATA-002 修复验证).

    email_changes 主表 migration 没 UniqueConstraint (只有 unique Index on token),
    ORM 也不应在 email_changes 上声明 UniqueConstraint.
    """
    from src.auth.account_models import EmailChange

    orm_names = _load_orm_constraint_names(EmailChange)
    upgrade = _load_migration_func("20260617_120000_account_settings.py", "upgrade")

    # email_changes 主表 migration 无 UniqueConstraint
    assert orm_names["unique"] == [], (
        f"EmailChange ORM 不应有 UniqueConstraint (migration 主表也没声明), 实际 {orm_names['unique']}"
    )

    # 校验所有 migration 主索引都在 ORM 里
    migration_index = _get_create_indexes_for_table(upgrade, "email_changes")
    for idx_name in migration_index:
        assert idx_name in orm_names["index"], f"EmailChange ORM 缺 index '{idx_name}', 实际 {orm_names['index']}"
    assert "idx_email_changes_token" in orm_names["index"]
    assert "idx_email_changes_account" in orm_names["index"]


def test_email_change_orm_token_column_no_legacy_unique_key():
    """EmailChange.token 列不能有 unique=True (migration 只用唯一索引)."""
    from src.auth.account_models import EmailChange

    token_col = EmailChange.__table__.c.token
    assert token_col.unique is False or token_col.unique is None, (
        "EmailChange.token 列不能设 unique=True, migration 只声明了 unique Index, 列级 unique 会产生额外 UniqueConstraint 假 diff."
    )


# ---- DeletionRestore ----


def test_deletion_restore_orm_constraints_match_migration():
    """DeletionRestore ORM __table_args__ 跟 migration 一致 (DATA-002 修复验证).

    主表 migration (20260617_120000) 没 UniqueConstraint, 但后续
    20260624 migration 加了 uq_deletion_restores_account_id_used_at, ORM 已声明.
    """
    from src.auth.account_models import DeletionRestore

    orm_names = _load_orm_constraint_names(DeletionRestore)
    upgrade = _load_migration_func("20260617_120000_account_settings.py", "upgrade")

    migration_index = _get_create_indexes_for_table(upgrade, "deletion_restores")
    # 校验所有 migration 主索引都在 ORM 里
    for idx_name in migration_index:
        assert idx_name in orm_names["index"], f"DeletionRestore ORM 缺 index '{idx_name}', 实际 {orm_names['index']}"
    assert "idx_deletion_restores_token" in orm_names["index"]
    assert "idx_deletion_restores_account" in orm_names["index"]


def test_deletion_restore_orm_token_column_no_legacy_unique_key():
    """DeletionRestore.token 列不能有 unique=True."""
    from src.auth.account_models import DeletionRestore

    token_col = DeletionRestore.__table__.c.token
    assert token_col.unique is False or token_col.unique is None, (
        "DeletionRestore.token 列不能设 unique=True, migration 只声明了 unique Index."
    )


def test_deletion_restore_orm_has_used_at_unique_constraint():
    """DeletionRestore ORM 必须含 uq_deletion_restores_account_id_used_at (2026-06-24 migration 加的)."""
    from src.auth.account_models import DeletionRestore

    orm_names = _load_orm_constraint_names(DeletionRestore)
    assert "uq_deletion_restores_account_id_used_at" in orm_names["unique"], (
        f"DeletionRestore ORM 缺 uq_deletion_restores_account_id_used_at, 实际 unique={orm_names['unique']}"
    )

    # migration 也必须真有这个 create_unique_constraint
    upgrade = _load_migration_func("20260624_000000_add_deletion_restore_used_at_unique.py", "upgrade")
    create_uq = _get_create_unique_constraints_for_table(
        upgrade, "deletion_restores", "uq_deletion_restores_account_id_used_at"
    )
    assert create_uq is not None, (
        "migration 缺 create_unique_constraint('uq_deletion_restores_account_id_used_at', ...)"
    )
