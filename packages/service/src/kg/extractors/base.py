"""BaseExtractor Protocol + 4 数据类 (2026-07-01 v3)

隐性规则 (rule_type) 一等公民:
- 把"兼容/依赖/互斥/降容"从隐式语义升到显式标签
- 4 个抽取器都必须输出此字段; 非 LLM 抽取器用规则模式匹配赋默认值 'factual'
- v1.1 Rule 节点派生基础 (隐性规则 → 约束推理)

不复用 neo4j-graphrag EntityRelationExtractor 的原因 (2026-07-01 调研):
- 仍在 experimental.* namespace, 1 年半未迁出实验命名空间
- 1.14+ 自动 structured output 忽略 response_format
- NodeType.properties 强制非空, 跟我们的松弛 schema 不匹配

v3: HanLP/mREBEL 已删, 只 2 个 extractor (spacy_rule / llm_pydantic)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Protocol, runtime_checkable

RuleType = Literal["compatibility", "dependency", "exclusion", "derating", "factual"]


@dataclass
class ExtractedEntity:
    text: str
    label: str
    chunk_id: str
    char_span: tuple[int, int]
    confidence: float = 1.0


@dataclass
class ExtractedRelation:
    head: str
    rel_type: str
    tail: str
    chunk_id: str
    confidence: float = 1.0
    rule_type: RuleType = "factual"


@dataclass
class ExtractionResult:
    entities: list[ExtractedEntity] = field(default_factory=list)
    relations: list[ExtractedRelation] = field(default_factory=list)
    extractor_id: str = ""
    elapsed_ms: int = 0
    error: str | None = None


@runtime_checkable
class BaseExtractor(Protocol):
    extractor_id: str

    def extract(self, chunks: list) -> ExtractionResult: ...
