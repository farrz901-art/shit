"""pre_analysis_tasks 迁移 AST 验证 + SQL 文本 (CLAUDE.md 禁真 PG, mode 1)

只验证:
1. migration 文件存在 + 含 upgrade/downgrade 函数
2. 字段定义完整 (id, user_hash, state, pdf_filename, pdf_uri, ...)
3. CHECK 约束 state 白名单
4. user_hash 字段 (跟 ingest_tasks 一致, 不是 user_id)
5. 索引 ix_pre_analysis_tasks_user_started
"""

import ast
from pathlib import Path

MIGRATION_FILE = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "storage"
    / "migrations"
    / "versions"
    / "20260702_000000_pre_analysis_tasks.py"
)


def test_migration_file_exists() -> None:
    """[M1] migration 文件存在"""
    assert MIGRATION_FILE.exists(), f"找不到 migration 文件: {MIGRATION_FILE}"


def test_migration_has_upgrade_and_downgrade() -> None:
    """[M1] 必含 upgrade() + downgrade() 两条函数 (CLAUDE.md §alembic 可回滚)"""
    source = MIGRATION_FILE.read_text(encoding="utf-8")
    tree = ast.parse(source)
    fns = {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    assert "upgrade" in fns
    assert "downgrade" in fns


def test_migration_required_columns() -> None:
    """[M1] 必含所有字段 (id, user_hash, state, pdf_filename, pdf_uri, ...)"""
    source = MIGRATION_FILE.read_text(encoding="utf-8")
    for col in [
        "id",
        "user_hash",
        "state",
        "pdf_filename",
        "pdf_uri",
        "started_at",
        "finished_at",
        "error",
        "output_files_json",
        "summary_json",
    ]:
        assert col in source, f"缺字段: {col}"


def test_migration_state_check_constraint() -> None:
    """[M1] state CHECK 约束白名单"""
    source = MIGRATION_FILE.read_text(encoding="utf-8")
    assert "ck_pre_analysis_tasks_state" in source
    assert "pending" in source
    assert "running" in source
    assert "completed" in source
    assert "failed" in source


def test_migration_user_hash_not_user_id() -> None:
    """[M1] 用 user_hash (跟 ingest_tasks 一致), 不用 user_id"""
    source = MIGRATION_FILE.read_text(encoding="utf-8")
    assert "user_hash" in source
    assert '"user_id"' not in source


def test_migration_index() -> None:
    """[M1] 索引 ix_pre_analysis_tasks_user_started (user_hash, started_at)"""
    source = MIGRATION_FILE.read_text(encoding="utf-8")
    assert "ix_pre_analysis_tasks_user_started" in source
