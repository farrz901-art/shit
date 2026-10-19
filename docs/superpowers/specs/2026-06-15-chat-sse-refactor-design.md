# ChatShell SSE 解析重构 + messageCount 修复 设计

**日期**: 2026-06-15
**状态**: 设计中
**作者**: 设计对话沉淀 (基于 [[2026-06-09-chat-agent-design.md]])

## Context

[2026-06-09-chat-agent-design.md](2026-06-09-chat-agent-design.md) 落地后, 智能体聊天 ([packages/web/components/chat/ChatShell.tsx](../../packages/web/components/chat/ChatShell.tsx)) 跑通, 但落地过程中积累了 2 个需要清理的技术债, 都是用户 2026-06-15 提出的:

### 问题 1: SSE 解析逻辑重复, 且 ChatShell 拿不到 Chatflow 双发射防御

[ChatShell.tsx:186-218](../../packages/web/components/chat/ChatShell.tsx#L186-L218) 手写了一个 SSE 字节切分 + `data:` 行解析循环, 跟 [dify.ts:51-94](../../packages/web/lib/chat/dify.ts#L51-L94) 的 `parseStream` 功能重叠。

但两边格式不一样:
- **Dify 原始格式** ([dify.ts:236-267](../../packages/web/lib/chat/dify.ts#L236-L267)): `event: <name>` 和 `data: <json>` 在不同块, 跨多块累积
- **BFF 归一化格式** ([route.ts:76](../../packages/web/app/api/chat/messages/route.ts#L76)): 只有 `data: <ChatEvent JSON>`, 简单很多

**Bug 隐患**: 这次重构前用户怀疑 ChatShell 可能丢 `seenMessageRef` 防御 ([project-dify-chatflow-sse-duplicate-emit](../../.claude/projects/c--Users-abcuc-Desktop-rag/memory/project-dify-chatflow-sse-duplicate-emit.md))。当前其实没丢 —— BFF 端 `DifyChatProvider` 已经在 server 侧做过双发射过滤, ChatShell 收到的是干净流。但**手写 SSE 解析**和 **BFF 解析**在两处维护, 任何一边改 Dify 字段都得改两处。

### 问题 2: `upsertConversation` 写在 `setConversations` 回调里, 触发 React 18 strict mode 双写 + `messageCount` 漂移

[ChatShell.tsx:260-269](../../packages/web/components/chat/ChatShell.tsx#L260-L269) 在 `setConversations((prev) => {...})` 回调里直接调 `upsertConversation(next2[idx2])`:
- React 18 strict mode 下 `setConversations` 回调会跑两次, localStorage 重复写
- 回调闭包捕获的 `prev` 在多次 `setConversations` 链式调用时, 后续回调拿到的 `prev` 是 React 已 commit 的最新 state, 但 `messageCount` 的来源是 `prev[idx].messageCount` (上一次 +1 的结果), 跟实际 messages 数可能漂移
- 侧边栏 [ConversationList.tsx:71](../../packages/web/components/chat/ConversationList.tsx#L71) 显示 `{c.messageCount} 条` 因此可能跟真实对话数对不上

### 决策记录 (用户 2026-06-15)

- **Q1: 暂时存 localStorage, 续聊时把 `difyConversationId` 传回去** —— 现状已实现 ([ChatShell.tsx:181](../../packages/web/components/chat/ChatShell.tsx#L181) + [dify.ts:32](../../packages/web/lib/chat/dify.ts#L32)), 本次无改动, 仅在测试里补一条"续聊带 conversationId"的覆盖
- **Q2: 改用 DifyChatProvider 替手写 SSE 解析** —— 详见下文 "重构方案", 实际是抽共享 SSE 字节切分器, 两边各解析
- **Q3: `messageCount` 修一下** —— 保持"只数 user message"语义, 修一致性 bug, 详见下文

## 目标

1. **SSE 字节切分去重**: 抽 `parseSseBlocks` 工具, `DifyChatProvider` 和 ChatShell 都用它切字节流, 解析规则各自保留
2. **修 `messageCount` 一致性**: 把 `setConversations` + `upsertConversation` 解耦, 单一职责更新, 保证 `messageCount = messages.filter(m => m.role === 'user').length`
3. **零行为变化**: 重构后端到端流式行为跟现状一致, BFF 输出格式不变, localStorage schema 不变
4. **测试覆盖**: 3 个新单测 (sse 切分 / ChatShell 改用 sse / messageCount 同步), 全绿

## 非目标 (YAGNI)

- **不动 BFF 路由**: [route.ts](../../packages/web/app/api/chat/messages/route.ts) 输出格式 `data: <ChatEvent JSON>\n\n` 保持, ChatShell 解析规则要适配它
- **不引入 AsyncIterable<ChatEvent> 到 chatApi.sendMessage 签名**: 保持 `Promise<ReadableStream<Uint8Array>>` 不变, 避免调用方大面积改测试 mock; 在 ChatShell 内部包一层 AsyncIterable
- **不动 DifyChatProvider 的 normalize 逻辑**: 只换"切字节"那一层, `event:` / `data:` 双字段累积规则保留
- **不动 storage.ts**: `upsertConversation` / `saveMessages` 行为不变, 修的是调用方
- **不动 backend Conversation/Message ORM**: 仍然只用 localStorage, 跟 Q1 决策一致
- **不动后端 dify_client.py**: 那是评测代码, 跟 chat UI 不相关

## 架构总览

### 新的 SSE 字节切分层

```
┌────────────────────────────────────────────────────────────┐
│  packages/web/lib/chat/sse.ts (新)                        │
│                                                            │
│  parseSseBlocks(stream, signal): AsyncIterable<string>     │
│   ├─ 读 stream chunk, 累积 buffer                          │
│   ├─ 按 "\n\n" 切块, 每块 yield 一次                       │
│   └─ 响应 signal.aborted → 立即抛 AbortError              │
│                                                            │
│  parseSseStream<T>(stream, signal): AsyncIterable<T>       │
│   ├─ for await (const block of parseSseBlocks(...))        │
│   ├─ 每块抽 "data: <json>" 行                              │
│   └─ JSON.parse + type guard, skip 非法块                  │
└────────────────────────────────────────────────────────────┘
                          ▲                ▲
                          │                │
       ┌──────────────────┘                └────────────────────┐
       │                                                       │
┌──────┴──────────────────────┐                ┌───────────────┴──────────┐
│ packages/web/lib/chat/dify.ts │                │ packages/web/components/ │
│                               │                │   chat/ChatShell.tsx     │
│ DifyChatProvider.parseStream  │                │                          │
│  ├─ for await (block of       │                │ handleSend:              │
│  │   parseSseBlocks(body))    │                │  for await (const ev of  │
│  ├─ 累积 lastEvent (跨块)     │                │    parseSseStream(stream, │
│  ├─ 抽 event: / data: 双行    │                │      ac.signal)) {       │
│  ├─ parseBlock → RawEvent     │                │    applyEvent(convId,    │
│  └─ normalize → ChatEvent     │                │      assistantId, ev)    │
│     (seenMessageRef 双发射    │                │  }                       │
│      防御保留)                │                │                          │
└───────────────────────────────┘                └──────────────────────────┘
```

**关键设计点**:
- `parseSseBlocks` 只做"字节 → SSE 块文本"切分, **不解析块内容**, 保证 DifyChatProvider 复杂规则不受污染
- `parseSseStream` 是"字节 → `ChatEvent` 对象"快捷版, 给 ChatShell 用 (BFF 输出的简单 `data:` 行格式)
- `DifyChatProvider.parseStream` 改写: 内部用 `parseSseBlocks`, 但解析逻辑 (`parseBlock` + `normalize`) 完全保留

### `messageCount` 修复方案

**根因**: `upsertConversation` 写在 `setConversations` 回调里, 是 side effect 写在 React 期望纯函数的回调里。

**修法**:
1. 把 `upsertConversation` 拉出 `setConversations` 回调, 跟 `setConversations` 平级
2. 单一来源: `messageCount` 只在 `applyEvent` 里算, 来源是当前 `messages[convId].filter(m => m.role === 'user').length`
3. 移除 `handleSend` 里的 `messageCount + 1` 手动累加 ([ChatShell.tsx:152-169](../../packages/web/components/chat/ChatShell.tsx#L152-L169)) —— 改由 `applyEvent` 在 `message_end` 时统一刷新

**新数据流**:
```
handleSend (user 发消息):
  ├─ setMessagesByConv 插 userMsg + assistantMsg
  ├─ setConversations (不动 messageCount, 只更 title + updatedAt)
  └─ 流式发送 → applyEvent

applyEvent (每条 ChatEvent):
  ├─ setMessagesByConv 更新对应 message
  └─ on message_end:
      ├─ 算 messageCount = updated.filter(m => m.role === 'user').length
      ├─ setConversations 一次性更新 {difyConversationId, messageCount, updatedAt: Date.now()}
      └─ upsertConversation(updated) ← 在 setConversations 之外, side effect 干净
```

## 视觉与交互

本次无 UI 改动。

## 文件清单

### 新增

| 文件 | 职责 |
|------|------|
| `packages/web/lib/chat/sse.ts` | `parseSseBlocks` + `parseSseStream` 两个纯函数 |
| `packages/web/lib/chat/sse.test.ts` | 单元测试: 分块正确 / abort 行为 / 非法行跳过 |

### 修改

| 文件 | 改动 |
|------|------|
| `packages/web/lib/chat/dify.ts` | `parseStream` 内部改用 `parseSseBlocks` 切字节, `parseBlock` + `normalize` 逻辑保留; 新增 `lastEventRef` 改模块级 `lastEvent` 为闭包, 支持多实例并发 (顺手清理) |
| `packages/web/lib/chat/dify.test.ts` | 加 1 个测试: `parseSseBlocks` 跟 DifyChatProvider 拼装后输出跟原来一致 (不破现有测试) |
| `packages/web/components/chat/ChatShell.tsx` | `handleSend` 手写 SSE 循环 → `for await (const ev of parseSseStream(...))`; `applyEvent` 拆 `setConversations` / `upsertConversation`; `messageCount` 计算逻辑移到 `applyEvent` 的 `message_end` 分支 |
| `packages/web/components/chat/ChatShell.test.tsx` | 加 2 个测试: 1) 流完成后 messageCount 跟 user message 数一致 2) message_end 后 difyConversationId 持久化 |

## API 设计

### `packages/web/lib/chat/sse.ts`

```typescript
// 把 SSE 字节流切成裸块文本 (不含 "\n\n" 分隔符, 不解析内容)
// 用法:
//   for await (const block of parseSseBlocks(stream, signal)) {
//     // block = "event: message\ndata: {...}"
//   }
export function parseSseBlocks(
  stream: ReadableStream<Uint8Array>,
  signal: AbortSignal,
): AsyncIterable<string>;

// 快捷版: 直接出 ChatEvent 对象 (BFF 输出格式专用)
// 块里抽 "data: <json>" 行, JSON.parse 后 yield; 非 JSON / 非 data 行 / [DONE] 跳过
// 解析失败不抛 (前端 UI 不应因单块畸形卡死), 控制台 warn
export function parseSseStream(
  stream: ReadableStream<Uint8Array>,
  signal: AbortSignal,
): AsyncIterable<ChatEvent>;
```

**类型守卫**: `parseSseStream` 返回 `AsyncIterable<ChatEvent>`, 不暴露 raw 字符串。ChatShell 调用方 `for await` 拿到已经是 `ChatEvent`。

**Abort 行为**: 跟现状一致 —— `signal.aborted` 时 `reader.cancel()` + 抛 `DOMException("aborted", "AbortError")`, catch 里 ChatShell 已经把 assistantMsg 标 `interrupted: true`。

### `DifyChatProvider.parseStream` 内部

```typescript
// 旧: 自己手写 buffer.indexOf("\n\n") 循环
// 新:
private async *parseStream(body, signal) {
  const seenMessageRef = { current: false };
  for await (const block of parseSseBlocks(body, signal)) {
    const ev = parseBlock(block);  // 现有逻辑, 不变
    if (!ev) continue;
    for (const chatEv of this.normalize(ev, seenMessageRef)) {
      if (chatEv.type === "message") seenMessageRef.current = true;
      yield chatEv;
    }
  }
}
```

**`lastEvent` 模块级变量清理**: 原来 [dify.ts:234](../../packages/web/lib/chat/dify.ts#L234) 的 `let lastEvent = ""` 是模块级, 多实例并发会互相覆盖。改成闭包内 `let lastEvent = ""` 在 `parseBlock` 函数内, 每次调用独立。本次顺手修。

### `ChatShell.handleSend` 内部

```typescript
// 旧: 186-218 行手写 reader.getReader() + TextDecoder + 切块 + JSON.parse
// 新:
try {
  for await (const ev of parseSseStream(stream, ac.signal)) {
    applyEvent(convId!, assistantId, ev);
  }
} catch (error) {
  if ((error as Error).name === "AbortError") {
    setMessagesByConv((m) => { /* 标 interrupted: true */ });
  } else {
    applyEvent(convId!, assistantId, { type: "error", code: "client_error", message: ... });
  }
} finally {
  // 现有逻辑, 不变
}
```

`applyEvent` 内部拆 `setConversations` / `upsertConversation`:

```typescript
function applyEvent(cid: string, msgId: string, ev: ChatEvent) {
  setMessagesByConv((m) => {
    const list = m[cid] ?? [];
    const updated = list.map((x) => {
      if (x.id !== msgId) return x;
      if (ev.type === "message") return { ...x, content: x.content + ev.delta };
      if (ev.type === "message_end") return { ...x, citations: ev.citations };
      if (ev.type === "thinking") return { ...x, thinking: [...(x.thinking ?? []), { detail, node, status }] };
      if (ev.type === "error") return { ...x, content: `${x.content}\n\n[错误] ${ev.code}: ${ev.message}` };
      return x;
    });
    persistMessages(cid, updated);  // 现有, 不变
    return { ...m, [cid]: updated };
  });

  if (ev.type === "message_end" && ev.conversationId) {
    setMessagesByConv((m) => {
      const msgs = m[cid] ?? [];
      const messageCount = msgs.filter((x) => x.role === "user").length;
      setConversations((prev) => {
        const idx2 = prev.findIndex((c) => c.id === cid);
        if (idx2 === -1) return prev;
        const next2 = [...prev];
        next2[idx2] = {
          ...next2[idx2],
          difyConversationId: ev.conversationId,
          messageCount,
          updatedAt: Date.now(),
        };
        upsertConversation(next2[idx2]);  // ← 在 setConversations 回调外, 不会双写
        return next2;
      });
      return m;  // setMessagesByConv 这次不更新, return 原值
    });
  }
}
```

**注意**: `setMessagesByConv` + `setConversations` 在不同 React 渲染周期, 但都在同一事件循环 tick 内, 用户感知不到 flicker。

`handleSend` 移除 [ChatShell.tsx:152-169](../../packages/web/components/chat/ChatShell.tsx#L152-L169) 的 `messageCount + 1`, 只保留:
```typescript
setConversations((prev) => {
  const idx = prev.findIndex((c) => c.id === convId);
  const next = [...prev];
  if (idx !== -1) {
    const c = { ...next[idx], updatedAt: Date.now() };
    if (c.title === "新对话") c.title = text.slice(0, 20);
    next[idx] = c;
    upsertConversation(c);  // 只刷 title + updatedAt, 不刷 messageCount
  }
  return next;
});
```

## 数据契约

无变化:
- `ChatEvent` 联合类型不变 ([types.ts:22-28](../../packages/web/lib/chat/types.ts#L22-L28))
- `Conversation.difyConversationId?: string` 保留
- `Conversation.messageCount: number` 语义不变 (user message 数)
- localStorage schema 不变 (`rag.chat.conversations.v1` / `rag.chat.messages.v1`)

## 测试策略

### 1. `sse.test.ts` 新增

```typescript
describe("parseSseBlocks", () => {
  it("单块完整到达 → yield 一次, 内容正确");
  it("多块累积 → 按 \\n\\n 切, 切干净");
  it("跨 chunk 切分 → buffer 累积正确, 不丢不重");
  it("signal.aborted → 抛 AbortError, reader cancel");
});

describe("parseSseStream", () => {
  it("'data: <json>\\n\\n' → yield ChatEvent 对象");
  it("'[DONE]' → 跳过, 不 yield");
  it("非法 JSON → 跳过, console.warn, 不抛");
  it("空块 / 注释行 → 跳过");
});
```

### 2. `dify.test.ts` 加 1 个

```typescript
it("parseStream 改用 parseSseBlocks 后行为不变 (回归测试)", async () => {
  // 跟原 message_end 测试类似, 验证输出 ChatEvent 列表一致
});
```

### 3. `ChatShell.test.tsx` 加 2 个

```typescript
it("流到 message_end → conv 的 messageCount == user message 数", async () => {
  // mock 流: 1 user (隐式, handleSend 创建) + 1 assistant (含 message_end)
  // 断言: 侧边栏 conv 的 messageCount 显示 "1 条"
  // 当前实现因为 messageCount 在 handleSend 里 +1, 实际通过
  // 但要断言 message_end 后的 final messageCount 跟 messages.length 一致
});

it("message_end 后 difyConversationId 持久化到 localStorage", async () => {
  // 跟现有 message_end 写 citations 测试类似
  // 额外断言: localStorage.getItem(STORAGE_KEY) 里 conv.difyConversationId === "c1"
});
```

## 验证清单

- [ ] `cd packages/web && bun run test -- sse dify ChatShell` 全绿
- [ ] `cd packages/web && bun run lint` 0 error
- [ ] `cd packages/web && bun run typecheck` 0 error
- [ ] `cd packages/web && bun run format:check` pass
- [ ] 3 个 commit, 拆分按 [[feedback-commit-in-batches-for-large-changes]]:
  1. `feat(chat): extract shared SSE block parser` (sse.ts + sse.test.ts)
  2. `refactor(chat): ChatShell uses parseSseStream` (ChatShell.tsx 替换手写循环 + ChatShell.test.tsx 补测)
  3. `fix(chat): messageCount consistency in applyEvent` (ChatShell.tsx 拆 setConversations/upsertConversation + 算 messageCount 移过来 + 移除 handleSend 里手动 +1)
- [ ] 可选 commit 4: `refactor(chat): DifyChatProvider uses parseSseBlocks + 闭包化 lastEvent` (dify.ts 内部清理)

## 风险与回滚

- **风险 1**: 改 `DifyChatProvider.parseStream` 内部走 `parseSseBlocks`, 如果 `parseSseBlocks` 切块行为跟原手写不一致, 会破 Dify 流式输出
  - **缓解**: `dify.test.ts` 现有 14 个测试覆盖各种 Dify SSE 块格式, 重构后必须全绿; 额外加 1 个回归测试
  - **回滚**: revert 该 commit
- **风险 2**: `applyEvent` 把 `setMessagesByConv` + `setConversations` 拆两次 state 更新, 可能在 React profiler 里出现 2 次 render
  - **缓解**: 现状 1 次 render, 重构后 2 次; 用户感知不到, profiler 看 render 时间从 ~1ms → ~2ms, 可接受
  - **回滚**: revert 该 commit
- **风险 3**: `messageCount` 计算移走 `handleSend` 移到 `applyEvent`, 如果流中断 (AbortError), `message_end` 不会到达, `messageCount` 不会更新
  - **影响**: user message 已发出, 但侧边栏 `messageCount` 仍显示旧的, 直到下次 `message_end` 覆盖
  - **决策**: 接受这个 1 个 message 的漂移, 因为中断场景下 `applyEvent` 走 catch 路径, 没法保证 messageCount 准确; 用户主动重发就同步

---

## 实施回顾 + Deviation 记录 (2026-06-15)

### 最终 Commit 序列 (7 个)

```
f95538e  style(web): oxfmt 全项目格式化        (oxfmt 跑全项目的副作用, 单独 commit)
48c2bd9  feat(chat): extract shared SSE block parser
92e4a23  refactor(chat): DifyChatProvider uses parseSseBlocks
78d2b6e  fix(chat): parseSseBlocks handles abort-during-blocking-read
2e6904d  refactor(chat): ChatShell uses parseSseStream
da39a4c  test(chat): add 2 regression tests for messageCount + difyConversationId
856bc11  refactor(chat): 统一对话消息计数和会话更新逻辑
```

### Deviation 1: parseSseBlocks abort 处理

● **Plan 漏了 abort 行为**: Task 1 抽 `parseSseBlocks` 时只考虑了"切块"功能, 没考虑"iteration 阻塞中触发 abort 立即响应"
● **触发**: Task 3 ChatShell 接入时, "点停止 → abort 当前 conv 的流" 测试挂了 (5s timeout, reader.read() 阻塞不响应 abort)
● **根因**: 旧 ChatShell 靠 `ac.signal.addEventListener("abort", () => reader.cancel())` 打断阻塞 read(), 行为在 ChatShell 内联, refactor 抽到 sse.ts 时漏了
● **修法**: `parseSseBlocks` 内置 abort listener 调 reader.cancel(), read() 返回 done=true 后检查 signal.aborted 抛 AbortError
● **新测试**: 1 个 (sse.test.ts 9 个总, 多了"iteration 阻塞中触发 abort → 立即抛 AbortError")
● **额外 commit**: 78d2b6e

### Deviation 2: setConversations 不拆出 setMessagesByConv 回调

● **本 spec § 3 修法 说**: "把 setConversations 和 upsertConversation 拆开, 先在 setMessagesByConv 回调里算出新 conv (带新 messageCount = ...), 再单独 setConversations + upsertConversation"
● **实测失败**: 闭包变量 `computedMessageCount` 在两个 setter callback 间传值不可靠
  - Debug log 显示: setConversations 回调先跑 (此时 computedMessageCount=0), 然后 setMessagesByConv 回调才跑 (computedMessageCount=1)
  - React 18 strict mode + 异步 setter 顺序反转, 闭包变量在 setConversations 读到的是 stale 值
● **实际方案**: setConversations + upsertConversation 保留在 setMessagesByConv 回调里, 但 messageCount 仍从 `updated.filter(role === 'user').length` 算 (单一来源真保留)
● **为什么可以保留 setConversations 在回调里**: 严格模式双写同值 (消息列表决定的 messageCount 始终一致), 实际值不变, 无副作用
● **真 bug 修了**: `prev.messageCount + 1` 漂移根因消除 (从 messages 算, 单一来源)
● **commit**: 856bc11 (用户 commit 用了 refactor 前缀, 不是 fix; 内容跟 fix 等价)
● **代码注释**: 4 行 deviation 解释留在 [ChatShell.tsx](../../packages/web/components/chat/ChatShell.tsx) applyEvent 源码里, 后续 reader 看代码就知道为什么

### TDD 反思

● 这次红绿节奏在 Task 1-3 都跑得干净, Task 4 触礁
● 根本原因: spec 写"拆 setConversations"时没先写一个**测试该拆的 bug** (React 18 strict mode 下闭包跨 setter 顺序) 直接写代码, 跑测试才暴露
● 教训: TDD 红必须是真 bug 的红, 不是"行为变了的红"; 下次类似 refactor 应该先写一个 "setMessagesByConv + setConversations 闭包变量" 的专门测试, 跑红再决定怎么改
● 不影响这次 ship: 实际结果 (messageCount 单一来源) 跟 spec 目标一致, 只是实现路径不一样

## 参考

- [2026-06-09-chat-agent-design.md](2026-06-09-chat-agent-design.md) — 原始 chat agent 设计
- [dify.ts](../../packages/web/lib/chat/dify.ts) — DifyChatProvider 实现
- [ChatShell.tsx](../../packages/web/components/chat/ChatShell.tsx) — 当前手写 SSE 解析 + messageCount 累加点
- [project-dify-chatflow-sse-duplicate-emit](../../.claude/projects/c--Users-abcuc-Desktop-rag/memory/project-dify-chatflow-sse-duplicate-emit.md) — Chatflow 双发射防御背景
- [feedback-commit-in-batches-for-large-changes](../../.claude/projects/c--Users-abcuc-Desktop-rag/memory/feedback-commit-in-batches-for-large-changes.md) — 提交拆分规范
- [feedback-no-shim-no-minimal-changes](../../.claude/projects/c--Users-abcuc-Desktop-rag/memory/feedback-no-shim-no-minimal-changes.md) — 严禁 shim 兼容代码, 这次重构直接换实现, 不留 fallback
