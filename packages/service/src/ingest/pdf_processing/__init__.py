"""pdf_processing 子包 — PDF 转 markdown 流水线 (2026-07-06)."""

from .analyzers.pdf import PDFAnalyzer, PDFInfo, analyze_pdf_complexity
from .converters import get_converter
from .pipeline import (
    process_cad_files,
    process_documents,
    process_files,
    process_passthrough,
)
from .router import (  # noqa: F401  # 路由注册用
    IngestTask,
    OutputFile,
    ingest_router,
)

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
]
