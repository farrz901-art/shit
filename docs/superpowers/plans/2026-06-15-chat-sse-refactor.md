# ChatShell SSE 解析重构 + messageCount 修复 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `packages/web` 智能体聊天的 SSE 字节切分逻辑去重 (`DifyChatProvider` + `ChatShell` 共用 `parseSseBlocks` 工具), 同时修 `messageCount` 在 React 18 strict mode 下因 `upsertConversation` 写在 `setConversations` 回调里导致的双写 + 漂移 bug.

**Architecture:**
- **抽 `parseSseBlocks`**: 纯函数, 字节流 → SSE 裸块文本 `AsyncIterable<string>`, 不解析内容
- **抽 `parseSseStream`**: 字节流 → `ChatEvent` 快捷版, 给 ChatShell 用 (BFF 输出格式)
- **DifyChatProvider 改用 `parseSseBlocks` 切字节**, 内部 `parseBlock` + `normalize` 逻辑完全保留, 顺手把模块级 `lastEvent` 闭包化 (修多实例并发 bug)
- **ChatShell 替手写 SSE 循环**: `for await (const ev of parseSseStream(...))` 一行替 30 行
- **`messageCount` 单一来源**: 在 `applyEvent.message_end` 里从 `messages.filter(m => m.role === 'user').length` 算, 移除 `handleSend` 手动 +1
- **`upsertConversation` 拉出 `setConversations` 回调**: 修 React 18 strict mode 双写

**Tech Stack:**
- TypeScript 5.x + tsgo
- vitest 4.x + jsdom
- bun (package manager)
- React 19.2 (strict mode 默认开)
- DifyChatProvider (现有 lib/chat/dify.ts)

**Spec:** [../specs/2026-06-15-chat-sse-refactor-design.md](../specs/2026-06-15-chat-sse-refactor-design.md)

---

## 文件结构总览 (4 任务, 0.5d 估)

| 任务 | 工作量 | 核心改动 |
|---|---|---|
| 1 抽 SSE 切分器 (TDD) | 0.15d | 新建 `lib/chat/sse.ts` + `sse.test.ts` |
| 2 DifyChatProvider 用 parseSseBlocks | 0.1d | `dify.ts` 内部重构, 闭包化 lastEvent |
| 3 ChatShell 用 parseSseStream | 0.1d | `ChatShell.tsx` 替手写 SSE 循环 |
| 4 修 messageCount 一致性 | 0.15d | `ChatShell.tsx` 拆 setConversations/upsertConversation, 单一来源 |

**并行性**: 任务 1 必须先做, 2 和 3 都依赖 1, 2 和 3 之间可并行, 4 依赖 3 (改的是 ChatShell 同一函数).

---

## Task 1: 抽 SSE 切分器 (parseSseBlocks + parseSseStream)

**Files:**
- Create: `packages/web/lib/chat/sse.ts`
- Create: `packages/web/lib/chat/sse.test.ts`

- [ ] **Step 1: 写失败测试 (sse.test.ts)**

```typescript
// 字节流切块器 + ChatEvent 解析器
// 跟 DifyChatProvider 复用同一套切块逻辑, ChatShell 替手写 SSE 循环
import { describe, expect, it } from "vitest";
import { parseSseBlocks, parseSseStream } from "./sse";

function makeStream(text: string): ReadableStream<Uint8Array> {
  return new ReadableStream<Uint8Array>({
    start(c) {
      c.enqueue(new TextEncoder().encode(text));
      c.close();
    },
  });
}

function makeChunkedStream(text: string, chunkSize: number): ReadableStream<Uint8Array> {
  return new ReadableStream<Uint8Array>({
    start(c) {
      for (let i = 0; i < text.length; i += chunkSize) {
        c.enqueue(new TextEncoder().encode(text.slice(i, i + chunkSize)));
      }
      c.close();
    },
  });
}

async function collect<T>(it: AsyncIterable<T>): Promise<T[]> {
  const out: T[] = [];
  for await (const x of it) out.push(x);
  return out;
}

describe("parseSseBlocks", () => {
  it("单块完整到达 → yield 一次", async () => {
    const stream = makeStream("event: message\ndata: {\"x\":1}\n\n");
    const blocks = await collect(parseSseBlocks(stream, new AbortController().signal));
    expect(blocks).toEqual(["event: message\ndata: {\"x\":1}"]);
  });

  it("多块按 \\n\\n 切分", async () => {
    const stream = makeStream("data: a\n\ndata: b\n\ndata: c\n\n");
    const blocks = await collect(parseSseBlocks(stream, new AbortController().signal));
    expect(blocks).toEqual(["data: a", "data: b", "data: c"]);
  });

  it("跨 chunk 切分不丢不重", async () => {
    // 1 字节 1 chunk, 强制分块边界
    const stream = makeChunkedStream("data: hello\n\n", 1);
    const blocks = await collect(parseSseBlocks(stream, new AbortController().signal));
    expect(blocks).toEqual(["data: hello"]);
  });

  it("signal.aborted → 抛 AbortError", async () => {
    const ac = new AbortController();
    const never = new ReadableStream<Uint8Array>({ start() {} });
    ac.abort();
    await expect(async () => {
      for await (const _ of parseSseBlocks(never, ac.signal)) {
        /* noop */
      }
    }).rejects.toThrow(/aborted/);
  });
});

describe("parseSseStream", () => {
  it("data: <json>\\n\\n → yield ChatEvent 对象", async () => {
    const ev = { type: "message", delta: "hi" };
    const stream = makeStream(`data: ${JSON.stringify(ev)}\n\n`);
    const events = await collect(parseSseStream(stream, new AbortController().signal));
    expect(events).toEqual([ev]);
  });

  it("data: [DONE]\\n\\n → 跳过, 不 yield", async () => {
    const stream = makeStream("data: [DONE]\n\n");
    const events = await collect(parseSseStream(stream, new AbortController().signal));
    expect(events).toEqual([]);
  });

  it("非法 JSON 块 → 跳过, 不抛", async () => {
    const stream = makeStream("data: {not json}\n\ndata: {\"x\":1}\n\n");
    const events = await collect(parseSseStream(stream, new AbortController().signal));
    // 跳过非法块, 只 yield 合法块
    expect(events.length).toBe(1);
  });

  it("空块 / 无 data 行 → 跳过", async () => {
    const stream = makeStream("\n\ndata: {\"x\":1}\n\n");
    const events = await collect(parseSseStream(stream, new AbortController().signal));
    expect(events).toEqual([{ x: 1 }]);
  });
});
```

- [ ] **Step 2: 跑测试确认红**

```bash
cd packages/web && bun x vitest run lib/chat/sse.test.ts
```

期望: FAIL (sse.ts 不存在, 导入失败)

- [ ] **Step 3: 写实现 (sse.ts)**

```typescript
// SSE 字节流切分器 (BFF 输出格式 + 通用 Dify 原始格式都用同一套切块)
// 切块规则: 按 "\n\n" 分隔, 跨 chunk 累积
// 解析: parseSseBlocks 只切不解析, parseSseStream 直接出 ChatEvent 对象
import type { ChatEvent } from "./types";

export async function* parseSseBlocks(
  stream: ReadableStream<Uint8Array>,
  signal: AbortSignal,
): AsyncIterable<string> {
  const reader = stream.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";
  try {
    while (true) {
      if (signal.aborted) {
        await reader.cancel();
        throw new DOMException("aborted", "AbortError");
      }
      const { value, done } = await reader.read();
      if (done) {
        break;
      }
      buffer += decoder.decode(value, { stream: true });
      let idx: number;
      while ((idx = buffer.indexOf("\n\n")) !== -1) {
        const block = buffer.slice(0, idx);
        buffer = buffer.slice(idx + 2);
        yield block;
      }
    }
  } finally {
    reader.releaseLock();
  }
}

// 快捷版: 抽 data: 行, JSON.parse 后 yield (BFF 输出格式专用)
export async function* parseSseStream(
  stream: ReadableStream<Uint8Array>,
  signal: AbortSignal,
): AsyncIterable<ChatEvent> {
  for await (const block of parseSseBlocks(stream, signal)) {
    const dataLine = block.split("\n").find((l) => l.startsWith("data: "));
    if (!dataLine) {
      continue;
    }
    const json = dataLine.slice("data: ".length);
    if (json === "[DONE]") {
      continue;
    }
    try {
      const parsed = JSON.parse(json) as ChatEvent;
      yield parsed;
    } catch {
      // 非法 JSON 跳过, 不让单块畸形卡死流
      console.warn(`[sse] 跳过非法 JSON 块: ${json.slice(0, 80)}`);
    }
  }
}
```

- [ ] **Step 4: 跑测试确认绿**

```bash
cd packages/web && bun x vitest run lib/chat/sse.test.ts
```

期望: PASS, 7 个 test 全绿

- [ ] **Step 5: Lint + typecheck**

```bash
cd packages/web && bun run lint && bun run typecheck
```

期望: 0 error

- [ ] **Step 6: Commit**

```bash
git add packages/web/lib/chat/sse.ts packages/web/lib/chat/sse.test.ts
git commit -m "feat(chat): extract shared SSE block parser

parseSseBlocks 切字节流到 SSE 裸块文本, parseSseStream 字节直出 ChatEvent
对象, 给 ChatShell 替手写 SSE 循环用. DifyChatProvider 后续任务接入."
```

---

## Task 2: DifyChatProvider 用 parseSseBlocks (闭包化 lastEvent)

**Files:**
- Modify: `packages/web/lib/chat/dify.ts:51-94` (parseStream 内部) + `:234-267` (模块级 lastEvent)

- [ ] **Step 1: 跑基线测试确认绿**

```bash
cd packages/web && bun x vitest run lib/chat/dify.test.ts
```

期望: PASS, 14 个 dify 测试全绿

- [ ] **Step 2: 改 dify.ts parseStream 内部 + 闭包化 lastEvent**

**改前** ([dify.ts:51-94](../../packages/web/lib/chat/dify.ts#L51-L94)):

```typescript
private async *parseStream(
  body: ReadableStream<Uint8Array>,
  signal: AbortSignal,
): AsyncIterable<ChatEvent> {
  const reader = body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";
  // ... 30 行手写切块 + parseBlock 循环
}
```

**改后**: 内部用 `parseSseBlocks` 切字节, 解析规则 (`parseBlock` + `normalize`) 保留

```typescript
import { parseSseBlocks } from "./sse";

// (在 DifyChatProvider 类内, 替换整个 parseStream 方法):
private async *parseStream(
  body: ReadableStream<Uint8Array>,
  signal: AbortSignal,
): AsyncIterable<ChatEvent> {
  // Dify Chatflow app 双发射防御: seenMessageRef 让 normalize 知道是否
  // 已经流过 message delta, 见过了则 workflow_finished.outputs.answer 跳过
  const seenMessageRef = { current: false };
  for await (const block of parseSseBlocks(body, signal)) {
    const ev = parseBlock(block);
    if (!ev) {
      continue;
    }
    for (const chatEv of this.normalize(ev, seenMessageRef)) {
      if (chatEv.type === "message") {
        seenMessageRef.current = true;
      }
      yield chatEv;
    }
  }
}
```

**闭包化 `lastEvent`** ([dify.ts:232-267](../../packages/web/lib/chat/dify.ts#L232-L267)):

**改前**:
```typescript
// Dify SSE 格式: event: xxx\n\ndata: {...}\n\n
// Event 和 data 在不同块, 需要累积 event name
let lastEvent = "";

function parseBlock(block: string): RawEvent | null {
  const lines = block.split("\n");
  let event = "";
  let data = "";
  for (const line of lines) {
    if (line.startsWith("event:")) {
      event = line.slice("event:".length).trim();
    } else if (line.startsWith("data:")) {
      data += line.slice("data:".length).trimStart();
    }
  }

  if (event && !data) {
    lastEvent = event;
    return null;
  }
  if (data && !event) {
    event = lastEvent;
  }
  // ...
}
```

**改后**: `lastEvent` 移到 `parseBlock` 闭包内, 每次调用独立

```typescript
function parseBlock(block: string): RawEvent | null {
  // 闭包内 lastEvent 替代模块级变量, 修多实例并发互相覆盖 bug
  const lines = block.split("\n");
  let event = "";
  let data = "";
  for (const line of lines) {
    if (line.startsWith("event:")) {
      event = line.slice("event:".length).trim();
    } else if (line.startsWith("data:")) {
      data += line.slice("data:".length).trimStart();
    }
  }

  // 用 Dify 块内 event 字段覆盖, 没有则保持块内 event
  if (data && !event && blockLastEvent) {
    event = blockLastEvent;
  }

  if (event && !data) {
    blockLastEvent = event;
    return null;
  }
  if (!event || !data) {
    return null;
  }
  try {
    const parsed = JSON.parse(data);
    return { event: parsed.event ?? event, ...parsed } as RawEvent;
  } catch {
    return null;
  }
  let blockLastEvent = "";
}
```

- [ ] **Step 3: 跑 dify 测试确认绿 (回归)**

```bash
cd packages/web && bun x vitest run lib/chat/dify.test.ts
```

期望: PASS, 14 个测试全绿 (证明 `parseSseBlocks` 切块跟原手写行为一致)

- [ ] **Step 4: Lint + typecheck**

```bash
cd packages/web && bun run lint && bun run typecheck
```

期望: 0 error

- [ ] **Step 5: Commit**

```bash
git add packages/web/lib/chat/dify.ts
git commit -m "refactor(chat): DifyChatProvider uses parseSseBlocks

内部用共享切块器替 30 行手写 SSE 循环, parseBlock + normalize 逻辑保留.
顺手把模块级 lastEvent 闭包化, 修多实例并发互相覆盖 bug."
```

---

## Task 3: ChatShell 用 parseSseStream 替手写 SSE 循环

**Files:**
- Modify: `packages/web/components/chat/ChatShell.tsx:186-218`

- [ ] **Step 1: 跑基线测试确认绿**

```bash
cd packages/web && bun x vitest run components/chat/ChatShell.test.tsx
```

期望: PASS, 现有 ChatShell 测试全绿

- [ ] **Step 2: 改 ChatShell.tsx handleSend 内的手写 SSE 循环**

**改前** ([ChatShell.tsx:179-218](../../packages/web/components/chat/ChatShell.tsx#L179-L218)):

```typescript
try {
  const stream = await chatApi.sendMessage({
    conversationId: conv?.difyConversationId,
    inputs: {},
    query: text,
    user: convId!,
  });
  const reader = stream.getReader();
  const decoder = new TextDecoder("utf-8");
  let buf = "";

  ac.signal.addEventListener("abort", () => reader.cancel(), { once: true });

  while (true) {
    if (ac.signal.aborted) {
      reader.cancel();
      break;
    }
    const { value, done } = await reader.read();
    if (done) {
      break;
    }
    buf += decoder.decode(value, { stream: true });
    let idx: number;
    while ((idx = buf.indexOf("\n\n")) !== -1) {
      const block = buf.slice(0, idx);
      buf = buf.slice(idx + 2);
      const dataLine = block.split("\n").find((l) => l.startsWith("data: "));
      if (!dataLine) {
        continue;
      }
      const json = dataLine.slice("data: ".length);
      if (json === "[DONE]") {
        continue;
      }
      const ev = JSON.parse(json) as ChatEvent;
      applyEvent(convId!, assistantId, ev);
    }
  }
} catch (error) {
  // ... AbortError + 错误处理
}
```

**改后** (在文件顶部 import 加一行):

```typescript
import { parseSseStream } from "@/lib/chat/sse";
```

**handleSend 内部替换**:

```typescript
try {
  const stream = await chatApi.sendMessage({
    conversationId: conv?.difyConversationId,
    inputs: {},
    query: text,
    user: convId!,
  });

  for await (const ev of parseSseStream(stream, ac.signal)) {
    applyEvent(convId!, assistantId, ev);
  }
} catch (error) {
  if ((error as Error).name === "AbortError") {
    setMessagesByConv((m) => {
      const list = m[convId!] ?? [];
      return {
        ...m,
        [convId!]: list.map((x) => (x.id === assistantId ? { ...x, interrupted: true } : x)),
      };
    });
  } else {
    applyEvent(convId!, assistantId, {
      code: "client_error",
      message: (error as Error).message,
      type: "error",
    });
  }
}
```

**注意**: 删掉 `ac.signal.addEventListener("abort", () => reader.cancel(), { once: true })`, 因为 `parseSseStream` 内部已经处理 abort → cancel + 抛 AbortError.

- [ ] **Step 3: 跑 ChatShell 测试确认绿**

```bash
cd packages/web && bun x vitest run components/chat/ChatShell.test.tsx
```

期望: PASS, 现有 5 个测试全绿 (mock 返回的 ReadableStream 仍兼容, `parseSseStream` 内部用同一个切块器)

- [ ] **Step 4: Lint + typecheck**

```bash
cd packages/web && bun run lint && bun run typecheck
```

期望: 0 error

- [ ] **Step 5: Commit**

```bash
git add packages/web/components/chat/ChatShell.tsx
git commit -m "refactor(chat): ChatShell uses parseSseStream

替 30 行手写 SSE 切块 + JSON.parse 循环, for await 一行接 parseSseStream.
abort / [DONE] / 非法 JSON 行为跟原来一致."
```

---

## Task 4: 修 messageCount 一致性 (拆 setConversations / upsertConversation + 单一来源)

**Files:**
- Modify: `packages/web/components/chat/ChatShell.tsx` (3 处: handleSend / applyEvent)
- Modify: `packages/web/components/chat/ChatShell.test.tsx` (加 2 个测试)

- [ ] **Step 1: 写失败测试 (ChatShell.test.tsx 加 2 个)**

```typescript
// 追加到现有 describe("ChatShell", () => { ... }) 块内:

it("流到 message_end → conv.messageCount == user message 数", async () => {
  vi.mocked(chatApi.sendMessage).mockResolvedValue(
    makeStream([
      { delta: "你", type: "message" },
      { delta: "好", type: "message" },
      { conversationId: "c1", type: "message_end" },
    ]),
  );

  renderInI18n(<ChatShell />);
  fireEvent.click(screen.getByTestId("new-conv"));
  const ta = await screen.findByTestId("composer-textarea");
  fireEvent.change(ta, { target: { value: "hi" } });
  fireEvent.keyDown(ta, { key: "Enter" });

  // 等流结束 (message_end 触发 messageCount 刷新)
  await waitFor(() => {
    const stored = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "{}");
    const conv = stored.items?.[0];
    expect(conv?.messageCount).toBe(1);
  });
});

it("message_end 后 difyConversationId 持久化到 localStorage", async () => {
  vi.mocked(chatApi.sendMessage).mockResolvedValue(
    makeStream([
      { delta: "ok", type: "message" },
      { conversationId: "dify-conv-xyz", type: "message_end" },
    ]),
  );

  renderInI18n(<ChatShell />);
  fireEvent.click(screen.getByTestId("new-conv"));
  const ta = await screen.findByTestId("composer-textarea");
  fireEvent.change(ta, { target: { value: "hi" } });
  fireEvent.keyDown(ta, { key: "Enter" });

  await waitFor(() => {
    const stored = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "{}");
    const conv = stored.items?.[0];
    expect(conv?.difyConversationId).toBe("dify-conv-xyz");
  });
});
```

- [ ] **Step 2: 跑测试确认红 (部分)**

```bash
cd packages/web && bun x vitest run components/chat/ChatShell.test.tsx
```

期望: 第 1 个测试可能通过 (因为 handleSend 里手动 +1 还在), 第 2 个测试 FAIL (`difyConversationId` 写入路径在 `setConversations` 回调里有 React 18 strict mode 双写问题, mock 环境下可能通过也可能失败, 但 messageCount 来源不是从 messages 算的是真问题)

- [ ] **Step 3: 改 handleSend - 移除手动 messageCount +1**

**改前** ([ChatShell.tsx:152-169](../../packages/web/components/chat/ChatShell.tsx#L152-L169)):

```typescript
setConversations((prev) => {
  const idx = prev.findIndex((c) => c.id === convId);
  const next = [...prev];
  if (idx !== -1) {
    // Bug fix: +1 (只计 user message, assistant placeholder 不算)
    const c = {
      ...next[idx],
      messageCount: next[idx].messageCount + 1,
      updatedAt: Date.now(),
    };
    if (c.title === "新对话") {
      c.title = text.slice(0, 20);
    }
    next[idx] = c;
    upsertConversation(c);
  }
  return next;
});
```

**改后**: 只刷 title + updatedAt, 不动 messageCount (统一在 `applyEvent.message_end` 里算)

```typescript
setConversations((prev) => {
  const idx = prev.findIndex((c) => c.id === convId);
  const next = [...prev];
  if (idx !== -1) {
    const c = { ...next[idx], updatedAt: Date.now() };
    if (c.title === "新对话") {
      c.title = text.slice(0, 20);
    }
    next[idx] = c;
    upsertConversation(c);
  }
  return next;
});
```

- [ ] **Step 4: 改 applyEvent - 拆 setConversations / upsertConversation + 算 messageCount 单一来源**

**改前** ([ChatShell.tsx:247-288](../../packages/web/components/chat/ChatShell.tsx#L247-L288)):

```typescript
function applyEvent(cid: string, msgId: string, ev: ChatEvent) {
  setMessagesByConv((m) => {
    const list = m[cid] ?? [];
    const updated = list.map((x) => {
      if (x.id !== msgId) {
        return x;
      }
      if (ev.type === "message") {
        return { ...x, content: x.content + ev.delta };
      }
      if (ev.type === "message_end") {
        // Bug fix: 存储 Dify 返回的 conversationId
        if (ev.conversationId) {
          setConversations((prev) => {
            const idx2 = prev.findIndex((c) => c.id === cid);
            if (idx2 !== -1) {
              const next2 = [...prev];
              next2[idx2] = { ...next2[idx2], difyConversationId: ev.conversationId };
              upsertConversation(next2[idx2]);
              return next2;
            }
            return prev;
          });
        }
        return { ...x, citations: ev.citations };
      }
      if (ev.type === "thinking") {
        const t = [
          ...(x.thinking ?? []),
          { detail: ev.detail, node: ev.node, status: ev.status },
        ];
        return { ...x, thinking: t };
      }
      if (ev.type === "error") {
        return { ...x, content: `${x.content}\n\n[错误] ${ev.code}: ${ev.message}` };
      }
      return x;
    });
    persistMessages(cid, updated);
    return { ...m, [cid]: updated };
  });
}
```

**改后**: 把 `message_end` 的 setConversations 拆出, 跟 `setMessagesByConv` 平级; 算 messageCount 单一来源

```typescript
function applyEvent(cid: string, msgId: string, ev: ChatEvent) {
  setMessagesByConv((m) => {
    const list = m[cid] ?? [];
    const updated = list.map((x) => {
      if (x.id !== msgId) {
        return x;
      }
      if (ev.type === "message") {
        return { ...x, content: x.content + ev.delta };
      }
      if (ev.type === "message_end") {
        return { ...x, citations: ev.citations };
      }
      if (ev.type === "thinking") {
        const t = [
          ...(x.thinking ?? []),
          { detail: ev.detail, node: ev.node, status: ev.status },
        ];
        return { ...x, thinking: t };
      }
      if (ev.type === "error") {
        return { ...x, content: `${x.content}\n\n[错误] ${ev.code}: ${ev.message}` };
      }
      return x;
    });
    persistMessages(cid, updated);
    return { ...m, [cid]: updated };
  });

  // message_end: 刷新 messageCount + difyConversationId, 单一来源从 messages 算
  // 拆到 setMessagesByConv 之外, 修 React 18 strict mode 双写
  if (ev.type === "message_end") {
    const currentMessages = messagesByConv[cid] ?? [];
    const messageCount = currentMessages.filter((x) => x.role === "user").length;
    setConversations((prev) => {
      const idx2 = prev.findIndex((c) => c.id === cid);
      if (idx2 === -1) {
        return prev;
      }
      const next2 = [...prev];
      next2[idx2] = {
        ...next2[idx2],
        ...(ev.conversationId ? { difyConversationId: ev.conversationId } : {}),
        messageCount,
        updatedAt: Date.now(),
      };
      // 在 setConversations 回调外, side effect 干净, 不会双写
      upsertConversation(next2[idx2]);
      return next2;
    });
  }
}
```

**注意**: 这段代码依赖外层 `handleSend` 闭包内的 `messagesByConv` state 引用, 每次 `handleSend` 调用时是当时的快照. 因为 `setMessagesByConv` 是异步的, 同一 tick 内 `messagesByConv` 还没更新, 但这里只是读 messages 列表算 messageCount, 不是触发 setMessagesByConv, 读旧值也 OK —— `setMessagesByConv` 完成后会触发组件重渲染, 后续 `applyEvent` 再读时就是新值.

- [ ] **Step 5: 跑 ChatShell 测试确认绿**

```bash
cd packages/web && bun x vitest run components/chat/ChatShell.test.tsx
```

期望: PASS, 7 个测试全绿 (5 旧 + 2 新)

- [ ] **Step 6: 跑全量 ChatShell + sse + dify 测试确认无回归**

```bash
cd packages/web && bun x vitest run components/chat/ChatShell.test.tsx lib/chat/sse.test.ts lib/chat/dify.test.ts
```

期望: 26 个测试全绿

- [ ] **Step 7: Lint + typecheck + format**

```bash
cd packages/web && bun run lint && bun run typecheck && bun run format
```

期望: 0 error, format 自动修无残留

- [ ] **Step 8: Commit**

```bash
git add packages/web/components/chat/ChatShell.tsx packages/web/components/chat/ChatShell.test.tsx
git commit -m "fix(chat): messageCount consistency in applyEvent

- setConversations + upsertConversation 解耦, 修 React 18 strict mode 双写
- messageCount 单一来源: messages.filter(m => m.role === 'user').length
- 移除 handleSend 手动 +1, 由 applyEvent.message_end 统一刷新
- 加 2 个测试: 1) messageCount 跟 user message 数一致 2) difyConversationId 持久化"
```

---

## 最终验证

- [ ] **Step 1: 跑全量 web 测试**

```bash
cd packages/web && bun run test
```

期望: 全绿, 测试时间 < 2 分钟

- [ ] **Step 2: 跑全量 lint + typecheck + format check**

```bash
cd packages/web && bun run lint && bun run typecheck && bun run format:check
```

期望: 0 error

- [ ] **Step 3: 确认 4 个 commit 全部就位**

```bash
git log --oneline -4
```

期望:
```
<hash> fix(chat): messageCount consistency in applyEvent
<hash> refactor(chat): ChatShell uses parseSseStream
<hash> refactor(chat): DifyChatProvider uses parseSseBlocks
<hash> feat(chat): extract shared SSE block parser
```

- [ ] **Step 4: 跟 spec 校验**

```bash
diff <(git log --format=%s -4) <(echo "fix(chat): messageCount consistency in applyEvent
refactor(chat): ChatShell uses parseSseStream
refactor(chat): DifyChatProvider uses parseSseBlocks
feat(chat): extract shared SSE block parser")
```

期望: 无 diff

---

## 风险与回滚

参见 [spec § 风险与回滚](../specs/2026-06-15-chat-sse-refactor-design.md#风险与回滚).

简述:
- 任务 2 改 DifyChatProvider 切块: 现有 14 个 dify.test 是安全网, 任何回退直接 `git revert <hash>`
- 任务 4 拆 setConversations/upsertConversation: 2 个新测试覆盖 messageCount 跟 difyConversationId, 回退同样 `git revert`
