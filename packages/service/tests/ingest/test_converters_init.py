"""converters __init__ 导出测试

跟 test_converters.py 不同: 这个测文件测 __init__.py 公共 API,
不依赖 fixture mock (kreuzberg 装好了, 直接 import).
"""

import pytest

from src.ingest.pdf_processing.converters import (
    CONVERTERS,
    Converter,
    EzdxfConverter,
    KreuzbergConverter,
    MineruConverter,
    classify_files,
    get_converter,
)


def test_converter_classes_exported():
    """KreuzbergConverter, MineruConverter, EzdxfConverter 均可访问"""
    assert KreuzbergConverter is not None
    assert MineruConverter is not None
    assert EzdxfConverter is not None
    # 都是 Converter 的子类
    assert issubclass(KreuzbergConverter, Converter)
    assert issubclass(MineruConverter, Converter)
    assert issubclass(EzdxfConverter, Converter)


def test_get_converter_returns_instance():
    """get_converter('kreuzberg') 返回 KreuzbergConverter 实例"""
    conv = get_converter("kreuzberg")
    assert isinstance(conv, KreuzbergConverter)
    assert conv.name == "kreuzberg"


def test_get_converter_unknown_name():
    """get_converter 未知名称抛出 KeyError"""
    with pytest.raises(KeyError):
        get_converter("nonexistent")


def test_converter_classes_have_name_and_extensions():
    """各 Converter 类有 name 和 extensions 属性"""
    for name in ["kreuzberg", "mineru", "ezdxf"]:
        conv = get_converter(name)
        assert hasattr(conv, "name")
        assert hasattr(conv, "extensions")
        assert isinstance(conv.extensions, list)


def test_classify_files_groups_by_extension():
    """classify_files 按 converter extensions 分桶"""
    # 用 MagicMock 当 PDFInfo
    from unittest.mock import MagicMock

    infos = {
        "a.pdf": MagicMock(),
        "b.dxf": MagicMock(),
    }
    grouped = classify_files(infos, list(CONVERTERS.values()))
    # 3 个 converter 各有 1 个桶
    assert set(grouped.keys()) == {"kreuzberg", "mineru", "ezdxf"}
    # a.pdf → kreuzberg (假设 can_handle 返回 True, 这里 Mock 默认 True)
    assert "a.pdf" in grouped["kreuzberg"]
    # b.dxf → ezdxf
    assert "b.dxf" in grouped["ezdxf"]


def test_CONVERTERS_dict_has_all_converters():
    """CONVERTERS 字典含 3 个 converter"""
    assert set(CONVERTERS.keys()) == {"kreuzberg", "mineru", "ezdxf"}
    assert CONVERTERS["kreuzberg"] is KreuzbergConverter
    assert CONVERTERS["mineru"] is MineruConverter
    assert CONVERTERS["ezdxf"] is EzdxfConverter
