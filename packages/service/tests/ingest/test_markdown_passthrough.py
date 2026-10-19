"""MarkdownPassthroughHandler 单元测试"""

import os

import pytest

from src.ingest.pdf_processing.markdown_passthrough import MarkdownPassthroughHandler

SAMPLE_MD = "tests/fixtures/test_doc.md"


class TestMarkdownPassthrough:
    """MarkdownPassthroughHandler 行为测试"""

    def test_name(self):
        """name 必须是 'passthrough'"""
        handler = MarkdownPassthroughHandler()
        assert handler.name == "passthrough"

    def test_passthrough_extensions(self):
        """passthrough_extensions 含 .md"""
        handler = MarkdownPassthroughHandler()
        assert ".md" in handler.passthrough_extensions

    def test_extensions_alias_matches_passthrough_extensions(self):
        """extensions 别名跟 passthrough_extensions 保持一致

        跟 Converter.extensions 接口对齐，让 process_files 等通用代码能用
        ext in handler.extensions 这种 polymorphic 写法。
        """
        handler = MarkdownPassthroughHandler()
        assert ".md" in handler.extensions
        assert handler.extensions is handler.passthrough_extensions

    def test_convert_copies_md_to_subdir(self, tmp_path):
        """.md 文件被复制到 <output>/<stem>/<stem>.md"""
        handler = MarkdownPassthroughHandler()
        src = SAMPLE_MD

        result = handler.convert(src, str(tmp_path))

        stem = os.path.splitext(os.path.basename(src))[0]
        expected = tmp_path / stem / f"{stem}.md"
        assert os.path.exists(expected), f"未复制到: {expected}"
        assert result == str(expected), f"convert 返回路径不对: {result}"

    def test_convert_content_identical(self, tmp_path):
        """复制后内容字节级一致"""
        handler = MarkdownPassthroughHandler()
        result = handler.convert(SAMPLE_MD, str(tmp_path))

        with open(result, encoding="utf-8") as f:
            dst_content = f.read()
        with open(SAMPLE_MD, encoding="utf-8") as f:
            src_content = f.read()
        assert dst_content == src_content

    def test_convert_auto_creates_dirs(self, tmp_path):
        """子目录不存在时自动创建（深嵌套）"""
        handler = MarkdownPassthroughHandler()
        deep = tmp_path / "a" / "b" / "c"
        assert not deep.exists()

        handler.convert(SAMPLE_MD, str(deep))

        stem = os.path.splitext(os.path.basename(SAMPLE_MD))[0]
        assert (deep / stem / f"{stem}.md").exists()

    def test_convert_nonexistent_raises(self, tmp_path):
        """源文件不存在时报 FileNotFoundError"""
        handler = MarkdownPassthroughHandler()
        with pytest.raises(FileNotFoundError):
            handler.convert(str(tmp_path / "nonexistent.md"), str(tmp_path))

    def test_convert_batch_returns_dict(self, tmp_path):
        """convert_batch 返回 {src: dst} 字典"""
        handler = MarkdownPassthroughHandler()
        results = handler.convert_batch([SAMPLE_MD], str(tmp_path))

        assert SAMPLE_MD in results
        assert os.path.exists(results[SAMPLE_MD])
