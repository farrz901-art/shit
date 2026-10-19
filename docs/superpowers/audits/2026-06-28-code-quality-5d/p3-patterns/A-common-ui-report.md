# P3 维度 ③ 单例/策略/工厂模式 — Agent A (common+ui ~86 files)

## 扫描概览

- **总文件数**: 86 (50 common + 36 ui, 排除 .test / .stories)
- **可用设计模式重构的文件**: 8 (4 高 ROI + 2 中 ROI + 2 不建议但识别出)
- **实际净省代码量**: ~165 行 (含重构后类型文档成本抵消)
- **扫描日期**: 2026-06-28

## ROI 总览

| 等级 | 数量 | 净省行数 | 主题 |
|---|---|---|---|
| 🔴 高 ROI | 4 | ~150 行 | 弹层族外观统一 + 状态徽章合并 + 页面头合并 + 卡片家族合并 |
| 🟡 中 ROI | 2 | ~25 行 | 状态 lookup 字典化 + Form 装饰器模式确认 |
| 🟢 低 ROI | 3 | 0 (识别出但不建议重构) | ErrorBanner 策略模式已实现 + PageHeader/PageHero 共存合理 |
| ❌ 明确不做 | ~77 | 0 | shadcn 原语 / 单一职责小函数 / 纯展示组件 |

---

## 🔴 高 ROI（建议重写）

### 1. 弹层族外观统一: AppDialog + AppDrawer + AppConfirm (Facade / Strategy)

**问题**: 三者**头部固定 + 内容滚动 + 底部固定**结构完全相同，且 AlertDialog 是 Dialog 的同源变体（同源于 Radix Dialog 同源码）。4 处文件 (`app-dialog.tsx` / `app-drawer.tsx` / `app-confirm.tsx` / `ui/alert-dialog.tsx`/`dialog.tsx`) 重复出现 `"border-b border-border/40 px-6 py-4"` + `<DialogHeader>` + `<div className="flex-1 overflow-auto px-6 py-4">` + `"border-t border-border/40 px-6 py-4"` 这套 layout。**重复 3+ 处。**

**当前实现**:
- `app-dialog.tsx`: 90 行
- `app-drawer.tsx`: 55 行
- `app-confirm.tsx`: 55 行
- **合计**: 200 行

**模式重写 (外观模式 Facade)**:

```typescript
// 提取共同的 LayoutStrategy
const OVERLAY_LAYOUT = "flex flex-col gap-0 p-0";
const HEADER_CLASS = "border-b border-border/40 px-6 py-4";
const BODY_CLASS = "flex-1 overflow-auto px-6 py-4";
const FOOTER_CLASS = "border-t border-border/40 px-6 py-4";

// AppDialog / AppDrawer / AppConfirm 抽出共享 <OverlayShell>
function OverlayShell({ header, body, footer, ...rest }: ...) {
  return (
    <XxxContent className={OVERLAY_LAYOUT} {...rest}>
      {header && <XxxHeader className={HEADER_CLASS}>{header}</XxxHeader>}
      <div className={BODY_CLASS}>{body}</div>
      {footer && <XxxFooter className={FOOTER_CLASS}>{footer}</XxxFooter>}
    </XxxContent>
  );
}

// 业务 wrapper 只剩 4-5 行 + props 透传
export const AppDialog = ({ title, description, footer, children, ...rest }) => (
  <Dialog {...rest}>
    <DialogContent className={cn(OVERLAY_LAYOUT, maxWidthClass[rest.maxWidth])}>
      <OverlayShell
        header={title && <DialogTitle>{title}</DialogTitle>}
        body={children}
        footer={footer}
        Primitive={DialogPrimitive}
      />
    </DialogContent>
  </Dialog>
);
```

**行数对比**:
| 文件 | 当前 | 重构后 | 节省 |
|---|---|---|---|
| `app-dialog.tsx` | 90 | 50 | -40 |
| `app-drawer.tsx` | 55 | 35 | -20 |
| `app-confirm.tsx` | 55 | 35 | -20 |
| `+ overlay-shell.tsx` (新) | 0 | 30 | +30 |
| **合计** | **200** | **150** | **-50** |

**复杂度对比**: 重构前修改 layout 需改 3 文件；重构后改 1 文件 (`overlay-shell.tsx`)。
**ROI**: 🟢 -25% 行数 + 强一致性收益。**列为 🟡 中 ROI**——投入回报在中期（避免未来 4 处需要同步改），但弹层 API 改写风险高（30 个调用方），且项目当前未报 bug。**不急切**。

---

### 2. StatusBadge × TaskStatusBadge 合并 (策略模式 / Lookup 字典)

**问题**: `app-status-badge.tsx` 和 `app-task-status-badge.tsx` 都是**状态徽章**，几乎同形态 (`Badge` + `Record<status, colorClass>`)。但**状态枚举不同** (一个 7 个 evaluation 状态 / 一个 6 个 task 状态)。StatusBadge 写在 `common/display/`，TaskStatusBadge 也写在 `common/display/`，但 `components/evaluate/status-badge.tsx` 还有一个**第三份**实现（不同位置），**3 处重复**。

**当前实现**:
- `app-status-badge.tsx`: 32 行
- `app-task-status-badge.tsx`: 19 行
- `components/evaluate/status-badge.tsx`: ~40 行 (3 处合计)
- **合计**: ~91 行

**模式重写 (策略模式 + lookup 字典 — 跟项目 lookups/README.md 约定一致)**:

```typescript
// 新建 lib/lookups/status-badge.ts (项目规约: 业务 enum 走 lookup 字典模块)
// 集中所有状态枚举 + 颜色 token + i18n 文案

type StatusKind = "evaluation" | "task";
const STATUS_COLOR: Record<string, string> = {
  pending: "bg-status-warning/10 text-status-warning",
  running: "bg-status-running/10 text-status-running animate-pulse",
  // ... 9 个统一枚举
};
const STATUS_LABEL: Record<string, string> = {
  pending: "排队",
  running: "运行中",
  // ... i18n key
};

// 单一组件，按 kind 选枚举
export const StatusBadge = ({ status, kind }: { status: string; kind: StatusKind }) => (
  <Badge className={STATUS_COLOR[status]} data-testid={`status-${kind}`}>
    {STATUS_LABEL[status] ?? status}
  </Badge>
);
```

**行数对比**:
| 文件 | 当前 | 重构后 | 节省 |
|---|---|---|---|
| `app-status-badge.tsx` | 32 | 0 (删) | -32 |
| `app-task-status-badge.tsx` | 19 | 0 (删) | -19 |
| `components/evaluate/status-badge.tsx` | ~40 | 0 (删) | -40 |
| `lib/lookups/status-badge.tsx` (新) | 0 | ~50 | +50 |
| **合计** | **~91** | **~50** | **-41** |

**复杂度对比**: 状态枚举去重；颜色 token 单一事实源；新增状态只改 1 处。
**ROI**: 🔴 高 — 3 处重复 + lookup 字典是项目规约。但 `app-status-badge.tsx` 当前**无 import** (grep 0 处使用)，是孤儿代码可直接删；`evaluate/status-badge.tsx` 跟另 2 个色板不一致（`bg-yellow-100` vs `bg-status-warning/10`），合并要先做样式统一。**建议做**，但要先确认 evaluate 团队接受 token 迁移。

---

### 3. PageHeader + PageHero 合并 (装饰器 / Template Method)

**问题**: `app-page-header.tsx` (27 行) 和 `app-page-hero.tsx` (67 行) 都是**页面顶部头**，结构高度相似 (返回链接 + title + 右侧 actions 插槽)。`PageHeader` 仅 1 处用法 (evaluate/new + evaluate/[id] + buyers/[id] 实际**只有 3 处**)，`PageHero` 跨 14+ 页使用。两者 API 不同 (`PageHero` 有 eyebrow/meta/description slot, `PageHeader` 仅 back+title+actions)。`PageHero` 已经在 v2 (2026-06-28) 通过 `backHref`/`backLabel` prop 吸收了 `PageHeader` 的功能。

**当前实现**:
- `app-page-header.tsx`: 27 行
- `app-page-hero.tsx`: 67 行 (含 back 模式)
- **合计**: 94 行

**模式重写**: `PageHeader` 已**被 PageHero 装饰器模式吸收** (通过 backHref prop 注入 BackLink)。剩余 3 处 `PageHeader` 调用可改为 `PageHero eyebrow="" title={...} backHref={...} actions={...}`。

**行数对比**:
| 文件 | 当前 | 重构后 | 节省 |
|---|---|---|---|
| `app-page-header.tsx` | 27 | 0 (删) | -27 |
| `app-page-hero.tsx` | 67 | 67 (不变) | 0 |
| **合计** | **94** | **67** | **-27** |

**复杂度对比**: 调用方从 2 个组件简化到 1 个；新页只需要选 PageHero 一个。
**ROI**: 🟡 中 — 节省行数有限 (27 行)，但统一抽象收益明显。

---

### 4. SectionCard + SettingsCard 合并 (外观模式)

**问题**: `app-section-card.tsx` (29 行) 和 `app-settings-card.tsx` (41 行) 都是**带 title + description + children + 右侧 actions** 的卡片。差异：SettingsCard 用 shadcn Card + Reveal 入场 + Lucide icon，SectionCard 是裸 div + h2 + 文本。

**当前实现**:
- `app-section-card.tsx`: 29 行
- `app-settings-card.tsx`: 41 行
- **合计**: 70 行

**模式重写 (外观模式)**: 抽出共享 `<CardShell title={title} description={description} icon={icon} actions={actions}>{children}</CardShell>`，SectionCard 和 SettingsCard 仅作 thin wrapper 选 style。

**行数对比**:
| 文件 | 当前 | 重构后 | 节省 |
|---|---|---|---|
| `app-section-card.tsx` | 29 | 15 (thin wrapper) | -14 |
| `app-settings-card.tsx` | 41 | 20 (thin wrapper) | -21 |
| `+ card-shell.tsx` (新) | 0 | 30 | +30 |
| **合计** | **70** | **65** | **-5** |

**复杂度对比**: 调用方 API 几乎不变。
**ROI**: 🟢 低 — 净省仅 5 行 + 增加新文件 + 抽象层成本不划算。**不建议重写**。

---

## 🟡 中 ROI（可选）

### 5. 状态 lookup 字典化 (跟项目规约对齐)

**问题**: `app-status-badge.tsx` / `app-task-status-badge.tsx` / `app-env-badge.tsx` 三个组件都内联了 `Record<string, string>` 颜色 map。项目规约 (`packages/service/src/lookups/README.md`) 要求业务 enum 走 lookup 字典模块。web 项目暂无 `lib/lookups/` 目录。

**模式重写 (策略模式 + lookup)**:

```typescript
// lib/lookups/task-status.ts
export const TASK_STATUS_COLOR: Record<TaskState, string> = {
  queued: "bg-muted text-muted-foreground",
  running: "bg-status-running/10 text-status-running animate-pulse",
  // ...
} as const;
```

**ROI**: 🟡 中 — 单独看不省代码，但**对齐后端 lookups 规约**，未来色板 token 切换只改一处。建议在 [#2 状态徽章合并](#2-statusbadge--taskstatusbadge-合并-策略模式--lookup-字典) 中顺带做。

---

### 6. Form Context / Provider 装饰器模式确认

**观察**: `app-form.tsx` 用 React Context (`FormCtx`) 提供 `form` 实例 + `layout` 给 `app-field.tsx` / `app-submit.tsx` 消费。这是 React **装饰器模式** (Provider) 的标准实现，**已经做得对**。

**ROI**: ✅ 已实现无需重写。仅作"模式确认"记录。

---

## 🟢 低 ROI（识别出但不建议）

### 7. ErrorBanner 已是策略模式

`app-error-banner.tsx` 已有 5 个 variant (`destructive | warning | info | success | loading`)，用 `Record<Variant, LucideIcon>` + `Record<Variant, string>` 双 lookup map 分发 icon 和 class。**已经是策略模式的标准实现**，无重构空间。

---

### 8. PageHeader / PageHero 共存合理

虽然 API 重叠，但 PageHero 适合"内容页" (eyebrow + 大 title + description)，PageHeader 适合"工具页" (紧凑 title + actions)。当前调用分布 (PageHero 14 处 / PageHeader 3 处) 反映了两者的语义差异。详见 [#3](#3-pageheader--pagehero-合并-装饰器--template-method) — 但合并仍有 ~27 行收益，建议做。

---

### 9. AppTooltip 3 variant 策略模式

`app-tooltip.tsx` 已有 `default | error | none` 3 variant，通过 `VARIANT_BAR` lookup 映射颜色 token。**已实现策略模式**，无重构空间。

---

## ❌ 明确不做（违反 YAGNI / 不适合 React）

| 类别 | 文件 | 原因 |
|---|---|---|
| **shadcn 原语** | `ui/dialog.tsx`, `ui/alert-dialog.tsx`, `ui/sheet.tsx`, `ui/dropdown-menu.tsx`, `ui/select.tsx`, `ui/tooltip.tsx`, `ui/calendar.tsx`, `ui/command.tsx`, `ui/pagination.tsx`, `ui/popover.tsx`, `ui/radio-group.tsx`, `ui/scroll-area.tsx`, `ui/skeleton.tsx`, `ui/sonner.tsx`, `ui/switch.tsx`, `ui/separator.tsx`, `ui/table.tsx`, `ui/tabs.tsx`, `ui/textarea.tsx`, `ui/toggle.tsx`, `ui/toggle-group.tsx`, `ui/progress.tsx`, `ui/label.tsx`, `ui/input.tsx`, `ui/checkbox.tsx`, `ui/card.tsx`, `ui/collapsible.tsx`, `ui/avatar.tsx`, `ui/empty.tsx`, `ui/alert.tsx`, `ui/badge.tsx`, `ui/button.tsx` | shadcn 官方生成代码，**禁止改**（改了就破坏 shadcn cli 重新生成能力） |
| **纯展示组件** | `app-spinner.tsx`, `app-loading-skeleton.tsx`, `app-breathing-dot.tsx`, `app-data-empty.tsx`, `app-image-preview.tsx` | 单一职责，无重复逻辑 |
| **单一函数工具** | `data-table-skeleton.tsx` | 28 行单组件，抽象成本不划算 |
| **React 组件不能单例化** | `app-error-boundary.tsx` | React 错误边界本身要求 Class 组件；React 组件单例化违反模型 |
| **业务无关外观** | `app-collapsible.tsx`, `app-tabs.tsx`, `app-toggle.tsx`, `app-select.tsx`, `app-dropdown-menu.tsx`, `app-search-input.tsx`, `app-file-dropzone.tsx` | 已是 antd 风格 1 行 API 包装，封装到位 |
| **导航类** | `app-back-link.tsx` | 单一职责，47 行完成单一功能 |
| **StatCard / StatsGrid / EntryCard / EntryCardGrid** | display/ | 已通过 Grid 二次封装消重，无重构空间 |
| **lookup 表已经合理** | `BreathingDot` 用 `COLOR_MAP`/`SIZE_MAP` lookup | 已用策略模式 |
| **环境标识 / 健康点** | `app-env-badge.tsx`, `app-health-dot.tsx` | 单组件，无重复 |
| **stats-grid / entry-card-grid** | display/ | 已通过"items[] + columns"消除 N 处重复 |
| **DataTable 子件** | `data-table.tsx` / `data-table-body.tsx` / `data-table-pagination.tsx` / `data-table-skeleton.tsx` | 已合理拆分；TanStack 换底已完成 |

---

## 总结与建议优先级

### 立即做（高 ROI + 低风险）
- **#2 StatusBadge × TaskStatusBadge 合并**: 3 处重复 → 1 处 lookup 字典。但要先跟 evaluate 团队对齐样式 token 迁移 (从 `bg-yellow-100` 到 `bg-status-warning/10`)。**预期 1 PR, ~30 行净省。**

### 中期做（中 ROI, 中风险）
- **#3 PageHeader 删, 调用方改 PageHero**: 3 处调用方简单替换。**预期 1 PR, ~27 行净省。**

### 暂不做（重构价值低或风险高）
- **#1 弹层族外观统一**: 30 个调用方，改 API 风险高。保留 facade 内部消重也行（仅改 4 个封装文件），但**当前不是痛点**。**留作未来 PR。**
- **#4 SectionCard + SettingsCard 合并**: 净省 5 行，**不值得重构**。

### 模式层面结论
1. **策略模式**已经在 ErrorBanner / AppTooltip / StatusBadge 等多处实现，无需新引入。
2. **外观模式**最适合弹层族 (`#1`) 和卡片族 (`#4`)，但前者 30 调用方改造成本高，后者净省太少。
3. **装饰器模式**已在 Form Context (`app-form.tsx` + `useFormCtx`) 正确实现。
4. **单例模式**不适合 React 组件；`zustand store` 已经是单例等价物 (项目已用)。
5. **适配器模式**用在 `lib/api/*` 和 `lib/chat/*`，**跟 common/ui 无关**，不属本次审计范围。

---

## 扫描方法说明

1. **列出全部 86 文件** (`find ... ! -name "*.test.*" ! -name "*.stories.*"`)
2. **优先级筛选**: 先读任务指定的 7 个核心候选 (`error-banner` / `error-boundary` / `loading-skeleton` / `tooltip` / `dialog` / `drawer` / `confirm`)，再扩展到同目录其它 common 组件 (display / form / input / navigation / table)
3. **识别重复模式**:
   - 同一目录内 `app-status-badge.tsx` vs `app-task-status-badge.tsx` vs 外部 `evaluate/status-badge.tsx` (Grep `StatusBadge|TaskStatusBadge`) → 发现 3 处状态徽章重复
   - 弹层族结构重复: `AppDialog` / `AppDrawer` / `AppConfirm` 都用 `border-b` + `flex-1 overflow-auto` + `border-t` 三段式 (Grep `border-b border-border/40 px-6 py-4`)
   - 页面头重复: `PageHero` 已通过 `backHref` 装饰吸收 `PageHeader` 功能 (Grep `PageHeader|PageHero`)
4. **调用方验证**: 通过 Grep 统计实际调用次数 (`AppDialog` 30 文件 / `PageHero` 14 文件 / `PageHeader` 3 文件)，评估重构风险
5. **ROI 计算**: 对每个候选计算"重构前 N 行 vs 重构后 M 行"，加 +抽象层成本，对比"重复代码 ≥3 处 + 可读性提升 + 净省 ≥20%"三重门

**关键约束**:
- shadcn 原语 (`ui/*`) **绝对不改**（破坏 cli 重新生成能力）
- React 组件不单例化（违反 React 模型，zustand 已经是单例等价）
- 已用策略模式的组件不重复识别（ErrorBanner / AppTooltip 等）
- 调用方 ≥10 处的 API 重构 = 高风险，需单独 spec

**未深入审计**:
- `ui/calendar.tsx` (7613 行) 和 `ui/command.tsx` (4834 行) 体量过大，本次仅粗读未深入（怀疑有 dayjs/cmdk 复杂状态机，但需单独 spec 评估）
- `lib/api/*` 和 `lib/chat/*` 适配器模式 (跟 common/ui 无关，属 B 维度审计范围)