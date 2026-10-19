"""config_loader 测试"""

import pytest

from src.kg import config_loader


def test_load_extractor_config_spacy(monkeypatch: pytest.MonkeyPatch) -> None:
    """load_extractor_config('spacy_rule') 返 enabled + spacy_model"""
    cfg = config_loader.load_extractor_config("spacy_rule")
    assert cfg["extractor_id"] == "spacy_rule"
    assert cfg["enabled"] is True
    assert "spacy_model" in cfg


def test_load_extractor_config_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    """load_extractor_config('llm_pydantic') 返 enabled"""
    cfg = config_loader.load_extractor_config("llm_pydantic")
    assert cfg["extractor_id"] == "llm_pydantic"
    assert cfg["enabled"] is True


def test_load_extractor_config_missing_raises(tmp_path) -> None:
    """不存在的 extractor_id 必报错"""
    # 用 RAG_EXTRACTOR_CONFIG_DIR 指到空目录
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setenv("RAG_EXTRACTOR_CONFIG_DIR", str(tmp_path))
    with pytest.raises(FileNotFoundError, match="extractor config 不存在"):
        config_loader.load_extractor_config("nonexistent")
    monkeypatch.undo()


def test_list_extractor_ids_returns_yaml_stems(monkeypatch: pytest.MonkeyPatch) -> None:
    """list_extractor_ids 返所有 yaml 文件 stem, sorted"""
    ids = config_loader.list_extractor_ids()
    # 至少含 llm_pydantic + spacy_rule (configs/extractors/ 下的)
    assert "spacy_rule" in ids
    assert "llm_pydantic" in ids
    assert ids == sorted(ids)
