---
name: feedback-docreateserverconv-isaccount-skip-idb
description: "登录态创建 server conv 成功后会无脑调 persistCb 写 IDB, storage.ts 强制 owner=anon → IDB 永远脏 → 迁移弹框永远触发"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 623e8a0b-5f11-4892-8333-52384121101e
---

`doCreateServerConv` 创建 server conv 成功后调 `persistCb = upsertConversation`, 后者走 `storage.ts:48` 强制 owner=`"anon"`. 登录态也走这条路径 → IDB 永远有 anon 记录 → 下次进 /chat `useAnonToLoginMigration` 查 IDB owner=anon count > 0 → 弹 "本地 N 段聊天将清除" toast, 实际是登录态的 server conv 被误标 anon.

**Why**: 2026-06-24 实战, 用户登录后发消息, 服务端创建 server conv 成功, 前端顺手写 IDB 一条 owner=anon 记录, 下次 mount ChatShell 永远弹框. 用户报 "performAnonToLoginMigration 弹框莫名其妙弹出来, 没有 indexdb 的时候也弹出来".

**How to apply**:
1. **修法**: `doCreateServerConv` 加 `isAccount` 参数, 内部 `if (!isAccount)` 包住 `persistCb` 调用块. 登录态完全不写 IDB (登录态数据走 server).
2. **判定规则**: 写 IDB 的逻辑必须确认 caller 是不是 anon, 不要无脑 persist. 登录态 IDB 是冗余, **不写**。
3. **关联**:
   - [[feedback-chat-effectiveconversations-vs-state-conversations]] (同日 同样 use-chat-state 路径 bug)
   - [[feedback-fix-root-cause-not-remove-feature]] (修法不是去 disable toast 弹框逻辑, 是不再往 IDB 喂脏数据)
4. **Handoff**: docs/superpowers/handoffs/2026-06-24-chat-bugfix.md 这次修复的根因之一.
