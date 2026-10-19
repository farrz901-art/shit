"""(2026-07-08 refactor) 段落切分. 4-mode 链 (spec §4.3).

提取自 runner.py:468-508 私有方法 _split_paragraphs, 改 module-level 函数
让上游直接调, 跟 table_extractors/ 的工厂模式对齐.
"""

from __future__ import annotations

import re
from typing import Any


def split_paragraphs(
    page: Any,  # pymupdf Page; 测试传 mock
    mode: str,
    max_sentence_chars: int = 200,
) -> list[str]:
    """(2026-07-07) 段落切分. 4 mode 链 (spec §4.3).

    Modes:
      - blocks: 用 pymupdf page.get_text("blocks") 返坐标块列表
      - double_newline: 按 \\n\\s*\\n 切, 段内 \\n 替空格
      - newline: 按 \\n 切 (默认 fallback 模式)
      - sentence_fallback: 按 [.!?] 切句, 滑窗合段 ≤ max_sentence_chars 字符

    Returns:
      段落文本列表, 已 strip + 去空段.
    """
    if mode == "blocks":
        # pymupdf get_text("blocks") 返 [(x0,y0,x1,y1,text,bn,bt), ...]
        # pymupdf API 复杂, 参数 Any 豁免
        blocks = page.get_text("blocks")
        return [str(b[4]).strip() for b in blocks if str(b[4]).strip()]
    if mode == "double_newline":
        text = page.get_text()
        paras = re.split(r"\n\s*\n", text)
        return [p.strip().replace("\n", " ") for p in paras if p.strip()]
    if mode == "newline":
        text = page.get_text()
        return [p.strip() for p in text.split("\n") if p.strip()]
    if mode == "sentence_fallback":
        text = page.get_text()
        sentences = re.split(r"(?<=[.?!])\s+", text)
        merged: list[str] = []
        buf = ""
        for s in sentences:
            s = s.strip()
            if not s:
                continue
            if len(buf) + len(s) <= max_sentence_chars:
                buf = (buf + " " + s).strip()
            else:
                if buf:
                    merged.append(buf)
                buf = s
        if buf:
            merged.append(buf)
        return merged
    raise ValueError(f"unknown paragraph_splitter mode: {mode}")
