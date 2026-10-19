# Spec: chat 模块协议层接 Vercel AI SDK 7 (Phase 1: 协议层重构)

**日期**: 2026-07-01 (v3 — 按实际代码状态清理已实现项)
**作者**: Claude (跟用户 brainstorm + agent 对抗审查 + spike 验证)
**状态**: Design (待 plan)
**前置**: 已通过 brainstorming 5 段设计 + agent 对抗审查 (5 CRITICAL) + T0 spike 验证 Dify 双块 SSE 兼容性

---

## 1. 背景与现状

### 1.1 问题

chat 模块当前**自己实现了 AI SDK 已经做好的协议层之部分**，表现为：

| 自实现文件 | 行数 | 职责 | 能否被 AI SDK 7 接管 |
|------------|------|------|---------------------|
| [lib/chat/sse.ts](../../packages/web/lib/chat/sse.ts) | 77 | 字节级 SSE 切分 + JSON 解析 | **部分** — `TextDecoderStream` 可接管字节解码；但 [Dify 双块 SSE 格式](../../packages/web/lib/chat/dify.ts#L226-L261) (`event: xxx\n\n` + `data: {...}\n\n` 分两块) 不兼容 AI SDK 的 `EventSourceParserStream`，需要保留简化版 `parseSseBlocks` |
| [lib/chat/dify.ts](../../packages/web/lib/chat/dify.ts) | 263 | Dify Chatflow 协议归一化 + 双发射防御 | **否** — 双块 SSE + 6 种事件归一化是 Dify 自有逻辑，无法通用化 |
| [lib/chat/openai.ts](../../packages/web/lib/chat/openai.ts) | 118 | OpenAI 兼容 API 流解析 (reader/decoder/buffer 另一套手写) | **部分** — reader/decoder/buffer 样板可复用简化后的 `parseSseBlocks`；`reasoning_content` 累积 + `[DONE]` sentinel 是 OpenAI 专有，保留 |
| [lib/chat/stream-handler.ts `applyEvent`](../../packages/web/lib/chat/stream-handler.ts#L87-L148) | 62 | 6 种 ChatEvent dispatch | **部分** — `handleStreamError` 可提取；dispatch 逻辑不改 |
| [lib/chat/stream-handler.ts `processStream`/`handleStreamError`](../../packages/web/lib/chat/stream-handler.ts#L280-L371) | 90 | 流处理 + abort 生命周期 + 3 出口错误归一 | **是** — 可提取成 `chat-event-decoder.ts`，用 `AbortSignal` + `TransformStream` |
| [app/api/chat/messages/route.ts](../../packages/web/app/api/chat/messages/route.ts) SSE 写入 | 37 | 手写 `TextEncoder` + `data: xxx\n\n` + `[DONE]` + try/catch 嵌套 | **是** — `JsonToSseTransformStream` + `pipeTextStreamToResponse` 接管 |
| [lib/chat/use-chat-state.ts](../../packages/web/lib/chat/use-chat-state.ts) | 403 | 全量状态管理 + 事件处理 + abort 字典 | **是** — `useChat` hook 接管 (Phase 2) |

> **T0 spike 关键发现（2026-06-29）**：
> Vercel `EventSourceParserStream` (`@ai-sdk/provider-utils` 依赖的 `eventsource-parser`) 在遇到 `event: xxx\n\n`（事件只含 event 不含 data 的空白行）时，会清除 `eventType` 状态。Dify `/chat-messages` API 发送的是双块 SSE (`event: message\n\n` → `data: {"answer": ...}\n\n` 分两个 `\n\n` 块)，所以 `parseJsonEventStream` + `EventSourceParserStream` **不能直接用于 Dify SSE 解析**。必须保留简化版 `parseSseBlocks`（只去除字节层 TextDecoder，保留双块合并逻辑），**这对其他 LLM provider (OpenAI/Anthropic) 的实现没有影响**，因为它们的 SSE 在单个 `\n\n` 块内包含 `data:` 行。

### 1.2 收益估算（分 Phase）

AI SDK 7 各能力的替代范围和行数影响：

| 可替部分 | AI SDK 能力 | 本期？ | 削/加行数 | 说明 |
|---------|------------|-------|----------|------|
| `sse.ts` 字节解码 (reader/decoder/buffer) | `TextDecoderStream` | ✅ Phase 1 | -30 | 手写 51 行 → ~20 行 |
| `openai.ts` reader/decoder/buffer 样板 | 共享简化后 `parseSseBlocks` | ✅ Phase 1 | -15 | 复用 sse.ts 而非再写一套 |
| `route.ts` SSE 写入 | `JsonToSseTransformStream` | ✅ Phase 1 | -20 | 省手写 encoder + [DONE] + try/catch |
| `chat-event-decoder.ts` 新文件 | TransformStream 封装 | ✅ Phase 1 | +60 | 从 dify.ts 搬 normalize* |
| `dify.ts` normalize* 迁出 | 代码重组 | ✅ Phase 1 | -63 | 搬到 decoder |
| `use-chat-state.ts` + `stream-handler.ts` 状态管理 | `useChat` hook | ❌ Phase 2 | -600 | 砍 dispatchSendStream / aborters / applyEvent 等 |
| **Phase 1 净变化** | | | **~-68** | -30 -15 -20 -63 +60 = -68 |
| **Phase 1+2 净变化** | | | **~-418** | -68 + (-350) = -418 |

核心价值不在行数削减，在**统一抽象层**：未来加 OpenAI/Anthropic 时，新 provider 可以直接用 AI SDK 的 `HttpChatTransport` subclass + `EventSourceParserStream`（它们都是标准 SSE 单块格式），不需要手写 SSE 解析。

`factory.ts` + `openai.ts` 已存在（118 行），Phase 5 路线已实现。

---

## 2. 目标 & 非目标

### 2.1 目标

1. **简化** `lib/chat/sse.ts`（77 行 → ~20 行）：去掉手写 `TextDecoder` 字节拼合（AI SDK `TextDecoderStream` 接管），保留 Dify 双块合并逻辑
2. **简化** `lib/chat/openai.ts`（118 行 → ~100 行）：复用 sse.ts 简化后的 `parseSseBlocks`，去掉重复的 reader/decoder/buffer 样板
3. **简化** `app/api/chat/messages/route.ts` SSE 写入（~37 行 → ~15 行）：用 AI SDK `JsonToSseTransformStream` + `pipeTextStreamToResponse` 替代手写 encoder + [DONE] + try/catch
4. **新建** `lib/chat/chat-event-decoder.ts`（~60 行）：从 `dify.ts` 搬出 `normalize*` 函数 + `seenMessageRef` 双发射防御 + `createParseBlock`，封装为 TransformStream
5. **调整** `lib/chat/dify.ts`（263 行 → ~200 行）：代码结构调整，normalize* 迁出
6. **改 import** `use-chat-state.ts` / `stream-handler.ts`（签名不变）

### 2.2 非目标

- ❌ **不接 `useChat` Hook**：messages / status 仍走现有 `messagesByConv` + `streamingConvId`
- ❌ **不动 UI 层**：MessageBubble / MessageList / Composer / Voice / Image / File slots
- ❌ **不动 Memory Dialog / Share Dialog**
- ❌ **不动后端 / BFF 逻辑**：Dify 配置 / FastAPI 路由 / 鉴权 / 限流 / 0 改动
- ❌ **不新建 `chat-provider.ts`**：`lib/chat/factory.ts`（39 行）已存在，扩展 factory 而非新建文件
- ❌ **不接 `extractReasoningMiddleware`**：AI SDK middleware 跟当前 `ChatProvider` 接口不兼容

---

## 3. 架构设计

### 3.1 新文件结构

```
lib/chat/
  ├─ types.ts                          (不动, ChatEvent union 保持)
  ├─ db.ts                             (不动, IDB Schema)
  ├─ storage.ts                        (不动, anon IDB facade)
  ├─ migration.ts                      (不动, anon→login 迁移)
  ├─ api.ts                            (不动, TanStack Query hooks)
  ├─ factory.ts                        (扩, add new ChatProvider variants)
  ├─ openai.ts                         ⭐ 简化: 复用 parseSseBlocks, 去重复 reader/decoder
  │                                       (118 → ~100 行)
  ├─ send-request.ts                   (已有, 62 行, 2026-06-30 从 chat-utils 拆出, 不动)
  ├─ use-chat-state.ts                 (改 import 路径, 签名不变)
  │
  ├─ sse.ts                            ⭐ 简化: 去掉 TextDecoder 字节拼合,保留 Dify 双块合并
  │                                       (77 → ~20 行)
  ├─ dify.ts                           ⭐ 调整: 代码重构, normalize* 函数迁出到 decoder
  │                                       (263 → ~200 行)
  ├─ chat-event-decoder.ts             ⭐ 新: 从 dify.ts 搬出 normalize* + seenMessageRef + createParseBlock
  │                                       封装为 TransformStream (~60 行)
  └─ stream-handler.ts                 ⭐ 已有(436 行, 2026-06-30 从 chat-utils 拆出)
                                         包含 applyEvent / processStream / handleStreamError

app/api/chat/messages/
  └─ route.ts                          ⭐ 简化: JsonToSseTransformStream 替手写 SSE 写入
                                          (~37 → ~15 行)
```

### 3.2 架构变化图

**旧链路**：
```
fetch (sse.ts: 字节级 parseSseBlocks + 手写 TextDecoder)
  → bytes → blocks (含 Dify 双块合并)
  → parseSseStream → ChatEvent[]
  → processStream (stream-handler.ts) → applyEvent dispatch → setMessagesByConv
  → handleStreamError 3 出口
```

**新链路**：
```
fetch (dify.ts: apiProxy + Bearer)
  → ReadableStream<Uint8Array>
  → AI SDK TextDecoderStream (替代手写字节拼合)
  → sse.ts (简化版): 切 \n\n 双块 + Dify lastEvent 闭包合并
  → chat-event-decoder.ts (新):
      - TransformStream: Dify RawEvent → ChatEvent (6 事件归一化, 从 dify.ts normalize* 搬)
      - seenMessageRef 双发射防御 (从 dify.ts 搬)
      - createParseBlock (从 dify.ts 搬)
  → ReadableStream<ChatEvent>
  → stream-handler.ts 消费 (processStream + applyEvent 保持, 签名不变)
  → setMessagesByConv 旧路径不变

BFF route.ts SSE 写入 (旧):
  hand-write: TextEncoder → data: JSON\n\n → [DONE] → try/catch

BFF route.ts SSE 写入 (新):
  JsonToSseTransformStream → pipeTextStreamToResponse
```

### 3.3 ChatProvider 接口（保留）

**接口**（[lib/chat/types.ts:39-42](../../packages/web/lib/chat/types.ts#L39-L42)）**不改签名**：
```ts
export interface ChatProvider {
  readonly name: string;
  sendMessage: (req: SendMessageRequest, signal: AbortSignal) => AsyncIterable<ChatEvent>;
}
```

**重要决策**：
- `AsyncIterable<ChatEvent>` 保持（**不升级为 `ReadableStream<ChatEvent>`**，规避 `for-await-of` 类型推导风险，且 `AsyncIterable` 在标准 SSE provider 已足够）
- `factory.ts` 已有 `getChatProvider()` 和 5 个 case（dify / dify-debug / openai / openai-debug / openai-health），本期只调整 Dify 内部实现

### 3.4 AI SDK 7 能力全景分析

AI SDK 7 不止流解析。以下按能否接入当前架构逐项评估：

| AI SDK 能力 | 可替代码 | 省行数 | 本期？ | 理由 |
|------------|---------|--------|-------|------|
| `TextDecoderStream` | `sse.ts` 字节解码 | ~30 | ✅ | 标准 Web API，直接替换 reader/decoder/buffer |
| `JsonToSseTransformStream` | `route.ts` SSE 写入 | ~20 | ✅ | 直接替换手写 encoder + [DONE] + try/catch |
| `EventSourceParserStream` | 标准 SSE 解析 | ~0 | ❌ | Dify 双块 SSE 不兼容，仅对 OpenAI/Anthropic 有用 |
| `parseJsonEventStream` | JSON 行解析 | ~0 | ❌ | 同上，不兼容双块 SSE |
| `extractReasoningMiddleware` | `openai.ts` reasoningBuf | ~15 | ❌ | middleware 走 `streamText` 路径，跟当前 `ChatProvider` 接口不兼容 |
| `smoothStream` | 流平滑 | — | ❌ | 纯优化，不影响行数 |
| `useChat` | `use-chat-state.ts` + `stream-handler.ts` | ~600 | ❌ Phase 2 | 见 §10.1 详细分析 |
| `AISDKError` 层级 | 自定义 error 类型 | 很少 | ❌ | 不值得替换 |

**结论**：除流解析外，唯一可以本期顺带做的是 `route.ts` 的 `JsonToSseTransformStream`（省 ~20 行）。`useChat` 是最大收益项（~600 行），但需要完整设计 + 测试，归 Phase 2。

### 3.5 与 openai.ts 的共享复用

`openai.ts` 当前有独立的 reader/decoder/buffer 实现（跟 `sse.ts` 完全相同模式），简化后的 `parseSseBlocks` 可被它复用：

```
openai.ts 旧: reader.read() → TextDecoder → buf += → buf.indexOf("\n\n") → data: 行 → JSON.parse
openai.ts 新: for await (const block of parseSseBlocks(res.body!, signal)) → JSON.parse
```

省 ~15 行重复样板。`reasoning_content` 累积 + `[DONE]` sentinel 保留不变。

---

## 4. 数据流

### 4.1 客户端发消息完整路径（本期变化）

```
[用户点 Send]
  ↓
useChatHandlers.handleSend (use-chat-state.ts)                 ◀ 不动
  ↓
createServerConvIfNeeded                                        ◀ 不动
  ↓
initMessages (本地 state 写 user + assistant 空壳)             ◀ 不动
  ↓
getChatProvider("dify").sendMessage(req, signal)
  │
  │ 内部 (dify.ts + sse.ts 简化版 + chat-event-decoder.ts 新):
  │   1. fetch Dify /chat-messages (apiProxy + Bearer + body + AbortController.signal)
  │   2. ReadableStream<Uint8Array>
  │      → .pipeThrough(new TextDecoderStream())          ⭐ AI SDK 接管字节解码
  │      → sse.ts 简化版: 切 \n\n 双块 + lastEvent 闭包   ⭐ 保留 (Dify 专有)
  │      → chat-event-decoder TransformStream:
  │         - seenMessageRef 双发射防御
  │         - 6 种 ChatEvent 归一化
  │
  ↓ AsyncIterable<ChatEvent>
useChatHandlers.dispatchSendStream 旧路径                     ◀ 签名不变
  ↓ for-await-of 消费
applyEvent 旧 dispatch                                       ◀ 保留
  ↓
message_end → persistAssistantToServer (已有)               ◀ 不动
```

### 4.2 BFF route.ts 新旧对比（本期变化）

```
旧: provider.sendMessage() → for-await-of → TextEncoder → `data: JSON\n\n` → [DONE] → try/catch
新: provider.sendMessage() → for-await-of → JsonToSseTransformStream → pipeTextStreamToResponse
```

### 4.3 openai.ts 新旧对比（本期变化）

```
旧: reader.read() → new TextDecoder() → buf += → buf.indexOf("\n\n") → data: 行 → JSON.parse → reasoningBuf
新: for await (const block of parseSseBlocks(res.body!, signal)) → JSON.parse → reasoningBuf
```

### 4.4 错误处理（3 出口统一，跟 2026-06-24 spec 一致）

| 出口 | 行为 | 落库 |
|------|------|------|
| `message_end` (Dify 流结束) | assistant.content 完整 + citations 渲染 | `persistAssistantToServer(finishReason: "stop")` |
| 用户点 stop (AbortController) | assistant.content partial + `interrupted: true` Badge | `persistAssistantToServer(finishReason: "interrupted")` |
| Dify `error` 事件 | content append `[code] message` + partial 落库 | `persistAssistantToServer(finishReason: "error", code)` |

**零改动**：3 出口收敛到 1 个 `persistAssistantToServer` helper。

---

## 5. 测试策略

| 测试文件 | 现状 | 变化 |
|----------|------|------|
| `sse.test.ts` | 测 `parseSseBlocks` 字节级切分 | **简化**：去掉 TextDecoder 测试（AI SDK 自测），保留双块合并 + lastEvent 测试（Dify 专有） |
| `openai.test.ts` | `makeStream` 直接 emit SSE 块 | **小幅调整**：mock 形状基本不变，流解析路径变化但断言不变 |
| `dify.test.ts` | 测 `DifyChatProvider.parseStream` + 双发射防御 | **调整**：代码结构调整后 normalize 函数路径变化，断言更新。行为不变 |
| `stream-handler.test.ts` | 测 `applyEvent` / `persistAssistantToServer` / `persistUserToServer` | **保留**，删 `processStream`/`handleStreamError` 测试（迁入 decoder） |
| `route.test.ts` | 自建 `parseSSE` + `readBodyAsText`（~30 行） | **简化**：复用 sse.ts 的 `parseSseBlocks` 替代手写 helper |
| `chat-shell.test.tsx` | mock `@/lib/api/chat.sendMessage` 走 `makeStream()` | **小幅调整**：`makeStream` 仍返 `ReadableStream<Uint8Array>`（emit SSE 格式 data），跟新 sse.ts 输入形状兼容 |
| `chat-event-decoder.test.ts` | 新文件 | 测 TransformStream 转换 + 双发射防御 + 3 出口错误归一 |

**关键事实**：`chat-shell.test.tsx:107` 的 `makeStream()` 当前 emit SSE 格式 `data: ${JSON.stringify(ev)}\n\n`，与简化后 sse.ts 的 `TextDecoderStream + parseSseBlocks` 输入兼容（TextDecoderStream 处理字节→字符串，sse.ts 处理字符串→块）。**mock 形状基本不变**。

---

## 6. 任务拆分

```
T1  简化 sse.ts: 去掉 TextDecoder 字节拼合, 保留双块合并 (77→~20 行)
  ↓
T2  简化 openai.ts: 复用 parseSseBlocks, 去重复 reader/decoder (118→~100 行)
  ↓
T3  简化 route.ts: JsonToSseTransformStream 替手写 SSE 写入 (~37→~15 行)
  ↓
T4  新增 chat-event-decoder.ts: TransformStream + normalize* 从 dify.ts 搬入 (~60 行)
  ↓
T5  调整 dify.ts: 代码重构, normalize* 函数迁出 (263→~200 行)
  ↓
T6  写 chat-event-decoder.test.ts (新)
  ↓
T7  调整 sse.test.ts + openai.test.ts + dify.test.ts + stream-handler.test.ts
     + route.test.ts + chat-shell.test.tsx
  ↓
T8  跑 vitest 全量 + lint + typecheck + format
  ↓
T9  CLAUDE.md 加 AI SDK 条款 + commit
```

---

## 7. 验收

### 7.1 功能验收（E2E 手工）

- 启动后端 `uv run python main.py`，前端 `bun run dev`
- 登录账号 → 发消息 → 流式回答 + citations 正常显示
- 切 anon → 发消息 → IDB 持久化（刷新还在）
- 切回登录 → 迁移弹框不弹（anon conv 走 IDB 没污染）
- 点 stop → AbortController 真断开，partial content 落库 + interrupted Badge

### 7.2 质量验收（CI）

```bash
bun run test              # 719 baseline 全绿
bun run test:coverage     # chat 模块覆盖不降
bun run lint              # oxlint 0 warning
bun run typecheck         # tsc 0 error
bun run format            # oxfmt 0 报错
```

### 7.3 代码量验收

- Phase 1 净削减 **~68 行**（sse.ts -57, openai.ts -18, route.ts -22, dify.ts -63, decoder.ts +60, openai.test.ts +2）
- `lib/chat/sse.ts`：77→~20 行（无 TextDecoder 字节拼合）
- `lib/chat/openai.ts`：118→~100 行（复用 parseSseBlocks）
- `lib/chat/dify.ts`：263→~200 行（normalize* 迁到 decoder）
- `app/api/chat/messages/route.ts`：~37→~15 行（JsonToSseTransformStream）

---

## 8. 回滚策略

按 [feedback-commit-in-batches-for-large-changes](../../.claude/memory/feedback-commit-in-batches-for-large-changes.md) 拆分 commit：

```
refactor(chat): T1 简化 sse.ts (TextDecoder → AI SDK)
refactor(chat): T2 简化 openai.ts (复用 parseSseBlocks)
refactor(chat): T3 简化 route.ts (JsonToSseTransformStream)
feat(chat): T4 新增 chat-event-decoder.ts
refactor(chat): T5 调整 dify.ts
test(chat): T6-T7 测试调整
docs(chat): T9 CLAUDE.md AI SDK 条款
```

任一 commit 跑红可单独 revert。

---

## 9. 风险 & 缓解

| 风险 | 影响 | 缓解 |
|------|------|------|
| **`TextDecoderStream` 跨浏览器兼容性**（IE 不支持、某些旧 Safari） | 客户 anon 路径 SSE 解析失败 | `parseSseBlocks` fallback：当 `typeof TextDecoderStream === 'undefined'` 时走手写字节解码 |
| **chat-shell.test.tsx mock 形状隐含依赖** | T5 发现 mock 实际不兼容新 sse.ts | T5 前跑 `bun run test -- chat-shell` 验证，不兼容则临时用 `asyncGeneratorToStream` 桥接 |
| **Dify `/chat-messages` API behavior change** | 双块 SSE 格式变标准格式 | 不影响——标准化后 `EventSourceParserStream` 兼容，双块合并逻辑变成 no-op |

---

## 10. 后续路线（**本期不做，文档化**）

### Phase 2 — 接 useChat（状态管理重构）

**触发条件**：当前状态管理分散在多个文件中，`use-chat-state.ts` + `stream-handler.ts` + `chat-utils.ts` + `send-request.ts` 合计 ~970 行手动管理 messages / status / abort / persist 生命周期。AI SDK `useChat` hook 可替代大部分。

#### 10.1.1 当前状态管理全貌

| 文件 | 行数 | 职责 | useChat 替代度 |
|------|------|------|---------------|
| `use-chat-state.ts` | 403 | 4 hooks + 8 状态 + abort 字典 + 事件处理 | **~200 行可删** — `useChatShellState` / `useChatHandlers` / `dispatchSendStream` |
| `stream-handler.ts` | 436 | applyEvent / processStream / initMessages / ensureConv / persist helpers | **~200 行可删** — applyEvent / processStream / handleStreamError / initMessages / ensureConversation |
| `chat-utils.ts` | 70 | newId / setupAbortController / computeEffectiveConversations | **~30 行可删** — setupAbortController |
| `send-request.ts` | 62 | 拼装请求 + 调 BFF API | **~40 行可删** — 并入 transport |
| `api.ts` | ~200 | TanStack Query hooks (CRUD conversations) | **保留** — useChat 不替代会话列表管理 |
| **合计可删** | | | **~470 行** |
| **新增 adapter** | | | **~120 行** (transport + persistence callbacks + conversation sync) |
| **净变化** | | | **~-350 行** |

#### 10.1.2 useChat 接入方案

```
当前架构:
  useChatShellState (8 个 useState)
    → useChatHandlers.handleSend
      → dispatchSendStream
        → sendRequest → BFF API
        → processStream → applyEvent → setMessagesByConv
        → handleStreamError (3 出口)
    → useChatHandlers.handleStop → aborters.current[convId].abort()

新架构:
  useChat({
    api: "/api/chat/messages",       // 复用现有 BFF route
    id: currentConvId,                // 会话维度, 切换时重置
    onFinish: ({ message }) => {      // 替代 persistAssistantToServer
      storage.saveMessages(convId, [message]);
    },
    onError: (error) => {             // 替代 handleStreamError
      // error → 写入 state + toast
    },
  })
  // messages / status / input / handleSubmit / stop 直接绑定 UI
  // IDB 持久化走 onFinish + onError callback
  // 服务端持久化 (登录态) 走 onFinish 内调 appendMessageMut.mutate
```

#### 10.1.3 主要变化

| 当前代码 | useChat 替代 | 说明 |
|---------|-------------|------|
| `messagesByConv` + `streamingConvId` | `useChat.messages` + `useChat.status` | 每个会话一个 useChat 实例 |
| `draft` (localStorage) | `useChat.input` + `handleInputChange` | 内置 |
| `handleSend` + `dispatchSendStream` | `useChat.handleSubmit` | 内置 |
| `handleStop` + `aborters.current` | `useChat.stop` | 内置 |
| `processStream` + `applyEvent` | useChat 内部流处理 | 自动处理 delta 追加 |
| `initMessages` (user + assistant slot) | useChat 自动 | 发送即追加 |
| `persistAssistantToServer` | `onFinish` callback | 3 出口统一 |
| `handleStreamError` | `onError` callback | |
| `sendRequest` | transport (默认 `HttpChatTransport`) | 直接配 `api` URL |
| `setupAbortController` | 内置 | 每个 useChat 独立 |
| `ensureConversation` | **保留简化版** | 仅用于首次创建 conv + IDB 记录 |
| `computeEffectiveConversations` | **保留** | 会话列表合并逻辑与 useChat 正交 |

#### 10.1.4 保留 / 不能替代的部分

- **IDB 持久化** — useChat 不提供离线存储，走 `onFinish` callback 调 `storage.saveMessages`
- **会话列表管理** — `useConversations` / `useCreateConversation` / `useDeleteConversation` 保留
- **迁移逻辑** — `migration.ts` 保留
- **自定义 ChatProvider** — `dify.ts` / `openai.ts` / `factory.ts` 保留（BFF route 已封装）
- **`ensureConversation`** — 简化版保留（仅首次创建 + IDB 写）
- **Citations / thinking 渲染** — useChat 的 `UIMessage` 跟项目 `Message` 类型不同，需 adapter 转换

#### 10.1.5 风险

| 风险 | 影响 | 缓解 |
|------|------|------|
| **useChat 每个会话实例化** | 会话切换时消息需重载 | `id` prop 切换自动加载；`messages` 映射到 `messagesByConv` 需要缓存策略 |
| **`UIMessage` 与项目 `Message` 类型不兼容** | citations / thinking / interrupted 字段需适配 | adapter: `UIMessage[] → Message[]` 转换层 |
| **Dify 双块 SSE 不兼容 useChat 默认 transport** | useChat 默认走 `HttpChatTransport` 期望标准 SSE | BFF route 已做归一化，useChat 消费的是 BFF 输出的标准 SSE，无影响 |
| **anon 路径无服务端** | useChat 默认走 fetch API，anon 需要 fallback | 条件判断：anon 不走 useChat（保留现有 IDB 路径）或 useChat 切 `DirectChatTransport` |

**估算**：净 -350 行 / 新增 120 行 adapter

### Phase 3 — IDB 单源化

**触发条件**：用户报"会话列表在 anon/登录切换时不一致" 或 `migration.ts` 弹框太烦

**范围**：
- 砍 `useChatShellState.conversations` 本地 useState
- `computeEffectiveConversations` 直接删
- `migration.ts` 简化

**估算**：-300 行

### Phase 4 — Memory 接入 AI SDK tools（可完全跳过本期 Phase 1 直接独立做）

**触发条件**：用户要做"长期记忆自动 inject"

**范围**：AI SDK tool definition / 后端 MCP-style transport

**估算**：+300 行
**注意**：跟本期 Phase 1 完全正交，可以独立开始。

---

## 11. 对抗审查 & Spike 摘要

### 对抗审查结果（agent 执行，4 CRITICAL + 4 WARNING + 9 CONFIRMED）

| # | 严重程度 | 原 spec claim | 真相 | 修法 |
|---|---------|-------------|------|------|
| **C1** | CRITICAL | 用 `streamFromReadable` / `parseSSEStream`（AI SDK 6） | **这两个 API 在 ai@6.0.208 不存在** | 改为 AI SDK `TextDecoderStream` + 简化 `parseSseBlocks` |
| **C2** | CRITICAL | 用 `customTransport` 做自定义后端 | **没有 `customTransport` prop**（真实是 subclass `HttpChatTransport`） | Phase 1 不接 useChat，保持 `ChatProvider` 接口不变 |
| **C3** | CRITICAL | 新建 `chat-provider.ts`，工厂 `getChatProvider("dify")` | **`factory.ts` 39 行已存在** | 扩 factory 而非新建文件 |
| **C4** | CRITICAL | Phase 5 "新增 OpenAiChatProvider 30 行" | **`openai.ts` 118 行已实现** | 删 Phase 5 |
| W1-W4 | WARNING | `ReadableStream<ChatEvent>` / `for-await-of` 类型推导 / 测试 mock 形状等 | 部分不准确 | 保持 `AsyncIterable<ChatEvent>` |

### T0 Spike 结果（Dify 双块 SSE 兼容性验证）

验证了 `@ai-sdk/provider-utils` 依赖的 `EventSourceParserStream`（`eventsource-parser` 3.1.0）的实现细节：

```typescript
// parse.ts:164-172 — 关键路径
if (blankLine) {
  if (dataLines > 0) onEvent(...)  // Dify 的 event: xxx\n\n → dataLines=0, 跳过
  // 然后 RESET eventType = undefined
}
```

结论：**`EventSourceParserStream` 不兼容 Dify 双块 SSE**。项目需要保留简化版 `parseSseBlocks`（只负责双块合并 + lastEvent 闭包，不负责字节解码）。

### 修正后核心指标

- Phase 1 净代码削减：**~68 行**（sse.ts -57 + openai.ts -18 + route.ts -22 + dify.ts -63 + decoder.ts +60）
- Phase 1+2 净代码削减：**~418 行**（含 useChat 接管状态管理 ~350 行）
- AI SDK 核心价值：**统一抽象层，未来 LLM provider 0 行 SSE 手写**（不仅限于行数）
- Phase 1 测试改动幅度：~6 文件小幅调整（非重写）
- 业务代码 0 逻辑变更

---

## 12. 关联文档

- 对抗审查 agent 输出：[agent a012651ed8526c9d0 全文](../../agent-a012651ed8526c9d0.md)（包含 5 CRITICAL + TypeScript + exact SDK 签名）
- T0 spike 验证：`eventsource-parser` `parse.ts` 源码 + Dify `createParseBlock` 对比
- 现状 spec：[2026-06-24-chat-message-persistence-design.md](./2026-06-24-chat-message-persistence-design.md)
- 项目规约：[packages/web/CLAUDE.md](../../packages/web/CLAUDE.md)
