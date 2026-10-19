"""kg/schema.py 单元测试"""

import pytest

from src.kg.exceptions import SchemaError
from src.kg.schema import get_node, get_relations_from, load_schema


def test_load_schema_success(tmp_path):
    yml = tmp_path / "schema.yaml"
    yml.write_text("""
nodes:
  - name: Product
    fields: []
  - name: Series
    fields: []
relations:
  - name: belongs_to
    from: Product
    to: Series
""")
    result = load_schema(str(yml))
    assert len(result["nodes"]) == 2
    assert len(result["relations"]) == 1


def test_load_schema_missing_file():
    with pytest.raises(SchemaError, match="不存在"):
        load_schema("/nonexistent/path.yaml")


def test_load_schema_invalid_yaml(tmp_path):
    yml = tmp_path / "bad.yaml"
    yml.write_text("{{ broken: [")
    with pytest.raises(SchemaError):
        load_schema(str(yml))


def test_load_schema_ref_validation(tmp_path):
    yml = tmp_path / "schema.yaml"
    yml.write_text("""
nodes:
  - name: Product
    fields:
      - key: series
        type: ref
        ref_to: NonExistent
relations: []
""")
    with pytest.raises(SchemaError, match="ref_to=NonExistent"):
        load_schema(str(yml))


def test_load_schema_relation_validation(tmp_path):
    yml = tmp_path / "schema.yaml"
    yml.write_text("""
nodes:
  - name: Product
    fields: []
relations:
  - name: bad_rel
    from: Product
    to: NonExistent
""")
    with pytest.raises(SchemaError, match="NonExistent"):
        load_schema(str(yml))


def test_get_node_found():
    loaded = {"nodes": [{"name": "Product"}, {"name": "Series"}], "relations": []}
    node = get_node(loaded, "Product")
    assert node["name"] == "Product"


def test_get_node_not_found():
    loaded = {"nodes": [{"name": "Product"}], "relations": []}
    with pytest.raises(SchemaError, match="未找到"):
        get_node(loaded, "NonExistent")


def test_get_relations_from():
    loaded = {
        "nodes": [{"name": "Product"}],
        "relations": [
            {"name": "r1", "from": "Product", "to": "Series"},
            {"name": "r2", "from": "Series", "to": "Product"},
        ],
    }
    rels = get_relations_from(loaded, "Product")
    assert len(rels) == 1
    assert rels[0]["name"] == "r1"
