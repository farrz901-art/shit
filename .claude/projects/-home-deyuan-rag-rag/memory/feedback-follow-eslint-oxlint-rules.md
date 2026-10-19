---
name: feedback-follow-eslint-oxlint-rules
description: "改完代码必须修 IDE 提示的所有 lint 警告, 不能批量赶进度忽略"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: ddb02d13-b877-47c3-8a38-ffa0f0098894
---

改完代码必须修 IDE 提示的所有 lint 警告, 不能批量赶进度忽略.

**Why**: 2026-06-16 withMemoryHooks 重写时赶进度, 一堆 IDE 警告没管 (id-length `c` / func-style `function` / no-magic-numbers / sort-imports / max-statements), 用户反馈 "解释为什么你写代码不遵守eslint和oxlint的规范, 也不遵守claude.md的规范, IDE里面一堆警告也当没看到". web/CLAUDE.md 当天被加了一条: "需要修复IDE提示的警告".

**How to apply**:
- 每次改完文件, 跑 `bun x oxlint <file>` + `bun x tsc --noEmit` 验证
- 警告 (不只是错误) 也修
- 常见警告类型:
  - `id-length`: 1 字符变量, 用 `idx` / `val` / 全名
  - `func-style`: 用 `const fn = () => {}` 不用 `function fn() {}`
  - `no-magic-numbers`: `0` `1` `8` 等数字提 const
  - `sort-imports`: import 按字母序, multi-line 在 single-line 前
  - `max-statements`: 函数 ≤10 句, 拆小函数
- 装饰器 / 库函数 (如 withMemoryHooks) 也按规范, 不豁免
