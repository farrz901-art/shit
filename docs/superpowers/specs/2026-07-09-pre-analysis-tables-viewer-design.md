# Pre-analysis 表格查看页设计 (2026-07-09)

> 用户报告: 详情页只能下载产物 zip 看表格, 看不到内容.
>
> 本章在前 2 个 viewer 页 (章节 + 段落) 基础上, 新增第 3 个 viewer 页 — **表格 CSV 阅读器**.
> 与章节/段落不同, 表格 CSV 可能**数千个**, 不能一次性拉取, 必须按页懒加载.
> 新增 2 个后端端点 + 2 个 BFF 代理路由 + 1 个客户端 + 1 个 helper.

---

## 1. 背景

### 1.1 现状

`PreAnalysisTaskDetail.output_files` 中 `kind: "table"` 条目文件名格式为
`tables/page-{N}-table-{M}.csv`. 详情页产物 DataTable 目前对 `kind: "table"`
只有下载按钮, 没有查看按钮. admin 必须下载 zip 解压才能看表格长啥样.

### 1.2 与章节/段落 viewer 的关键差异

| 维度 | 章节 viewer | 段落 viewer | **表格 viewer** |
|---|---|---|---|
| 产物数量 | 1 个 JSON | 1 个 CSV | **N 个 CSV (可能数千)** |
| 获取策略 | 一次性 fetch | 一次性 fetch | **按页懒加载, 只看当前页** |
| 列定义 | 编译期已知 (4 列) | 编译期已知 (8 列) | **运行时动态 (每张表不同)** |
| 前端页码 | 无分页 | 自然数 1..N | **PDF 真实頁号 (P3, P9, P12...)** |

### 1.3 现有模式 (可复用)

- BFF 路由模板: `app/api/ingest/tasks/[id]/files/[name]/route.ts` (3 行代理 + auth)
- 客户端组件模板: `admin-pre-analysis-chapters-client.tsx` (useQuery + DataTable + BackLink + PageHero + ErrorBanner)
- Detail 页 `VIEWABLE_KINDS` 模式: `admin-pre-analysis-detail-client.tsx` 已有 chapters/flagged 跳转
- i18n flat-key 模式: `t("中文 key")` zh.json identity, en.json 翻译
- 解析: `papaparse` 已装, `fetchPreAnalysisFile` 已存在

---

## 2. 目标

- **新增 2 个后端端点** (pre-analysis router): 表格页列表 + 指定页的表格数据 (含 CSV→JSON)
- **新增 2 个 BFF 代理路由**: 透传 2 个后端端点 (鉴权 + auth header 注入)
- **新增 1 个 client 组件**: pagination 按 PDF 頁号 + 每页多表格 DataTable 渲染
- **详情页改**: 「表格数」StatCard 可点击 → tables viewer; 产物表格 `kind: "table"` 行加「查看」按钮
- **i18n**: ~10 个新增 key

## 3. 非目标

- ❌ 不改表格 CSV 文件的原始产物 (不合并, 不转格式)
- ❌ 不做 llm 摘要表格
- ❌ 不做前端批量下载 (已有 zip 下载)
- ❌ 不做跨页表格合并提示 (已有 details page warning banner)
- ❌ 不做全部展开/折叠 (表格视图中每个表格独立, 无需此功能)

---

## 4. 后端 API 变更

后端 `packages/service/src/ingest/pre_analysis/router.py` 新增 2 个只读 GET 端点.

### 4.1 表格页列表

```http
GET /api/pre-analysis/tasks/{task_id}/tables/pages
Response 200:
{
  "pages": [3, 9, 12, 15, 21, 31, 39, 45, 46, 49],  // 所有有表格的 PDF 页号 (升序)
  "total": 12                                          // 总表格数
}
```

实现: 从 `PreAnalysisTask.output_files_json` 中筛选 `kind == "table"`, 提取
`page-(\d+)` 组号, 去重排序. 全程读 DB JSON 字段, 不读 ObjectStore.

### 4.2 指定页的表格数据

```http
GET /api/pre-analysis/tasks/{task_id}/tables/page/{page_num}
Response 200:
{
  "page": 9,
  "tables": [
    {
      "table_index": 1,
      "filename": "tables/page-9-table-1.csv",
      "size_bytes": 512,
      "columns": ["机座号", "极数", "额定功率 kW", "额定电压 V", "额定电流 A", "效率 %", "转速 rpm", "机座长度"],
      "rows": [
        { "机座号": "80M", "极数": "2", "额定功率 kW": "0.75", ... }
      ]
    }
  ]
}
```

实现: 从 `output_files_json` 筛出 `page == page_num` 的条目, 对每个条目
从 ObjectStore 读 CSV 文本, 拆 header + body, 拼成 JSON. 不要求 csv
解析库 (python stdlib `csv.DictReader` 即可).

错误: 无此页 → `{"detail": "page not found"}` 404.

### 4.3 鉴权

两端点都复用 `Depends(auth.require_super_admin)`.

---

## 5. BFF 路由设计

### 5.1 文件结构

```
packages/web/app/api/pre-analysis/tasks/[id]/tables/
└── pages/route.ts                       # 新: GET → 后端 /tables/pages
└── page/[pageNum]/route.ts             # 新: GET → 后端 /tables/page/{page}
```

### 5.2 pages BFF

```ts
// packages/web/app/api/pre-analysis/tasks/[id]/tables/pages/route.ts
import { type NextRequest } from "next/server";
import { apiProxy, bffProxyResponse } from "@/lib/api/config";
import { serverAuthHeaders } from "@/lib/api/auth.server";

export const dynamic = "force-dynamic";

export const GET = async (
  _req: NextRequest,
  ctx: { params: Promise<{ id: string }> },
) => {
  const { id } = await ctx.params;
  const resp = await apiProxy(
    `/api/pre-analysis/tasks/${encodeURIComponent(id)}/tables/pages`,
    { cache: "no-store", headers: await serverAuthHeaders() },
  );
  return bffProxyResponse(resp);
};
```

### 5.3 page/{pageNum} BFF

```ts
// packages/web/app/api/pre-analysis/tasks/[id]/tables/page/[pageNum]/route.ts
import { type NextRequest } from "next/server";
import { apiProxy, bffProxyResponse } from "@/lib/api/config";
import { serverAuthHeaders } from "@/lib/api/auth.server";

export const dynamic = "force-dynamic";

export const GET = async (
  _req: NextRequest,
  ctx: { params: Promise<{ id: string; pageNum: string }> },
) => {
  const { id, pageNum } = await ctx.params;
  const resp = await apiProxy(
    `/api/pre-analysis/tasks/${encodeURIComponent(id)}/tables/page/${encodeURIComponent(pageNum)}`,
    { cache: "no-store", headers: await serverAuthHeaders() },
  );
  return bffProxyResponse(resp);
};
```

两个 BFF 都只做：读 cookie → 注入 `x-user-token` → 透传上游 status + body + content-type.
不做数据转换, 不做缓存. 跟 `app/api/ingest/tasks/[id]/files/[name]/route.ts` 模式一致.

---

## 6. 前端 API 类型和 Helper

### 6.1 新类型 (`lib/api/pre-analysis.ts`)

```ts
/** 表格页列表响应 */
export interface TablePagesResponse {
  pages: number[];
  total: number;
}

/** 单张表格的解析数据 (含 CSV header + rows) */
export interface TablePageItem {
  table_index: number;
  filename: string;
  size_bytes: number;
  columns: string[];
  rows: Record<string, string>[];
}

/** 指定页的表格数据响应 */
export interface TablePageResponse {
  page: number;
  tables: TablePageItem[];
}
```

### 6.2 新 Helper

```ts
/**
 * 从表格 CSV 文件名提取页号和表索引.
 * "tables/page-9-table-1.csv" → { pageNumber: 9, tableIndex: 1 }
 * @param filename 产物文件名 (e.g. "tables/page-9-table-1.csv")
 * @returns 解析结果
 * @throws filename 格式不符时抛错
 * @shared
 */
export const parseTableFilename = (
  filename: string,
): { pageNumber: number; tableIndex: number } => {
  const match = /tables\/page-(\d+)-table-(\d+)\.csv$/.exec(filename);
  if (!match) throw new Error(`Invalid table filename: ${filename}`);
  return { pageNumber: Number(match[1]), tableIndex: Number(match[2]) };
};

/**
 * 查指定预分析任务的表格页列表 (用于渲染 pagination).
 * BFF: GET /api/pre-analysis/tasks/{taskId}/tables/pages.
 * @param taskId 任务 ID
 * @returns {pages: number[], total: number}
 * @throws 4xx/5xx 时 handleError 抛
 * @client-bff
 */
export const getPreAnalysisTablePages = async (
  taskId: string,
): Promise<TablePagesResponse>;

/**
 * 查指定页的表格数据 (含 CSV → JSON 解析).
 * BFF: GET /api/pre-analysis/tasks/{taskId}/tables/page/{pageNum}.
 * @param taskId 任务 ID
 * @param pageNum PDF 頁号
 * @returns {page: number, tables: TablePageItem[]}
 * @throws 4xx/5xx 时 handleError 抛
 * @client-bff
 */
export const getPreAnalysisTablePage = async (
  taskId: string,
  pageNum: number,
): Promise<TablePageResponse>;
```

Helper 实现直接调 `apiFetch` (走 BFF 同源):

```ts
// 注意: apiFetch 在浏览器端自动使用 location.origin + path 拼 URL,
// 不走 API_BASE (见 config.ts:resolveUrl).
export const getPreAnalysisTablePages = async (
  taskId: string,
): Promise<TablePagesResponse> =>
  apiFetch<TablePagesResponse>(
    `/api/pre-analysis/tasks/${encodeURIComponent(taskId)}/tables/pages`,
    { credentials: "include" },
  );

export const getPreAnalysisTablePage = async (
  taskId: string,
  pageNum: number,
): Promise<TablePageResponse> =>
  apiFetch<TablePageResponse>(
    `/api/pre-analysis/tasks/${encodeURIComponent(taskId)}/tables/page/${pageNum}`,
    { credentials: "include" },
  );
```

---

## 7. 客户端组件设计

### 7.1 文件

```
packages/web/app/[locale]/admin/pre-analysis/[task_id]/
├── tables/
│   ├── page.tsx                                    # RSC entry (chapters/page.tsx 模板)
│   └── _components/
│       └── admin-pre-analysis-tables-client.tsx     # 新
```

### 7.2 RSC entry

跟 chapters/page.tsx 完全同 shape:

```tsx
import { GuardPage } from "@/components/auth/guard-page";
import { AdminPreAnalysisTablesClient } from "./_components/admin-pre-analysis-tables-client";

export default async function AdminPreAnalysisTablesPage({
  params,
}: {
  params: Promise<{ task_id: string }>;
}) {
  const { task_id } = await params;
  return (
    <GuardPage pageKey="admin">
      <AdminPreAnalysisTablesClient params={{ task_id }} />
    </GuardPage>
  );
}
```

### 7.3 Client 组件结构

```
AdminPreAnalysisTablesClient
├── useQuery("pre-analysis-tables-pages", taskId) → { pages, total }
├── useSearchParams → ?page=N (回退到 pages[0])
├── Pagination bar (上一页 / P3 P9 P12... / 下一页)
│   └── 页号为 PDF 真实页号, 不是自然数索引
│   └── 首/末页固定, 中间多时放 ... 省略
├── useQuery(["pre-analysis-tables-page", taskId, currentPage])
│   → { page, tables: TablePageItem[] }
└── Tables render area
    ├── table #1: <DataTable<Record<string, string>>>
    │   ├── id="table-1" (anchor)
    │   ├── 标题: "Page 9 — Table 1"
    │   └── 动态列 = tableItem.columns.map(col => ({ accessorKey: col, header: col }))
    ├── table #2: ...
    └── scrollIntoView if hash matches
```

### 7.4 Pagination 设计

每一页的标签是 PDF 真实页号:

```
[< Prev]  P3  P9  P12  P15  P21  P31  P39  P45  P46  P49  [Next >]
```

逻辑:

- 当前页高亮 (primary variant 或 underline)
- 页数较多时 (>= 8 页) 中间插入 `...`:
  - 固定显示: 首 3 页 + 末 2 页 + 当前页附近 ±1
  - e.g. pages = [3,9,12,15,21,31,39,45,46,49,52,58], 当前 31:
    - `P3  P9  P12  ...  P21  P31  P39  ...  P46  P49  P52  P58`
- `< Prev`: 取当前页前一个 (按 pages 数组顺序), 最小时 disabled
- `Next >`: 取当前页后一个, 最大时 disabled
- 点击页号: `router.push(\`/admin/pre-analysis/${taskId}/tables?page=${pageNum}\`)`
- URL `?page=999` (不在 pages 内): 自动回退到 pages[0]

Pagination 用 shadcn Button 组手工拼 (不需要复杂 Pagination 组件, 逻辑集中在这个组件内):

```tsx
const pages = data?.pages ?? [];
const currentIdx = pages.indexOf(currentPage);
const prevPage = currentIdx > 0 ? pages[currentIdx - 1] : null;
const nextPage = currentIdx < pages.length - 1 ? pages[currentIdx + 1] : null;
```

### 7.5 表格渲染

```tsx
// 动态列构建
const buildDynamicColumns = (columns: string[]): ColumnDef<Record<string, string>>[] =>
  columns.map((col) => ({
    accessorKey: col,
    header: col,
  }));

// 渲染区
{tablesData?.tables.map((table) => (
  <div key={table.table_index} id={`table-${table.table_index}`} className="space-y-2">
    <h3 className="text-sm font-medium text-muted-foreground">
      {translate("表格 {index}").replace("{index}", String(table.table_index))}
      <span className="ml-2 text-xs">
        ({table.filename} · {table.rows.length} {translate("行")})
      </span>
    </h3>
    <DataTable<Record<string, string>>
      columns={buildDynamicColumns(table.columns)}
      dataSource={table.rows}
      rowKey={(row, idx) => `${table.table_index}-${idx}`}
      pagination={undefined}   // 表格本身不分页 (单表通常 < 100 行)
      maxHeight="400px"        // 大表格滚动
    />
  </div>
))}
```

### 7.6 Hash 锚点滚动

```tsx
useEffect(() => {
  const hash = window.location.hash;
  if (hash && tablesData) {
    const el = document.getElementById(hash.slice(1));
    el?.scrollIntoView({ behavior: "smooth", block: "start" });
  }
}, [tablesData]); // 数据加载后 + hash 变化时触发
```

从详情页点「查看」时 URL 带 `#table-{table_index}`, 组件加载后自动滚动到该表.

---

## 8. 详情页改动

### 8.1 `admin-pre-analysis-detail-client.tsx`

```ts
// VIEWABLE_KINDS 加入 "table"
const VIEWABLE_KINDS = ["chapter_structure", "flagged_paragraphs", "table"] as const;
```

```ts
// viewHrefForKind 拓展 — 第三个参数 filename 可选
const viewHrefForKind = (kind: ViewableKind, taskId: string, filename?: string): string => {
  if (kind === "table" && filename) {
    const { pageNumber, tableIndex } = parseTableFilename(filename);
    return `/admin/pre-analysis/${taskId}/tables?page=${pageNumber}#table-${tableIndex}`;
  }
  if (kind === "chapter_structure") return `/admin/pre-analysis/${taskId}/chapters`;
  return `/admin/pre-analysis/${taskId}/flagged`;
};
```

actions 列 cell 内传 `file.filename`:

```tsx
const viewable = isViewableKind(file.kind)
  ? viewHrefForKind(file.kind, params.task_id, file.kind === "table" ? file.filename : undefined)
  : null;
```

**StatCard 表格数** 加 onClick (和章节数/段落数一样):

```tsx
<StatCard
  accent="clay"
  label={translate("表格数")}
  hint={translate("跨页候选: {N}", { N: data.summary.cross_page_candidates })}
  value={data.summary.total_tables}
  onClick={data.summary.total_tables > 0
    ? () => router.push(`/admin/pre-analysis/${params.task_id}/tables`)
    : undefined}
  testId="stat-card-tables"
/>
```

---

## 9. i18n

新增 ~10 个 key:

### zh.json

```jsonc
"表格查看": "表格查看",
"PDF 页码": "PDF 页码",
"共 {N} 页含表格": "共 {N} 页含表格",
"第 {page} 页 — 共 {count} 个表格": "第 {page} 页 — 共 {count} 个表格",
"无表格数据": "无表格数据",
"该任务没有提取到表格": "该任务没有提取到表格",
"表格 {index}": "表格 {index}",
"上一页": "上一页",
"下一页": "下一页",
"总表格数": "总表格数",
"行": "行",
"表格数": "表格数",
```

### en.json

```jsonc
"表格查看": "Table Viewer",
"PDF 页码": "PDF Page",
"共 {N} 页含表格": "{N} pages with tables",
"第 {page} 页 — 共 {count} 个表格": "Page {page} — {count} table(s)",
"无表格数据": "No table data",
"该任务没有提取到表格": "No tables found in this task",
"表格 {index}": "Table {index}",
"上一页": "Previous",
"下一页": "Next",
"总表格数": "Total Tables",
"行": "rows",
"表格数": "Tables",
```

---

## 10. 错误处理

| 场景 | UI 表现 |
|---|---|
| pages 接口 4xx/5xx | `<ErrorBanner variant="destructive">` (全页级别) |
| pages 返空数组 | `<DataEmpty title="无表格数据" description="该任务没有提取到表格" />` |
| page 接口 404 (page not found) | 自动回退到 pages[0] |
| page 接口 5xx | `<ErrorBanner>` 在当前 tables 区域显示, pagination 条不受影响 |
| URL `?page=999` 不存在 | currentPage 不在 pages 中 → 自动用 pages[0] |
| 单张表 rows 为空 | 该表显示 `<DataEmpty>` 仅带标题 (空表头, 无数据行) |
| 无 hash anchor 对应 | 不滚动, 从顶部开始渲染 |

---

## 11. 测试

### 11.1 Helper 单测 (`lib/api/pre-analysis.test.ts`)

1. `parseTableFilename`: `tables/page-9-table-1.csv` → `{9, 1}`; 非法格式抛错
2. `getPreAnalysisTablePages`: mock fetch 返 `{pages: [3,9,12], total: 3}`
3. `getPreAnalysisTablePage`: mock fetch 返完整的 TablePageResponse

### 11.2 客户端单测 (`admin-pre-analysis-tables-client.test.tsx`)

1. ✅ mock pages 返 `[3, 9, 12]` → 断言 pagination 渲染 P3 P9 P12 (3 个按钮)
2. ✅ 当前页 P9 高亮 (primary variant class 或 aria-current)
3. ✅ 点 P12 → router.push 被调用, 参数含 `?page=12`
4. ✅ mock page 数据 (2 个 table, 各 5 行 8 列) → 断言 2 个 DataTable 渲染
5. ✅ 空 pages → `<DataEmpty>` 渲染
6. ✅ pages 接口 error → `<ErrorBanner>` 渲染
7. ✅ page 接口 error → `<ErrorBanner>` 渲染, pagination 条仍在
8. ✅ URL `?page=999` (pages 返 [3,9,12]) → 自动 fallback 到页 3

### 11.3 详情页回归 (`admin-pre-analysis-detail-client.test.tsx`)

- 新增断言: `kind: "table"` 行有 `[data-testid="view-file-tables/page-9-table-1.csv"]` 按钮
- 新增断言: StatCard 表格数有 `onClick` (total_tables > 0 时)

---

## 12. 文件树总览

```
packages/
├── service/src/ingest/pre_analysis/
│   └── router.py                          # [改] +2 端点: /tables/pages + /tables/page/{page}
├── web/
│   ├── app/api/pre-analysis/tasks/[id]/tables/
│   │   ├── pages/route.ts                # [新] BFF pages 代理
│   │   └── page/[pageNum]/route.ts       # [新] BFF page 代理
│   ├── app/[locale]/admin/pre-analysis/[task_id]/
│   │   ├── tables/
│   │   │   ├── page.tsx                  # [新] RSC entry
│   │   │   └── _components/
│   │   │       └── admin-pre-analysis-tables-client.tsx  # [新]
│   │   └── _components/
│   │       └── admin-pre-analysis-detail-client.tsx      # [改]
│   ├── lib/api/
│   │   ├── pre-analysis.ts               # [改] +类型 + 2 helper
│   │   └── pre-analysis.test.ts          # [改] helper 单测
│   └── messages/
│       ├── zh.json                       # [改] +~10 key
│       └── en.json                       # [改] +~10 key
```

---

## 13. 不要做的事

1. ❌ 不改 `fetchPreAnalysisFile` / `downloadPreAnalysisFile` 签名 (仍走 `files/{filename}` BFF)
2. ❌ 不引入新 npm 库 (papaparse 已装)
3. ❌ 不抽 AppTablesPagination 组件 (仅 1 处使用, 不满足 ≥2 次封装门槛)
4. ❌ 不合并跨页表格 (后端已做合并提示, 前端不做)
5. ❌ 不修改后端 CSV 产物存储格式 (后端 `/tables/page/{page}` 是读时转换, 不改写)

---

## 14. 交付阶段 (3 phase, 各跑 lint + typecheck + 单测)

| Phase | 内容 | 验收 |
|---|---|---|
| **P1** — 后端 2 端点 | `router.py` + tests (pytest) | `curl` 验 pages / page 端点 |
| **P2** — BFF + helper + types | 2 个 BFF route + `pre-analysis.ts` helper + 单测 | `bun run test lib/api/pre-analysis.test.ts` |
| **P3** — Tables viewer client + detail 页改 | `admin-pre-analysis-tables-client.tsx` + 测试 + i18n + detail 页改 | `bun run test` 全量 + 浏览器手测 |

---

## 15. 实施记录 (2026-07-09 Task 5.1 端到端验证)

### 15.1 提交清单 (11 commit, 从 spec 设计 → 客户端 + 详情页改造)

按阶段列出:

**Phase 1 — 后端纯函数 + 2 端点 (3 commit)**
- `8601ba87` feat(pre-analysis): 表格视图纯函数 (`parse_table_filename` + `extract_table_pages` + `build_table_page_response`)
- `a17ac8ae` feat(pre-analysis): GET `/tables/pages` 端点 + 测试
- `f97d1ba5` feat(pre-analysis): GET `/tables/page/{page_num}` 端点 + 测试

**Phase 2 — BFF + 前端 helpers (4 commit)**
- `86125814` feat(web): pre-analysis tables pages BFF route
- `4278c02b` feat(web): pre-analysis table page BFF route
- `ee26e0aa` feat(web): pre-analysis table types + `parseTableFilename` + 2 helpers + 单测
- `04168dff` feat(web): pre-analysis tables viewer 客户端组件 + 单测

**Phase 3 — RSC entry + i18n + 详情页改造 (3 commit)**
- `82e063cb` feat(web): pre-analysis tables viewer RSC entry
- `810431a0` feat(i18n): pre-analysis tables viewer 加 5 个新 i18n key
- `0d068916` feat(web): pre-analysis detail — table 行 查看 按钮 + 表格数 StatCard 可点击

**配合前置基础设施** (本 spec 之外, 详情页跳转 + 后台章节/段落 viewer)
- `de358cd4` docs(plan): pre-analysis 表格 viewer 实施 plan
- (前置: `b40b7165` 章节目录 viewer + `52e282cf` 段落提取 viewer + `7f320dd8` 详情页 actions 列查看按钮 + `92b69958` StatCard 可点击跳子路由 — 这些由前一个 spec `2026-07-09-pre-analysis-viewer-pages` 完成)

### 15.2 验证结果 (Task 5.1, 2026-07-09)

| Step | 命令 | 结果 |
|---|---|---|
| 1. 后端代码质量 | `uv run ruff format && uv run ruff check && uv run pyright` | 515 文件 unchanged / All checks passed / 0 errors |
| 2. 后端 pre_analysis 测试 | `uv run pytest tests/ingest/pre_analysis/` | **288 passed**, 2 skipped (slow/e2e markers 期望), 0 fail |
| 3. 前端 lint + typecheck | `bun run format && bun run lint:fix && bun run typecheck` | 757 文件 unchanged / oxlint 0 退出 / tsc 0 error |
| 4. 前端单文件测试 | `bun run test -- lib/api/pre-analysis.test.ts` + `bun run test -- "app/[locale]/admin/pre-analysis"` | **24 passed** (lib/api) + **49 passed** (admin/pre-analysis 8 文件) |
| 5. 前端全量测试 | `bun run test` | **1319 passed**, 1 skipped, 7 todo (pre-existing), 0 fail |
| 6. API 契约测试 | `uv run pytest tests/test_api_contract.py -m slow` | **4 passed** (修了 1 个新 fail, 见下文) |
| 7. 手工 E2E | (dev 环境) | **Deferred** — 自动验证 harness 无法启 dev 服务器, 留待用户手测 |

### 15.3 Step 6 出现的新 fail + 修复

`test_no_dead_routes_in_backend` 失败, 报告 2 个"后端有但前端未声明"的路由:
- `/api/pre-analysis/tasks/{task_id}/tables/page/{page_num}`
- `/api/pre-analysis/tasks/{task_id}/tables/pages`

**根因**: 这 2 个新后端端点被 BFF (`app/api/pre-analysis/tasks/[id]/tables/{pages,page/[pageNum]}/route.ts`) 透传, 前端 `getPreAnalysisTablePages` / `getPreAnalysisTablePage` 走 `apiFetch` (BFF), 不是直接 fetch FastAPI. 契约测试误判它们是"孤儿路由".

**修法**: `tests/test_api_contract.py` 的 `KNOWN_DEAD` 集合按现有 pre-analysis 模式追加这 2 条 + 注释. 跟 `/api/pre-analysis/tasks` 等老 7 条同组 (都在 KNOWN_DEAD 内, 标"前端走 BFF").

修改后契约测试 4/4 全绿.

### 15.4 新增测试统计

| 模块 | 数量 | 测试文件 |
|---|---|---|
| 后端 `table_view.py` 纯函数 | 8 | `tests/ingest/pre_analysis/test_table_view.py` |
| 后端列表 / 单页接口 | 4 + 4 = 8 (含 endpoint integration) | `tests/ingest/pre_analysis/test_router.py` 内新增 (复用既有 fixture) |
| 前端 `parseTableFilename` + 2 helpers | 8 | `packages/web/lib/api/pre-analysis.test.ts` 内新增段 |
| 前端 tables client 组件 | 6 | `app/[locale]/admin/pre-analysis/[task_id]/tables/_components/admin-pre-analysis-tables-client.test.tsx` |
| 前端 detail 详情页跳子路由 | (含在前一个 spec `2026-07-09-pre-analysis-viewer-pages`) — 本次额外 + 2 (StatCard 可点击 + table 行查看按钮) | `app/[locale]/admin/pre-analysis/[task_id]/page.test.tsx` |

合计本 spec 新增测试 ~32 条 (后端 16 + 前端 ~16-17).

### 15.5 Pre-existing failures (不算 regression)

| 来源 | 数量 |
|---|---|
| 后端 (KNOWN_ISSUES.md) | 22 fail + 38 errors (跟本 spec 无关) |
| 前端 baseline | 8 fail (跟本 spec 无关) — 本次 1319 pass 已远高于基线, 无任何新 fail |

### 15.6 结论

- Phase 1-3 全部 commit 完成, 11 commit 全部 pre-commit 钩子通过 (lint-staged + tsc + vitest)
- 端到端验证 6/6 自动化 step 全绿 (Step 7 手工 E2E deferred, 见上)
- 契约测试中 1 个新 fail 已修 (KNOWN_DEAD 扩展, 注释明确原因)
- 无新代码 fail

**Status: DONE**
