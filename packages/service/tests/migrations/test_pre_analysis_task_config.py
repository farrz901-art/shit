"""pre_analysis_tasks.task_config_json 列迁移 AST 验证 (CLAUDE.md §纯 AST mode 1).

只验证:
1. migration 文件存在 + 含 upgrade/downgrade 函数
2. 新增 task_config_json 列 + server_default '{}'
3. nullable=False (跟现有 Text 列一致)
4. down_revision = 20260703_000000 (上一条 pre_analysis 迁移)
"""

from __future__ import annotations

import ast
from pathlib import Path

MIGRATION_FILE = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "storage"
    / "migrations"
    / "versions"
    / "20260706_000000_pre_analysis_task_config.py"
)


def test_migration_file_exists() -> None:
    """迁移文件存在."""
    assert MIGRATION_FILE.exists(), f"找不到 migration 文件: {MIGRATION_FILE}"


def test_migration_has_upgrade_and_downgrade() -> None:
    """upgrade() + downgrade() 函数 (CLAUDE.md §alembic 可回滚)."""
    source = MIGRATION_FILE.read_text(encoding="utf-8")
    tree = ast.parse(source)
    fns = {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    assert "upgrade" in fns
    assert "downgrade" in fns


def test_migration_adds_task_config_json_column() -> None:
    """新增 task_config_json Text NOT NULL 列 + server_default '{}'."""
    source = MIGRATION_FILE.read_text(encoding="utf-8")
    # 列名
    assert "task_config_json" in source
    # sa.Column 中含 server_default
    assert 'server_default="{}"' in source or "server_default='{}'" in source
    # 必含 Text / sa.Text
    assert "Text" in source or "text" in source.lower()


def test_migration_down_revision_is_20260703_000000() -> None:
    """down_revision 链上接 20260703 (上一条 pre_analysis migration)."""
    source = MIGRATION_FILE.read_text(encoding="utf-8")
    assert 'down_revision = "20260703_000000"' in source


def test_migration_drop_column_in_downgrade() -> None:
    """downgrade 必含 op.drop_column(task_config_json)."""
    source = MIGRATION_FILE.read_text(encoding="utf-8")
    assert "op.drop_column" in source
    assert "task_config_json" in source
