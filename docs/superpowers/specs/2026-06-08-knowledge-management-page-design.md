# 知识库 + 知识图谱管理页 设计

**日期**: 2026-06-08
**状态**: 设计已批准, 待实施
**作者**: 设计对话沉淀

## Context

项目当前已有产品订货号解析服务 (FastAPI, 端口 8000) 和 RAG 离线流水线 (`src/rag/`), 但 **Dify 知识库和 Neo4j 图谱的"录入环节"没有友好的管理界面**:
- 业务人员想把 FAQ/产品手册喂给 Dify, 只能走 Dify 控制台或 curl
- 工程师想往 Neo4j 写三元组, 只能跑 `scripts/neo4j_import.py` CLI + 准备 YAML
- 两类用户操作目标不同, 但目前都没有路径

Dify 知识库 (Datasets → 向量库) 和 Neo4j (实体-关系图谱) 是两个独立系统:
- **Dify Datasets**: RAG 检索用, 文档分段 → embedding → 写入 Qdrant/Weaviate 等向量库
- **Neo4j**: 结构化实体-关系推理, 适合"产品-系列-规格"类查询

本设计为后台新增一个 `/knowledge` 模块, 把这两条录入路径统一到一个管理页面。

## 目标

1. **业务人员能自助录入** QA 对、产品文档到 Dify, 不需要找工程师
2. **工程师能批量写入** 三元组到 Neo4j, 走表单 + 模板下载
3. **统一 Dashboard** 看 4 类知识资产总量、活跃任务、最近活动
4. **Schema 驱动**: 加节点/关系类型只改 YAML, 不改代码
5. **行业最佳实践**: 文件幂等去重、上传预览校验、失败行可下载、索引状态实时反映、retriever 自测

## 非目标 (YAGNI)

- 多用户实时协作编辑 (v1 用乐观锁)
- 全文搜索 (用 Dify 自带 retriever)
- 权限分级 / SSO (v1 假设内网可信环境, BasicAuth 占位)
- 工作流编排 (v1 只做"录入", 不接 Dify workflow 节点执行)
- 图 schema 迁移/清理/备份 (本期只新增)

## 架构总览

### 混合架构: Next.js 写 Dify, FastAPI 写 Neo4j

```
┌──────────────────── Browser (Next.js Client) ────────────────────┐
│ /knowledge (Dashboard)                                            │
│     ├─ /knowledge/qa         ← 写 Dify (TS)                     │
│     ├─ /knowledge/documents  ← 写 Dify (TS)                     │
│     ├─ /knowledge/triples    ← 写 Neo4j (经 FastAPI)            │
│     └─ /knowledge/batch      ← 双写: Dify(TS) + Neo4j(FastAPI)  │
└──────────────────┬─────────────────────────┬────────────────────┘
                   │ fetch                   │ fetch
       ┌───────────▼──────────┐   ┌──────────▼──────────────┐
       │ Next.js API Routes   │   │ FastAPI (port 8000)     │
       │ (BFF for Dify)       │   │  - 现有: /decode, ...   │
       │  - DatasetsClient    │   │  - 新增:                 │
       │  - Document upload   │   │    /api/kg/triples      │
       │  - Retriever test    │   │    /api/kg/batch        │
       │  - Templates (xlsx)  │   │    /api/kg/tasks/{id}   │
       │  - Stats (从 FastAPI │   │    /api/kg/stats        │
       │    拉, 不直连 Neo4j) │   │  Neo4jClient (Python)   │
       │                      │   │  + InMemory TaskStore   │
       │  DIFY_API_KEY 在     │   │  + BackgroundTasks      │
       │  server env          │   │  NEO4J_* 在 server env  │
       └──────────┬───────────┘   └──────────┬──────────────┘
                  │                           │
                  ▼                           ▼
            Dify REST API                Neo4j Bolt
            (Datasets endpoints)
```

**设计要点**:
- 浏览器绝不能拿到 Dify/Neo4j 凭据, 全部走 BFF
- Stats 走 FastAPI 不让 Next.js 直连 Neo4j (统一凭据管理)
- 现有 Python 后端 (产品解析 + RAG ingest) 不动, 平行新增
- Datasets API 选型参考 [Dify 官方文档](https://docs.dify.ai/api-reference/dataset)

## 视觉与交互

### 视觉风格: 卡片+数据看板 (C)
- 白底 + slate 主色 + 蓝紫渐变强调色
- shadcn/ui (Default + Slate) 全程使用
- 统计卡片用渐变数字、彩色徽章
- 体现"数据感"和"专业感", 不浮夸

### 布局: Dashboard 入口 + 顶部 Tab (C)
- `/knowledge` 首页: 4 张统计卡片 + 4 个入口卡 + 最近活动时间线
- 点进各 Tab 后切到"顶部 Tab 横向排列"形态 (跟现有 /decode 风格一致)
- 顶部加 dataset 切换器 + 环境徽章 (DEV/STAGING/PROD) + Dify 健康状态点

### 组件清单 (shadcn/ui)
- `card`, `tabs`, `table`, `form` (react-hook-form 适配), `input`, `textarea`
- `button`, `badge`, `alert`, `dialog`, `dropdown-menu`, `select`, `combobox`
- `toast` (sonner), `progress`, `tooltip`, `popover`, `separator`, `skeleton`
- 新增: `DataTable`, `FileDropzone`, `TaskStatusBadge`, `SchemaFieldRenderer`, `ErrorReport`

## Schema 配置文件

### 路径: `configs/knowledge-schema.yaml`

```yaml
# 加节点/关系不用改代码, 前端表单和后端校验都从这读
nodes:
  - name: Product
    color: blue
    fields:
      - { key: model,        label: 产品订货号, type: string,  required: true,  unique: true }
      - { key: name,         label: 产品名称,   type: string,  required: true }
      - { key: series,       label: 所属系列,   type: ref, ref_to: Series, required: true }
      - { key: manufacturer, label: 厂商,       type: enum, options: ["Siemens","ABB","Schneider"], required: true }

  - name: Series
    color: purple
    fields:
      - { key: name,         label: 系列名,   type: string,  required: true, unique: true }
      - { key: manufacturer, label: 厂商,     type: enum,   options: ["Siemens","ABB","Schneider"], required: true }
      - { key: description,  label: 说明,     type: text }

  - name: Document
    color: green
    fields:
      - { key: title,       label: 标题,     type: string,  required: true }
      - { key: source,      label: 来源,     type: enum, options: ["manual","dify","url"] }
      - { key: url,         label: URL,      type: url }
      - { key: uploaded_at, label: 上传时间, type: datetime, readonly: true }

  - name: QAPair
    color: orange
    fields:
      - { key: question, label: 问题, type: text,   required: true }
      - { key: answer,   label: 答案, type: text,   required: true }
      - { key: tags,     label: 标签, type: string,      multiple: true }

relations:
  - { name: BELONGS_TO,      from: Product,  to: Series,    cardinality: many_to_one }
  - { name: ABOUT,           from: QAPair,   to: Product,   cardinality: many_to_one }
  - { name: REFERENCES,      from: QAPair,   to: Document,  cardinality: many_to_many }
  - { name: DESCRIBES,       from: Document, to: Product,   cardinality: many_to_one }
  - { name: COMPATIBLE_WITH, from: Product,  to: Product,   cardinality: many_to_many }
```

**关键约束**:
- 节点字段 `type: ref` + `ref_to: NodeName` 表示外键引用, 前后端都要校验
- 关系类型按 from/to 节点对在表单里限定, 避免乱连
- 加新节点/关系: 加 yaml 段, **不改代码**

## 4 个 Tab 设计

### Tab 1 · `/knowledge/qa` (QA 对 → Dify 向量库)

**布局**: 左 60% 表单, 右 40% 最近 20 条列表

**字段**:
- 知识库选择: 顶部 `Dify Dataset` combobox (v1 单选, v2 多选)
- 问题 *: textarea (必填)
- 答案 *: textarea (必填)
- 标签: chip-input, multiple
- 关联产品: combobox 多选, 从 Neo4j `Product` 拉 (走 FastAPI `/api/kg/products`)
- 引用文档: combobox 多选, 从 Dify `Document` 拉
- 同步到 Neo4j: checkbox (默认关; 勾上时在 Neo4j 写 `QAPair` 节点 + `ABOUT` 关系)
- [保存草稿] 按钮 → 写 localStorage
- [录入 + 立即测试] 按钮 → 保存完弹 dialog, 用 `DifyClient.chatQuery` (TS 端口) 发一句验证; v1 调用 `POST {DIFY_BASE}/v1/chat-messages` 阻塞模式

**API 调用**:
- 创建: `POST /api/knowledge/qa` (Next.js) → `POST {DIFY_BASE}/v1/datasets/{id}/document/create_by_text` + Neo4j (可选)
- 列表: `GET /api/knowledge/qa?dataset_id=&page=`

### Tab 2 · `/knowledge/documents` (文档 → Dify 向量库)

**布局**: 顶部工具栏 + 大拖拽区 + 三步流程展开面板

**工具栏**:
- `[📥 下载 Excel 模板]` `/api/knowledge/templates/excel`
- `[📥 下载 JSON 模板]` `/api/knowledge/templates/json`
- `[📋 查看字段说明]` 弹 dialog 显示 schema

**拖拽区** (`react-dropzone`):
- 接受: `.xlsx`, `.xls`, `.json`
- 上限: 50MB (client 拦截)
- 拖入后立刻调 `POST /api/knowledge/documents/upload` 拿解析结果

**三步流程 (核心亮点)**:
1. **解析**: 显示 `✅ 解析成功 · 124 行 · 0 错误 · 3 警告`
2. **校验 (Zod)**: 错误行号 + 错误原因, `❌ 第 7 行 model 字段缺失`, `[📥 下载错误行 CSV]`
3. **提交 (异步)**: 修正后点提交, 调 `POST /api/knowledge/documents/commit` 拿 task_id, SWR 轮询 1s

**索引状态反映**:
- 提交后表格行实时显示 Dify 返回的索引状态 (`queued` / `indexing` / `completed` / `error`)
- 失败行可下载 CSV

### Tab 3 · `/knowledge/triples` (三元组 → Neo4j)

**布局**: 顶部工具栏 + 多行可编辑表格

**工具栏**:
- `[+ 新增行]`, `[📋 从 JSON 粘贴]`, `[📥 下载模板]`, `[批量提交]`, `[清空]`

**表格列**:
| # | 起点 (类型) | 关系 | 终点 (类型) | 属性 | × |
| --- | --- | --- | --- | --- | --- |
| 1 | [Product ▼] | [BELONGS_TO ▼] | [Series ▼] | {...} | × |
| 2 | ... | ... | ... | ... | × |

**下拉联动规则**:
- 起点下拉: 自动填 schema 中所有节点的 name
- 关系下拉: 自动限定 `from=起点类型` 的合法关系
- 终点下拉: 自动填 schema 中所有节点
- 提交时: 类型不匹配或缺字段的行高亮

**API 调用**:
- `POST /api/kg/triples` (FastAPI) → Neo4j `UNWIND $rows AS row MERGE ...` 事务
- 同步返回成功/失败明细
- 提交后可选"展开 1 跳邻居" 按钮 → `POST /api/kg/subgraph` 返回节点+边数据

### Tab 4 · `/knowledge/batch` (批量导入 + 任务面板)

**布局**: 顶部操作 + 活跃任务 + 历史记录

**操作**:
- `[📁 选择 JSON]`, `[📁 选择 Excel]`, `[⏵ 提交为后台任务]`
- JSON 包格式示例 (`web/public/templates/knowledge-batch.json`):
  ```json
  {
    "items": [
      {
        "target": "dify",
        "type": "qa",
        "payload": { "question": "1LE0001 是什么?", "answer": "...", "tags": ["电机"] }
      },
      {
        "target": "neo4j",
        "type": "triple",
        "payload": { "from": {"label": "Product", "key": "model", "value": "1LE0001"}, "rel": "BELONGS_TO", "to": {"label": "Series", "key": "name", "value": "1LE 系列"} }
      }
    ]
  }
  ```

**活跃任务** (SWR 1s 轮询):
- 任务 ID, 类型, 进度条, 错误数, ETA

**历史** (近 7 天, 持久化到 SQLite):
- 状态 (`done`/`partial`/`failed`/`cancelled`), 时间, 数量, 错误数
- `[📥 下载错误报告]`

## API 契约

### Next.js API Routes (BFF for Dify)

| 端点 | 方法 | 用途 | 备注 |
|---|---|---|---|
| `/api/knowledge/stats` | GET | 4 卡片数据 (Neo4j 节点数 + Dify 文档数 + QA 对数) | 内部: Neo4j 走 FastAPI `/api/kg/stats`, Dify 走 `DifyClient.listDatasets` + 文档列表; 缓存 30s |
| `/api/knowledge/schema` | GET | 节点/关系定义 | 从 yaml 读 |
| `/api/knowledge/datasets` | GET | 列 Dify dataset | 缓存 30s |
| `/api/knowledge/qa` | POST | 创建 QA 对 | 同步, 小数据 |
| `/api/knowledge/qa` | GET | 列 QA 对 | 分页+搜索 |
| `/api/knowledge/qa/retrieve` | POST | Retriever 自测 | 调 Dify `POST /v1/datasets/{id}/retrieve` |
| `/api/knowledge/documents/upload` | POST | 接收文件, 解析 | 同步返回解析结果 |
| `/api/knowledge/documents/commit` | POST | 提交已校验数据 | 提交即返 task_id |
| `/api/knowledge/documents` | GET | 列文档 | 含索引状态 |
| `/api/knowledge/templates/[excel\|json]` | GET | 下发模板 | 读 `static/knowledge-templates/` |
| `/api/knowledge/health` | GET | Dify 健康检查 | 调 Dify `/v1/datasets?limit=1` |

### FastAPI 路由 (Neo4j)

| 端点 | 方法 | 用途 | 备注 |
|---|---|---|---|
| `/api/kg/stats` | GET | 4 节点 label 计数 | Neo4j `MATCH (n) RETURN count(n) GROUP BY label` |
| `/api/kg/products` | GET | 列 Product 节点 (供 QA tab combobox) | 分页+搜索 |
| `/api/kg/triples` | POST | 单批提交 | 同步, 事务 |
| `/api/kg/triples` | GET | 列三元组 | 分页+过滤 |
| `/api/kg/subgraph` | POST | 取节点 1 跳邻居 | 节点 ID 列表入参 |
| `/api/kg/batch` | POST | 大批量提交 | 立即返 task_id, BackgroundTasks 跑 |
| `/api/kg/tasks/[id]` | GET | 任务状态 | 内存 TaskStore |

### 任务状态机

```
queued ──→ running ──┬──→ done      (全部成功)
                     ├──→ partial   (≥ 80% 成功)
                     ├──→ failed    (致命错)
                     └──→ cancelled (用户取消)
```

### 错误处理

| 失败场景 | 表现 | 恢复 |
|---|---|---|
| Dify API 超时 | Toast + 任务入队 | 后台重试 3 次 |
| Dify 索引失败 | 任务标 `partial`, 错误行可下载 | 用户决定"重试/跳过" |
| Neo4j 唯一约束冲突 | 行级报错"已存在" | `MERGE` 更新或 `CREATE` 跳过 |
| 上传文件 > 50MB | 上传前 client 拦截 + Toast | 提示分片或降级 |
| Excel 列错位 | "找不到 model 列" | 用户手动改 mapping |
| Neo4j 断连 | 顶部 dot 变红 + 任务暂停 | 恢复后自动续跑 |

## Python 端新增模块 (FastAPI)

```
src/rag/kg/                      # 新建子包
├── __init__.py
├── client.py                    # Neo4j 客户端 (事务, UNWIND 批量 MERGE)
├── schema.py                    # 从 yaml 加载节点/关系, 校验引用完整性
├── tasks.py                     # 后台任务 + TaskStore
├── router.py                    # FastAPI 路由
└── exceptions.py                # KgError, DuplicateNodeError, ...
```

### `client.py` 关键 API
- `connect()` → Driver 单例
- `merge_node(label, props, unique_keys) -> dict`
- `merge_relation(from_label, from_key, rel_type, to_label, to_key, props)`
- `batch_upsert_triples(rows: list[TripleRow]) -> BatchResult`
- `count_by_label() -> dict[str, int]`
- `subgraph(node_ids: list[str], depth=1) -> {nodes, edges}`

### `tasks.py` 状态机
- `TaskStore` (in-memory `dict[str, TaskStatus]`, v1)
- `submit_task(type, payload) -> task_id`
- `get_task(task_id) -> TaskStatus`
- `cancel_task(task_id)`
- 历史持久化: SQLite `data/kg_tasks.db` (`web/data/` 不放, 放 `data/`)

## Next.js 端新增结构

```
web/
├── app/
│   └── knowledge/
│       ├── layout.tsx                 # 顶部 dataset 切换 + 环境徽章 + 健康点
│       ├── page.tsx                   # Dashboard
│       ├── qa/
│       │   ├── page.tsx
│       │   └── page.test.tsx
│       ├── documents/
│       │   ├── page.tsx
│       │   └── page.test.tsx
│       ├── triples/
│       │   ├── page.tsx
│       │   └── page.test.tsx
│       └── batch/
│           ├── page.tsx
│           └── page.test.tsx
├── components/
│   └── knowledge/
│       ├── DataTable.tsx
│       ├── FileDropzone.tsx
│       ├── TaskStatusBadge.tsx
│       ├── SchemaFieldRenderer.tsx
│       ├── ErrorReport.tsx
│       ├── DatasetSwitcher.tsx
│       └── EnvBadge.tsx
├── lib/
│   ├── dify-datasets.ts               # TS 版 Datasets 客户端
│   ├── dify-datasets.test.ts
│   ├── parse-excel.ts                 # xlsx 解析
│   ├── parse-excel.test.ts
│   ├── schema-renderer.tsx            # 动态表单
│   └── schema-renderer.test.tsx
└── public/
    └── templates/                     # 内置 JSON 模板 (Excel 由后端生成)
        └── knowledge-import.json
```

### Datasets 客户端 (TS) 关键 API
- `listDatasets() -> Dataset[]`
- `createDocumentByText(datasetId, name, text, indexingMode) -> Document`
- `createDocumentByFile(datasetId, file, indexingMode) -> Document`
- `getDocumentStatus(datasetId, docId) -> 'queued'|'indexing'|'completed'|'error'` (Dify 无独立状态端点, 从 `GET /v1/datasets/{id}/documents` 的 indexed 字段读; 前端按 docId 过滤)
- `retrieve(datasetId, query, topK) -> RetrievalResult[]`
- `deleteDocument(datasetId, docId)`
- `updateDocumentByFile(...)` (重建索引)
- 全部走 Next.js server-side fetch, 凭据在 env

## 模板文件

### Excel 模板 (后端生成)
- 路径: `static/knowledge-templates/knowledge-import.xlsx`
- v1 决策: 手工生成 1 个固定模板 (列头硬编码); 后续 PR 再升级为从 yaml 动态生成
- 包含示例行 + 数据验证下拉
- 通过 `GET /api/knowledge/templates/excel` 下发, Content-Type: `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`

### JSON 模板 (前端内置)
- `web/public/templates/knowledge-import.json`
- 包含完整 schema 注释 + 1 个 example

## 测试策略

### Python 后端
- `tests/test_kg_schema.py` — yaml 加载、节点/关系引用完整性
- `tests/test_kg_client.py` — Neo4j 客户端 (testcontainers 起真 Neo4j)
- `tests/test_kg_triples.py` — 单条 MERGE, UNWIND 批量, 事务回滚
- `tests/test_kg_tasks.py` — TaskStore 状态机
- `tests/test_kg_router.py` — FastAPI 路由 httpx 测试
- `tests/test_kg_dedupe.py` — SHA-256 重复检测

### Next.js 前端
- `web/lib/dify-datasets.test.ts` — 用 msw mock
- `web/lib/parse-excel.test.ts` — Excel 解析, 错误行定位
- `web/lib/schema-renderer.test.tsx` — 动态表单字段映射
- `web/app/knowledge/qa/page.test.tsx` — 表单, Zod 校验, 错误展示
- `web/app/knowledge/documents/page.test.tsx` — 三步流程
- `web/app/knowledge/triples/page.test.tsx` — 多行编辑, 类型联动
- `web/app/knowledge/batch/page.test.tsx` — 任务轮询
- E2E: Playwright 跑"打开 /knowledge → 录 QA 对 → 看到 dashboard 数字 +1"

## 主动补的功能清单

1. **去重幂等**: 上传文件先算 SHA-256, Datasets/Neo4j 都先查再写
2. **预览/校验中间层**: Excel/JSON 上传后**必须**先解析展示, 错误行高亮
3. **失败行可下载**: 100 行错 3 行 → 一键下载 CSV
4. **Dify 索引状态实时反映**: `queued`/`indexing`/`completed` 卡片轮询
5. **Retriever 自测**: 录入后一键试查
6. **草稿保存 (localStorage)**: 表单填一半关浏览器不丢
7. **最近活动时间线**: Dashboard 显示"2 小时前 录入了 50 个 QA 对"
8. **Neo4j 图谱子图预览**: 三元组录入后点节点能展开 1 跳邻居
9. **批量操作的二次确认 Dialog**
10. **失败重试 / 跳过错误**: 按行/按文件级粒度重试
11. **Schema 浏览器**: 右上角 `?` 弹窗
12. **多 dataset 切换**
13. **环境标识徽章** (DEV/STAGING/PROD)
14. **Dify 健康检查** 顶部 dot
15. **Audit log** (who/when/what/result, 写 SQLite)
16. **错误边界 ErrorBoundary**
17. **空状态引导** (首次进入给 3 个示例)
18. **键盘快捷键** (⌘+S, ⌘+K, Esc)
19. **Datasets 分段配置 UI** (按段落/按分隔符/按长度)

## 行业最佳实践引用

- **Schema 驱动 UI**: 自建轻量 renderer, 不引 `react-jsonschema-form`
- **Form 库**: `react-hook-form` + `zod resolver` (Zod 已是项目栈)
- **数据获取**: `swr` 轮询任务状态, `revalidateInterval: 1000`
- **文件上传**: `react-dropzone` + `papaparse` + `xlsx`
- **去重与幂等**: SHA-256 hash, 参考 Dify Cloud
- **Datasets API**: 官方文档 [docs.dify.ai/api-reference/dataset](https://docs.dify.ai/api-reference/dataset)
- **Neo4j 写入**: `UNWIND $rows AS row MERGE ...` 事务, 比逐条快 10-50×
- **A11y**: shadcn/ui 默认 WCAG AA
- **错误处理**: 失败行**必须可下载** (Dify/Notion/Linear 一致)
- **审计**: 每次 commit 写 audit log (GitHub PR 模式)

## 风险与边界

- **Dify rate limit**: 未明示, 实现里加简单 throttle (并发 5)
- **大文件**: Excel 50MB 硬上限, 超了 client 拦截
- **任务持久化**: v1 in-memory, dev server 重启任务丢; 后续接 Redis
- **多进程**: FastAPI 多 worker 跑时 in-memory TaskStore 不共享, v1 假设单 worker
- **Neo4j 凭据**: 全部 server env, 不进前端 bundle

## 实施顺序 (建议 PR 拆法)

1. PR 1: `configs/knowledge-schema.yaml` + `src/rag/kg/` 后端骨架 (无前端)
2. PR 2: Next.js `app/knowledge/*` 4 个空页面 + 顶部导航
3. PR 3: Dashboard 卡片 + Datasets 客户端 + Dify 集成
4. PR 4: Tab 1 (QA) 完整流程
5. PR 5: Tab 2 (Documents) 三步流程 + 模板下载
6. PR 6: Tab 3 (Triples) + Neo4j 写入
7. PR 7: Tab 4 (Batch) + 后台任务 + 任务面板
8. PR 8: Schema 浏览器 + Audit log + 收尾打磨

每个 PR 独立可测, 都能跑现有测试套件不挂。
