"""rag 包: RAG 系统 (LangChain 1.x + DeepEval)

分层结构:
- ingest/      文档摄取
- api/         HTTP 接口层 (FastAPI routes + schemas)
- common/      共享工具 (chunk/doc/embed/token/batch + RAGDoc)
- retrieval/   检索层 (embedder + LC PGVectorStore)
- generation/  生成层 (ChatOpenAI/ChatOllama + LCEL chain)
- memory/      记忆层 (Mem0)
- kg/          知识图谱 (Neo4j)
- eval/        评估子系统 (DeepEval 5 指标 + 评估批 CRUD)
- auth/        鉴权
- telemetry/   可观测性 (Langfuse)
"""
# ruff: noqa: E402  # 故意: register_routers() 在顶层 import 前定义, 供 product_decoders/app.py 一次性调用


def _register_orm_models() -> None:
    """force import ORM models, 触发 model class 注册到 Base.metadata.

    (2026-06-30) SA 2.0 懒解析 FK, chat_shares.conv_id FK → conversations.id,
    不 import 这些 models, Base.metadata 不知道 conversations 存在,
    commit 时 sort_tables 炸 NoReferencedTableError.

    只 import 真有 SQLAlchemy ORM model 的包. router 链已触发注册的 (approvals / chat_share
    / ingest / lookups / permissions) 不重复 import — 它们的 router 顶部直接 import models.
    chat 走 raw SQL, router 不触发, 必须 force.
    """
    from .chat import models as _chat_models  # noqa: F401
    from .eval import models as _eval_models  # noqa: F401


def register_routers(app) -> None:
    """把所有 RAG 子模块的 FastAPI 路由注册到 app.

    由 src/core/app_factory.py 的 create_app() 调用一次.
    各 router 各自独立 prefix, 不叠加.
    """
    _register_orm_models()

    from .api import router as rag_router
    from .approvals.router import router as approvals_router
    from .auth.account_settings_router import (
        router as account_settings_router,  # (2026-06-17) profile/avatar/email/password/deletion
    )
    from .auth.auth_account_router import router as account_router
    from .auth.auth_admin_router import router as admin_router
    from .auth.auth_invite_router import router as invite_router
    from .auth.router import router as auth_router
    from .buyer_profile.router import router as buyer_profile_router  # (2026-06-22) 新增
    from .chat.router import router as chat_router  # (2026-06-19) 新增 7 端点 + soft delete
    from .chat_share.router import router as chat_share_router  # (2026-06-16) 新增
    from .eval.router import router as eval_router
    from .health.router import router as health_router  # (2026-06-11) 新增
    from .ingest.pdf_processing import (
        ingest_router,
    )
    from .ingest.pre_analysis import pre_analysis_router  # (2026-07-02) PDF 预分析
    from .kg.router import router as kg_router
    from .lookups.admin_router import (
        router as lookups_admin_router,  # (2026-06-19) POST/PATCH/DELETE /api/admin/dicts/*
    )
    from .lookups.router import router as lookups_router  # (2026-06-19) GET /api/lookups/*
    from .memory.router import memory_router  # (2026-06-16) 新增
    from .permissions.router import router as permissions_router  # (2026-06-17) RBAC v2

    app.include_router(rag_router)  # /api/v1/*
    app.include_router(kg_router)  # /api/kg/*
    app.include_router(eval_router)  # /api/evaluate/*
    app.include_router(ingest_router)  # /api/ingest/*
    app.include_router(pre_analysis_router)  # /api/pre-analysis/* (2026-07-02)
    app.include_router(auth_router)  # /api/auth/*
    app.include_router(account_router)  # /api/account/*  (2026-06-13 Task 4)
    app.include_router(
        account_settings_router
    )  # /api/account/{profile,avatar,email,password,deletion}/*  (2026-06-17 T2.1+)
    app.include_router(admin_router)  # /api/admin/*  (2026-06-13 Task 11)
    app.include_router(invite_router)  # /api/invites/*  (2026-06-13 Task 9)
    app.include_router(approvals_router)  # /api/approvals/*  (2026-06-13 Task 7)
    app.include_router(health_router)  # /api/health/*  (2026-06-11) 新增
    app.include_router(memory_router)  # /api/memory/*  (2026-06-16) 新增
    app.include_router(buyer_profile_router)  # /api/buyer-profiles/*  (2026-06-22) 新增
    app.include_router(lookups_router)  # /api/lookups/*  (2026-06-19) 新增
    app.include_router(lookups_admin_router)  # /api/admin/dicts/*  (2026-06-19) T6 写 API + super_admin 守卫
    app.include_router(chat_share_router)  # /api/chat/*  (2026-06-16) 新增
    app.include_router(chat_router)  # /api/chat/*  (2026-06-19) 7 端点 + soft delete
    app.include_router(permissions_router)  # /api/permissions/* + /api/roles/*  (2026-06-17 RBAC v2 Phase 2)


# Ingest
# API
from .api import router

# Common
from .common import (
    EvaluationReport,
    RAGAMetrics,
    batch_embed,
    chunk_documents,
    documents_to_texts,
    estimate_tokens,
    filter_empty_documents,
    generate_evaluation_dataset,
    load_documents_from_files,
    load_md_files,
    load_txt_files,
    truncate_text,
)

# Generation
from .generation import (
    LocalLLM,
    OpenAILLM,
    QueryResult,
    aquery,
    build_query_engine,
    get_llm,
    query,
)
from .ingest.pdf_processing import (
    PDFAnalyzer,
    PDFInfo,
    analyze_pdf_complexity,
    get_converter,
    process_cad_files,
    process_documents,
    process_files,
    process_passthrough,
)

# Knowledge Graph
from .kg import BatchResult, KgClient, Neo4jConfig, Neo4jStore, TripleRow, get_neo4j_store

# Memory (2026-06-16: mem0 self-host, 新 export 见 src.memory.service / src.memory.router)
# 旧的 4 个 helper (add_document_memory / build_memory_enhanced_prompt / get_mem0_store /
# retrieve_with_memory) 全部删除, 确认无调用方.
# Retrieval
from .retrieval import (
    AsyncPGVectorStore,
    OpenAIEmbedder,
    PGVectorConfig,
    PGVectorStore,
    add_to_vector_store,
    delete_from_vector_store,
    embed_documents,
    embed_texts,
    get_embedder,
    get_embedding_dimension,
    get_vector_store,
    init_pgvector,
    is_embedder_ready,
)

# Telemetry
from .telemetry import (
    RAGTraceContext,
    get_langfuse_client,
    trace_rag_step,
)

__all__ = [
    # ingest
    "process_files",
    "process_documents",
    "process_cad_files",
    "process_passthrough",
    "PDFAnalyzer",
    "analyze_pdf_complexity",
    "PDFInfo",
    "get_converter",
    # retrieval
    "get_embedder",
    "get_vector_store",
    "PGVectorStore",
    "AsyncPGVectorStore",
    "PGVectorConfig",
    "init_pgvector",
    "add_to_vector_store",
    "delete_from_vector_store",
    "OpenAIEmbedder",
    "embed_documents",
    "embed_texts",
    "get_embedding_dimension",
    "is_embedder_ready",
    # generation
    "build_query_engine",
    "query",
    "aquery",
    "QueryResult",
    "get_llm",
    "OpenAILLM",
    "LocalLLM",
    # memory (2026-06-16: 旧 export 删, 新 export 走 src.memory.{service,router})
    # 保留空注释, 后续 spec 加 mem0 service export 时再补 __all__ 条目
    # knowledge_graph (kg)
    "get_neo4j_store",
    "Neo4jStore",
    "Neo4jConfig",
    "KgClient",
    "TripleRow",
    "BatchResult",
    # workflows (2026-06-29: orchestration 子包删, 0 调用)
    # telemetry
    "get_langfuse_client",
    "RAGTraceContext",
    "trace_rag_step",
    # common
    "chunk_documents",
    "load_md_files",
    "load_txt_files",
    "load_documents_from_files",
    "filter_empty_documents",
    "documents_to_texts",
    "estimate_tokens",
    "truncate_text",
    "batch_embed",
    "RAGAMetrics",
    "EvaluationReport",
    "generate_evaluation_dataset",
    # api
    "router",
]
