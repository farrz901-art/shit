---
name: feedback-record-errors-and-lessons
description: 用户明确要求：以后每次犯错（bug 修错、推断失误、判断错误）必须立刻记录到 memory，写清错误和教训，不能糊弄过去
metadata: 
  node_type: memory
  type: feedback
  originSessionId: d5923208-4647-4dd0-9acb-40426948d1ee
---

用户要求：**以后每次犯错都要记录错误和教训**到 memory，不能只口头说一句"我搞错了"就过。

**Why:** 用户发现我在 [[project-mineru-docker-integration]] 调试中连续犯了多个错（猜错路径布局、误判 docker 库没装、用 mock 测试替代真实端到端），但每次都只在对话里说"我搞错了"就过，没有沉淀。用户希望下次类似错误再发生时我能直接 reference 之前的教训，避免重复犯。

**How to apply:**
- 任何错误（代码 bug 修错、推断失误、误报、漏看、对工具输出理解错）都要写一条 memory
- 每条 memory 必须包含：(1) 错误是什么 (2) 当时为什么犯 (3) 教训/如何避免
- 写完要在 MEMORY.md 加索引
- 用户没要求总结时也要主动写
- 调试任务结束前自检：本轮有没有犯错？有没有该写没写的？
