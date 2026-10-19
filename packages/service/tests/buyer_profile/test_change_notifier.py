"""change_notifier.py 单元测试 (模式 1: mock)

测试 detect_changes / log_changes / check_and_notify.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

# ── detect_changes 纯函数测试 ────────────────────────────


def test_detect_changes_no_change():
    """值未变时返回空列表."""
    from src.buyer_profile.change_notifier import detect_changes

    old = {"country": {"value": "Nigeria"}}
    new = {"country": "Nigeria"}
    assert detect_changes(old, new) == []


def test_detect_changes_new_value():
    """值变化时返回变更记录."""
    from src.buyer_profile.change_notifier import detect_changes

    old = {"country": {"value": "Nigeria"}}
    new = {"country": "Ghana"}
    changes = detect_changes(old, new)
    assert len(changes) == 1
    assert changes[0]["field_code"] == "country"
    assert changes[0]["old_value"] == "Nigeria"
    assert changes[0]["new_value"] == "Ghana"


def test_detect_changes_new_field():
    """新增字段视为变更 (old_value=None)."""
    from src.buyer_profile.change_notifier import detect_changes

    old = {}
    new = {"country": "Nigeria"}
    changes = detect_changes(old, new)
    assert len(changes) == 1
    assert changes[0]["old_value"] is None


def test_detect_changes_skip_none():
    """new_values 中的 None 值被跳过."""
    from src.buyer_profile.change_notifier import detect_changes

    old = {"country": {"value": "Nigeria"}}
    new = {"country": None}
    assert detect_changes(old, new) == []


def test_detect_changes_multiple():
    """多个字段同时变更."""
    from src.buyer_profile.change_notifier import detect_changes

    old = {"country": {"value": "Nigeria"}, "equipment": {"value": "excavator"}}
    new = {"country": "Ghana", "equipment": "excavator", "stage": "negotiation"}
    changes = detect_changes(old, new)
    assert len(changes) == 2
    codes = {c["field_code"] for c in changes}
    assert codes == {"country", "stage"}


# ── log_changes 测试 ─────────────────────────────────────


@pytest.fixture
def mock_cn_session(monkeypatch):
    """Mock change_notifier.session_scope."""
    mock_session = MagicMock()
    mock_scope = MagicMock()
    mock_scope.__enter__.return_value = mock_session
    mock_scope.__exit__.return_value = False
    monkeypatch.setattr(
        "src.buyer_profile.change_notifier.session_scope",
        lambda: mock_scope,
    )
    return mock_session


def test_log_changes_empty(mock_cn_session):
    """空 changes 时不执行 INSERT."""
    from src.buyer_profile.change_notifier import log_changes

    log_changes(1, "00000000-0000-0000-0000-000000000000", [])
    mock_cn_session.execute.assert_not_called()


def test_log_changes_writes_insert(mock_cn_session):
    """有变更时执行 INSERT."""
    from src.buyer_profile.change_notifier import log_changes

    changes = [{"field_code": "country", "old_value": "Nigeria", "new_value": "Ghana"}]
    log_changes(1, "550e8400-e29b-41d4-a716-446655440000", changes)

    mock_cn_session.execute.assert_called_once()


def test_log_changes_with_conv_id(mock_cn_session):
    """conv_id 被传入."""
    from src.buyer_profile.change_notifier import log_changes

    changes = [{"field_code": "country", "old_value": "A", "new_value": "B"}]
    log_changes(1, "pid", changes, source="manual", conv_id="conv-123")

    call_args = mock_cn_session.execute.call_args
    # execute(text(...), params_dict) → 2 positional args
    params = call_args[0][1]
    assert params["conv"] == "conv-123"
    assert params["src"] == "manual"


# ── check_and_notify 测试 ────────────────────────────────


def test_check_and_notify_no_rules(monkeypatch):
    """无通知规则时不触发."""
    from src.buyer_profile.change_notifier import check_and_notify

    logger_info = MagicMock()
    monkeypatch.setattr("src.buyer_profile.change_notifier.logger.info", logger_info)

    changes = [{"field_code": "country", "new_value": "Nigeria"}]
    configs = [{"code": "country", "notify_on_change": []}]
    check_and_notify(1, changes, configs)
    logger_info.assert_not_called()


def test_check_and_notify_triggered(monkeypatch):
    """满足 value_in 规则时触发通知."""
    from src.buyer_profile.change_notifier import check_and_notify

    logger_info = MagicMock()
    monkeypatch.setattr("src.buyer_profile.change_notifier.logger.info", logger_info)

    changes = [{"field_code": "priority", "new_value": "high_priority"}]
    configs = [
        {
            "code": "priority",
            "notify_on_change": [
                {"type": "value_in", "values": ["high_priority", "urgent"]},
            ],
        }
    ]
    check_and_notify(1, changes, configs)
    logger_info.assert_called_once()


def test_check_and_notify_no_match(monkeypatch):
    """值不在 value_in 列表时不触发."""
    from src.buyer_profile.change_notifier import check_and_notify

    logger_info = MagicMock()
    monkeypatch.setattr("src.buyer_profile.change_notifier.logger.info", logger_info)

    changes = [{"field_code": "priority", "new_value": "normal"}]
    configs = [
        {
            "code": "priority",
            "notify_on_change": [
                {"type": "value_in", "values": ["high_priority"]},
            ],
        }
    ]
    check_and_notify(1, changes, configs)
    logger_info.assert_not_called()


def test_check_and_notify_config_not_found(monkeypatch):
    """字段无对应配置时跳过."""
    from src.buyer_profile.change_notifier import check_and_notify

    logger_info = MagicMock()
    monkeypatch.setattr("src.buyer_profile.change_notifier.logger.info", logger_info)

    changes = [{"field_code": "unknown_field", "new_value": "x"}]
    check_and_notify(1, changes, [])
    logger_info.assert_not_called()
