"""chat Pydantic schemas (2026-06-19 chat spec §5)

8 个模型:
- ConversationCreate / ConversationResponse / ConversationUpdate: 单 conv CRUD
- ConversationDetailResponse: 详情 = ConversationResponse + messages
- MessageResponse: 单条消息
- BackupMessage / BackupConversation / BackupResponse: 全量导出 JSON
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class ConversationCreate(BaseModel):
    """创建会话请求体 — title 可选, 不传默认 '新对话'"""

    title: str | None = Field(
        default=None,
        max_length=200,
        description="会话标题, 不传则后端默认 '新对话' (跟 ChatGPT/ChatShell 行为一致)",
    )


class ConversationResponse(BaseModel):
    """会话响应 — 单 conv 元数据 (不含 messages)"""

    id: str = Field(..., description="会话 UUID, 跟前端 crypto.randomUUID() 兼容")
    title: str = Field(..., description="会话标题")
    message_count: int = Field(..., description="消息总数 (冗余字段, 减少 COUNT(*))")
    created_at: datetime = Field(..., description="ISO 8601 时间字符串")
    updated_at: datetime = Field(..., description="ISO 8601 时间字符串, 按它 DESC 排序")


class ConversationUpdate(BaseModel):
    """重命名请求体 — title 必填, 1-200 字符"""

    title: str = Field(..., min_length=1, max_length=200, description="新标题, 1-200 字符")


class MessageCreate(BaseModel):
    """追加消息请求体 — role + content + 可选 meta JSON.

    role: 'user' / 'assistant' / 'system' (StrEnum Literal, Pydantic 自动校验).
    content: 1-64000 字符 (Dify 上下文窗口约束).
    meta: 透传 JSON, 业务用 finish_reason / error_code / citations, 后端不 schema-validate.
    """

    role: Literal["user", "assistant", "system"] = Field(
        ..., description="消息角色, 必填; user 入库会累加 conv.message_count"
    )
    content: str = Field(..., min_length=1, max_length=64_000, description="消息文本, 1-64000 字符")
    meta: dict[str, Any] | None = Field(
        default=None, description="元数据 JSON: finish_reason / error_code / citations / tokens 等, 后端透传不校验"
    )


class MessageResponse(BaseModel):
    """单条消息响应"""

    id: str = Field(..., description="消息 ID (后端 bigint 转 str)")
    role: str = Field(..., description="'user' / 'assistant' / 'system'")
    content: str = Field(..., description="消息文本")
    meta: dict[str, Any] | None = Field(default=None, description="元数据 JSON: token 用量 / 模型名 / 工具调用 (可空)")
    created_at: datetime = Field(..., description="ISO 8601 时间字符串")


class ConversationDetailResponse(ConversationResponse):
    """会话详情 — ConversationResponse + messages 列表"""

    messages: list[MessageResponse] = Field(default_factory=list, description="会话消息列表, 按 created_at ASC 排")


# ---- 备份导出 (GDPR, 2026-06-19 chat spec §5 GET /backup) ----


class BackupMessage(BaseModel):
    """备份消息 — 跟 MessageResponse 几乎一致, 但 created_at 是 str (方便 JSON 解析)"""

    role: str = Field(..., description="角色 (user / assistant / system)")
    content: str = Field(..., description="消息内容文本")
    meta: dict[str, Any] | None = Field(None, description="消息元数据 (附件 / source 等)")
    created_at: str = Field(..., description="ISO 8601 字符串 (备份用, 避免时区解析差异)")


class BackupConversation(BaseModel):
    """备份会话 — 含 messages"""

    id: str = Field(..., description="会话唯一 ID (UUID)")
    title: str = Field(..., description="会话标题")
    message_count: int = Field(..., description="消息总数")
    created_at: str = Field(..., description="创建时间 ISO 8601 字符串 (UTC)")
    updated_at: str = Field(..., description="最后更新时间 ISO 8601 字符串 (UTC)")
    messages: list[BackupMessage] = Field(default_factory=list, description="消息列表")


class BackupResponse(BaseModel):
    """全量备份响应 — exported_at + conversations[]"""

    exported_at: str = Field(..., description="导出时间 ISO 8601 字符串 (UTC)")
    conversations: list[BackupConversation] = Field(
        default_factory=list, description="按 created_at ASC 排的会话列表, 含全部消息"
    )


# 前向引用: ConversationDetailResponse 用 MessageResponse
ConversationDetailResponse.model_rebuild()
