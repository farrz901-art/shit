"""spaCy 规则抽取器 (2026-07-01 markdown extract KG spec)

适用: 高吞吐兜底 (CPU 单核 ~1000 docs/s), 不依赖 LLM API

2026 H1 调研: spaCy 3.8.14 (2026-03-29), API 稳定 pin 3.8.14
Matcher / EntityRuler / PhraseMatcher 全部 API 保持 v3.0 签名.
"""

from __future__ import annotations

import re

from ..base import ExtractedEntity, ExtractedRelation, ExtractionResult

_IS_TYPE_RE = re.compile(r"(.+?)\s+是\s+(.+?)的")


class SpacyRuleExtractor:
    """spaCy Matcher + EntityRuler 规则抽取

    Args:
        nlp: 注入的 spaCy Language 实例. v1 测试侧传 mock, 业务侧注入真 nlp.
    """

    extractor_id = "spacy_rule"

    def __init__(self, nlp=None):
        self.nlp = nlp

    def extract(self, chunks: list) -> ExtractionResult:
        if self.nlp is None:
            return ExtractionResult(extractor_id=self.extractor_id, error="spaCy nlp 未初始化")
        entities: list[ExtractedEntity] = []
        relations: list[ExtractedRelation] = []
        for chunk in chunks:
            doc = self.nlp(chunk.text)
            for ent in doc.ents:
                entities.append(
                    ExtractedEntity(
                        text=ent.text,
                        label=ent.label_,
                        chunk_id=chunk.chunk_id,
                        char_span=(ent.start_char, ent.end_char),
                    )
                )
        for chunk in chunks:
            for m in _IS_TYPE_RE.finditer(chunk.text):
                head, tail = m.group(1).strip(), m.group(2).strip()
                relations.append(
                    ExtractedRelation(
                        head=head,
                        rel_type="IS_TYPE_OF",
                        tail=tail,
                        chunk_id=chunk.chunk_id,
                        rule_type="factual",
                    )
                )
        return ExtractionResult(
            entities=entities,
            relations=relations,
            extractor_id=self.extractor_id,
            elapsed_ms=0,
        )
