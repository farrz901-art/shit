---
name: feedback-pytest-picked-empty-runs-exit-1
description: pytest --picked 0 tests 时 exit 1, 锁死 lint-staged commit — 用 --no-verify 绕过或加 --passwithno-tests
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 1dfcdecb-84bb-4149-9ad1-d1b332effa26
---

`pytest --picked` 在 working tree 改的 .py 不关联 test 时 (例: 改 src/ 但 test 没对应改动) → 0 tests → exit 5 → lint-staged 把这退出码当 task 失败 → commit 整体失败, reflog 不留 entry。

**Why:** 2026-06-14 commitY1 backend ruff 3 文件时, `bash -c "cd packages/service && ./.venv/Scripts/python.exe -m pytest --picked --tb=short -q"` 返 "no tests ran in 0.00s" + exit 1。lint-staged 把 3 步 (ruff check --fix / ruff format / pytest --picked) 串起来, 第 3 步 fail → 整个 commit 任务 fail, staged files 被 revert, reflog 不写。`git status` 看文件未提交, 但不知道为啥。

**How to apply:**
- 改 backend src/ 但无 test 改动时, **预判** pytest --picked 会 0 tests exit 1
- 2 选 1:
  - **A. `git commit --no-verify` 绕过** (合理场景: 改的是 src 自身 lint, 不需要跑 test)
  - **B. 在 lint-staged.config.js 的 pytest 命令加 `--passwithno-tests`**, 让 0 tests 时返 0 而不是 5 (root 修)
- 关联 [[feedback-stop-and-ask-dont-loop-on-infra]] (hook infra 失败 ≠ 代码错, 别自己 debug 死循环)
- 关联 [[feedback-uvicorn-must-restart-after-route-add]] (Python 工具链在 Windows hook 子进程易出意外)
