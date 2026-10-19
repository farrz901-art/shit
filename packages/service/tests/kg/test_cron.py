"""kg_extract_items 7d cron 测试 (PR3 Task 17)

走 AST 验证 + mock session_scope (CLAUDE.md §测试隔离 强制 0 真 PG)
"""

import ast
from contextlib import contextmanager
from pathlib import Path


def test_cron_module_has_cleanup_function():
    """[M7] cron 模块必含 cleanup_old_extract_items 函数"""
    # tests/kg/<name>.py → parents[2] = packages/service
    cron_file = Path(__file__).resolve().parents[2] / "src" / "kg" / "cron.py"
    assert cron_file.exists(), f"找不到 cron 模块: {cron_file}"
    source = cron_file.read_text(encoding="utf-8")
    tree = ast.parse(source)
    fns = {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    assert "cleanup_old_extract_items" in fns


def test_cleanup_deletes_items_older_than_7_days(monkeypatch):
    """[M7] 7d 前的 kg_extract_items 必删, 必返 deleted_count"""
    captured_sql: list[tuple[str, dict]] = []

    class FakeResult:
        rowcount = 5

    class FakeSession:
        def execute(self, stmt, params=None):
            captured_sql.append((str(stmt.compile()), params or {}))
            return FakeResult()

        def commit(self):
            pass

    @contextmanager
    def fake_session_scope():
        yield FakeSession()

    monkeypatch.setattr("src.kg.cron.session_scope", fake_session_scope)

    from src.kg.cron import cleanup_old_extract_items

    result = cleanup_old_extract_items(days=7)
    assert result.deleted_count == 5
    # DELETE + INTERVAL '7 days'
    assert len(captured_sql) == 1
    sql_text = captured_sql[0][0]
    assert "DELETE" in sql_text.upper()
    assert "INTERVAL '7 days'" in sql_text


def test_cleanup_default_days_is_7():
    """[M7] 默认 days=7, 不传也跑得通"""
    from inspect import signature

    from src.kg.cron import cleanup_old_extract_items

    sig = signature(cleanup_old_extract_items)
    assert sig.parameters["days"].default == 7


def test_cleanup_result_dataclass():
    """[M7] CleanupResult dataclass 含 deleted_count 字段"""
    from src.kg.cron import CleanupResult

    r = CleanupResult(deleted_count=42)
    assert r.deleted_count == 42
    r2 = CleanupResult()
    assert r2.deleted_count == 0


def test_cleanup_no_rows_returns_zero(monkeypatch):
    """[M7] 无 rowcount 时 deleted_count 返 0 (不抛异常)"""

    class FakeResult:
        rowcount = None

    class FakeSession:
        def execute(self, stmt, params=None):
            return FakeResult()

        def commit(self):
            pass

    @contextmanager
    def fake_session_scope():
        yield FakeSession()

    monkeypatch.setattr("src.kg.cron.session_scope", fake_session_scope)

    from src.kg.cron import cleanup_old_extract_items

    result = cleanup_old_extract_items(days=30)
    assert result.deleted_count == 0
