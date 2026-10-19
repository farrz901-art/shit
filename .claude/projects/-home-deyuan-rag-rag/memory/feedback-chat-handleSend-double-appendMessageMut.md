---
name: feedback-chat-handlesend-double-appendmessagemut
description: handleSend 显式调 persistUserToServer + initMessages deps.appendMutate 调 → 2 次 POST /api/chat/messages → 后端 500
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 623e8a0b-5f11-4892-8333-52384121101e
---

`handleSend` 在登录态**2 次**调 `appendMessageMut.mutate`:
1. `deps.appendMutate = serverData.appendMessageMut.mutate` 传给 `initMessages` → initMessages 内部 (chat-utils.ts:240 块) 调 `persistUserToServer`
2. `handleSend` 显式 `persistUserToServer({ mutate: ... })` 再调一次

**结果**:1 次发消息 = 2 个 POST `/api/chat/messages` + 1 个 POST `/api/chat/conversations/{id}/messages` (跟下面重复),**重复 content 入同 conv** → 后端 500。

**Why**: 2026-06-24 实战, Network 面板看到 7 个请求, 2 个红 500. 根因 chat-message-persistence spec (2026-06-24) 加了 "user msg 立即落库" 逻辑, 但同时塞了 deps.appendMutate + 显式 persistUserToServer, 2 条路径都调 mutate.

**How to apply**:
1. **修法**: 删 handleSend 显式 persistUserToServer, 让 user msg 落库走 initMessages 内部 deps.appendMutate 唯一路径. 跟 [[feedback-fix-root-cause-not-remove-feature]] 一致, 不删 user msg 落库功能, 只去重.
2. **InitMsgDeps 接口必须加 `appendMutate?` + `isAccount?`** — 之前接口只有 persistMessages + upsertConversation, 加 user msg 落库需扩.
3. **设计原则**: 任何"副作用"只能走 1 条路径, 显式 + 隐式(deps)同时调 = 100% 重复. 写时只走 1 处.
4. **关联**: [[feedback-react18-strict-mode-setstate-callback-order]] (React 18 strict mode 双调用类似陷阱, 但这里是逻辑层 2 次, 不是 React 18 双 mount)
