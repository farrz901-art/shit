"""文本文件 I/O 工具

抽公共函数是为了消除 _read_file_with_fallback 在 prompt_loader 和
document_loader 里的重复实现 (2026-06-08 shim 清理)。

(2026-06-23) 修 2 个边界:
- 文件不存在: 返 None (不抛 FileNotFoundError), 业务上 read_text 是 best-effort
- 二进制文件: latin-1 不会失败 (1:1 映射所有 256 字节), 靠 NUL 字节比例判断 → 返 None
"""

from pathlib import Path

# 编码回退顺序：utf-8 (现代默认) → gbk / gb2312 (Windows 中文遗留) → latin-1 (兜底)
_FALLBACK_ENCODINGS = ("utf-8", "gbk", "gb2312", "latin-1")

# 二进制文件判定阈值: 任何 NUL 字节 (\x00) 即视为二进制.
# bytes(range(256)) 含 1 个 NUL, 1/256 ≈ 0.4% 已经够低, 真实文本不会出现 NUL.
# 用 'any' 避免 0.4% < 1% 漏判. (2026-06-23)
_BINARY_NUL_RATIO = 0.0


def _looks_binary(content: str) -> bool:
    """(2026-06-23) 检测是否二进制: 内容含 NUL 字节 (\x00) 即视为二进制.

    真实文本 (utf-8/gbk 编码) 不会含 NUL, 二进制文件 (图片/可执行/zip) 一定含 NUL.
    'any NUL' 简单可靠, 业务用 latin-1 兜底解码, 拿到 \x00 即识别 binary 返 None.
    """
    return "\x00" in content


def read_text_with_fallback(f: str | Path) -> str | None:
    """尝试多种编码读取文本文件

    适用于 .md / .txt 等可能来自不同平台/编辑器的文本文件。
    文件不存在或疑似二进制时返回 None（不抛异常）。

    Args:
        f: 文件路径

    Returns:
        解码后的字符串；文件不存在 / 疑似二进制 / 所有编码都失败时返 None
    """
    fp = Path(f)
    # (2026-06-23) 文件不存在: 返 None 而非抛 FileNotFoundError, 业务上 read_text 是 best-effort
    if not fp.exists():
        return None
    for enc in _FALLBACK_ENCODINGS:
        try:
            content = fp.read_text(encoding=enc)
        except UnicodeDecodeError:
            continue
        # (2026-06-23) 二进制文件 latin-1 不会失败 (1:1 映射所有 256 字节),
        # 用 NUL 字节比例识别, 避免返一堆乱码
        if _looks_binary(content):
            return None
        return content
    return None
