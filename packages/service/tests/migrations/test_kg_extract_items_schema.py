"""kg_extract_items 迁移 AST 验证 + SQL 文本 (CLAUDE.md 禁真 PG)

v3 设计: 测试全用 AST + 文件文本扫描, 不连 PG (跟 CLAUDE.md §测试隔离 一致).
本测试只验证:
1. migration 文件存在 + 含 upgrade/downgrade 函数
2. 字段定义完整 (task_id, dataset, payload 等)
3. JSONB 用对, 不用 sa.JSON()
4. dataset 字段加 CHECK 约束
5. v3 不加 user_hash 字段 (已删)
"""

import ast
from pathlib import Path

# tests/migrations/<name>.py → parents[1] = tests, parents[2] = packages/service
MIGRATION_FILE = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "storage"
    / "migrations"
    / "versions"
    / "20260701_000000_kg_extract_items.py"
)


def test_migration_file_exists() -> None:
    """[M5] migration 文件存在"""
    assert MIGRATION_FILE.exists(), f"找不到 migration 文件: {MIGRATION_FILE}"


def test_migration_has_upgrade_and_downgrade() -> None:
    """[M5] 必含 upgrade() + downgrade() 两条函数 (CLAUDE.md §alembic 可回滚)"""
    source = MIGRATION_FILE.read_text(encoding="utf-8")
    tree = ast.parse(source)
    fns = {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    assert "upgrade" in fns
    assert "downgrade" in fns


def test_migration_uses_jsonb_not_sa_json() -> None:
    """[M5] payload / corrected_payload 用 JSONB 不是 sa.JSON()"""
    source = MIGRATION_FILE.read_text(encoding="utf-8")
    assert "from sqlalchemy.dialects.postgresql import JSONB" in source
    assert "sa.JSON()" not in source


def test_migration_has_dataset_field_with_check() -> None:
    """[M5] v3: 必含 dataset 字段 + CHECK 格式约束"""
    source = MIGRATION_FILE.read_text(encoding="utf-8")
    assert "dataset" in source
    assert "ck_kg_extract_items_dataset_format" in source
    # dataset CHECK 必含 identifier 格式
    assert "^[A-Za-z_][A-Za-z0-9_]*$" in source


def test_migration_no_user_hash() -> None:
    """[M5] v3: 不要 user_hash 残留 (v1 设计, v3 已删)"""
    source = MIGRATION_FILE.read_text(encoding="utf-8")
    assert "user_hash" not in source


def test_migration_has_all_required_fields() -> None:
    """[M5] 必含 10 字段: id / task_id / dataset / extractor / splitter / kind / payload / selected / chunk_id / corrected_payload / confirmed_at / created_at"""
    source = MIGRATION_FILE.read_text(encoding="utf-8")
    required_fields = [
        "id",
        "task_id",
        "dataset",
        "extractor",
        "splitter",
        "kind",
        "payload",
        "selected",
        "chunk_id",
        "corrected_payload",
        "confirmed_at",
        "created_at",
    ]
    for field in required_fields:
        assert f'"{field}"' in source, f"migration 缺字段: {field}"


def test_migration_has_three_indexes() -> None:
    """[M5] 3 索引验证: task_dataset / dataset_created / dataset_confirmed (部分)"""
    source = MIGRATION_FILE.read_text(encoding="utf-8")
    assert "ix_kg_extract_items_task_dataset" in source
    assert "ix_kg_extract_items_dataset_created" in source
    assert "ix_kg_extract_items_dataset_confirmed" in source
    # dataset_confirmed 必是部分索引 (postgresql_where)
    assert "postgresql_where" in source


def test_migration_has_kind_check_constraint() -> None:
    """[M5] kind CHECK 约束: 只允许 'entity' / 'relation'"""
    source = MIGRATION_FILE.read_text(encoding="utf-8")
    assert "ck_kg_extract_items_kind" in source
    assert "kind IN ('entity', 'relation')" in source
