# KG 任务列表页设计 (2026-07-03)

> **Status**: draft → implementation pending
> **Owner**: frontend + backend
> **Scope**: 列出所有 kg_extract / kg_batch 后台任务 + tab 切换 + "新建提取"入口 + "重跑"动作

## 背景

`packages/web/app/[locale]/knowledge/extract/page.tsx` 当前**只有"新建"页**: 用户上传 .md → 调 `/api/kg/extract/start` → 跳到 `/extract/{task_id}` 进度页。**没有"任务列表"**: 用户无法回顾历史抽取、无法一眼看出哪些任务在跑、无法重新基于历史参数跑同一个文件。

**调整 (2026-07-03 决策)**:
- 启动页 (`/extract`) → **删除整页**, 改为 `_components/extract-create-dialog.tsx` 弹框组件, 由列表页触发
- `/extract` → 列表页 (新, RSC entry 只返 `<TasksListClient />`)
- `/extract/{task_id}` → 进度页 (不动)
- `/extract/{task_id}/preview` → 预览页 (不动)
- 弹框内容: **完整复刻老表单** (FileDropzone + dataset / extractor / splitter 3 个 AppSelect + 启动按钮), 提交后启新 task 并跳进度页

后端 `TaskStore` (`packages/service/src/kg/tasks.py`) 已有 `list_recent(limit=50)`, **但 HTTP 层没有暴露列表端点** — `/api/kg/extract/tasks/{task_id}` 只能查单条, 没有 `/api/kg/extract/tasks` GET 列表。

本期补上这个能力 + 启动页改弹框。

## 方案

### 路由 (已敲定 B)

| 方案 | 评估 |
|---|---|
| A. 拆两个独立子路由 `/extract/tasks/extract` + `/extract/tasks/batch` | ❌ 重复 70% markup + 2 套 useQuery |
| **B. 单页 `/extract/tasks` + AppToggle 客户端切换 (推荐)** | ✅ 1 个 RSC entry + 1 个 client container + 2 个子表格组件, TanStack staleTime 60s 切回不重拉 |
| C. 单页 + URL `?tab=` 同步 | ❌ 多一层 useSearchParams + i18n router 耦合, YAGNI |

### 用户决策 (2026-07-03 brainstorming)

1. **范围**: 两个 tab — "抽取" (kg_extract) + "批量" (kg_batch)
2. **入口**: "新建提取"按钮放在**抽取 tab** 的 PageHero actions 槽, 触发 `ExtractCreateDialog` 弹框 (2026-07-03 决策: 启动页从独立页改为弹框组件, 弹框内容完整复刻老表单)
3. **行点击**: 按 kind+state 路由 — kg_extract 走详情; kg_batch 无详情页
4. **后端查询参数**: `limit + offset` 分页 (用户决策)
5. **重跑**: 仅 kg_extract 提供, 复用 `startExtract()` 函数启新任务
6. **轮询**: 手动刷新按钮 (PageHero actions 槽)
7. **聚合**: 增返 `total_success` + `total_failed` (用户决策, 跟 `kg.extract.export` 审计一致)
8. **路由调整** (2026-07-03 用户反馈): 列表页直接放 `/extract`, 启动页 **改为弹框组件** (不保留 `/extract/create` 路径, 删整页)
9. **弹框组件位置** (2026-07-03 用户反馈): `_components/extract-create-dialog.tsx`, 业务私用, 不抽 `components/common/`

## 架构

### 文件布局

```
packages/web/app/[locale]/knowledge/extract/
├── page.tsx                          # [新] 列表页 RSC entry, 只返 <TasksListClient />
├── _components/
│   ├── tasks-list-client.tsx         # [新] 客户端容器: AppToggle + DataTable + 弹框状态
│   ├── extract-create-dialog.tsx     # [新] 启动弹框 (原 page.tsx 表单内容改写为 AppDialog)
│   ├── extract-tasks-table.tsx       # [新] kg_extract 表格 (含"重跑"操作)
│   └── batch-tasks-table.tsx         # [新] kg_batch 表格 (无操作)
├── [task_id]/
│   ├── page.tsx                      # 不动
│   ├── page.test.tsx                 # 不动
│   ├── _components/task-progress-client.tsx  # 不动
│   └── preview/...                   # 不动
└── (删) 原 page.tsx                  # [删] 整页删除, 内容搬到 extract-create-dialog.tsx

packages/web/components/knowledge/knowledge-tabs.tsx
  ~ children 数组保留 "/knowledge/extract" (列表页跟 /{task_id}/... 都自动 startsWith 匹配)

packages/web/lib/api/knowledge.ts
  + fetchExtractTasks({ kind, limit, offset })
  + ExtractTaskRow 类型

packages/service/src/kg/router.py
  + GET /api/kg/extract/tasks
  + _serialize_task() helper

packages/service/tests/kg/test_router.py
  + test_list_extract_tasks_default
  + test_list_extract_tasks_filter_by_kind
  + test_list_extract_tasks_pagination
  + test_list_extract_tasks_invalid_kind_422

packages/service/tests/test_api_contract.py
  + FRONTEND_EXPECTS += "/api/kg/extract/tasks" (GET)

packages/web/messages/{zh,en}.json
  + 19 个新 key (见 §i18n)
```

### 不动 / 保留

- `app/[locale]/knowledge/extract/[task_id]/**` — 不动
- `TaskStore` (`packages/service/src/kg/tasks.py`) — 不动, 直接复用 `list_recent()`
- `knowledge-tabs.tsx` — **children 数组不动** (`"/knowledge/extract"` 自动匹配列表页 + `/extract/{task_id}/...` 全部子路径)

## API 契约

### GET /api/kg/extract/tasks

```python
# request
GET /api/kg/extract/tasks?kind=kg_extract&limit=20&offset=0
Headers: x-user-token (cookie rag_user_token 也行, 走 resolve_user 链)
Auth: require_page("knowledge")

# response 200
{
  "items": [
    {
      "task_id": "abc123def456",
      "kind": "kg_extract",                     # 或 "kg_batch"
      "state": "running",                        # queued/running/done/partial/failed/cancelled
      "dataset": "motor",                        # 仅 kg_extract; kg_batch 为 null
      "extractor": "llm_pydantic",               # 仅 kg_extract
      "splitter": "heading",                     # 仅 kg_extract
      "uri": "local://inputs/motor/abc/source.md",  # 仅 kg_extract, 前端不展示
      "success": 12,
      "failed": 0,
      "created_at": 1751480000.123,              # epoch float
      "started_at": 1751480001.0,
      "finished_at": null
    }
  ],
  "total": 137,           # 按当前 kind 过滤后的总数
  "total_success": 412,   # 按当前 kind 过滤后 sum(success)
  "total_failed": 3,      # 按当前 kind 过滤后 sum(failed)
  "limit": 20,
  "offset": 0
}

# response 422: kind 不在 ["kg_extract", "kg_batch", "all"]
# response 403: require_page("knowledge") 失败
# response 401: 未登录
```

### 后端实现

```python
@router.get(
    "/extract/tasks",
    summary="列抽取任务",
    description=(
        "列出 TaskStore 中的后台任务 — 支持 kind 过滤 (kg_extract / kg_batch / all) + 分页 (limit/offset). "
        '鉴权: require_page("knowledge").'
    ),
    responses={
        200: {"description": "返 {items, total, total_success, total_failed, limit, offset}"},
        422: {"description": "kind 不在枚举"},
        403: {"description": "权限不足"},
    },
)
def list_extract_tasks(
    kind: str = "kg_extract",
    limit: int = 20,
    offset: int = 0,
    current_user: CurrentUser = Depends(require_page("knowledge")),
) -> dict:
    if kind not in ("kg_extract", "kg_batch", "all"):
        raise HTTPException(422, "kind 必须在 [kg_extract, kg_batch, all]")
    # 上限 200 条 in-memory 拿够; 超过用 offset 切割
    all_tasks = _task_store.list_recent(limit=200)
    if kind != "all":
        all_tasks = [t for t in all_tasks if t.kind == kind]
    total = len(all_tasks)
    page = all_tasks[offset : offset + limit]
    return {
        "items": [_serialize_task(t) for t in page],
        "total": total,
        "total_success": sum(t.success for t in all_tasks),
        "total_failed": sum(t.failed for t in all_tasks),
        "limit": limit,
        "offset": offset,
    }


def _serialize_task(t: TaskStatus) -> dict:
    base = {
        "task_id": t.task_id,
        "kind": t.kind,
        "state": t.state,
        "success": t.success,
        "failed": t.failed,
        "created_at": t.created_at,
        "started_at": t.started_at,
        "finished_at": t.finished_at,
    }
    if t.kind == "kg_extract":
        base.update({
            "dataset": t.payload.get("dataset"),
            "extractor": t.payload.get("extractor"),
            "splitter": t.payload.get("splitter"),
            "uri": t.payload.get("uri"),
        })
    return base
```

### 前端 API 封装

```typescript
// packages/web/lib/api/knowledge.ts

export type ExtractTaskRow = {
  task_id: string;
  kind: "kg_extract" | "kg_batch";
  state: "queued" | "running" | "done" | "partial" | "failed" | "cancelled";
  dataset?: string;
  extractor?: string;
  splitter?: string;
  uri?: string;             // 前端不展示, 仅重跑用
  success: number;
  failed: number;
  created_at: number;
  started_at: number | null;
  finished_at: number | null;
};

export type ExtractTaskList = {
  items: ExtractTaskRow[];
  total: number;
  total_success: number;
  total_failed: number;
  limit: number;
  offset: number;
};

/** 列任务 (kind 必传, limit/offset 可选) */
/** @shared */
export const fetchExtractTasks = async (params: {
  kind: "kg_extract" | "kg_batch";
  limit?: number;
  offset?: number;
}): Promise<ExtractTaskList> => {
  const qs = new URLSearchParams({ kind: params.kind });
  if (params.limit !== undefined) qs.set("limit", String(params.limit));
  if (params.offset !== undefined) qs.set("offset", String(params.offset));
  return apiFetch<ExtractTaskList>(`/api/kg/extract/tasks?${qs.toString()}`);
};
```

**重跑复用现有 `startExtract`**: 不新增 `rerunExtractTask`, 组件内直接调 `startExtract({ uri, dataset, extractor, splitter })`。

## UI 与交互

### 页面布局

```
┌─────────────────────────────────────────────────────────────┐
│  PageHero                                                    │
│    eyebrow: "知识图谱"                                       │
│    title:   "任务列表"                                       │
│    actions: ┌──────────┐  ┌────────┐                         │
│             │+ 新建提取 │  │  刷新  │                        │
│             └──────────┘  └────────┘                        │
│    description: "查看所有 KG 抽取与批量任务"                  │
├─────────────────────────────────────────────────────────────┤
│  AppToggle: [抽取] [批量]                                    │
│  ←── 当前 tab                                                │
├─────────────────────────────────────────────────────────────┤
│  Stats: 总数 137  ·  成功 412  ·  失败 3                     │
├─────────────────────────────────────────────────────────────┤
│  DataTable<ExtractTaskRow>                                   │
│  ┌────────┬───────┬─────┬─────┬──────┬─────┬──────┬──────┐ │
│  │Task ID │Dataset│Extr.│Spl. │State │suc/│Created│Actions│ │
│  │        │       │     │     │      │fail│       │      │ │
│  ├────────┼───────┼─────┼─────┼──────┼─────┼──────┼──────┤ │
│  │abc123… │ motor │llm  │head │●Run  │12/0│ 3s前 │重跑  │ │
│  │def456… │ motor │spcy │tok  │●Done │25/0│ 2m前 │重跑  │ │
│  └────────┴───────┴─────┴─────┴──────┴─────┴──────┴──────┘ │
│  pagination: 1/7 (limit=20)                                 │
└─────────────────────────────────────────────────────────────┘
```

### "抽取" Tab 列 (kg_extract)

| 列 | 数据源 | 渲染 |
|---|---|---|
| Task ID | `task_id` | 前 8 字符 + `<CopyButton value={task_id} />` (复用 common/) |
| Dataset | `payload.dataset` | Badge (env 白名单 label) |
| 抽取器 | `payload.extractor` | 字串: spacy_rule / llm_pydantic |
| 切片器 | `payload.splitter` | 字串: heading / token / semantic |
| 状态 | `state` | `<TaskStatusBadge state={state} />` (复用 common/) |
| 进度 | `success` / `failed` | "23/25" 文本 (queued/失败时显示 0/0) |
| 创建时间 | `created_at` | `formatRelativeTime` (项目已有) |
| 操作 | — | "重跑" 按钮 (Button variant="ghost" size="sm") |

### "批量" Tab 列 (kg_batch)

- 同上, **无"重跑"操作** (kg_batch 路由没详情页)
- 进度列: 显示 success/failed (kg_batch 也跑 batch_upsert_triples)

### 行点击行为 (按 kind+state 路由)

```typescript
const handleRowClick = (row: ExtractTaskRow) => {
  if (row.kind !== "kg_extract") return;  // kg_batch 无详情
  const dataset = row.dataset ?? "motor";
  if (row.state === "done" || row.state === "partial") {
    void router.push(`/knowledge/extract/${row.task_id}/preview?dataset=${encodeURIComponent(dataset)}`);
  } else {
    // queued / running / failed / cancelled 都跳进度页
    void router.push(`/knowledge/extract/${row.task_id}?dataset=${encodeURIComponent(dataset)}`);
  }
};
```

**表格 rowClassName**: 用 `ExtractTaskRow.kind` 区分:
- kg_extract → `"cursor-pointer hover:bg-muted/50"`
- kg_batch → 默认 (不响应点击)

### "重跑" 按钮 (仅 kg_extract)

```typescript
// 用 useState 控 showConfirm 弹窗, 不调 openConfirm() (项目无此 API)
const [confirmRow, setConfirmRow] = useState<ExtractTaskRow | null>(null);

const handleRerunClick = (row: ExtractTaskRow) => {
  if (!row.uri || !row.dataset || !row.extractor || !row.splitter) {
    toast.error(t("重跑参数缺失"));
    return;
  }
  setConfirmRow(row);  // 弹 AppConfirm
};

const handleRerunConfirm = async () => {
  const row = confirmRow;
  if (!row) return;
  setConfirmRow(null);
  try {
    const { task_id } = await startExtract({
      uri: row.uri!,
      dataset: row.dataset!,
      extractor: row.extractor as "spacy_rule" | "llm_pydantic",
      splitter: row.splitter as "heading" | "token" | "semantic",
    });
    void router.push(`/knowledge/extract/${task_id}?dataset=${encodeURIComponent(row.dataset!)}`);
  } catch (err) {
    // t() 是 flat-key 不支持 placeholder, 拼字符串
    const msg = err instanceof Error ? err.message : "";
    toast.error(`${t("重跑失败")}: ${msg}`);
  }
};

// JSX:
{confirmRow ? (
  <AppConfirm
    open={true}
    title={t("重跑确认")}
    description={t("重跑将基于历史参数启动新任务, 是否继续?")}
    onConfirm={handleRerunConfirm}
    onCancel={() => setConfirmRow(null)}
  />
) : null}
```

> 走 `<AppConfirm>` (项目已封装) 而非自定义 AppDialog, 复用危险操作二次确认 UI 范式。AppConfirm 不可嵌套在表格 cell 内 — 提到顶层 + 单一实例。

### TanStack Query 状态

```typescript
// tasks-list-client.tsx
const [activeTab, setActiveTab] = useState<"kg_extract" | "kg_batch">("kg_extract");
const [page, setPage] = useState(0);  // 0-indexed

const tasksQuery = useQuery({
  queryKey: ["kg", "tasks", activeTab, page],
  queryFn: () => fetchExtractTasks({ kind: activeTab, limit: PAGE_SIZE, offset: page * PAGE_SIZE }),
  enabled: true,  // AppToggle 切 tab 改 activeTab → queryKey 变 → 新 query
  staleTime: 60_000,
  refetchOnWindowFocus: false,
});

// "刷新" 按钮: tasksQuery.refetch()
```

> **重要**: `PAGE_SIZE = 20`, DataTable 内建 pagination 跟 `page` 同步, 切 tab 时 `page` reset 为 0 (避免 kg_batch 有 50 条但 page=3 越界)。

### 空态 / 错误态

- **加载中**: `DataTable loading={tasksQuery.isLoading}` (内建 skeleton)
- **空表**: `<DataEmpty icon={FileText} title={t("暂无任务")} description={t("暂无任务描述")} />`
- **网络错**: 表格上方 `<ErrorBanner variant="destructive" title={t("加载任务失败")} description={err.message} />` + "重试" 按钮调 `tasksQuery.refetch()`
- **401/403**: 现有 middleware 跳登录页, 表格不处理

## 错误处理

| 场景 | 处理 |
|---|---|
| apiFetch throw (网络错) | TanStack Query `error` state → `<ErrorBanner>` + 重试按钮 |
| 401/403 | middleware 重定向, 表格不处理 |
| 422 kind 非法 | 前端不发非法 kind (3 个固定值), 触发后兜底 `<ErrorBanner>` |
| 重跑失败 | Sonner toast error variant + `t("重跑失败: {msg}")` |
| 老 task 404 (dev server 重启 in-memory 丢失) | 列表里点进去 404 → 现有进度页已有 404 行为, 不需新处理 |

## i18n 新增 (zh.json + en.json, 共 19 key)

| key (中文) | zh value | en value |
|---|---|---|
| `任务列表` | 任务列表 | Tasks |
| `抽取` | 抽取 | Extract |
| `批量` | 批量 | Batch |
| `新建提取` | 新建提取 | New Extraction |
| `刷新` | 刷新 | Refresh |
| `暂无任务` | 暂无任务 | No tasks yet |
| `暂无任务描述` | 暂无任务。点击右上角"新建提取"开始抽取。 | No tasks. Click "New Extraction" to start. |
| `复制` | 复制 | Copy |
| `重跑` | 重跑 | Re-run |
| `重跑确认` | 重跑将基于历史参数启动新任务, 是否继续? | Re-run will start a new task with the same parameters. Continue? |
| `数据集` | 数据集 | Dataset |
| `抽取器` | 抽取器 | Extractor |
| `切片器` | 切片器 | Splitter |
| `创建时间` | 创建时间 | Created |
| `进度` | 进度 | Progress |
| `任务 ID` | 任务 ID | Task ID |
| `加载任务失败` | 加载任务失败 | Failed to load tasks |
| `重跑参数缺失` | 重跑参数缺失 | Re-run parameters missing |
| `重跑失败` | 重跑失败 | Re-run failed |

省略号: zh 写 `…` (U+2026), en 写 `...` (ASCII 3 个点), 跟项目 2026-06-18 统一约定一致。

## 范围边界 (YAGNI)

### 本期不做

- ❌ 删除任务 (TaskStore 没 DELETE API)
- ❌ 取消任务 (mark_cancelled 已存在但无 HTTP 端点)
- ❌ 按 dataset / 时间范围 / 状态过滤
- ❌ URL 同步 tab 状态 (`?tab=`)
- ❌ 自动轮询 (用户选手动刷新)
- ❌ kg_batch 任务的"重跑" (无业务路径)
- ❌ 表格里展示 `uri` 完整路径 (payload 内部数据, 不外露)
- ❌ 多租户隔离 (TaskStore 是 in-memory 全局, v1 接受)
- ❌ TaskStore 持久化 (v2 走 Redis / SQLite)

### 未来 spec 候选

- 多租户隔离: TaskStore 加 user_id, 前端按 current_user.id 过滤
- 持久化: TaskStore v2 → Redis / SQLite (dev server 重启不丢)
- kg_batch 详情页: 三元组批量提交后让用户看成功/失败的 row
- 取消任务端点: `POST /extract/tasks/{id}/cancel` → `_task_store.mark_cancelled(id)`
- 表格 payload 展开面板: 失败时调试看 `errors[]` 详情

## 测试矩阵

| 层级 | 文件 | 模式 | 覆盖 |
|---|---|---|---|
| 后端 router | `tests/kg/test_router.py` (新建) | 模式 1 mock (`_task_store` 实例) | 4 case: list_default / list_filter_kind / list_pagination / list_422 |
| 后端契约 | `tests/test_api_contract.py` | 模式 1 mock | 1 case: GET `/api/kg/extract/tasks` 在 FRONTEND_EXPECTS |
| 前端 page | `app/[locale]/knowledge/extract/page.test.tsx` (新) | vitest + jsdom | 2 case: render 表格 (mock fetchExtractTasks) + 切 tab 触发新 query |
| 前端弹框 | `_components/extract-create-dialog.test.tsx` (新) | vitest | 3 case: open/close state + 提交调 startExtract + 跳进度页 |
| 前端 extract-table | `extract-tasks-table.test.tsx` | vitest | 3 case: 行 click 路由 / 重跑弹 confirm / 确认后调 startExtract |
| 前端 batch-table | `batch-tasks-table.test.tsx` | vitest | 1 case: render + 行 click 不响应 |

## 验证清单 (合并到 plan)

- [ ] 后端 `uv run pytest tests/kg/test_router.py -v` 全绿
- [ ] 后端 `uv run pytest tests/test_api_contract.py -v` 全绿
- [ ] 后端 `uv run pyright` 0 error
- [ ] 后端 `uv run ruff check` 0 error
- [ ] 前端 `bun run test -- extract-tasks` 全绿
- [ ] 前端 `bun run typecheck` 0 error
- [ ] 前端 `bun run lint` 0 error
- [ ] 前端 `bun run format:check` 0 error
- [ ] E2E: Playwright 跑通"访问 /extract/tasks → 看到列表 → 切 tab → 点行进详情"
- [ ] commit message: `feat(kg): 抽取任务列表 + tab 切换 + 重跑动作`

## 关联文档

- 后端 router: [packages/service/src/kg/router.py](../../packages/service/src/kg/router.py)
- 后端 TaskStore: [packages/service/src/kg/tasks.py](../../packages/service/src/kg/tasks.py)
- 前端弹框组件 (替代原启动页): [packages/web/app/[locale]/knowledge/extract/_components/extract-create-dialog.tsx](../../packages/web/app/[locale]/knowledge/extract/_components/extract-create-dialog.tsx)
- 前端进度页: [packages/web/app/[locale]/knowledge/extract/[task_id]/_components/task-progress-client.tsx](../../packages/web/app/[locale]/knowledge/extract/[task_id]/_components/task-progress-client.tsx)
- 前端 API 封装: [packages/web/lib/api/knowledge.ts](../../packages/web/lib/api/knowledge.ts)
- 抽取 KG 上一期 spec: [docs/superpowers/specs/2026-07-01-markdown-extract-kg-design.md](2026-07-01-markdown-extract-kg-design.md)
