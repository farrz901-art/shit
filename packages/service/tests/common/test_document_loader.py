"""document_loader 测试"""


def test_load_md_files(tmp_path):
    """验证加载目录下 .md 文件"""
    (tmp_path / "a.md").write_text("# A\ncontent a", encoding="utf-8")
    (tmp_path / "b.md").write_text("# B\ncontent b", encoding="utf-8")
    (tmp_path / "c.txt").write_text("not md", encoding="utf-8")
    from src.common.document_loader import load_md_files

    docs = load_md_files(tmp_path)
    assert len(docs) == 2


def test_load_md_files_recursive(tmp_path):
    """验证递归加载"""
    sub = tmp_path / "sub"
    sub.mkdir()
    (tmp_path / "root.md").write_text("root", encoding="utf-8")
    (sub / "nested.md").write_text("nested", encoding="utf-8")
    from src.common.document_loader import load_md_files

    docs_recursive = load_md_files(tmp_path, recursive=True)
    assert len(docs_recursive) == 2
    docs_flat = load_md_files(tmp_path, recursive=False)
    assert len(docs_flat) == 1


def test_load_md_files_empty_dir(tmp_path):
    """空目录返回空列表"""
    from src.common.document_loader import load_md_files

    assert load_md_files(tmp_path) == []


def test_load_txt_files(tmp_path):
    """验证加载 .txt 文件"""
    (tmp_path / "a.txt").write_text("hello", encoding="utf-8")
    (tmp_path / "b.md").write_text("ignored", encoding="utf-8")
    from src.common.document_loader import load_txt_files

    docs = load_txt_files(tmp_path)
    assert len(docs) == 1


def test_load_txt_files_recursive(tmp_path):
    """验证递归加载 .txt"""
    sub = tmp_path / "sub"
    sub.mkdir()
    (tmp_path / "root.txt").write_text("root", encoding="utf-8")
    (sub / "nested.txt").write_text("nested", encoding="utf-8")
    from src.common.document_loader import load_txt_files

    docs = load_txt_files(tmp_path, recursive=True)
    assert len(docs) == 2


def test_load_documents_from_files(tmp_path):
    """从路径列表加载"""
    (tmp_path / "a.md").write_text("content a", encoding="utf-8")
    (tmp_path / "b.txt").write_text("content b", encoding="utf-8")
    from src.common.document_loader import load_documents_from_files

    docs = load_documents_from_files([tmp_path / "a.md", tmp_path / "b.txt"])
    assert len(docs) == 2


def test_load_documents_from_files_skips_missing(tmp_path):
    """不存在的文件跳过不报错"""
    from src.common.document_loader import load_documents_from_files

    docs = load_documents_from_files([tmp_path / "nonexistent.md"])
    assert len(docs) == 0


def test_extract_plain_text():
    """提取纯文本"""
    from src.common.document import RAGDoc
    from src.common.document_loader import extract_plain_text

    doc = RAGDoc(text="纯文本内容")
    assert extract_plain_text(doc) == "纯文本内容"


def test_filter_empty_documents():
    """过滤空文档"""
    from src.common.document import RAGDoc
    from src.common.document_loader import filter_empty_documents

    docs = [
        RAGDoc(text="有内容"),
        RAGDoc(text="   \n\t  "),
        RAGDoc(text=""),
    ]
    filtered = filter_empty_documents(docs)
    assert len(filtered) == 1
    assert "有内容" in filtered[0].text


def test_documents_to_texts():
    """验证 documents_to_texts"""
    from src.common.document import RAGDoc
    from src.common.document_loader import documents_to_texts

    docs = [RAGDoc(text="text1"), RAGDoc(text="text2")]
    texts = documents_to_texts(docs)
    assert texts == ["text1", "text2"]
