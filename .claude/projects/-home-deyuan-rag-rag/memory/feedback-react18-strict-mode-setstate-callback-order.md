---
name: feedback-react18-strict-mode-setstate-callback-order
description: "React 18 strict mode 下 setState 回调执行顺序不可控, 闭包变量在两个 setter 间传值会读 stale"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: d365816f-f987-4fea-93d9-5415bde993bf
---

React 18 strict mode (默认开) 下, 当你在同一 tick 调用多个 setState:
- `setX(fn1); setY(fn2);`
- 回调 `fn1` 和 `fn2` 的执行顺序**不保证是调用顺序**
- 实测案例 (2026-06-15 ChatShell refactor): 调用 setMessagesByConv 后调 setConversations, 调试日志显示 setConversations 回调先跑, setMessagesByConv 回调后跑
- 想用闭包变量 `let computed = 0; setX(m => { computed = ...; }); setY(prev => { use(computed); });` 传值 → 读到 stale 0

**Why**: 2026-06-15 chat SSE refactor Task 4 想 "拆 setConversations/upsertConversation 出来" 修 strict mode 双写, 实测 closure 变量传值失效, 1 个 messageCount 测试挂在 expected 1 / actual 0

**How to apply**:
- 不要跨 setter 回调用闭包变量传值, 改用 useRef / useReducer 共享
- 或者把后续 setter 放在前一个 setter 的 callback 里 (callback 内闭包变量有效, 因为 callback 同步执行到 return)
- TDD: 写测试模拟"两个 setter + 闭包变量"场景, 红再决定怎么改, 不要先写"理想方案"再让现实打脸
- 真正的"bug 修了"= 单一来源 (从 messages 算 messageCount, 不从 prev 算), 拆不拆 callback 是次要的
