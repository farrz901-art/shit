---
name: feedback-front-end-api-must-have-tests
description: 前端新增的 API 接口必须写 vitest 单元测试
metadata: 
  node_type: memory
  type: feedback
  originSessionId: eec4f205-4669-4734-b77f-77c2e0b18e11
---

前端新增的 API 接口（BFF 路由、lib/api 层）必须写 vitest 单元测试。

**Why**：
- 防止接口参数变更导致静默失败（如 Dify API 缺 `inputs` 字段返回 400）
- 保证请求体结构、鉴权、错误处理符合预期
- 回归测试覆盖，重构时有安全网

**How to apply**：
- 每个 BFF route 新增时，对应写 `app/api/xxx/route.test.ts`
- 每个 lib/api 层新增时，对应写 `lib/xxx.test.ts`
- 测试内容至少覆盖：
  1. 正常请求体结构（字段名、类型、默认值）
  2. 必填字段校验
  3. 错误处理（HTTP 4xx/5xx）
  4. 鉴权头（Authorization Bearer）
- 命名规范：`描述 + 断言`（如 "inputs 字段必须存在"）
