"""Memory 模块 Pydantic schemas (2026-06-16)"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    """记忆检索请求"""

    query: str = Field(..., min_length=1, max_length=2000, description="查询文本")
    limit: int = Field(5, ge=1, le=20, description="检索条数")


class MemoryHit(BaseModel):
    """单条记忆命中"""

    id: str = Field(..., description="记忆 ID, Mem0 内部唯一")
    text: str = Field(..., description="记忆内容文本")
    score: float | None = Field(None, description="相似度分数, 0.0-1.0, 越高越相关")
    metadata: dict | None = Field(None, description="Mem0 元数据, 自由 JSON")


class SearchResponse(BaseModel):
    """记忆检索响应 (降级时 memories=[])"""

    memories: list[MemoryHit] = Field(default_factory=list, description="相关记忆")


class TurnMessage(BaseModel):
    """单轮对话消息"""

    role: Literal["user", "assistant"] = Field(..., description="消息角色")
    content: str = Field(..., min_length=1, max_length=32000, description="消息内容")


class AddRequest(BaseModel):
    """记忆写入请求"""

    messages: list[TurnMessage] = Field(..., min_length=1, max_length=20, description="本轮完整对话")
    conversation_id: str | None = Field(
        None, max_length=128, description="Dify conversation_id, 写到 metadata 便于回溯"
    )
    buyer_key: str | None = Field(None, max_length=128, description="买家标识 (如 whatsapp:+234...), 触发 LLM 画像提取")


# ---- Phase 2 (2026-06-16): 记忆管理 ----


class MemoryListResponse(BaseModel):
    """记忆列表响应 (Phase 2: GET /api/memory/list)"""

    memories: list[MemoryHit] = Field(default_factory=list, description="当前用户所有记忆")


class UpdateRequest(BaseModel):
    """编辑单条记忆请求 (Phase 2: PATCH /api/memory/{id})"""

    text: str = Field(..., min_length=1, max_length=32000, description="新记忆内容")


class DeleteResponse(BaseModel):
    """清空所有记忆响应 (Phase 2: DELETE /api/memory/all)
    mem0 delete_all 不返 count, 占位返 0 让前端不依赖具体数值"""

    deleted_count: int = Field(0, ge=0, description="删除的条数 (占位)")
