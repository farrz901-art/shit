"""AuditStore 单元测试 (模式 1 纯 mock, 2026-06-29 重写)

跟项目 "100% mock 不连真 PG" 规约一致 (CLAUDE.md §强制测试隔离).
原模式 2 (autouse DELETE + 真 PG) 跟 dev DB 共享有数据污染风险, 改纯 mock.

集成行为 (真 SQL + ORM + JSON 反序列化) 由 tests/integration/test_kg_audit_e2e.py
覆盖 (mark integration, CI 默认 skip).
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch


def test_record_inserts_row():
    """record() 调用 session.add(KgAudit(...)), 字段全部透传"""
    from src.kg.audit import AuditStore
    from src.kg.audit_models import KgAudit

    mock_session = MagicMock()
    mock_scope = MagicMock()
    mock_scope.__enter__ = lambda self: mock_session
    mock_scope.__exit__ = lambda self, *args: False

    with patch("src.kg.audit.session_scope", return_value=mock_scope):
        store = AuditStore()
        store.record(
            action="create_triple",
            actor="user-1",
            target="triple-42",
            result="ok",
            detail={"nodes": 3, "edges": 2},
        )

    # 1 次 add, 实参是 KgAudit 实例
    assert mock_session.add.call_count == 1
    added = mock_session.add.call_args[0][0]
    assert isinstance(added, KgAudit)
    assert added.action == "create_triple"
    assert added.actor == "user-1"
    assert added.target == "triple-42"
    assert added.result == "ok"
    # detail JSON 序列化 (跟 list_recent json.loads 配对)
    assert json.loads(added.detail) == {"nodes": 3, "edges": 2}
    assert isinstance(added.ts, float)


def test_list_recent_ordered_desc():
    """list_recent 走 select.order_by(ts.desc()).limit(N), 反序列化 detail"""
    from src.kg.audit import AuditStore
    from src.kg.audit_models import KgAudit

    # 模拟 ORM 返回 3 条 KgAudit, 按 ts desc 排
    rows = [
        KgAudit(
            id=3,
            ts=3.0,
            action="action_2",
            actor=None,
            target=None,
            result="ok",
            detail=json.dumps({"i": 2}),
        ),
        KgAudit(
            id=2,
            ts=2.0,
            action="action_1",
            actor=None,
            target=None,
            result="ok",
            detail=json.dumps({"i": 1}),
        ),
        KgAudit(
            id=1,
            ts=1.0,
            action="action_0",
            actor=None,
            target=None,
            result="ok",
            detail=json.dumps({"i": 0}),
        ),
    ]
    mock_session = MagicMock()
    mock_session.execute.return_value.scalars.return_value.all.return_value = rows
    mock_scope = MagicMock()
    mock_scope.__enter__ = lambda self: mock_session
    mock_scope.__exit__ = lambda self, *args: False

    with patch("src.kg.audit.session_scope", return_value=mock_scope):
        store = AuditStore()
        result = store.list_recent(limit=10)

    assert len(result) == 3
    assert result[0]["action"] == "action_2"
    assert result[1]["action"] == "action_1"
    assert result[2]["action"] == "action_0"
    # detail 反 JSON
    assert result[0]["detail"] == {"i": 2}


def test_list_recent_limit():
    """list_recent 传 limit 参数到 SQL, 用 N 条数据验证返回 ≤ N"""
    from src.kg.audit import AuditStore
    from src.kg.audit_models import KgAudit

    rows = [
        KgAudit(id=i, ts=float(i), action=f"a{i}", actor=None, target=None, result="ok", detail="{}") for i in range(2)
    ]
    mock_session = MagicMock()
    mock_session.execute.return_value.scalars.return_value.all.return_value = rows
    mock_scope = MagicMock()
    mock_scope.__enter__ = lambda self: mock_session
    mock_scope.__exit__ = lambda self, *args: False

    with patch("src.kg.audit.session_scope", return_value=mock_scope):
        store = AuditStore()
        result = store.list_recent(limit=2)

    assert len(result) == 2


def test_db_path_arg_ignored():
    """向后兼容: AuditStore(db_path) 旧调用不报错 (参数忽略)."""
    from src.kg.audit import AuditStore

    store = AuditStore("/some/old/path.db")
    assert store is not None
