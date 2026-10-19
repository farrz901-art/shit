---
name: undo-typo-commit-reset-soft-origin
description: 撤销本地误 commit 的正确目标不是 origin/master，而是误 commit 的父 commit (^1)，用 git reset --hard HEAD^ 比 reset --soft origin/master 安全
metadata: 
  node_type: memory
  type: feedback
  originSessionId: e3739144-feb9-4fec-b18a-a46a56d8d700
---

撤销本地误 commit 的正确目标不是 origin/master，而是**误 commit 的父 commit (`^1`)**。

**Why:** `git reset --soft origin/master` 会把所有领先于 origin 的本地 commit 一起"撤销"——HEAD 落到 origin/master = 丢光所有未 push 的工作。`git reset --hard HEAD^` 只撤销最近 1 个 commit，本地其他 commit 保留。

**How to apply:**
- 误 commit 之前，先 `git reflog` 找到误 commit 的 hash (例如 `116cb47f`)，用 `git reset --hard 116cb47f^` 或 `git reset --hard HEAD^` 撤销
- 永远不要在有领先未 push commit 的分支上 `git reset --soft origin/master` 想"撤销最近一次"
- 如果已经误 reset 到 origin/master，用 `git reflog` 找 HEAD 之前的位置 (e.g. HEAD@{n} = 误 commit 之前的状态)，`git reset --hard <那个 hash>` 恢复
- 测试 husky hook 不要用 `--allow-empty`——它只跳过"index 与 HEAD 相同"检查，staged 里有任何文件会一起被 commit。改用临时分支或 `git -c core.hooksPath=/dev/null commit` 跳过 hook 验证内容
