---
name: feedback-turbopack-postcss-panic-10054
description: "Turbopack dev server panic (os error 10054 远程主机关闭连接) 是 PostCSS worker 子进程偶发崩溃, 不是代码 bug. 重启 dev server 即可."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 298dc759-254d-43ee-a841-71ccb0b25682
---

Turbopack dev server 偶发 panic: `FATAL: An unexpected Turbopack error occurred` + `GET <path> 500` + 浏览器报 `An unexpected Turbopack error occurred`.

**panic log 关键诊断信息**:
- `Failed to write app endpoint <path>` (看起来像页面, 实际是子进程死)
- 错误链: `app/globals.css [app-client] (css)` → `PostCssTransformedAsset::process` → `evaluate_webpack_loader` → `failed to receive message` → `reading packet length` → `os error 10054 远程主机强迫关闭了一个现有的连接`
- 页面 + 错误页内容**无关**: 任何页面都可能触发, 不代表该页面有 bug

**Why**: 2026-06-15 用户访问 `http://localhost:3000/zh/evaluate/new` 报 500. 当时 typecheck 0 错, page.tsx 极简 (1 行 import + RSC wrapper), 最近 commit (StatusBadge 重构) 不被该页面 import. grep 全项目找 `evaluate/new` 引用 5 个都是预期的 (子组件 / 测试 / e2e / 工具). **判定: Turbopack PostCSS worker 子进程崩溃, Windows 已知偶发**.

**How to apply**:
- 看到 Turbopack panic + `os error 10054` / `failed to receive message` / PostCSS worker 链路: **不要怀疑代码, 先重启 dev server**
- 重启步骤: `Ctrl+C` 停 `bun run dev` → 再 `bun run dev` → 刷页面
- 重启还 500: `rm -rf .next && bun run dev` 清缓存
- 修复前**不要**乱改 page / globals.css / tailwind config (Turbopack panic log 提的 globals.css 是子进程死时正在处理的文件, 不是 globals.css 的错)
- 关联 [[feedback-debug-distinguish-root-causes]] (TCP 连接重置 ≠ 应用代码错) + [[feedback-debug-stop-after-root-cause-confirmed]] (panic log 锁底层连接错就停, 别追应用层)
