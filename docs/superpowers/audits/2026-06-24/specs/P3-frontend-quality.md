# P3 - 前端质量 spec 草稿 (2026-06-24)

> ⚠️ 草稿, 未实施.
> 来源: [AUDIT-REPORT.md](../AUDIT-REPORT.md) §D5 Frontend pitfalls + D6 ARCH-001 (useRouter dedup)
> 关联 checklist: [docs/audit/2026-06-24-findings.md](../../../../docs/audit/2026-06-24-findings.md)

## 范围

### Critical (2)
- FE-001 — evaluate-new-form useRouter 违规
- FE-002 — output/new useRouter 违规

### High (10)
- FE-003 — run-detail-view
- FE-004 — evaluate-list-view
- FE-005 — submissions-tabs
- FE-006 — permissions-admin-client
- FE-007 — message-feedback
- FE-008 — reset-password
- FE-009 — back-link (全局封装组件)
- FE-010 — settings-dialog
- FE-011 — triples-form / qa-submit-form / import-commit-card (3 个表单)
- ARCH-001 (dedup) — 12 个 useRouter 违规 (D6 视角, 跟 FE-001~011 完全重叠)

### Medium (1)
- FE-012 — NEXT_PUBLIC_CHAT_TOKEN 公开

合计 12 条 finding (1 dedup).

## 修复策略

### Phase 1 (1-3 天) — useRouter 批量修

1. **统一修复模式** (跟 login/invite 已修同款):
   - `import { useRouter } from "next/navigation"` → `import { useRouter } from "@/i18n/navigation"`
   - `router.push("/foo")` → `router.push("/foo")` (createNavigation 包装自动加 locale)
   - 手动拼 `${params.locale}/foo` 全部去掉, 走 wrapper

2. **FE-009 back-link.tsx 优先**: 全局封装组件, 修了影响所有 `useHistory=true` 页面.

3. **批量修复文件 (12 个)**:
   - evaluate-new-form.tsx, output/new/page.tsx
   - run-detail-view.tsx, evaluate-list-view.tsx, submissions-tabs.tsx
   - permissions-admin-client.tsx, message-feedback.tsx, reset-password/page.tsx
   - back-link.tsx, settings-dialog.tsx
   - triples-form.tsx, qa-submit-form.tsx, import-commit-card.tsx (3 个表单同模式, 一次性改)

4. **加 import guard 测试** (跟 login/page.test.tsx 同模式):
   - 在 `vitest.setup.ts` 加全局 grep: 任何 `*.tsx` import `next/navigation` 的 `useRouter` 都 fail
   - CI 跑 `bun run typecheck && bun run lint:fix && bun run test`, 卡住不通过

### Phase 2 (1 周) — token 设计 review

5. **FE-012**: 评估 `NEXT_PUBLIC_CHAT_TOKEN` 设计: 是 CSRF token 还是其他用途? 文档化, 加速率限制 (跟 D1 SEC-007 同模式).

## 不在本文范围

- 实施代码 (留到 plan + implement 阶段)
- a11y / i18n key 完整性 / bundle 体积 (后续 spec, D5 已知缺口)
- P0/P1/P2/P4 其他维度 finding

## 验收标准

- 12 条 finding 全部 verified=true
- `grep -r 'from "next/navigation"' packages/web --include="*.tsx" --include="*.ts"` 0 命中 (除了 `useSearchParams` 已知豁免)
- import guard 测试通过, 阻止新违规
- E2E Playwright 验证登录 → 各页面跳转无 307
