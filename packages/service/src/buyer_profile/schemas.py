"""buyer_profile Pydantic schemas (2026-06-22 buyer-profile spec)

9 个模型:
- ProfileFieldValue: profile_data 中单字段结构
- BuyerProfileResponse: 客户画像响应
- BuyerProfileListResponse: 分页列表响应
- BuyerProfileUpdate: 客户画像更新请求
- ProfileFieldConfigResponse: 字段配置响应
- ProfileFieldConfigCreate: 字段配置创建
- ProfileFieldConfigUpdate: 字段配置更新
- ChangeLogResponse: 变更日志响应
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class ProfileFieldValue(BaseModel):
    """profile_data 中单字段值结构"""

    value: Any = Field(None, description="字段值")
    confidence: Literal["high", "medium", "low"] = Field("medium", description="抽取置信度")
    source: Literal["auto", "manual"] = Field("auto", description="来源: 自动抽取 / 人工编辑")
    updated_at: datetime | None = Field(None, description="最近更新时间")


class BuyerProfileResponse(BaseModel):
    """客户画像响应"""

    id: UUID = Field(..., description="客户画像 ID")
    buyer_key: str = Field(..., description="买家唯一标识 (WhatsApp/Email)")
    buyer_name: str | None = Field(None, description="买家名称/公司名")
    status: str = Field("active", description="状态: active/archived")
    profile_data: dict[str, dict] = Field(default_factory=dict, description="画像字段数据")
    tags: list[str] = Field(default_factory=list, description="标签")
    notes: str | None = Field(None, description="人工备注")
    first_seen_at: datetime | None = Field(None, description="首次发现时间")
    last_contact_at: datetime | None = Field(None, description="最近联系时间")


class BuyerProfileListResponse(BaseModel):
    """客户画像分页列表响应"""

    items: list[BuyerProfileResponse] = Field(default_factory=list, description="客户画像列表")
    total: int = Field(0, description="总数")


class BuyerProfileUpdate(BaseModel):
    """客户画像更新请求"""

    profile_data: dict[str, Any] | None = Field(None, description="画像字段数据")
    buyer_name: str | None = Field(None, description="买家名称")
    status: str | None = Field(None, description="状态")
    tags: list[str] | None = Field(None, description="标签")
    notes: str | None = Field(None, description="备注")


class ProfileFieldConfigResponse(BaseModel):
    """字段配置响应"""

    id: int = Field(..., description="字段 ID")
    code: str = Field(..., description="字段 code")
    label: str = Field(..., description="字段显示名")
    field_type: str = Field("text", description="字段类型")
    extraction_prompt: str | None = Field(None, description="LLM 抽取 prompt")
    options: list[str | dict] = Field(default_factory=list, description="select/tags 选项 (字符串列表或结构体)")
    is_required: bool = Field(False, description="是否必填")
    is_active: bool = Field(True, description="是否启用")
    notify_on_change: list[dict] = Field(default_factory=list, description="变更通知规则")
    sort_order: int = Field(0, description="排序")


class ProfileFieldConfigCreate(BaseModel):
    """字段配置创建请求"""

    code: str = Field(..., min_length=1, max_length=64, pattern=r"^[a-z_]+$", description="字段 code (小写下划线)")
    label: str = Field(..., min_length=1, max_length=128, description="字段显示名")
    field_type: Literal["text", "tags", "select", "number", "boolean"] = Field("text", description="字段类型")
    extraction_prompt: str | None = Field(None, description="LLM 抽取 prompt")
    options: list[str | dict] = Field(default_factory=list, description="select/tags 选项 (字符串列表或结构体)")
    is_required: bool = Field(False, description="是否必填")
    notify_on_change: list[dict] = Field(default_factory=list, description="变更通知规则")
    sort_order: int = Field(0, description="排序")


class ProfileFieldConfigUpdate(BaseModel):
    """字段配置更新请求"""

    label: str | None = Field(None, description="字段显示名")
    field_type: str | None = Field(None, description="字段类型")
    extraction_prompt: str | None = Field(None, description="LLM 抽取 prompt")
    options: list[str | dict] | None = Field(None, description="select/tags 选项 (字符串列表或结构体)")
    is_required: bool | None = Field(None, description="是否必填")
    is_active: bool | None = Field(None, description="是否启用")
    sort_order: int | None = Field(None, description="排序")
    notify_on_change: list[dict] | None = Field(None, description="变更通知规则")


class ChangeLogResponse(BaseModel):
    """变更日志响应"""

    id: int = Field(..., description="日志 ID")
    profile_id: UUID = Field(..., description="客户画像 ID")
    field_code: str = Field(..., description="变更字段 code")
    old_value: Any = Field(None, description="旧值")
    new_value: Any = Field(None, description="新值")
    source: str = Field("auto", description="来源")
    conv_id: str | None = Field(None, description="对话 ID")
    created_at: datetime | None = Field(None, description="变更时间")
