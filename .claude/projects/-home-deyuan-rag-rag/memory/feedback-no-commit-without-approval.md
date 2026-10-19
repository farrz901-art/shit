---
name: no-commit-without-approval
description: User requires explicit approval before any commit or push - never commit without asking first
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 34f7405b-12e3-4f2b-b4b7-d591a1b68758
---

# 禁止擅自 commit 和 push

**Rule:** 没有用户明确同意，禁止执行 `git commit` 和 `git push`。

**Why:** 2026-06-22 session 中多次未经用户同意就 commit，用户纠正"没有我同意禁止commit和push"。用户要自己控制什么代码进版本库。

**How to apply:** 任何改动完成后，列出改了什么、等用户说"提交"或"commit"才执行 git commit。push 同理。
