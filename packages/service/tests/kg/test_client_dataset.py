"""KgClient dataset label 隔离测试 (2026-07-01 markdown extract KG spec PR1, v3)

覆盖: 默认 dataset / cypher 加 WHERE n:<Dataset> / MERGE 加 :<Dataset> / 5 元组分组不变

测试模式: 模式 1 (纯 mock, 0 Neo4j/0 PG)
"""

from typing import Any, cast
from unittest.mock import MagicMock

import pytest

from src.kg import datasets
from src.kg.client import KgClient, TripleRow


@pytest.fixture(autouse=True)
def _seed_allowed_datasets(monkeypatch: pytest.MonkeyPatch):
    """每个 test 前种子 ALLOWED_DATASETS 白名单, 避免被其他 test 污染"""
    monkeypatch.setattr(datasets, "ALLOWED_DATASETS", ["motor", "plc", "sensor"])


def test_kgclient_default_dataset_in_cypher():
    """KgClient 实例化必加 dataset 校验, cypher 加 WHERE n:<Dataset>"""
    kg = KgClient(store=MagicMock(), dataset="motor")
    cypher, _params = kg._build_unwind_cypher(
        [
            TripleRow(
                from_label="Product",
                from_key="model",
                from_value="1LE0001",
                rel_type="HAS_SPEC",
                to_label="Spec",
                to_key="name",
                to_value="230V",
            )
        ]
    )
    # MERGE 加 :<Dataset> label
    assert "MERGE (a:Product:`motor`" in cypher
    assert "MERGE (b:Spec:`motor`" in cypher


def test_kgclient_rejects_unknown_dataset():
    """dataset 不在白名单 → ValueError (强校验)"""
    with pytest.raises(ValueError, match="白名单"):
        KgClient(store=MagicMock(), dataset="evil_inject")


def test_kgclient_rejects_invalid_identifier():
    """dataset 不是合法 Cypher identifier (含特殊字符) → ValueError"""
    with pytest.raises(ValueError, match="identifier"):
        KgClient(store=MagicMock(), dataset="motor'` OR 1=1--")


def test_kgclient_list_nodes_uses_dataset_in_where():
    """list_nodes cypher 必含 WHERE n:`<Dataset>`, 强制隔离"""
    kg = KgClient(store=MagicMock(), dataset="plc")
    store = cast(Any, kg._store)
    store.execute_and_fetch.return_value = []
    kg.list_nodes(skip=0, limit=10)
    cypher = store.execute_and_fetch.call_args[0][0]
    assert "WHERE n:`plc`" in cypher


def test_kgclient_list_relationships_filters_both_endpoints():
    """list_relationships 必须两个 endpoint 都带 dataset label"""
    kg = KgClient(store=MagicMock(), dataset="sensor")
    store = cast(Any, kg._store)
    store.execute_and_fetch.return_value = []
    kg.list_relationships(skip=0, limit=10)
    cypher = store.execute_and_fetch.call_args[0][0]
    assert "MATCH (a:`sensor`)" in cypher
    assert "MATCH (a:`sensor`)-[r]->(b:`sensor`)" in cypher


def test_batch_upsert_grouping_keeps_5_tuple():
    """5 元组分组不变, dataset 在每组 cypher 字面量展开"""
    kg = KgClient(store=MagicMock(), dataset="motor")
    store = cast(Any, kg._store)
    store.execute_and_fetch.return_value = [{"cnt": 1}]
    rows = [
        TripleRow(
            from_label="Product",
            from_key="model",
            from_value="1LE0001",
            rel_type="HAS_SPEC",
            to_label="Spec",
            to_key="name",
            to_value="230V",
        ),
    ]
    kg.batch_upsert_triples(rows)
    # 同 5 元组 → 1 次 execute_and_fetch
    assert store.execute_and_fetch.call_count == 1
    cypher = store.execute_and_fetch.call_args[0][0]
    assert "MERGE (a:Product:`motor`" in cypher


def test_validate_dataset_accepts_allowed():
    """白名单内的合法 identifier 通过校验"""
    datasets.validate_dataset("motor")
    datasets.validate_dataset("plc")
    datasets.validate_dataset("sensor")


def test_validate_dataset_rejects_invalid_chars():
    """非 identifier 字符被拒 (Cypher label 注入防御)"""
    with pytest.raises(ValueError):
        datasets.validate_dataset("motor; DROP")
    with pytest.raises(ValueError):
        datasets.validate_dataset("1motor")  # 不能数字开头 (Cypher 要求)
    with pytest.raises(ValueError):
        datasets.validate_dataset("motor-plc")  # - 是减号非下划线


def test_validate_dataset_rejects_empty():
    """空字符串被拒"""
    with pytest.raises(ValueError):
        datasets.validate_dataset("")
