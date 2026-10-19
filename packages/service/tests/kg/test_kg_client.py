"""kg.client 红测试 (mock Neo4j driver)

- KgClient 是 Neo4jStore 的轻量封装, 加 UNWIND MERGE 批量 API
- batch_upsert_triples 接收 TripleRow 列表, 返回 BatchResult
- count_by_label 返回 {label: count}
- subgraph 返回节点 + 边
"""

from unittest.mock import MagicMock

import pytest

from src.kg.client import BatchResult, KgClient, TripleRow


@pytest.fixture
def mock_store():
    store = MagicMock()
    store.driver = MagicMock()
    return store


class TestMergeNode:
    def test_calls_neo4j_with_cypher(self, mock_store):
        kg = KgClient(store=mock_store)
        kg.merge_node("Product", {"model": "1LE0001", "name": "X"}, unique_keys={"model": "1LE0001"})
        mock_store.execute_and_fetch.assert_called_once()
        cypher, params = mock_store.execute_and_fetch.call_args[0][:2]
        assert "MERGE" in cypher.upper()
        assert params["model"] == "1LE0001"


class TestBatchUpsertTriples:
    def test_empty_list_returns_empty_result(self, mock_store):
        kg = KgClient(store=mock_store)
        result = kg.batch_upsert_triples([])
        assert isinstance(result, BatchResult)
        assert result.success == 0
        assert result.failed == 0

    def test_single_row_runs_unwind_cypher(self, mock_store):
        mock_store.execute_and_fetch.return_value = [{"ok": 1}]
        kg = KgClient(store=mock_store)
        rows = [
            TripleRow(
                from_label="Product",
                from_key="model",
                from_value="1LE0001",
                rel_type="BELONGS_TO",
                to_label="Series",
                to_key="name",
                to_value="1LE 系列",
                properties={},
            )
        ]
        result = kg.batch_upsert_triples(rows)
        assert result.success == 1
        cypher, params = mock_store.execute_and_fetch.call_args[0][:2]
        assert "UNWIND" in cypher.upper()
        assert "MERGE" in cypher.upper()
        assert params["rows"][0]["from_value"] == "1LE0001"

    def test_returns_failed_count_on_neo4j_error(self, mock_store):
        mock_store.execute_and_fetch.side_effect = RuntimeError("boom")
        kg = KgClient(store=mock_store)
        rows = [
            TripleRow(
                from_label="Product",
                from_key="model",
                from_value="X",
                rel_type="BELONGS_TO",
                to_label="Series",
                to_key="name",
                to_value="Y",
                properties={},
            )
        ]
        result = kg.batch_upsert_triples(rows)
        assert result.success == 0
        assert result.failed == 1
        assert "boom" in result.errors[0]

    def test_heterogeneous_rows_grouped_by_label_and_rel_type(self, mock_store):
        """根因回归 (2026-06-12): 老 _build_unwind_cypher 用 rows[0] 的
        from_label/to_label/rel_type 硬编码 Cypher (Cypher 限制: label/rel_type 不能
        参数化), UNWIND 时其他行的 label/rel_type 全被覆盖成第一行 → Neo4j 里
        所有节点都成一种 label, 所有关系都成一种 type. 修复: 按 5 元组
        (from_label, from_key, to_label, to_key, rel_type) 分组, 每组一次
        UNWIND, 这样组内同质能批量但组间独立."""
        mock_store.execute_and_fetch.return_value = [{"cnt": 1}]
        kg = KgClient(store=mock_store)
        rows = [
            # 组 A: 产品系列 包含系列 产品系列
            TripleRow(
                from_label="产品系列",
                from_key="name",
                from_value="1LE1001",
                rel_type="包含系列",
                to_label="产品系列",
                to_key="name",
                to_value="1LE1001-0BB32-2GA4",
                properties={},
            ),
            # 组 B: 产品型号 符合标准 认证标准
            TripleRow(
                from_label="产品型号",
                from_key="name",
                from_value="1LE1001-0BB32-2GA4",
                rel_type="符合标准",
                to_label="认证标准",
                to_key="name",
                to_value="CCC",
                properties={},
            ),
            # 组 C: 产品系列 符合标准 认证标准 (跟 B 同 rel_type 但 from_label 不同 → 必须独立组)
            TripleRow(
                from_label="产品系列",
                from_key="name",
                from_value="1LE1001",
                rel_type="符合标准",
                to_label="认证标准",
                to_key="name",
                to_value="CCC",
                properties={},
            ),
            # 组 D: 产品型号 具有参数 技术参数
            TripleRow(
                from_label="产品型号",
                from_key="name",
                from_value="1LE1001-0BB32-2GA4",
                rel_type="具有参数",
                to_label="技术参数",
                to_key="name",
                to_value="重量",
                properties={},
            ),
        ]
        result = kg.batch_upsert_triples(rows)
        # 4 行全成功
        assert result.success == 4
        assert result.failed == 0
        # 4 个独立组 → execute_and_fetch 被调 4 次 (而非 1 次, 后者是 bug 行为)
        assert mock_store.execute_and_fetch.call_count == 4
        # 每次 Cypher 必须含正确的 label/rel_type 字面量 (验证不是硬编码首行)
        cyphers = [call_args[0][0] for call_args in mock_store.execute_and_fetch.call_args_list]
        joined = "\n---\n".join(cyphers)
        assert "MERGE (a:产品系列" in joined  # 组 A + C 的起点
        assert "MERGE (a:产品型号" in joined  # 组 B + D 的起点
        assert "MERGE (b:产品系列" in joined  # 组 A 的终点
        assert "MERGE (b:认证标准" in joined  # 组 B + C 的终点
        assert "MERGE (b:技术参数" in joined  # 组 D 的终点
        assert "[r:包含系列]" in joined  # 组 A
        assert "[r:符合标准]" in joined  # 组 B + C
        assert "[r:具有参数]" in joined  # 组 D

    def test_heterogeneous_partial_failure_isolated_per_group(self, mock_store):
        """一组失败不影响其他组, errors 收集每组的失败信息"""
        # 第 1 次调用 OK, 第 2 次抛错
        mock_store.execute_and_fetch.side_effect = [
            [{"cnt": 1}],
            RuntimeError("group2 boom"),
        ]
        kg = KgClient(store=mock_store)
        rows = [
            TripleRow(
                from_label="A",
                from_key="name",
                from_value="x",
                rel_type="R1",
                to_label="B",
                to_key="name",
                to_value="y",
                properties={},
            ),
            TripleRow(
                from_label="A",
                from_key="name",
                from_value="m",
                rel_type="R2",
                to_label="B",
                to_key="name",
                to_value="n",
                properties={},
            ),
        ]
        result = kg.batch_upsert_triples(rows)
        assert result.success == 1
        assert result.failed == 1
        assert any("group2 boom" in e for e in result.errors)


class TestCountByLabel:
    def test_groups_by_label(self, mock_store):
        mock_store.execute_and_fetch.return_value = [
            {"label": "Product", "cnt": 12},
            {"label": "Series", "cnt": 3},
        ]
        kg = KgClient(store=mock_store)
        out = kg.count_by_label()
        assert out == {"Product": 12, "Series": 3}

    def test_empty_db_returns_empty_dict(self, mock_store):
        mock_store.execute_and_fetch.return_value = []
        kg = KgClient(store=mock_store)
        assert kg.count_by_label() == {}

    def test_uses_labels_function_not_label(self, mock_store):
        """bug fix: 老 cypher 用 label(n), 某些 Neo4j 实例 (driver/server 协议不匹配)
        报 Unknown function 'label'. 改用 labels(n)[0] 是 Cypher 标准等价写法
        兼容所有 4.x/5.x 版本."""
        mock_store.execute_and_fetch.return_value = []
        kg = KgClient(store=mock_store)
        kg.count_by_label()
        cypher = mock_store.execute_and_fetch.call_args[0][0]
        assert "labels(n)[0]" in cypher
        # 旧写法不能残留 (label(n) 是函数调用, labels(n) 是列表取值, 二选一)
        assert "label(n)" not in cypher

    def test_filters_unlabeled_nodes(self, mock_store):
        """无 label 的节点 (罕见) 不应污染字典 key, 加 size(labels(n)) > 0 过滤"""
        mock_store.execute_and_fetch.return_value = [
            {"label": "Product", "cnt": 12},
        ]
        kg = KgClient(store=mock_store)
        kg.count_by_label()
        cypher = mock_store.execute_and_fetch.call_args[0][0]
        assert "size(labels(n))" in cypher


class TestCounts:
    def test_returns_nodes_and_relations(self, mock_store):
        """counts() 返回总节点数 + 总关系数"""
        mock_store.execute_and_fetch.side_effect = [
            [{"cnt": 57}],
            [{"cnt": 81}],
        ]
        kg = KgClient(store=mock_store)
        out = kg.counts()
        assert out == {"nodes": 57, "relations": 81}

    def test_empty_db_returns_zeros(self, mock_store):
        mock_store.execute_and_fetch.return_value = []
        kg = KgClient(store=mock_store)
        out = kg.counts()
        assert out == {"nodes": 0, "relations": 0}


class TestListNodes:
    def test_returns_nodes_with_business_fields(self, mock_store):
        """业务标识优先: props.name 提到 name, props.id 提到 business_id"""
        mock_store.execute_and_fetch.return_value = [
            {"id": 0, "label": "产品系列", "props": {"id": "e1", "name": "W21"}},
            {"id": 1, "label": "技术参数", "props": {"id": "e2", "name": "机座号"}},
        ]
        kg = KgClient(store=mock_store)
        out = kg.list_nodes()
        assert len(out) == 2
        assert out[0] == {
            "id": "0",
            "business_id": "e1",
            "name": "W21",
            "label": "产品系列",
            "props": {"id": "e1", "name": "W21"},
        }
        assert out[1]["name"] == "机座号"
        assert out[1]["business_id"] == "e2"

    def test_passes_skip_and_limit(self, mock_store):
        mock_store.execute_and_fetch.return_value = []
        kg = KgClient(store=mock_store)
        kg.list_nodes(skip=10, limit=25)
        _cypher, params = mock_store.execute_and_fetch.call_args[0][:2]
        assert params["skip"] == 10
        assert params["limit"] == 25

    def test_filters_unlabeled_nodes(self, mock_store):
        mock_store.execute_and_fetch.return_value = []
        kg = KgClient(store=mock_store)
        kg.list_nodes()
        cypher = mock_store.execute_and_fetch.call_args[0][0]
        assert "size(labels(n))" in cypher

    def test_handles_missing_props_fields(self, mock_store):
        """无 name/id 的节点也能正常返回 (空字符串兜底)"""
        mock_store.execute_and_fetch.return_value = [
            {"id": 0, "label": "X", "props": None},
        ]
        kg = KgClient(store=mock_store)
        out = kg.list_nodes()
        assert out[0]["name"] == ""
        assert out[0]["business_id"] == ""

    def test_empty_db_returns_empty_list(self, mock_store):
        mock_store.execute_and_fetch.return_value = []
        kg = KgClient(store=mock_store)
        assert kg.list_nodes() == []


class TestListRelationships:
    def test_returns_relationships_with_endpoint_names(self, mock_store):
        """端点也带 props.name/business_id, 前端能显示'产品系列 W21 → 技术参数 机座号'"""
        mock_store.execute_and_fetch.return_value = [
            {
                "src": 0,
                "src_label": "产品系列",
                "src_props": {"id": "e1", "name": "W21"},
                "type": "具有参数",
                "dst": 1,
                "dst_label": "技术参数",
                "dst_props": {"id": "e2", "name": "机座号"},
                "props": {},
            },
        ]
        kg = KgClient(store=mock_store)
        out = kg.list_relationships()
        assert out[0]["type"] == "具有参数"
        assert out[0]["src_name"] == "W21"
        assert out[0]["src_business_id"] == "e1"
        assert out[0]["dst_name"] == "机座号"
        assert out[0]["dst_business_id"] == "e2"

    def test_passes_skip_and_limit(self, mock_store):
        mock_store.execute_and_fetch.return_value = []
        kg = KgClient(store=mock_store)
        kg.list_relationships(skip=5, limit=50)
        _, params = mock_store.execute_and_fetch.call_args[0][:2]
        assert params["skip"] == 5
        assert params["limit"] == 50

    def test_empty_db_returns_empty_list(self, mock_store):
        mock_store.execute_and_fetch.return_value = []
        kg = KgClient(store=mock_store)
        assert kg.list_relationships() == []


class TestSubgraph:
    def test_returns_nodes_and_edges(self, mock_store):
        # 第一次 execute_and_fetch 跑 MATCH 拿节点, 第二次跑 MATCH 拿边
        mock_store.execute_and_fetch.side_effect = [
            [{"id": "1", "label": "Product", "props": {"model": "1LE0001"}}],
            [{"src": "1", "dst": "2", "type": "BELONGS_TO", "props": {}}],
        ]
        kg = KgClient(store=mock_store)
        out = kg.subgraph(["1"], depth=1)
        assert out["nodes"][0]["id"] == "1"
        assert out["edges"][0]["type"] == "BELONGS_TO"
