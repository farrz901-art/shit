"""common 子包: 共享工具 (chunker, document_loader, batch_utils, evaluation, defaults)"""

from . import defaults
from .batch_utils import batch_embed, estimate_tokens, truncate_text
from .chunker import chunk_documents
from .document import RAGDoc
from .document_loader import (
    documents_to_texts,
    extract_plain_text,
    filter_empty_documents,
    load_documents_from_files,
    load_md_files,
    load_txt_files,
)
from .evaluation import EvaluationReport, RAGAMetrics, generate_evaluation_dataset

__all__ = [
    "defaults",
    # chunker
    "chunk_documents",
    # document
    "RAGDoc",
    # document_loader
    "load_md_files",
    "load_txt_files",
    "load_documents_from_files",
    "filter_empty_documents",
    "extract_plain_text",
    "documents_to_texts",
    # batch_utils
    "estimate_tokens",
    "truncate_text",
    "batch_embed",
    # evaluation
    "RAGAMetrics",
    "EvaluationReport",
    "generate_evaluation_dataset",
]
