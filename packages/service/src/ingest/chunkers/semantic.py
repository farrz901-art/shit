"""Semantic 切: 句切 + embedder cosine 距离, 高于阈值合并, 低于切分

思路同 Microsoft GraphRAG (2026 H1 仍维护 3.1.0 MIT)
2026 H1 调研: LightRAG/HippoRAG/RAPTOR 在多个 benchmark 跑赢 GraphRAG
  (e.g. arXiv:2606.29399 ICML 2026 Workshop GraphRAG 49.5% vs LightRAG 73.0%),
  且 GraphRAG 提取管线带 19-53% token 开销. 所以选自实现的 deterministic splitter.

降级: embedder 抛错 → fallback heading splitter + log warning
"""

from __future__ import annotations

import math
import re

from loguru import logger

from .base import TextChunk, _make_chunk_id
from .heading import HeadingSplitter

_SENT_RE = re.compile(r"[^。！？.!?]+[。！？.!?]+")


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


class SemanticSplitter:
    """按语义相似度合并相邻句

    Args:
        embedder: 注入的 embedder (项目 OpenAIEmbedder 或 mock)
        cosine_threshold: 相邻句 cosine 距离阈值; < 阈值合并, >= 阈值切分
        min_chunk_size: 单 chunk 最小字符数 (防太碎)
        max_chunk_size: 单 chunk 最大字符数 (防超 LLM 上下文)
    """

    splitter_id = "semantic"

    def __init__(
        self,
        embedder,
        cosine_threshold: float = 0.5,
        min_chunk_size: int = 200,
        max_chunk_size: int = 2000,
    ):
        self.embedder = embedder
        self.cosine_threshold = cosine_threshold
        self.min_chunk_size = min_chunk_size
        self.max_chunk_size = max_chunk_size

    def split(self, text: str, source_uri: str) -> list[TextChunk]:
        try:
            sentences = [s.strip() for s in _SENT_RE.findall(text) if s.strip()]
            if not sentences:
                return HeadingSplitter().split(text, source_uri)
            embeddings = self.embedder.embed_batch(sentences)
            return self._merge_by_cosine(sentences, embeddings, source_uri)
        except Exception as e:
            logger.warning("SemanticSplitter 降级到 HeadingSplitter ({}): {}", source_uri, e)
            return HeadingSplitter().split(text, source_uri)

    def _merge_by_cosine(self, sentences, embeddings, source_uri):
        chunks: list[TextChunk] = []
        current_group: list[str] = []
        current_text = ""
        for idx, (sent, emb) in enumerate(zip(sentences, embeddings)):
            if not current_group:
                current_group.append(sent)
                current_text = sent
                continue
            prev_emb = embeddings[idx - 1]
            dist = 1.0 - _cosine(prev_emb, emb)
            if dist < self.cosine_threshold and len(current_text) < self.max_chunk_size:
                current_group.append(sent)
                current_text += sent
            else:
                if len(current_text) >= self.min_chunk_size or not chunks:
                    chunks.append(
                        TextChunk(
                            chunk_id=_make_chunk_id(current_text, source_uri, len(chunks)),
                            text=current_text,
                            meta={
                                "start_idx": idx - len(current_group),
                                "sentence_count": len(current_group),
                            },
                        )
                    )
                current_group = [sent]
                current_text = sent
        if current_text:
            chunks.append(
                TextChunk(
                    chunk_id=_make_chunk_id(current_text, source_uri, len(chunks)),
                    text=current_text,
                    meta={
                        "start_idx": len(sentences) - len(current_group),
                        "sentence_count": len(current_group),
                    },
                )
            )
        return chunks
