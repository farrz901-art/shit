"""chapter_tree.py 测试 (mode 1 mock, 2026-07-09).

覆盖:
- build_chapter_tree: 空/单节点/多层嵌套/截断/page_end 推导
- cluster_by_font_size: 正常/空/边界
- detect_toc_pages: 命中/未命中/多命中
- parse_toc_pages: 单行/多行/编号层级
"""

from __future__ import annotations

from unittest.mock import MagicMock


class TestBuildChapterTree:
    def test_empty_toc_returns_empty_list(self) -> None:
        """空 toc → []."""
        from src.ingest.pre_analysis.chapter_extractors.chapter_tree import build_chapter_tree

        assert build_chapter_tree([], total_pages=10) == []

    def test_single_node(self) -> None:
        """单节点 → [{id, level, title, page_start, page_end=total_pages, children: []}]."""
        from src.ingest.pre_analysis.chapter_extractors.chapter_tree import build_chapter_tree

        result = build_chapter_tree([(1, "第1章", 1)], total_pages=10)
        assert len(result) == 1
        assert result[0]["level"] == 1
        assert result[0]["title"] == "第1章"
        assert result[0]["page_start"] == 1
        assert result[0]["page_end"] == 10
        assert result[0]["children"] == []
        assert result[0]["id"] == "ch_1"

    def test_multi_level_nesting(self) -> None:
        """L1-L2-L3 嵌套, 验证树结构 + page_end 推导."""
        from src.ingest.pre_analysis.chapter_extractors.chapter_tree import build_chapter_tree

        toc = [
            (1, "第1章", 1),
            (2, "1.1节", 2),
            (3, "1.1.1节", 3),
            (2, "1.2节", 5),
            (1, "第2章", 10),
        ]
        result = build_chapter_tree(toc, total_pages=20)
        assert len(result) == 2  # 2 个 L1

        ch1 = result[0]
        assert ch1["title"] == "第1章"
        assert ch1["page_start"] == 1
        assert ch1["page_end"] == 9  # 到第2章 page_start - 1
        assert len(ch1["children"]) == 2

        s1 = ch1["children"][0]
        assert s1["title"] == "1.1节"
        assert s1["page_start"] == 2
        assert s1["page_end"] == 4  # 到1.2节 page_start - 1
        assert len(s1["children"]) == 1

        ss1 = s1["children"][0]
        assert ss1["title"] == "1.1.1节"
        assert ss1["page_start"] == 3
        assert ss1["page_end"] == 4  # 父级 page_end
        assert ss1["children"] == []

        s2 = ch1["children"][1]
        assert s2["title"] == "1.2节"
        assert s2["page_start"] == 5
        assert s2["page_end"] == 9  # 到第2章 page_start - 1

        ch2 = result[1]
        assert ch2["title"] == "第2章"
        assert ch2["page_start"] == 10
        assert ch2["page_end"] == 20  # 末节点 = total_pages

    def test_max_level_truncation(self) -> None:
        """max_level=1 时仅 L1 节点, L2+ 跳过."""
        from src.ingest.pre_analysis.chapter_extractors.chapter_tree import build_chapter_tree

        toc = [
            (1, "章1", 1),
            (2, "1.1节", 2),
            (2, "1.2节", 3),
            (1, "章2", 5),
            (3, "2.1.1节", 6),
        ]
        result = build_chapter_tree(toc, total_pages=10, max_level=1)
        assert len(result) == 2
        assert result[0]["title"] == "章1"
        assert result[0]["page_end"] == 4
        assert result[0]["children"] == []
        assert result[1]["title"] == "章2"
        assert result[1]["page_end"] == 10

    def test_max_level_3_d81_fixture_style(self) -> None:
        """模拟 D81.1 382 条 → max_level=3 截断后只有 L1-L3 节点."""
        from src.ingest.pre_analysis.chapter_extractors.chapter_tree import build_chapter_tree

        toc: list[tuple[int, str, int]] = []
        page = 1
        for ch in range(1, 6):  # 5 个 L1
            toc.append((1, f"Chapter {ch}", page))
            page += 1
            for sec in range(1, 3):  # 每个 L1 2 个 L2
                toc.append((2, f"{ch}.{sec}", page))
                page += 1
                for sub in range(1, 6):  # 每个 L2 5 个 L3
                    toc.append((3, f"{ch}.{sec}.{sub}", page))
                    page += 1
                for _ in range(1, 4):  # 每个 L2 3 个 L4 (应被截断)
                    toc.append((4, f"{ch}.{sec}.x", page))
                    page += 1
        for i in range(1, 20):
            toc.append((5, f"deep {i}", page))
            page += 1
        for i in range(1, 20):
            toc.append((6, f"deepest {i}", page))
            page += 1

        result = build_chapter_tree(toc, total_pages=page, max_level=3)

        def count_all(nodes: list[dict]) -> int:
            return sum(1 + count_all(n["children"]) for n in nodes)

        total = count_all(result)
        assert total == 65  # 5 L1 + 10 L2 + 50 L3
        # 确保没有 L4+ 节点
        max_lvl = 0

        def walk(nodes: list[dict]) -> None:
            nonlocal max_lvl
            for n in nodes:
                max_lvl = max(max_lvl, n["level"])
                walk(n["children"])

        walk(result)
        assert max_lvl <= 3

    def test_sibling_page_end_edge_case(self) -> None:
        """连续同 level 节点: page_end = 下一同级 page_start - 1."""
        from src.ingest.pre_analysis.chapter_extractors.chapter_tree import build_chapter_tree

        toc = [
            (1, "A", 1),
            (1, "B", 5),
            (1, "C", 10),
        ]
        result = build_chapter_tree(toc, total_pages=20)
        assert result[0]["page_end"] == 4
        assert result[1]["page_end"] == 9
        assert result[2]["page_end"] == 20

    def test_nested_children_not_clamped_by_short_parent(self) -> None:
        """(2026-07-09 D81 真实 bug, 二次确认) ch_1 有 L2 children 且 ch_1.page_end=1
        (因为下一个 L1 紧接在 page 2), 子节点 page_end 不能被钳到 1 < page_start.

        用户真实 toc:
          ch_1 (L1 p1) > ch_2 (L2 p2), ch_3 (L2 p4), ch_4 (L2 p6)
          ch_5 (L1 p2)
        期望:
          ch_2.page_end = 3 (= ch_3.page_start - 1)
          ch_3.page_end = 5 (= ch_4.page_start - 1)
          ch_4.page_end = 6 (不是 1)
        """
        from src.ingest.pre_analysis.chapter_extractors.chapter_tree import build_chapter_tree

        toc = [
            (1, "Catalog D 81.1", 1),
            (2, "Related catalogs", 2),
            (2, "Digital Enterprise", 4),
            (2, "Integrated Drive Systems", 6),
            (1, "SIMOTICS", 2),
        ]
        result = build_chapter_tree(toc, total_pages=710)
        ch1 = result[0]
        assert ch1["title"] == "Catalog D 81.1"
        assert ch1["page_end"] == 1  # 下个 L1 在 page 2
        assert len(ch1["children"]) == 3
        # 关键: 子节点 page_end >= page_start, 不能被钳到 1
        s2, s3, s4 = ch1["children"]
        assert s2["page_start"] == 2 and s2["page_end"] == 3  # 到 s3.page_start-1
        assert s3["page_start"] == 4 and s3["page_end"] == 5  # 到 s4.page_start-1
        assert s4["page_start"] == 6 and s4["page_end"] == 6  # 末子 = 父 page_end
        ch5 = result[1]
        assert ch5["page_start"] == 2

    def test_same_page_start_siblings_share_physical_page(self) -> None:
        """(2026-07-09 D81 bug) 多个兄弟同 page_start 时, 它们共享物理页,
        每个 page_end = 自己 page_start (而不是 next.page_start - 1).
        否则前两个会算成 page_start - 1 = 709 (PDF 最后一页), 失真.

        用户场景: 'Get more information' / 'Publisher' / 'Cybersecurity information'
        都标在 PDF 的最后一页 (page 710) 作为页脚链接, 应该各自 page_end=710.
        """
        from src.ingest.pre_analysis.chapter_extractors.chapter_tree import build_chapter_tree

        toc = [
            (1, "正文章", 1),
            (1, "Get more information", 10),
            (1, "Publisher", 10),
            (1, "Cybersecurity information", 10),
        ]
        result = build_chapter_tree(toc, total_pages=10)
        assert len(result) == 4
        assert result[0]["page_end"] == 9  # 章1 = next.page_start - 1
        assert result[1]["page_end"] == 10  # 同页共享, 不丢到 9
        assert result[2]["page_end"] == 10  # 同页共享
        assert result[3]["page_end"] == 10  # 末节点 = total_pages

    def test_page_end_not_below_page_start(self) -> None:
        """(2026-07-09 边界) 当兄弟 next.page_start == self.page_start 时
        page_end 不能 < page_start, 否则会算出 0 (页号从 1 起).
        """
        from src.ingest.pre_analysis.chapter_extractors.chapter_tree import build_chapter_tree

        toc = [
            (1, "A", 1),
            (1, "B", 1),  # 同一页
        ]
        result = build_chapter_tree(toc, total_pages=10)
        assert result[0]["page_end"] >= result[0]["page_start"]
        assert result[1]["page_end"] == 10

    def test_nested_last_child_page_end(self) -> None:
        """嵌套末子节点 page_end = 父节点 page_end."""
        from src.ingest.pre_analysis.chapter_extractors.chapter_tree import build_chapter_tree

        toc = [
            (1, "章1", 1),
            (2, "1.1", 2),
            (2, "1.2", 5),
            (1, "章2", 10),
        ]
        result = build_chapter_tree(toc, total_pages=20)
        ch1 = result[0]
        assert ch1["page_end"] == 9
        assert ch1["children"][1]["page_end"] == 9

    def test_ids_sequential(self) -> None:
        """id 按顺序 ch_1, ch_2, ..."""
        from src.ingest.pre_analysis.chapter_extractors.chapter_tree import build_chapter_tree

        toc = [(1, "A", 1), (2, "A.1", 2), (3, "A.1.1", 3)]
        result = build_chapter_tree(toc, total_pages=10)
        assert result[0]["id"] == "ch_1"
        assert result[0]["children"][0]["id"] == "ch_2"
        assert result[0]["children"][0]["children"][0]["id"] == "ch_3"


class TestClusterByFontSize:
    def test_happy_path(self) -> None:
        """正常返回 (level, title, page_start) 列表."""
        from src.ingest.pre_analysis.chapter_extractors.chapter_tree import cluster_by_font_size

        pages = []
        for text in ["Chapter 1", "1.1 Section"]:
            p = MagicMock()
            p.rect = MagicMock(height=800)
            p.get_text.return_value = {
                "blocks": [
                    {
                        "type": 0,
                        "lines": [
                            {
                                "spans": [
                                    {"size": 20, "bbox": [0, 0, 100, 20], "font": "Arial", "text": text},
                                ]
                            }
                        ],
                    },
                ]
            }
            pages.append(p)
        doc = MagicMock()
        doc.__len__.return_value = len(pages)
        doc.__getitem__ = MagicMock(side_effect=lambda idx: pages[idx])
        doc.__iter__.return_value = iter(pages)

        result = cluster_by_font_size(doc, max_pages=2)
        assert len(result) >= 1

    def test_no_spans_returns_empty(self) -> None:
        """没有候选 span → []."""
        from src.ingest.pre_analysis.chapter_extractors.chapter_tree import cluster_by_font_size

        page = MagicMock()
        page.rect = MagicMock(height=800)
        page.get_text.return_value = {"blocks": []}
        doc = MagicMock()
        doc.__len__.return_value = 3
        doc.__getitem__ = MagicMock(return_value=page)
        doc.__iter__.return_value = iter([page, page, page])

        assert cluster_by_font_size(doc) == []


class TestDetectTocPages:
    def test_detect_contents_hit(self) -> None:
        """含 'Contents' + dotted-leader ≥ 5 → 命中."""
        from src.ingest.pre_analysis.chapter_extractors.chapter_tree import detect_toc_pages

        doc = MagicMock()
        doc.__len__.return_value = 20
        page0 = MagicMock()
        page0.get_text.return_value = "Contents\n" + "\n".join(f"Chapter {i} .......... {i}" for i in range(1, 10))
        other = MagicMock()
        other.get_text.return_value = ""
        doc.__getitem__ = MagicMock(side_effect=[page0] + [other] * 19)

        result = detect_toc_pages(doc)
        assert result == [0]

    def test_no_contents_returns_empty(self) -> None:
        """不含目录关键字 → []."""
        from src.ingest.pre_analysis.chapter_extractors.chapter_tree import detect_toc_pages

        doc = MagicMock()
        doc.__len__.return_value = 20
        page = MagicMock()
        page.get_text.return_value = "Introduction\nThis is the first chapter..."
        doc.__getitem__ = MagicMock(return_value=page)

        assert detect_toc_pages(doc) == []

    def test_few_leader_lines_returns_empty(self) -> None:
        """含 'Contents' 但 dotted-leader < 5 行 → []."""
        from src.ingest.pre_analysis.chapter_extractors.chapter_tree import detect_toc_pages

        doc = MagicMock()
        doc.__len__.return_value = 20
        page = MagicMock()
        page.get_text.return_value = "Contents\nChapter 1 .... 1"
        doc.__getitem__ = MagicMock(return_value=page)

        assert detect_toc_pages(doc) == []

    def test_chinese_toc_hit(self) -> None:
        """中文 '目录' 命中."""
        from src.ingest.pre_analysis.chapter_extractors.chapter_tree import detect_toc_pages

        doc = MagicMock()
        doc.__len__.return_value = 20
        page0 = MagicMock()
        page0.get_text.return_value = "目录\n" + "\n".join(f"第{i}章 .......... {i}" for i in range(1, 10))
        other = MagicMock()
        other.get_text.return_value = ""
        doc.__getitem__ = MagicMock(side_effect=[page0] + [other] * 19)

        result = detect_toc_pages(doc)
        assert result == [0]


class TestParseTocPages:
    def test_parse_single_page(self) -> None:
        """解析含 dotted-leader 的行."""
        from src.ingest.pre_analysis.chapter_extractors.chapter_tree import parse_toc_pages

        doc = MagicMock()
        page = MagicMock()
        page.get_text.return_value = (
            "Chapter 1 ................... 1\n    Chapter 1.1 ............. 3\n    Chapter 1.2 ............. 5\n"
        )
        doc.__getitem__ = MagicMock(return_value=page)

        result = parse_toc_pages(doc, [0])
        assert len(result) == 3
        assert result[0] == (1, "Chapter 1", 1)
        # 缩进推断 level: 4 空格缩进 → indent//2+1 = 3
        assert result[1][0] == 3
        assert result[1][1] == "Chapter 1.1"
        assert result[2][0] == 3

    def test_parse_numbered_levels(self) -> None:
        """编号 '1.2.3' → level 3."""
        from src.ingest.pre_analysis.chapter_extractors.chapter_tree import parse_toc_pages

        doc = MagicMock()
        page = MagicMock()
        page.get_text.return_value = (
            "1. Introduction ................... 1\n"
            "    1.1 Background ............... 2\n"
            "    1.1.1 Motivation ............. 3\n"
        )
        doc.__getitem__ = MagicMock(return_value=page)

        result = parse_toc_pages(doc, [0])
        assert len(result) == 3
        assert result[0][0] == 1
        assert result[1][0] == 2
        assert result[2][0] == 3

    def test_empty_page_indices(self) -> None:
        """空 page_indices → []."""
        from src.ingest.pre_analysis.chapter_extractors.chapter_tree import parse_toc_pages

        doc = MagicMock()
        assert parse_toc_pages(doc, []) == []
