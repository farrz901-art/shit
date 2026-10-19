"""prompt_loader 测试"""

import pytest

from src.common.prompt_loader import load_prompt_from_md_file


def test_load_prompt_from_md_file(tmp_path):
    """验证加载 markdown 文件内容"""
    md_file = tmp_path / "test.md"
    md_file.write_text("# Test Title\n\n这是测试内容。", encoding="utf-8")

    content = load_prompt_from_md_file(md_file)
    assert "# Test Title" in content
    assert "这是测试内容。" in content


def test_load_prompt_file_not_found():
    """文件不存在时抛出 FileNotFoundError"""
    with pytest.raises(FileNotFoundError):
        load_prompt_from_md_file("not_exist.md")


def test_load_prompt_gbk_encoding(tmp_path):
    """验证 GBK 编码文件读取"""
    md_file = tmp_path / "gbk.md"
    md_file.write_text("# GBK 测试\n\n内容", encoding="gbk")

    content = load_prompt_from_md_file(md_file)
    assert "GBK" in content


def test_load_prompt_empty_file(tmp_path):
    """空文件返回空字符串"""
    md_file = tmp_path / "empty.md"
    md_file.write_text("", encoding="utf-8")

    content = load_prompt_from_md_file(md_file)
    assert content == ""


def test_load_prompt_multiline_content(tmp_path):
    """验证多行内容完整读取"""
    content = """# Title

## Section 1
段落1内容。

## Section 2
段落2内容。
"""
    md_file = tmp_path / "multi.md"
    md_file.write_text(content, encoding="utf-8")

    result = load_prompt_from_md_file(md_file)
    assert "# Title" in result
    assert "## Section 1" in result
    assert "段落1内容。" in result
    assert "段落2内容。" in result
