---
title: 2026-06-25 代码质量分析 5 维度
description: 基于全量代码扫描的 5 个重构方向分析设计报告
status: draft
author: AI
created: 2026-06-25
tags: [code-quality, refactoring, analysis]
---

# 代码质量 5 维度扫描分析设计

> 本文档基于 2026-06-25 全量代码扫描，分析 5 个重构方向的可行性和具体方案。

## 1. TanStack Form 替换 react-hook-form

### 现状

`react-hook-form` 只在 `components/ui/form.tsx`（shadcn Form 模板）中使用，业务代码（pages/components/app）不直接 import react-hook-form。`@tanstack/react-form` 已安装（`^1.33.0`）但未被任何文件 import。

`components/ui/form.tsx` 对 react-hook-form 的依赖：

```typescript
import {
  Controller,        // FormField 组件底层
  type ControllerProps,
  type FieldPath,
  type FieldValues,
  FormProvider,      // Form = FormProvider 别名
  useFormContext,    // useFormField 内部使用
} from "react-hook-form";
```

### 替换可行性

替换方案：将 `components/ui/form.tsx` 从 react-hook-form 切换为 TanStack Form。

| react-hook-form | TanStack Form | shadcn 包装后的暴露接口 |
|----------------|--------------|----------------------|
| `FormProvider` | `form.Field` + `form.state` | `<Form>` 不变 |
| `Controller` | `<Field name>{children}</Field>` | `<FormField>` 不变 |
| `useFormContext` → `getFieldState` | `field.state.meta` | `useFormField` hook 内部改 |

迁移方案：

1. 改 `components/ui/form.tsx`：
   - `Controller` → TanStack `useForm` + `<Field>`
   - `FormProvider` → 移掉，改用 `<form>` 标签 + TanStack `form.handleSubmit()`
   - `useFormContext` → 改用 `useFieldContext()`
   - 保持导出接口完全一致（`Form`, `FormField`, `FormItem`, `FormLabel`, `FormControl`, `FormDescription`, `FormMessage`, `useFormField`）

2. 改 `components/ui/form.test.tsx`：
   - `useForm` from react-hook-form → TanStack `useForm`

3. 移除依赖：
   - `react-hook-form`
   - `@hookform/resolvers`

### 工作量

- 改动文件：2 个（form.tsx + form.test.tsx）
- 影响：0 业务文件
- 时间预估：0.5 天

### 建议

当前收益较小（业务代码尚未使用 shadcn Form 模式），建议等有新的表单需求时同步进行，或在新表单项目开始时做替换。

---

## 2. TanStack Table 重构 DataTable

### 现状

`@tanstack/react-table`（`^8.21.3`）已安装但未被任何 source 文件 import。当前 DataTable 是自定义实现：

```
components/common/data-table/
├── data-table.tsx        # 180 行，自定 ColumnDef + 分页 + 动画
├── data-table-skeleton.tsx
├── data-table.test.tsx
└── index.ts
```

使用范围：14 个业务文件（buyers, evaluate, knowledge/nodes/relations/datasets/documents, admin/users/invites/dicts/profile-fields, output, evaluate/new）。

### 核心差异：ColumnDef 体系不兼容

**当前 ColumnDef（简化的 antd 风格）**：

```typescript
interface ColumnDef<TData> {
  key: string;                                    // 字段名
  render?: (row: TData, index: number) => ReactNode;  // 渲染
  title: string;                                  // 标题
  width?: ColumnWidth;                            // 宽
  align?: "left" | "center" | "right";            // 对齐
}
```

**TanStack Table ColumnDef**：

```typescript
// TanStack Table 各有 accessorKey/accessorFn/cell/header/id 等多种字段
const columns = columnHelper.accessor("name", {
  header: "姓名",
  cell: ({ row }) => <Badge>{row.original.role}</Badge>,
});
```

### 不兼容点

| 维度 | 当前 DataTable | TanStack Table |
|------|--------------|----------------|
| 列定义方式 | 对象数组（dataSource + columns） | 声明式（accessor + header + cell） |
| 分页 | 内建，支持受控/非受控 | 需手动配置 pagination state |
| 行选择 | 无 | 内建 |
| 排序 | 无 | 内建 |
| 筛选 | 无 | 内建 |
| 行展开 | key-based expanded | getRowCanExpand 回调模式 |
| 动画 | 内建 stagger motion | 无，需手动包装 |
| 空态 | 内建 | 无，需手动处理 |
| 加载态 | 内建 | 无，需手动处理 |
| 列宽模式 | 4 种（fixed/auto/fill/flex） | 平台默认 table-layout |

### 迁移方案（如果做）

1. 重写 `data-table.tsx`：内部用 TanStack Table 的 `useReactTable` + `getCoreRowModel`
2. 保留现有 ColumnDef 类型（加适配层，或直接改用 TanStack 类型）
3. 保留 TestID（`data-table-row`）不破坏现有测试
4. 逐个改 14 处业务代码的 column 定义
5. 重写 `data-table.test.tsx`（约 200 行）

### 工作量

- 改动文件：1 个核心 + 14 个业务文件 + 1 个测试文件
- 时间预估：3-5 天
- 同时失去 motion 动画（需要额外的手动包装）

### 建议

**当前不推荐执行**。两个原因：

1. 迁移成本高（14 处 + 测试）
2. 当前 DataTable 已覆盖核心需求，且 TanStack Table 不提供 `loading`/`empty`/`animation` 等能力，仍需要封装

建议保留当前实现。如果未来明确需要列排序/列筛选/行选择等功能，再引入 TanStack Table。

---

## 3. Base UI 替换 Radix UI

### 现状

Radix UI 的使用链路：

```
@radix-ui/react-* (21 个 npm 包)
    → components/ui/* (21 个 shadcn 包装文件，每文件包装 1 个)
        → components/common/* (AppDialog/AppConfirm/AppSelect/AppToggle/AppTooltip 等二次封装)
            → 业务代码 (pages/app 层)
```

**关键事实**：没有业务代码直接 import `@radix-ui`。所有 Radix 的复杂度都已经由 shadcn + common 包装隔离。

### 安装的 Radix 组件

| 包名 | 是否被业务代码间接使用 |
|------|-------------------|
| `@radix-ui/react-alert-dialog` | ✅ 通过 AppConfirm |
| `@radix-ui/react-avatar` | ✅ 用户头像 |
| `@radix-ui/react-checkbox` | ✅ 复选框场景 |
| `@radix-ui/react-collapsible` | ⚠️ 业务代码中直接使用（2 处） |
| `@radix-ui/react-dialog` | ✅ 通过 AppDialog |
| `@radix-ui/react-dropdown-menu` | ✅ 用户菜单 |
| `@radix-ui/react-label` | ✅ 全局表单 |
| `@radix-ui/react-popover` | ✅ 日历选择 |
| `@radix-ui/react-progress` | ❓ 待确认 |
| `@radix-ui/react-radio-group` | ❓ 待确认 |
| `@radix-ui/react-scroll-area` | ❓ 待确认 |
| `@radix-ui/react-select` | ✅ 通过 AppSelect |
| `@radix-ui/react-separator` | ❓ 待确认 |
| `@radix-ui/react-slot` | ✅ Button/DropdownMenu 等 |
| `@radix-ui/react-switch` | ✅ 设置页 |
| `@radix-ui/react-tabs` | ✅ 通过 AppTabs |
| `@radix-ui/react-toggle` | ✅ 通过 AppToggle |
| `@radix-ui/react-toggle-group` | ✅ 表格工具栏 |
| `@radix-ui/react-tooltip` | ✅ 通过 AppTooltip |

### 替换分析

Base UI 替换意味着：

1. 重写 `components/ui/` 下 21 个 shadcn 包装文件，每个改为对应 Base UI + Tailwind
2. `components/common/` 的包装层不需要改动（它们依赖 shadcn 接口而非 Radix 接口）
3. 业务代码完全无感知

### 不推荐原因

- 当前已经三层隔离（Radix → shadcn → common），替换底层对业务无任何影响
- 21 个文件的全量重写工作量极大（估 3-5 天）
- Base UI 发布不到 1 年，React 19 兼容性和社区生态远不如 Radix
- shadcn 的默认选择是 Radix，切换后偏离主流生态

### 建议

**不换**。如果未来 Radix 出现许可/维护问题再评估。

---

## 4. components/common 目录重组和命名统一

### 现状

当前 components/common 结构：

```
平铺文件 (25 个):
  app-select.tsx / app-tabs.tsx / app-toggle.tsx / app-tooltip.tsx    ← app- 前缀
  back-link.tsx / breathing-dot.tsx / confirm-dialog.tsx / copy-button.tsx
  data-empty.tsx / entry-card.tsx / env-badge.tsx / error-banner.tsx
  error-banner-static.tsx / error-boundary.tsx / file-dropzone.tsx
  form-field.tsx / health-dot.tsx / image-preview.tsx / loading-skeleton.tsx
  page-header.tsx / page-hero.tsx / search-input.tsx / section-card.tsx
  settings-card.tsx / stat-card.tsx / status-badge.tsx / submit-button.tsx
  task-status-badge.tsx

子目录 (6 个):
  confirm/   → app-confirm.tsx     (有独立 index.ts 出口)
  data-table/ → data-table.tsx + data-table-skeleton.tsx (有 index.ts)
  dialog/    → app-dialog.tsx      (有 index.ts)
  drawer/    → app-drawer.tsx      (有 index.ts)
  form/      → form.tsx + form-context.ts + form-item.tsx (有 index.ts)
  motion/    → animated.tsx + count-up.tsx + ... (有 index.ts)

顶层出口文件:
  index.ts   ← 混排了直出和子目录 re-export
```

### 发现的问题

| 编号 | 问题 | 详情 |
|------|------|------|
| Q1 | 死文件 | `confirm-dialog.tsx` — 从未被 import，已被 `confirm/app-confirm.tsx` 替代 |
| Q2 | 功能重复 | `form-field.tsx` 和 `form/form-item.tsx` 几乎完全一样（都是 Context 绑定 + label + error） |
| Q3 | 命名不统一 | 4 个用 `app-` 前缀，21 个没有前缀 |
| Q4 | 子目录分布不均衡 | `dialog/` 只放 1 个文件，`drawer/` 只放 1 个，`confirm/` 只放 1 个 |
| Q5 | 类别混杂 | 平铺文件中混合了 display（data-empty）、input（file-dropzone）、feedback（error-banner）、navigation（back-link） |

### 重组方案

#### 第一步：清理（P0，可独立执行）

1. **删除** `confirm-dialog.tsx`（死文件）
2. **合并** `form-field.tsx` → `form/form-item.tsx`，删除 `form-field.tsx`
3. 更新 `index.ts` 移除已删文件的导出

#### 第二步：分类目录 + 统一命名（P2，建议批处理）

所有文件统一 `app-` 前缀 + kebab-case，按功能分类：

```
components/common/
├── form/                   ← 表单 (保留, 清理 form-field.tsx)
│   ├── app-form.tsx
│   ├── app-form-context.ts
│   └── app-form-item.tsx
├── table/                  ← 表格 (重构自 data-table/)
│   ├── app-table.tsx
│   └── app-table-skeleton.tsx
├── dialog/                 ← 弹框类 (合并 confirm/)
│   ├── app-dialog.tsx
│   └── app-confirm.tsx     ← 从 confirm/ 移入
├── overlay/                ← 覆盖层
│   ├── app-drawer.tsx      ← 从 drawer/ 移入
│   └── app-tooltip.tsx
├── display/                ← 展示类
│   ├── app-data-empty.tsx
│   ├── app-status-badge.tsx
│   ├── app-health-dot.tsx
│   ├── app-env-badge.tsx
│   ├── app-breathing-dot.tsx
│   ├── app-task-status-badge.tsx
│   ├── app-stat-card.tsx
│   ├── app-settings-card.tsx
│   ├── app-entry-card.tsx
│   └── app-section-card.tsx
├── feedback/               ← 反馈类
│   ├── app-error-banner.tsx
│   ├── app-error-banner-static.tsx
│   └── app-error-boundary.tsx
├── navigation/             ← 导航类
│   ├── app-back-link.tsx
│   ├── app-page-header.tsx
│   └── app-page-hero.tsx
├── input/                  ← 输入类
│   ├── app-select.tsx
│   ├── app-toggle.tsx
│   ├── app-tabs.tsx
│   ├── app-file-dropzone.tsx
│   ├── app-search-input.tsx
│   └── app-image-preview.tsx
├── button/                 ← 按钮类
│   ├── app-copy-button.tsx
│   ├── app-submit-button.tsx
│   ├── app-loading-skeleton.tsx
│   └── app-env-badge.tsx
├── motion/                 ← 动画 (保留不变)
│   ├── app-animated.tsx
│   ├── app-count-up.tsx
│   ├── app-hover-lift.tsx
│   ├── app-pressable.tsx
│   ├── app-reveal.tsx
│   ├── app-stagger-item.tsx
│   └── app-stagger.tsx
└── index.ts                ← 统一出口，自动 import 所有子目录
```

### 迁移注意事项

- 所有 import 路径需要同步更新（约 180 处引用）
- 建议用批量工具（sed / 脚本）处理 import 重写，减少手工遗漏
- 测试文件路径也要对应更新
- 分阶段执行，每阶段 commit 一次

---

## 5. 组件提取和 shadcn 直用机会

### 原则

- **能用 shadcn 直接替代的**（1-2 个标签，不需要组合）：直接用 shadcn
- **需要组合 3+ shadcn 子组件或原生标签的**：封装成 common 组件
- common 组件本身是封装产物，不需要再被 shadcn 替代

### 扫描结果

#### 发现 1：reject-dialog.tsx 手写 raw `<Dialog>` 模板

`app/[locale]/submissions/_components/reject-dialog.tsx` 直接 import 了 6 个 shadcn 子组件（`Dialog`, `DialogContent`, `DialogDescription`, `DialogFooter`, `DialogHeader`, `DialogTitle`），应该改用 `<AppDialog>`：

```typescript
// 当前
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
// 改为
import { AppDialog } from "@/components/common/dialog/app-dialog";
```

**工作量**：1 个文件，改 import + JSX

#### 发现 2：Collapsible 模式出现 2 处，可提取 common 组件

地点：
- `app/[locale]/submissions/_components/approval-row.tsx`（CollapsibleTrigger + CollapsibleContent）
- `components/chat/message-bubble.tsx`（CollapsibleTrigger + CollapsibleContent）

模式一致（`<Collapsible>` + `<CollapsibleTrigger asChild>` + `<CollapsibleContent>`），可提取：

```typescript
// components/common/app-collapsible.tsx
<AppCollapsible title="" icon? defaultOpen?>
  content
</AppCollapsible>
```

**工作量**：新增 1 个文件，改 2 处业务代码

#### 发现 3：DropdownMenu 可考虑封装 ✅ (2026-06-25 已完成)

多处使用 shadcn `<DropdownMenu>` + `<DropdownMenuTrigger>` + `<DropdownMenuContent>` + `<DropdownMenuItem>` 组合（如 user-menu, admin users table 等），组合 4+ 子组件，符合封装标准。

```typescript
// 已实现的 API
<AppDropdownMenu
  trigger={<Button variant="ghost"><MoreHorizontal /></Button>}
  items={[
    { key: "edit", label: "编辑", icon: <Pencil />, onClick: onEdit },
    { key: "delete", label: "删除", icon: <Trash2 />, variant: "destructive", onClick: onDelete, hidden: !isDeletable },
    { key: "sep", separator: true, label: "" },  // 分隔线
    { key: "logout", label: "登出", onClick: handleLogout },
  ]}
/>
```

**实现情况**：
- 新建 `components/common/app-dropdown-menu.tsx` + `app-dropdown-menu.test.tsx`
- 已迁移 3 处手写 DropdownMenu：`permission-row.tsx`, `role-detail-card.tsx`, `user-menu.tsx`
- 支持：icon / onClick / href(Link) / hidden / disabled / destructive / separator
- 8 个测试全部通过

#### 发现 4：ErrorBanner + AppDialog 组合模式（8+ 处重复）✅ (2026-06-25 已完成)

扫描发现多处弹框内嵌错误提示：

- ✅ `admin/users/_components/reset-password-dialog.tsx`
- ✅ `admin/users/_components/create-invite-dialog.tsx`
- ✅ `admin/permssions/_components/create-role-dialog.tsx`
- ✅ `admin/dicts/_components/dict-item-create-dialog.tsx`
- ✅ `admin/dicts/_components/dict-item-delete-dialog.tsx`
- ✅ `account/settings/_components/change-password-dialog.tsx`
- ✅ `account/settings/_components/change-email-dialog.tsx`
- ✅ `account/settings/_components/request-deletion-dialog.tsx`
- ✅ `account/settings/_components/cancel-deletion-dialog.tsx`

**实现方式**：在 AppDialog 内建 `error` prop，替代手写 `{error && <ErrorBanner variant="destructive" description={error} />}`。

```typescript
// 改造后
<AppDialog
  open={open}
  onOpenChange={onOpenChange}
  title={translate("修改密码")}
  error={state.error}          // ← 自动渲染 ErrorBanner
  errorTestid="password-error"
>
  {/* 表单内容 */}
</AppDialog>
```

**实现情况**：
- AppDialog 新增 `error?: string | null` + `errorTestid?: string` props
- 9 个 dialog 文件全部移除 ErrorBanner import，改用 error prop
- 全部测试通过 (pre-existing failures 无关)

---

## 执行优先级

| 优先级 | 事项 | 影响文件数 | 状态 |
|--------|------|-----------|------|
| P0 | 删 `confirm-dialog.tsx`（死文件） | 1 删 | 待执行 |
| P0 | 合并 `form-field.tsx` → `form/form-item.tsx` | 2 改 | 待执行 |
| P0 | `reject-dialog.tsx` 改 `AppDialog` | 1 改 | 待执行 |
| P1 | Collapsible 提取 common 组件 | 3 文件（新 1 + 改 2） | 待执行 |
| P1 | DropdownMenu 封装 AppDropdownMenu | 新 2 + 改 3 | ✅ 已完成 |
| P2 | ErrorBanner + AppDialog 提取（内建 error slot） | 改 AppDialog + 9 处 | ✅ 已完成 |
| P2 | 目录重组 + 命名统一（批处理） | ~180 处 import | 待执行 |
| P3 | TanStack Form 替换 react-hook-form | 2 文件 | 待评估 |
| - | TanStack Table 重构 DataTable | 16 文件 | **不推荐** |
| - | Base UI 替换 Radix UI | 21 文件 | **不推荐** |

---

## 关联文档

- [项目代码质量铁律](../../../CLAUDE.md)
- [前端局部约定](../../../packages/web/CLAUDE.md)
- [全局开发规范](../../../../.claude/CLAUDE.md)
