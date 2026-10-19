# 知识图谱模块 (src/rag/kg/)

为 RAG 后台 `/knowledge` 管理页提供 Neo4j 写入 / 校验 / 任务管理 / 审计 / 模板导出能力。

## 子模块

| 文件 | 职责 |
|---|---|
| `schema.py` | 加载 `configs/knowledge-schema.yaml`, 校验节点/关系引用完整性 |
| `neo4j.py` | `Neo4jStore` 通用 Neo4j 驱动封装 (CRUD: upsert_node / find_nodes / upsert_relationship / get_neighbors / delete_node / upsert_entity_knowledge) — 2026-06-09 从 `src/rag/knowledge_graph/` 合并 |
| `client.py` | `KgClient` 业务层, 包装 `Neo4jStore`, UNWIND MERGE 批量写入 + 子图查询 |
| `tasks.py` | in-memory `TaskStore`, 状态机: queued → running → {done, partial, failed, cancelled} |
| `router.py` | FastAPI 路由, 前缀 `/api/kg/*` |
| `templates.py` | Excel/JSON 模板导出 (openpyxl), 给前端 `<a download>` 用 |
| `audit.py` | SQLite 持久化审计日志 (`data/kg_audit.db`), Windows 安全的单连接方案 |
| `exceptions.py` | `KgError` / `DuplicateNodeError` / `InvalidTripleError` / `SchemaError` / `TaskNotFoundError` |
| `__init__.py` | 子包 docstring |

## 端点 (9 个)

| 方法 | 路径 | 用途 |
|---|---|---|
| GET | `/api/kg/stats` | 4 label 节点数 |
| GET | `/api/kg/schema` | 加载并校验 `knowledge-schema.yaml` (前端类型联动用) |
| GET | `/api/kg/products` | 列 Product 节点 (前端 combobox) |
| GET | `/api/kg/templates/{format}` | 模板下载 (format: excel / json) |
| POST | `/api/kg/triples` | 单批三元组 (事务) |
| POST | `/api/kg/batch` | 大批量 (后台任务) |
| GET | `/api/kg/tasks/{id}` | 任务状态 (前端 SWR 轮询) |
| GET | `/api/kg/audit` | 审计日志 (前端表格 + 分页) |

(详细请求/响应 schema 见 [knowledge-management-page.md](knowledge-management-page.md) 第二节 BFF 端点。)

## 加节点/关系

只改 `configs/knowledge-schema.yaml`, 不动代码:

```yaml
nodes:
  - name: NewNode
    fields:
      - { key: name, type: string, required: true, unique: true }

relations:
  - { name: NEW_REL, from: NewNode, to: Product, cardinality: many_to_one }
```

跑 `uv run pytest tests/test_kg_schema.py -v` 校验新加内容合法。

## 关联模块 (不是本包)

| 模块 | 关系 |
|---|---|
| `src/rag/api/routes.py` | 旧 RAG HTTP 路由 (`/api/v1/*`), **未挂到 app**; 生产用 `/api/kg/*` |
| ~~`src/rag/knowledge_graph/`~~ | **2026-06-09 已合并到本包** (`kg/neo4j.py` + `kg/client.py`), 目录已删 |

## 测试

```bash
# 45 个用例
uv run pytest tests/test_kg_*.py -v

# 拆分
uv run pytest tests/test_kg_schema.py    # 9: schema 加载 + 引用校验
uv run pytest tests/test_kg_neo4j.py     # 7: Neo4jStore CRUD (从 tests/rag/knowledge_graph/ 迁来)
uv run pytest tests/test_kg_client.py    # 7: KgClient 批量
uv run pytest tests/test_kg_tasks.py     # 9: 任务状态机
uv run pytest tests/test_kg_router.py    # 7: 端点
uv run pytest tests/test_kg_templates.py # 3: 模板导出
uv run pytest tests/test_kg_audit.py     # 3: 审计写入
```
