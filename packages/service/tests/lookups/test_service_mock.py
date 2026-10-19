"""lookups/service.py 单元测试 (mode 1, mock 全部依赖)"""

from unittest.mock import MagicMock, patch

SAMPLE_DICT = {
    "status": {
        "code": "status",
        "label_zh": "状态",
        "label_en": "Status",
        "version": 1,
        "items": [
            {"key": "active", "label_zh": "启用", "label_en": "Active", "is_active": True, "sort": 1},
            {"key": "inactive", "label_zh": "停用", "label_en": "Inactive", "is_active": True, "sort": 2},
        ],
    }
}

SAMPLE_DICT_WITH_INACTIVE = {
    "status": {
        "code": "status",
        "label_zh": "状态",
        "label_en": "Status",
        "version": 1,
        "items": [
            {"key": "active", "label_zh": "启用", "label_en": "Active", "is_active": True, "sort": 1},
            {"key": "inactive", "label_zh": "停用", "label_en": "Inactive", "is_active": False, "sort": 2},
        ],
    }
}


@patch("src.lookups.service.lookup_cache.get_all", return_value=SAMPLE_DICT)
async def test_get_from_cache(mock_get_all):
    from src.lookups.service import LookupService

    result = await LookupService.get("status")
    assert result["code"] == "status"
    assert len(result["items"]) == 2


@patch("src.lookups.service.lookup_cache.get_all", return_value=SAMPLE_DICT_WITH_INACTIVE)
async def test_get_only_active(mock_get_all):
    from src.lookups.service import LookupService

    result = await LookupService.get("status", only_active=True)
    assert len(result["items"]) == 1
    assert result["items"][0]["key"] == "active"


@patch("src.lookups.service.lookup_cache.get_all", return_value=SAMPLE_DICT)
async def test_list_all_dicts(mock_get_all):
    from src.lookups.service import LookupService

    result = await LookupService.list_all_dicts()
    assert len(result) == 1
    assert result[0]["code"] == "status"


@patch("src.lookups.service.lookup_cache.get_all", return_value=SAMPLE_DICT)
async def test_get_one_found(mock_get_all):
    from src.lookups.service import LookupService

    result = await LookupService.get_one("status", "active")
    assert result["key"] == "active"


@patch("src.lookups.service.lookup_cache.get_all", return_value=SAMPLE_DICT)
@patch("src.lookups.service.log_dict_change")
async def test_create_item_success(mock_audit, mock_get_all):
    """(2026-06-23) 修 mock: create_item 内部 2 次 execute, 第 1 次查 Dictionary (需返 mock),
    第 2 次查重复 key (返 None). 旧 mock 只返 None → 第 1 次查 dict 返 None 直接 raise."""
    mock_session = MagicMock()
    # execute() 2 次调用: 第 1 次查 Dictionary (返 mock obj), 第 2 次查重复 key (返 None)
    mock_dict = MagicMock()
    mock_dict.code = "status"
    mock_session.execute.side_effect = [
        MagicMock(scalar_one_or_none=MagicMock(return_value=mock_dict)),
        MagicMock(scalar_one_or_none=MagicMock(return_value=None)),
    ]
    with patch(
        "src.lookups.service.session_scope", return_value=MagicMock(__enter__=MagicMock(return_value=mock_session))
    ):
        from src.lookups.service import LookupService

        result = await LookupService.create_item(
            "status",
            {"key": "new", "label_zh": "新", "label_en": "New", "sort": 3},
            actor="admin",
            actor_id=1,
            ip="127.0.0.1",
        )
    assert result["key"] == "new"


@patch("src.lookups.service.lookup_cache.get_all", return_value=SAMPLE_DICT)
@patch("src.lookups.service.log_dict_change")
async def test_soft_delete_item(mock_audit, mock_get_all):
    mock_session = MagicMock()
    mock_item = MagicMock()
    mock_item.is_active = True
    mock_session.execute.return_value.scalar_one_or_none.return_value = mock_item
    with patch(
        "src.lookups.service.session_scope", return_value=MagicMock(__enter__=MagicMock(return_value=mock_session))
    ):
        from src.lookups.service import LookupService

        await LookupService.soft_delete_item("status", "active", actor="admin", actor_id=1, ip="127.0.0.1")
    assert mock_item.is_active is False
