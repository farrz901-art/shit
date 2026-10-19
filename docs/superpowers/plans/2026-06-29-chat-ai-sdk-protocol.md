# Chat AI SDK 协议层重构 — 实施计划 (v2)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 替换 chat 模块手写字节解码 (TextDecoder) 为 AI SDK TextDecoderStream，简化重复的 SSE 解析，提取 Dify normalize* 层为独立文件，BFF route 用 JsonToSseTransformStream。

**Architecture (Phase 1, ~-68 行):**
- `sse.ts` 从手写 TextDecoder + 字节拼合 + JSON 解析 (~77 行) 简化为纯 `\n\n` 切块器 (~20 行)。字节解码委托给 `ReadableStream.pipeThrough(new TextDecoderStream())`
- `openai.ts` 复用简化后 `parseSseBlocks`，去掉重复 reader/decoder/buffer（118→~100 行）
- `route.ts` 用 AI SDK `JsonToSseTransformStream` + `pipeTextStreamToResponse` 替代手写 encoder + [DONE] + try/catch（~37→~15 行）
- `chat-event-decoder.ts` 从 `dify.ts` 搬出 `normalize*` + `seenMessageRef` + `createParseBlock`，封装为 TransformStream（新 ~60 行）
- `dify.ts` normalize* 函数迁出（263→~200 行）
- `stream-handler.ts` + `use-chat-state.ts` 签名不变
- `chat-utils.ts` 已简化（70 行），不动

**Tech Stack:** TypeScript 8, `ai@7.0.8`, `@ai-sdk/react@4.0.9`, vitest

---

## 前提条件（已满足）

| 条件 | 状态 |
|------|------|
| `ai@7.0.8` 已安装 | ✅ |
| `@ai-sdk/react@4.0.9` 已安装 | ✅ |
| `chat-utils.ts` 已拆为 stream-handler.ts + send-request.ts（2026-06-30） | ✅ |
| `bun run test` baseline 719 passed | ✅ |
| `bun run typecheck` 0 error | ✅ |
| `bun run lint` 0 error | ✅ |

**不需要升包、不需要改 tsconfig、不需要安装新依赖。**

---

## 文件变化总表

| 文件 | 变化 | 行数变化 |
|------|------|---------|
| `lib/chat/sse.ts` | 删 TextDecoder + parseSseStream，保留简化 parseSseBlocks | 77→~20（-57） |
| `lib/chat/openai.ts` | 复用 parseSseBlocks，去重复 reader/decoder | 118→~100（-18） |
| `app/api/chat/messages/route.ts` | JsonToSseTransformStream 替手写 SSE 写入 | ~37→~15（-22） |
| `lib/chat/chat-event-decoder.ts` | **新建**: normalize* + seenMessageRef + createParseBlock 从 dify.ts 迁入 | 0→~60（+60） |
| `lib/chat/dify.ts` | normalize* 迁出，parseStream 用 TextDecoderStream | 263→~200（-63） |
| `lib/chat/stream-handler.ts` | import 路径微调（parseSseStream→createChatEventStream） | ~±2 |
| `lib/chat/use-chat-state.ts` | import 路径微调 | 0 |
| 测试 (6 文件) | sse.test.ts 简化, openai.test.ts 微调, dify.test.ts 微调, stream-handler.test.ts 微调, route.test.ts 简化, chat-shell.test.tsx 不动; chat-event-decoder.test.ts 新建 | — |

---

## 任务

### Task 1: 简化 sse.ts — 去掉 TextDecoder + parseSseStream，保留 \n\n 切块

**Files:**
- Modify: `packages/web/lib/chat/sse.ts` (77→~20 行)

**当前 sse.ts 结构：**
- `parseSseBlocks(stream: ReadableStream<Uint8Array>, signal)` — 手写 `TextDecoder("utf-8")` + 字节拼合 buffer + `\n\n` 切块 (~50 行)
- `parseSseStream(stream, signal)` — 在 parseSseBlocks 之上做 `data:` 前缀剥离 + JSON 解析 → ChatEvent (~27 行)
- 被 `dify.ts:70` (`parseStream` 调 `parseSseBlocks`) 和 `stream-handler.ts:363` (`processStream` 调 `parseSseStream`) import

**改动：**
1. `parseSseBlocks` 签名从 `ReadableStream<Uint8Array>` → `ReadableStream<string>`（字节解码由上游 TextDecoderStream 负责）
2. `parseSseStream` 整个删除（JSON 解析由消费方自行处理）

- [ ] **Step 1: 重写 sse.ts**

```typescript
// SSE \n\n 切块器 (2026-07-01 简化版)
// 字节解码委托给上游 ReadableStream.pipeThrough(new TextDecoderStream())
// 只做 \n\n 切块, 不解析 JSON, 不做 data: 前缀剥离
import { log } from "@/lib/log";

const NOT_FOUND = -1;
const DELIMITER_LENGTH = 2;
const START_INDEX = 0;

export async function* parseSseBlocks(
  stream: ReadableStream<string>,
  signal: AbortSignal,
): AsyncIterable<string> {
  const reader = stream.getReader();
  const onAbort = () => {
    reader.cancel().catch(() => { /* Ignore */ });
  };
  signal.addEventListener("abort", onAbort, { once: true });
  let buffer = "";
  try {
    while (true) {
      if (signal.aborted) {
        await reader.cancel();
        throw new DOMException("aborted", "AbortError");
      }
      const { value, done } = await reader.read();
      if (done) break;
      buffer += value;
      let index = 0;
      while ((index = buffer.indexOf("\n\n")) !== NOT_FOUND) {
        const block = buffer.slice(START_INDEX, index);
        buffer = buffer.slice(index + DELIMITER_LENGTH);
        yield block;
      }
    }
  } finally {
    signal.removeEventListener("abort", onAbort);
    reader.releaseLock();
  }
}
```

**注意：** `parseSseStream` 整个删除。不再 import `ChatEvent` 类型。不再 import `log`（可保留给 debug 用）。

- [ ] **Step 2: 跑 lint + typecheck**

```bash
cd packages/web && bun run lint:fix 2>&1 | tail -5 && bun run typecheck 2>&1 | tail -5
```

预期应有红色 typecheck（dify.ts 和 stream-handler.ts import 了 parseSseBlocks/parseSseStream 但签名变了）。将在 T3/T5 修复。

- [ ] **Step 3: Commit**

```bash
git add packages/web/lib/chat/sse.ts
git commit -m "refactor(chat): T1 简化 sse.ts — 删 TextDecoder + parseSseStream
parseSseBlocks 签名改为 ReadableStream<string>, 字节解码委托 upstream.
parseSseStream 删除 (JSON 解析由消费方自行处理)"
```

---

### Task 2: 简化 openai.ts — 复用 parseSseBlocks，去重复 reader/decoder

**Files:**
- Modify: `packages/web/lib/chat/openai.ts` (118→~100 行)

**当前 openai.ts sendMessage 结构（已读 verify）：**
- 手写 `reader = res.body!.getReader()` + `new TextDecoder("utf-8")` + `buf +=` + `buf.indexOf("\n\n")` + `data:` 行解析 + JSON.parse
- 这些跟 sse.ts 的 parseSseBlocks 功能完全重复
- `reasoning_content` 累积 + `[DONE]` sentinel 是 OpenAI 专有逻辑，保留

**改动：** 用 `parseSseBlocks` 替代手写 reader/decoder/buffer 样板。

- [ ] **Step 1: 重写 openai.ts 的流解析部分**

```typescript
// 修改 import
import { parseSseBlocks } from "./sse";

// 在 sendMessage 内, 替换 reader/decoder/buffer 循环:
// 旧:
const reader = res.body!.getReader();
const decoder = new TextDecoder("utf-8");
let buf = "";
let reasoningBuf = "";
try {
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    let index = START_INDEX;
    while ((index = buf.indexOf("\n\n")) !== NOT_FOUND) {
      const block = buf.slice(START_INDEX, index);
      buf = buf.slice(index + DELIMITER_LENGTH);
      // ... data: 行处理
    }
  }
} finally {
  reader.releaseLock();
}

// 新:
let reasoningBuf = "";
const textStream = res.body!.pipeThrough(new TextDecoderStream());
for await (const block of parseSseBlocks(textStream, signal)) {
  // ... data: 行处理 (完全不变)
}
```

具体修改位置：
- 删 `reader = res.body!.getReader()` + `new TextDecoder("utf-8")`
- 删 `buf` + `reasoningBuf` 的 `let`（reasoningBuf 保留）
- 删 `reader.read()` 循环 + `buf += decoder.decode(value, { stream: true })`
- 删 `buf.indexOf("\n\n")` 内循环 + 切片
- 删 `try/finally` + `reader.releaseLock()`
- 加 `const textStream = res.body!.pipeThrough(new TextDecoderStream())`
- 加 `for await (const block of parseSseBlocks(textStream, signal))`
- 保留 `data:` 行提取 + JSON.parse + reasoning_content 累积 + [DONE] 的全部逻辑

- [ ] **Step 2: 跑 openai.test.ts**

```bash
cd packages/web && bun run test -- lib/chat/openai.test.ts 2>&1
```

预期全绿（5 it）。如果红，检查 `parseSseBlocks` 是否从 `./sse` import、signal 传递是否正确。

- [ ] **Step 3: Commit**

```bash
git add packages/web/lib/chat/openai.ts
git commit -m "refactor(chat): T2 简化 openai.ts — 复用 parseSseBlocks, 去重复 reader/decoder
手写 reader.read() + TextDecoder + buf 循环替换为 TextDecoderStream + parseSseBlocks
reasoning_content 累积 + [DONE] sentinel 保留不变"
```

---

### Task 3: 简化 route.ts — JsonToSseTransformStream 替手写 SSE 写入

**Files:**
- Modify: `packages/web/app/api/chat/messages/route.ts` (~37→~15 行 SSE 写入部分)

**当前 route.ts SSE 写入（已读 verify, lines 131-167）：**
```typescript
const stream = new ReadableStream({
  async start(controller) {
    const encoder = new TextEncoder();
    try {
      for await (const ev of provider.sendMessage(...)) {
        controller.enqueue(encoder.encode(`data: ${JSON.stringify(ev)}\n\n`));
      }
    } catch (error) {
      const errEv = { code: "upstream_error", message: (error as Error).message, type: "error" };
      try { controller.enqueue(encoder.encode(`data: ${JSON.stringify(errEv)}\n\n`)); } catch {}
    } finally {
      try { controller.enqueue(encoder.encode("data: [DONE]\n\n")); controller.close(); } catch {}
    }
  },
});
return new Response(stream, { headers: { "Content-Type": "text/event-stream", ... } });
```

**改动：** 用 AI SDK `JsonToSseTransformStream` + `pipeTextStreamToResponse` 替代。

- [ ] **Step 1: 确认 JsonToSseTransformStream API**

```bash
cd packages/web && node -e "
import('ai').then(m => {
  console.log('JsonToSseTransformStream:', typeof m.JsonToSseTransformStream);
  console.log('pipeTextStreamToResponse:', typeof m.pipeTextStreamToResponse);
});
" 2>&1
```

如果 `JsonToSseTransformStream` 或 `pipeTextStreamToResponse` 不存在，查 `ai` 包导出名：

```bash
grep -E 'JsonToSse|pipeTextStreamToResponse' node_modules/ai/dist/index.d.ts | head -5
```

- [ ] **Step 2: 重写 route.ts 的 SSE 写入部分**

```typescript
// 文件顶部加 import
import { JsonToSseTransformStream, pipeTextStreamToResponse } from "ai";

// 替换 POST 函数中的 stream 创建 + return 部分 (lines 131-177):
// 旧:
//   const stream = new ReadableStream({ ... });
//   return new Response(stream, { headers: { ... } });

// 新:
const chatEventStream = new ReadableStream<ChatEvent>({
  async start(controller) {
    try {
      for await (const ev of provider.sendMessage(
        { autoGenerateName: body.autoGenerateName, conversationId: body.conversationId, inputs: body.inputs, query: body.query, user: body.user },
        req.signal,
      )) {
        controller.enqueue(ev);
      }
    } catch (error) {
      controller.enqueue({ code: "upstream_error", message: (error as Error).message, type: "error" } as ChatEvent);
    } finally {
      controller.close();
    }
  },
});

const sseStream = chatEventStream.pipeThrough(new JsonToSseTransformStream());
return pipeTextStreamToResponse(sseStream);
```

**注意：** `pipeTextStreamToResponse` 会自动设置 `Content-Type: text/event-stream` + `Cache-Control: no-cache, no-transform`。如果 AI SDK 返回的 Response 跟现有 header 有差异，在 return 前手动合并。

- [ ] **Step 3: 跑 route.test.ts**

```bash
cd packages/web && bun run test -- app/api/chat/messages/route.test.ts 2>&1
```

预期全绿（~9 it）。如果红，检查 `parseSSE` helper（route.test.ts 内的）是否仍兼容 — 它解析的是 Uint8Array SSE 格式，新输出也是标准 SSE `data: JSON\n\n` 格式，应兼容。

- [ ] **Step 4: Commit**

```bash
git add packages/web/app/api/chat/messages/route.ts
git commit -m "refactor(chat): T3 简化 route.ts — JsonToSseTransformStream 替手写 SSE 写入
删手写 TextEncoder + data: xxx\n\n + [DONE] + try/catch 三层嵌套"
```

---

### Task 4: 新建 chat-event-decoder.ts — 从 dify.ts 搬出 normalize* + seenMessageRef + createParseBlock

**Files:**
- Create: `packages/web/lib/chat/chat-event-decoder.ts` (~60 行)

**职责：** 从 dify.ts 搬出 Dify SSE 专有的归一化层。dify.ts 减少 ~60 行，专注做 HTTP 请求 + 编排。

- [ ] **Step 1: 创建 chat-event-decoder.ts**

```typescript
// Dify SSE 事件归一化层 (2026-07-01 从 dify.ts 拆出)
// 职责: RawEvent → ChatEvent (6 种事件) + 双发射防御 + 双块 SSE 合并
import type { ChatEvent, Citation } from "./types";
import { log } from "@/lib/log";

interface RawEvent {
  event: string;
  [k: string]: unknown;
}

interface RawRetrieverResource {
  position?: number;
  dataset_name?: string;
  document_name?: string;
  score?: number;
  content?: string;
  summary?: string | null;
}

const toCitation = (resource: RawRetrieverResource): Citation => ({
  content: resource.content ?? "",
  datasetName: resource.dataset_name,
  documentName: resource.document_name ?? "",
  position: resource.position,
  score: resource.score,
  summary: resource.summary ?? null,
});

// ---- 6 种 normalize 函数 ----

export const normalizeMessage = function* normalizeMessage(ev: RawEvent): Iterable<ChatEvent> {
  yield { delta: String(ev.answer ?? ""), type: "message" };
};

export const normalizeMessageEnd = function* normalizeMessageEnd(ev: RawEvent): Iterable<ChatEvent> {
  const meta = (ev.metadata ?? {}) as { retriever_resources?: RawRetrieverResource[] };
  const citations: Citation[] | undefined = meta.retriever_resources?.map(toCitation);
  yield { citations, conversationId: String(ev.conversation_id ?? ""), type: "message_end" };
};

export const normalizeNodeStarted = function* normalizeNodeStarted(ev: RawEvent): Iterable<ChatEvent> {
  yield { detail: ev.node_type ? String(ev.node_type) : undefined, node: String(ev.node_id ?? ""), status: "started", type: "thinking" };
};

export const normalizeNodeFinished = function* normalizeNodeFinished(ev: RawEvent): Iterable<ChatEvent> {
  yield { detail: ev.error ? `failed: ${String(ev.error)}` : ev.status ? String(ev.status) : undefined, node: String(ev.node_id ?? ""), status: "finished", type: "thinking" };
};

export const normalizeWorkflowFinished = function* normalizeWorkflowFinished(
  ev: RawEvent, seenMessageRef?: { current: boolean },
): Iterable<ChatEvent> {
  const wfData = (ev.data ?? {}) as { outputs?: { answer?: string } };
  const answer = wfData.outputs?.answer;
  if (answer && !seenMessageRef?.current) {
    yield { delta: answer, type: "message" };
  }
  yield { status: String(ev.status ?? "succeeded") as "succeeded" | "failed" | "partial-succeeded" | "stopped", type: "workflow_done" };
};

export const normalizeError = function* normalizeError(ev: RawEvent): Iterable<ChatEvent> {
  yield { code: String(ev.code ?? "unknown"), message: String(ev.message ?? ""), type: "error" };
};

// ---- 查表 dispatch ----

export const normalizeEvent = function* normalizeEvent(
  ev: RawEvent, seenMessageRef?: { current: boolean },
): Iterable<ChatEvent> {
  switch (ev.event) {
    case "message":
    case "message_replace": { yield* normalizeMessage(ev); return; }
    case "message_end": { yield* normalizeMessageEnd(ev); return; }
    case "workflow_started": { return; }
    case "node_started": { yield* normalizeNodeStarted(ev); return; }
    case "node_finished": { yield* normalizeNodeFinished(ev); return; }
    case "workflow_finished": { yield* normalizeWorkflowFinished(ev, seenMessageRef); return; }
    case "error": { yield* normalizeError(ev); return; }
    case "ping": case "tts_message": case "tts_message_end": { return; }
    default: { log.warn(`[dify] 未知事件: ${ev.event}`); return; }
  }
};

// ---- Dify 双块 SSE 解析 ----

export const createParseBlock = (): ((block: string) => RawEvent | null) => {
  let lastEvent = "";
  return (block: string): RawEvent | null => {
    const lines = block.split("\n");
    let event = "";
    let data = "";
    for (const line of lines) {
      if (line.startsWith("event:")) { event = line.slice("event:".length).trim(); }
      else if (line.startsWith("data:")) { data += line.slice("data:".length).trimStart(); }
    }
    if (event && !data) { lastEvent = event; return null; }
    if (data && !event) { event = lastEvent; }
    if (!event || !data) { return null; }
    try {
      const parsed = JSON.parse(data);
      return { event: parsed.event ?? event, ...parsed } as RawEvent;
    } catch { return null; }
  };
};
```

- [ ] **Step 2: 跑 lint + typecheck**

```bash
cd packages/web && bun run lint:fix 2>&1 | tail -5 && bun run typecheck 2>&1 | tail -5
```

预期 0 error。

- [ ] **Step 3: Commit**

```bash
git add packages/web/lib/chat/chat-event-decoder.ts
git commit -m "feat(chat): T4 新增 chat-event-decoder.ts — Dify 事件归一化层
从 dify.ts 搬出 normalize* (6 种) + seenMessageRef + createParseBlock + toCitation"
```

---

### Task 5: 调整 dify.ts — normalize* 迁出，parseStream 用 TextDecoderStream

**Files:**
- Modify: `packages/web/lib/chat/dify.ts` (263→~200 行)

**改动：**
1. 删 `normalizeMessage` / `normalizeMessageEnd` / `normalizeNodeStarted` / `normalizeNodeFinished` / `normalizeWorkflowFinished` / `normalizeError` / `toCitation` / `createParseBlock` / `RawEvent` / `RawRetrieverResource` 接口（已迁入 chat-event-decoder.ts）
2. `normalize` 方法改为调 `normalizeEvent`（从 decoder import）
3. `parseBlock` 改为调 `createParseBlock`（从 decoder import）
4. `parseStream` 内部加 `body.pipeThrough(new TextDecoderStream())`（跟 T1 parseSseBlocks 签名变化一致）

- [ ] **Step 1: 改 import**

```typescript
// 删:
import { parseSseBlocks } from "./sse";

// 增:
import { parseSseBlocks } from "./sse";
import { createParseBlock, normalizeEvent } from "./chat-event-decoder";
```

- [ ] **Step 2: 改 parseStream — 加 TextDecoderStream**

```typescript
private async *parseStream(
  body: ReadableStream<Uint8Array>,
  signal: AbortSignal,
): AsyncIterable<ChatEvent> {
  const seenMessageRef = { current: false };
  const parseBlock = createParseBlock();
  const textStream = body.pipeThrough(new TextDecoderStream());  // ⭐ 新增
  for await (const block of parseSseBlocks(textStream, signal)) {  // 签名匹配了
    const ev = parseBlock(block);
    if (ev) {
      for (const chatEv of normalizeEvent(ev, seenMessageRef)) {  // normalize → normalizeEvent
        if (chatEv.type === "message") { seenMessageRef.current = true; }
        yield chatEv;
      }
    }
  }
}
```

- [ ] **Step 3: 删 normalize* 函数**

删除 `DifyChatProvider` 类中的 `normalize` 方法，替换为直接调 `normalizeEvent`。删除类外所有 `normalize*` 函数 + `toCitation` + `createParseBlock` + `RawEvent` + `RawRetrieverResource` 接口。

```typescript
// 在 DifyChatProvider 类中:
private *normalize(ev: RawEvent, seenMessageRef?: { current: boolean }): Iterable<ChatEvent> {
  // 旧: switch(ev.event) { case "message": yield* normalizeMessage(ev); ... }
  // 新:
  return normalizeEvent(ev, seenMessageRef);
}
```

- [ ] **Step 4: 跑 dify.test.ts**

```bash
cd packages/web && bun run test -- lib/chat/dify.test.ts 2>&1
```

预期全绿（~12 it）。如果红，检查 import 路径 + normalizeEvent 导出名。

- [ ] **Step 5: Commit**

```bash
git add packages/web/lib/chat/dify.ts
git commit -m "refactor(chat): T5 调整 dify.ts — normalize* 迁出, parseStream 用 TextDecoderStream
删 ~60 行 normalize/toCitation/createParseBlock, import 自 chat-event-decoder
parseStream 内部加 body.pipeThrough(new TextDecoderStream())"
```

---

### Task 6: 写 chat-event-decoder.test.ts

**Files:**
- Create: `packages/web/lib/chat/chat-event-decoder.test.ts`

- [ ] **Step 1: 写测试**

```typescript
// chat-event-decoder.test.ts — Dify 事件归一化 + 双块 SSE 解析
import { describe, expect, it } from "vitest";
import {
  createParseBlock, normalizeEvent, normalizeMessage, normalizeMessageEnd,
  normalizeNodeStarted, normalizeNodeFinished, normalizeWorkflowFinished, normalizeError,
} from "./chat-event-decoder";

describe("createParseBlock", () => {
  it("event: xxx + data: {...} 在同一块 → 解析出 event+data", () => {
    const parse = createParseBlock();
    const result = parse('event: message\ndata: {"answer":"hi"}');
    expect(result).toBeTruthy();
    expect(result!.event).toBe("message");
    expect(result!.answer).toBe("hi");
  });

  it("event: xxx 单独一块 (无 data) → 缓存 lastEvent, 返 null", () => {
    const parse = createParseBlock();
    expect(parse("event: message")).toBeNull();
  });

  it("data: {...} 单独一块 → 用 lastEvent 补 event", () => {
    const parse = createParseBlock();
    parse("event: message"); // 缓存 lastEvent
    const result = parse('data: {"answer":"hi"}');
    expect(result!.event).toBe("message");
  });
});

describe("normalizeEvent", () => {
  it("message → yield {type: message, delta}", () => {
    const result = [...normalizeEvent({ event: "message", answer: "你好" })];
    expect(result).toEqual([{ delta: "你好", type: "message" }]);
  });

  it("message_end → yield {type: message_end, conversationId, citations}", () => {
    const result = [...normalizeEvent({
      conversation_id: "c1", event: "message_end", metadata: {
        retriever_resources: [{ document_name: "d1", content: "c1" }],
      },
    })];
    expect(result[0].type).toBe("message_end");
    expect(result[0].conversationId).toBe("c1");
  });

  it("error → yield {type: error, code, message}", () => {
    const result = [...normalizeEvent({ code: "E001", event: "error", message: "失败" })];
    expect(result).toEqual([{ code: "E001", message: "失败", type: "error" }]);
  });

  it("workflow_finished + seenMessage=true → 跳过 answer, 只 yield workflow_done", () => {
    const result = [...normalizeWorkflowFinished(
      { data: { outputs: { answer: "完整答案" } }, event: "workflow_finished", status: "succeeded" },
      { current: true },
    )];
    expect(result).toEqual([{ status: "succeeded", type: "workflow_done" }]);
  });
});
```

- [ ] **Step 2: 跑测试**

```bash
cd packages/web && bun run test -- lib/chat/chat-event-decoder.test.ts 2>&1
```

预期全绿（~8 it）。

- [ ] **Step 3: Commit**

```bash
git add packages/web/lib/chat/chat-event-decoder.test.ts
git commit -m "test(chat): T6 chat-event-decoder.test.ts — normalize* + createParseBlock 覆盖"
```

---

### Task 7: 调整现有测试 + 修 stream-handler.ts import

**Files:**
- Modify: `packages/web/lib/chat/stream-handler.ts`（改 import + processStream 体）
- Modify: `packages/web/lib/chat/sse.test.ts`
- Modify: `packages/web/lib/chat/openai.test.ts`
- Modify: `packages/web/lib/chat/dify.test.ts`
- Modify: `packages/web/lib/chat/stream-handler.test.ts`
- Modify: `packages/web/app/api/chat/messages/route.test.ts`
- No change: `packages/web/components/chat/chat-shell.test.tsx`（mock 形状兼容）

- [ ] **Step 0: 修 stream-handler.ts — 删 parseSseStream import，改内联解析**

`stream-handler.ts:5` import `parseSseStream`，T1 删了该导出，需同步更新。

```typescript
// 删: import { parseSseStream } from "./sse";
// 改: import 只保留需要的类型 (当前 line 4 已有 ChatEvent import)
// 在 processStream 内部 (line 363):
// 旧: for await (const ev of parseSseStream(stream, ac.signal))
// 新: 内联 data: 行解析
for await (const block of parseSseBlocks(stream.pipeThrough(new TextDecoderStream()), ac.signal)) {
  const dataLine = block.split("\n").find((line) => line.startsWith("data: "));
  if (!dataLine) continue;
  const json = dataLine.slice("data: ".length);
  if (json === "[DONE]") continue;
  try {
    const ev = JSON.parse(json) as ChatEvent;
    applyEvent({ cid: convId, deps, ev, msgId: assistantId, state });
  } catch { /* skip */ }
}
```

需要加 import：`import { parseSseBlocks } from "./sse";`

```bash
cd packages/web && bun run test -- lib/chat/stream-handler.test.ts 2>&1
```

预期全绿。

- [ ] **Step 1: 调整 sse.test.ts**

改动：
1. 删 `parseSseStream` 相关测试（`describe("parseSseStream", ...)` 整块）
2. `makeStream` helper 改输出 `ReadableStream<string>` 而非 `ReadableStream<Uint8Array>`
3. 删 `makeChunkedStream` helper（TextDecoderStream 处理字节分块）
4. 保留 `parseSseBlocks` 测试（\n\n 切块、跨块、abort）

```typescript
// 新 helper:
const makeStream = (text: string): ReadableStream<string> =>
  new ReadableStream<string>({
    start(ctrl) {
      ctrl.enqueue(text);
      ctrl.close();
    },
  });
```

- [ ] **Step 2: 调整 openai.test.ts**

`openai.test.ts` 的 `makeStream` 已输出 `ReadableStream<Uint8Array>`（`new TextEncoder().encode(...)`），openai.ts 内部会 `pipeThrough(new TextDecoderStream())`，**不需要改**。只需要确认测试跑绿。

```bash
cd packages/web && bun run test -- lib/chat/openai.test.ts 2>&1
```

- [ ] **Step 3: 调整 dify.test.ts**

dify.test.ts 的 mock 构造 `ReadableStream<Uint8Array>` 给 fetch body，dify.ts 内部 `pipeThrough(new TextDecoderStream())`，**不需要改**。确认跑绿。

```bash
cd packages/web && bun run test -- lib/chat/dify.test.ts 2>&1
```

- [ ] **Step 4: 调整 stream-handler.test.ts**

`stream-handler.test.ts` 当前不直接测 `processStream`（它 mock 了 applyEvent），**不需要改**。确认跑绿。

```bash
cd packages/web && bun run test -- lib/chat/stream-handler.test.ts 2>&1
```

- [ ] **Step 5: 调整 route.test.ts**

`route.test.ts` 的 `parseSSE` helper（lines 78-90）和 `readBodyAsText`（lines 61-75）是自建的 SSE 解析，route.ts 输出格式不变（仍是标准 SSE `data: JSON\n\n`），**不需要改** helper。

但如果 `pipeTextStreamToResponse` 返回的 Response body 格式跟手动构造不同（如不包含 `[DONE]` 行），需要调整测试断言。先跑：

```bash
cd packages/web && bun run test -- app/api/chat/messages/route.test.ts 2>&1
```

如果红，检查 `[DONE]` 是否被 `JsonToSseTransformStream` 自动添加。

- [ ] **Step 6: 跑所有改动的测试**

```bash
cd packages/web && bun run test -- lib/chat/sse.test.ts lib/chat/openai.test.ts lib/chat/dify.test.ts lib/chat/stream-handler.test.ts app/api/chat/messages/route.test.ts lib/chat/chat-event-decoder.test.ts 2>&1
```

预期全部绿色。

- [ ] **Step 7: Commit**

```bash
git add packages/web/lib/chat/sse.test.ts packages/web/lib/chat/stream-handler.test.ts packages/web/app/api/chat/messages/route.test.ts
git commit -m "test(chat): T7 调整现有测试 — sse.test.ts/stream-handler.test.ts/route.test.ts 适配新 sse.ts"
```

---

### Task 8: 全量验证

- [ ] **Step 1: 全量跑 vitest**

```bash
cd packages/web && bun run test 2>&1 | tail -20
```

预期：719+ baseline 全绿。

- [ ] **Step 2: 跑 lint + typecheck + format**

```bash
cd packages/web && bun run lint:fix 2>&1 | tail -5
bun run typecheck 2>&1 | tail -5
bun run format 2>&1 | tail -5
```

- [ ] **Step 3: Commit**

```bash
git commit --allow-empty -m "test(chat): T8 全量验证 pass — vitest/lint/typecheck/format"
```

---

### Task 9: CLAUDE.md 加 AI SDK 条款 + 最终 commit

**Files:**
- Modify: `packages/web/CLAUDE.md`

- [ ] **Step 1: 在 CLAUDE.md 加条款**

```markdown
### AI SDK 协议层 (2026-07-01)

- **chat 协议层用 `TextDecoderStream` + `parseSseBlocks` (AI SDK 7)**，不用手写 TextDecoder 字节解码
- `lib/chat/sse.ts` 只做 `\n\n` 切块，不做字节解码、不做 JSON 解析
- BFF SSE 写入用 `JsonToSseTransformStream` + `pipeTextStreamToResponse`
- 新增 LLM provider 时，byte→text 层用 `ReadableStream.pipeThrough(new TextDecoderStream())`，不再手写 SSE 字节解析
- Dify 双块 SSE 归一化在 `chat-event-decoder.ts`，新建 provider 不需要关心
```

- [ ] **Step 2: 最终 commit**

```bash
git add packages/web/CLAUDE.md
git commit -m "docs(chat): T9 CLAUDE.md 加 AI SDK 7 条款 — TextDecoderStream + JsonToSseTransformStream"
```

---

## 自审清单

**1. Spec 覆盖（每项 spec §2.1 目标对应一个 Task）：**
- §2.1.1 简化 sse.ts = **T1** ✅
- §2.1.2 简化 openai.ts = **T2** ✅
- §2.1.3 简化 route.ts = **T3** ✅
- §2.1.4 新建 chat-event-decoder.ts = **T4** ✅
- §2.1.5 调整 dify.ts = **T5** ✅
- §2.1.6 改 import = T5/T7 覆盖 ✅
- 测试 = **T6-T7** ✅
- 全量验证 = **T8** ✅
- CLAUDE.md = **T9** ✅

**2. 类型一致性：**
- `parseSseBlocks` T1 签名 `ReadableStream<string>` → T2 (openai.ts) 和 T5 (dify.ts) 上游 `pipeThrough(new TextDecoderStream())` ✅
- `parseSseStream` T1 删 → T7 Step 0 stream-handler.ts 同步改内联解析 ✅
- `normalize*` T4 迁入 decoder → T5 dify.ts 调 `normalizeEvent` ✅

**3. 范围控制：**
- 单次 commit 改 < 100 行 ✅
- T6 新建测试文件 ✅
- 业务逻辑 0 变更（只重构协议层） ✅

---

## 执行选项

**Plan complete and saved to `docs/superpowers/plans/2026-06-29-chat-ai-sdk-protocol.md`. Two execution options:**

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
