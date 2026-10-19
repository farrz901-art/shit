---
name: feedback-clarify-ambiguous-instructions
description: "以后我让你做任何有一点模糊的指令, 都要先向我澄清你的理解和你打算怎么做"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 822e2447-09c4-4b8a-9808-d37453aff4b8
---

以后用户让做任何有一点模糊的指令, 都要先向用户澄清自己的理解 + 打算怎么做, 等用户确认后再执行。

**Why:** 避免理解偏差导致返工, 用户希望先对齐意图再动手。

**How to apply:** 收到非完全明确指令时, 先 Read 相关文件理解现状, 然后用 AskUserQuestion 或文字描述: "我的理解是 ..., 打算这样做 ..., 确认吗?"
