"""回归测试：保证老路径 src.pdf_processor 在代码库中 0 引用

重命名后必须无遗漏；任何文件 import 老路径都视为 bug。
"""

import subprocess
from pathlib import Path


def test_no_stale_pdf_processor_imports():
    """全代码库 grep 老路径必须 0 命中（仅 Python 文件）"""
    root = Path(__file__).parent.parent

    patterns = [
        "from src.pdf_processor",  # 标准 import
        "import src.pdf_processor",  # 备选 import
        "src.pdf_processor.",  # 属性访问
    ]

    for pattern in patterns:
        # 只搜 .py 文件（import 是 Python 概念，markdown 文档是历史记录不算）
        # 排除 self（本测试文件包含 pattern 字面量）
        # 排除 rewrite_imports.py（一次性迁移工具，含 OLD 字符串常量）
        # 排除 update_doc_references.py（一次性迁移工具，含 OLD 字符串常量）
        result = subprocess.run(
            [
                "grep",
                "-rn",
                "--include=*.py",
                "--exclude-dir=.git",
                "--exclude-dir=.venv",
                "--exclude-dir=__pycache__",
                "--exclude-dir=.pytest_cache",
                "--exclude=test_no_stale_pdf_processor_imports.py",
                "--exclude=rewrite_imports.py",
                "--exclude=update_doc_references.py",
                pattern,
                str(root),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        # grep 找到时 returncode=0 + stdout 有内容
        assert result.returncode != 0 or not result.stdout.strip(), (
            f"发现老路径引用: {pattern}\n{result.stdout}\n所有 src.pdf_processor 引用必须改成 src.ingest"
        )
