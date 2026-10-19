"""service.py + extractor.py 单元测试 (模式 1: mock)

测试 ProfileService CRUD + try_extract + extractor 纯函数.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

# ── extractor 纯函数测试 ──────────────────────────────────


def test_extract_fields_empty_configs(monkeypatch):
    """空字段配置时 extract_fields 返回空 dict."""
    from src.buyer_profile.extractor import extract_fields

    # _call_llm 在这个分支不会被实际调用, 但 mock 掉确保安全
    monkeypatch.setattr("src.buyer_profile.extractor._call_llm", lambda p: {})
    result = extract_fields([], {}, [{"role": "user", "content": "hi"}])
    assert result == {}


def test_build_prompt_contains_field_labels():
    """_build_extraction_prompt 包含字段 code 和 label."""
    from src.buyer_profile.extractor import _build_extraction_prompt

    configs = [
        {
            "code": "country",
            "label": "Country",
            "field_type": "text",
            "extraction_prompt": None,
        }
    ]
    prompt = _build_extraction_prompt(configs, {}, [{"role": "user", "content": "hello"}])
    assert "country" in prompt
    assert "Country" in prompt


def test_build_prompt_with_custom_prompt():
    """自定义 extraction_prompt 会被包含在提示中."""
    from src.buyer_profile.extractor import _build_extraction_prompt

    configs = [
        {
            "code": "equipment",
            "label": "设备类型",
            "field_type": "tags",
            "extraction_prompt": "列出买家询问的全部设备类型",
        }
    ]
    prompt = _build_extraction_prompt(configs, {}, [{"role": "user", "content": "我要买挖机"}])
    assert "列出买家询问的全部设备类型" in prompt
    assert "tags" in prompt


def test_call_llm_parses_json(monkeypatch):
    """_call_llm 能正确解析 LLM 返回的 JSON."""
    from unittest.mock import MagicMock

    from src.buyer_profile.extractor import _call_llm

    mock_resp = MagicMock()
    mock_resp.content = '{"country": "Nigeria", "equipment": null}'
    mock_llm = MagicMock()
    mock_llm.llm.invoke.return_value = mock_resp

    monkeypatch.setattr("src.generation.llm.OpenAILLM", lambda: mock_llm)

    result = _call_llm("some prompt")
    assert result == {"country": "Nigeria"}  # null 被过滤


def test_call_llm_strips_markdown(monkeypatch):
    """_call_llm 去除 markdown 代码块标记."""
    from unittest.mock import MagicMock

    from src.buyer_profile.extractor import _call_llm

    mock_resp = MagicMock()
    mock_resp.content = '```json\n{"country": "Ghana"}\n```'
    mock_llm = MagicMock()
    mock_llm.llm.invoke.return_value = mock_resp

    monkeypatch.setattr("src.generation.llm.OpenAILLM", lambda: mock_llm)

    result = _call_llm("some prompt")
    assert result == {"country": "Ghana"}


# ── ProfileService 测试 ──────────────────────────────────


@pytest.fixture
def mock_svc_session(monkeypatch):
    """Mock service.session_scope, 返回可控 mock session."""
    mock_session = MagicMock()
    mock_scope = MagicMock()
    mock_scope.__enter__.return_value = mock_session
    mock_scope.__exit__.return_value = False
    monkeypatch.setattr(
        "src.buyer_profile.service.session_scope",
        lambda: mock_scope,
    )
    return mock_session


@pytest.fixture
def mock_svc_deps(monkeypatch):
    """Mock service 内依赖: get_active_configs + extract_fields."""
    monkeypatch.setattr(
        "src.buyer_profile.service.get_active_configs",
        lambda: [],
    )
    monkeypatch.setattr(
        "src.buyer_profile.service.extract_fields",
        lambda configs, existing, messages: {},
    )
    # change_notifier 的 session_scope
    mock_cn_session = MagicMock()
    mock_cn_scope = MagicMock()
    mock_cn_scope.__enter__.return_value = mock_cn_session
    mock_cn_scope.__exit__.return_value = False
    monkeypatch.setattr(
        "src.buyer_profile.service.log_changes",
        lambda *a, **kw: None,
    )
    monkeypatch.setattr(
        "src.buyer_profile.service.check_and_notify",
        lambda *a, **kw: None,
    )
    monkeypatch.setattr(
        "src.buyer_profile.service.detect_changes",
        lambda old, new: [],
    )


def test_create_or_get_profile_new(mock_svc_session):
    """首次创建返回记录."""
    from src.buyer_profile.service import ProfileService

    row = {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "account_id": 1,
        "buyer_key": "whatsapp:+234801234567",
        "buyer_name": "ABC Trading",
        "status": "active",
        "profile_data": {},
        "profile_meta": {},
    }
    mock_svc_session.execute.return_value.mappings.return_value.one_or_none.return_value = row

    result = ProfileService.create_or_get_profile(1, "whatsapp:+234801234567", "ABC Trading")
    assert result is not None
    assert result["buyer_key"] == "whatsapp:+234801234567"


def test_get_profile_found(mock_svc_session):
    """查询已有记录."""
    from src.buyer_profile.service import ProfileService

    row = {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "account_id": 1,
        "buyer_key": "whatsapp:+234801234567",
        "buyer_name": "ABC Trading",
    }
    mock_svc_session.execute.return_value.mappings.return_value.one_or_none.return_value = row

    result = ProfileService.get_profile(1, "whatsapp:+234801234567")
    assert result is not None
    assert result["buyer_name"] == "ABC Trading"


def test_get_profile_not_found(mock_svc_session):
    """查询不存在的记录返回 None."""
    from src.buyer_profile.service import ProfileService

    mock_svc_session.execute.return_value.mappings.return_value.one_or_none.return_value = None

    result = ProfileService.get_profile(1, "nonexistent")
    assert result is None


def test_validate_profile_data_valid():
    """_validate_profile_data 验证合法数据通过."""
    from src.buyer_profile.service import ProfileService

    result = ProfileService._validate_profile_data(
        {
            "country": "Nigeria",
            "equipment": ["excavator", "crane"],
        }
    )
    assert "country" in result
    assert result["country"]["value"] == "Nigeria"
    assert result["country"]["confidence"] == "high"  # truthy value
    assert result["country"]["source"] == "auto"
    assert result["country"]["updated_at"] is not None

    assert "equipment" in result
    assert result["equipment"]["value"] == ["excavator", "crane"]
    assert result["equipment"]["confidence"] == "high"  # truthy value


def test_validate_profile_data_preserves_structure():
    """空值/假值字段 confidence 为 medium."""
    from src.buyer_profile.service import ProfileService

    result = ProfileService._validate_profile_data(
        {
            "empty_str": "",
            "none_val": None,
            "zero": 0,
        }
    )
    assert result["empty_str"]["confidence"] == "medium"  # 空字符串 falsy
    assert result["none_val"]["confidence"] == "medium"
    assert result["zero"]["confidence"] == "medium"


def test_list_profiles_empty(mock_svc_session):
    """空列表."""
    from src.buyer_profile.service import ProfileService

    mock_svc_session.execute.return_value.scalar.return_value = 0
    mock_svc_session.execute.return_value.mappings.return_value.all.return_value = []

    items, total = ProfileService.list_profiles(1)
    assert total == 0
    assert items == []


def test_list_profiles_with_filters(mock_svc_session):
    """带 status 过滤."""
    from src.buyer_profile.service import ProfileService

    rows = [{"id": "uuid-1", "buyer_key": "k1", "status": "active"}]
    mock_svc_session.execute.return_value.scalar.return_value = 1
    mock_svc_session.execute.return_value.mappings.return_value.all.return_value = rows

    items, total = ProfileService.list_profiles(1, filters={"status": "active"})
    assert total == 1
    assert items[0]["buyer_key"] == "k1"


def test_soft_delete_true(mock_svc_session):
    """软删成功返回 True."""
    from src.buyer_profile.service import ProfileService

    mock_svc_session.execute.return_value.rowcount = 1

    result = ProfileService.soft_delete(1, "550e8400-e29b-41d4-a716-446655440000")  # type: ignore[arg-type]
    assert result is True


def test_soft_delete_false(mock_svc_session):
    """软删不存在记录返回 False."""
    from src.buyer_profile.service import ProfileService

    mock_svc_session.execute.return_value.rowcount = 0

    result = ProfileService.soft_delete(1, "550e8400-e29b-41d4-a716-446655440000")  # type: ignore[arg-type]
    assert result is False


def test_update_profile_fields_creates_if_missing(mock_svc_session, mock_svc_deps):
    """profile 不存在时自动创建再更新."""
    from src.buyer_profile.service import ProfileService

    # get_profile 返回 None (未找到)
    mock_svc_session.execute.return_value.mappings.return_value.one_or_none.return_value = None

    # 为了让第二次 get_profile 返回记录, 改 mock 行为
    def side_effect(*args, **kwargs):
        # 第一次 call (get_profile) → None
        # 第二次 call (create_or_get_profile) → row
        # 第三次 call (get_profile 再次) → row
        # 第四次 call (update) → rowcount
        return MagicMock(rowcount=1)

    # 用更可控的方式: 第一次 None, 之后有值
    mock_svc_session.execute.return_value.mappings.return_value.one_or_none.side_effect = [
        None,  # 第一次 get_profile
        {
            "id": "uuid-1",
            "account_id": 1,
            "buyer_key": "k1",
            "profile_data": {},
            "buyer_name": None,
            "status": "active",
        },
        {
            "id": "uuid-1",
            "account_id": 1,
            "buyer_key": "k1",
            "profile_data": {},
            "buyer_name": None,
            "status": "active",
        },
    ]
    mock_svc_session.execute.return_value.rowcount = 1

    result = ProfileService.update_profile_fields(1, "k1", {"country": "Nigeria"})
    assert result is True


def test_try_extract_silent_on_failure(mock_svc_deps):
    """try_extract 在失败时不抛异常."""
    from src.buyer_profile.service import ProfileService

    # 即使任何依赖失败, try_extract 应静默处理
    ProfileService.try_extract(account_id=999, buyer_key="nonexistent", messages=[])
    # Should not raise


def test_try_extract_no_configs_returns_early(monkeypatch):
    """无字段配置时 try_extract 提前返回."""
    from src.buyer_profile.service import ProfileService

    monkeypatch.setattr(
        "src.buyer_profile.service.get_active_configs",
        lambda: [],
    )

    ProfileService.try_extract(account_id=1, buyer_key="k1", messages=[{"role": "user", "content": "hi"}])
