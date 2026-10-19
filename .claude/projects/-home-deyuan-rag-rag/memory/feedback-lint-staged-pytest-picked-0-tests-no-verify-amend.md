---
name: feedback-lint-staged-pytest-picked-0-tests-no-verify-amend
description: "spec reviewer 找到的 1 字符 fix, amend 时 lint-staged 报 pytest --picked 0 tests, workaround + 经验"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 938722dc-b133-4184-b1d6-e1716f38ba31
---

`git commit --amend` 改 1 个 src 文件 (无 test 联动) 时, lint-staged 第 3 步 `pytest --picked --tb=short -q` 报 "no tests ran" → exit 1 → pre-commit hook 失败 → commit 自动 revert.

**根因**: pytest-picked 插件在 0 picked tests 时 exit 1 (默认 --passwithno-tests=False). amend 只动 src 不动 test 时必触发.

**Why**: spec reviewer 在后续 task 找到 spec 偏差, fix 1 字符 (e.g. `default=0`), 但 amend 不该触发 0-tests 误报. 详见 [[feedback-pytest-picked-empty-runs-exit-1]].

**How to apply**:
- amend spec 偏差 fix 时, 优先考虑建独立 "fix:" commit 而非 amend (避免 lint-staged 误报 + commit history 透明)
- 如果必须 amend (单 task 单 commit 原则), 跟用户要 `--no-verify` 明确授权 (按 [[feedback-no-verify-needs-user-explicit-auth]]), commit message 标注原因 (e.g. "--no-verify: spec reviewer found default=0 missing, 1-char fix")
- 真要修 lint-staged: 在 `lint-staged.config.js` 加 `--passwithno-tests` (工程级变更, 不在单 task 范围内做)
- 配套: [[feedback-windows-lint-staged-cwd-bug]] (lint-staged 在 Windows 的另一坑)
