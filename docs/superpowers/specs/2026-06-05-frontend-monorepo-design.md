# Next.js 管理后台：单仓 + web/ 子目录方案

**日期**: 2026-06-05
**状态**: 待批准

## Context

项目目前**没有浏览器 UI**。产品订货号解析服务（`src/product_decoders/`）只通过 FastAPI 暴露 `/decode`、`/series`、`/health` 三个端点，前端消费方是 Dify 工作流的 HTTP 节点；PDF 离线流水线（`src/rag/ingest/`）连 API 都没有，只能 `python main.py ingest` 命令行触发 + 看 `output/` 目录落盘的 markdown。

用户 2026-06-05 决定加一个 **Next.js 管理后台**，定位是 **PDF 流水线的可视化操作台**：看现有 ingest 结果、查 `output/`、触发 decode 看结构化字段。

**为什么不是 Dify 工作流能 cover 的**：Dify 是 LLM 编排工具，它的"前端"是聊天框或者工作流的 step-by-step 视图，**不是给人 review PDF 解析结果、不是给人翻 output/ 目录**。管理后台要的是表格/列表/详情页这种"运营 UI"。

**关键决策（brainstorming 2026-06-05）**：

1. **仓库结构**：单仓不分 workspace。在现有仓库加 `web/` 目录，跟 `src/`、`main.py`、`configs/` 并列。
2. **范围**：**只读**管理后台。前端不触发 ingest、不编辑 configs、不做登录鉴权。
3. **后端 API 增量**：2 个新只读 API——`GET /api/output/files`（列文件）、`GET /api/output/files/{name}`（读单个 markdown），挂同一个 FastAPI app 上。
4. **技术栈**：Next.js 15 App Router + TypeScript strict + Tailwind v4 + shadcn/ui + bun（包管理）+ vitest（测试）。
5. **本地开发通信**：CORS。后端开 `CORSMiddleware`，允许 `http://localhost:3000`。

## 关键设计

### 1. 目录结构

```text
rag/
├── src/                                # 不动
│   ├── product_decoders/               # 不动 (追加 CORS 中间件)
│   └── rag/                            # 不动
├── main.py                             # 不动
├── pyproject.toml                      # 不动 (fastapi 已有, 无新依赖)
├── tests/                              # 不动 (追加 test_web_apis.py)
├── web/                                # 新增
│   ├── package.json
│   ├── bun.lock                        # bun 自动生成 (文本格式)
│   ├── tsconfig.json
│   ├── next.config.ts
│   ├── vitest.config.ts
│   ├── postcss.config.mjs              # Tailwind v4
│   ├── tailwind.config.ts              # Tailwind 配置
│   ├── .gitignore
│   ├── components.json                 # shadcn 配置
│   ├── app/
│   │   ├── layout.tsx                  # 根布局
│   │   ├── page.tsx                    # / 仪表盘
│   │   ├── decode/page.tsx             # /decode 表单
│   │   ├── output/page.tsx             # /output 文件列表
│   │   ├── output/[file]/page.tsx      # /output/<file> 详情
│   │   └── globals.css                 # Tailwind 入口
│   ├── components/
│   │   ├── ui/                         # shadcn 组件 (复制进来)
│   │   └── *.tsx                       # 自定义组合
│   ├── lib/
│   │   ├── api.ts                      # fetch 封装
│   │   ├── api.test.ts                 # 单测
│   │   └── utils.ts                    # cn() 等工具
│   └── CLAUDE.md                       # 前端局部约定
├── configs/                            # 不动
├── scripts/                            # 不动
├── docs/                               # 不动
├── .gitignore                          # 追加 web/node_modules 等
├── CLAUDE.md                           # 追加"前端开发"小节
└── README.md                           # 追加"启动前端"小节
```

### 2. 前后端 API 契约

**现有 API（不改动）**：

| 方法 | 路径 | 用途 |
|---|---|---|
| POST | `/decode` | 解码一个型号 |
| GET  | `/series` | 列出所有支持系列 |
| GET  | `/health` | 健康检查 |

**新 API（本 spec 范围）**：

| 方法 | 路径 | 用途 | 响应 |
|---|---|---|---|
| GET | `/api/output/files` | 列 `output/` 目录下的 .md / .json 文件 | `{files: [{name, size, mtime}]}` |
| GET | `/api/output/files/{name}` | 读单个文件 | `{name, content, mime}` |

**新 API 的安全边界**：
- `name` 参数必须用 `Path(...).name` 取 basename，防 `../` 越权
- 只接受 `[a-zA-Z0-9._-]+` 字符集，不符合返回 400
- 文件大小上限 10 MB，超过返回 413
- 路径必须在配置项 `paths.output_dir` 之下，构造绝对路径后校验 `is_relative_to(output_dir)`

**错误响应**（FastAPI 抛 HTTPException，前端 lib/api.ts 统一处理）：

| 状态 | 含义 | 前端展示 |
|---|---|---|
| 400 | 参数非法 | 表单红字 |
| 404 | 文件不存在 | 详情页"文件已被删除" |
| 413 | 文件太大 | 列表项红字提示 |
| 5xx | 后端挂了 | 全屏错误页 + 重试按钮 |

### 3. CORS 配置

后端 `src/product_decoders/app.py` 工厂里加：
```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # dev only
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
```

**生产部署时改** `allow_origins` 为前端域名（spec 不覆盖）。

### 4. 前端页面职责

| 页面 | 调什么 | 展示什么 |
|---|---|---|
| `/` | `GET /health` + `GET /series` | "服务在线 · 已注册 N 个系列" + 列表 |
| `/decode` | `POST /decode` | 表单（input + 提交）+ 结果卡片（_zh/_en/_raw 三列） |
| `/output` | `GET /api/output/files` | 表格：name / size / mtime / 操作 |
| `/output/[file]` | `GET /api/output/files/{name}` | markdown 渲染（用 `react-markdown`）+ 元信息 |

**布局**：`app/layout.tsx` 提供顶部 nav（首页 / Decode / Output），左侧空白，右侧 main。

### 5. shadcn/ui 用法

- 初始化：`bunx shadcn@latest init`，选 Default 风格、Slate 配色
- 首批装的组件：`button`, `input`, `card`, `table`, `badge`, `alert`
- **不**装 `form`、`dialog`、`dropdown-menu`——当前页面用不到，YAGNI
- 组件复制到 `web/components/ui/`，不装成 npm 依赖（shadcn 标准做法）

**运行时依赖清单**（写进 `web/package.json`）：

| 包 | 用途 |
|---|---|
| `next` | 框架 |
| `react`, `react-dom` | UI |
| `tailwindcss`, `postcss`, `autoprefixer` | 样式（v4） |
| `react-markdown` | `/output/[file]` 渲染 markdown |
| `clsx`, `tailwind-merge` | shadcn 依赖（`cn()` 工具） |
| `class-variance-authority` | shadcn 依赖（variant 样式） |
| `lucide-react` | shadcn 依赖（图标） |

**开发依赖**：`typescript`, `@types/react`, `@types/node`, `vitest`, `@testing-library/react`, `@testing-library/jest-dom`, `@vitejs/plugin-react`, `jsdom`

### 6. 测试

| 文件 | 测什么 | 工具 |
|---|---|---|
| `tests/test_web_apis.py` | 2 个新 API：列文件成功、列空目录、读文件成功、读不存在文件 404、`../` 越权返回 400、超大文件 413 | pytest + httpx AsyncClient |
| `web/lib/api.test.ts` | `api.ts` 的 fetch 封装：成功路径、4xx 抛 ApiError、5xx 抛 NetworkError、超时 | vitest |
| `web/app/decode/page.test.tsx` | 输入→提交→结果渲染（mock fetch） | vitest + @testing-library/react |
| `web/app/output/page.test.tsx` | 列表加载、空态、错误态 | vitest + @testing-library/react |

**CLAUDE.md TDD 规范**：先红后绿，commit 用 `test:` / `feat:` 前缀。

### 7. 文档

| 文件 | 内容 |
|---|---|
| `web/CLAUDE.md` | 前端局部约定：bun 命令、Tailwind 用法、shadcn 怎么加组件、vitest 怎么跑 |
| 根 `CLAUDE.md` | 追加"前端开发"小节：链接到 `web/CLAUDE.md`，说明 dev 模式要开两个终端 |
| `README.md` | 追加"启动前端"小节：2 行命令、CORS 已开、无需额外配置 |
| 本 spec | 即本文档 |
| 实施计划 | `docs/superpowers/plans/2026-06-05-frontend-monorepo-plan.md`（由 writing-plans 写） |

## 文件级改动清单

| 文件 | 性质 | 说明 |
|---|---|---|
| `web/` 全部 | 新增 | ~25 个文件，bun 装 ~600MB deps（不入库） |
| `web/CLAUDE.md` | 新增 | 前端约定 |
| `web/lib/api.ts` | 新增 | fetch 封装，单一职责 |
| `web/lib/utils.ts` | 新增 | `cn()` 工具（shadcn 需要） |
| `src/product_decoders/app.py` | 改 | 加 CORS 中间件 + `include_router(output_api.router)` |
| `src/product_decoders/output_api.py` | 新增 | 2 个新路由的 handler，单独文件避免 app.py 膨胀 |
| `tests/test_web_apis.py` | 新增 | 后端 2 个 API 测试 |
| `pyproject.toml` | 不改 | 依赖都已存在（fastapi, starlette 的 CORS 中间件内置） |
| `.gitignore` | 改 | 追加 `web/node_modules/`, `web/.next/`, `web/out/`, `*.tsbuildinfo`, `next-env.d.ts` |
| `web/.gitignore` | 新增 | Next.js 标准产物清单 |
| `CLAUDE.md` | 改 | 追加"前端开发"小节 |
| `README.md` | 改 | 追加"启动前端"小节 |
| `docs/superpowers/specs/2026-06-05-frontend-monorepo-design.md` | 新增 | 本文档 |

## 风险与权衡

1. **`src/product_decoders/app.py` 单文件承担太多**：CORS + 2 个新路由会让这个文件从 ~80 行涨到 ~150 行。**缓解**：把 2 个新路由拆到 `output_api.py`，用 `app.include_router()` 挂载。
2. **CORS 只允许 localhost:3000**：生产部署需要改。**缓解**：写在 spec 不覆盖范围，部署时再调整。
3. **没有 e2e 测试**：vitest 测的是组件 + 单元，跨前后端没覆盖。**缓解**：本 spec 范围明确不做 e2e；后端 API 单测已经覆盖了契约。
4. **`web/node_modules` 不会被 CI 装**：现有 CI（pre-commit）只跑 ruff + pytest，不会跑 bun install。**缓解**：本 spec 范围明确 CI 不动；如果以后 CI 要加 web 测试，由独立 spec 处理。
5. **shadcn 组件复制进项目**：版本升级靠 `bunx shadcn@latest diff` 手动同步。**接受**：shadcn 官方推荐做法。

## 非目标（明确不做）

- ❌ 触发 ingest / 上传 PDF
- ❌ 编辑 `configs/*.yaml`
- ❌ 用户登录 / 鉴权
- ❌ 部署到 Vercel / 任何云
- ❌ E2E 测试
- ❌ 把 `src/` 移到 `apps/api/`
- ❌ 引入 pnpm workspace / Turborepo
- ❌ CI 跑前端测试
