"""20260623 migration downgrade 验证 (DATA-001 回归测试)

CLAUDE.md 规范: 测试禁止连真 PG / Redis 等数据库. 此处用 ast 解析
migration 源码, 验证 downgrade 函数结构 + 防 DATA-001 bug 回归.

背景 DATA-001:
- 2026-06-23 写了 20260623_000000_drop_account_id_from_field_configs.py
- upgrade 把 profile_field_configs.account_id 列删掉 (全局模板, 不按账号隔离)
- 原 downgrade 用 server_default="0" 加 account_id 列, 然后 create_unique_constraint
  UNIQUE(account_id, code). server_default="0" 让所有现有行落同一 account_id=0,
  再加 UNIQUE(account_id, code) 必冲突 → downgrade 必失败.
- 修复策略 (本测试验证): 加列 nullable=True, 不回填 (account_id 留 NULL),
  FK 用 ondelete=SET NULL, 不重建 UNIQUE 约束 (PG UNIQUE 不约束 NULL).

测试覆盖:
- migration 文件存在, 可被 ast 解析
- revision / down_revision 字段正确 (链在 20260622 之后)
- upgrade() 含: drop_constraint FK + drop_constraint UNIQUE + drop_column + create_unique_constraint
- downgrade() 不含 server_default="0" (DATA-001 防回归关键)
- downgrade() 加列 nullable=True (关键: 不能是 nullable=False)
- downgrade() 加 FK 含 ondelete="SET NULL"
- downgrade() 不重建 UNIQUE(account_id, code) (NULL 允许多行)
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
        / "20260623_000000_drop_account_id_from_field_configs.py"
    )


def _load_module_via_spec():
    """用 importlib.util 加载 migration 模块 (不连 PG).

    module-level import 不触发任何 DB 调用, 仅 import 副作用 = 变量绑定.
    """
    import importlib.util

    migration_path = _migration_path()
    assert migration_path.exists(), f"migration file not found: {migration_path}"

    spec = importlib.util.spec_from_file_location("drop_account_id_from_field_configs_migration", migration_path)
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


def _call_kwarg(call: ast.Call, key: str) -> ast.AST | None:
    """提取 op.drop_index(..., table_name='foo') 的关键字参数"""
    for kw in call.keywords:
        if kw.arg == key:
            return kw.value
    return None


def _find_call_by_name(calls: list[ast.Call], name: str) -> ast.Call | None:
    """在 op.* 调用列表里找第一个 name 匹配的 call."""
    return next((c for c in calls if _call_name(c) == name), None)


def _add_column_target_table(add_column_call: ast.Call) -> str | None:
    """提取 op.add_column('table', ...) 的表名"""
    return _call_first_str_arg(add_column_call)


def _add_column_column_node(add_column_call: ast.Call) -> ast.Call | None:
    """提取 op.add_column('table', sa.Column(...)) 里的 sa.Column(...) 节点."""
    for arg in add_column_call.args:
        if isinstance(arg, ast.Call) and isinstance(arg.func, ast.Attribute):
            if arg.func.attr == "Column":
                return arg
    return None


def _column_kwargs(col_call: ast.Call, key: str) -> ast.AST | None:
    """提取 sa.Column(name, type, nullable=False, server_default='0') 的某个 kwarg."""
    for kw in col_call.keywords:
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
    """revision / down_revision 字段正确.

    revision = "20260623_000000"
    down_revision = "20260622_000000" (上一个 head: create buyer_profiles)
    """
    module = _load_module_via_spec()
    assert module.revision == "20260623_000000", f"revision mismatch: {module.revision!r}"
    assert module.down_revision == "20260622_000000", f"down_revision mismatch: {module.down_revision!r}"


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


# ---- upgrade 验证 ----


def test_upgrade_drops_fk_and_unique_and_column():
    """upgrade 含: drop_constraint FK + drop_constraint UNIQUE(account_id,code) + drop_column + create_unique_constraint(code)

    顺序: 先 drop FK, 再 drop UNIQUE, 再 drop column (PG 依赖顺序).
    """
    module = _parse_source()
    func = next(n for n in module.body if isinstance(n, ast.FunctionDef) and n.name == "upgrade")
    calls = _extract_op_calls(func)

    drop_constraint_calls = [c for c in calls if _call_name(c) == "drop_constraint"]
    assert len(drop_constraint_calls) == 2, (
        f"expected 2 drop_constraint calls (FK + UNIQUE), got {len(drop_constraint_calls)}"
    )

    # 验证 drop 的约束名: uq_field_configs_account_code + fk_field_configs_account
    drop_constraint_names = [_call_first_str_arg(c) for c in drop_constraint_calls]
    assert "uq_field_configs_account_code" in drop_constraint_names
    assert "fk_field_configs_account" in drop_constraint_names

    drop_column_calls = [c for c in calls if _call_name(c) == "drop_column"]
    assert len(drop_column_calls) == 1, f"expected 1 drop_column call, got {len(drop_column_calls)}"

    create_unique_calls = [c for c in calls if _call_name(c) == "create_unique_constraint"]
    assert len(create_unique_calls) == 1, (
        f"expected 1 create_unique_constraint call (new UNIQUE(code)), got {len(create_unique_calls)}"
    )
    new_unique = create_unique_calls[0]
    assert _call_first_str_arg(new_unique) == "uq_field_configs_code"


# ---- DATA-001 防回归核心 ----


def test_downgrade_does_not_use_server_default_zero():
    """DATA-001 防回归: downgrade 不能用 server_default='0' 加 account_id 列.

    原来 bug: server_default='0' 让所有现有行落同一 account_id=0,
    再加 UNIQUE(account_id, code) 必冲突.
    """
    module = _parse_source()
    func = next(n for n in module.body if isinstance(n, ast.FunctionDef) and n.name == "downgrade")
    calls = _extract_op_calls(func)

    add_column_calls = [c for c in calls if _call_name(c) == "add_column"]
    assert len(add_column_calls) == 1, f"expected 1 add_column call, got {len(add_column_calls)}"

    col_node = _add_column_column_node(add_column_calls[0])
    assert col_node is not None, "sa.Column(...) not found in op.add_column(...)"

    # 必须没有 server_default kwarg (这是 bug 根因)
    server_default = _column_kwargs(col_node, "server_default")
    assert server_default is None, (
        f"DATA-001 回归: sa.Column(..., server_default={ast.unparse(server_default)!r}) "
        f"会让所有现有行落同一 account_id, 跟 UNIQUE(account_id, code) 冲突. "
        f"必须 nullable=True 且不设 server_default."
    )


def test_downgrade_add_column_nullable_true():
    """DATA-001 防回归: downgrade 加 account_id 列必须 nullable=True.

    nullable=False + server_default='0' 是原 bug 根因.
    """
    module = _parse_source()
    func = next(n for n in module.body if isinstance(n, ast.FunctionDef) and n.name == "downgrade")
    calls = _extract_op_calls(func)

    add_column_call = _find_call_by_name(calls, "add_column")
    assert add_column_call is not None, "op.add_column(...) not found in downgrade"

    col_node = _add_column_column_node(add_column_call)
    assert col_node is not None, "sa.Column(...) not found in op.add_column(...)"

    nullable_kw = _column_kwargs(col_node, "nullable")
    assert nullable_kw is not None, "sa.Column(...) 缺 nullable kwarg — 默认 nullable=True 但应显式标注"

    # nullable 必须为 True (literal True, 不是 False)
    assert isinstance(nullable_kw, ast.Constant), (
        f"nullable kwarg 必须是字面量 True/False, got {ast.unparse(nullable_kw)!r}"
    )
    assert nullable_kw.value is True, (
        "DATA-001 回归: account_id 列 nullable=False 会强制回填数据, 必须 nullable=True 让现有行 account_id=NULL"
    )


def test_downgrade_fk_uses_set_null():
    """downgrade 加 FK 用 ondelete='SET NULL': account 删时 account_id 变 NULL."""
    module = _parse_source()
    func = next(n for n in module.body if isinstance(n, ast.FunctionDef) and n.name == "downgrade")
    calls = _extract_op_calls(func)

    create_fk_call = _find_call_by_name(calls, "create_foreign_key")
    assert create_fk_call is not None, "op.create_foreign_key(...) not found in downgrade"

    ondelete_kw = _call_kwarg(create_fk_call, "ondelete")
    assert ondelete_kw is not None, (
        "op.create_foreign_key 缺 ondelete kwarg — 应为 'SET NULL' 让 account 删时 account_id 变 NULL"
    )
    assert isinstance(ondelete_kw, ast.Constant), f"ondelete kwarg 必须是字面量, got {ast.unparse(ondelete_kw)!r}"
    assert ondelete_kw.value == "SET NULL", (
        f"ondelete 应为 'SET NULL', got {ondelete_kw.value!r}. "
        f"业务侧需求: account 删时 profile_field_config.account_id 变 NULL, 保留 field_config 记录."
    )


def test_downgrade_does_not_recreate_unique_constraint():
    """downgrade 不重建 UNIQUE(account_id, code) — PG UNIQUE 不约束 NULL, 多行 NULL 允许.

    重建会触发 DATA-001 同样的 bug (server_default='0' → 所有行同 account_id → 冲突).
    """
    module = _parse_source()
    func = next(n for n in module.body if isinstance(n, ast.FunctionDef) and n.name == "downgrade")
    calls = _extract_op_calls(func)

    create_unique_calls = [c for c in calls if _call_name(c) == "create_unique_constraint"]
    assert len(create_unique_calls) == 0, (
        f"DATA-001 回归: downgrade 不应重建 UNIQUE 约束 (会触发同样的 UNIQUE 冲突), "
        f"got {len(create_unique_calls)} create_unique_constraint calls"
    )


def test_downgrade_drops_existing_unique_code():
    """downgrade 必须先 drop 现有的 UNIQUE(code) 才能加回 account_id 列.

    因为 20260623 upgrade 把 UNIQUE(account_id, code) 替换成 UNIQUE(code),
    downgrade 必须先 drop UNIQUE(code), 才能恢复原 schema 行为.
    """
    module = _parse_source()
    func = next(n for n in module.body if isinstance(n, ast.FunctionDef) and n.name == "downgrade")
    calls = _extract_op_calls(func)

    drop_constraint_calls = [c for c in calls if _call_name(c) == "drop_constraint"]
    assert any(_call_first_str_arg(c) == "uq_field_configs_code" for c in drop_constraint_calls), (
        "downgrade 必须 drop UNIQUE(code) 约束 (uq_field_configs_code), 否则 add_column account_id 后 schema 不一致"
    )


def test_downgrade_adds_account_id_column():
    """downgrade 必须加回 account_id 列 (profile_field_configs.account_id)."""
    module = _parse_source()
    func = next(n for n in module.body if isinstance(n, ast.FunctionDef) and n.name == "downgrade")
    calls = _extract_op_calls(func)

    add_column_call = _find_call_by_name(calls, "add_column")
    assert add_column_call is not None, "op.add_column(...) not found in downgrade"

    assert _add_column_target_table(add_column_call) == "profile_field_configs", (
        f"add_column 表名应为 'profile_field_configs', got {_add_column_target_table(add_column_call)!r}"
    )

    col_node = _add_column_column_node(add_column_call)
    assert col_node is not None
    # sa.Column 第一个 positional arg 是列名
    first = col_node.args[0]
    assert isinstance(first, ast.Constant) and isinstance(first.value, str)
    assert first.value == "account_id", f"加的列名应为 'account_id', got {first.value!r}"


def test_downgrade_creates_fk_to_accounts():
    """downgrade 加 FK: profile_field_configs.account_id → accounts.id."""
    module = _parse_source()
    func = next(n for n in module.body if isinstance(n, ast.FunctionDef) and n.name == "downgrade")
    calls = _extract_op_calls(func)

    create_fk_call = _find_call_by_name(calls, "create_foreign_key")
    assert create_fk_call is not None

    # 约束名 / 表名 / 引用表 验证
    assert _call_first_str_arg(create_fk_call) == "fk_field_configs_account"
    # 第 2 个 positional arg 是 source table
    assert isinstance(create_fk_call.args[1], ast.Constant)
    assert create_fk_call.args[1].value == "profile_field_configs"
    # 第 3 个 positional arg 是 referent table
    assert isinstance(create_fk_call.args[2], ast.Constant)
    assert create_fk_call.args[2].value == "accounts"


def test_migration_module_loadable_no_pg():
    """migration 模块 import 不触发 PG / Redis 连接."""
    module = _load_module_via_spec()
    assert callable(module.upgrade)
    assert callable(module.downgrade)
    assert isinstance(module.revision, str)
    assert isinstance(module.down_revision, str)


def test_migration_docstring_mentions_data_001():
    """migration docstring 应提到 DATA-001 + 防回归, 帮 reviewer 理解来龙去脉."""
    source = _migration_path().read_text(encoding="utf-8")
    assert "DATA-001" in source, "migration docstring 应明确提到 DATA-001 bug + 修复策略, 帮 reviewer 理解"
    assert "server_default" in source, "migration docstring 应解释 server_default='0' 是 DATA-001 bug 根因"
