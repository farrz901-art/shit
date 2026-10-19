"""(2026-07-09) Markdown 文本切片器

从 src/kg/splitters/ 搬来. 纯文本切片, 不依赖 kg/ingest 其他模块.
kg / 后续 RAG 等模块均可引用.

用法:
    from ingest.chunkers import HeadingSplitter, TokenSplitter, SemanticSplitter
    from ingest.chunkers.base import TextChunk, BaseSplitter
"""

from .base import BaseSplitter, TextChunk, _make_chunk_id
from .heading import HeadingSplitter
from .semantic import SemanticSplitter
from .token import TokenSplitter

__all__ = [
    "BaseSplitter",
    "TextChunk",
    "HeadingSplitter",
    "SemanticSplitter",
    "TokenSplitter",
    "_make_chunk_id",
]
