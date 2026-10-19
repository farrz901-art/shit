"""BaseExtractor 数据类 + Protocol 测试"""

from typing import Protocol

from src.kg.extractors.base import (
    BaseExtractor,
    ExtractedEntity,
    ExtractedRelation,
    ExtractionResult,
)


def test_extracted_entity_defaults():
    """[M4] Entity 默认可选字段: confidence=1.0, char_span 不变"""
    e = ExtractedEntity(text="1LE0001", label="Product", chunk_id="abc12345ab", char_span=(0, 7))
    assert e.confidence == 1.0
    assert e.text == "1LE0001"


def test_extracted_relation_rule_type_default_factual():
    """[M4] rule_type 默认 'factual' (事实陈述), 非 LLM 抽取器用此默认值"""
    r = ExtractedRelation(head="1LE0001", rel_type="HAS_SPEC", tail="230V", chunk_id="abc12345ab")
    assert r.rule_type == "factual"


def test_extracted_relation_rule_type_validates_literal():
    """[M4] rule_type 5 选 1: compatibility/dependency/exclusion/derating/factual"""
    for rt in ("compatibility", "dependency", "exclusion", "derating", "factual"):
        r = ExtractedRelation(head="X", rel_type="R", tail="Y", chunk_id="c", rule_type=rt)
        assert r.rule_type == rt


def test_extraction_result_aggregates_entities_relations():
    """[M4] ExtractionResult 同时装 entities + relations + metadata"""
    r = ExtractionResult(
        entities=[ExtractedEntity(text="A", label="L", chunk_id="c", char_span=(0, 1))],
        relations=[ExtractedRelation(head="A", rel_type="R", tail="B", chunk_id="c")],
        extractor_id="spacy_rule",
        elapsed_ms=42,
    )
    assert len(r.entities) == 1
    assert len(r.relations) == 1
    assert r.extractor_id == "spacy_rule"
    assert r.error is None


def test_extraction_result_error_short_circuits():
    """[M4] error 非 None 时 entities/relations 可为空"""
    r = ExtractionResult(error="模型未加载", extractor_id="spacy_rule")
    assert r.error == "模型未加载"
    assert r.entities == []
    assert r.relations == []


def test_base_extractor_is_protocol():
    """[M4] BaseExtractor 是 Protocol (非 ABC), 支持 MagicMock"""
    assert issubclass(BaseExtractor, Protocol)
