# KG 任务列表页实现 Plan (2026-07-03)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把现有 `/extract` 启动页 (上传 .md) 改造成"任务列表"页 (DataTable 列出 kg_extract / kg_batch 后台任务), 启动页改为弹框组件, 加"重跑"动作, 后端补 GET `/api/kg/extract/tasks` 列表端点.

**Architecture:**
- 前端: RSC entry `extract/page.tsx` (只返 `<TasksListClient />`) + 4 个 `_components/` 子组件 (list 容器 / 弹框 / 2 个表格)
- 后端: `kg/router.py` 新增 `GET /extract/tasks` 端点 (复用现有 `TaskStore.list_recent()`), 序列化 `_serialize_task()` 把 payload 字段摊平
- 鉴权: 后端 `require_page("knowledge")` (跟 `/extract/start` 保持一致)
- 删除: 原 `extract/page.tsx` (启动页) 整页

**Tech Stack:**
- 前端: Next.js 16 (App Router) + React 19 + TypeScript + TanStack Query 5 + next-intl 4 + shadcn/ui + 项目封装 (DataTable / AppDialog / AppConfirm / AppToggle / DataEmpty / ErrorBanner / TaskStatusBadge / CopyButton)
- 后端: FastAPI + Pydantic v2 + 现有 `TaskStore` in-memory
- 测试: vitest + jsdom (前端) / pytest 模式 1 mock (后端)

---

## 文件结构 (实现总览)

### 新增 (7)

| 文件 | 职责 |
|---|---|
| `packages/web/app/[locale]/knowledge/extract/page.tsx` (替换) | RSC entry, 只返 `<TasksListClient />` |
| `packages/web/app/[locale]/knowledge/extract/_components/tasks-list-client.tsx` | 客户端容器: AppToggle + DataTable 切换 + 弹框状态 + 刷新 |
| `packages/web/app/[locale]/knowledge/extract/_components/extract-create-dialog.tsx` | 启动弹框 (原 page.tsx 表单内容, 包成 AppDialog) |
| `packages/web/app/[locale]/knowledge/extract/_components/extract-tasks-table.tsx` | kg_extract 表格 (含"重跑"按钮 + 行 click 路由) |
| `packages/web/app/[locale]/knowledge/extract/_components/batch-tasks-table.tsx` | kg_batch 表格 (无操作, 行 click 不响应) |
| `packages/web/app/[locale]/knowledge/extract/_components/extract-create-dialog.test.tsx` | 弹框测试 (3 case) |
| `packages/web/app/[locale]/knowledge/extract/_components/tasks-list-client.test.tsx` | 列表容器测试 (2 case: render + 切 tab) |

### 删除 (1)

| 文件 | 备注 |
|---|---|
| `packages/web/app/[locale]/knowledge/extract/page.tsx` (原启动页) | 内容搬到 `_components/extract-create-dialog.tsx` |

### 修改 (5)

| 文件 | 改动 |
|---|---|
| `packages/web/lib/api/knowledge.ts` | 加 `ExtractTaskRow` / `ExtractTaskList` 类型 + `fetchExtractTasks()` 函数 |
| `packages/web/lib/api/knowledge.test.ts` | 加 `fetchExtractTasks` 测试 case |
| `packages/web/lib/format.ts` | 加 `fmtRelativeTime(epoch: number): string` (项目目前没有这工具) |
| `packages/web/messages/zh.json` + `en.json` | 加 19 个 i18n key |
| `packages/service/src/kg/router.py` | 加 `list_extract_tasks` + `_serialize_task` + 路由注册 |
| `packages/service/tests/kg/test_router_extract.py` | 加 4 个 list_extract_tasks 测试 case |
| `packages/service/tests/test_api_contract.py` | FRONTEND_EXPECTS 加 `("GET", "/api/kg/extract/tasks")` |

### 不动 (验证存在即可)

- `app/[locale]/knowledge/extract/[task_id]/**` — 进度/预览页
- `packages/service/src/kg/tasks.py` — TaskStore
- `packages/web/components/knowledge/knowledge-tabs.tsx` — children 数组 (新路径自动 startsWith 匹配)

---

## Task 1: 后端 GET /api/kg/extract/tasks 端点 + 序列化函数

**Files:**
- Modify: `packages/service/src/kg/router.py:1-50` (在 `# ============== 抽取 API (extract/...) ==============` 注释之前, 紧跟 `list_kg_datasets` 之后插入)
- Test: `packages/service/tests/kg/test_router_extract.py`

### Step 1: 写失败测试

在 `packages/service/tests/kg/test_router_extract.py` 末尾追加 4 个 test case:

```python
def test_list_extract_tasks_default_kg_extract():
    """[2026-07-03] GET /api/kg/extract/tasks 不传 kind 默认 kg_extract, 返 200 + items"""
    from src.kg.router import list_extract_tasks
    from src.kg.tasks import TaskStore

    store = TaskStore()
    store.submit("kg_extract", {"dataset": "motor", "uri": "local://x", "extractor": "spacy_rule", "splitter": "heading"})
    store.submit("kg_batch", {"rows": []})  # 不应出现在默认结果

    result = list_extract_tasks(kind="kg_extract", limit=20, offset=0, current_user=None)
    assert result["total"] == 1
    assert len(result["items"]) == 1
    assert result["items"][0]["kind"] == "kg_extract"
    assert result["items"][0]["dataset"] == "motor"
    assert result["items"][0]["uri"] == "local://x"
    assert result["total_success"] == 0
    assert result["total_failed"] == 0


def test_list_extract_tasks_filter_kind_batch():
    """[2026-07-03] kind=kg_batch 只返 batch 任务, kg_extract 被过滤"""
    from src.kg.router import list_extract_tasks
    from src.kg.tasks import TaskStore

    store = TaskStore()
    store.submit("kg_extract", {"dataset": "motor", "uri": "local://x", "extractor": "spacy_rule", "splitter": "heading"})
    store.submit("kg_batch", {"rows": []})

    result = list_extract_tasks(kind="kg_batch", limit=20, offset=0, current_user=None)
    assert result["total"] == 1
    assert result["items"][0]["kind"] == "kg_batch"
    # kg_batch 没有这些 payload 字段
    assert "dataset" not in result["items"][0]
    assert "uri" not in result["items"][0]


def test_list_extract_tasks_pagination():
    """[2026-07-03] limit + offset 切割 items, total 反映过滤后总数"""
    from src.kg.router import list_extract_tasks
    from src.kg.tasks import TaskStore

    store = TaskStore()
    for _ in range(5):
        store.submit("kg_extract", {"dataset": "motor", "uri": "local://x", "extractor": "spacy_rule", "splitter": "heading"})

    page0 = list_extract_tasks(kind="kg_extract", limit=2, offset=0, current_user=None)
    assert page0["total"] == 5
    assert len(page0["items"]) == 2
    assert page0["limit"] == 2
    assert page0["offset"] == 0

    page2 = list_extract_tasks(kind="kg_extract", limit=2, offset=4, current_user=None)
    assert len(page2["items"]) == 1


def test_list_extract_tasks_invalid_kind_422():
    """[2026-07-03] kind 不在枚举 → HTTPException 422"""
    from fastapi import HTTPException

    from src.kg.router import list_extract_tasks
    from src.kg.tasks import TaskStore

    store = TaskStore()  # 空 store

    with pytest.raises(HTTPException) as exc_info:
        list_extract_tasks(kind="invalid_kind", limit=20, offset=0, current_user=None)
    assert exc_info.value.status_code == 422


def test_list_extract_tasks_aggregates_success_failed():
    """[2026-07-03] total_success / total_failed 是 kind 过滤后 sum"""
    from src.kg.router import list_extract_tasks
    from src.kg.tasks import TaskStore

    store = TaskStore()
    tid_a = store.submit("kg_extract", {"dataset": "motor", "uri": "local://a", "extractor": "spacy_rule", "splitter": "heading"})
    store.mark_running(tid_a)
    store.mark_done(tid_a, success=10, failed=2)
    tid_b = store.submit("kg_extract", {"dataset": "plc", "uri": "local://b", "extractor": "llm_pydantic", "splitter": "token"})
    store.mark_running(tid_b)
    store.mark_done(tid_b, success=5, failed=0)
    # kg_batch 不参与 sum
    tid_c = store.submit("kg_batch", {"rows": []})
    store.mark_running(tid_c)
    store.mark_done(tid_c, success=100, failed=100)

    result = list_extract_tasks(kind="kg_extract", limit=20, offset=0, current_user=None)
    assert result["total"] == 2
    assert result["total_success"] == 15
    assert result["total_failed"] == 2
```

### Step 2: 跑测试, 确认 fail

```bash
cd packages/service && uv run pytest tests/kg/test_router_extract.py -v -k "list_extract_tasks"
```

Expected: 5 tests FAIL with `AttributeError: module 'src.kg.router' has no attribute 'list_extract_tasks'`.

### Step 3: 实现端点 + 序列化函数

打开 `packages/service/src/kg/router.py`, 在 `list_kg_datasets` 函数 (第 590 行) **之前** 插入新端点 (逻辑分组: 任务列表跟其他查询类端点放一起, 不混进 extract/* 业务流):

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
    """列本知识库后台任务 (kg_extract + kg_batch), 支持 kind 过滤 + limit/offset 分页"""
    if kind not in ("kg_extract", "kg_batch", "all"):
        raise HTTPException(422, "kind 必须在 [kg_extract, kg_batch, all]")
    # 拿 200 条 in-memory 全集做 kind 过滤 + offset 切割
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


def _serialize_task(t) -> dict:
    """把 TaskStatus 序列化成 API 响应; kg_extract 摊平 payload 里的 dataset/extractor/splitter/uri"""
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

**注意**: `_serialize_task` 接收 `TaskStatus` 实例, 类型注解用 `t` 避免循环 import; 类型由 mypy 推断。`current_user: CurrentUser` 走 `Depends` 鉴权, 测试中传 `None` mock 跳过鉴权链 (跟现有 `_kg_datasets.validate_dataset` 等模式一致)。

### Step 4: 跑测试, 确认 pass

```bash
cd packages/service && uv run pytest tests/kg/test_router_extract.py -v -k "list_extract_tasks"
```

Expected: 5 tests PASS.

### Step 5: 跑全量后端测试, 确认无回归

```bash
cd packages/service && uv run pytest tests/kg/ -v
```

Expected: 全绿 (pre-existing 失败不算新 fail, 见 [packages/service/KNOWN_ISSUES.md](../../packages/service/KNOWN_ISSUES.md))。

### Step 6: 跑 pyright + ruff

```bash
cd packages/service && uv run pyright
cd packages/service && uv run ruff check
```

Expected: 0 error.

### Step 7: Commit

```bash
git add packages/service/src/kg/router.py packages/service/tests/kg/test_router_extract.py
git commit -m "feat(kg): 列抽取任务端点 GET /api/kg/extract/tasks"
```

---

## Task 2: 契约测试加 FRONTEND_EXPECTS

**Files:**
- Modify: `packages/service/tests/test_api_contract.py:30-50` (FRONTEND_EXPECTS 列表)

### Step 1: 找 `kg` 分组位置

跑 `grep -n "/api/kg" packages/service/tests/test_api_contract.py` 找到 `# --- kg (knowledge.ts 直连) ---` 注释所在的行号。

### Step 2: 加 GET /api/kg/extract/tasks

在 `FRONTEND_EXPECTS` 列表的 `("# --- kg ...")` 分组**末尾**追加 1 行 (跟现有 `kg` 端点聚一起):

```python
    ("GET", "/api/kg/extract/tasks"),  # [2026-07-03] 列表页后端
```

### Step 3: 跑契约测试

```bash
cd packages/service && uv run pytest tests/test_api_contract.py -v
```

Expected: PASS. 如果 FAIL, 检查后端 router 是否正确注册了 `@router.get("/extract/tasks")` 路径。

### Step 4: Commit

```bash
git add packages/service/tests/test_api_contract.py
git commit -m "test(contract): 加 GET /api/kg/extract/tasks 到 FRONTEND_EXPECTS"
```

---

## Task 3: 前端 lib/api 类型 + fetchExtractTasks 函数

**Files:**
- Modify: `packages/web/lib/api/knowledge.ts` (在 fetchExtractTask 之后追加)
- Test: `packages/web/lib/api/knowledge.test.ts`

### Step 1: 写失败测试

打开 `packages/web/lib/api/knowledge.test.ts`, 在 import 块加 `fetchExtractTasks` import, 在 describe 块末尾加 3 个 case:

```typescript
// import 块加
import {
  // ... 现有 import
  fetchExtractTasks,
  // ... 现有 import
} from "./knowledge";
```

```typescript
  // describe 块末尾 (knowledgeApi 内部) 加
  it("fetchExtractTasks 返 {items, total, total_success, total_failed}", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        okResponse({
          items: [{ task_id: "t1", kind: "kg_extract", state: "done", success: 5, failed: 0, created_at: 0, started_at: 0, finished_at: 0 }],
          total: 1,
          total_success: 5,
          total_failed: 0,
          limit: 20,
          offset: 0,
        }),
      ),
    );
    const out = await fetchExtractTasks({ kind: "kg_extract" });
    expect(out.total).toBe(1);
    expect(out.items[0].task_id).toBe("t1");
  });

  it("fetchExtractTasks 拼 query string kind/limit/offset", async () => {
    const mock = vi.fn().mockResolvedValue(
      okResponse({ items: [], total: 0, total_success: 0, total_failed: 0, limit: 5, offset: 10 }),
    );
    vi.stubGlobal("fetch", mock);
    await fetchExtractTasks({ kind: "kg_batch", limit: 5, offset: 10 });
    const url = String(mock.mock.calls[0][0]);
    expect(url).toContain("kind=kg_batch");
    expect(url).toContain("limit=5");
    expect(url).toContain("offset=10");
  });

  it("fetchExtractTasks 4xx 抛 ApiError", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(errResponse(422, "Unprocessable", "kind 必须在 [kg_extract, kg_batch, all]")));
    await expect(fetchExtractTasks({ kind: "invalid" as "kg_extract" })).rejects.toThrow("kind 必须在");
  });
```

### Step 2: 跑测试, 确认 fail

```bash
cd packages/web && bun run test -- knowledge.test.ts
```

Expected: 3 new tests FAIL with `fetchExtractTasks is not a function` 或类似 import 错。

### Step 3: 实现类型 + 函数

在 `packages/web/lib/api/knowledge.ts` 末尾追加 (在 `triggerExportDownload` 之后):

```typescript
// ============================================================
// (2026-07-03) KG 任务列表页: 后端 GET /api/kg/extract/tasks
// ============================================================

/** 抽取任务行 (kg_extract / kg_batch 共用形状, kg_extract 多 4 个 payload 字段) */
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
  created_at: number;       // epoch float (秒)
  started_at: number | null;
  finished_at: number | null;
};

/** 任务列表响应 (含分页 + 聚合) */
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

### Step 4: 跑测试, 确认 pass

```bash
cd packages/web && bun run test -- knowledge.test.ts
```

Expected: 3 new tests PASS, 老 case 仍绿。

### Step 5: typecheck + lint

```bash
cd packages/web && bun run typecheck
cd packages/web && bun run lint
```

Expected: 0 error.

### Step 6: Commit

```bash
git add packages/web/lib/api/knowledge.ts packages/web/lib/api/knowledge.test.ts
git commit -m "feat(web): fetchExtractTasks + ExtractTaskRow/List 类型"
```

---

## Task 4: 前端 fmtRelativeTime 工具

**Files:**
- Modify: `packages/web/lib/format.ts`
- Test: 跟随 Task 8 列表容器测试一起 (fmtRelativeTime 渲染断言)

### Step 1: 追加工具

打开 `packages/web/lib/format.ts`, 末尾追加:

```typescript
import { SECONDS_PER_MINUTE, SECONDS_PER_HOUR, SECONDS_PER_DAY, ONE } from "@/const";

/**
 * epoch 秒 → 相对时间字符串 ("3 秒前" / "2 分钟前" / "1 小时前" / "5 天前").
 * 用于任务列表 created_at 列渲染. 跟 antd Tag / 5+ 表的"X 前"风格一致.
 *
 * @param epoch epoch 秒 (后端 TaskStatus.created_at 是 time.time() 浮点)
 * @param now 当前 epoch 秒, 默认 Date.now()/1000 (测试可注入)
 * @returns 中文相对时间 (i18n 由调用方决定, 这里只返中文常量)
 */
export const fmtRelativeTime = (epoch: number, now: number = Date.now() / SECONDS_PER_MINUTE): string => {
  const diff = Math.max(0, now - epoch);
  if (diff < SECONDS_PER_MINUTE) return `${Math.floor(diff)} 秒前`;
  if (diff < SECONDS_PER_HOUR) return `${Math.floor(diff / SECONDS_PER_MINUTE)} 分钟前`;
  if (diff < SECONDS_PER_DAY) return `${Math.floor(diff / SECONDS_PER_HOUR)} 小时前`;
  return `${Math.floor(diff / SECONDS_PER_DAY)} 天前`;
};
```

> **注**: `now` 默认 `Date.now() / SECONDS_PER_MINUTE` 是笔误, 应该是 `Date.now() / 1000` 转秒。修正:

```typescript
export const fmtRelativeTime = (epoch: number, now: number = Date.now() / 1000): string => {
```

> 同时 import 去掉 `SECONDS_PER_HOUR` / `SECONDS_PER_DAY` 重新命名为 `SECONDS_PER_HOUR` / `SECONDS_PER_DAY` (const/index.ts:31-32 已定义)。

### Step 2: typecheck

```bash
cd packages/web && bun run typecheck
```

Expected: 0 error.

### Step 3: Commit

```bash
git add packages/web/lib/format.ts
git commit -m "feat(web): fmtRelativeTime 时间格式化工具"
```

---

## Task 5: i18n 19 个 key 同步 zh/en

**Files:**
- Modify: `packages/web/messages/zh.json`
- Modify: `packages/web/messages/en.json`

### Step 1: 加 zh.json (identity, 中文作 key)

打开 `packages/web/messages/zh.json`, 在合适位置 (e.g. 最后一个 i18n key 之后) 追加 19 行。**确保 JSON 合法** (用 `node -e "JSON.parse(require('fs').readFileSync('messages/zh.json'))"` 验证):

```json
  "任务列表": "任务列表",
  "抽取": "抽取",
  "批量": "批量",
  "新建提取": "新建提取",
  "刷新": "刷新",
  "暂无任务": "暂无任务",
  "暂无任务描述": "暂无任务。点击右上角\"新建提取\"开始抽取。",
  "复制": "复制",
  "重跑": "重跑",
  "重跑确认": "重跑将基于历史参数启动新任务, 是否继续?",
  "数据集": "数据集",
  "抽取器": "抽取器",
  "切片器": "切片器",
  "创建时间": "创建时间",
  "进度": "进度",
  "任务 ID": "任务 ID",
  "加载任务失败": "加载任务失败",
  "重跑参数缺失": "重跑参数缺失",
  "重跑失败": "重跑失败",
  "总数": "总数",
  "成功": "成功",
  "失败": "失败",
```

### Step 2: 加 en.json (英文翻译)

打开 `packages/web/messages/en.json`, 同位置追加:

```json
  "任务列表": "Tasks",
  "抽取": "Extract",
  "批量": "Batch",
  "新建提取": "New Extraction",
  "刷新": "Refresh",
  "暂无任务": "No tasks yet",
  "暂无任务描述": "No tasks. Click \"New Extraction\" to start.",
  "复制": "Copy",
  "重跑": "Re-run",
  "重跑确认": "Re-run will start a new task with the same parameters. Continue?",
  "数据集": "Dataset",
  "抽取器": "Extractor",
  "切片器": "Splitter",
  "创建时间": "Created",
  "进度": "Progress",
  "任务 ID": "Task ID",
  "加载任务失败": "Failed to load tasks",
  "重跑参数缺失": "Re-run parameters missing",
  "重跑失败": "Re-run failed",
  "总数": "Total",
  "成功": "Succeeded",
  "失败": "Failed",
```

### Step 3: 验证 JSON 合法

```bash
cd packages/web && node -e "JSON.parse(require('fs').readFileSync('messages/zh.json')); JSON.parse(require('fs').readFileSync('messages/en.json')); console.log('OK')"
```

Expected: `OK`.

### Step 4: Commit

```bash
git add packages/web/messages/zh.json packages/web/messages/en.json
git commit -m "i18n: 加 KG 任务列表页 19 个 key (zh/en)"
```

---

## Task 6: 创建启动弹框组件 ExtractCreateDialog

**Files:**
- Create: `packages/web/app/[locale]/knowledge/extract/_components/extract-create-dialog.tsx`
- Test: `packages/web/app/[locale]/knowledge/extract/_components/extract-create-dialog.test.tsx`

### Step 1: 写失败测试

Create `extract-create-dialog.test.tsx`:

```tsx
// 启动弹框测试 (2026-07-03)
// 复刻老 page.tsx 表单内容, 包成 AppDialog
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, waitFor } from "@testing-library/react";
import { IntlWrapper } from "@/lib/test-utils/intl-wrapper";

vi.mock("server-only", () => ({}));

const mockStartExtract = vi.fn(async () => ({ task_id: "new-tx-id", state: "queued" }));
const mockUploadExtractFile = vi.fn(async () => ({ uri: "local://inputs/motor/abc/source.md", file_id: "abc", dataset: "motor" }));
const mockPush = vi.fn();
const mockFile = new File(["# test"], "test.md", { type: "text/markdown" });

vi.mock("@/lib/api/knowledge", () => ({
  fetchExtractDatasets: async () => [{ label: "motor" }, { label: "plc" }],
  fetchExtractors: async () => [{ id: "llm_pydantic", available: true }, { id: "spacy_rule", available: true }],
  fetchSplitters: async () => [{ id: "heading", chunk_size_range: [100, 5000] }, { id: "token", chunk_size_range: [128, 2048] }],
  uploadExtractFile: (...args: unknown[]) => mockUploadExtractFile(...args),
  startExtract: (...args: unknown[]) => mockStartExtract(...args),
}));

vi.mock("@/i18n/navigation", () => ({
  useRouter: () => ({ push: mockPush }),
}));

afterEach(() => vi.clearAllMocks());

describe("ExtractCreateDialog", () => {
  beforeEach(() => {
    mockStartExtract.mockResolvedValue({ task_id: "new-tx-id", state: "queued" });
    mockUploadExtractFile.mockResolvedValue({ uri: "local://inputs/motor/abc/source.md", file_id: "abc", dataset: "motor" });
  });

  it("open=false 不渲染 Dialog 内容", () => {
    const { ExtractCreateDialog } = require("./extract-create-dialog");
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const { container } = render(
      <IntlWrapper locale="zh">
        <QueryClientProvider client={qc}>
          <ExtractCreateDialog open={false} onOpenChange={vi.fn()} />
        </QueryClientProvider>
      </IntlWrapper>,
    );
    expect(container.textContent).not.toContain("数据集");
  });

  it("open=true 渲染 3 个 AppSelect + FileDropzone", async () => {
    const { ExtractCreateDialog } = require("./extract-create-dialog");
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const { container } = render(
      <IntlWrapper locale="zh">
        <QueryClientProvider client={qc}>
          <ExtractCreateDialog open onOpenChange={vi.fn()} />
        </QueryClientProvider>
      </IntlWrapper>,
    );
    await waitFor(() => {
      expect(container.textContent).toContain("数据集");
      expect(container.textContent).toContain("抽取器");
      expect(container.textContent).toContain("切片器");
      expect(container.textContent).toContain("上传 Markdown 文件");
    });
  });

  it("提交后调 startExtract + router.push 跳进度页", async () => {
    const { ExtractCreateDialog } = require("./extract-create-dialog");
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const { container } = render(
      <IntlWrapper locale="zh">
        <QueryClientProvider client={qc}>
          <ExtractCreateDialog open onOpenChange={vi.fn()} />
        </QueryClientProvider>
      </IntlWrapper>,
    );

    // 模拟上传文件 (跳 FileDropzone 内部 input)
    await waitFor(() => expect(container.textContent).toContain("上传 Markdown 文件"));
    const fileInput = container.querySelector('input[type="file"]') as HTMLInputElement;
    fireEvent.change(fileInput, { target: { files: [mockFile] } });

    // 提交
    await waitFor(() => {
      const submitBtn = container.querySelector('button[type="submit"]') as HTMLButtonElement;
      expect(submitBtn).toBeTruthy();
      expect(submitBtn.disabled).toBe(false);
    });
    const submitBtn = container.querySelector('button[type="submit"]') as HTMLButtonElement;
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(mockUploadExtractFile).toHaveBeenCalled();
      expect(mockStartExtract).toHaveBeenCalledWith({
        uri: "local://inputs/motor/abc/source.md",
        dataset: "motor",
        extractor: "llm_pydantic",
        splitter: "heading",
      });
      expect(mockPush).toHaveBeenCalledWith(expect.stringContaining("/knowledge/extract/new-tx-id"));
    });
  });
});
```

### Step 2: 跑测试, 确认 fail

```bash
cd packages/web && bun run test -- extract-create-dialog.test.tsx
```

Expected: FAIL with `Cannot find module './extract-create-dialog'`.

### Step 3: 实现弹框组件

Create `extract-create-dialog.tsx`:

```tsx
"use client";
// 知识图谱抽取启动弹框 (2026-07-03)
// 复刻原 page.tsx 表单内容 (FileDropzone + 3 AppSelect + 启动按钮),
// 包成 AppDialog 由列表页触发. 提交后调 startExtract 启新 task, 弹框关闭, 跳进度页.
/* oxlint-disable max-statements, id-length -- 弹框逻辑连贯, 拆分增加阅读成本; 短变量 d/e/s 是 map 回调惯例 */
import { useState, useTransition, type FormEvent } from "react";
import { useRouter } from "@/i18n/navigation";
import { useTranslations } from "next-intl";
import { useQuery } from "@tanstack/react-query";
import { FileText, X } from "lucide-react";
import { AppDialog } from "@/components/common/dialog/app-dialog";
import { FileDropzone } from "@/components/common/input/app-file-dropzone";
import { AppSelect } from "@/components/common/input/app-select";
import { Button } from "@/components/ui/button";
import { ErrorBanner } from "@/components/common/feedback/app-error-banner";
import { FIVE } from "@/const";
import { fmtSize } from "@/lib/format";
import {
  fetchExtractDatasets,
  fetchExtractors,
  fetchSplitters,
  startExtract,
  uploadExtractFile,
} from "@/lib/api/knowledge";

export interface ExtractCreateDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

const ExtractCreateDialog = ({ open, onOpenChange }: ExtractCreateDialogProps) => {
  const tr = useTranslations();
  const router = useRouter();
  const [isPending, startTransition] = useTransition();
  const [file, setFile] = useState<File | null>(null);
  const [dataset, setDataset] = useState("motor");
  const [extractor, setExtractor] = useState("llm_pydantic");
  const [splitter, setSplitter] = useState("heading");
  const [error, setError] = useState<string | null>(null);

  const { data: datasets = [] } = useQuery({
    queryKey: ["kg", "extract-datasets"],
    queryFn: fetchExtractDatasets,
  });
  const { data: extractors = [] } = useQuery({
    queryKey: ["kg", "extractors"],
    queryFn: fetchExtractors,
  });
  const { data: splitters = [] } = useQuery({
    queryKey: ["kg", "splitters"],
    queryFn: fetchSplitters,
  });

  const handleClose = (next: boolean) => {
    if (!next) {
      // 关闭时重置 (避免下次打开残留)
      setFile(null);
      setError(null);
    }
    onOpenChange(next);
  };

  const handleSubmit = (event: FormEvent<HTMLFormElement>): void => {
    event.preventDefault();
    if (!file) {
      setError(tr("请先选择文件"));
      return;
    }
    setError(null);
    startTransition(async () => {
      try {
        const { uri } = await uploadExtractFile(file, dataset);
        const { task_id } = await startExtract({
          uri,
          dataset,
          extractor,
          splitter,
        });
        // 关闭弹框 + 跳进度页
        handleClose(false);
        void router.push(`/knowledge/extract/${task_id}?dataset=${encodeURIComponent(dataset)}`);
      } catch (submitError) {
        const message = submitError instanceof Error ? submitError.message : tr("启动失败");
        setError(message);
      }
    });
  };

  return (
    <AppDialog
      open={open}
      onOpenChange={handleClose}
      title={tr("新建提取")}
      description={tr("选择数据集与抽取器")}
      maxWidth="lg"
      error={error}
      errorTestid="extract-dialog-error"
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="space-y-1">
          <label className="text-sm font-medium">{tr("数据集")}</label>
          <AppSelect
            value={dataset}
            onChange={setDataset}
            options={datasets.map((d) => ({ value: d.label, label: d.label }))}
          />
        </div>
        <div className="space-y-1">
          <label className="text-sm font-medium">{tr("抽取器")}</label>
          <AppSelect
            value={extractor}
            onChange={setExtractor}
            options={extractors.map((e) => ({ value: e.id, label: e.id }))}
          />
        </div>
        <div className="space-y-1">
          <label className="text-sm font-medium">{tr("切片器")}</label>
          <AppSelect
            value={splitter}
            onChange={setSplitter}
            options={splitters.map((s) => ({ value: s.id, label: s.id }))}
          />
        </div>
        <div className="space-y-1">
          <label className="text-sm font-medium">{tr("上传 Markdown 文件")}</label>
          {file === null ? (
            <FileDropzone onFile={setFile} accept=".md" maxSizeMB={FIVE} />
          ) : (
            <div
              className="flex items-center justify-between gap-3 rounded-lg border border-border/60 bg-card/40 p-4"
              data-testid="extract-file-info"
            >
              <div className="flex min-w-0 items-center gap-3">
                <FileText className="h-5 w-5 shrink-0 text-muted-foreground" />
                <div className="min-w-0">
                  <div className="truncate text-sm font-medium text-foreground">{file.name}</div>
                  <div className="text-xs text-muted-foreground">{fmtSize(file.size)}</div>
                </div>
              </div>
              <Button
                data-testid="extract-file-clear"
                type="button"
                variant="ghost"
                size="icon"
                onClick={() => setFile(null)}
                aria-label={tr("清空")}
              >
                <X className="h-4 w-4" />
              </Button>
            </div>
          )}
        </div>
        <div className="flex justify-end gap-2 border-t border-border/40 pt-4">
          <Button
            type="button"
            variant="ghost"
            onClick={() => handleClose(false)}
            disabled={isPending}
          >
            {tr("取消")}
          </Button>
          <Button type="submit" disabled={!file || isPending}>
            {isPending ? tr("加载中…") : tr("启动抽取")}
          </Button>
        </div>
      </form>
    </AppDialog>
  );
};

export default ExtractCreateDialog;
```

### Step 4: 跑测试, 确认 pass

```bash
cd packages/web && bun run test -- extract-create-dialog.test.tsx
```

Expected: 3 tests PASS.

### Step 5: typecheck + lint

```bash
cd packages/web && bun run typecheck
cd packages/web && bun run lint
```

Expected: 0 error.

### Step 6: Commit

```bash
git add packages/web/app/[locale]/knowledge/extract/_components/extract-create-dialog.tsx packages/web/app/[locale]/knowledge/extract/_components/extract-create-dialog.test.tsx
git commit -m "feat(web): ExtractCreateDialog 启动弹框组件"
```

---

## Task 7: 创建 kg_extract 表格组件 ExtractTasksTable (含重跑)

**Files:**
- Create: `packages/web/app/[locale]/knowledge/extract/_components/extract-tasks-table.tsx`
- Test: `packages/web/app/[locale]/knowledge/extract/_components/extract-tasks-table.test.tsx`

### Step 1: 写失败测试 (3 case: 行 click 路由 / 重跑弹 confirm / 确认后调 startExtract)

Create `extract-tasks-table.test.tsx`:

```tsx
// kg_extract 表格测试 (2026-07-03): 行 click 路由 + 重跑 AppConfirm 弹窗 + 确认后调 startExtract
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, waitFor } from "@testing-library/react";
import { IntlWrapper } from "@/lib/test-utils/intl-wrapper";

vi.mock("server-only", () => ({}));

const mockPush = vi.fn();
vi.mock("@/i18n/navigation", () => ({
  useRouter: () => ({ push: mockPush }),
}));

const mockStartExtract = vi.fn();
vi.mock("@/lib/api/knowledge", () => ({
  startExtract: (...args: unknown[]) => mockStartExtract(...args),
}));

const mockRows = [
  {
    task_id: "tx-done",
    kind: "kg_extract" as const,
    state: "done" as const,
    dataset: "motor",
    extractor: "spacy_rule",
    splitter: "heading",
    uri: "local://inputs/motor/done/source.md",
    success: 10,
    failed: 0,
    created_at: Math.floor(Date.now() / 1000) - 30,
    started_at: 0,
    finished_at: 0,
  },
  {
    task_id: "tx-running",
    kind: "kg_extract" as const,
    state: "running" as const,
    dataset: "plc",
    extractor: "llm_pydantic",
    splitter: "token",
    uri: "local://inputs/plc/running/source.md",
    success: 0,
    failed: 0,
    created_at: Math.floor(Date.now() / 1000) - 5,
    started_at: 0,
    finished_at: null,
  },
];

const baseProps = {
  rows: mockRows,
  total: 2,
  totalSuccess: 10,
  totalFailed: 0,
  page: 0,
  pageSize: 20,
  loading: false,
  error: null,
  onPageChange: vi.fn(),
  onRetry: vi.fn(),
};

afterEach(() => vi.clearAllMocks());

describe("ExtractTasksTable", () => {
  beforeEach(() => {
    mockStartExtract.mockResolvedValue({ task_id: "new-tx", state: "queued" });
  });

  it("点 done 行跳 preview 路径", async () => {
    const { default: ExtractTasksTable } = await import("./extract-tasks-table");
    const { container } = render(<IntlWrapper locale="zh"><ExtractTasksTable {...baseProps} /></IntlWrapper>);
    await waitFor(() => {
      const row = container.querySelector('[data-testid="data-table-row-tx-done"]') as HTMLElement | null;
      expect(row).toBeTruthy();
    });
    const row = container.querySelector('[data-testid="data-table-row-tx-done"]') as HTMLElement;
    fireEvent.click(row);
    await waitFor(() => {
      expect(mockPush).toHaveBeenCalledWith(expect.stringContaining("/knowledge/extract/tx-done/preview?dataset=motor"));
    });
  });

  it("点 running 行跳进度页 (非 done/partial)", async () => {
    const { default: ExtractTasksTable } = await import("./extract-tasks-table");
    const { container } = render(<IntlWrapper locale="zh"><ExtractTasksTable {...baseProps} /></IntlWrapper>);
    await waitFor(() => {
      const row = container.querySelector('[data-testid="data-table-row-tx-running"]') as HTMLElement | null;
      expect(row).toBeTruthy();
    });
    const row = container.querySelector('[data-testid="data-table-row-tx-running"]') as HTMLElement;
    fireEvent.click(row);
    await waitFor(() => {
      expect(mockPush).toHaveBeenCalledWith(expect.stringContaining("/knowledge/extract/tx-running?dataset=plc"));
    });
  });

  it("点重跑按钮弹 AppConfirm, 确认后调 startExtract + 跳进度页", async () => {
    const { default: ExtractTasksTable } = await import("./extract-tasks-table");
    const { container, getByTestId } = render(<IntlWrapper locale="zh"><ExtractTasksTable {...baseProps} /></IntlWrapper>);
    await waitFor(() => {
      expect(getByTestId("rerun-tx-done")).toBeTruthy();
    });
    fireEvent.click(getByTestId("rerun-tx-done"));
    // AppConfirm 弹窗
    await waitFor(() => {
      expect(container.textContent).toContain("重跑将基于历史参数启动新任务");
    });
    // 确认按钮: 取 alertdialog 上的 AlertDialogAction
    const confirmBtn = container.querySelector('[role="alertdialog"] button:last-child') as HTMLButtonElement;
    fireEvent.click(confirmBtn);
    await waitFor(() => {
      expect(mockStartExtract).toHaveBeenCalledWith({
        uri: "local://inputs/motor/done/source.md",
        dataset: "motor",
        extractor: "spacy_rule",
        splitter: "heading",
      });
      expect(mockPush).toHaveBeenCalledWith(expect.stringContaining("/knowledge/extract/new-tx?dataset=motor"));
    });
  });
});
```

### Step 2: 跑测试, 确认 fail

```bash
cd packages/web && bun run test -- extract-tasks-table.test.tsx
```

Expected: FAIL with `Cannot find module './extract-tasks-table'`.

### Step 3: 实现表格组件

Create `extract-tasks-table.tsx`:

```tsx
"use client";
// kg_extract 任务列表 (2026-07-03): Task ID (复制) + Dataset/Extractor/Splitter + 状态 + 进度 + 创建时间 + 重跑
// 行 click 路由: done/partial → preview; 其他 → 进度页. 重跑弹 AppConfirm 二次确认.
/* oxlint-disable max-statements -- 表格列定义连贯, 拆分增加阅读成本 */
import { useState } from "react";
import { useRouter } from "@/i18n/navigation";
import { useTranslations } from "next-intl";
import { toast } from "sonner";
import { FileText, RefreshCw } from "lucide-react";
import { type ColumnDef } from "@/components/common/table";
import { DataTable } from "@/components/common/table";
import { Button } from "@/components/ui/button";
import { AppConfirm } from "@/components/common/confirm";
import { TaskStatusBadge } from "@/components/common/display/app-task-status-badge";
import { DataEmpty } from "@/components/common/display/app-data-empty";
import { CopyButton } from "@/components/common/button/app-copy-button";
import { startExtract, type ExtractTaskRow } from "@/lib/api/knowledge";
import { fmtRelativeTime } from "@/lib/format";

export interface ExtractTasksTableProps {
  rows: ExtractTaskRow[];
  total: number;
  totalSuccess: number;
  totalFailed: number;
  page: number;
  pageSize: number;
  loading: boolean;
  error: string | null;
  onPageChange: (page: number) => void;
  onRetry: () => void;
}

const TASK_ID_PREVIEW_LENGTH = 8;

const ExtractTasksTable = ({
  rows,
  loading,
  error,
  page,
  pageSize,
  total,
  totalSuccess,
  totalFailed,
  onPageChange,
  onRetry,
}: ExtractTasksTableProps) => {
  const tr = useTranslations();
  const router = useRouter();
  const [confirmRow, setConfirmRow] = useState<ExtractTaskRow | null>(null);

  const handleRowClick = (row: ExtractTaskRow) => {
    const dataset = row.dataset ?? "motor";
    if (row.state === "done" || row.state === "partial") {
      void router.push(`/knowledge/extract/${row.task_id}/preview?dataset=${encodeURIComponent(dataset)}`);
    } else {
      void router.push(`/knowledge/extract/${row.task_id}?dataset=${encodeURIComponent(dataset)}`);
    }
  };

  const handleRerunClick = (row: ExtractTaskRow) => {
    if (!row.uri || !row.dataset || !row.extractor || !row.splitter) {
      toast.error(tr("重跑参数缺失"));
      return;
    }
    setConfirmRow(row);
  };

  const handleRerunConfirm = async () => {
    const row = confirmRow;
    if (!row || !row.uri || !row.dataset || !row.extractor || !row.splitter) return;
    setConfirmRow(null);
    try {
      const { task_id } = await startExtract({
        uri: row.uri,
        dataset: row.dataset,
        extractor: row.extractor as "spacy_rule" | "llm_pydantic",
        splitter: row.splitter as "heading" | "token" | "semantic",
      });
      void router.push(`/knowledge/extract/${task_id}?dataset=${encodeURIComponent(row.dataset)}`);
    } catch (err) {
      const message = err instanceof Error ? err.message : "";
      toast.error(`${tr("重跑失败")}: ${message}`);
    }
  };

  const columns: ColumnDef<ExtractTaskRow>[] = [
    {
      id: "task_id",
      header: tr("任务 ID"),
      cell: ({ row }) => {
        const id = row.original.task_id;
        return (
          <div className="flex items-center gap-2">
            <span className="font-mono text-xs">{id.slice(0, TASK_ID_PREVIEW_LENGTH)}…</span>
            <CopyButton text={id} label={tr("复制")} successLabel="✓" size="sm" variant="ghost" />
          </div>
        );
      },
    },
    {
      id: "dataset",
      header: tr("数据集"),
      cell: ({ row }) => <span>{row.original.dataset ?? "-"}</span>,
    },
    {
      id: "extractor",
      header: tr("抽取器"),
      cell: ({ row }) => <span className="text-xs">{row.original.extractor ?? "-"}</span>,
    },
    {
      id: "splitter",
      header: tr("切片器"),
      cell: ({ row }) => <span className="text-xs">{row.original.splitter ?? "-"}</span>,
    },
    {
      id: "state",
      header: tr("状态"),
      cell: ({ row }) => <TaskStatusBadge state={row.original.state} />,
    },
    {
      id: "progress",
      header: tr("进度"),
      cell: ({ row }) => (
        <span className="text-xs text-muted-foreground">
          {row.original.success}/{row.original.success + row.original.failed}
        </span>
      ),
    },
    {
      id: "created_at",
      header: tr("创建时间"),
      cell: ({ row }) => <span className="text-xs text-muted-foreground">{fmtRelativeTime(row.original.created_at)}</span>,
    },
    {
      id: "actions",
      header: tr("操作"),
      cell: ({ row }) => (
        <Button
          variant="ghost"
          size="sm"
          onClick={(e) => {
            e.stopPropagation();  // 不触发行 click 路由
            handleRerunClick(row.original);
          }}
          data-testid={`rerun-${row.original.task_id}`}
        >
          <RefreshCw className="mr-1 h-3 w-3" />
          {tr("重跑")}
        </Button>
      ),
    },
  ];

  return (
    <>
      <DataTable<ExtractTaskRow>
        dataSource={rows}
        columns={columns}
        rowKey="task_id"
        loading={loading}
        onRowClick={handleRowClick}
        rowClassName={() => "cursor-pointer hover:bg-muted/50"}
        emptyText={
          <DataEmpty
            icon={FileText}
            title={tr("暂无任务")}
            description={tr("暂无任务描述")}
          />
        }
        pagination={
          total > 0
            ? { current: page + 1, pageSize, total, onChange: (p) => onPageChange(p - 1) }
            : undefined
        }
      />
      {error ? (
        <div className="mt-4">
          <ErrorBannerWithRetry error={error} onRetry={onRetry} />
        </div>
      ) : null}
      {confirmRow ? (
        <AppConfirm
          open
          onOpenChange={(open) => {
            if (!open) setConfirmRow(null);
          }}
          title={tr("重跑确认")}
          description={tr("重跑将基于历史参数启动新任务, 是否继续?")}
          onConfirm={() => {
            void handleRerunConfirm();
          }}
        />
      ) : null}
      <p className="mt-2 text-xs text-muted-foreground">
        {tr("任务列表")} · {tr("总数")}: {total} · {tr("成功")}: {totalSuccess} · {tr("失败")}: {totalFailed}
      </p>
    </>
  );
};

// ErrorBanner 带 "重试" 按钮的本地 helper
const ErrorBannerWithRetry = ({ error, onRetry }: { error: string; onRetry: () => void }) => {
  const tr = useTranslations();
  return (
    <ErrorBanner
      variant="destructive"
      title={tr("加载任务失败")}
      description={error}
      action={
        <Button variant="outline" size="sm" onClick={onRetry}>
          {tr("刷新")}
        </Button>
      }
    />
  );
};

export default ExtractTasksTable;
```

### Step 4: 跑测试, 确认 pass

```bash
cd packages/web && bun run test -- extract-tasks-table.test.tsx
```

Expected: 3 tests PASS.

### Step 5: typecheck + lint

```bash
cd packages/web && bun run typecheck
cd packages/web && bun run lint
```

Expected: 0 error.

### Step 6: Commit

```bash
git add packages/web/app/[locale]/knowledge/extract/_components/extract-tasks-table.tsx packages/web/app/[locale]/knowledge/extract/_components/extract-tasks-table.test.tsx
git commit -m "feat(web): ExtractTasksTable kg_extract 表格 + 3 个测试 case"
```

---

## Task 8: 创建 kg_batch 表格组件 BatchTasksTable

**Files:**
- Create: `packages/web/app/[locale]/knowledge/extract/_components/batch-tasks-table.tsx`
- Test: `packages/web/app/[locale]/knowledge/extract/_components/batch-tasks-table.test.tsx`

### Step 1: 写失败测试 (1 case: render 不响应 click)

Create `batch-tasks-table.test.tsx`:

```tsx
// kg_batch 表格测试 (2026-07-03): render 行 + 行 click 不响应
import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, waitFor } from "@testing-library/react";
import { IntlWrapper } from "@/lib/test-utils/intl-wrapper";

vi.mock("server-only", () => ({}));

const mockPush = vi.fn();
vi.mock("@/i18n/navigation", () => ({
  useRouter: () => ({ push: mockPush }),
}));

const mockRows = [
  {
    task_id: "batch-001",
    kind: "kg_batch" as const,
    state: "done" as const,
    success: 5,
    failed: 0,
    created_at: Math.floor(Date.now() / 1000) - 60,
    started_at: 0,
    finished_at: 0,
  },
];

const baseProps = {
  rows: mockRows,
  total: 1,
  totalSuccess: 5,
  totalFailed: 0,
  page: 0,
  pageSize: 20,
  loading: false,
  error: null,
  onPageChange: vi.fn(),
  onRetry: vi.fn(),
};

describe("BatchTasksTable", () => {
  it("render batch 行, 行 click 不触发 router.push (无详情页)", async () => {
    const { default: BatchTasksTable } = await import("./batch-tasks-table");
    const { container } = render(<IntlWrapper locale="zh"><BatchTasksTable {...baseProps} /></IntlWrapper>);
    await waitFor(() => {
      const row = container.querySelector('[data-testid="data-table-row-batch-001"]') as HTMLElement | null;
      expect(row).toBeTruthy();
    });
    const row = container.querySelector('[data-testid="data-table-row-batch-001"]') as HTMLElement;
    fireEvent.click(row);
    // wait 一拍让 click handler 跑完
    await new Promise((r) => setTimeout(r, 50));
    expect(mockPush).not.toHaveBeenCalled();
  });
});
```

### Step 2: 跑测试, 确认 fail

```bash
cd packages/web && bun run test -- batch-tasks-table.test.tsx
```

Expected: FAIL with `Cannot find module './batch-tasks-table'`.

### Step 3: 实现表格组件

Create `batch-tasks-table.tsx`:

```tsx
"use client";
// kg_batch 任务列表 (2026-07-03): 跟 kg_extract 类似, 但无"重跑" + 行 click 不响应 (无详情页)
/* oxlint-disable max-statements -- 表格列定义连贯, 拆分增加阅读成本 */
import { useTranslations } from "next-intl";
import { FileText } from "lucide-react";
import { type ColumnDef } from "@/components/common/table";
import { DataTable } from "@/components/common/table";
import { ErrorBanner } from "@/components/common/feedback/app-error-banner";
import { TaskStatusBadge } from "@/components/common/display/app-task-status-badge";
import { DataEmpty } from "@/components/common/display/app-data-empty";
import { CopyButton } from "@/components/common/button/app-copy-button";
import { type ExtractTaskRow } from "@/lib/api/knowledge";
import { fmtRelativeTime } from "@/lib/format";
import { Button } from "@/components/ui/button";

const TASK_ID_PREVIEW_LENGTH = 8;

export interface BatchTasksTableProps {
  rows: ExtractTaskRow[];
  total: number;
  totalSuccess: number;
  totalFailed: number;
  page: number;
  pageSize: number;
  loading: boolean;
  error: string | null;
  onPageChange: (page: number) => void;
  onRetry: () => void;
}

const BatchTasksTable = ({
  rows,
  loading,
  error,
  page,
  pageSize,
  total,
  onPageChange,
  onRetry,
}: BatchTasksTableProps) => {
  const tr = useTranslations();

  const columns: ColumnDef<ExtractTaskRow>[] = [
    {
      id: "task_id",
      header: tr("任务 ID"),
      cell: ({ row }) => {
        const id = row.original.task_id;
        return (
          <div className="flex items-center gap-2">
            <span className="font-mono text-xs">{id.slice(0, TASK_ID_PREVIEW_LENGTH)}…</span>
            <CopyButton text={id} label={tr("复制")} successLabel="✓" size="sm" variant="ghost" />
          </div>
        );
      },
    },
    {
      id: "kind",
      header: tr("类型"),
      cell: () => <span className="text-xs text-muted-foreground">kg_batch</span>,
    },
    {
      id: "state",
      header: tr("状态"),
      cell: ({ row }) => <TaskStatusBadge state={row.original.state} />,
    },
    {
      id: "progress",
      header: tr("进度"),
      cell: ({ row }) => (
        <span className="text-xs text-muted-foreground">
          {row.original.success}/{row.original.success + row.original.failed}
        </span>
      ),
    },
    {
      id: "created_at",
      header: tr("创建时间"),
      cell: ({ row }) => <span className="text-xs text-muted-foreground">{fmtRelativeTime(row.original.created_at)}</span>,
    },
  ];

  return (
    <>
      <DataTable<ExtractTaskRow>
        dataSource={rows}
        columns={columns}
        rowKey="task_id"
        loading={loading}
        emptyText={
          <DataEmpty
            icon={FileText}
            title={tr("暂无任务")}
            description={tr("暂无任务描述")}
          />
        }
        pagination={
          total > 0
            ? { current: page + 1, pageSize, total, onChange: (p) => onPageChange(p - 1) }
            : undefined
        }
      />
      {error ? (
        <div className="mt-4">
          <ErrorBanner
            variant="destructive"
            title={tr("加载任务失败")}
            description={error}
            action={
              <Button variant="outline" size="sm" onClick={onRetry}>
                {tr("刷新")}
              </Button>
            }
          />
        </div>
      ) : null}
    </>
  );
};

export default BatchTasksTable;
```

> kg_batch 没有 dataset/extractor/splitter 字段, 只展示 task_id + kind + state + 进度 + 时间. 行 click 不传 onRowClick → 表格行 cursor 走默认 (不可点).

### Step 4: 跑测试, 确认 pass

```bash
cd packages/web && bun run test -- batch-tasks-table.test.tsx
```

Expected: 1 test PASS.

### Step 5: typecheck + lint

```bash
cd packages/web && bun run typecheck
cd packages/web && bun run lint
```

Expected: 0 error.

### Step 6: Commit

```bash
git add packages/web/app/[locale]/knowledge/extract/_components/batch-tasks-table.tsx packages/web/app/[locale]/knowledge/extract/_components/batch-tasks-table.test.tsx
git commit -m "feat(web): BatchTasksTable kg_batch 表格 + render 不响应测试"
```

---

## Task 9: 列表容器 TasksListClient (含弹框状态 + AppToggle + 刷新)

**Files:**
- Create: `packages/web/app/[locale]/knowledge/extract/_components/tasks-list-client.tsx`
- Test: `packages/web/app/[locale]/knowledge/extract/_components/tasks-list-client.test.tsx`

### Step 1: 写失败测试

Create `tasks-list-client.test.tsx`:

```tsx
// 列表容器测试 (2026-07-03)
// 验证 2 件事: 1) render 表格 (mock fetchExtractTasks) 2) 切 tab 触发新 query
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, waitFor } from "@testing-library/react";
import { IntlWrapper } from "@/lib/test-utils/intl-wrapper";

vi.mock("server-only", () => ({}));

const mockRows = [
  {
    task_id: "tx-001",
    kind: "kg_extract" as const,
    state: "done" as const,
    dataset: "motor",
    extractor: "llm_pydantic",
    splitter: "heading",
    success: 10,
    failed: 0,
    created_at: Math.floor(Date.now() / 1000) - 60,
    started_at: 0,
    finished_at: 0,
  },
];

const mockBatchRows = [
  {
    task_id: "batch-001",
    kind: "kg_batch" as const,
    state: "running" as const,
    success: 0,
    failed: 0,
    created_at: Math.floor(Date.now() / 1000) - 30,
    started_at: 0,
    finished_at: null,
  },
];

const mockFetch = vi.fn(async (params: { kind: string }) => {
  if (params.kind === "kg_extract") {
    return { items: mockRows, total: 1, total_success: 10, total_failed: 0, limit: 20, offset: 0 };
  }
  return { items: mockBatchRows, total: 1, total_success: 0, total_failed: 0, limit: 20, offset: 0 };
});

vi.mock("@/lib/api/knowledge", () => ({
  fetchExtractTasks: (params: { kind: string }) => mockFetch(params),
}));

vi.mock("@/i18n/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
}));

afterEach(() => vi.clearAllMocks());

describe("TasksListClient", () => {
  beforeEach(() => {
    mockFetch.mockClear();
  });

  it("render 抽取 tab 显示 kg_extract 行", async () => {
    const { default: TasksListClient } = await import("./tasks-list-client");
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const { container } = render(
      <IntlWrapper locale="zh">
        <QueryClientProvider client={qc}>
          <TasksListClient />
        </QueryClientProvider>
      </IntlWrapper>,
    );
    await waitFor(() => {
      expect(container.textContent).toContain("tx-001");
      expect(container.textContent).toContain("motor");
      expect(container.textContent).toContain("重跑");
    });
  });

  it("切到批量 tab 触发新 query, 显示 batch 行", async () => {
    const { default: TasksListClient } = await import("./tasks-list-client");
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const { container, getByTestId } = render(
      <IntlWrapper locale="zh">
        <QueryClientProvider client={qc}>
          <TasksListClient />
        </QueryClientProvider>
      </IntlWrapper>,
    );
    // 切 tab (AppToggle items 用 value 属性)
    await waitFor(() => {
      const batchTab = container.querySelector('[data-testid="tasks-tab-kg_batch"]') as HTMLElement | null;
      expect(batchTab).toBeTruthy();
    });
    const batchTab = container.querySelector('[data-testid="tasks-tab-kg_batch"]') as HTMLElement;
    fireEvent.click(batchTab);
    await waitFor(() => {
      expect(container.textContent).toContain("batch-001");
    });
    // 验证 query 至少被调了 2 次 (默认 kg_extract + 切到 kg_batch)
    expect(mockFetch.mock.calls.length).toBeGreaterThanOrEqual(2);
  });
});
```

### Step 2: 跑测试, 确认 fail

```bash
cd packages/web && bun run test -- tasks-list-client.test.tsx
```

Expected: FAIL with `Cannot find module './tasks-list-client'`.

### Step 3: 实现容器

Create `tasks-list-client.tsx`:

```tsx
"use client";
// KG 任务列表容器 (2026-07-03): PageHero + AppToggle (抽取/批量) + DataTable + 弹框状态 + 刷新
import { useState } from "react";
import { useRouter } from "@/i18n/navigation";
import { useTranslations } from "next-intl";
import { useQuery } from "@tanstack/react-query";
import { Plus, RefreshCw } from "lucide-react";
import { PageHero } from "@/components/common/navigation/app-page-hero";
import { AppToggle } from "@/components/common/input/app-toggle";
import { Button } from "@/components/ui/button";
import { fetchExtractTasks, type ExtractTaskRow } from "@/lib/api/knowledge";
import { DEFAULT_PAGE_SIZE, ONE, ZERO } from "@/const";
import ExtractTasksTable from "./extract-tasks-table";
import BatchTasksTable from "./batch-tasks-table";
import ExtractCreateDialog from "./extract-create-dialog";

type TaskKind = "kg_extract" | "kg_batch";

const TasksListClient = () => {
  const tr = useTranslations();
  const router = useRouter();
  const [activeTab, setActiveTab] = useState<TaskKind>("kg_extract");
  const [page, setPage] = useState(ZERO);
  const [dialogOpen, setDialogOpen] = useState(false);

  const tasksQuery = useQuery({
    queryKey: ["kg", "tasks", activeTab, page],
    queryFn: () =>
      fetchExtractTasks({
        kind: activeTab,
        limit: DEFAULT_PAGE_SIZE,
        offset: page * DEFAULT_PAGE_SIZE,
      }),
    staleTime: 60_000,
    refetchOnWindowFocus: false,
  });

  const handleTabChange = (value: string) => {
    setActiveTab(value as TaskKind);
    setPage(ZERO);  // 切 tab 重置 page, 避免越界
  };

  const handleRefresh = () => {
    void tasksQuery.refetch();
  };

  const handleNewExtract = () => {
    setDialogOpen(true);
  };

  // 弹框里提交后, AppDialog 内已 router.push; 这里只需 refetch 让新 task 立刻出现在列表
  const handleDialogChange = (open: boolean) => {
    setDialogOpen(open);
    if (!open) {
      void tasksQuery.refetch();
    }
  };

  const rows: ExtractTaskRow[] = tasksQuery.data?.items ?? [];
  const total = tasksQuery.data?.total ?? ZERO;
  const totalSuccess = tasksQuery.data?.total_success ?? ZERO;
  const totalFailed = tasksQuery.data?.total_failed ?? ZERO;
  const error = tasksQuery.error instanceof Error ? tasksQuery.error.message : null;

  return (
    <div className="space-y-6">
      <PageHero
        eyebrow={tr("知识图谱")}
        title={tr("任务列表")}
        description={tr("查看所有 KG 抽取与批量任务")}
        actions={
          <>
            {activeTab === "kg_extract" ? (
              <Button onClick={handleNewExtract} data-testid="new-extract-btn">
                <Plus className="mr-1 h-4 w-4" />
                {tr("新建提取")}
              </Button>
            ) : null}
            <Button variant="outline" onClick={handleRefresh} data-testid="refresh-btn">
              <RefreshCw className="mr-1 h-4 w-4" />
              {tr("刷新")}
            </Button>
          </>
        }
      />

      <AppToggle
        options={[
          { value: "kg_extract", label: tr("抽取") },
          { value: "kg_batch", label: tr("批量") },
        ]}
        value={activeTab}
        onChange={handleTabChange}
        dataTestid="tasks-tab"
      />

      {activeTab === "kg_extract" ? (
        <ExtractTasksTable
          rows={rows}
          total={total}
          totalSuccess={totalSuccess}
          totalFailed={totalFailed}
          page={page}
          pageSize={DEFAULT_PAGE_SIZE}
          loading={tasksQuery.isLoading || tasksQuery.isFetching}
          error={error}
          onPageChange={setPage}
          onRetry={handleRefresh}
        />
      ) : (
        <BatchTasksTable
          rows={rows}
          total={total}
          totalSuccess={totalSuccess}
          totalFailed={totalFailed}
          page={page}
          pageSize={DEFAULT_PAGE_SIZE}
          loading={tasksQuery.isLoading || tasksQuery.isFetching}
          error={error}
          onPageChange={setPage}
          onRetry={handleRefresh}
        />
      )}

      <ExtractCreateDialog open={dialogOpen} onOpenChange={handleDialogChange} />
    </div>
  );
};

export default TasksListClient;
```

### Step 4: 跑测试, 确认 pass

```bash
cd packages/web && bun run test -- tasks-list-client.test.tsx
```

Expected: 2 tests PASS.

### Step 5: typecheck + lint

```bash
cd packages/web && bun run typecheck
cd packages/web && bun run lint
```

Expected: 0 error.

### Step 6: Commit

```bash
git add packages/web/app/[locale]/knowledge/extract/_components/tasks-list-client.tsx packages/web/app/[locale]/knowledge/extract/_components/tasks-list-client.test.tsx
git commit -m "feat(web): TasksListClient 列表容器 (AppToggle + 弹框 + 刷新)"
```

---

## Task 10: 替换 /extract/page.tsx 为 RSC entry + 删除原启动页内容

**Files:**
- Modify: `packages/web/app/[locale]/knowledge/extract/page.tsx` (整页替换, **不是**简单加 RSC entry, 是把启动页内容删掉, 替换为列表 RSC)

### Step 1: 整页替换

打开 `packages/web/app/[locale]/knowledge/extract/page.tsx`, **完全替换**文件内容为:

```tsx
// 知识图谱任务列表页 RSC entry (2026-07-03)
// 列表 + tab 切换 + 弹框创建 + 重跑. 启动页 (原 page.tsx) 已删, 改为 _components/extract-create-dialog.tsx 弹框.
import TasksListClient from "./_components/tasks-list-client";

export default function ExtractTasksPage() {
  return <TasksListClient />;
}
```

> **重要**: 不再保留老的启动页内容。原 `ExtractPage` 组件 (FileDropzone + 3 AppSelect) **已搬到** `extract-create-dialog.tsx`, 此处彻底删除。

### Step 2: typecheck + lint

```bash
cd packages/web && bun run typecheck
cd packages/web && bun run lint
```

Expected: 0 error.

### Step 3: 跑全量前端测试, 确认无回归

```bash
cd packages/web && bun run test
```

Expected: 全绿 (pre-existing 失败不算新 fail).

### Step 4: 写列表页 RSC entry 守门测试

Create `packages/web/app/[locale]/knowledge/extract/page.test.tsx` (跟现有 [task_id]/page.test.tsx 模式一致):

```tsx
// 列表页 RSC entry 守门测试 (2026-07-03)
// 验证: page.tsx 渲染 <TasksListClient />, 不 throw
// 防止后续误改 page.tsx 漏掉 TasksListClient 引入
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, describe, expect, it, vi } from "vitest";
import { render, waitFor } from "@testing-library/react";
import { IntlWrapper } from "@/lib/test-utils/intl-wrapper";

vi.mock("server-only", () => ({}));

afterEach(() => vi.restoreAllMocks());

describe("ExtractTasksPage (RSC entry)", () => {
  it("渲染 <TasksListClient />, 不抛", async () => {
    // mock 整个 list 容器避免依赖所有子组件的 query / i18n setup
    vi.mock("./_components/tasks-list-client", () => ({
      default: () => <div data-testid="tasks-list-client-stub">stub</div>,
    }));

    const mod = await import("./page");
    const page = mod.default;
    const element = page();
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const { container } = render(
      <IntlWrapper locale="zh">
        <QueryClientProvider client={qc}>{element}</QueryClientProvider>
      </IntlWrapper>,
    );
    await waitFor(() => {
      expect(container.querySelector('[data-testid="tasks-list-client-stub"]')).toBeTruthy();
    });
  });
});
```

### Step 5: 跑测试, 确认 pass

```bash
cd packages/web && bun run test -- extract/page.test.tsx
```

Expected: 1 test PASS.

### Step 6: Commit

```bash
git add packages/web/app/[locale]/knowledge/extract/page.tsx packages/web/app/[locale]/knowledge/extract/page.test.tsx
git commit -m "refactor(web): /extract 页换为列表 RSC entry + 守门测试"
```

---

## Task 11: format 验证 + 端到端冒烟 (Playwright)

**Files:** (无新文件)

### Step 1: format

```bash
cd packages/web && bun run format
cd packages/service && uv run ruff format
```

Expected: 0 files reformatted (or 自动修; 若有修改, `git add` 改动后继续).

### Step 2: 端到端冒烟 (手动 / 走 E2E)

启动前后端:

```bash
# 终端 1
cd packages/service && uv run python main.py

# 终端 2
cd packages/web && bun run dev
```

访问 `http://localhost:3000/zh/knowledge/extract` 确认:
1. 看到列表页 (默认 kg_extract tab)
2. 点击右上角 "新建提取" → 弹框
3. 选文件 + dataset + 提交 → 跳进度页
4. 回到列表 → 看到新 task 出现在第 1 行
5. 切到 "批量" tab → 显示 kg_batch 行 (没有"重跑"按钮)
6. 回到 "抽取" tab → 切到某 done 行 → 跳预览页
7. 切到某 running 行 → 跳进度页
8. 点 "重跑" → 弹 AppConfirm → 确认 → 启新 task 跳进度页

### Step 3: 跑全量测试 + lint

```bash
cd packages/web && bun run test
cd packages/web && bun run typecheck
cd packages/web && bun run lint
cd packages/web && bun run format:check
cd packages/service && uv run pytest
cd packages/service && uv run pyright
cd packages/service && uv run ruff check
```

Expected: 全绿.

### Step 4: Commit (如 format 有自动修)

```bash
git status  # 查自动修
git add -A  # 如果有
git commit -m "style: format 收尾"
```

---

## 验证清单 (覆盖 spec)

| Spec 要求 | Task |
|---|---|
| 列出 kg_extract / kg_batch 任务 | T1, T3, T9 |
| tab 切换 (kg_extract / kg_batch) | T9 |
| "新建提取" 按钮触发弹框 | T6, T9 |
| 弹框完整复刻老表单 (FileDropzone + 3 AppSelect + 启动) | T6 |
| 行 click 路由 (按 kind+state) | T7 |
| "重跑" 动作 (kg_extract only) | T7 |
| 后端 limit + offset 分页 | T1, T3 |
| 后端聚合 total_success / total_failed | T1 |
| 鉴权 require_page("knowledge") | T1 |
| 19 个 i18n key 同步 zh/en | T5 |
| 5 个测试文件 (后端 4 case + 契约 1 + 前端 5 case) | T1, T2, T3, T6, T9 |
| 路由调整: /extract 列表, 启动页改弹框, 删 /extract/create | T10 |
| 弹框组件放 _components/ 业务私用 | T6 |
| 手动刷新按钮 (无自动轮询) | T7, T8, T9 |
| YAGNI: 不做 delete / cancel / URL sync tab / 自动轮询 / kg_batch 重跑 | (Plan 不引入) |

---

## 失败模式与修复

| 失败 | 排查 |
|---|---|
| `bun run test` 全量跑 1+ 分钟 | 只跑改过的: `bun run test -- extract` 限定 1 目录 |
| vitest mock sonner 报 unhandled rejection | 用 `vi.mock("sonner", () => ({ toast: { error: vi.fn() } }))` 显式 stub |
| `tr("...")` 报 MISSING_MESSAGE | dev 模式停 `bun run dev` 重启, 浏览器 hard refresh (见 [feedback-next-intl-dev-messages-cache](../../.claude/memory/feedback-nextintl-dev-messages-cache.md)) |
| `useRouter` import 报 Module not found | 必须 `import { useRouter } from "@/i18n/navigation"`, 不能 next/navigation (见 [feedback-next-intl-4-useRouter-createNavigation](../../.claude/memory/project-next-intl-4-useRouter-createNavigation.md)) |
| `pyright` 报 Type of parameter "current_user" unknown | 已用 `current_user: CurrentUser = Depends(require_page("knowledge"))`, 测试传 None 跳过 |
| `lint` 报 oxlint id-length | 弹框变量 `d/e/s` 是 map 回调惯例, 加 `/* oxlint-disable id-length ... */` 注释 |
| 后端测试 `test_router_extract.py` 报 `validate_dataset` ALLOWED_DATASETS 空 | 用 `_seed_datasets` fixture (autouse) 注入 `monkeypatch.setattr(datasets, "ALLOWED_DATASETS", ["motor", "plc"])` |
| AppConfirm onConfirm 同步调 + setState 顺序问题 | 用 `void handleRerunConfirm()` + setConfirmRow(null) 在 await 之前 |

---

## 执行 handoff

Plan 写完 + 提交到 `docs/superpowers/plans/2026-07-03-extract-tasks-list.md` 后, 你 (用户) 选择:
1. **subagent-driven** (推荐): 每个 task 派新 subagent, 我在 task 之间 review
2. **inline execution**: 当前 session 按顺序执行 task, 带 checkpoint review
