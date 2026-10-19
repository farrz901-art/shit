"""rag_ingest 业务包（多格式文档 → markdown 流水线）

public API 包含:
- PDF 转 markdown: pdf_processing/ 子包
- PDF 预分析: pre_analysis/ 子包
- Markdown 文本切片器: chunkers/ 子包 (via src.ingest.chunkers, kg/RAG 引用入口)
"""

from .pdf_processing import (
    IngestTask,
    OutputFile,
    PDFAnalyzer,
    PDFInfo,
    analyze_pdf_complexity,
    get_converter,
    ingest_router,
    process_cad_files,
    process_documents,
    process_files,
    process_passthrough,
)
from .pre_analysis import pre_analysis_router  # noqa: F401  # (2026-07-02) PDF 预分析 router

__all__ = [
    "process_files",
    "process_documents",
    "process_cad_files",
    "process_passthrough",
    "PDFAnalyzer",
    "analyze_pdf_complexity",
    "PDFInfo",
    "get_converter",
    "ingest_router",
    "IngestTask",
    "OutputFile",
    "pre_analysis_router",
]
