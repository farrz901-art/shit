"""章节提取器测试 (mode 1 mock, 2026-07-08 + 2026-07-09).

(2026-07-09 树状化) extract() 返回嵌套树 (id/level/title/page_start/page_end/children),
不再是平铺 dict list. OutlineExtractor 加 max_level 截断.

覆盖:
- OutlineExtractor: 正常 toc / 空 toc / name 字段 / max_level 截断
- 工厂: 默认 / 显式 / 未知抛 ValueError
- 顶层 extract_chapters 入口: 默认策略 + 显式策略 + max_level 透传
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest


class TestOutlineExtractor:
    def test_normal_toc_returns_tree(self) -> None:
        """正常 outline → 嵌套树 (有 children + page_end 推导)."""
        from src.ingest.pre_analysis.chapter_extractors.outline import OutlineExtractor

        doc = MagicMock()
        doc.get_toc.return_value = [
            [1, "第一章", 1],
            [2, "1.1 节", 3],
        ]
        doc.__len__.return_value = 10
        result = OutlineExtractor().extract(doc)
        # 嵌套树: 1 个 L1, 含 1 个 L2 子节点
        assert len(result) == 1
        ch1 = result[0]
        assert ch1["level"] == 1
        assert ch1["title"] == "第一章"
        assert ch1["page_start"] == 1
        assert ch1["page_end"] == 10  # 末节点 = total_pages
        assert ch1["id"] == "ch_1"
        assert len(ch1["children"]) == 1
        s1 = ch1["children"][0]
        assert s1["level"] == 2
        assert s1["title"] == "1.1 节"
        assert s1["page_start"] == 3
        assert s1["page_end"] == 10  # 末节点 = 父 page_end
        assert s1["children"] == []

    def test_empty_toc_returns_empty_list(self) -> None:
        """PDF 无 outline → 返 [], 不报错."""
        from src.ingest.pre_analysis.chapter_extractors.outline import OutlineExtractor

        doc = MagicMock()
        doc.get_toc.return_value = []
        assert OutlineExtractor().extract(doc) == []

    def test_max_level_truncates(self) -> None:
        """max_level=1 → 仅 L1 节点, L2+ 跳过."""
        from src.ingest.pre_analysis.chapter_extractors.outline import OutlineExtractor

        doc = MagicMock()
        doc.get_toc.return_value = [
            [1, "章1", 1],
            [2, "1.1 节", 2],
            [2, "1.2 节", 3],
            [1, "章2", 5],
        ]
        doc.__len__.return_value = 10
        result = OutlineExtractor().extract(doc, max_level=1)
        assert len(result) == 2
        assert all(n["level"] == 1 for n in result)
        assert all(n["children"] == [] for n in result)

    def test_name_matches_toc_source_field(self) -> None:
        """name 字段跟 chapter_structure.json 的 toc_source 字符串一致."""
        from src.ingest.pre_analysis.chapter_extractors.outline import OutlineExtractor

        assert OutlineExtractor.name == "pdf_outline"


class TestFactory:
    def test_default_strategy_is_outline(self) -> None:
        """默认 strategy='outline' → OutlineExtractor 实例."""
        from src.ingest.pre_analysis.chapter_extractors import (
            OutlineExtractor,
            get_chapter_extractor,
        )

        ext = get_chapter_extractor()
        assert isinstance(ext, OutlineExtractor)

    def test_explicit_outline_strategy(self) -> None:
        from src.ingest.pre_analysis.chapter_extractors import (
            OutlineExtractor,
            get_chapter_extractor,
        )

        ext = get_chapter_extractor("outline")
        assert isinstance(ext, OutlineExtractor)

    def test_unknown_strategy_raises_value_error(self) -> None:
        """未知 strategy 抛 ValueError, 错误信息含 strategy 名."""
        from src.ingest.pre_analysis.chapter_extractors import get_chapter_extractor

        with pytest.raises(ValueError, match="未知章节策略"):
            get_chapter_extractor("foo")


class TestExtractChaptersEntry:
    def test_default_strategy(self) -> None:
        """顶层入口默认 outline 策略."""
        from src.ingest.pre_analysis.chapter_extractors import extract_chapters

        doc = MagicMock()
        doc.get_toc.return_value = [[1, "A", 1]]
        doc.__len__.return_value = 5
        result = extract_chapters(doc)
        assert len(result) == 1
        assert result[0]["title"] == "A"

    def test_explicit_strategy(self) -> None:
        """显式传 strategy='outline' 也走得通."""
        from src.ingest.pre_analysis.chapter_extractors import extract_chapters

        doc = MagicMock()
        doc.get_toc.return_value = []
        assert extract_chapters(doc, strategy="outline") == []

    def test_max_level_passed_through(self) -> None:
        """max_level 透传到 extractor."""
        from src.ingest.pre_analysis.chapter_extractors import extract_chapters

        doc = MagicMock()
        doc.get_toc.return_value = [
            [1, "章1", 1],
            [2, "1.1", 2],
            [1, "章2", 5],
        ]
        doc.__len__.return_value = 10
        result = extract_chapters(doc, max_level=1)
        assert all(n["level"] == 1 for n in result)
        assert all(n["children"] == [] for n in result)

    def test_unknown_strategy_propagates_value_error(self) -> None:
        """顶层入口同样抛 ValueError."""
        from src.ingest.pre_analysis.chapter_extractors import extract_chapters

        doc = MagicMock()
        with pytest.raises(ValueError, match="未知章节策略"):
            extract_chapters(doc, strategy="toc_page")


# (2026-07-09) count_chapters 递归统计所有章节节点数 (含嵌套子章节)
class TestCountChapters:
    def test_empty_returns_zero(self) -> None:
        """空树 → 0."""
        from src.ingest.pre_analysis.chapter_extractors import count_chapters

        assert count_chapters([]) == 0

    def test_flat_tree_returns_top_level_count(self) -> None:
        """5 顶层 (无 children) → 5."""
        from src.ingest.pre_analysis.chapter_extractors import count_chapters

        chapters = [
            {"id": "1", "children": []},
            {"id": "2", "children": []},
            {"id": "3", "children": []},
            {"id": "4", "children": []},
            {"id": "5", "children": []},
        ]
        assert count_chapters(chapters) == 5

    def test_nested_tree_counts_all_levels(self) -> None:
        """嵌套树 → 递归总数. 跟 len(chapters) 顶层数区分开.

        5 顶层 + 2 + 3 + 1 = 11 节点.
        """
        from src.ingest.pre_analysis.chapter_extractors import count_chapters

        chapters = [
            {
                "id": "1",
                "children": [
                    {"id": "1.1", "children": []},
                    {"id": "1.2", "children": []},
                ],
            },
            {
                "id": "2",
                "children": [
                    {"id": "2.1", "children": []},
                    {"id": "2.2", "children": []},
                    {"id": "2.3", "children": []},
                ],
            },
            {"id": "3", "children": []},
            {"id": "4", "children": []},
            {"id": "5", "children": [{"id": "5.1", "children": []}]},
        ]
        # 顶层 5 + 2 + 3 + 1 = 11
        assert count_chapters(chapters) == 11
        # 反例: 顶层数是 5 (跟 message 错误的旧行为一致)
        assert len(chapters) == 5

    def test_deeply_nested_tree(self) -> None:
        """深层嵌套 (4 层) → 递归正确."""
        from src.ingest.pre_analysis.chapter_extractors import count_chapters

        chapters = [
            {
                "id": "1",
                "children": [
                    {
                        "id": "1.1",
                        "children": [
                            {
                                "id": "1.1.1",
                                "children": [{"id": "1.1.1.1", "children": []}],
                            }
                        ],
                    }
                ],
            }
        ]
        # 1 + 1 + 1 + 1 = 4
        assert count_chapters(chapters) == 4
