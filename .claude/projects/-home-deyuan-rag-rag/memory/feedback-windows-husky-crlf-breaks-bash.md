---
name: feedback-windows-husky-crlf-breaks-bash
description: "Windows + core.autocrlf=true 会把 .husky/* 改成 CRLF, sh 把 `(` 当 subshell → commit-msg 语法错; 治本用 .gitattributes 强制 LF"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 3b7af552-3127-4a12-ab0d-d07207a4578e
---

●Windows 上 `core.autocrlf=true` 会把 `.husky/commit-msg` (含中文 + `(` + `"`) 转成 CRLF, bash 解析到 `"...\r\n` 时把 `\r` 当 token 边界破坏, 下行 `echo "feat(api): ..."` 里的 `(` 被当 subshell 起始符 → `syntax error near unexpected token '('`

**Why:** 2026-06-15 commit 时报两个错: lint-staged "no staged files matching" (.md 没规则) + .husky/commit-msg line 31 syntax error. 根因是 autocrlf 把 sh 脚本污染了.

**How to apply:**
- 治本: 项目根加 `.gitattributes` 含 `.husky/* text eol=lf` + `*.sh text eol=lf`
- 本机: `git config core.autocrlf false` 然后 `git rm --cached` + `git checkout` 拿回 LF
- 诊断: `file .husky/commit-msg` 看 "with CRLF line terminators" 即确诊
- 同时: lint-staged.config.js 没 `.md` 规则, staged markdown 文件会让 lint-staged exit 1
- 相关: [[feedback-windows-lint-staged-cwd-bug]] (另一个 Windows lint-staged 坑)
