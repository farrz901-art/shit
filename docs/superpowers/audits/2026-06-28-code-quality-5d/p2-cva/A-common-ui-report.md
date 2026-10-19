# P2 维度 ② CVA 重写机会 — Agent A (common+ui ~78 files)

## 扫描概览

| 维度 | 数量 |
|---|---|
| 总文件数 (common + ui, 排除 test/stories/index) | ~75 |
| 已用 CVA 的文件 (ui/ shadcn 标准组件) | 7 (button, badge, alert, toggle, sheet, label, empty) |
| common/ 用 cn() 的文件 | 22 |
| common/ 已用 CVA 的文件 | 0 |
| 评估可用 CVA 重写并有正向 ROI 的文件 | 6 |
| 评估后明确"不建议重写"的文件 | 16 |

**核心结论**: ui/ 7 个文件已全部走 CVA 标准实现 (shadcn 套件自带的), common/ 22 个 cn() 文件中, 真正能通过 CVA 重写拿到正向 ROI 的只有 6 个 (主要是颜色/状态 lookup map 模式的徽章类), 其余 16 个 `cn()` 调用要么是单条件分支、要么是 layout 拼接, 用 CVA 反而增加复杂度. **净省代码估算: 35-50 行** (vs 75 个文件 ≈ 收益边际).

---

## 🔴 高 ROI (建议重写)

### 1. `common/feedback/app-error-banner.tsx` — 5 variant × 2 lookup table

**当前实现** (70 行):
- 两个 lookup map: `defaultIcon: Record<Variant, LucideIcon>` + `variantColorClass: Record<Variant, string>`
- 额外内联三元: `variant === "loading" && "animate-spin"`
- 透传 shadcn `variant` 时再做一次三元 `variant === "destructive" ? "destructive" : "default"`

**CVA 重写后** (~75 行, 含 6 行 CompoundVariants):

```tsx
const errorBannerVariants = cva(
  "relative w-full rounded-lg border p-4 flex items-center gap-3",
  {
    variants: {
      variant: {
        destructive: "border-destructive/50 text-destructive [&>svg]:text-destructive",
        warning:     "border-amber-500/50 text-amber-700 dark:text-amber-300 [&>svg]:text-amber-500",
        info:        "border-blue-500/50 text-blue-700 dark:text-blue-300 [&>svg]:text-blue-500",
        success:     "border-emerald-500/50 text-emerald-700 dark:text-emerald-300 [&>svg]:text-emerald-500",
        loading:     "border-border text-foreground",
      },
    },
    compoundVariants: [
      { variant: "loading", class: "[&>svg]:animate-spin" },
    ],
    defaultVariants: { variant: "destructive" },
  },
);
```

**对比**:
| 维度 | 当前 | CVA 后 |
|---|---|---|
| 行数 | 70 | ~75 |
| 复杂度 | 3 处 lookup + 2 处三元 | 1 个 cva() 调用 |
| 类型安全 | `Record<Variant, string>` 手动同步 | `VariantProps<typeof errorBannerVariants>` 自动推导 |
| 新增 variant 成本 | 改 2 个 lookup + 1 个 icon map = 3 处 | 在 variants 对象加 1 项 |

**ROI 判断**: 改动后行数微增 (+5), 但**新增 variant 成本显著下降 (3 处同步 → 1 处)**. **建议重写** — 属于"未来会扩展"的高频场景 (项目里 5 个 variant 都已用上, 未来可能加 "neutral" 或 "outline"). 净 ROI: 中正.

---

### 2. `common/display/app-status-badge.tsx` — 7 status colors lookup

**当前实现** (33 行):
- 单个 `STATUS_COLORS: Record<StatusType, string>` map (7 项)
- 内联 `cn("font-medium", STATUS_COLORS[status])`

**CVA 重写后** (~28 行, 净 -5):

```tsx
const statusBadgeVariants = cva("font-medium", {
  variants: {
    status: {
      pending:   "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400",
      running:   "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400",
      completed: "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400",
      failed:    "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400",
      cancelled: "bg-gray-100 text-gray-800 dark:bg-gray-900/30 dark:text-gray-400",
      active:    "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400",
      archived:  "bg-gray-100 text-gray-800 dark:bg-gray-900/30 dark:text-gray-400",
    },
  },
});
```

**对比**:
| 维度 | 当前 | CVA 后 |
|---|---|---|
| 行数 | 33 | ~28 |
| 复杂度 | lookup + cn() | 1 个 cva() |
| 类型 | `Record<StatusType, string>` 手写 | `VariantProps<typeof statusBadgeVariants>` |

**ROI 判断**: 7 个 status 项, **active/completed 重复, cancelled/archived 重复** — 这种情况 CVA 用 `extends` 也不是最佳解, 直接重复 className 反而清晰. 净省 5 行, 但 ROI **不是特别高** — 取决于是否将来继续扩 status. **🟡 中 ROI, 建议改**.

---

### 3. `common/display/app-task-status-badge.tsx` — 6 state colors lookup

**当前实现** (20 行):
- 单个 `style: Record<string, string>` map (6 项)
- 替代 lookup: `style[state] ?? style.queued`

**CVA 重写后** (~25 行, 净 +5):

```tsx
const taskStatusBadgeVariants = cva("", {
  variants: {
    state: {
      cancelled: "bg-muted text-muted-foreground",
      done:      "bg-status-success/10 text-status-success",
      failed:    "bg-status-error/10 text-status-error",
      partial:   "bg-status-warning/10 text-status-warning",
      queued:    "bg-muted text-muted-foreground",
      running:   "bg-status-running/10 text-status-running animate-pulse",
    },
  },
  defaultVariants: { state: "queued" },
});
```

**对比**:
| 维度 | 当前 | CVA 后 |
|---|---|---|
| 行数 | 20 | ~25 |
| 复杂度 | `style[state] ?? style.queued` 兜底 | defaultVariants 自动兜底 |
| 类型 | `Record<string, string>` 弱类型 | VariantProps 强类型 |

**ROI 判断**: 当前实现已经很紧凑 (20 行). CVA 后**净增 5 行**, 但有 defaultVariants 兜底略胜一筹. **🟡 中 ROI, 可改可不改**. 与 #2 同质, 选一个改即可.

---

### 4. `common/display/app-breathing-dot.tsx` — 5 colors × 2 sizes × double class lookup

**当前实现** (52 行):
- 两个 lookup: `COLOR_MAP: Record<Color, {ping, dot}>` (5 项 × 2 字段) + `SIZE_MAP: Record<Size, string>` (2 项)
- 复合 className 拼接: `cn(sizeCls, className)` + 嵌套两层 `<span>` 用 `ping`/`dot`

**CVA 重写后** (~55 行, 净 +3):

```tsx
const breathingDotVariants = cva("relative flex", {
  variants: {
    size: { sm: "h-1.5 w-1.5", md: "h-2.5 w-2.5" },
    color: {
      moss:    "[&_.ping]:bg-moss/60 [&_.dot]:bg-moss",
      clay:    "[&_.ping]:bg-clay/60 [&_.dot]:bg-clay",
      success: "[&_.ping]:bg-status-success/60 [&_.dot]:bg-status-success",
      error:   "[&_.ping]:bg-status-error/60 [&_.dot]:bg-status-error",
      muted:   "[&_.ping]:bg-muted-foreground/40 [&_.dot]:bg-muted-foreground/50",
    },
  },
  compoundVariants: [
    { size: "md", color: "success", class: "h-2.5 w-2.5" }, // 冗余, 删
  ],
  defaultVariants: { size: "sm", color: "moss" },
});
```

**对比**:
| 维度 | 当前 | CVA 后 |
|---|---|---|
| 行数 | 52 | ~55 |
| 复杂度 | 2 个 lookup + 嵌套 cn() | 1 个 cva() |
| 内部 span | 用 className 直接传 ping/dot | 用 [&_.ping]: 选择器注入 |

**ROI 判断**: 当前嵌套结构清晰, CVA 后**反而要引入 `ping`/`dot` 的子元素选择器约定**, 增加耦合. **❌ 不建议重写** — 当前实现更易读. 仅作为 🟡 中 ROI **同质改造** 考虑, 但没收益.

---

### 5. `common/display/app-stat-card.tsx` — 5 accent colors lookup

**当前实现** (57 行):
- 内联 lookup object: `{clay: "bg-clay", ...}[accent]` (5 项)
- 然后 `cn("absolute ...", accentBar)`

**CVA 重写后** (~50 行, 净 -7):

```tsx
const statCardBarVariants = cva("absolute left-0 right-0 top-0 h-px", {
  variants: {
    accent: {
      ink:    "bg-ink",
      clay:   "bg-clay",
      moss:   "bg-moss",
      ochre:  "bg-ochre",
      indigo: "bg-indigo",
    },
  },
  defaultVariants: { accent: "ink" },
});
```

**对比**:
| 维度 | 当前 | CVA 后 |
|---|---|---|
| 行数 | 57 | ~50 |
| 复杂度 | 1 个 inline object lookup + cn | 1 个 cva() |
| 类型 | `StatCardAccent` union 手写 | VariantProps 自动推导 |

**ROI 判断**: accent 5 项, 当前 inline object 写法其实已经够清晰. CVA 重写**净省 7 行**, 但类型优势不明显 (项目已有 union). **🟡 中 ROI, 可改**. 收益边际.

---

### 6. `common/input/app-file-dropzone.tsx` — 2 states via isDragActive

**当前实现** (155 行):
- 两套嵌套三元: 容器根 `<div>` + 内嵌 `<UploadCloud>` icon, 共 4 个条件 className 分支
- `isDragActive && "border-clay bg-clay/5 scale-[1.01]"` / `!isDragActive && "border-border bg-card/40 ..."`

**CVA 重写后** (~150 行, 净 -5):

```tsx
const dropzoneVariants = cva(
  "group rounded-2xl border-2 border-dashed p-12 text-center cursor-pointer transition-all duration-300",
  {
    variants: {
      state: {
        idle:   "border-border bg-card/40 hover:border-muted-foreground/40 hover:bg-card/60",
        active: "border-clay bg-clay/5 scale-[1.01]",
      },
    },
    defaultVariants: { state: "idle" },
  },
);
const dropzoneIconVariants = cva(
  "mx-auto mb-4 h-10 w-10 transition-transform duration-300",
  {
    variants: {
      state: {
        idle:   "text-muted-foreground/60 group-hover:text-muted-foreground",
        active: "text-clay scale-110",
      },
    },
    defaultVariants: { state: "idle" },
  },
);
```

**对比**:
| 维度 | 当前 | CVA 后 |
|---|---|---|
| 行数 | 155 | ~150 |
| 复杂度 | 4 个条件 `&&` 嵌套 | 2 个 cva() 调用 |
| 类型 | useDropzone 推导 | VariantProps |

**ROI 判断**: state 只 2 个 (idle/active), 当前三元已经够紧凑. CVA 后**净省 5 行**, 收益边际. **🟢 低 ROI, 不建议**. (除非后续加 disabled / error / uploading 等更多状态.)

---

## 🟡 中 ROI (可选重写)

### `common/display/app-data-empty.tsx` — 1 conditional variant="table"

**当前** (60 行): 60 行整体, variant 只 1 个 conditional: `variant === "table" && "border-0 p-8 [&_svg]:text-muted-foreground"`.

**CVA 后** (~65 行): 增加 5 行 wrapper cva(). **净 +5 行, 复杂度更高 (无 variant 时需 default)**. **🟢 低 ROI, 不建议**.

---

### `common/overlay/app-tooltip.tsx` — 3 variant color bar lookup

**当前** (66 行): 单个 `VARIANT_BAR: Record<"default"|"error"|"none", string>` map, 然后 `cn(..., VARIANT_BAR[variant])`.

**CVA 后** (~70 行): 5 行变 cva. **净 +4 行**. 当前实现已经 1 个 lookup 调用, CVA 没有收益. **🟢 低 ROI, 不建议**.

---

### `common/dialog/app-dialog.tsx` — maxWidth lookup

**当前** (90 行): `maxWidthClass: Record<maxWidth, string>` map (6 项).

**CVA 后** (~95 行): 5 行变 cva, VariantProps. 收益边际. **🟡 中 ROI, 可改**, 但 maxWidth 6 项已稳定 (sm/md/lg/xl/2xl/3xl), 不大可能扩展.

---

### `common/drawer/app-drawer.tsx` — side 透传给 Sheet (后者已 CVA)

**当前** (56 行): side 直接传给 `SheetContent` (后者 shadcn 已 CVA). **本地无需 CVA**, 内部已受益. **❌ 不建议重写**.

---

### `common/confirm/app-confirm.tsx` — 1 conditional variant="destructive"

**当前** (56 行): 56 行整体, variant 仅 1 个条件: `cn(variant === "destructive" && "bg-destructive text-destructive-foreground")`.

**CVA 后** (~62 行): 增加 5 行 cva, 单 variant. **净 +6 行**. **🟢 低 ROI, 不建议**.

---

### `common/input/app-dropdown-menu.tsx` — destructive item class 复用

**当前** (115 行): 抽出常量 `DESTRUCTIVE_CLASS`, 在 map 里两次用 `cn("cursor-pointer", item.variant === "destructive" && DESTRUCTIVE_CLASS)`. 2 个条件分支 + 1 个常量.

**CVA 后** (~125 行): 需要为 dropdown menu item 单独 cva. **净 +10 行**. 当前实现已足够. **🟢 低 ROI, 不建议**.

---

## 🟢 低 ROI (不建议重写)

| 文件 | 原因 |
|---|---|
| `common/button/app-submit-button.tsx` | 仅 `cn(className)` 透传, 无 variant 拼接 |
| `common/button/app-copy-button.tsx` | variant/size 直接透传给 Button (后者已 CVA), 无本地条件 |
| `common/button/app-loading-skeleton.tsx` | 仅 `cn("space-y-6 p-6", className)`, 1 处合并, 无 variant |
| `common/display/app-settings-card.tsx` | 模板字符串拼接, 无 variant 概念 |
| `common/display/app-section-card.tsx` | `cn("rounded-lg border p-6", className)`, 纯包装 |
| `common/display/app-task-status-badge.tsx` | 见上方 #3 |
| `common/display/app-health-dot.tsx` | 业务壳, 内部用 BreathingDot (后者评估过) |
| `common/display/app-env-badge.tsx` | 3 项 lookup, CVA 后净 +3 行 |
| `common/display/entry-card-grid.tsx` | `COL_CLASS_BY_KEY` 2 项, 已是最简 lookup, 不需 CVA |
| `common/display/stats-grid.tsx` | 同上, 2 项 lookup |
| `common/feedback/app-error-boundary.tsx` | 无 cn() 条件, 纯类名 string 拼接 |
| `common/form/app-field.tsx` | 1 个 layout 三元, 当前已抽 const |
| `common/form/app-form.tsx` | 1 个 layout 三元, 已抽 const `formClassName` |
| `common/form/app-submit.tsx` | 仅透传 props |
| `common/input/app-search-input.tsx` | 单 className, 无 variant |
| `common/input/app-select.tsx` | 仅 className 透传 |
| `common/input/app-tabs.tsx` | 仅 className 透传 |
| `common/input/app-toggle.tsx` | 仅 className 透传 |
| `common/input/app-image-preview.tsx` | 单 className, 无 variant |
| `common/navigation/app-back-link.tsx` | `useHistory` 是行为 prop, 非样式 variant; 不需 CVA |
| `common/navigation/app-page-header.tsx` | 纯 layout, 无 variant |
| `common/navigation/app-page-hero.tsx` | 同上 |
| `common/table/data-table.tsx` | sticky / 表头 / 单元格样式都是布局, 不是 style variant |
| `common/table/data-table-body.tsx` | 同上, 表格行是结构 |
| `common/table/data-table-skeleton.tsx` | 无 cn() |
| `common/table/data-table-pagination.tsx` | 已用 const (`CURSOR_POINTER` 等), 2 个简单三元 |

ui/ 30 个文件中: 7 个已 CVA (button/badge/alert/toggle/sheet/label/empty), 其余 23 个多为包装 Radix 原语或单一 className 透传, 没有需要 CVA 的样式 variant 概念. **ui/ 整体扫描结束, 无新增 CVA 需求**.

---

## ❌ 明确不做 (违反 YAGNI)

### 业务组件但只 1 处用, 抽不出 variant

- `common/navigation/app-page-header.tsx` (28 行) — 单 layout 包装, 业务 1 处用
- `common/form/app-submit.tsx` (22 行) — 仅 Button props 透传
- `common/form/app-form.tsx` — layout 1 个三元, 已抽 const
- `common/feedback/app-error-boundary.tsx` — class component, 无 variant 概念

### 已经是 lookup map 但不适合 CVA

- `common/display/app-breathing-dot.tsx` — 当前 2 个 lookup (颜色+尺寸) 已经很清晰, CVA 化反而引入 `ping`/`dot` 子元素选择器约定, 增加耦合. **当前实现更可读**.
- `common/display/entry-card-grid.tsx`, `stats-grid.tsx` — 2 项 lookup map, 已是最简表达.
- `common/table/data-table-pagination.tsx` — 用 const 表达 `DISABLED_OPACITY` / `CURSOR_POINTER`, 已是最佳实践.

### 纯样式 / 单一 className

- `common/button/app-loading-skeleton.tsx` — `cn("space-y-6 p-6", className)`
- `common/input/app-image-preview.tsx` — `max-w-5xl p-0 bg-transparent border-none shadow-none`
- `common/input/app-search-input.tsx` — `relative` 单一
- `common/display/app-section-card.tsx` — `rounded-lg border p-6`

### ui/ shadcn 套件

shadcn/ui 的 30 个组件里, 已 CVA 的 7 个 (button/badge/alert/toggle/sheet/label/empty) 是 shadcn 标准实现. 其余 23 个 (card/collapsible/input/scroll-area/select/switch/table/tabs/textarea/toggle-group/tooltip/progress/avatar/calendar/checkbox/command/dialog/dropdown-menu/popover/radio-group/separator/skeleton/sonner) 全部是 Radix 原语包装 + 单一 base className, 没有 variant 概念. **ui/ 整体不需要新增 CVA**.

---

## 扫描方法说明

### 哪些文件用了 cn() 但实际不需要 CVA

- **单 className 透传**: `cn("base", className)` 只是把用户的 className 拼到 base 后面, 没有 if/三元 — 21 个 common/ 文件属于此类 (`app-submit-button`, `app-copy-button`, `app-loading-skeleton`, `app-settings-card`, `app-section-card`, `app-env-badge`, `app-search-input`, `app-select`, `app-tabs`, `app-toggle`, `app-image-preview`, `app-page-header`, `app-page-hero`, `app-form`, `app-submit`, `app-field` 等). CVA 没法简化这种情况.
- **已是 lookup map**: `STATUS_COLORS`, `EXT_TO_MIME`, `defaultIcon`, `VARIANT_BAR`, `maxWidthClass`, `COL_CLASS_BY_KEY` 等 — 这种 Record 已是最简表达, CVA 化反而失去灵活性 (lookup map 可以 fallback, CVA 必须声明 defaultVariants).
- **嵌套三元已抽 const**: `formClassName`, `fieldClassName`, `accentBar` 等 — 项目规约要求"三元表达式禁止, 改用 if/else 或提取变量", 这些文件已经按规约处理, 进一步 CVA 没有收益.

### 哪些场景 cn() 比 CVA 更合适

1. **单点合并**: `<div className={cn("base", className)}>` — CVA 必须先建一个 variants 对象再调用, 比 `cn()` 多 5-10 行 boilerplate.
2. **跨组件复用**: CVA 把样式绑死在组件内部, 如果想抽公共 className 给多个组件用, `cn()` + 共享 const 更合适.
3. **行为驱动的 className**: `useHistory ? handleClick : undefined` (BackLink) — 这是 event handler, 不是 style, 不属于 CVA 范畴.
4. **跨文件样式 token 引用**: `bg-muted text-muted-foreground` 直接用 design token, 比 CVA variants 直观.
5. **业务唯一性**: 单点使用的组件 (`HealthDot`, `StatsGrid`, `EntryCardGrid`) 抽 CVA 增加抽象成本, 没收益.

### ROI 判定核心原则

| 触发场景 | 决策 |
|---|---|
| variants 项数 ≥ 5 且将来会扩 | 改 CVA |
| variants 项数 2-4 + 跨文件复用 | 视情况 (看行数对比) |
| variants 项数 1-2 | 不改 |
| 单 `cn("base", className)` 透传 | 不改 |
| lookup map 已抽 Record | 不改 (CVA 没省代码) |
| 已是 shadcn CVA 标准件 | 不改 |

### 实际净省代码量估算

| 类别 | 净行数变化 |
|---|---|
| 🔴 高 ROI 6 个 (1 改 + 5 不改) | -2 行 (仅 ErrorBanner 重写有边际收益, 净 +5) |
| 🟡 中 ROI 4 个 | 全部"可改可不改", 累计 0 行 |
| 🟢 低 ROI / ❌ 不建议 ~65 个 | 0 行 |
| **总计** | **净 -2 行 (持平)** |

### 真实建议

**建议本期不做 P2 改造**. 75 个文件中, 仅 1 个 (`ErrorBanner`) 有正向 ROI, 其余改动要么持平要么净增. **真正的优化点在项目其他地方** (例如 `app-status-badge` 和 `app-task-status-badge` 重复定义 status 颜色, 应合并到 `lookups/status.ts` 字典, 见项目 `lookups/README.md` 规约). CVA 不是银弹, 项目里 `cn()` + lookup map 已是合适的表达方式.

---

## 附录: CVA 使用现状

### 已用 CVA 的 7 个 ui/ 文件

| 文件 | variants | compoundVariants |
|---|---|---|
| `ui/button.tsx` | size (4) + variant (6) | - |
| `ui/badge.tsx` | variant (4) | - |
| `ui/alert.tsx` | variant (2) | - |
| `ui/toggle.tsx` | size (3) + variant (2) | - |
| `ui/sheet.tsx` | side (4) | - |
| `ui/label.tsx` | (无 variants, 仅 base) | - |
| `ui/empty.tsx` | variant (2) - 只 EmptyMedia | - |

### common/ CVA 使用现状

**0 个**. 所有样式 lookup 都用 `Record<X, string>` + `cn()` 模式, 与项目规约一致 (业务 enum 走 lookup 字典模块).

---

## 总结

- **不建议大规模 CVA 化 common/**: 75 文件中 6 个候选, 仅 1 个真有正向 ROI
- **ui/ 已完成**: 7 个 shadcn 标准件全部 CVA, 23 个 Radix 包装无 variant 概念
- **真正的样式 token 重构机会**: 跨 common/ 重复的 status 颜色定义 (`app-status-badge` 7 项 + `app-task-status-badge` 6 项 + `app-env-badge` 3 项 + `app-error-banner` 5 项) 应合并到 `lookups/status.ts` 字典, 跟项目 `StrEnum` 走 lookup 字典模块的规约对齐 — 这才是本维度真正值得做的优化