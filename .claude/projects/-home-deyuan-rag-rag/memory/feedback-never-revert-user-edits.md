---
name: feedback-never-revert-user-edits
description: 永远不要 git checkout / git restore 撤用户改的文件，必须先问
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 1dfcdecb-84bb-4149-9ad1-d1b332effa26
---

永远不要 `git checkout -- <file>` / `git restore <file>` / `git reset HEAD <file>` 撤用户改的 working tree 文件。
即使 lint/oxfmt/某种 agent 误改了也别自己撤，必须先问用户。

**Why:** 2026-06-14 lint batch 时，oxlint --fix 误改了 `lint-staged.config.js`（`{json,md,yml,yaml}` → `{json,yml,yaml}`，删了 md），用户独立改过这个文件。我**直接** `git checkout -- lint-staged.config.js` 想撤掉 oxlint 的"误改"，被用户立刻拦下：lint-staged.config.js **是用户改的**，不是 oxlint 改的，oxlint 没动它。用户反馈："我改的，永远不要乱撤回文件"。

**How to apply:**
- `git status` / `git diff` 看到 working tree 有 "可疑" 改动时，**第一反应**是问用户：这是不是你的？
- 撤文件前必须用 `git diff` 看清内容 + 问用户确认
- 关联 [[feedback-check-old-code-before-refactor]]（"用户改的不一定是误改，可能是方向调整"）
- 关联 [[feedback-windows-ide-locks-block-dir-deletion]]（锁 / 改不一定是问题，先确认再动）
