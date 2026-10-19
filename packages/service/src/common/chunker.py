"""文档分块器

将 RAGDoc 列表分块为更小的片段, 用于 embedding 和检索.
"""

from collections.abc import Sequence

from .document import RAGDoc

# 中文友好 separators: 段落 → 行 → 中文句末 → 西文句末 → 空格 → 字符
# LC 默认 ["\n\n", "\n", " ", ""] 对中文表现差, 必须显式加中文标点
_CN_SEPARATORS = ["\n\n", "\n", "。", "！", "？", "；", " ", ""]


def chunk_documents(
    documents: Sequence[RAGDoc],
    chunk_size: int = 512,
    chunk_overlap: int = 128,
) -> list[RAGDoc]:
    """将 RAGDoc 列表分块, 返回新 RAGDoc 列表.

    Args:
        documents: 原始 RAGDoc 列表
        chunk_size: 每块字符数
        chunk_overlap: 相邻块重叠字符数

    Returns:
        分块后的 RAGDoc 列表 (metadata 从原文档复制)
    """
    if not documents:
        return []

    # 重依赖 lazy: langchain_text_splitters 在 import 期会拉 sentence_transformers + spacy
    # 这俩间接拽 torch, 触发 CUDA init. 无 GPU 机器 import 时打印 CUDA warning 噪音.
    # 只在真正分块时才付启动成本.
    from langchain_text_splitters import RecursiveCharacterTextSplitter  # noqa: E402

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=_CN_SEPARATORS,
    )
    out: list[RAGDoc] = []
    for d in documents:
        for piece in splitter.split_text(d.text):
            out.append(RAGDoc(text=piece, metadata=d.metadata.copy()))
    return out
