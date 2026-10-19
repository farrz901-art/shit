"""ingest presign/finalize Pydantic schemas (2026-06-16 RAG MinIO 集成)"""

from __future__ import annotations

from pydantic import BaseModel, Field


class PresignFileItem(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="文件名, 例: 'manual.pdf'; 扩展名必须在白名单")
    size: int = Field(..., ge=0, le=200 * 1024 * 1024, description="字节数, 单文件 ≤ 200MB; 任务总 ≤ 200MB")
    mime: str = Field(..., min_length=1, max_length=100, description="MIME, 例: 'application/pdf' / 'image/png'")


class PresignUploadRequest(BaseModel):
    files: list[PresignFileItem] = Field(..., min_length=1, max_length=50, description="文件列表, 1-50 个")


class PresignUploadItem(BaseModel):
    name: str = Field(..., description="文件名")
    uri: str = Field(..., description="完整 URI, 例: 's3://rag-ingest/inputs/{task_id}/input/manual.pdf'")
    put_url: str | None = Field(None, description="预签名 PUT URL; local backend 可能为 null (走 fallback upload 端点)")
    mime: str = Field(..., description="MIME, 例: 'application/pdf' / 'image/png'")


class PresignUploadResponse(BaseModel):
    task_id: str = Field(..., description="摄取任务 ID, 用于后续 finalize / status 查询")
    uploads: list[PresignUploadItem] = Field(..., description="列表, 元素是 PresignUploadItem 对象 (含 put_url + URI)")


class FinalizeUploadRequest(BaseModel):
    task_id: str = Field(..., min_length=1, max_length=64, description="presign 返的 task_id")


class FinalizeUploadResponse(BaseModel):
    task_id: str = Field(..., description="摄取任务 ID, 跟 presign 一致")
    state: str = Field(..., description="摄取任务状态, 例: 'queued' / 'processing' / 'completed' / 'failed'")
