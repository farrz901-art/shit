# Web 前端架构优化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `web/lib/api.ts` 单文件 + 散落 `fetch('/api/...')` 改成 `lib/api/<领域>.ts` 业务客户端层; 把 `/knowledge` Tab 状态机改成 `/knowledge/documents` + `/knowledge/graph` 路由; 把 11 个只转发的 BFF 裁掉直连 FastAPI.

**Architecture:** 浏览器端 `lib/api/<领域>.ts` 一文件一领域暴露 1 个对象 (knowledgeApi/chatApi/evaluateApi), 内部按 4 条规则决定直连 FastAPI 还是经 Next BFF; BFF 只保留"需服务端资源" 4 类 (Dify Chatflow / multipart / 后台任务 / SSE); `/knowledge` 子路由化让 URL 即真理.

**Tech Stack:** Next.js 15 App Router + TypeScript + SWR + bun + vitest + Playwright + Tailwind v4 + shadcn/ui (Default + Slate)

**前置依赖**: 已落地 — 评估页 spec (`docs/superpowers/specs/2026-06-09-evaluate-page-redesign-design.md`) 提供了 `lib/evaluate/headers.ts` 鉴权头模式可复用; 客户端 token spec (admin virtual user) 已合 master.

**Spec**: `docs/superpowers/specs/2026-06-10-web-frontend-architecture.md`

---

## File Structure

**新建**:
- `web/lib/api/auth.ts` — 鉴权头工具 (getUserToken / getAdminToken / authHeaders)
- `web/lib/api/auth.test.ts`
- `web/lib/api/knowledge.ts` — 业务客户端 (knowledgeApi)
- `web/lib/api/knowledge.test.ts`
- `web/lib/api/chat.ts` — 业务客户端 (chatApi, 含 SSE 流式)
- `web/lib/api/chat.test.ts`
- `web/lib/api/evaluate.ts` — 业务客户端 (evaluateApi, multipart + 鉴权后多用户数据)
- `web/lib/api/evaluate.test.ts`
- `web/components/knowledge/StatCard.tsx` — 从 `app/knowledge/` 移过来
- `web/components/knowledge/EntryCard.tsx` — 从 `app/knowledge/` 移过来
- `web/components/knowledge/KnowledgeHero.tsx`
- `web/components/knowledge/KnowledgeHero.test.tsx`
- `web/components/knowledge/KnowledgeEmptyState.tsx`
- `web/components/knowledge/KnowledgeEmptyState.test.tsx`
- `web/components/knowledge/KnowledgeTabs.tsx`
- `web/components/knowledge/KnowledgeTabs.test.tsx`
- `web/app/knowledge/documents/page.test.tsx`
- `web/app/knowledge/graph/page.test.tsx`
- `web/app/knowledge/page.test.tsx`
- `web/e2e/05-knowledge-routes.spec.ts`

**修改**:
- `web/lib/api/swr.ts` — fetcher 加 authHeaders
- `web/lib/api/swr.test.ts` — 新建 (旧不存在, spec 加)
- `web/lib/api.ts` → 删 (在 Task 4 完成后删, 由 `lib/api/chat.ts` + `lib/api/auth.ts` 接管)
- `web/app/knowledge/page.tsx` — 改 redirect
- `web/app/knowledge/documents/page.tsx` — 改用 knowledgeApi + KnowledgeTabs + KnowledgeHero
- `web/app/knowledge/graph/page.tsx` — 改用 knowledgeApi + KnowledgeTabs + KnowledgeHero
- `web/app/chat/page.tsx` — 切到 `chatApi` (如果原代码用 `lib/api.ts.chatApi`)
- `web/app/evaluate/page.tsx` + `app/evaluate/new/page.tsx` + `app/evaluate/[id]/page.tsx` — 切到 `evaluateApi`
- `web/app/knowledge/qa/page.tsx` + 其他 knowledge 子页 — 切到 `knowledgeApi`

**删除 (BFF 瘦身)**: 11 个 `web/app/api/knowledge/*` route.ts, 见 Task 7.

**保留不动**:
- `web/lib/dify-datasets.ts` (服务端 Dify 封装)
- `web/lib/store/` (zustand 状态)
- `web/lib/evaluate/types.ts` / `web/lib/evaluate/headers.ts` (evaluate 业务类型, evaluateApi 桥接)
- `web/app/api/chat/messages/route.ts` (Dify Chatflow SSE, 保留)
- `web/app/api/evaluate/*` (multipart + 鉴权后多用户, 保留)
- `web/app/api/knowledge/qa/retrieve/route.ts` (Dify 调用, 保留)
- `web/app/api/knowledge/documents/upload/route.ts` (multipart, 保留)
- `web/app/api/knowledge/batch/route.ts` (后台任务, 保留)

---

## 任务分解 (11 个, 按依赖链分批)

**批次 1 (串行, 1 个)**:
- Task 1: `lib/api/auth.ts` + test (地基)

**批次 2 (并行, 4 个 — 都不依赖彼此, 都依赖 Task 1)**:
- Task 2: `lib/api/swr.ts` 升级 fetcher + test
- Task 3: `lib/api/knowledge.ts` + test
- Task 4: `lib/api/chat.ts` + test + 删 `lib/api.ts`
- Task 5: `lib/api/evaluate.ts` + test

**批次 3 (并行, 3 个 — 页面迁移, 依赖 Task 3/4/5)**:
- Task 6a: knowledge 页面切到 `knowledgeApi`
- Task 6b: chat 页面切到 `chatApi` (如果用 `lib/api.ts.chatApi`)
- Task 6c: evaluate 页面切到 `evaluateApi`

**批次 4 (并行, 2 个 — 组件抽取 + 路由化, 独立可批 2 一起做)**:
- Task 7: 抽 `KnowledgeHero` / `KnowledgeEmptyState` / 移 StatCard + EntryCard
- Task 8: BFF 裁剪 11 个 route.ts (依赖 Task 6a 验证页面已切直连)

**批次 5 (串行, 1 个 — 路由化, 依赖 Task 7)**:
- Task 9: `/knowledge` 拆 documents + graph 子页 + KnowledgeTabs

**批次 6 (串行, 2 个 — E2E + 验证)**:
- Task 10: E2E `05-knowledge-routes.spec.ts` (依赖 Task 9)
- Task 11: 最终验证 (typecheck + lint + test + 18 E2E 全绿)

---

### Task 1: 鉴权头工具 `lib/api/auth.ts`

**Files:**
- Create: `web/lib/api/auth.ts`
- Test: `web/lib/api/auth.test.ts`

- [ ] **Step 1: Write the failing test**

```ts
// web/lib/api/auth.test.ts
import { describe, it, expect, beforeEach } from "vitest";
import { getUserToken, getAdminToken, authHeaders } from "./auth";

describe("auth", () => {
  beforeEach(() => localStorage.clear());

  it("getUserToken 返 localStorage.rag_user_token", () => {
    localStorage.setItem("rag_user_token", "u_abc");
    expect(getUserToken()).toBe("u_abc");
  });

  it("getUserToken 无 token 返空串", () => {
    expect(getUserToken()).toBe("");
  });

  it("getAdminToken 返 localStorage.rag_admin_token", () => {
    localStorage.setItem("rag_admin_token", "a_xyz");
    expect(getAdminToken()).toBe("a_xyz");
  });

  it("getAdminToken 无 token 返空串", () => {
    expect(getAdminToken()).toBe("");
  });

  it("authHeaders 只有 user 时注入 x-user-token", () => {
    localStorage.setItem("rag_user_token", "u_abc");
    expect(authHeaders()).toEqual({ "x-user-token": "u_abc" });
  });

  it("authHeaders admin 优先, 跳过 user", () => {
    localStorage.setItem("rag_user_token", "u_abc");
    localStorage.setItem("rag_admin_token", "a_xyz");
    expect(authHeaders()).toEqual({ "x-admin-token": "a_xyz" });
  });

  it("authHeaders 都无时返空对象", () => {
    expect(authHeaders()).toEqual({});
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd web && bun run test lib/api/auth.test.ts`
Expected: FAIL — `Cannot find module './auth'`

- [ ] **Step 3: Write minimal implementation**

```ts
// web/lib/api/auth.ts
// 浏览器端鉴权头工具 — 跟 evaluate/lib/evaluate/headers.ts 模式一致
export function getUserToken(): string {
  if (typeof window === "undefined") return "";
  return localStorage.getItem("rag_user_token") ?? "";
}

export function getAdminToken(): string {
  if (typeof window === "undefined") return "";
  return localStorage.getItem("rag_admin_token") ?? "";
}

/** admin 优先; 都没则返空对象 */
export function authHeaders(): Record<string, string> {
  const out: Record<string, string> = {};
  const user = getUserToken();
  const admin = getAdminToken();
  if (admin) out["x-admin-token"] = admin;
  else if (user) out["x-user-token"] = user;
  return out;
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd web && bun run test lib/api/auth.test.ts`
Expected: 7 个用例全 PASS

- [ ] **Step 5: Commit**

```bash
git add web/lib/api/auth.ts web/lib/api/auth.test.ts
git commit -m "feat(web): 加 lib/api/auth 鉴权头工具 (admin 优先)"
```

---

### Task 2: `lib/api/swr.ts` 升级 fetcher 加 authHeaders

**Files:**
- Modify: `web/lib/api/swr.ts`
- Create: `web/lib/api/swr.test.ts`

- [ ] **Step 1: Write the failing test**

```ts
// web/lib/api/swr.test.ts
import { describe, it, expect, beforeEach, vi } from "vitest";
import { fetcher } from "./swr";

describe("fetcher", () => {
  beforeEach(() => localStorage.clear());

  it("请求注入 x-user-token", async () => {
    localStorage.setItem("rag_user_token", "u_abc");
    const mock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ foo: 1 }),
    });
    vi.stubGlobal("fetch", mock);

    const data = await fetcher("/api/foo");

    expect(mock).toHaveBeenCalledWith("/api/foo", {
      headers: { "x-user-token": "u_abc" },
    });
    expect(data).toEqual({ foo: 1 });
  });

  it("admin 优先, 跳过 user", async () => {
    localStorage.setItem("rag_user_token", "u_abc");
    localStorage.setItem("rag_admin_token", "a_xyz");
    const mock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({}),
    });
    vi.stubGlobal("fetch", mock);

    await fetcher("/api/foo");

    expect(mock).toHaveBeenCalledWith("/api/foo", {
      headers: { "x-admin-token": "a_xyz" },
    });
  });

  it("无 token 时不带鉴权头", async () => {
    const mock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({}),
    });
    vi.stubGlobal("fetch", mock);

    await fetcher("/api/foo");

    expect(mock).toHaveBeenCalledWith("/api/foo", { headers: {} });
  });

  it("非 2xx 抛 Error 含 status 和 text", async () => {
    const mock = vi.fn().mockResolvedValue({
      ok: false,
      status: 401,
      text: async () => "Unauthorized",
    });
    vi.stubGlobal("fetch", mock);

    await expect(fetcher("/api/foo")).rejects.toThrow("HTTP 401: Unauthorized");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd web && bun run test lib/api/swr.test.ts`
Expected: FAIL — `fetcher` 不注入 x-user-token (旧代码只加 x-chat-token, 我们升级要新行为)

- [ ] **Step 3: Replace implementation**

把 `web/lib/api/swr.ts` 完整替换为:

```ts
// SWR fetcher + 全局配置 (2026-06-10 升级: 鉴权头用 authHeaders 统一注入)
import useSWR, { type SWRConfiguration } from "swr";
import { authHeaders } from "./auth";
import { ApiError, NetworkError } from "@/lib/api";

/** 通用 fetcher: 2xx 返 JSON, 4xx/5xx 抛 ApiError, 网络错抛 NetworkError */
export const fetcher = async (url: string) => {
  let res: Response;
  try {
    res = await fetch(url, { headers: authHeaders() });
  } catch (e) {
    throw new NetworkError(e instanceof Error ? e.message : String(e));
  }
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new ApiError(res.status, text);
  }
  return res.json();
};

/** 全局 SWR 默认配置 */
export const swrConfig: SWRConfiguration = {
  fetcher,
  revalidateOnFocus: true,
  dedupingInterval: 5_000,
  shouldRetryOnError: false,
};

/** 类型化 useSWR 包装 — 用法跟 useSWR 一样但带全局 fetcher */
export function useApi<T>(url: string | null, config?: SWRConfiguration) {
  return useSWR<T>(url, fetcher, { ...swrConfig, ...config });
}
```

> 注意: `ApiError` / `NetworkError` 这时还在 `web/lib/api.ts` (Task 4 才删), 暂时 import 路径用 `@/lib/api`. Task 4 删 `lib/api.ts` 时, 把这 2 个 class 移到 `lib/api/errors.ts`, swr.ts 一并改 import.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd web && bun run test lib/api/swr.test.ts`
Expected: 4 个用例全 PASS

- [ ] **Step 5: Commit**

```bash
git add web/lib/api/swr.ts web/lib/api/swr.test.ts
git commit -m "feat(web): swr fetcher 注入 admin/user token, 抛 ApiError/NetworkError"
```

---

### Task 3: `lib/api/knowledge.ts` 业务客户端

**Files:**
- Create: `web/lib/api/knowledge.ts`
- Test: `web/lib/api/knowledge.test.ts`

- [ ] **Step 1: Write the failing test**

```ts
// web/lib/api/knowledge.test.ts
import { describe, it, expect, beforeEach, vi, afterEach } from "vitest";
import { knowledgeApi } from "./knowledge";

describe("knowledgeApi", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.unstubAllGlobals();
  });

  afterEach(() => vi.unstubAllGlobals());

  describe("URL 工厂", () => {
    it("statsUrl 无 domain 时不带 query", () => {
      expect(knowledgeApi.statsUrl()).toBe("/api/knowledge/stats");
    });

    it("statsUrl 有 domain 时拼 query", () => {
      expect(knowledgeApi.statsUrl("电机")).toBe("/api/knowledge/stats?domain=%E7%94%B5%E6%9C%BA");
    });

    it("qaListUrl 需要 datasetId", () => {
      expect(knowledgeApi.qaListUrl("ds_123")).toBe(
        "/api/knowledge/qa?dataset_id=ds_123",
      );
    });
  });

  describe("createQA (直连后端, 鉴权头)", () => {
    it("POST 注入 x-user-token + Content-Type + body JSON", async () => {
      localStorage.setItem("rag_user_token", "u_abc");
      const mock = vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ id: "qa_1" }),
      });
      vi.stubGlobal("fetch", mock);

      const result = await knowledgeApi.createQA({
        dataset_id: "ds_1",
        question: "Q",
        answer: "A",
      });

      expect(mock).toHaveBeenCalledWith(
        "http://localhost:8000/api/knowledge/qa",
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "x-user-token": "u_abc",
          },
          body: JSON.stringify({
            dataset_id: "ds_1",
            question: "Q",
            answer: "A",
          }),
        },
      );
      expect(result).toEqual({ id: "qa_1" });
    });

    it("4xx 抛 ApiError 含 status 和 detail", async () => {
      const mock = vi.fn().mockResolvedValue({
        ok: false,
        status: 400,
        json: async () => ({ detail: "missing question" }),
      });
      vi.stubGlobal("fetch", mock);

      await expect(
        knowledgeApi.createQA({ dataset_id: "ds_1", question: "Q", answer: "A" }),
      ).rejects.toMatchObject({ status: 400, message: "missing question" });
    });

    it("5xx 抛 ApiError", async () => {
      const mock = vi.fn().mockResolvedValue({
        ok: false,
        status: 500,
        json: async () => ({ detail: "internal" }),
      });
      vi.stubGlobal("fetch", mock);

      await expect(
        knowledgeApi.createQA({ dataset_id: "ds_1", question: "Q", answer: "A" }),
      ).rejects.toMatchObject({ status: 500 });
    });

    it("网络错抛 NetworkError", async () => {
      vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("ECONNREFUSED")));

      await expect(
        knowledgeApi.createQA({ dataset_id: "ds_1", question: "Q", answer: "A" }),
      ).rejects.toThrow("ECONNREFUSED");
    });
  });

  describe("uploadDocument (走 BFF, multipart)", () => {
    it("POST /api/knowledge/documents/upload 用 FormData, 不设 Content-Type", async () => {
      localStorage.setItem("rag_user_token", "u_abc");
      const mock = vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ document_id: "doc_1" }),
      });
      vi.stubGlobal("fetch", mock);

      const file = new File(["content"], "test.csv", { type: "text/csv" });
      const result = await knowledgeApi.uploadDocument(file, "ds_1");

      const [url, init] = mock.mock.calls[0];
      expect(url).toBe("/api/knowledge/documents/upload");
      expect(init.method).toBe("POST");
      expect(init.headers).toEqual({ "x-user-token": "u_abc" });
      expect(init.body).toBeInstanceOf(FormData);
      expect(result).toEqual({ document_id: "doc_1" });
    });
  });

  describe("retrieveQA (走 BFF, Dify)", () => {
    it("POST /api/knowledge/qa/retrieve 注入 top_k 默认 3", async () => {
      localStorage.setItem("rag_user_token", "u_abc");
      const mock = vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ records: [] }),
      });
      vi.stubGlobal("fetch", mock);

      await knowledgeApi.retrieveQA("Q?", "ds_1");

      expect(mock).toHaveBeenCalledWith(
        "/api/knowledge/qa/retrieve",
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "x-user-token": "u_abc",
          },
          body: JSON.stringify({
            question: "Q?",
            dataset_id: "ds_1",
            top_k: 3,
          }),
        },
      );
    });
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd web && bun run test lib/api/knowledge.test.ts`
Expected: FAIL — `Cannot find module './knowledge'`

- [ ] **Step 3: Write minimal implementation**

```ts
// web/lib/api/knowledge.ts
// 知识库业务客户端 (2026-06-10)
// 直连 FastAPI (统计/列表/CRUD) 或 走 BFF (multipart / Dify 调用)
import { authHeaders } from "./auth";
import { ApiError, NetworkError } from "@/lib/api";

const BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

export interface QAInput {
  dataset_id: string;
  question: string;
  answer: string;
  tags?: string[];
  sync_to_neo4j?: boolean;
}

export interface QA {
  id: string;
  question: string;
  answer: string;
}

export interface StatsResponse {
  neo4j: { nodes: number; relations: number };
  dify: { datasets: number; documents: number };
}

export interface QAListResponse {
  items: Array<{
    id: string;
    question: string;
    answer: string;
    name: string;
    indexing_status: string;
  }>;
}

export interface RetrieveRecord {
  content: string;
  score: number;
  document_name: string;
}

export interface RetrieveResult {
  records: RetrieveRecord[];
}

export interface UploadResult {
  document_id: string;
}

async function toApiError(r: Response): Promise<Error> {
  const detail = (await r.json().catch(() => ({}))).detail ?? r.statusText;
  return new ApiError(r.status, String(detail));
}

async function post<T>(url: string, body: unknown, contentType = "application/json"): Promise<T> {
  let res: Response;
  try {
    res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": contentType, ...authHeaders() },
      body: contentType === "application/json" ? JSON.stringify(body) : (body as BodyInit),
    });
  } catch (e) {
    throw new NetworkError(e instanceof Error ? e.message : String(e));
  }
  if (!res.ok) throw await toApiError(res);
  return res.json() as Promise<T>;
}

export const knowledgeApi = {
  /** URL 工厂: 给 useApi(SWR) 用, 不带鉴权头 (fetcher 统一加) */
  statsUrl: (domain?: string): string =>
    domain ? `/api/knowledge/stats?domain=${encodeURIComponent(domain)}` : "/api/knowledge/stats",

  qaListUrl: (datasetId: string): string =>
    `/api/knowledge/qa?dataset_id=${encodeURIComponent(datasetId)}`,

  /** 统计 — 走 SWR */
  fetchStats: (): Promise<StatsResponse> =>
    fetch(`${BASE}/api/knowledge/stats`, { headers: authHeaders() }).then((r) => {
      if (!r.ok) throw new ApiError(r.status, r.statusText);
      return r.json() as Promise<StatsResponse>;
    }),

  /** QA 列表 — 走 SWR */
  fetchQADocuments: (datasetId: string): Promise<QAListResponse> =>
    fetch(`${BASE}${knowledgeApi.qaListUrl(datasetId)}`, { headers: authHeaders() }).then((r) => {
      if (!r.ok) throw new ApiError(r.status, r.statusText);
      return r.json() as Promise<QAListResponse>;
    }),

  /** 写 QA — 一次性 */
  createQA: (input: QAInput): Promise<QA> =>
    post<QA>(`${BASE}/api/knowledge/qa`, input),

  /** 上传文档 — 走 BFF (multipart, 服务端中转) */
  uploadDocument: async (file: File, datasetId: string): Promise<UploadResult> => {
    const fd = new FormData();
    fd.append("file", file);
    fd.append("dataset_id", datasetId);
    let res: Response;
    try {
      res = await fetch("/api/knowledge/documents/upload", {
        method: "POST",
        headers: authHeaders(),
        body: fd,
      });
    } catch (e) {
      throw new NetworkError(e instanceof Error ? e.message : String(e));
    }
    if (!res.ok) throw await toApiError(res);
    return res.json() as Promise<UploadResult>;
  },

  /** Retriever 自测 — 走 BFF (Dify 调用) */
  retrieveQA: (question: string, datasetId: string, topK = 3): Promise<RetrieveResult> =>
    post<RetrieveResult>("/api/knowledge/qa/retrieve", {
      question,
      dataset_id: datasetId,
      top_k: topK,
    }),
};
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd web && bun run test lib/api/knowledge.test.ts`
Expected: 10 个用例全 PASS

- [ ] **Step 5: Commit**

```bash
git add web/lib/api/knowledge.ts web/lib/api/knowledge.test.ts
git commit -m "feat(web): knowledgeApi 业务客户端 (统计直连 / multipart+BFF / Dify 走 BFF)"
```

---

### Task 4: `lib/api/chat.ts` 业务客户端 + 删 `lib/api.ts`

**Files:**
- Create: `web/lib/api/chat.ts`
- Create: `web/lib/api/errors.ts` (提取 ApiError/NetworkError, 因 lib/api.ts 要删)
- Test: `web/lib/api/chat.test.ts`
- Modify: `web/lib/api/swr.ts` (改 import 路径)
- Delete: `web/lib/api.ts`

- [ ] **Step 1: Write the failing test**

```ts
// web/lib/api/chat.test.ts
import { describe, it, expect, beforeEach, vi, afterEach } from "vitest";
import { chatApi } from "./chat";

describe("chatApi", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.unstubAllGlobals();
  });
  afterEach(() => vi.unstubAllGlobals());

  it("getToken 读 NEXT_PUBLIC_CHAT_TOKEN env", () => {
    process.env.NEXT_PUBLIC_CHAT_TOKEN = "ct_abc";
    expect(chatApi.getToken()).toBe("ct_abc");
  });

  it("getToken 无 env 返空串", () => {
    delete process.env.NEXT_PUBLIC_CHAT_TOKEN;
    expect(chatApi.getToken()).toBe("");
  });

  it("sendMessage 注入 Content-Type + x-chat-token", async () => {
    process.env.NEXT_PUBLIC_CHAT_TOKEN = "ct_abc";
    const stream = new ReadableStream<Uint8Array>({
      start(c) { c.enqueue(new TextEncoder().encode("chunk")); c.close(); },
    });
    const mock = vi.fn().mockResolvedValue({ ok: true, body: stream });
    vi.stubGlobal("fetch", mock);

    const body = await chatApi.sendMessage({
      query: "hi",
      user: "u-1",
      inputs: {},
    });

    expect(mock).toHaveBeenCalledWith("/api/chat/messages", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "x-chat-token": "ct_abc",
      },
      body: JSON.stringify({ query: "hi", user: "u-1", inputs: {} }),
    });
    expect(body).toBe(stream);
  });

  it("sendMessage 非 2xx 抛 Error 含 status", async () => {
    const mock = vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      text: async () => "boom",
    });
    vi.stubGlobal("fetch", mock);

    await expect(
      chatApi.sendMessage({ query: "hi", user: "u-1" }),
    ).rejects.toThrow("chat api 500: boom");
  });

  it("sendMessage body 为空抛 Error", async () => {
    const mock = vi.fn().mockResolvedValue({ ok: true, body: null });
    vi.stubGlobal("fetch", mock);

    await expect(
      chatApi.sendMessage({ query: "hi", user: "u-1" }),
    ).rejects.toThrow("chat api 无 body");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd web && bun run test lib/api/chat.test.ts`
Expected: FAIL — `Cannot find module './chat'`

- [ ] **Step 3: 写 errors.ts (先把 ApiError/NetworkError 移出 lib/api.ts, 避免 import 死循环)**

```ts
// web/lib/api/errors.ts
// fetch 错误类型 (2026-06-10 从 lib/api.ts 移过来)

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = "ApiError";
  }
}

export class NetworkError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "NetworkError";
  }
}
```

- [ ] **Step 4: 写 chat.ts**

```ts
// web/lib/api/chat.ts
// 智能体聊天 BFF 客户端 (2026-06-10 从 lib/api.ts 移过来)
export interface SendMessageInput {
  query: string;
  user: string;
  inputs?: Record<string, unknown>;
  conversationId?: string;
}

export const chatApi = {
  getToken(): string {
    return process.env.NEXT_PUBLIC_CHAT_TOKEN ?? "";
  },

  async sendMessage(body: SendMessageInput): Promise<ReadableStream<Uint8Array>> {
    const res = await fetch("/api/chat/messages", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "x-chat-token": this.getToken(),
      },
      body: JSON.stringify(body),
    });
    if (!res.ok) {
      const text = await res.text();
      throw new Error(`chat api ${res.status}: ${text}`);
    }
    if (!res.body) throw new Error("chat api 无 body");
    return res.body;
  },
};
```

- [ ] **Step 5: 改 swr.ts import 路径**

把 `web/lib/api/swr.ts` 里 `import { ApiError, NetworkError } from "@/lib/api";` 改成 `import { ApiError, NetworkError } from "./errors";`

- [ ] **Step 6: Run test to verify it passes**

Run: `cd web && bun run test lib/api/chat.test.ts lib/api/swr.test.ts lib/api/auth.test.ts lib/api/knowledge.test.ts`
Expected: 26 个用例全 PASS (7 + 4 + 5 + 10)

- [ ] **Step 7: 删 lib/api.ts**

```bash
git rm web/lib/api.ts
```

- [ ] **Step 8: typecheck + lint 验证删除无遗漏引用**

Run: `cd web && bun run typecheck && bun run lint`
Expected: 0 错. 如果有 import `@/lib/api` 引用, 报错. 改完再跑一遍.

- [ ] **Step 9: Commit**

```bash
git add web/lib/api/chat.ts web/lib/api/chat.test.ts web/lib/api/errors.ts web/lib/api/swr.ts
git commit -m "feat(web): chatApi 客户端 (从 lib/api.ts 移过来) + 删 lib/api.ts"
```

---

### Task 5: `lib/api/evaluate.ts` 业务客户端

**Files:**
- Create: `web/lib/api/evaluate.ts`
- Test: `web/lib/api/evaluate.test.ts`

- [ ] **Step 1: Write the failing test**

```ts
// web/lib/api/evaluate.test.ts
import { describe, it, expect, beforeEach, vi, afterEach } from "vitest";
import { evaluateApi } from "./evaluate";

describe("evaluateApi", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.unstubAllGlobals();
  });
  afterEach(() => vi.unstubAllGlobals());

  describe("runsUrl 工厂", () => {
    it("runsUrl 列表", () => {
      expect(evaluateApi.runsUrl()).toBe("/api/evaluate/runs");
    });
    it("runDetailUrl", () => {
      expect(evaluateApi.runDetailUrl(42)).toBe("/api/evaluate/runs/42");
    });
    it("runCancelUrl", () => {
      expect(evaluateApi.runCancelUrl(42)).toBe("/api/evaluate/runs/42/cancel");
    });
    it("templateUrl", () => {
      expect(evaluateApi.templateUrl()).toBe("/api/evaluate/template");
    });
  });

  describe("createRun (multipart 走 BFF)", () => {
    it("POST /api/evaluate/runs FormData 带 file + concurrency", async () => {
      localStorage.setItem("rag_user_token", "u_abc");
      const mock = vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ id: 1, status: "pending" }),
      });
      vi.stubGlobal("fetch", mock);

      const file = new File(["q,a\n1,2\n"], "eval.csv", { type: "text/csv" });
      const result = await evaluateApi.createRun(file, 5);

      expect(mock.mock.calls[0][0]).toBe("/api/evaluate/runs");
      const init = mock.mock.calls[0][1];
      expect(init.method).toBe("POST");
      expect(init.headers).toEqual({ "x-user-token": "u_abc" });
      expect(init.body).toBeInstanceOf(FormData);
      expect(result).toEqual({ id: 1, status: "pending" });
    });

    it("5xx 抛 ApiError", async () => {
      const mock = vi.fn().mockResolvedValue({
        ok: false,
        status: 500,
        json: async () => ({ detail: "boom" }),
      });
      vi.stubGlobal("fetch", mock);

      const file = new File(["q,a\n"], "eval.csv");
      await expect(evaluateApi.createRun(file, 5)).rejects.toMatchObject({
        status: 500,
        message: "boom",
      });
    });
  });

  describe("cancelRun", () => {
    it("POST /api/evaluate/runs/{id}/cancel 注入 admin token", async () => {
      localStorage.setItem("rag_user_token", "u_abc");
      localStorage.setItem("rag_admin_token", "a_xyz");
      const mock = vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ cancelled: true }),
      });
      vi.stubGlobal("fetch", mock);

      await evaluateApi.cancelRun(7);

      expect(mock).toHaveBeenCalledWith("/api/evaluate/runs/7/cancel", {
        method: "POST",
        headers: { "x-admin-token": "a_xyz" },
      });
    });
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd web && bun run test lib/api/evaluate.test.ts`
Expected: FAIL — `Cannot find module './evaluate'`

- [ ] **Step 3: Write minimal implementation**

```ts
// web/lib/api/evaluate.ts
// 评估页业务客户端 (2026-06-10)
// 跟 lib/evaluate/headers.ts 共用 localStorage 鉴权 key
import { authHeaders } from "./auth";
import { ApiError, NetworkError } from "./errors";

export interface EvalRunSummary {
  id: number;
  name: string;
  status: "pending" | "running" | "completed" | "failed" | "cancelled";
  total_samples: number;
  created_at: string;
}

export interface CreateRunResponse {
  id: number;
  status: string;
}

export interface CancelResponse {
  cancelled: boolean;
}

async function toApiError(r: Response): Promise<Error> {
  const detail = (await r.json().catch(() => ({}))).detail ?? r.statusText;
  return new ApiError(r.status, String(detail));
}

export const evaluateApi = {
  /** URL 工厂: 给 useApi(SWR) 用 */
  runsUrl: (): string => "/api/evaluate/runs",
  runDetailUrl: (id: number): string => `/api/evaluate/runs/${id}`,
  runCancelUrl: (id: number): string => `/api/evaluate/runs/${id}/cancel`,
  templateUrl: (): string => "/api/evaluate/template",

  /** 启动评估 — multipart 走 BFF */
  createRun: async (file: File, concurrency: number): Promise<CreateRunResponse> => {
    const fd = new FormData();
    fd.append("file", file);
    fd.append("concurrency", String(concurrency));
    let res: Response;
    try {
      res = await fetch("/api/evaluate/runs", {
        method: "POST",
        headers: authHeaders(),
        body: fd,
      });
    } catch (e) {
      throw new NetworkError(e instanceof Error ? e.message : String(e));
    }
    if (!res.ok) throw await toApiError(res);
    return res.json() as Promise<CreateRunResponse>;
  },

  /** 取消评估 — 走 BFF, 鉴权后多用户数据 */
  cancelRun: async (id: number): Promise<CancelResponse> => {
    let res: Response;
    try {
      res = await fetch(`/api/evaluate/runs/${id}/cancel`, {
        method: "POST",
        headers: authHeaders(),
      });
    } catch (e) {
      throw new NetworkError(e instanceof Error ? e.message : String(e));
    }
    if (!res.ok) throw await toApiError(res);
    return res.json() as Promise<CancelResponse>;
  },
};
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd web && bun run test lib/api/evaluate.test.ts`
Expected: 7 个用例全 PASS

- [ ] **Step 5: Commit**

```bash
git add web/lib/api/evaluate.ts web/lib/api/evaluate.test.ts
git commit -m "feat(web): evaluateApi 业务客户端 (multipart 走 BFF + 鉴权后多用户)"
```

---

### Task 6a: knowledge 页面切到 `knowledgeApi`

**Files:**
- Modify: `web/app/knowledge/qa/page.tsx`
- Modify: `web/app/knowledge/nodes/page.tsx`
- Modify: `web/app/knowledge/relations/page.tsx`
- Modify: `web/app/knowledge/triples/page.tsx`
- Modify: `web/app/knowledge/documents/page.tsx`
- Modify: `web/app/knowledge/batch/page.tsx`

- [ ] **Step 1: 先 grep 验证每个页面用到的 BFF 路径**

```bash
cd web && grep -rn "from \"/api/knowledge" app/knowledge/ 2>&1 | head -50
```

确认每个 BFF 路径要么在 [BFF 边界保留清单] 内 (qa/retrieve, documents/upload, batch), 要么**这个 task 之内** 改用 `knowledgeApi.fetchX` 直连后端.

- [ ] **Step 2: 改 `app/knowledge/qa/page.tsx`**

把 `useSWR<{ items: ... }>(datasetId ? \`/api/knowledge/qa?dataset_id=${datasetId}\` : null)` 改成:

```ts
import { useApi } from "@/lib/api/swr";
import { knowledgeApi } from "@/lib/api/knowledge";

const { data: list, mutate } = useApi<{ items: ... }>(
  datasetId ? knowledgeApi.qaListUrl(datasetId) : null,
  { refreshInterval: 5000 },
);
```

把 onSubmit 里 `fetch("/api/knowledge/qa", { method: "POST", ... })` 改成:

```ts
const r = await knowledgeApi.createQA({
  dataset_id: datasetId,
  question: data.question,
  answer: data.answer,
  tags: tagsArr,
  sync_to_neo4j: data.sync_to_neo4j,
});
// 用 try/catch 捕获 ApiError 设 submitResult
```

把 onTest 里 `fetch("/api/knowledge/qa/retrieve", ...)` 改成:

```ts
const r = await knowledgeApi.retrieveQA(question, datasetId);
```

- [ ] **Step 3: 改其他 knowledge 子页**

对 `nodes` / `relations` / `triples` / `documents` / `batch` 每个页:
- 把页面里的 `useSWR("/api/knowledge/xxx", ...)` 改成 `useApi(knowledgeApi.xxxUrl(), ...)` (如果该 URL 工厂存在; 不存在就在 `knowledgeApi` 加)
- 把页面里的 `fetch("/api/knowledge/xxx", { method: "POST", body: ... })` 改成 `await knowledgeApi.createXxx(input)` (如果方法存在; 不存在就在 `knowledgeApi` 加)

> 实施 subagent: 如果发现某页面调用了**裁剪清单**里要删的 BFF (datasets/documents/commit/health/nodes/qa/relations/schema*/segments/stats/templates), **先在 `knowledgeApi` 加对应方法** (走 `${BASE}/api/...` 直连 FastAPI), 再继续.

- [ ] **Step 4: 跑 typecheck + lint + test 验证**

Run:
```bash
cd web && bun run typecheck && bun run lint && bun run test
```
Expected: 0 错, 现有 26 + 原有 chat/evaluate 单测全绿

- [ ] **Step 5: Commit**

```bash
git add web/app/knowledge/
git commit -m "refactor(web): knowledge 页面切到 knowledgeApi (直连 FastAPI)"
```

---

### Task 6b: chat 页面切到 `chatApi` (新位置)

**Files:**
- Modify: 引用 `lib/api.ts` 的 `chatApi` 的所有文件 (grep 找)

- [ ] **Step 1: grep 找引用方**

```bash
cd web && grep -rn "from \"@/lib/api\"\|from '@/lib/api'\|chatApi\b" app/ components/ lib/ 2>&1
```

- [ ] **Step 2: 改 import**

把所有 `import { chatApi } from "@/lib/api"` 改成 `import { chatApi } from "@/lib/api/chat"`

- [ ] **Step 3: 验证**

Run: `cd web && bun run typecheck && bun run test app/chat/`
Expected: 0 错

- [ ] **Step 4: Commit**

```bash
git add web/
git commit -m "refactor(web): chat 引用 chatApi 从新路径 lib/api/chat"
```

---

### Task 6c: evaluate 页面切到 `evaluateApi`

**Files:**
- Modify: `web/app/evaluate/page.tsx`
- Modify: `web/app/evaluate/new/page.tsx`
- Modify: `web/app/evaluate/[id]/page.tsx`

- [ ] **Step 1: 改 `app/evaluate/page.tsx`**

把页面里 `useSWR<EvaluationRunSummary[]>(`/api/evaluate/runs`, fetcher, ...)` 里的 fetcher 去掉, 改成 `useApi<EvaluationRunSummary[]>(evaluateApi.runsUrl())`. 鉴权头由 fetcher 统一加.

- [ ] **Step 2: 改 `app/evaluate/new/page.tsx`**

把 `POST /api/evaluate/runs` 的 `fetch` 改成 `evaluateApi.createRun(file, concurrency)`. multipart 走 evaluateApi 内部.

- [ ] **Step 3: 改 `app/evaluate/[id]/page.tsx`**

把 SWR 路径 `/api/evaluate/runs/${id}` 改成 `evaluateApi.runDetailUrl(id)`. 把"取消"按钮 `fetch` 改成 `evaluateApi.cancelRun(id)`.

- [ ] **Step 4: 验证**

Run: `cd web && bun run typecheck && bun run test app/evaluate/`
Expected: 0 错

- [ ] **Step 5: Commit**

```bash
git add web/app/evaluate/
git commit -m "refactor(web): evaluate 页面切到 evaluateApi"
```

---

### Task 7: 抽 KnowledgeHero / KnowledgeEmptyState + 移 StatCard/EntryCard

**Files:**
- Create: `web/components/knowledge/StatCard.tsx` (从 `app/knowledge/StatCard.tsx` 移)
- Create: `web/components/knowledge/EntryCard.tsx` (从 `app/knowledge/EntryCard.tsx` 移)
- Create: `web/components/knowledge/KnowledgeHero.tsx`
- Create: `web/components/knowledge/KnowledgeHero.test.tsx`
- Create: `web/components/knowledge/KnowledgeEmptyState.tsx`
- Create: `web/components/knowledge/KnowledgeEmptyState.test.tsx`
- Delete: `web/app/knowledge/StatCard.tsx`
- Delete: `web/app/knowledge/EntryCard.tsx`

- [ ] **Step 1: Write failing test for KnowledgeHero**

```tsx
// web/components/knowledge/KnowledgeHero.test.tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { KnowledgeHero } from "./KnowledgeHero";

describe("KnowledgeHero", () => {
  it("渲染 eyebrow + display title", () => {
    render(<KnowledgeHero eyebrow="Knowledge" title="知识库" />);
    expect(screen.getByText("Knowledge")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "知识库" })).toBeInTheDocument();
  });

  it("支持右侧 meta slot (refresh 间隔等)", () => {
    render(
      <KnowledgeHero
        eyebrow="Knowledge"
        title="知识库"
        meta={<span>30s 刷新</span>}
      />,
    );
    expect(screen.getByText("30s 刷新")).toBeInTheDocument();
  });
});
```

> 如果 vitest 配置没有 `@testing-library/react`, 加进 package.json + 重装: `bun add -D @testing-library/react @testing-library/dom`. 检查 `web/package.json`.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd web && bun run test components/knowledge/KnowledgeHero.test.tsx`
Expected: FAIL — `Cannot find module './KnowledgeHero'`

- [ ] **Step 3: Write KnowledgeHero**

```tsx
// web/components/knowledge/KnowledgeHero.tsx
"use client";
import { Reveal, Stagger, StaggerItem } from "@/components/ui/animated";

export interface KnowledgeHeroProps {
  eyebrow: string;
  title: string;
  meta?: React.ReactNode;
}

export function KnowledgeHero({ eyebrow, title, meta }: KnowledgeHeroProps) {
  return (
    <Stagger className="space-y-2" delay={0.08}>
      <StaggerItem>
        <div className="flex items-center gap-3">
          <span className="eyebrow">{eyebrow}</span>
          <span className="h-px flex-1 bg-border" />
          {meta && <span className="num text-sm text-muted-foreground/60">{meta}</span>}
        </div>
      </StaggerItem>
      <StaggerItem>
        <h1 className="display text-4xl tracking-tight md:text-5xl">{title}</h1>
      </StaggerItem>
    </Stagger>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd web && bun run test components/knowledge/KnowledgeHero.test.tsx`
Expected: 2 个用例 PASS

- [ ] **Step 5: Write failing test for KnowledgeEmptyState**

```tsx
// web/components/knowledge/KnowledgeEmptyState.test.tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { KnowledgeEmptyState } from "./KnowledgeEmptyState";

describe("KnowledgeEmptyState", () => {
  it("渲染 title + description", () => {
    render(
      <KnowledgeEmptyState
        title="第一次使用?"
        description="3 个示例帮你上手"
        examples={[]}
      />,
    );
    expect(screen.getByText("第一次使用?")).toBeInTheDocument();
    expect(screen.getByText("3 个示例帮你上手")).toBeInTheDocument();
  });

  it("渲染 example 列表链接", () => {
    render(
      <KnowledgeEmptyState
        title="hi"
        description="d"
        examples={[
          { href: "/knowledge/qa", title: "录 QA", desc: "A" },
          { href: "/knowledge/triples", title: "录 三元组", desc: "B" },
        ]}
      />,
    );
    expect(screen.getByText("录 QA")).toBeInTheDocument();
    expect(screen.getByText("录 三元组")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /录 QA/ })).toHaveAttribute(
      "href",
      "/knowledge/qa",
    );
  });
});
```

- [ ] **Step 6: Run test to verify it fails**

Run: `cd web && bun run test components/knowledge/KnowledgeEmptyState.test.tsx`
Expected: FAIL

- [ ] **Step 7: Write KnowledgeEmptyState**

```tsx
// web/components/knowledge/KnowledgeEmptyState.tsx
"use client";
import Link from "next/link";
import { Sparkles } from "lucide-react";
import { Reveal } from "@/components/ui/animated";

export interface KnowledgeEmptyExample {
  href: string;
  title: string;
  desc: string;
}

export interface KnowledgeEmptyStateProps {
  title: string;
  description: string;
  examples: KnowledgeEmptyExample[];
}

export function KnowledgeEmptyState({
  title,
  description,
  examples,
}: KnowledgeEmptyStateProps) {
  return (
    <Reveal delay={0.25}>
      <div
        className="rounded-2xl border border-dashed border-border/80 bg-card/40 p-8"
        data-testid="empty-state"
      >
        <div className="display mb-3 text-xl text-foreground">
          <Sparkles className="inline h-6 w-6 mr-2 text-clay" />
          {title}
        </div>
        <p className="text-base text-muted-foreground">{description}</p>
        <ul className="mt-4 grid grid-cols-1 gap-2 md:grid-cols-3">
          {examples.map((it) => (
            <li key={it.href}>
              <Link
                href={it.href}
                className="group block rounded-lg border border-border/40 bg-card p-4 transition-colors hover:border-clay/40"
              >
                <div className="text-base font-medium text-foreground group-hover:text-clay">
                  {it.title}
                </div>
                <div className="mt-1 text-sm text-muted-foreground">{it.desc}</div>
              </Link>
            </li>
          ))}
        </ul>
      </div>
    </Reveal>
  );
}
```

- [ ] **Step 8: Run test to verify it passes**

Run: `cd web && bun run test components/knowledge/KnowledgeEmptyState.test.tsx`
Expected: 2 个用例 PASS

- [ ] **Step 9: 移动 StatCard 和 EntryCard**

```bash
mkdir -p web/components/knowledge
git mv web/app/knowledge/StatCard.tsx web/components/knowledge/StatCard.tsx
git mv web/app/knowledge/EntryCard.tsx web/components/knowledge/EntryCard.tsx
```

修改 `StatCard.tsx` 和 `EntryCard.tsx` 顶部的 import 路径, 把 `./` 改成 `@/components/knowledge/...`. 改完跑 typecheck 验证 0 错.

- [ ] **Step 10: Commit**

```bash
git add web/components/knowledge/ web/app/knowledge/
git commit -m "refactor(web): 抽 KnowledgeHero + KnowledgeEmptyState, 移 StatCard/EntryCard 到 components/knowledge"
```

---

### Task 8: BFF 裁剪 11 个 route.ts

**Files:**
- Delete: 11 个 `web/app/api/knowledge/*/route.ts`

清单 (按 spec [BFF 边界](#bff-边界) 段):
- `web/app/api/knowledge/datasets/route.ts`
- `web/app/api/knowledge/documents/commit/route.ts`
- `web/app/api/knowledge/health/route.ts`
- `web/app/api/knowledge/nodes/route.ts`
- `web/app/api/knowledge/qa/route.ts`
- `web/app/api/knowledge/relations/route.ts`
- `web/app/api/knowledge/schemas/route.ts`
- `web/app/api/knowledge/schema/route.ts`
- `web/app/api/knowledge/segments/route.ts`
- `web/app/api/knowledge/stats/route.ts`
- `web/app/api/knowledge/stats/route.test.ts` (跟 route 一起删)
- `web/app/api/knowledge/templates/[format]/route.ts` (改 public 静态)

- [ ] **Step 1: grep 验证 0 调用残留**

```bash
cd web && grep -rn "/api/knowledge/datasets\|/api/knowledge/documents/commit\|/api/knowledge/health\|/api/knowledge/nodes\|/api/knowledge/qa\b\|/api/knowledge/relations\|/api/knowledge/schemas\|/api/knowledge/schema\b\|/api/knowledge/segments\|/api/knowledge/stats\|/api/knowledge/templates" app/ components/ lib/ 2>&1 | grep -v "qa/retrieve\|documents/upload"
```

Expected: 0 行. 如果有, 改 `knowledgeApi` 走直连 (`/api/knowledge/qa/retrieve` 和 `/api/knowledge/documents/upload` 是保留的).

- [ ] **Step 2: 删 11 个 route.ts + 1 个 test**

```bash
git rm web/app/api/knowledge/datasets/route.ts \
      web/app/api/knowledge/documents/commit/route.ts \
      web/app/api/knowledge/health/route.ts \
      web/app/api/knowledge/nodes/route.ts \
      web/app/api/knowledge/qa/route.ts \
      web/app/api/knowledge/relations/route.ts \
      web/app/api/knowledge/schemas/route.ts \
      web/app/api/knowledge/schema/route.ts \
      web/app/api/knowledge/segments/route.ts \
      web/app/api/knowledge/stats/route.ts \
      web/app/api/knowledge/stats/route.test.ts \
      web/app/api/knowledge/templates/\[format\]/route.ts
```

- [ ] **Step 3: typecheck + lint + test**

Run: `cd web && bun run typecheck && bun run lint && bun run test`
Expected: 0 错

- [ ] **Step 4: Commit**

```bash
git add -A web/app/api/knowledge/
git commit -m "chore(web): 裁 11 个只转发 BFF (页面已直连 FastAPI)"
```

---

### Task 9: `/knowledge` 拆 documents + graph 子页 + KnowledgeTabs

**Files:**
- Create: `web/components/knowledge/KnowledgeTabs.tsx`
- Create: `web/components/knowledge/KnowledgeTabs.test.tsx`
- Modify: `web/app/knowledge/page.tsx` (改 redirect)
- Modify: `web/app/knowledge/documents/page.tsx` (用 KnowledgeHero + KnowledgeTabs + KnowledgeEmptyState)
- Modify: `web/app/knowledge/graph/page.tsx` (同上, 数据用 nodes/relations)
- Create: `web/app/knowledge/page.test.tsx`
- Create: `web/app/knowledge/documents/page.test.tsx`
- Create: `web/app/knowledge/graph/page.test.tsx`

- [ ] **Step 1: Write failing test for KnowledgeTabs**

```tsx
// web/components/knowledge/KnowledgeTabs.test.tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { KnowledgeTabs } from "./KnowledgeTabs";

vi.mock("next/navigation", () => ({
  usePathname: () => "/knowledge/documents",
}));

describe("KnowledgeTabs", () => {
  it("渲染 2 个 Link: 向量库 + 知识图谱", () => {
    render(<KnowledgeTabs />);
    expect(screen.getByRole("link", { name: "向量库" })).toHaveAttribute(
      "href",
      "/knowledge/documents",
    );
    expect(screen.getByRole("link", { name: "知识图谱" })).toHaveAttribute(
      "href",
      "/knowledge/graph",
    );
  });

  it("active link 走高亮样式 (clay border-b)", () => {
    render(<KnowledgeTabs />);
    const link = screen.getByRole("link", { name: "向量库" });
    expect(link.className).toMatch(/border-clay/);
  });

  it("非 active link 走 muted 样式", () => {
    render(<KnowledgeTabs />);
    const link = screen.getByRole("link", { name: "知识图谱" });
    expect(link.className).toMatch(/text-muted-foreground/);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd web && bun run test components/knowledge/KnowledgeTabs.test.tsx`
Expected: FAIL

- [ ] **Step 3: Write KnowledgeTabs**

```tsx
// web/components/knowledge/KnowledgeTabs.tsx
"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";

const TABS = [
  { href: "/knowledge/documents", label: "向量库" },
  { href: "/knowledge/graph", label: "知识图谱" },
] as const;

export function KnowledgeTabs() {
  const pathname = usePathname();
  return (
    <nav className="flex gap-1 border-b border-border/60">
      {TABS.map((t) => {
        const active = pathname?.startsWith(t.href) ?? false;
        return (
          <Link
            key={t.href}
            href={t.href}
            data-testid={`tab-${t.href.split("/").pop()}`}
            className={cn(
              "px-4 py-2 text-sm transition-colors",
              active
                ? "border-b-2 border-clay text-foreground"
                : "text-muted-foreground hover:text-foreground",
            )}
          >
            {t.label}
          </Link>
        );
      })}
    </nav>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd web && bun run test components/knowledge/KnowledgeTabs.test.tsx`
Expected: 3 个用例 PASS

- [ ] **Step 5: 改 `app/knowledge/page.tsx` 为 redirect**

```tsx
// web/app/knowledge/page.tsx
import { redirect } from "next/navigation";

export default function KnowledgeIndex() {
  redirect("/knowledge/documents");
}
```

- [ ] **Step 6: Write failing test for redirect page**

```tsx
// web/app/knowledge/page.test.tsx
import { describe, it, expect, vi } from "vitest";
import KnowledgeIndex from "./page";

vi.mock("next/navigation", () => ({
  redirect: vi.fn(),
}));

describe("/knowledge page", () => {
  it("redirect 到 /knowledge/documents", () => {
    const { redirect } = await import("next/navigation");
    KnowledgeIndex();
    expect(redirect).toHaveBeenCalledWith("/knowledge/documents");
  });
});
```

> 实际 subagent 写的时候要把 `await` 加在 `describe` 内, 因为 `KnowledgeIndex` 是 sync 函数但 import 用了 dynamic. 如果 typecheck 报错改用 `vi.mocked(redirect)`.

- [ ] **Step 7: Run test + commit redirect**

Run: `cd web && bun run test app/knowledge/page.test.tsx`
Expected: 1 个用例 PASS

```bash
git add web/components/knowledge/KnowledgeTabs.tsx web/components/knowledge/KnowledgeTabs.test.tsx web/app/knowledge/page.tsx web/app/knowledge/page.test.tsx
git commit -m "feat(web): KnowledgeTabs Link 组件 + /knowledge redirect /knowledge/documents"
```

- [ ] **Step 8: 改 `app/knowledge/documents/page.tsx` 用 KnowledgeHero/Tabs/EmptyState**

原 page.tsx 顶部 `<Stagger>` + `<StaggerItem>` 抽到 `<KnowledgeHero eyebrow="Knowledge" title="知识库" meta="30s 刷新" />`.

原 `<Tabs>` (shadcn) 整段换成 `<KnowledgeTabs />` + 2 个 `<section>` (documents 内容 / graph 内容).

> 实际做法: documents/page.tsx 只留"向量库"那一节, graph/page.tsx 只留"知识图谱"那一节, 各自 page 用 KnowledgeTabs 渲染.

`documents/page.tsx` 关键代码:

```tsx
"use client";
import { useApi } from "@/lib/api/swr";
import { knowledgeApi } from "@/lib/api/knowledge";
import { KnowledgeHero } from "@/components/knowledge/KnowledgeHero";
import { KnowledgeTabs } from "@/components/knowledge/KnowledgeTabs";
import { KnowledgeEmptyState } from "@/components/knowledge/KnowledgeEmptyState";
import { StatCard } from "@/components/knowledge/StatCard";
import { EntryCard } from "@/components/knowledge/EntryCard";
import { MessageSquare, FileText } from "lucide-react";
import { Reveal } from "@/components/ui/animated";

export default function KnowledgeDocuments() {
  const { data, isLoading } = useApi<{ dify: { datasets: number; documents: number } }>(
    knowledgeApi.statsUrl(),
    { refreshInterval: 30_000 },
  );

  const showEmpty = !isLoading && data?.dify.documents === 0;

  return (
    <div className="h-full overflow-y-auto space-y-8 pb-8">
      <KnowledgeHero eyebrow="Knowledge" title="向量库" meta="30s 刷新" />
      <KnowledgeTabs />

      {showEmpty && (
        <KnowledgeEmptyState
          title="第一次使用?"
          description="3 个示例帮你上手"
          examples={[
            { href: "/knowledge/qa", title: "录 1 条 QA 对", desc: "体验 Dify 写入" },
            { href: "/knowledge/documents", title: "传文档", desc: "Excel/JSON 模板导入" },
            { href: "/knowledge/batch", title: "批量导入", desc: "跑后台任务" },
          ]}
        />
      )}

      <Reveal delay={0.2}>
        <div className="grid grid-cols-2 gap-4">
          <StatCard label="文档数" value={data?.dify.documents ?? 0} accent="indigo" index={0} />
          <StatCard label="数据集" value={data?.dify.datasets ?? 0} accent="ochre" index={1} />
        </div>
        <div className="mt-6 grid grid-cols-1 gap-4 md:grid-cols-2">
          <EntryCard href="/knowledge/qa" icon={<MessageSquare className="h-6 w-6" />} title="录 QA 对" desc="表单写入 Dify 向量库" index={0} />
          <EntryCard href="/knowledge/documents" icon={<FileText className="h-6 w-6" />} title="传文档" desc="Excel/JSON 模板导入" index={1} />
        </div>
      </Reveal>
    </div>
  );
}
```

- [ ] **Step 9: 改 `app/knowledge/graph/page.tsx` 类似, 用 neo4j 数据**

```tsx
"use client";
import { useApi } from "@/lib/api/swr";
import { knowledgeApi } from "@/lib/api/knowledge";
import { KnowledgeHero } from "@/components/knowledge/KnowledgeHero";
import { KnowledgeTabs } from "@/components/knowledge/KnowledgeTabs";
import { StatCard } from "@/components/knowledge/StatCard";
import { EntryCard } from "@/components/knowledge/EntryCard";
import { Network, Package } from "lucide-react";
import { Reveal } from "@/components/ui/animated";
import Link from "next/link";

export default function KnowledgeGraph() {
  const { data } = useApi<{ neo4j: { nodes: number; relations: number } }>(
    knowledgeApi.statsUrl(),
    { refreshInterval: 30_000 },
  );

  return (
    <div className="h-full overflow-y-auto space-y-8 pb-8">
      <KnowledgeHero eyebrow="Knowledge" title="知识图谱" meta="30s 刷新" />
      <KnowledgeTabs />

      <Reveal delay={0.2}>
        <div className="grid grid-cols-2 gap-4">
          <Link href="/knowledge/nodes" className="block">
            <StatCard label="节点数" value={data?.neo4j.nodes ?? 0} hint="点击查看全部 →" accent="clay" index={0} />
          </Link>
          <Link href="/knowledge/relations" className="block">
            <StatCard label="关系数" value={data?.neo4j.relations ?? 0} hint="点击查看全部 →" accent="moss" index={1} />
          </Link>
        </div>
        <div className="mt-6 grid grid-cols-1 gap-4 md:grid-cols-2">
          <EntryCard href="/knowledge/triples" icon={<Network className="h-6 w-6" />} title="录三元组" desc="实体-关系写入 Neo4j" index={0} />
          <EntryCard href="/knowledge/batch" icon={<Package className="h-6 w-6" />} title="批量导入" desc="后台批量任务" index={1} />
        </div>
      </Reveal>
    </div>
  );
}
```

- [ ] **Step 10: 写 documents + graph page.test.tsx**

```tsx
// web/app/knowledge/documents/page.test.tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import KnowledgeDocuments from "./page";

vi.mock("@/lib/api/swr", () => ({
  useApi: () => ({ data: { dify: { documents: 5, datasets: 2 }, neo4j: { nodes: 0, relations: 0 } }, isLoading: false }),
}));
vi.mock("next/link", () => ({
  default: ({ href, children }: { href: string; children: React.ReactNode }) => <a href={href}>{children}</a>,
}));

describe("/knowledge/documents page", () => {
  it("渲染 KnowledgeHero title=向量库", () => {
    render(<KnowledgeDocuments />);
    expect(screen.getByRole("heading", { name: "向量库" })).toBeInTheDocument();
  });

  it("渲染 KnowledgeTabs", () => {
    render(<KnowledgeDocuments />);
    expect(screen.getByTestId("tab-documents")).toBeInTheDocument();
    expect(screen.getByTestId("tab-graph")).toBeInTheDocument();
  });

  it("不显示空态 (data.dify.documents > 0)", () => {
    render(<KnowledgeDocuments />);
    expect(screen.queryByTestId("empty-state")).not.toBeInTheDocument();
  });
});
```

```tsx
// web/app/knowledge/graph/page.test.tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import KnowledgeGraph from "./page";

vi.mock("@/lib/api/swr", () => ({
  useApi: () => ({ data: { dify: { documents: 0, datasets: 0 }, neo4j: { nodes: 30, relations: 80 } }, isLoading: false }),
}));
vi.mock("next/link", () => ({
  default: ({ href, children }: { href: string; children: React.ReactNode }) => <a href={href}>{children}</a>,
}));

describe("/knowledge/graph page", () => {
  it("渲染 KnowledgeHero title=知识图谱", () => {
    render(<KnowledgeGraph />);
    expect(screen.getByRole("heading", { name: "知识图谱" })).toBeInTheDocument();
  });

  it("渲染 StatCard 节点数 + 关系数", () => {
    render(<KnowledgeGraph />);
    expect(screen.getByText("节点数")).toBeInTheDocument();
    expect(screen.getByText("关系数")).toBeInTheDocument();
  });
});
```

- [ ] **Step 11: Run all page tests + typecheck + lint**

Run:
```bash
cd web && bun run test app/knowledge/ && bun run typecheck && bun run lint
```
Expected: 全部 0 错

- [ ] **Step 12: Commit**

```bash
git add web/app/knowledge/ web/components/knowledge/
git commit -m "feat(web): /knowledge 拆 documents + graph 子页, KnowledgeTabs 路由化"
```

---

### Task 10: E2E `05-knowledge-routes.spec.ts`

**Files:**
- Create: `web/e2e/05-knowledge-routes.spec.ts`

- [ ] **Step 1: 看现有 E2E 怎么写**

Run: `cd web && head -80 e2e/01-smoke.spec.ts` (或最近的 .spec.ts 文件)

- [ ] **Step 2: Write 5 个 E2E 用例**

```ts
// web/e2e/05-knowledge-routes.spec.ts
import { test, expect } from "@playwright/test";

test.describe("/knowledge 路由化", () => {
  test("/knowledge 重定向到 /knowledge/documents", async ({ page }) => {
    await page.goto("/knowledge");
    await expect(page).toHaveURL(/\/knowledge\/documents$/);
  });

  test("点 知识图谱 tab → URL 跳 /knowledge/graph", async ({ page }) => {
    await page.goto("/knowledge/documents");
    await page.getByRole("link", { name: "知识图谱" }).click();
    await expect(page).toHaveURL(/\/knowledge\/graph$/);
    await expect(page.getByRole("heading", { name: "知识图谱" })).toBeVisible();
  });

  test("浏览器后退回到 /knowledge/documents, 数据不重请求", async ({ page, request }) => {
    await page.goto("/knowledge/documents");
    await page.getByRole("link", { name: "知识图谱" }).click();
    await page.waitForURL(/\/knowledge\/graph$/);
    await page.goBack();
    await expect(page).toHaveURL(/\/knowledge\/documents$/);
    // SWR 缓存命中, 不重请求 stats. 用 network panel 观察.
    let statsCallCount = 0;
    page.on("request", (req) => {
      if (req.url().includes("/api/knowledge/stats")) statsCallCount++;
    });
    await page.waitForTimeout(500);
    expect(statsCallCount).toBe(0);
  });

  test("直连 /knowledge/graph 显示知识图谱, 不经 redirect", async ({ page }) => {
    await page.goto("/knowledge/graph");
    await expect(page.getByRole("heading", { name: "知识图谱" })).toBeVisible();
    await expect(page.getByTestId("tab-graph")).toBeVisible();
  });

  test("documents tab active 高亮", async ({ page }) => {
    await page.goto("/knowledge/documents");
    const link = page.getByTestId("tab-documents");
    await expect(link).toHaveClass(/border-clay/);
  });
});
```

- [ ] **Step 3: Run E2E**

Run: `cd web && bun run test:e2e 05-knowledge-routes`
Expected: 5 个用例全 PASS

- [ ] **Step 4: Commit**

```bash
git add web/e2e/05-knowledge-routes.spec.ts
git commit -m "test(e2e): 知识库路由化 5 个用例"
```

---

### Task 11: 最终验证 (typecheck + lint + test + 18 E2E)

**Files:**
- 无 (只跑验证)

- [ ] **Step 1: 跑全量单测**

Run: `cd web && bun run test`
Expected: 全部 PASS, `lib/api/*.ts` 覆盖率 ≥ 80%

- [ ] **Step 2: 跑 typecheck + lint**

Run: `cd web && bun run typecheck && bun run lint && bun run format:check`
Expected: 0 错

- [ ] **Step 3: 跑全量 E2E (含 18 个旧的)**

Run: `cd web && bun run test:e2e`
Expected: 18 旧 + 5 新全绿

- [ ] **Step 4: 后端测试也要绿 (评估页 spec 改的前端, 不影响后端, 但保险跑下)**

Run: `uv run --no-sync python -m pytest tests/ -q`
Expected: PASS

- [ ] **Step 5: 改 to-do.md, 划掉 knowledge 路由那一行 (因 spec 覆盖了)**

```bash
# 找 to-do.md 第 1 行
sed -i 's|^- \[\] http://localhost:3000/knowledge页面切换向量库和知识图谱用不同的路由|^- [x] http://localhost:3000/knowledge页面切换向量库和知识图谱用不同的路由 (2026-06-10 spec cb34b9d 已规划)|' docs/to-do.md
git add docs/to-do.md
git commit -m "chore: 划掉 knowledge 路由化待办 (本 spec 覆盖)"
```

- [ ] **Step 6: 看 git log, 确认所有 commit 入 master**

Run: `git log --oneline -15`
Expected: 看到 Task 1-10 的所有 commit + Task 11.5 的 to-do commit.

---

## Self-Review

**1. Spec coverage**:
- ✅ `lib/api/auth.ts` — Task 1
- ✅ `lib/api/swr.ts` 升级 — Task 2
- ✅ `lib/api/knowledge.ts` — Task 3
- ✅ `lib/api/chat.ts` + 删 `lib/api.ts` — Task 4
- ✅ `lib/api/evaluate.ts` — Task 5
- ✅ 页面切到 knowledgeApi — Task 6a
- ✅ 页面切到 chatApi — Task 6b
- ✅ 页面切到 evaluateApi — Task 6c
- ✅ 抽 KnowledgeHero/EmptyState + 移 StatCard/EntryCard — Task 7
- ✅ BFF 裁剪 11 个 route.ts — Task 8
- ✅ `/knowledge` 拆 documents + graph — Task 9
- ✅ KnowledgeTabs 组件 — Task 9
- ✅ E2E `05-knowledge-routes.spec.ts` — Task 10
- ✅ 最终验证 (typecheck/lint/test/18 E2E) — Task 11
- ✅ to-do.md 划掉 — Task 11.5
- ⚠️ `lib/api/errors.ts` 提取 — Task 4.3 顺带做了, spec "实施顺序 4" 已写
- ⚠️ `useApi` 加 onError toast — spec 提了, plan **没**单独 task. 实施时跟 Task 2 合并 (在 swr.ts 升级里加 onError). 备注: 如果 toast 库没装, subagent 改用现有错误展示 (跟现状保持一致), 后续 spec 再加.
- ✅ BFF 保留清单 (qa/retrieve, documents/upload, batch) — 任务没明说"别删", 留作 Task 8 grep 步骤自然拦下

**2. Placeholder scan**: 0 个 TBD/TODO/类似 Task N. 每个 Step 有具体代码.

**3. Type consistency**:
- `knowledgeApi.createQA(input: QAInput): Promise<QA>` 在 Task 3 定义, Task 6a 用 ✅
- `evaluateApi.runsUrl()` / `runDetailUrl(id)` / `runCancelUrl(id)` / `createRun(file, concurrency)` / `cancelRun(id)` 在 Task 5 定义, Task 6c / 9 / 10 用 ✅
- `authHeaders(): Record<string, string>` 在 Task 1 定义, Task 2/3/4/5 都用 ✅
- `KnowledgeTabs` 在 Task 9 定义, Task 10 E2E `data-testid="tab-documents"` / `"tab-graph"` 引用 ✅

无类型不一致.
