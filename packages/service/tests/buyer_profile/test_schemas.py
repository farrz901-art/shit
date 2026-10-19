"""buyer_profile schemas tests (2026-06-22)"""

from uuid import UUID

from src.buyer_profile.schemas import (
    BuyerProfileResponse,
    ChangeLogResponse,
    ProfileFieldConfigCreate,
)


def test_buyer_profile_response_roundtrip():
    data = {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "buyer_key": "whatsapp:+234801234567",
        "buyer_name": "ABC Trading",
        "status": "active",
        "profile_data": {"country": {"value": "Nigeria"}},
    }
    resp = BuyerProfileResponse.model_validate(data)
    assert resp.buyer_name == "ABC Trading"
    assert resp.profile_data["country"]["value"] == "Nigeria"
    assert isinstance(resp.id, UUID)
    assert resp.id.hex == "550e8400e29b41d4a716446655440000"


def test_field_config_create_validation():
    cfg = ProfileFieldConfigCreate(code="equipment_type", label="Equipment Type")  # pyright: ignore[reportCallIssue]  # pyright 不识别 Pydantic Field default, 必填字段都已有 default
    assert cfg.code == "equipment_type"
    assert cfg.field_type == "text"
    assert not cfg.is_required
    assert cfg.options == []


def test_field_config_create_rejects_bad_code():
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        ProfileFieldConfigCreate(code="Equipment-Type!", label="Bad")  # pyright: ignore[reportCallIssue]  # pyright 不识别 Pydantic Field default


def test_buyer_profile_update_optional_fields():
    from src.buyer_profile.schemas import BuyerProfileUpdate

    update = BuyerProfileUpdate(buyer_name="New Name")  # pyright: ignore[reportCallIssue]  # pyright 不识别 Pydantic Field default
    assert update.buyer_name == "New Name"
    assert update.status is None
    assert update.profile_data is None


def test_change_log_response_roundtrip():
    data = {
        "id": 1,
        "profile_id": "550e8400-e29b-41d4-a716-446655440000",
        "field_code": "country",
        "old_value": "Nigeria",
        "new_value": "Ghana",
        "source": "auto",
    }
    log = ChangeLogResponse.model_validate(data)
    assert log.field_code == "country"
    assert log.new_value == "Ghana"
    assert log.conv_id is None


def test_field_value_model_defaults():
    from src.buyer_profile.schemas import ProfileFieldValue

    fv = ProfileFieldValue(value="test")  # pyright: ignore[reportCallIssue]  # pyright 不识别 Pydantic Field default
    assert fv.confidence == "medium"
    assert fv.source == "auto"
    assert fv.updated_at is None
