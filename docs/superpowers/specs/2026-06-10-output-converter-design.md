# Output 页面支持上传 + 后端 ingest 转换 (设计)

**日期**: 2026-06-10
**状态**: 待批准
**作者**: brainstorming session

## Context

### 背景 1: Output 页是只读清单

当前 `web/app/output/page.tsx` 是只读页: 通过 `systemApi.listOutputFiles()` 拉后端 `output_dir` (config.toml 配置) 下的 `.md`/`.json` 文件, 表格展示, 点击进入详情页看内容。

要转换文件, 用户必须:
1. 把文件拷到 config 里的 `input_dir` 目录
2. 跑 `uv run python main.py ingest`
3. 等跑完回页面看

体验差, 不直观。期望: **页面上传, 后端转换, 前端下载**。

### 背景 2: 后端 ingest 能力已完整

[src/rag/ingest/pipeline.py](../ingest/pipeline.py) `process_path()` 已支持三路分发:
- 单文件 → 按扩展名分桶 (kreuzberg/mineru/ezdxf/md-passthrough)
- 单目录 → 完整流水线 (4 桶 + ArchiveHandler 解压 .zip)
- 压缩包 → 当目录处理

支持格式 (跟 CLI 一样):
- **Document**: PDF + 图片 (jpg/png/tiff/webp) + Office (docx/xlsx/pptx) + HTML
- **CAD**: dxf, dwg
- **Archive**: .zip (ArchiveHandler 自动解压)

**md 不支持** (因为产物就是 md)。

唯一缺的是 HTTP 入口 — 没接口让前端触发。

### 背景 3: 刚定的 web 架构分层

2026-06-10 完成的 web 前端架构优化 spec ([2026-06-10-web-frontend-architecture.md](2026-06-10-web-frontend-architecture.md)) 锁定了 BFF 边界规则:
- **BFF 保留 4 类**: Dify Chatflow / **multipart** / **后台任务** / SSE
- 其他都走 `lib/api/<领域>.ts` 直连 FastAPI

本 spec 完全符合 — 上传是 multipart, ingest 是后台任务, 下载是流式。

## Goal

让用户在 web 页面**拖文件 → 看进度 → 下载产物**, 后端 ingest 能力零改动 (复用 `process_path()`), 多个用户上传互不干扰。

## User Story

1. **Alice** (产品经理) 想把 1 份 30 页 PDF 产品手册转成 markdown 喂给 Dify。她点 `Output` 页面右上 `[+ 新转换]`, 拖入 `product-manual.pdf`, 点"开始转换"。3 秒后回到 Output 列表, 看到新任务 "processing 67%", 1 秒后变 "completed 1/1 成功", 点"查看产物"看 md 内容, 点"下载全部"拿到 zip。

2. **Bob** (工程师) 拿到一份 50 个文件的 zip, 想批量转。拖入 zip, 看到任务"running 23/50", 关掉页面去开会。10 分钟后回来刷新页面, 任务 "completed 48/50, 2 failed (ODA 未安装)", 点"下载全部"拿到 48 个 md + svg 的 zip。

3. **Carol** (Alice 的同事, 另一个 user token) 在 Alice 上传后立即打开 Output 页, 看不到 Alice 的任务, 自己的页面空白 — 跨用户隔离。

## 关键设计决策 (锁定)

| 决策 | 选择 | 理由 |
|---|---|---|
| 上传场景 | 两者都要 (单文件 + 批处理 / 压缩包) | 用户明确说"两个都要" |
| 文件存储 | **每次上传独立工作区** `var/ingest_uploads/{user_hash}/{task_id}/` | 干净隔离, 多个用户不互干 |
| 输入格式 | PDF + 图片 + Office + HTML + CAD + .zip (md 排除) | 跟 CLI 一样 |
| 输出结构 | **任务 = 文件夹**, 列表页每行一个任务 | 跟 CLI 体验一致, 适合批处理 |
| 压缩包下载 | **后端实时打包流式返回** | 实现简单, < 200 MB 够用 |
| 用户隔离 | **x-user-token** (跟知识库 / 评估页 spec 一致) | 已统一鉴权 key 跟 admin 优先规则 |
| 现有兼容 | **废弃** `web/app/output/[file]/page.tsx` 旧详情页, 新结构只走 `/output/[task_id]/[file]` | dev 模式单用户, 不在意老 URL |
| 异步模式 | **BFF 异步任务** (跟 `web/app/api/knowledge/batch/route.ts` 同模式) | 跟知识库 batch 模板一致, 复用 in-memory task map 模式 |

---

## 架构

```
┌──────────┐  multipart upload  ┌─────────────────┐  multipart upload  ┌──────────────┐
│  Browser │ ──────────────────▶│  Next BFF       │ ──────────────────▶│  FastAPI     │
│  (React) │                    │  /api/ingest/*  │                    │  /api/ingest │
│          │  JSON 轮询         │                 │  BackgroundTask   │  /tasks/{id} │
│          │ ◀────────────────── │                 │ ◀─────────────────│              │
│          │  zip download      │                 │  zip stream       │              │
└──────────┘                    └─────────────────┘                    └──────────────┘
                                                                              │
                                                                              ▼
                                                                     <repo-root>/ingest_uploads/
                                                                     {user_hash}/{task_id}/
                                                                     ├── input/   (上传原文件)
                                                                     └── output/  (md/svg 产物)
```

### 关键路径

| 路径 | 方向 | 用途 |
|---|---|---|
| `POST /api/ingest/upload` (BFF) | 浏览器 → BFF → FastAPI | multipart 透传, 启动 task |
| `GET /api/ingest/tasks` (BFF) | 浏览器 → BFF → FastAPI | 列用户任务 |
| `GET /api/ingest/tasks/{id}` (BFF) | 浏览器 → BFF → FastAPI | 查单任务 (轮询用) |
| `GET /api/ingest/tasks/{id}/files/{name}` (BFF) | 浏览器 → BFF → FastAPI | 读任务产物 (md / svg 预览) |
| `GET /api/ingest/tasks/{id}/download` (BFF) | 浏览器 → BFF → FastAPI | **zip 流式返回** |

### 鉴权

- BFF 从 `authHeaders()` 拿 `x-user-token` (admin 优先), 透传 FastAPI
- FastAPI 用 `sha256(token)[:8]` 做 user_hash, 工作区 `<repo-root>/ingest_uploads/{user_hash}/{task_id}/` (跟现有 `output/` 同级, 都在 .gitignore)
- 不传 token → 401 (跟前几个 spec 一致)
- 跨用户访问 task_id → 404 (不暴露存在性)

### Task 状态机

```
queued ──▶ running ──┬──▶ completed
                     └──▶ failed
```

字段 (Pydantic model `IngestTask`):
```python
class IngestTask(BaseModel):
    id: str                         # YYYYMMDD-HHMMSS-{6hex}
    user_hash: str                  # sha256(token)[:8]
    state: Literal["queued", "running", "completed", "failed"]
    total_files: int                # 上传时的文件数 (zip 内文件数 + 1 个 zip 本身)
    processed: int                  # 转换成功的文件数
    failed: int                     # 转换失败的文件数
    started_at: datetime
    finished_at: datetime | None
    error: str | None               # failed 时填
    output_files: list[OutputFile]  # 任务完成后填, 给前端展示产物树
```

`OutputFile`:
```python
class OutputFile(BaseModel):
    name: str        # 相对 work_dir/output 的路径
    size: int        # bytes
    mime: str        # "text/markdown" / "image/svg+xml" / ...
    error: str | None  # 失败时填
```

存储: **in-memory dict** `tasks: dict[str, IngestTask]` (dev 模式, v2 换 Redis)。

---

## 组件

### 后端 (新增)

#### `src/rag/ingest/api.py` (新)

FastAPI 路由模块, 跟 `src/rag/kg/router.py` 同样模式:

```python
router = APIRouter(prefix="/api/ingest", tags=["ingest"])
ALLOWED_EXTS = {".pdf", ".jpg", ".jpeg", ".png", ".tiff", ".webp",
                ".docx", ".xlsx", ".pptx", ".html", ".htm",
                ".dxf", ".dwg", ".zip"}
MAX_UPLOAD_SIZE = 200 * 1024 * 1024  # 200 MB / task
MAX_FILE_SIZE = 50 * 1024 * 1024     # 50 MB / file

@router.post("/upload", response_model=UploadResponse)
async def upload(files: list[UploadFile], bg: BackgroundTasks,
                 x_user_token: str | None = Header(None)):
    """收 multipart, 写工作区, 启动 BackgroundTask 跑 process_path"""
    ...

@router.get("/tasks", response_model=list[IngestTask])
def list_tasks(x_user_token: str | None = Header(None)):
    ...

@router.get("/tasks/{task_id}", response_model=IngestTask)
def get_task(task_id: str, x_user_token: str | None = Header(None)):
    ...

@router.get("/tasks/{task_id}/files/{name:path}")
def read_task_file(task_id: str, name: str, x_user_token: str | None = Header(None)):
    """读任务产物 (md / svg) — name 白名单 + 越权校验"""
    ...

@router.get("/tasks/{task_id}/download")
def download_zip(task_id: str, x_user_token: str | None = Header(None)):
    """流式打 zip 返回整个任务工作区"""
    ...
```

#### 关键业务逻辑复用

`upload` 路由启动的 BackgroundTask 直接调:
```python
def run_ingest(task_id: str, work_dir: Path):
    t = tasks[task_id]
    t.state = "running"
    try:
        result = process_path(
            path=str(work_dir / "input"),
            output_dir=str(work_dir / "output"),  # 产物落独立工作区
        )
        t.processed = ...
        t.failed = ...
        t.output_files = _collect_output_files(work_dir / "output")
        t.state = "completed"
    except Exception as e:
        t.state = "failed"
        t.error = str(e)
    finally:
        t.finished_at = datetime.now()
```

`process_path()` 业务层**几乎零改动** — 已经支持三路分发 (单文件 / 单目录 / 压缩包), 我们只是给它传一个临时目录路径。

**小改动** (1 行): `process_path(path)` 当前签名没 `output_dir` 参数, 内部 `process_files()` 走 config 的 output_dir。要让 task 产物落独立工作区, 需要给 `process_path` 加 `output_dir: str | None = None` 参数, 透传给 `process_files(output_dir=...)` (后者已经接受这个参数)。

### 前端 (新增 + 改 + 删)

#### 新增

| 路径 | 用途 |
|---|---|
| `web/app/output/new/page.tsx` | 上传页 — 拖拽 + 文件列表 + "开始转换" |
| `web/app/output/new/page.test.tsx` | 上传页单测 |
| `web/app/output/[task_id]/page.tsx` | 任务详情 — 产物树 + 下载全部 |
| `web/app/output/[task_id]/page.test.tsx` | 任务详情单测 |
| `web/app/output/[task_id]/[file]/page.tsx` | 文件预览 (md / svg) — 复用 ReactMarkdown |
| `web/lib/api/ingest.ts` | `ingestApi` 业务客户端 |
| `web/lib/api/ingest.test.ts` | 单测 |
| `web/app/api/ingest/upload/route.ts` | BFF multipart 透传 |
| `web/app/api/ingest/tasks/route.ts` | BFF GET 列表 |
| `web/app/api/ingest/tasks/[id]/route.ts` | BFF GET 单个 |
| `web/app/api/ingest/tasks/[id]/files/[name]/route.ts` | BFF GET 文件 |
| `web/app/api/ingest/tasks/[id]/download/route.ts` | BFF zip 流透传 |
| `web/e2e/06-ingest-upload.spec.ts` | E2E 上传 → 转换 → 下载 |

#### 修改

| 路径 | 改动 |
|---|---|
| `web/app/output/page.tsx` | **改**: 从"扁平文件清单"改成"任务清单" |
| `web/app/output/page.test.tsx` | **改**: 测试任务清单渲染 |
| `src/product_decoders/app.py` | **改**: `app.include_router(ingest_router)` (注册新路由) |
| `src/rag/ingest/__init__.py` | **改**: 导出 `ingest_router` |

#### 删除

| 路径 | 理由 |
|---|---|
| `web/app/output/[file]/page.tsx` | 旧全局详情页, 路径被新 `[task_id]/[file]` 替代 |
| `web/app/output/[file]/page.test.tsx` | 跟着删 |

### `ingestApi` 接口 (前端)

```ts
// web/lib/api/ingest.ts
import { authHeaders } from "./auth";
import { ApiError, NetworkError } from "./errors";

export interface IngestTask {
  id: string;
  state: "queued" | "running" | "completed" | "failed";
  total_files: number;
  processed: number;
  failed: number;
  started_at: string;
  finished_at?: string;
  error?: string;
  output_files?: Array<{ name: string; size: number; mime: string; error?: string }>;
}

export interface UploadResponse {
  task_id: string;
  state: "queued";
  total_files: number;
}

export const ingestApi = {
  // URL 工厂: 给 useApi(SWR) 用
  tasksUrl: (): string => "/api/ingest/tasks",
  taskUrl: (id: string): string => `/api/ingest/tasks/${encodeURIComponent(id)}`,
  taskFileUrl: (taskId: string, name: string): string =>
    `/api/ingest/tasks/${encodeURIComponent(taskId)}/files/${encodeURIComponent(name)}`,
  taskDownloadUrl: (id: string): string =>
    `/api/ingest/tasks/${encodeURIComponent(id)}/download`,

  /** 上传多个文件, multipart 走 BFF */
  upload: async (files: File[]): Promise<UploadResponse> => { ... },
};
```

**下载走 `<a>` 元素** (`<a href={ingestApi.taskDownloadUrl(taskId)} download>`), 不走 fetch, 因为浏览器原生支持流式下载 + 鉴权靠 BFF cookie / header 注入。

---

## 数据流

### 上传流 (Browser → FastAPI)

```
[1] 用户拖文件
   ↓
[2] web/app/output/new/page.tsx onSubmit
   FormData(files), POST /api/ingest/upload
   ↓
[3] BFF /api/ingest/upload/route.ts
   - 校验 authHeaders() 有 x-user-token
   - 透传 multipart 给 FastAPI POST /api/ingest/upload
   - 拿 response { task_id, state: "queued" }
   - 返给前端
   ↓
[4] 前端 router.push("/output") (列表页)
   ↓
[5] web/app/output/page.tsx
   useApi<IngestTask[]>(ingestApi.tasksUrl(), { refreshInterval: 1000 })
   ↓
[6] SWR 轮询 GET /api/ingest/tasks (经 BFF) → 拿到新 task (state=running)
   ↓
[7] 后端 BackgroundTask 同时在跑 process_path(), 状态机: queued → running
   ↓
[8] 任务完成, BackgroundTask 写 t.state = "completed", t.output_files = [...]
   ↓
[9] SWR 下次轮询看到 state=completed, 前端显示"4 成功 / 1 失败"
   ↓
[10] 用户点"查看产物" → 跳 /output/{task_id} 详情页
     或 点"下载全部" → 触发 <a href={downloadUrl} download>
```

### 下载流

```
[1] 用户点 <a href={ingestApi.taskDownloadUrl(taskId)} download>
   ↓
[2] 浏览器 GET /api/ingest/tasks/{id}/download (BFF)
   ↓
[3] BFF 透传给 FastAPI (带 x-user-token)
   ↓
[4] FastAPI StreamingResponse(zip_bytes, media_type="application/zip")
   ↓
[5] BFF 把 response.body 流式透传给浏览器
   ↓
[6] 浏览器触发文件下载, 文件名: {task_id}.zip
```

---

## 错误处理

| 错误 | HTTP | 触发 | 前端展示 |
|---|---|---|---|
| 缺 x-user-token | 401 | BFF authHeaders() 返空 + FastAPI 必传 | 跳登录 (现有 pattern) |
| 跨用户访问 task_id | 404 | t.user_hash != 当前 user_hash | "任务不存在或已过期" |
| 文件扩展名不在白名单 | 400 | FastAPI 校验 ALLOWED_EXTS | "不支持的格式: .xxx" |
| 单文件 > 50 MB | 413 | FastAPI 校验 | "文件太大: X MB (上限 50 MB)" |
| 任务总大小 > 200 MB | 413 | FastAPI 校验 | "总大小超限" |
| task_id 不存在 | 404 | FastAPI tasks.get(task_id) is None | "任务不存在或已过期" |
| name 非法字符 | 400 | BFF + FastAPI 双层白名单 | "非法文件名" |
| name 越权 | 400 | is_relative_to 校验 | "路径越权" |
| ingest 内部异常 | 200 + state="failed" | BackgroundTask try/except | 任务列表显示 failed 卡片 + 错误信息 |
| 上传超时 | NetworkError | BFF fetch 抛 | "网络异常, 请重试" |

**关键**: ingest 内部异常**不返 5xx** — BackgroundTask 捕获后写 `t.state = "failed"`, HTTP 返 200, 错误信息在 task 字段里。前端轮询看到 state=failed 后展示错误。

---

## 前端 UI

### `web/app/output/page.tsx` (改: 任务清单)

```
┌────────────────────────────────────────────────────┐
│ Output                                              │
│ 解析产物                              [+ 新转换]    │
│ 把 PDF/Office/CAD 拖进来, 后台跑, 跑完来看       │
├────────────────────────────────────────────────────┤
│  📁 2026-06-10 14:32  batch-upload-12              │
│     5 个文件 · 4 成功 · 1 失败 · 12.3s             │
│     [查看产物]  [↓ 下载全部 .zip]                   │
├────────────────────────────────────────────────────┤
│  📁 2026-06-10 14:18  manual                       │
│     1 个文件 · 1 成功 · 3.2s                       │
│     [查看产物]  [↓ 下载全部 .zip]                   │
├────────────────────────────────────────────────────┤
│  📁 2026-06-10 13:55  (running...)                 │
│     3 个文件 · 处理中... 67% (2/3)                  │
│     (后台跑, 刷新看进度)                            │
└────────────────────────────────────────────────────┘
```

- 每行一个**任务**
- 状态:
  - `completed` → 显示"成功/失败/总耗时" + 2 个按钮
  - `running` → 显示进度 + cancel 按钮 (cancel 是 P2, 本 spec 不做)
  - `failed` → 红色框 + error
  - `queued` → "排队中..."
- `useApi<IngestTask[]>(ingestApi.tasksUrl(), { refreshInterval: 1000 })` 轮询
- 顶部 `[+ 新转换]` 按钮 → 跳 `/output/new`

### `web/app/output/new/page.tsx` (新: 上传页)

```
┌────────────────────────────────────────────────────┐
│  ← 返回                                             │
│ Output                                              │
│ 新建转换                                            │
├────────────────────────────────────────────────────┤
│  ┌────────────────────────────────────────────┐    │
│  │         📁 拖文件到这里, 或点选            │    │
│  │   支持: PDF, 图片, Office, HTML,         │    │
│  │   CAD(dxf/dwg), 压缩包(.zip)              │    │
│  │         [选择文件...]                       │    │
│  └────────────────────────────────────────────┘    │
│  已选 3 个文件:                                     │
│  📄 product-manual.pdf       2.3 MB   [×]         │
│  📄 sales-brochure.pdf       1.8 MB   [×]         │
│  📦 assets.zip               5.1 MB   [×]         │
│              [开始转换 →]                          │
└────────────────────────────────────────────────────┘
```

- 拖拽 (HTML5 drag/drop) + 点选
- 文件列表可移除
- 点"开始转换" → `await ingestApi.upload(files)` → `router.push("/output")`

### `web/app/output/[task_id]/page.tsx` (新: 任务详情)

```
┌────────────────────────────────────────────────────┐
│  ← 返回 Output                                      │
│ Task 2026-06-10-14-32 / batch-upload-12            │
├────────────────────────────────────────────────────┤
│  📊 状态: 4 成功 / 1 失败 / 5 总数 / 12.3s         │
│  📂 产物 (5):                                       │
│  ├─ 📄 product-manual.md       12.4 KB  [查看]    │
│  ├─ 📄 sales-brochure.md        8.1 KB  [查看]    │
│  ├─ 📄 assets/page-001.md       2.1 KB  [查看]    │
│  ├─ 📄 assets/page-002.svg      3.4 KB  [查看]    │
│  └─ ❌ corrupted.dxf  转换失败: ODA 未安装         │
│                                                     │
│  [↓ 下载全部产物 .zip]                              │
└────────────────────────────────────────────────────┘
```

- 树形展示 (复用 `tree view` 还是简化为缩进列表, 看实现)
- "查看" → 跳 `[task_id]/[file]` 预览页
- 顶部"下载全部" 按钮

### `web/app/output/[task_id]/[file]/page.tsx` (新: 文件预览)

- 复用现有 `[file]/page.tsx` 的 ReactMarkdown 渲染逻辑
- API 改成 `systemApi.readOutputFile` → `ingestApi.taskFileUrl(taskId, name)` + `fetch` 拿 text
- 跟现有差异: API 路径变, 加 taskId 鉴权透传, 其他一样

---

## 文件结构

### 新建

**前端**:
- `web/lib/api/ingest.ts`
- `web/lib/api/ingest.test.ts`
- `web/app/output/new/page.tsx`
- `web/app/output/new/page.test.tsx`
- `web/app/output/[task_id]/page.tsx`
- `web/app/output/[task_id]/page.test.tsx`
- `web/app/output/[task_id]/[file]/page.tsx`
- `web/app/output/[task_id]/[file]/page.test.tsx`
- `web/app/api/ingest/upload/route.ts`
- `web/app/api/ingest/tasks/route.ts`
- `web/app/api/ingest/tasks/[id]/route.ts`
- `web/app/api/ingest/tasks/[id]/files/[name]/route.ts`
- `web/app/api/ingest/tasks/[id]/download/route.ts`
- `web/e2e/06-ingest-upload.spec.ts`

**后端**:
- `src/rag/ingest/api.py`
- `src/rag/ingest/api_test.py` (pytest)
- `tests/api/ingest_test.py` 或 `src/rag/ingest/api_test.py` (按现有约定)

### 修改

- `web/app/output/page.tsx` (从扁平文件清单 → 任务清单)
- `web/app/output/page.test.tsx`
- `src/product_decoders/app.py` (注册 ingest_router)
- `src/rag/ingest/__init__.py` (导出 router + IngestTask)
- `src/rag/ingest/pipeline.py` (确认 `process_path(output_dir=...)` 参数透传, 已有)

### 删除

- `web/app/output/[file]/page.tsx` (旧详情页)
- `web/app/output/[file]/page.test.tsx`

### 不动

- `web/lib/api/system.ts` (老 output/files 路由保留, 给 BFF 旧代码兜底 — dev 模式, 不在意)
- `src/product_decoders/output_api.py` (同上)
- `src/rag/ingest/pipeline.py` 业务层 (零改动)

---

## 测试策略

### 后端 pytest (`src/rag/ingest/api_test.py`)

- `test_upload_creates_task` — 传 1 个 PDF, 拿 task_id, state=queued
- `test_upload_rejects_unsupported_ext` — 传 .exe → 400
- `test_upload_rejects_oversized` — 51 MB 单文件 → 413
- `test_get_task_returns_404_for_unknown` — 随机 task_id → 404
- `test_get_task_returns_404_for_other_user` — 用 user_a 创建, 用 user_b 查 → 404
- `test_list_tasks_filters_by_user` — user_a 看不到 user_b
- `test_task_progresses_to_completed` — 跑 BackgroundTask 等完成, state=completed
- `test_read_task_file_blocks_traversal` — `name=../../etc/passwd` → 400
- `test_download_zip_returns_valid_archive` — 跑完任务, 下载, zipfile 解析能列文件

### 前端 vitest

- `lib/api/ingest.test.ts` — URL 工厂 (4) + upload happy/4xx/5xx/network (5)
- `app/output/new/page.test.tsx` — 拖拽 → 文件列表, 提交 → 调 ingestApi.upload
- `app/output/page.test.tsx` — mock useApi, 渲染 3 状态 (completed/running/failed)
- `app/output/[task_id]/page.test.tsx` — 渲染产物树 + 下载按钮
- BFF routes 透传测试 — 跟 `web/app/api/knowledge/batch/route.test.ts` 同样模式

### E2E (`web/e2e/06-ingest-upload.spec.ts`)

- `test upload 1 PDF → task created → polling → completed → see md output` — 主流程
- `test upload zip → see extracted files in output_files` — 压缩包
- `test download all → get non-empty zip` — 下载
- `test cross-user isolation` — admin token 看不到 user token 的 task
- `test unsupported ext rejected with friendly message` — 上传 .exe

---

## 风险 & 缓解

| 风险 | 缓解 |
|---|---|
| 50 个文件转换慢, 用户关页面任务死 | task 存服务端 in-memory dict, 用户刷新就看到; 关页面不影响后台跑 |
| 用户上传超大文件把内存吃满 | 流式写 (chunk), 实时校验大小, 超过 50 MB 单文件 / 200 MB 任务立即 413 |
| zip 内有恶意路径 (zip slip) | ArchiveHandler 已有 max_depth/max_total_size/max_file_count 三道防线 (看 [archive_handler.py](../../rag/ingest/archive_handler.py)) |
| 多用户并发任务, in-memory 字典冲突 | 字典 key 包含 user_hash 校验, 跨用户查不到 |
| 任务工作区堆积磁盘 | 本 spec 不做 cleanup; 加 TODO 后续 spec 加 7-day cleanup job |
| FastAPI BackgroundTask 在 reload 时丢失 | dev 模式, 单进程, 可接受; v2 换 Redis |
| BFF 流式透传 zip 时, Next.js 默认 buffer | BFF route 用 `new Response(res.body, ...)` 不读 body, 透传 ReadableStream |
| 上传 200 MB 多分 4 + 5 MB (vite dev proxy) | Next.js 默认 proxy 不限 body, FastAPI 用 `request.stream()` 读流 |
| 旧的 `web/app/output/[file]/page.tsx` 删了, 之前打开的 tab 404 | dev 单用户, 不在意; 提示可加 toast "页面已升级, 请回到 Output 主页" |

---

## 实施顺序 (后续 plan 拆)

预估 8-10 个 task, 按依赖分 3 批:

**Batch 1 (serial, 1 个) — 后端地基**:
- Task 1: `src/rag/ingest/api.py` 路由 + IngestTask model + BackgroundTask 跑 process_path + 单测

**Batch 2 (parallel, 2 个) — 前端基础设施**:
- Task 2: `web/lib/api/ingest.ts` + test
- Task 3: 5 个 BFF route.ts (upload / tasks list+detail / files / download) + 单测

**Batch 3 (serial, 4 个) — 前端 UI**:
- Task 4: `web/app/output/page.tsx` 改任务清单 + test
- Task 5: `web/app/output/new/page.tsx` 上传页 + test
- Task 6: `web/app/output/[task_id]/page.tsx` 任务详情 + test
- Task 7: `web/app/output/[task_id]/[file]/page.tsx` 文件预览 + test + 删旧 page

**Batch 4 (serial, 1 个) — E2E**:
- Task 8: `web/e2e/06-ingest-upload.spec.ts`

**Batch 5 (serial, 1 个) — 收尾**:
- Task 9: 最终验证 (typecheck + lint + test + 23 旧 E2E + 5 新 E2E) + to-do 划掉 (如果本 spec 覆盖 to-do 某行)

---

## 范围界定 (YAGNI)

本 spec **不做** (后续 spec 再加):
- ❌ 实时 SSE 日志推送 (用户刷新页面就能看到进度, 够用)
- ❌ 7-day cleanup job
- ❌ Cancel task API (前端 cancel 按钮是 P2)
- ❌ Admin 跨用户看 task 面板
- ❌ 任务命名 (用 task_id 作 title, 不让用户起名字)
- ❌ 多用户实时协作
- ❌ 任务分享 / 复制

本 spec **做** (明确边界):
- ✅ 多文件 multipart 上传 (单文件 + 多文件 + 压缩包)
- ✅ 后台异步 ingest 任务
- ✅ SWR 轮询进度
- ✅ 任务列表 + 详情 + 文件预览
- ✅ zip 流式下载
- ✅ 跨用户隔离 (x-user-token)
- ✅ 旧 output 详情页废弃

---

## 验收标准

1. ✅ 用户拖 1 个 PDF 到 `web/app/output/new`, 3 秒后 `web/app/output` 列表显示新任务 "completed 1/1 成功"
2. ✅ 用户点"查看产物"看到 md 内容 (ReactMarkdown 渲染)
3. ✅ 用户点"下载全部"拿到非空 zip
4. ✅ 用户拖 1 个含 10 个 PDF 的 .zip, 任务"running N/10" 实时刷新, 跑完"completed 10/10"
5. ✅ 两个不同 user_token 在浏览器 A / B 互不可见
6. ✅ 上传 .exe 弹"不支持的格式"错误
7. ✅ pytest 12+ cases 全绿, vitest 30+ cases 全绿
8. ✅ E2E 5 cases 全绿
9. ✅ typecheck 0 错 (modulo pre-existing)
10. ✅ 旧的 `web/app/output/[file]/page.tsx` 已删, 编译干净
