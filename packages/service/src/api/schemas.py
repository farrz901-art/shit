"""Pydantic request/response schemas"""

from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000, description="用户查询文本")
    user_id: str | None = Field(None, description="用户 ID, 用于 Mem0 记忆检索; null = 跳过记忆")
    top_k: int = Field(5, ge=1, le=100, description="检索条数, 默认 5")


class SourceNode(BaseModel):
    file_path: str = Field("", description="源文件路径, 例: '/data/docs/manual.pdf'")
    page_label: str = Field("", description="页码标签, 例: '3' / 'A-2'")
    text: str = Field("", description="源文本片段")


class QueryResponse(BaseModel):
    response: str = Field(..., description="LLM 生成的最终回答文本")
    sources: list[SourceNode] = Field(default_factory=list, description="检索到的源文档片段列表, 用于引用展示")
    latency_ms: float = Field(0.0, description="查询总耗时 (毫秒), 含 retrieval + LLM 推理")


class IngestRequest(BaseModel):
    input_dir: str | None = Field(None, description="本地 FS 绝对路径")
    output_dir: str | None = Field(None, description="本地 FS 绝对路径")


class IngestResponse(BaseModel):
    status: str = Field(..., description="ingest 状态, 例: 'success' / 'partial' / 'failed'")
    processed: int = Field(0, description="成功处理的文档条数")
    errors: int = Field(0, description="处理失败条数")
