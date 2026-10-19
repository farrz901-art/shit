# Chat AI SDK 协议层 Phase 2 — 接 useChat (状态管理重构) 实施计划

> **前置**: 已有 [2026-06-29-chat-ai-sdk-protocol.md](./2026-06-29-chat-ai-sdk-protocol.md) Phase 1 (协议层重构) plan,已完成.
> **范围**: 本 plan 落地 spec §10 Phase 2 — 用 AI SDK `useChat` hook 替代项目自实现的状态管理 (~970 行 → ~620 行,净 -350 行).
> **依赖**: Phase 1 (sse.ts/openai.ts/route.ts/dify.ts 简化 + chat-event-decoder.ts) 必须已落地, BFF 输出仍是 ChatEvent SSE 标准格式.

---

## ⚠️ Spike-First 策略 (跟 Phase 1 不同)

Phase 2 不是机械重构 — 它涉及 AI SDK 7 useChat hook 跟项目自实现的 ChatEvent/Message 类型适配, 多个技术决策需要 spike 验证后才能写实施 Task. 因此本 plan 结构是:

- **T0 spike** (3 个 spike 子任务): 验证技术假设,失败则 plan 重写
- **T1-T9 实施 Task** (依赖 T0 通过): spike 通过后追加

**用户已选**: 同样细粒度(拆多个 Task) + 独立 plan 文件 (本文件).

---

## 架构目标

```
现状 (Phase 1 后):
  ChatShell
    └─ useChatShellState (8 个 useState + aborters ref + localStorage draft)
    └─ useServerData (TanStack Query: 列表/CRUD/appendMessage)
    └─ useChatHandlers (handleNew/handleSend/handleStop/persist)
    └─ dispatchSendStream (initMessages + setupAbortController + sendRequest + processStream)
    └─ applyEvent (6 种 ChatEvent dispatch → setMessagesByConv)

目标 (Phase 2 后):
  ChatShell
    ├─ useServerData (保留 — TanStack Query CRUD)
    ├─ useChatWithPersistence ⭐ 新 (包 useChat + onFinish/onError + IDB sync)
    ├─ useChatShellUiState (轻量, 仅 UI state: pendingDeleteId/memoryOpen/shareOpen)
    └─ 删: useChatShellState (8 useState → 2 useState), useChatHandlers 大半, dispatchSendStream
    └─ 删: applyEvent / processStream / handleStreamError (3 出口归 useChat.onError)
    └─ 删: setupAbortController (useChat.stop 接管)
    └─ 保留: ensureConversation + initMessages (IDB 写, 不走 useChat)
    └─ 保留: persistAssistantToServer + persistUserToServer (作为 onFinish callback 内调)
    └─ 新: DifyHttpChatTransport (subclass HttpChatTransport, processResponseStream 转换 ChatEvent → UIMessageChunk)
    └─ 新: ui-message-adapter.ts (ServerMessage ↔ UIMessage ↔ IDB Message 转换层)
```

**核心价值**:
- useChat 内置状态管理 (messages/status/sendMessage/stop) 替代手写
- useChat 内置 abort 流控
- 未来 LLM provider 替换 useChat 默认 transport 即用
- 净 -350 行状态管理代码

**关键约束**:
- BFF `/api/chat/messages` 不变 (Phase 1 已重构成 ChatEvent SSE)
- IDB schema 不变 (仍是 flat Message, 在 useChat 边界转换 UIMessage)
- TanStack Query CRUD 不变
- 迁移 / anon 路径不变

---

## 前提条件 (Phase 1 落地)

| 条件 | 状态 | 验证 |
|------|------|------|
| `sse.ts` 已简化为 `ReadableStream<string> → AsyncIterable<string>` 切块 | ✅ Phase 1 落地 | plan 2026-06-29 T1 |
| BFF route.ts 已用 `JsonToSseTransformStream` | ✅ Phase 1 落地 | plan 2026-06-29 T3 |
| `chat-event-decoder.ts` 存在, normalize* 封装 | ✅ Phase 1 落地 | plan 2026-06-29 T4 |
| `ai@7.0.8` + `@ai-sdk/react@4.0.9` 已安装 | ✅ T0 spike (Phase 1 验证) | ai SDK 7 确认 |
| `HttpChatTransport` 抽象类已确认导出 | ⏳ 待 Phase 2 T0 重新 spike | `node_modules/ai/dist/index.d.ts:5751` |
| `UIMessageChunk` 含 text-delta / reasoning-delta / error / finish 等 | ⏳ 待 Phase 2 T0 重新 spike | `node_modules/ai/dist/index.d.ts:2401-2550` |
| `useChat({ chat: Chat })` 支持外部 Chat 实例 (keying by convId) | ⏳ 待 Phase 2 T0 重新 spike | `@ai-sdk/react/dist/index.d.ts:31-44` |

---

## 文件变化总表 (Phase 2)

| 文件 | 变化 | 行数变化 |
|------|------|---------|
| `lib/chat/use-chat-state.ts` | 删 useChatShellState 大半,保留 useServerData + UI 状态 | 403 → ~120 (-283) |
| `lib/chat/stream-handler.ts` | 删 applyEvent/processStream/handleStreamError,保留 ensureConv/initMessages/persist* | 436 → ~150 (-286) |
| `lib/chat/chat-utils.ts` | 删 setupAbortController,保留 newId + computeEffectiveConversations | 70 → ~50 (-20) |
| `lib/chat/send-request.ts` | 删 (并入 transport prepareSendMessagesRequest) | 62 → 0 (-62) |
| `lib/chat/dify-http-chat-transport.ts` | **新建**: HttpChatTransport subclass, ChatEvent SSE → UIMessageChunk | 0 → ~120 (+120) |
| `lib/chat/ui-message-adapter.ts` | **新建**: ServerMessage ↔ UIMessage ↔ IDB Message | 0 → ~80 (+80) |
| `lib/chat/use-chat-with-persistence.ts` | **新建**: 包 useChat + onFinish/onError + IDB sync | 0 → ~100 (+100) |
| **净变化** | | **~-351 行** (跟 spec §10.1.1 估算一致) |

---

## T0 — Spike 验证 (3 个子任务, 全部通过才能进入 T1)

### T0.1 — Spike: DifyHttpChatTransport processResponseStream 实现

**Goal**: 写一个 HttpChatTransport subclass, 把 BFF 输出的 `data: {ChatEvent JSON}\n\n` 转成 AI SDK 7 UIMessageChunk, 用 mock stream 验证 6 种 ChatEvent 转换正确.

**⚠️ 联网验证修正 (2026-07-01)**: AI SDK 7 `UIMessageChunk` **必须先 emit `text-start` / `reasoning-start`,再多个 `text-delta` / `reasoning-delta`,最后 `text-end` / `reasoning-end`**, 配对同 id ([dist/index.d.ts:2401-2542](packages/web/node_modules/ai/dist/index.d.ts#L2401-L2542)). 裸发 delta 会破坏 streaming 状态机. spike 必须按 start-delta*-end 5 段模式.

**Step 1: 验证 BFF 输出格式**
```bash
cd packages/web && grep -n "JsonToSse\|TextEncoderStream" app/api/chat/messages/route.ts | head -5
```
预期: `JsonToSseTransformStream` 自动 `data: ` 前缀 + `\n\n`, flush 时补 `[DONE]`.

**Step 2: spike DifyHttpChatTransport 实现** (修正后)
写一个临时 transport `lib/chat/dify-http-chat-transport.spike.ts` (commit 后删):

```typescript
// spike: ChatEvent → UIMessageChunk 转换 (5 段 start-delta*-end 模式)
import { HttpChatTransport, type UIMessageChunk } from "ai";
import { parseSseBlocks } from "./sse";
import type { ChatEvent } from "./types";

const TEXT_ID = "msg";
const REASONING_ID = "think";

// (2026-07-01 修正) ChatEvent.message 是流式 delta 序列, 需要维护 per-message start 状态.
// AI SDK 7 内部状态机要求: text-start → text-delta* → text-end. 裸 delta 会丢状态.
const startedTextIds = new Set<string>();
const startedReasoningIds = new Set<string>();

const eventToChunks = (ev: ChatEvent): UIMessageChunk[] => {
  switch (ev.type) {
    case "message": {
      const chunks: UIMessageChunk[] = [];
      if (!startedTextIds.has(TEXT_ID)) {
        chunks.push({ type: "text-start", id: TEXT_ID });
        startedTextIds.add(TEXT_ID);
      }
      chunks.push({ type: "text-delta", id: TEXT_ID, delta: ev.delta });
      return chunks;
    }
    case "message_end": {
      const chunks: UIMessageChunk[] = [];
      if (startedTextIds.has(TEXT_ID)) {
        chunks.push({ type: "text-end", id: TEXT_ID });
        startedTextIds.delete(TEXT_ID);
      }
      chunks.push({ type: "finish", finishReason: "stop" });
      return chunks;
    }
    case "thinking": {
      const chunks: UIMessageChunk[] = [];
      if (!startedReasoningIds.has(REASONING_ID)) {
        chunks.push({ type: "reasoning-start", id: REASONING_ID });
        startedReasoningIds.add(REASONING_ID);
      }
      chunks.push({ type: "reasoning-delta", id: REASONING_ID, delta: `${ev.node}:${ev.status}` });
      return chunks;
    }
    case "error":
      return [{ type: "error", errorText: `[${ev.code}] ${ev.message}` }];
    case "workflow_done":
    case "done":
      return [];
    default:
      return [];
  }
};

export class DifyHttpChatTransport extends HttpChatTransport {
  protected processResponseStream(stream: ReadableStream<Uint8Array>): ReadableStream<UIMessageChunk> {
    const textStream = stream.pipeThrough(new TextDecoderStream());
    return new ReadableStream<UIMessageChunk>({
      async start(controller) {
        try {
          for await (const block of parseSseBlocks(textStream, new AbortController().signal)) {
            const line = block.split("\n").find((l) => l.startsWith("data: "));
            if (!line) continue;
            const json = line.slice("data: ".length);
            if (json === "[DONE]") break;
            try {
              const ev = JSON.parse(json) as ChatEvent;
              for (const chunk of eventToChunks(ev)) controller.enqueue(chunk);
            } catch { /* skip malformed */ }
          }
        } finally {
          controller.close();
          startedTextIds.clear();
          startedReasoningIds.clear();
        }
      },
    });
  }
}
```

**Step 3: 写 spike 测试** (修正后)
```typescript
// dify-http-chat-transport.spike.test.ts
import { describe, expect, it } from "vitest";
import { DifyHttpChatTransport } from "./dify-http-chat-transport.spike";

const makeStream = (sse: string) =>
  new ReadableStream<Uint8Array>({
    start(c) { c.enqueue(new TextEncoder().encode(sse)); c.close(); },
  });

const collectChunks = async (stream: ReadableStream<unknown>): Promise<{ type: string }[]> => {
  const reader = stream.getReader();
  const out: { type: string }[] = [];
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    out.push(value as { type: string });
  }
  return out;
};

describe("DifyHttpChatTransport spike", () => {
  it("message → text-start + text-delta (5 段配对)", async () => {
    const transport = new DifyHttpChatTransport({ api: "/api/chat/messages" });
    const out = transport.processResponseStream(
      makeStream('data: {"type":"message","delta":"hi"}\n\ndata: [DONE]\n\n'),
    );
    const chunks = await collectChunks(out);
    expect(chunks.map((c) => c.type)).toEqual(["text-start", "text-delta"]);
  });

  it("message_end → text-end + finish", async () => {
    const transport = new DifyHttpChatTransport({ api: "/api/chat/messages" });
    const out = transport.processResponseStream(
      makeStream(
        'data: {"type":"message","delta":"x"}\n\n' +
        'data: {"type":"message_end","conversationId":"c1"}\n\n' +
        'data: [DONE]\n\n',
      ),
    );
    const chunks = await collectChunks(out);
    expect(chunks.map((c) => c.type)).toEqual([
      "text-start", "text-delta", "text-end", "finish",
    ]);
  });

  it("error → error chunk (无 text 状态)", async () => {
    const transport = new DifyHttpChatTransport({ api: "/api/chat/messages" });
    const out = transport.processResponseStream(
      makeStream('data: {"type":"error","code":"E001","message":"failed"}\n\ndata: [DONE]\n\n'),
    );
    const chunk = (await out.getReader().read()).value as { type: string; errorText: string };
    expect(chunk.type).toBe("error");
    expect(chunk.errorText).toContain("E001");
  });

  it("thinking → reasoning-start + reasoning-delta (5 段配对)", async () => {
    const transport = new DifyHttpChatTransport({ api: "/api/chat/messages" });
    const out = transport.processResponseStream(
      makeStream('data: {"type":"thinking","node":"n1","status":"started"}\n\ndata: [DONE]\n\n'),
    );
    const chunks = await collectChunks(out);
    expect(chunks.map((c) => c.type)).toEqual(["reasoning-start", "reasoning-delta"]);
  });

  it("多次 message delta → 单 text-start + 多个 text-delta (无重复 start)", async () => {
    const transport = new DifyHttpChatTransport({ api: "/api/chat/messages" });
    const out = transport.processResponseStream(
      makeStream(
        'data: {"type":"message","delta":"a"}\n\n' +
        'data: {"type":"message","delta":"b"}\n\n' +
        'data: {"type":"message","delta":"c"}\n\n' +
        'data: [DONE]\n\n',
      ),
    );
    const chunks = await collectChunks(out);
    expect(chunks.map((c) => c.type)).toEqual([
      "text-start", "text-delta", "text-delta", "text-delta",
    ]);
  });
});
```

**Step 4: 跑测试**
```bash
cd packages/web && bun run test -- dify-http-chat-transport.spike.test.ts 2>&1
```

预期: 5 个 it 全绿. 如果失败, 检查:
- `text-delta` 类型签名 (AI SDK 7 `text-delta` 需要 `id: string` + `delta: string`)
- 5 段顺序 (`text-start` 必须早于首个 `text-delta`;`text-end` 必须晚于最后一个)
- `processResponseStream` 是否是 `protected` 而不是 `public` (可能需要 cast)
- BFF `[DONE]` 行的处理 (必须 break, 否则 reader 会一直等)

**Step 5: 删 spike 文件** (成功后再删, 留 commit 记录)
```bash
rm packages/web/lib/chat/dify-http-chat-transport.spike.ts
rm packages/web/lib/chat/dify-http-chat-transport.spike.test.ts
```

- [ ] T0.1 跑绿 + spike 文件删干净

---

### T0.2 — Spike: useChat keying by convId 方案验证

**Goal**: 验证 useChat 在切换 convId 时是否正确隔离状态 (避免串台).

**⚠️ 联网验证修正 (2026-07-01)**: useChat 源码 ([use-chat.ts](https://raw.githubusercontent.com/vercel/ai/main/packages/react/src/use-chat.ts)) 的重创建逻辑是:
```ts
const shouldRecreateChat =
  ('chat' in options && options.chat !== chatRef.current) ||  // 外部 chat 模式: 必须传新实例
  ('id' in options && options.id != null && chatRef.current.id !== options.id);  // 内部 Chat 模式
```
**当外部传 `chat` 时,id 变化不重创建,只依靠 `options.chat !== chatRef.current`**. 因此 plan T3 的 `useMemo(() => new Chat({ id: convId, messages: initialMessages }), [convId])` 仍然 OK: convId 变 → useMemo 返新 Chat 实例 → useChat 的 `options.chat !== chatRef.current` 命中 → 重置状态. 但 **不能依赖 `id` 字段自动 keying,必须依赖 useMemo 的 deps**. T0.2 spike 必须验证这个不变量.

**Step 1: 验证 AbstractChat 实例化**
```bash
cd packages/web && grep -A 5 "class Chat<\|class AbstractChat" node_modules/@ai-sdk/react/dist/index.d.ts | head -15
```
预期: `Chat` 类支持外部实例化 + 传入 `messages: UIMessage[]` 初始值.

**Step 2: spike Chat 实例 keying**
写临时 spike `lib/chat/use-chat-spike.tsx`:
```typescript
"use client";
import { Chat, useChat } from "@ai-sdk/react";
import { useMemo } from "react";

// spike: 每个 convId 一个 Chat 实例
export const useSpikeChat = (convId: string, initialMessages: Parameters<typeof Chat>[0]["messages"]) => {
  const chat = useMemo(
    () => new Chat({ id: convId, messages: initialMessages }),
    [convId], // convId 变 → 新实例 → useChat 自动重置
  );
  return useChat({ chat });
};
```

**Step 3: 写 spike 测试** (vitest + @testing-library/react)
覆盖 2 个 case:
1. **同 convId**: `useSpikeChat("a", [msg1])` → `useSpikeChat("a", [msg1])` → messages 不变 (ref stable)
2. **切 convId**: `useSpikeChat("a", [msg1])` → `useSpikeChat("b", [])` → messages 重置为 [] (新实例)

mock 用 vitest `vi.mock("@ai-sdk/react")` + 假 Chat 类追踪 `lastMessages`.

- [ ] T0.2 跑绿 + spike 文件删干净

---

### T0.3 — Spike: IDB Message ↔ UIMessage 边界

**Goal**: 验证把项目 flat Message 转换为 UIMessage 不会丢字段 (citations / thinking / interrupted).

**Step 1: 写 spike adapter `lib/chat/ui-message-adapter.spike.ts`**
```typescript
import type { UIMessage } from "ai";
import type { Message } from "./types";

// spike: flat Message → UIMessage
export const messageToUIMessage = (m: Message): UIMessage => ({
  id: m.id,
  role: m.role,
  parts: m.thinking?.length
    ? [
        ...m.thinking.map((t) => ({ type: "reasoning" as const, text: `${t.node}:${t.status}` })),
        { type: "text" as const, text: m.content },
      ]
    : [{ type: "text" as const, text: m.content }],
  metadata: {
    conversationId: m.conversationId,
    citations: m.citations,
    interrupted: m.interrupted,
    createdAt: m.createdAt,
  },
});

// spike: UIMessage → flat Message
export const uiMessageToMessage = (u: UIMessage): Message => {
  const text = u.parts.filter((p) => p.type === "text").map((p) => p.text).join("");
  const thinking = u.parts
    .filter((p) => p.type === "reasoning")
    .map((p) => {
      const parts = p.text.split(":");
      return { node: parts[0] ?? "", status: (parts[1] as "started" | "finished") ?? "started" };
    });
  return {
    id: u.id,
    role: u.role as "user" | "assistant",
    content: text,
    createdAt: (u.metadata as { createdAt?: number })?.createdAt ?? Date.now(),
    conversationId: (u.metadata as { conversationId?: string })?.conversationId,
    citations: (u.metadata as { citations?: Message["citations"] })?.citations,
    thinking: thinking.length ? thinking : undefined,
    interrupted: (u.metadata as { interrupted?: boolean })?.interrupted,
  };
};
```

**Step 2: 写 spike 测试**
覆盖 5 个 case:
1. user message (无 thinking/citations)
2. assistant message (有 content + thinking)
3. assistant interrupted message (有 metadata.interrupted)
4. assistant with citations
5. round-trip (message → ui → message, 内容一致)

- [ ] T0.3 跑绿 + spike 文件删干净

---

### T0 验收门禁

T0.1 + T0.2 + T0.3 **全部跑绿** 才能进入 T1. 任一失败:
- T0.1 失败 → UIMessageChunk 5 段模式 (start-delta*-end) 不兼容,需要重新设计 (e.g. 用 `createUIMessageStream` server-side 重写 BFF,plan 重写)
- T0.2 失败 → useChat keying 方案改用单实例 + internal messagesByConv 分区 (跟 spec 估算 +150 行)
- T0.3 失败 → IDB schema 可能需要直接存 UIMessage (破坏"IDB 不变"约束, plan 重写)

---

## T1 — 新建 DifyHttpChatTransport (基于 T0.1 spike)

**Files**:
- Create: `packages/web/lib/chat/dify-http-chat-transport.ts` (~120 行)
- Create: `packages/web/lib/chat/dify-http-chat-transport.test.ts` (~80 行)

**职责**: HttpChatTransport subclass, 实现 2 个 override:
1. `processResponseStream(stream)` — ChatEvent SSE → UIMessageChunk (T0.1 spike 已验证)
2. `prepareSendMessagesRequest({messages, ...})` — 注入 `user` (accountId 或 anon UUID) + `conversationId` + `inputs.buyer_key` + `files`

**依赖**: T0.1 通过

**TDD**: 先写测试覆盖 6 种 ChatEvent 转换 + body 注入.

- [ ] Step 1: 写 dify-http-chat-transport.test.ts (test first)
- [ ] Step 2: 跑测试 (red)
- [ ] Step 3: 实现 dify-http-chat-transport.ts
- [ ] Step 4: 跑测试 (green)
- [ ] Step 5: 跑 lint + typecheck
- [ ] Step 6: Commit

---

## T2 — 新建 ui-message-adapter (基于 T0.3 spike)

**Files**:
- Create: `packages/web/lib/chat/ui-message-adapter.ts` (~80 行)
- Create: `packages/web/lib/chat/ui-message-adapter.test.ts` (~60 行)

**职责**: 3 个转换函数:
1. `messageToUIMessage(m: Message): UIMessage` — IDB flat → useChat
2. `uiMessageToMessage(u: UIMessage): Message` — useChat → IDB flat
3. `serverMessageToUIMessage(s: ServerMessage): UIMessage` — TanStack fetch → useChat (load 历史)

**依赖**: T0.3 通过

**特殊处理**:
- `interrupted: true` → `metadata.interrupted: boolean`
- `citations: Citation[]` → `metadata.citations: Citation[]`
- `thinking: {node, status, detail?}[]` → `parts: ReasoningUIPart[]` + `metadata.thinking`

- [ ] Step 1: 写 ui-message-adapter.test.ts (test first, 6 case)
- [ ] Step 2: 跑测试 (red)
- [ ] Step 3: 实现 ui-message-adapter.ts
- [ ] Step 4: 跑测试 (green)
- [ ] Step 5: 跑 lint + typecheck
- [ ] Step 6: Commit

---

## T3 — 新建 useChatWithPersistence hook (基于 T0.2 spike)

**Files**:
- Create: `packages/web/lib/chat/use-chat-with-persistence.ts` (~100 行)
- Create: `packages/web/lib/chat/use-chat-with-persistence.test.ts` (~80 行)

**职责**: 包 useChat, 加 3 层:
1. **Transport 注入**: `new DifyHttpChatTransport({ api: '/api/chat/messages', body: { user, conversationId, inputs } })`
2. **持久化 callback**: `onFinish` → `persistAssistantToServer` (account) + `saveMessages` (IDB, anon+account); `onError` → `handleStreamError` 3 出口 (或简化为 onError 一个)
3. **Chat 实例 keying**: `useMemo(() => new Chat({ id: convId, messages: initialMessages }), [convId])`

**核心 API**:
```typescript
export const useChatWithPersistence = ({
  convId, isAccount, accountId, difyConversationId, initialMessages,
  appendMessageMut,
}: UseChatWithPersistenceParams): UseChatReturn => {
  const transport = useMemo(() => new DifyHttpChatTransport({
    api: '/api/chat/messages',
    prepareSendMessagesRequest: ({ messages }) => ({
      body: {
        user: isAccount ? accountId : getAnonUserId(),
        conversationId: difyConversationId,
        inputs: isAccount ? { buyer_key: String(accountId) } : {},
        query: messages[messages.length - 1]?.parts.find((p) => p.type === "text")?.text ?? "",
      },
    }),
  }), [isAccount, accountId, difyConversationId]);

  const chat = useMemo(
    () => new Chat({
      id: convId,
      messages: initialMessages.map(messageToUIMessage),
    }),
    [convId],
  );

  const result = useChat({
    chat,
    transport,
    onFinish: ({ message }) => {
      const flat = uiMessageToMessage(message);
      if (isAccount && appendMessageMut) {
        persistAssistantToServer({ ... });
      }
      saveMessages(convId, [flat]); // IDB 永远写
    },
    onError: (error) => {
      // 处理 AbortError (interrupted) vs 其他 error
      // 简化: onError 统一存 partial content + finishReason="error"
    },
  });

  return result;
};
```

**依赖**: T1 (transport) + T2 (adapter) + T0.2 (keying)

**TDD**: 先写测试覆盖:
- isAccount=true → body 包含 accountId + buyer_key
- isAccount=false → body 包含 anon UUID
- onFinish → 触发 persistAssistantToServer (mock) + saveMessages (mock)
- onError → interrupted vs error 两种分支
- keying: 切 convId → messages 重置

- [ ] Step 1: 写 use-chat-with-persistence.test.ts (test first)
- [ ] Step 2: 跑测试 (red)
- [ ] Step 3: 实现 use-chat-with-persistence.ts
- [ ] Step 4: 跑测试 (green)
- [ ] Step 5: 跑 lint + typecheck
- [ ] Step 6: Commit

---

## T4 — 简化 use-chat-state.ts (用 useChatWithPersistence 替代 useChatShellState)

**Files**:
- Modify: `packages/web/lib/chat/use-chat-state.ts` (403 → ~120 行)

**改动**:
1. `useChatShellState` 简化为只含 UI 状态:
   - `conversations` (保留 — useServerData 内)
   - `currentId` (保留)
   - `pendingDeleteId`, `memoryOpen`, `shareOpen` (保留 UI)
   - **删**: `messagesByConv`, `streamingConvId`, `aborters`, `draft`
2. **删** `useChatHandlers.handleSend` + `handleStop` (改用 useChatWithPersistence.sendMessage/stop)
3. **删** `dispatchSendStream` 整个函数
4. **删** `doCreateServerConv` (并入新 hook 或 useServerData)
5. **保留** `useServerData` (TanStack Query, 不动)
6. **新增** `useChatShellUiState` (轻量 UI state, ~30 行)

**关键约束**:
- `draft` (localStorage) 保留在 Composer 内部 (react-use useLocalStorage), 不放 useChatShellUiState
- `currentId` 仍是 React state, 但 `messages[currentId]` 来自 useChatWithPersistence

**依赖**: T3 (useChatWithPersistence)

- [ ] Step 1: 写 use-chat-state.test.ts (覆盖保留 API: useServerData + 新 useChatShellUiState)
- [ ] Step 2: 跑测试 (red)
- [ ] Step 3: 重构 use-chat-state.ts
- [ ] Step 4: 跑测试 (green)
- [ ] Step 5: 跑 lint + typecheck
- [ ] Step 6: Commit

---

## T5 — 简化 stream-handler.ts (删 applyEvent/processStream/handleStreamError)

**Files**:
- Modify: `packages/web/lib/chat/stream-handler.ts` (436 → ~150 行)

**删**:
- `applyEvent` (~60 行) — 改用 useChat.onFinish + onError
- `processStream` (~40 行) — 改用 useChat 内置流处理
- `handleStreamError` (~50 行) — 改用 useChat.onError + interrupted flag 在 metadata

**保留**:
- `initMessages` (~80 行) — 创建 user + assistant slot, IDB 写, account 调 persistUserToServer
- `ensureConversation` (~30 行) — 创建新 conv (IDB)
- `persistAssistantToServer` (~30 行) — account 调, 改作为 useChatWithPersistence.onFinish callback 内调
- `persistUserToServer` (~10 行) — initMessages 内调
- `EVENT_HANDLERS` map — 删 (applyEvent 删了)

**依赖**: T4 (useChatState 重构后, stream-handler 调用方都改了)

- [ ] Step 1: 写 stream-handler.test.ts (覆盖保留: initMessages/ensureConv/persist*)
- [ ] Step 2: 跑测试 (red)
- [ ] Step 3: 重构 stream-handler.ts
- [ ] Step 4: 跑测试 (green)
- [ ] Step 5: 跑 lint + typecheck
- [ ] Step 6: Commit

---

## T6 — 删 chat-utils.ts:setupAbortController + send-request.ts 整个文件

**Files**:
- Modify: `packages/web/lib/chat/chat-utils.ts` (70 → ~50 行)
- Delete: `packages/web/lib/chat/send-request.ts` (62 行, 并入 DifyHttpChatTransport.prepareSendMessagesRequest)

**改动**:
1. chat-utils.ts 删 `setupAbortController` (~20 行), `getNextConversationId` 移到 useServerData 内部
2. send-request.ts 整个删,逻辑并入 T1 DifyHttpChatTransport

**依赖**: T1 (transport 接管 sendRequest) + T5 (stream-handler 不再需要 AbortController 字典)

- [ ] Step 1: 删 setupAbortController 函数
- [ ] Step 2: 跑 chat-utils.test.ts (应仍绿, 仅删函数不影响其他测试)
- [ ] Step 3: 删 send-request.ts 整个文件 + send-request.test.ts
- [ ] Step 4: 跑 typecheck (确认无 dangling import)
- [ ] Step 5: Commit

---

## T7 — 调整 ChatShell 组件接入 useChatWithPersistence

**Files**:
- Modify: `packages/web/components/chat/chat-shell.tsx`
- Modify: `packages/web/components/chat/chat-shell.test.tsx`

**改动**:
1. `useChatShellState` 调用 → 拆为 `useChatShellUiState` + `useChatWithPersistence`
2. `useChatHandlers.handleSend` 调用 → `useChatWithPersistence.sendMessage`
3. `useChatHandlers.handleStop` 调用 → `useChatWithPersistence.stop`
4. `messagesByConv[currentId]` 显示 → `useChatWithPersistence.messages` (UIMessage[] → 转回 Message 给 MessageBubble)
5. `streamingConvId` 显示 → `useChatWithPersistence.status === 'streaming'`
6. `aborters.current[convId].abort()` 调用 → `useChatWithPersistence.stop()`

**关键约束**:
- MessageBubble 接口不变 (仍接 `Message`, 在 ChatShell 内做 UIMessage → Message)
- ConversationList / ChatHeader / Composer / AppConfirm / MemoryManagementDialog / ShareDialog 不变
- Composer 内部 `draft` (localStorage) 保留 react-use

**依赖**: T3-T6

- [ ] Step 1: 跑现有 chat-shell.test.tsx (确认 mock 形状)
- [ ] Step 2: 改 ChatShell 接入 useChatWithPersistence
- [ ] Step 3: 跑 chat-shell.test.tsx (调 mock)
- [ ] Step 4: 跑 lint + typecheck
- [ ] Step 5: Commit

---

## T8 — 跑全量 vitest + lint + typecheck + format

**Files**: 无 (验证)

```bash
cd packages/web && bun run test 2>&1 | tail -20  # 719+ baseline
bun run test:coverage 2>&1 | tail -10  # chat 模块覆盖不降
bun run lint 2>&1 | tail -5
bun run typecheck 2>&1 | tail -5
bun run format 2>&1 | tail -5
```

**验收**:
- vitest 全绿 (pre-existing 8 fail 不算新 fail)
- 覆盖率: chat 模块不降
- lint 0 error
- typecheck 0 error
- format 0 error

**依赖**: T1-T7 全过

- [ ] Step 1: 全量 vitest
- [ ] Step 2: 跑覆盖率
- [ ] Step 3: lint + typecheck + format
- [ ] Step 4: Commit (if 任何 format 重排)

---

## T9 — E2E 手工验证 + CLAUDE.md 更新

**E2E 验收** (跟 spec §7.1 一致):
1. 启动后端 `uv run python main.py` + 前端 `bun run dev`
2. 登录账号 → 发消息 → 流式回答 + citations 正常
3. 切 anon → 发消息 → IDB 持久化
4. 切回登录 → 迁移弹框不弹
5. 点 stop → AbortController 真断开, partial content + interrupted Badge
6. 刷新页面 → messages 持久化 (account 走 server / anon 走 IDB)

**CLAUDE.md 更新**:
```markdown
### Chat 状态管理 (2026-07-01 Phase 2)

- **chat 用 AI SDK useChat + 自实现 DifyHttpChatTransport**, 不用 useChatShellState 手写状态
- `useChatWithPersistence` hook 是入口: 注入 transport + 持久化 callback + Chat 实例 keying by convId
- 新增 LLM provider 时, 改 `DifyHttpChatTransport.prepareSendMessagesRequest` 或建新 subclass, 不改 chat-shell
- IDB Message ↔ UIMessage 适配在 `ui-message-adapter.ts`, 新增字段时同步改 3 个转换函数
- 删了 useChatShellState 大半 / applyEvent / processStream / setupAbortController / dispatchSendStream
```

**依赖**: T8

- [ ] Step 1: 手工 E2E 验证
- [ ] Step 2: 更新 CLAUDE.md
- [ ] Step 3: 最终 commit

---

## 自审清单

**1. Spec 覆盖（每项 spec §10.1.3 替换对应一个 Task）:**

| Spec §10.1.3 替换项 | Task | 状态 |
|---------------------|------|------|
| `messagesByConv` + `streamingConvId` → `useChat.messages` + `useChat.status` | T3 + T4 | ✅ |
| `draft` (localStorage) → Composer 内部 react-use (保留, 不归 useChat) | T4 | ✅ |
| `handleSend` + `dispatchSendStream` → `useChat.sendMessage` | T3 + T7 | ✅ |
| `handleStop` + `aborters.current` → `useChat.stop` | T3 + T6 | ✅ |
| `processStream` + `applyEvent` → useChat 内部 + transport subclass | T1 + T5 | ✅ |
| `initMessages` (user + assistant slot) → useChat 自动 (但 IDB 写需保留) | T5 | ✅ |
| `persistAssistantToServer` → `onFinish` callback | T3 + T5 | ✅ |
| `handleStreamError` → `onError` callback (3 出口归一) | T3 | ✅ |
| `sendRequest` → transport `prepareSendMessagesRequest` | T1 + T6 | ✅ |
| `setupAbortController` → useChat 内置 | T6 | ✅ |
| `ensureConversation` → **保留简化版** (仅首次创建 + IDB 写) | T5 | ✅ |
| `computeEffectiveConversations` → **保留** (会话列表合并与 useChat 正交) | 不动 | ✅ |

**2. 范围控制:**
- 单次 commit 改 < 200 行 (T3/T4 接近上限)
- 新建 3 文件 (transport/adapter/hook), 改 4 文件, 删 1 文件
- 业务逻辑 0 变更 (只重构状态管理)

**3. 风险对应:**
- **UIMessage ↔ Message 适配** → T0.3 spike + T2 adapter
- **useChat keying by convId** → T0.2 spike + T3 hook
- **anon 路径同 transport** → T1 transport body 注入支持 user/conversationId 条件
- **DifyHttpChatTransport 兼容性** → T0.1 spike + T1 transport

---

## 执行选项

**Plan complete and saved to `docs/superpowers/plans/2026-07-01-chat-usechat-state.md`. Three execution options:**

**1. Subagent-Driven + Spike-First (recommended)** — T0 spike 由 subagent 并行做, T0 全过后 T1-T9 subagent 串行做, 每 Task 双 review (spec + quality)

**2. Spike First + Inline Execution** — T0 spike 我自己跑 (验证后再写 plan), T1-T9 我执行

**3. Plan Rewrite (T0 假设不可行)** — 跑 T0 spike, 发现问题后回退, 重写 plan

**Which approach?**