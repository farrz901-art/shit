"""datasets 白名单 + validate + load_from_env 测试 (2026-07-01 PR1, v3)

v3 设计: 单源白名单 (env KG_ALLOWED_DATASETS), 业务侧严禁任意字符串当 dataset

测试模式: 模式 1 (纯函数 + monkeypatch env, 0 PG/0 Neo4j)
"""

import pytest

from src.kg import datasets


def test_load_from_env_default(monkeypatch: pytest.MonkeyPatch):
    """env 缺失 → 默认 ["motor"] 兜底

    不让无 env 启动失败, 容错第一. 业务侧启动后看 logger warning.
    """
    monkeypatch.delenv("KG_ALLOWED_DATASETS", raising=False)
    assert datasets.load_from_env() == ["motor"]


def test_load_from_env_comma_separated(monkeypatch: pytest.MonkeyPatch):
    """env = "motor,plc,sensor" → 返列表"""
    monkeypatch.setenv("KG_ALLOWED_DATASETS", "motor,plc,sensor")
    assert datasets.load_from_env() == ["motor", "plc", "sensor"]


def test_load_from_env_strips_whitespace(monkeypatch: pytest.MonkeyPatch):
    """env 带空格 → trim"""
    monkeypatch.setenv("KG_ALLOWED_DATASETS", " motor , plc ")
    assert datasets.load_from_env() == ["motor", "plc"]


def test_load_from_env_skips_empty(monkeypatch: pytest.MonkeyPatch):
    """env 含空 token (e.g. "motor,,plc") → 跳空"""
    monkeypatch.setenv("KG_ALLOWED_DATASETS", "motor,,plc")
    assert datasets.load_from_env() == ["motor", "plc"]


def test_list_datasets_returns_module_level():
    """list_datasets 返模块级 ALLOWED_DATASETS snapshot"""
    datasets.ALLOWED_DATASETS = ["a", "b"]
    assert datasets.list_datasets() == ["a", "b"]


def test_validate_dataset_ok():
    """白名单内 + identifier 合法 → 通过"""
    datasets.ALLOWED_DATASETS = ["motor", "plc"]
    datasets.validate_dataset("motor")
    datasets.validate_dataset("plc")


def test_validate_dataset_not_in_whitelist():
    """白名单外 → ValueError, 错误信息含白名单"""
    datasets.ALLOWED_DATASETS = ["motor"]
    with pytest.raises(ValueError, match="白名单"):
        datasets.validate_dataset("evil")


def test_validate_dataset_invalid_identifier():
    """非法 identifier → ValueError

    Cypher label 注入防御: 业务侧忘校验会导致 cypher 语法错或注入
    """
    datasets.ALLOWED_DATASETS = ["motor"]
    with pytest.raises(ValueError, match="identifier"):
        datasets.validate_dataset("motor-dash")


def test_validate_dataset_empty():
    """空字符串 → ValueError"""
    datasets.ALLOWED_DATASETS = ["motor"]
    with pytest.raises(ValueError):
        datasets.validate_dataset("")
