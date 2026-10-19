"""Prompt 加载器

将 markdown 文件加载为字符串，供 LLM 使用。
"""

from pathlib import Path

from .text_io import read_text_with_fallback


def load_prompt_from_md_file(file_path: str | Path) -> str:
    """加载 markdown 文件内容为字符串

    Args:
        file_path: markdown 文件路径

    Returns:
        文件内容字符串

    Raises:
        FileNotFoundError: 文件不存在
        ValueError: 无法解码文件
    """
    fp = Path(file_path)
    if not fp.exists():
        raise FileNotFoundError(f"文件不存在: {file_path}")

    text = read_text_with_fallback(fp)
    if text is None:
        raise ValueError(f"无法解码文件: {file_path}")

    return text
