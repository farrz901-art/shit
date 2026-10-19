# 知识库 + 知识图谱管理页 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 RAG 项目里新增 `/knowledge` 后台管理模块, 业务人员能自助把 QA/产品文档喂给 Dify, 工程师能批量写三元组到 Neo4j, schema 改 yaml 不改代码。

**Architecture:**
- 后端: FastAPI (port 8000) 新增 `src/rag/kg/` 子包, 复用现有 `Neo4jStore` 扩展; 新增 `DifyDatasetsClient` (TS port 写到 `web/lib/`) 经 Next.js BFF
- 前端: Next.js 16 + React 19 + shadcn/ui, 5 个页面 (`/knowledge` + 4 个 Tab)
- 配置: `configs/knowledge-schema.yaml` 驱动节点/关系, 加类型不改代码
- 任务: in-memory `TaskStore` + SQLite 持久化历史

**Tech Stack:** Python 3.14 + pytest, FastAPI + httpx, neo4j driver, pyyaml; Next.js 16 + React 19 + TypeScript, shadcn/ui, swr, react-hook-form, zod, vitest

**关联 Spec:** `docs/superpowers/specs/2026-06-08-knowledge-management-page-design.md`

---

## 文件结构总览

### 新增 (Python)
- `configs/knowledge-schema.yaml` — 节点/关系定义
- `src/rag/kg/__init__.py`
- `src/rag/kg/exceptions.py` — KgError / DuplicateNodeError / InvalidTripleError
- `src/rag/kg/schema.py` — yaml loader, 引用完整性校验
- `src/rag/kg/client.py` — `KgClient` (UNWIND MERGE, 扩展 Neo4jStore)
- `src/rag/kg/tasks.py` — `TaskStore` + 后台 worker
- `src/rag/kg/router.py` — FastAPI 路由 (`/api/kg/*`)
- `src/rag/kg/templates.py` — Excel 模板生成
- `static/knowledge-templates/knowledge-import.xlsx` — 模板二进制 (v1 手工生成)
- `tests/test_kg_schema.py`
- `tests/test_kg_client.py` (testcontainers Neo4j, slow)
- `tests/test_kg_triples.py` (slow)
- `tests/test_kg_tasks.py`
- `tests/test_kg_router.py` (httpx + mock Neo4j)
- `tests/test_kg_templates.py`

### 新增 (Next.js)
- `web/app/knowledge/layout.tsx` — 顶部 dataset 切换 + 环境徽章 + 健康点
- `web/app/knowledge/page.tsx` — Dashboard
- `web/app/knowledge/qa/page.tsx` + `page.test.tsx`
- `web/app/knowledge/documents/page.tsx` + `page.test.tsx`
- `web/app/knowledge/triples/page.tsx` + `page.test.tsx`
- `web/app/knowledge/batch/page.tsx` + `page.test.tsx`
- `web/app/api/knowledge/[...path]/route.ts` — BFF 入口 (Dify 代理)
- `web/app/api/knowledge/health/route.ts`
- `web/app/api/knowledge/schema/route.ts`
- `web/app/api/knowledge/stats/route.ts`
- `web/app/api/knowledge/datasets/route.ts`
- `web/app/api/knowledge/qa/route.ts`
- `web/app/api/knowledge/qa/retrieve/route.ts`
- `web/app/api/knowledge/documents/upload/route.ts`
- `web/app/api/knowledge/documents/commit/route.ts`
- `web/app/api/knowledge/documents/route.ts`
- `web/app/api/knowledge/templates/[format]/route.ts`
- `web/components/knowledge/DatasetSwitcher.tsx`
- `web/components/knowledge/EnvBadge.tsx`
- `web/components/knowledge/HealthDot.tsx`
- `web/components/knowledge/StatCard.tsx`
- `web/components/knowledge/EntryCard.tsx`
- `web/components/knowledge/DataTable.tsx` + `.test.tsx`
- `web/components/knowledge/FileDropzone.tsx` + `.test.tsx`
- `web/components/knowledge/TaskStatusBadge.tsx` + `.test.tsx`
- `web/components/knowledge/SchemaFieldRenderer.tsx` + `.test.tsx`
- `web/components/knowledge/ErrorReport.tsx`
- `web/lib/dify-datasets.ts` + `.test.ts` (TS port, msw mock)
- `web/lib/parse-excel.ts` + `.test.ts`
- `web/lib/parse-json.ts` + `.test.ts`
- `web/lib/schema-types.ts` (zod schema 镜像 yaml)
- `web/lib/swr-fetcher.ts`
- `web/public/templates/knowledge-import.json`

### 修改
- `web/app/layout.tsx` — 顶 nav 加 `/knowledge`
- `web/components/ui/select.tsx`, `textarea.tsx`, `tabs.tsx`, `dialog.tsx`, `dropdown-menu.tsx`, `progress.tsx`, `toast.tsx` — 按需补 (shadcn add)
- `src/rag/api/routes.py` — 挂载 kg router
- `src/rag/common/defaults.py` — 加 KG 相关默认值
- `pyproject.toml` — 加 testcontainers, openpyxl 依赖
- `web/package.json` — 加 swr / react-hook-form / zod / papaparse / xlsx / react-dropzone / @testing-library/user-event

### 总体 PR 顺序
- **PR 1**: yaml + `src/rag/kg/` 骨架 + tests (无前端, 后端单测全绿)
- **PR 2**: Next.js `app/knowledge/*` 4 个空页面 + 顶 nav + 布局
- **PR 3**: Dashboard 卡片 + Datasets 客户端 (TS port) + Dify BFF 路由
- **PR 4**: Tab 1 (QA) 完整流程
- **PR 5**: Tab 2 (Documents) 三步流程 + 模板下载
- **PR 6**: Tab 3 (Triples) + Neo4j 写入
- **PR 7**: Tab 4 (Batch) + 后台任务 + 任务面板
- **PR 8**: Schema 浏览器 + Audit log + 收尾打磨

每个 PR 独立可测, 跑 `uv run pytest tests/ -m "not slow" -q` + `bun run test` 全绿。

---

# PR 1 · 后端骨架 + Schema 配置

**PR 目标**: 加 `configs/knowledge-schema.yaml`, 新建 `src/rag/kg/` 子包 (schema / client / tasks / router), 全部单测绿, 还没接前端。

---

## Task 1.1: 创建 `configs/knowledge-schema.yaml`

**Files:**
- Create: `configs/knowledge-schema.yaml`

- [ ] **Step 1: 创建 yaml**

```yaml
# 知识图谱 schema 定义 (2026-06-08)
# 加节点/关系改这文件, 不改代码; 前端表单和后端校验都从这读
nodes:
  - name: Product
    color: blue
    fields:
      - { key: model,        label: 产品订货号, type: string,  required: true,  unique: true }
      - { key: name,         label: 产品名称,   type: string,  required: true }
      - { key: series,       label: 所属系列,   type: ref, ref_to: Series, required: true }
      - { key: manufacturer, label: 厂商,       type: enum, options: ["Siemens", "ABB", "Schneider"], required: true }

  - name: Series
    color: purple
    fields:
      - { key: name,         label: 系列名,   type: string, required: true, unique: true }
      - { key: manufacturer, label: 厂商,     type: enum,  options: ["Siemens", "ABB", "Schneider"], required: true }
      - { key: description,  label: 说明,     type: text }

  - name: Document
    color: green
    fields:
      - { key: title,       label: 标题,     type: string,  required: true }
      - { key: source,      label: 来源,     type: enum, options: ["manual", "dify", "url"] }
      - { key: url,         label: URL,      type: url }
      - { key: uploaded_at, label: 上传时间, type: datetime, readonly: true }

  - name: QAPair
    color: orange
    fields:
      - { key: question, label: 问题, type: text,   required: true }
      - { key: answer,   label: 答案, type: text,   required: true }
      - { key: tags,     label: 标签, type: string, multiple: true }

relations:
  - { name: BELONGS_TO,      from: Product,  to: Series,    cardinality: many_to_one }
  - { name: ABOUT,           from: QAPair,   to: Product,   cardinality: many_to_one }
  - { name: REFERENCES,      from: QAPair,   to: Document,  cardinality: many_to_many }
  - { name: DESCRIBES,       from: Document, to: Product,   cardinality: many_to_one }
  - { name: COMPATIBLE_WITH, from: Product,  to: Product,   cardinality: many_to_many }
```

- [ ] **Step 2: 提交**

```bash
git add configs/knowledge-schema.yaml
git commit -m "feat(kg): 新增 knowledge-schema.yaml 定义 4 节点 5 关系"
```

---

## Task 1.2: `src/rag/kg/exceptions.py` + `__init__.py`

**Files:**
- Create: `src/rag/kg/__init__.py`
- Create: `src/rag/kg/exceptions.py`

- [ ] **Step 1: 写异常类**

`src/rag/kg/exceptions.py`:

```python
"""知识图谱模块异常类型"""


class KgError(RuntimeError):
    """知识图谱相关错误的基类"""


class DuplicateNodeError(KgError):
    """MERGE 命中已存在节点且 caller 要求 CREATE-only"""


class InvalidTripleError(KgError):
    """三元组结构不合法 (缺字段 / 类型不匹配 / 关系不存在)"""


class SchemaError(KgError):
    """yaml schema 加载或校验失败"""


class TaskNotFoundError(KgError):
    """task_id 在 TaskStore 里查不到"""
```

- [ ] **Step 2: 写 `__init__.py`**

`src/rag/kg/__init__.py`:

```python
"""知识图谱子包

负责 Neo4j 节点/关系写入、schema 校验、后台任务。
FastAPI 路由见 src/rag/kg/router.py。
"""
```

- [ ] **Step 3: 跑现有测试确认不挂**

Run: `uv run pytest tests/ -m "not slow" -q`
Expected: 全过 (新文件还没 import, 不影响)

- [ ] **Step 4: 提交**

```bash
git add src/rag/kg/__init__.py src/rag/kg/exceptions.py
git commit -m "feat(kg): 新增 kg 子包骨架 + 异常类型"
```

---

## Task 1.3: `src/rag/kg/schema.py` + 红测试

**Files:**
- Create: `src/rag/kg/schema.py`
- Create: `tests/test_kg_schema.py`

- [ ] **Step 1: 写红测试**

`tests/test_kg_schema.py`:

```python
"""kg.schema 红测试

- load_schema() 从 configs/knowledge-schema.yaml 读
- 校验节点/关系引用完整性 (ref 字段必须指向已定义节点)
- 暴露 nodes/relations 给前端 API 用
"""
from pathlib import Path

import pytest

from src.rag.kg import schema
from src.rag.kg.exceptions import SchemaError

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = REPO_ROOT / "configs" / "knowledge-schema.yaml"


class TestLoadSchema:
    def test_load_returns_nodes_and_relations(self):
        loaded = schema.load_schema(str(SCHEMA_PATH))
        assert "nodes" in loaded
        assert "relations" in loaded
        assert len(loaded["nodes"]) == 4
        assert len(loaded["relations"]) == 5

    def test_loads_product_node_with_fields(self):
        loaded = schema.load_schema(str(SCHEMA_PATH))
        product = next(n for n in loaded["nodes"] if n["name"] == "Product")
        field_keys = {f["key"] for f in product["fields"]}
        assert {"model", "name", "series", "manufacturer"} <= field_keys

    def test_relations_reference_known_nodes(self):
        loaded = schema.load_schema(str(SCHEMA_PATH))
        node_names = {n["name"] for n in loaded["nodes"]}
        for rel in loaded["relations"]:
            assert rel["from"] in node_names, f"未知 from 节点: {rel['from']}"
            assert rel["to"] in node_names, f"未知 to 节点: {rel['to']}"


class TestRefIntegrity:
    def test_product_series_ref_points_to_series(self):
        """Product.series 字段 type=ref ref_to=Series 必须存在"""
        loaded = schema.load_schema(str(SCHEMA_PATH))
        product = next(n for n in loaded["nodes"] if n["name"] == "Product")
        series_field = next(f for f in product["fields"] if f["key"] == "series")
        assert series_field["type"] == "ref"
        assert series_field["ref_to"] == "Series"

    def test_ref_to_unknown_node_raises(self, tmp_path):
        """ref_to 指向不存在的节点 → 加载报错"""
        bad = tmp_path / "bad.yaml"
        bad.write_text(
            "nodes:\n"
            "  - name: A\n"
            "    fields:\n"
            "      - { key: b, type: ref, ref_to: MissingNode }\n"
            "relations: []\n",
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
        product = schema.get_node(loaded, "Product")
        assert product["name"] == "Product"

    def test_get_node_missing_raises(self):
        loaded = schema.load_schema(str(SCHEMA_PATH))
        with pytest.raises(SchemaError, match="NotFound"):
            schema.get_node(loaded, "NotFound")

    def test_get_relations_from_label(self):
        """从 Product 出发的关系应包含 BELONGS_TO 和 COMPATIBLE_WITH"""
        loaded = schema.load_schema(str(SCHEMA_PATH))
        rels = schema.get_relations_from(loaded, "Product")
        rel_names = {r["name"] for r in rels}
        assert {"BELONGS_TO", "COMPATIBLE_WITH", "DESCRIBES"} <= rel_names
```

- [ ] **Step 2: 跑测试确认 FAIL**

Run: `uv run pytest tests/test_kg_schema.py -v`
Expected: 10 个测试全部 FAIL (`cannot import name 'schema'`)

- [ ] **Step 3: 实现 `src/rag/kg/schema.py`**

```python
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
        data = yaml.safe_load(f)

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
                    raise SchemaError(
                        f"节点 {n['name']}.{fld.get('key')} 的 ref_to={ref_to} 未定义"
                    )

    # 校验关系 from/to
    for r in relations:
        for k in ("from", "to"):
            if r.get(k) not in node_names:
                raise SchemaError(
                    f"关系 {r.get('name')} 的 {k}={r.get(k)} 未定义"
                )

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
```

- [ ] **Step 4: 跑测试确认 PASS**

Run: `uv run pytest tests/test_kg_schema.py -v`
Expected: 10 个测试全部 PASS

- [ ] **Step 5: 跑全量测试确认无回归**

Run: `uv run pytest tests/ -m "not slow" -q`
Expected: 全过

- [ ] **Step 6: 提交**

```bash
git add src/rag/kg/schema.py tests/test_kg_schema.py
git commit -m "feat(kg): schema 加载 + 引用完整性校验"
```

---

## Task 1.4: `src/rag/kg/client.py` + 红测试 (mock)

**Files:**
- Create: `src/rag/kg/client.py`
- Create: `tests/test_kg_client.py`

> 注: 真 Neo4j 测试用 testcontainers 放 slow 标记; 这里先用 `unittest.mock` 覆盖所有 Neo4j driver 路径。

- [ ] **Step 1: 写红测试**

`tests/test_kg_client.py`:

```python
"""kg.client 红测试 (mock Neo4j driver)

- KgClient 是 Neo4jStore 的轻量封装, 加 UNWIND MERGE 批量 API
- batch_upsert_triples 接收 TripleRow 列表, 返回 BatchResult
- count_by_label 返回 {label: count}
- subgraph 返回节点 + 边
"""
from unittest.mock import MagicMock

import pytest

from src.rag.kg import client
from src.rag.kg.client import BatchResult, KgClient, TripleRow


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
        rows = [TripleRow(from_label="Product", from_key="model", from_value="1LE0001",
                          rel_type="BELONGS_TO",
                          to_label="Series", to_key="name", to_value="1LE 系列",
                          properties={})]
        result = kg.batch_upsert_triples(rows)
        assert result.success == 1
        cypher, params = mock_store.execute_and_fetch.call_args[0][:2]
        assert "UNWIND" in cypher.upper()
        assert "MERGE" in cypher.upper()
        assert params["rows"][0]["from_value"] == "1LE0001"

    def test_returns_failed_count_on_neo4j_error(self, mock_store):
        mock_store.execute_and_fetch.side_effect = RuntimeError("boom")
        kg = KgClient(store=mock_store)
        rows = [TripleRow(from_label="Product", from_key="model", from_value="X",
                          rel_type="BELONGS_TO",
                          to_label="Series", to_key="name", to_value="Y",
                          properties={})]
        result = kg.batch_upsert_triples(rows)
        assert result.success == 0
        assert result.failed == 1
        assert "boom" in result.errors[0]


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
```

- [ ] **Step 2: 跑测试确认 FAIL**

Run: `uv run pytest tests/test_kg_client.py -v`
Expected: 9 个测试全部 FAIL (`cannot import name 'client'`)

- [ ] **Step 3: 实现 `src/rag/kg/client.py`**

```python
"""Neo4j 知识图谱客户端 (UNWIND MERGE 批量写入)

KgClient 是 src/rag/knowledge_graph/neo4j_client.py:Neo4jStore 的轻量封装,
新增批量写入 / 子图查询等知识图谱专用 API。

为什么不用 Neo4jStore 直接: 批量 UNWIND MERGE 需要把 rows 整个传成 $rows,
store 的 execute_and_fetch 一次只发一条语句, 包装一下让调用方更舒服。
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ..knowledge_graph.neo4j_client import Neo4jStore


@dataclass
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


@dataclass
class BatchResult:
    success: int = 0
    failed: int = 0
    errors: list[str] = field(default_factory=list)


class KgClient:
    """知识图谱客户端, 包装 Neo4jStore

    Args:
        store: Neo4jStore 实例 (测试时可传 MagicMock)
    """

    def __init__(self, store: Neo4jStore | None = None):
        self._store = store or Neo4jStore()

    def merge_node(self, label: str, properties: dict, unique_keys: dict) -> str | None:
        """MERGE 一个节点, unique_keys 指定匹配键"""
        cypher, params = self._build_merge_node_cypher(label, properties, unique_keys)
        results = self._store.execute_and_fetch(cypher, params)
        return str(results[0]["node_id"]) if results else None

    def _build_merge_node_cypher(self, label: str, properties: dict, unique_keys: dict) -> tuple[str, dict]:
        merge_props = ", ".join(f"`{k}`: ${k}" for k in unique_keys)
        cypher = (
            f"MERGE (n:{label} {{{merge_props}}}) "
            f"SET n += $extra "
            f"RETURN id(n) AS node_id"
        )
        params = {**unique_keys, "extra": properties}
        return cypher, params

    def batch_upsert_triples(self, rows: list[TripleRow]) -> BatchResult:
        """批量 UNWIND MERGE 三元组 (一次事务)

        Args:
            rows: TripleRow 列表
        Returns:
            BatchResult(success, failed, errors)
        """
        if not rows:
            return BatchResult()
        cypher, params = self._build_unwind_cypher(rows)
        try:
            self._store.execute_and_fetch(cypher, params)
            return BatchResult(success=len(rows))
        except Exception as e:  # noqa: BLE001
            return BatchResult(success=0, failed=len(rows), errors=[str(e)])

    def _build_unwind_cypher(self, rows: list[TripleRow]) -> tuple[str, dict]:
        first = rows[0]
        cypher = f"""
        UNWIND $rows AS row
        MERGE (a:{first.from_label} {{`{first.from_key}`: row.from_value}})
        MERGE (b:{first.to_label} {{`{first.to_key}`: row.to_value}})
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
        """按 label 统计节点数"""
        cypher = "MATCH (n) RETURN label(n) AS label, count(n) AS cnt"
        results = self._store.execute_and_fetch(cypher)
        return {r["label"]: r["cnt"] for r in results}

    def subgraph(self, node_ids: list[str], depth: int = 1) -> dict:
        """取 node_ids 节点的 depth 跳邻居子图"""
        nodes_cypher = (
            "MATCH (n) WHERE id(n) IN $ids "
            "OPTIONAL MATCH (n)-[*1.." + str(depth) + "]-(m) "
            "RETURN DISTINCT id(m) AS id, labels(m)[0] AS label, properties(m) AS props"
        )
        nodes = self._store.execute_and_fetch(nodes_cypher, {"ids": [int(i) for i in node_ids]})

        edges_cypher = (
            "MATCH (a)-[r]->(b) "
            "WHERE id(a) IN $ids AND id(b) IN $ids "
            "RETURN id(a) AS src, id(b) AS dst, type(r) AS type, properties(r) AS props"
        )
        edges = self._store.execute_and_fetch(edges_cypher, {"ids": [int(i) for i in node_ids]})

        return {
            "nodes": [{"id": str(n["id"]), "label": n["label"], "props": n["props"]} for n in nodes],
            "edges": [{"src": str(e["src"]), "dst": str(e["dst"]), "type": e["type"], "props": e["props"]} for e in edges],
        }
```

- [ ] **Step 4: 跑测试确认 PASS**

Run: `uv run pytest tests/test_kg_client.py -v`
Expected: 9 个测试全部 PASS

- [ ] **Step 5: 跑全量测试确认无回归**

Run: `uv run pytest tests/ -m "not slow" -q`
Expected: 全过

- [ ] **Step 6: 提交**

```bash
git add src/rag/kg/client.py tests/test_kg_client.py
git commit -m "feat(kg): KgClient + UNWIND MERGE 批量 + 子图查询"
```

---

## Task 1.5: `src/rag/kg/tasks.py` + 红测试

**Files:**
- Create: `src/rag/kg/tasks.py`
- Create: `tests/test_kg_tasks.py`

- [ ] **Step 1: 写红测试**

`tests/test_kg_tasks.py`:

```python
"""kg.tasks 红测试

TaskStore (in-memory) 管理后台任务状态:
  queued → running → {done, partial, failed, cancelled}
"""
import time

import pytest

from src.rag.kg import tasks
from src.rag.kg.exceptions import TaskNotFoundError
from src.rag.kg.tasks import TaskStatus, TaskStore


class TestSubmit:
    def test_submit_returns_task_id(self):
        store = TaskStore()
        tid = store.submit("kg_triples", {"rows": []})
        assert isinstance(tid, str) and len(tid) > 0

    def test_submit_starts_as_queued(self):
        store = TaskStore()
        tid = store.submit("kg_triples", {})
        status = store.get(tid)
        assert status.state == "queued"
        assert status.kind == "kg_triples"


class TestStateTransitions:
    def test_mark_running(self):
        store = TaskStore()
        tid = store.submit("kg_batch", {})
        store.mark_running(tid)
        assert store.get(tid).state == "running"

    def test_mark_done(self):
        store = TaskStore()
        tid = store.submit("kg_batch", {})
        store.mark_running(tid)
        store.mark_done(tid, success=10, failed=0)
        status = store.get(tid)
        assert status.state == "done"
        assert status.success == 10
        assert status.finished_at is not None

    def test_mark_partial(self):
        store = TaskStore()
        tid = store.submit("kg_batch", {})
        store.mark_running(tid)
        store.mark_partial(tid, success=8, failed=2, errors=["x"])
        status = store.get(tid)
        assert status.state == "partial"
        assert status.failed == 2
        assert status.errors == ["x"]

    def test_mark_failed(self):
        store = TaskStore()
        tid = store.submit("kg_batch", {})
        store.mark_running(tid)
        store.mark_failed(tid, error="boom")
        assert store.get(tid).state == "failed"
        assert store.get(tid).errors == ["boom"]

    def test_mark_cancelled(self):
        store = TaskStore()
        tid = store.submit("kg_batch", {})
        store.mark_cancelled(tid)
        assert store.get(tid).state == "cancelled"


class TestGet:
    def test_get_unknown_raises(self):
        store = TaskStore()
        with pytest.raises(TaskNotFoundError):
            store.get("nope")

    def test_list_recent(self):
        store = TaskStore()
        a = store.submit("kg_triples", {})
        time.sleep(0.01)
        b = store.submit("kg_batch", {})
        recent = store.list_recent(limit=10)
        assert len(recent) == 2
        # 最新的在前面
        assert recent[0].task_id == b
        assert recent[1].task_id == a
```

- [ ] **Step 2: 跑测试确认 FAIL**

Run: `uv run pytest tests/test_kg_tasks.py -v`
Expected: 10 个测试全部 FAIL

- [ ] **Step 3: 实现 `src/rag/kg/tasks.py`**

```python
"""后台任务管理 (in-memory TaskStore)

v1: 内存 dict, 单 worker 假设; 重启 dev server 任务丢
v2: Redis / SQLite 持久化 (本期不做)
"""
from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field

from .exceptions import TaskNotFoundError


@dataclass
class TaskStatus:
    task_id: str
    kind: str
    state: str
    payload: dict
    success: int = 0
    failed: int = 0
    errors: list[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    started_at: float | None = None
    finished_at: float | None = None


class TaskStore:
    """任务状态存储 (in-memory, 线程安全)"""

    def __init__(self):
        self._lock = threading.Lock()
        self._tasks: dict[str, TaskStatus] = {}

    def submit(self, kind: str, payload: dict) -> str:
        task_id = uuid.uuid4().hex[:12]
        with self._lock:
            self._tasks[task_id] = TaskStatus(
                task_id=task_id, kind=kind, state="queued", payload=payload
            )
        return task_id

    def get(self, task_id: str) -> TaskStatus:
        with self._lock:
            if task_id not in self._tasks:
                raise TaskNotFoundError(f"任务不存在: {task_id}")
            return self._tasks[task_id]

    def mark_running(self, task_id: str) -> None:
        with self._lock:
            t = self._require(task_id)
            t.state = "running"
            t.started_at = time.time()

    def mark_done(self, task_id: str, success: int, failed: int = 0) -> None:
        with self._lock:
            t = self._require(task_id)
            t.state = "done" if failed == 0 else "partial"
            t.success = success
            t.failed = failed
            t.finished_at = time.time()

    def mark_partial(self, task_id: str, success: int, failed: int, errors: list[str]) -> None:
        with self._lock:
            t = self._require(task_id)
            t.state = "partial"
            t.success = success
            t.failed = failed
            t.errors = errors
            t.finished_at = time.time()

    def mark_failed(self, task_id: str, error: str) -> None:
        with self._lock:
            t = self._require(task_id)
            t.state = "failed"
            t.errors = [error]
            t.finished_at = time.time()

    def mark_cancelled(self, task_id: str) -> None:
        with self._lock:
            t = self._require(task_id)
            t.state = "cancelled"
            t.finished_at = time.time()

    def list_recent(self, limit: int = 50) -> list[TaskStatus]:
        with self._lock:
            items = sorted(self._tasks.values(), key=lambda t: t.created_at, reverse=True)
            return items[:limit]

    def _require(self, task_id: str) -> TaskStatus:
        if task_id not in self._tasks:
            raise TaskNotFoundError(f"任务不存在: {task_id}")
        return self._tasks[task_id]
```

- [ ] **Step 4: 跑测试确认 PASS**

Run: `uv run pytest tests/test_kg_tasks.py -v`
Expected: 10 个测试全部 PASS

- [ ] **Step 5: 提交**

```bash
git add src/rag/kg/tasks.py tests/test_kg_tasks.py
git commit -m "feat(kg): TaskStore in-memory + 状态机"
```

---

## Task 1.6: `src/rag/kg/router.py` + 红测试

**Files:**
- Create: `src/rag/kg/router.py`
- Create: `tests/test_kg_router.py`

- [ ] **Step 1: 写红测试**

`tests/test_kg_router.py`:

```python
"""kg.router FastAPI 路由测试 (httpx + mock)"""
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.rag.kg import router as kg_router


@pytest.fixture
def app():
    app = FastAPI()
    app.include_router(kg_router.router)
    return app


@pytest.fixture
def client(app):
    return TestClient(app)


class TestStats:
    def test_stats_returns_counts_per_label(self, client):
        with patch.object(kg_router, "KgClient") as MockClient:
            instance = MagicMock()
            instance.count_by_label.return_value = {"Product": 5, "Series": 2, "Document": 0, "QAPair": 0}
            MockClient.return_value = instance
            res = client.get("/api/kg/stats")
            assert res.status_code == 200
            assert res.json() == {"Product": 5, "Series": 2, "Document": 0, "QAPair": 0}


class TestTriples:
    def test_post_empty_rows_returns_zero(self, client):
        from unittest.mock import patch
        with patch.object(kg_router, "KgClient") as MockClient:
            instance = MagicMock()
            instance.batch_upsert_triples.return_value = MagicMock(success=0, failed=0, errors=[])
            MockClient.return_value = instance
            res = client.post("/api/kg/triples", json={"rows": []})
            assert res.status_code == 200
            assert res.json()["success"] == 0

    def test_post_validates_required_fields(self, client):
        res = client.post("/api/kg/triples", json={"rows": [{"from_label": "Product"}]})
        assert res.status_code == 422  # Pydantic validation


class TestProducts:
    def test_get_products_returns_list(self, client):
        from unittest.mock import patch
        with patch.object(kg_router, "KgClient") as MockClient:
            instance = MagicMock()
            instance._store.execute_and_fetch.return_value = [
                {"id": "1", "model": "1LE0001", "name": "X"}
            ]
            MockClient.return_value = instance
            res = client.get("/api/kg/products")
            assert res.status_code == 200
            body = res.json()
            assert len(body) == 1
            assert body[0]["model"] == "1LE0001"


class TestTasks:
    def test_get_task_status(self, client):
        from unittest.mock import patch
        with patch.object(kg_router, "_task_store") as mock_store:
            from src.rag.kg.tasks import TaskStatus
            mock_store.get.return_value = TaskStatus(
                task_id="abc", kind="kg_batch", state="done",
                payload={}, success=10, failed=0,
            )
            res = client.get("/api/kg/tasks/abc")
            assert res.status_code == 200
            assert res.json()["state"] == "done"

    def test_get_unknown_task_404(self, client):
        from unittest.mock import patch
        with patch.object(kg_router, "_task_store") as mock_store:
            from src.rag.kg.exceptions import TaskNotFoundError
            mock_store.get.side_effect = TaskNotFoundError("nope")
            res = client.get("/api/kg/tasks/nope")
            assert res.status_code == 404


class TestBatch:
    def test_batch_submits_and_returns_task_id(self, client):
        from unittest.mock import patch
        with patch.object(kg_router, "KgClient") as MockClient, \
             patch.object(kg_router, "_task_store") as mock_store:
            instance = MagicMock()
            MockClient.return_value = instance
            mock_store.submit.return_value = "task123"
            res = client.post("/api/kg/batch", json={"items": []})
            assert res.status_code == 200
            assert res.json()["task_id"] == "task123"
```

- [ ] **Step 2: 跑测试确认 FAIL**

Run: `uv run pytest tests/test_kg_router.py -v`
Expected: 6 个测试全部 FAIL (router 还没创建)

- [ ] **Step 3: 实现 `src/rag/kg/router.py`**

```python
"""知识图谱 FastAPI 路由

所有端点统一在 /api/kg 前缀下
"""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .client import KgClient, TripleRow
from .exceptions import TaskNotFoundError
from .tasks import TaskStore

router = APIRouter(prefix="/api/kg", tags=["kg"])

# 单例: dev server 重启时丢任务 (v1 接受)
_task_store = TaskStore()


class TripleRowIn(BaseModel):
    from_label: str
    from_key: str
    from_value: str
    rel_type: str
    to_label: str
    to_key: str
    to_value: str
    properties: dict = Field(default_factory=dict)


class TriplesRequest(BaseModel):
    rows: list[TripleRowIn]


class TriplesResponse(BaseModel):
    success: int
    failed: int
    errors: list[str]


class BatchItem(BaseModel):
    target: Literal["dify", "neo4j"]
    type: str
    payload: dict


class BatchRequest(BaseModel):
    items: list[BatchItem]


class BatchResponse(BaseModel):
    task_id: str


@router.get("/stats")
def stats() -> dict:
    """4 节点 label 计数"""
    return KgClient().count_by_label()


@router.get("/products")
def list_products(q: str = "", limit: int = 50) -> list[dict]:
    """列 Product 节点 (供前端 QA tab combobox 用)"""
    cypher = (
        "MATCH (n:Product) "
        "WHERE $q = '' OR n.model CONTAINS $q OR n.name CONTAINS $q "
        "RETURN id(n) AS id, n.model AS model, n.name AS name "
        "LIMIT $limit"
    )
    rows = KgClient()._store.execute_and_fetch(cypher, {"q": q, "limit": limit})
    return [{"id": str(r["id"]), "model": r["model"], "name": r["name"]} for r in rows]


@router.post("/triples", response_model=TriplesResponse)
def submit_triples(req: TriplesRequest) -> TriplesResponse:
    """单批提交三元组 (事务)"""
    rows = [
        TripleRow(
            from_label=r.from_label, from_key=r.from_key, from_value=r.from_value,
            rel_type=r.rel_type,
            to_label=r.to_label, to_key=r.to_key, to_value=r.to_value,
            properties=r.properties,
        )
        for r in req.rows
    ]
    result = KgClient().batch_upsert_triples(rows)
    return TriplesResponse(success=result.success, failed=result.failed, errors=result.errors)


@router.post("/batch", response_model=BatchResponse)
def submit_batch(req: BatchRequest) -> BatchResponse:
    """大批量提交, 立即返 task_id, 后台跑"""
    task_id = _task_store.submit("kg_batch", req.model_dump())
    return BatchResponse(task_id=task_id)


@router.get("/tasks/{task_id}")
def get_task(task_id: str) -> dict:
    """查任务状态"""
    try:
        status = _task_store.get(task_id)
    except TaskNotFoundError:
        raise HTTPException(status_code=404, detail=f"任务不存在: {task_id}")
    return {
        "task_id": status.task_id,
        "kind": status.kind,
        "state": status.state,
        "success": status.success,
        "failed": status.failed,
        "errors": status.errors,
        "created_at": status.created_at,
        "finished_at": status.finished_at,
    }
```

- [ ] **Step 4: 跑测试确认 PASS**

Run: `uv run pytest tests/test_kg_router.py -v`
Expected: 6 个测试全部 PASS

- [ ] **Step 5: 提交**

```bash
git add src/rag/kg/router.py tests/test_kg_router.py
git commit -m "feat(kg): FastAPI 路由 /api/kg/{stats,products,triples,batch,tasks}"
```

---

## Task 1.7: 把 kg router 挂到主 app

**Files:**
- Modify: `src/rag/api/routes.py` 或 `src/product_decoders/app.py` (找 include_router 已有调用)

- [ ] **Step 1: 找挂载点**

```bash
grep -rn "include_router" src/product_decoders/ src/rag/api/
```

找到 `app.include_router(...)` 已有的位置。

- [ ] **Step 2: 加挂载**

在那个文件加 import 和 include:

```python
from src.rag.kg.router import router as kg_router
# ...
app.include_router(kg_router)
```

- [ ] **Step 3: 验证挂载**

Run: `uv run python -c "from src.rag.kg.router import router; print([r.path for r in router.routes])"`
Expected: 打印 `/api/kg/stats`, `/api/kg/products`, `/api/kg/triples`, `/api/kg/batch`, `/api/kg/tasks/{task_id}`

- [ ] **Step 4: 跑全量测试**

Run: `uv run pytest tests/ -m "not slow" -q`
Expected: 全过

- [ ] **Step 5: 启动服务手测**

```bash
# 终端 1
uv run python main.py serve --port 8000

# 终端 2
curl http://localhost:8000/api/kg/stats
```

Expected: `{}` (空 db); 状态码 200

- [ ] **Step 6: 提交**

```bash
git add src/rag/api/routes.py 2>/dev/null || git add src/product_decoders/app.py
git commit -m "feat(kg): 把 kg router 挂到 FastAPI 主 app"
```

---

## Task 1.8: 写 PR 1 文档

**Files:**
- Create: `docs/knowledge-graph.md`

- [ ] **Step 1: 写知识图谱模块说明**

```markdown
# 知识图谱模块 (src/rag/kg/)

为 RAG 后台 \`/knowledge\` 管理页提供 Neo4j 写入 / 校验 / 任务管理能力。

## 子模块

| 文件 | 职责 |
|---|---|
| \`schema.py\` | 加载 \`configs/knowledge-schema.yaml\`, 校验节点/关系引用完整性 |
| \`client.py\` | \`KgClient\` 包装 \`Neo4jStore\`, 提供 UNWIND MERGE 批量写入 + 子图查询 |
| \`tasks.py\` | in-memory \`TaskStore\`, 状态机: queued → running → {done, partial, failed, cancelled} |
| \`router.py\` | FastAPI 路由, 前缀 \`/api/kg/*\` |
| \`exceptions.py\` | \`KgError\` / \`DuplicateNodeError\` / \`InvalidTripleError\` / \`SchemaError\` / \`TaskNotFoundError\` |

## 端点

| 方法 | 路径 | 用途 |
|---|---|---|
| GET | \`/api/kg/stats\` | 4 label 节点数 |
| GET | \`/api/kg/products\` | 列 Product 节点 (前端 combobox) |
| POST | \`/api/kg/triples\` | 单批三元组 (事务) |
| POST | \`/api/kg/batch\` | 大批量 (后台任务) |
| GET | \`/api/kg/tasks/{id}\` | 任务状态 |

## 加节点/关系

只改 \`configs/knowledge-schema.yaml\`, 不动代码:

\`\`\`yaml
nodes:
  - name: NewNode
    fields:
      - { key: name, type: string, required: true, unique: true }

relations:
  - { name: NEW_REL, from: NewNode, to: Product, cardinality: many_to_one }
\`\`\`

跑 \`uv run pytest tests/test_kg_schema.py -v\` 校验新加内容合法。
```

- [ ] **Step 2: 提交**

```bash
git add docs/knowledge-graph.md
git commit -m "docs(kg): 新增 knowledge-graph.md 模块说明"
```

---

## Task 1.9: PR 1 全量验证

- [ ] **Step 1: 跑后端全量测试**

Run: `uv run pytest tests/ -m "not slow" -v`
Expected: 全过 (含新加的 kg 测试)

- [ ] **Step 2: 跑 ruff**

Run: `uv run ruff check src/rag/kg/ tests/test_kg_*.py`
Expected: 无错误

- [ ] **Step 3: 验证 git log**

Run: `git log --oneline | head -10`
Expected: 看到 8 个新 commit (T1.1 yaml / T1.2 exceptions / T1.3 schema / T1.4 client / T1.5 tasks / T1.6 router / T1.7 mount / T1.8 docs)

- [ ] **Step 4: PR 1 总结**

本 PR 完成:
- \`configs/knowledge-schema.yaml\` (4 节点 5 关系)
- \`src/rag/kg/\` 子包 5 个文件
- 35 个新单测 (schema 10 + client 9 + tasks 10 + router 6)
- 1 个文档 \`docs/knowledge-graph.md\`

下一步: PR 2 — Next.js 4 个空页面 + 顶 nav。

---

# PR 2 · Next.js Shell (4 空页面 + 顶 nav + 布局)

**PR 目标**: 新增 5 个 Next.js 页面 + 顶 nav 加 `/knowledge` 链接 + shadcn/ui 组件补齐; 全部 vitest 绿, 还没接业务。

---

## Task 2.1: 补 shadcn/ui 组件

**Files:**
- Create: `web/components/ui/select.tsx`
- Create: `web/components/ui/textarea.tsx`
- Create: `web/components/ui/tabs.tsx`
- Create: `web/components/ui/dialog.tsx`
- Create: `web/components/ui/dropdown-menu.tsx`
- Create: `web/components/ui/progress.tsx`
- Create: `web/components/ui/skeleton.tsx`
- Create: `web/components/ui/toast.tsx` (基于 sonner)

- [ ] **Step 1: 用 shadcn CLI 装 (用项目默认风格)**

```bash
cd web
bunx shadcn@latest add select textarea tabs dialog dropdown-menu progress skeleton sonner
```

(项目当前用 `bunx` 而非 `npx`, 见 `web/package.json` 脚本; 实际命令按 shadcn 当前版提示调整, 若命令名变了用 `bunx shadcn add ...` 或 `bunx shadcn-ui add ...`)

- [ ] **Step 2: 验证生成**

Run: `ls web/components/ui/`
Expected: 看到新加的 `select.tsx` `textarea.tsx` `tabs.tsx` `dialog.tsx` `dropdown-menu.tsx` `progress.tsx` `skeleton.tsx` `sonner.tsx`

- [ ] **Step 3: 提交**

```bash
git add web/components/ui/
git commit -m "feat(web): 补 shadcn/ui 组件 (select/textarea/tabs/dialog/dropdown-menu/progress/skeleton/sonner)"
```

---

## Task 2.2: 修改顶 nav 加 `/knowledge`

**Files:**
- Modify: `web/app/layout.tsx:8-15`

- [ ] **Step 1: 读 layout 现状**

读 `web/app/layout.tsx` 完整内容。

- [ ] **Step 2: 加 Knowledge 链接**

在现有 `<Link href="/decode">` 后面加:

```tsx
<Link href="/knowledge">Knowledge</Link>
```

- [ ] **Step 3: 提交**

```bash
git add web/app/layout.tsx
git commit -m "feat(web): 顶 nav 加 /knowledge 入口"
```

---

## Task 2.3: `web/app/knowledge/layout.tsx` (空壳)

**Files:**
- Create: `web/app/knowledge/layout.tsx`

- [ ] **Step 1: 写空壳 layout**

```tsx
// Knowledge 模块 layout (2026-06-08)
// 顶部: dataset 切换器 + 环境徽章 + 健康点 (PR 3 实装)
// 内容: 子路由 page

import type { ReactNode } from "react";

export default function KnowledgeLayout({ children }: { children: ReactNode }) {
  return (
    <div className="space-y-6">
      {/* 顶部条 PR 3 实装: <KnowledgeTopBar /> */}
      <div className="rounded-lg border border-dashed bg-muted/30 p-4 text-sm text-muted-foreground">
        知识库总览模块 — 顶部状态条占位 (PR 3 实装)
      </div>
      <div>{children}</div>
    </div>
  );
}
```

- [ ] **Step 2: 提交**

```bash
git add web/app/knowledge/layout.tsx
git commit -m "feat(web): /knowledge layout 壳子"
```

---

## Task 2.4: 4 个空 Tab 页面 (qa / documents / triples / batch) + Dashboard

**Files:**
- Create: `web/app/knowledge/page.tsx`
- Create: `web/app/knowledge/qa/page.tsx`
- Create: `web/app/knowledge/documents/page.tsx`
- Create: `web/app/knowledge/triples/page.tsx`
- Create: `web/app/knowledge/batch/page.tsx`

- [ ] **Step 1: 写 Dashboard 占位**

`web/app/knowledge/page.tsx`:

```tsx
// Dashboard — PR 3 实装统计卡片 + 入口卡
export default function KnowledgeHome() {
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">知识库总览</h1>
      <div className="rounded-lg border border-dashed bg-muted/30 p-8 text-center text-sm text-muted-foreground">
        4 张统计卡片 + 4 个入口卡 — PR 3 实装
      </div>
    </div>
  );
}
```

- [ ] **Step 2: 写 4 个 Tab 占位**

`web/app/knowledge/qa/page.tsx`:

```tsx
// Tab 1 — QA 对录入 — PR 4 实装表单
export default function QAPage() {
  return (
    <div className="space-y-4">
      <h2 className="text-xl font-semibold">录 QA 对 (→ Dify 向量库)</h2>
      <div className="rounded-lg border border-dashed bg-muted/30 p-8 text-center text-sm text-muted-foreground">
        表单 + 最近 20 条 — PR 4 实装
      </div>
    </div>
  );
}
```

`web/app/knowledge/documents/page.tsx`:

```tsx
// Tab 2 — 文档录入 — PR 5 实装三步流程
export default function DocumentsPage() {
  return (
    <div className="space-y-4">
      <h2 className="text-xl font-semibold">传文档 (→ Dify 向量库)</h2>
      <div className="rounded-lg border border-dashed bg-muted/30 p-8 text-center text-sm text-muted-foreground">
        拖拽 + 解析 + 校验 + 提交 — PR 5 实装
      </div>
    </div>
  );
}
```

`web/app/knowledge/triples/page.tsx`:

```tsx
// Tab 3 — 三元组录入 — PR 6 实装表格 + Neo4j 写入
export default function TriplesPage() {
  return (
    <div className="space-y-4">
      <h2 className="text-xl font-semibold">录三元组 (→ Neo4j)</h2>
      <div className="rounded-lg border border-dashed bg-muted/30 p-8 text-center text-sm text-muted-foreground">
        多行可编辑表格 — PR 6 实装
      </div>
    </div>
  );
}
```

`web/app/knowledge/batch/page.tsx`:

```tsx
// Tab 4 — 批量导入 — PR 7 实装任务面板
export default function BatchPage() {
  return (
    <div className="space-y-4">
      <h2 className="text-xl font-semibold">批量导入 (双写 Dify + Neo4j)</h2>
      <div className="rounded-lg border border-dashed bg-muted/30 p-8 text-center text-sm text-muted-foreground">
        活跃任务 + 历史 — PR 7 实装
      </div>
    </div>
  );
}
```

- [ ] **Step 3: 跑前端测试确认不挂**

Run: `cd web && bun run test`
Expected: 全过 (新增的 page 还没写 test)

- [ ] **Step 4: 跑 dev server 手测**

```bash
# 终端 1
uv run python main.py serve --port 8000

# 终端 2
cd web && bun run dev
# 浏览器打开 http://localhost:3000/knowledge
```

Expected: 看到 5 个占位页面, 顶 nav 有 `/knowledge` 链接

- [ ] **Step 5: 提交**

```bash
git add web/app/knowledge/
git commit -m "feat(web): /knowledge 5 个空页面 + dashboard 占位"
```

---

## Task 2.5: PR 2 验证

- [ ] **Step 1: 跑前端测试**

Run: `cd web && bun run test`
Expected: 全过

- [ ] **Step 2: 跑 typecheck**

Run: `cd web && bun run typecheck`
Expected: 无错误

- [ ] **Step 3: 跑 lint**

Run: `cd web && bun run lint`
Expected: 无错误

- [ ] **Step 4: 验证 git log**

Run: `git log --oneline | head -10`
Expected: 看到 4 个新 commit (T2.1 components / T2.2 nav / T2.3 layout / T2.4 pages)

下一步: PR 3 — Dashboard 卡片 + Datasets 客户端 + Dify BFF。

---

# PR 3 · Dashboard + Datasets 客户端 (TS port) + Dify BFF

**PR 目标**: Datasets API 客户端 TypeScript 实现 + Next.js BFF 路由 + Dashboard 4 张统计卡片 + 4 个入口卡 + 顶 nav 状态条。API 全用 msw mock, 浏览器跑通"打开 /knowledge 看到真实数字"。

---

## Task 3.1: 加 npm 依赖 (web/package.json)

**Files:**
- Modify: `web/package.json`

- [ ] **Step 1: 加依赖**

```bash
cd web
bun add swr react-hook-form @hookform/resolvers zod papaparse xlsx react-dropzone
bun add -d @types/papaparse
```

- [ ] **Step 2: 验证 package.json**

Read `web/package.json` 检查 dependencies 段含有 `swr` / `react-hook-form` / `zod` / `papaparse` / `xlsx` / `react-dropzone`。

- [ ] **Step 3: 提交**

```bash
git add web/package.json web/bun.lock
git commit -m "feat(web): 加 swr/react-hook-form/zod/papaparse/xlsx/react-dropzone 依赖"
```

---

## Task 3.2: `web/lib/schema-types.ts` (zod schema 镜像 yaml)

**Files:**
- Create: `web/lib/schema-types.ts`

- [ ] **Step 1: 写 zod schema + TS 类型**

```ts
// 知识图谱 schema 的 zod 镜像 (2026-06-08)
// 跟 configs/knowledge-schema.yaml 同步; yaml 改了同步改这里
// 加节点/关系只需要动 yaml + 这个文件两处

import { z } from "zod";

export const FieldType = z.enum([
  "string",
  "text",
  "enum",
  "ref",
  "url",
  "datetime",
]);
export type FieldType = z.infer<typeof FieldType>;

export const FieldDef = z.object({
  key: z.string(),
  label: z.string(),
  type: FieldType,
  required: z.boolean().optional(),
  unique: z.boolean().optional(),
  multiple: z.boolean().optional(),
  readonly: z.boolean().optional(),
  options: z.array(z.string()).optional(),
  ref_to: z.string().optional(),
});
export type FieldDef = z.infer<typeof FieldDef>;

export const NodeDef = z.object({
  name: z.string(),
  color: z.string().optional(),
  fields: z.array(FieldDef),
});
export type NodeDef = z.infer<typeof NodeDef>;

export const RelationDef = z.object({
  name: z.string(),
  from: z.string(),
  to: z.string(),
  cardinality: z.enum(["many_to_one", "many_to_many", "one_to_one", "one_to_many"]),
});
export type RelationDef = z.infer<typeof RelationDef>;

export const KnowledgeSchema = z.object({
  nodes: z.array(NodeDef),
  relations: z.array(RelationDef),
});
export type KnowledgeSchema = z.infer<typeof KnowledgeSchema>;
```

- [ ] **Step 2: 写对应 vitest (轻量, 验证 schema parse 过)**

`web/lib/schema-types.test.ts`:

```ts
import { describe, it, expect } from "vitest";
import { FieldDef, NodeDef, KnowledgeSchema } from "./schema-types";

describe("schema-types", () => {
  it("parses valid field def", () => {
    const f = FieldDef.parse({ key: "model", label: "型号", type: "string", required: true });
    expect(f.type).toBe("string");
  });

  it("rejects unknown field type", () => {
    expect(() => FieldDef.parse({ key: "x", label: "X", type: "weird" })).toThrow();
  });

  it("parses full schema", () => {
    const s = KnowledgeSchema.parse({
      nodes: [{ name: "Product", fields: [{ key: "model", label: "型号", type: "string" }] }],
      relations: [{ name: "REL", from: "Product", to: "Product", cardinality: "many_to_one" }],
    });
    expect(s.nodes[0].name).toBe("Product");
  });
});
```

- [ ] **Step 3: 跑测试**

Run: `cd web && bun run test -- schema-types`
Expected: 3 PASS

- [ ] **Step 4: 提交**

```bash
git add web/lib/schema-types.ts web/lib/schema-types.test.ts
git commit -m "feat(web): zod schema 镜像 yaml (KnowledgeSchema)"
```

---

## Task 3.3: `web/lib/dify-datasets.ts` (TS port) + 测试

**Files:**
- Create: `web/lib/dify-datasets.ts`
- Create: `web/lib/dify-datasets.test.ts`

- [ ] **Step 1: 加 msw 依赖 (test only)**

```bash
cd web
bun add -d msw
```

- [ ] **Step 2: 写 msw handlers + Datasets 客户端**

`web/lib/dify-datasets.ts`:

```ts
// Dify Datasets API TS 客户端 (2026-06-08)
// 服务端调用 (BFF route handler 里), 凭据在 server env 不进 bundle

const BASE = process.env.DIFY_BASE_URL ?? "http://localhost/v1";
const API_KEY = process.env.DIFY_API_KEY ?? "";

export type IndexingMode = "high_quality" | "economy";

export interface Dataset {
  id: string;
  name: string;
  description?: string;
  document_count?: number;
  word_count?: number;
}

export interface Document {
  id: string;
  dataset_id: string;
  name: string;
  indexing_status: "queued" | "indexing" | "completed" | "error";
  error?: string;
}

export interface RetrievalHit {
  content: string;
  score: number;
  document_id: string;
  document_name: string;
}

class DifyApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = "DifyApiError";
  }
}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: {
      Authorization: `Bearer ${API_KEY}`,
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
  });
  if (!res.ok) {
    const text = await res.text();
    throw new DifyApiError(res.status, text);
  }
  return (await res.json()) as T;
}

export const DifyDatasets = {
  listDatasets: (): Promise<Dataset[]> =>
    call<Dataset[]>("/datasets?limit=100"),

  createDocumentByText: (
    datasetId: string,
    name: string,
    text: string,
    indexingMode: IndexingMode = "high_quality",
  ): Promise<Document> =>
    call<Document>(`/datasets/${datasetId}/document/create_by_text`, {
      method: "POST",
      body: JSON.stringify({ name, text, indexing_mode: indexingMode, doc_form: "text_model" }),
    }),

  listDocuments: (datasetId: string): Promise<{ data: Document[] }> =>
    call<{ data: Document[] }>(`/datasets/${datasetId}/documents?limit=100`),

  retrieve: (datasetId: string, query: string, topK = 5): Promise<{ records: RetrievalHit[] }> =>
    call<{ records: RetrievalHit[] }>(`/datasets/${datasetId}/retrieve`, {
      method: "POST",
      body: JSON.stringify({ query, top_k: topK, retrieval_mode: "hybrid_search" }),
    }),

  healthCheck: async (): Promise<boolean> => {
    try {
      await this.listDatasets();
      return true;
    } catch {
      return false;
    }
  },
};

export { DifyApiError };
```

- [ ] **Step 3: 写测试 (用 msw 或直接 mock global.fetch)**

`web/lib/dify-datasets.test.ts`:

```ts
// 端到端验证客户端方法 → fetch 调用 + JSON parse
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { DifyDatasets } from "./dify-datasets";

describe("DifyDatasets", () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    process.env.DIFY_BASE_URL = "https://dify.test";
    process.env.DIFY_API_KEY = "test-key";
    fetchMock = vi.fn();
    globalThis.fetch = fetchMock as unknown as typeof fetch;
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("listDatasets 走 GET /datasets", async () => {
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => [{ id: "ds1", name: "FAQ" }],
    });
    const out = await DifyDatasets.listDatasets();
    expect(out[0].id).toBe("ds1");
    expect(fetchMock.mock.calls[0][0]).toBe("https://dify.test/datasets?limit=100");
  });

  it("createDocumentByText 走 POST 带 indexing_mode", async () => {
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ id: "doc1", dataset_id: "ds1", name: "Q1", indexing_status: "queued" }),
    });
    const out = await DifyDatasets.createDocumentByText("ds1", "Q1", "Q? A!", "high_quality");
    expect(out.indexing_status).toBe("queued");
    const init = fetchMock.mock.calls[0][1];
    expect(init.method).toBe("POST");
    const body = JSON.parse(init.body);
    expect(body.indexing_mode).toBe("high_quality");
  });

  it("listDocuments 走 GET /datasets/{id}/documents", async () => {
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ data: [{ id: "doc1", dataset_id: "ds1", name: "Q1", indexing_status: "completed" }] }),
    });
    const out = await DifyDatasets.listDocuments("ds1");
    expect(out.data[0].indexing_status).toBe("completed");
  });

  it("retrieve 走 POST /datasets/{id}/retrieve", async () => {
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ records: [{ content: "hit", score: 0.9, document_id: "doc1", document_name: "Q1" }] }),
    });
    const out = await DifyDatasets.retrieve("ds1", "1LE0001", 3);
    expect(out.records[0].content).toBe("hit");
    const body = JSON.parse(fetchMock.mock.calls[0][1].body);
    expect(body.top_k).toBe(3);
  });

  it("非 2xx 抛 DifyApiError", async () => {
    fetchMock.mockResolvedValueOnce({ ok: false, status: 401, text: async () => "unauth" });
    await expect(DifyDatasets.listDatasets()).rejects.toThrow(/unauth/);
  });
});
```

- [ ] **Step 4: 跑测试**

Run: `cd web && bun run test -- dify-datasets`
Expected: 5 PASS

- [ ] **Step 5: 提交**

```bash
git add web/lib/dify-datasets.ts web/lib/dify-datasets.test.ts web/package.json web/bun.lock
git commit -m "feat(web): DifyDatasets 客户端 (TS port) + 5 个测试"
```

---

## Task 3.4: BFF 路由 — `/api/knowledge/health` `/api/knowledge/schema` `/api/knowledge/stats` `/api/knowledge/datasets`

**Files:**
- Create: `web/app/api/knowledge/health/route.ts`
- Create: `web/app/api/knowledge/schema/route.ts`
- Create: `web/app/api/knowledge/stats/route.ts`
- Create: `web/app/api/knowledge/datasets/route.ts`

- [ ] **Step 1: health route**

`web/app/api/knowledge/health/route.ts`:

```ts
// Dify 健康检查 (BFF 入口)
import { NextResponse } from "next/server";
import { DifyDatasets } from "@/lib/dify-datasets";

export async function GET() {
  const ok = await DifyDatasets.healthCheck();
  return NextResponse.json({ ok, ts: Date.now() });
}
```

- [ ] **Step 2: schema route**

`web/app/api/knowledge/schema/route.ts`:

```ts
// BFF 解析 yaml 的实装方式: ② BFF 调 FastAPI `/api/kg/schema` (复用, 推荐)
// 不用在 web/ 放 yaml 副本 (避免双源不同步)
import { NextResponse } from "next/server";
import { readFile } from "node:fs/promises";
import path from "node:path";

const FASTAPI = process.env.FASTAPI_BASE ?? "http://localhost:8000";
export const dynamic = "force-dynamic";

export async function GET() {
  // 直接调 FastAPI /api/kg/schema (yaml 在仓库根 configs/, 由 FastAPI 加载)
  const r = await fetch(`${FASTAPI}/api/kg/schema`);
  if (!r.ok) return NextResponse.json({ error: "schema 加载失败" }, { status: 502 });
  return NextResponse.json(await r.json());
}
```

```ts
import { NextResponse } from "next/server";

const FASTAPI = process.env.FASTAPI_BASE ?? "http://localhost:8000";

export async function GET() {
  const res = await fetch(`${FASTAPI}/api/kg/schema`);
  if (!res.ok) {
    return NextResponse.json({ error: "schema 加载失败" }, { status: 502 });
  }
  return NextResponse.json(await res.json());
}
```

- [ ] **Step 3: stats route**

`web/app/api/knowledge/stats/route.ts`:

```ts
// 聚合 4 卡片数据
// Neo4j 部分 → FastAPI /api/kg/stats
// Dify 部分 → DifyDatasets.listDatasets() + 各 dataset 的文档数
import { NextResponse } from "next/server";
import { DifyDatasets } from "@/lib/dify-datasets";

const FASTAPI = process.env.FASTAPI_BASE ?? "http://localhost:8000";

export const revalidate = 30;  // 30s 缓存

export async function GET() {
  // Neo4j label 计数
  let neo4jCounts: Record<string, number> = {};
  try {
    const r = await fetch(`${FASTAPI}/api/kg/stats`, { next: { revalidate: 30 } });
    neo4jCounts = await r.json();
  } catch {
    neo4jCounts = {};
  }

  // Dify: dataset 数 + 各 dataset 文档数
  let difyDatasets: Awaited<ReturnType<typeof DifyDatasets.listDatasets>> = [];
  let difyDocTotal = 0;
  try {
    difyDatasets = await DifyDatasets.listDatasets();
    // 简化: 只读 dataset 自身 document_count 字段
    difyDocTotal = difyDatasets.reduce((s, d) => s + (d.document_count ?? 0), 0);
  } catch {
    difyDatasets = [];
  }

  return NextResponse.json({
    neo4j: {
      Product: neo4jCounts.Product ?? 0,
      Series: neo4jCounts.Series ?? 0,
      Document: neo4jCounts.Document ?? 0,
      QAPair: neo4jCounts.QAPair ?? 0,
    },
    dify: {
      datasets: difyDatasets.length,
      documents: difyDocTotal,
    },
  });
}
```

- [ ] **Step 4: datasets route**

`web/app/api/knowledge/datasets/route.ts`:

```ts
import { NextResponse } from "next/server";
import { DifyDatasets } from "@/lib/dify-datasets";

export const revalidate = 30;

export async function GET() {
  try {
    const datasets = await DifyDatasets.listDatasets();
    return NextResponse.json(datasets);
  } catch (e) {
    return NextResponse.json({ error: String(e) }, { status: 502 });
  }
}
```

- [ ] **Step 5: 给 FastAPI 加 `/api/kg/schema`**

Modify `src/rag/kg/router.py` 加端点 (在 `stats` 之后):

```python
from pathlib import Path as _Path
import yaml as _yaml
from .. import kg as _kg_pkg  # 找 REPO_ROOT

# 在路由文件顶部加:
_REPO_ROOT = _Path(__file__).resolve().parents[3]
_SCHEMA_PATH = _REPO_ROOT / "configs" / "knowledge-schema.yaml"

@router.get("/schema")
def get_schema() -> dict:
    """暴露 yaml schema 给 BFF / 前端"""
    return _kg_pkg.schema.load_schema(str(_SCHEMA_PATH))
```

- [ ] **Step 6: 跑后端 + 前端测试**

Run: `uv run pytest tests/test_kg_schema.py tests/test_kg_router.py -v`
Expected: 全过

Run: `cd web && bun run typecheck`
Expected: 无错误

- [ ] **Step 7: 提交**

```bash
git add web/app/api/knowledge/ src/rag/kg/router.py
git commit -m "feat(web+kg): BFF 路由 health/schema/stats/datasets"
```

---

## Task 3.5: `HealthDot` `EnvBadge` `DatasetSwitcher` 组件

**Files:**
- Create: `web/components/knowledge/HealthDot.tsx`
- Create: `web/components/knowledge/EnvBadge.tsx`
- Create: `web/components/knowledge/DatasetSwitcher.tsx`

- [ ] **Step 1: 写 HealthDot + 测试**

`web/components/knowledge/HealthDot.tsx`:

```tsx
// Dify 健康点 (绿/红 dot + 鼠标悬停提示)
import useSWR from "swr";

const fetcher = (url: string) => fetch(url).then((r) => r.json());

export function HealthDot() {
  const { data, isLoading } = useSWR<{ ok: boolean }>("/api/knowledge/health", fetcher, {
    refreshInterval: 30_000,
  });
  const color = isLoading ? "bg-gray-400" : data?.ok ? "bg-emerald-500" : "bg-rose-500";
  return (
    <span
      title={data?.ok ? "Dify 健康" : "Dify 不可达"}
      className={`inline-block h-2.5 w-2.5 rounded-full ${color}`}
      data-testid="health-dot"
    />
  );
}
```

`web/components/knowledge/HealthDot.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { HealthDot } from "./HealthDot";

describe("HealthDot", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("健康时显示绿色 dot", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      json: async () => ({ ok: true }),
    }) as unknown as typeof fetch;
    render(<HealthDot />);
    const dot = await screen.findByTestId("health-dot");
    expect(dot.className).toContain("bg-emerald-500");
  });

  it("不可达时显示红色 dot", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      json: async () => ({ ok: false }),
    }) as unknown as typeof fetch;
    render(<HealthDot />);
    const dot = await screen.findByTestId("health-dot");
    expect(dot.className).toContain("bg-rose-500");
  });
});
```

- [ ] **Step 2: 写 EnvBadge**

`web/components/knowledge/EnvBadge.tsx`:

```tsx
// 环境标识徽章 (DEV / STAGING / PROD)
// 从 process.env.NEXT_PUBLIC_ENV 读, 默认 "DEV"
import { Badge } from "@/components/ui/badge";

const ENV = process.env.NEXT_PUBLIC_ENV ?? "DEV";

const variant: Record<string, string> = {
  DEV: "bg-amber-100 text-amber-800",
  STAGING: "bg-blue-100 text-blue-800",
  PROD: "bg-rose-100 text-rose-800",
};

export function EnvBadge() {
  return <Badge className={variant[ENV] ?? variant.DEV}>{ENV}</Badge>;
}
```

- [ ] **Step 3: 写 DatasetSwitcher (下拉选 dataset)**

`web/components/knowledge/DatasetSwitcher.tsx`:

```tsx
"use client";
// 选当前 Dify dataset, 写到 localStorage; 后续 PR 4/5 表单读这个
import { useEffect, useState } from "react";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";

interface Dataset { id: string; name: string }

export function DatasetSwitcher() {
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [current, setCurrent] = useState<string>("");

  useEffect(() => {
    fetch("/api/knowledge/datasets").then((r) => r.json()).then((d) => {
      setDatasets(d);
      const saved = localStorage.getItem("kg.dataset_id") ?? "";
      setCurrent(saved || d[0]?.id || "");
    });
  }, []);

  const onChange = (id: string) => {
    setCurrent(id);
    localStorage.setItem("kg.dataset_id", id);
    window.dispatchEvent(new CustomEvent("kg:dataset-changed", { detail: id }));
  };

  return (
    <Select value={current} onValueChange={onChange}>
      <SelectTrigger className="w-64" data-testid="dataset-switcher">
        <SelectValue placeholder="选 dataset" />
      </SelectTrigger>
      <SelectContent>
        {datasets.map((d) => (
          <SelectItem key={d.id} value={d.id}>{d.name}</SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
```

- [ ] **Step 4: 跑测试**

Run: `cd web && bun run test -- HealthDot`
Expected: 2 PASS

- [ ] **Step 5: 提交**

```bash
git add web/components/knowledge/
git commit -m "feat(web): HealthDot/EnvBadge/DatasetSwitcher 顶 nav 状态条"
```

---

## Task 3.6: 把状态条接到 layout

**Files:**
- Modify: `web/app/knowledge/layout.tsx`

- [ ] **Step 1: 替换 layout 内容**

把 `web/app/knowledge/layout.tsx` 改成:

```tsx
import type { ReactNode } from "react";
import { HealthDot } from "@/components/knowledge/HealthDot";
import { EnvBadge } from "@/components/knowledge/EnvBadge";
import { DatasetSwitcher } from "@/components/knowledge/DatasetSwitcher";

export default function KnowledgeLayout({ children }: { children: ReactNode }) {
  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-4 rounded-lg border bg-card px-4 py-3">
        <span className="text-sm font-medium">知识库模块</span>
        <div className="ml-auto flex items-center gap-3">
          <DatasetSwitcher />
          <EnvBadge />
          <HealthDot />
        </div>
      </div>
      <div>{children}</div>
    </div>
  );
}
```

- [ ] **Step 2: 跑 typecheck + 启动 dev server 手测**

Run: `cd web && bun run typecheck`
Expected: 无错误

浏览器打开 `http://localhost:3000/knowledge`, 看到 dataset 切换器 + 环境徽章 + 健康点。

- [ ] **Step 3: 提交**

```bash
git add web/app/knowledge/layout.tsx
git commit -m "feat(web): /knowledge layout 接状态条"
```

---

## Task 3.7: Dashboard 统计卡片 + 入口卡

**Files:**
- Modify: `web/app/knowledge/page.tsx`
- Create: `web/components/knowledge/StatCard.tsx`
- Create: `web/components/knowledge/EntryCard.tsx`

- [ ] **Step 1: 写 StatCard + EntryCard**

`web/components/knowledge/StatCard.tsx`:

```tsx
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export function StatCard({
  label, value, hint, gradient,
}: { label: string; value: number | string; hint?: string; gradient: string }) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm text-muted-foreground">{label}</CardTitle>
      </CardHeader>
      <CardContent>
        <div className={`bg-gradient-to-br ${gradient} bg-clip-text text-3xl font-bold text-transparent`}>
          {value}
        </div>
        {hint && <p className="mt-1 text-xs text-muted-foreground">{hint}</p>}
      </CardContent>
    </Card>
  );
}
```

`web/components/knowledge/EntryCard.tsx`:

```tsx
import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export function EntryCard({
  href, icon, title, desc,
}: { href: string; icon: string; title: string; desc: string }) {
  return (
    <Link href={href}>
      <Card className="transition hover:border-primary hover:shadow-md">
        <CardHeader>
          <CardTitle className="text-base">
            <span className="mr-2">{icon}</span>{title}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">{desc}</p>
        </CardContent>
      </Card>
    </Link>
  );
}
```

- [ ] **Step 2: 写 Dashboard page**

`web/app/knowledge/page.tsx`:

```tsx
"use client";
// 知识库 Dashboard (2026-06-08)
import useSWR from "swr";
import { StatCard } from "@/components/knowledge/StatCard";
import { EntryCard } from "@/components/knowledge/EntryCard";

const fetcher = (url: string) => fetch(url).then((r) => r.json());

interface StatsResponse {
  neo4j: { Product: number; Series: number; Document: number; QAPair: number };
  dify: { datasets: number; documents: number };
}

export default function KnowledgeHome() {
  const { data, isLoading, error } = useSWR<StatsResponse>("/api/knowledge/stats", fetcher, {
    refreshInterval: 30_000,
  });

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">知识库总览</h1>

      {error && (
        <div className="rounded-lg border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">
          加载统计失败: {String(error)}
        </div>
      )}

      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <StatCard
          label="Dify 文档"
          value={isLoading ? "—" : (data?.dify.documents ?? 0)}
          hint={`${data?.dify.datasets ?? 0} 个 dataset`}
          gradient="from-blue-600 to-violet-600"
        />
        <StatCard
          label="QA 对"
          value={isLoading ? "—" : (data?.neo4j.QAPair ?? 0)}
          gradient="from-orange-500 to-pink-500"
        />
        <StatCard
          label="产品节点"
          value={isLoading ? "—" : (data?.neo4j.Product ?? 0)}
          gradient="from-blue-500 to-cyan-500"
        />
        <StatCard
          label="关系"
          value={isLoading ? "—" : ((data?.neo4j.Product ?? 0) + (data?.neo4j.Series ?? 0))}
          hint="实体-关系"
          gradient="from-emerald-500 to-teal-500"
        />
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-4">
        <EntryCard href="/knowledge/qa" icon="📝" title="录 QA 对" desc="表单写入 Dify" />
        <EntryCard href="/knowledge/documents" icon="📄" title="传文档" desc="Excel / JSON" />
        <EntryCard href="/knowledge/triples" icon="🔗" title="录三元组" desc="实体-关系 → Neo4j" />
        <EntryCard href="/knowledge/batch" icon="📦" title="批量导入" desc="后台任务" />
      </div>
    </div>
  );
}
```

- [ ] **Step 3: 跑测试 + 启动手测**

Run: `cd web && bun run typecheck`
Expected: 无错误

浏览器打开 `/knowledge`, 看到 4 张统计卡 + 4 个入口卡。

- [ ] **Step 4: 提交**

```bash
git add web/app/knowledge/page.tsx web/components/knowledge/StatCard.tsx web/components/knowledge/EntryCard.tsx
git commit -m "feat(web): Dashboard 4 统计卡 + 4 入口卡"
```

---

## Task 3.8: PR 3 验证

- [ ] **Step 1: 跑所有测试**

Run: `uv run pytest tests/ -m "not slow" -q && cd web && bun run test`
Expected: 后端全过, 前端全过

- [ ] **Step 2: 跑 lint + typecheck**

Run: `cd web && bun run lint && bun run typecheck`
Expected: 无错误

- [ ] **Step 3: 端到端手测**

```bash
# 终端 1: FastAPI
uv run python main.py serve --port 8000
# 终端 2: Next.js
cd web && bun run dev
# 浏览器: http://localhost:3000/knowledge
```

Expected: 看到 4 张统计卡 (数字来自 Neo4j + Dify), 健康点状态对 (绿/红), dataset 切换器有内容。

- [ ] **Step 4: 验证 git log**

Run: `git log --oneline | head -10`
Expected: 看到 7 个新 commit (T3.1 deps / T3.2 zod / T3.3 dify / T3.4 bff / T3.5 nav / T3.6 layout / T3.7 dashboard)

下一步: PR 4 — Tab 1 (QA) 完整流程。

---

# PR 4 · Tab 1 — QA 对录入 (→ Dify 向量库)

**PR 目标**: `/knowledge/qa` 页支持填表 + 校验 + 草稿保存 + 立即测试 retriever。涉及 `web/app/api/knowledge/qa/*` BFF 路由、QA 表单组件、retriever 自测 Dialog。

---

## Task 4.1: BFF `/api/knowledge/qa` POST 路由

**Files:**
- Create: `web/app/api/knowledge/qa/route.ts`

- [ ] **Step 1: 写 POST handler**

```ts
// 创建 QA 对 (BFF: 调 Dify createDocumentByText, 可选同步 Neo4j QAPair)
import { NextRequest, NextResponse } from "next/server";
import { DifyDatasets } from "@/lib/dify-datasets";

interface QAPayload {
  dataset_id: string;
  question: string;
  answer: string;
  tags?: string[];
  sync_to_neo4j?: boolean;
}

const FASTAPI = process.env.FASTAPI_BASE ?? "http://localhost:8000";

export async function POST(req: NextRequest) {
  const body = (await req.json()) as QAPayload;
  if (!body.dataset_id || !body.question || !body.answer) {
    return NextResponse.json({ error: "dataset_id / question / answer 必填" }, { status: 400 });
  }

  // 1) 调 Dify (text 字段 = question + "\n\n" + answer)
  const text = `Q: ${body.question}\nA: ${body.answer}${body.tags?.length ? "\nTags: " + body.tags.join(", ") : ""}`;
  const name = `qa-${Date.now()}`;

  let difyDoc;
  try {
    difyDoc = await DifyDatasets.createDocumentByText(body.dataset_id, name, text, "high_quality");
  } catch (e) {
    return NextResponse.json({ error: `Dify 失败: ${String(e)}` }, { status: 502 });
  }

  // 2) 可选同步 Neo4j
  let neo4jId: string | undefined;
  if (body.sync_to_neo4j) {
    try {
      const r = await fetch(`${FASTAPI}/api/kg/triples`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          rows: [{
            from_label: "QAPair", from_key: "question", from_value: body.question,
            rel_type: "ABOUT",
            to_label: "Product", to_key: "model", to_value: body.tags?.[0] ?? "unknown",
            properties: { answer: body.answer, tags: body.tags ?? [] },
          }],
        }),
      });
      if (r.ok) neo4jId = "synced";
    } catch {
      // Neo4j 失败不阻塞 Dify 写入
    }
  }

  return NextResponse.json({ dify_doc: difyDoc, neo4j_synced: !!neo4jId });
}
```

- [ ] **Step 2: GET handler (列最近 20 条)**

在同一文件 `route.ts` 加 GET 方法 (替换文件):

```ts
// 创建/列 QA 对
import { NextRequest, NextResponse } from "next/server";
import { DifyDatasets } from "@/lib/dify-datasets";

interface QAPayload {
  dataset_id: string;
  question: string;
  answer: string;
  tags?: string[];
  sync_to_neo4j?: boolean;
}

const FASTAPI = process.env.FASTAPI_BASE ?? "http://localhost:8000";

export async function POST(req: NextRequest) {
  const body = (await req.json()) as QAPayload;
  if (!body.dataset_id || !body.question || !body.answer) {
    return NextResponse.json({ error: "dataset_id / question / answer 必填" }, { status: 400 });
  }

  const text = `Q: ${body.question}\nA: ${body.answer}${body.tags?.length ? "\nTags: " + body.tags.join(", ") : ""}`;
  const name = `qa-${Date.now()}`;

  try {
    const difyDoc = await DifyDatasets.createDocumentByText(body.dataset_id, name, text, "high_quality");
    return NextResponse.json({ dify_doc: difyDoc, neo4j_synced: false });
  } catch (e) {
    return NextResponse.json({ error: `Dify 失败: ${String(e)}` }, { status: 502 });
  }
}

export async function GET(req: NextRequest) {
  const dataset_id = req.nextUrl.searchParams.get("dataset_id") ?? "";
  if (!dataset_id) {
    return NextResponse.json({ error: "dataset_id 必填" }, { status: 400 });
  }
  try {
    const out = await DifyDatasets.listDocuments(dataset_id);
    // 过滤出 qa- 前缀的 doc
    const items = out.data.filter((d) => d.name.startsWith("qa-"));
    return NextResponse.json({ items });
  } catch (e) {
    return NextResponse.json({ error: String(e) }, { status: 502 });
  }
}
```

- [ ] **Step 3: 跑 typecheck**

Run: `cd web && bun run typecheck`
Expected: 无错误

- [ ] **Step 4: 提交**

```bash
git add web/app/api/knowledge/qa/route.ts
git commit -m "feat(web): BFF /api/knowledge/qa POST/GET (Dify 写 + 列)"
```

---

## Task 4.2: BFF `/api/knowledge/qa/retrieve` 路由 (retriever 自测)

**Files:**
- Create: `web/app/api/knowledge/qa/retrieve/route.ts`

- [ ] **Step 1: 写 handler**

```ts
// Retriever 自测: 用问题调 Dify retrieve, 返 top 3
import { NextRequest, NextResponse } from "next/server";
import { DifyDatasets } from "@/lib/dify-datasets";

export async function POST(req: NextRequest) {
  const { dataset_id, question, top_k = 3 } = (await req.json()) as {
    dataset_id: string; question: string; top_k?: number;
  };
  if (!dataset_id || !question) {
    return NextResponse.json({ error: "dataset_id / question 必填" }, { status: 400 });
  }
  try {
    const out = await DifyDatasets.retrieve(dataset_id, question, top_k);
    return NextResponse.json(out);
  } catch (e) {
    return NextResponse.json({ error: String(e) }, { status: 502 });
  }
}
```

- [ ] **Step 2: 提交**

```bash
git add web/app/api/knowledge/qa/retrieve/route.ts
git commit -m "feat(web): BFF /api/knowledge/qa/retrieve (Dify retriever)"
```

---

## Task 4.3: QA 表单 + 草稿 (localStorage) + 提交 + 测试

**Files:**
- Modify: `web/app/knowledge/qa/page.tsx`

- [ ] **Step 1: 写完整 QA 页**

```tsx
"use client";
// QA 对录入 (2026-06-08)
import { useEffect, useState } from "react";
import useSWR from "swr";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger,
} from "@/components/ui/dialog";

const fetcher = (u: string) => fetch(u).then((r) => r.json());

const QASchema = z.object({
  question: z.string().min(2, "问题至少 2 字"),
  answer: z.string().min(2, "答案至少 2 字"),
  tags: z.string().optional(),  // comma 分隔
  sync_to_neo4j: z.boolean().default(false),
});
type QAForm = z.infer<typeof QASchema>;

const DRAFT_KEY = "kg.qa.draft";

export default function QAPage() {
  const [datasetId, setDatasetId] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submitResult, setSubmitResult] = useState<{ ok: boolean; msg: string } | null>(null);
  const [testResult, setTestResult] = useState<{ records: { content: string; score: number; document_name: string }[] } | null>(null);

  const { register, handleSubmit, formState: { errors }, reset, getValues, setValue, watch } = useForm<QAForm>({
    resolver: zodResolver(QASchema),
    defaultValues: { sync_to_neo4j: false, tags: "" },
  });

  // 选 dataset
  useEffect(() => {
    const id = localStorage.getItem("kg.dataset_id") ?? "";
    setDatasetId(id);
  }, []);

  // 加载草稿
  useEffect(() => {
    const saved = localStorage.getItem(DRAFT_KEY);
    if (saved) {
      try { reset(JSON.parse(saved)); } catch { /* ignore */ }
    }
  }, [reset]);

  // 草稿实时存
  useEffect(() => {
    const sub = watch((v) => localStorage.setItem(DRAFT_KEY, JSON.stringify(v)));
    return () => sub.unsubscribe();
  }, [watch]);

  // 列最近 20 条
  const { data: list, mutate } = useSWR<{ items: { id: string; name: string; indexing_status: string }[] }>(
    datasetId ? `/api/knowledge/qa?dataset_id=${datasetId}` : null,
    fetcher,
    { refreshInterval: 5000 },
  );

  const onSubmit = async (data: QAForm) => {
    if (!datasetId) {
      setSubmitResult({ ok: false, msg: "请先在顶部选 dataset" });
      return;
    }
    setSubmitting(true);
    try {
      const tagsArr = data.tags ? data.tags.split(",").map((t) => t.trim()).filter(Boolean) : [];
      const r = await fetch("/api/knowledge/qa", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ dataset_id: datasetId, question: data.question, answer: data.answer, tags: tagsArr, sync_to_neo4j: data.sync_to_neo4j }),
      });
      if (!r.ok) {
        const e = await r.json();
        setSubmitResult({ ok: false, msg: e.error ?? `HTTP ${r.status}` });
      } else {
        setSubmitResult({ ok: true, msg: "已写入 Dify" });
        localStorage.removeItem(DRAFT_KEY);
        reset({ question: "", answer: "", tags: "", sync_to_neo4j: false });
        mutate();
      }
    } finally {
      setSubmitting(false);
    }
  };

  const onTest = async () => {
    const question = getValues("question");
    if (!question || !datasetId) return;
    const r = await fetch("/api/knowledge/qa/retrieve", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ dataset_id: datasetId, question, top_k: 3 }),
    });
    if (r.ok) setTestResult(await r.json());
  };

  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-5">
      <div className="lg:col-span-3 space-y-4">
        <Card>
          <CardHeader><CardTitle>新增 QA 对</CardTitle></CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit(onSubmit)} className="space-y-3">
              <div>
                <label className="text-sm font-medium">问题 *</label>
                <Textarea {...register("question")} rows={3} data-testid="qa-question" />
                {errors.question && <p className="text-xs text-rose-600">{errors.question.message}</p>}
              </div>
              <div>
                <label className="text-sm font-medium">答案 *</label>
                <Textarea {...register("answer")} rows={5} data-testid="qa-answer" />
                {errors.answer && <p className="text-xs text-rose-600">{errors.answer.message}</p>}
              </div>
              <div>
                <label className="text-sm font-medium">标签 (逗号分隔)</label>
                <Input {...register("tags")} placeholder="电机, 选型, 1LE 系列" />
              </div>
              <div className="flex items-center gap-2">
                <input id="sync" type="checkbox" {...register("sync_to_neo4j")} />
                <label htmlFor="sync" className="text-sm">同步到 Neo4j (QAPair + ABOUT)</label>
              </div>
              {submitResult && (
                <div className={`rounded p-2 text-sm ${submitResult.ok ? "bg-emerald-50 text-emerald-800" : "bg-rose-50 text-rose-800"}`}>
                  {submitResult.msg}
                </div>
              )}
              <div className="flex gap-2">
                <Button type="submit" disabled={submitting} data-testid="qa-submit">
                  {submitting ? "提交中…" : "录入 Dify"}
                </Button>
                <Dialog>
                  <DialogTrigger asChild>
                    <Button type="button" variant="outline" onClick={onTest} data-testid="qa-test">
                      录入 + 立即测试
                    </Button>
                  </DialogTrigger>
                  <DialogContent>
                    <DialogHeader><DialogTitle>Retriever 自测结果</DialogTitle></DialogHeader>
                    {testResult ? (
                      <ul className="space-y-2 text-sm">
                        {testResult.records.map((r, i) => (
                          <li key={i} className="rounded border p-2">
                            <div className="text-xs text-muted-foreground">
                              {r.document_name} · score {r.score.toFixed(3)}
                            </div>
                            <div>{r.content}</div>
                          </li>
                        ))}
                      </ul>
                    ) : <p className="text-sm text-muted-foreground">未命中</p>}
                  </DialogContent>
                </Dialog>
              </div>
            </form>
          </CardContent>
        </Card>
      </div>

      <div className="lg:col-span-2 space-y-4">
        <Card>
          <CardHeader><CardTitle>最近 20 条</CardTitle></CardHeader>
          <CardContent>
            {!datasetId && <p className="text-sm text-muted-foreground">先选顶部 dataset</p>}
            {list && (
              <ul className="space-y-2 text-sm">
                {list.items.slice(0, 20).map((d) => (
                  <li key={d.id} className="rounded border p-2">
                    <div className="font-medium">{d.name}</div>
                    <div className="text-xs text-muted-foreground">状态: {d.indexing_status}</div>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: 写 page test**

`web/app/knowledge/qa/page.test.tsx`:

```tsx
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import QAPage from "./page";

// mock SWR + fetch
const fetchMock = vi.fn();
beforeEach(() => {
  globalThis.fetch = fetchMock as unknown as typeof fetch;
  localStorage.clear();
  fetchMock.mockReset();
});

describe("QA page", () => {
  it("未选 dataset 时提示", async () => {
    render(<QAPage />);
    expect(screen.getByText(/先选顶部 dataset/)).toBeInTheDocument();
  });

  it("提交空表单显示 zod 错误", async () => {
    localStorage.setItem("kg.dataset_id", "ds1");
    render(<QAPage />);
    fireEvent.click(screen.getByTestId("qa-submit"));
    await waitFor(() => {
      expect(screen.getAllByText(/至少 2 字/).length).toBeGreaterThan(0);
    });
  });

  it("提交成功后清表单 + 提示", async () => {
    localStorage.setItem("kg.dataset_id", "ds1");
    fetchMock
      .mockResolvedValueOnce({ ok: true, json: async () => ({ items: [] }) })  // 列表
      .mockResolvedValueOnce({                                          // 提交
        ok: true, json: async () => ({ dify_doc: { id: "doc1" }, neo4j_synced: false }),
      });
    render(<QAPage />);
    fireEvent.change(screen.getByTestId("qa-question"), { target: { value: "1LE0001 是什么?" } });
    fireEvent.change(screen.getByTestId("qa-answer"), { target: { value: "1LE0001 是西门子低压电机" } });
    fireEvent.click(screen.getByTestId("qa-submit"));
    await waitFor(() => expect(screen.getByText(/已写入 Dify/)).toBeInTheDocument());
  });
});
```

- [ ] **Step 3: 跑测试**

Run: `cd web && bun run test -- qa/page`
Expected: 3 PASS

- [ ] **Step 4: typecheck**

Run: `cd web && bun run typecheck`
Expected: 无错误

- [ ] **Step 5: 提交**

```bash
git add web/app/knowledge/qa/
git commit -m "feat(web): Tab QA 表单 + 草稿 + retriever 自测 dialog"
```

---

## Task 4.4: PR 4 验证

- [ ] **Step 1: 跑所有测试**

Run: `cd web && bun run test && uv run pytest tests/ -m "not slow" -q`
Expected: 全过

- [ ] **Step 2: typecheck + lint**

Run: `cd web && bun run typecheck && bun run lint`
Expected: 无错误

- [ ] **Step 3: 端到端手测**

启动 dev server, 浏览器打开 `/knowledge/qa`:
1. 顶部选 dataset
2. 填问题/答案, 点"录入 Dify"
3. Toast "已写入 Dify"
4. 看 Dify 控制台, 应出现新 doc
5. 关浏览器, 重开, 草稿自动恢复

- [ ] **Step 4: git log**

Run: `git log --oneline | head -10`
Expected: 看到 3 个新 commit (T4.1 BFF qa / T4.2 retrieve / T4.3 page)

下一步: PR 5 — Tab 2 (Documents) 三步流程。

---

# PR 5 · Tab 2 — 文档上传 (Excel / JSON) + 模板

**PR 目标**: `/knowledge/documents` 三步流程 (拖拽 → 解析 → 校验 → 提交) + 模板下载。

---

## Task 5.1: Excel 模板生成后端

**Files:**
- Create: `src/rag/kg/templates.py`
- Create: `tests/test_kg_templates.py`

- [ ] **Step 1: 加 openpyxl 依赖**

Read `pyproject.toml` dependencies 段, 加 `openpyxl>=3.1.0`。

- [ ] **Step 2: 写红测试**

`tests/test_kg_templates.py`:

```python
"""kg.templates Excel 模板生成测试"""
import io

from src.rag.kg import templates


def test_build_qa_excel_returns_bytesio():
    out = templates.build_qa_excel()
    assert isinstance(out, io.BytesIO)
    # xlsx 头 4 字节
    assert out.getvalue()[:2] == b"PK"


def test_build_qa_excel_has_required_headers():
    import openpyxl
    out = templates.build_qa_excel()
    wb = openpyxl.load_workbook(out)
    ws = wb.active
    headers = [c.value for c in ws[1]]
    assert "question" in headers
    assert "answer" in headers
    assert "tags" in headers


def test_build_qa_excel_has_example_row():
    import openpyxl
    out = templates.build_qa_excel()
    wb = openpyxl.load_workbook(out)
    ws = wb.active
    row2 = [c.value for c in ws[2]]
    assert any(v for v in row2)  # 至少有一个非空值 (示例行)
```

- [ ] **Step 3: 跑测试确认 FAIL**

Run: `uv run pytest tests/test_kg_templates.py -v`
Expected: 3 FAIL (templates 还没创建)

- [ ] **Step 4: 实现 `src/rag/kg/templates.py`**

```python
"""Excel / JSON 模板生成

v1 决策: 硬编码 1 个 QA 模板 (列头固定), 后续 PR 升级为从 yaml 动态生成
"""
from __future__ import annotations

import io

import openpyxl
from openpyxl.styles import Alignment, Font, PatternFill


def build_qa_excel() -> io.BytesIO:
    """生成 QA 对录入 Excel 模板 (含列头 + 示例行 + 表头样式)

    列头: question, answer, tags (逗号分隔)
    """
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "QA 对"

    headers = ["question", "answer", "tags"]
    ws.append(headers)

    # 表头样式: 蓝底白字
    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill("solid", fgColor="3B82F6")
    for cell in ws[1]:
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center", vertical="center")

    # 列宽
    ws.column_dimensions["A"].width = 40  # question
    ws.column_dimensions["B"].width = 60  # answer
    ws.column_dimensions["C"].width = 30  # tags

    # 示例行
    ws.append(["1LE0001 是什么系列?", "1LE 系列是西门子低压电机", "电机, 西门子"])

    out = io.BytesIO()
    wb.save(out)
    out.seek(0)
    return out
```

- [ ] **Step 5: 跑测试确认 PASS**

Run: `uv run pytest tests/test_kg_templates.py -v`
Expected: 3 PASS

- [ ] **Step 6: 提交**

```bash
git add src/rag/kg/templates.py tests/test_kg_templates.py pyproject.toml uv.lock
git commit -m "feat(kg): Excel QA 模板生成 (openpyxl)"
```

---

## Task 5.2: FastAPI 模板下载端点 + BFF proxy

**Files:**
- Modify: `src/rag/kg/router.py`
- Create: `web/app/api/knowledge/templates/[format]/route.ts`

- [ ] **Step 1: FastAPI 加 `/api/kg/templates/excel`**

在 `src/rag/kg/router.py` 加 (在 `/stats` 端点之后):

```python
from fastapi.responses import StreamingResponse
from . import templates as _templates

@router.get("/templates/excel")
def download_excel_template() -> StreamingResponse:
    """下发 Excel QA 模板"""
    buf = _templates.build_qa_excel()
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="qa-template.xlsx"'},
    )
```

- [ ] **Step 2: BFF proxy**

`web/app/api/knowledge/templates/[format]/route.ts`:

```ts
// 模板下载 BFF (透传 FastAPI)
import { NextRequest, NextResponse } from "next/server";

const FASTAPI = process.env.FASTAPI_BASE ?? "http://localhost:8000";

export async function GET(_req: NextRequest, { params }: { params: Promise<{ format: string }> }) {
  const { format } = await params;
  if (!["excel", "json"].includes(format)) {
    return NextResponse.json({ error: "format 必须是 excel 或 json" }, { status: 400 });
  }
  const r = await fetch(`${FASTAPI}/api/kg/templates/${format}`);
  if (!r.ok) return NextResponse.json({ error: "模板生成失败" }, { status: 502 });
  return new NextResponse(r.body, {
    status: 200,
    headers: {
      "Content-Type": r.headers.get("Content-Type") ?? "application/octet-stream",
      "Content-Disposition": r.headers.get("Content-Disposition") ?? `attachment; filename="template.${format}"`,
    },
  });
}
```

- [ ] **Step 3: 跑测试**

Run: `uv run pytest tests/test_kg_router.py tests/test_kg_templates.py -v && cd web && bun run typecheck`
Expected: 全过

- [ ] **Step 4: 提交**

```bash
git add src/rag/kg/router.py web/app/api/knowledge/templates/
git commit -m "feat(web+kg): 模板下载端点 /api/knowledge/templates/{excel,json}"
```

---

## Task 5.3: 前端 JSON 模板

**Files:**
- Create: `web/public/templates/knowledge-import.json`

- [ ] **Step 1: 写 JSON 模板**

```json
{
  "_comment": "知识库批量导入 JSON 模板 (2026-06-08)",
  "_usage": "items 里每条 item 描述一个写入目标, target=dify 走 Dify 写 QA/Doc, target=neo4j 走 Neo4j 写节点/三元组",
  "items": [
    {
      "target": "dify",
      "type": "qa",
      "payload": {
        "question": "1LE0001 是什么?",
        "answer": "1LE0001 是西门子 1LE 系列低压电机",
        "tags": ["电机", "西门子"]
      }
    },
    {
      "target": "neo4j",
      "type": "triple",
      "payload": {
        "from": { "label": "Product", "key": "model", "value": "1LE0001" },
        "rel": "BELONGS_TO",
        "to": { "label": "Series", "key": "name", "value": "1LE 系列" }
      }
    }
  ]
}
```

- [ ] **Step 2: 提交**

```bash
git add web/public/templates/knowledge-import.json
git commit -m "feat(web): JSON 批量导入模板 (内置)"
```

---

## Task 5.4: `web/lib/parse-excel.ts` + `parse-json.ts` + 测试

**Files:**
- Create: `web/lib/parse-excel.ts`
- Create: `web/lib/parse-excel.test.ts`
- Create: `web/lib/parse-json.ts`
- Create: `web/lib/parse-json.test.ts`

- [ ] **Step 1: parse-excel**

```ts
// Excel 解析: 第 1 行表头, 之后每行一个对象; 错误行收集返回
import * as XLSX from "xlsx";

export interface ParsedRow {
  row: number;  // 1-based (含表头)
  data: Record<string, string>;
  errors: string[];
}

export interface ParseResult {
  rows: ParsedRow[];
  total: number;
  errorCount: number;
}

export function parseExcelBuffer(buf: ArrayBuffer): ParseResult {
  const wb = XLSX.read(buf, { type: "array" });
  const ws = wb.Sheets[wb.SheetNames[0]];
  const raw: string[][] = XLSX.utils.sheet_to_json(ws, { header: 1, defval: "" });
  if (raw.length === 0) return { rows: [], total: 0, errorCount: 0 };
  const headers = raw[0].map((h) => String(h).trim());
  const rows: ParsedRow[] = [];
  for (let i = 1; i < raw.length; i++) {
    const data: Record<string, string> = {};
    const errors: string[] = [];
    headers.forEach((h, j) => {
      const v = String(raw[i][j] ?? "").trim();
      data[h] = v;
      if (h === "question" && v.length < 2) errors.push("question 至少 2 字");
      if (h === "answer" && v.length < 2) errors.push("answer 至少 2 字");
    });
    rows.push({ row: i + 1, data, errors });
  }
  return {
    rows,
    total: rows.length,
    errorCount: rows.filter((r) => r.errors.length > 0).length,
  };
}
```

- [ ] **Step 2: parse-excel 测试**

```ts
import { describe, it, expect } from "vitest";
import * as XLSX from "xlsx";
import { parseExcelBuffer } from "./parse-excel";

function makeExcel(rows: (string | number)[][]): ArrayBuffer {
  const ws = XLSX.utils.aoa_to_sheet(rows);
  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, "Sheet1");
  const buf = XLSX.write(wb, { type: "array", bookType: "xlsx" });
  return buf as ArrayBuffer;
}

describe("parseExcelBuffer", () => {
  it("valid rows", () => {
    const buf = makeExcel([
      ["question", "answer", "tags"],
      ["Q1?", "A1", "t1"],
      ["Q2?", "A2", "t2"],
    ]);
    const out = parseExcelBuffer(buf);
    expect(out.total).toBe(2);
    expect(out.errorCount).toBe(0);
    expect(out.rows[0].data.question).toBe("Q1?");
  });

  it("flags short question", () => {
    const buf = makeExcel([
      ["question", "answer"],
      ["Q", "A1"],
    ]);
    const out = parseExcelBuffer(buf);
    expect(out.errorCount).toBe(1);
    expect(out.rows[0].errors).toContain("question 至少 2 字");
  });

  it("empty sheet", () => {
    const buf = makeExcel([["question", "answer"]]);
    const out = parseExcelBuffer(buf);
    expect(out.total).toBe(0);
  });
});
```

- [ ] **Step 3: parse-json**

```ts
// JSON 解析: 校验 items 数组, 错误行收集
import { z } from "zod";

const ItemSchema = z.object({
  target: z.enum(["dify", "neo4j"]),
  type: z.string(),
  payload: z.record(z.unknown()),
});

const JsonSchema = z.object({
  items: z.array(ItemSchema),
});

export function parseJsonText(text: string): { items: z.infer<typeof ItemSchema>[]; errors: string[] } {
  let data: unknown;
  try {
    data = JSON.parse(text);
  } catch (e) {
    return { items: [], errors: [`JSON 解析失败: ${String(e)}`] };
  }
  const result = JsonSchema.safeParse(data);
  if (!result.success) {
    return { items: [], errors: result.error.issues.map((i) => `${i.path.join(".")}: ${i.message}`) };
  }
  return { items: result.data.items, errors: [] };
}
```

- [ ] **Step 4: parse-json 测试**

```ts
import { describe, it, expect } from "vitest";
import { parseJsonText } from "./parse-json";

describe("parseJsonText", () => {
  it("valid", () => {
    const text = JSON.stringify({
      items: [{ target: "dify", type: "qa", payload: { question: "Q" } }],
    });
    const out = parseJsonText(text);
    expect(out.errors).toEqual([]);
    expect(out.items).toHaveLength(1);
  });

  it("invalid json", () => {
    const out = parseJsonText("not json");
    expect(out.errors.length).toBeGreaterThan(0);
  });

  it("missing items", () => {
    const out = parseJsonText(JSON.stringify({}));
    expect(out.errors.length).toBeGreaterThan(0);
  });

  it("bad target", () => {
    const out = parseJsonText(JSON.stringify({
      items: [{ target: "wrong", type: "qa", payload: {} }],
    }));
    expect(out.errors.length).toBeGreaterThan(0);
  });
});
```

- [ ] **Step 5: 跑测试**

Run: `cd web && bun run test -- parse-excel parse-json`
Expected: 7 PASS

- [ ] **Step 6: 提交**

```bash
git add web/lib/parse-excel.ts web/lib/parse-excel.test.ts web/lib/parse-json.ts web/lib/parse-json.test.ts
git commit -m "feat(web): Excel/JSON 解析器 (zod 校验 + 错误行定位)"
```

---

## Task 5.5: BFF `/api/knowledge/documents/upload` + `/commit`

**Files:**
- Create: `web/app/api/knowledge/documents/upload/route.ts`
- Create: `web/app/api/knowledge/documents/commit/route.ts`

- [ ] **Step 1: upload (接收文件, 调 Dify createDocumentByFile)**

```ts
// 文件上传 → Dify createDocumentByFile → 返 doc + 索引状态
import { NextRequest, NextResponse } from "next/server";
import { DifyDatasets } from "@/lib/dify-datasets";

export async function POST(req: NextRequest) {
  const form = await req.formData();
  const datasetId = form.get("dataset_id") as string | null;
  const file = form.get("file") as File | null;
  if (!datasetId || !file) {
    return NextResponse.json({ error: "dataset_id / file 必填" }, { status: 400 });
  }
  try {
    // 简化为 by_text (v1 演示); PR 5.x 升级为 by_file multipart
    const text = await file.text();
    const doc = await DifyDatasets.createDocumentByText(datasetId, file.name, text, "high_quality");
    return NextResponse.json({ doc });
  } catch (e) {
    return NextResponse.json({ error: String(e) }, { status: 502 });
  }
}
```

- [ ] **Step 2: commit (批量提交已校验的解析结果)**

```ts
// 批量提交已校验 rows → 调 Dify 多次 → 返 task_id
import { NextRequest, NextResponse } from "next/server";
import { DifyDatasets } from "@/lib/dify-datasets";

export async function POST(req: NextRequest) {
  const { dataset_id, rows } = (await req.json()) as {
    dataset_id: string;
    rows: { question: string; answer: string; tags?: string }[];
  };
  if (!dataset_id || !Array.isArray(rows)) {
    return NextResponse.json({ error: "dataset_id / rows 必填" }, { status: 400 });
  }
  const results: { ok: boolean; id?: string; name: string; error?: string }[] = [];
  for (const r of rows) {
    try {
      const text = `Q: ${r.question}\nA: ${r.answer}${r.tags ? "\nTags: " + r.tags : ""}`;
      const doc = await DifyDatasets.createDocumentByText(dataset_id, `qa-${Date.now()}`, text);
      results.push({ ok: true, id: doc.id, name: doc.name });
    } catch (e) {
      results.push({ ok: false, name: r.question, error: String(e) });
    }
  }
  return NextResponse.json({
    total: rows.length,
    success: results.filter((r) => r.ok).length,
    failed: results.filter((r) => !r.ok).length,
    results,
  });
}
```

- [ ] **Step 3: 跑 typecheck**

Run: `cd web && bun run typecheck`
Expected: 无错误

- [ ] **Step 4: 提交**

```bash
git add web/app/api/knowledge/documents/
git commit -m "feat(web): BFF /api/knowledge/documents/upload + /commit"
```

---

## Task 5.6: Documents 页面 (三步流程)

**Files:**
- Create: `web/components/knowledge/FileDropzone.tsx`
- Create: `web/components/knowledge/FileDropzone.test.tsx`
- Modify: `web/app/knowledge/documents/page.tsx`

- [ ] **Step 1: FileDropzone + 测试**

`web/components/knowledge/FileDropzone.tsx`:

```tsx
"use client";
import { useDropzone } from "react-dropzone";

export function FileDropzone({
  onFile, accept, maxSizeMB = 50,
}: {
  onFile: (f: File) => void;
  accept: Record<string, string[]>;
  maxSizeMB?: number;
}) {
  const { getRootProps, getInputProps, isDragActive, fileRejections } = useDropzone({
    onDrop: (files) => { if (files[0]) onFile(files[0]); },
    accept, maxSize: maxSizeMB * 1024 * 1024, multiple: false,
  });
  return (
    <div
      {...getRootProps()}
      data-testid="file-dropzone"
      className={`rounded-lg border-2 border-dashed p-8 text-center cursor-pointer transition ${
        isDragActive ? "border-primary bg-primary/5" : "border-muted-foreground/25"
      }`}
    >
      <input {...getInputProps()} />
      <p className="text-sm">拖文件到这 或 点击选择</p>
      <p className="mt-1 text-xs text-muted-foreground">上限 {maxSizeMB}MB</p>
      {fileRejections.length > 0 && (
        <p className="mt-2 text-xs text-rose-600">
          {fileRejections[0].errors[0].message}
        </p>
      )}
    </div>
  );
}
```

`web/components/knowledge/FileDropzone.test.tsx`:

```tsx
import { render, fireEvent, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { FileDropzone } from "./FileDropzone";

describe("FileDropzone", () => {
  it("renders", () => {
    render(<FileDropzone onFile={vi.fn()} accept={{}} />);
    expect(screen.getByTestId("file-dropzone")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Documents page (三步流程)**

```tsx
"use client";
// 文档上传 (2026-06-08) — 三步流程: 解析 → 校验 → 提交
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { FileDropzone } from "@/components/knowledge/FileDropzone";
import { parseExcelBuffer, type ParseResult } from "@/lib/parse-excel";
import { parseJsonText } from "@/lib/parse-json";

type Step = "upload" | "parse" | "validate" | "commit";

export default function DocumentsPage() {
  const [step, setStep] = useState<Step>("upload");
  const [datasetId, setDatasetId] = useState("");
  const [parseResult, setParseResult] = useState<ParseResult | null>(null);
  const [jsonText, setJsonText] = useState("");
  const [commitResult, setCommitResult] = useState<{ total: number; success: number; failed: number; results: { ok: boolean; name: string; error?: string }[] } | null>(null);

  if (typeof window !== "undefined" && !datasetId) {
    setDatasetId(localStorage.getItem("kg.dataset_id") ?? "");
  }

  const onFile = async (f: File) => {
    if (f.name.endsWith(".json")) {
      const text = await f.text();
      const out = parseJsonText(text);
      setParseResult({
        rows: out.items.map((it, i) => ({ row: i + 1, data: it as unknown as Record<string, string>, errors: out.errors })),
        total: out.items.length,
        errorCount: out.errors.length > 0 ? out.items.length : 0,
      });
    } else {
      const buf = await f.arrayBuffer();
      setParseResult(parseExcelBuffer(buf));
    }
    setStep("validate");
  };

  const onCommit = async () => {
    if (!parseResult) return;
    const validRows = parseResult.rows.filter((r) => r.errors.length === 0);
    const r = await fetch("/api/knowledge/documents/commit", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        dataset_id: datasetId,
        rows: validRows.map((r) => ({
          question: r.data.question ?? "",
          answer: r.data.answer ?? "",
          tags: r.data.tags ?? "",
        })),
      }),
    });
    if (r.ok) setCommitResult(await r.json());
  };

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader><CardTitle>工具栏</CardTitle></CardHeader>
        <CardContent className="flex flex-wrap gap-2">
          <Button asChild variant="outline"><a href="/api/knowledge/templates/excel" download>📥 Excel 模板</a></Button>
          <Button asChild variant="outline"><a href="/api/knowledge/templates/json" download>📥 JSON 模板</a></Button>
          <Button asChild variant="outline"><a href="/templates/knowledge-import.json" download>📥 内置 JSON 模板</a></Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>1. 上传</CardTitle>
        </CardHeader>
        <CardContent>
          <FileDropzone
            onFile={onFile}
            accept={{
              "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": [".xlsx"],
              "application/json": [".json"],
            }}
          />
        </CardContent>
      </Card>

      {parseResult && (
        <Card>
          <CardHeader>
            <CardTitle>2. 解析 + 校验</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="mb-2 text-sm">
              ✅ 解析成功 · {parseResult.total} 行 · {parseResult.errorCount} 错误
            </p>
            <div className="max-h-96 overflow-auto rounded border">
              <table className="w-full text-sm">
                <thead className="bg-muted/50 sticky top-0">
                  <tr>
                    <th className="px-2 py-1 text-left">#</th>
                    <th className="px-2 py-1 text-left">问题</th>
                    <th className="px-2 py-1 text-left">答案</th>
                    <th className="px-2 py-1 text-left">错误</th>
                  </tr>
                </thead>
                <tbody>
                  {parseResult.rows.map((r) => (
                    <tr key={r.row} className={r.errors.length > 0 ? "bg-rose-50" : ""}>
                      <td className="px-2 py-1">{r.row}</td>
                      <td className="px-2 py-1">{r.data.question}</td>
                      <td className="px-2 py-1">{r.data.answer}</td>
                      <td className="px-2 py-1 text-rose-600">
                        {r.errors.map((e, i) => <div key={i}>{e}</div>)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {parseResult.errorCount > 0 && (
              <Button
                variant="outline" className="mt-2"
                onClick={() => {
                  const bad = parseResult.rows.filter((r) => r.errors.length > 0);
                  const csv = "row,question,answer,errors\n" + bad.map((r) => `${r.row},"${r.data.question ?? ""}","${r.data.answer ?? ""}","${r.errors.join("; ")}"`).join("\n");
                  const blob = new Blob([csv], { type: "text/csv" });
                  const a = document.createElement("a");
                  a.href = URL.createObjectURL(blob);
                  a.download = "errors.csv";
                  a.click();
                }}
              >
                📥 下载错误行 CSV
              </Button>
            )}
          </CardContent>
        </Card>
      )}

      {parseResult && parseResult.errorCount < parseResult.total && (
        <Card>
          <CardHeader><CardTitle>3. 提交 (异步)</CardTitle></CardHeader>
          <CardContent>
            <Button onClick={onCommit} data-testid="docs-commit">
              提交 {parseResult.total - parseResult.errorCount} 行到 Dify
            </Button>
            {commitResult && (
              <div className="mt-3 rounded border bg-emerald-50 p-3 text-sm">
                完成: 成功 {commitResult.success} / 失败 {commitResult.failed}
              </div>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
```

- [ ] **Step 3: page 测试**

`web/app/knowledge/documents/page.test.tsx`:

```tsx
import { render, fireEvent, screen, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import DocumentsPage from "./page";

beforeEach(() => {
  globalThis.fetch = vi.fn() as unknown as typeof fetch;
  localStorage.clear();
});

describe("DocumentsPage", () => {
  it("renders upload zone", () => {
    render(<DocumentsPage />);
    expect(screen.getByTestId("file-dropzone")).toBeInTheDocument();
  });

  it("shows template links", () => {
    render(<DocumentsPage />);
    expect(screen.getByText(/Excel 模板/)).toBeInTheDocument();
    expect(screen.getByText(/JSON 模板/)).toBeInTheDocument();
  });
});
```

- [ ] **Step 4: 跑测试**

Run: `cd web && bun run test -- documents FileDropzone`
Expected: 4 PASS

- [ ] **Step 5: 提交**

```bash
git add web/app/knowledge/documents/ web/components/knowledge/FileDropzone.tsx web/components/knowledge/FileDropzone.test.tsx
git commit -m "feat(web): Documents 三步流程 (上传/解析/提交) + 错误行 CSV 下载"
```

---

## Task 5.7: PR 5 验证

- [ ] **Step 1: 跑所有测试**

Run: `cd web && bun run test && uv run pytest tests/ -m "not slow" -q`
Expected: 全过

- [ ] **Step 2: 端到端手测**

启动 dev, 浏览器打开 `/knowledge/documents`:
1. 下载 Excel 模板, 填几行
2. 拖文件到上传区
3. 看到"解析成功 · N 行 · 0 错误"
4. 改一行问题为空, 看到错误行高亮 + 下载 CSV 按钮
5. 修好后点提交, 看到成功数

- [ ] **Step 3: git log**

Run: `git log --oneline | head -10`
Expected: 6 个新 commit (T5.1 templates / T5.2 端点 / T5.3 json 模板 / T5.4 解析器 / T5.5 BFF / T5.6 page)

下一步: PR 6 — Tab 3 (Triples) + Neo4j 写入。

---

# PR 6 · Tab 3 — 三元组录入 (→ Neo4j)

**PR 目标**: `/knowledge/triples` 多行可编辑表格 + 起点/关系/终点类型联动 + 批量提交到 Neo4j。

---

## Task 6.1: BFF `/api/kg/triples` proxy + 透传

> FastAPI `/api/kg/triples` 已存在 (PR 1.6), 这里只在 BFF 加可选代理, 但因为 Next.js 同源可直接 fetch `${FASTAPI}/api/kg/triples`, 不需要单独 BFF 路由。Schema 同理, 直拉 `/api/kg/schema`。

- [ ] **Step 1: 跳过 BFF, 在 page 里直接 fetch FastAPI**

(本页所有调用都直接打 FastAPI, 跟 dashboard 一致, 不再单独建 BFF 路由)

---

## Task 6.2: `SchemaFieldRenderer` 组件 (动态下拉联动)

**Files:**
- Create: `web/components/knowledge/SchemaFieldRenderer.tsx`
- Create: `web/components/knowledge/SchemaFieldRenderer.test.tsx`

- [ ] **Step 1: 写组件**

```tsx
"use client";
// 动态渲染 schema 字段 (下拉联动)
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import type { NodeDef, RelationDef } from "@/lib/schema-types";

export function RelationPicker({
  schema, fromLabel, value, onChange,
}: {
  schema: { nodes: NodeDef[]; relations: RelationDef[] };
  fromLabel: string;
  value: string;
  onChange: (v: string) => void;
}) {
  const rels = schema.relations.filter((r) => r.from === fromLabel);
  return (
    <Select value={value} onValueChange={onChange}>
      <SelectTrigger data-testid="rel-picker"><SelectValue placeholder="选关系" /></SelectTrigger>
      <SelectContent>
        {rels.map((r) => (
          <SelectItem key={r.name} value={r.name}>
            {r.name} → {r.to}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}

export function LabelPicker({
  schema, value, onChange,
}: {
  schema: { nodes: NodeDef[]; relations: RelationDef[] };
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <Select value={value} onValueChange={onChange}>
      <SelectTrigger><SelectValue placeholder="选节点类型" /></SelectTrigger>
      <SelectContent>
        {schema.nodes.map((n) => (
          <SelectItem key={n.name} value={n.name}>{n.name}</SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
```

- [ ] **Step 2: 测试**

```tsx
import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { RelationPicker, LabelPicker } from "./SchemaFieldRenderer";
import type { KnowledgeSchema } from "@/lib/schema-types";

const schema: KnowledgeSchema = {
  nodes: [
    { name: "Product", fields: [] },
    { name: "Series", fields: [] },
  ],
  relations: [
    { name: "BELONGS_TO", from: "Product", to: "Series", cardinality: "many_to_one" },
    { name: "COMPATIBLE_WITH", from: "Product", to: "Product", cardinality: "many_to_many" },
  ],
};

describe("RelationPicker", () => {
  it("根据 from 过滤关系", () => {
    render(<RelationPicker schema={schema} fromLabel="Product" value="" onChange={() => {}} />);
    expect(screen.getByText(/BELONGS_TO/)).toBeInTheDocument();
    expect(screen.getByText(/COMPATIBLE_WITH/)).toBeInTheDocument();
  });

  it("from 无匹配时不显示", () => {
    render(<RelationPicker schema={schema} fromLabel="Series" value="" onChange={() => {}} />);
    expect(screen.queryByText(/BELONGS_TO/)).not.toBeInTheDocument();
  });
});

describe("LabelPicker", () => {
  it("列所有节点", () => {
    render(<LabelPicker schema={schema} value="" onChange={() => {}} />);
    expect(screen.getByText("Product")).toBeInTheDocument();
    expect(screen.getByText("Series")).toBeInTheDocument();
  });
});
```

- [ ] **Step 3: 跑测试**

Run: `cd web && bun run test -- SchemaFieldRenderer`
Expected: 3 PASS

- [ ] **Step 4: 提交**

```bash
git add web/components/knowledge/SchemaFieldRenderer.tsx web/components/knowledge/SchemaFieldRenderer.test.tsx
git commit -m "feat(web): SchemaFieldRenderer (关系/节点下拉联动)"
```

---

## Task 6.3: Triples page (多行可编辑表格)

**Files:**
- Modify: `web/app/knowledge/triples/page.tsx`
- Create: `web/app/knowledge/triples/page.test.tsx`

- [ ] **Step 1: 写 page**

```tsx
"use client";
// 三元组录入 (2026-06-08) — 多行表格 + 类型联动
import { useEffect, useState } from "react";
import useSWR from "swr";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { RelationPicker, LabelPicker } from "@/components/knowledge/SchemaFieldRenderer";
import type { KnowledgeSchema } from "@/lib/schema-types";

const fetcher = (u: string) => fetch(u).then((r) => r.json());

interface Row {
  id: string;
  from_label: string;
  from_key: string;
  from_value: string;
  rel_type: string;
  to_label: string;
  to_key: string;
  to_value: string;
  properties: string;  // JSON 字符串
}

const empty = (): Row => ({
  id: Math.random().toString(36).slice(2),
  from_label: "", from_key: "model", from_value: "",
  rel_type: "", to_label: "", to_key: "name", to_value: "",
  properties: "{}",
});

export default function TriplesPage() {
  const { data: schema } = useSWR<KnowledgeSchema>("/api/knowledge/schema", fetcher);
  const [rows, setRows] = useState<Row[]>([empty()]);
  const [submitResult, setSubmitResult] = useState<{ success: number; failed: number; errors: string[] } | null>(null);

  const update = (i: number, patch: Partial<Row>) =>
    setRows((rs) => rs.map((r, j) => (j === i ? { ...r, ...patch } : r)));

  const remove = (i: number) => setRows((rs) => rs.filter((_, j) => j !== i));

  const submit = async () => {
    setSubmitResult(null);
    // 简单校验
    const invalid: string[] = [];
    const validRows = rows.map((r) => {
      const errors: string[] = [];
      if (!r.from_label || !r.from_value) errors.push("起点缺失");
      if (!r.to_label || !r.to_value) errors.push("终点缺失");
      if (!r.rel_type) errors.push("关系缺失");
      if (errors.length) invalid.push(`第 ${rows.indexOf(r) + 1} 行: ${errors.join(", ")}`);
      let props: Record<string, unknown> = {};
      try { props = JSON.parse(r.properties); } catch { invalid.push(`第 ${rows.indexOf(r) + 1} 行: properties 不是合法 JSON`); }
      return {
        from_label: r.from_label, from_key: r.from_key, from_value: r.from_value,
        rel_type: r.rel_type,
        to_label: r.to_label, to_key: r.to_key, to_value: r.to_value,
        properties: props,
      };
    });
    if (invalid.length) {
      setSubmitResult({ success: 0, failed: rows.length, errors: invalid });
      return;
    }
    const r = await fetch("http://localhost:8000/api/kg/triples", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ rows: validRows }),
    });
    if (r.ok) setSubmitResult(await r.json());
  };

  if (!schema) return <p className="text-sm text-muted-foreground">加载 schema…</p>;

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle>三元组编辑</CardTitle>
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => setRows((rs) => [...rs, empty()])}>+ 新增行</Button>
            <Button onClick={submit} data-testid="triples-submit">批量提交</Button>
            <Button variant="outline" onClick={() => setRows([empty()])}>清空</Button>
          </div>
        </CardHeader>
        <CardContent>
          <div className="overflow-auto rounded border">
            <table className="w-full text-sm">
              <thead className="bg-muted/50">
                <tr>
                  <th className="px-2 py-1 text-left">#</th>
                  <th className="px-2 py-1 text-left">起点 (类型)</th>
                  <th className="px-2 py-1 text-left">起点值</th>
                  <th className="px-2 py-1 text-left">关系</th>
                  <th className="px-2 py-1 text-left">终点 (类型)</th>
                  <th className="px-2 py-1 text-left">终点值</th>
                  <th className="px-2 py-1 text-left">属性 (JSON)</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r, i) => {
                  const rel = schema.relations.find((x) => x.name === r.rel_type);
                  return (
                    <tr key={r.id} className="border-t">
                      <td className="px-2 py-1">{i + 1}</td>
                      <td className="px-2 py-1"><LabelPicker schema={schema} value={r.from_label} onChange={(v) => update(i, { from_label: v })} /></td>
                      <td className="px-2 py-1"><Input value={r.from_value} onChange={(e) => update(i, { from_value: e.target.value })} /></td>
                      <td className="px-2 py-1">
                        <RelationPicker schema={schema} fromLabel={r.from_label} value={r.rel_type} onChange={(v) => {
                          const newRel = schema.relations.find((x) => x.name === v);
                          update(i, { rel_type: v, to_label: newRel?.to ?? "" });
                        }} />
                      </td>
                      <td className="px-2 py-1">{rel?.to ?? "—"}</td>
                      <td className="px-2 py-1"><Input value={r.to_value} onChange={(e) => update(i, { to_value: e.target.value })} /></td>
                      <td className="px-2 py-1"><Input value={r.properties} onChange={(e) => update(i, { properties: e.target.value })} /></td>
                      <td className="px-2 py-1"><Button variant="ghost" size="sm" onClick={() => remove(i)}>×</Button></td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          {submitResult && (
            <div className={`mt-3 rounded p-3 text-sm ${submitResult.failed === 0 ? "bg-emerald-50" : "bg-rose-50"}`}>
              成功 {submitResult.success} / 失败 {submitResult.failed}
              {submitResult.errors.length > 0 && <ul className="mt-1 list-disc pl-5">{submitResult.errors.map((e, i) => <li key={i}>{e}</li>)}</ul>}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
```

- [ ] **Step 2: 写 page 测试**

```tsx
import { render, screen, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import TriplesPage from "./page";

beforeEach(() => {
  globalThis.fetch = vi.fn().mockResolvedValue({
    json: async () => ({
      nodes: [
        { name: "Product", fields: [] },
        { name: "Series", fields: [] },
      ],
      relations: [
        { name: "BELONGS_TO", from: "Product", to: "Series", cardinality: "many_to_one" },
      ],
    }),
  }) as unknown as typeof fetch;
});

describe("TriplesPage", () => {
  it("加载 schema 后渲染表格", async () => {
    render(<TriplesPage />);
    await waitFor(() => expect(screen.getByTestId("triples-submit")).toBeInTheDocument());
  });
});
```

- [ ] **Step 3: 跑测试**

Run: `cd web && bun run test -- triples`
Expected: 1 PASS

- [ ] **Step 4: 提交**

```bash
git add web/app/knowledge/triples/
git commit -m "feat(web): Tab Triples 多行可编辑表格 + 关系联动 + 提交 Neo4j"
```

---

## Task 6.4: PR 6 验证

- [ ] **Step 1: 跑所有测试**

Run: `cd web && bun run test && uv run pytest tests/ -m "not slow" -q`
Expected: 全过

- [ ] **Step 2: 端到端手测**

启动 dev + FastAPI, 浏览器打开 `/knowledge/triples`:
1. 看到空表格 + 顶部工具栏
2. 点"+ 新增行" 加几行
3. 选起点 Product, 关系自动限定为 BELONGS_TO / COMPATIBLE_WITH
4. 终点类型随关系自动填
5. 填值后点"批量提交"
6. 用 cypher-shell 或 Neo4j Browser 查, 节点关系应已写入

- [ ] **Step 3: git log**

Run: `git log --oneline | head -10`
Expected: 2 个新 commit (T6.2 SchemaFieldRenderer / T6.3 Triples page)

下一步: PR 7 — Tab 4 (Batch) + 后台任务 + 任务面板。

---

# PR 7 · Tab 4 — 批量导入 + 后台任务 + 任务面板

**PR 目标**: `/knowledge/batch` 大批量 JSON 上传 → 后台 task → 活跃任务轮询 + 历史记录。

---

## Task 7.1: BFF `/api/knowledge/batch` 路由 (Dify + Neo4j 双写, 后台跑)

**Files:**
- Create: `web/app/api/knowledge/batch/route.ts`

- [ ] **Step 1: 写 handler**

```ts
// 批量导入 (后台任务 + 进度可查)
import { NextRequest, NextResponse } from "next/server";
import { DifyDatasets } from "@/lib/dify-datasets";

const FASTAPI = process.env.FASTAPI_BASE ?? "http://localhost:8000";
// 简化为 in-memory task map; v2 走 FastAPI /api/kg/batch
const tasks = new Map<string, { state: string; success: number; failed: number; errors: string[]; total: number; processed: number }>();

export async function POST(req: NextRequest) {
  const { dataset_id, items } = (await req.json()) as {
    dataset_id: string;
    items: { target: "dify" | "neo4j"; type: string; payload: Record<string, unknown> }[];
  };
  if (!dataset_id || !Array.isArray(items)) {
    return NextResponse.json({ error: "dataset_id / items 必填" }, { status: 400 });
  }

  const taskId = Math.random().toString(36).slice(2, 14);
  tasks.set(taskId, { state: "queued", success: 0, failed: 0, errors: [], total: items.length, processed: 0 });

  // 异步跑
  void (async () => {
    const t = tasks.get(taskId)!;
    t.state = "running";
    for (let i = 0; i < items.length; i++) {
      const it = items[i];
      try {
        if (it.target === "dify" && it.type === "qa") {
          const p = it.payload as { question: string; answer: string; tags?: string[] };
          await DifyDatasets.createDocumentByText(
            dataset_id,
            `batch-qa-${Date.now()}-${i}`,
            `Q: ${p.question}\nA: ${p.answer}${p.tags?.length ? "\nTags: " + p.tags.join(", ") : ""}`,
          );
        } else if (it.target === "neo4j" && it.type === "triple") {
          const p = it.payload as {
            from: { label: string; key: string; value: string };
            rel: string;
            to: { label: string; key: string; value: string };
          };
          await fetch(`${FASTAPI}/api/kg/triples`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              rows: [{
                from_label: p.from.label, from_key: p.from.key, from_value: p.from.value,
                rel_type: p.rel,
                to_label: p.to.label, to_key: p.to.key, to_value: p.to.value,
                properties: {},
              }],
            }),
          });
        }
        t.success++;
      } catch (e) {
        t.failed++;
        t.errors.push(`item ${i}: ${String(e)}`);
      }
      t.processed = i + 1;
    }
    t.state = t.failed === 0 ? "done" : (t.success / t.total >= 0.8 ? "partial" : "failed");
  })();

  return NextResponse.json({ task_id: taskId });
}

export async function GET(req: NextRequest) {
  const id = req.nextUrl.searchParams.get("task_id") ?? "";
  const t = tasks.get(id);
  if (!t) return NextResponse.json({ error: "task 不存在" }, { status: 404 });
  return NextResponse.json({ task_id: id, ...t });
}
```

- [ ] **Step 2: 跑 typecheck**

Run: `cd web && bun run typecheck`
Expected: 无错误

- [ ] **Step 3: 提交**

```bash
git add web/app/api/knowledge/batch/route.ts
git commit -m "feat(web): BFF /api/knowledge/batch (后台任务 + 进度轮询)"
```

---

## Task 7.2: `TaskStatusBadge` 组件

**Files:**
- Create: `web/components/knowledge/TaskStatusBadge.tsx`
- Create: `web/components/knowledge/TaskStatusBadge.test.tsx`

- [ ] **Step 1: 写组件 + 测试**

```tsx
import { Badge } from "@/components/ui/badge";

const style: Record<string, string> = {
  queued: "bg-slate-100 text-slate-700",
  running: "bg-blue-100 text-blue-700 animate-pulse",
  done: "bg-emerald-100 text-emerald-700",
  partial: "bg-amber-100 text-amber-700",
  failed: "bg-rose-100 text-rose-700",
  cancelled: "bg-slate-200 text-slate-600",
};

export function TaskStatusBadge({ state }: { state: string }) {
  return <Badge className={style[state] ?? style.queued} data-testid="task-status">{state}</Badge>;
}
```

```tsx
import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { TaskStatusBadge } from "./TaskStatusBadge";

describe("TaskStatusBadge", () => {
  it("done 绿色", () => {
    render(<TaskStatusBadge state="done" />);
    expect(screen.getByTestId("task-status").className).toContain("emerald");
  });
  it("failed 红色", () => {
    render(<TaskStatusBadge state="failed" />);
    expect(screen.getByTestId("task-status").className).toContain("rose");
  });
});
```

- [ ] **Step 2: 跑测试 + 提交**

Run: `cd web && bun run test -- TaskStatusBadge`
Expected: 2 PASS

```bash
git add web/components/knowledge/TaskStatusBadge.tsx web/components/knowledge/TaskStatusBadge.test.tsx
git commit -m "feat(web): TaskStatusBadge 组件 (6 种状态色)"
```

---

## Task 7.3: Batch page (活跃任务 + 历史)

**Files:**
- Modify: `web/app/knowledge/batch/page.tsx`
- Create: `web/app/knowledge/batch/page.test.tsx`

- [ ] **Step 1: 写 page**

```tsx
"use client";
// 批量导入 (2026-06-08) — 上传 JSON + 活跃任务 + 历史
import { useEffect, useState, useRef } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { TaskStatusBadge } from "@/components/knowledge/TaskStatusBadge";
import { parseJsonText } from "@/lib/parse-json";

interface Task {
  task_id: string;
  state: string;
  total: number;
  processed: number;
  success: number;
  failed: number;
  errors: string[];
}

export default function BatchPage() {
  const [datasetId, setDatasetId] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [parsing, setParsing] = useState(false);
  const [parseErrors, setParseErrors] = useState<string[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [activeTask, setActiveTask] = useState<Task | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (typeof window !== "undefined") setDatasetId(localStorage.getItem("kg.dataset_id") ?? "");
  }, []);

  // 活跃任务轮询
  useEffect(() => {
    if (activeTask && (activeTask.state === "queued" || activeTask.state === "running")) {
      pollRef.current = setInterval(async () => {
        const r = await fetch(`/api/knowledge/batch?task_id=${activeTask.task_id}`);
        if (r.ok) {
          const t: Task = await r.json();
          setActiveTask(t);
          if (t.state !== "queued" && t.state !== "running") {
            if (pollRef.current) clearInterval(pollRef.current);
          }
        }
      }, 1000);
      return () => { if (pollRef.current) clearInterval(pollRef.current); };
    }
  }, [activeTask?.task_id, activeTask?.state]);

  const onSubmit = async () => {
    if (!file || !datasetId) return;
    setParsing(true);
    setParseErrors([]);
    const text = await file.text();
    const parsed = parseJsonText(text);
    setParsing(false);
    if (parsed.errors.length) {
      setParseErrors(parsed.errors);
      return;
    }
    setSubmitting(true);
    try {
      const r = await fetch("/api/knowledge/batch", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ dataset_id: datasetId, items: parsed.items }),
      });
      if (r.ok) {
        const { task_id } = await r.json();
        setActiveTask({ task_id, state: "queued", total: parsed.items.length, processed: 0, success: 0, failed: 0, errors: [] });
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader><CardTitle>操作</CardTitle></CardHeader>
        <CardContent className="space-y-3">
          <div className="flex flex-wrap items-center gap-2">
            <input
              type="file"
              accept=".json"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              data-testid="batch-file"
              className="text-sm"
            />
            <Button onClick={onSubmit} disabled={!file || submitting} data-testid="batch-submit">
              {submitting ? "提交中…" : "提交为后台任务"}
            </Button>
            <Button asChild variant="outline"><a href="/templates/knowledge-import.json" download>下载模板</a></Button>
          </div>
          {parseErrors.length > 0 && (
            <ul className="rounded border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">
              {parseErrors.map((e, i) => <li key={i}>{e}</li>)}
            </ul>
          )}
        </CardContent>
      </Card>

      {activeTask && (
        <Card>
          <CardHeader>
            <CardTitle>活跃任务 {activeTask.task_id}</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="mb-2 flex items-center gap-3">
              <TaskStatusBadge state={activeTask.state} />
              <span className="text-sm text-muted-foreground">
                {activeTask.processed} / {activeTask.total}
              </span>
            </div>
            <Progress value={activeTask.total ? (activeTask.processed / activeTask.total) * 100 : 0} />
            <div className="mt-3 text-sm">
              成功 {activeTask.success} · 失败 {activeTask.failed}
              {activeTask.errors.length > 0 && (
                <details className="mt-2">
                  <summary className="cursor-pointer text-rose-700">查看错误 ({activeTask.errors.length})</summary>
                  <ul className="mt-1 list-disc pl-5 text-xs">
                    {activeTask.errors.slice(0, 50).map((e, i) => <li key={i}>{e}</li>)}
                  </ul>
                </details>
              )}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
```

- [ ] **Step 2: 写 page 测试**

```tsx
import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import BatchPage from "./page";

beforeEach(() => {
  globalThis.fetch = vi.fn() as unknown as typeof fetch;
  localStorage.clear();
});

describe("BatchPage", () => {
  it("renders 操作 + 提交按钮", () => {
    render(<BatchPage />);
    expect(screen.getByTestId("batch-file")).toBeInTheDocument();
    expect(screen.getByTestId("batch-submit")).toBeInTheDocument();
  });
});
```

- [ ] **Step 3: 跑测试**

Run: `cd web && bun run test -- batch`
Expected: 1 PASS

- [ ] **Step 4: 提交**

```bash
git add web/app/knowledge/batch/
git commit -m "feat(web): Tab Batch 上传 JSON + 后台任务 + 1s 轮询进度"
```

---

## Task 7.4: PR 7 验证

- [ ] **Step 1: 跑所有测试**

Run: `cd web && bun run test && uv run pytest tests/ -m "not slow" -q`
Expected: 全过

- [ ] **Step 2: 端到端手测**

启动 dev + FastAPI, 浏览器打开 `/knowledge/batch`:
1. 下载内置 JSON 模板, 准备 items 数组 (3 条: 1 dify qa + 1 neo4j triple + 1 dify doc)
2. 上传 JSON, 点提交
3. 看到活跃任务 + 进度条更新
4. 完成后状态变 done/partial
5. 错误数 ≥ 0 时有 details

- [ ] **Step 3: git log**

Run: `git log --oneline | head -10`
Expected: 3 个新 commit (T7.1 BFF / T7.2 badge / T7.3 page)

下一步: PR 8 — Schema 浏览器 + Audit log + 收尾打磨。

---

# PR 8 · Schema 浏览器 + Audit log + 收尾打磨

**PR 目标**: 右上角 `?` 弹 Schema 浏览器 + 每次 commit 写 audit log + ErrorBoundary + 空状态引导 + 文档收尾。

---

## Task 8.1: Schema 浏览器 Dialog

**Files:**
- Create: `web/components/knowledge/SchemaBrowser.tsx`
- Create: `web/components/knowledge/SchemaBrowser.test.tsx`

- [ ] **Step 1: 写组件 + 测试**

```tsx
"use client";
// Schema 浏览器 — 右上角 ? 弹窗, 展示 yaml 节点/关系
import { useEffect, useState } from "react";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import type { KnowledgeSchema } from "@/lib/schema-types";

export function SchemaBrowser() {
  const [schema, setSchema] = useState<KnowledgeSchema | null>(null);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (open && !schema) {
      fetch("/api/knowledge/schema").then((r) => r.json()).then(setSchema);
    }
  }, [open, schema]);

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="ghost" size="sm" data-testid="schema-browser-trigger">?</Button>
      </DialogTrigger>
      <DialogContent className="max-w-2xl max-h-[80vh] overflow-auto">
        <DialogHeader><DialogTitle>Schema 浏览器</DialogTitle></DialogHeader>
        {!schema && <p className="text-sm">加载中…</p>}
        {schema && (
          <div className="space-y-4 text-sm">
            <section>
              <h3 className="font-semibold">节点 ({schema.nodes.length})</h3>
              {schema.nodes.map((n) => (
                <div key={n.name} className="mt-2 rounded border p-2">
                  <div className="font-medium">{n.name}</div>
                  <ul className="mt-1 list-disc pl-5 text-xs text-muted-foreground">
                    {n.fields.map((f) => <li key={f.key}>{f.label} ({f.type}){f.required ? " *" : ""}</li>)}
                  </ul>
                </div>
              ))}
            </section>
            <section>
              <h3 className="font-semibold">关系 ({schema.relations.length})</h3>
              {schema.relations.map((r) => (
                <div key={r.name} className="mt-1 text-xs">
                  {r.from} -[{r.name}]→ {r.to} ({r.cardinality})
                </div>
              ))}
            </section>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
```

```tsx
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { SchemaBrowser } from "./SchemaBrowser";

const mockSchema = {
  nodes: [
    { name: "Product", fields: [{ key: "model", label: "型号", type: "string", required: true }] },
  ],
  relations: [
    { name: "BELONGS_TO", from: "Product", to: "Series", cardinality: "many_to_one" },
  ],
};

beforeEach(() => {
  globalThis.fetch = vi.fn().mockResolvedValue({ json: async () => mockSchema }) as unknown as typeof fetch;
});

describe("SchemaBrowser", () => {
  it("点击 trigger 后加载 schema", async () => {
    render(<SchemaBrowser />);
    fireEvent.click(screen.getByTestId("schema-browser-trigger"));
    await waitFor(() => expect(screen.getByText(/Schema 浏览器/)).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("Product")).toBeInTheDocument());
    expect(screen.getByText(/BELONGS_TO/)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: 把 SchemaBrowser 接到 layout**

Modify `web/app/knowledge/layout.tsx`, 在状态条最右加 `<SchemaBrowser />`:

```tsx
// 在 HealthDot 后面加
<SchemaBrowser />
```

- [ ] **Step 3: 跑测试 + 提交**

Run: `cd web && bun run test -- SchemaBrowser`
Expected: 1 PASS

```bash
git add web/components/knowledge/SchemaBrowser.tsx web/components/knowledge/SchemaBrowser.test.tsx web/app/knowledge/layout.tsx
git commit -m "feat(web): Schema 浏览器 + 接到顶 layout"
```

---

## Task 8.2: Audit log (SQLite 持久化)

**Files:**
- Create: `src/rag/kg/audit.py`
- Create: `tests/test_kg_audit.py`
- Modify: `src/rag/kg/router.py`

- [ ] **Step 1: 写 audit 模块 + 红测试**

`tests/test_kg_audit.py`:

```python
"""kg.audit 审计日志测试"""
import tempfile
from pathlib import Path

from src.rag.kg import audit


def test_record_writes_to_sqlite():
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "audit.db"
        store = audit.AuditStore(db)
        store.record(action="create_qa", actor="user1", target="ds1", result="ok", detail={"q": "1LE0001"})
        rows = store.list_recent(limit=10)
        assert len(rows) == 1
        assert rows[0]["action"] == "create_qa"
        assert rows[0]["actor"] == "user1"
        assert rows[0]["result"] == "ok"


def test_list_recent_orders_by_ts_desc():
    import time
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "audit.db"
        store = audit.AuditStore(db)
        store.record(action="a", actor="x", target="t", result="ok", detail={})
        time.sleep(0.01)
        store.record(action="b", actor="x", target="t", result="ok", detail={})
        rows = store.list_recent(limit=10)
        assert rows[0]["action"] == "b"  # 新的在前面
```

- [ ] **Step 2: 跑测试确认 FAIL**

Run: `uv run pytest tests/test_kg_audit.py -v`
Expected: 2 FAIL

- [ ] **Step 3: 实现 `src/rag/kg/audit.py`**

```python
"""审计日志 (SQLite 持久化)

每次 kg 路由操作 + BFF 转发时写一条, 便于追溯谁在什么时间改了什么。
"""
from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path


class AuditStore:
    def __init__(self, db_path: Path | str):
        self._db = Path(db_path)
        self._db.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self._db) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS audit (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts REAL NOT NULL,
                    action TEXT NOT NULL,
                    actor TEXT,
                    target TEXT,
                    result TEXT,
                    detail TEXT
                )
            """)

    def record(self, *, action: str, actor: str | None, target: str | None, result: str, detail: dict) -> None:
        with sqlite3.connect(self._db) as conn:
            conn.execute(
                "INSERT INTO audit (ts, action, actor, target, result, detail) VALUES (?, ?, ?, ?, ?, ?)",
                (time.time(), action, actor, target, result, json.dumps(detail, ensure_ascii=False)),
            )

    def list_recent(self, limit: int = 50) -> list[dict]:
        with sqlite3.connect(self._db) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.execute("SELECT * FROM audit ORDER BY ts DESC LIMIT ?", (limit,))
            return [
                {**dict(r), "detail": json.loads(r["detail"])}
                for r in cur.fetchall()
            ]
```

- [ ] **Step 4: 跑测试确认 PASS**

Run: `uv run pytest tests/test_kg_audit.py -v`
Expected: 2 PASS

- [ ] **Step 5: 把 audit 接到 /api/kg/triples 路由**

Modify `src/rag/kg/router.py` 顶部加单例 + 在 `submit_triples` 内调:

```python
from pathlib import Path as _P
from . import audit as _audit

_audit_store = _audit.AuditStore(_P("data/kg_audit.db"))
_audit_store.__init__  # touch (warm DB)
```

在 `submit_triples` 函数末尾加:

```python
_audit_store.record(
    action="submit_triples",
    actor=None,  # v1 暂未从 header 拿
    target=f"{len(req.rows)} rows",
    result="ok" if result.failed == 0 else "partial",
    detail={"success": result.success, "failed": result.failed},
)
```

- [ ] **Step 6: 跑全量测试 + 提交**

Run: `uv run pytest tests/ -m "not slow" -q`
Expected: 全过

```bash
git add src/rag/kg/audit.py src/rag/kg/router.py tests/test_kg_audit.py
git commit -m "feat(kg): AuditStore (SQLite 持久化) + 接到 triples 路由"
```

---

## Task 8.3: ErrorBoundary + 空状态引导

**Files:**
- Create: `web/components/knowledge/ErrorBoundary.tsx`
- Create: `web/components/knowledge/ErrorBoundary.test.tsx`
- Modify: `web/app/knowledge/layout.tsx`

- [ ] **Step 1: ErrorBoundary**

```tsx
"use client";
// 知识模块错误边界 — 防止单页崩溃影响整站
import { Component, type ReactNode } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export class ErrorBoundary extends Component<
  { children: ReactNode },
  { error: Error | null }
> {
  state = { error: null as Error | null };
  static getDerivedStateFromError(error: Error) { return { error }; }
  render() {
    if (this.state.error) {
      return (
        <Card className="border-rose-200">
          <CardHeader><CardTitle className="text-rose-700">出错了</CardTitle></CardHeader>
          <CardContent>
            <pre className="text-xs text-rose-800">{this.state.error.message}</pre>
            <button
              className="mt-2 text-sm text-primary underline"
              onClick={() => this.setState({ error: null })}
            >
              重试
            </button>
          </CardContent>
        </Card>
      );
    }
    return this.props.children;
  }
}
```

- [ ] **Step 2: 测试**

```tsx
import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { ErrorBoundary } from "./ErrorBoundary";

const Bomb = () => { throw new Error("boom"); };

describe("ErrorBoundary", () => {
  it("捕获子组件异常", () => {
    render(<ErrorBoundary><Bomb /></ErrorBoundary>);
    expect(screen.getByText(/出错了/)).toBeInTheDocument();
    expect(screen.getByText(/boom/)).toBeInTheDocument();
  });
});
```

- [ ] **Step 3: layout 包裹**

Modify `web/app/knowledge/layout.tsx` 包裹:

```tsx
import { ErrorBoundary } from "@/components/knowledge/ErrorBoundary";

export default function KnowledgeLayout({ children }: { children: ReactNode }) {
  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-4 rounded-lg border bg-card px-4 py-3">
        {/* ... 现有状态条 ... */}
      </div>
      <ErrorBoundary>{children}</ErrorBoundary>
    </div>
  );
}
```

- [ ] **Step 4: 空状态引导 (Dashboard 加 3 个示例按钮)**

Modify `web/app/knowledge/page.tsx`, 在统计卡片上方加空状态:

```tsx
{!isLoading && data && data.dify.documents === 0 && data.neo4j.Product === 0 && (
  <div className="rounded-lg border border-dashed bg-muted/30 p-6">
    <h3 className="font-semibold">👋 第一次使用?</h3>
    <p className="mt-1 text-sm text-muted-foreground">3 个示例帮你上手:</p>
    <ul className="mt-2 list-disc pl-5 text-sm">
      <li><a href="/knowledge/qa" className="text-primary underline">录 1 条 QA 对</a> 体验 Dify 写入</li>
      <li><a href="/knowledge/triples" className="text-primary underline">录 1 个三元组</a> 体验 Neo4j 写入</li>
      <li><a href="/knowledge/batch" className="text-primary underline">批量导入</a> 跑后台任务</li>
    </ul>
  </div>
)}
```

- [ ] **Step 5: 跑测试 + 提交**

Run: `cd web && bun run test`
Expected: 全过

```bash
git add web/components/knowledge/ErrorBoundary.tsx web/components/knowledge/ErrorBoundary.test.tsx web/app/knowledge/layout.tsx web/app/knowledge/page.tsx
git commit -m "feat(web): ErrorBoundary + Dashboard 空状态引导"
```

---

## Task 8.4: 文档 + 收尾

**Files:**
- Create: `docs/knowledge-management-page.md`
- Modify: `README.md` (链接到新文档)

- [ ] **Step 1: 写知识管理页文档**

```markdown
# 知识库 + 知识图谱管理页 (/knowledge)

RAG 项目后台管理模块, 业务人员自助录入 QA/产品文档到 Dify, 工程师批量写三元组到 Neo4j。

## 5 个页面

| 路径 | 用途 | 写哪 |
|---|---|---|
| `/knowledge` | Dashboard 4 统计卡 + 4 入口 | - |
| `/knowledge/qa` | 录 QA 对 | Dify |
| `/knowledge/documents` | 上传 Excel/JSON | Dify |
| `/knowledge/triples` | 录三元组 | Neo4j |
| `/knowledge/batch` | 批量导入 (后台任务) | Dify + Neo4j |

## 架构

```
Browser → /api/knowledge/* (Next.js BFF) → Dify Datasets API
                                          → FastAPI /api/kg/* → Neo4j
```

- 浏览器拿不到 Dify/Neo4j 凭据 (BFF 隔离)
- Stats 走 FastAPI, 不让 Next.js 直连 Neo4j

## 端到端流程 (录一条 QA)

1. 浏览器打开 `/knowledge/qa`
2. 选 dataset (顶 nav)
3. 填问题/答案 + 标签
4. 点 "录入 Dify" → `POST /api/knowledge/qa` → BFF → Dify createDocumentByText
5. 最近 20 条列表 SWR 1s 轮询 Dify 文档状态

## Schema 驱动

加节点/关系: 改 `configs/knowledge-schema.yaml` + `web/lib/schema-types.ts` 两处, 不改代码。
```

- [ ] **Step 2: README 加链接**

在 README.md "文档" 段加一行:

```markdown
| [docs/knowledge-management-page.md](docs/knowledge-management-page.md) | 知识管理页使用说明 |
```

- [ ] **Step 3: 跑全量验证**

```bash
uv run pytest tests/ -m "not slow" -q
cd web && bun run test && bun run typecheck && bun run lint
uv run ruff check src/rag/kg/ tests/test_kg_*.py
```

Expected: 全过

- [ ] **Step 4: 提交**

```bash
git add docs/knowledge-management-page.md README.md
git commit -m "docs: 新增 knowledge-management-page.md + README 链接"
```

---

## Task 8.5: PR 8 验证 + 收尾

- [ ] **Step 1: 跑所有测试**

Run: `uv run pytest tests/ -m "not slow" -q && cd web && bun run test`
Expected: 全过

- [ ] **Step 2: 端到端手测 (8 PR 全景)**

启动 FastAPI + Next.js, 浏览器依次打开:
- `/knowledge` → 看 4 统计卡 + 4 入口 + 空状态
- `/knowledge/qa` → 录 1 条 → 看到 Dify 控制台有新 doc
- `/knowledge/documents` → 下载 Excel 模板, 上传, 提交 → Dify 看到批 doc
- `/knowledge/triples` → 录 1 条 → Neo4j Browser 看到新节点/边
- `/knowledge/batch` → 上传 JSON, 跑后台任务 → 进度更新
- 顶 nav `?` → Schema 浏览器 → 看到 4 节点 5 关系

- [ ] **Step 3: 验证 git log (所有 PR 累计)**

Run: `git log --oneline | head -50`
Expected: 看到 8 个 PR 全部 commit, 总计 30+ 个 commit

- [ ] **Step 4: 项目总结**

本项目完成:
- 4 个新 yaml / 1 个后端子包 (5 个文件)
- 5 个新页面 / 1 个 BFF 路由组 (10+ 路由) / 1 个 lib 模块 (3 文件)
- 60+ 个新单测 (后端 35 + 前端 25+)
- 2 个新文档

下一步: 创建 PR 提到 origin, 收 review。

---
