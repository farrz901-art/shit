---
name: project-dify-chatflow-sse-duplicate-emit
description: "Dify Chatflow app 在 message delta + workflow_finished.outputs.answer 双发射完整答案, 归一化层必须 seenMessage 守卫避免重复"
metadata: 
  node_type: memory
  type: project
  originSessionId: b6549352-bae7-4990-9bda-b272f6c023d1
---

Dify Chatflow 类型 app (新式 workflow + 流式 message) 通过 SSE **双发射**完整答案:

1. `message` 事件: 流式 delta chunks (前端 content += delta 累加)
2. `workflow_finished.data.outputs.answer`: workflow 完成后把完整最终答案放在 outputs 里

**老式 Workflow app** (无 message 事件, 只有 node_* + workflow_finished) 走第 2 条路拿答案.

**坑**: 早期 `packages/web/lib/chat/dify.ts:workflow_finished` 无脑 `yield { type: "message", delta: answer }`. Chatflow 下前端 content 重复显示 ("1LE1001-0BB32-2GA4型号属于1LE1系列" 出现两遍).

**修法** (commit `fc0722a`, 2026-06-12): `parseStream` 维护 `seenMessageRef = { current: false }` 闭包状态, `normalize(ev, seenMessageRef?)` 接收, workflow_finished 守卫:
```ts
if (answer && !seenMessageRef?.current) {
  yield { type: "message", delta: answer };
}
```
`parseStream` 在 yield message 事件时设 `seenMessageRef.current = true`. 老式 Workflow app 没 message 事件, 守卫永远 false, 兼容不变.

**Why:** 双源归一化是上游协议复杂时的常见坑, 守卫必须按"上游是否已经发过"判断, 不能按"该字段是否存在".

**How to apply:** 任何 SSE / event-stream 归一化场景, 上游可能多源发同语义数据时, 用 per-stream ref 跟踪"已见标志", 在归一化层守卫. TDD 必须**两个 case**都覆盖 (多源 + 单一源兼容).

**Test 模板** (见 `packages/web/lib/chat/dify.test.ts:127-238`):
- Chatflow case: 2 个 message delta + 1 个 workflow_finished (outputs.answer 跟 delta 拼出的相同), 期望 2 个 message 事件
- 老 Workflow case: 0 个 message + 1 个 workflow_finished (outputs.answer 有), 期望 1 个 message 事件 (兼容老 app)

**Link**: [[feedback-no-shim-no-minimal-changes]] (不要用 type cast 或 ignore 兜底掩盖), [[feedback-tdd-test-real-behavior-not-just-no-crash]] (测试必须真覆盖双源 + 单源两端)
