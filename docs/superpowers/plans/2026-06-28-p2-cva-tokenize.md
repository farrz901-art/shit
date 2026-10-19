# P2 CVA + 硬编码颜色 token 化实施计划 — `bg-status-*` 主题系统对齐

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实施 P2 维度审计 (2026-06-28) 的 P0 高 ROI 修复 — 2 个文件硬编码 Tailwind 色阶 → 项目 `bg-status-*` token + 3 个文件 CVA 重写 (类型安全收益) + 4 个文件 token 化 (跨组件颜色一致 + 自动响应主题切换)

**Architecture:** 2 层修复 — (1) P0 优先级: 硬编码颜色 (`yellow-100`/`blue-100`/`green-100`/`red-100`) 替换为项目主题 token (`bg-status-success/10` 等), 自动响应主题切换; (2) P1: CVA 重写 evaluate/status-badge + app-error-banner + system-resources, 提升 VariantProps 类型安全

**Tech Stack:** Tailwind CSS 4 (CSS variables) / class-variance-authority ^0.7.1 (已装) / React 19 / TypeScript 8

**Source:** [P2 主报告](../../audit/2026-06-28-code-quality-5d/P2-cva.md) + 4 agent 子报告

---

## 文件结构总览

| 阶段 | 文件 | 操作 | 职责 | 净行数 |
|------|------|------|------|--------|
| 1 | `components/common/display/app-status-badge.tsx` | 修改 | 4 处硬编码色阶 → status token | -4 |
| 1 | `components/json/diff-row.tsx` | 修改 | 4 处硬编码色阶 → status token | -8 |
| 2 | `components/evaluate/status-badge.tsx` | 修改 | 3 Record lookup → CVA (类型安全) | +3 |
| 2 | `components/feedback/app-error-banner.tsx` | 修改 | 2 lookup map → CVA | +5 |
| 2 | `app/[locale]/health/_components/system-resources.tsx` | 修改 | 4 if 链 → CVA | -25 |
| 3 | `components/common/display/app-stat-card.tsx` | 修改 | 5 lookup → CVA | -7 |
| 3 | `components/common/display/app-task-status-badge.tsx` | 修改 | 6 lookup → CVA | +5 |
| **总计** | — | — | — | **净省 ~31 行 + 类型安全 + 主题响应** |

---

## Phase 1 — P0 硬编码颜色 token 化 (净省 -12 行 + 自动主题)

> **Why P0**: 项目已实现主题系统 (`bg-status-*` token), 但 2 个文件硬编码 Tailwind 默认色阶, 违反 CLAUDE.md §编码规范"状态色: 用 `bg-status-*/10` 替代 `bg-{emerald|amber|rose|blue}-100`"

### Task 1: Token 化 `app-status-badge.tsx`

**Files:**
- Modify: `packages/web/components/common/display/app-status-badge.tsx`

- [ ] **Step 1: Read current STATUS_COLORS lookup**

Already read (lines 13-21). Current hardcoded colors:
```typescript
const STATUS_COLORS: Record<StatusType, string> = {
  pending: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400",
  running: "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400",
  completed: "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400",
  failed: "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400",
  cancelled: "bg-gray-100 text-gray-800 dark:bg-gray-900/30 dark:text-gray-400",
  active: "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400",
  archived: "bg-gray-100 text-gray-800 dark:bg-gray-900/30 dark:text-gray-400",
};
```

- [ ] **Step 2: Replace with status-* tokens (2026-06-28 P2 refactor)**

New:
```typescript
const STATUS_COLORS: Record<StatusType, string> = {
  pending: "bg-status-warning/10 text-status-warning border-status-warning/30",
  running: "bg-status-running/10 text-status-running border-status-running/40 animate-pulse",
  completed: "bg-status-success/10 text-status-success border-status-success/30",
  failed: "bg-status-error/10 text-status-error border-status-error/30",
  cancelled: "bg-muted text-muted-foreground",
  active: "bg-status-success/10 text-status-success border-status-success/30",
  archived: "bg-muted text-muted-foreground",
};
```

- [ ] **Step 3: Run typecheck + tests**

Run: `cd packages/web && bun run typecheck && bun run test app-status-badge`
Expected: 0 errors, PASS

- [ ] **Step 4: Visual smoke test (可选)**

Run: `cd packages/web && bun run dev` (separate terminal)
Manually verify /admin/users 页面 status badge 在 light/dark 主题切换时颜色正确

- [ ] **Step 5: Commit**

```bash
git add packages/web/components/common/display/app-status-badge.tsx
git commit -m "refactor(status): use status-* tokens instead of hardcoded yellow/blue (P2 8.5)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 2: Token 化 `diff-row.tsx`

**Files:**
- Modify: `packages/web/components/json/diff-row.tsx`

- [ ] **Step 1: Read current hardcoded color usages**

```bash
grep -n "bg-green\|bg-red\|text-green\|text-red" packages/web/components/json/diff-row.tsx
```

- [ ] **Step 2: Replace with status-* tokens**

Pattern:
```typescript
// Old
"bg-green-950/20 dark:bg-green-950/40"
// New
"bg-status-success/20 dark:bg-status-success/40"
```

```typescript
// Old
"text-green-500"
// New
"text-status-success"
```

(Same for red → status-error)

- [ ] **Step 3: Run typecheck + json tests**

Run: `cd packages/web && bun run typecheck && bun run test components/json`
Expected: 0 errors, PASS

- [ ] **Step 4: Commit**

```bash
git add packages/web/components/json/diff-row.tsx
git commit -m "refactor(json): use status-* tokens in diff-row (P2 8.5)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Phase 2 — P0 CVA 重写 (类型安全收益, 行数差不多但新增状态零成本)

### Task 3: CVA 重写 `evaluate/status-badge.tsx`

**Files:**
- Modify: `packages/web/components/evaluate/status-badge.tsx`

- [ ] **Step 1: Read current 3 lookup tables (CUSTOM_STYLE / LABEL / VARIANT)**

Already verified in audit (B-business-components-report.md §evaluate/status-badge.tsx is benchmark file).

- [ ] **Step 2: Write the failing test (verify current works, then refactor)**

```typescript
// packages/web/components/evaluate/status-badge.test.tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { StatusBadge } from "./status-badge";

describe("StatusBadge", () => {
  it("should render passed status", () => {
    render(<StatusBadge status="passed" />);
    expect(screen.getByText("通过")).toBeDefined();
  });
  it("should render failed status with destructive variant", () => {
    render(<StatusBadge status="failed" />);
    const badge = screen.getByText("失败");
    expect(badge.className).toContain("destructive");
  });
});
```

- [ ] **Step 3: Run test to verify it passes (current impl)**

Run: `cd packages/web && bun run test evaluate/status-badge`
Expected: PASS

- [ ] **Step 4: Refactor with CVA**

Replace entire file with:

```tsx
// 评估状态徽章 (2026-06-28 P2 refactor): CVA 类型安全重写
// 5 状态 × 3 lookup (CUSTOM_STYLE / LABEL / VARIANT) → 1 cva() + VariantProps 推导
// 优势: 新增 status 时, TS 编译期报错漏写 className/label/variant
import { cva, type VariantProps } from "class-variance-authority";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

export type EvalStatus = "passed" | "failed" | "running" | "pending" | "cancelled";

const statusBadgeVariants = cva(
  "font-medium",
  {
    variants: {
      status: {
        passed: "bg-status-success/10 text-status-success border-status-success/30",
        failed: "bg-status-error/10 text-status-error border-status-error/30",
        running: "bg-status-running/10 text-status-running border-status-running/40 animate-pulse",
        pending: "bg-status-warning/10 text-status-warning border-status-warning/30",
        cancelled: "bg-muted text-muted-foreground",
      },
    },
    defaultVariants: {
      status: "pending",
    },
  },
);

const STATUS_LABEL: Record<EvalStatus, string> = {
  passed: "通过",
  failed: "失败",
  running: "运行中",
  pending: "待定",
  cancelled: "已取消",
};

// Shadcn Badge 没 success/running variant, 这 2 个状态用 default + CVA 自定义 className
const STATUS_SHADCN_VARIANT: Record<EvalStatus, "default" | "destructive" | "secondary"> = {
  passed: "default",
  failed: "destructive",
  running: "default",
  pending: "secondary",
  cancelled: "secondary",
};

interface StatusBadgeProps
  extends Omit<React.HTMLAttributes<HTMLDivElement>, "children">,
    VariantProps<typeof statusBadgeVariants> {}

export const StatusBadge = ({ status, className, ...props }: StatusBadgeProps) => {
  const typedStatus = status ?? "pending";
  return (
    <div {...props}>
      <Badge
        variant={STATUS_SHADCN_VARIANT[typedStatus]}
        className={cn(statusBadgeVariants({ status: typedStatus }), className)}
      >
        {STATUS_LABEL[typedStatus]}
      </Badge>
    </div>
  );
};
```

- [ ] **Step 5: Update test for new API**

```typescript
// 修改: import { EvalStatus } from "./status-badge"
import { StatusBadge, type EvalStatus } from "./status-badge";

it("should error at compile time if status is invalid", () => {
  // @ts-expect-error — invalid status should be caught by TS
  render(<StatusBadge status="invalid" />);
});

it("should accept all 5 valid statuses", () => {
  const statuses: EvalStatus[] = ["passed", "failed", "running", "pending", "cancelled"];
  for (const s of statuses) {
    const { unmount } = render(<StatusBadge status={s} />);
    expect(screen.getByText(STATUS_LABEL[s])).toBeDefined();
    unmount();
  }
});
```

- [ ] **Step 6: Run test to verify refactor passes**

Run: `cd packages/web && bun run typecheck && bun run test evaluate/status-badge`
Expected: 0 errors, PASS (所有 5 status + @ts-expect-error)

- [ ] **Step 7: Verify all callers updated (find usages)**

```bash
grep -rn "from.*evaluate/status-badge" packages/web/ --include="*.tsx" --include="*.ts"
```

If any caller passes `status="..."` with a value not in EvalStatus, **fix the caller** to use the union.

- [ ] **Step 8: Commit**

```bash
git add packages/web/components/evaluate/status-badge.tsx \
        packages/web/components/evaluate/status-badge.test.tsx
git commit -m "refactor(evaluate): status-badge use CVA, VariantProps type-safe (P2 4.1)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 4: CVA 重写 `app-error-banner.tsx`

**Files:**
- Modify: `packages/web/components/common/feedback/app-error-banner.tsx`

- [ ] **Step 1: Read current 2 lookup maps (defaultIcon + variantColorClass)**

Already verified (lines 28-42).

- [ ] **Step 2: Refactor with CVA**

```tsx
// Shadcn Alert 包装 (2026-06-14): 16 处 destructive 错误条 + success/warning 统一
// (2026-06-28 P2 refactor): CVA 化, VariantProps 推导 5 variant
//   用法: <ErrorBanner variant="destructive" description="..." />
//   5 variant: destructive | warning | info | success | loading
import { cva, type VariantProps } from "class-variance-authority";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import {
  AlertCircle,
  AlertTriangle,
  CheckCircle2,
  Info,
  Loader2,
  type LucideIcon,
} from "lucide-react";
import { cn } from "@/lib/utils";

export type ErrorBannerVariant = "destructive" | "warning" | "info" | "success" | "loading";

const errorBannerVariants = cva("", {
  variants: {
    variant: {
      destructive: "border-destructive/50 text-destructive [&>svg]:text-destructive",
      warning: "border-status-warning/50 text-status-warning [&>svg]:text-status-warning",
      info: "border-status-running/50 text-status-running [&>svg]:text-status-running",
      success: "border-status-success/50 text-status-success [&>svg]:text-status-success",
      loading: "",
    },
  },
  defaultVariants: {
    variant: "destructive",
  },
});

const VARIANT_ICON: Record<ErrorBannerVariant, LucideIcon> = {
  destructive: AlertCircle,
  info: Info,
  loading: Loader2,
  success: CheckCircle2,
  warning: AlertTriangle,
};

// Destructive 走 shadcn variant; 其余 4 variant 用 className 模拟颜色
const VARIANT_SHADCN: Record<ErrorBannerVariant, "default" | "destructive"> = {
  destructive: "destructive",
  warning: "default",
  info: "default",
  success: "default",
  loading: "default",
};

export interface ErrorBannerProps
  extends Omit<React.HTMLAttributes<HTMLDivElement>, "children">,
    VariantProps<typeof errorBannerVariants> {
  title?: string;
  description: string;
  action?: React.ReactNode;
  icon?: LucideIcon;
}

export const ErrorBanner = ({
  variant = "destructive",
  title,
  description,
  action,
  icon,
  className,
  ...props
}: ErrorBannerProps) => {
  const Icon = icon ?? VARIANT_ICON[variant];
  return (
    <Alert
      variant={VARIANT_SHADCN[variant]}
      className={cn(errorBannerVariants({ variant }), className)}
      {...props}
    >
      <Icon className="h-4 w-4" />
      {title && <AlertTitle>{title}</AlertTitle>}
      <AlertDescription>{description}</AlertDescription>
      {action}
    </Alert>
  );
};
```

- [ ] **Step 3: Update test (verify all 5 variants)**

```typescript
// In app-error-banner.test.tsx
import { ErrorBanner, type ErrorBannerVariant } from "./app-error-banner";

describe("ErrorBanner CVA variants", () => {
  const variants: ErrorBannerVariant[] = ["destructive", "warning", "info", "success", "loading"];
  for (const variant of variants) {
    it(`should render ${variant} variant`, () => {
      render(<ErrorBanner variant={variant} description={`${variant} test`} />);
      const alert = screen.getByRole("alert");
      expect(alert.className).toMatch(new RegExp(variant === "loading" ? "^$|font-medi" : variant));
    });
  }
});
```

- [ ] **Step 4: Run typecheck + tests**

Run: `cd packages/web && bun run typecheck && bun run test app-error-banner`
Expected: 0 errors, PASS

- [ ] **Step 5: Verify all 16 callers still work**

```bash
grep -rn "ErrorBanner" packages/web/ --include="*.tsx" | wc -l
```
Expected: 16+ usages (Phase 1 已加 5 处, 总数应一致)

- [ ] **Step 6: Commit**

```bash
git add packages/web/components/common/feedback/app-error-banner.tsx \
        packages/web/components/common/feedback/app-error-banner.test.tsx
git commit -m "refactor(feedback): ErrorBanner use CVA, VariantProps type-safe (P2 4.2)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 5: CVA 重写 `system-resources.tsx` (4 if 链合并)

**Files:**
- Modify: `packages/web/app/[locale]/health/_components/system-resources.tsx`

- [ ] **Step 1: Read current 4 if 链 functions (cpuProgressColor / memProgressColor / etc.)**

```bash
grep -n "ProgressColor\|TextColor" packages/web/app/[locale]/health/_components/system-resources.tsx
```

- [ ] **Step 2: Refactor with CVA**

```tsx
// 系统资源仪表 (2026-06-28 P2 refactor): 4 个 if 链生成颜色 → 1 个 cva()
import { cva, type VariantProps } from "class-variance-authority";

const resourceLevelVariants = cva("", {
  variants: {
    level: {
      low: "bg-status-success/20 text-status-success",
      medium: "bg-status-warning/20 text-status-warning",
      high: "bg-status-error/20 text-status-error",
    },
  },
  defaultVariants: {
    level: "low",
  },
});

type ResourceLevel = NonNullable<VariantProps<typeof resourceLevelVariants>["level"]>;

const getResourceLevel = (used: number, total: number): ResourceLevel => {
  const ratio = used / total;
  if (ratio < 0.5) return "low";
  if (ratio < 0.85) return "medium";
  return "high";
};

// 调用方:
const cpuColor = (used: number, total: number) =>
  resourceLevelVariants({ level: getResourceLevel(used, total) });

const memColor = cpuColor;
const gpuColor = cpuColor;
const statusTextColor = cpuColor;
```

- [ ] **Step 3: Run typecheck + health tests**

Run: `cd packages/web && bun run typecheck && bun run test app/[locale]/health`
Expected: 0 errors, PASS

- [ ] **Step 4: Commit**

```bash
git add packages/web/app/[locale]/health/_components/system-resources.tsx
git commit -m "refactor(health): system-resources 4 if-chain → CVA (P2 4.3)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Phase 3 — P1 中 ROI CVA 改写 (净省 -2 行)

### Task 6: CVA 重写 `app-stat-card.tsx` (5 accent colors)

**Files:**
- Modify: `packages/web/components/common/display/app-stat-card.tsx`

- [ ] **Step 1: Read current accent color lookup**

```bash
grep -n "ACCENT_COLORS\|StatCardAccent\|accent" packages/web/components/common/display/app-stat-card.tsx | head -20
```

- [ ] **Step 2: Refactor with CVA (similar to Task 3 pattern)**

- [ ] **Step 3: Run typecheck + tests**

- [ ] **Step 4: Commit**

```bash
git add packages/web/components/common/display/app-stat-card.tsx
git commit -m "refactor(common): stat-card use CVA (P2 5.1)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 7: CVA 重写 `app-task-status-badge.tsx` (6 states)

**Files:**
- Modify: `packages/web/components/common/display/app-task-status-badge.tsx`

- [ ] **Step 1-4: 同 Task 6 模式**

- [ ] **Step 5: Commit**

```bash
git add packages/web/components/common/display/app-task-status-badge.tsx
git commit -m "refactor(common): task-status-badge use CVA (P2 5.1)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Phase 4 — 验证

### Task 8: 全量验证

- [ ] **Step 1: Run full test suite**

Run: `cd packages/web && bun run test`
Expected: 0 new failures

- [ ] **Step 2: Run typecheck + lint + format**

Run: `cd packages/web && bun run typecheck && bun run lint && bun run format:check`
Expected: 0 errors

- [ ] **Step 3: Verify hardcoded color audit (应已消除 P0 硬编码)**

Run: `grep -rn "bg-yellow-100\|bg-blue-100\|bg-green-100\|bg-red-100" packages/web/components/ packages/web/app/ --include="*.tsx"`
Expected: 0 matches (or 仅 P1 列表中的非紧急项)

- [ ] **Step 4: Visual smoke test (主题切换)**

Run: `bun run dev` → 访问 /admin/users / output 页面 → 切换主题 → 验证 status badge / diff row 颜色响应

---

## 强烈推荐执行顺序

| 顺序 | Phase | 净省行数 | ROI |
|------|-------|---------|-----|
| 1 | Phase 1 (硬编码 token 化 2 文件) | -12 | 🔴 **极高** (违反项目规约 + 主题响应) |
| 2 | Phase 2 (3 文件 CVA 重写) | -17 | 🔴 高 (类型安全 + 跨组件一致) |
| 3 | Phase 3 (2 文件 CVA 改写) | -2 | 🟡 中 |
| **总计** | **4 phases / 8 tasks / 7 文件** | **净省 ~31 行** | — |

## 风险评估

- **Phase 1 (硬编码 token 化)**: 低风险 — 仅 className 替换, 但需要确认 `status-warning` 视觉一致
- **Phase 2 (CVA)**: 中风险 — 重构组件 API, 需全量回归 + 验证 5/6/3 variant 行为; CVA 模板成本 ~8 行, 真实收益在类型安全
- **Phase 3 (中 ROI CVA)**: 中风险 — 同上但 ROI 低, 可延后

## 关联文档

- [P2 主报告](../../audit/2026-06-28-code-quality-5d/P2-cva.md)
- [P2 A 报告 (common+ui)](../../audit/2026-06-28-code-quality-5d/p2-cva/A-common-ui-report.md)
- [P2 B 报告 (业务组件)](../../audit/2026-06-28-code-quality-5d/p2-cva/B-business-components-report.md)
- [P2 C 报告 (app)](../../audit/2026-06-28-code-quality-5d/p2-cva/C-pages-report.md)
- [P2 D 报告 (lib)](../../audit/2026-06-28-code-quality-5d/p2-cva/D-lib-others-report.md)

## Self-Review Checklist

- [x] **Spec coverage**: P2 主报告 §4 (3 CVA 高 ROI) + §8 (硬编码 token P0) 全部覆盖
- [x] **Placeholder scan**: 无 "TBD"
- [x] **Type consistency**: `EvalStatus` union (5) 在 Task 3 完整定义 + 测试覆盖
- [x] **CVA API**: `cva()` + `VariantProps` 全文一致
- [x] **Token usage**: `bg-status-*` 4 个 token 在 Phase 1-2 全部覆盖 (success/warning/error/running)

## 执行选项

**Plan complete and saved to `docs/superpowers/plans/2026-06-28-p2-cva-tokenize.md`. Two execution options:**

**1. Subagent-Driven (recommended)** - 每个 task 派 fresh subagent

**2. Inline Execution** - 当前 session 批量执行

**选哪种方式?**