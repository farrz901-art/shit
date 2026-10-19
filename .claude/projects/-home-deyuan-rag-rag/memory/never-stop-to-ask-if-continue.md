---
name: never-stop-to-ask-if-continue
description: 禁止擅自停下来问用户是否要继续
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 2660315c-cbbc-4ea0-864e-e0a4a05a15b0
---

用户 2026-07-06 纠正：我在 Task 9 完成后停下来问"要今天继续还是改天再做？"，用户要求"禁止擅自停下来问是否继续"。

**Why**: 用户没说过要停，也没问过进度。我停下来问是在把"要不要继续"的决策成本丢给用户，本质上是让自己省事。项目 CLAUDE.md 明确写"不要用户的任务没完成,随意停下来"。

**How to apply**:
- 用户下达任务后，持续执行直到完成，不中途问"要不要继续" / "要今天还是改天" / "还做吗"
- 如果遇到真正的 blocker（依赖缺失 / 测试全红 / 理解分歧），可以报告问题+给方案，但不是问"还做不做"
- 任务完成（全部测试通过 + 全量验证）后，按 finishing-a-development-branch skill 自动收尾，不额外问
