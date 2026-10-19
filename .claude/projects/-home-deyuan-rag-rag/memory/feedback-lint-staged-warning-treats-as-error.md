---
name: feedback-lint-staged-warning-treats-as-error
description: lint-staged (oxlint) 阻塞的判定 — 只看真 error (category=error 跟 rules 里标 error), warn 不阻塞. 旧说法"warning 也 exit 1"是过时或别的项目配置.
metadata:
  node_type: memory
  type: feedback
  originSessionId: 1dfcdecb-84bb-4149-9ad1-d1b332effa26
---

lint-staged 跑 oxlint 阻塞 commit **只**由真 error 触发:
- `categories.correctness = error` (默认)
- `categories.suspicious = warn` (默认, **不阻塞**)
- `categories.style = warn` (默认, **不阻塞**)
- `rules` 里显式标 `"error"` 的规则 (e.g. `complexity: ["error", { max: 20 }]`)

**WARN 不阻塞** — 之前 [[feedback-lint-staged-warning-treats-as-error]] 标题/首段说 "warning 也 exit 1" 是**过时**认知. 2026-06-15 BackLink 6 页迁移 commit 实测: staged 14 文件含 30+ 风格 warning (id-length / no-null / func-style / no-ternary / max-statements / max-params), 修了唯一真 error (TriplesForm complexity 23) 后 oxlint 0 报错退出 0, commit 通过. warning 留着没动.

**How to apply:**
- commit 前: `bunx oxlint <files> 2>&1 | grep "error "` 看**真 error 数量**. warning 数量不重要
- 真 error (no-unused-vars / complexity > 20 / no-console / 任何 correctness 分类的) 必修
- 风格 warning (id-length / no-null / func-style / no-ternary / no-magic-numbers / max-statements) 不阻塞 commit, **别**为这些花 scope
- 旧 memory [[feedback-windows-lint-staged-cwd-bug]] 仍有效 (Windows lint-staged ruff glob CWD bug)
- 关联 [[feedback-stop-and-ask-dont-loop-on-infra]] (lint-staged 阻塞 → 看是真 error 还是 warning; 真 error 修函数, warning 忽略)
- 关联 [[feedback-debug-stop-after-root-cause-confirmed]] (根因确认: 只看 oxlint error 行的, 别被 warning 数量吓退)
