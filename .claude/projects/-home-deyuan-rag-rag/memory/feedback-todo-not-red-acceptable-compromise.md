---
name: feedback-todo-not-red-acceptable-compromise
description: "当 pre-commit hook 阻塞时, vitest `it.todo` 是 TDD-red 的可接受妥协 (用户授权用过)"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: e231d327-c644-4a6c-949e-d3f999036ee1
---

当 pre-commit hook 跑 `vitest` 全量阻塞 TDD-red (subagent 加了 4 个 .todo 占位而不是真 fail), 用户接受了. 在 `decode-llm-view` 计划 (2026-06-12) Task 5 验证时: 4 个新 toggle 测以 `it.todo(...)` 形式 commit, 注释里写明 "Task 6 后改回 it() 即可". hook 通过, Task 6 时直接 un-todo + 写实现, 4 测转 green.

**Why**: 真 TDD-red 会让 hook 持续 fail, 卡 commit. `.todo` 在 vitest 报告里是独立状态 (不计数通过/失败), 告诉下一个 dev "这里有测试要实现". 比 `it.skip` 表达更强意图 (skip = 暂不跑, todo = 待实现).

**How to apply**:
- 默认走真 TDD-red (test 真 fail), `feedback-tdd-test-real-behavior-not-just-no-crash` 仍然优先
- 当 pre-commit hook / CI 强制 green, 且改动范围超出当前 PR 上下文, `it.todo` 是可接受的妥协
- `it.todo` 必须在测试文件里加中文注释说清: 这个测试对应什么 feature, 谁 implement 后要 un-todo
- Subagent 自主把测试改 `it.todo` 算"工作妥协" — 应该先停下来问用户, 不该自作主张 (跟 `feedback-clarify-ambiguous-instructions` 一致)
- 关联: [[feedback-tdd-test-real-behavior-not-just-no-crash]]
