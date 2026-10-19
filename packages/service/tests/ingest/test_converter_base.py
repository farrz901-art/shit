"""Converter 基类测试"""

import importlib.util
from pathlib import Path

import pytest


@pytest.fixture
def base_module():
    src_dir = Path(__file__).resolve().parent.parent.parent / "src"
    spec = importlib.util.spec_from_file_location(
        "converter_base", src_dir / "ingest" / "pdf_processing" / "converters" / "base.py"
    )
    assert spec is not None and spec.loader is not None, (
        f"spec 解析失败: {src_dir / 'ingest' / 'pdf_processing' / 'converters' / 'base.py'}"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_converter_base_class(base_module):
    """Converter 基类有 name 和 extensions 属性"""
    Converter = base_module.Converter
    conv = Converter()
    assert conv.name == "base"
    assert conv.extensions == []


def test_converter_can_handle_returns_false(base_module):
    """Converter.can_handle 默认返回 False"""
    Converter = base_module.Converter
    assert Converter.can_handle(None) is False


def test_convert_raises_not_implemented(base_module):
    """Converter.convert 抛出 NotImplementedError"""
    Converter = base_module.Converter
    conv = Converter()
    with pytest.raises(NotImplementedError):
        conv.convert("input.pdf", "output.md")


def test_convert_batch_fallback(base_module):
    """convert_batch 有兜底实现，逐个调用 convert"""
    Converter = base_module.Converter

    class DummyConverter(Converter):
        name = "dummy"
        extensions = [".pdf"]

        def convert(self, pdf_path: str, output_path: str) -> str:
            return "content"

    conv = DummyConverter()
    results = conv.convert_batch(["a.pdf", "b.pdf"], "/tmp/output")
    assert len(results) == 2
    assert results["a.pdf"] == "content"
    assert results["b.pdf"] == "content"
