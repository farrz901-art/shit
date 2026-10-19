"""TokenSplitter 测试"""

import pytest

from src.ingest.chunkers import TextChunk, TokenSplitter


def test_token_splitter_chunks_per_window():
    """[M3] ~500 tokens 文本用 chunk_size=128 切, 应产 ≥3 个 chunk"""
    text = " ".join(["这是一个用于测试的句子"] * 100)
    chunks = TokenSplitter(chunk_size=128, overlap=16).split(text, "test://doc.md")
    assert len(chunks) >= 3
    assert all(isinstance(c, TextChunk) for c in chunks)
    assert all(len(c.chunk_id) == 12 for c in chunks)


def test_token_splitter_overlap_preserves_context():
    """[M3] overlap: 相邻 chunk 应共享部分 tokens"""
    text = " ".join(["句子"] * 200)
    chunks = TokenSplitter(chunk_size=64, overlap=8).split(text, "test://doc.md")
    assert len(chunks) >= 2
    # overlap token ('句子') 应出现在第二 chunk 开头
    second_head = chunks[1].text[:50]
    assert "句子" in second_head


def test_token_splitter_empty_text_returns_empty_list():
    """[M3] 空字符串 → 空 list"""
    chunks = TokenSplitter(chunk_size=128).split("", "test://doc.md")
    assert chunks == []


def test_token_splitter_meta_contains_token_count():
    """[M3] meta.token_count > 0, meta.start_token >= 0"""
    text = "短文本测试"
    chunks = TokenSplitter(chunk_size=128).split(text, "test://doc.md")
    assert chunks[0].meta["token_count"] > 0
    assert "start_token" in chunks[0].meta


def test_token_splitter_invalid_overlap_raises():
    """overlap >= chunk_size 必报错"""
    with pytest.raises(ValueError, match="overlap"):
        TokenSplitter(chunk_size=64, overlap=64)
    with pytest.raises(ValueError, match="overlap"):
        TokenSplitter(chunk_size=64, overlap=100)
