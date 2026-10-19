"""Kreuzberg 转换器 - 适合简单 PDF"""

import os
from pathlib import Path
from typing import TYPE_CHECKING, cast

from kreuzberg import ExtractionConfig, batch_extract_files_sync, extract_file_sync

# OutputFormat 在 kreuzberg 4.9.7 存在但 stub 不全, 用 TYPE_CHECKING 占位 + 运行时 getattr
if TYPE_CHECKING:
    from kreuzberg import OutputFormat  # pyright: ignore[reportAttributeAccessIssue]
else:
    from kreuzberg import __dict__ as _kz_dict

    OutputFormat = _kz_dict.get("OutputFormat")

from .base import Converter


class KreuzbergConverter(Converter):
    """Kreuzberg转换器 - 适合简单PDF"""

    name = "kreuzberg"
    extensions = [".pdf"]  # kreuzberg 只处理简单 PDF（其他格式走 mineru / 不支持）

    @staticmethod
    def can_handle(info) -> bool:
        return info.is_simple and info.has_text

    def convert(self, pdf_path: str, output_path: str) -> str:
        config = ExtractionConfig(output_format=OutputFormat.MARKDOWN)
        result = extract_file_sync(pdf_path, config=config)

        if result.content:
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(result.content)
            return result.content
        return ""

    def convert_batch(self, pdf_paths: list[str], output_dir: str) -> dict[str, str]:
        """kreuzberg 批量处理

        输出布局: <output_dir>/<stem>/<stem>.md（2 层，跟 CAD / md 直通对齐）
        注：mineru 容器原生输出 <output>/<stem>/auto/<stem>.md（3 层），
            不在本次统一范围。
        """
        # 注意：必须用 *_sync 版。
        # kreuzberg 4.9.7 中 batch_extract_files 是 async 协程函数，
        # 直接调用会拿到 coroutine 对象而不是 list，导致 'coroutine' object is not iterable
        # 以及 RuntimeWarning: coroutine ... was never awaited。
        config = ExtractionConfig(output_format=OutputFormat.MARKDOWN)

        # 与 MineruConverter 对齐：调用方无需关心 output_dir 是否已存在
        os.makedirs(output_dir, exist_ok=True)

        # 调用kreuzberg的批量接口
        results = batch_extract_files_sync(cast(list[str | Path], pdf_paths), config=config)

        output: dict[str, str] = {}
        for pdf_path, result in zip(pdf_paths, results):
            stem = Path(pdf_path).stem
            # 子目录布局：<output_dir>/<stem>/<stem>.md
            subdir = os.path.join(output_dir, stem)
            os.makedirs(subdir, exist_ok=True)
            output_path = os.path.join(subdir, f"{stem}.md")
            if result.content:
                with open(output_path, "w", encoding="utf-8") as f:
                    f.write(result.content)
                output[str(pdf_path)] = result.content
            else:
                output[str(pdf_path)] = ""
        return output
