---
name: project-settings-dialog-no-account-row
description: "SettingsDialog 故意只渲染 2 行 (主题/语言)，没有 \"账号\" 行 — T4.3 测试预期已过时，回归测试应删"
metadata: 
  node_type: memory
  type: project
  originSessionId: c0af4e04-e5b9-4a48-b332-19f579a3ee44
---

`packages/web/components/settings/settings-dialog.tsx` 当前实现**故意只有 2 行**：

- 行 1: 主题 (active)
- 行 2: 语言 (active)

**没有** "账号" 行 / `settings-account-link` testid。

历史：T4.3 (2026-06-18) 曾规划加"账号"行链 `/account/settings`，配套写了 `components/settings/settings-dialog.test.tsx` 里 2 个测试（"渲染 3 行" + "账号行激活"），但实现后来被用户**主动删除**（确认于 2026-06-27 conversation），原因待补。

**Why**: 用户主动删除功能实现意味着测试也要同步清理（测试预期跟实际行为不一致 = 死回归）。

**How to apply**:
- 跑 `bun run test` 看到 `settings-dialog.test.tsx` 的 2 个 fail（"渲染 3 行" + "账号行激活"），**不要修** SettingsDialog.tsx 添加账号行，**也不要**简单加 testid。
- 正确做法：从测试文件删除这 2 个过时的 `it(...)` 块（让测试反映当前真实行为）。改前先跟用户确认是否同意删测试。
- 关联：[[feedback-bun-run-test-no-redundant-runs]]（避免看到 fail 反复重跑）