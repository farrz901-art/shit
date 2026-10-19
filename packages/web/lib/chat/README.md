# lib/chat/

聊天模块 (`智能体聊天` 业务域). 跨 client + server + BFF.

## 分层 (2026-06-30 audit)

### Client-only (`"use client"` 顶部 marker)

- **`api.ts`** — TanStack Query hooks (useConversations / useCreateConversation / useDeleteConversation / useBackup / useAppendMessage). 全部 useQuery/useMutation.
- **`use-chat-state.ts`** — `useChatShellState` / `useServerData` / `useChatHandlers` / `removeConvLocal` 4 个核心 hook. 全部 useState/useEffect/useRef.
- **`migration.ts`** — `useAnonToLoginMigration` / `performAnonToLoginMigration` / `downloadLocalBackup`. useEffect + localStorage + sonner toast.

### Client-only (隐式, 不加 marker — module-level 副作用)

- **`db.ts`** — `new ChatDB()` module-level 调用 Dexie IndexedDB. 加 `"use client"` 会污染 server bundle (any server import 拉进 indexedDB). 安全做法: 仅 client 代码引.
- **`storage.ts`** — facade 包装 `./db` 的 Dexie 调用, 同上风险, 不加 marker.
- **`chat-utils.ts`** — 含 `localStorage.getItem` (L0 纯函数), 拆 `getAnonUserId` 后, send-request.ts / stream-handler.ts 都不再直接碰 localStorage.

### Server-only (`import "server-only"` 顶部 marker)

- **`dify.ts`** — `DifyChatProvider` 调 `process.env.DIFY_*` + `apiProxy()` 外部服务. BFF route 唯一消费方.
- **`openai.ts`** — `OpenAIChatProvider` 同上, `OPENAI_*` env.
- **`factory.ts`** — `getChatProvider` 按 `process.env.CHAT_PROVIDER` 选 dify/openai 实例 + 自动套 `withMemoryHooks` 装饰器.
- **`memory-integration.ts`** — `withMemoryHooks` 装饰器, `cookies()` from `next/headers` + fire-and-forget 记忆 fetch.

### Shared (无 marker)

- **`types.ts`** — 纯类型/interface (ChatEvent / ChatFile / Citation / Conversation / Message / SendMessageRequest / ChatProvider).
- **`sse.ts`** — `parseSseBlocks` / `parseSseStream` async generator, 纯函数. BFF + client 都用.
- **`chat-utils.ts`** (L0) — `newId` / `computeEffectiveConversations` / `getNextConversationId` / `setupAbortController` 4 个纯函数.
- **`send-request.ts`** — `sendRequest` / `SendRequestParams` / `getAnonUserId` (内部). 走 `lib/api/chat` BFF + `localStorage` (client-only 副作用, 但因 lib/api/chat 已 shared, 不强制 marker).
- **`stream-handler.ts`** — SSE 流生命周期 (applyEvent + 6 handler + ensureConversation + initMessages + handleStreamError + processStream + 3 persist helper). 内部 `AppendMutateFn` 类型 re-export.
- **`index.ts`** — barrel 暴露 dify / factory / openai / send-request / storage / types (6 个).

## 数据流

```
浏览器 (React)            BFF route                后端

chat-shell.tsx ──┐         ┌─ app/api/chat/messages/route.ts ──→ getChatProvider() (factory)
                ├─ useState│                                 (server-only)
                │           │
                ├─ useChatShellState ─ useConversations() ─→ /api/chat/conversations
                │           │              (lib/api/index.ts)
                ├─ api.ts ──┤
                │           │
                ├─ migration.ts ─ clearLocalChat() ─ db.ts (Dexie IDB)
                │           │
                ├─ db.ts ────┘
                │
                └─ stream-handler.ts ─ applyEvent(ChatEvent) ─ setMessagesByConv
```

## 关键约束

1. **BFF route 必须走 `getChatProvider` from `@/lib/chat/factory`** — server-only, 不能在 client 调 (会泄露 `DIFY_API_KEY` env).
2. **anon → IDB, 登录 → server** 策略见 [web/CLAUDE.md §聊天历史存储约定](../../CLAUDE.md).
3. **拆分后**: `chat-utils.ts` 只留 4 个 L0 纯函数 (~70 行). `send-request.ts` (~60 行) / `stream-handler.ts` (~360 行).
4. **`AppendMutateFn` 类型集中在 `stream-handler.ts`**, `chat-utils.ts` re-export 给业务调用方.

## 测试

- `chat-utils.test.ts` (空, L0 函数无独立测试) — 占位历史.
- `send-request.test.ts` — 5 个 `sendRequest` 测试 (mock `@/lib/api/chat` + `@/lib/store/auth-store`).
- `stream-handler.test.ts` — 11 个测试 (persistAssistantToServer 4 + persistUserToServer 2 + applyEvent 5).
- `db.test.ts` / `storage.test.ts` / `api.test.tsx` / `memory-integration.test.ts` / `migration.test.tsx` / `sse.test.ts` — 各自覆盖.
- `use-chat-state.ts` 测试集成在 `components/chat/chat-shell.test.tsx` (vitest jsdom).

## 修改历史

- **2026-06-30** (本 spec): 加 marker + 拆 chat-utils.ts → 3 文件 + barrel 补 send-request.
- **2026-06-23** P3: applyEvent 对象 dispatch refactor.
- **2026-06-19** chat spec: anon → IDB, 登录 → server 策略落地.
