---
name: feedback-debug-with-console-log-not-quiet-fails
description: "try/catch 静默吞错误让上游不知调用失败; debug 先加 console.log, 再看 dev server 终端"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: ddb02d13-b877-47c3-8a38-ffa0f0098894
---

try/catch 静默吞错误（只 console.warn）让上游和用户完全不知原因. BFF route 的 console.warn / console.log 输出在 Next.js dev server 终端（不是浏览器 console），开发者要打开看.

**Why:** 2026-06-16 withMemoryHooks → memoryApi → apiFetch 静默 401, 用户说"没有调用 mem0 接口", 根因被 try/catch 藏掉, 花了 10+ 轮来回才定位.

**How to apply:**
1. BFF/服务端代码加 `console.log` 验证关键路径（请求发出了、响应状态码、auth headers）
2. 告诉用户看 Next.js dev server 终端输出（不是浏览器 terminal）
3. 不要假设 Turbopack 改了就生效 — 让用户确认重启 dev server
4. 调试完删掉 console.log 再 commit
5. **不要在服务端用 console.warn 静默吞错误**: 错误应该冒泡到调用方, 调用方决定降级还是报错
