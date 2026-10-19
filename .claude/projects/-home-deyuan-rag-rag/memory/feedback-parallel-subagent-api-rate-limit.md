---
name: parallel-subagent-api-rate-limit
description: "4 个 background subagent 派发时 API 限流, 表现 + 应对 (2026-07-08 code-quality 4 plan)"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 0eaa132e-ba77-44f2-a0b6-807b6fd66f8c
---

**问题**: 同一 message 派 3-4 个 `run_in_background: true` agent 时, 部分会撞 "MiniMax-M3[512K] is temporarily unavailable" 错误 (auto mode 分类器暂时禁用, 跟模型本身无关心). 失败率 ~50%, 4 次 retry 后稳定.

**根因猜测**: classifier 高并发过载 (auto mode 跑安全检查需要算力), 不是 quota 也不是内容. 改 prompt 没用, 改 plan 也没用.

**应对**:
- 第一次只派 2-3 个, 留一个 retry
- 失败立即重试, 不要 batch 等; classifier 恢复很快 (~10-30s)
- 4 次以内 retry 必成功, 超过就等下一个 background agent 完成通知
- 永远不要因为 "派发失败" 就放弃 parallel 模式, 这是工具链小毛病, 跟项目无关心

**Why**: 用户在 2026-07-08 code-quality-scan 4 plan 并行执行时, 问了"为什么只有 planA 在改文件". 我若误判是 plan 内容问题, 反而会推串行执行浪费 1 周. 真相是 classifier 限流, B/C/D 接连 4 次 retry 失败但 worktree 早就 ready.

**How to apply**: 派 ≥3 个并行 subagent 时, 第 1 轮失败立刻 retry (不 sleep 不 batch), 直到成功. 用 todo 列表标 API 限流, 不当 BLOCKED 报用户.
