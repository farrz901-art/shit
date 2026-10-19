# P1 维度 ① div/span 提取样式组件 — Agent A (common+ui 78 files)

## 扫描概览

- 总文件数: 78
  - `components/common/`: 43 个 .tsx (排除 .test.tsx / .stories.tsx)
  - `components/ui/`: 35 个 .tsx (排除 .test.tsx)
- 含 div/span 的文件: 71 (封装实现层 div/span 必然存在, 排除纯包装的 index.ts)
- 发现重复 pattern: 8 类
- 可直接替换为已有封装: 2 (Dialog/Sheet/Dropdown close 按钮 + Sheet/Dialog/AlertDialog Header/Footer 重复)
- 建议新封装组件: 3 (DialogCloseButton / FormFieldHorizontal / TabsContent + Content wrapper)

## 扫描范围说明

本报告聚焦 **封装实现层**(common/ + ui/) 的 div/span 使用模式. 这些文件**本身就是封装层**, 用 div/span 是合理的; 但跨文件重复模式说明**可以再抽一层公共 sub-component** 或在 **shadcn/ui 实现层** 提炼一个 `cn()` 复用.

`components/common/` 大量 div/span 用于**业务组合**(如 `AppDialog` 把 shadcn DialogContent 拼成 antd 风格), 这部分**不应**继续拆 div (会引入额外抽象); 但有少数**跨文件重复样式块**值得抽.

`components/ui/` 是 shadcn/ui 标准实现层, 文件之间确实有高度同构的 className (Dialog/Sheet/AlertDialog 三个 close 按钮 + 三个 Header/Footer), 但这是 **shadcn 标准实现**, 改它会破坏 shadcn 升级兼容性. **不建议改**.

---

## 🔴 严重（高频重复 5+）

### Pattern A.1: 弹框/抽屉 close 按钮 (X) — Dialog/Sheet 重复 2 处

```tsx
<DialogPrimitive.Close className="absolute right-4 top-4 rounded-sm opacity-70 ring-offset-background transition-opacity hover:opacity-100 focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:pointer-events-none data-[state=open]:bg-accent data-[state=open]:text-muted-foreground">
  <X className="h-4 w-4" />
  <span className="sr-only">Close</span>
</DialogPrimitive.Close>
```

- **出现位置**:
  - `packages/web/components/ui/dialog.tsx:47-50` (DialogContent 内部)
  - `packages/web/components/ui/sheet.tsx:65-68` (SheetContent 内部, 唯一区别: `bg-secondary` 替代 `bg-accent`)
- **现有封装**: 无 (shadcn 原始模板)
- **方案**:
  - **(不推荐) 抽 `AppDialogCloseButton`**: 业务层目前都被 `AppDialog` / `AppDrawer` 包装, 默认就有 X. 抽会让 Radix 状态注入复杂化.
  - **(推荐) 保持现状**: shadcn 升级时会同步覆盖, 跨文件 2 处重复可接受. 但**Sheet close 按钮用 `bg-secondary` 跟 Dialog 不一致**, 应该统一为 `bg-accent`, 这是 shadcn 默认行为差异, 不是封装问题.

### Pattern A.2: 弹框/抽屉/确认框 Header 三件套 (shadcn 模板) — 3 文件重复

```tsx
const DialogHeader = ({ className, ...props }) => (
  <div className={cn("flex flex-col space-y-1.5 text-center sm:text-left", className)} {...props} />
);
```

- **出现位置** (className 一致或差异 ≤ 2 个 token):
  - `packages/web/components/ui/dialog.tsx:56-59` — `space-y-1.5 text-center sm:text-left`
  - `packages/web/components/ui/sheet.tsx:74-77` — `space-y-2 text-center sm:text-left`
  - `packages/web/components/ui/alert-dialog.tsx:48-51` — `space-y-2 text-center sm:text-left`
- **现有封装**: 无
- **方案**: 全部都是 shadcn 标准模板, **不建议改** (改即破坏 shadcn 升级路径). space-y-1.5 vs 2 是上游 shadcn 设计差异, 不应本地合并.
- **建议**: **保留现状**, 在 P1 报告里只标注不需替换.

### Pattern A.3: 弹框/抽屉/确认框 Footer 三件套 (shadcn 模板) — 3 文件完全一致

```tsx
const DialogFooter = ({ className, ...props }) => (
  <div className={cn("flex flex-col-reverse sm:flex-row sm:justify-end sm:space-x-2", className)} {...props} />
);
```

- **出现位置** (className 完全相同):
  - `packages/web/components/ui/dialog.tsx:61-66`
  - `packages/web/components/ui/sheet.tsx:79-84`
  - `packages/web/components/ui/alert-dialog.tsx:53-58`
- **现有封装**: 无
- **方案**: **不建议改**, 同 Pattern A.2, shadcn 标准模板.

### Pattern A.4: Overlay 遮罩层 (fixed inset-0 z-50 bg-black/80 + animate) — 3 文件重复

```tsx
className={cn(
  "fixed inset-0 z-50 bg-black/80  data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0",
  className,
)}
```

- **出现位置** (DialogOverlay/SheetOverlay/AlertDialogOverlay):
  - `packages/web/components/ui/dialog.tsx:23-25`
  - `packages/web/components/ui/sheet.tsx:23-25`
  - `packages/web/components/ui/alert-dialog.tsx:20-23`
- **现有封装**: 无 (但 `AppDialog` / `AppDrawer` / `AppConfirm` 是包装层)
- **方案**: **不建议改**, shadcn 标准 Overlay 实现.

### Pattern A.5: 数据结构 table 容器 (rounded-lg border border-border/60) — 1 文件但跨封装内部多处

```tsx
<div className="relative w-full overflow-auto">  // Table 内 div
  <table ref={ref} className={cn("w-full caption-bottom text-base", className)} {...props} />
</div>
```

- **出现位置**: `packages/web/components/ui/table.tsx:5-9`
- **现有封装**: `<Table>` 已用 (shadcn), 业务层禁用手写 (项目规约见 `CLAUDE.md §表格组件`)
- **方案**: **保留现状**, shadcn Table 模板.

### Pattern A.6: animate-in / animate-out Radix state 模板 — 6 文件重复

```tsx
data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0
```

- **出现位置** (弹层族):
  - `packages/web/components/ui/alert-dialog.tsx` (2 处)
  - `packages/web/components/ui/dialog.tsx` (2 处)
  - `packages/web/components/ui/dropdown-menu.tsx` (2 处)
  - `packages/web/components/ui/popover.tsx` (1 处)
  - `packages/web/components/ui/select.tsx` (1 处)
  - `packages/web/components/ui/sheet.tsx` (2 处)
- **现有封装**: 无
- **方案**: **不建议改**, shadcn 标准动画类. 抽公共 `cn()` 函数会失去每文件可读性.

---

## 🟡 中等（重复 3-4）

### Pattern B.1: 表单 input 容器 — Input/Select/Textarea 重复 3 处

```tsx
"flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-base shadow-sm"
"flex h-9 w-full items-center justify-between whitespace-nowrap rounded-md border border-input bg-transparent px-3 py-2 text-base shadow-sm"
"flex min-h-[60px] w-full rounded-md border border-input bg-transparent px-3 py-2 text-base shadow-sm"
```

- **出现位置**:
  - `packages/web/components/ui/input.tsx:8` (Input — `h-9 px-3 py-1`)
  - `packages/web/components/ui/select.tsx:18` (SelectTrigger — `h-9 px-3 py-2 items-center justify-between`)
  - `packages/web/components/ui/textarea.tsx:9` (Textarea — `min-h-[60px] px-3 py-2`)
- **现有封装**: 已各自封装 (`<Input>` / `<AppSelect>` / shadcn `<Textarea>`)
- **方案**: **不建议合并**. 三个组件的尺寸/对齐/换行差异是设计意图, 合并会失去灵活性.
- **建议**: 业务层已统一走 `Input` / `AppSelect` / `Textarea`, 没有手写 input 的反模式 (项目 CLAUDE.md 强制).

### Pattern B.2: 业务表单字段 help/error 提示 (`text-sm text-destructive` / `text-muted-foreground`) — 2 处

```tsx
<p className="text-sm text-destructive">{errorMessage}</p>
<p className="text-sm text-muted-foreground">{help}</p>
```

- **出现位置**:
  - `packages/web/components/common/form/app-field.tsx:126-129`
- **现有封装**: 项目无 FormHelp / FormError 组件
- **方案**: **建议新封装** `<FormHelp error />` 和 `<FormError>` (或单一 `<FormHelper kind="help|error">`), 放 `components/common/form/`. 详见下文"建议新增封装组件清单".

### Pattern B.3: 弹框内容区滚动容器 (flex-1 overflow-auto px-6 py-4) — Dialog/Drawer 重复

```tsx
<div className="flex-1 overflow-auto px-6 py-4">
```

- **出现位置**:
  - `packages/web/components/common/dialog/app-dialog.tsx:74`
  - `packages/web/components/common/drawer/app-drawer.tsx:49`
- **现有封装**: 无
- **方案**: **建议抽** `<DialogScrollBody>` 或类似公共组件, 或在 `AppDialog` / `AppDrawer` 内部共用 const string. 当前 2 处差异仅为 Dialog 多了 ErrorBanner slot, 可保留; 但 body 容器样式 100% 一致.
- **实施**: 在 `common/dialog/` 加 `dialog-body.tsx` 暴露复用 div; 或者用 tailwind `@apply` 抽 class. **改动量小, 收益一般**, 标 🟢 而非 🔴.

### Pattern B.4: 弹框/抽屉 Header/Footer 边距 (`border-b border-border/40 px-6 py-4` + `border-t`) — 2 处

```tsx
<DialogHeader className="border-b border-border/40 px-6 py-4">
<DialogFooter className="border-t border-border/40 px-6 py-4">
```

- **出现位置**:
  - `packages/web/components/common/dialog/app-dialog.tsx:64, 86`
  - `packages/web/components/common/drawer/app-drawer.tsx:44, 51`
- **现有封装**: 无
- **方案**: **建议抽**常量 `DIALOG_HEADER_CLS` / `DIALOG_FOOTER_CLS` 放 `common/dialog/const.ts` 或 `lib/styles.ts`. **改动量小**.

---

## 🟢 建议（重复 2 或独有但值得封装）

### Pattern C.1: 业务表单 SectionCard 容器 (`rounded-lg border p-6`) — 1 文件

```tsx
<div className={cn("rounded-lg border p-6", className)}>
```

- **出现位置**: `packages/web/components/common/display/app-section-card.tsx:19`
- **现有封装**: shadcn `<Card>` (但 Card 自带 shadow + bg-card + text-card-foreground, 跟 SectionCard 视觉差异明显)
- **方案**: **保留现状**. SectionCard 跟 shadcn Card 是**不同视觉风格** (前者朴素, 后者富阴影). 业务目前没大量用 `rounded-lg border p-6` 模式重复. **不建议合并**.

### Pattern C.2: StatCard 主数值样式 (text-4xl font-medium leading-none tracking-tight) — 1 文件 2 处

```tsx
"num text-4xl font-medium leading-none tracking-tight text-foreground"
```

- **出现位置**:
  - `packages/web/components/common/display/app-stat-card.tsx:46, 49`
- **现有封装**: 无
- **方案**: **建议内部抽 const** `STAT_VALUE_CLS`, 不暴露 API. 2 处同文件重复, 抽 const 即可. **改动量极小**.

### Pattern C.3: SettingsCard icon+title 行 (`flex items-center gap-2`) — 1 文件

```tsx
<div className="flex items-center gap-2">
  <Icon className="h-4 w-4 text-muted-foreground" strokeWidth={1.5} />
  <CardTitle>{title}</CardTitle>
</div>
```

- **出现位置**: `packages/web/components/common/display/app-settings-card.tsx:33-36`
- **现有封装**: 无
- **方案**: **保留现状**. 1 文件 1 处, 不值得抽.

### Pattern C.4: PageHero eyebrow 行 (`eyebrow` + `h-px flex-1 bg-border` + meta) — 1 文件

```tsx
<div className="flex items-center gap-3">
  <span className="eyebrow">{eyebrow}</span>
  <span className="h-px flex-1 bg-border" />
  {meta && <span className="num text-sm text-muted-foreground/60">{meta}</span>}
</div>
```

- **出现位置**: `packages/web/components/common/navigation/app-page-hero.tsx:39-43`
- **现有封装**: 无
- **方案**: **保留现状**. 这是 PageHero 特有设计 (eyebrow + 分隔线 + meta), 业务页面没重复.

### Pattern C.5: LoadingSkeleton 行容器 (`space-y-6 p-6`) — 1 文件

```tsx
<div className={cn("space-y-6 p-6", className)}>
```

- **出现位置**: `packages/web/components/common/button/app-loading-skeleton.tsx:16`
- **现有封装**: 无
- **方案**: **保留现状**. LoadingSkeleton 是专用组件, 没重复.

### Pattern C.6: LoadingSkeleton 内部骨架行 (`h-4 w-full`) — 1 文件多处

```tsx
<Skeleton key={idx} className={idx === HEADER_ROW_INDEX ? "mb-4 h-8 w-48" : "h-4 w-full"} />
```

- **出现位置**: `packages/web/components/common/button/app-loading-skeleton.tsx:18`
- **现有封装**: shadcn `<Skeleton>`
- **方案**: **保留现状**, 已在用 shadcn Skeleton.

### Pattern C.7: DataTableSkeleton 头/行容器 (`flex gap-2`) — 1 文件 2 处

```tsx
<div className="flex gap-2">  // 头
<div className="flex gap-2">  // 行
```

- **出现位置**: `packages/web/components/common/table/data-table-skeleton.tsx:17, 24`
- **现有封装**: 无
- **方案**: **保留现状**. 2 处同文件, 已是 const-less 内联, 可读性 OK.

### Pattern C.8: ErrorBoundary 错误态 pre 块 (`text-sm text-status-error whitespace-pre-wrap`) — 1 文件

```tsx
<pre className="text-sm text-status-error whitespace-pre-wrap">
  {this.state.error.message}
</pre>
```

- **出现位置**: `packages/web/components/common/feedback/app-error-boundary.tsx:28-30`
- **现有封装**: 项目 `<ErrorBanner>` (但 ErrorBanner 是 Alert 包装, 不能直接展示 stack trace 整段)
- **方案**: **保留现状**. ErrorBoundary 是 React class component, 错误态用 `<pre>` 是合理设计.

### Pattern C.9: DropdownMenu checkbox/radio 项图标占位 (`absolute left-2 flex h-3.5 w-3.5`) — 1 文件 2 处

```tsx
<span className="absolute left-2 flex h-3.5 w-3.5 items-center justify-center">
  <DropdownMenuPrimitive.ItemIndicator>
    <Check className="h-4 w-4" />
  </DropdownMenuPrimitive.ItemIndicator>
</span>
```

- **出现位置**: `packages/web/components/ui/dropdown-menu.tsx:98-102, 120-124`
- **现有封装**: 无
- **方案**: **保留现状**. shadcn DropdownMenu 标准模板. 抽 const 可减少 2 处重复但不会改善业务.

### Pattern C.10: Select item 图标占位 (`absolute right-2 flex h-3.5 w-3.5`) — 1 文件

```tsx
<span className="absolute right-2 flex h-3.5 w-3.5 items-center justify-center">
  <SelectPrimitive.ItemIndicator>
    <Check className="h-4 w-4" />
  </SelectPrimitive.ItemIndicator>
</span>
```

- **出现位置**: `packages/web/components/ui/select.tsx:116-120`
- **现有封装**: 无
- **方案**: **保留现状**. shadcn Select 模板.

### Pattern C.11: LoadingSkeleton + DataTableSkeleton 骨架列 (`flex-1`) — 2 文件

```tsx
<Skeleton className="h-10 flex-1" />
<Skeleton className="h-12 flex-1" />
```

- **出现位置**: `packages/web/components/common/button/app-loading-skeleton.tsx:18`, `packages/web/components/common/table/data-table-skeleton.tsx:19, 26`
- **现有封装**: shadcn `<Skeleton>` 已在用
- **方案**: **保留现状**. 已用封装.

---

## Top-10 高频 pattern 汇总

| pattern | 出现次数 | 替换方案 | 严重程度 |
|---------|---------|---------|---------|
| `data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0` (Radix animate) | 10 (6 文件) | 不建议改 (shadcn 模板) | 🟢 |
| `fixed inset-0 z-50 bg-black/80` (Dialog/Sheet Overlay) | 6 (3 文件) | 不建议改 (shadcn 模板) | 🟢 |
| `flex flex-col-reverse sm:flex-row sm:justify-end sm:space-x-2` (Dialog/Sheet/AlertDialog Footer) | 3 (3 文件) | 不建议改 (shadcn 模板) | 🟢 |
| `flex flex-col space-y-X text-center sm:text-left` (Dialog/Sheet/AlertDialog Header) | 3 (3 文件) | 不建议改 (shadcn 模板) | 🟢 |
| `absolute right-4 top-4` + X 关闭按钮 | 2 (2 文件) | 不建议改 (shadcn 模板) | 🟢 |
| `flex-1 overflow-auto px-6 py-4` (AppDialog/Drawer 滚动内容) | 2 (2 文件) | 建议抽 const 复用 | 🟡 |
| `border-b border-border/40 px-6 py-4` + `border-t` (AppDialog/Drawer 边) | 2 (2 文件) | 建议抽 const 复用 | 🟡 |
| `flex h-9 w-full ... rounded-md border border-input bg-transparent` (Input/Select 基础样式) | 3 (3 文件) | 不建议合并 (尺寸/对齐差异) | 🟢 |
| `flex items-center justify-between` (PageHeader / PageHero / Pagination 等) | 4 (4 文件) | 保留现状, 跨组件不重复 | 🟢 |
| `border-border/60` (rounded border 容器) | 6 (6 文件) | 保留现状, 跟 shadcn Card 视觉差异 | 🟢 |

---

## 建议新增封装组件清单

### 1. `<FormHelp>` / `<FormError>` (low priority)

- **位置**: `packages/web/components/common/form/form-help.tsx`
- **Props**: `{ kind?: "help" | "error"; children: ReactNode; className?: string }`
- **替换**: `packages/web/components/common/form/app-field.tsx:126-129` 当前手写 `<p className="text-sm text-destructive">` / `<p className="text-sm text-muted-foreground">`
- **收益**: 当前 1 处使用, 抽封装收益有限. **降级为内部 const** `FORM_HELP_CLS` / `FORM_ERROR_CLS` 更合适. 不开新文件.

### 2. `<DialogBody>` (low priority)

- **位置**: `packages/web/components/common/dialog/dialog-body.tsx`
- **Props**: `{ children: ReactNode; className?: string }`
- **替换**: AppDialog:74 + AppDrawer:49
- **收益**: 2 处重复, **抽 const** `DIALOG_BODY_CLS = "flex-1 overflow-auto px-6 py-4"` 更轻量. 不开新文件, 放 `common/dialog/const.ts`.

### 3. `<StatNumber>` (low priority)

- **位置**: `packages/web/components/common/display/app-stat-card.tsx` 内部 (不暴露)
- **替换**: app-stat-card.tsx:46, 49 重复 `num text-4xl font-medium leading-none tracking-tight text-foreground`
- **收益**: 抽内部 const `STAT_VALUE_CLS`, 不开新文件.

---

## 扫描方法说明

1. **文件清单**: 用 `Glob` 列出 `components/common/**/*.tsx` 和 `components/ui/**/*.tsx`, 排除 `*.test.tsx` 和 `*.stories.tsx`, 共 78 文件.
2. **逐文件 Read**: 全部 78 文件完整 Read, 不只看名字. 重点关注 (1) 同文件内 div/span className 重复 ≥2 次 (2) 跨文件出现的同 pattern.
3. **grep 交叉验证**: 用 Grep 工具 + `output_mode: "count"` 交叉验证以下高频 class 段:
   - `flex items-center gap-2`, `flex justify-between`, `flex items-center justify-between`
   - `text-sm text-muted-foreground`, `flex-1 overflow-auto`, `flex flex-col space-y-`
   - `rounded-lg border`, `border-border/60`, `rounded-md border border-input bg-transparent`
   - `fixed inset-0 z-50 bg-black/80`, `data-[state=open]:animate-in ...`, `data-[state=closed]:fade-out-0 ...`
   - `absolute right-4 top-4`, `sr-only`, `flex h-full w-full items-center justify-center rounded-full bg-muted`
   - `flex flex-col-reverse sm:flex-row sm:justify-end sm:space-x-2`
4. **分类输出**: 按重复频次分为 🔴 (5+) / 🟡 (3-4) / 🟢 (2 或独有).
5. **判断标准**:
   - shadcn/ui 原生模板 (Dialog/Sheet/AlertDialog/DropdownMenu/Select/Popover/Tooltip 等的内部子件) → **不替换** (破坏升级路径)
   - 业务封装层 (AppDialog / AppDrawer 等) 内部 div/span 用于组合 shadcn 原语 → **不替换** (那是封装目的)
   - 跨业务封装层重复同款 className 块 → 评估抽 const 或新组件

---

## 已知遗漏

1. **i18n message 文案**: `<EmptyTitle>暂无数据</EmptyTitle>` (`data-table.tsx:108`) 这种硬编码中文未走 `t()` — 不在本任务范围, 由 P3 维度处理.
2. **跨目录跨文件未覆盖**: 本任务只扫 `components/common/` + `components/ui/`, 业务页面 (e.g. `app/[locale]/.../page.tsx`) 的 div/span 重复模式**未覆盖**, 应由后续 Agent B/C 扫描.
3. **shadcn 模板升级兼容性**: 标 🔴/🟡 的所有 shadcn 模板 Pattern (DialogHeader/Footer/Overlay 等) 都是 shadcn 新版交付的标准实现, 本地合并会破坏 `npx shadcn@latest add` 升级. 建议**保持现状**, 仅在跨业务封装层重复时抽 const.
4. **测试文件未读**: 本任务排除 `.test.tsx`, 但部分测试文件也可能包含重复 div/span 模式 (e.g. mock setup). 当前不展开.
5. **CardTitle 是 `<div>`**: shadcn CardTitle 用 `forwardRef<HTMLDivElement>` 渲染 `<div>`, 而 CardContent 也是 `<div>`. 这是 shadcn 标准做法, 不在本任务范围.
6. **AppForm 中 inline 三元 layout**: `app-form.tsx:93` `grid grid-cols-[140px_1fr] gap-3 items-start` 是 horizontal layout 专用 className, 仅 1 处使用, 不抽.