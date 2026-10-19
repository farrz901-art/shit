"""转换器基类"""

import os
from pathlib import Path


class Converter:
    """转换器基类"""

    name: str = "base"
    # 子类必须声明：本 converter 支持哪些扩展名（小写、含点）
    # 例：KreuzbergConverter.extensions = [".pdf", ".png", ".docx", ...]
    extensions: list[str] = []

    @staticmethod
    def can_handle(info) -> bool:
        return False

    def convert(self, pdf_path: str, output_path: str) -> str:
        raise NotImplementedError

    def convert_batch(self, pdf_paths: list[str], output_dir: str) -> dict[str, str]:
        """批量转换多个PDF"""
        results = {}
        for pdf_path in pdf_paths:
            pdf_name = Path(pdf_path).stem
            output_path = os.path.join(output_dir, f"{pdf_name}.md")
            try:
                content = self.convert(pdf_path, output_path)
                results[pdf_path] = content
            except Exception as e:
                results[pdf_path] = f"[ERROR] {e}"
        return results
