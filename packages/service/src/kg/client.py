"""Neo4j 知识图谱客户端 (UNWIND MERGE 批量写入, 2026-07-01 v3 dataset label 隔离)

2026-07-01 update (markdown extract KG spec PR1, v3):
- KgClient.__init__ 加 dataset: str 参数, 所有方法透传给 cypher
- _build_unwind_cypher 在 MERGE (a:Product ...) 节点加 :<Dataset> label
- merge_node 同上
- list_nodes / list_relationships 加 WHERE n:<Dataset> 防跨 dataset 泄露
- 5 元组分组不变 (label/rel_type 仍字面量)

v3 设计 (2026-07-01):
- 项目用 Neo4j Community Edition (1 database only), 用 dataset label 隔离不同数据集
- env KG_ALLOWED_DATASETS=motor,plc,sensor 单源白名单 (在 src/kg/datasets.py)
- 业务侧严禁任意字符串当 dataset label, 走 validate_dataset() 校验

历史上下文 (2026-06-12 bug):
MERGE 的 label 和 rel_type 不能参数化, 只能字面量.
所以必须按 (from_label, from_key, to_label, to_key, rel_type) 5 元组
分组, 每组生成一条独立 Cypher. 不分组的话所有行的 label/rel_type
都会被首行覆盖.
"""

from __future__ import annotations

from dataclasses import field

from pydantic.dataclasses import dataclass as pydantic_dataclass

from .datasets import validate_dataset
from .neo4j import Neo4jStore


@pydantic_dataclass
class TripleRow:
    """单条三元组 (起点 + 关系 + 终点 + 属性)"""

    from_label: str
    from_key: str
    from_value: str
    rel_type: str
    to_label: str
    to_key: str
    to_value: str
    properties: dict = field(default_factory=dict)


@pydantic_dataclass
class BatchResult:
    success: int = 0
    failed: int = 0
    errors: list[str] = field(default_factory=list)


class KgClient:
    """知识图谱客户端, 包装 Neo4jStore, 加 dataset label 隔离 (2026-07-01 v3)

    Args:
        store: Neo4jStore 实例 (测试时可传 MagicMock)
        dataset: Neo4j dataset label (如 "motor" / "plc" / "sensor"),
                 必须在 ALLOWED_DATASETS 白名单内 (env KG_ALLOWED_DATASETS)
    """

    def __init__(
        self,
        store: Neo4jStore | None = None,
        dataset: str = "motor",  # 默认值仅为兼容, 业务侧必传
    ):
        validate_dataset(dataset)  # 强校验: 白名单 + 合法 identifier
        self._store = store or Neo4jStore()
        self._dataset = dataset

    @property
    def dataset(self) -> str:
        """dataset label (只读)"""
        return self._dataset

    def merge_node(self, label: str, properties: dict, unique_keys: dict, dataset: str | None = None) -> str | None:
        """MERGE 一个节点, unique_keys 指定匹配键 + dataset label 隔离

        Args:
            label: 业务 label (e.g. "Product" / "Spec")
            properties: 节点属性
            unique_keys: 匹配键 (e.g. {"model": "1LE0001"})
            dataset: dataset 标签 (None = 用 self._dataset)
        """
        ds = dataset or self._dataset
        validate_dataset(ds)
        cypher, params = self._build_merge_node_cypher(label, properties, unique_keys, ds)
        results = self._store.execute_and_fetch(cypher, params)
        return str(results[0]["node_id"]) if results else None

    def _build_merge_node_cypher(
        self, label: str, properties: dict, unique_keys: dict, dataset: str
    ) -> tuple[str, dict]:
        merge_props = ", ".join(f"`{k}`: ${k}" for k in unique_keys)
        # v3: MERGE 加 dataset label, 防止跨 dataset 同 model 误合并
        cypher = f"MERGE (n:{label}:`{dataset}` {{{merge_props}}}) SET n += $extra RETURN id(n) AS node_id"
        params = {**unique_keys, "extra": properties}
        return cypher, params

    def batch_upsert_triples(self, rows: list[TripleRow]) -> BatchResult:
        """批量 UNWIND MERGE 三元组 (按 5 元组分组, 写 self._dataset)

        v3: 节点都加 :<Dataset> label, 防跨 dataset 误合并
        """
        if not rows:
            return BatchResult()

        groups: dict[tuple[str, str, str, str, str], list[TripleRow]] = {}
        for r in rows:
            key = (r.from_label, r.from_key, r.to_label, r.to_key, r.rel_type)
            groups.setdefault(key, []).append(r)

        success = 0
        failed = 0
        errors: list[str] = []
        for group_rows in groups.values():
            cypher, params = self._build_unwind_cypher(group_rows)
            try:
                self._store.execute_and_fetch(cypher, params)
                success += len(group_rows)
            except Exception as e:  # noqa: BLE001
                failed += len(group_rows)
                errors.append(str(e))
        return BatchResult(success=success, failed=failed, errors=errors)

    def _build_unwind_cypher(self, rows: list[TripleRow]) -> tuple[str, dict]:
        """生成 UNWIND MERGE cypher (2026-07-01 v3: 加 dataset label)

        Cypher 模板设计原则:
        - 节点用 `:Product:<Dataset>` 字面量 (label 不能参数化)
        - 5 元组仍按 label/key/rel_type 分组, dataset 在每组 cypher 字面量展开
        """
        first = rows[0]
        ds = self._dataset
        cypher = f"""
        UNWIND $rows AS row
        MERGE (a:{first.from_label}:`{ds}` {{`{first.from_key}`: row.from_value}})
        MERGE (b:{first.to_label}:`{ds}` {{`{first.to_key}`: row.to_value}})
        MERGE (a)-[r:{first.rel_type}]->(b)
        SET r += row.properties
        RETURN count(r) AS cnt
        """.strip()
        params = {"rows": [self._row_to_dict(r) for r in rows]}
        return cypher, params

    @staticmethod
    def _row_to_dict(r: TripleRow) -> dict:
        return {
            "from_value": r.from_value,
            "to_value": r.to_value,
            "properties": r.properties,
        }

    def count_by_label(self) -> dict[str, int]:
        """按 label 统计节点数 (全 dataset, 不隔离, 供 /stats 大盘用)"""
        cypher = "MATCH (n) WHERE size(labels(n)) > 0 RETURN labels(n)[0] AS label, count(n) AS cnt"
        results = self._store.execute_and_fetch(cypher)
        return {r["label"]: r["cnt"] for r in results}

    def counts(self) -> dict[str, int]:
        """返回 neo4j 总节点数 + 总关系数 (供 stats 大盘用, 全 dataset)"""
        node_cypher = "MATCH (n) RETURN count(n) AS cnt"
        rel_cypher = "MATCH ()-[r]->() RETURN count(r) AS cnt"
        nodes = self._store.execute_and_fetch(node_cypher)
        rels = self._store.execute_and_fetch(rel_cypher)
        return {
            "nodes": nodes[0]["cnt"] if nodes else 0,
            "relations": rels[0]["cnt"] if rels else 0,
        }

    def list_nodes(self, skip: int = 0, limit: int = 100) -> list[dict]:
        """列本 dataset 节点 (按 self._dataset label 过滤, 防跨 dataset 泄露)

        v3: 必加 WHERE n:`<Dataset>`, 不能忘, 否则泄露其他 dataset
        """
        cypher = (
            f"MATCH (n) WHERE n:`{self._dataset}` AND size(labels(n)) > 0 "
            "RETURN id(n) AS id, labels(n)[0] AS label, properties(n) AS props "
            "SKIP $skip LIMIT $limit"
        )
        results = self._store.execute_and_fetch(cypher, {"skip": skip, "limit": limit})
        out: list[dict] = []
        for r in results:
            props = r["props"] or {}
            out.append(
                {
                    "id": str(r["id"]),
                    "business_id": str(props.get("id", "")),
                    "name": str(props.get("name", "")),
                    "label": r["label"],
                    "props": props,
                }
            )
        return out

    def list_relationships(self, skip: int = 0, limit: int = 100) -> list[dict]:
        """列本 dataset 关系 (按 endpoint label 包含 self._dataset 过滤)

        v3: 两个 endpoint 都必须带 :<Dataset> label
        """
        cypher = (
            f"MATCH (a:`{self._dataset}`)-[r]->(b:`{self._dataset}`) "
            "RETURN id(a) AS src, labels(a)[0] AS src_label, properties(a) AS src_props, "
            "type(r) AS type, id(b) AS dst, labels(b)[0] AS dst_label, properties(b) AS dst_props, "
            "properties(r) AS props "
            "SKIP $skip LIMIT $limit"
        )
        results = self._store.execute_and_fetch(cypher, {"skip": skip, "limit": limit})
        out: list[dict] = []
        for r in results:
            src_props = r["src_props"] or {}
            dst_props = r["dst_props"] or {}
            out.append(
                {
                    "src": str(r["src"]),
                    "src_label": r["src_label"],
                    "src_name": str(src_props.get("name", "")),
                    "src_business_id": str(src_props.get("id", "")),
                    "type": r["type"],
                    "dst": str(r["dst"]),
                    "dst_label": r["dst_label"],
                    "dst_name": str(dst_props.get("name", "")),
                    "dst_business_id": str(dst_props.get("id", "")),
                    "props": r["props"] or {},
                }
            )
        return out

    def subgraph(self, node_ids: list[str], depth: int = 1) -> dict:
        """取节点 ID 的 depth 跳邻居子图 (按 self._dataset 隔离)

        v3: 所有 MATCH 都加 :<Dataset> label, 防止子图泄漏
        """
        ds = self._dataset
        nodes_cypher = (
            f"MATCH (n:`{ds}`) WHERE id(n) IN $ids "
            f"OPTIONAL MATCH (n)-[*1..{depth}]-(m:`{ds}`) "
            "RETURN DISTINCT id(m) AS id, labels(m)[0] AS label, properties(m) AS props"
        )
        nodes = self._store.execute_and_fetch(nodes_cypher, {"ids": [int(i) for i in node_ids]})
        edges_cypher = (
            f"MATCH (a:`{ds}`)-[r]->(b:`{ds}`) "
            "WHERE id(a) IN $ids AND id(b) IN $ids "
            "RETURN id(a) AS src, id(b) AS dst, type(r) AS type, properties(r) AS props"
        )
        edges = self._store.execute_and_fetch(edges_cypher, {"ids": [int(i) for i in node_ids]})
        return {
            "nodes": [{"id": str(n["id"]), "label": n["label"], "props": n["props"]} for n in nodes],
            "edges": [
                {"src": str(e["src"]), "dst": str(e["dst"]), "type": e["type"], "props": e["props"]} for e in edges
            ],
        }
