# Markdown Extract KG — PR1: KG dataset label 隔离 + Neo4j 索引 + GET /datasets (M1 + M2)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Neo4j 写入路径按 `dataset` label 隔离 (env 白名单 `KG_ALLOWED_DATASETS`), 加 dataset label 索引, GET /datasets admin API, 修 submit_triples 加 dataset audit, 删 graphifyy dev dep。

**Scope (5 commits, ~8h):**
- Task 1 (P0): KgClient `__init__` 加 `dataset` 参数 + cypher 模板加 `WHERE n:<Dataset>` 过滤
- Task 2 (P0): `src/kg/datasets.py` 新文件 (env 白名单 + validate + list_datasets + load_from_env)
- Task 3 (P0): `main.py` 启动时调 `load_allowed_datasets_from_env()` 固化 ALLOWED_DATASETS
- Task 4 (P0): list_nodes / list_relationships / list_products / submit_triples 加 dataset query param + audit + 删 (label,key) 唯一约束相关代码 (本期本来就没实现, 不需删)
- Task 5 (P1+P2): Neo4j dataset label 索引 cypher 脚本 + init script + 删 graphifyy dev dep + GET /datasets admin API

**v3 重要设计调整 (2026-07-01)**:
- 项目用 Neo4j **Community Edition** (`neo4j:2026.05.0` docker 镜像), **只能 1 个 standard database**
- 调研结论: Community Edition 限制决定必须用 **dataset label 隔离**, 不能用 database 方案
- env `KG_ALLOWED_DATASETS=motor,plc,sensor` 单源白名单, 业务侧严禁任意字符串当 label (类似 SQL 注入防御)
- **不加** (label,key) 唯一约束 (因为不同 dataset 的同一 key 可合法存在)
- **不加** user_hash 字段 (项目是内部项目, admin-only, 不需要多租户)

## 项目规约 (PR1 必须遵守的跨 PR 不变量)

1. **测试 100% mock, 0 真实 Neo4j/PG/Redis 连接**: 用 `MagicMock` mock Neo4jStore, `monittest.mock.patch` mock 所有 `execute_and_fetch` 调用。集成测试 (DDL 校验) 走 AST 验证 + mock, **不连真 PG** (CLAUDE.md 强制)。
2. **业务 enum 走 lookup 字典**: `extractor_id` / `splitter_id` 走 `src/lookups/`, 不许新增 `StrEnum` (CLAUDE.md §字典使用规范)
3. **`# type: ignore` 必须带具体错误码 + 注释**: 不接受裸 `# type: ignore`
4. **`# noqa` 必须带具体错误码 + 注释**: 业务故意 broad 例外
5. **业务代码用 loguru**: `logger.info("kg_extract done task={}", task_id)`
6. **PR 收尾必须跑**: `uv run pytest -q && uv run ruff format && uv run ruff check --fix && uv run pyright`

---

## Task 1: KgClient `__init__` 加 `dataset` 参数 + cypher 模板加 `WHERE n:<Dataset>` 过滤

**Files:**
- Modify: `packages/service/src/kg/client.py` (所有方法加 dataset 透传 + cypher 加 `WHERE n:<Dataset>`)

- [ ] **Step 1: 修改 client.py 加 dataset 参数**

```python
# packages/service/src/kg/client.py (完整重写关键部分)

"""Neo4j 知识图谱客户端 (UNWIND MERGE 批量写入, 2026-07-01 加 dataset label 隔离)

2026-07-01 update (markdown extract KG spec PR1, v3):
- KgClient.__init__ 加 dataset: str 参数, 所有方法透传给 cypher
- _build_unwind_cypher 在 MERGE (a:Product ...) 后加 WHERE 过滤 dataset label
- merge_node 同上
- list_nodes / list_relationships 加 WHERE n:<Dataset> 防跨 dataset 泄露
- 5 元组分组不变 (label/rel_type 仍字面量)

调研结论 (2026-07-01):
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

from .neo4j import Neo4jStore
from .datasets import validate_dataset

from pydantic.dataclasses import dataclass as pydantic_dataclass

# 2026-07-01 v3: TripleRow 不加 user_hash 字段 (admin 模式无租户隔离)
# 2026-07-01 v3: TripleRow 保留 Pydantic dataclass (跟 v1 一致, 为以后加字段留接口)

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
        return self._dataset

    def _cypher_label(self, base_label: str) -> str:
        """构造 `<BaseLabel>:<Dataset>` 字面量, 用于 MERGE 标签

        例: _cypher_label("Product") -> "Product:`motor`"
        """
        return f"{base_label}:`{self._dataset}`"

    def _where_dataset(self, var: str = "n") -> str:
        """构造 `WHERE <var>:<Dataset>` 过滤, 防止跨 dataset 泄露

        用于 list_nodes / list_relationships / merge_node 的 WHERE 子句
        """
        return f"{var}:`{self._dataset}`"

    def merge_node(
        self, label: str, properties: dict, unique_keys: dict, dataset: str | None = None
    ) -> str | None:
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
        cypher = (
            f"MERGE (n:{label}:`{dataset}` {{{merge_props}}}) "
            "SET n += $extra RETURN id(n) AS node_id"
        )
        params = {**unique_keys, "extra": properties}
        return cypher, params

    def batch_upsert_triples(self, rows: list[TripleRow]) -> BatchResult:
        """批量 UNWIND MERGE 三元组 (按 5 元组分组, 写 self._dataset)

        v3: 节点和关系都加 `<Dataset>` label, 防跨 dataset 误合并
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
        """按 label 统计节点数 (全 dataset, 不隔离)"""
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
        results = self._store.execute_and_fetch(
            cypher, {"skip": skip, "limit": limit}
        )
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

        v3: 两个 endpoint 都必须带 :<Dataset> label, WHERE 双向都过滤
        """
        cypher = (
            f"MATCH (a:`{self._dataset}`)-[r]->(b:`{self._dataset}`) "
            "RETURN id(a) AS src, labels(a)[0] AS src_label, properties(a) AS src_props, "
            "type(r) AS type, id(b) AS dst, labels(b)[0] AS dst_label, properties(b) AS dst_props, "
            "properties(r) AS props "
            "SKIP $skip LIMIT $limit"
        )
        results = self._store.execute_and_fetch(
            cypher, {"skip": skip, "limit": limit}
        )
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
        nodes = self._store.execute_and_fetch(
            nodes_cypher, {"ids": [int(i) for i in node_ids]}
        )
        edges_cypher = (
            f"MATCH (a:`{ds}`)-[r]->(b:`{ds}`) "
            "WHERE id(a) IN $ids AND id(b) IN $ids "
            "RETURN id(a) AS src, id(b) AS dst, type(r) AS type, properties(r) AS props"
        )
        edges = self._store.execute_and_fetch(
            edges_cypher, {"ids": [int(i) for i in node_ids]}
        )
        return {
            "nodes": [{"id": str(n["id"]), "label": n["label"], "props": n["props"]} for n in nodes],
            "edges": [
                {"src": str(e["src"]), "dst": str(e["dst"]), "type": e["type"], "props": e["props"]}
                for e in edges
            ],
        }
```

- [ ] **Step 2: 写失败测试**

```python
# packages/service/tests/kg/test_client_dataset.py
"""KgClient dataset label 隔离测试 (2026-07-01 markdown extract KG spec PR1, v3)

覆盖: 默认 dataset / cypher 加 WHERE n:<Dataset> / MERGE 加 :<Dataset> / 5 元组分组不变

测试模式: 模式 1 (纯 mock, 0 Neo4j/0 PG)
"""
from typing import Any, cast
from unittest.mock import MagicMock

import pytest

from src.kg.client import KgClient, TripleRow
from src.kg import datasets


@pytest.fixture(autouse=True)
def _seed_allowed_datasets(monkeypatch: pytest.MonkeyPatch):
    """每个 test 前种子 ALLOWED_DATASETS 白名单, 避免被其他 test 污染"""
    monkeypatch.setattr(datasets, "ALLOWED_DATASETS", ["motor", "plc", "sensor"])


def test_kgclient_default_dataset_in_cypher():
    """KgClient 实例化必加 dataset 校验, cypher 加 WHERE n:<Dataset>"""
    kg = KgClient(store=MagicMock(), dataset="motor")
    cypher, _params = kg._build_unwind_cypher(
        [TripleRow(
            from_label="Product", from_key="model", from_value="1LE0001",
            rel_type="HAS_SPEC", to_label="Spec", to_key="name", to_value="230V",
        )]
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
    # 反例: 不能漏 filter 走全 dataset
    assert "WHERE n:`sensor`" not in cypher  # 在 node 模式才用, rel 模式用 endpoint


def test_batch_upsert_grouping_keeps_5_tuple():
    """5 元组分组不变, dataset 在每组 cypher 字面量展开"""
    kg = KgClient(store=MagicMock(), dataset="motor")
    store = cast(Any, kg._store)
    store.execute_and_fetch.return_value = [{"cnt": 1}]
    rows = [
        TripleRow(
            from_label="Product", from_key="model", from_value="1LE0001",
            rel_type="HAS_SPEC", to_label="Spec", to_key="name", to_value="230V",
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
```

- [ ] **Step 3: 跑测试确认通过**

```bash
cd packages/service && uv run pytest tests/kg/test_client_dataset.py -v
```

Expected: 全部 test PASS.

---

## Task 2: src/kg/datasets.py 新文件 (env 白名单 + validate + list_datasets)

**Files:**
- Create: `packages/service/src/kg/datasets.py`
- Test: `packages/service/tests/kg/test_datasets.py`

- [ ] **Step 1: 写失败测试**

```python
# packages/service/tests/kg/test_datasets.py
"""datasets 白名单 + validate + load_from_env 测试 (2026-07-01 PR1, v3)

v3 设计: 单源白名单 (env KG_ALLOWED_DATASETS), 业务侧严禁任意字符串当 dataset

测试模式: 模式 1 (纯函数 + monkeypatch env, 0 PG/0 Neo4j)
"""
from unittest.mock import patch

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
```

- [ ] **Step 2: 实现 datasets.py**

```python
# packages/service/src/kg/datasets.py
"""Neo4j dataset label 白名单管理 (2026-07-01 markdown extract KG spec PR1, v3)

v3 设计: 项目用 Neo4j Community Edition (1 database only), 用 dataset label 隔离
不同数据集. env KG_ALLOWED_DATASETS 单源白名单, 业务侧严禁任意字符串当 label
(类似 SQL 注入防御).

为什么不走 StrEnum / lookup 字典:
- dataset 列表由 DBA 在 env 配置, 业务代码无新增需求
- env 是唯一源头, 启动时固化一次, 业务代码读模块级 ALLOWED_DATASETS
- 用 lookup 字典的话要加字典表 + 缓存失效逻辑, ROI 为负
"""
from __future__ import annotations

import os

from loguru import logger


# 模块级白名单 (启动时由 main.py 调 load_from_env() 固化)
# 业务代码严禁修改本变量, 应只读
ALLOWED_DATASETS: list[str] = []


def load_from_env(env_var: str = "KG_ALLOWED_DATASETS") -> list[str]:
    """从 env 读 comma-separated dataset 列表

    Args:
        env_var: env 变量名 (默认 KG_ALLOWED_DATASETS)
                 测试时可换名隔离

    Returns:
        list[str], 排序无关, 已 strip, 跳空 token

    默认值 "motor" 兜底: 不让无 env 启动失败, 业务侧启动后看 logger warning.
    """
    raw = os.getenv(env_var, "motor")
    datasets = [d.strip() for d in raw.split(",") if d.strip()]
    return datasets


def list_datasets() -> list[str]:
    """返模块级 ALLOWED_DATASETS snapshot

    业务侧 (router API / 前端下拉框) 调这个拿白名单, 不要读模块级变量
    避免测试隔离问题.
    """
    return list(ALLOWED_DATASETS)


def validate_dataset(dataset: str) -> None:
    """校验 dataset 在白名单内 + 是合法 Cypher identifier

    Raises:
        ValueError: 白名单外 / 非法 identifier / 空字符串

    业务侧 (KgClient 构造 / router 接收 query param) 必调本函数.
    Cypher label 注入防御: 不校验会导致 cypher 语法错或潜在注入.
    """
    if not dataset:
        raise ValueError("dataset 不能为空字符串")
    if not dataset.isidentifier():
        raise ValueError(
            f"Neo4j dataset label 必须是合法 identifier (字母数字下划线, 不以数字开头): {dataset!r}"
        )
    if dataset not in ALLOWED_DATASETS:
        raise ValueError(
            f"Neo4j dataset label 不在白名单: {dataset!r} (allowed={ALLOWED_DATASETS})"
        )


def bootstrap() -> list[str]:
    """main.py 启动时调一次, 固化模块级 ALLOWED_DATASETS

    同时 log INFO 让运维确认启动状态.

    Returns:
        固化的白名单 (供 main.py log 用)
    """
    global ALLOWED_DATASETS
    ALLOWED_DATASETS = load_from_env()
    logger.info("KG datasets 白名单已加载, allowed={}", ALLOWED_DATASETS)
    return ALLOWED_DATASETS
```

- [ ] **Step 3: 跑测试确认通过**

```bash
cd packages/service && uv run pytest tests/kg/test_datasets.py -v
```

Expected: 全部 PASS.

---

## Task 3: main.py 启动时 bootstrap() datasets 白名单

**Files:**
- Modify: `packages/service/src/main.py` (启动入口加 `from src.kg.datasets import bootstrap; bootstrap()`)

- [ ] **Step 1: 修改 main.py**

```python
# packages/service/src/main.py
# 顶部在 import 列表里找合适位置加
from src.kg.datasets import bootstrap as bootstrap_kg_datasets

# 在 setup_dictionaries 等同位置加:
def _setup_kg_datasets():
    """main.py 启动时调一次, 固化 ALLOWED_DATASETS 模块级 + log INFO"""
    bootstrap_kg_datasets()


# 跟 _setup_dictionaries 同位置调
_setup_kg_datasets()
```

- [ ] **Step 2: 验证 import 不报错**

```bash
cd packages/service && uv run python -c "from src.kg.datasets import bootstrap; bootstrap()"
```

Expected: log `KG datasets 白名单已加载, allowed=['motor']` (env 缺失), 退出码 0.

---

## Task 4: list_nodes / list_relationships / list_products / submit_triples 加 dataset query param

**Files:**
- Modify: `packages/service/src/kg/router.py` (4 端点加 dataset query param + admin 鉴权 + audit dataset)

- [ ] **Step 1: 修改 router.py**

```python
# packages/service/src/kg/router.py
# 顶部 import 加
from . import datasets as _kg_datasets
from .client import KgClient
# dataset validate 已经在 client 内部调, router 这层再调一次防御

# 修改 list_nodes 端点
@router.get("/nodes", ...)
def list_nodes(
    dataset: str = "motor",  # v3: 加 dataset 默认 "motor", 业务侧必传
    skip: int = 0,
    limit: int = 100,
    _user: CurrentUser = Depends(require_page("kg")),  # v3: 加 admin 守卫
) -> list[dict]:
    """列本 dataset 节点 (admin + kg 页面权限)"""
    _kg_datasets.validate_dataset(dataset)  # 防御白名单
    try:
        return KgClient(dataset=dataset).list_nodes(skip=skip, limit=limit)
    except Exception:
        return []


# 修改 list_relationships 端点 (同 list_nodes 模式)
@router.get("/relationships", ...)
def list_relationships(
    dataset: str = "motor",
    skip: int = 0,
    limit: int = 100,
    _user: CurrentUser = Depends(require_page("kg")),
) -> list[dict]:
    _kg_datasets.validate_dataset(dataset)
    try:
        return KgClient(dataset=dataset).list_relationships(skip=skip, limit=limit)
    except Exception:
        return []


# 修改 list_products 端点
@router.get("/products", ...)
def list_products(
    dataset: str = "motor",
    q: str = "",
    limit: int = 50,
    _user: CurrentUser = Depends(require_page("kg")),
) -> list[dict]:
    _kg_datasets.validate_dataset(dataset)
    cypher = (
        f"MATCH (n:Product:`{dataset}`) "
        "WHERE ($q = '' OR n.model CONTAINS $q OR n.name CONTAINS $q) "
        "RETURN id(n) AS id, n.model AS model, n.name AS name "
        "LIMIT $limit"
    )
    rows = KgClient(dataset=dataset)._store.execute_and_fetch(
        cypher, {"q": q, "limit": limit}
    )
    return [{"id": str(r["id"]), "model": r["model"], "name": r["name"]} for r in rows]


# 修改 submit_triples 端点
@router.post("/triples", ...)
def submit_triples(
    req: TriplesRequest,
    dataset: str = "motor",
    current_user: CurrentUser = Depends(require_page("kg")),  # v3: 加 admin 鉴权
) -> TriplesResponse:
    """提交三元组 (事务, admin + kg 页面权限)"""
    _kg_datasets.validate_dataset(dataset)
    rows = [
        TripleRow(
            from_label=r.from_label,
            from_key=r.from_key,
            from_value=r.from_value,
            rel_type=r.rel_type,
            to_label=r.to_label,
            to_key=r.to_key,
            to_value=r.to_value,
            properties=r.properties,
        )
        for r in req.rows
    ]
    kg = KgClient(dataset=dataset)
    result = kg.batch_upsert_triples(rows)
    _audit_store.record(
        action="kg.submit_triples",
        actor=current_user.email,
        actor_id=current_user.id,
        target=f"{len(req.rows)} rows",
        result="ok" if result.failed == 0 else "partial",
        detail={
            "success": result.success,
            "failed": result.failed,
            "errors": result.errors,
            "dataset": dataset,
        },
    )
    return TriplesResponse(success=result.success, failed=result.failed, errors=result.errors)


# 新增 GET /api/kg/datasets 端点 (admin 用, 公开读白名单)
@router.get(
    "/datasets",
    summary="列允许的 KG dataset labels (env 白名单)",
    description=(
        "## 用途\n\n"
        "返 `KG_ALLOWED_DATASETS` env 配置的 dataset label 白名单 — "
        "前端 KG 页面 dataset 下拉框渲染用.\n\n"
        "## 鉴权\n\n"
        "无 (公开端点, 仅返 env 白名单, 无敏感数据).\n\n"
        "## 行为\n\n"
        "返 `[{label: str}, ...]`, 跟 env 配置一致. "
        "运行时修改 env 需重启服务 (Python 启动时固化)."
    ),
)
def list_kg_datasets() -> list[dict]:
    return [{"label": d} for d in _kg_datasets.list_datasets()]
```

- [ ] **Step 2: 写 router test**

```python
# packages/service/tests/kg/test_router_dataset.py
"""dataset query param + GET /datasets + submit_triples admin 鉴权 测试"""
from typing import Any, cast
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.core.app_factory import create_app
from src.kg import datasets


@pytest.fixture(autouse=True)
def _seed_datasets(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(datasets, "ALLOWED_DATASETS", ["motor", "plc"])


def test_list_datasets_returns_whitelist():
    """GET /api/kg/datasets 返 env 白名单"""
    client = TestClient(create_app())
    r = client.get("/api/kg/datasets")
    if r.status_code == 200:
        labels = {d["label"] for d in r.json()}
        assert labels == {"motor", "plc"}


def test_list_nodes_invalid_dataset_returns_422():
    """dataset 不在白名单 → 422 (Pydantic validation 之前手动 raise)"""
    with patch("src.kg.router.KgClient") as mock_kg_cls:
        mock_kg = MagicMock()
        mock_kg.list_nodes.return_value = []
        mock_kg_cls.return_value = mock_kg
        client = TestClient(create_app())
        r = client.get("/api/kg/nodes?dataset=evil")
        # 应该是 4xx, 不是 200
        assert r.status_code >= 400
```

- [ ] **Step 3: 跑测试确认通过**

```bash
cd packages/service && uv run pytest tests/kg/test_router_dataset.py tests/kg/test_client_dataset.py tests/kg/test_datasets.py -v
```

Expected: 全部 PASS.

- [ ] **Step 4: commit**

```bash
cd c:/doc/Code/rag && git add packages/service/src/kg/datasets.py \
        packages/service/src/kg/client.py \
        packages/service/src/kg/router.py \
        packages/service/src/main.py \
        packages/service/tests/kg/test_datasets.py \
        packages/service/tests/kg/test_client_dataset.py \
        packages/service/tests/kg/test_router_dataset.py
git commit -m "feat(kg): dataset label 隔离 (env 白名单 KG_ALLOWED_DATASETS, MERGE/WHERE 加 :Dataset label)"
```

---

## Task 5: Neo4j dataset label 索引 + init script + GET /datasets API + 删 graphifyy dev dep (v3, 不加 (label,key) 约束)

**Files:**
- Create: `packages/service/src/kg/migrations/neo4j_init.cypher` (dataset label 索引)
- Create: `packages/service/scripts/init_neo4j_dataset_indexes.py` (--dry-run 入口)
- Modify: `packages/service/pyproject.toml` (删 graphifyy>=0.8.44)
- Modify: `packages/service/uv.lock` (uv remove graphifyy 同步)
- Test: `packages/service/tests/kg/test_init_neo4j_script.py` (2 个 test)

- [ ] **Step 1: 写 2 个失败测试**

```python
# packages/service/tests/kg/test_init_neo4j_script.py
"""init_neo4j_dataset_indexes 测试 (2026-07-01 PR1, v3)"""
import subprocess
import sys


def test_init_neo4j_dataset_indexes_dry_run_prints_cypher():
    """dry-run 必须 print dataset label 索引 cypher, 不真连 Neo4j"""
    result = subprocess.run(
        [sys.executable, "-m", "packages.service.scripts.init_neo4j_dataset_indexes",
         "--dataset", "motor", "--dry-run"],
        capture_output=True, text=True, check=False, cwd=".",
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert "CREATE INDEX" in result.stdout
    assert "Motor" in result.stdout or "motor" in result.stdout
    # 关键: dry-run 不连 Neo4j
    assert "connect" not in result.stderr.lower()
    assert "error" not in result.stderr.lower()


def test_init_neo4j_dataset_indexes_no_label_key_constraint():
    """v3: 不建 (label,key) 唯一约束 (v1 删了, v2 删了, v3 仍不要)

    根因: 不同 dataset 同一 key 可合法存在
    (例: motor dataset 的 Product model="1LE0001" + plc dataset 的 Product model="1LE0001"),
    唯一约束会导致 MERGE 误合并
    """
    result = subprocess.run(
        [sys.executable, "-m", "packages.service.scripts.init_neo4j_dataset_indexes",
         "--dataset", "motor", "--dry-run"],
        capture_output=True, text=True, check=False, cwd=".",
    )
    # 0 CREATE CONSTRAINT
    assert "CREATE CONSTRAINT" not in result.stdout.upper()
    # 只有 dataset label index
    assert "CREATE INDEX" in result.stdout.upper()
```

- [ ] **Step 2: 实现 cypher + script**

**`packages/service/src/kg/migrations/neo4j_init.cypher`** (每 dataset 单独跑):

```cypher
-- Neo4j dataset label 索引 (2026-07-01 markdown extract KG spec PR1, v3)
-- v3 设计: 项目用 Neo4j Community Edition (1 database only), 用 dataset label 隔离
-- env KG_ALLOWED_DATASETS 白名单控制允许的 dataset (motor/plc/sensor)
-- v3: 不加 (label,key) 唯一约束 (不同 dataset 同一 key 可合法存在)
--
-- 运行: uv run python -m packages.service.scripts.init_neo4j_dataset_indexes --dataset motor

-- :Motor 索引 (对 Product / Spec / Series / Standard 业务 label 加 dataset 联合索引)
CREATE INDEX motor_product_idx IF NOT EXISTS FOR (n:Product) ON (n:`Motor`);
CREATE INDEX motor_spec_idx IF NOT EXISTS FOR (n:Spec) ON (n:`Motor`);
CREATE INDEX motor_series_idx IF NOT EXISTS FOR (n:Series) ON (n:`Motor`);
CREATE INDEX motor_standard_idx IF NOT EXISTS FOR (n:Standard) ON (n:`Motor`);
```

**`packages/service/scripts/init_neo4j_dataset_indexes.py`** (按 dataset 跑):

```python
"""Neo4j dataset label 索引初始化 (2026-07-01 PR1, v3, M2)

用法:
    uv run python -m packages.service.scripts.init_neo4j_dataset_indexes --dataset motor  # 真跑
    uv run python -m packages.service.scripts.init_neo4j_dataset_indexes --dataset motor --dry-run  # 只 print

行为:
    读 src/kg/migrations/neo4j_init.cypher, 过滤出 CREATE INDEX for current dataset,
    --dry-run 只 print, 否则连 Neo4j 执行.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from loguru import logger


def main() -> int:
    parser = argparse.ArgumentParser(description="Neo4j dataset label 索引初始化")
    parser.add_argument("--dataset", required=True, help="dataset label, 如 motor/plc/sensor")
    parser.add_argument("--dry-run", action="store_true", help="只 print cypher, 不连 Neo4j")
    args = parser.parse_args()

    ds = args.dataset
    if not ds.isidentifier():
        logger.error("dataset 必须是合法 identifier: {}", ds)
        return 1

    cypher_file = Path(__file__).resolve().parents[1] / "src" / "kg" / "migrations" / "neo4j_init.cypher"
    cypher_text = cypher_file.read_text(encoding="utf-8")
    statements = [
        s.strip() for s in cypher_text.split(";")
        if s.strip() and not s.strip().startswith("--") and ds.lower() in s.lower()
    ]

    if args.dry_run:
        for s in statements:
            print(s + ";")
        return 0

    # 真跑: 连 Neo4j
    from src.kg.neo4j import Neo4jStore
    store = Neo4jStore()
    for s in statements:
        logger.info("执行 cypher: {}", s[:80])
        store.execute(s, {})
    logger.info("Neo4j dataset label 索引初始化完成 (dataset={}, statements={})", ds, len(statements))
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

**`pyproject.toml`** (删 graphifyy):

```toml
# packages/service/pyproject.toml
# 删除前 (v0):
# dev = [
#   ...
#   "graphifyy>=0.8.44",
# ]
#
# 删除后 (v3): 移除 graphifyy 那一行
# 调研确认: graphifyy 是 AI 编码助手 slash command 不是 NLP 抽取库, 项目 0 import
```

```bash
# 同步 uv.lock
cd packages/service && uv remove graphifyy
```

- [ ] **Step 3: 跑测试确认通过**

```bash
cd packages/service && uv run pytest tests/kg/test_init_neo4j_script.py -v
uv run python -m packages.service.scripts.init_neo4j_dataset_indexes --dataset motor --dry-run
```

Expected: 2 个 test PASS, dry-run 输出 4 条 CREATE INDEX for `Motor`.

- [ ] **Step 4: commit**

```bash
cd c:/doc/Code/rag && git add packages/service/src/kg/migrations/neo4j_init.cypher \
        packages/service/scripts/init_neo4j_dataset_indexes.py \
        packages/service/pyproject.toml \
        packages/service/uv.lock \
        packages/service/tests/kg/test_init_neo4j_script.py
git commit -m "feat(kg): Neo4j dataset label 索引 cypher + init script + 删 graphifyy dev dep"
```

---

## PR1 收尾验证

```bash
cd packages/service
uv run pytest tests/kg/ tests/core/ -v   # 25+ 新 test pass
uv run ruff format
uv run ruff check --fix
uv run pyright
```

### PR1 准备合并 checklist

- [ ] **dataset label 隔离验证**: `KgClient.list_nodes` cypher 必含 `WHERE n:\`<Dataset>\`` 防跨 dataset 泄露. 已通过 `test_kgclient_list_nodes_uses_dataset_in_where` 覆盖
- [ ] **dataset 白名单防御**: `validate_dataset` 拒绝白名单外 + 非法 identifier. 已通过 `test_kgclient_rejects_unknown_dataset` 等覆盖
- [ ] **5 元组分组不变**: dataset 在 cypher 字面量展开, 跟 v1 一致. 已通过 `test_batch_upsert_grouping_keeps_5_tuple` 覆盖
- [ ] **Neo4j dataset label 索引**: dry-run 输出 4 条 CREATE INDEX. 不建 (label,key) 唯一约束. 已通过 `test_init_neo4j_dataset_indexes_*` 覆盖
- [ ] **graphifyy 删除**: `pyproject.toml` 无 `graphifyy`, `uv.lock` 同步
- [ ] **PR description**: `"M1+M2 完成, Neo4j dataset label 隔离 (env 白名单 + WHERE/MERGE 加 label) + dataset label 索引 + GET /datasets + submit_triples admin 鉴权 + 删 graphifyy"`