"""ChatShare Pydantic schemas (2026-06-16)

请求 / 响应 5 个核心模型:
- CreateShareRequest: 创建 share 请求体
- ShareResponse: 创建后返回 (含 share_id + 完整 URL)
- SharedConversationResponse: 公开读返回 (不含 user_id 等敏感字段)
- SharedMessage: 单条消息快照
- ShareListItem: 按 conv 列 share 元数据 (不含 messages 快照)
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class SharedMessageInput(BaseModel):
    """创建 share 时携带的单条消息 (客户端序列化, 不含内部 id / meta)"""

    role: Literal["user", "assistant"] = Field(..., description="'user' = 用户消息, 'assistant' = AI 回复")
    content: str = Field(..., min_length=1, description="消息文本内容")
    timestamp: datetime | None = Field(None, description="ISO 8601 时间字符串, 可选")


class CreateShareRequest(BaseModel):
    """创建 share 请求体: conv_id 必填, messages 必填, title 可选"""

    conv_id: str = Field(..., max_length=36, description="已登录用户 conv_id (server 端 UUID, String(36))")
    title: str | None = Field(default=None, max_length=200, description="分享标题, None 则前端可编辑")
    messages: list[SharedMessageInput] = Field(
        ...,
        min_length=1,
        max_length=200,
        description="客户端当前会话全部消息快照 (role + content + timestamp), 至少 1 条",
    )


class ShareResponse(BaseModel):
    """创建 share 响应: share_id + 完整 URL + 元数据"""

    share_id: str = Field(..., description="share 唯一 ID, 路径参数 /s/{share_id}")
    url: str = Field(..., description="完整分享 URL: {WEB_BASE_URL}/{locale}/chat/s/{share_id}")
    title: str | None = Field(None, description="分享标题, 创建时可能为 None")
    expires_at: datetime | None = Field(None, description="ISO 8601 时间字符串; 永不过期则为 None")
    created_at: datetime = Field(..., description="ISO 8601 时间字符串")


class ShareListItem(BaseModel):
    """share 列表项: 不含 messages 快照 (避免大 JSON 进列表响应)"""

    share_id: str = Field(..., description="share 唯一 ID")
    url: str = Field(..., description="完整分享 URL: {WEB_BASE_URL}/{locale}/chat/s/{share_id}")
    title: str | None = Field(None, description="分享标题")
    expires_at: datetime | None = Field(None, description="ISO 8601; 永不过期则为 None")
    created_at: datetime = Field(..., description="ISO 8601")


class SharedMessage(BaseModel):
    """单条快照消息: 纯文本, 不含 thinking / 引用 / metadata"""

    role: Literal["user", "assistant"] = Field(..., description="'user' = 用户消息, 'assistant' = AI 回复")
    content: str = Field(..., description="消息文本内容")
    timestamp: datetime | None = Field(None, description="ISO 8601 时间字符串")


class SharedConversationResponse(BaseModel):
    """公开读返回: 不含 user_id / share_password / token 等敏感字段"""

    share_id: str = Field(..., description="share 唯一 ID, 路径参数 /s/{share_id}")
    title: str | None = Field(None, description="分享标题, 创建时可能为 None")
    messages: list[SharedMessage] = Field(..., description="列表, 元素是 SharedMessage 对象")
    model: str | None = Field(None, description="生成时使用的 LLM 模型名, 例: 'gpt-4o-mini'")
    created_at: datetime = Field(..., description="ISO 8601 时间字符串")


class UploadFileResponse(BaseModel):
    """文件上传响应: Dify uploadFileId + URI"""

    uploadFileId: str = Field(..., description="Dify uploadFileId, 用于后续对话引用此文件")
    uri: str = Field(
        default="", description="MinIO/S3 URI, 例: 's3://rag-ingest/chat/{user_id}/image.png'"
    )  # (2026-06-16) 新增, 旧调用方依赖 uploadFileId, 加默认值兼容


class PresignChatFileRequest(BaseModel):
    """presign 请求体"""

    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        pattern=r"^[a-zA-Z0-9._-]+$",
        description="文件名, 只允许字母数字._-, 不含路径分隔符 (例: 'image.png')",
    )
    size: int = Field(..., ge=0, description="字节数, 20MB 上限在 router 校验, 返 413 而非 422")
    mime: str = Field(
        ..., min_length=1, max_length=100, description="MIME, 例: 'image/png' / 'application/pdf'; 前缀须匹配白名单"
    )


class PresignChatFileResponse(BaseModel):
    """presign 响应: 签 PUT URL + URI"""

    uri: str = Field(..., description="完整 URI, 例: 's3://rag-ingest/chat/{user_id}/image.png'")
    put_url: str = Field(..., description="预签名 PUT URL, 浏览器直传, 900s 有效")
    mime: str = Field(..., description="MIME, 透传自 request, 用于 client 校验一致性")


class FinalizeChatFileRequest(BaseModel):
    """finalize 请求体: 前端 PUT 完, 通知后端转发到 Dify"""

    uri: str = Field(..., min_length=1, max_length=500, description="presign 返的 URI; 必须在 store 存在")
    name: str = Field(..., min_length=1, max_length=255, description="文件名, 用于 Dify uploadFileId 关联")
    mime: str = Field(..., min_length=1, max_length=100, description="MIME, 用于 Dify uploadFileId 关联")


class FinalizeChatFileResponse(BaseModel):
    """finalize 响应: Dify uploadFileId + URI 透传"""

    uploadFileId: str = Field(..., description="Dify uploadFileId, 用于后续对话引用此文件")
    uri: str = Field(..., description="MinIO/S3 URI, 例: 's3://rag-ingest/chat/{user_id}/image.png'")
