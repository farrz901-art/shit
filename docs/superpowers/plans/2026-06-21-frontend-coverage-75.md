# 前端覆盖率 75% 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Frontend coverage from 70.87% to 75% Lines (~238 additional covered lines)

**Architecture:** Add tests for 4 uncovered code areas: OpenAI streaming provider, migration toast/backup logic, knowledge API missing methods, ingest presign upload path. Each test file follows existing patterns (mock fetch, stubGlobal, fake-indexeddb).

**Tech Stack:** vitest + jsdom, @testing-library/react, fake-indexeddb, sonner mock

---

### Task 1: `lib/chat/openai.test.ts` — OpenAI Chat Provider

**Files:**
- Create: `packages/web/lib/chat/openai.test.ts`
- Source: `packages/web/lib/chat/openai.ts` (118 lines, 13.2% coverage)

Mock strategy: mock `apiProxy` from `@/lib/api/config` to return a Response with a `ReadableStream` that emits SSE chunks. Test the async generator `sendMessage`.

- [ ] **Step 1: Write the test file**

```typescript
// OpenAIChatProvider 单测
// 覆盖: 构造函数 + sendMessage 流式解析 (SSE 块)
import { afterEach, describe, expect, it, vi } from "vitest";

// Mock apiProxy before module import
const apiProxyMock = vi.fn();
vi.mock("@/lib/api/config", () => ({ apiProxy: apiProxyMock }));

import { OpenAIChatProvider } from "./openai";

// 构造一个 SSE 流: 返回 ReadableStream, 在 reader.read() 逐步返回块
const makeStream = (chunks: string[]): ReadableStream<Uint8Array> => {
  const encoder = new TextEncoder();
  let idx = 0;
  return new ReadableStream({
    pull(controller) {
      if (idx < chunks.length) {
        controller.enqueue(encoder.encode(chunks[idx]));
        idx++;
      } else {
        controller.close();
      }
    },
  });
};

// 从 Response.body 构建 mock Response
const streamResponse = (body: ReadableStream): Response =>
  ({ body, ok: true, status: 200, text: async () => "" }) as unknown as Response;

const errorResponse = (status: number): Response =>
  ({ ok: false, status, text: async () => `HTTP ${status}` }) as unknown as Response;

describe("OpenAIChatProvider", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    // 恢复 process.env
    // process.env 在 vi.mock hoist 前可读, mock 内不改
  });

  it("name = 'openai'", () => {
    const provider = new OpenAIChatProvider();
    expect(provider.name).toBe("openai");
  });

  it("sendMessage: API_KEY 未设时 yield error", async () => {
    // 保存原值并设为空
    const origKey = process.env.OPENAI_API_KEY;
    process.env.OPENAI_API_KEY = "";
    const provider = new OpenAIChatProvider();
    const events: unknown[] = [];
    for await (const ev of provider.sendMessage({ query: "hi", inputs: {}, user: "u" }, new AbortController().signal)) {
      events.push(ev);
    }
    expect(events).toHaveLength(1);
    expect(events[0]).toMatchObject({ type: "error", code: "config_error" });
    process.env.OPENAI_API_KEY = origKey;
  });

  it("sendMessage: 正常流 → message_end", async () => {
    const origKey = process.env.OPENAI_API_KEY;
    process.env.OPENAI_API_KEY = "sk-test";
    const stream = makeStream([
      'data: {"choices":[{"delta":{"content":"你好"}}]}\n\n',
      'data: [DONE]\n\n',
    ]);
    apiProxyMock.mockResolvedValue(streamResponse(stream));
    const provider = new OpenAIChatProvider();
    const events: unknown[] = [];
    for await (const ev of provider.sendMessage({ query: "hi", inputs: {}, user: "u" }, new AbortController().signal)) {
      events.push(ev);
    }
    expect(events.length).toBeGreaterThanOrEqual(2);
    expect(events[0]).toMatchObject({ type: "message", delta: "你好" });
    expect(events[events.length - 1]).toMatchObject({ type: "message_end" });
    process.env.OPENAI_API_KEY = origKey;
  });

  it("sendMessage: reasoning_content 累积后输出 thinking 事件", async () => {
    const origKey = process.env.OPENAI_API_KEY;
    process.env.OPENAI_API_KEY = "sk-test";
    const stream = makeStream([
      'data: {"choices":[{"delta":{"reasoning_content":"思考中..."}}]}\n\n',
      'data: {"choices":[{"delta":{"content":"最终答案"}}]}\n\n',
      'data: [DONE]\n\n',
    ]);
    apiProxyMock.mockResolvedValue(streamResponse(stream));
    const provider = new OpenAIChatProvider();
    const events: unknown[] = [];
    for await (const ev of provider.sendMessage({ query: "hi", inputs: {}, user: "u" }, new AbortController().signal)) {
      events.push(ev);
    }
    const thinkingEvents = events.filter((ev: any) => ev.type === "thinking");
    expect(thinkingEvents.length).toBeGreaterThanOrEqual(1);
    expect(thinkingEvents[0]).toMatchObject({ detail: "思考中...", node: "reasoning" });
    process.env.OPENAI_API_KEY = origKey;
  });

  it("sendMessage: HTTP 非 200 时 yield http_ error", async () => {
    const origKey = process.env.OPENAI_API_KEY;
    process.env.OPENAI_API_KEY = "sk-test";
    apiProxyMock.mockResolvedValue(errorResponse(401));
    const provider = new OpenAIChatProvider();
    const events: unknown[] = [];
    for await (const ev of provider.sendMessage({ query: "hi", inputs: {}, user: "u" }, new AbortController().signal)) {
      events.push(ev);
    }
    expect(events[0]).toMatchObject({ type: "error", code: "http_401" });
    process.env.OPENAI_API_KEY = origKey;
  });
});
```

- [ ] **Step 2: Run tests to verify**

Run: `cd packages/web && bun x vitest run lib/chat/openai.test.ts --reporter=verbose`
Expected: 4 passed

- [ ] **Step 3: Run oxlint**

Run: `cd packages/web && bun x oxlint lib/chat/openai.test.ts`
Expected: 0 warnings

- [ ] **Step 4: Commit**

```bash
cd /c/doc/Code/rag && git add packages/web/lib/chat/openai.test.ts && git commit -m "test: add OpenAIChatProvider streaming tests"
```

---

### Task 2: `lib/chat/migration.test.ts` — Add performAnonToLoginMigration + downloadLocalBackup

**Files:**
- Modify: `packages/web/lib/chat/migration.test.ts`
- Source: `packages/web/lib/chat/migration.ts` (102 lines, 38.88% coverage)

Existing tests cover `clearLocalChat` and `useAnonToLoginMigration`. Missing: `performAnonToLoginMigration` (lines 45-73) and `downloadLocalBackup` (lines 79-102).

Mock strategy: reuse existing fake-indexeddb setup + sonner mock. For `downloadLocalBackup`, mock `document.createElement("a")` to verify click is called.

- [ ] **Step 1: Add tests to existing file**

Append to `packages/web/lib/chat/migration.test.ts`:

```typescript
describe("performAnonToLoginMigration", () => {
  beforeEach(async () => {
    await db.conversations.clear();
    await db.messages.clear();
  });

  it("无 anon 数据时直接返回, 不弹 toast", async () => {
    const { performAnonToLoginMigration } = await import("./migration");
    await performAnonToLoginMigration(vi.fn() as any);
    expect(vi.mocked(toast)).not.toHaveBeenCalled();
  });

  it("有 anon 数据时弹 toast", async () => {
    await db.conversations.bulkPut([{ ...SAMPLE_CONV, owner: "anon" }]);
    const { performAnonToLoginMigration } = await import("./migration");
    // toast 需要 resolve, 用 mock 自动 resolve "dismiss"
    vi.mocked(toast).mockImplementation((_msg: string, opts?: any) => {
      opts?.cancel?.onClick?.();
      return "";
    });
    await performAnonToLoginMigration((key: string) => key);
    expect(vi.mocked(toast)).toHaveBeenCalled();
  });
});

describe("downloadLocalBackup", () => {
  beforeEach(async () => {
    await db.conversations.clear();
    await db.messages.clear();
  });

  it("导出 anon 数据为 JSON 文件", async () => {
    await db.conversations.bulkPut([{ ...SAMPLE_CONV, owner: "anon" }]);
    await db.messages.bulkPut([SAMPLE_MSG]);

    const clickFn = vi.fn();
    const createElementFn = vi.fn().mockReturnValue({ click: clickFn, href: "", download: "" });
    const createObjectURLFn = vi.fn().mockReturnValue("blob:url");
    vi.stubGlobal("URL", { createObjectURL: createObjectURLFn, revokeObjectURL: vi.fn() });
    vi.stubGlobal("document", {
      createElement: createElementFn,
      body: { appendChild: vi.fn(), removeChild: vi.fn() },
    });

    const { downloadLocalBackup } = await import("./migration");
    await downloadLocalBackup();
    expect(createObjectURLFn).toHaveBeenCalled();
    expect(clickFn).toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: Run tests**

Run: `cd packages/web && bun x vitest run lib/chat/migration.test.ts --reporter=verbose`
Expected: 5 passed (3 existing + 2 new)

- [ ] **Step 3: Run oxlint**

Run: `cd packages/web && bun x oxlint lib/chat/migration.test.ts`
Expected: 0 warnings

- [ ] **Step 4: Commit**

```bash
cd /c/doc/Code/rag && git add packages/web/lib/chat/migration.test.ts && git commit -m "test: add performAnonToLoginMigration + downloadLocalBackup tests"
```

---

### Task 3: `lib/api/knowledge.test.ts` — Add missing API method tests

**Files:**
- Modify: `packages/web/lib/api/knowledge.test.ts`
- Source: `packages/web/lib/api/knowledge.ts` (187 lines, 81.48% coverage)

Existing tests cover: fetchStats, fetchNodes (4xx), fetchBatchStatus (4xx), createTriples, uploadDocument. Missing: fetchDatasets, fetchHealth, fetchRelations, fetchSchema, fetchSchemas, fetchSegments, retrieveQA, startBatch.

Mock strategy: same `okResponse`/`errResponse` helpers, `vi.stubGlobal("fetch")`.

- [ ] **Step 1: Add tests for remaining API methods**

Append to `packages/web/lib/api/knowledge.test.ts` inside the existing `describe("knowledgeApi", ...)` block (before the closing `});`):

```typescript
  it("fetchDatasets 返 data 数组", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        okResponse({ data: [{ id: "ds1", name: "测试数据集" }] }),
      ),
    );
    const result = await knowledgeApi.fetchDatasets();
    expect(result).toHaveLength(1);
    expect(result[0].name).toBe("测试数据集");
  });

  it("fetchDatasets data 为 undefined 时返 []", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(okResponse({})),
    );
    const result = await knowledgeApi.fetchDatasets();
    expect(result).toEqual([]);
  });

  it("fetchHealth 返 ok", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(okResponse({ ok: true })),
    );
    const result = await knowledgeApi.fetchHealth();
    expect(result.ok).toBe(true);
  });

  it("fetchRelations 返关系数组", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        okResponse([{ src: "n1", src_label: "Node", src_name: "A", src_business_id: "b1", type: "RELATES_TO", dst: "n2", dst_label: "Node", dst_name: "B", dst_business_id: "b2", props: {} }]),
      ),
    );
    const result = await knowledgeApi.fetchRelations();
    expect(result).toHaveLength(1);
    expect(result[0].type).toBe("RELATES_TO");
  });

  it("fetchSchema 拼 domain 到 query", async () => {
    const mock = vi.fn().mockResolvedValue(okResponse({ nodes: [], relations: [] }));
    vi.stubGlobal("fetch", mock);
    await knowledgeApi.fetchSchema("motor");
    const url = mock.mock.calls[0][0] as string;
    expect(url).toContain("domain=motor");
  });

  it("fetchSchemas 返 schemas 列表", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(okResponse({ schemas: [{ name: "motor" }, { name: "pump" }] })),
    );
    const result = await knowledgeApi.fetchSchemas();
    expect(result.schemas).toHaveLength(2);
  });

  it("retrieveQA POST 返 records", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(okResponse({ records: [{ content: "答案", score: 0.95, document_name: "doc1" }] })),
    );
    const result = await knowledgeApi.retrieveQA("问题", "ds1");
    expect(result.records).toHaveLength(1);
    expect(result.records[0].content).toBe("答案");
  });

  it("startBatch POST 返 task_id", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(okResponse({ task_id: "t1" })),
    );
    const result = await knowledgeApi.startBatch({
      dataset_id: "ds1",
      items: [{ target: "neo4j", type: "create_node", payload: {} }],
    });
    expect(result.task_id).toBe("t1");
  });
```

- [ ] **Step 2: Run tests**

Run: `cd packages/web && bun x vitest run lib/api/knowledge.test.ts --reporter=verbose`
Expected: 12+ passed (4 existing + 8 new)

- [ ] **Step 3: Run oxlint**

Run: `cd packages/web && bun x oxlint lib/api/knowledge.test.ts`
Expected: 0 warnings

- [ ] **Step 4: Commit**

```bash
cd /c/doc/Code/rag && git add packages/web/lib/api/knowledge.test.ts && git commit -m "test: add knowledge API missing method tests"
```

---

### Task 4: `lib/api/ingest.test.ts` — Add uploadViaPresign tests

**Files:**
- Modify: `packages/web/lib/api/ingest.test.ts`
- Source: `packages/web/lib/api/ingest.ts` (167 lines, 80.76% coverage)

Existing tests cover: URL factories, upload (happy + 4xx), taskDownload (happy + 4xx). Missing: `uploadViaPresign` (lines 112-141) — presign → PUT → finalize flow.

Mock strategy: same `okResponse` helpers. Mock `fetch` 3 times (presign → PUT → finalize).

- [ ] **Step 1: Add uploadViaPresign tests**

Append to `packages/web/lib/api/ingest.test.ts` (after existing describe blocks):

```typescript
describe("ingestApi.uploadViaPresign", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.unstubAllGlobals();
  });
  afterEach(() => vi.unstubAllGlobals());

  it("完整 presign→PUT→finalize 流程", async () => {
    const presignResp = okResponse({
      task_id: "t1",
      total_files: 1,
      state: "queued",
      uploads: [{ name: "f.pdf", uri: "minio/uri", put_url: "https://minio/put", mime: "application/pdf" }],
    });
    const putResp = { ok: true } as Response;
    const finalizeResp = okResponse({ task_id: "t1", total_files: 1, state: "queued" });
    vi.stubGlobal("fetch", vi.fn()
      .mockResolvedValueOnce(presignResp)
      .mockResolvedValueOnce(putResp)
      .mockResolvedValueOnce(finalizeResp),
    );
    const result = await ingestApi.uploadViaPresign([new File(["x"], "f.pdf", { type: "application/pdf" })]);
    expect(result.task_id).toBe("t1");
  });

  it("presign 不返 PUT URL 抛错", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      okResponse({
        task_id: "t1",
        uploads: [{ name: "f.pdf", uri: "minio/uri", put_url: null, mime: "application/pdf" }],
        total_files: 1,
        state: "queued",
      }),
    ));
    await expect(ingestApi.uploadViaPresign([new File(["x"], "f.pdf")])).rejects.toThrow("PUT URL");
  });

  it("PUT MinIO 失败抛错", async () => {
    const presignResp = okResponse({
      task_id: "t1",
      uploads: [{ name: "f.pdf", uri: "minio/uri", put_url: "https://minio/put", mime: "application/pdf" }],
      total_files: 1,
      state: "queued",
    });
    const putResp = { ok: false, status: 403 } as Response;
    vi.stubGlobal("fetch", vi.fn()
      .mockResolvedValueOnce(presignResp)
      .mockResolvedValueOnce(putResp),
    );
    await expect(ingestApi.uploadViaPresign([new File(["x"], "f.pdf")])).rejects.toThrow("PUT MinIO 失败");
  });
});
```

- [ ] **Step 2: Run tests**

Run: `cd packages/web && bun x vitest run lib/api/ingest.test.ts --reporter=verbose`
Expected: 9 passed (6 existing + 3 new)

- [ ] **Step 3: Run oxlint**

Run: `cd packages/web && bun x oxlint lib/api/ingest.test.ts`
Expected: 0 warnings

- [ ] **Step 4: Commit**

```bash
cd /c/doc/Code/rag && git add packages/web/lib/api/ingest.test.ts && git commit -m "test: add uploadViaPresign tests"
```

---

### Task 5: Run coverage verification (first time)

Only after all 4 tasks above are complete and committed:

- [ ] **Step 1: Run full coverage**

Run: `cd packages/web && bun run test:coverage 2>&1 | tail -10`
Expected: Lines >= 73.5% (estimate ~74%). If already >= 75%, done.

- [ ] **Step 2: Check if 75% reached**

If Lines >= 75% → done, skip Task 6.
If Lines < 75% → proceed to Task 6.

---

### Task 6 (contingency): AppDialog + AppConfirm — add edge case tests

**Files:**
- Modify: `packages/web/components/common/dialog/app-dialog.test.tsx`
- Modify: `packages/web/components/common/confirm/app-confirm.test.tsx`
- Source: `app-dialog.tsx` (73 lines, 22.22%), `app-confirm.tsx` (55 lines, 15%)

Existing tests cover basic rendering. Add edge cases for uncovered code paths.

- [ ] **Step 1: Add AppDialog edge case tests**

Append to `app-dialog.test.tsx`:

```typescript
  it("无 title/description 时不渲染 header", () => {
    const { container } = render(
      <AppDialog open={true} onOpenChange={vi.fn()}>
        <p>内容</p>
      </AppDialog>,
    );
    // DialogHeader 应该不存在
    expect(container.querySelector("[class*='border-b']")).toBeNull();
  });

  it("无 footer 时不渲染 footer", () => {
    const { container } = render(
      <AppDialog open={true} onOpenChange={vi.fn()} title="测试">
        <p>内容</p>
      </AppDialog>,
    );
    // DialogFooter 有 border-t, 没有 footer 时不应有
    expect(container.querySelector("[class*='border-t']")).toBeNull();
  });

  it("dataTestid 透传", () => {
    render(
      <AppDialog open={true} onOpenChange={vi.fn()} title="测试" dataTestid="my-dialog">
        <p>内容</p>
      </AppDialog>,
    );
    expect(screen.getByTestId("my-dialog")).toBeInTheDocument();
  });

  it("maxWidth 默认 lg", () => {
    const { container } = render(
      <AppDialog open={true} onOpenChange={vi.fn()} title="测试">
        <p>内容</p>
      </AppDialog>,
    );
    const content = container.querySelector("[data-state='open']");
    expect(content?.className).toContain("max-w-lg");
  });
```

- [ ] **Step 2: Add AppConfirm edge case tests**

Append to `app-confirm.test.tsx`:

```typescript
  it("description 可选, 不传时不渲染", () => {
    render(
      <AppConfirm
        open={true}
        onOpenChange={vi.fn()}
        title="删除"
        confirmText="删除"
        onConfirm={vi.fn()}
      />,
    );
    expect(screen.getByRole("heading", { name: "删除" })).toBeInTheDocument();
    // 没有 description 时不应有 description 文本
    expect(screen.queryByRole("paragraph")).toBeNull();
  });

  it("variant=destructive 确认按钮用破坏色", () => {
    render(
      <AppConfirm
        open={true}
        onOpenChange={vi.fn()}
        title="危险操作"
        variant="destructive"
        confirmText="确认删除"
        onConfirm={vi.fn()}
      />,
    );
    const confirmBtn = screen.getByRole("button", { name: "确认删除" });
    expect(confirmBtn.className).toContain("bg-destructive");
  });

  it("onCancel 被调用", async () => {
    const userEventModule = await import("@testing-library/user-event");
    const user = userEventModule.default.setup();
    const onCancel = vi.fn();
    render(
      <AppConfirm
        open={true}
        onOpenChange={vi.fn()}
        title="测试"
        confirmText="确认"
        onConfirm={vi.fn()}
        onCancel={onCancel}
      />,
    );
    await user.click(screen.getByRole("button", { name: "取消" }));
    expect(onCancel).toHaveBeenCalled();
  });
```

- [ ] **Step 3: Run tests**

Run: `cd packages/web && bun x vitest run components/common/dialog/app-dialog.test.tsx components/common/confirm/app-confirm.test.tsx --reporter=verbose`
Expected: 10+ passed (6 existing + 4 new for dialog, 2 existing + 3 new for confirm)

- [ ] **Step 4: Run oxlint**

Run: `cd packages/web && bun x oxlint components/common/dialog/app-dialog.test.tsx components/common/confirm/app-confirm.test.tsx`
Expected: 0 warnings

- [ ] **Step 5: Commit**

```bash
cd /c/doc/Code/rag && git add packages/web/components/common/dialog/app-dialog.test.tsx packages/web/components/common/confirm/app-confirm.test.tsx && git commit -m "test: add AppDialog + AppConfirm edge case tests"
```

---

### Task 7: Final coverage verification

- [ ] **Step 1: Run full coverage**

Run: `cd packages/web && bun run test:coverage 2>&1 | tail -10`
Expected: Lines >= 75%

- [ ] **Step 2: Report result**

If 75%+ reached: "目标达成！Lines X% → Y%"
If not: report remaining gap, suggest next targets.

---

## 剩余可测文件评估

截止 Task 6 完成后，当前 Lines 72.63%（尚需 ~136 行）。以下按批次列出所有剩余可测文件。

### 不可测（明确排除）

| 文件 | 行数 | 原因 |
|------|------|------|
| `app/api/[...path]/route.ts` | 167 | BFF 路由，需 Request 对象，jsdom 不支持 |
| `components/ui/form.tsx` | 182 | shadcn Form，依赖 React Hook Form 复杂 mock |
| `components/ui/calendar.tsx` | 181 | shadcn Calendar，依赖 date-fns 复杂交互 |
| `components/ui/command.tsx` | 139 | shadcn Command，依赖 cmdk |
| `components/ui/dropdown-menu.tsx` | 175 | shadcn DropdownMenu，依赖 Radix 复杂交互 |
| `components/ui/select.tsx` | 149 | shadcn Select，依赖 Radix 复杂交互 |
| `components/ui/pagination.tsx` | 113 | 已有 88.46%，剩余边界情况价值低 |
| `components/ui/dialog.tsx` | 104 | 已有 91.66%（sheet），dialog 本身 0% 但无业务逻辑 |

### 可测（按价值排序）

| 优先级 | 文件 | 行数 | 当前覆盖 | 预估可覆盖 | 测试策略 |
|--------|------|------|----------|-----------|----------|
| P0 | `components/ui/alert.tsx` | 49 | 0% | ~40 | 基础渲染测试 |
| P0 | `components/ui/avatar.tsx` | 47 | 0% | ~35 | 基础渲染测试 |
| P0 | `components/ui/checkbox.tsx` | 28 | 0% | ~20 | 基础渲染测试 |
| P0 | `components/ui/collapsible.tsx` | 11 | 0% | ~8 | 基础渲染测试 |
| P0 | `components/ui/progress.tsx` | 33 | 100% | 0 | 已满 |
| P0 | `components/ui/scroll-area.tsx` | 46 | 100% | 0 | 已满 |
| P0 | `components/ui/tooltip.tsx` | 31 | 0% | ~25 | 基础渲染测试 |
| P0 | `components/ui/toggle-group.tsx` | 57 | 0% | ~40 | 基础渲染测试 |
| P0 | `components/ui/empty.tsx` | 82 | 92.3% | 0 | 已满 |
| P0 | `components/ui/sheet.tsx` | 122 | 91.66% | 0 | 已满 |
| **P0** | **`app/_actions/account-settings.ts`** | **339** | **17.79%** | **~200** | **mock apiFetch + serverAuthHeaders + next/cache，测纯函数 + server action** |
| P1 | `lib/api/rsc-queries.ts` | 82 | ~30% | ~50 | mock apiFetch + 测 prefetchQuery / rscGet |
| P1 | `lib/api/config.ts` | 192 | 93.1% | ~10 | 已有 93%，边际价值低 |
| P2 | `lib/dify-datasets.ts` | ~100 | 91.3% | ~5 | 已有 91%，边际价值低 |
| P2 | `lib/parse-eval-csv.ts` | ~50 | 95.65% | ~2 | 已满 |
| P2 | `lib/parse-excel.ts` | ~50 | 91.3% | ~5 | 已有 91%，边际价值低 |
| P2 | `lib/parse-json.ts` | ~50 | 未覆盖 | ~30 | 纯函数，易测 |
| P2 | `lib/motion.ts` | ~50 | 未覆盖 | ~30 | 动画工具函数 |
| P2 | `lib/utils.ts` | ~50 | 未覆盖 | ~30 | cn() 等工具函数 |
| P2 | `lib/schema-types.ts` | ~50 | 未覆盖 | ~30 | 纯类型定义 |

### 批次计划

**第 3 批（优先覆盖 UI 组件，预估贡献 ~170 行）：**

| 文件 | 预估贡献 |
|------|----------|
| `components/ui/alert.tsx` | ~40 |
| `components/ui/avatar.tsx` | ~35 |
| `components/ui/checkbox.tsx` | ~20 |
| `components/ui/collapsible.tsx` | ~8 |
| `components/ui/tooltip.tsx` | ~25 |
| `components/ui/toggle-group.tsx` | ~40 |

**第 4 批（如果需要，业务文件，预估贡献 ~140 行）：**

| 文件 | 预估贡献 |
|------|----------|
| `lib/api/rsc-queries.ts` | ~50 |
| `lib/motion.ts` | ~30 |
| `lib/utils.ts` | ~30 |
| `lib/parse-json.ts` | ~30 |

### Task 8: UI 组件基础渲染测试（第 3 批）

- [ ] **Step 1-6: 为每个文件创建测试**

每个测试文件使用统一模板：

```typescript
// [ComponentName] 组件单测
import { describe, expect, it } from "vitest";
import { render } from "@testing-library/react";
import { ComponentName } from "./component-name";

describe("ComponentName", () => {
  it("渲染无报错", () => {
    const { container } = render(<ComponentName />);
    expect(container.firstChild).toBeInTheDocument();
  });
});
```

具体文件：
- `components/ui/alert.tsx` → `components/ui/alert.test.tsx`
- `components/ui/avatar.tsx` → `components/ui/avatar.test.tsx`
- `components/ui/checkbox.tsx` → `components/ui/checkbox.test.tsx`
- `components/ui/collapsible.tsx` → `components/ui/collapsible.test.tsx`
- `components/ui/tooltip.tsx` → `components/ui/tooltip.test.tsx`
- `components/ui/toggle-group.tsx` → `components/ui/toggle-group.test.tsx`

### Task 9: 业务文件测试（第 4 批，如果需要）

- [ ] **Step 1: `lib/api/rsc-queries.test.ts`**

mock `apiFetch` + `serverAuthHeaders`，测：
- `getRscQueryClient` 返 QueryClient 实例
- `prefetchQuery` 成功写入 cache
- `prefetchQuery` 失败不抛（catch 内 console.warn）
- `rscGet` 自动解包 data 数组
- `rscGet` 非数组 data 不拆包装

- [ ] **Step 2: `lib/motion.test.ts`**

纯函数测试，测动画工具函数。

- [ ] **Step 3: `lib/utils.test.ts`**

测 `cn()` 函数（classnames 合并）。

- [ ] **Step 4: `lib/parse-json.test.ts`**

测 JSON 解析工具函数。

### Task 10: 最终覆盖率验证

只在第 3 批和第 4 批全部完成后跑一次：

- [ ] **Step 1: Run full coverage**

Run: `cd packages/web && bun run test:coverage 2>&1 | tail -10`
Expected: Lines >= 75%

- [ ] **Step 2: Report result**

如果达到则完成，如果未达到则评估原因。

---

### Task 11: `app/_actions/account-settings.test.ts` — 账号设置 Server Action 测试

**Files:**
- Create: `packages/web/app/_actions/account-settings.test.ts`
- Source: `packages/web/app/_actions/account-settings.ts` (339 lines, 17.79% coverage)

测试分两层：纯函数 + server action。

#### 纯函数（零 mock）

```typescript
import { describe, expect, it, vi } from "vitest";
import { ApiError, NetworkError } from "@/lib/api/errors";

vi.mock("@/lib/api/config", () => ({ apiFetch: vi.fn() }));
vi.mock("@/lib/api/auth.server", () => ({ serverAuthHeaders: vi.fn().mockResolvedValue({ authorization: "Bearer tok" }) }));
vi.mock("next/cache", () => ({ revalidatePath: vi.fn() }));

import {
  changePasswordAction,
  deleteAvatarAction,
  requestDeletionAction,
  updateProfileAction,
  uploadAvatarAction,
} from "./account-settings";

describe("validateAvatarFile", () => {
  it("空文件返回错误", async () => {
    const formData = new FormData();
    formData.append("file", new File([], ""));
    const result = await uploadAvatarAction({ ok: false, avatarUrl: null, error: null }, formData);
    expect(result.ok).toBe(false);
    expect(result.error).toBe("请选择文件");
  });
});

describe("updateProfileAction", () => {
  it("displayName 太短返回校验错误", async () => {
    const formData = new FormData();
    formData.append("display_name", "");
    const result = await updateProfileAction({ ok: false, error: null }, formData);
    expect(result.ok).toBe(false);
  });

  it("成功返 ok=true", async () => {
    const { apiFetch } = await import("@/lib/api/config");
    vi.mocked(apiFetch).mockResolvedValue(undefined);
    const formData = new FormData();
    formData.append("display_name", "新昵称");
    const result = await updateProfileAction({ ok: false, error: null }, formData);
    expect(result.ok).toBe(true);
  });

  it("apiFetch 抛 ApiError 返错误", async () => {
    const { apiFetch } = await import("@/lib/api/config");
    vi.mocked(apiFetch).mockRejectedValue(new ApiError(400, "保存失败"));
    const formData = new FormData();
    formData.append("display_name", "新昵称");
    const result = await updateProfileAction({ ok: false, error: null }, formData);
    expect(result.ok).toBe(false);
    expect(result.error).toBe("保存失败");
  });
});

describe("uploadAvatarAction", () => {
  it("文件类型不支持返回错误", async () => {
    const formData = new FormData();
    formData.append("file", new File(["x"], "test.gif", { type: "image/gif" }));
    const result = await uploadAvatarAction({ ok: false, avatarUrl: null, error: null }, formData);
    expect(result.ok).toBe(false);
    expect(result.error).toContain("仅支持");
  });

  it("成功返 avatarUrl", async () => {
    const { apiFetch } = await import("@/lib/api/config");
    vi.mocked(apiFetch).mockResolvedValue({ avatar_url: "https://example.com/av.jpg" });
    const formData = new FormData();
    formData.append("file", new File(["x"], "test.png", { type: "image/png" }));
    const result = await uploadAvatarAction({ ok: false, avatarUrl: null, error: null }, formData);
    expect(result.ok).toBe(true);
    expect(result.avatarUrl).toBe("https://example.com/av.jpg");
  });
});

describe("deleteAvatarAction", () => {
  it("成功返 ok=true", async () => {
    const { apiFetch } = await import("@/lib/api/config");
    vi.mocked(apiFetch).mockResolvedValue(undefined);
    const result = await deleteAvatarAction();
    expect(result.ok).toBe(true);
  });

  it("失败返错误", async () => {
    const { apiFetch } = await import("@/lib/api/config");
    vi.mocked(apiFetch).mockRejectedValue(new Error("网络错误"));
    const result = await deleteAvatarAction();
    expect(result.ok).toBe(false);
  });
});

describe("changePasswordAction", () => {
  it("密码太短返回校验错误", async () => {
    const formData = new FormData();
    formData.append("current_password", "old");
    formData.append("new_password", "短");
    formData.append("confirm", "短");
    const result = await changePasswordAction({ ok: false, error: null }, formData);
    expect(result.ok).toBe(false);
    expect(result.error).toContain("8");
  });

  it("两次密码不一致返回错误", async () => {
    const formData = new FormData();
    formData.append("current_password", "old12345");
    formData.append("new_password", "new12345");
    formData.append("confirm", "new99999");
    const result = await changePasswordAction({ ok: false, error: null }, formData);
    expect(result.ok).toBe(false);
    expect(result.error).toContain("不一致");
  });

  it("成功返 ok=true", async () => {
    const { apiFetch } = await import("@/lib/api/config");
    vi.mocked(apiFetch).mockResolvedValue(undefined);
    const formData = new FormData();
    formData.append("current_password", "old12345");
    formData.append("new_password", "new12345");
    formData.append("confirm", "new12345");
    const result = await changePasswordAction({ ok: false, error: null }, formData);
    expect(result.ok).toBe(true);
  });
});

describe("requestDeletionAction", () => {
  it("空密码返回错误", async () => {
    const formData = new FormData();
    formData.append("current_password", "");
    formData.append("confirm_text", "我要注销");
    const result = await requestDeletionAction({ ok: false, error: null, restoreUrl: null, expiresAt: null }, formData);
    expect(result.ok).toBe(false);
  });

  it("确认文本不对返回错误", async () => {
    const formData = new FormData();
    formData.append("current_password", "pass12345");
    formData.append("confirm_text", "我不注销");
    const result = await requestDeletionAction({ ok: false, error: null, restoreUrl: null, expiresAt: null }, formData);
    expect(result.ok).toBe(false);
  });
});
```

- [ ] **Step 1: Write test file** with the above code
- [ ] **Step 2: Run tests** `cd packages/web && bun run test -- app/_actions/account-settings.test.ts --reporter=verbose`
- [ ] **Step 3: Run oxlint** `cd packages/web && bun x oxlint app/_actions/account-settings.test.ts`
- [ ] **Step 4: Fix any warnings** (magic numbers, import order)

### Task 12: 最终覆盖率验证

只在所有任务完成后跑一次：

- [ ] **Step 1: Run full coverage**

Run: `cd packages/web && bun run test:coverage 2>&1 | tail -10`
Expected: Lines >= 75%

- [ ] **Step 2: Report result**

---
