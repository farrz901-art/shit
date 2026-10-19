"""RAGDoc 数据载体 (项目内统一文档表示).

接口保留 `.get_content()` 兼容老 Document 形式, 调用方零改动.
"""

from dataclasses import dataclass, field


@dataclass
class RAGDoc:
    """统一 RAG 文档载体. 提供 `.get_content()` 取正文."""

    text: str
    metadata: dict = field(default_factory=dict)

    def get_content(self) -> str:
        return self.text
