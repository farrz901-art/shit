---
name: feedback-chat-effectiveconversations-vs-state-conversations
description: "选历史对话发送消息会新建会话, 根因 createServerConvIfNeeded 用 state.conversations 判存在, 没用 effectiveConversations (merged server+local)"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 623e8a0b-5f11-4892-8333-52384121101e
---

登录态 chat 选历史 conv 再发消息, 每次都新建一个会话, 不续写到选中的 conv。

**根因**: `packages/web/lib/chat/use-chat-state.ts` 里 `createServerConvIfNeeded(currentConvId, state.conversations)` 判定 `currentConvId` 是否在**本地 `state.conversations` (`useState<Conversation[]>([])` 初始空数组)** 里。`ConversationList` 展示的是 `effectiveConversations` (= `computeEffectiveConversations(state.conversations, serverConvs, isAccount)`, 走 server TanStack Query 列表), 用户从 effective 选中一个 conv 设到 `state.currentId`, 但 `state.conversations` 本身没被更新, 判定 miss → 调 `doCreateServerConv` → 新建一个 conv, 后续消息全进新建的, 跟用户选中的割裂。

**Why**: 2026-06-24 实战, login user 选 /chat 列表里的历史对话, 在 composer 发消息, 服务端 log 显示 POST /api/chat/conversations 每次都创建新 conv (而不是 append 到选中的)。

**How to apply**:
1. **修法**: `createServerConvIfNeeded` 签名加 `effectiveConversationsSnapshot` 参数, 内部用 effective 判存在, 不用 state.conversations。调用处 `handleSend` 传 `effectiveConversations` (props 里已有)。
2. **不要**用闭包 deps 加 `effectiveConversations` 到 `createServerConvIfNeeded` 的 `useCallback` deps, 改用参数传入避免 stale closure。
3. **判定来源规则**: 凡是要查 "这个 id 服务端有没有" 的逻辑, **永远用 effective/server 数据源**, 不用本地 useState 初始空数组。
4. 关联: `effectiveConversations` 是 project chat spec (2026-06-19) 引入的 server+local 合并层, 跟 [[feedback-apifetch-bff-prefix-list]] 类似, 多个数据源并存时必走合并层判, 不走单一 source。
