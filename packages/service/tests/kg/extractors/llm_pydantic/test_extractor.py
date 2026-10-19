"""LlmPydanticExtractor 测试"""

import json
from unittest.mock import MagicMock

from src.ingest.chunkers import TextChunk
from src.kg.extractors.llm_pydantic.extractor import LlmPydanticExtractor


def test_llm_extractor_parses_llm_response():
    """[M4] mock LLM 返 JSON, 验 entity + relation 正确解析"""
    mock_llm = MagicMock()
    mock_llm.chat.return_value = json.dumps(
        {
            "entities": [{"text": "1LE0001", "label": "Product", "span": [0, 7], "confidence": 0.95}],
            "relations": [
                {"head": "1LE0001", "rel_type": "HAS_SPEC", "tail": "230V", "rule_type": "factual", "confidence": 0.9}
            ],
        },
        ensure_ascii=False,
    )
    extractor = LlmPydanticExtractor(llm=mock_llm, prompt_template="提取实体和关系")
    chunks = [TextChunk(chunk_id="abc12345ab", text="1LE0001 支持 230V", meta={})]
    result = extractor.extract(chunks)
    assert result.extractor_id == "llm_pydantic"
    assert result.error is None
    assert len(result.entities) == 1
    assert result.entities[0].text == "1LE0001"
    assert result.relations[0].rule_type == "factual"


def test_llm_extractor_handles_rule_type():
    """[M4] rule_type = 'compatibility' 正确解析"""
    mock_llm = MagicMock()
    mock_llm.chat.return_value = json.dumps(
        {
            "entities": [],
            "relations": [{"head": "A", "rel_type": "COMPATIBLE_WITH", "tail": "B", "rule_type": "compatibility"}],
        }
    )
    extractor = LlmPydanticExtractor(llm=mock_llm)
    chunks = [TextChunk(chunk_id="c", text="A 兼容 B", meta={})]
    result = extractor.extract(chunks)
    assert result.relations[0].rule_type == "compatibility"


def test_llm_extractor_skips_malformed_json_chunk():
    """[M4] 单 chunk JSON 解析失败 → 跳过, 不影响其他 chunk"""
    mock_llm = MagicMock()
    mock_llm.chat.side_effect = [
        "bad json {{{",
        json.dumps(
            {
                "entities": [{"text": "X", "label": "Product", "span": [0, 1]}],
                "relations": [],
            }
        ),
    ]
    extractor = LlmPydanticExtractor(llm=mock_llm)
    chunks = [TextChunk(chunk_id="c1", text="bad", meta={}), TextChunk(chunk_id="c2", text="good", meta={})]
    result = extractor.extract(chunks)
    assert len(result.entities) == 1
    assert result.entities[0].text == "X"


def test_llm_extractor_no_llm_returns_error():
    """[M4] None LLM → error 字符串"""
    extractor = LlmPydanticExtractor(llm=None)
    result = extractor.extract([TextChunk(chunk_id="c", text="x", meta={})])
    assert result.error == "LLM 未初始化"
