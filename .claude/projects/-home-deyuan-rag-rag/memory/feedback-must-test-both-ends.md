---
name: feedback-must-test-both-ends
description: "改 bug 必须自测涉及接口的前后端 — curl 验证后端返回格式 + vitest 验证前端解析逻辑, 不能只看一边"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 822e2447-09c4-4b8a-9808-d37453aff4b8
---

改 bug 必须自测涉及接口的前后端, 不能只看一边就提交.

**Why:** 2026-06-10 修 switcher 空值 bug, 只测了前端组件逻辑 (vitest pass), 没有 curl 验证后端实际返回格式. 结果:
- 后端 `/api/kg/stats` 返回扁平 `{"nodes":61,"relations":84}`
- 前端期望嵌套 `{"neo4j":{...},"dify":{...}}`
- vitest 全绿但页面显示 0 — 因为 mock 数据是"正确格式", 真实后端不是
- 用户报"页面上没有数据"才暴露

**How to apply:**
1. 改完后端路由 → `curl http://localhost:8000/api/xxx` 确认返回格式
2. 改完前端组件 → vitest 确认解析逻辑
3. 前后端对接处 → 用真实后端返回格式写 test mock, 不要手造"理想格式"
4. 如果涉及 API 返回格式变更 → 同时更新前后端 + 测试
