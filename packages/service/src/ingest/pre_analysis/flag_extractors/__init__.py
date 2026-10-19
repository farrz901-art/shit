"""(2026-07-08 refactor) Paragraph flag extraction 包.

从 runner.py 拆出, 跟 src/ingest/pre_analysis/table_extractors/ 同结构:
- extractor.py: 主算法 (_extract_flagged_paragraphs + CompiledRulePatterns + 14 列 dict)
- splitter.py: 4-mode 段落切分 (_split_paragraphs)
- spacy_enhancer.py: spacy + tiktoken 增强 (SpacyEnhancer + 模块级单例 + _get_enhancer)

公开 API 重导出, 让 caller 一次 from .flag_extractors import ... 拿全部.
"""

from __future__ import annotations

from .extractor import CompiledRulePatterns, extract_flagged_paragraphs
from .spacy_enhancer import _ENHANCER, SpacyEnhancer, _get_enhancer  # noqa: F401  (测试侧需要 monkeypatch 单例)
from .splitter import split_paragraphs

__all__ = [
    "CompiledRulePatterns",
    "extract_flagged_paragraphs",
    "split_paragraphs",
    "SpacyEnhancer",
    "_ENHANCER",
    "_get_enhancer",
]
