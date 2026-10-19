# Web 前端架构优化: 业务 API 客户端层 + 知识库 Tab 路由化

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Date:** 2026-06-10
**Status:** Approved (待实施)
**Scope:** 2 块 — `lib/api/<领域>.ts` 业务客户端层重构 + `/knowledge` Tab 路由化 (`/knowledge/documents` + `/knowledge/graph`)

## 背景

`docs/to-do.md` 滚动条待办 2026-06-09 commit `dfa85ca` 已修复, 从 to-do 划掉. 本 spec 只覆盖上 2 块.

## Goal

把"页面直接 `fetch('/api/...')` 满天飞 + BFF 全转发 + 知识库 Tab 状态机" 改成:
1. **`lib/api/<领域>.ts` 一文件一领域**: 导出 `knowledgeApi` / `chatApi` / `evaluateApi` 等业务客户端对象, 调用方 0 行鉴权代码
2. **`/knowledge` Tab 路由化**: 拆 2 个完整子页 `/knowledge/documents` + `/knowledge/graph`, URL 即真理, 浏览器历史/分享/刷新都自然
3. **BFF 瘦身**: 只保留"需服务端资源" 4 类 (Dify Chatflow / 鉴权后多用户数据 / multipart / 流式), 其他直连 FastAPI

## User Story

1. 开发者打开 `/knowledge` → 自动 redirect 到 `/knowledge/documents`, 看到向量库 dashboard
2. 点顶部 "知识图谱" Tab → URL 变 `/knowledge/graph`, 浏览器历史加一条
3. 后退 → 回到 `/knowledge/documents`, 数据不丢 (SWR 缓存)
4. 复制 `/knowledge/graph` 给同事 → 同事打开也是知识图谱, 不是默认页
5. 业务团队加新功能 "知识库订阅" → 1 个 `lib/api/knowledge.ts` 加 1 个方法即可, 不用碰页面

## Architecture

```
Browser
  ↓
app/knowledge/
  page.tsx            # redirect("/knowledge/documents")
  documents/page.tsx  # 向量库 (原 Tab "dify" 内容)
  graph/page.tsx      # 知识图谱 (原 Tab "neo4j" 内容)
  ↓ 调用
lib/api/knowledge.ts  # knowledgeApi.fetchStats / fetchQADocuments / createQA / ...
  ↓ 拆 2 路:
  ├── 直连 FastAPI:    fetch('http://localhost:8000/api/...')  # 统计 / 列表 (无 multipart, 非流式, 无 Dify 调用)
  └── 经 Next BFF:     fetch('/api/knowledge/...')            # Dify Chatflow / 鉴权后多用户数据 / multipart / 流式
  ↓
app/api/knowledge/    # 只保留需服务端资源的 (具体清单见 [BFF 边界](#bff-边界))
  ↓
FastAPI / Dify
```

### 关键边界: `lib/api/` vs `lib/dify-datasets.ts`

| 路径 | 层 | 用途 | 端用户 |
|---|---|---|---|
| `lib/api/<领域>.ts` | 浏览器端业务客户端 | 调 FastAPI / Next BFF | 页面组件 |
| `lib/dify-datasets.ts` | 服务端 Dify SDK 封装 | 服务端代码 (BFF) 调 Dify API | 不直接被页面用 |
| `lib/api/swr.ts` | SWR fetcher + 全局配置 | 浏览器端 useApi hook | 页面组件 |
| `lib/api/auth.ts` | 鉴权头工具 | 浏览器端读 localStorage token | lib/api/* 内部用 |

**两套不能跨层 import**:
- `lib/api/*` **不能** import `lib/dify-datasets.ts` (前者是浏览器, 后者应只在服务端)
- `lib/dify-datasets.ts` **不能** import `lib/api/*` (后者是浏览器)

## BFF 边界

**保留** (需服务端资源):

| 路径 | 理由 |
|---|---|
| `app/api/knowledge/qa/retrieve/route.ts` | 服务端调 Dify retriever (API key 不暴露) |
| `app/api/knowledge/documents/upload/route.ts` | multipart 大文件上传, 服务端中转 |
| `app/api/knowledge/batch/route.ts` | 后台任务启动, 服务端持有 run_id |
| `app/api/chat/messages/route.ts` | Dify Chatflow 流式响应 (SSE) |
| `app/api/evaluate/runs/route.ts` (含 [id] 和 cancel) | multipart CSV 上传 + 鉴权后多用户数据 |
| `app/api/evaluate/template/route.ts` | 无鉴权模板下载, 保留 (静态生成可放 public/) |

**裁掉** (页面直连 FastAPI, 走 CORS):
- `app/api/knowledge/datasets/route.ts` (只转发)
- `app/api/knowledge/documents/commit/route.ts` (调 FastAPI, 无 Dify)
- `app/api/knowledge/health/route.ts` (healthcheck)
- `app/api/knowledge/nodes/route.ts` (Neo4j 列表)
- `app/api/knowledge/qa/route.ts` (QA 列表/写入)
- `app/api/knowledge/relations/route.ts` (Neo4j 关系)
- `app/api/knowledge/schema*/route.ts` (Dify schema 查询)
- `app/api/knowledge/segments/route.ts` (segments 列表)
- `app/api/knowledge/stats/route.ts` (统计聚合)

> 注意: `app/api/knowledge/templates/[format]/route.ts` 是 Excel/JSON 模板下载, 留 **public/templates/** 静态文件, 裁 BFF.

裁掉的 BFF 文件直接删除, 不留 stub.

## `lib/api/<领域>.ts` 模式

**1 文件 1 领域, 1 个导出对象**:

```ts
// web/lib/api/knowledge.ts
import { getUserToken, getAdminToken, authHeaders } from "./auth";

const BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

/** 纯 URL 工厂: 给 useApi(SWR) 用 */
export const knowledgeApi = {
  statsUrl: (domain?: string) =>
    domain ? `/api/knowledge/stats?domain=${domain}` : "/api/knowledge/stats",
  qaListUrl: (datasetId: string) => `/api/knowledge/qa?dataset_id=${datasetId}`,

  /** 表单提交 (一次性) */
  createQA: async (input: QAInput): Promise<QA> => {
    const r = await fetch(`${BASE}/api/knowledge/qa`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeaders() },
      body: JSON.stringify(input),
    });
    if (!r.ok) throw await toApiError(r);
    return r.json();
  },

  /** 走 BFF (multipart) */
  uploadDocument: async (file: File, datasetId: string): Promise<UploadResult> => {
    const fd = new FormData();
    fd.append("file", file);
    fd.append("dataset_id", datasetId);
    const r = await fetch("/api/knowledge/documents/upload", {
      method: "POST",
      headers: authHeaders(),
      body: fd,
    });
    if (!r.ok) throw await toApiError(r);
    return r.json();
  },

  /** 走 BFF (Dify 调用) */
  retrieveQA: async (question: string, datasetId: string): Promise<RetrieveResult> => {
    const r = await fetch("/api/knowledge/qa/retrieve", {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeaders() },
      body: JSON.stringify({ question, dataset_id: datasetId, top_k: 3 }),
    });
    if (!r.ok) throw await toApiError(r);
    return r.json();
  },
};
```

**`lib/api/auth.ts`**:

```ts
// 浏览器端鉴权头工具 — 跟 evaluate/lib/evaluate/headers.ts 模式一致
export function getUserToken(): string {
  return typeof window === "undefined" ? "" : localStorage.getItem("rag_user_token") ?? "";
}
export function getAdminToken(): string {
  return typeof window === "undefined" ? "" : localStorage.getItem("rag_admin_token") ?? "";
}
export function authHeaders(): Record<string, string> {
  const out: Record<string, string> = {};
  const user = getUserToken();
  const admin = getAdminToken();
  if (admin) out["x-admin-token"] = admin;
  else if (user) out["x-user-token"] = user;
  return out;
}
```

**`lib/api/swr.ts` 升级**:

```ts
// 现有 fetcher 加鉴权头 (之前只加 x-chat-token, 漏 x-user-token / x-admin-token)
import { authHeaders } from "./auth";
export const fetcher = async (url: string) => {
  const r = await fetch(url, { headers: authHeaders() });
  if (!r.ok) {
    const text = await r.text();
    throw new Error(`HTTP ${r.status}: ${text || url}`);
  }
  return r.json();
};
```

### SWR vs fetch 选择

| 场景 | 用什么 | 理由 |
|---|---|---|
| 列表/统计 (要缓存/轮询) | `useApi(knowledgeApi.xUrl())` (SWR) | 自动 dedupe + `refreshInterval` + 错误重试 |
| 表单提交 (一次性) | `await knowledgeApi.createQA(input)` | 一次性, 无需缓存 |
| 流式 (SSE) | `await chatApi.sendMessage(...)` 拿 ReadableStream | SWR 不支持流 |
| Multipart | `await knowledgeApi.uploadDocument(file)` 走 BFF | 浏览器 fetch 默认支持, BFF 处理 API key |

## 知识库 Tab 路由化

### 目录

```
app/knowledge/
├── page.tsx              # redirect("/knowledge/documents")
├── documents/page.tsx    # 向量库 (原 Tab "dify" 内容)
└── graph/page.tsx        # 知识图谱 (原 Tab "neo4j" 内容)
```

### `/knowledge/page.tsx` (壳)

```tsx
import { redirect } from "next/navigation";
export default function KnowledgeIndex() {
  redirect("/knowledge/documents");
}
```

### `components/knowledge/KnowledgeTabs.tsx` (替换 shadcn Tabs)

```tsx
"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";

export function KnowledgeTabs() {
  const pathname = usePathname();
  return (
    <nav className="flex gap-1 border-b border-border/60">
      {[
        { href: "/knowledge/documents", label: "向量库" },
        { href: "/knowledge/graph", label: "知识图谱" },
      ].map((t) => (
        <Link
          key={t.href}
          href={t.href}
          className={cn(
            "px-4 py-2 text-sm transition-colors",
            pathname.startsWith(t.href) ? "border-b-2 border-clay text-foreground" : "text-muted-foreground hover:text-foreground"
          )}
        >
          {t.label}
        </Link>
      ))}
    </nav>
  );
}
```

### 抽出的组件 (`web/components/knowledge/`)

| 文件 | 状态 | 职责 |
|---|---|---|
| `StatCard.tsx` | 移动 (现 `app/knowledge/`) | 统计卡 |
| `EntryCard.tsx` | 移动 (现 `app/knowledge/`) | 入口卡 |
| `KnowledgeHero.tsx` | 新抽 | Stagger + eyebrow + display title (2 页共用) |
| `KnowledgeEmptyState.tsx` | 新抽 | 3 个示例链接 (走子路由) |
| `KnowledgeTabs.tsx` | 新建 | 上面代码 |

> 现状: `StatCard` / `EntryCard` 已经存在 (在 `app/knowledge/`), 仅**移动**到 `components/knowledge/`.

## Error Handling

| 错误类型 | 来源 | 处理 |
|---|---|---|
| `ApiError(status, detail)` | `lib/api.ts` 已 export, HTTP 4xx/5xx 抛 | 透传给 `useApi` 调用方 |
| `NetworkError(msg)` | 网络断 / CORS / timeout, 已 export | `useApi` 兜底 toast |
| 401 Unauthorized | 后端鉴权失败 | `useApi` onError 默认: toast "登录过期, 请重试" |
| 5xx Server | 后端崩 | `useApi` onError 默认: toast "服务异常, 请稍后" |
| 4xx 表单 | 提交时 zod 校验失败 | 调用方 `try/catch`, 渲染到现有 `submitResult` 红框 |
| SSE 流式中断 | `chatApi.sendMessage` 返回 body 关闭 | 调用方 `reader.read()` 判 done, 渲染 "连接中断" |

**`useApi` 加默认 `onError`**:

```ts
export function useApi<T>(url: string | null, config?: SWRConfiguration) {
  return useSWR<T>(url, fetcher, {
    ...swrConfig,
    ...config,
    onError: (err) => {
      if (err instanceof ApiError && err.status === 401) {
        toast.error("登录过期, 请重试");
      } else {
        toast.error(`加载失败: ${err.message}`);
      }
      config?.onError?.(err);
    },
  });
}
```

## File Structure (新建/修改/删除)

### 新建

```
web/lib/api/
├── auth.ts              # getUserToken / getAdminToken / authHeaders
├── knowledge.ts         # knowledgeApi (核心)
├── chat.ts              # chatApi (从 lib/api.ts 移过来)
├── evaluate.ts          # evaluateApi (从 evaluate/lib/evaluate/headers.ts 抽出业务方法)
├── auth.test.ts
├── knowledge.test.ts
├── chat.test.ts
└── evaluate.test.ts

web/components/knowledge/
├── StatCard.tsx         # 从 app/knowledge/ 移过来
├── EntryCard.tsx        # 从 app/knowledge/ 移过来
├── KnowledgeHero.tsx
├── KnowledgeEmptyState.tsx
├── KnowledgeTabs.tsx
└── KnowledgeTabs.test.tsx

web/app/knowledge/
├── page.tsx             # 改: redirect
├── documents/page.tsx   # 改: 用 knowledgeApi + KnowledgeTabs + KnowledgeHero
├── graph/page.tsx       # 改: 用 knowledgeApi + KnowledgeTabs + KnowledgeHero
├── documents/page.test.tsx
├── graph/page.test.tsx
└── page.test.tsx        # 测 redirect

web/e2e/
└── 05-knowledge-routes.spec.ts  # 新: 路由化 E2E
```

### 修改

```
web/lib/api/swr.ts                  # fetcher 加 authHeaders
web/lib/api.ts                      # 删 (在实施顺序 4 后删: 改由 lib/api/chat.ts + lib/api/auth.ts 接管)
web/app/knowledge/documents/page.tsx (旧, 合并到 documents/page.tsx)  # 删
```

### 删除 (BFF 瘦身)

```
web/app/api/knowledge/datasets/route.ts
web/app/api/knowledge/documents/commit/route.ts
web/app/api/knowledge/health/route.ts
web/app/api/knowledge/nodes/route.ts
web/app/api/knowledge/qa/route.ts
web/app/api/knowledge/relations/route.ts
web/app/api/knowledge/schemas/route.ts
web/app/api/knowledge/schema/route.ts
web/app/api/knowledge/segments/route.ts
web/app/api/knowledge/stats/route.ts
web/app/api/knowledge/stats/route.test.ts
web/app/api/knowledge/templates/[format]/route.ts  (改 public 静态)
```

> 删前先 `grep -r "from '@/app/api/knowledge/stats'" web/` 确认 0 调用, 再删.

## 测试策略

### 单元 (vitest + jsdom, 文件跟实现同目录)

| 文件 | 用例 |
|---|---|
| `web/lib/api/auth.test.ts` | localStorage mock: 有 token 返 token; 无 token 返空; SSR 时返空; admin 优先 |
| `web/lib/api/knowledge.test.ts` | mock fetch: 鉴权头注入 (user/admin); URL 拼接 query; 4xx/5xx 抛 ApiError; 网络错抛 NetworkError |
| `web/lib/api/chat.test.ts` | mock fetch: 流式 body 透传; 鉴权头注入 |
| `web/lib/api/evaluate.test.ts` | mock fetch: multipart 走 BFF; x-user-token + x-admin-token 切换 |
| `web/lib/api/swr.test.ts` | mock useSWR: useApi 错误 onError 触发 |
| `web/components/knowledge/KnowledgeTabs.test.tsx` | mock usePathname: active 状态判断; Link href 正确 |

### 组件 (`*.page.test.tsx`)

| 文件 | 用例 |
|---|---|
| `web/app/knowledge/page.test.tsx` | mock redirect: 测调用了 redirect("/knowledge/documents") |
| `web/app/knowledge/documents/page.test.tsx` | mock useApi 注入数据: 渲染 StatCard + EntryCard + KnowledgeTabs (active=documents) |
| `web/app/knowledge/graph/page.test.tsx` | mock useApi: 渲染 StatCard + EntryCard + KnowledgeTabs (active=graph) |

### E2E (Playwright)

`web/e2e/05-knowledge-routes.spec.ts`:
1. 进 `/knowledge` → URL 跳 `/knowledge/documents`
2. 点 "知识图谱" → URL 跳 `/knowledge/graph`, 浏览器历史 +1
3. 浏览器后退 → 回到 `/knowledge/documents`, 数据不重请求 (网络面板 0 新请求)
4. 复制 `/knowledge/graph` 粘到新 tab → 直接打开知识图谱, 不经 redirect
5. 现有 18 E2E 全绿 (vitest + playwright run)

### 覆盖目标

- `web/lib/api/*.ts` ≥ 80% (跟 `src/rag/eval/*` 一样)
- 新组件 ≥ 60%
- 现有 18 E2E 不掉 (`--grep` 跑评估 / 知识库 / 解析 / 输出 4 块)

## 风险与缓解

| 风险 | 缓解 |
|---|---|
| BFF 裁了页面还在用 | 实施前先 `grep` 全量调用方, 列清单, 一次切完 |
| 路由化后知识库子页面跟现有 E2E 选择器冲突 | E2E 选择器用 `data-testid` 改唯一名, 不复用 `qa-list` 等通用名 |
| shadcn `<Tabs>` 跟 `<Link>` 双轨状态撕裂 | 全面换 `KnowledgeTabs`, shadcn Tabs 在 knowledge 页不 import |
| CORS 直连 FastAPI 漏配 | 后端已配 `http://localhost:3000` CORS (查 CORS middleware); 实施后用 `curl` 验证 |
| multipart 走 BFF 改了路径 | `app/api/knowledge/documents/upload` 保留, 文档列保留清单 |
| 删除 BFF 时误删 `route.test.ts` | 同步检查 `route.test.ts`, 一起删 |

## 跟现有代码兼容

**复用** (直接 import):
- `lib/api.ts` 已 export 的 `ApiError` / `NetworkError` (类型不变, 继续用)
- `lib/api/swr.ts` 的 `useApi` (升级 fetcher 加鉴权头)
- `components/evaluate/*` (evaluate 页 spec 已落地)
- `lib/evaluate/types.ts` / `lib/evaluate/headers.ts` (evaluate 业务不动, `lib/api/evaluate.ts` 引用)

**保留** (不重构):
- `lib/dify-datasets.ts` (服务端 Dify 封装, 跟 `lib/api/` 不交叉)
- `lib/store/` (zustand 状态)
- `app/chat/*` / `app/decode/*` / `app/output/*` (本次不动, 后续 spec)

**已删除 to-do 项**:
- `docs/to-do.md` 滚动条行 — 2026-06-09 commit `dfa85ca` 已修, 划掉.

## 实施顺序

1. **`lib/api/auth.ts` + `auth.test.ts`** — 鉴权头工具先行, 后续 `knowledge.ts` / `chat.ts` / `evaluate.ts` 都依赖
2. **`lib/api/swr.ts` 升级 fetcher** — 加 authHeaders, 不破坏现有调用
3. **`lib/api/knowledge.ts` + test** — 核心业务客户端, TDD
4. **`lib/api/chat.ts` + test** — 从 `lib/api.ts` 移过来, 加 authHeaders
5. **`lib/api/evaluate.ts` + test** — 跟 `lib/evaluate/headers.ts` 桥接
6. **页面切到 `knowledgeApi`** — knowledge 子页 + decode/chat/evaluate 4 个域按需切
7. **BFF 裁剪** — 按清单删 11 个 route.ts, 删前 grep 验证
8. **knowledge Tab 路由化** — 拆 `page.tsx` 为 documents / graph, 抽 KnowledgeTabs
9. **E2E 05-knowledge-routes** — 路由化冒烟

**依赖关系**: 1→2→3→4→5 可并行, 6 依赖 1-5, 7 依赖 6, 8 独立可与 6 并行, 9 依赖 8.

## Success Criteria

1. `lib/api/<领域>.ts` 5 个文件就位 (auth/knowledge/chat/evaluate + 1 swr), 每个有 `.test.ts`
2. 现有 18 E2E 全绿
3. 新增 E2E `05-knowledge-routes.spec.ts` 5 个用例全绿
4. `/knowledge/documents` + `/knowledge/graph` URL 独立访问, 浏览器历史/分享/刷新正常
5. `lib/api/*.ts` 单元测试覆盖率 ≥ 80%
6. BFF 裁剪 11 个 route.ts 删完, 无新调用方引用残留
7. `bun run typecheck` + `bun run lint` + `bun run test` 全绿
8. `docs/to-do.md` 滚动条行划掉
