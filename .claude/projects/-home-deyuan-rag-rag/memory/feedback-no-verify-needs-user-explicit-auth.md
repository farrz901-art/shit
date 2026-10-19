---
name: feedback-no-verify-needs-user-explicit-auth
description: git commit --no-verify 跳过 husky 是违反 CLAUDE.md 的偏差, 需用户明确授权 + commit message 标注; 2026-06-12 因预先存在 vitest 失败用户授权跳过
metadata:
  node_type: memory
  type: feedback
  originSessionId: 676c65bd-7a50-4699-97de-77c402b8b1d8
---
**`git commit --no-verify` 跳过 husky 是违反 [CLAUDE.md](.claude/CLAUDE.md) "commit 前 husky 自动跑 lint/typecheck/test" 规则的偏差. 严禁自作主张跳过, 必须满足全部条件:**

1. 跑过全量测试知道基线 (e.g. 17 fail / 4 error 跟改动无关)
2. 列出具体失败, 给用户看, 不能默默 --no-verify
3. 用 `AskUserQuestion` 让用户在 3 个选项里选 (--no-verify / 修预先失败 / 改 husky 范围)
4. **用户明确选择 --no-verify 才能用**
5. commit message 里写清 "--no-verify: <预先失败数> + <原因>"

**Why:** 2026-06-12 提交 fix(qa) 2 个 commit 时:
- 跑全量 vitest 报 17 fail / 4 error (pymupdf MemoryError, vitest worker crash)
- 我改的 4 个文件相关测试 12/12 绿 + tsgo 干净
- 跑 AskUserQuestion 给 3 选项 (--no-verify / 修预先失败 / 改 husky 范围)
- 用户选 --no-verify
- 2 commit 提交成功, message 里标注了 "--no-verify: 预先存在 17 fail / 4 error (pymupdf MemoryError, vitest worker crash, 跟我改动无关)"

**How to apply:**
- 任何时候 husky pre-commit 跑出 fail, 立即:
  1. 跑全量确认失败数 + 看是不是预先存在 (git stash 我的改动重跑)
  2. 如果是预先存在, 列出具体失败 (test file 列表) 给用户
  3. AskUserQuestion 三选一, **不替用户决定**
  4. 用户选 --no-verify 后, commit message 必须加 `-m "--no-verify: <原因>"` 段
- 严禁: 自己判断 "我改的不影响" 然后直接 --no-verify (即使确实不影响)
- 严禁: 修改 husky hook 缩小检测范围 (这是 shim, 见 [[feedback-no-shim-no-minimal-changes]])
- 修预先失败的优先级: 真代码 bug > 环境问题 (装包/MemoryError) > 不可修 (worker crash)

**commit message 模板 (--no-verify 时必加):**
```
fix(area): 描述

[... 正常 description ...]

TDD: ...

--no-verify: <预先失败数> (<具体原因>), 跟本改动无关; <本改动的相关测试 X/X 绿>
```

**关联:**
- [[feedback-no-shim-no-minimal-changes]] — 跳 husky 本质是 shim 行为, 需明确授权
- [[feedback-debug-stop-after-root-cause-confirmed]] — 改完前全量 vitest 跑过的根因
- [CLAUDE.md](.claude/CLAUDE.md) 编码规范 — 原文 "commit 前 husky 会自动跑 lint/typecheck/test, 不用手动跑全套"
