"""SemanticSplitter 测试"""

from unittest.mock import MagicMock

from src.ingest.chunkers import SemanticSplitter


def test_semantic_splitter_merges_similar_adjacent_sentences():
    """[M3] cosine 距离 < 阈值 合并相邻句; > 阈值 切分"""
    embedder = MagicMock()
    embedder.embed_batch.return_value = [
        [1.0, 0.0],
        [0.95, 0.05],  # 跟句 1 相似 → 合并
        [0.0, 1.0],  # 跟句 2 不相似 → 切分
        [0.0, 0.95],  # 跟句 3 相似 → 合并
    ]
    text = "句 1。句 2。句 3。句 4。"
    chunks = SemanticSplitter(embedder=embedder, cosine_threshold=0.5, min_chunk_size=2).split(text, "test://doc.md")
    assert len(chunks) == 2
    assert "句 1" in chunks[0].text
    assert "句 2" in chunks[0].text
    assert "句 3" in chunks[1].text
    assert "句 4" in chunks[1].text


def test_semantic_splitter_fallback_when_embedder_fails():
    """[M3] embedder 抛错 → 降级到 HeadingSplitter"""
    embedder = MagicMock()
    embedder.embed_batch.side_effect = RuntimeError("embed unavailable")
    text = "# H1\n\ncontent under h1"
    chunks = SemanticSplitter(embedder=embedder, cosine_threshold=0.5).split(text, "test://doc.md")
    assert len(chunks) >= 1
    assert chunks[0].meta["heading_path"] == ["H1"]


def test_semantic_splitter_respects_max_chunk_size():
    """[M3] max_chunk_size 防止单个 chunk 太大, 强制切分"""
    embedder = MagicMock()
    embedder.embed_batch.return_value = [[1.0, 0.0]] * 10
    text = "。".join(["句子"] * 10)
    chunks = SemanticSplitter(
        embedder=embedder,
        cosine_threshold=0.5,
        max_chunk_size=3,
        min_chunk_size=1,
    ).split(text, "test://doc.md")
    assert len(chunks) >= 3


def test_semantic_splitter_no_sentences_falls_back_to_heading():
    """[M3] 无句号 → fallback heading (不调 embedder)"""
    embedder = MagicMock()
    text = "plain text without punctuation"
    chunks = SemanticSplitter(embedder=embedder).split(text, "test://doc.md")
    assert len(chunks) == 1
    embedder.embed_batch.assert_not_called()
