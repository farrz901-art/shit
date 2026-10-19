"""PDFAnalyzer 测试"""

import importlib.util
from pathlib import Path

import pytest


@pytest.fixture
def pdf_module():
    src_dir = Path(__file__).resolve().parent.parent.parent / "src"
    spec = importlib.util.spec_from_file_location(
        "pdf_analyzer", src_dir / "ingest" / "pdf_processing" / "analyzers" / "pdf.py"
    )
    assert spec is not None and spec.loader is not None, (
        f"spec 解析失败: {src_dir / 'ingest' / 'pdf_processing' / 'analyzers' / 'pdf.py'}"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_pdf_info_dataclass(pdf_module):
    """PDFInfo dataclass 属性验证"""
    PDFInfo = pdf_module.PDFInfo
    info = PDFInfo(page_count=5, has_images=True, is_simple=False)
    assert info.page_count == 5
    assert info.has_images is True
    assert info.is_simple is False


def test_analyze_pdf_complexity(tmp_path, pdf_module):
    """analyze_pdf_complexity 便捷函数返回 PDFInfo"""
    # 创建一个简单 PDF
    import pymupdf

    pdf_path = tmp_path / "test.pdf"
    doc = pymupdf.open()
    doc.new_page()
    doc[0].insert_text((100, 100), "Hello World", fontsize=12)
    doc.save(str(pdf_path))
    doc.close()

    PDFAnalyzer = pdf_module.PDFAnalyzer
    result = PDFAnalyzer().analyze(str(pdf_path))
    assert result.page_count == 1
    assert result.has_text is True


def test_pdf_analyzer_classify(pdf_module):
    """classify 方法将 PDF 分为简单/复杂两组"""
    PDFAnalyzer = pdf_module.PDFAnalyzer
    PDFInfo = pdf_module.PDFInfo

    infos = {
        "simple.pdf": PDFInfo(page_count=1, has_text=True, is_simple=True),
        "complex.pdf": PDFInfo(page_count=10, has_text=True, is_simple=False),
    }
    simple, complex_ = PDFAnalyzer().classify(infos)
    assert "simple.pdf" in simple
    assert "complex.pdf" in complex_


def test_is_table_page(pdf_module):
    """_is_table_page 表格页判断逻辑"""
    PDFAnalyzer = pdf_module.PDFAnalyzer
    analyzer = PDFAnalyzer()

    # 无 drawings 返回 False
    assert analyzer._is_table_page([]) is False

    # 模拟表格 drawings（多条横竖线，rect.height/width < 5）
    class MockRect:
        height = 3
        width = 3

    class MockDrawing:
        def get(self, key):
            if key == "rect":
                return MockRect()
            return None

        def __getitem__(self, key):
            if key == "rect":
                return MockRect()
            raise KeyError(key)

    table_drawings = [MockDrawing() for _ in range(25)]
    # 至少需要 20 条（实际25条）且 rect.height < 5 的横线 + rect.width < 5 的竖线各 >10 条
    assert analyzer._is_table_page(table_drawings) is True


def test_evaluate_simple_pdf(pdf_module):
    """_evaluate 正确标记简单 vs 复杂 PDF"""
    PDFInfo = pdf_module.PDFInfo
    PDFAnalyzer = pdf_module.PDFAnalyzer
    analyzer = PDFAnalyzer()

    info = PDFInfo(has_text=True, table_like_pages=0, drawing_count=10, image_count=1)
    analyzer._evaluate(info)
    assert info.is_simple is True

    info2 = PDFInfo(has_text=True, table_like_pages=1, drawing_count=0, image_count=0)
    analyzer._evaluate(info2)
    assert info2.is_simple is False
    assert "表格页面" in info2.reasons[0]
