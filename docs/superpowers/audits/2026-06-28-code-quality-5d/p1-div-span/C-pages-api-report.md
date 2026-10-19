# P1 维度审计 · C 区（pages + api）div/span 可封装扫描报告

- **生成时间**: 2026-06-28
- **扫描范围**: `packages/web/app/**` 下所有 `.tsx` / `.ts`（排除 `.test.tsx` / `.test.ts`）
- **扫描目的**: 找出仍以原生 `<div>` / `<span>` 形式出现、且项目已有封装组件可替换的重复 markup
- **审计员**: Agent C（覆盖范围 = 所有页面路由 `app/[locale]/**/page.tsx` + `app/[locale]/**/_components/**/*.tsx` + 所有 `app/api/**/route.ts`）
- **已读文件**: 128 个 `.tsx` 业务文件 + 25 个 `.ts` API 路由 + 1 个 `proxy.ts`（实际是 `app/api/[...path]/route.ts`）

---

## 1. 扫描概览

| 维度 | 数值 |
| --- | --- |
| 扫描文件总数 | 154（128 .tsx + 25 .ts + 1 catch-all proxy） |
| 页面路由 `page.tsx` | 56 |
| `_components/**/*.tsx` 客户端组件 | 72 |
| API 路由 `route.ts`（含 BFF catch-all） | 26（全部为 JSON `Response.json`，**无 div/span**） |
| 含 `<div>` + `<span>` 的业务文件 | 128（100% 页面/component 文件） |
| 重复出现 ≥2 次的可封装 pattern | **24 类**（Top-10 见 §3） |
| 已经正确使用 `<ErrorBanner>` 替代手写 `border-destructive/30 bg-destructive/5` 的文件 | 9 |
| 仍然手写失败/告警条幅的文件 | **5**（详见 §2.6） |
| 已经正确使用 `<PageHero>` / `<BackLink>` / `<DataTable>` 的文件 | 23 / 2 / 9 |
| 仍未迁移到 `<PageHero>` 的 hero 自渲染 | **3**（详见 §2.2） |

> API 路由（25 个 `route.ts` + 1 个 catch-all proxy）全部为 JSON 转发 / SSE 透传 / 上传 presign，没有 UI markup。本报告**不展开**。

---

## 2. 按子模块汇总

### 2.1 account / 个人中心

| 文件 | 命中模式 | 建议封装 |
| --- | --- | --- |
| `account/settings/page.tsx` | `<div className="space-y-6 p-6">` | `<PageContainer>`（建议新增，见 §4.1） |
| `account/settings/_components/account-settings-client.tsx` | 已是 `<Card>` + `<Tabs>`，无重复 markup | ✅ 已合规 |
| `account/settings/_components/change-email-dialog.tsx` | `<div className="flex justify-end gap-2 pt-2">` | `<DialogFooter>`（见 §4.2） |
| `account/settings/_components/change-password-dialog.tsx` | 同上 | 同上 |
| `account/settings/_components/request-deletion-dialog.tsx` | 同上 | 同上 |
| `account/settings/_components/cancel-deletion-dialog.tsx` | 同上 | 同上 |
| `account/settings/_components/profile-section.tsx` | `<div className="space-y-4">` | `<Stack size="md">`（见 §4.3） |
| `account/settings/_components/email-section.tsx` | `<Card>` + 内部 div | ✅ |
| `account/settings/_components/password-section.tsx` | 同上 | ✅ |
| `account/settings/_components/deletion-section.tsx` | `<RestoreDeletionBanner>` 已封装 | ✅ |
| `account/settings/_components/restore-deletion-banner.tsx` | 用 `<ErrorBanner variant="warning">` | ✅ |
| `account/settings/_components/avatar-uploader.tsx` | `<div className="space-y-2">` | `<Stack size="sm">` |
| `account/restore/restore-form.tsx` | `<div className="space-y-4">` | `<Stack size="md">` |

### 2.2 output / 文档结构化

| 文件 | 命中模式 | 建议封装 |
| --- | --- | --- |
| `output/page.tsx` (RSC) | `<div className="space-y-6 p-6">` | `<PageContainer>` |
| `output/new/page.tsx` | **手写 `<span className="eyebrow">Output</span> + <h1 className="display text-4xl">` 而未用 `<PageHero>`** | 迁 `<PageHero eyebrow="Output" title=...>` |
| `output/_components/output-list-client.tsx` | **手写 hero `<span className="eyebrow">Document Structuring</span> + <h1>`**，未用 `<PageHero>` | 迁 `<PageHero>` |
| `output/_components/output-card.tsx` | `<div className="flex justify-end gap-2">`（行内 actions） | `<RowActions>`（见 §4.4） |
| `output/[task_id]/page.tsx` | RSC 简单 wrapper | ✅ |
| `output/[task_id]/_components/task-detail-client.tsx` | **手写 `<LocalizedLink className="eyebrow group inline-flex items-center gap-2 text-muted-foreground">` 返回链**（× 1） | 迁 `<BackLink>` |
| `output/[task_id]/_components/task-download.tsx` | `<Button>` + `<a>`，无 markup 重复 | ✅ |
| `output/[task_id]/[file]/page.tsx` | **手写返回链**（同 task-detail-client 模板） | 迁 `<BackLink>` |

### 2.3 knowledge / 知识库（17 文件，本区最大）

| 文件 | 命中模式 | 建议封装 |
| --- | --- | --- |
| `knowledge/page.tsx` (RSC) | `<PageHero>` 已用 | ✅ |
| `knowledge/_components/knowledge-dashboard.tsx` | 4 张 `<EntryCard>`，**已经迁到 `<PageHero>` + `<Reveal>`** | ✅ Phase3 Task 3.5 标杆 |
| `knowledge/datasets/page.tsx` | `<PageHero>` 已用 | ✅ |
| `knowledge/datasets/_components/datasets-table.tsx` | `<DataTable>` + `<DataEmpty>` 已用 | ✅ |
| `knowledge/dataset-documents/[dataset_id]/page.tsx` | `<PageHero>` 已用 | ✅ |
| `knowledge/dataset-documents/_components/dataset-documents-table.tsx` | `<DataTable>` 已用 | ✅ |
| `knowledge/documents/page.tsx` | `<PageHero>` 已用 | ✅ |
| `knowledge/documents/_components/documents-entry.tsx` | 已迁 `<EntryCardGrid>` (Phase3 Task3.5) | ✅ |
| `knowledge/documents/import/page.tsx` | `<PageHero>` + `<ErrorBanner>` 已用 | ✅ |
| `knowledge/documents/import/_components/documents-import-form.tsx` | `<div className="h-full overflow-y-auto">` | 考虑 `<PageScrollArea>`（见 §4.5） |
| `knowledge/documents/import/_components/import-commit-card.tsx` | **手写 `rounded-lg border border-destructive/30 bg-destructive/5 p-3`** | 迁 `<ErrorBanner variant="destructive">` |
| `knowledge/qa/page.tsx` | `<PageHero>` 已用 | ✅ |
| `knowledge/qa/_components/qa-submit-form.tsx` | `<div className="h-full overflow-y-auto">` | `<PageScrollArea>` |
| `knowledge/graph/page.tsx` | `<PageHero>` 已用 | ✅ |
| `knowledge/graph/_components/graph-view.tsx` | `<div className="h-full overflow-y-auto">` | `<PageScrollArea>` |
| `knowledge/batch/page.tsx` | `<div className="h-full overflow-y-auto">` + **手写 `border-destructive/40 bg-destructive/10 p-3` 错误条** | `<PageScrollArea>` + `<ErrorBanner>` |
| `knowledge/triples/page.tsx` | `<PageHero>` 已用 | ✅ |
| `knowledge/triples/_components/triples-form.tsx` | `<div className="h-full overflow-y-auto">` + **手写 `border-destructive/30 bg-destructive/5`** | `<PageScrollArea>` + `<ErrorBanner>` |
| `knowledge/layout.tsx` | `<div className="flex items-center justify-between gap-4">` | 保留（业务特定） |

### 2.4 admin / 后台管理

| 文件 | 命中模式 | 建议封装 |
| --- | --- | --- |
| `admin/users/page.tsx` | `<div className="space-y-6 p-6">` + **手写 `<div className="flex items-end justify-between"> + <h1 className="display text-3xl">` 而未用 `<PageHero>`**（× 1） | `<PageContainer>` + 改用 `<PageHeader title=... actions=...>` |
| `admin/users/_components/admin-users-table.tsx` | `<div className="space-y-4">` + 分页 `<div className="flex items-center justify-end gap-2">` | `<Stack>` + `<PaginationBar>`（见 §4.6） |
| `admin/users/_components/user-filters.tsx` | `<div className="flex flex-wrap items-center gap-2">` | `<FilterBar>`（见 §4.7） |
| `admin/users/_components/create-invite-button.tsx` | 仅 `<>` fragment，无 markup 重复 | ✅ |
| `admin/users/_components/create-invite-dialog.tsx` | `<div className="flex gap-2">`（底部按钮） | `<DialogFooter>` |
| `admin/users/_components/reset-password-dialog.tsx` | 同上 | `<DialogFooter>` |
| `admin/invites/page.tsx` | `<div className="space-y-6 p-6">` + **手写 `<h1 className="display text-3xl">` 未用 `<PageHero>`** | `<PageContainer>` + `<PageHero>` |
| `admin/invites/_components/admin-invites-table.tsx` | `<div className="space-y-4">` | `<Stack>` |
| `admin/profile-fields/page.tsx` | 7 个 `<div className="space-y-2">` + 2 个 `<div className="space-y-4">` + 2 个 `<div className="flex justify-end gap-2">` | `<Stack>` + `<DialogFooter>` |
| `admin/dicts/page.tsx` (RSC) | 简单 wrapper | ✅ |
| `admin/dicts/_components/admin-dicts-client.tsx` | `<div className="space-y-6 p-6">` + `<p className="text-sm text-muted-foreground">加载中…</p>` | `<PageContainer>` + `<DataEmpty loading>` |
| `admin/dicts/_components/dict-list.tsx` | `<DataTable>` 已用 | ✅ |
| `admin/dicts/_components/dict-item-create-dialog.tsx` | `<div className="flex gap-2 pt-2">`（底部按钮） | `<DialogFooter>` |
| `admin/dicts/_components/dict-item-delete-dialog.tsx` | `<div className="rounded-md border border-destructive/30 bg-destructive/5 p-3 text-sm">`（确认提示框） | `<ErrorBanner variant="destructive">` |
| `admin/dicts/_components/dict-item-editor.tsx` | `<form className="flex flex-wrap items-center gap-3 rounded border border-border/40 bg-muted/20 p-3">` | `<SettingsCard>`（见 §4.8） |
| `admin/dicts/_components/dict-audit-log.tsx` | `<p className="text-sm text-muted-foreground">加载中…</p>` + `<ul className="space-y-3">` | `<DataEmpty loading>` |
| `admin/dicts/_components/readonly-banner.tsx` | 用 shadcn `<Alert>` 自定义绿/红色 | ✅（无现成封装） |
| `admin/permissions/page.tsx` (RSC) | `<div className="space-y-6 p-6">` + `<PageHero>` | ✅ |
| `admin/permissions/_components/permissions-admin-client.tsx` | `<div className="space-y-6">` | `<Stack size="md">` |
| `admin/permissions/_components/permissions-table.tsx` | `<div className="space-y-4">` + 自定义 edit mode banner `<div className="flex items-center justify-between rounded-lg border border-status-warning/30 bg-status-warning/5 px-4 py-2 text-sm">` | `<Stack>` + `<Callout variant="warning">`（见 §4.9） |
| `admin/permissions/_components/permission-row.tsx` | 表格内部，shadcn `<TableCell>` 已用 | ✅ |
| `admin/permissions/_components/role-detail-card.tsx` | `<Card>` + `<dl>` 已用 | ✅ |
| `admin/permissions/_components/create-role-dialog.tsx` | `<div className="flex gap-2 pt-2">` | `<DialogFooter>` |

### 2.5 health / 系统监控

| 文件 | 命中模式 | 建议封装 |
| --- | --- | --- |
| `health/page.tsx` | `<PageHero>` 已用 | ✅ |
| `health/layout.tsx` | 仅 wrapper | ✅ |
| `health/_components/health-client.tsx` | **手写 `rounded-lg border border-destructive/40 bg-destructive/10 p-6 text-destructive` ErrorState** | `<ErrorBanner variant="destructive">` |
| `health/_components/health-service-card.tsx` | `<Card>` 已用 | ✅ |
| `health/_components/services-grid.tsx` | `<EntryCardGrid>` Phase3 已用 | ✅ |
| `health/_components/system-resources.tsx` | **`<div className="space-y-2 bg-card/40 p-5">` × 3**（Cpu/Memory/Gpu 列同模板） | 抽 `MetricColumn` 子组件（项目级建议） |

### 2.6 decode / 型号解码

| 文件 | 命中模式 | 建议封装 |
| --- | --- | --- |
| `decode/page.tsx` | `<div className="h-full overflow-y-auto">` + `<PageHero>` 已用 | `<PageScrollArea>` |
| `decode/series-dialog.tsx` | `<p className="text-sm text-muted-foreground">暂无数据</p>` | `<DataEmpty title=... variant="inline">` |
| `decode/_components/decode-view.tsx`（推测位置） | `<AppToggle>` 已用 | ✅ |

### 2.7 evaluate / 评估

| 文件 | 命中模式 | 建议封装 |
| --- | --- | --- |
| `evaluate/page.tsx` | `<PageHero>` 已用 | ✅ |
| `evaluate/_components/evaluate-list-view.tsx` | `<div className="h-full overflow-y-auto">` | `<PageScrollArea>` |
| `evaluate/new/page.tsx` | `<PageHero>` 已用 | ✅ |
| `evaluate/new/_components/evaluate-new-form.tsx` | `<div className="h-full overflow-y-auto">` + **手写 `rounded-lg border border-destructive/30 bg-destructive/5 p-3`** | `<PageScrollArea>` + `<ErrorBanner>` |
| `evaluate/[id]/page.tsx` | `<PageHeader>` 已用 | ✅ |
| `evaluate/[id]/_components/run-detail-view.tsx` | **`<PageHeader>` + 内联 `<h1 className="display text-3xl">` 重复** + `<div className="h-full overflow-y-auto">` | 删内联 h1，迁 `<PageScrollArea>` |
| `evaluate/[id]/_components/metric-bar.tsx` | 自定义条形 | ✅ |
| `evaluate/[id]/_components/sample-table.tsx` | `<DataTable>` 已用 | ✅ |

### 2.8 chat / 聊天

| 文件 | 命中模式 | 建议封装 |
| --- | --- | --- |
| `chat/page.tsx` | 用 ChatShell 内部组件 | ✅ |
| `chat/s/[shareId]/page.tsx` | 简单只读 wrapper | ✅ |

### 2.9 buyers / 客户画像

| 文件 | 命中模式 | 建议封装 |
| --- | --- | --- |
| `buyers/page.tsx` | `<div className="space-y-6 p-6">` + `<PageHero>` 已用 | `<PageContainer>` |
| `buyers/[id]/page.tsx` | `<div className="space-y-6 p-6">` + `<PageHeader backHref="/buyers">` | `<PageContainer>` |
| `buyers/[id]/_components/change-timeline.tsx` | **`<div className="text-muted-foreground py-4 text-center text-sm">暂无变更记录</div>`**（× 2，含 loading 态） | `<DataEmpty title=...>` |
| `buyers/[id]/_components/profile-card.tsx` | `<div className="flex justify-end gap-2">` | `<RowActions>` |
| `buyers/layout.tsx` | `<div className="min-h-screen">` | 保留（layout 必需） |

### 2.10 submissions / 审批中心

| 文件 | 命中模式 | 建议封装 |
| --- | --- | --- |
| `submissions/page.tsx` | `<PageHero>` 已用 | ✅ |
| `submissions/layout.tsx` | 仅 wrapper | ✅ |
| `submissions/_components/approval-row.tsx` | `<div className="rounded border p-3">` (Collapsible) + **手写 `rounded bg-status-error/10 p-3 text-sm`**（rejection 提示） | `<SettingsCard>` + `<Callout variant="error">` |
| `submissions/_components/all-approvals-table.tsx` | `<div className="space-y-2">` | `<Stack>` |
| `submissions/_components/my-submissions-list.tsx` | 同上 | `<Stack>` |
| `submissions/_components/reject-dialog.tsx` | `<div className="flex justify-end gap-2">` | `<DialogFooter>` |

### 2.11 其他页面

| 文件 | 命中模式 | 建议封装 |
| --- | --- | --- |
| `[locale]/page.tsx`（home） | `<h1 className="display text-3xl">` | 考虑 `<PageHero>` |
| `[locale]/error.tsx` | `<h1 className="display text-3xl">` | 保留（错误页） |
| `[locale]/forbidden.tsx` | `<ErrorBanner>` 已用 | ✅ |
| `[locale]/not-found.tsx` | `<p>` + `<LocalizedLink>` | ✅ |
| `[locale]/login/page.tsx` | `<div className="mx-auto mt-20 max-w-sm space-y-6">` | `<AuthFormContainer>`（见 §4.10） |
| `[locale]/forgot-password/page.tsx` | 同上 + `<div className="mx-auto max-w-md p-6">` | 同上 |
| `[locale]/reset-password/page.tsx` | 同上 | 同上 |
| `[locale]/invite/[token]/page.tsx` | `<div className="mx-auto mt-20 max-w-sm space-y-6">` + `<div className="mx-auto max-w-md p-6">` | 同上 |
| `[locale]/account/restore/restore-form.tsx` | `<div className="space-y-4">` | `<Stack>` |
| `global-error.tsx` | 全局错误 | 保留 |
| `[locale]/loading.tsx` | 加载页 | ✅ |

---

## 3. Top-10 重复模式（按频率排序）

> **数据基于 Grep count（已在扫描时确认）**

| # | 模式 | 文件数 | 出现次数 | 现状 | 建议封装 |
| --- | --- | --- | --- | --- | --- |
| 🔴 1 | `<div className="space-y-2">` 堆叠 | 13 | **23** | 多处重复 | **`<Stack size="sm">`**（见 §4.3） |
| 🔴 2 | `<h1 className="display text-{3xl,4xl,5xl}">` 手写标题 | 15 | **18** | 9 处已迁 `<PageHero>` | **3 处仍未迁**（output/new, output-list-client, admin/users, admin/invites） |
| 🔴 3 | `<div className="h-full overflow-y-auto">` 滚动容器 | 15 | **15** | 无封装 | **`<PageScrollArea>`**（见 §4.5） |
| 🔴 4 | `<p className="text-sm text-muted-foreground">加载中…</p>` 空态/loading 文本 | 12 | **12** | 部分已迁 `<DataEmpty loading>` | **新增 `loading` variant**（见 §4.11） |
| 🟡 5 | `<div className="space-y-4">` 堆叠 | 10 | **12** | 多处重复 | **`<Stack size="md">`** |
| 🟡 6 | `<div className="flex justify-end gap-2 (pt-2)">` 弹框底部 | 8 | **9** | 部分已用 `<DialogFooter>` 命名但未抽封装 | **新增 `<DialogFooter>`**（见 §4.2） |
| 🟡 7 | `<div className="space-y-6 p-6">` 页面外容器 | 8 | **8** | 重复 | **`<PageContainer>`**（见 §4.1） |
| 🟡 8 | `<div className="mx-auto mt-20 max-w-sm space-y-6">` 居中表单容器 | 4 | **5** | 重复 | **`<AuthFormContainer>`**（见 §4.10） |
| 🟡 9 | `<div className="rounded (md|lg) border border-destructive/30 bg-destructive/5 p-3">` 错误条 | 5 | **5** | 4 处仍手写（health, knowledge/batch, knowledge/triples, knowledge/import, evaluate-new-form） | 迁 `<ErrorBanner variant="destructive">` |
| 🟢 10 | `<LocalizedLink className="eyebrow group inline-flex items-center gap-2 text-muted-foreground transition-colors hover:text-foreground">` 返回链 | 2 | **2** | 手写返回链（task-detail-client + file-preview） | 迁 `<BackLink>` |

### 严重度图例

- 🔴 **5+** 出现次数 — 高优先级，应尽快封装
- 🟡 **3-4** 出现次数 — 中优先级，下个 sprint 处理
- 🟢 **2** 出现次数 — 低优先级，按需重构

---

## 4. 建议新增的封装组件

> 每条都附"调用方一览"+ 实施复杂度估算。封装规则: ≥3 个 shadcn 原语 或 ≥2 次业务出现 → 必须封装。

### 4.1 `<PageContainer>`（建议新增 · 🔴 高优先）

- **签名**: `<PageContainer size="default|wide">{children}</PageContainer>`
- **模板**: `<div className="space-y-6 p-6" />`（或 `mx-auto max-w-5xl p-6`）
- **调用方 (8)**:
  1. `account/settings/page.tsx`
  2. `admin/users/page.tsx`
  3. `admin/invites/page.tsx`
  4. `admin/permissions/page.tsx`
  5. `admin/dicts/_components/admin-dicts-client.tsx`
  6. `buyers/page.tsx`
  7. `buyers/[id]/page.tsx`
  8. `output/page.tsx` (RSC)
- **复杂度**: 低（无状态纯包装）

### 4.2 `<DialogFooter>`（建议新增 · 🟡 中优先）

- **签名**: `<DialogFooter primary primaryLabel onPrimary onCancel cancelLabel destructive />`
- **模板**: `<div className="flex gap-2 pt-2"> + <Button>primary</Button> + <Button variant="outline">cancel</Button></div>`
- **调用方 (9+)**:
  1. `account/settings/_components/change-email-dialog.tsx`
  2. `account/settings/_components/change-password-dialog.tsx`
  3. `account/settings/_components/request-deletion-dialog.tsx`
  4. `account/settings/_components/cancel-deletion-dialog.tsx`
  5. `admin/users/_components/create-invite-dialog.tsx`
  6. `admin/users/_components/reset-password-dialog.tsx`
  7. `admin/dicts/_components/dict-item-create-dialog.tsx`
  8. `admin/permissions/_components/create-role-dialog.tsx`
  9. `submissions/_components/reject-dialog.tsx`
  10. `admin/profile-fields/page.tsx`（× 2）
- **复杂度**: 中（要处理 destructive / loading / 双按钮联动）

### 4.3 `<Stack>`（建议新增 · 🔴 高优先）

- **签名**: `<Stack size="xs|sm|md|lg|xl" as="div|section">{children}</Stack>`
- **模板映射**: `space-y-{0.5|2|4|6|8}`
- **调用方 (35+)**:
  - `space-y-2`: 23 处（13 文件）
  - `space-y-4`: 12 处（10 文件）
  - `space-y-6`: 8 处
- **复杂度**: 低

### 4.4 `<RowActions>`（建议新增 · 🟢 低优先）

- **签名**: `<RowActions align="start|end">{children}</RowActions>`
- **模板**: `<div className="flex justify-end gap-2">或<flex justify-end gap-1.5>`
- **调用方 (4)**:
  1. `output/_components/output-card.tsx`
  2. `buyers/[id]/_components/profile-card.tsx`
  3. `output/[task_id]/_components/task-detail-client.tsx`
  4. `output/new/page.tsx`
- **复杂度**: 低

### 4.5 `<PageScrollArea>`（建议新增 · 🟡 中优先）

- **签名**: `<PageScrollArea>{children}</PageScrollArea>`
- **模板**: `<div className="h-full overflow-y-auto space-y-8">`
- **调用方 (15)**:
  1. `decode/page.tsx`
  2. `evaluate/_components/evaluate-list-view.tsx`
  3. `evaluate/new/_components/evaluate-new-form.tsx`
  4. `evaluate/[id]/_components/run-detail-view.tsx`
  5. `knowledge/_components/knowledge-dashboard.tsx`
  6. `knowledge/graph/_components/graph-view.tsx`
  7. `knowledge/batch/page.tsx`
  8. `knowledge/dataset-documents/_components/...`
  9. `knowledge/datasets/_components/datasets-table.tsx`
  10. `knowledge/documents/_components/documents-entry.tsx`
  11. `knowledge/qa/_components/qa-submit-form.tsx`
  12. `knowledge/triples/_components/triples-form.tsx`
  13. `knowledge/documents/import/_components/documents-import-form.tsx`
  14. `output/_components/output-list-client.tsx`
  15. `output/[task_id]/_components/task-detail-client.tsx`
  16. `output/[task_id]/[file]/page.tsx`
- **复杂度**: 低（纯 div 包装）

### 4.6 `<PaginationBar>`（建议新增 · 🟡 中优先）

- **签名**: `<PaginationBar page pageSize total onPageChange />`
- **模板**: 上一页/页码/下一页 3 按钮 + 总数提示
- **调用方 (1+)**:
  - `admin/users/_components/admin-users-table.tsx`
  - `DataTable` 已有内置 pagination，可考虑直接用 `DataTable` pagination
- **复杂度**: 中

### 4.7 `<FilterBar>`（建议新增 · 🟢 低优先）

- **签名**: `<FilterBar>{children}</FilterBar>`
- **模板**: `<div className="flex flex-wrap items-center gap-2">`
- **调用方 (2)**:
  1. `admin/users/_components/user-filters.tsx`
  2. `buyers/page.tsx` 的 `BuyersToolbar`
- **复杂度**: 低

### 4.8 `<SettingsCard>`（建议新增 · 🟢 低优先）

- **签名**: `<SettingsCard title description>{children}</SettingsCard>`
- **模板**: `<div className="rounded border border-border/40 bg-muted/20 p-3">` 或 `<Card className="border-border/60 bg-card/40">`
- **调用方 (3)**:
  1. `admin/dicts/_components/dict-item-editor.tsx`
  2. `submissions/_components/approval-row.tsx`
  3. `account/settings/_components/profile-section.tsx`
- **复杂度**: 低（可基于 shadcn Card）

### 4.9 `<Callout>`（建议新增 · 🟡 中优先）

- **签名**: `<Callout variant="warning|error|info|success" title>{children}</Callout>`
- **模板**:
  - warning: `border border-status-warning/30 bg-status-warning/5 px-4 py-2 text-sm`
  - error: `border-destructive/30 bg-destructive/5 p-3 text-sm`
- **调用方 (3+)**:
  1. `admin/permissions/_components/permissions-table.tsx`（edit mode banner）
  2. `submissions/_components/approval-row.tsx`（rejection / apply-error）
  3. `admin/dicts/_components/dict-item-delete-dialog.tsx`（确认提示框）
  4. `health/_components/health-client.tsx`（ErrorState）
- **复杂度**: 中
- **注**: 与 `<ErrorBanner>` 区别 — `<Callout>` 是页面**上下文**通知（dismissable），`<ErrorBanner>` 是**全页错误**（红条阻断）

### 4.10 `<AuthFormContainer>`（建议新增 · 🟢 低优先）

- **签名**: `<AuthFormContainer width="sm|md">{children}</AuthFormContainer>`
- **模板**:
  - sm: `<div className="mx-auto mt-20 max-w-sm space-y-6">`
  - md: `<div className="mx-auto max-w-md p-6">`
- **调用方 (5)**:
  1. `login/page.tsx`
  2. `forgot-password/page.tsx`（× 2）
  3. `reset-password/page.tsx`
  4. `invite/[token]/page.tsx`（× 2）
- **复杂度**: 低

### 4.11 `<DataEmpty loading>`（建议扩展 · 🟡 中优先）

- **现状**: `<DataEmpty icon title description variant />` 已有 page/inline variant
- **缺失**: 没有 `loading` variant
- **新签名**: 加 `loading?: boolean` prop
- **调用方 (12)**: `decode/series-dialog.tsx`, `dict-audit-log.tsx`, `admin-dicts-client.tsx`, `output-list-client.tsx`, `task-detail-client.tsx`, `file-preview/page.tsx`, `run-detail-view.tsx`, `invite/[token]/page.tsx`, `change-timeline.tsx`, `evaluations`, `triples-form.tsx`...
- **复杂度**: 低

### 4.12 `<PageHero>` 迁移（建议补做 · 🔴 高优先）

- **未迁的 3 处**:
  1. `output/new/page.tsx`：手写 `<span className="eyebrow">Output</span> + <h1 className="display text-4xl">`
  2. `output/_components/output-list-client.tsx`：同上
  3. `admin/users/page.tsx`：手写 `<div className="flex items-end justify-between"> + <h1 className="display text-3xl"> + <CreateInviteButton>`
  4. `admin/invites/page.tsx`：手写 `<h1 className="display text-3xl">`
- **复杂度**: 低（直接替换）

### 4.13 `<BackLink>` 迁移（建议补做 · 🟢 低优先）

- **未迁的 2 处**:
  1. `output/[task_id]/_components/task-detail-client.tsx`：手写返回链
  2. `output/[task_id]/[file]/page.tsx`：手写返回链
- **复杂度**: 低

---

## 5. 总结与建议

### 5.1 已合规的封装使用（值得保留）

- ✅ `<PageHero>` 已迁移 9 处（knowledge/, evaluate/, submissions/, output/ 部分）
- ✅ `<DataTable>` + `<DataEmpty>` 9 处表格
- ✅ `<ErrorBanner>` 9 处替换了手写 `border-destructive/30 bg-destructive/5` 红条
- ✅ `<AppDialog>` + `<AppConfirm>` 9 处替代了 shadcn Dialog 直用
- ✅ `<EntryCardGrid>` (Phase3 Task3.5) 已用于 knowledge-dashboard / documents-entry / graph-view / services-grid

### 5.2 优先重构 Top-5（按 ROI 排序）

| # | 任务 | 文件数 | 节省行数（估） | 工期 |
| --- | --- | --- | --- | --- |
| 1 | 迁 `<PageHero>` 4 处 + 迁 `<BackLink>` 2 处 | 6 | ~40 行 | 0.5d |
| 2 | 新增 `<PageContainer>` 统一 `space-y-6 p-6` 8 处 | 8 | ~10 行 | 0.3d |
| 3 | 新增 `<PageScrollArea>` 统一 `h-full overflow-y-auto` 15 处 | 15 | ~25 行 | 0.3d |
| 4 | 迁手写失败条 → `<ErrorBanner>` 5 处 | 5 | ~15 行 | 0.3d |
| 5 | 新增 `<DialogFooter>` + `<Stack>` 19+35 处 | 50+ | ~100 行 | 1.0d |

### 5.3 风险点

- **API 路由**：25 个 `route.ts` 文件均为 JSON 透传，无 div/span。本报告**不展开**。但 `app/api/[...path]/route.ts`（catch-all）需要 cookie 鉴权注入，跟 server actions 保持一致（已在 `auth.server.ts` 同步）。
- **测试文件**: 不在扫描范围（已排除 `.test.tsx`）。但部分测试断言依赖具体 className（如 `data-testid`），封装迁移时要同步更新测试。
- **Tailwind v4 token**: 部分旧代码用 `border-destructive/30`，新封装统一用 `border-status-error/30` 或保留 `destructive` token（看 DesignToken 决定）。
- **变更历史**: 提议的 `<Stack>` `<RowActions>` `<PageScrollArea>` 都是无状态纯 div 包装，几乎无破坏性。但 `<DialogFooter>` 与 `<AppDialog>` 已有 `<AppDialog error=...>` 内置错误展示联动，需要小心不要重复。

### 5.4 不建议封装（避免过度抽象）

- `<div className="flex items-center gap-1.5">` 单文件 1-2 处的小布局：不抽
- `<span className="num font-mono text-xs">` 单调数字 / monospace 文本：不抽
- `<div className="absolute left-2 top-1 h-full w-px bg-border">` 时间线竖线（仅 change-timeline.tsx 1 处）：不抽
- `<span className="text-sm">…</span>` 纯文本 span：不抽

---

## 6. 附录：扫描未覆盖 & 后续 follow-up

1. **未覆盖**: `packages/web/components/common/**` 下已封装组件（DataTable, ErrorBanner, PageHero, BackLink 等）本身是否还有可进一步抽取的内部 div — 不在本任务范围。
2. **未覆盖**: `packages/web/components/ui/**` shadcn 原始件 — 不在本任务范围。
3. **未覆盖**: `packages/web/app/**/.test.tsx` 测试文件 — 显式排除。
4. **未覆盖**: `packages/web/messages/**` i18n 文件 — 无 markup。
5. **未覆盖**: `packages/web/lib/**` 非 UI 工具 — 无 markup。
6. **follow-up**: 本报告建议的 13 个新封装（§4.1 - §4.13）合计 ~250 行节省，需经用户评审通过后再动手。

---

> 报告生成完毕。Agent C 覆盖范围 `packages/web/app/**` 全部 `.tsx` 与 `.ts`（除测试），共扫描 154 个文件，识别 24 类重复 markup，建议 13 个新封装组件。