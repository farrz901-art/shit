# P3 - 前端质量 spec 草稿 (2026-06-26)

> ⚠️ 草稿, 未实施.
> 来源: [AUDIT-REPORT.md](../AUDIT-REPORT.md) §Frontend (D5)
> 关联 checklist: [docs/audit/2026-06-26-findings.md](../../../../docs/audit/2026-06-26-findings.md)

## 范围

### 已验证 finding
- FE-001 (critical) — ActiveSwitch 用 next/navigation 的 usePathname, 路由匹配全失效 (en locale 下 DomainSwitcher 不渲染)

### 未 verify
- FE-004 (medium) — 6 个 RSC 文件用 next/navigation 的 redirect
- FE-005 (low) — knowledge-tabs 缺 aria-current="page"
- FE-006 (info) — useConversations 覆盖 refetchOnWindowFocus=true
- FE-007 (medium) — SettingsDialog 混用两种 usePathname/useRouter 导入源

### Refuted (排除)
- FE-002 (high) — ImportCommitCard useRouter (手动拼 locale 前缀, 功能正确)
- FE-003 (high) — KnowledgeTabs usePathname (next-intl middleware 已剥离 locale 前缀)

## 修复策略

### 1. ActiveSwitch critical fix (P0 级别)
- `import { usePathname } from "next/navigation"` → `import { usePathname } from "@/i18n/navigation"`
- 或改用 `useParams()` 获取 locale, 自行剥离前缀
- 验证: en locale 下 DomainSwitcher 正确渲染

### 2. RSC redirect 统一
- 6 个 admin/page.tsx 文件: `redirect()` from `next/navigation` → `@/i18n/navigation`
- 验证: admin 页面跳转无 307 重定向

### 3. A11y
- knowledge-tabs 加 `aria-current="page"` 在 active tab
- 统一 `<button>` 替代 `<div onClick>`

### 4. TanStack Query 配置
- useConversations 加 `refetchOnWindowFocus: false` (或改全局默认)
- cache key 规范化

### 5. Import 源统一
- SettingsDialog 统一为 `@/i18n/navigation` 导入

## 不在本文范围
- FE-002, FE-003 (refuted) — 排除
- P0/P1/P2/P4 finding
