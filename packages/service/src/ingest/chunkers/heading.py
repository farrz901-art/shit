"""Heading 切: Markdown # / ## / ### 切, 保留 heading_path 层级

算法:
1. 正则匹配 # / ## / ### heading
2. 每个 heading 开始到下一个 heading 之前 = 一个 chunk
3. 从当前 chunk 往前回溯父 heading, 构建 heading_path
"""

from __future__ import annotations

import re

from .base import TextChunk, _make_chunk_id

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.MULTILINE)


class HeadingSplitter:
    """按 Markdown heading 切 (# / ## / ### / ... 最多 6 级)

    每个 chunk 保留 heading_path (e.g. ['H1', 'H2', 'H3-1']),
    供抽取器识别上下文.

    适用: 结构化 Markdown 文档 (PDF→MD 转换结果, 已有完整 heading 层级)
    """

    splitter_id = "heading"

    def split(self, text: str, source_uri: str) -> list[TextChunk]:
        chunks: list[TextChunk] = []
        matches = list(_HEADING_RE.finditer(text))
        if not matches:
            # 整段一个 chunk
            return [
                TextChunk(
                    chunk_id=_make_chunk_id(text, source_uri, 0),
                    text=text,
                    meta={"heading_path": [], "start_line": 0},
                )
            ]

        for idx, m in enumerate(matches):
            start = m.start()
            end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
            section_text = text[start:end].rstrip()
            heading_path = self._build_heading_path(matches, idx)
            chunks.append(
                TextChunk(
                    chunk_id=_make_chunk_id(section_text, source_uri, idx),
                    text=section_text,
                    meta={
                        "heading_path": heading_path,
                        "start_line": text[:start].count("\n"),
                    },
                )
            )
        return chunks

    @staticmethod
    def _build_heading_path(matches: list[re.Match], idx: int) -> list[str]:
        """从 idx 往前回溯, 构建 heading 层级

        算法:
        - 从当前 heading 开始
        - 往前找 level 更小的 heading (父级), 插入 path 开头
        - 直到回到 H1 (level 1)
        """
        path: list[str] = []
        current_heading = matches[idx]
        current_level = current_heading.group(1).count("#")
        path.insert(0, current_heading.group(2).strip())

        for i in range(idx - 1, -1, -1):
            level = matches[i].group(1).count("#")
            if level < current_level:
                path.insert(0, matches[i].group(2).strip())
                current_level = level
                if current_level <= 1:
                    break
        return path
