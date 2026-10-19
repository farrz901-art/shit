"""field_config.py 单元测试 (模式 1: mock session_scope)

测试 get_active_configs / create_config / update_config / soft_delete_config.
(2026-06-23) 去掉 account_id: 字段配置是全局模板, 不按账号隔离.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest


@pytest.fixture
def mock_fc_session(monkeypatch):
    """Mock field_config.session_scope, 返回可控的 mock session."""
    mock_session = MagicMock()
    mock_scope = MagicMock()
    mock_scope.__enter__.return_value = mock_session
    mock_scope.__exit__.return_value = False
    monkeypatch.setattr(
        "src.buyer_profile.field_config.session_scope",
        lambda: mock_scope,
    )
    return mock_session


def test_get_active_configs_empty(mock_fc_session):
    """无配置时返回空列表."""
    from src.buyer_profile.field_config import get_active_configs

    mock_fc_session.execute.return_value.mappings.return_value.all.return_value = []

    result = get_active_configs()
    assert result == []


def test_get_active_configs_returns_sorted(mock_fc_session):
    """启用配置按 sort_order 返回."""
    from src.buyer_profile.field_config import get_active_configs

    rows = [
        {"id": 1, "code": "country", "label": "Country", "sort_order": 1},
        {"id": 2, "code": "equipment", "label": "Equipment", "sort_order": 2},
    ]
    mock_fc_session.execute.return_value.mappings.return_value.all.return_value = rows

    result = get_active_configs()
    assert len(result) == 2
    assert result[0]["code"] == "country"


def test_create_config_returns_record(mock_fc_session):
    """create_config 返回含 id 的完整记录."""
    from src.buyer_profile.field_config import create_config

    returned = {
        "id": 1,
        "code": "country",
        "label": "Country",
        "field_type": "select",
        "extraction_prompt": "Extract country",
        "options": [],
        "is_required": True,
        "sort_order": 0,
        "notify_on_change": [],
        "is_active": True,
    }
    mock_fc_session.execute.return_value.mappings.return_value.one.return_value = returned

    result = create_config(
        data={
            "code": "country",
            "label": "Country",
            "field_type": "select",
            "extraction_prompt": "Extract country",
            "options": [],
            "is_required": True,
        },
    )
    assert result["code"] == "country"
    assert result["id"] == 1


def test_update_config_none_when_no_allowed_fields(mock_fc_session):
    """data 中无允许字段时返回 None."""
    from src.buyer_profile.field_config import update_config

    result = update_config(code="country", data={"unknown": "x"})
    assert result is None


def test_update_config_returns_updated(mock_fc_session):
    """update_config 返回更新后的记录."""
    from src.buyer_profile.field_config import update_config

    returned = {
        "id": 1,
        "code": "country",
        "label": "Updated Country",
        "is_active": True,
    }
    mock_fc_session.execute.return_value.mappings.return_value.one_or_none.return_value = returned

    result = update_config(code="country", data={"label": "Updated Country"})
    assert result is not None
    assert result["label"] == "Updated Country"


def test_update_config_not_found(mock_fc_session):
    """记录不存在时返回 None."""
    from src.buyer_profile.field_config import update_config

    mock_fc_session.execute.return_value.mappings.return_value.one_or_none.return_value = None

    result = update_config(code="nonexistent", data={"label": "X"})
    assert result is None


def test_soft_delete_config_success(mock_fc_session):
    """软删成功返回 True."""
    from src.buyer_profile.field_config import soft_delete_config

    mock_fc_session.execute.return_value.rowcount = 1

    result = soft_delete_config(code="country")
    assert result is True


def test_soft_delete_config_not_found(mock_fc_session):
    """记录不存在时返回 False."""
    from src.buyer_profile.field_config import soft_delete_config

    mock_fc_session.execute.return_value.rowcount = 0

    result = soft_delete_config(code="nonexistent")
    assert result is False
