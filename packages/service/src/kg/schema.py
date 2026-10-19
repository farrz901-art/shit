"""yaml schema 加载 + 引用完整性校验

configs/knowledge-schema.yaml 是知识图谱节点/关系定义的唯一来源。
加节点/关系改 yaml, 不改代码; 本模块负责加载并校验:
- 节点 field 引用 (type=ref ref_to=NodeName) 必须指向已定义节点
- 关系 from/to 必须指向已定义节点
"""

from __future__ import annotations

from pathlib import Path

import yaml

from .exceptions import SchemaError


def load_schema(path: str) -> dict:
    """加载并校验 yaml schema

    Returns:
        dict with keys "nodes" (list) and "relations" (list)
    Raises:
        SchemaError: 加载失败或引用不完整
    """
    p = Path(path)
    if not p.exists():
        raise SchemaError(f"schema 文件不存在: {path}")

    with p.open("r", encoding="utf-8") as f:
        try:
            data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            # (2026-06-23) PyYAML 6.x 抛 yaml.parser.ParserError / YAMLError;
            # 业务期望统一抛 SchemaError 方便上层 try/except.
            raise SchemaError(f"schema yaml 解析失败: {e}") from e

    if not isinstance(data, dict):
        raise SchemaError(f"schema 顶层必须是 dict, 实际: {type(data).__name__}")

    nodes = data.get("nodes") or []
    relations = data.get("relations") or []
    if not isinstance(nodes, list) or not isinstance(relations, list):
        raise SchemaError("schema.nodes / schema.relations 必须是 list")

    node_names = {n["name"] for n in nodes if "name" in n}

    # 校验节点 ref 字段
    for n in nodes:
        for fld in n.get("fields", []):
            if fld.get("type") == "ref":
                ref_to = fld.get("ref_to")
                if ref_to not in node_names:
                    raise SchemaError(f"节点 {n['name']}.{fld.get('key')} 的 ref_to={ref_to} 未定义")

    # 校验关系 from/to
    for r in relations:
        for k in ("from", "to"):
            if r.get(k) not in node_names:
                raise SchemaError(f"关系 {r.get('name')} 的 {k}={r.get(k)} 未定义")

    return {"nodes": nodes, "relations": relations}


def get_node(loaded: dict, name: str) -> dict:
    """按 name 查节点; 找不到抛 SchemaError"""
    for n in loaded["nodes"]:
        if n.get("name") == name:
            return n
    raise SchemaError(f"节点未找到: {name}")


def get_relations_from(loaded: dict, label: str) -> list[dict]:
    """查所有 from=label 的关系 (按 from 类型限定合法关系)"""
    return [r for r in loaded["relations"] if r.get("from") == label]
