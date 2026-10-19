"""文档加载器

从文件系统加载 .md / .txt 文件为 RAGDoc.
"""

from collections.abc import Iterable, Sequence
from pathlib import Path

from .document import RAGDoc
from .text_io import read_text_with_fallback


def load_md_files(dir_path: str | Path, recursive: bool = True) -> list[RAGDoc]:
    """递归加载目录下所有 .md 文件, 返回 RAGDoc 列表"""
    dir_path = Path(dir_path)
    pattern = "**/*.md" if recursive else "*.md"
    files = sorted(dir_path.glob(pattern))
    return _load_text_files(files)


def load_txt_files(dir_path: str | Path, recursive: bool = True) -> list[RAGDoc]:
    """递归加载目录下所有 .txt 文件"""
    dir_path = Path(dir_path)
    pattern = "**/*.txt" if recursive else "*.txt"
    files = sorted(dir_path.glob(pattern))
    return _load_text_files(files)


def _load_text_files(files: Sequence[Path]) -> list[RAGDoc]:
    """通用文本文件加载器"""
    docs: list[RAGDoc] = []
    for f in files:
        text = read_text_with_fallback(f)
        if text is None:
            continue
        docs.append(RAGDoc(text=text, metadata={"file_path": str(f)}))
    return docs


def load_documents_from_files(
    file_paths: Iterable[str | Path],
) -> list[RAGDoc]:
    """从文件路径列表加载为 RAGDoc 列表"""
    docs: list[RAGDoc] = []
    for fp in file_paths:
        fp = Path(fp)
        if not fp.exists():
            continue
        text = read_text_with_fallback(fp)
        if text is None:
            continue
        docs.append(RAGDoc(text=text, metadata={"file_path": str(fp)}))
    return docs


def filter_empty_documents(docs: Sequence[RAGDoc]) -> list[RAGDoc]:
    """过滤空白文档"""
    return [d for d in docs if extract_plain_text(d).strip()]


def extract_plain_text(doc: RAGDoc) -> str:
    return doc.get_content()


def documents_to_texts(docs: Sequence[RAGDoc]) -> list[str]:
    return [extract_plain_text(d) for d in docs]
