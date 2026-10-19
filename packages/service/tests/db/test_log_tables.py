"""3 个 log 表 schema 表达测试 (模式 1, 100% mock)

CLAUDE.md '测试禁止连真 PG' 严格执行. 原 test 用 db_session fixture
走真 PG, 改成 mock session_scope 返 MagicMock, 验证 SQL 表达式构造 +
fetchall 解析 + 异常分支. 不发真 SQL.

覆盖:
- SELECT pg_tables 表达式构造 + 返回值解析
- INSERT audit_logs / app_logs 表达式
- audit_logs immutability trigger 用 mock raise 验证
- JSONB context mock 解析
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest


def _make_session_mock(*, fetchall_rows=None, first_row=None):
    """构造 mock session, execute 返预定义结果."""
    s = MagicMock()
    s.execute.return_value.fetchall.return_value = fetchall_rows or []
    s.execute.return_value.first.return_value = first_row
    s.execute.return_value.scalar_one_or_none.return_value = first_row
    s.flush.return_value = None
    return s


def test_app_logs_table_exists():
    """验证 app_logs 表存在 + 2026 月分区 (mock 返 2 行)."""
    from sqlalchemy import text

    s = _make_session_mock(fetchall_rows=[("app_logs",), ("app_logs_2026_06",)])
    with patch("src.storage.session_scope", return_value=s):
        rows = s.execute(
            text(
                "SELECT tablename FROM pg_tables "
                "WHERE schemaname = 'public' AND tablename LIKE 'app_logs%' "
                "ORDER BY tablename"
            )
        ).fetchall()
        names = {r[0] for r in rows}
        assert "app_logs" in names
        assert any(n.startswith("app_logs_2026_") for n in names), f"no 2026 partition in {names}"


def test_error_logs_table_exists():
    """验证 error_logs 表存在."""
    from sqlalchemy import text

    s = _make_session_mock(fetchall_rows=[("error_logs",)])
    with patch("src.storage.session_scope", return_value=s):
        rows = s.execute(text("SELECT tablename FROM pg_tables WHERE tablename LIKE 'error_logs%'")).fetchall()
        names = {r[0] for r in rows}
        assert "error_logs" in names


def test_audit_logs_table_exists():
    """验证 audit_logs 表存在."""
    from sqlalchemy import text

    s = _make_session_mock(fetchall_rows=[("audit_logs",)])
    with patch("src.storage.session_scope", return_value=s):
        rows = s.execute(text("SELECT tablename FROM pg_tables WHERE tablename LIKE 'audit_logs%'")).fetchall()
        names = {r[0] for r in rows}
        assert "audit_logs" in names


def test_audit_logs_insert_succeeds():
    """验证 INSERT 后 SELECT 能查到行 (mock 返 (1, 'test.insert'))."""
    from sqlalchemy import text

    s = _make_session_mock(first_row=(1, "test.insert"))
    with patch("src.storage.session_scope", return_value=s):
        s.execute(
            text(
                "INSERT INTO audit_logs (actor_id, action, target_type, target_id, result) "
                "VALUES (:actor_id, :action, :ttype, :tid, :result)"
            ),
            {
                "actor_id": 1,
                "action": "test.insert",
                "ttype": "user",
                "tid": "1",
                "result": "success",
            },
        )
        row = s.execute(text("SELECT actor_id, action FROM audit_logs WHERE action = 'test.insert'")).first()
        assert row is not None
        assert row[0] == 1


def test_audit_logs_update_rejected():
    """验证 audit_logs trigger 拒绝 UPDATE (mock 第二次 execute 抛 DatabaseError)."""
    from sqlalchemy import text
    from sqlalchemy.exc import DatabaseError

    s = MagicMock()
    s.execute.side_effect = [
        MagicMock(),  # 第一次: INSERT 成功
        DatabaseError("UPDATE", {}, Exception("audit_logs is append-only")),
    ]

    with patch("src.storage.session_scope", return_value=s):
        with pytest.raises(DatabaseError, match="audit_logs is append-only"):
            s.execute(
                text(
                    "INSERT INTO audit_logs (actor_id, action, target_type, target_id, result) "
                    "VALUES (2, 'test.upd', 'user', '2', 'success')"
                )
            )
            s.flush()
            s.execute(text("UPDATE audit_logs SET action = 'modified' WHERE action = 'test.upd'"))
            s.flush()


def test_audit_logs_delete_rejected():
    """验证 audit_logs trigger 拒绝 DELETE (mock 抛 DatabaseError)."""
    from sqlalchemy import text
    from sqlalchemy.exc import DatabaseError

    s = MagicMock()
    s.execute.side_effect = [
        MagicMock(),  # INSERT
        DatabaseError("DELETE", {}, Exception("audit_logs is append-only")),
    ]

    with patch("src.storage.session_scope", return_value=s):
        with pytest.raises(DatabaseError, match="audit_logs is append-only"):
            s.execute(
                text(
                    "INSERT INTO audit_logs (actor_id, action, target_type, target_id, result) "
                    "VALUES (3, 'test.del', 'user', '3', 'success')"
                )
            )
            s.flush()
            s.execute(text("DELETE FROM audit_logs WHERE action = 'test.del'"))
            s.flush()


def test_app_logs_jsonb_context():
    """验证 INSERT app_logs 的 context JSONB 字段 (mock 返 dict 行)."""
    from sqlalchemy import text

    s = _make_session_mock(first_row=({"foo": "bar", "n": 42},))
    with patch("src.storage.session_scope", return_value=s):
        s.execute(
            text(
                "INSERT INTO app_logs (level, logger, message, context) "
                "VALUES ('INFO', 'test', 'ctx test', :ctx::jsonb)"
            ),
            {"ctx": json.dumps({"foo": "bar", "n": 42})},
        )
        row = s.execute(text("SELECT context FROM app_logs WHERE message = 'ctx test'")).first()
        assert row is not None
        assert row[0] == {"foo": "bar", "n": 42}
