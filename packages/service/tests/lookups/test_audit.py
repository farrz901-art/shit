"""lookups/audit.py 单元测试"""

from unittest.mock import MagicMock, patch

from src.lookups.audit import log_dict_change


@patch("src.lookups.audit.session_scope")
def test_log_dict_change(mock_scope_cls):
    mock_session = MagicMock()
    mock_scope_cls.return_value.__enter__.return_value = mock_session
    log_dict_change(
        actor="admin@x.com",
        actor_id=1,
        action="item.create",
        target="status:new",
        before=None,
        after={"key": "new", "label_zh": "新"},
        ip="127.0.0.1",
    )
    mock_session.add.assert_called_once()


@patch("src.lookups.audit.session_scope")
def test_log_dict_change_forced(mock_scope_cls):
    mock_session = MagicMock()
    mock_scope_cls.return_value.__enter__.return_value = mock_session
    log_dict_change(
        actor="admin@x.com",
        actor_id=1,
        action="item.delete",
        target="status:old",
        before={"key": "old"},
        after=None,
        ip=None,
        forced=True,
    )
    mock_session.add.assert_called_once()


def test_log_dict_change_no_actor_id():
    import pytest

    with pytest.raises(TypeError, match="actor_id"):
        log_dict_change(
            actor="anon",
            actor_id=None,  # type: ignore[reportArgumentType]  # 故意传 None 触发 TypeError
            action="test",
            target="x",
            before=None,
            after=None,
            ip=None,
        )
