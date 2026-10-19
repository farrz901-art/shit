"""Markdown 直通处理器

不转换 .md 文件，直接复制到 <output>/<stem>/<stem>.md。
跟 Document / CAD 输出布局对齐。
"""

import shutil
from pathlib import Path


class MarkdownPassthroughHandler:
    """把 .md 原样复制到 output 子目录"""

    name: str = "passthrough"
    passthrough_extensions: list[str] = [".md"]
    # 别名：跟 Converter.extensions 接口对齐，让 process_files 等通用代码
    # 能用 ext in handler.extensions 这种 polymorphic 写法
    extensions = passthrough_extensions

    def convert(self, file_path: str, output_dir: str) -> str:
        """复制单个 .md 到 <output>/<stem>/<stem>.md

        Args:
            file_path: 源 .md 路径
            output_dir: 输出根目录

        Returns:
            复制后文件绝对路径

        Raises:
            FileNotFoundError: 源文件不存在
        """
        src = Path(file_path).resolve()
        if not src.exists():
            raise FileNotFoundError(f"源文件不存在: {src}")

        subdir = Path(output_dir) / src.stem
        subdir.mkdir(parents=True, exist_ok=True)
        dst = subdir / src.name
        shutil.copy(src, dst)
        return str(dst)

    def convert_batch(self, file_paths: list[str], output_dir: str) -> dict[str, str]:
        """批量复制

        Returns:
            {src_path: dst_path}
        """
        return {p: self.convert(p, output_dir) for p in file_paths}
