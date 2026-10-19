"""kg.templates Excel 模板生成测试"""

import io

import openpyxl

from src.kg import templates


def test_build_qa_excel_returns_bytesio():
    out = templates.build_qa_excel()
    assert isinstance(out, io.BytesIO)
    # xlsx 头 4 字节
    assert out.getvalue()[:2] == b"PK"


def test_build_qa_excel_has_required_headers():
    out = templates.build_qa_excel()
    wb = openpyxl.load_workbook(out)
    ws = wb.active
    assert ws is not None
    headers = [c.value for c in ws[1]]
    assert "question" in headers
    assert "answer" in headers
    assert "tags" in headers


def test_build_qa_excel_has_example_row():
    out = templates.build_qa_excel()
    wb = openpyxl.load_workbook(out)
    ws = wb.active
    assert ws is not None
    row2 = [c.value for c in ws[2]]
    assert any(v for v in row2)
