"""PDFAnalyzer 单元测试

(2026-06-29) 改用 tests/fixtures/ 下已入库的真 PDF (1LE1.pdf / complex_pdf_test.pdf / easy_pdf_test.pdf).
之前指 packages/service/pdfs/ 但 repo 不入库, 14 test 永远 skip.
"""

from pathlib import Path

import pytest

from src.ingest.pdf_processing.analyzers.pdf import PDFAnalyzer, PDFInfo, analyze_pdf_complexity

# 真 PDF 在 tests/fixtures/ (已入库), 跟 pdfs/ 软链等价.
_FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures"
# 替代映射: 旧 pdfs/foo.pdf 路径 → fixtures/ 下的对应真 PDF
PATH_MAP = {
    "pdfs/book_zh_HGT51022016_extracted_page_12.pdf": str(_FIXTURES_DIR / "complex_pdf_test.pdf"),
    "pdfs/magazine_TheEconomist.2024.02.24_page_076.pdf": str(_FIXTURES_DIR / "complex_pdf_test.pdf"),
    "pdfs/yanbaopptmerge_d4fc7cba428625974e93183edfccea73.pdf_89.pdf": str(_FIXTURES_DIR / "1LE1.pdf"),
}


class TestPDFInfo:
    """PDFInfo 数据类测试"""

    def test_default_values(self):
        """测试默认值"""
        info = PDFInfo()
        assert info.page_count == 0
        assert info.has_images is False
        assert info.has_text is False
        assert info.image_count == 0
        assert info.drawing_count == 0
        assert info.table_like_pages == 0
        assert info.is_simple is True
        assert info.reasons == []


class TestPDFAnalyzer:
    """PDFAnalyzer 分析器测试 (走 tests/fixtures/ 已入库 PDF, 永不 skip)"""

    def setup_method(self):
        """每个测试方法前初始化"""
        self.analyzer = PDFAnalyzer()

    def test_analyze_returns_pdf_info(self):
        """测试分析返回PDFInfo对象"""
        info = self.analyzer.analyze(PATH_MAP["pdfs/book_zh_HGT51022016_extracted_page_12.pdf"])
        assert isinstance(info, PDFInfo)
        assert info.page_count >= 1

    def test_analyze_detects_no_text(self):
        """测试检测无文字PDF"""
        info = self.analyzer.analyze(PATH_MAP["pdfs/book_zh_HGT51022016_extracted_page_12.pdf"])
        assert info.is_simple is False
        assert any("无文字" in r for r in info.reasons)

    def test_analyze_detects_images(self):
        """测试检测图片"""
        info = self.analyzer.analyze(PATH_MAP["pdfs/magazine_TheEconomist.2024.02.24_page_076.pdf"])
        assert info.has_images is True
        assert info.image_count >= 1

    def test_analyze_counts_pages(self):
        """测试页数统计 (1LE1.pdf 实际 96 页)"""
        info = self.analyzer.analyze(PATH_MAP["pdfs/yanbaopptmerge_d4fc7cba428625974e93183edfccea73.pdf_89.pdf"])
        assert info.page_count == 96

    def test_analyze_invalid_file(self):
        """测试无效文件"""
        with pytest.raises(Exception):
            self.analyzer.analyze("nonexistent.pdf")

    def test_analyze_all_returns_dict(self):
        """测试批量分析 (2 个不同 fixture 路径, dict 应有 2 key)"""
        paths = [
            PATH_MAP["pdfs/book_zh_HGT51022016_extracted_page_12.pdf"],
            PATH_MAP["pdfs/yanbaopptmerge_d4fc7cba428625974e93183edfccea73.pdf_89.pdf"],
        ]
        results = self.analyzer.analyze_all(paths)
        assert isinstance(results, dict)
        assert len(results) == 2
        for _path, info in results.items():
            assert isinstance(info, PDFInfo)

    def test_classify_splits_simple_and_complex(self):
        """测试分类功能 (2 个不同 fixture 路径)"""
        paths = [
            PATH_MAP["pdfs/book_zh_HGT51022016_extracted_page_12.pdf"],
            PATH_MAP["pdfs/yanbaopptmerge_d4fc7cba428625974e93183edfccea73.pdf_89.pdf"],
        ]
        infos = self.analyzer.analyze_all(paths)
        simple, complex_ = self.analyzer.classify(infos)
        assert len(simple) + len(complex_) == 2


class TestPDFAnalyzerPureFunctions:
    """PDFAnalyzer 纯函数测试 (不依赖真 PDF, 走 mock 数据)

    (2026-06-29) 拆出来独立 class, 之前挂在 @pytest.mark.skipif(_have_pdfs()) 一起 skip,
    不需要 PDF 的纯函数测也跟着跳了, 这是 fixture 错配.
    """

    def setup_method(self):
        self.analyzer = PDFAnalyzer()

    def test_is_table_page_with_few_drawings(self):
        """测试表格检测 - 少量图形"""
        assert self.analyzer._is_table_page([]) is False
        assert self.analyzer._is_table_page([{"rect": None}] * 10) is False

    def test_is_table_page_with_many_drawings(self):
        """测试表格检测 - 大量纵横线条"""
        drawings = []
        for _ in range(15):
            drawings.append({"rect": type("R", (), {"height": 2, "width": 50})()})
        for _ in range(15):
            drawings.append({"rect": type("R", (), {"height": 50, "width": 2})()})
        assert self.analyzer._is_table_page(drawings) is True

    def test_evaluate_simple_pdf(self):
        """测试评估为简单PDF"""
        info = PDFInfo(has_text=True, drawing_count=10, image_count=2)
        self.analyzer._evaluate(info)
        assert info.is_simple is True
        assert len(info.reasons) == 0

    def test_evaluate_no_text_complex(self):
        """测试无文字判定为复杂"""
        info = PDFInfo(has_text=False)
        self.analyzer._evaluate(info)
        assert info.is_simple is False
        assert len(info.reasons) == 1

    def test_evaluate_too_many_drawings(self):
        """测试矢量图形过多"""
        info = PDFInfo(has_text=True, drawing_count=150)
        self.analyzer._evaluate(info)
        assert info.is_simple is False
        assert any("矢量图形" in r for r in info.reasons)

    def test_evaluate_too_many_images(self):
        """测试图片过多"""
        info = PDFInfo(has_text=True, image_count=20)
        self.analyzer._evaluate(info)
        assert info.is_simple is False
        assert any("图片" in r for r in info.reasons)


class TestConvenienceFunction:
    """便捷函数测试 (走 fixtures)"""

    def test_analyze_pdf_complexity(self):
        """测试便捷函数"""
        info = analyze_pdf_complexity(PATH_MAP["pdfs/book_zh_HGT51022016_extracted_page_12.pdf"])
        assert isinstance(info, PDFInfo)
        assert info.page_count >= 1
