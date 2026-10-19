"""BaseSplitter Protocol + TextChunk dataclass

每个 splitter 的输出是 list[TextChunk]:
- chunk_id: sha256(source_uri + idx + text)[:12], 保证同输入同 id
- text: 切片文本
- meta: heading_path (结构文档) / start_token (滑窗) / 等
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Protocol, cast, runtime_checkable


@dataclass
class TextChunk:
    """Markdown 切片器输出"""

    chunk_id: str  # sha256(source_uri + idx + text)[:12]
    text: str
    meta: dict = field(default_factory=dict)  # heading_path / start_line / token_count


@runtime_checkable
class BaseSplitter(Protocol):
    splitter_id: str

    def split(self, text: str, source_uri: str) -> list[TextChunk]: ...


def _make_chunk_id(text: str, source_uri: str, idx: int) -> str:
    """sha256(source_uri + '#' + idx) + sha256(text) → 拼 12 字符

    加 idx 是因为同一文本在同一 source 不同切片 (e.g. H1, H2, H3) 需不同 id.
    """
    h = hashlib.sha256(f"{source_uri}#{idx}".encode())
    h.update(text.encode("utf-8"))
    return cast(str, h.hexdigest()[:12])  # hexdigest 返 str
