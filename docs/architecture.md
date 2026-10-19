# 架构

## 系统总览

```
┌─────────────────────────────────────────────────────────────┐
│                       Browser (RAG 后台)                     │
│  /  /decode  /output  /knowledge  (5 主模块 + 4 知识库 Tab)   │
└──────────┬─────────────────────────────────────┬────────────┘
           │ 浏览器拿不到凭据                     │
           ↓                                     ↓
   ┌───────────────────┐              ┌────────────────────┐
   │  Next.js BFF      │              │  直接 fetch         │
   │  /api/knowledge/* │              │  localhost:8000     │
   └─────────┬─────────┘              └──────────┬─────────┘
             │                                    │
             ↓                                    ↓
   ┌──────────────────────────────────────────────────────┐
   │              FastAPI (端口 8000)                       │
   │  /decode  /series  /health                            │
   │  /api/output/*    (RAG 产物文件)                      │
   │  /api/kg/*        (知识图谱 Neo4j)                    │
   │  /api/knowledge/* (BFF 透传到 kg + Dify)              │
   └─────────┬────────────────────────────┬───────────────┘
             ↓                            ↓
        ┌────────┐                  ┌──────────┐
        │ Neo4j  │                  │   Dify   │
        └────────┘                  └──────────┘
             ↑
             │ (离线)
   ┌─────────┴────────────────────────────────────────────┐
   │              RAG 离线流水线 (main.py ingest)            │
   │  PDF → Kreuzberg/Mineru → Markdown                     │
   │  DWG/DXF → EzdxfConverter → Markdown + SVG            │
   │  ZIP → archive_handler 解压 → 递归扫描                  │
   └──────────────────────────────────────────────────────┘
```

**关键设计**:

1. **BFF 隔离**: 浏览器所有 Dify/Neo4j 调用都走 Next.js `/api/knowledge/*`, 凭据只在 server 端
2. **配置驱动**: 业务规则 (YAML/JSON Schema) 改文件不动代码:
   - 产品解码: `configs/product_decoders/**/*.yaml`
   - 知识图谱: `configs/knowledge-schema.yaml` + `web/lib/schema-types.ts`
3. **零兼容代码**: 新项目零技术债, 详见 [dev-conventions.md § shim 禁令](dev-conventions.md#shim-禁令)

## 项目结构

```
rag-refactor/
├── main.py                              # 统一入口 (默认 serve, 子命令 ingest)
├── config.toml                          # RAG 路径 / archive / cad 配置 (代码读)
├── pyproject.toml                       # Python 依赖 (uv 管理)
│
├── configs/                             # 业务配置 (YAML, 部署数据)
│   ├── product_decoders/                # 产品解码规则
│   │   └── motor/siemens/1le0_low_voltage.yaml
│   └── knowledge-schema.yaml            # Neo4j 节点/关系定义
│
├── src/
│   ├── product_decoders/                # 产品订货号解析 (FastAPI, 纯代码)
│   │   ├── app.py                       # FastAPI 工厂 + 挂载全部 router
│   │   ├── engine.py                    # ProductDecoder 核心引擎
│   │   ├── config_loader.py             # YAML 递归加载
│   │   └── output_api.py                # /api/output/* (RAG 产物文件列表/读)
│   │
│   ├── rag/                             # RAG PDF 处理 + 知识图谱
│   │   ├── ingest/                      # 离线流水线
│   │   │   ├── pipeline.py              # 统一入口 process_files + process_path
│   │   │   ├── analyzers/               # PDFAnalyzer 等
│   │   │   └── converters/              # Kreuzberg / Mineru / Ezdxf
│   │   │
│   │   ├── kg/                          # 知识图谱 (Neo4j) — 2026-06 新增
│   │   │   ├── neo4j.py                 # Neo4jStore: 通用驱动封装 (CRUD)
│   │   │   ├── client.py                # KgClient: 业务 API (UNWIND MERGE 批量)
│   │   │   ├── schema.py                # 加载 yaml + 引用完整性校验
│   │   │   ├── tasks.py                 # TaskStore (状态机)
│   │   │   ├── router.py                # /api/kg/* FastAPI 路由
│   │   │   ├── templates.py             # Excel/JSON 模板下载
│   │   │   ├── audit.py                 # 审计日志 (PG ORM 写 kg_audit 表)
│   │   │   └── exceptions.py
│   │   │
│   │   ├── api/                         # 旧 /api/v1 (未挂到 app, 未来清理目标)
│   │
│   └── ...
│
├── tests/                               # Python 测试
│   ├── test_kg_*.py                     # 知识图谱 45 个 (2026-06, 含 neo4j/audit)
│   ├── rag/
│   │   ├── ingest/
│   │   └── api/                         # 旧 API 测试
│   ├── product_decoders/
│   ├── integration/
│   ├── test_main_cli.py
│   ├── test_rag_eval.py
│   └── test_web_apis.py
│
├── web/                                 # Next.js 前端 (2026-06 大重写)
│   ├── app/                             # App Router
│   │   ├── page.tsx                     # / 仪表盘
│   │   ├── decode/page.tsx              # /decode
│   │   ├── output/                      # /output + /output/[file]
│   │   ├── knowledge/                   # /knowledge 5 页面
│   │   │   ├── page.tsx                 # Dashboard
│   │   │   ├── qa/                      # Tab 1: QA 录入
│   │   │   ├── documents/               # Tab 2: 文档上传
│   │   │   ├── triples/                 # Tab 3: 三元组录入
│   │   │   └── batch/                   # Tab 4: 批量导入
│   │   ├── layout.tsx                   # 根 layout (top nav)
│   │   ├── globals.css                  # @import "tailwindcss" + theme vars
│   │   └── api/knowledge/               # BFF 路由 (10 个)
│   │       ├── health/                  # GET  Dify 健康
│   │       ├── stats/                   # GET  Neo4j 节点数
│   │       ├── datasets/                # GET  Dify datasets
│   │       ├── schema/                  # GET  知识图谱 schema
│   │       ├── qa/                      # GET/POST  QA 文档
│   │       ├── qa/retrieve/             # POST  Retriever 自测
│   │       ├── templates/[format]/      # GET  Excel/JSON 模板
│   │       ├── documents/upload/        # POST 文件解析
│   │       ├── documents/commit/        # POST 提交到 Dify
│   │       └── batch/                   # POST 批量任务
│   ├── components/
│   │   ├── ui/                          # shadcn (button, card, dialog, ...)
│   │   └── knowledge/                   # 9 个知识库专用组件
│   ├── lib/
│   │   ├── api.ts                       # 后端 fetch 封装 (ApiError/NetworkError)
│   │   ├── schema-types.ts              # zod schema 镜像 yaml
│   │   ├── parse-excel.ts
│   │   ├── parse-json.ts
│   │   └── utils.ts                     # cn() 等
│   ├── e2e/                             # Playwright E2E (4 spec, 18 用例)
│   ├── scripts/e2e-up.sh                # 并行起 next dev + 后端
│   ├── playwright.config.ts
│   ├── postcss.config.mjs               # Tailwind v4 必须
│   ├── vitest.config.ts                 # 单元测试 (49 用例)
│   └── package.json
│
├── docs/
│   ├── architecture.md                  # 本文件
│   ├── dev-conventions.md               # 测试/编码规范
│   ├── product-decoder.md               # /decode 服务
│   ├── ingestion.md                     # RAG 流水线
│   ├── knowledge-graph.md               # src/rag/kg/ 模块
│   ├── knowledge-management-page.md     # /knowledge 管理页
│   ├── web-e2e.md                       # Playwright E2E
│   ├── cad-converter.md
│   ├── cad-ezdxf-best-practices.md
│   └── mineru-output-for-rag.md
│
└── .claude/CLAUDE.md                    # Claude Code 项目级配置
```

## 模块职责

### `src/product_decoders/`

产品订货号解析服务（FastAPI HTTP）。

- 入口：`create_app()` 工厂 (测试可 monkeypatch)
- 路由：
  - `/decode` POST 解码
  - `/series` GET 列支持系列
  - `/health` GET 健康检查
  - `/api/output/*` RAG 产物文件列表/读 (output_api.py)
  - `/api/kg/*` 知识图谱 9 个端点 (kg/router.py)
- 引擎：`ProductDecoder` 按型号前缀路由到 YAML 配置
- 配置加载：`ConfigLoader` 从 `configs/product_decoders/` 递归加载

### `src/rag/ingest/`

PDF + CAD 离线处理流水线。

- 入口：
  - `process_files(input_dir, output_dir)` — 完整目录流水线（含 zip 解压、tempfile 隔离、递归扫描）
  - `process_path(path)` — 单文件 / 单目录 / 默认三路分发
- 底层：`process_documents / process_cad_files / process_passthrough` 三个 list[str] 入口
- 转换器：
  - `KreuzbergConverter` — 快速 PDF 文本提取
  - `MineruConverter` — Docker 容器跑复杂 PDF（OCR + 表格）
  - `EzdxfConverter` — DXF/DWG 解析 + SVG 渲染

### `src/rag/kg/` (2026-06 新增, 2026-06-09 合并 knowledge_graph)

知识图谱写入 / 校验 / 任务管理 / 审计 / 模板导出。

- `neo4j.py` — `Neo4jStore` 通用 Neo4j 驱动封装 (CRUD)
- `client.py` — `KgClient` 业务层, 包装 Neo4jStore, 加 UNWIND MERGE 批量 / 子图查询
- `schema.py` — 加载 `configs/knowledge-schema.yaml`, 校验节点/关系引用完整性
- `tasks.py` — in-memory `TaskStore`, 状态机: queued → running → {done, partial, failed, cancelled}
- `router.py` — 9 个 `/api/kg/*` 端点
- `templates.py` — Excel/JSON 模板导出 (openpyxl)
- `audit.py` — 审计日志 (PG ORM 写 kg_audit 表, 跟业务表共用 PG)
- `exceptions.py` — `KgError` / `DuplicateNodeError` / `InvalidTripleError` / `SchemaError` / `TaskNotFoundError`

详见 [knowledge-graph.md](knowledge-graph.md)。

### `src/rag/api/`

**遗留模块**: 旧 `/api/v1/*` RAG HTTP 接口 (Query / Evaluate / Ingest)。**当前未挂到 app**,
仅在 `src/rag/api/__init__.py` 导出 router。生产用 `product_decoders/output_api.py` 看 RAG 产物。
**未来清理目标**。

### `web/` (2026-06 新增)

Next.js 16 + React 19 + Tailwind v4 + shadcn/ui 前端管理后台。

- **5 主模块**: `/` 仪表盘 · `/decode` 解码 · `/output` 文件列表 · `/output/[file]` 详情 · `/knowledge` 知识库
- **4 知识库 Tab**: QA 录入 · Documents 上传 · Triples 录入 · Batch 批量
- **BFF 模式**: 浏览器 fetch `/api/knowledge/*` → Next.js server route → FastAPI `/api/kg/*` 或 Dify REST
- **测试**: vitest (49 单元) + Playwright (18 E2E), 详见 [web-e2e.md](web-e2e.md)

### `main.py`

统一入口，argparse 子命令分发。

- 默认（无子命令）→ `serve` 模式（FastAPI, 端口 8000）
- `ingest [path]` → RAG 流水线
- `serve` → 显式启动服务

## 配置文件位置

| 文件 | 用途 |
|---|---|
| `pyproject.toml` | Python 依赖 (uv 管理) |
| `web/package.json` | 前端依赖 (bun 管理) |
| `config.toml` | RAG 路径 / archive / cad 配置（代码读） |
| `.env` | 环境变量覆盖 (ODA 路径等) |
| `configs/product_decoders/**/*.yaml` | 产品解码规则（部署数据） |
| `configs/knowledge-schema.yaml` | Neo4j 节点/关系定义 (驱动 kg + web BFF) |
| `web/components.json` | shadcn/ui 配置 |

## 部署入口

| 进程 | 命令 | 端口 |
|---|---|---|
| 后端 | `uv run python main.py` | 8000 |
| 前端 (生产) | `cd web && bun run build && bun run start` | 3000 |
| 前端 (开发) | `cd web && bun run dev` | 3000 |

详见 [README.md](../README.md#环境要求)。
