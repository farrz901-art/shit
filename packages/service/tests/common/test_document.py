"""测试 RAGDoc 数据类"""

from src.common.document import RAGDoc


def test_ragdoc_basic():
    doc = RAGDoc(text="hello", metadata={"file_path": "/a.md"})
    assert doc.text == "hello"
    assert doc.metadata == {"file_path": "/a.md"}


def test_ragdoc_get_content_returns_text():
    doc = RAGDoc(text="content")
    assert doc.get_content() == "content"


def test_ragdoc_default_metadata():
    doc = RAGDoc(text="x")
    assert doc.metadata == {}


def test_ragdoc_metadata_is_dict():
    doc = RAGDoc(text="x", metadata={"k": "v"})
    doc.metadata["k2"] = "v2"
    assert doc.metadata == {"k": "v", "k2": "v2"}
