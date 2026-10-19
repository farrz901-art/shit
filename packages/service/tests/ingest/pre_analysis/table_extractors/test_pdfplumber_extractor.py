"""PdfplumberTableExtractor 测试 (mode 1 mock + 真 PDF skipIf).

依赖 pdfplumber 包; 未装则 skipped.
核心测试:
- 包缺失抛 BackendNotInstalledError(backend='pdfplumber')
"""

from __future__ import annotations

import importlib.util
import sys
from unittest.mock import patch

import pytest


def test_pdfplumber_not_installed_raises_backend_not_installed_error() -> None:
    """pdfplumber 未装 → 构造抛 BackendNotInstalledError(backend='pdfplumber')."""
    # 移除已缓存的 pdfplumber 模块
    for k in [k for k in sys.modules if k == "pdfplumber" or k.startswith("pdfplumber.")]:
        del sys.modules[k]

    real_import = __builtins__["__import__"] if isinstance(__builtins__, dict) else __builtins__.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):  # noqa: A002
        if name == "pdfplumber" or name.startswith("pdfplumber."):
            raise ImportError(f"No module named {name!r}")
        return real_import(name, globals, locals, fromlist, level)

    with patch("builtins.__import__", side_effect=fake_import):
        from src.ingest.pre_analysis.table_extractors.base import (
            BackendNotInstalledError,
        )
        from src.ingest.pre_analysis.table_extractors.pdfplumber_extractor import (
            PdfplumberTableExtractor,
        )

        with pytest.raises(BackendNotInstalledError) as exc_info:
            PdfplumberTableExtractor({})

    assert exc_info.value.backend == "pdfplumber"
    assert "uv add pdfplumber" in exc_info.value.install_hint


def test_pdfplumber_init_with_default_params_ok(monkeypatch) -> None:
    """pdfplumber 可 import → 构造不抛. 默认参数生效."""
    fake_pdfplumber = type(sys)("pdfplumber")
    monkeypatch.setitem(sys.modules, "pdfplumber", fake_pdfplumber)

    from src.ingest.pre_analysis.table_extractors.pdfplumber_extractor import (
        PdfplumberTableExtractor,
    )

    extractor = PdfplumberTableExtractor({})
    # 默认参数 fallback
    assert extractor._params.get("vertical_strategy") is None  # params dict 透传未变


@pytest.mark.skipif(
    importlib.util.find_spec("pdfplumber") is None,
    reason="pdfplumber 未装, 真 PDF 测试 skip",
)
def test_extract_real_pdf() -> None:
    """真 PDF 走 pdfplumber.open().pages[].extract_tables() → TableData 列表."""
    from src.ingest.pre_analysis.table_extractors.pdfplumber_extractor import (
        PdfplumberTableExtractor,
    )

    fixture_path = __import__("pathlib").Path(__file__).resolve().parents[2] / "fixtures" / "d81_dummy.pdf"

    extractor = PdfplumberTableExtractor(
        {
            "vertical_strategy": "lines",
            "horizontal_strategy": "lines",
            "snap_tolerance": 3,
        }
    )
    result = extractor.extract(str(fixture_path))
    assert isinstance(result, list)
    for td in result:
        # (2026-07-09) page_no 跨页合并后是 str (e.g. "5+6"), 只对 int 守卫
        if isinstance(td.page_no, int):
            assert td.page_no >= 1
        assert td.table_no >= 1


# (2026-07-09) extract() 内部退化表过滤


def test_extract_filters_degenerate_tables(monkeypatch) -> None:
    """mock pdfplumber.open() 返 1 页 + 退化 + 有效表 -> 只返有效表.

    退化表 (1xN / 1x1) 在 extract() 内部被 TableData.is_valid_table 过滤.
    """
    from types import SimpleNamespace

    from src.ingest.pre_analysis.table_extractors.pdfplumber_extractor import (
        PdfplumberTableExtractor,
    )

    # 构造 mock pdfplumber module
    fake_page = SimpleNamespace(
        extract_tables=lambda table_settings: [
            [["a", "b", "c"]],  # 1xN 退化
            [["only"]],  # 1x1 退化
            [["h1", "h2"], ["v1", "v2"]],  # 2x2 有效
        ]
    )

    class FakePDF:
        def __init__(self) -> None:
            self.pages = [fake_page]

        def __enter__(self) -> FakePDF:
            return self

        def __exit__(self, *args: object) -> None:
            return None

    fake_pdfplumber = SimpleNamespace(open=lambda pdf_path: FakePDF())
    monkeypatch.setitem(sys.modules, "pdfplumber", fake_pdfplumber)

    extractor = PdfplumberTableExtractor({})
    result = extractor.extract("fake.pdf")

    # 只 valid 表 (2x2) 进了结果
    assert len(result) == 1
    assert result[0].page_no == 1
    assert result[0].table_no == 3  # table_no 仍递增, 退化表虽丢弃
    assert result[0].rows == [["h1", "h2"], ["v1", "v2"]]
