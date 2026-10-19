"""text_io.py 单元测试"""

from src.common.text_io import read_text_with_fallback


def test_read_utf8(tmp_path):
    f = tmp_path / "test.txt"
    f.write_text("你好 world", encoding="utf-8")
    result = read_text_with_fallback(f)
    assert result == "你好 world"


def test_read_gbk(tmp_path):
    f = tmp_path / "test.txt"
    f.write_bytes("中文GBK编码".encode("gbk"))
    result = read_text_with_fallback(f)
    assert result == "中文GBK编码"


def test_read_nonexistent_returns_none(tmp_path):
    result = read_text_with_fallback(tmp_path / "nonexistent.txt")
    assert result is None


def test_read_binary_returns_none(tmp_path):
    f = tmp_path / "test.bin"
    f.write_bytes(bytes(range(256)))
    result = read_text_with_fallback(f)
    assert result is None
