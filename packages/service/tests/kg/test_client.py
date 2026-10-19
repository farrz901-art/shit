"""kg/client.py 单元测试"""

from unittest.mock import MagicMock

import pytest

from src.kg import datasets
from src.kg.client import BatchResult, KgClient, TripleRow


@pytest.fixture(autouse=True)
def _seed_allowed_datasets(monkeypatch: pytest.MonkeyPatch):
    """每个 test 前种子 ALLOWED_DATASETS 白名单 (PR1 v3 dataset 隔离)"""
    monkeypatch.setattr(datasets, "ALLOWED_DATASETS", ["motor", "plc", "sensor"])


class TestTripleRow:
    def test_default_properties(self):
        row = TripleRow(
            from_label="A", from_key="k1", from_value="v1", rel_type="R", to_label="B", to_key="k2", to_value="v2"
        )
        assert row.properties == {}


class TestBatchResult:
    def test_defaults(self):
        r = BatchResult()
        assert r.success == 0
        assert r.failed == 0
        assert r.errors == []


class TestKgClient:
    def test_build_merge_node_cypher(self):
        client = KgClient(store=MagicMock(), dataset="motor")
        cypher, params = client._build_merge_node_cypher(
            "Product",
            {"name": "P1"},
            {"id": "123"},
            "motor",
        )
        assert "MERGE" in cypher
        assert "Product" in cypher
        # PR1 v3: cypher 必含 :<Dataset> label
        assert ":`motor`" in cypher
        assert params["extra"]["name"] == "P1"

    def test_row_to_dict(self):
        row = TripleRow(
            from_label="A", from_key="k", from_value="v", rel_type="R", to_label="B", to_key="k2", to_value="v2"
        )
        d = KgClient._row_to_dict(row)
        assert d["from_value"] == "v"
        assert d["to_value"] == "v2"

    def test_batch_upsert_triples_empty(self):
        client = KgClient(store=MagicMock(), dataset="motor")
        result = client.batch_upsert_triples([])
        assert result.success == 0

    def test_merge_node(self):
        store = MagicMock()
        store.execute_and_fetch.return_value = [{"node_id": 42}]
        client = KgClient(store=store, dataset="motor")
        result = client.merge_node("Product", {"name": "P1"}, {"id": "123"})
        assert result == "42"

    def test_merge_node_returns_none(self):
        store = MagicMock()
        store.execute_and_fetch.return_value = []
        client = KgClient(store=store, dataset="motor")
        result = client.merge_node("Product", {"name": "P1"}, {"id": "123"})
        assert result is None

    def test_count_by_label(self):
        store = MagicMock()
        store.execute_and_fetch.return_value = [{"label": "Product", "cnt": 5}]
        client = KgClient(store=store, dataset="motor")
        result = client.count_by_label()
        assert result["Product"] == 5

    def test_counts(self):
        store = MagicMock()
        store.execute_and_fetch.side_effect = [
            [{"cnt": 10}],
            [{"cnt": 20}],
        ]
        client = KgClient(store=store, dataset="motor")
        result = client.counts()
        assert result["nodes"] == 10
        assert result["relations"] == 20

    def test_list_nodes(self):
        store = MagicMock()
        store.execute_and_fetch.return_value = [
            {"id": 1, "label": "Product", "props": {"name": "P1", "id": "e1"}},
        ]
        client = KgClient(store=store, dataset="motor")
        result = client.list_nodes()
        assert result[0]["business_id"] == "e1"
        assert result[0]["name"] == "P1"

    def test_list_relationships(self):
        store = MagicMock()
        store.execute_and_fetch.return_value = [
            {
                "src": 1,
                "src_label": "Product",
                "src_props": {"name": "P1"},
                "type": "HAS",
                "dst": 2,
                "dst_label": "Param",
                "dst_props": {"name": "W"},
                "props": {},
            },
        ]
        client = KgClient(store=store, dataset="motor")
        result = client.list_relationships()
        assert result[0]["type"] == "HAS"

    def test_build_unwind_cypher(self):
        rows = [
            TripleRow(
                from_label="A", from_key="k", from_value="v", rel_type="R", to_label="B", to_key="k2", to_value="v2"
            )
        ]
        client = KgClient(store=MagicMock(), dataset="motor")
        cypher, params = client._build_unwind_cypher(rows)
        assert "UNWIND" in cypher
        # PR1 v3: cypher 必含 :<Dataset> label
        assert ":`motor`" in cypher
        assert len(params["rows"]) == 1
