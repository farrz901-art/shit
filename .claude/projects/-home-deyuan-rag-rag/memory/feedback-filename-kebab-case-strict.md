---
name: feedback-filename-kebab-case-strict
description: "所有 .ts/.tsx 文件名必须 kebab-case, 不许 PascalCase, 不许混用 (用户 2026-06-15 严正纠错)"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 298dc759-254d-43ee-a841-71ccb0b25682
---

oxlint `unicorn/filename-case` 在项目内强制 kebab-case (跟 CLAUDE.md "必须严格遵守 eslint 和 oxlint 代码规范" 对齐)。用户 2026-06-15 严正反馈: 即使是组件文件 (如 BreathingDot/HealthDot/DecodeInputBar) 也必须用 `breathing-dot.tsx` / `health-dot.tsx` / `decode-input-bar.tsx`, 跟测试文件 `xxx.test.tsx` 一致。**不要弄两种命名方式混用**。

**Why:** 项目 oxlint 强制规则 + 跟 shadcn / Next 社区惯例统一; 大驼峰 + 小写混用让 grep/import 时记忆负担大, 也让新手不知道用哪个 case 起新文件。Trae/VSCode 在 Windows 大小写不敏感的 NTFS 上还可能出现 `HealthDot.tsx` 和 `healthdot.tsx` 都能 import 但 git 看作两个文件的诡异 bug。

**How to apply:**
1. **新建文件**: 一律 kebab-case (`breathing-dot.tsx`, `data-table.tsx`, `app-dialog.tsx`)。
2. **改到 PascalCase 旧文件**: 顺手 `git mv` 改名 + 更新所有 import (grep `from "@/.../OldName"`)。改名 commit 单独发, 不混进功能 commit。
3. **export 标识符**: 仍用 PascalCase (`export function BreathingDot`), 只文件名 kebab-case。React 组件名/类名 PascalCase 是 ESLint/React 规则要求, 不矛盾。
4. **测试文件命名**: `xxx.test.tsx` (跟实现文件同 case, 即 kebab-case)。
5. **检查存量违规**: `bun lint | grep "filename-case"`, 改名前先评估 import 影响面 (grep 引用点)。
6. **历史 PascalCase 违规清单 (2026-06-15)**: HealthDot.tsx, DecodeInputBar.tsx, ChatShell.tsx, 至少这 3 个待清。

**关联:** 覆盖/作废 [[feedback-react-file-size-and-dialog-naming]] 里 "XXDialog.tsx" 这句 — 应该是 `xx-dialog.tsx`。
