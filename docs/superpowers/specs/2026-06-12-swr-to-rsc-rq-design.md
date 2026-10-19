# SWR → RSC + React Query 数据层重构 (设计)

**日期**: 2026-06-12
**状态**: 待批准
**作者**: brainstorming session
**关联 spec**: [2026-06-10-web-frontend-architecture.md](2026-06-10-web-frontend-architecture.md) (BFF 边界), [2026-06-10-knowledge-detail-pages-design.md](2026-06-10-knowledge-detail-pages-design.md) (现有页面架构)

## Context

### 背景 1: 当前全 SWR 客户端拉数据

`packages/web` 全部 18 处数据获取走 `swr@2.4.1` + 自写 `fetcher`, 每个 page 都是 `"use client"`, 客户端 `useSWR(url, fetcher)` 拿数据。

- **14 个 page** 用 `useSWR/useApi`: `datasets / documents / documents/import / graph / nodes / relations / triples / qa / dataset-documents/[id] / evaluate / evaluate/[id] / evaluate/new / output / output/[task_id] / health`
- **4 个组件** 也用: `HealthDot (5s 轮询) / DatasetSwitcher / DomainSwitcher / chat 流式`
- 18 份 `.test.tsx` 同目录覆盖

### 背景 2: Next.js 16 App Router + React 19.2 已就绪

- 已用 Next.js 16.2 App Router (支持 RSC)
- React 19.2 (Actions / `useActionState` / `use()` / `useOptimistic` 可用)
- 已有 zustand 5 (`lib/store/app-store.ts`, dataset/domain + persist)
- 测试: vitest + jsdom, 单测同目录, E2E playwright 18 用例
- 18 份单测覆盖成熟, 删 SWR 必须保证测试跟着迁移

### 背景 3: 认证 token 存 localStorage 阻碍 RSC

当前 `lib/api/auth.ts`:
- `getUserToken()/getAdminToken()` 读 `localStorage` (浏览器独有)
- `ensureAuthToken()` 首次 client 端 POST `/api/auth/anon` 拿 token 写 localStorage
- `fetcher` 拼 `x-user-token` / `x-admin-token` header

**RSC 拿不到 localStorage** — 这是 RSC 路径的根本障碍, 必须先改认证模型。

### 背景 4: 刚定的 BFF 边界规则

[2026-06-10-web-frontend-architecture.md](2026-06-10-web-frontend-architecture.md) 锁定 BFF 保留 4 类: Dify Chatflow / multipart / 后台任务 / SSE。本 spec 完全在此约束下。

## Goal

**主目标**: 把 18 个 SWR 调用点从"client fetch"改成"以 RSC 为主、RQ 接管为辅", 提升首屏 LCP, 简化数据层。

**具体子目标**:
1. 列表/详情页首屏由 RSC 在 server 端 fetch, **零客户端首次请求**
2. 客户端交互 (翻页/筛选/轮询) 由 React Query 接管 (仅 4 处需要)
3. 简单 mutation 走 React 19 server actions, 减少手写 `isPending/error`
4. 认证从 localStorage 迁到 httpOnly cookie, 让 RSC 能代用户拉后端
5. SWR 依赖彻底移除
6. 18 份单测全部跟着迁移, 不能漏

## User Story

1. **Alice** (产品经理) 打开 `/knowledge/datasets` — 看到的不再是"加载中…", 而是**直接渲染好**的数据表 (RSC SSR 输出)
2. **Alice** 切 dataset — 页面通过 `router.refresh()` 触发 RSC 重跑预取, **不发新 fetch** (zustand + RSC 协同)
3. **Alice** 写一条 QA — 提交走 server action, 成功后 `revalidatePath` 让列表页 RSC 重拉, **无 loading 抖动**
4. **Bob** (工程师) 看后台 batch 任务 — 列表用 RQ `useQuery` 接管 + 5s 轮询, 跟现在 SWR 体验一致
5. **Carol** (admin) 切换 dataset 时 — 客户端 **不下载 RQ 库** (A 档页面不挂 RQ provider), bundle 减少 ~12KB

## 关键设计决策 (锁定)

| 决策 | 选择 | 理由 |
|---|---|---|
| 数据层架构 | **A 档 13 处纯 RSC** + **B 档 4 处 RSC 预取 + RQ** + 1 处 chat 保持原样 | 用户优先级"先 RSC, 后 RQ" |
| 认证模型 | token 改 **httpOnly cookie** (后端 Set-Cookie, 前端去 localStorage) | RSC 路径最大障碍, 必须先解 |
| 兼容旧 token | 后端保留 `x-user-token` header 回退 + 一次性 migrate 端点 | 不破存量用户 |
| Mutation 路径 | 简单 POST → **server actions**; multipart / 流式 / 后台任务 → **BFF 保留** | 混合: 利用 Actions 但不勉强复杂场景 |
| Loading 体验 | **1 份** root layout `loading.tsx` (最近祖先生效) | 18 份重复无意义 |
| 状态管理 | zustand 维持 `datasetId/domain`; datasets/schemas 列表走 **RSC 灌 Context** | persist 行为不变, 列表跨请求新鲜 |
| React Compiler | **本期不采用** | 用户决定; 后续单独立 spec |
| 范围 | **全量 + 分阶段 (P0-P4)** | 5 个阶段渐进上线, 每阶段可回滚 |

---

## 设计 1 — 架构总览

**目标**: 列表/详情页首屏由 RSC 在 server 端 fetch (带 cookie token), 灌进 RQ server-side cache; 客户端 `useQuery` 接管, 零首次网络。

### 三层角色

```
┌────────────────────────────────────────────────────┐
│ Page (server component)                            │
│  ├─ await fetch(URL, { headers: cookie token })    │
│  ├─ 注入 <HydrationBoundary state={dehydrate(qc)}> │
│  └─ <ClientTable initialData=... />                │
└────────────────────────────────────────────────────┘
        │ 序列化
        ▼
┌────────────────────────────────────────────────────┐
│ ClientTable (use client)                           │
│  └─ useQuery({                                    │
│       queryKey: ['rag', 'output', 'list'],         │
│       queryFn: () => ingestApi.fetchTasks(),       │
│       refetchInterval: 5_000,                      │
│     })                                             │
└────────────────────────────────────────────────────┘
        │ 写后
        ▼
┌────────────────────────────────────────────────────┐
│ Action: 简单 POST → server action + revalidatePath │
│         复杂(上传/流式/任务) → BFF route + RQ mutate│
└────────────────────────────────────────────────────┘
```

### 18 处调用点归类

| 档 | 条件 | 数量 | 代表 |
|---|---|---|---|
| **A. 纯 RSC** | 首屏即用、无客户端轮询 | 13 | datasets/documents/graph/nodes/relations/triples/qa/... |
| **B. RSC 预取 + RQ 轮询** | 需要客户端 interval | 4 | output/output[id]/health/HealthDot |
| **保持原样** | chat 流式 / Switcher | 3 | chat/DatasetSwitcher/DomainSwitcher |

---

## 设计 2 — 认证改造 (cookie-only)

### 后端 (FastAPI) — P0 阶段

1. `/api/auth/anon` POST 响应改 Set-Cookie:
   ```
   Set-Cookie: rag_user_token=<jwt>; HttpOnly; SameSite=Lax; Path=/; Max-Age=...
   ```
2. CORS 加:
   ```
   Access-Control-Allow-Credentials: true
   Access-Control-Allow-Origin: http://localhost:3000  # 显式, 不用 *
   ```
3. 保留 `/api/auth/admin-login` 同样 Set-Cookie `rag_admin_token`
4. **保留** "读 `x-user-token` / `x-admin-token` header" 的回退, 灰度期两种都认 (`LEGACY_AUTH_HEADERS=true` 默认)

### 前端 — P1 阶段

**`lib/api/auth.ts` 改造**:

```ts
// 服务端读 token (供 RSC + server actions + BFF route handler 用)
import { cookies } from "next/headers";

export async function getServerToken(): Promise<string> {
  const c = await cookies();
  return c.get("rag_user_token")?.value ?? c.get("rag_admin_token")?.value ?? "";
}

export const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

export function clientFetch(url: string, init: RequestInit = {}): Promise<Response> {
  return fetch(url, {
    ...init,
    credentials: "include",          // 跨域带 cookie
    headers: {
      ...(init.body && !(init.body instanceof FormData)
        ? { "Content-Type": "application/json" } : {}),
      ...init.headers,
    },
  });
}
```

- 删除所有 `getUserToken` / `getAdminToken` 的 `localStorage` 读取
- `authHeaders()` 简化为 client 端空对象 (浏览器自动带 cookie)
- `ensureAuthToken()` 改: 直接 POST `/api/auth/anon` 让后端 Set-Cookie, 客户端不存任何东西

### BFF route handler 改造

```ts
// app/api/knowledge/qa/route.ts
import { cookies } from "next/headers";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

export async function GET(request: Request) {
  const token = (await cookies()).get("rag_user_token")?.value ?? "";
  const url = new URL(request.url);
  const res = await fetch(
    `${API_BASE}/api/knowledge/qa?${url.searchParams}`,
    { headers: token ? { "x-user-token": token } : {} },
  );
  // 错误处理 + 透传
}
```

> 注: BFF 走 server-to-server, **不靠 cookie 自动带** (cookie 是浏览器↔Next 的), 必须显式读 cookie 写 header。

### 迁移兼容 (灰度期)

- 首次访问: 客户端检查 `localStorage.getItem("rag_user_token")` — 如果有, POST `/api/auth/migrate` (后端新加) 做"旧 token → 新 cookie"换发, 成功后清 localStorage
- 后端 "读 header" 回退保留 ~2 周, feature flag `LEGACY_AUTH_HEADERS=true`

---

## 设计 3 — RSC 预取 + RQ 接管协议

### queryKey 中心化

**`lib/api/queryKeys.ts`** (所有 queryKey 的唯一来源):

```ts
export const qKeys = {
  all: ["rag"] as const,
  health: {
    all: ["rag", "health"] as const,
    system: () => [...qKeys.health.all, "system"] as const,
  },
  output: {
    all: ["rag", "output"] as const,
    list: () => [...qKeys.output.all, "list"] as const,
    detail: (id: string) => [...qKeys.output.all, "detail", id] as const,
  },
  batch: {
    all: ["rag", "batch"] as const,
    status: (id: string) => [...qKeys.batch.all, "status", id] as const,
  },
} as const;
```

### RSC 预取 + HydrationBoundary 模板

**`lib/api/rsc-queries.ts`** (server-only):

```ts
import "server-only";
import { cache } from "react";
import { QueryClient } from "@tanstack/react-query";
import { getServerToken } from "./auth";

export const getRscQueryClient = cache(() => new QueryClient({
  defaultOptions: {
    queries: { staleTime: Infinity, gcTime: 0, retry: false },
  },
}));

export async function prefetchQuery<T>(
  qc: QueryClient,
  queryKey: readonly unknown[],
  url: string,
): Promise<void> {
  await qc.prefetchQuery({
    queryKey,
    queryFn: async () => {
      const token = await getServerToken();
      const res = await fetch(url, {
        headers: token ? { "x-user-token": token } : {},
        cache: "no-store",
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return res.json() as Promise<T>;
    },
  });
}
```

**Page 入口** (B 档典型):

```tsx
// app/[locale]/output/page.tsx
import { HydrationBoundary, dehydrate } from "@tanstack/react-query";
import { getRscQueryClient, prefetchQuery } from "@/lib/api/rsc-queries";
import { qKeys } from "@/lib/api/queryKeys";
import { OutputListClient } from "./_components/OutputListClient";

export default async function OutputPage() {
  const qc = getRscQueryClient();
  await prefetchQuery(qc, qKeys.output.list(), `${API_BASE}/api/ingest/tasks`);

  return (
    <HydrationBoundary state={dehydrate(qc)}>
      <OutputListClient />
    </HydrationBoundary>
  );
}
```

**Client 端**:

```tsx
// app/[locale]/output/_components/OutputListClient.tsx
"use client";
import { useQuery } from "@tanstack/react-query";
import { qKeys } from "@/lib/api/queryKeys";
import { ingestApi } from "@/lib/api/ingest";

export function OutputListClient() {
  const { data, error, isLoading } = useQuery({
    queryKey: qKeys.output.list(),
    queryFn: () => ingestApi.fetchTasks(),
    refetchInterval: 5_000,
  });
  // 渲染同前
}
```

### 失效机制 (双触发)

| 触发点 | 动作 |
|---|---|
| server action 写完 | `revalidatePath("/[locale]/output")` + client 端 `invalidateQueries({ queryKey: qKeys.output.all })` |
| BFF route handler 写完 | 仅 client 端 `invalidateQueries` (BFF 没法 revalidatePath) |
| zustand dataset 切换 | `router.refresh()` (让 RSC 重新跑预取), 走 useEffect 监听 zustand |

### Provider 嵌套 (仅 B 档入口要)

**`app/[locale]/output/layout.tsx`** (B 档专属 layout):

```tsx
"use client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";

export default function OutputLayout({ children }: { children: React.ReactNode }) {
  const [qc] = useState(() => new QueryClient({
    defaultOptions: { queries: { staleTime: Infinity, gcTime: 0 } },
  }));
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}
```

A 档页面 (datasets/documents/...) **不挂** RQ provider, 省一份 JS。

### 关键约束

1. `staleTime: Infinity` 必须在 RSC 和 Client 端一致 — 否则 HydrationBoundary 状态"被立即视为过期", client 立即重拉 (白做预取)
2. queryKey 引用一致 — RSC prefetch 用 `qKeys.output.list()`, client `useQuery` 用同样的, 不准字面量手写
3. RSC 端 `cache: "no-store"` — 不污染 Next.js data cache, 避免 token 过期问题
4. 不引入 `unstable_cache` — 本期不优化 RSC 之间 cache 复用, 避免复杂度爆炸
5. 错误处理: RSC `prefetchQuery` 失败时 throw, 由 Next.js `error.tsx` 兜住; client 端 `useQuery` 失败用 `error.tsx` client 边界

---

## 设计 4 — 数据流分档 (18 处)

### A 档: 13 处纯 RSC + server actions

**通用模式**:
```
原: "use client" page → useSWR(url, fetcher) → setState 翻页
新: RSC page → await fetch + cookie → <ClientTable initialData={...} />
    ClientTable 改 useState 管分页/筛选; 切 dataset 触发 router.refresh()
    mutation 改 server action + revalidatePath
```

| 页面 | 改动 |
|---|---|
| `knowledge/datasets/page.tsx` | RSC fetch `getDatasets` → prop 灌 `<DatasetsTable>` |
| `knowledge/documents/page.tsx` | RSC 并行 fetch `stats` + `documents` |
| `knowledge/documents/import/page.tsx` | RSC 空壳 + server action `commitDocuments` |
| `knowledge/graph/page.tsx` | RSC fetch `stats(domain)` |
| `knowledge/nodes/page.tsx` | RSC fetch `nodes(1000)` |
| `knowledge/relations/page.tsx` | RSC fetch `relations(1000)` |
| `knowledge/triples/page.tsx` | RSC fetch `schema` + server action `createTriples` |
| `knowledge/qa/page.tsx` | RSC fetch `qaList` + server action `createQA` |
| `knowledge/dataset-documents/[id]/page.tsx` | RSC fetch `datasets` + `qaList(id)` |
| `evaluate/page.tsx` | RSC fetch `runs` |
| `evaluate/[id]/page.tsx` | RSC fetch `runDetail` + server action `deleteRun` |
| `evaluate/new/page.tsx` | RSC 表单 + server action `createRun` + `redirect` |
| `knowledge/page.tsx` (根) | RSC fetch `stats` 概览 |

### B 档: 4 处 RSC 预取 + RQ 轮询

| 页面/组件 | RSC 端 | Client 端 `useQuery` |
|---|---|---|
| `output/page.tsx` | prefetch `qKeys.output.list()` | `refetchInterval: 5_000` |
| `output/[task_id]/page.tsx` | prefetch `qKeys.output.detail(id)` | `refetchInterval: 2_000` (进行中时) |
| `health/page.tsx` | prefetch `qKeys.health.system()` | `refetchInterval: 10_000` |
| `HealthDot.tsx` | 父级 prefetch | `refetchInterval: 5_000` (navbar) |

### 保持原样 (3 处)

- `chat/page.tsx` — 流式, 走 `fetch` + `ReadableStream` (CLAUDE.md 提到 chat-agent spec)
- `DatasetSwitcher.tsx` — 读 zustand+Context
- `DomainSwitcher.tsx` — 同上

### Loading 体验

- **1 份** root layout `app/[locale]/loading.tsx` (最近祖先生效, 全路由自动套)
- 18 份 `loading.tsx` 不写 (Next.js 嵌套机制兜底)
- 配合现有 shadcn `<Skeleton />` 组件

### 18 处改造总表

| # | 文件 | 档 | 改造 |
|---|---|---|---|
| 1 | `app/[locale]/knowledge/datasets/page.tsx` | A | 改 RSC |
| 2 | `app/[locale]/knowledge/documents/page.tsx` | A | 改 RSC |
| 3 | `app/[locale]/knowledge/documents/import/page.tsx` | A | 改 RSC + action |
| 4 | `app/[locale]/knowledge/graph/page.tsx` | A | 改 RSC |
| 5 | `app/[locale]/knowledge/nodes/page.tsx` | A | 改 RSC |
| 6 | `app/[locale]/knowledge/relations/page.tsx` | A | 改 RSC |
| 7 | `app/[locale]/knowledge/triples/page.tsx` | A | 改 RSC + action |
| 8 | `app/[locale]/knowledge/qa/page.tsx` | A | 改 RSC + action |
| 9 | `app/[locale]/knowledge/dataset-documents/[id]/page.tsx` | A | 改 RSC |
| 10 | `app/[locale]/knowledge/datasets/page.test.tsx` 等 13 个测试 | — | 改写 |
| 11 | `app/[locale]/output/page.tsx` | B | 改 RSC + HydrationBoundary |
| 12 | `app/[locale]/output/[task_id]/page.tsx` | B | 改 RSC + HydrationBoundary |
| 13 | `app/[locale]/health/page.tsx` | B | 改 RSC + HydrationBoundary |
| 14 | `components/knowledge/HealthDot.tsx` | B | 改 client + useQuery |
| 15 | `app/[locale]/chat/page.tsx` | — | 不动 |
| 16 | `components/knowledge/DatasetSwitcher.tsx` | — | 删 SWR 读 context |
| 17 | `components/knowledge/DomainSwitcher.tsx` | — | 删 SWR 读 context |
| 18 | `lib/api/swr.ts` + `lib/api/swr-provider.tsx` | — | **整体删** |

---

## 设计 5 — Mutation 路径

### 判定规则

| 判定 | 走法 | 原因 |
|---|---|---|
| 单条数据 POST/DELETE/PUT | server action | RSC 原生; 自动 revalidate; React 19 Actions |
| multipart 上传 | BFF route | server action 处理 multipart 在 Next 16 仍糙 |
| 流式 (chat) | BFF route | server action 不支持 streaming response |
| **服务端状态机** (batch in-memory task map) | BFF route | server action 调用间不共享内存 |

### server action 模板

**`app/[locale]/_actions/knowledge.ts`**:

```ts
"use server";
import { revalidatePath } from "next/cache";
import { getServerToken } from "@/lib/api/auth";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

/** 统一返回包装 — 永不抛异常, 错误走 error 字段 */
export type ActionResult<T> = { ok: true; data: T } | { ok: false; error: string };

async function postJson<T>(path: string, body: unknown): Promise<ActionResult<T>> {
  const token = await getServerToken();
  try {
    const res = await fetch(`${API_BASE}${path}`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(token ? { "x-user-token": token } : {}),
      },
      body: JSON.stringify(body),
      cache: "no-store",
    });
    if (!res.ok) {
      const text = await res.text().catch(() => res.statusText);
      return { ok: false, error: `HTTP ${res.status}: ${text}` };
    }
    return { ok: true, data: (await res.json()) as T };
  } catch (e) {
    return { ok: false, error: e instanceof Error ? e.message : String(e) };
  }
}

export async function createQA(input: QAInput): Promise<ActionResult<QA>> {
  const result = await postJson<QA>("/api/knowledge/qa", input);
  if (result.ok) revalidatePath("/[locale]/knowledge/qa");
  return result;
}

export async function createTriples(input: TriplesInput): Promise<ActionResult<TriplesResponse>> {
  const result = await postJson<TriplesResponse>("/api/kg/triples", input);
  if (result.ok) revalidatePath("/[locale]/knowledge/triples");
  return result;
}

export async function commitDocuments(input: CommitInput): Promise<ActionResult<CommitResult>> {
  const result = await postJson<CommitResult>("/api/knowledge/documents/commit", input);
  if (result.ok) revalidatePath("/[locale]/knowledge/documents/import");
  return result;
}
```

### client 端: React 19 `useActionState` + `<form action>`

```tsx
"use client";
import { useActionState } from "react";
import { createQA } from "@/app/[locale]/_actions/knowledge";
import { toast } from "sonner";

export function QASubmitForm({ datasetId }: { datasetId: string }) {
  const [state, formAction, isPending] = useActionState(
    async (_prev: { ok: boolean; error?: string }, formData: FormData) => {
      const result = await createQA({
        dataset_id: datasetId,
        question: String(formData.get("question") ?? ""),
        answer: String(formData.get("answer") ?? ""),
      });
      if (!result.ok) return { ok: false, error: result.error };
      toast.success("已保存");
      return { ok: true };
    },
    { ok: true },
  );

  return (
    <form action={formAction} className="space-y-3">
      <textarea name="question" required disabled={isPending} />
      <textarea name="answer" required disabled={isPending} />
      <button type="submit" disabled={isPending}>
        {isPending ? "提交中..." : "提交"}
      </button>
      {!state.ok && state.error && (
        <p className="text-sm text-destructive">{state.error}</p>
      )}
    </form>
  );
}
```

### BFF route handler 改造 (cookie 透传)

**`app/api/knowledge/documents/upload/route.ts`**:

```ts
import { cookies } from "next/headers";
import { NextResponse } from "next/server";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

export async function POST(request: Request) {
  const cookieStore = await cookies();
  const token = cookieStore.get("rag_user_token")?.value ?? "";

  const incoming = await request.formData();
  const backendFd = new FormData();
  const file = incoming.get("file");
  const datasetId = incoming.get("dataset_id");
  if (!(file instanceof File) || typeof datasetId !== "string") {
    return NextResponse.json({ error: "file and dataset_id required" }, { status: 400 });
  }
  backendFd.append("file", file);
  backendFd.append("dataset_id", datasetId);

  try {
    const res = await fetch(`${API_BASE}/api/knowledge/documents/upload`, {
      method: "POST",
      headers: token ? { "x-user-token": token } : {},
      body: backendFd,
    });
    const text = await res.text();
    return new NextResponse(text, {
      status: res.status,
      headers: { "Content-Type": res.headers.get("Content-Type") ?? "application/json" },
    });
  } catch (e) {
    return NextResponse.json({ error: e instanceof Error ? e.message : String(e) }, { status: 502 });
  }
}
```

**关键**: BFF 收的是浏览器请求 (cookie 自动带), 转发给 FastAPI 时**必须显式写 `x-user-token` header** (server-to-server 不会自动带 cookie)。

### 关键约束

1. **server action 永不抛异常** — 所有错误返 `ActionResult` 包装
2. **server action 调完必 revalidate** (仅成功时)
3. **BFF 透传 cookie → header** — 每个 route handler 都写
4. **batch 任务页 B 档化** — startBatch 走 BFF, client RQ `refetchInterval: 2_000` 轮询
5. **server action 文件必带 `"use server"`** directive 顶置

### 18 处 mutation 去向

| # | mutation | 去向 | 新增文件 |
|---|---|---|---|
| 1 | `createQA` | server action | `_actions/knowledge.ts` |
| 2 | `createTriples` | server action | `_actions/knowledge.ts` |
| 3 | `commitDocuments` | server action | `_actions/knowledge.ts` |
| 4 | `createRun` | server action | `_actions/evaluate.ts` |
| 5 | `deleteRun` | server action | `_actions/evaluate.ts` |
| 6 | `cancelTask` | server action | `_actions/output.ts` |
| 7 | `uploadDocument` | BFF 不动 | (已存在 route.ts, 仅改 cookie) |
| 8 | `startBatch` / `fetchBatchStatus` | BFF 不动 | (已存在) |
| 9 | `chat send` | 保持原样 | 不动 |

---

## 设计 6 — Zustand / 测试 / 依赖

### Zustand 现状与改造

**现状**: `lib/store/app-store.ts` 用 `persist` 存 `datasetId + domain` (`rag.app-store.v1` key)。

**改造后**:

| 维度 | 决定 |
|---|---|
| zustand store 本身 | **维持现状** (保留 datasetId + domain + persist) |
| Switcher 数据源 | 改 RSC 灌 + Context (**不进 zustand**) |
| 切 dataset 触发 | zustand action + `router.refresh()` |

**`lib/store/app-data.tsx`** (client provider):

```tsx
"use client";
import { createContext, useContext } from "react";
import type { DatasetRow } from "@/lib/api/knowledge";

interface AppData {
  datasets: DatasetRow[];
  schemas: { name: string }[];
}

const Ctx = createContext<AppData | null>(null);

export function AppDataProvider({
  datasets, schemas, children,
}: AppData & { children: React.ReactNode }) {
  return <Ctx.Provider value={{ datasets, schemas }}>{children}</Ctx.Provider>;
}

export function useAppData() {
  const v = useContext(Ctx);
  if (!v) throw new Error("useAppData must be used inside <AppDataProvider>");
  return v;
}
```

**Switcher 改写**:

```tsx
"use client";
import { useAppData } from "@/lib/store/app-data";
import { useAppStore } from "@/lib/store/app-store";
import { useRouter } from "next/navigation";

export function DatasetSwitcher() {
  const { datasets } = useAppData();
  const { datasetId, setDatasetId } = useAppStore();
  const router = useRouter();
  return (
    <Select
      value={datasetId}
      onValueChange={(id) => {
        setDatasetId(id);
        router.refresh();   // 切完触发所有 RSC 重新预取
      }}
    >
      {datasets.map((d) => <SelectItem key={d.id} value={d.id}>{d.name}</SelectItem>)}
    </Select>
  );
}
```

**关键约束**:
- zustand `datasetId / domain` 仍 persist (用户体验: 刷新后保留选择)
- RSC 灌的 `datasets / schemas` **不进 zustand** (仅 Context, 跨请求新鲜)
- 切 dataset 不发任何 fetch — 全部靠 `router.refresh()`

### 测试策略

**vitest 单元测试** (同目录 `.test.tsx`):

| 类型 | 文件 | 数量 | 写法 |
|---|---|---|---|
| RSC page 渲染 | `app/[locale]/knowledge/*/page.test.tsx` | 13 改写 | `render` + mock `fetch` + 断言表格 |
| Client 子组件 | `app/[locale]/knowledge/**/_components/*.test.tsx` | 13 新增 | render + prop 注入 |
| B 档 client 组件 | `output/_components/OutputListClient.test.tsx` 等 | 3 新增 | mock `useQuery` 验证 `refetchInterval` |
| server actions | `app/[locale]/_actions/*.test.ts` | 3 新增 | mock `next/cache` + `next/headers` + `fetch` |
| RQ utility | `lib/api/rsc-queries.test.ts` | 1 新增 | mock cookies + fetch |
| queryKey | `lib/api/queryKeys.test.ts` | 1 新增 | 参数化断言 |
| BFF route | `app/api/knowledge/documents/upload/route.test.ts` 等 | 改写 | mock request cookie → 后端 fetch header |
| 现有 SWR 测试 | 18 份 `*.test.tsx` | 18 改 | 删 SWR 断言, 加新断言 |

**契约测试** (CLAUDE.md 强制):
- `tests/test_api_contract.py` 必须**改完每个 BFF 后跑一次**
- 删 BFF route 前必跑 (红了不能删)
- P4 阶段删 `lib/api/swr.ts` 后再跑一次兜底

**E2E**:
- `e2e/*.spec.ts` 现有 18 份, 改造阶段每 P 跑一次
- 重点新增 1 项: **首屏 RSC 直达验证** (禁 JS 也能看到列表数据)

### 依赖变更

**`packages/web/package.json`**:

```diff
   "dependencies": {
-    "swr": "^2.4.1",
+    "@tanstack/react-query": "^5.62.0",
     ...
   },
   "devDependencies": {
+    "@tanstack/react-query-devtools": "^5.62.0",
     ...
   }
```

**新增包大小**: `@tanstack/react-query` ≈ 12KB gzipped (vs `swr` ≈ 4KB)
**A 档不加载** (懒加载优势) — 实际 bundle 净减 4KB
**B 档加载** — 不可避免

### 文件清单

**新增** (12 个):
```
lib/api/queryKeys.ts
lib/api/rsc-queries.ts
lib/store/app-data.tsx
app/[locale]/_actions/knowledge.ts
app/[locale]/_actions/evaluate.ts
app/[locale]/_actions/output.ts
app/[locale]/output/layout.tsx
app/[locale]/_actions/knowledge.test.ts
app/[locale]/_actions/evaluate.test.ts
app/[locale]/_actions/output.test.ts
lib/api/queryKeys.test.ts
lib/api/rsc-queries.test.ts
```

**改写** (约 47 个, 分 3 类):

```
# (A) lib/api 工具层 (4 个)
lib/api/auth.ts                              # localStorage → cookie
lib/api/knowledge.ts                         # 删 URL 工厂注释
lib/api/evaluate.ts
lib/api/ingest.ts

# (B) page + 组件实现 (24 个)
app/[locale]/knowledge/datasets/page.tsx              # A 档 RSC
app/[locale]/knowledge/documents/page.tsx             # A 档 RSC
app/[locale]/knowledge/documents/import/page.tsx      # A 档 RSC
app/[locale]/knowledge/graph/page.tsx                 # A 档 RSC
app/[locale]/knowledge/nodes/page.tsx                 # A 档 RSC
app/[locale]/knowledge/relations/page.tsx             # A 档 RSC
app/[locale]/knowledge/triples/page.tsx               # A 档 RSC
app/[locale]/knowledge/qa/page.tsx                    # A 档 RSC
app/[locale]/knowledge/dataset-documents/[id]/page.tsx # A 档 RSC
app/[locale]/evaluate/page.tsx                        # A 档 RSC
app/[locale]/evaluate/[id]/page.tsx                   # A 档 RSC
app/[locale]/evaluate/new/page.tsx                    # A 档 RSC
app/[locale]/knowledge/page.tsx                       # A 档 RSC 概览
app/[locale]/output/page.tsx                          # B 档 RSC + Hydration
app/[locale]/output/[task_id]/page.tsx                # B 档 RSC + Hydration
app/[locale]/health/page.tsx                          # B 档 RSC + Hydration
components/knowledge/HealthDot.tsx                    # B 档 useQuery
components/knowledge/DatasetSwitcher.tsx              # 读 zustand+context
components/knowledge/DomainSwitcher.tsx               # 读 zustand+context
app/api/knowledge/qa/route.ts                         # 改读 cookie (保留 GET/POST, P4 评估删除)
app/api/knowledge/documents/upload/route.ts           # 改读 cookie (multipart, 保留)
app/api/knowledge/batch/route.ts                      # 改读 cookie (后台任务, 保留)
app/api/ingest/upload/route.ts                        # 改读 cookie (保留)

# (C) 测试文件 (19 个)
app/[locale]/knowledge/datasets/page.test.tsx         # 13 A 档 page 测试改写
app/[locale]/knowledge/documents/page.test.tsx
app/[locale]/knowledge/documents/import/page.test.tsx
app/[locale]/knowledge/graph/page.test.tsx
app/[locale]/knowledge/nodes/page.test.tsx
app/[locale]/knowledge/relations/page.test.tsx
app/[locale]/knowledge/triples/page.test.tsx
app/[locale]/knowledge/qa/page.test.tsx
app/[locale]/knowledge/dataset-documents/[id]/page.test.tsx
app/[locale]/evaluate/page.test.tsx
app/[locale]/evaluate/[id]/page.test.tsx
app/[locale]/evaluate/new/page.test.tsx
app/[locale]/knowledge/page.test.tsx
app/[locale]/output/page.test.tsx                     # 3 B 档 page 测试改写
app/[locale]/output/[task_id]/page.test.tsx
app/[locale]/health/page.test.tsx
components/knowledge/HealthDot.test.tsx               # HealthDot 测试改写
components/knowledge/DatasetSwitcher.test.tsx         # 2 Switcher 测试改写
components/knowledge/DomainSwitcher.test.tsx
```

**BFF route 处置说明**:
- `app/api/knowledge/qa/route.ts`: 现在同时处理 GET + POST。P0 阶段改读 cookie, GET/POST 都保留。P2 阶段 QA POST 改 server action 后, GET 也被 RSC 替代, 整个 route.ts **变为空壳** — 进入 P4 评估: 跟 swr.ts 同期删除, 删除前必跑 `tests/test_api_contract.py` (CLAUDE.md 强制)
- `app/api/knowledge/documents/upload/route.ts` + `batch/route.ts` + `ingest/upload/route.ts`: 全部保留 (multipart / 后台任务 / 服务端状态机不能 server action 化)

**删除** (3 个, P4 阶段统一处理):
```
lib/api/swr.ts                       # 整体删 (P4 阶段)
lib/api/swr-provider.tsx             # 整体删 (P4 阶段)
app/[locale]/providers.tsx           # 如有引用 SWRProvider 也要拆掉
app/api/knowledge/qa/route.ts        # P2 后变空壳, P4 评估删除 (必跑契约测试)
```

> 删除顺序: `lib/api/swr.ts` → `swr-provider.tsx` → 视情况删 `app/api/knowledge/qa/route.ts`, 每步必跑 `tests/test_api_contract.py` (CLAUDE.md 强制, 红了不能删)

---

## 设计 7 — 风险 & 回滚

### 风险矩阵

| # | 风险 | 等级 | 触发条件 | 缓解 |
|---|---|---|---|---|
| R1 | cookie 改造后老用户 localStorage token 失效 | 高 | 第一次访问无 cookie | 后端保留 header 回退; 前端加 migrate 端点 |
| R2 | RSC 拿数据时 token 过期 → 401 → SSR 抛 500 | 高 | cookie 过期/被清 | getServerToken 返空时仍调后端; 后端 401 时 RSC redirect("/login") |
| R3 | revalidatePath 失效粒度不够, 多个 dataset 切换串味 | 中 | RSC 缓存串味 | 阶段 4 评估: revalidateTag + queryKey 标签 |
| R4 | RQ staleTime: Infinity 跟 refetchInterval 配合 bug | 中 | 轮询不到 | 已验证 refetchInterval 不受 staleTime 影响; 测试跑 30s 观察 |
| R5 | server action 在 dev 热重载偶发"already registered" | 低 | dev 环境 | 不阻塞; production 不存在 |
| R6 | BFF 改 cookie 后 x-user-token 透传漏 | 中 | BFF 改完未测 | BFF 改完必跑 tests/test_api_contract.py (CLAUDE.md 强制) |
| R7 | root layout 预取 datasets / schemas 在大表下拉慢 | 中 | 未来列表变大 | 阶段 4 评估: datasets < 100 项, 不优化 |
| R8 | 切 dataset 时 RSC 重跑但 RQ client cache 未失效 → 数据不一致 | 高 | A+B 档混用 | router.refresh() 后 RQ 信任 RSC; A 档不挂 RQ |
| R9 | zustand persist 跟 SSR hydration 冲突 | 中 | localStorage 跟服务端不同步 | zustand persist 默认 SSR 跳过; client mount 后读 localStorage 覆盖 |
| R10 | 删 lib/api/swr.ts 后漏改某处 import | 高 | 漏掉某页面 | P4 阶段 bun run typecheck 兜底; git grep "from .*swr" 必须 0 命中 |

### 灰度策略

**P0** (认证): 后端 feature flag `LEGACY_AUTH_HEADERS=true` (默认) 保留回退
**P1** (A 档试点): datasets/page 改完保留旧 SWR 备份 1 天, 验证后删
**P2-P3** (批量): 每改一个 page 跑对应 test + E2E, 整体回滚靠 git revert
**P4** (删 swr): lib/api/swr.ts 改空 re-export 1 周, git grep 0 命中后删

### 回滚预案

| 失败点 | 回滚动作 | 时间 |
|---|---|---|
| P0 cookie 上线后 RSC 全 500 | 撤 cookie 提交 + 后端关 LEGACY_AUTH_HEADERS 回到 localStorage | 5 分钟 |
| P1 datasets 改造后页面错 | git revert 该 commit | 1 分钟 |
| P2-P3 批量失败 | git revert 整 stage commit (按 stage 1 个 PR) | 5 分钟 |
| P4 删 swr 后漏改某页 | bun install swr + 恢复 lib/api/swr.ts (git reflog) | 10 分钟 |

### 监控指标

**性能**:
- 首屏 LCP: Lighthouse 测 RSC 改造前后对比
  - A 档目标: LCP < 1.5s (去 SWR 首次请求后省 200-500ms)
- 客户端 JS 体积: `next build` 输出 `.next/static/chunks/*.js` 总和
  - 目标: A 档页面不加载 RQ 库 → 减少 12KB

**质量**:
- `bun run test` 全绿 (vitest)
- `bun run typecheck` 0 错 (tsgo)
- `bun run lint` 0 错 (oxlint)
- `tests/test_api_contract.py` 全绿 (CLAUDE.md 强制)
- E2E 18 个用例全过

**功能**:
- 切 dataset 后 RSC 重拉
- 后台 batch 任务轮询
- 登录态 (admin token) 不破坏
- 移动端 viewport 不破坏

### 已知接受 (不做的事)

| 事项 | 不做原因 |
|---|---|
| React Compiler | 本期不采用, 单独 spec |
| Server Actions 替代 BFF 上传 | multipart 复杂 |
| `unstable_cache` 跨请求共享 | 增加复杂度 |
| 后端 BFF route 改 server action | 不在范围 |
| 多语言翻译覆盖 | 不在范围 |
| 主题切换 | 不在范围 |
| ESLint / Prettier 配置 | 不在范围 |

---

## 阶段安排

| 阶段 | 内容 | 验证 |
|---|---|---|
| **P0** | 后端 Set-Cookie + CORS credentials; 前端 `auth.ts` 改写; BFF route 改读 cookie; 装 `@tanstack/react-query` | 现有 18 份测试继续过 |
| **P1** | A 档试点 1 页 (datasets): RSC 重写 + server action + 删 SWR | 1 个 e2e 通过; vitest 跑通 |
| **P2** | A 档剩 12 页全切 | 18 份 `.test.tsx` 重写完, 全绿 |
| **P3** | B 档 4 页: output / output/[id] / health / HealthDot, 引入 HydrationBoundary + RQ | 轮询 + 首屏直达测通 |
| **P4** | 删 `lib/api/swr.ts` + `lib/api/swr-provider.tsx`; package.json 删 `swr` | `bun run typecheck` 0 错; E2E 18 跑过 |

---

## 验收标准 (Definition of Done)

1. ✅ `git grep "from .*swr"` 0 命中 (源码 + 测试)
2. ✅ `package.json` 不含 `swr`, 含 `@tanstack/react-query@^5.62`
3. ✅ `lib/api/swr.ts` 和 `swr-provider.tsx` 已删
3b. ✅ (可选) `app/api/knowledge/qa/route.ts` 已删, 跑过 `tests/test_api_contract.py` 绿
4. ✅ `lib/api/auth.ts` 不再读 `localStorage` 的 `rag_user_token / rag_admin_token`
5. ✅ 13 个 A 档 page 是 server component (无 `"use client"` 顶部 directive)
6. ✅ 4 个 B 档 page 有 `HydrationBoundary` + `useQuery` + `refetchInterval`
7. ✅ 18 份 `.test.tsx` 全部跟着改造, vitest 全绿
8. ✅ 3 份 server action 测试 + 2 份 RQ utility 测试存在并绿
9. ✅ `tests/test_api_contract.py` 绿 (CLAUDE.md 强制)
10. ✅ E2E 18 个用例全过 (新增 1 个 RSC 首屏直达用例)
11. ✅ `bun run typecheck` 0 错
12. ✅ `bun run lint` 0 错
13. ✅ A 档页面在 root layout 不挂 `QueryClientProvider` (devtools Network 面板验证)
14. ✅ 切 dataset 用 `router.refresh()`, 无新 fetch (Network 面板验证)

---

## 附录: 关键文件依赖图

```
RSC page
  ├─ getServerToken()          ← lib/api/auth.ts (server)
  ├─ getRscQueryClient()       ← lib/api/rsc-queries.ts (server-only)
  ├─ prefetchQuery(qc, key, url)  ← 同上
  └─ <HydrationBoundary state={dehydrate(qc)}>
       └─ <ClientTable />       ← use client
            └─ useQuery({ queryKey: qKeys.x.list() })
                 └─ queryFn → lib/api/{domain}.ts (client fetch)

server action (_actions/*.ts)
  ├─ getServerToken()          ← 同一个 server util
  ├─ fetch(API_BASE, { headers: { x-user-token: token } })
  └─ revalidatePath("/[locale]/knowledge/qa")

BFF route (app/api/.../route.ts)
  ├─ cookies() → token
  └─ fetch(API_BASE, { headers: { x-user-token: token } })
```
