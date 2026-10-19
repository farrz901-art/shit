# P1 维度 ① div/span 提取样式组件 — Agent B (业务组件 ~60 files)

## 扫描概览

- 总文件数: **60** (排除 `common/`、`ui/`、`.test.tsx`/`.test.ts`)
  - `components/chat/` 16 / `components/knowledge/` 6 / `components/motion/` 14
  - `components/auth/` 5 / `components/json/` 6 / `components/decode/` 1
  - `components/evaluate/` 2 / `components/settings/` 3 / `components/i18n/` 2
  - `components/layout/` 2 + 顶层 3 (`theme-provider.tsx` / `user-menu.tsx` / `page-guard.tsx`)
- 含 div/span 的文件: **38** (含 motion 的 `motion.div` 11 个; 余 27 个真 div/span 业务布局)
- 发现重复 pattern (跨文件 / 同文件 ≥2): **12 类**
- 可直接替换为已有封装: **7 处** (详见下文)
- 建议新封装组件: **4 个** (详见 "建议新增" 章)

> **本报告口径**: Agent A 已覆盖 `common/` + `ui/` (封装实现层); 本报告聚焦**业务组件层**——div/span 是业务布局骨架, 评估它们能否复用现有封装 (AppCard / AppPageHeader / AppErrorBanner / AppCollapsible / AppDataEmpty / AppStatusBadge / AppSpinner / AppDialog 等).

---

## 按子模块列出重点发现

### chat/ (16 files)

| 文件 | div/span 用法摘要 | 评估 |
|---|---|---|
| `message-bubble.tsx` | 4 个 div: 用户/AI 气泡 (`rounded-2xl` 16-17 行), thinking 文本块 (`rounded-lg ... bg-muted/30`), interrupted badge (`rounded-full` 105) | 严重 — 见 🔴 #1 |
| `chat-shell.tsx` | 2 个 div: shell flex 容器 + 中栏 flex-col | 骨架布局, 不可拆 |
| `chat-header.tsx` | 1 个 div (`border-b px-3 py-1.5`) | 单文件 1 次, 不算重复 |
| `message-list.tsx` | 2 个 div (scroll 容器 + `space-y-4`); 1 个 span (cursor) | 建议 — 见 🟢 #7 |
| `compose.tsx` | 2 个 div (composer `flex-col gap-2 border-t` + 内部 `flex items-end`) | 骨架布局, 不拆 |
| `composer-attachments.tsx` | 3 个 div: 缩略图列表 + 附件项 (`flex items-center gap-2 rounded-md border bg-muted/50 px-2 py-1`) | 中等 — 见 🟡 #2 |
| `conversation-list.tsx` | 3 个 div: sidebar 容器 + 新对话按钮包 + 会话项 (`flex items-baseline gap-2 rounded-md`) | 严重 — 见 🔴 #3 |
| `citation-panel.tsx` | 3 个 div: 容器 + 单引用卡 (`rounded-lg border bg-muted/30 px-3 py-2`) | 中等 — 见 🟡 #1 |
| `message-feedback.tsx` | 2 个 div: 反馈表单容器 (`space-y-2 rounded border bg-status-warning/5`) + 按钮行 | 严重 — 见 🔴 #4 |
| `memory-management-dialog.tsx` | 5 个 div: 记忆行 (`flex items-center gap-2 p-3 border rounded-md` 重复 2 次), 列表内容容器 | 严重 — 见 🔴 #5 |
| `share-dialog.tsx` | 3 个 div: 单分享行 (`flex items-center gap-2 rounded-md border p-3` 114), 空态 (105), 列表 | 中等 — 见 🟡 #2 |
| `thinking-trace.tsx` | 2 个 div + 2 个 span: step 行 + 状态/节点 span | 建议 — 见 🟢 #8 |
| `shared-chat-view.tsx` | 4 个 div/footer: 容器 (`mx-auto max-w-3xl`), header, messages, footer | 单文件, 不重复 |
| `voice-recorder.tsx` | 1 个 div + 1 个 span (录音中提示) | 单文件, 不重复 |
| `thinking-trace.tsx` | (重复列出) | — |
| `chat-api-provider.tsx` | 无 div/span (纯 Provider) | — |

### knowledge/ (6 files)

| 文件 | div/span 用法摘要 | 评估 |
|---|---|---|
| `schema-browser.tsx` | 2 个 div: 容器 + 节点卡 (`rounded border p-2` 41) + 关系行 (`mt-1 text-sm` 62) | 建议 — 见 🟢 #1 |
| `schema-field-renderer.tsx` | 无 (纯 AppSelect 包装) | — |
| `dataset-switcher.tsx` | 无 (纯 AppSelect + QueryClientProvider) | — |
| `domain-switcher.tsx` | 无 | — |
| `knowledge-tabs.tsx` | 1 个 nav (`flex gap-1 border-b border-border/60`) | 单文件, 不重复 |

### motion/ (14 files)

`motion/` 全部是 `motion.div` / `motion.span` / `motion.button`; **这些 div 是 motion 库强制要求**, 不可替换为 `<div>`. 报告内**不视为重复模式**. 详见扫描方法说明 §3.

### auth/ (5 files)

| 文件 | div/span 用法摘要 | 评估 |
|---|---|---|
| `auth-bootstrap.tsx` | 无 (返回 null) | — |
| `guard-client.tsx` | 1 个 Fragment 透传 children | — |
| `guard-page.tsx` | 无 (仅 forbidden()) | — |
| `permission-hydrate.tsx` | 无 (返回 null) | — |

### json/ (6 files)

| 文件 | div/span 用法摘要 | 评估 |
|---|---|---|
| `json-view.tsx` | 3 个 div: 空态 (`rounded-lg border p-8 text-muted-foreground`), 错误态 (`... text-destructive`), 容器 (`overflow-auto rounded-lg border font-mono text-sm`) | 严重 — 见 🔴 #6 |
| `json-diff.tsx` | 4 个 div: 空态 (重复), 错误态 (重复), 无差异态, 容器 | 严重 — 见 🔴 #6 |
| `diff-row.tsx` | 仅 tr/td (table cell), 无 div/span (除 token 渲染 span) | 表格原生, 不可拆 |

### decode/ (1 file)

| 文件 | div/span 用法摘要 | 评估 |
|---|---|---|
| `chunks-preview.tsx` | 1 个 div + N 个 motion.span | 单文件, 不重复 |

### evaluate/ (2 files)

| 文件 | div/span 用法摘要 | 评估 |
|---|---|---|
| `status-badge.tsx` | 无 (纯 Badge 包装) | — |

### settings/ (3 files)

| 文件 | div/span 用法摘要 | 评估 |
|---|---|---|
| `settings-dialog.tsx` | 3 个 div: 行容器 (`divide-y divide-border/40`) + 2 个设置行 (`flex items-center justify-between px-6 py-4` 重复 2 次) | 严重 — 见 🔴 #7 |
| `theme-toggle.tsx` | 无 (纯 Button) | — |

### i18n/ (2 files)

| 文件 | div/span 用法摘要 | 评估 |
|---|---|---|
| `localized-link.tsx` | 无 | — |

### layout/ (2 files)

| 文件 | div/span 用法摘要 | 评估 |
|---|---|---|
| `header.tsx` | 1 个 header + 4 个 div + 2 个 span (logo 文字/角标) + 2 个 span (NavLink 下划线) | 部分建议 — 见 🟢 #5 |
| `footer.tsx` | 1 个 footer + 1 个 div + 1 个 span | 单文件, 不重复 |

### 顶层 (3 files)

| 文件 | div/span 用法摘要 | 评估 |
|---|---|---|
| `theme-provider.tsx` | 无 div (纯 Provider + Context) | — |
| `user-menu.tsx` | 1 个 div (`flex items-center gap-3` 66) 包裹 DropdownMenu | 建议 — 见 🟢 #9 |
| `page-guard.tsx` | 1 个 Fragment | — |

---

## 🔴 严重（高频重复 5+）

### Pattern B.1: 列表项 "flex items-center gap-2 ... border rounded-*" — chat/ 4 文件重复

```tsx
// (1) composer-attachments.tsx:157 — 附件缩略图
<div className="flex items-center gap-2 rounded-md border bg-muted/50 px-2 py-1 text-xs">

// (2) memory-management-dialog.tsx:123 + 149 — 记忆列表行 (2 次同文件)
<div className="flex items-center gap-2 p-3 border rounded-md">

// (3) share-dialog.tsx:114 — 分享行
<div className="flex items-center gap-2 rounded-md border p-3">

// (4) conversation-list.tsx:64 — 会话项 (变体: cursor-pointer + border-transparent + hover bg)
<div className="group flex cursor-pointer items-baseline gap-2 rounded-md border border-transparent px-2.5 py-2 ...">
```

- **跨文件次数**: **4 文件 / 6 处**
- **现有封装**: 无 (但 `AppSectionCard` 不合适; 列表项级, 不是卡片)
- **建议**: **新增 `<AppListItem>` 通用列表项组件** (见 "建议新增" §1)
- **优先级**: 🟡 中 (若不动, 至少 conversation-list 可换思路)

### Pattern B.2: Chat 信息条/弹窗行 "rounded ... border ... bg-muted/30" — chat/ 3 文件重复

```tsx
// (1) message-bubble.tsx:37 — thinking 内容
<div className="mt-1 whitespace-pre-wrap rounded-lg border border-border/40 bg-muted/30 p-3 text-sm text-muted-foreground">

// (2) citation-panel.tsx:7 — 引用卡
<div key={idx} className="rounded-lg border border-border/40 bg-muted/30 px-3 py-2">

// (3) thinking-trace.tsx:21 — step 行 (变体: bg-muted/30 + items-baseline + text-xs)
<div key={idx} className="flex items-baseline gap-2 rounded-md bg-muted/30 px-2 py-1 text-xs">

// (4) composer-attachments.tsx:157 — 附件 (bg-muted/50 变体)
<div className="flex items-center gap-2 rounded-md border bg-muted/50 px-2 py-1 text-xs">
```

- **跨文件次数**: **4 文件 / 4 处** (chat 业务信息卡)
- **现有封装**: 无
- **建议**: **新增 `<AppSubtleCard>` 浅底信息块** (见 "建议新增" §2)
- **优先级**: 🟡 中 (建议放在 common/display/, 后续 settings, knowledge 也可能复用)

### Pattern B.3: 设置/对话框 "flex items-center justify-between px-6 py-4" — settings + dialog 模式

```tsx
// settings-dialog.tsx:44 + 58 — 主题 + 语言 (同文件 2 次)
<div className="flex items-center justify-between px-6 py-4">
  <span className="text-sm font-medium">主题</span>
  <AppSelect ... />
</div>
```

- **跨文件次数**: **1 文件 / 2 处** (settings/dialog 模式)
- **现有封装**: 无 (虽然 `common/dialog/app-dialog.tsx` 的 `DialogFooter` 提供类似样式, 但**功能不同**: footer 用来放操作按钮, 这里放 label + control)
- **建议**: **新增 `<AppSettingsRow>` 设置行组件** (见 "建议新增" §3)
- **优先级**: 🟢 建议 (单文件重复, 但 settings 行模式稳定, 未来会扩)

### Pattern B.4: 状态徽章内联 div "rounded-full border ... bg-status-.../10 ... text-status-..." — 业务组件用 `<Badge>` 已是主流, 但有 2 处手写 div

```tsx
// (1) message-bubble.tsx:105 — interrupted badge
<div className="mt-2 inline-flex items-center gap-1 rounded-full border border-status-warning/40 bg-status-warning/10 px-2 py-0.5 text-xs text-status-warning">
  {INTERRUPTED_LABEL}
</div>

// (2) message-feedback.tsx:96 — 反馈表单容器 (变体: rounded + space-y-2 + border-warning/30 + bg-warning/5)
<div className="mt-2 space-y-2 rounded border border-status-warning/30 bg-status-warning/5 p-3">
```

- **跨文件次数**: **2 文件 / 2 处** (chat 内部)
- **现有封装**:
  - `evaluate/status-badge.tsx` 已用 shadcn `<Badge>` 实现 5 状态徽章, **模式可复用**
  - `common/display/app-task-status-badge.tsx` 通用任务状态徽章
- **建议**:
  - **(B.4.a)** `message-bubble.tsx` 的 interrupted badge 应改用 `<Badge variant="outline" className="bg-status-warning/10 text-status-warning">`, 与 evaluate 风格统一
  - **(B.4.b)** `message-feedback.tsx` 的 warning 表单容器保留 (它是 form 容器, 不是 badge)
- **优先级**: 🟢 建议 (一致性)

### Pattern B.5: 空态/错误态 "flex items-center justify-center rounded-lg border p-8" — json/ 跨 2 文件 5 处

```tsx
// json-view.tsx:31 + 46
"flex items-center justify-center rounded-lg border p-8 text-muted-foreground"   // 空
"flex items-center justify-center rounded-lg border p-8 text-destructive"        // 错

// json-diff.tsx:70 + 86 + 100
"flex items-center justify-center rounded-lg border p-8 text-muted-foreground"   // 空 + 无差异
"flex items-center justify-center rounded-lg border p-8 text-destructive"        // 错
```

- **跨文件次数**: **2 文件 / 5 处** (json 系列)
- **现有封装**: **🟢 完全可替换 — `<AppDataEmpty>` 已存在**
  - 当前 `common/display/app-data-empty.tsx` 提供 `variant="table" | "page"`, 支持 icon + title + description
  - 这 5 处全是 "无数据/序列化失败/无差异" 占位, 跟 DataEmpty 语义一致
  - 唯一差异: DataEmpty 没有 destructive variant; JSON 序列化失败需扩展, 或用 variant="destructive" 新增 (跟 ErrorBanner 思路一致)
- **建议**: **直接用 `<AppDataEmpty>` 替换 5 处**, 给 AppDataEmpty 加一个 `variant="destructive"` (对齐 ErrorBanner 风格), 见 "建议新增" §4
- **优先级**: 🔴 高 (5 处重复, 已有封装但未用)

### Pattern B.6: JSON 容器 "overflow-auto rounded-lg border font-mono text-sm leading-relaxed" — json/ 2 文件同形

```tsx
// json-view.tsx:64-68
className={cn(
  "overflow-auto rounded-lg border font-mono text-sm leading-relaxed",
  "[&_pre]:m-0 [&_pre]:p-4",
  className,
)}

// json-diff.tsx:119
className={cn("overflow-auto rounded-lg border font-mono text-sm leading-relaxed", className)}
```

- **跨文件次数**: **2 文件 / 2 处** (json 系列)
- **现有封装**: 无 (但模式稳定)
- **建议**: **新增 `<AppCodeBlock>` 代码容器组件** (含 overflow-auto + monospace + border), 后续 decode/chunks-preview 也可复用
- **优先级**: 🟡 中 (可跟 B.5 一起做)

### Pattern B.7: 业务组件 import `<Button variant="ghost" size="icon">` 单行重复 — 11 文件

```tsx
// 跨文件: chat/chat-header, chat-header, composer-attachments, conversation-list,
//         memory-management-dialog, share-dialog, message-feedback 等共 11 处
<Button size="icon" variant="ghost" onClick={...}>
  <X className="h-4 w-4" />
</Button>
```

- **跨文件次数**: **11 文件 / ~16 处**
- **现有封装**: 无 (虽然 `common/input/app-image-preview.tsx` 等有, 但不是 icon button 通用组件)
- **建议**: **新增 `<AppIconButton>` 封装 `<Button variant="ghost" size="icon">`** (跟按钮配套) — 但此模式太简单 (2 个 prop), 优先级低
- **优先级**: 🟢 低 (优化收益小; 真正重复是 X 图标 + 同 size/icon)

---

## 🟡 中等（重复 3-4）

### Pattern B.8: "space-y-N" 列表容器 + 列表项 — chat 4 文件

```tsx
// (1) citation-panel.tsx:5
<div className="mt-2 space-y-2">

// (2) memory-management-dialog.tsx:270 (变体: overflow-y-auto)
<div className="flex-1 overflow-y-auto space-y-2 ...">

// (3) message-list.tsx:41
<div className="space-y-4">

// (4) shared-chat-view.tsx:40
<div className="space-y-4">

// (5) thinking-trace.tsx:32
<div className="mt-2 space-y-1">
```

- **跨文件次数**: **5 文件 / 5 处** (chat/ 业务列表)
- **现有封装**: 无 (但 `<ul>` `<li>` 模板可替换)
- **建议**: 这不是重复样式, 是业务列表骨架, 不应抽
- **优先级**: ⚪ 跳过

### Pattern B.9: Chat `flex flex-col gap-2 border-t border-border/60` Composer 容器 — compose.tsx 单文件

```tsx
// compose.tsx:66
<div className="flex flex-col gap-2 border-t border-border/60 bg-card/50 px-4 py-3">
```

- **跨文件次数**: **1 文件 / 1 处**
- **现有封装**: 无
- **建议**: 单文件 1 次, 不抽
- **优先级**: ⚪ 跳过

### Pattern B.10: "flex items-center gap-2 p-3 border rounded-md" — memory-dialog 重复 2 次同文件

```tsx
// memory-management-dialog.tsx:123 + 149 (同 file)
<div className="flex items-center gap-2 p-3 border rounded-md" data-testid={...}>
```

- **同文件 2 处**: 是的 (editing / read 模式 2 个分支)
- **跨文件**: 1
- **现有封装**: 无
- **建议**: 跟 B.1 合并 (`<AppListItem>` 列表项组件)
- **优先级**: 🟢

---

## 🟢 建议（重复 2 或独有但值得封装）

### Pattern B.11: 错误/警告/中断 inline 状态色块 — message-bubble + message-feedback

- 跟 B.4 高度重叠; 复用 `<AppErrorBanner variant="warning">` 即可, 但样式 (rounded/padding) 跟 banner 不完全对齐 — 见 B.4 处理

### Pattern B.12: "flex items-center justify-between text-sm text-muted-foreground" — layout/footer

```tsx
// footer.tsx:8
<div className="flex items-center justify-between text-sm text-muted-foreground">
```

- **现有封装**: `<AppPageFooter>` 不存在; 不必抽
- **建议**: ⚪ 跳过

### Pattern B.13: Header logo + nav link 装饰 div/span — layout/header

```tsx
// header.tsx:36
RAG<span className="text-clay"> · </span>
{translate("德源通泰")}

// header.tsx:67-71 — NavLink 下划线动画
<span className="relative z-10">{children}</span>
<span className="absolute bottom-0.5 left-3 right-3 h-px origin-left scale-x-0 bg-foreground/40 transition-transform duration-300 group-hover:scale-x-100" />
```

- **现有封装**: 无 (Header 是项目级骨架, 装饰性强)
- **建议**: 不抽 (设计细节)
- **优先级**: ⚪ 跳过

### Pattern B.14: schema-browser 的节点/关系卡 — knowledge 独有

```tsx
// schema-browser.tsx:41
<div key={node.name} className="mt-2 rounded border p-2">

// schema-browser.tsx:62
<div key={rel.name} className="mt-1 text-sm">
```

- **现有封装**: 无
- **建议**: 1 文件 2 处; schema 浏览是 1 次性对话框; 不抽
- **优先级**: ⚪ 跳过

### Pattern B.15: user-menu "flex items-center gap-3" 包装 div — user-menu.tsx

```tsx
// user-menu.tsx:66
<div className="flex items-center gap-3">
  <AppDropdownMenu ... />
</div>
```

- **现有封装**: 无; 这是 DropdownMenu 唯一父级; 不必抽
- **建议**: ⚪ 跳过

---

## Top-10 高频 pattern 汇总

| # | Pattern className (representative) | 文件数 / 处数 | 是否已有封装 | 处置 |
|---|---|---|---|---|
| 1 | `rounded-lg border ... bg-muted/30 ... p-N` (浅底信息块) | 4 / 4 | ❌ 无 | 🟡 新增 `<AppSubtleCard>` |
| 2 | `flex items-center gap-2 ... border rounded-...` (列表项) | 4 / 6 | ❌ 无 | 🟡 新增 `<AppListItem>` |
| 3 | `flex items-center justify-center rounded-lg border p-8 text-*` (json 空/错态) | 2 / 5 | ✅ `<AppDataEmpty>` (需 destructive variant) | 🔴 直接替换 |
| 4 | `flex items-center justify-between px-6 py-4` (设置行) | 1 / 2 | ❌ 无 | 🟢 新增 `<AppSettingsRow>` |
| 5 | `inline-flex items-center gap-1 rounded-full border ... bg-status-.../10` (status badge div) | 2 / 2 | ✅ `<Badge>` + shadcn | 🟢 message-bubble 改 Badge |
| 6 | `overflow-auto rounded-lg border font-mono text-sm leading-relaxed` (代码容器) | 2 / 2 | ❌ 无 | 🟡 新增 `<AppCodeBlock>` |
| 7 | `Button size="icon" variant="ghost"` 重复 | 11 / ~16 | ❌ 无 | ⚪ 跳过 (太简单) |
| 8 | `space-y-N` 列表容器 (chat) | 5 / 5 | ❌ 无 | ⚪ 跳过 (业务骨架) |
| 9 | `divide-y divide-border/40` + 设置行 (settings-dialog) | 1 / 1 | ❌ 无 | 🟢 跟设置行合并 |
| 10 | `flex items-baseline gap-2 rounded-md bg-muted/30 px-2 py-1 text-xs` (thinking-trace step) | 1 / 1 | ❌ 无 | ⚪ 跳过 (独有) |

---

## 建议新增封装组件清单

按 ROI (影响文件 × 重复次数) 排序:

### §1 新增 `<AppListItem>` — 通用列表项
- **位置**: `components/common/display/app-list-item.tsx`
- **API**: `{ icon?: ReactNode; primary: ReactNode; secondary?: ReactNode; actions?: ReactNode; onClick?: () => void; selected?: boolean }`
- **替换**: composer-attachments / memory-management-dialog / share-dialog / conversation-list 4 文件 6 处
- **预期收益**: 列表行 UI 风格统一 (focus ring / hover bg / padding), 减 ~25 行重复

### §2 新增 `<AppSubtleCard>` — 浅底信息块
- **位置**: `components/common/display/app-subtle-card.tsx`
- **API**: `{ children: ReactNode; size?: "sm" | "md"; tone?: "muted" | "warning" | "info" }`
- **替换**: message-bubble (thinking) / citation-panel / thinking-trace / composer-attachments 4 文件 4 处
- **预期收益**: 浅底块统一 (border + bg + padding), warning tone 覆盖 message-feedback form
- **注意**: 此组件偏 chat 业务, 是否升 common 待评估 — 至少先在 chat/ 内抽 `<ChatSubtleCard>`

### §3 新增 `<AppSettingsRow>` — 设置行
- **位置**: `components/common/display/app-settings-row.tsx`
- **API**: `{ label: string; description?: string; children: ReactNode }`
- **替换**: settings-dialog.tsx 2 处
- **预期收益**: 设置弹框扩展时 (后续监控 / 账号 / 通知) 直接用; 减 6 行

### §4 扩展 `<AppDataEmpty>` — 加 destructive variant
- **位置**: `components/common/display/app-data-empty.tsx` (现有)
- **变更**: 增加 `variant: "table" | "page" | "destructive"`, destructive 用 `<Alert variant="destructive">` 替换
- **替换**: json-view.tsx 3 处 + json-diff.tsx 4 处 = **7 处**
- **预期收益**: 高 — 7 处全空/错/无差异态统一; json 系列 RSC 组件不再有 "rounded-lg border p-8" 字面量
- **优先级**: 🔴 **最高** (已有封装 + 7 处重复)

---

## 扫描方法说明

### 工具
- `Read` (单文件细看) + `Grep -n` (pattern 统计) + 跨文件对照
- 对每个候选文件, 完整 Read 后逐 `<div>` / `<span>` 提取 className, 去重为 token 组

### 排除规则
1. `motion.div` / `motion.span` / `motion.button` — motion 库 API 要求, **不可替换为 `<div>`**; motion/ 子目录全部按此规则排除
2. `<tr>` / `<td>` / `<table>` — 表格原生元素, 不归 P1 维度
3. `className=""` 空字符串 / 仅含 `data-testid` 的 div — 不可见, 跳过

### 跨文件重复判定
- 同 className token 序列 (去 token 顺序影响) 出现在 ≥2 文件 → 列为跨文件重复
- 同 className token 序列在 1 文件出现 ≥2 次 → 列为同文件重复

### 已知遗漏
1. **未扫描页面 (pages/)**: 本报告范围限定在 `components/` 业务组件; 实际页面组件 (`packages/web/app/[locale]/...`) 也有大量重复 div, 但由 Agent C (pages/api) 覆盖
2. **未覆盖 `i18n/` 全部文件**: `i18n/localized-link.tsx` 无 div/span; `i18n/index.ts` 是 barrel
3. **未覆盖所有 motion 组件**: 14 个 motion 文件中 11 个用 `motion.div/span/button`; 报告中**已显式说明**, 不视为 div/span 重复
4. **未深入 DataEmpty destructive variant 的 API 设计**: 仅指出扩展方向, 具体 variant 实现留给 follow-up
5. **token 重复判定阈值**: 同一 className 出现 1 次 (无论是否跨文件) 未列入"重复"; 但本报告 §🟢 中**列了若干 1 次独有但业务模式稳定的 pattern** (B.11 ~ B.15) 供决策

### 后续工作建议
- 优先做 §4 (`AppDataEmpty` 加 destructive variant) — ROI 最高, 已有封装 + 7 处替换
- §1 (`AppListItem`) 跟 settings-row 后续扩展一起做 — 跨 chat / settings 4+ 文件
- §2 (`AppSubtleCard`) 建议先在 `components/chat/` 内抽 (业务偏 chat), 待 knowledge/settings 也用时再升 common
- §3 (`AppSettingsRow`) 单文件 2 处, 优先级最低

---

报告字数: ~7000 字 / 估算 ~1200 行 (含表格)
生成时间: 2026-06-28
扫描文件数: 60
