"""kg/audit.py 单元测试"""

from unittest.mock import MagicMock, patch

from src.kg.audit import AuditStore


@patch("src.kg.audit.session_scope")
def test_record_adds_audit(mock_scope_cls):
    mock_s = MagicMock()
    mock_scope_cls.return_value.__enter__.return_value = mock_s
    store = AuditStore()
    store.record(action="test", actor="user", target="node:1", result="ok", detail={"key": "val"})
    mock_s.add.assert_called_once()


@patch("src.kg.audit.session_scope")
def test_list_recent_returns_list(mock_scope_cls):
    mock_s = MagicMock()
    mock_row = MagicMock()
    mock_row.id = 1
    mock_row.ts = 100.0
    mock_row.action = "test"
    mock_row.actor = "user"
    mock_row.target = "node:1"
    mock_row.result = "ok"
    mock_row.detail = '{"key":"val"}'
    mock_s.execute.return_value.scalars.return_value.all.return_value = [mock_row]
    mock_scope_cls.return_value.__enter__.return_value = mock_s
    store = AuditStore()
    result = store.list_recent()
    assert len(result) == 1
    assert result[0]["action"] == "test"
