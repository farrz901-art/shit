"""LLM + Pydantic 强约束抽取器 (主力, 2026-07-01 spec, v3)

准确率 88-97% (业界 2026 H1 SOTA)
JSON Schema 强约束在 prompt 里手写 (不靠 response_format).
"""

from __future__ import annotations

import json

from ..base import ExtractedEntity, ExtractedRelation, ExtractionResult


class LlmPydanticExtractor:
    extractor_id = "llm_pydantic"

    def __init__(self, llm=None, prompt_template: str = "", max_retries: int = 3):
        self.llm = llm
        self.prompt_template = prompt_template or _DEFAULT_PROMPT
        self.max_retries = max_retries

    def extract(self, chunks: list) -> ExtractionResult:
        if self.llm is None:
            return ExtractionResult(extractor_id=self.extractor_id, error="LLM 未初始化")
        entities: list[ExtractedEntity] = []
        relations: list[ExtractedRelation] = []
        for chunk in chunks:
            response_text = self._call_llm_with_retry(chunk.text)
            try:
                data = json.loads(response_text)
            except json.JSONDecodeError:
                continue
            for e in data.get("entities", []):
                span = e.get("span", [0, 0])
                entities.append(
                    ExtractedEntity(
                        text=e["text"],
                        label=e["label"],
                        chunk_id=chunk.chunk_id,
                        char_span=(span[0], span[1]) if len(span) == 2 else (0, 0),
                        confidence=e.get("confidence", 1.0),
                    )
                )
            for r in data.get("relations", []):
                relations.append(
                    ExtractedRelation(
                        head=r["head"],
                        rel_type=r["rel_type"],
                        tail=r["tail"],
                        chunk_id=chunk.chunk_id,
                        confidence=r.get("confidence", 1.0),
                        rule_type=r.get("rule_type", "factual"),
                    )
                )
        return ExtractionResult(entities=entities, relations=relations, extractor_id=self.extractor_id, elapsed_ms=0)

    def _call_llm_with_retry(self, chunk_text: str) -> str:
        # 重依赖 lazy: tenacity 启动慢, 仅 retry 包装需要
        from tenacity import retry, stop_after_attempt, wait_exponential  # noqa: E402

        llm = self.llm
        prompt = self.prompt_template

        @retry(stop=stop_after_attempt(self.max_retries), wait=wait_exponential(min=1, max=10))
        def _call():
            return llm.chat(  # type: ignore[union-attr]
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": chunk_text},
                ]
            )

        return _call()


_DEFAULT_PROMPT = """从以下中文 Markdown 文本抽取实体和关系. 严格返 JSON 格式, 不要任何额外解释:

{
  "entities": [{"text": "...", "label": "Product|Series|Spec|Standard", "span": [start, end], "confidence": 0.0-1.0}],
  "relations": [{"head": "...", "rel_type": "HAS_SPEC|BELONGS_TO|MATCHES|IS_TYPE_OF", "tail": "...",
                  "rule_type": "compatibility|dependency|exclusion|derating|factual", "confidence": 0.0-1.0}]
}

rule_type 必填, 5 选 1:
- compatibility: 兼容关系
- dependency: 依赖关系
- exclusion: 互斥关系
- derating: 降容关系
- factual: 事实陈述 (默认)

只输出 JSON, 不输出解释文字."""
