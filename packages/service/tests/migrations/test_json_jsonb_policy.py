"""禁止新增 sa.JSON() — 必须用 JSONB (json-jsonb spec Task C1).

测试模式 1 (mock, AST parse): 0 PG 依赖.

历史白名单 = 1 个 migration (2026-06-15 consolidated_pg_init).
2026-06-26 migration 已把这 5 列迁到 JSONB, 白名单按理应清空, 但保留作历史档案
(白名单文件本身已经把 sa.JSON 改成 JSONB 不是再创建 — 这里防的是新引入).

跟 tests/buyer_profile/test_migration.py 同款 AST 风格.
"""

from __future__ import annotations

import ast
from pathlib import Path

# 历史白名单 (这些文件曾经引入过 sa.JSON, 不阻止留作历史档案).
# 注意: 这些文件本身不应再含 sa.JSON 调用 — 白名单只表示"扫到 ast.Call sa.JSON 不报警".
# 但实际上历史 migration 已经凝固, 不再改; 列在白名单里只是表明"这是历史, 任何新行都禁止".
LEGACY_ALLOWLIST: set[str] = {
    "20260615_000000_consolidated_pg_init.py",
}


def _migration_dir() -> Path:
    return Path(__file__).parent.parent.parent / "src" / "storage" / "migrations" / "versions"


def _find_sa_json_calls(tree: ast.Module) -> list[ast.Call]:
    """提取 AST 里所有 `sa.JSON()` / `sqlalchemy.JSON()` 调用."""
    found: list[ast.Call] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        # sa.JSON() or sqlalchemy.JSON()
        if isinstance(func, ast.Attribute) and func.attr == "JSON":
            if isinstance(func.value, ast.Name) and func.value.id in ("sa", "sqlalchemy"):
                found.append(node)
    return found


def test_no_new_sa_json_in_migrations():
    """禁止新 migration 用 sa.JSON()."""
    migration_dir = _migration_dir()
    assert migration_dir.exists(), f"migration dir 不存在: {migration_dir}"

    violations: list[str] = []
    for py in migration_dir.glob("*.py"):
        if py.name == "__init__.py" or py.name in LEGACY_ALLOWLIST:
            continue
        source = py.read_text(encoding="utf-8")
        tree = ast.parse(source)
        calls = _find_sa_json_calls(tree)
        for call in calls:
            violations.append(f"{py.name}:{call.lineno} 用了 sa.JSON() — 必须用 JSONB")

    assert not violations, "\n".join(violations) + "\n\n修法: from sqlalchemy.dialects.postgresql import JSONB"


def test_legacy_allowlist_files_exist():
    """白名单文件存在 (防写错文件名)."""
    migration_dir = _migration_dir()
    for fname in LEGACY_ALLOWLIST:
        assert (migration_dir / fname).exists(), f"白名单文件不存在: {fname}"
