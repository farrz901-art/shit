"""HeadingSplitter 测试"""

from src.ingest.chunkers import HeadingSplitter


def test_heading_splitter_splits_at_h2():
    """[M3] H1 → H2-A → H2-B 切出 3 个 chunk, 每个保留 heading_path"""
    text = """# H1

intro under h1

## H2-A

content A

## H2-B

content B
"""
    chunks = HeadingSplitter().split(text, "test://doc.md")
    assert len(chunks) == 3
    # chunk 0: H1 (无父 heading)
    assert chunks[0].meta["heading_path"] == ["H1"]
    # chunk 1: H2-A → path 包含 H1
    assert "H2-A" in chunks[1].meta["heading_path"]
    assert "content A" in chunks[1].text
    # chunk_id 12 字符
    assert len(chunks[0].chunk_id) == 12


def test_heading_splitter_no_heading_returns_single_chunk():
    """[M3] 无 heading 的纯文本 → 整段 1 个 chunk"""
    text = "plain text\nno heading\nat all"
    chunks = HeadingSplitter().split(text, "test://doc.md")
    assert len(chunks) == 1
    assert chunks[0].meta["heading_path"] == []


def test_heading_splitter_preserves_h3_under_h2():
    """[M3] H1 → H2 → H3-1/H3-2 共 4 chunk, H3 的 path 含 H1+H2"""
    text = """# H1

## H2

### H3-1

content 1

### H3-2

content 2
"""
    chunks = HeadingSplitter().split(text, "test://doc.md")
    assert len(chunks) == 4  # H1, H2, H3-1, H3-2
    assert chunks[2].meta["heading_path"] == ["H1", "H2", "H3-1"]
    assert chunks[3].meta["heading_path"] == ["H1", "H2", "H3-2"]


def test_heading_splitter_chunk_id_stable_same_input():
    """[M3] 同 input 必返同 chunk_id (idempotent, 防 preview 页刷新 hash 变)"""
    text = "# H\n\ncontent"
    c1 = HeadingSplitter().split(text, "test://doc.md")
    c2 = HeadingSplitter().split(text, "test://doc.md")
    assert c1[0].chunk_id == c2[0].chunk_id
