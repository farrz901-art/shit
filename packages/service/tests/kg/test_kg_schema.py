"""kg.schema 测试 (适配 motor domain 2026-06-12)

- load_schema() 从 configs/triples/motor/motor-schema.yaml 读
- 校验节点/关系引用完整性 (ref 字段必须指向已定义节点)
- 暴露 nodes/relations 给前端 API 用
"""

from pathlib import Path

import pytest

from src.kg import schema
from src.kg.exceptions import SchemaError

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCHEMA_PATH = REPO_ROOT / "configs" / "triples" / "motor" / "motor-schema.yaml"


class TestLoadSchema:
    def test_load_returns_nodes_and_relations(self):
        loaded = schema.load_schema(str(SCHEMA_PATH))
        assert "nodes" in loaded
        assert "relations" in loaded
        # 7 类电机节点: 产品系列/产品型号/技术参数/参数值/部件/工况条件/认证标准
        assert len(loaded["nodes"]) == 7
        # 9 个关系
        assert len(loaded["relations"]) == 9

    def test_loads_model_node_with_fields(self):
        loaded = schema.load_schema(str(SCHEMA_PATH))
        # 产品型号节点 (最类似旧 Product 的角色)
        model = next(n for n in loaded["nodes"] if n["name"] == "产品型号")
        field_keys = {f["key"] for f in model["fields"]}
        assert {"name", "description"} <= field_keys

    def test_relations_reference_known_nodes(self):
        loaded = schema.load_schema(str(SCHEMA_PATH))
        node_names = {n["name"] for n in loaded["nodes"]}
        for rel in loaded["relations"]:
            assert rel["from"] in node_names, f"未知 from 节点: {rel['from']}"
            assert rel["to"] in node_names, f"未知 to 节点: {rel['to']}"


class TestRefIntegrity:
    def test_ref_to_unknown_node_raises(self, tmp_path):
        """ref_to 指向不存在的节点 → 加载报错"""
        bad = tmp_path / "bad.yaml"
        bad.write_text(
            "nodes:\n  - name: A\n    fields:\n      - { key: b, type: ref, ref_to: MissingNode }\nrelations: []\n",
            encoding="utf-8",
        )
        with pytest.raises(SchemaError, match="MissingNode"):
            schema.load_schema(str(bad))

    def test_relation_unknown_label_raises(self, tmp_path):
        """关系 from/to 引用未知节点 → 加载报错"""
        bad = tmp_path / "bad.yaml"
        bad.write_text(
            "nodes:\n"
            "  - name: A\n"
            "    fields: []\n"
            "relations:\n"
            "  - { name: REL, from: A, to: Ghost, cardinality: many_to_one }\n",
            encoding="utf-8",
        )
        with pytest.raises(SchemaError, match="Ghost"):
            schema.load_schema(str(bad))


class TestLookupHelpers:
    def test_get_node_by_name(self):
        loaded = schema.load_schema(str(SCHEMA_PATH))
        node = schema.get_node(loaded, "产品型号")
        assert node["name"] == "产品型号"

    def test_get_node_missing_raises(self):
        loaded = schema.load_schema(str(SCHEMA_PATH))
        with pytest.raises(SchemaError, match="NotFound"):
            schema.get_node(loaded, "NotFound")

    def test_get_relations_from_model(self):
        """从 产品型号 出发的关系应包含 属于系列/具有参数/适用工况 等"""
        loaded = schema.load_schema(str(SCHEMA_PATH))
        rels = schema.get_relations_from(loaded, "产品型号")
        rel_names = {r["name"] for r in rels}
        # 产品型号 出发: 属于系列/具有参数/具有参数值/适用工况/符合标准
        assert {"属于系列", "具有参数", "适用工况"} <= rel_names
