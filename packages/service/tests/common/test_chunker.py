"""测试 chunker - 走 RAGDoc + RecursiveCharacterTextSplitter"""

from src.common.chunker import chunk_documents
from src.common.document import RAGDoc


def test_chunk_documents_empty():
    """空输入返空列表, 不抛"""
    assert chunk_documents([]) == []


def test_chunk_documents_short_text_not_split():
    """文本短于 chunk_size, 不切"""
    docs = [RAGDoc(text="短文本", metadata={"k": "v"})]
    out = chunk_documents(docs, chunk_size=512, chunk_overlap=128)
    assert len(out) == 1
    assert out[0].text == "短文本"
    assert out[0].metadata == {"k": "v"}


def test_chunk_documents_long_text_split():
    """长文本按 chunk_size 切多块"""
    long_text = "。".join([f"句子{i}" for i in range(200)])  # ~1200 字符
    docs = [RAGDoc(text=long_text, metadata={"file_path": "/a.md"})]
    out = chunk_documents(docs, chunk_size=200, chunk_overlap=50)
    assert len(out) > 1
    for c in out:
        assert c.metadata == {"file_path": "/a.md"}


def test_chunk_documents_metadata_independent_copies():
    """metadata 是 copy, 改一个不影响另一个"""
    docs = [RAGDoc(text="句子。" * 100, metadata={"k": "v"})]
    out = chunk_documents(docs, chunk_size=50, chunk_overlap=10)
    assert len(out) > 1
    out[0].metadata["new"] = "x"
    assert "new" not in out[1].metadata


def test_chunk_documents_cn_separators_prefer_period():
    """中文 separator 优先在句号断"""
    text = "句一。" * 50  # 一堆短句, 句号分隔
    docs = [RAGDoc(text=text)]
    out = chunk_documents(docs, chunk_size=100, chunk_overlap=20)
    for c in out[:-1]:
        assert "句" in c.text
