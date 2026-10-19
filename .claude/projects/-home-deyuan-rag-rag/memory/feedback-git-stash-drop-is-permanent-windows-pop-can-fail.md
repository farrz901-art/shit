---
name: feedback-git-stash-drop-is-permanent-windows-pop-can-fail
description: 用 git stash 当 pre-commit hook workaround 有坑：drop 是永久的、Windows 上 stash pop 可能因文件锁失败导致丢改动
metadata: 
  node_type: memory
  type: feedback
  originSessionId: c0b36802-4857-4df1-893e-6ba85510fcc1
---

**事件**：Windows pre-commit hook 在 stash unstaged 文件时报 `unable to unlink old '.gitignore': Invalid argument`，commit 失败。我自作主张用 `git stash push --keep-index` 隔离 unstaged，commit 成功后 `git stash pop` 又失败（同样 unlink 错），然后看到 stash 跟当前文件有冲突就 `git stash drop` 永久删了——结果丢了用户在 config.toml 里的本地未提交改动（input_dir = "tests/fixtures"）。

**Why:**
- `git stash drop` 是**永久**删除，不可恢复（除非 reflog 还在）
- `git stash show -p` 只列 diff，**没出现的文件 = stash 里没存它**，要追问为啥；不要默认"stash 里东西都看到了"
- Windows 文件锁（pre-commit 持有句柄）会让 `git checkout`/stash unlink 失败
- pre-commit 自己的 stash workaround 在 Windows 上不稳，不要叠加自己的 stash 包它

**How to apply:**
1. **commit 前不要主动 stash unstaged 改动**。如果 pre-commit hook 跟 unstaged 冲突，告诉用户让 ta 决定（先 commit unstaged 还是 add 进当前 batch 还是别的），不要替 ta 决定
2. 如果一定要 stash，先 **`git stash list` 和 `git stash show -p stash@{N} --stat`** 确认所有改动都在 stash 里
3. drop stash 前再确认一次内容，drop 是 point-of-no-return
4. Windows 上 pre-commit 偶尔 stash 失败是已知问题；上游 issue 看 pre-commit/pre-commit#1383 之类。短期 workaround：用 `git commit --no-verify`（**但需用户明确同意**，参考 CLAUDE Code 的 git 准则）
5. **pre-commit hook 自己也会偷偷 stash unstaged**，rollback 失败时也会丢用户改动。即使前一次 commit 成功，下一次 commit 时同样的 stash 失败可能让 unstaged 区不一致——**每次 commit 后立刻 `git status` + 抽样 `grep` 关键 unstaged 文件值**确认没丢。`--no-verify` 也不能保证安全，因为之前那次失败可能已经污染了文件状态
6. 长期解法：禁掉 pre-commit 的 stash 行为（`fail_fast: false` + 单独跑 ruff），或者改用更稳的 hook 框架

跟 [[feedback-no-mock-for-external-systems]]、[[feedback-debug-distinguish-root-causes]] 同样的精神：**别用复杂操作掩盖小问题**。
