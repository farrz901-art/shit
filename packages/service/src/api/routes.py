"""FastAPI 路由"""

import time

from fastapi import APIRouter

# TODO: 加 @audited("admin.access") 中间件 (2026-06-18 sync)
# TODO: 加 audit.read_self 端点 (2026-06-18 sync)
from .schemas import (
    IngestRequest,
    IngestResponse,
    QueryRequest,
    QueryResponse,
    SourceNode,
)

router = APIRouter(prefix="/api/v1", tags=["rag"])


@router.post(
    "/query",
    response_model=QueryResponse,
    summary="RAG 检索查询",
    description=(
        "## 用途\n\n"
        "对 RAG 向量库发起一次检索 + 生成查询 (LangChain LCEL chain), "
        "返回答 + 命中的 source 节点 + 延迟.\n\n"
        "## 鉴权\n\n"
        "无 (内部脚本 / 离线评估流水线用, 不对外开放).\n\n"
        "## 行为\n\n"
        "请求体 {query: str, top_k?: int=5}; top_k 范围 1-100. "
        "返 {response: str, sources: [{text, score, metadata}], latency_ms: float}. "
        "后端异常 (LLM 不可达 / vector store 挂) → 500."
    ),
    responses={
        200: {"description": "返 QueryResponse: response + sources[] + latency_ms"},
        422: {"description": "Pydantic 校验失败 (query 缺失 / top_k 越界)"},
        500: {"description": "后端异常 (LLM / vector store 不可达)"},
    },
)
def query_endpoint(req: QueryRequest):
    """RAG 查询"""
    start = time.perf_counter()
    # (2026-06-26 ERR-001) 不再 catch → raise HTTPException(500, str(e)),
    # 避免把 str(e) (含模型名/路径) 泄露给客户端. 让全局 exception handler
    # (src/core/errors.py:unhandled_exc) 统一返 "Internal server error",
    # 详细异常走 loguru + error_logs 留给运维.
    # 重依赖 lazy: generation + retrieval 触发 langchain_* 装载链, 非 /query 路径不需要
    from ..generation import build_query_engine  # noqa: E402
    from ..generation import query as do_query  # noqa: E402
    from ..retrieval import get_embedder, get_vector_store  # noqa: E402

    vs = get_vector_store()
    embedder = get_embedder()
    # OpenAIEmbedder 是项目封装, 鸭子类型实现 BaseEmbedding 接口 (项目内未继承)
    qe = build_query_engine(vs, embedder, top_k=req.top_k)
    result = do_query(req.query, qe)
    return QueryResponse(
        response=result.response,
        sources=[SourceNode(**s) for s in result.sources],
        latency_ms=(time.perf_counter() - start) * 1000,
    )


@router.post(
    "/ingest",
    response_model=IngestResponse,
    summary="触发文档摄取",
    description=(
        "## 用途\n\n"
        "同步触发一次文档摄取流水线, 把 input_dir 下文件处理后写到 output_dir.\n\n"
        "## 鉴权\n\n"
        "无 (内部脚本 / 离线构建用, 不对外开放).\n\n"
        "## 行为\n\n"
        "请求体 IngestRequest {input_dir: str, output_dir: str}; input_dir/output_dir 走本地 FS. "
        "调 process_files; 返 {status, processed, errors}: "
        "input_dir 为空 → status='no_files' (processed=0, errors=0); "
        "正常 → status='ok' (processed / errors 从 result.document 聚合). "
        "异常 → 500."
    ),
    responses={
        200: {"description": "返 IngestResponse: status + processed + errors"},
        422: {"description": "Pydantic 校验失败 (路径缺失)"},
        500: {"description": "摄取异常 (parser / embedder 失败)"},
    },
)
def ingest_endpoint(req: IngestRequest):
    """触发文档摄取"""
    # (2026-06-26 ERR-001) 不再 catch → raise HTTPException(500, str(e)),
    # 让全局 exception handler 统一处理. 避免泄露路径/解析器细节.
    # 重依赖 lazy: ingest.pdf_processing 触发 kreuzberg / ezdxf / docker 装载
    from ..ingest import process_files  # noqa: E402

    result = process_files(input_dir=req.input_dir, output_dir=req.output_dir)
    if result is None:
        return IngestResponse(status="no_files", processed=0, errors=0)
    processed = len(result.get("document", {}).get("processed", []))
    errors = len(result.get("document", {}).get("errors", []))
    return IngestResponse(status="ok", processed=processed, errors=errors)


@router.get(
    "/health",
    summary="RAG 子系统 health",
    description=(
        "## 用途\n\n"
        "RAG 子系统 liveness ping — 用来确认 query engine / vector store 进程在跑.\n\n"
        "## 鉴权\n\n"
        "无 (内部脚本 / 监控用).\n\n"
        "## 行为\n\n"
        "无 IO, 直接返 {status: 'ok'}. "
        "跟 /api/health/system 不同 (那个是 super_admin 才看, 含 DB/MinIO/Dify/LLM/Mem0 5 类检查), "
        "这个只 ping RAG 进程本身, 永不带鉴权."
    ),
    responses={
        200: {"description": "返 {status: 'ok'}"},
    },
)
def health_endpoint():
    return {"status": "ok"}
