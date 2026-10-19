# P5 维度 ⑤ 注释完整性审计 — Agent A (common + ui ~84 files)

> 审计范围: `packages/web/components/common/` + `packages/web/components/ui/`
> 排除 `.test.tsx` / `.stories.tsx`
> 审计日期: 2026-06-28
> 规约基线: `.claude/CLAUDE.md` §编码规范 (中文注释 / 不删注释 / 函数文档化)

## 扫描概览

- 总扫描文件: **84** (common/ 52 + ui/ 32)
- common/ 文件头注释覆盖率: **22 / 52 (42.3%)**
- ui/ 文件头注释覆盖率: **0 / 32 (0%)** — 全部为 shadcn/ui CLI 生成, **禁止改**
- common/ 主导出 JSDoc 覆盖率: **1 / 36 (2.8%)** (仅 `app-data-empty.tsx` 的 `DataEmpty`)
- internal 辅助函数 JSDoc 覆盖率: **~5 / ~25 (20%)** (集中在 form/table 模块)
- **🔴 P0 缺失 (文件头 + 公共 API)**: 30
- **🟡 P1 缺失 (内部函数 + 复杂分支)**: 8
- **🟢 可豁免**: ~70 (lookup map / type / props interface / index.ts re-export)

> **修正用户原始估算**: 用户提示 "~50 common + ~36 ui = 86", 实际 glob 结果为 52 + 32 = **84 文件** (ui/ 比预期少 4 个, 可能是 2026-06-27 移除 `breadcrumb`/`breadcrumb-separator`/`aspect-ratio`/`form` 等未用组件).

---

## 🔴 P0 缺失 (建议补全)

### A.1 [common/button/app-copy-button.tsx]
**类型**: 文件头缺失 + 主组件缺 JSDoc
**现状** (前 12 行):
```ts
"use client";
// Clipboard + 1.5s 反馈 (2026-06-14): 替 4 处 navigator.clipboard.writeText
//   用法: <CopyButton text={inviteUrl} label="复制" successLabel="已复制 ✓" />
//   失败走 sonner toast.error, 成功 1.5s "已复制 ✓" 反馈
import { useState, useTransition } from "react";
...
```
有 4 行 `//` 用法注释 (位置非首行, 第 2-4 行), 但首行是 `"use client"` — 按规约"文件第一行 (import 前)"严格判 ❌
**建议**:
```ts
/**
 * @file Clipboard 复制按钮 (2026-06-14)
 * @description 封装 navigator.clipboard.writeText, 1.5s 内显 successLabel, 失败走 sonner toast
 */
/**
 * 复制文本到剪贴板并显示反馈
 * @param props.text 待复制文本
 * @param props.label 按钮默认文案 (默认 "复制")
 * @param props.successLabel 复制成功后文案 (默认 "已复制 ✓")
 * @param props.onCopied 复制成功回调
 */
export const CopyButton = (props: CopyButtonProps) => { ... }
```
**理由**: 项目规约"所有 .ts/.tsx 文件必须写这个文件的作用"; CopyButton 是项目 4 处统一复用组件, 公共 API 缺文档会拖慢调用方理解.

### A.2 [common/button/app-loading-skeleton.tsx]
**类型**: 文件头缺失 + 主组件缺 JSDoc
**现状** (前 12 行):
```ts
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
const DEFAULT_SKELETON_ROWS = 3;
const HEADER_ROW_INDEX = 0;
interface LoadingSkeletonProps { rows?: number; className?: string }
export const LoadingSkeleton = ({ rows = DEFAULT_SKELETON_ROWS, className }: LoadingSkeletonProps) => (
```
**建议**:
```ts
/**
 * @file 表格/卡片加载骨架屏 (2026-06-14)
 * @description 默认 3 行, 首行宽 48 高 8, 其余 4 行全宽 — 替手写 Skeleton × N
 */
/**
 * 渲染 rows 行骨架占位, 首行 header 样式, 其余行 content 样式
 * @param props.rows 骨架行数 (默认 3)
 * @param props.className 外层额外 className
 */
```
**理由**: LoadingSkeleton 是 DataTable 的 fallback, 业务 ≥ 3 处调用, 公共 API 缺文档.

### A.3 [common/button/app-submit-button.tsx]
**类型**: 文件头缺失 + 主组件缺 JSDoc
**现状** (前 19 行):
```ts
"use client";
// 通用提交按钮 — 内部用 useFormStatus 感知 pending, 父组件不用传 pending prop
// (2026-06-14) Sprint 2.1 新建: React 19 useFormStatus 模式
import { Button } from "@/components/ui/button";
```
有 3 行 `//` 注释但仍非首行 ❌
**建议**: 同 A.1 模式, 把 3 行 `//` 注释提升到 `/** ... */` 文件头, 主组件加 JSDoc.

### A.4 [common/confirm/app-confirm.tsx]
**类型**: 文件头缺失 + 主组件缺 JSDoc
**现状**:
```ts
"use client";
// AppConfirm — 危险操作二次确认 (2026-06-10)
import { AlertDialog, ... } from "@/components/ui/alert-dialog";
```
**建议**: 注释提升到 `/** */`, 主组件加 JSDoc 说明 `variant="destructive"` 触发红按钮.

### A.5 [common/dialog/app-dialog.tsx]
**类型**: 文件头缺失 + 主组件缺 JSDoc
**现状**: 前 5 行均有 `//` 注释但非首行 (`"use client"` 占位).
**建议**: 提升到 `/** */`, 主组件 JSDoc 提及 `error` prop 内建 ErrorBanner 自动渲染.

### A.6 [common/display/app-breathing-dot.tsx]
**类型**: 文件头缺失 + 主组件缺 JSDoc
**现状**:
```ts
// 呼吸灯圆点 (2026-06-15): 替代 page.tsx / HealthDot / DecodeInputBar 散落的 ping 圆点
```
**建议**: 提升到 `/** */` + 主组件 JSDoc 说明 5 种 color 枚举含义.

### A.7 [common/display/app-collapsible.tsx]
**类型**: 文件头缺失 + 主组件缺 JSDoc
**现状**:
```ts
"use client";
// AppCollapsible — antd Collapse 风格折叠面板 (2026-06-25)
// 封装 Radix Collapsible 3 子组件为 1 行 API
```
**建议**: 提升 + JSDoc.

### A.8 [common/display/app-entry-card.tsx]
**类型**: 文件头缺失 + 主组件缺 JSDoc
**现状**: 5 行 `//` 注释包含 "从 components/knowledge/ 升 common/", **业务关键** (3 处调用).
**建议**: 提升 + JSDoc 明确 `index` 用于 stagger 延迟.

### A.9 [common/display/app-env-badge.tsx]
**类型**: 文件头缺失 + 主组件缺 JSDoc
**现状**: 仅 3 行 `//` 注释.
**建议**: 提升 + JSDoc (因为含环境变量副作用).

### A.10 [common/display/app-health-dot.tsx]
**类型**: 文件头缺失 + 主组件缺 JSDoc + 内部 helper `Dot` 缺 JSDoc
**现状**: 6 行 `//` 注释描述 SWR→QueryClient 迁移历史. **业务复杂** (5s 轮询 + 独立 QueryClient).
**建议**: 提升 + JSDoc 详细说明 polling 间隔 / loading vs ok vs 不可达 3 状态颜色映射.

### A.11 [common/display/app-section-card.tsx]
**类型**: 文件头缺失 + 主组件缺 JSDoc
**现状**: 无注释, 21 行简单组件.
**建议**: 加文件头 `/** 通用 section 容器 — title + description + actions slot + children */`.

### A.12 [common/display/app-settings-card.tsx]
**类型**: 文件头缺失 + 主组件缺 JSDoc
**现状**:
```ts
// SettingsCard — 统一设置页卡片组件
// 入场动画 (Reveal) + hover 微浮 (hover:shadow-md) + 主题色边框
// 不修改卡片长宽高, 不影响周边布局 (motion 只改 transform)
```
3 行 `//` 注释非首行.
**建议**: 提升.

### A.13 [common/display/app-spinner.tsx]
**类型**: 文件头缺失 + 主组件缺 JSDoc
**现状**: 2 行 `//` 注释说明旋转动画参数. SpinnerProps.borderClass 有 `/** */` 单字段文档 (好习惯).
**建议**: 提升 + 主组件 JSDoc 说明 reduced-motion 退化行为.

### A.14 [common/display/app-stat-card.tsx]
**类型**: 文件头缺失 + 主组件缺 JSDoc
**现状**:
```ts
"use client";
// 统计卡 (2026-06-09 redesign) — 用统一 CountUp 弹数字
```
**建议**: 提升 + JSDoc 说明 5 种 accent 颜色 token 含义.

### A.15 [common/display/app-status-badge.tsx]
**类型**: 文件头缺失 + 主组件缺 JSDoc + 含 lookup map (🟢 部分豁免)
**现状**: STATUS_COLORS lookup map (🟢 可豁免), 但 StatusBadge 组件本身有业务逻辑 (customLabels fallback).
**建议**: 文件头 + JSDoc 说明 7 种 status 枚举 + customLabels 覆盖机制.

### A.16 [common/display/app-task-status-badge.tsx]
**类型**: 文件头缺失 + 主组件缺 JSDoc
**现状**:
```ts
// 任务状态徽章 (2026-06-15) — 从 components/knowledge/ 升 common/
```
**建议**: 提升 + JSDoc 说明 6 种状态 + running 有 animate-pulse.

### A.17 [common/display/entry-card-grid.tsx]
**类型**: 文件头缺失 + 主组件缺 JSDoc
**现状**: 4 行 `//` 注释 (关键: "替代 3 个 dashboard 入口页的 14+ 行重复 JSX").
**建议**: 提升 + JSDoc 说明 ENTRY_COLS_TWO / ENTRY_COLS_FOUR 字符串键模式.

### A.18 [common/display/stats-grid.tsx]
**类型**: 文件头缺失 + 主组件缺 JSDoc + 内部 helper `renderItem` 缺 JSDoc
**现状**: 4 行 `//` 注释说明 Phase3 抽组件动机.
**建议**: 提升 + JSDoc 说明 LocalizedLink wrapper 逻辑 (href 时自动包 link).

### A.19 [common/drawer/app-drawer.tsx]
**类型**: 文件头缺失 + 主组件缺 JSDoc
**现状**: 1 行 `//` 注释.
**建议**: 提升 + JSDoc 说明 `side` / `maxWidth` props (业务未用, 但属公共 API).

### A.20 [common/feedback/app-error-banner.tsx]
**类型**: 文件头缺失 + 主组件缺 JSDoc + 2 个 lookup map (🟢 部分豁免)
**现状**: 4 行 `//` 注释说明 5 variant. **业务复杂** (16 处统一组件).
**建议**: 提升 + JSDoc 详述 5 variant 颜色 + icon 自动选择.

### A.21 [common/feedback/app-error-boundary.tsx]
**类型**: 文件头缺失 + 类组件缺 JSDoc
**现状**: 4 行 `//` 注释. **React class component** (项目少用, 唯一 class).
**建议**: 提升 + 类 JSDoc 说明 getDerivedStateFromError 用法 + "重试" button 行为.

### A.22 [common/form/app-field.tsx]
**类型**: 文件头缺失 + 主组件缺 JSDoc + 内部 helper 缺 JSDoc
**现状**: 3 行 `//` 注释 + 3 个内部 helper (extractEventValue / buildInputElement / getErrorMessage) 全无 JSDoc.
**建议**: 提升 + JSDoc 4 处.

### A.23 [common/form/app-form.tsx]
**类型**: 文件头缺失 + 主组件缺 JSDoc + useFormCtx hook 缺 JSDoc
**现状**: 3 行 `//` 注释 + useFormCtx 抛错提示.
**建议**: 提升 + JSDoc 说明 onFinish / action 双模式 + Zod schema integration.

### A.24 [common/form/app-submit.tsx]
**类型**: 文件头缺失 + 主组件缺 JSDoc
**现状**: 1 行 `//` 注释.
**建议**: 提升 + JSDoc 区分 vs button/app-submit-button.tsx (前者用 react-form store, 后者用 react-dom useFormStatus).

### A.25 [common/input/app-dropdown-menu.tsx]
**类型**: 文件头缺失 + 主组件缺 JSDoc + 内部 destruct `DESTRUCTIVE_CLASS` (🟢 简单常量)
**现状**: 12 行 `//` 注释 (用法示例 + 复杂场景指引). **业务复杂** (DESTRUCTIVE variant 处理).
**建议**: 提升 + JSDoc 说明 hidden / separator / href / destructive 4 个 item 字段.

### A.26 [common/input/app-file-dropzone.tsx]
**类型**: 文件头缺失 + 主组件缺 JSDoc + 2 个内部 helper (parseAcceptString / parseAccept) 缺 JSDoc
**现状**: 14 行 `//` 注释 (升级点 + 调用点 + 后向兼容). **业务复杂** (MIME 解析).
**建议**: 提升 + JSDoc 4 处. parseAcceptString 尤其需要 — 行为不直观 (扩展 → MIME 字典).

### A.27 [common/input/app-image-preview.tsx]
**类型**: 文件头缺失 + 主组件缺 JSDoc
**现状**: 4 行 `//` 注释 (含 ESC / overlay 行为说明).
**建议**: 提升 + JSDoc 说明 `bg-transparent border-none shadow-none` 视觉原因.

### A.28 [common/input/app-search-input.tsx]
**类型**: 文件头完全缺失 (首行就是 import)
**现状**:
```ts
"use client";
import { Search } from "lucide-react";
import { Input } from "@/components/ui/input";
import { useDebounce } from "react-use";
import { useEffect, useState } from "react";
```
**建议**:
```ts
/**
 * @file 搜索输入框 — debounce + 受控 + Lucide 图标 (2026-06-15)
 * @description 默认 300ms debounce, useDebounce + useEffect 同步外部 value
 */
/**
 * 带 debounce 的搜索框
 * @param props.value 受控值
 * @param props.onChange debounce 后的回调
 * @param props.debounceMs debounce 延时 (默认 300ms)
 */
```
**理由**: 完全无注释 (❌ 双重缺失), 是项目规约明确禁止的样例.

### A.29 [common/input/app-select.tsx]
**类型**: 文件头缺失 + 主组件缺 JSDoc
**现状**: 4 行 `//` 注释 (含 antd 风格封装动机).
**建议**: 提升 + JSDoc.

### A.30 [common/input/app-tabs.tsx]
**类型**: 文件头缺失 + 主组件缺 JSDoc
**现状**: 7 行 `//` 注释 (2 种用法 + content 自动检测).
**建议**: 提升 + JSDoc 说明 `hasContent` 自动检测逻辑.

### A.31 [common/input/app-toggle.tsx]
**类型**: 文件头缺失 + 主组件缺 JSDoc
**现状**: 4 行 `//` 注释.
**建议**: 提升 + JSDoc.

### A.32 [common/navigation/app-back-link.tsx]
**类型**: 文件头缺失 + 主组件缺 JSDoc
**现状**: 7 行 `//` 注释 (2 模式说明 + 修饰键透传逻辑). **业务复杂** (修饰键处理).
**建议**: 提升 + JSDoc 详述 useHistory 行为.

### A.33 [common/navigation/app-page-header.tsx]
**类型**: 文件头完全缺失 (首行就是 import)
**现状**:
```ts
"use client";
import { ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useRouter } from "@/i18n/navigation";
```
**建议**: 加文件头 + JSDoc 区分 vs `app-page-hero.tsx` (前者是 BackLink 简化版, 后者是 hero slot 模式).

### A.34 [common/navigation/app-page-hero.tsx]
**类型**: 文件头缺失 + 主组件缺 JSDoc
**现状**: 7 行 `//` 注释 (slot 模式说明 + 2026-06-28 Phase3 更新).
**建议**: 提升 + JSDoc.

### A.35 [common/overlay/app-tooltip.tsx]
**类型**: 文件头缺失 + 主组件缺 JSDoc
**现状**: 6 行 `//` 注释 (含 TooltipProvider 易漏教训).
**建议**: 提升 + JSDoc 详述 `variant="error"` 左侧红条视觉.

### A.36 [common/table/data-table-body.tsx]
**类型**: 文件头缺失 + 主组件缺 JSDoc + 3 个内部 helper (renderLoadingRow / renderEmptyRow / renderDataRows) 缺 JSDoc
**现状**: 4 行 `//` 注释. **业务复杂** (TanStack table + 展开行 + 减少动画).
**建议**: 提升 + JSDoc 4 处. renderDataRows 尤需说明 expanded row null 跳过逻辑.

### A.37 [common/table/data-table-pagination.tsx]
**类型**: 文件头缺失 + 主组件缺 JSDoc + 1 个内部 helper (buildButtonClass) 缺 JSDoc
**现状**: 3 行 `//` 注释 (受控分页说明).
**建议**: 提升 + JSDoc 2 处.

### A.38 [common/table/data-table-skeleton.tsx]
**类型**: 文件头缺失 + 主组件缺 JSDoc
**现状**:
```ts
// DataTable 通用 Suspense fallback — RSC use(promise) 模式下的骨架屏
// (2026-06-14) Sprint 1.6 新建
```
**建议**: 提升 + JSDoc.

### A.39 [common/table/data-table.tsx]
**类型**: 文件头缺失 + 主组件缺 JSDoc + 4 个内部 helper (resolveMaxHeight / getFlexColStyle / getStringColStyle / getColStyle) 缺 JSDoc
**现状**: 9 行 `//` 注释 (3 模块说明 + 换底历史 + 受控/非受控逻辑). **项目最复杂公共 API** (4 列宽模式).
**建议**: 提升 + JSDoc 5 处. getColStyle 尤需说明 4 种 ColumnWidth mode 处理.

---

## 🟡 P1 缺失 (建议补全, 可分批)

### B.1 [common/display/app-data-empty.tsx]
**类型**: 主组件已有 JSDoc (唯一), 但内部 lookup (🟢 豁免)
**现状**: JSDoc 在 line 31-34, ✅ 合规. **作为标杆**, 其他文件应向其看齐.

### B.2 [common/display/app-status-badge.tsx]
**类型**: 复杂分支 (customLabels fallback) 无行内注释
**现状**: `customLabels?.[status] ?? status` — 无行内注释解释 fallback 行为.
**建议**: 加 `// 未指定 label 时直接显示 status key`.

### B.3 [common/display/app-task-status-badge.tsx]
**类型**: 复杂分支 (style[state] fallback) 无行内注释
**现状**: `style[state] ?? style.queued` — fallback 行为未注释.
**建议**: 加 `// 未知状态降级为 queued (中性灰)`.

### B.4 [common/form/app-field.tsx:65]
**类型**: 复杂 cloneElement 注入无行内注释
**现状**: cloneElement 注入 name/value/onChange/onBlur/required/placeholder 5 个字段, 关键注释已在 line 55 但未涵盖全部字段语义.
**建议**: 加 `// 必传 name: form action 模式 FormData 取值依赖 name 属性`.

### B.5 [common/form/app-form.tsx:74-77]
**类型**: onFinish 错误吞咽无行内注释
**现状**: catch 后 console.error, **业务关键** (用户感知不到).
**建议**: 加 `// onFinish 内部 catch: 防止 TanStack Form 内部 onSubmit 抛 unhandled rejection`.

### B.6 [common/navigation/app-back-link.tsx:53]
**类型**: 修饰键透传条件复杂无注释
**现状**: 4 个修饰键 + button 编号检查 — 已部分注释, 但 button 编号为何 ≠ 0 不注释.
**建议**: 加 `// MOUSE_BUTTON_LEFT=0 是标准主键编号, 修饰键按下时让浏览器原生处理 (新窗口)`.

### B.7 [common/table/data-table.tsx:131-155]
**类型**: TanStack 复杂条件分页无行内注释
**现状**: 注释已说明受控/非受控, 但 `...(pagination !== undefined ? {...} : {})` 展开运算符细节未注.
**建议**: 加 `// 非受控时不传 manualPagination, 用默认 onChange → handleSubmit 流程`.

### B.8 [common/table/data-table-pagination.tsx:46-65]
**类型**: handlePrev/handleNext 双分支无注释
**现状**: 受控 vs 非受控分支, **关键逻辑** (受控时 Math.max/Math.min 边界).
**建议**: 加 `// Math.max(1, ...) 防止 current=1 时 prev 退到 0; Math.min(totalPages, ...) 防越界`.

---

## 🟢 可豁免 (列出即可, 不详细展开)

**类别 A: lookup map (颜色 / 样式 / 状态枚举映射) — 含义自明, 不需要 JSDoc**:
- common/display/app-breathing-dot.tsx `COLOR_MAP` / `SIZE_MAP` (lookup)
- common/display/app-env-badge.tsx `variant` (lookup)
- common/display/app-status-badge.tsx `STATUS_COLORS` (lookup)
- common/display/app-task-status-badge.tsx `style` (lookup)
- common/feedback/app-error-banner.tsx `defaultIcon` / `variantColorClass` (lookup)
- common/overlay/app-tooltip.tsx `VARIANT_BAR` (lookup)
- common/display/entry-card-grid.tsx `COL_CLASS_BY_KEY` (lookup)
- common/display/stats-grid.tsx `COL_CLASS_BY_KEY` (lookup)
- common/table/data-table-pagination.tsx `PAGE_STEP` / `DISABLED_OPACITY` / `CURSOR_POINTER` (常量)
- common/form/app-field.tsx (内部常量如 extractEventValue 等函数本身有 JSDoc 价值, **不在此豁免**)

**类别 B: type/interface 定义 — 类型自描述, 不需要 JSDoc**:
- 所有 `export interface *Props` 块 (50+ 处)
- 所有 `export type * = ...` 块 (BreathingDotColor, StatCardAccent, ColumnWidth, ColumnDef 等)

**类别 C: index.ts barrel re-export — 无业务逻辑, 不需要 JSDoc**:
- common/index.ts + 9 个子模块 index.ts (button/confirm/dialog/display/drawer/feedback/form/input/navigation/overlay/table) = **11 个 index.ts**

**类别 D: 简单 1 行导出 (含义自明) — 可豁免**:
- common/display/app-env-badge.tsx `EnvBadge` (1 行 JSX, 含义 = "环境标识")
- common/display/app-status-badge.tsx `StatusBadge` (1 行 JSX, 类型 + lookup 决定行为)
- common/display/app-task-status-badge.tsx `TaskStatusBadge` (1 行 JSX, 同上)
- common/table/data-table-skeleton.tsx `DataTableSkeleton` (骨架屏 JSX, 自描述)

**类别 E: shadcn/ui 自动生成 — 禁止改**:
- ui/* 32 文件全部 (alert / alert-dialog / avatar / badge / button / calendar / card / checkbox / collapsible / command / dialog / dropdown-menu / empty / input / label / pagination / popover / progress / radio-group / scroll-area / select / separator / sheet / skeleton / sonner / switch / table / tabs / textarea / toggle / toggle-group / tooltip)

**合计可豁免**: ~70 文件 / 段 (lookup map + type + index + 1 行 JSX + shadcn).

---

## ❌ 明确不做

- **ui/* 32 文件**: shadcn/ui CLI 生成, 修改会被 `bunx shadcn@latest add` 覆盖. 按项目规约, 不计入缺失 (见 `.claude/CLAUDE.md` §工具链 + shadcn 文档).
- **类型/interface 定义块**: 项目规约未要求 JSDoc, TS 自描述.
- **index.ts re-export**: 无业务逻辑.
- **简单 lookup map** (≤ 5 字段 + 含义自明): 已豁免.

---

## 扫描方法说明

**步骤 1: 列出所有源文件** (排除 .test/.stories):
```bash
cd packages/web/components && \
  find common ui -name "*.ts" -o -name "*.tsx" | \
  grep -vE "\.(test|stories)\.(ts|tsx)$" | sort
```
结果: common/ 52 + ui/ 32 = **84 文件**.

**步骤 2: 文件头注释检测** (首行 `^//` 或 `^/**`):
```bash
for f in $(find common ui ...); do
  head -1 "$f" | grep -qE "^/\*\*|^//" && echo "HAS_HEADER: $f" || echo "NO_HEADER:  $f"
done
```
结果: common/ 22/52 有头; ui/ 0/32 有头 (全部豁免).

**步骤 3: 主导出 JSDoc 检测** (排除 type/interface):
```bash
for f in $(find common ...); do
  main_line=$(grep -nE "^export (const [A-Z]|class [A-Z])" "$f" | head -1 | cut -d: -f1)
  if [ -n "$main_line" ]; then
    # 在 main_line 前 5 行内查找 /** 或 *
    start=$((main_line - 5))
    sed -n "${start},$((main_line - 1))p" "$f" | grep -c "/\*\*"
  fi
done
```
结果: common/ 1/36 主导出有 JSDoc (仅 `app-data-empty.tsx`).

**步骤 4: 内部 helper 函数检测** (grep `const xxx =` 非 export + `function xxx`):
仅 form/, table/, display/stats-grid.tsx, display/entry-card-grid.tsx 等含内部 helper (估算 ~25 个), 仅 ~5 个有 JSDoc.

**步骤 5: ui/ 确认 shadcn 原生**:
```bash
head -3 ui/*.tsx | grep -E "Radix|class-variance-authority|lucide-react"
```
全部命中 shadcn 依赖, 标记为 禁止改.

---

## 修复优先级建议

**第一批 (P0, 估计 30 文件 × 平均 5 行新增 = 150 行)**: 修 A.1-A.39 — 每个文件加 `/** @file ... */` 头 + 主组件 JSDoc.
- 估时: 1-2 小时 (批量机械补)
- 风险: 低 (纯文档, 0 业务变更)
- 验证: 跑 `bun run lint` + `bun run typecheck` (oxlint/tsgo 不会报错, 但需注意 JSDoc 中文标点不被 oxfmt 重排)

**第二批 (P1, 估计 8 处行内)**: 修 B.2-B.8 — 复杂分支补行内注释.
- 估时: 30 分钟
- 风险: 低

**不修 (豁免 + 禁止改)**:
- ui/* 32 文件
- index.ts 11 文件
- lookup map / type / 1 行 JSX 简单导出 (~20 个)

---

## 关联文档

- 项目级规约: `.claude/CLAUDE.md` §编码规范
- 前端局部约定: `packages/web/CLAUDE.md`
- 本审计上下文: `docs/superpowers/specs/2026-06-19-code-quality-cleanup-design.md`