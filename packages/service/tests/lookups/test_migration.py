"""migration 验证 (2026-06-19 lookup spec Task 1)

CLAUDE.md 规范: 测试禁止连真 PG / Redis 等数据库. 此处用 mock 模式:
- 不 import alembic.command / 不连 engine / 不真跑 upgrade/downgrade
- 用 ast 解析 migration 源码, 验证调用结构 (revision / down_revision / 函数体含 op.* 调用)

测试覆盖:
- migration 文件存在, 可被 ast 解析
- revision / down_revision 字段正确
- upgrade() 含 2 个 create_table + 3 个 create_index
- downgrade() 含 2 个 drop_table + 3 个 drop_index
- 索引名 / 表名 / UNIQUE 约束 / FK CASCADE 都跟 spec §3.1-3.2 一致
- partial index 用 is_active=true WHERE 子句
- 函数签名: upgrade() / downgrade() 都 0 参 (alembic 约定)
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
        / "20260619_120000_create_dictionary_tables.py"
    )


def _load_module_via_spec():
    """用 importlib 加载 migration 模块 (不连 PG).

    module-level import 不触发任何 DB 调用, 仅 import 副作用 = 变量绑定.
    """
    import importlib.util

    migration_path = _migration_path()
    assert migration_path.exists(), f"migration file not found: {migration_path}"

    spec = importlib.util.spec_from_file_location("create_dictionary_tables_migration", migration_path)
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
            # op.create_table(...) / op.create_index(...) 形式
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


def _call_kwarg(call: ast.Call, key: str) -> ast.AST | None:
    """提取 op.drop_index(..., table_name='foo') 的关键字参数"""
    for kw in call.keywords:
        if kw.arg == key:
            return kw.value
    return None


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
    """revision / down_revision 字段符合 spec.

    spec 期望:
    - revision = "20260619_120000"
    - down_revision = "20260619_000000" (当前 head: chat_soft_delete)
    """
    module = _load_module_via_spec()
    assert module.revision == "20260619_120000", f"revision mismatch: {module.revision!r}"
    assert module.down_revision == "20260619_000000", f"down_revision mismatch: {module.down_revision!r}"


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


def test_upgrade_creates_two_tables():
    """upgrade 含 2 个 op.create_table: dictionaries + dictionary_items"""
    module = _parse_source()
    func = next(n for n in module.body if isinstance(n, ast.FunctionDef) and n.name == "upgrade")
    calls = _extract_op_calls(func)
    create_table_calls = [c for c in calls if _call_name(c) == "create_table"]

    assert len(create_table_calls) == 2, f"expected 2 create_table calls, got {len(create_table_calls)}"

    table_names = [_call_first_str_arg(c) for c in create_table_calls]
    assert "dictionaries" in table_names
    assert "dictionary_items" in table_names


def test_upgrade_creates_three_indexes():
    """upgrade 含 3 个 op.create_index, 跟 spec §3.2 一致"""
    module = _parse_source()
    func = next(n for n in module.body if isinstance(n, ast.FunctionDef) and n.name == "upgrade")
    calls = _extract_op_calls(func)
    create_index_calls = [c for c in calls if _call_name(c) == "create_index"]

    assert len(create_index_calls) == 3, f"expected 3 create_index calls, got {len(create_index_calls)}"

    index_names = [_call_first_str_arg(c) for c in create_index_calls]
    # spec §3.2 的 3 个索引名 (顺序不强求, 但必须全部出现)
    assert "ix_dictionaries_is_active" in index_names
    assert "ix_dictionary_items_dict_code_is_active_sort" in index_names
    assert "ix_dictionary_items_dict_code_key_active" in index_names


def test_upgrade_dictionary_items_table_has_unique_constraint():
    """dictionary_items 表含 UNIQUE(dict_code, key) 约束

    migration 里 sa.UniqueConstraint("dict_code", "key", name="...") 是
    op.create_table() 的 positional arg (不是 kwarg).
    """
    module = _parse_source()
    func = next(n for n in module.body if isinstance(n, ast.FunctionDef) and n.name == "upgrade")
    calls = _extract_op_calls(func)
    create_table_calls = [c for c in calls if _call_name(c) == "create_table"]

    items_call = next(c for c in create_table_calls if _call_first_str_arg(c) == "dictionary_items")

    # 在 positional args 里找 sa.UniqueConstraint("dict_code", "key", ...)
    found_unique = False
    for arg in items_call.args:
        # sa.UniqueConstraint(...) 形式
        if isinstance(arg, ast.Call) and isinstance(arg.func, ast.Attribute):
            if arg.func.attr == "UniqueConstraint":
                arg_names = [a.value for a in arg.args if isinstance(a, ast.Constant) and isinstance(a.value, str)]
                if "dict_code" in arg_names and "key" in arg_names:
                    found_unique = True
                    break

    assert found_unique, (
        "sa.UniqueConstraint('dict_code', 'key', ...) not found in "
        "create_table('dictionary_items', ...) positional args"
    )


def test_upgrade_dictionary_items_table_has_fk_cascade():
    """dictionary_items.dict_code FK → dictionaries.code ON DELETE CASCADE.

    通过源码关键字检查 (因为 Column(ForeignKey(...)) 在 AST 里嵌套较深).
    """
    source = _migration_path().read_text(encoding="utf-8")
    assert "ForeignKey" in source, "ForeignKey not found"
    assert "dictionaries.code" in source, "dictionaries.code reference not found"
    assert "ondelete=" in source and "CASCADE" in source, "FK ON DELETE CASCADE not configured"


def test_upgrade_partial_index_uses_is_active_where():
    """partial index 用 postgresql_where=is_active=true WHERE 子句"""
    module = _parse_source()
    func = next(n for n in module.body if isinstance(n, ast.FunctionDef) and n.name == "upgrade")
    calls = _extract_op_calls(func)
    create_index_calls = [c for c in calls if _call_name(c) == "create_index"]

    # 找 ix_dictionary_items_dict_code_key_active 这个索引
    partial_call = next(
        (c for c in create_index_calls if _call_first_str_arg(c) == "ix_dictionary_items_dict_code_key_active"),
        None,
    )
    assert partial_call is not None

    # 必须含 postgresql_where 关键字参数
    where_arg = _call_kwarg(partial_call, "postgresql_where")
    assert where_arg is not None, "postgresql_where kwarg missing"

    # 验证是 sa.text("is_active = true")
    assert isinstance(where_arg, ast.Call)
    assert isinstance(where_arg.func, ast.Attribute)
    assert where_arg.func.attr == "text"
    assert where_arg.args and isinstance(where_arg.args[0], ast.Constant)
    assert isinstance(where_arg.args[0].value, str)
    assert "is_active" in where_arg.args[0].value.lower()


def test_downgrade_drops_two_tables():
    """downgrade 含 2 个 op.drop_table: dictionary_items + dictionaries (items 先)

    migration 里 op.drop_table("table_name") 是 positional arg 形式,
    op.drop_table(table_name="table_name") 也都支持, 这里两种都兼容.
    """
    module = _parse_source()
    func = next(n for n in module.body if isinstance(n, ast.FunctionDef) and n.name == "downgrade")
    calls = _extract_op_calls(func)
    drop_table_calls = [c for c in calls if _call_name(c) == "drop_table"]

    assert len(drop_table_calls) == 2, f"expected 2 drop_table calls, got {len(drop_table_calls)}"

    # 提取表名: 优先 positional[0], 退化到 table_name kwarg
    drop_names: list[str] = []
    for c in drop_table_calls:
        name = _call_first_str_arg(c)
        if name is None:
            tn = _call_kwarg(c, "table_name")
            if isinstance(tn, ast.Constant) and isinstance(tn.value, str):
                name = tn.value
        if name is not None:
            drop_names.append(name)

    assert "dictionary_items" in drop_names
    assert "dictionaries" in drop_names

    # 顺序: items 先, dictionaries 后 (FK 反向)
    items_idx = drop_names.index("dictionary_items")
    dicts_idx = drop_names.index("dictionaries")
    assert items_idx < dicts_idx, f"drop_table order wrong: items={items_idx}, dicts={dicts_idx}"


def test_downgrade_drops_three_indexes():
    """downgrade 含 3 个 op.drop_index (跟 3 个 create_index 对应)"""
    module = _parse_source()
    func = next(n for n in module.body if isinstance(n, ast.FunctionDef) and n.name == "downgrade")
    calls = _extract_op_calls(func)
    drop_index_calls = [c for c in calls if _call_name(c) == "drop_index"]

    assert len(drop_index_calls) == 3, f"expected 3 drop_index calls, got {len(drop_index_calls)}"

    drop_names = [_call_first_str_arg(c) for c in drop_index_calls]
    assert "ix_dictionary_items_dict_code_key_active" in drop_names
    assert "ix_dictionary_items_dict_code_is_active_sort" in drop_names
    assert "ix_dictionaries_is_active" in drop_names


def test_migration_module_loadable_no_pg():
    """migration 模块 import 不触发 PG / Redis 连接.

    spec 边界: 模块加载 (含 import sqlalchemy / from alembic import op) 副作用可控.
    没有 import 触发 DB connect, 因为 migration 文件本身没有顶级 connection 调用.
    """
    module = _load_module_via_spec()
    assert callable(module.upgrade)
    assert callable(module.downgrade)
    # revision / down_revision 都是 string
    assert isinstance(module.revision, str)
    assert isinstance(module.down_revision, str)
