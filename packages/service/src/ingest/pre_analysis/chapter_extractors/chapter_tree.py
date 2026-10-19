"""PDF 章节树状化工具函数 (2026-07-09).

提供:
- build_chapter_tree: PyMuPDF get_toc() 平铺 list → 嵌套树 + page_end 推导
- cluster_by_font_size: 字体聚类 fallback (outline 为空时)
- detect_toc_pages: 视觉目录页检测
- parse_toc_pages: 目录页 → chapter entries
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterator
from typing import Any


def build_chapter_tree(
    raw_toc: list[tuple[int, str, int]],  # [(level, title, page_start), ...]
    total_pages: int,
    max_level: int = 6,
) -> list[dict]:
    """从 PyMuPDF doc.get_toc() 平铺 list 转嵌套树, page_end 推导.

    单调栈算法:
    1. 遍历每个 (level, title, page_start), level > max_level 跳过
    2. 当 stack 顶层 level >= 当前 level, pop 回父级
    3. 当前节点入栈顶层 children, 再 push 自身到 stack
    4. 后序遍历推导 page_end (enumerate O(N))

    Args:
        raw_toc: [(level, title, page_start), ...] — doc.get_toc() 输出.
        total_pages: PDF 总页数, 末节点 page_end 用.
        max_level: 最大层级, level > max_level 跳过 (截断).

    Returns:
        list[dict]: 嵌套树, 每个节点 {id, level, title, page_start, page_end, children}.
    """
    root_children: list[dict] = []
    children_stack: list[list[dict]] = [root_children]
    level_stack: list[int] = [0]  # 哨兵 level 0
    counter = 0
    for level, title, page_start in raw_toc:
        if level > max_level:
            continue
        counter += 1
        node = {
            "id": f"ch_{counter}",
            "level": level,
            "title": title,
            "page_start": page_start,
            "page_end": 0,  # 后续推导
            "children": [],
        }
        while level_stack[-1] >= level:
            children_stack.pop()
            level_stack.pop()
        children_stack[-1].append(node)
        children_stack.append(node["children"])
        level_stack.append(level)

    # 后序: 推导 page_end (enumerate O(N))
    def _compute_end(children: list[dict], parent_end: int) -> None:
        for idx, node in enumerate(children):
            if idx + 1 < len(children):
                # (2026-07-09 D81 fix) 兄弟同 page_start 时共享物理页,
                # 自身 page_end = 自己 page_start (而不是 next.page_start - 1).
                # 不同页时按传统区间 next.page_start - 1.
                # 关键: 不要用 parent_end 钳非末节点 — parent_end 可能极小
                # (例 ch_1.page_end=1 因为下一个 L1 紧跟 page 2),
                # 会让子节点算成 page_end < page_start.
                next_start = children[idx + 1]["page_start"]
                if next_start == node["page_start"]:
                    node_end = node["page_start"]
                else:
                    node_end = next_start - 1
            else:
                # 末节点 = parent_end. 若 parent_end < page_start (PDF 数据不一致:
                # 子节点 page_start 超出父声明区间), 用 page_start 兜底, 让 page_end >= page_start.
                node_end = max(node["page_start"], parent_end)
            node["page_end"] = node_end
            if node["children"]:
                _compute_end(node["children"], node_end)

    _compute_end(root_children, total_pages)
    return root_children


def _candidate_spans(doc: Any, max_pages: int = 30) -> Iterator[tuple[int, dict]]:
    """生成器: yield (page_no, span) 元组. 过滤 size + 位置 (页面顶部 70% 区域)."""
    for page_idx in range(min(max_pages, len(doc))):
        page_no = page_idx + 1
        page_height = doc[page_idx].rect.height
        for block in doc[page_idx].get_text("dict").get("blocks", []):
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    size = round(span.get("size", 0), 1)
                    if not (10 <= size <= 30):
                        continue
                    bbox = span.get("bbox", [0, 0, 0, 0])
                    if bbox[1] > page_height * 0.7:
                        continue
                    fontname = span.get("font", "")
                    if "Italic" in fontname or "Oblique" in fontname:
                        continue
                    yield (page_no, span)


def cluster_by_font_size(doc: Any, max_pages: int = 30) -> list[tuple[int, str, int]]:
    """PDF outline 为空时, 用 font-size + 位置 + 字体名过滤找候选 heading.

    Args:
        doc: pymupdf Document (已 open).
        max_pages: 扫描前 N 页.

    Returns:
        list[(level, title, page_start), ...] — 跟 get_toc() 同 shape, 可喂 build_chapter_tree.
    """
    size_counter: Counter[float] = Counter(round(span["size"], 1) for _, span in _candidate_spans(doc, max_pages))
    top_sizes = [s for s, _ in size_counter.most_common(3)]
    if not top_sizes:
        return []

    candidates: list[tuple[int, str, int]] = []
    seen_pages: set[int] = set()
    for page_no, span in _candidate_spans(doc, max_pages):
        if page_no in seen_pages:
            continue
        size = round(span["size"], 1)
        if size in top_sizes:
            text = span.get("text", "").strip()
            if text and len(text) > 1 and not re.match(r"^\d+/\d+$", text):
                level = top_sizes.index(size) + 1
                candidates.append((level, text, page_no))
                seen_pages.add(page_no)
    return candidates


def detect_toc_pages(doc: Any, max_scan: int = 20) -> list[int]:
    """扫描前 max_scan 页找含 'Contents' 标题 + dotted-leader 行的目录页.

    Args:
        doc: pymupdf Document (已 open).
        max_scan: 扫描前 N 页.

    Returns:
        list[int]: 命中目录页的 page_index (0-based).
    """
    headers = ("table of contents", "contents", "目录", "目  录", "目 录")
    hits: list[int] = []
    for page_idx in range(min(max_scan, len(doc))):
        text = (doc[page_idx].get_text() or "").lower()
        head = text[:300]
        for kw in headers:
            if kw in head:
                leader_lines = re.findall(r"\.{3,}\s*\d{1,4}\s*$", text, re.MULTILINE)
                if len(leader_lines) >= 5:
                    hits.append(page_idx)
                break
    return hits


def parse_toc_pages(doc: Any, page_indices: list[int]) -> list[tuple[int, str, int]]:
    """从目录页文本解析 (level, title, page_start) 三元组.

    Args:
        doc: pymupdf Document (已 open).
        page_indices: detect_toc_pages 返回的页索引列表.

    Returns:
        list[(level, title, page_start), ...] — 可喂 build_chapter_tree.
    """
    raw_lines: list[tuple[int, str, int]] = []
    for page_idx in page_indices:
        text = doc[page_idx].get_text() or ""
        lines = text.split("\n")
        for line in lines:
            line_stripped = line.strip()
            if not line_stripped:
                continue
            match = re.match(r"^(?P<title>.+?)\.+\s*(?P<page>\d{1,4})\s*$", line_stripped)
            if match:
                title = match.group("title").strip()
                page_start = int(match.group("page"))
                indent = len(line) - len(line.lstrip())
                level = min(indent // 2 + 1, 6)
                num_match = re.match(r"^(\d+(?:\.\d+)*)\s", title)
                if num_match:
                    level = min(num_match.group(1).count(".") + 1, 6)
                raw_lines.append((level, title, page_start))
    return raw_lines


__all__ = [
    "build_chapter_tree",
    "cluster_by_font_size",
    "detect_toc_pages",
    "parse_toc_pages",
]
