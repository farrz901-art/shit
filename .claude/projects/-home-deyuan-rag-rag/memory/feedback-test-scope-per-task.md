---
name: test-scope-per-task-not-whole-plan
description: "跑 subagent-driven task 时只 test 修改的文件, 不跑全量; 只有完成整个 plan 才跑全量 test"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 04c90ace-3037-4d78-89b5-cf5b537f4d60
---

跑 subagent-driven task 时, 单 task 验证 **只 test 该 task 修改过的文件** (e.g. `bun run test <modified_dir>`). 不要 `bun run test` 全量跑.

**唯一例外**: 完成整个 plan (e.g. P3 全部 10 task) 后, 才跑全量 `bun run test` + `bun run test:coverage` 验证 baseline 没回归.

**Why**: P4 期间每 task 都跑全量 test, 单次 test 130+ seconds + 多次重复. 浪费 token + 时间. 用户 2026-06-28 明确要求: "除非完成一整个 plan 才允许执行全量 test, 其他时候只允许 test 修改的文件".

**How to apply**:
- 单 task 跑完 → `bun run test <modified_dir>` (e.g. `bun run test components/knowledge` if only that dir changed)
- 单 task 验证 typecheck + lint + format 仍要全量跑 (这些快, 几秒)
- 完成 plan 的最后一个 task 后 → 跑全量 `bun run test` + `bun run typecheck` + `bun run lint` + `bun run format:check`
- 如果 task 修了多个 dir, 把多个 dir 都列出来: `bun run test components/knowledge components/common`

**Related**: [[feedback-bun-run-test-no-redundant-runs]] (单次定位 file:line, 不重跑找 detail)
