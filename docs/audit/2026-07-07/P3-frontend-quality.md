# P3 — 前端质量 修复 spec 草稿 (2026-07-07)

> ⚠️ 草稿, 未实施. 来源: [AUDIT-REPORT.md §D5](../AUDIT-REPORT.md)

## 范围
- **FE-001** (critical, verified) — submissions 4 文件 namespace + dotted key 必报 MISSING_MESSAGE
- **FE-002** (high, verified) — 22 处直引 next/navigation
- **FE-003** (high, verified) — AppField 缺 aria-invalid / aria-describedby
- **FE-005** (high, verified) — useBuyerProfiles queryKey inline object
- D5 其余 8 条 medium/low (FE-006/007/008/009/010/011/012/013)

## 修复策略

### 1. 修复 i18n 必报 (FE-001) — 最优先
- `app/[locale]/submissions/_components/*.tsx` 4 文件改 flat key 模式:
  - `useTranslations()` 不传 namespace
  - `t("审批")`, `t("通过")`, `t("驳回")` 中文作 key
- messages/zh.json + en.json 加对应中文 key
- 验收: `bun run test submissions` 不报 MISSING_MESSAGE

### 2. 22 处 import 路径 (FE-002) — 批量改
- 全部 22 处 `from "next/navigation"` 改 `from "@/i18n/navigation"`
- `useParams`, `useSearchParams` 保留 next/navigation (项目规约豁免)
- 验收: `grep "from \"next/navigation\"" packages/web/{app,components}` 仅剩 0 行 (除豁免项)

### 3. 表单 a11y (FE-003)
- `components/common/form/app-field.tsx` `buildInputElement` 加:
  ```tsx
  {hasError && "aria-invalid"}
  aria-describedby={error ? `${id}-error` : undefined}
  ```
- 同步更新所有 Form 组件 (AppField 是基础)

### 4. TanStack Query Key (FE-005)
- `useBuyerProfiles` 改 `queryKey: queryKeys.buyer.list(params)` 工厂模式
- 全项目建立 `lib/api/query-keys.ts` 统一 key 工厂

## 不在本文范围
- 实施代码
- FE-004 已 refuted (CLAUDE.md 默认 false)
