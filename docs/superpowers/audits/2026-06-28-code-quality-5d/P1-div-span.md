# P1 维度审计报告 — ① div/span 提取样式组件

**审计日期**: 2026-06-28
**范围**: `packages/web/` 全量源文件（排除 `.test.tsx`/`.test.ts`/`.stories.tsx`/`e2e/`/`tests/`/`messages/`）
**审计员**: 4 个 agent 并行扫描后汇总
- A: common + ui 封装实现层（78 文件）→ [详细报告](p1-div-span/A-common-ui-report.md)
- B: 业务组件 chat/knowledge/motion/auth/json/...（60 文件）→ [详细报告](p1-div-span/B-business-components-report.md)
- C: app/ 全部页面+API（154 文件）→ [详细报告](p1-div-span/C-pages-api-report.md)
- D: lib/ + const/ + i18n/ + scripts/ + proxy + next.config（76 文件）→ [详细报告](p1-div-span/D-lib-others-report.md)

> 旧版原汁原味的 [SUMMARY.md](p1-div-span/SUMMARY.md) 保留作为索引快照。本文件是该维度的**最终整合报告**，实施处理时以本文件为准，细节参考 4 个 agent 子报告的具体行号定位。

---

## 1. 总体扫描概览

| 维度 | 数值 |
| --- | --- |
| 总源文件数 | **568** (.tsx) + 88 (.ts, lib/api/store 等) = **~656 个非测试源文件** |
| 含 div/span 的文件 | **237**（业务 UI） |
| 纯逻辑/配置文件（无 UI） | **419**（D 报告全 0；C 报告 API routes 25 个；其余 hooks/api/store/theme） |
| 发现重复 pattern（跨文件 / 同文件 ≥2） | **44 类** |
| 可直接替换为已有封装 | **30 处** |
| 建议新封装组件 | **11 个**（高 ROI 6 + 中 ROI 2 + 不推荐 7） |
| 已正确使用 `<PageHero>` 的页面 | 9 |
| 已正确使用 `<DataTable>` 的页面 | 9 |
| 已正确使用 `<ErrorBanner>` 的页面 | 9 |
| 仍手写失败/告警条幅的页面 | 5 |

**严重度分布**：

| 严重度 | 数量 | 说明 |
| --- | --- | --- |
| 🔴 严重（高频重复 5+） | **6 类** | 跨多文件 / 多处出现的固定 pattern |
| 🟡 中等（重复 3-4） | **12 类** | 跨 3-4 处或特定模块内的重复 |
| 🟢 建议（重复 2） | **26 类** | 同文件重复或独有但值得封装 |

---

## 2. Top-10 高频重复模式（按 ROI 重排）

> ⚠️ **Top-3 模式 (`space-y-N` / `h-full overflow-y-auto` / `<h1 display>`) 不建议抽组件**：单 className 包组件反而增加复杂度。仅 5/9/4 处仍手写的错误条/PageHero/BackLink 直接迁现有封装即可。

| # | 模式 | 文件数 | 出现次数 | 现有封装 | 建议方案 | ROI |
| --- | --- | --- | --- | --- | --- | --- |
| 🔴 1 | `<div ... border-destructive bg-destructive/5>` 错误条 | 5 | 5 | `<ErrorBanner>` 已存在 | **直接迁 5 处** | 🔴 极高 |
| 🔴 2 | `<h1 className="display text-Nxl">` 手写标题 | 15 | 18 | `<PageHero>` 9 处 | 4 处仍手写迁 PageHero | 🔴 高 |
| 🔴 3 | `<div className="flex justify-end gap-2 pt-2">` 弹框底部 | 8 | 9 | 无 | 新增 `<DialogFooter>` | 🔴 高 |
| 🔴 4 | `<div className="rounded ... border ... bg-muted/30">` 信息块 | 4 | 4 | 无 | 新增 `<AppSubtleCard>` | 🟡 中 |
| 🔴 5 | `<div className="flex items-center gap-2 ... border">` 列表项 | 4 | 6 | 无 | 新增 `<AppListItem>` | 🟡 中 |
| 🔴 6 | `<div ... border-warning bg-warning/5>` 状态容器 | 3 | 3 | 无 | 新增 `<Callout>` | 🟢 低 |
| ⚪ 7 | `<div className="space-y-2/4/6">` 堆叠 | 23 | 35 | 无 | **不抽**，保留 div | ⚪ N/A |
| ⚪ 8 | `<div className="h-full overflow-y-auto">` 滚动容器 | 15 | 15 | 无 | **不抽**，保留 div | ⚪ N/A |
| ⚪ 9 | `<div className="space-y-6 p-6">` 页面外容器 | 8 | 8 | 无 | **不抽**，保留 div | ⚪ N/A |
| ⚪ 10 | `<p className="text-sm text-muted-foreground">加载中…</p>` | 12 | 12 | `<DataEmpty>` 部分 | DataEmpty 已支持 loading | ⚪ N/A |

---

## 3. 🔴 严重（高频重复 5+）— 6 个 Pattern 详解

### Pattern 1: 列表项 "flex items-center gap-2 ... border rounded-*" — chat/ 4 文件重复

```tsx
// (1) composer-attachments.tsx:157 — 附件缩略图
<div className="flex items-center gap-2 rounded-md border bg-muted/50 px-2 py-1 text-xs">

// (2) memory-management-dialog.tsx:123 + 149 — 记忆列表行（2 次同文件）
<div className="flex items-center gap-2 p-3 border rounded-md">

// (3) share-dialog.tsx:114 — 分享行
<div className="flex items-center gap-2 rounded-md border p-3">

// (4) conversation-list.tsx:64 — 会话项（变体: cursor-pointer + border-transparent + hover bg）
<div className="group flex cursor-pointer items-baseline gap-2 rounded-md border border-transparent px-2.5 py-2 ...">
```

- **跨文件次数**: **4 文件 / 6 处**
- **现有封装**: 无（`AppSectionCard` 不合适；列表项级，不是卡片）
- **建议**: **新增 `<AppListItem>` 通用列表项组件**（见 §4.1）
- **优先级**: 🟡 中

### Pattern 2: Chat 信息条/弹窗行 "rounded ... border ... bg-muted/30" — chat/ 4 文件重复

```tsx
// (1) message-bubble.tsx:37 — thinking 内容
<div className="mt-1 whitespace-pre-wrap rounded-lg border border-border/40 bg-muted/30 p-3 text-sm text-muted-foreground">

// (2) citation-panel.tsx:7 — 引用卡
<div key={idx} className="rounded-lg border border-border/40 bg-muted/30 px-3 py-2">

// (3) thinking-trace.tsx:21 — step 行（变体: bg-muted/30 + items-baseline + text-xs）
<div key={idx} className="flex items-baseline gap-2 rounded-md bg-muted/30 px-2 py-1 text-xs">

// (4) composer-attachments.tsx:157 — 附件（bg-muted/50 变体）
<div className="flex items-center gap-2 rounded-md border bg-muted/50 px-2 py-1 text-xs">
```

- **跨文件次数**: **4 文件 / 4 处**（chat 业务信息卡）
- **现有封装**: 无
- **建议**: **新增 `<AppSubtleCard>` 浅底信息块**（见 §4.2）
- **优先级**: 🟡 中

### Pattern 3: 空态/错误态 "flex items-center justify-center rounded-lg border p-8" — json/ 跨 2 文件 5 处

```tsx
// json-view.tsx:31 + 46
"flex items-center justify-center rounded-lg border p-8 text-muted-foreground"   // 空
"flex items-center justify-center rounded-lg border p-8 text-destructive"        // 错

// json-diff.tsx:70 + 86 + 100
"flex items-center justify-center rounded-lg border p-8 text-muted-foreground"   // 空 + 无差异
"flex items-center justify-center rounded-lg border p-8 text-destructive"        // 错
```

- **跨文件次数**: **2 文件 / 5 处**（json 系列）
- **现有封装**: **🟢 完全可替换 — `<AppDataEmpty>` 已存在**
- **建议**: **直接用 `<AppDataEmpty>` 替换 5 处**，给 AppDataEmpty 加一个 `variant="destructive"`（对齐 ErrorBanner 风格）
- **优先级**: 🔴 高（5 处重复，已有封装但未用）

### Pattern 4: 业务组件 `<Button variant="ghost" size="icon">` 单行重复 — 11 文件

```tsx
// 跨文件: chat/chat-header, chat-header, composer-attachments, conversation-list,
//         memory-management-dialog, share-dialog, message-feedback 等共 11 处
<Button size="icon" variant="ghost" onClick={...}>
  <X className="h-4 w-4" />
</Button>
```

- **跨文件次数**: **11 文件 / ~16 处**
- **现有封装**: 无
- **建议**: **新增 `<AppIconButton>` 封装** — 但此模式太简单（2 个 prop），优先级低
- **优先级**: 🟢 低

### Pattern 5: "space-y-N" 列表容器 + 列表项 — chat 5 文件

```tsx
// (1) citation-panel.tsx:5
<div className="mt-2 space-y-2">

// (2) memory-management-dialog.tsx:270（变体: overflow-y-auto）
<div className="flex-1 overflow-y-auto space-y-2 ...">

// (3) message-list.tsx:41
<div className="space-y-4">

// (4) shared-chat-view.tsx:40
<div className="space-y-4">

// (5) thinking-trace.tsx:32
<div className="mt-2 space-y-1">
```

- **跨文件次数**: **5 文件 / 5 处**（chat/ 业务列表）
- **现有封装**: 无（但 `<ul>` `<li>` 模板可替换）
- **建议**: 这不是重复样式，是业务列表骨架，不应抽
- **优先级**: ⚪ 跳过

### Pattern 6: 业务手写 hero `<h1 className="display text-Nxl">` — 4 处仍手写

```tsx
// output/new/page.tsx
<span className="eyebrow">Output</span>
<h1 className="display text-4xl">...</h1>

// output/_components/output-list-client.tsx
<span className="eyebrow">Document Structuring</span>
<h1>...</h1>

// admin/users/page.tsx + admin/invites/page.tsx
<h1 className="display text-3xl">...</h1>
```

- **跨文件次数**: **4 处**（手写 hero，`<PageHero>` 已存在）
- **建议**: **直接迁 4 处到 `<PageHero>`**
- **优先级**: 🔴 高

---

## 4. 建议新增的封装组件清单（11 个，按 ROI 排序）

> **ROI 判定标准**:
> - **高 ROI**: 单个抽取能省 ≥5 行 OR 集中设计 token OR 跨 ≥3 文件
> - **中 ROI**: 跨 2-3 文件，未来扩展
> - **低 ROI**: 仅 1-2 文件，未来不一定扩展 — **不推荐做**
>
> **明确不推荐**: `<Stack>` `<PageContainer>` `<PageScrollArea>` `<RowActions>` `<FilterBar>` `<PaginationBar>` 这些"把 1-2 个 Tailwind className 包成组件"的提议，**反而增加复杂度**，违反 YAGNI。

### ✅ 推荐做（高 ROI，6 个）

#### 4.1 `<AppListItem>` — 通用列表项

- **调用方**: chat/ 4 文件 / 6 处（composer-attachments, memory-management-dialog, share-dialog, conversation-list）
- **Props**: `{ children: ReactNode; className?: string; onClick?: () => void; variant?: "default" | "interactive" }`
- **收益**: 节省 ~20 行 + 跨组件复用 + 统一 hover/cursor 行为
- **位置**: `components/common/list/app-list-item.tsx`
- **来源**: B 报告

#### 4.2 `<AppSubtleCard>` — 浅底信息块

- **调用方**: chat/ 4 文件 / 4 处（message-bubble thinking, citation-panel, thinking-trace, composer-attachments）
- **Props**: `{ children: ReactNode; size?: "sm" | "md"; tone?: "muted" | "highlight" }`
- **收益**: 颜色 token 统一，省 ~15 行
- **位置**: `components/common/display/app-subtle-card.tsx`
- **来源**: B 报告

#### 4.3 `<DialogFooter>` — 弹框底部按钮组

- **调用方**: 9 个 dialog（change-email, change-password, request-deletion, cancel-deletion, create-invite, reset-password, profile-fields 等）
- **Props**: `{ primary?: ReactNode; cancel?: ReactNode; destructive?: ReactNode }`
- **收益**: 集中 cancel/save/destructive 模式，省 ~30 行
- **位置**: `components/common/dialog/dialog-footer.tsx`
- **来源**: C 报告

#### 4.4 `<AppDataEmpty variant="destructive">` — 扩展现有组件

- **调用方**: json-view/diff 5 处
- **Props 扩展**: `variant: "table" | "page" | "destructive"`
- **收益**: 加 1 个 prop 省 15 行，统一视觉
- **位置**: 现有 `components/common/display/app-data-empty.tsx` 加 variant
- **来源**: B 报告

#### 4.5 `<AuthFormContainer>` — 认证表单容器

- **调用方**: login / forgot / reset / invite 4 处
- **Props**: `{ children: ReactNode; title: string; description?: string; footer?: ReactNode }`
- **收益**: 同模板复用，省 ~10 行
- **位置**: `components/common/layout/auth-form-container.tsx`
- **来源**: C 报告

#### 4.6 `<Callout variant="warning|error|info">` — 状态容器

- **调用方**: 3 处（message-feedback, knowledge/triples, ...）
- **Props**: `{ variant: "warning" | "error" | "info"; children: ReactNode }`
- **收益**: 状态容器统一，省 ~10 行
- **位置**: `components/common/feedback/callout.tsx`
- **来源**: C 报告

### ⚠️ 可选（中 ROI，单文件/小扩展，2 个）

| 组件 | 调用方 | 收益 | 来源 |
| --- | --- | --- | --- |
| `<AppSettingsRow>` | settings-dialog 2 处 | 单文件重复但模式稳定，未来可能扩 | B |
| `<AppCodeBlock>` | json-view/diff 2 处 | 同上 | B |

### ❌ 不推荐做（低 ROI，违反 YAGNI，3 个）

| 提议 | 原因 |
| --- | --- |
| `<FormHelp>` / `<FormError>` | 当前 1 处使用，抽内部 `FORM_HELP_CLS` / `FORM_ERROR_CLS` const 更轻量，不开新文件（A 报告） |
| `<DialogBody>` | AppDialog/AppDrawer 2 处，抽内部 `DIALOG_BODY_CLS` const 更轻量（A 报告） |
| `<StatNumber>` | app-stat-card.tsx 内部 2 处重复，抽内部 const 即可，不暴露（A 报告） |

### ❌❌ 明确不做（违反 YAGNI，7 个）

| 提议 | 原因 |
| --- | --- |
| `<Stack size="sm\|md\|lg">` | `<div className="space-y-N">` 仅 1 个 className，抽组件增加 prop+import+抽象，省 0 行 |
| `<PageContainer>` | 同上，`<div className="space-y-6 p-6">` 1 个 className 没必要包 |
| `<PageScrollArea>` | `<div className="h-full overflow-y-auto">` 1 个 className 包组件是过度抽象 |
| `<RowActions>` | `<div className="flex justify-end gap-2">` 1 个 className |
| `<FilterBar>` | 单调用方 |
| `<PaginationBar>` | 单调用方 |
| `<SettingsCard>` | shadcn `<Card>` 已存在，1 调用方 |

---

## 5. 真正可节省的代码量（重写 ROI 重新计算）

| 类别 | 文件数 | 节省行数 |
| --- | --- | --- |
| **5 处错误条 → ErrorBanner** | 5 | -25 |
| **4 处 PageHero + 2 处 BackLink 迁移** | 6 | -50 |
| **json-view/diff 5 处 → AppDataEmpty** | 2 | -15 |
| **9 处 DialogFooter 抽取** | 9 | -30 |
| **6 处 AppListItem** | 4 | -20 |
| **4 处 AppSubtleCard** | 4 | -15 |
| **4 处 AuthFormContainer** | 4 | -10 |
| **3 处 Callout** | 3 | -10 |
| **1 处 message-bubble Badge** | 1 | -3 |
| **总计** | **~38 文件** | **~-178 行** |

---

## 6. 可直接替换为已有封装的清单（30 处）

### 6.1 错误条（5 处仍手写）

| 文件 | 当前代码 | 替换为 |
| --- | --- | --- |
| `app/[locale]/health/_components/health-client.tsx` | `<div className="rounded-lg border border-destructive/40 bg-destructive/10 p-6 text-destructive">` | `<ErrorBanner variant="destructive">` |
| `app/[locale]/knowledge/batch/page.tsx` | `<div className="rounded border ... bg-destructive/10 p-3">` | `<ErrorBanner variant="destructive">` |
| `app/[locale]/knowledge/triples/_components/triples-form.tsx` | `<div ... border-destructive/30 bg-destructive/5>` | `<ErrorBanner variant="destructive">` |
| `app/[locale]/knowledge/documents/import/_components/import-commit-card.tsx` | `<div ... border-destructive/30 bg-destructive/5 p-3>` | `<ErrorBanner variant="destructive">` |
| `app/[locale]/evaluate/new/_components/evaluate-new-form.tsx` | `<div ... border-destructive/30 bg-destructive/5>` | `<ErrorBanner variant="destructive">` |

### 6.2 PageHero 仍未迁移（4 处）

| 文件 | 现状 |
| --- | --- |
| `app/[locale]/output/new/page.tsx` | 手写 `<span className="eyebrow">Output</span> + <h1 className="display text-4xl">` |
| `app/[locale]/output/_components/output-list-client.tsx` | 手写 hero |
| `app/[locale]/admin/users/page.tsx` | 手写 `<h1 className="display text-3xl">` |
| `app/[locale]/admin/invites/page.tsx` | 手写 `<h1 className="display text-3xl">` |

### 6.3 BackLink 仍未迁移（2 处）

| 文件 | 现状 |
| --- | --- |
| `app/[locale]/output/[task_id]/_components/task-detail-client.tsx` | 手写返回链 |
| `app/[locale]/output/[task_id]/[file]/page.tsx` | 手写返回链 |

### 6.4 AppDataEmpty 可直接替换（5 处，json-view/diff）

`components/json/json-view.tsx:31+46` 和 `components/json/json-diff.tsx:46` 共 5 处：
- 空态：`<div className="flex items-center justify-center rounded-lg border p-8 text-muted-foreground">` → `<AppDataEmpty>`
- 错误态：`<div ... text-destructive>` → 给 AppDataEmpty 加 `variant="destructive"`

### 6.5 Badge 替换手写徽章（1 处）

`components/chat/message-bubble.tsx:105` interrupted badge → shadcn `<Badge variant="outline" className="bg-status-warning/10 text-status-warning">`

### 6.6 业务模块 div/span 重复（C 报告按模块）

#### account / 个人中心
- `account/settings/page.tsx` `<div className="space-y-6 p-6">` → `<PageContainer>`（不推荐）
- `account/settings/_components/change-email-dialog.tsx` + `change-password-dialog.tsx` + `request-deletion-dialog.tsx` + `cancel-deletion-dialog.tsx` 4 处 `<div className="flex justify-end gap-2 pt-2">` → `<DialogFooter>`
- 其它：`profile-section`, `avatar-uploader`, `restore-form` 已有 `<Card>` 包装

#### output / 文档结构化
- `output/page.tsx` `<div className="space-y-6 p-6">` → `<PageContainer>`（不推荐）
- `output/new/page.tsx` 手写 hero → 迁 `<PageHero>`
- `output/_components/output-list-client.tsx` 手写 hero → 迁 `<PageHero>`
- `output/[task_id]/_components/task-detail-client.tsx` + `[file]/page.tsx` 手写返回链 → 迁 `<BackLink>`
- `output/_components/output-card.tsx` `<div className="flex justify-end gap-2">` → `<RowActions>`（不推荐）

#### knowledge / 知识库（17 文件，本区最大）
- `knowledge/_components/knowledge-dashboard.tsx` 4 张 `<EntryCard>`，已迁 `<PageHero>` + `<Reveal>`（Phase3 Task 3.5 标杆）
- `knowledge/documents/import/_components/import-commit-card.tsx` 手写错误条 → `<ErrorBanner>`
- `knowledge/batch/page.tsx` 手写错误条 → `<ErrorBanner>`
- `knowledge/triples/_components/triples-form.tsx` 手写错误条 → `<ErrorBanner>`
- 3 处 `<div className="h-full overflow-y-auto">` → 不推荐抽 `<PageScrollArea>`（单 className）

#### admin / 后台管理
- `admin/users/page.tsx` 手写 hero → 迁 `<PageHero>`
- `admin/users/_components/admin-users-table.tsx` `<div className="space-y-4">` → `<Stack>`（不推荐）
- `admin/users/_components/user-filters.tsx` `<div className="flex flex-wrap items-center gap-2">` → `<FilterBar>`（不推荐）
- `admin/users/_components/create-invite-dialog.tsx` + `reset-password-dialog.tsx` 2 处 `<div className="flex gap-2">` → `<DialogFooter>`
- `admin/invites/page.tsx` 手写 hero → 迁 `<PageHero>`
- `admin/profile-fields/page.tsx` 7 个 `<div className="space-y-2">` + 2 个 `<div className="space-y-4">` + 2 个 `<div className="flex justify-end gap-2">` → `<Stack>` + `<DialogFooter>`

---

## 7. 不建议改动的 Pattern（A 报告的 6 类 shadcn 标准模板）

shadcn/ui 标准实现层（`components/ui/`）的以下 pattern 是上游设计，**不建议改**：

1. 弹框 close 按钮（X）— Dialog/Sheet 重复 2 处（破坏 shadcn 升级）
2. 弹框 Header 三件套 — Dialog/Sheet/AlertDialog 3 文件
3. 弹框 Footer 三件套 — 3 文件
4. Overlay 遮罩层 — 3 文件
5. Table 容器 — 1 文件
6. animate-in / animate-out Radix state — 6 文件 10 处

**建议处理方式**：跨业务封装层重复时抽 `const`（如 `DIALOG_BODY_CLS`），不开新文件。

---

## 8. lib/ 区无任何发现（D 报告）

- **76 个 lib/ const/ i18n/ scripts/ proxy/ next.config 文件全部 0 div/span**
- lib/hooks/* 9 个 hooks 全是纯逻辑（TanStack Query + zustand + useState）
- lib/chat/* 15 个文件是 fetch/storage/类型定义
- lib/motion.ts 是 framer-motion variants object，不是 JSX
- 仅 `lib/store/app-data.tsx` 和 `lib/test-utils/intl-wrapper.tsx` 是 React Provider，无包装 div

**结论**: P2-P5 维度扫描时可跳过 lib/，除非是函数式写法扫描。

---

## 9. 已合规的使用模式（鼓励保持）

以下封装使用率较高的项目，需要保持：

- ✅ `<PageHero>` — 9 处（Phase3 Task3.5 完成度）
- ✅ `<DataTable>` — 9 处（4 个旧表格已迁移）
- ✅ `<ErrorBanner>` — 9 处（但仍有 5 处手写需迁）
- ✅ `<AppDialog>` / `<AppConfirm>` — 9 处
- ✅ `<EntryCardGrid>` — 4 处（Phase3 Task3.5）
- ✅ `<Reveal>` — knowledge 仪表盘等

---

## 10. 实施优先级建议（按 ROI 重排）

| 优先级 | 行动 | ROI | 估算 |
| --- | --- | --- | --- |
| **P0 本周** | 5 处手写错误条 → `<ErrorBanner>` | 🔴 极高 | 5 文件 × 5 行 = 25 行 |
| **P0 本周** | 4 处 PageHero + 2 处 BackLink 迁移 | 🔴 高 | 6 文件 × 8 行 = 50 行 |
| **P0 本周** | message-bubble interrupted → `<Badge>` | 🔴 高 | 1 文件 × 3 行 |
| **P1 下 sprint** | `<DialogFooter>` 新增 + 9 处替换 | 🔴 高 | 9 文件 × 4 行 = 36 行 |
| **P1 下 sprint** | `<AppDataEmpty variant="destructive">` 扩展 + 5 处替换 | 🟡 中 | 2 文件 |
| **P2 后续** | `<AppListItem>` + `<AppSubtleCard>` 抽封装 | 🟡 中 | 8 文件 / 10 处 |
| **P2 后续** | `<AuthFormContainer>` 抽封装 | 🟡 中 | 4 文件 |
| **P2 后续** | `<Callout>` 抽封装 | 🟢 低 | 3 文件 |
| **P3 可选** | `<AppSettingsRow>` `<AppCodeBlock>` 单文件/小扩展 | 🟢 低 | 2-3 文件 |

**总计**: ~178 行节省（净减少），覆盖 ~38 文件，~2 人天

> ⚠️ **明确不做**（违反 YAGNI）：`<Stack>` `<PageContainer>` `<PageScrollArea>` `<RowActions>` `<FilterBar>` `<PaginationBar>` `<SettingsCard>` —— 这些是把 1-2 个 className 包成组件，**净增复杂度**。

---

## 11. 后续建议

1. **先验证 ROI**: 抽样 1-2 个新封装（如 `<Stack>`），确认收益符合预期后再批量
2. **保持封装层纯净**: components/common/ 和 components/ui/ 不必再拆
3. **统一视觉语言**: 优先用项目 token（`bg-status-*/10` 而非 `bg-{emerald/amber/rose}-100`），如 message-bubble 徽章
4. **后续审计维度 (P2-P5)**:
   - P2 CVA: 重点扫业务组件（chat/knowledge/admin）
   - P3 设计模式: 重点扫 lib/api/, lib/store/, lib/chat/ 业务编排
   - P4 函数式: 重点扫 lib/hooks/, lib/chat/, lib/api/ 工具函数
   - P5 注释: 全项目统一扫描（lib/ 也需注释）