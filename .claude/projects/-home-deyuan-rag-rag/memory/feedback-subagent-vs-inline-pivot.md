---
name: feedback-subagent-vs-inline-pivot
description: 用户选 subagent-driven (选项 1) 不等于立刻派 subagent — 改 1 文件的小 task 应该 inline 执行，派 subagent 浪费 ≥ 1 个 turn
metadata: 
  node_type: memory
  type: feedback
  originSessionId: c0af4e04-e5b9-4a48-b332-19f579a3ee44
---

用户回复 subagent-driven (选项 1) 时，**默认不是"立刻派 subagent"**，而是"接受 subagent-driven 模式"。小 task（≤ 2 文件 + 改动 < 50 行）应该**直接 inline 执行**，**不要先派 subagent**。

派 subagent 前的判断标准：

- **inline 执行**：1-2 个文件，改动 < 50 行，无架构决策
- **派 subagent**：3+ 文件，多处协调，需要探索代码库，或方案不确定

**反例（本次 2026-06-27 实战教训）**：

用户选 subagent-driven → 我立刻派 subagent → 用户 reject → 我"猜他想 inline"但没真做 → 用户 4 次 interrupt → 我才发现根本没人改代码。

正确流程：

1. 用户选 1 → **直接开始 inline 执行**
2. inline 遇到 3+ 文件协调 / 架构不确定 → 这时**才**考虑派 subagent
3. 派之前**先**问"这个 task 是否要派 subagent"，不要默认派

**Why**: 派 subagent 多 1 个 turn（controller prompt + implementer 接活），对小 task 是浪费。harness 还有一个 classifier 拦"撤销自己改动"等动作 — 多一个工具调用 = 多一个 classifier 拒绝风险。

**How to apply**: 接到任务时按文件数 / 改动量评估，< 50 行直接 Edit；50-200 行看是否需要 Read 多文件决定；> 200 行或多文件协调才派 subagent。Subagent-driven skill 强调"per task" 但没强调"小 task 跳过 subagent"。