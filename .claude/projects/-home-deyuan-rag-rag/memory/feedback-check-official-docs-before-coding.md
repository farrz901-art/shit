---
name: feedback-check-official-docs-before-coding
description: 工具/平台的 API 和接口必须先查官方文档再写代码，不要猜测
metadata: 
  node_type: memory
  type: feedback
  originSessionId: eec4f205-4669-4734-b77f-77c2e0b18e11
---

工具和平台的 API 和接口必须先查官方文档再写代码，不要猜测。

**Why**：
- 非标准格式（如 Dify SSE 把 event 和 data 放在不同块）
- 字段名不一致（如 indexing_mode vs indexing_technique）
- 必填字段遗漏（如 inputs 字段）
- 答案位置不同（如 workflow_finished.data.outputs.answer 而非 message 事件）

**How to apply**：
1. 遇到第三方 API，先查官方文档（搜索 "xxx API reference"）
2. 用 curl 测试真实响应格式，不要假设格式
3. 对比文档和实际响应，确认字段名、类型、必填项
4. 写代码前先理解 API 的完整流程（请求 → 响应 → 错误处理）

**本次踩坑记录**（2026-06-09）：
- Dify chat-messages API：缺 inputs 字段 → 400
- Dify SSE 格式：event 和 data 在不同块 → parseBlock 需累积 event name
- Dify Chatflow 答案位置：workflow_finished.data.outputs.answer 而非 message 事件
- Dify createDocumentByText：字段名是 indexing_technique 不是 indexing_mode
