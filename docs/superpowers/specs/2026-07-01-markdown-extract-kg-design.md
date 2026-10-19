# Markdown → 实体/关系抽取 → 写 Neo4j 设计 (v3)

**日期**: 2026-07-01 (v3 重写: 单一 Neo4j database, 用 dataset label 多 KG 隔离)
**状态**: 设计已批准 (plan file 待 writing-plans 技能生成)
**对应 plan**: `2026-07-01-markdown-extract-kg-pr1.md` ~ `pr4.md`

## Context

项目 Neo4j 现在靠手工录入 (`/knowledge/triples` 页表单) 或 Excel 导入 (`/knowledge/batch`), 中文文档里有大量"X 是 Y 的 Z" / "X 符合标准 Y" 这种结构化信息, 应该自动抽取。

**v3 关键调整** (2026-07-01 用户决策):
- **项目是内部项目, 只有管理员能修改知识图谱** — 无需 user_hash 隔离
- **单一 Neo4j database** (Community Edition 限制) — 用 `dataset` label 隔离不同数据集 (例: `motor`, `plc`, `sensor`)
- **dataset 白名单** — env `KG_ALLOWED_DATASETS=motor,plc,sensor` 控制, 业务/API/抽取都必须从白名单选, 类似 SQL 注入防御
- **.env `NEO4J_DATABASE=neo4j`** (符合 docker-compose.yml 默认 image)
- **移除** TripleRow user_hash、`user_hash_for` util、ON CREATE/ON MATCH list、ANY() 过滤、(label,key) 唯一约束

**关键事实 (2026-07-01 调研)**:
- Neo4j Community Edition (项目用的 `neo4j:2026.05.0` docker 镜像默认) **只能有 1 个 standard database**
- Enterprise Edition 才支持多 database (composite databases / database aliases)
- 项目无 enterprise license, 必须 1 database + label 隔离

## 目标

实现一个"上传 Markdown → 异步抽取 → 预览校对 → 3 个出口"的服务, **支持多 dataset label 隔离**:
- 上传: 管理员在 `/knowledge/extract` 上传 `.md` 文件, **选 dataset (从白名单)** + 选抽取器 + 切片策略
- 抽取: 后台异步跑, 进度可轮询
- 预览: 实体/关系以表格展示, 可勾选 + 可编辑
- 出口: **写 Neo4j (指定 dataset)** / **导出 JSONL** / **导出 Cypher CREATE 脚本**

## 非目标

- 本期不做文档结构化语义理解 — v1 仅做"段落级 NER + 句子级关系"
- 本期不做增量更新 / 流式抽取 / 在线 sub-second 返回
- 本期不做端到端 RAG 集成
- 本期不做跨 dataset 的实体/关系查询 (管理员需要 Neo4j Browser 自己查)
- ~~本期不删除 / 替换 `graphifyy>=0.8.44` dev dep~~ (2026-07-01 update: **已纳入本 spec**, 见 M2 milestone)
- 本期不做 Markdown 之外的格式
- 本期不做 Neo4j Enterprise 升级路径 (单 DB label 隔离够用)

## 调研结论

### Neo4j Community Edition 限制 (决定 v3 设计)

| 维度 | Community Edition | Enterprise Edition |
|---|---|---|
| Standard databases | **1 个** (`neo4j`) | 任意 |
| Composite databases | ❌ | ✅ |
| Clustering | ❌ | ✅ |
| Online backup | ❌ | ✅ |
| **多 dataset 隔离方案** | **用 label** | 多 DB / composite DB |

→ 项目用 CE, 必须 label 隔离, 不考虑 database 方案 (v2 已废弃).

### Label 隔离的权衡 (2026-07-01 调研)

**优点**:
- 单 DB 完全兼容 Community Edition
- 性能: label 加索引后 query 走索引, 不全表扫
- 写时自动加 label, MERGE 包含 label 即可定位同 dataset 节点

**风险 (应用层必须防御)**:
- ⚠️ Label **不是硬隔离**:query 忘了 `WHERE n:Motor` 会泄露其他 dataset 节点
- 防御方案: 业务侧白名单校验 (类似 SQL 注入), label 必须从预定义列表里选
- ⚠️ 不能加 (label, key) 唯一约束(因为不同 dataset 的同一 key 可合法存在)
- ⚠️ 节点同时属于多个 dataset 时不能直接用 label 区分, 需用 `dataset` 属性 + 应用层 WHERE 过滤

**v3 决定**:
- **单一全局 namespace**: 所有节点 **同时**有业务 label (例 `:Product`) 和 dataset label (例 `:Motor`)。 不用 `:MotorProduct` 这种语义组合。
- **dataset 白名单**: env `KG_ALLOWED_DATASETS=motor,plc,sensor` 单一来源, 业务/API/抽取都必须用这个白名单
- **query 模板统一**: 把 `WHERE <dataset_label>` 抽到 helper, 强制业务侧走 helper

### 业界方案对比 (2026 H1)

| 维度 | 主流做法 |
|---|---|
| 抽取算法 | **LLM + JSON Schema 强约束** (88-97% 准确), 纯 NLP/REBEL 退守高吞吐限定领域 |
| LLM 选型 | 由运行时配置决定, 代码不绑定具体厂商/模型; 走 OpenAI 兼容协议 |
| 抽取后格式 | JSONL `{head, head_type, relation, tail, tail_type, source_span, confidence}` |
| 架构 | **离线异步批处理** (LLM 调用 5-30s/文档) |
| 隔离粒度 | 单租户: **共享 label (CE) 或多 database (EE)**, 多租户 SaaS 才用 user_hash |
| Python 库 | `neo4j-graphrag-python` SimpleKGPipeline, **本项目选 BaseExtractor Protocol 自实现** |

**关于项目里 `graphifyy>=0.8.44` dev dep**: 项目代码 0 import, **M2 milestone 顺手删**.

**2026-07-01 事后清理: HanLP + mREBEL 不纳入本项目** (含原因, 详见原 spec v1):
- HanLP 2.1.3 无中文 RE API, 仅 NER, 但 spaCy 已能 NER
- mREBEL `Babelscape/mrebel-large` 3 年无更新, GitHub repo 404

**变更范围**: extractor_id 白名单从 4 个减至 2 个 (spacy_rule / llm_pydantic).

### 输入形态说明

本特性的输入是**已经解析过的 Markdown 纯文本**, 不是 PDF 原文件。前序流水线已经把 PDF / DOCX / 图片 → Markdown, 业界文章"PDF 表格解析" **在本项目范围外**.

### 项目内部已有 80% 零件 (不需要重写)

- **Neo4j 写层 (v3 适配)**: `KgClient.batch_upsert_triples` + `TripleRow` 已就绪, 加 `dataset` 参数 + 写入加 dataset label
- **LLM 调用**: `OpenAILLM` + `buyer_profile/extractor.py` prompt 模板
- **Embedding**: `OpenAIEmbedder` OpenAI 兼容协议
- **后台模式**: `FastAPI BackgroundTasks`
- **临时任务状态**: `TaskStore` (`src/kg/tasks.py`)
- **前端模板**: `knowledge/batch/page.tsx` + `triples-form.tsx` + `usePolling` + `<TaskStatusBadge>` + `<FileDropzone>`
- **审计**: `@audited(action, target_type)` 装饰器 + `kg_audit` ORM 表

### 缺的 20% (要补)

1. 3 个 splitter (heading / token / semantic)
2. `KgClient` 加 `dataset` 参数 + cypher 自动注入 dataset label (5 处方法签名调整)
3. 2 个抽取器 + BaseExtractor Protocol
4. 后台 pipeline 真执行器 `extract_runner.py`
5. PG 临时表 `kg_extract_items` (含 `dataset` 字段) → alembic 迁移
6. Neo4j dataset label 索引 (性能必需) + dataset label 白名单 admin API
7. 前端 3 页面 + BFF + i18n 同步

## 架构设计

### 后端目录布局

```
packages/service/src/kg/
├── client.py                      # [改] 所有方法加 dataset: str 参数, cypher 自动注入 dataset label
├── router.py                      # [改] 新加 9 端点 + dataset query param + 删 (label,key) 约束相关
├── extract_runner.py              # [新] 后台 pipeline
├── config_loader.py               # [新] 加载 configs/extractors/*.yaml
├── datasets.py                    # [新] dataset 白名单 (env 读取) + 校验 + GET /datasets
├── extractors/
│   ├── base.py                    # [新] BaseExtractor Protocol + 数据类
│   ├── spacy_rule/                # [新] spaCy Matcher + EntityRuler + "X 是 Y 的" 规则
│   └── llm_pydantic/              # [新] LLM + Pydantic + tenacity retry
├── splitters/
│   ├── base.py                    # [新] BaseSplitter Protocol + TextChunk
│   ├── heading.py                 # [新] 按 #/##/### 切
│   ├── token.py                   # [新] tiktoken cl100k_base 滑窗
│   └── semantic.py                # [新] 句切 + OpenAIEmbedder cosine 距离 + 降级 heading
└── (existing) tasks.py / audit.py / ...

packages/service/src/storage/migrations/versions/
└── <date>_kg_extract_items.py     # [新] alembic 迁移 + dataset 字段 + 3 索引
```

### 抽象接口

```python
# extractors/base.py (跟 v2 一致)
@dataclass
class ExtractedEntity:
    text: str
    label: str           # 业务 label, 例 "Product" / "Spec"
    chunk_id: str
    char_span: tuple[int, int]
    confidence: float = 1.0

@dataclass
class ExtractedRelation:
    head: str
    rel_type: str
    tail: str
    chunk_id: str
    confidence: float = 1.0
    rule_type: Literal["compatibility", "dependency", "exclusion", "derating", "factual"] = "factual"

@dataclass
class ExtractionResult:
    entities: list[ExtractedEntity]
    relations: list[ExtractedRelation]
    extractor_id: str
    elapsed_ms: int
    error: str | None = None

class BaseExtractor(Protocol):
    extractor_id: str
    def extract(self, chunks: list[TextChunk]) -> ExtractionResult: ...


# splitters/base.py
@dataclass
class TextChunk:
    chunk_id: str          # sha256[:12]
    text: str
    meta: dict             # heading_path / start_line / token_count

class BaseSplitter(Protocol):
    splitter_id: str
    def split(self, text: str, source_uri: str) -> list[TextChunk]: ...
```

### Neo4j dataset label 隔离 (v3 核心改造)

**核心接口调整**:

```python
# src/kg/client.py — 加 dataset 参数
class KgClient:
    def __init__(
        self,
        store: Neo4jStore | None = None,
        dataset: str = "neo4j",  # 默认 dataset, 所有方法透传
    ):
        self._store = store or Neo4jStore()
        self._dataset = dataset
        validate_dataset(dataset)  # 强校验在白名单内

    def batch_upsert_triples(self, rows: list[TripleRow]) -> BatchResult:
        # cypher 自动追加 WHERE n:`<Dataset>` 过滤, 防跨 dataset 泄露
        ...

    def list_nodes(self, skip=0, limit=100) -> list[dict]:
        # cypher 自动加 WHERE n:`<Dataset>`, 防忘加 WHERE
        ...
```

**dataset 白名单机制** (防 label 注入, 类似 SQL 注入防御):

```python
# src/kg/datasets.py
import os
from loguru import logger

# env 控制的允许列表 (DBA 决定哪些 dataset 业务侧能用)
ALLOWED_DATASETS: list[str] = []


def load_allowed_datasets_from_env() -> list[str]:
    """从 env KG_ALLOWED_DATASETS (comma-separated) 加载白名单

    例: KG_ALLOWED_DATASETS=motor,plc,sensor
    启动时调一次, 后续业务代码用模块级 ALLOWED_DATASETS (避免每次 IO)
    """
    raw = os.getenv("KG_ALLOWED_DATASETS", "motor")  # 默认值兜底
    return [d.strip() for d in raw.split(",") if d.strip()]


def list_datasets() -> list[str]:
    """返白名单 (snapshot, 启动时读 env, 不动态改)"""
    return list(ALLOWED_DATASETS)


def validate_dataset(dataset: str) -> None:
    if dataset not in ALLOWED_DATASETS:
        raise ValueError(
            f"Neo4j dataset label 不在白名单: {dataset!r} (allowed={ALLOWED_DATASETS})"
        )
    if not dataset.isidentifier():
        raise ValueError(f"Neo4j dataset label 必须是合法 identifier: {dataset!r}")


# main.py 启动时调一次
ALLOWED_DATASETS = load_allowed_datasets_from_env()
logger.info("KG allowed datasets: {}", ALLOWED_DATASETS)
```

**Cypher 模板示例**:

```cypher
-- batch_upsert_triples (v3 加 dataset label 隔离)
UNWIND $rows AS row
MERGE (a:Product:`<Dataset>` {`model`: row.from_value})
MERGE (b:Spec:`<Dataset>` {`name`: row.to_value})
MERGE (a)-[r:HAS_SPEC]->(b)
SET r += row.properties
RETURN count(r) AS cnt

-- list_nodes (v3 加 dataset 过滤)
MATCH (n:Product)
WHERE n:`<Dataset>` AND size(labels(n)) > 0
RETURN id(n) AS id, n.model AS model, n.name AS name
```

**关键约束**:
- `dataset` 必须在 ALLOWED_DATASETS 白名单 (env 读, 启动固化)
- `dataset` 必须是合法 identifier (字母数字下划线开头, `.isidentifier()` 校验)
- 业务侧 (API / 抽取 / 导入脚本) 严禁接受任意字符串当 dataset label

### 配置文件

`packages/service/configs/extractors/{spacy_rule,llm_pydantic}.yaml`

`configs/extractors/llm_pydantic.prompt.txt` 模板要求:
- system prompt 明文要求 LLM 给每条关系打 `rule_type` 标签, 5 选 1: `compatibility` / `dependency` / `exclusion` / `derating` / `factual`

### kg_extract_items 表 (含 dataset 字段)

```python
# alembic migration: 2026-07-01_kg_extract_items
sa.Column("id", sa.BigInteger, primary_key=True),
sa.Column("task_id", sa.Text, nullable=False),
sa.Column("dataset", sa.Text, nullable=False),  # 2026-07-01: 记录写哪个 dataset label
sa.Column("extractor", sa.Text, nullable=False),
sa.Column("splitter", sa.Text, nullable=False),
sa.Column("kind", sa.Text, nullable=False),  # 'entity' / 'relation'
sa.Column("payload", JSONB, nullable=False),
sa.Column("selected", sa.Boolean, nullable=False, server_default=sa.true()),
sa.Column("chunk_id", sa.Text),
sa.Column("corrected_payload", JSONB),
sa.Column("confirmed_at", sa.TIMESTAMP(timezone=True)),
sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
sa.CheckConstraint("kind IN ('entity', 'relation')", name="ck_kg_extract_items_kind"),
sa.CheckConstraint(
    "dataset IS NOT NULL AND length(dataset) > 0 AND dataset ~ '^[A-Za-z_][A-Za-z0-9_]*$'",
    name="ck_kg_extract_items_dataset_format",
),
```

索引:
- `(task_id, dataset)`: 主查询 (preview / commit / export 都走此 WHERE)
- `(dataset, created_at DESC)`: 列表查询
- `(dataset, confirmed_at) WHERE confirmed_at IS NOT NULL`: 部分索引, 校对率统计

### Dataset 改造 (v3, 替代 v2 的 database 改造和 v1 的 user_hash 改造)

| 改动点 | 工作量 | 文件 |
|---|---|---|
| `KgClient.__init__` 加 `dataset` 参数 + cypher 模板加 `WHERE n:<Dataset>` | 1.5h | `src/kg/client.py:44-205` |
| `list_nodes` / `list_relationships` / `subgraph` / `list_products` 加 dataset query param | 1h | `src/kg/router.py` |
| `submit_triples` 加 dataset query param + audit 记录 | 0.5h | `src/kg/router.py:437-459` |
| `src/kg/datasets.py` 新文件 (env 白名单 + validate + GET /datasets) | 1h | `src/kg/datasets.py` |
| main.py 启动时加载 ALLOWED_DATASETS + 改 kg_router.py 注入 | 0.5h | `src/main.py` + `kg/router.py` |
| Neo4j dataset label 索引 cypher 脚本 + init script (性能必需) | 0.5h | `src/kg/migrations/neo4j_init.cypher` + `scripts/init_neo4j_dataset_indexes.py` |
| 测试 (mock store 验证 cypher 走指定 dataset + 白名单校验) | 1h | `tests/kg/test_client_dataset.py` + `tests/kg/test_datasets.py` |
| 删 graphifyy dev dep + 顺手清 (~10 行杂项) | 0.2h | `pyproject.toml` + `uv.lock` |

## 实施拆分 (7 个 Milestone, 约 28 commits)

| # | Milestone | 文件 | 验证命令 | commits |
|---|---|---|---|---|
| M1 | KgClient dataset 透传 + 现有端点 (list_nodes/list_relationships/products) 加 dataset query param + submit_triples + 删 graphifyy + GET /datasets | `src/kg/client.py` + `src/kg/router.py` + `src/kg/datasets.py` + `main.py` + `pyproject.toml` + tests | `uv run pytest tests/kg/test_client_dataset.py tests/kg/test_router_dataset.py -v` | 4 |
| M2 | Neo4j dataset label 索引 cypher + init script + (label,key) 唯一约束**移除**(不需) | `src/kg/migrations/neo4j_init.cypher` + `scripts/init_neo4j_dataset_indexes.py` + tests | `uv run python -m packages.service.scripts.init_neo4j_dataset_indexes --dataset motor --dry-run` | 2 |
| M3 | 3 个 splitter + BaseSplitter Protocol | `src/kg/splitters/` + tests | `uv run pytest tests/kg/splitters/ -v` | 5 |
| M4 | BaseExtractor + 2 个 extractor (spacy_rule + llm_pydantic; HanLP/mREBEL 已排除) | `src/kg/extractors/` + tests | `uv run pytest tests/kg/extractors/ -v` | 4 |
| M5 | configs + config_loader + kg_extract_items alembic 迁移 (含 dataset 字段 + dataset 格式 CHECK) | `configs/extractors/*.yaml` + `configs/extractors/llm_pydantic.prompt.txt` + alembic + `src/kg/config_loader.py` + tests (mock + AST, 禁真 PG) | `uv run pytest tests/kg/test_config_loader.py tests/migrations/test_kg_extract_items.py` | 3 |
| M6 | extract_runner 后台 pipeline (带 dataset 透传) + 5 端点 list_extractors/list_splitters/upload/start/tasks | `src/kg/extract_runner.py` + `kg/router.py` 新增 + tests | `uv run pytest tests/kg/test_extract_runner.py tests/kg/test_router_extract.py -v` | 5 |
| M7 | 4 端点 preview/items PATCH/commit/export + 7d cron + @audited 4 处 | `kg/router.py` 增 + `@audited` + `src/kg/cron.py` + tests | `uv run pytest tests/kg/test_commit_export.py tests/kg/test_cron.py` | 5 |
| M8 | 前端 3 页面 (含 dataset 下拉) + BFF + lib/api + i18n zh/en + vitest + Playwright 1 冒烟 | `app/[locale]/knowledge/extract/**` + `app/api/**` + `lib/api/knowledge.ts` + `messages/{zh,en}.json` + `knowledge-tabs.tsx` 改 1 行 | `bun run test` + `bun run typecheck` + `bun run test:e2e` | 6 |

**PR 拆分建议**:
- PR1 = M1+M2 (KG dataset label 隔离 + Neo4j 索引 + GET /datasets + 删 graphifyy)
- PR2 = M3+M4+M5 (splitters + extractors + 配置 + 迁移)
- PR3 = M6+M7 (抽取 pipeline + API + cron)
- PR4 = M8 (前端 3 页面 + BFF)

## 错误处理

| 失败点 | 降级行为 |
|---|---|
| `extract()` 整批失败 | `ExtractionResult.error` 字段填字符串, `TaskStore.state="failed"`, 不抛 500 |
| 单 chunk 抽取失败 | 该 chunk 跳过, `errors[]` 累积, 不影响其他 chunk |
| Neo4j 不可达 (`Neo4jCircuitOpen`) | `/commit` 返 `{success: 0, failed: N, errors: ["neo4j 不可达"]}`, audit 标 `result="failed"` |
| Specified dataset 不在 ALLOWED_DATASETS | 422 `dataset 不允许` (前端 GET /datasets 拿列表) |
| Specified dataset 不是合法 identifier | 422 `dataset 非法` |
| Splitter 抛错 | BackgroundTasks catch → `TaskStore.mark_failed` |
| LLM rate limit | `tenacity` 指数退避 3 次后, 该 chunk 标 failed, 任务继续 |
| Markdown 文件 > 5MB | `POST /upload` 返 413 |
| extractor_id / splitter_id 不在白名单 | Pydantic Literal 校验 422 |
| 语义切片 embed 失败 | 降级到 heading splitter, log warning, 任务继续 |

## 测试隔离 (CLAUDE.md 强制 4 模式)

| 模块 | 测试模式 | Fixture | 备注 |
|---|---|---|---|
| `extractors/base.py` + 2 子包 | 模式 1 | `monkeypatch` `OpenAIEmbedder` | 0 PG/Neo4j |
| `splitters/` | 模式 1 | (无) | 纯函数 |
| `config_loader.py` | 模式 1 | (无) | yaml 加载, tmp 文件 |
| `extract_runner.py` | 模式 1 | mock TaskStore + ObjectStore + extractor | 验证状态机 |
| `kg/router.py` 端点 | 模式 1 | `TestClient` + mock KgClient + mock session_scope | 鉴权 + 入参 + 出参 |
| `client.py` dataset 改造 | 模式 1 | MagicMock Neo4jStore | 验证 cypher 加 WHERE n:dataset |
| `datasets.py` 白名单校验 | 模式 1 | monkeypatch env | 纯函数 |
| `kg_extract_items` 迁移 | 模式 1 (AST 验证) | (无) | **不连 PG**, 验 migration 文件结构 + SQL 文本 + CHECK 约束 |
| 前端 vitest | 模式 1 | jsdom + mock fetch | |

**CLAUDE.md §测试隔离 (2026-07-01 phase2)** 强制: **所有 test 禁止直连 PG/Redis/Neo4j**, 必须 mock. AST 验证足够 DDL 校验, 不必真连 PG.

`@audited` 覆盖:
- `POST /start` → `@audited("kg.extract.start", target_type="kg_extract_task")`
- `PATCH /items` → `@audited("kg.extract.items.update", target_type="kg_extract_task")`
- `POST /commit` → `@audited("kg.extract.commit", target_type="kg_extract_task")` (主审计点)
- `GET /export` → `@audited("kg.extract.export", target_type="kg_extract_task")`

## 验证 (Verification)

### 单元测试

```bash
# 后端
uv run pytest tests/kg/ -v                          # ~30 个新 test
uv run pytest tests/migrations/test_kg_extract_items.py -v   # AST 验证 + SQL 文本
uv run ruff format && uv run ruff check --fix && uv run pyright
```

### 手工端到端 (dev 环境)

1. 启动后端 `uv run python main.py` + 前端 `bun run dev`
2. 登录拿 super_admin token
3. 访问 `http://localhost:3000/zh/knowledge/extract`
4. **选 dataset = motor** (从白名单下拉)
5. 选 extractor=`llm_pydantic` + splitter=`heading`
6. 上传 README.md
7. 异步进度轮询
8. 预览实体/关系, 勾选, 编辑
9. 点 "写 Neo4j (motor)" → 验 `MATCH (n:Product) WHERE n:Motor RETURN count(n)` 有数据
10. 点 "导出 JSONL" / "导出 Cypher"
11. **跨 dataset 隔离**: 换 `plc` 抽一次, Neo4j Browser 验 motor 看不到 plc 的节点

### 端到端 (Playwright)

```bash
bun run test:e2e -- --grep "知识图谱.*抽取"
```

## 不要做的事 (Top 8)

1. **MERGE label/rel_type 不可参数化** — 5 元组分组保持不变, dataset label 加进 `MATCH (a:Product:<Dataset>)` 也是字面量, 不破坏 5 元组
2. **业务 enum 走 lookup** — `extractor_id` / `splitter_id` 走 `src/lookups/`, 不许新增 `StrEnum`
3. **测试必须 mock, 不连真 PG/Redis/Neo4j** — 全部走模式 1 mock + AST 验证, 绝不连真 PG (CLAUDE.md 强制)
4. **不复用 ingest/upload** — 新加 `POST /api/kg/extract/upload`, 走 ObjectStore
5. **不用 in-memory 临时表** — `kg_extract_items` 必须落 PG, 含 `dataset` 字段
6. **不把 LLM 抽取同步到请求线程** — 走 `BackgroundTasks`
7. **前端不直调后端** — 走 BFF `app/api/kg/extract/.../route.ts` 透传
8. **dataset label 必须白名单** — 业务侧严禁接受任意字符串当 dataset, 类似 SQL 注入防御 (env `KG_ALLOWED_DATASETS` 控制)
9. **(新)** **不加 (label, key) 唯一约束** — 不同 dataset 同一 key 可合法存在, 唯一约束会破坏抽取

## 关联文档

- 项目根 [CLAUDE.md](../../CLAUDE.md) — 代码质量铁律, 工具链锁定
- 后端 [packages/service/CLAUDE.md](../../packages/service/CLAUDE.md) — API/日志/审计/测试隔离 4 模式
- 前端 [packages/web/CLAUDE.md](../../packages/web/CLAUDE.md) — i18n/封装组件/路由跳转
- Neo4j database 概念: <https://neo4j.com/docs/operations-manual/current/clustering/databases/>
- Neo4j pricing (CE 1 database 限制): <https://neo4j.com/pricing/>
- Neo4j labels 概念: <https://neo4j.com/docs/cypher-manual/current/clauses/labels/>