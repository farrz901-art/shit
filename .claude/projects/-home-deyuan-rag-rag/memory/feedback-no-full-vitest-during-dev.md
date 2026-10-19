---
name: feedback-no-full-vitest-during-dev
description: "开发中只测改过的文件, 禁止动辄跑全量 vitest (1+ 分钟, 跟其他卡点叠加让用户等)"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 1dfcdecb-84bb-4149-9ad1-d1b332effa26
---
开发中只跑修改文件的测试 (`bun run test -- <pattern>` 或具体 `path.test.ts`), 禁止动辄 `bun run test` 跑全量. 用户原话: "不要动不动跑全量测试, 开发的时候测试只允许测试修改的文件".

**Why:** 全量 vitest 在该项目要 50-80 秒 (117 文件, 522+ tests), dev 反馈循环里叠加 1+ 分钟很拖, 用户多次被打断.

**How to apply:**
- dev 改完单文件: `bun run test -- <文件名或 glob 模式>` (vitest 的 path filter)
- 改跨多个文件: `bun run test -- <dir 或 file1 file2>`
- **只**在以下情况跑全量:
  - pre-commit hook 自己会跑 (用户没要求手动跑)
  - commit 之前, 验证 lint-staged 之外的东西
  - 明确"全量过一遍" 的指令
- typecheck 也是同理, 优先按 `tsc` 增量, 或用 IDE 提示
- 关联 [[feedback-stop-and-ask-dont-loop-on-infra]] (耗时长 = 浪费 token, 别自动跑)
