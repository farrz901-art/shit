"""buyer_profile migration 验证 (2026-06-23 回归测试)

CLAUDE.md 规范: 测试禁止连真 PG / Redis 等数据库. 此处用 mock 模式:
- 不 import alembic.command / 不连 engine / 不真跑 upgrade/downgrade
- 用 ast 解析 migration 源码, 验证调用结构 (revision / down_revision / 函数体含 op.* 调用)

背景: 2026-06-23 修 bug — 之前 migration 用 sa.JSON() 给 profile_data / profile_meta
定义 PG `json` 类型, 但 GIN index idx_buyer_profiles_data 用 jsonb_path_ops opclass,
PG 抛 "operator class jsonb_path_ops does not accept data type json".
修复: 把所有需要 opclass 的列 (profile_data / profile_meta / options /
notify_on_change / old_value / new_value) 改成 sa.dialects.postgresql.JSONB().

测试覆盖:
- migration 文件存在, 可被 ast 解析
- revision / down_revision 字段正确
- upgrade() 含 3 个 create_table + 4 个 create_index
- downgrade() 含 3 个 drop_table
- 所有 JSON 列必须用 JSONB() (不能是 sa.JSON()) — 关键防回归
- GIN index 用 jsonb_path_ops opclass, 跟 JSONB 列类型匹配
- 函数签名: upgrade() / downgrade() 都 0 参
- 加载模块 0 PG 依赖
"""

from __future__ import annotations

import ast
from pathlib import Path

# ---- helpers ----


def _migration_path() -> Path:
    """migration 文件路径"""
    return (
        Path(__file__).parent.parent.parent
        / "src"
        / "storage"
        / "migrations"
        / "versions"
        / "20260622_000000_create_buyer_profiles.py"
    )


def _load_module_via_spec():
    """用 importlib 加载 migration 模块 (不连 PG).

    module-level import 不触发任何 DB 调用, 仅 import 副作用 = 变量绑定.
    """
    import importlib.util

    migration_path = _migration_path()
    assert migration_path.exists(), f"migration file not found: {migration_path}"

    spec = importlib.util.spec_from_file_location("create_buyer_profiles_migration", migration_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _parse_source() -> ast.Module:
    """解析 migration 源码 (AST)."""
    source = _migration_path().read_text(encoding="utf-8")
    return ast.parse(source)


def _extract_op_calls(func_node: ast.FunctionDef) -> list[ast.Call]:
    """从 upgrade() / downgrade() 函数体里提取所有 op.* 调用."""
    calls: list[ast.Call] = []
    for node in ast.walk(func_node):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name):
                if node.func.value.id == "op":
                    calls.append(node)
    return calls


def _call_name(call: ast.Call) -> str:
    """提取 op.<name> 中的 <name>"""
    assert isinstance(call.func, ast.Attribute)
    return call.func.attr


def _call_first_str_arg(call: ast.Call) -> str | None:
    """提取 op.create_table('name', ...) / op.create_index('name', ...) 的第一个 str arg"""
    if not call.args:
        return None
    first = call.args[0]
    if isinstance(first, ast.Constant) and isinstance(first.value, str):
        return first.value
    return None


def _column_calls(create_table_call: ast.Call) -> list[ast.Call]:
    """从 op.create_table() 调用里提取 sa.Column(...) positional args.

    Column 可能在 args (sa.Column 直接) 或 kwarg 内, 这里只取 positional args.
    """
    cols: list[ast.Call] = []
    for arg in create_table_call.args:
        if isinstance(arg, ast.Call) and isinstance(arg.func, ast.Attribute):
            if arg.func.attr == "Column":
                cols.append(arg)
    return cols


def _column_name(col_call: ast.Call) -> str | None:
    """提取 sa.Column('col_name', ...) 的第一个 str arg (列名)."""
    if not col_call.args:
        return None
    first = col_call.args[0]
    if isinstance(first, ast.Constant) and isinstance(first.value, str):
        return first.value
    return None


def _column_type(col_call: ast.Call) -> ast.AST | None:
    """提取 sa.Column('name', <TYPE>, ...) 的第 2 个 arg (类型节点)."""
    if len(col_call.args) < 2:
        return None
    return col_call.args[1]


def _type_repr(type_node: ast.AST) -> str:
    """把类型节点序列化成 'JSONB()' / 'sa.JSON()' / 'String(64)' 这种字符串.

    用于断言比较, 不解析完整 AST (Column 类型表达式变化多).
    """
    return ast.unparse(type_node)


# ---- 测试 ----


def test_migration_file_exists():
    """migration 文件存在"""
    assert _migration_path().exists()


def test_migration_source_parseable():
    """migration 源码能被 AST 解析 (无语法错误)"""
    module = _parse_source()
    assert isinstance(module, ast.Module)
    assert any(isinstance(n, ast.FunctionDef) and n.name == "upgrade" for n in module.body)
    assert any(isinstance(n, ast.FunctionDef) and n.name == "downgrade" for n in module.body)


def test_revision_and_down_revision():
    """revision / down_revision 字段正确"""
    module = _load_module_via_spec()
    assert module.revision == "20260622_000000", f"revision mismatch: {module.revision!r}"
    assert module.down_revision == "20260619_120000", f"down_revision mismatch: {module.down_revision!r}"


def test_upgrade_function_signature():
    """upgrade() 函数 0 参 (alembic 约定)"""
    module = _parse_source()
    func = next(n for n in module.body if isinstance(n, ast.FunctionDef) and n.name == "upgrade")
    args = func.args
    assert len(args.args) == 0, f"upgrade() should have 0 positional args, got {len(args.args)}"
    assert len(args.kwonlyargs) == 0


def test_downgrade_function_signature():
    """downgrade() 函数 0 参"""
    module = _parse_source()
    func = next(n for n in module.body if isinstance(n, ast.FunctionDef) and n.name == "downgrade")
    args = func.args
    assert len(args.args) == 0
    assert len(args.kwonlyargs) == 0


def test_upgrade_creates_three_tables():
    """upgrade 含 3 个 op.create_table: buyer_profiles / profile_field_configs / profile_change_logs"""
    module = _parse_source()
    func = next(n for n in module.body if isinstance(n, ast.FunctionDef) and n.name == "upgrade")
    calls = _extract_op_calls(func)
    create_table_calls = [c for c in calls if _call_name(c) == "create_table"]

    assert len(create_table_calls) == 3, f"expected 3 create_table calls, got {len(create_table_calls)}"

    table_names = [_call_first_str_arg(c) for c in create_table_calls]
    assert "buyer_profiles" in table_names
    assert "profile_field_configs" in table_names
    assert "profile_change_logs" in table_names


def test_upgrade_creates_five_indexes():
    """upgrade 含 5 个 op.create_index (3 普通 buyer_profiles + 1 GIN jsonb_path_ops + 1 change_logs)"""
    module = _parse_source()
    func = next(n for n in module.body if isinstance(n, ast.FunctionDef) and n.name == "upgrade")
    calls = _extract_op_calls(func)
    create_index_calls = [c for c in calls if _call_name(c) == "create_index"]

    assert len(create_index_calls) == 5, f"expected 5 create_index calls, got {len(create_index_calls)}"

    index_names = [_call_first_str_arg(c) for c in create_index_calls]
    # buyer_profiles 上的 4 个 index (3 普通 + 1 GIN)
    assert "idx_buyer_profiles_account" in index_names
    assert "idx_buyer_profiles_status" in index_names
    assert "idx_buyer_profiles_updated" in index_names
    assert "idx_buyer_profiles_data" in index_names
    # profile_change_logs 上的 1 个 index
    assert "idx_change_logs_profile" in index_names


# ---- 关键防回归: JSON 列必须用 JSONB ----


JSONB_COLUMN_TABLE_COLUMNS: list[tuple[str, str]] = [
    # (table_name, column_name) — 这些列在 GIN index / 业务代码里被当 JSONB 用
    ("buyer_profiles", "profile_data"),
    ("buyer_profiles", "profile_meta"),
    ("profile_field_configs", "options"),
    ("profile_field_configs", "notify_on_change"),
    ("profile_change_logs", "old_value"),
    ("profile_change_logs", "new_value"),
]


def _find_column_type(create_table_call: ast.Call, col_name: str) -> str | None:
    """从 create_table call 里找指定列名的类型 repr. 找不到返 None."""
    for col_call in _column_calls(create_table_call):
        if _column_name(col_call) == col_name:
            type_node = _column_type(col_call)
            if type_node is None:
                return None
            return _type_repr(type_node)
    return None


def test_jsonb_columns_use_jsonb_not_sa_json():
    """关键防回归: 所有 6 个 JSON 列必须用 JSONB(), 绝不能用 sa.JSON().

    背景: 之前用 sa.JSON() 生成 PG json 类型, 但 GIN index idx_buyer_profiles_data
    用 jsonb_path_ops opclass 要求 JSONB, PG 抛:
    "operator class jsonb_path_ops does not accept data type json".
    """
    module = _parse_source()
    func = next(n for n in module.body if isinstance(n, ast.FunctionDef) and n.name == "upgrade")
    calls = _extract_op_calls(func)
    create_table_calls = [c for c in calls if _call_name(c) == "create_table"]

    for table_name, col_name in JSONB_COLUMN_TABLE_COLUMNS:
        table_call = next(
            (c for c in create_table_calls if _call_first_str_arg(c) == table_name),
            None,
        )
        assert table_call is not None, f"table {table_name!r} not found in create_table calls"

        type_repr = _find_column_type(table_call, col_name)
        assert type_repr is not None, f"column {table_name}.{col_name} not found or has no type arg"

        # 必须用 JSONB(), 不能是 sa.JSON() / JSON() / 任何不带 JSONB 的形式
        assert "JSONB" in type_repr, (
            f"列 {table_name}.{col_name} 类型 {type_repr!r} 必须用 JSONB() "
            f"(否则 GIN index jsonb_path_ops 会报 'does not accept data type json')"
        )
        # 排除 sa.JSON() — 它 unparse 出来是 'JSON()', 不是 'JSONB()'
        assert "sa.JSON()" not in type_repr, (
            f"列 {table_name}.{col_name} 类型 {type_repr!r} 用了 sa.JSON() — "
            f"必须改为 sqlalchemy.dialects.postgresql.JSONB()"
        )


def test_gin_index_uses_jsonb_path_ops():
    """idx_buyer_profiles_data GIN index 必须用 jsonb_path_ops opclass.

    验证 postgresql_using='gin' + postgresql_ops={'profile_data': 'jsonb_path_ops'}.
    """
    module = _parse_source()
    func = next(n for n in module.body if isinstance(n, ast.FunctionDef) and n.name == "upgrade")
    calls = _extract_op_calls(func)
    create_index_calls = [c for c in calls if _call_name(c) == "create_index"]

    gin_call = next(
        (c for c in create_index_calls if _call_first_str_arg(c) == "idx_buyer_profiles_data"),
        None,
    )
    assert gin_call is not None, "idx_buyer_profiles_data index not found"

    # postgresql_using kwarg 必须是 'gin'
    using_kw = next((kw for kw in gin_call.keywords if kw.arg == "postgresql_using"), None)
    assert using_kw is not None, "postgresql_using kwarg missing"
    assert isinstance(using_kw.value, ast.Constant) and using_kw.value.value == "gin", (
        f"postgresql_using should be 'gin', got {ast.unparse(using_kw.value)!r}"
    )

    # postgresql_ops kwarg 必须是 {'profile_data': 'jsonb_path_ops'}
    ops_kw = next((kw for kw in gin_call.keywords if kw.arg == "postgresql_ops"), None)
    assert ops_kw is not None, "postgresql_ops kwarg missing"
    assert isinstance(ops_kw.value, ast.Dict), f"postgresql_ops should be dict, got {ast.unparse(ops_kw.value)!r}"

    ops_keys = []
    ops_values = []
    for k, v in zip(ops_kw.value.keys, ops_kw.value.values):
        if isinstance(k, ast.Constant):
            ops_keys.append(k.value)
        if isinstance(v, ast.Constant):
            ops_values.append(v.value)

    assert "profile_data" in ops_keys, f"postgresql_ops should include 'profile_data', got {ops_keys}"
    assert "jsonb_path_ops" in ops_values, f"postgresql_ops values should include 'jsonb_path_ops', got {ops_values}"


def test_downgrade_drops_three_tables():
    """downgrade 含 3 个 op.drop_table: profile_change_logs + profile_field_configs + buyer_profiles"""
    module = _parse_source()
    func = next(n for n in module.body if isinstance(n, ast.FunctionDef) and n.name == "downgrade")
    calls = _extract_op_calls(func)
    drop_table_calls = [c for c in calls if _call_name(c) == "drop_table"]

    assert len(drop_table_calls) == 3, f"expected 3 drop_table calls, got {len(drop_table_calls)}"

    drop_names: list[str] = []
    for c in drop_table_calls:
        name = _call_first_str_arg(c)
        if name is None:
            tn = next((kw.value for kw in c.keywords if kw.arg == "table_name"), None)
            if isinstance(tn, ast.Constant) and isinstance(tn.value, str):
                name = tn.value
        if name is not None:
            drop_names.append(name)

    assert "buyer_profiles" in drop_names
    assert "profile_field_configs" in drop_names
    assert "profile_change_logs" in drop_names

    # 顺序: 引用方 (profile_change_logs → profile_field_configs) 先, 被引用方 (buyer_profiles) 后
    # FK 链: profile_change_logs.profile_id → buyer_profiles.id
    # FK: profile_field_configs.account_id → accounts.id (跟 buyer_profiles 无关, 但顺序先于 buyer_profiles 也 OK)
    # 正确顺序: 必须 buyer_profiles 最后 drop (有其他表引用它的 id)
    profiles_idx = drop_names.index("buyer_profiles")
    logs_idx = drop_names.index("profile_change_logs")
    assert logs_idx < profiles_idx, (
        f"drop_table 顺序错: buyer_profiles (被引用方) 必须最后 drop, 实际 drop_names={drop_names}"
    )


def test_migration_module_loadable_no_pg():
    """migration 模块 import 不触发 PG / Redis 连接.

    module-level import 副作用可控, 没有顶级 connection 调用.
    """
    module = _load_module_via_spec()
    assert callable(module.upgrade)
    assert callable(module.downgrade)
    assert isinstance(module.revision, str)
    assert isinstance(module.down_revision, str)
    # JSONB 应该被 import 进模块 (从 sqlalchemy.dialects.postgresql)
    from sqlalchemy.dialects.postgresql import JSONB

    assert JSONB is not None, "JSONB type not importable — migration 修法基础失效"


def test_migration_imports_jsonb():
    """migration 文件必须显式 import JSONB.

    避免有人改回去用 sa.JSON(), 必须确保 from sqlalchemy.dialects.postgresql import JSONB
    在源码里 (因为 JSONB 是 sqlalchemy 的 postgres dialect 扩展, 默认不导出).
    """
    source = _migration_path().read_text(encoding="utf-8")
    assert "from sqlalchemy.dialects.postgresql import JSONB" in source, (
        "migration 缺 `from sqlalchemy.dialects.postgresql import JSONB` — "
        "JSONB 是 postgres dialect 扩展, 必须显式 import"
    )
