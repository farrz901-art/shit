# Web 数据获取方案 Audit 报告

**审计范围**: `packages/web` (Next.js 15 App Router + next-intl 4.x)
**审计时间**: 2026-06-15
**审计方法**: 全代码库 grep + 逐文件阅读入口实现 + 调用方统计

---

## 0. 摘要 (TL;DR)

● 项目实际用了 **9 种**数据获取/状态管理机制 (用户问的 8 种 + 1 个隐藏的 React Context).

● **绝对主导**: `apiFetch` (~60+ 调用点) + `apiProxy` (17 调用点) 这两个底层封装, 其余 7 种都是建立在这两个之上或者正交补充.

● **真正"分这么多层"的根因不是历史遗留, 而是 3 个**:
  1. **RSC ↔ Client 边界** (cookie vs localStorage 鉴权, 不能用 useQuery)
  2. **JSON ↔ Raw Response** (业务 API 解析 vs BFF/外部服务透传)
  3. **One-shot ↔ Polling** (纯 RSC 一次性 vs RQ 轮询)

● **真有技术债**: `clientFetch` (`lib/api/auth.ts:33`) 是 0 业务调用的死代码, `lib/store/app-data.tsx` 是 0 调用方的预留空壳. 这两处按 `[[feedback-no-shim-no-minimal-changes]]` 应当删除.

---

## 1. `apiFetch` — 业务 API 统一封装 (绝对主导)

**入口**: `packages/web/lib/api/config.ts:44-62`

**签名**:
```ts
export async function apiFetch<T = unknown>(path: string, init: ApiFetchInit = {}): Promise<T>
```

**它做了什么**:
- 拼 `API_BASE` (兜底 `http://127.0.0.1:8000`, 强制 IPv4 解 undici 双栈 ECONNREFUSED)
- 自动注入鉴权头 (browser→localStorage, server→cookies)
- `body: object` → 自动 `JSON.stringify` + `Content-Type: application/json`
- `body: FormData/Blob/ArrayBuffer/string` → 原样
- 4xx/5xx → 抛 `ApiError(status, detail)`, 优先读 `body.detail`
- 底层 fetch 失败 → 抛 `NetworkError`

**调用规模**: ~60+ 处, 分布在 4 个角色:
- 业务 API 层 (`lib/api/{approvals,chat,evaluate,health,ingest,knowledge,system}.ts`)
- Server Action (`app/[locale]/_actions/*.ts`, 14 个 action)
- RSC 直接读 (`app/[locale]/layout.tsx:60` 等 8 处)
- 客户端 `useQuery` 的 `queryFn`

**典型调用 1 (RSC 拿用户菜单)** — `app/[locale]/layout.tsx:60`:
```ts
const user = await apiFetch<UserMenuUser>("/api/account/me");
```

**典型调用 2 (客户端 useQuery)** — `components/knowledge/DatasetSwitcher.tsx:16`:
```ts
useQuery<DatasetRow[]>({
  queryFn: () => apiFetch<DatasetRow[]>("/api/kg/datasets"),
  queryKey: qKeys.kg.datasets(),
})
```

**BFF 路由白名单** (`config.ts:78-86`): 7 条 RegExp 决定同源 vs 直连, 修了之前"全 `/api/*` 同源"导致 `/api/kg/*` 等 14 个路径 404 的 bug.

---

## 2. `apiProxy` — 透传 Response (BFF + 外部服务)

**入口**: `packages/web/lib/api/config.ts:194-205`

**签名**:
```ts
export async function apiProxy(
  path: string,
  init: ApiFetchInit & { base?: string } = {}
): Promise<Response>
```

**跟 `apiFetch` 的本质区别**:
- **不 throw**: 4xx/5xx 仍返 `Response`, 由调用方 (BFF route) 决定如何透传
- **不 parse JSON**: 返 raw Response, BFF 用 `new NextResponse(await resp.text(), ...)` 透传
- **不强制 Content-Type**: BFF 转发 multipart, boundary 由上游定
- **多一个 `base` 参数**: 走外部服务 (Dify/OpenAI) 时拼不同 host, 跳过本项目鉴权

**调用分布** (17 处):
- 13 个 BFF route (`app/api/{approvals,evaluate,health,ingest,ingest,knowledge,...}/route.ts`)
- 4 个外部服务: `lib/dify-datasets.ts:45` / `lib/chat/dify.ts:27` / `lib/chat/openai.ts:21` / `lib/api/ingest.ts:68` (blob 下载)

**典型 BFF 调用** — `app/api/approvals/[id]/approve/route.ts:10-20`:
```ts
export async function POST(_req: NextRequest, { params }) {
  const { id } = await params;
  const resp = await apiProxy(`/api/approvals/${id}/approve`, {
    cache: "no-store", method: "POST",
  });
  return new NextResponse(await resp.text(), {
    headers: { "content-type": resp.headers.get("content-type") ?? "application/json" },
    status: resp.status,
  });
}
```

**典型外部服务调用** — `lib/dify-datasets.ts:45`:
```ts
return apiProxy(path, { base: DIFY_BASE_URL, headers: { Authorization: `Bearer ${apiKey}` } });
```

**为什么 BFF 必须有这一层**: 见 `[[feedback-bff-must-propagate-502-not-silently-zero]]`, 后端 5xx 时 `apiFetch` 会抛 `ApiError`, BFF 必须用 `apiProxy` 拿 raw Response 才能透传 `status: 502` 给浏览器; 之前用 `?? 0` 兜底让调试极费时.

---

## 3. `rscGet` — 纯 RSC 一次性数据获取

**入口**: `packages/web/lib/api/rsc-queries.ts:71-78`

**签名**:
```ts
export const rscGet = async <T>(path: string): Promise<T>
```

**它做了什么** (本质是 `apiFetch` + Dify 解包):
```ts
export const rscGet = async <T>(path: string): Promise<T> => {
  const raw = await apiFetch<unknown>(path);
  // 仅当 data 字段值是数组时拆包装 (Dify 风格 { data: T[], has_more, total, limit, page })
  if (typeof raw === "object" && raw !== null && Array.isArray((raw as { data?: unknown }).data)) {
    return (raw as { data: T }).data;
  }
  return raw as T;
};
```

**调用规模**: 8 处, 全部在 `app/[locale]/knowledge/*` + `app/[locale]/evaluate/*`.

**典型模式** — `app/[locale]/knowledge/datasets/page.tsx:12`:
```ts
// RSC
export default async function Page() {
  const datasetsPromise = rscGet<DatasetRow[]>("/api/kg/datasets");
  return <DatasetsList datasetsPromise={datasetsPromise} />; // 传 Promise 给 client
}
```

**为什么不直接用 `apiFetch`**: 调用方拿的是 `DatasetRow[]` 不是 `{ data: DatasetRow[], has_more, ... }`. 后端 list endpoint 统一 Dify 包装 (见 `[[feedback-dify-api-returns-data-wrapper]]`), `rscGet` 把拆包装前置, 调用方零感知.

**为什么不直接 RSC 调 `useQuery`**: useQuery 是 client hook, RSC 里调会跟客户端 hook 冲突 (`config.ts:14-15` 注释). 改用 `rscGet` (一次返回) 或 `prefetchQuery` (写 RQ cache) 两条路径.

---

## 4. `prefetchQuery` + `getRscQueryClient` + `HydrationBoundary` — RSC 预取 + RQ 接管

**入口**: `packages/web/lib/api/rsc-queries.ts:15-26` (工厂) + `:41-56` (预取)

**签名**:
```ts
export const getRscQueryClient = cache(
  async (): Promise<QueryClient> => new QueryClient({...})
);
export async function prefetchQuery<T>(
  qc: QueryClient, queryKey: readonly unknown[], path: string
): Promise<void>;
```

**它做了什么**:
- `cache()` 包工厂 → per-request 单例 QueryClient (不污染下个 request)
- `staleTime: Infinity` → RSC 预取视为新鲜, 客户端 useQuery 不会立即重拉
- `gcTime: 0` → SSR 端不缓存
- `retry: false` + 内部 `try/catch` + `console.warn` → 失败不挂整页, 让客户端 `useQuery` 重拉 + 全局 toast
- 用 `fetchQuery` 不用 `prefetchQuery` (后者 `.catch(noop)` 吞错)

**调用规模**: 3 处 (`/health` + `/output` + `/output/[task_id]`), 都是需要客户端轮询的页面.

**典型模式** — `app/[locale]/output/page.tsx:20-23`:
```ts
const qc = await getRscQueryClient();
await prefetchQuery(qc, qKeys.output.list(), "/api/ingest/tasks");
return (
  <HydrationBoundary state={dehydrate(qc)}>
    <OutputListClient />
  </HydrationBoundary>
);
```

**客户端接管** — `app/[locale]/output/_components/OutputListClient.tsx:60`:
```ts
const { data } = useQuery<IngestTask[]>({
  queryKey: qKeys.output.list(),       // ← 同 key 接管 RSC 预取
  queryFn: () => ingestApi.fetchTasks(),
  refetchInterval: 5_000,              // ← 轮询
});
```

**为什么要这一层**: 单纯 RSC 一次拿完就 stale, 但 `/health` `/output` 页面要每 2-10s 自动刷新. RSC 不能"再 render"自己, 必须由客户端 RQ 接管. RSC 预取解决了"首屏不闪 loading"+"首屏数据被 SEO/无 JS 看到".

---

## 5. `useQuery` / `useMutation` — 客户端 RQ

**入口**: `@tanstack/react-query` v5.x

**QueryClient 注入点 (6 个)**:
- 3 个 B 档 layout 共享: `app/[locale]/{health,output,submissions}/layout.tsx:11`
- 3 个自包组件 (不依赖 layout): `components/knowledge/{health-dot,DatasetSwitcher,DomainSwitcher}.tsx`

**调用规模**: 9 个组件, ~14 处.

**典型轮询** — `components/knowledge/health-dot.tsx:18`:
```ts
useQuery({ queryKey: qKeys.health.system(), queryFn: () => apiFetch(...), refetchInterval: 5_000 });
```

**典型 mutation** — `app/[locale]/submissions/_components/ApprovalRow.tsx:49-64`:
```ts
const approveMut = useMutation({
  mutationFn: () => apiFetch(`/api/approvals/${id}/approve`, { method: "POST" }),
  onSuccess: () => qc.invalidateQueries({ queryKey: qKeys.approvals.list() }),
});
```

**全局错误兜底** — `lib/api/query-client.ts:41-46`:
```ts
queryCache: new QueryCache({
  onError: (error) => toast.error(errorMessage(error)), // 全局弹 toast
}),
```

**为什么不只写"全局 toast"就够**: useMutation 需要 `onSuccess` 做 cache invalidation, 单纯 fetch+toast 缺了"成功后自动刷新相关列表"的能力. RQ 的 mutation/invalidation 协议是核心价值.

---

## 6. Server Action (`"use server"`)

**入口目录**: `app/[locale]/_actions/` (4 个文件, 14 个 action)

| 文件 | Action 数 | 用途 |
|---|---|---|
| `_actions/account.ts` | 7 | 账号系统 (login, forgot/reset, invite, logout) |
| `_actions/knowledge.ts` | 4 | 知识库操作 (createQA/Triples/commit/optimize) — 全走 `approvalsApi.submit` 审核流 |
| `_actions/evaluate.ts` | 2 | 评估批 (createRun, deleteRun) |
| `_actions/output.ts` | 1 | 取消 ingest 任务 |

**统一签名** — `app/[locale]/_actions/evaluate.ts:11`:
```ts
export type ActionResult<T> = { ok: true; data: T } | { ok: false; error: string };
```

**典型实现** — `app/[locale]/_actions/evaluate.ts:33-44`:
```ts
export async function createRun(input: CreateRunInput): Promise<ActionResult<CreateRunResult>> {
  try {
    const data = await apiFetch<CreateRunResult>("/api/evaluate/runs", {
      body: input, method: "POST",
    });
    revalidatePath("/[locale]/evaluate");  // ← 让 RSC 重预取
    return { data, ok: true };
  } catch (error) {
    return { error: errMsg(error), ok: false };  // ← 永不抛
  }
}
```

**关键约定**:
- **永不 throw**: 错误走 `ActionResult.error`, 客户端 `useActionState` 直接渲染
- **必 `revalidatePath`**: 成功后让 RSC 重预取, 客户端 RQ 用同 queryKey 接管
- **审核流 (`_actions/knowledge.ts`)**: `createQA/createTriples/commitDocuments/optimizeAnswer` **不**直写 Dify/Neo4j, 全走 `approvalsApi.submit(kind, payload)` → 后端 executor 异步执行, 做到可观测/可回滚

**为什么不直接用 RQ mutation**: RQ mutation 在 client, 不触发 RSC 重渲染. `revalidatePath` 是 Server Action 独占能力, 让 RSC 端数据也立即更新.

---

## 7. API Route / Route Handler (`app/api/**/route.ts`)

**总数**: 18 个 route.ts, 分 3 类:

### 7.1 BFF 透传型 (13 个) — 全 `apiProxy`

| Route | 用途 |
|---|---|
| `app/api/approvals/[id]/{approve,reject,retry}/route.ts` | 审批 (3) |
| `app/api/evaluate/runs/route.ts` + `[id]/route.ts` + `[id]/cancel/route.ts` | 评估 (3) |
| `app/api/evaluate/template/route.ts` | CSV 模板下载 (强制 content-disposition) |
| `app/api/health/system/route.ts` | admin health (NetworkError 必返 502) |
| `app/api/ingest/tasks/route.ts` + `[id]/route.ts` + `[id]/download/route.ts` + `[id]/files/[name]/route.ts` | ingest (4) |
| `app/api/ingest/upload/route.ts` | multipart 上传 |

### 7.2 特殊 BFF (1 个) — 直接 `fetch`, 因 set-cookie 透传

`app/api/auth/anon/route.ts:18`:
```ts
const resp = await fetch(`${API_BASE}/api/auth/anon`, {...});
return proxyAuthResponse(resp);  // 透传多个 set-cookie 的 helper
```

**为什么特殊**: 后端返 1 个匿名 token 时设 7 天 HttpOnly cookie, `apiProxy` 不会透传多个 `set-cookie` 头, 必须用 raw `fetch` + 专用 helper. `Headers.getSetCookie()` (Node 18+) 拿到全部值再手动构造 `NextResponse`.

### 7.3 业务封装型 (4 个) — 不是 BFF, 是 Next 后端业务中转

| Route | 用途 | 走什么 |
|---|---|---|
| `app/api/chat/messages/route.ts` | Dify Chatflow BFF | `getChatProvider()` 抽象 (Provider 模式) |
| `app/api/knowledge/batch/route.ts` | 批量导入后台任务 | `apiFetch` + `DifyDatasets.createDocumentByText` |
| `app/api/knowledge/documents/upload/route.ts` | 文件上传 | `DifyDatasets` |
| `app/api/knowledge/qa/retrieve/route.ts` | Dify retriever 自测 | `DifyDatasets.retrieve` |

**关键模式** (`app/api/ingest/tasks/[id]/download/route.ts:15`):
```ts
return new Response(resp.body, {  // 流式, 不 await .text() 避免内存爆
  headers: { "content-disposition": ... },
  status: resp.status,
});
```

**为什么需要 BFF 这一层** (而不是浏览器直连后端):
- `proxy.ts` 的 next-intl middleware 不会给 `/api/*` 加 locale 前缀, BFF 路径被显式直通 (`lib/api/config.ts:78-86`)
- 流式上传/下载需要服务端中转 (浏览器→FastAPI 直连会被 CORS 拦, multipart 边界也无法透传)
- 鉴权头注入 (cookie→`x-user-token`/`x-admin-token`) 由服务端透传, 浏览器不知道 FastAPI 期望的 header 名

---

## 8. Zustand `useAppStore` — 跨组件选择状态

**入口**: `packages/web/lib/store/app-store.ts:18-31` (32 行, 整文件已读)

```ts
export const useAppStore = create<AppState>()(
  persist(
    (set) => ({
      datasetId: "", domain: "motor",
      setDatasetId: (id) => set({ datasetId: id }),
      setDomain: (d) => set({ domain: d }),
    }),
    { name: "rag.app-store.v1",
      partialize: (state) => ({ datasetId: state.datasetId, domain: state.domain }) },
  ),
);
```

**调用规模**: 9 处 (7 读 + 2 写)

**典型读** — `app/[locale]/knowledge/batch/page.tsx:23`:
```ts
const datasetId = useAppStore((s) => s.datasetId);
```

**典型写** — `components/knowledge/DatasetSwitcher.tsx:21`:
```ts
const setDatasetId = useAppStore((s) => s.setDatasetId);
```

**它的边界 (重要)**:
- **只存"用户选择"** (datasetId/domain), 跨组件共享, localStorage 持久化
- **不存"数据"** (datasets/schemas 列表不进 zustand), 改走 React Context (`lib/store/app-data.tsx`) + RQ
- **替代之前 `localStorage` + `CustomEvent` 同步**: 之前用 `useEffect` 读 localStorage + `window.addEventListener("kg:dataset-changed", sync)`, 改用 zustand 后零副作用

**为什么用 zustand 不用 React Context**: Context 改值会 re-render 整子树, zustand selector 只 re-render 用到该字段的组件. datasetId 在 7+ 个组件读, 用 Context 会无谓 re-render.

---

## 9. (隐藏) React Context `AppDataProvider` — 预留但未使用

**入口**: `packages/web/lib/store/app-data.tsx` (有自测 `app-data.test.tsx`)

**API**:
```ts
<AppDataProvider datasets={...} schemas={...}>
  ...
</AppDataProvider>
// 子组件: useAppData() → { datasets, schemas }
```

**调用规模**: **0 生产调用方** (`grep "AppDataProvider|useAppData"` 0 命中, 除自测).

**它的设计意图** (注释): "Zustand 仍管 datasetId/domain, 列表数据本身不进 zustand, 改走 RSC 灌 + 客户端读".

**实际状态**: 跟 RQ `useQuery` + `qKeys.kg.datasets()` 重叠, RQ 已能解决"跨组件共享 + 自动重拉 + 缓存", 所以 Context 没有调用方. 应当删除或填一个真正用得上的场景.

---

## 10. (死代码) `clientFetch` — 0 业务调用

**入口**: `packages/web/lib/api/auth.ts:33-45`

```ts
export function clientFetch(url: string, init: RequestInit = {}): Promise<Response> {
  const headers: Record<string, string> = { ...(init.headers as Record<string, string> | undefined) };
  if (init.body && !(init.body instanceof FormData) && !headers["Content-Type"]) {
    headers["Content-Type"] = "application/json";
  }
  return fetch(url, { ...init, credentials: "include", headers });
}
```

**调用规模**: **0 业务调用**. 仅自身测试 + `AuthBootstrap.tsx:5` 注释提到 ("改走 apiFetch() 不再手写 clientFetch").

**它被废弃的原因**: `apiFetch` 接管了所有 `clientFetch` 的能力:
- `credentials: include` → 不需要, BFF 用 same-origin cookie, 直连 FastAPI 用 `x-user-token` header 注入
- `Content-Type: application/json` → `apiFetch` 自动 (`config.ts:142-144`)
- `url` 拼 `API_BASE` → `apiFetch` 内部 `resolveUrl` 做

**按 `[[feedback-no-shim-no-minimal-changes]]` 应当删除** (代码 + 测试).

---

## 11. (零) RSC 裸 `await fetch` — 已废弃

**全代码库 grep**: `await fetch(` 在 RSC 组件内 **0 命中** (除 BFF route.ts 的 set-cookie 必要场景).

**所有 RSC 数据获取走 `rscGet` 包装** (8 处) 或 `apiFetch` (8 处) 或 `prefetchQuery` (3 处). 没有"裸 fetch"反模式.

---

## 12. 为什么弄这么多种方案 — 第一性原理拆解

不是历史遗留, 是 **6 个**正交轴交叉产生的组合. 每一层都对应一个**不可化简**的差异.

### 轴 1: RSC ↔ Client (运行环境)

● 鉴权数据源不同: server 能读 `cookies()` 拿 `rag_user_token`, client 只有 `localStorage` (兼容期残留).

● 这决定了 `resolveAuthHeader` 必须分叉 (`config.ts:112-120`):
```ts
return typeof window !== "undefined" ? getClientAuthHeader() : getServerAuthHeader();
```

● 决定了: **RSC 不能用 `useQuery`** (是 client hook, 在 RSC 里调会冲突, 见 `config.ts:14-15` 注释). 由此引出 `rscGet` (纯 RSC 一次) 和 `prefetchQuery` (RSC 预取 + client 接管) 两条路径.

### 轴 2: JSON 解析 ↔ Raw Response (消费方需求)

● 业务 API 调用方想拿 `T`, 不关心 HTTP 状态码细节 → `apiFetch` 解析 + 归一错误.

● BFF route 想透传 status/body 给浏览器 → 必须有 `apiProxy` 返 raw Response, 否则 502 会被 `?? 0` 吞掉 (`[[feedback-bff-must-propagate-502-not-silently-zero]]`).

● Dify 流式响应想保留 `ReadableStream` → 也要 raw Response, 不能 `await res.json()`.

### 轴 3: 一次性 ↔ 持续轮询 (数据生命周期)

● `/knowledge/datasets` 这种列表, 渲染一次就够 → `rscGet` 一次拿完.

● `/health` `/output` 这种"任务进度"页, 要每 2-10s 自动刷 → 必须 RQ 接管, 引出 `prefetchQuery + HydrationBoundary` 模式.

### 轴 4: 读 ↔ 写 (操作语义)

● 读: RSC (`rscGet` / `apiFetch`) + client useQuery.

● 写:
  - **表单提交 / 业务变更** → Server Action (有 `revalidatePath` 独占能力, 让 RSC 端也立即更新)
  - **列表内的快捷操作** (approve/reject) → RQ useMutation (有 `onSuccess` cache invalidation, 跟列表 queryKey 自动联动)

### 轴 5: 内部服务 ↔ 外部服务 (鉴权归属)

● 内部 (FastAPI): `apiFetch` 注入 `x-user-token`/`x-admin-token`, 走 `API_BASE`.

● 外部 (Dify/OpenAI): `apiProxy({ base: DIFY_BASE_URL })` 跳过本项目 auth, 注入 Dify 自己的 `Authorization: Bearer ...`. `config.ts:200-202` 注释明确说.

### 轴 6: 同源 (BFF) ↔ 直连 (FastAPI) (URL 解析)

● Next.js 没有 `app/api/kg/*` route.ts, 但前端代码统一写 `/api/kg/*` 风格.

● 必须有 `BFF_PATTERNS` 白名单 (7 条 RegExp) 决定同源 vs 跨 host, 修"全 `/api/*` 同源"导致 14 个路径 404 的 bug (`[[feedback-apifetch-bff-prefix-list]]`).

### 不可化简的特殊情况

● **set-cookie 透传** (`/api/auth/anon`): `apiProxy` 不会保留多个 `set-cookie` 值, 必须 raw `fetch` + `Headers.getSetCookie()`. 这是 Node 18+ 的 Headers 行为, 不是设计选择.

● **multipart 流**: 上传/下载路由必须用 BFF (浏览器→FastAPI 直连会被 CORS 拦, multipart `boundary` 也无法跨域透传).

● **Dify `{ data }` 包装**: 后端 list endpoint 统一 Dify 风格包装, `rscGet` 用启发式 (`Array.isArray(data)`) 自动拆, 调用方零感知.

---

## 13. 重复 / 重叠分析

| 重叠组合 | 真的重叠吗 | 备注 |
|---|---|---|
| `rscGet` vs `apiFetch` 直接调 | **不重叠** | `rscGet` 拆 `{ data: T[] }`, `apiFetch` 返原始 JSON. 按需选. |
| `apiProxy` vs `apiFetch` | **不重叠** | 一个解析+归一, 一个透传. 消费方不同. |
| `getRscQueryClient` vs `createBrowserQueryClient` | **不重叠** | server 单例 (cache) vs browser 单例 (useState), per-request vs per-mount. |
| `approvalsApi.submit` (lib) vs `_actions/knowledge.ts` Server Action vs ApprovalRow useMutation | **不重叠** | lib 封装底层调用, Action 走 RSC revalidate, mutation 走 RQ invalidation. 三方各自场景, lib 是共同底层. |
| RSC `apiFetch("/api/approvals/me")` initialData + client useQuery 接管 | **正确模式** | 不是重叠, 是 "RSC 预填 + client 接管" 的预期行为. `MySubmissionsList.tsx:34` `.catch(() => initialData)` 兜底, RSC 失败不挂 client. |
| **死代码**: `clientFetch` | **是死代码** | 0 业务调用, 仅测试. 应当删除. |
| **死代码**: `app-data.tsx` React Context | **是死代码** | 0 调用方, RQ 已覆盖. 应当删除或填空. |

---

## 14. 行动项 (可选, 非用户要求, 仅做记录)

| 优先级 | 行动 | 理由 |
|---|---|---|
| P1 | 删 `lib/api/auth.ts:33-45` 的 `clientFetch` + 它的测试 | 0 调用, 死代码, `[[feedback-no-shim-no-minimal-changes]]` |
| P1 | 删 `lib/store/app-data.tsx` + 测试 | 0 调用, RQ 已覆盖, 留空壳误导后人 |
| P2 | 把 `rscGet` 的 Dify 启发式 (data 是数组才拆) 注释写进 `lib/api/errors.ts` 或独立文档, 提示后端**统一 list 包装格式** | 当前靠注释 + 1 个测试, 后端若改 schema 容易漏. |
| P3 | 把 `BFF_PATTERNS` 7 条 RegExp 抽成 `BFF_ROUTES: string[]` 声明式, 跟 `app/api/**/route.ts` 一一对应, 加 `scripts/check-bff-coverage.ts` 校验 (前端期望 ↔ 实际 route.ts) | `[[feedback-must-test-both-ends]]`, 防止后端删路由前端没感知. |
| P3 | 文档: 在 `docs/web-data-fetch.md` 写一份"9 种方案的选择决策树", 让新人按页面类型选正确方案 | 报告是 audit, 不是文档. 后续如果团队扩张再做. |

---

## 15. 一句话总结

● 项目分这么多层**不是技术债, 是 6 个正交轴 (RSC/Client × JSON/Raw × 一次性/轮询 × 读/写 × 内部/外部 × 同源/直连) 的笛卡尔积**; 真正需要清理的是 `clientFetch` 和 `app-data.tsx` 两个死代码, 而不是合并其它层.
