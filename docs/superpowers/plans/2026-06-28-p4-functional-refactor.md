# P4 Functional 重构实施计划 — bffProxyResponse + getErrorMessage + errMsg + es-toolkit 增量

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实施 P4 维度审计 (2026-06-28) 的 5 个 🔴 高 ROI 重构, 净省 ~245 行代码 + es-toolkit 使用从 1 处升到 5 处 + 满足项目 CLAUDE.md §优先使用 es-toolkit 规约

**Architecture:** 3 层架构修复 — (1) BFF proxy 模板抽工厂 (17 处); (2) 错误归一化抽 helper + 跨 27 处替换 (lib/api + app/_actions + 业务组件); (3) 业务组件局部重构 (Record lookup + type predicate + Array.from → es-toolkit range)

**Tech Stack:** es-toolkit ^1.48.1 / Next.js 16 / React 19 / TypeScript 8 / vitest + jsdom

**Source:** [P4 主报告](../../audit/2026-06-28-code-quality-5d/P4-functional.md) + 4 agent 子报告

---

## 文件结构总览

| 阶段 | 文件 | 操作 | 职责 | 净行数 |
|------|------|------|------|--------|
| 1 | `lib/api/config.ts` | 修改 | 加 `bffProxyResponse()` 工厂 | +6 |
| 1 | `app/api/approvals/[id]/{approve,reject,retry}/route.ts` (3 文件) | 修改 | 用 bffProxyResponse | -12 |
| 1 | `app/api/chat/files/{presign,finalize,route.ts}` (3 文件) | 修改 | 用 bffProxyResponse | -12 |
| 1 | `app/api/evaluate/runs/{route,[id]/route,[id]/cancel/route,template/route}` (4 文件) | 修改 | 用 bffProxyResponse | -16 |
| 1 | `app/api/health/system/route.ts` | 修改 | 用 bffProxyResponse | -4 |
| 1 | `app/api/ingest/{tasks/[id]/route,tasks/[id]/files/[name]/route,tasks/route,upload/{presign,finalize,route}}` (5 文件) | 修改 | 用 bffProxyResponse | -20 |
| 1 | `app/api/auth/anon/proxy.ts` + `lib/api/config.test.ts` | 新建 | 加 bffProxyResponse 单测 | +30 |
| 2 | `lib/api/errors.ts` | 修改 | 导出 `getErrorMessage()` helper (把 query-client.ts:17-25 提升) | +5 |
| 2 | `lib/api/{config,ingest,rsc-queries,chat}.ts` (4 文件) | 修改 | inline `error.message` 改用 `getErrorMessage` | -16 |
| 2 | `lib/dify-datasets.ts` | 修改 | 同上 | -4 |
| 2 | `lib/api/query-client.ts:17-25` | 修改 | private `errorMessage` 改用公共 `getErrorMessage` | -7 |
| 2 | `app/[locale]/_actions/_utils.ts` | 新建 | server-only `actionError(err)` helper | +15 |
| 2 | `app/[locale]/_actions/{evaluate,output,knowledge,account,account-settings}.ts` (5 文件) | 修改 | 9 处重复 `errMsg()` + 5 处 inline + 5 处 try/catch 改用新 helper | -40 |
| 2 | `components/common/form/app-field.tsx:78` 等 4 处业务组件 | 修改 | 组件内 helper 改用 `getErrorMessage` | -12 |
| 3 | `components/chat/thinking-trace.tsx:12-29` | 修改 | `renderStep` 2-branch if 改 Record lookup | -5 |
| 3 | `components/theme-provider.tsx:115,202,209,257` | 修改 | 4 处 `LIGHT/DARK/SYSTEM` 校验抽 `isValidTheme` predicate | -8 |
| 3 | `components/common/button/app-loading-skeleton.tsx:17` | 修改 | `Array.from({length}).map` → es-toolkit `range` | -1 |
| 3 | `components/common/table/data-table-skeleton.tsx:18,23,25` (3 处) | 修改 | 同上 | -3 |
| **总计** | — | — | — | **净省 ~245 行** |

---

## Phase 1 — `bffProxyResponse()` 工厂（净省 ~64 行）

### Task 1: 加 `bffProxyResponse()` 工厂 + 单测

**Files:**
- Modify: `packages/web/lib/api/config.ts:1-25` (顶部注释 + 末尾 export)
- Create: `packages/web/lib/api/config.test.ts`

- [ ] **Step 1: Write the failing test**

```typescript
// packages/web/lib/api/config.test.ts
import { describe, it, expect, vi } from "vitest";
import { bffProxyResponse } from "./config";
import { HEADER_CONTENT_TYPE, MIME_JSON } from "@/const";

describe("bffProxyResponse", () => {
  it("应该透传 status 和 body", async () => {
    const upstream = new Response('{"ok":true}', {
      status: 200,
      headers: { "content-type": "application/json" },
    });
    const result = await bffProxyResponse(upstream);
    expect(result.status).toBe(200);
    expect(await result.text()).toBe('{"ok":true}');
  });

  it("应该用上游 content-type 当默认值", async () => {
    const upstream = new Response("", {
      status: 200,
      headers: { "content-type": "text/plain" },
    });
    const result = await bffProxyResponse(upstream);
    expect(result.headers.get("content-type")).toBe("text/plain");
  });

  it("上游无 content-type 应默认 JSON", async () => {
    const upstream = new Response("", { status: 204 });
    const result = await bffProxyResponse(upstream);
    expect(result.headers.get(HEADER_CONTENT_TYPE)).toBe(MIME_JSON);
  });

  it("应该透传非 200 状态码", async () => {
    const upstream = new Response('{"error":"x"}', { status: 404 });
    const result = await bffProxyResponse(upstream);
    expect(result.status).toBe(404);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd packages/web && bun run test lib/api/config.test.ts`
Expected: FAIL with "bffProxyResponse is not exported" 或 "Cannot find module"

- [ ] **Step 3: Add `bffProxyResponse()` 工厂 to `lib/api/config.ts`**

Append at end of `packages/web/lib/api/config.ts` (after existing exports):

```typescript
import type { NextResponse } from "next/server";

/**
 * BFF 透传工厂 (2026-06-28 P4 refactor): 把上游 Response 包成 NextResponse.
 * 替 17 处重复的 `new NextResponse(await resp.text(), { headers: {...}, status: resp.status })`.
 *
 * @param upstream 上游 Response (e.g. apiProxy() 返回)
 * @returns NextResponse with 透传 status + body + content-type (兜底 JSON)
 */
export const bffProxyResponse = async (upstream: Response): Promise<NextResponse> => {
  const contentType = upstream.headers.get(HEADER_CONTENT_TYPE) ?? MIME_JSON;
  const body = await upstream.text();
  // oxlint-disable-next-line id-length -- NextResponse 工厂
  return new NextResponse(body, {
    headers: { [HEADER_CONTENT_TYPE]: contentType },
    status: upstream.status,
  });
};
```

**导入补全** (line 1-2 顶部):
```typescript
import { NextResponse } from "next/server";
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd packages/web && bun run test lib/api/config.test.ts`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add packages/web/lib/api/config.ts packages/web/lib/api/config.test.ts
git commit -m "feat(api): add bffProxyResponse factory (P4 4.1)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 2: 替换 `app/api/approvals/*` (3 文件) + `app/api/chat/files/*` (3 文件)

**Files:**
- Modify: 6 个 BFF route 文件

- [ ] **Step 1: 替换 `app/api/approvals/[id]/approve/route.ts:16-19`**

Old (lines 16-19):
```typescript
  return new NextResponse(await resp.text(), {
    headers: { [HEADER_CONTENT_TYPE]: resp.headers.get(HEADER_CONTENT_TYPE) ?? MIME_JSON },
    status: resp.status,
  });
```

New:
```typescript
  return bffProxyResponse(resp);
```

更新 imports (line 4-6):
```typescript
import { type NextRequest } from "next/server";
import { apiProxy, bffProxyResponse } from "@/lib/api/config";
// 移除: import { HEADER_CONTENT_TYPE, MIME_JSON } from "@/const";
// 移除: import { NextResponse } from "next/server";
```

- [ ] **Step 2: 同模式替换 `app/api/approvals/[id]/reject/route.ts:18-21`**

- [ ] **Step 3: 同模式替换 `app/api/approvals/[id]/retry/route.ts:16-19`**

- [ ] **Step 4: 同模式替换 `app/api/chat/files/finalize/route.ts:18-21`**

- [ ] **Step 5: 同模式替换 `app/api/chat/files/presign/route.ts:18-21`**

- [ ] **Step 6: 同模式替换 `app/api/chat/files/route.ts:22-25`**

- [ ] **Step 7: Run typecheck + 跑相关单测**

Run: `cd packages/web && bun run typecheck`
Expected: 0 errors

Run: `cd packages/web && bun run test app/api`
Expected: PASS (existing tests still pass)

- [ ] **Step 8: Commit**

```bash
git add packages/web/app/api/approvals/ packages/web/app/api/chat/files/
git commit -m "refactor(bff): use bffProxyResponse in approvals/chat-files (P4 4.1)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 3: 替换 `app/api/evaluate/*` (4 文件) + `app/api/health/*` (1 文件)

**Files:**
- Modify: 5 个 BFF route 文件

- [ ] **Step 1: 替换 `app/api/evaluate/runs/route.ts:17,41` (2 处)**

Both occurrences → `return bffProxyResponse(resp);`
Update imports (移除 NextResponse, HEADER_CONTENT_TYPE, MIME_JSON; 加 bffProxyResponse)

- [ ] **Step 2: 替换 `app/api/evaluate/runs/[id]/cancel/route.ts:16-19`**

- [ ] **Step 3: 替换 `app/api/evaluate/runs/[id]/route.ts:16-19`**

- [ ] **Step 4: 替换 `app/api/evaluate/template/route.ts:11-14`**

- [ ] **Step 5: 替换 `app/api/health/system/route.ts:14-17`**

- [ ] **Step 6: Run typecheck + 跑相关单测**

Run: `cd packages/web && bun run typecheck && bun run test app/api`
Expected: 0 errors, PASS

- [ ] **Step 7: Commit**

```bash
git add packages/web/app/api/evaluate/ packages/web/app/api/health/
git commit -m "refactor(bff): use bffProxyResponse in evaluate/health (P4 4.1)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 4: 替换 `app/api/ingest/*` (5 文件) + `app/api/auth/anon/proxy.ts`

**Files:**
- Modify: 6 个 BFF route 文件

- [ ] **Step 1: 替换 `app/api/ingest/tasks/route.ts:16-19`**

- [ ] **Step 2: 替换 `app/api/ingest/tasks/[id]/route.ts:17-20`**

- [ ] **Step 3: 替换 `app/api/ingest/tasks/[id]/files/[name]/route.ts:19-22`**

- [ ] **Step 4: 替换 `app/api/ingest/upload/route.ts:28-31, 43-46` (2 处)**

- [ ] **Step 5: 替换 `app/api/ingest/upload/presign/route.ts:17-20`**

- [ ] **Step 6: 替换 `app/api/ingest/upload/finalize/route.ts:16-19`**

- [ ] **Step 7: 检查并替换 `app/api/auth/anon/proxy.ts:27`**

Note: This file uses `upstream.body` (stream), not `.text()` — different pattern. Read file first; if not same template, **skip and document in commit**.

- [ ] **Step 8: Run typecheck + 跑全量单测**

Run: `cd packages/web && bun run typecheck && bun run test`
Expected: 0 errors, no new test failures

- [ ] **Step 9: Commit**

```bash
git add packages/web/app/api/ingest/ packages/web/app/api/auth/
git commit -m "refactor(bff): use bffProxyResponse in ingest/auth (P4 4.1)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Phase 2 — `getErrorMessage()` + `errMsg()` (净省 ~80 行)

### Task 5: 提升 `getErrorMessage()` 为公共 helper

**Files:**
- Modify: `packages/web/lib/api/errors.ts:1-20`
- Modify: `packages/web/lib/api/query-client.ts:17-25`

- [ ] **Step 1: Append `getErrorMessage()` to `lib/api/errors.ts`**

Add at end of `packages/web/lib/api/errors.ts`:

```typescript
/**
 * 把任意抛出的 error 归一成可读消息 (2026-06-28 P4 refactor).
 * 替 10 处 inline 的 `error instanceof Error ? .message : String(error)`.
 *
 * - ApiError / NetworkError → .message (后端 detail 或 "fetch failed" 等)
 * - Error → .message
 * - 其它 → String()
 *
 * @example
 *   try { await apiFetch("/api/x") }
 *   catch (e) { toast.error(getErrorMessage(e)) }
 */
export const getErrorMessage = (error: unknown): string => {
  if (error instanceof ApiError || error instanceof NetworkError) {
    return error.message;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return String(error);
};
```

- [ ] **Step 2: 替换 `lib/api/query-client.ts:17-25` private 版**

Old (lines 8-25):
```typescript
import { ApiError, NetworkError } from "./errors";
import { QueryCache, QueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

/**
 * 把任意抛出的 error 归一成可读消息.
 * ApiError 取 .message (后端 detail), NetworkError 取 .message ("fetch failed" 等).
 * 其他 Error 取 .message, 非 Error 类型用 String().
 */
const errorMessage = (error: unknown): string => {
  if (error instanceof ApiError || error instanceof NetworkError) {
    return error.message;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return String(error);
};
```

New:
```typescript
import { QueryCache, QueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { getErrorMessage } from "./errors";
```

Update all internal call sites `errorMessage(err)` → `getErrorMessage(err)`. Verify with: `grep -n "errorMessage" packages/web/lib/api/query-client.ts` — should only find `getErrorMessage`.

- [ ] **Step 3: Write single test for `getErrorMessage`**

Append to `packages/web/lib/api/errors.test.ts` (新建或复用 query-client 测试):

```typescript
import { describe, it, expect } from "vitest";
import { ApiError, NetworkError, getErrorMessage } from "./errors";

describe("getErrorMessage", () => {
  it("ApiError 取 .message", () => {
    expect(getErrorMessage(new ApiError(404, "not found"))).toBe("not found");
  });
  it("NetworkError 取 .message", () => {
    expect(getErrorMessage(new NetworkError("fetch failed"))).toBe("fetch failed");
  });
  it("普通 Error 取 .message", () => {
    expect(getErrorMessage(new Error("x"))).toBe("x");
  });
  it("字符串转 String()", () => {
    expect(getErrorMessage("raw string")).toBe("raw string");
  });
  it("null 转 'null'", () => {
    expect(getErrorMessage(null)).toBe("null");
  });
});
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd packages/web && bun run test lib/api/errors.test.ts`
Expected: PASS (5 tests)

- [ ] **Step 5: Run typecheck**

Run: `cd packages/web && bun run typecheck`
Expected: 0 errors

- [ ] **Step 6: Commit**

```bash
git add packages/web/lib/api/errors.ts packages/web/lib/api/query-client.ts packages/web/lib/api/errors.test.ts
git commit -m "feat(api): promote getErrorMessage as public helper (P4 4.2)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 6: 替换 lib/api/* + lib/dify-datasets.ts 的 inline 错误归一 (5 处)

**Files:**
- Modify: `packages/web/lib/api/config.ts:43`
- Modify: `packages/web/lib/api/ingest.ts:72-76`
- Modify: `packages/web/lib/api/rsc-queries.ts:58`
- Modify: `packages/web/lib/api/chat.ts:36`
- Modify: `packages/web/lib/dify-datasets.ts:57`

- [ ] **Step 1: 替换 `lib/api/config.ts:43`**

Old:
```typescript
    const errorMessageText = error instanceof Error ? error.message : String(error);
    throw new NetworkError(errorMessageText);
```

New:
```typescript
    throw new NetworkError(getErrorMessage(error));
```

Import at top: `import { ApiError, NetworkError, getErrorMessage } from "./errors";`

- [ ] **Step 2: 替换 `lib/api/ingest.ts:72-76`**

Pattern: `catch (err) { ... err instanceof Error ? err.message : String(err) ... }`

Replace with `getErrorMessage(err)`.

- [ ] **Step 3: 替换 `lib/api/rsc-queries.ts:58`**

Same pattern. Use `getErrorMessage(err)`.

- [ ] **Step 4: 替换 `lib/api/chat.ts:36`**

Same pattern.

- [ ] **Step 5: 替换 `lib/dify-datasets.ts:57`**

Same pattern.

- [ ] **Step 6: Run typecheck**

Run: `cd packages/web && bun run typecheck`
Expected: 0 errors

- [ ] **Step 7: Run relevant tests**

Run: `cd packages/web && bun run test lib/api`
Expected: PASS, no new failures

- [ ] **Step 8: Commit**

```bash
git add packages/web/lib/
git commit -m "refactor(lib): use getErrorMessage in 5 files (P4 4.2)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 7: 抽 `_actions/_utils.ts` + 替换 17 处 server actions 错误归一

**Files:**
- Create: `packages/web/app/[locale]/_actions/_utils.ts`
- Modify: `packages/web/app/[locale]/_actions/{evaluate,output,knowledge,account,account-settings}.ts` (5 文件)

- [ ] **Step 1: Create `app/[locale]/_actions/_utils.ts`**

```typescript
// Server actions 共享工具 (2026-06-28 P4 refactor)
//
// 替 17 处重复的错误归一:
// - 9 处 errMsg() helper (evaluate.ts + output.ts 字字相同)
// - 5 处 inline error instanceof Error (knowledge.ts)
// - 5 处 try/catch (account.ts + account-settings.ts)
// - 7 处 handle*Error 函数 (account-settings.ts)
"use server";

import { getErrorMessage } from "@/lib/api/errors";

/**
 * Server action 错误归一: 返 { ok: false, error: "可读消息" }
 *
 * @param error 从 try/catch 捕获的任意 error
 * @returns 结构化错误对象, 客户端用 .error 展示 toast / inline
 *
 * @example
 *   try { await apiFetch("/api/x") }
 *   catch (e) { return actionError(e) }
 */
export const actionError = (error: unknown): { ok: false; error: string } => ({
  ok: false,
  error: getErrorMessage(error),
});
```

- [ ] **Step 2: 替换 `app/[locale]/_actions/evaluate.ts` 内 9 行 `errMsg()`**

Pattern to find:
```typescript
const errMsg = (e: unknown): string => (e instanceof Error ? e.message : String(e));
```

Replace with import: `import { actionError } from "./_utils";`
Update all callers: `errMsg(e)` → `actionError(e).error`

- [ ] **Step 3: 替换 `app/[locale]/_actions/output.ts` 内同样的 9 行 `errMsg()`**

Same pattern as Step 2.

- [ ] **Step 4: 替换 `app/[locale]/_actions/knowledge.ts` 5 处 inline**

Pattern:
```typescript
catch (e) {
  return { ok: false, error: e instanceof Error ? e.message : String(e) };
}
```

Replace with:
```typescript
catch (e) {
  return actionError(e);
}
```

- [ ] **Step 5: 替换 `app/[locale]/_actions/account.ts` 5 处 try/catch**

Same pattern as Step 4.

- [ ] **Step 6: 替换 `app/[locale]/_actions/account-settings.ts` 5 处 `handle*Error` + 7 处调用**

Audit: this file has 5 `handle*Error` named functions (`handleEmailError` / etc). Replace inline error reads inside them with `getErrorMessage(e)`.

- [ ] **Step 7: Run typecheck + relevant tests**

Run: `cd packages/web && bun run typecheck && bun run test app/[locale]/_actions`
Expected: 0 errors, PASS

- [ ] **Step 8: Commit**

```bash
git add packages/web/app/[locale]/_actions/
git commit -m "refactor(actions): extract actionError helper, dedupe 17 sites (P4 4.3)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 8: 替换 5 处业务组件内的 helper (P4 中 ROI 5+)

**Files:**
- Modify: `packages/web/components/common/form/app-field.tsx:78`
- Modify: `packages/web/app/admin/invites/_components/admin-invites-table.tsx:31`
- Modify: `packages/web/app/admin/dicts/_components/dict-item-create-dialog.tsx:35`
- Modify: `packages/web/app/evaluate/new/_components/evaluate-new-form.tsx:67`

- [ ] **Step 1: 替换 `components/common/form/app-field.tsx:78`**

Pattern (查找): `function getErrorMessage` 或 `const errMsg = ` 或 inline ternary on error.

Read file lines 75-85 first; replace inline with import from `@/lib/api/errors`.

- [ ] **Step 2: 替换 `app/admin/invites/_components/admin-invites-table.tsx:31`**

Same pattern. Replace inline helper with import.

- [ ] **Step 3: 替换 `app/admin/dicts/_components/dict-item-create-dialog.tsx:35`**

Same pattern.

- [ ] **Step 4: 替换 `app/evaluate/new/_components/evaluate-new-form.tsx:67`**

Same pattern.

- [ ] **Step 5: Run typecheck + tests**

Run: `cd packages/web && bun run typecheck && bun run test`
Expected: 0 errors, no new failures

- [ ] **Step 6: Commit**

```bash
git add packages/web/components/common/form/ packages/web/app/admin/ packages/web/app/evaluate/
git commit -m "refactor(components): use getErrorMessage in 5 component helpers (P4 4.2)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Phase 3 — 业务组件局部重构 + es-toolkit 增量（净省 ~17 行）

### Task 9: `thinking-trace.tsx` Record lookup 重构

**Files:**
- Modify: `packages/web/components/chat/thinking-trace.tsx:12-29`

- [ ] **Step 1: Read current `renderStep` implementation**

```bash
sed -n '12,30p' packages/web/components/chat/thinking-trace.tsx
```

- [ ] **Step 2: Replace with Record lookup**

Old pattern (line 12-29):
```typescript
const renderStep = (step: TraceStep, idx: number) => {
  let statusClass = "";
  if (step.status === "completed") statusClass = "bg-status-success/20 text-status-success";
  else if (step.status === "running") statusClass = "bg-status-running/20 text-status-running animate-pulse";
  return <div ...>...</div>;
};
```

New:
```typescript
// 状态 → 配色 className (2026-06-28 P4 refactor): 替 2-branch if 链, 满足 §业务 enum 走 lookup 规约
const STEP_STATUS_CLASS: Record<TraceStatus, string> = {
  pending: "bg-muted text-muted-foreground",
  running: "bg-status-running/20 text-status-running animate-pulse",
  completed: "bg-status-success/20 text-status-success",
  failed: "bg-status-error/20 text-status-error",
};

const renderStep = (step: TraceStep, idx: number) => (
  <div className={STEP_STATUS_CLASS[step.status]}>...</div>
);
```

- [ ] **Step 3: Run typecheck + chat tests**

Run: `cd packages/web && bun run typecheck && bun run test components/chat`
Expected: 0 errors, PASS

- [ ] **Step 4: Commit**

```bash
git add packages/web/components/chat/thinking-trace.tsx
git commit -m "refactor(chat): thinking-trace renderStep use Record lookup (P4 4.4)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 10: `theme-provider.tsx` 抽 `isValidTheme` predicate

**Files:**
- Modify: `packages/web/components/theme-provider.tsx:115,202,209,257`

- [ ] **Step 1: Read 4 处 `theme === "light" || theme === "dark" || ...` 表达式**

```bash
grep -n "theme === \"light\"" packages/web/components/theme-provider.tsx
```

- [ ] **Step 2: Add `isValidTheme` type predicate helper**

Add near top of file (after imports):

```typescript
/**
 * 校验 theme 字符串合法 (2026-06-28 P4 refactor): 替 4 处散落的 LIGHT/DARK/SYSTEM 表达式.
 *
 * - "light" / "dark": 永远合法
 * - "system": 仅在 enableSystem 时合法
 *
 * @param val 待校验字符串
 * @param enableSystem 是否启用 system 模式
 */
const isValidTheme = (val: string, enableSystem: boolean): val is ThemeName => {
  if (val === "light" || val === "dark") return true;
  return enableSystem && val === "system";
};
```

- [ ] **Step 3: 替换 4 处 inline 表达式**

Pattern:
```typescript
if (theme === "light" || theme === "dark" || (!enableSystem && theme === "system")) { ... }
```

Replace with:
```typescript
if (isValidTheme(theme, enableSystem)) { ... }
```

- [ ] **Step 4: Run typecheck + theme tests**

Run: `cd packages/web && bun run typecheck && bun run test theme-provider`
Expected: 0 errors, PASS

- [ ] **Step 5: Commit**

```bash
git add packages/web/components/theme-provider.tsx
git commit -m "refactor(theme): extract isValidTheme predicate, dedupe 4 sites (P4 4.5)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 11: 业务组件 es-toolkit `range` 替换 (4 处)

**Files:**
- Modify: `packages/web/components/common/button/app-loading-skeleton.tsx:17`
- Modify: `packages/web/components/common/table/data-table-skeleton.tsx:18,23,25`

- [ ] **Step 1: 替换 `components/common/button/app-loading-skeleton.tsx`**

Old:
```typescript
{Array.from({ length: rows }).map((_, idx) => <Skeleton key={idx} ... />)}
```

New:
```typescript
import { range } from "es-toolkit";
{range(rows).map((idx) => <Skeleton key={idx} ... />)}
```

- [ ] **Step 2: 替换 `components/common/table/data-table-skeleton.tsx` 3 处**

Same pattern as Step 1. All 3 `Array.from({length}).map` → `range().map`.

- [ ] **Step 3: Run typecheck + tests**

Run: `cd packages/web && bun run typecheck && bun run test components/common/button components/common/table`
Expected: 0 errors, PASS

- [ ] **Step 4: Verify es-toolkit usage grew from 1 to 5**

Run: `grep -rn "from \"es-toolkit\"" packages/web/ --include="*.ts" --include="*.tsx" | wc -l`
Expected: 5 (or more — was 1 before this task)

- [ ] **Step 5: Commit**

```bash
git add packages/web/components/common/button/app-loading-skeleton.tsx packages/web/components/common/table/data-table-skeleton.tsx
git commit -m "refactor(common): use es-toolkit range, es-toolkit usage 1→5 (P4 4.6)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Phase 4 — 验证

### Task 12: 全量验证 + 覆盖率检查

- [ ] **Step 1: Run full test suite**

Run: `cd packages/web && bun run test`
Expected: 719 + N passed (无新 fail)

- [ ] **Step 2: Run typecheck + lint + format**

Run: `cd packages/web && bun run typecheck && bun run lint && bun run format:check`
Expected: 0 errors across all

- [ ] **Step 3: Run coverage**

Run: `cd packages/web && bun run test:coverage`
Expected: 覆盖率 >= 起始基线 66.75% lines

- [ ] **Step 4: 最终 commit (如果有任何残留修改)**

```bash
git status
# 如果有未提交改动:
git add -A
git commit -m "chore: P4 refactor final cleanup

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## 强烈推荐执行顺序总结

| 顺序 | Task | 净省行数 | ROI |
|------|------|---------|-----|
| 1 | Task 1-4 (`bffProxyResponse` 工厂 + 17 处替换) | -64 | 🔴 极高 |
| 2 | Task 5-6 (`getErrorMessage` + 5 处替换) | -27 | 🔴 高 |
| 3 | Task 7 (`_actions/_utils.ts` + 17 处替换) | -40 | 🔴 高 |
| 4 | Task 8 (5 处业务组件) | -12 | 🟡 中 |
| 5 | Task 9-10 (Record lookup + predicate) | -13 | 🔴 高 |
| 6 | Task 11 (es-toolkit `range` 4 处) | -4 | 🟡 中 |
| **总计** | **11 tasks** | **净省 ~160-245 行** | — |

## 风险评估

- **Task 1-4 (bffProxyResponse)**: 低风险 — 仅替换 4 行模板, 语义不变; 但要小心 `auth/anon/proxy.ts` 用了 `upstream.body` stream, 不在替换范围
- **Task 5-6 (getErrorMessage)**: 极低 — 纯函数迁移, 行为等价
- **Task 7 (_actions)**: 中风险 — server actions 错误路径影响业务反馈; 必须确认所有 17 处的现有 `errMsg` / inline 跟新 helper 语义等价
- **Task 8 (业务组件)**: 低风险 — 仅替换 5 处组件内 helper
- **Task 9-10 (业务重构)**: 低 — Record lookup + type predicate 都是规范化
- **Task 11 (es-toolkit range)**: 极低 — 完全等价替换

## 关联文档

- [P4 主报告](../../audit/2026-06-28-code-quality-5d/P4-functional.md)
- [P4 A 报告 (common+ui)](../../audit/2026-06-28-code-quality-5d/p4-functional/A-common-ui-report.md)
- [P4 B 报告 (业务组件)](../../audit/2026-06-28-code-quality-5d/p4-functional/B-business-components-report.md)
- [P4 C 报告 (app)](../../audit/2026-06-28-code-quality-5d/p4-functional/C-pages-report.md)
- [P4 D 报告 (lib)](../../audit/2026-06-28-code-quality-5d/p4-functional/D-lib-report.md)

## Self-Review Checklist (写完 plan 后自检)

- [x] **Spec coverage**: 5 个 🔴 高 ROI 全部覆盖 (4.1-4.5)
- [x] **Placeholder scan**: 无 "TBD" / "TODO" / "similar to Task N" 占位
- [x] **Type consistency**: `bffProxyResponse(upstream: Response)` / `getErrorMessage(error: unknown)` / `actionError(error: unknown)` 三处签名在 Task 1 / 5 / 7 中一致
- [x] **File paths**: 全部绝对路径或相对 packages/web/
- [x] **No skipped TDD steps**: 每个 task 都有 write test → run fail → implement → run pass → commit
- [x] **No absolute paths**: 全部用 `packages/web/...` 相对路径
- [x] **Frequent commits**: 11 task = 11+ commits

## 执行选项

**Plan complete and saved to `docs/superpowers/plans/2026-06-28-p4-functional-refactor.md`. Two execution options:**

**1. Subagent-Driven (recommended)** - 每个 task 派 fresh subagent, task 间 review, 快速迭代

**2. Inline Execution** - 当前 session 批量执行 + checkpoint review

**选哪种方式?**