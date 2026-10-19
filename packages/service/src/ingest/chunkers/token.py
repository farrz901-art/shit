"""Token 滑窗: tiktoken cl100k_base, 切窗口 + overlap

cl100k_base 编码: GPT-4 / Claude / DeepSeek 都用此编码族
适用: 通用 fallback, 任何纯文本 (不限 Markdown)
"""

from __future__ import annotations

import tiktoken

from .base import TextChunk, _make_chunk_id

_ENCODER = tiktoken.get_encoding("cl100k_base")


class TokenSplitter:
    """按 token 切 (cl100k_base)

    Args:
        chunk_size: 每个 chunk 最大 token 数 (默认 512, 约 ~2000 字符)
        overlap: 相邻 chunk 重叠 token 数 (默认 32, 约 6% overlap, 防切碎语义)
    """

    splitter_id = "token"

    def __init__(self, chunk_size: int = 512, overlap: int = 32):
        if overlap >= chunk_size:
            raise ValueError(f"overlap ({overlap}) 必须 < chunk_size ({chunk_size})")
        self.chunk_size = chunk_size
        self.overlap = overlap

    def split(self, text: str, source_uri: str) -> list[TextChunk]:
        tokens = _ENCODER.encode(text)
        if not tokens:
            return []

        chunks: list[TextChunk] = []
        stride = self.chunk_size - self.overlap
        idx = 0
        chunk_idx = 0
        while idx < len(tokens):
            window = tokens[idx : idx + self.chunk_size]
            chunk_text = _ENCODER.decode(window)
            chunks.append(
                TextChunk(
                    chunk_id=_make_chunk_id(chunk_text, source_uri, chunk_idx),
                    text=chunk_text,
                    meta={
                        "start_token": idx,
                        "token_count": len(window),
                    },
                )
            )
            idx += stride
            chunk_idx += 1
        return chunks
