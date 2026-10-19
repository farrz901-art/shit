"""SpacyRuleExtractor 测试"""

from unittest.mock import MagicMock

from src.ingest.chunkers import TextChunk
from src.kg.extractors.spacy_rule.extractor import SpacyRuleExtractor


def test_spacy_rule_uses_injected_nlp():
    """[M4] mock nlp (0 真 spaCy), 验 entity 解析"""
    mock_nlp = MagicMock()
    ent = MagicMock()
    ent.text = "1LE0001"
    ent.label_ = "Product"
    ent.start_char = 0
    ent.end_char = 7
    mock_doc = MagicMock()
    mock_doc.ents = [ent]
    mock_nlp.return_value = mock_doc

    extractor = SpacyRuleExtractor(nlp=mock_nlp)
    chunks = [TextChunk(chunk_id="abc12345ab", text="1LE0001 是 电机 系列 的成员", meta={})]
    result = extractor.extract(chunks)
    assert result.extractor_id == "spacy_rule"
    assert result.error is None
    assert len(result.entities) == 1
    assert result.entities[0].text == "1LE0001"
    assert result.entities[0].label == "Product"


def test_spacy_rule_extracts_is_type_of_relation():
    """[M4] 'X 是 Y 的' 模式 → IS_TYPE_OF 关系, rule_type=factual"""
    mock_nlp = MagicMock()
    mock_doc = MagicMock()
    mock_doc.ents = []
    mock_nlp.return_value = mock_doc

    extractor = SpacyRuleExtractor(nlp=mock_nlp)
    chunks = [TextChunk(chunk_id="abc12345ab", text="电机 是 旋转机械 的子类", meta={})]
    result = extractor.extract(chunks)
    assert any(r.head == "电机" and r.tail == "旋转机械" and r.rel_type == "IS_TYPE_OF" for r in result.relations)


def test_spacy_rule_no_nlp_returns_error():
    """[M4] None nlp → error 字符串, 不抛异常"""
    extractor = SpacyRuleExtractor(nlp=None)
    chunks = [TextChunk(chunk_id="abc12345ab", text="content", meta={})]
    result = extractor.extract(chunks)
    assert result.error == "spaCy nlp 未初始化"
    assert result.entities == []
    assert result.relations == []
