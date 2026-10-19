"""PDF转换器"""

from pathlib import Path

from .base import Converter
from .cad import EzdxfConverter, OdaNotInstalledError, read_cad_with_oda
from .kreuzberg import KreuzbergConverter
from .mineru import MineruConverter

# 转换器列表
CONVERTERS = {
    "kreuzberg": KreuzbergConverter,
    "mineru": MineruConverter,
    "ezdxf": EzdxfConverter,
}


def classify_files(infos: dict, converters: list) -> dict[str, list[str]]:
    """按 converter 声明的 extensions 过滤文件 → converter 桶

    Args:
        infos: {file_path: PDFInfo} —— 来自 PDFAnalyzer.analyze_all()
        converters: converter 类列表（用 .name / .extensions 声明属性）

    Returns:
        {converter_name: [file_path, ...]} —— 一个文件最多分给一个 converter
    """
    grouped: dict[str, list[str]] = {conv.name: [] for conv in converters}

    for file_path, info in infos.items():
        ext = Path(file_path).suffix.lower()
        for conv in converters:
            if ext not in conv.extensions:
                continue
            if conv().can_handle(info):
                grouped[conv.name].append(file_path)
                break
    return grouped


def get_converter(name: str) -> Converter:
    """获取转换器实例"""
    return CONVERTERS[name]()


__all__ = [
    "Converter",
    "KreuzbergConverter",
    "MineruConverter",
    "EzdxfConverter",
    "OdaNotInstalledError",
    "read_cad_with_oda",
    "CONVERTERS",
    "classify_files",
    "get_converter",
]
