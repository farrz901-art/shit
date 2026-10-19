# shadcn 化 + 抽封装 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 30+ 业务文件从手写 `<input>`/`<select>`/`<table>`/`<div className="fixed inset-0 bg-black/50">` 等切到 shadcn 或项目自有封装, 抽 5 个新 antd 风格封装 (`AppSelect` / `ErrorBanner` / `CopyButton` / `FormField` + 新 `AppToggle`) + 升级 `FormItem`, CLAUDE.md 加 3 段封装约定, 净减 ≥ 1500 行.

**Spec:** [docs/superpowers/specs/2026-06-14-shadcn-unification-design.md](../specs/2026-06-14-shadcn-unification-design.md)

**Architecture:**

- 5 个新封装全用 antd 风格 (`options={[...]}` + `value` + `onChange` 一行) 跟现有 `AppDialog` / `AppConfirm` 一致
- `<FormItem>` 升级接 shadcn `<Label>` + 错误展示, 抽 `<FormField>` 顶替 6 表单模板
- 16 处 destructive 错误条统一 `<ErrorBanner>`, 4 处 `navigator.clipboard` 统一 `<CopyButton>`
- 5 阶段 12 commit, 按 Layer A→B→C→D→E 顺序 (新基础设施 → admin → 6 表单 → 业务+错误条 → 文档)

**Tech Stack:** Next.js 16, React 19, TypeScript, shadcn/ui (33 套件已装), tailwindcss 4, vitest + jsdom, sonner toast.

---

## File Structure (新增/修改/删除, 全部)

### 新建 5 个新封装 + 升级 1 个
| File | Change |
|---|---|
| `packages/web/components/common/AppSelect.tsx` | Create: antd 风格 Select 包装 (替 6-行 shadcn 模板) |
| `packages/web/components/common/AppToggle.tsx` | Create: shadcn ToggleGroup 单选包装 (替 decode view 切换) |
| `packages/web/components/common/ErrorBanner.tsx` | Create: shadcn Alert 包装, 5 variant (16 处统一) |
| `packages/web/components/common/CopyButton.tsx` | Create: clipboard + 1.5s 反馈 (4 处统一) |
| `packages/web/components/common/FormField.tsx` | Create: FormItem 升级, 错误展示 + Label (6 表单模板) |
| `components/common/form/form-item.tsx` | Modify: 接 shadcn `<Label>` + 错误展示 |

### 新建 5 个单测
| File | Change |
|---|---|
| `packages/web/components/common/app-select.test.tsx` | Create: 5 case (同目录) |
| `packages/web/components/common/app-toggle.test.tsx` | Create: 3 case |
| `packages/web/components/common/error-banner.test.tsx` | Create: 5 variant |
| `packages/web/components/common/copy-button.test.tsx` | Create: 3 case (mock clipboard) |
| `packages/web/components/common/form-field.test.tsx` | Create: 4 case |

### 修改 25 个文件 (按 P0-P4 优先级)

#### P0 admin 4 文件
| File | Change |
|---|---|
| `app/[locale]/admin/users/_components/AdminUsersTable.tsx` | DataTable + AppSelect + Input + Pagination + AppConfirm + ErrorBanner |
| `app/[locale]/admin/invites/_components/AdminInvitesTable.tsx` | DataTable + AppConfirm + ErrorBanner |
| `app/[locale]/admin/users/_components/CreateInviteDialog.tsx` | AppDialog + Input + CopyButton + ErrorBanner + Form + FormField |
| `app/[locale]/admin/users/_components/ResetPasswordDialog.tsx` | AppDialog + CopyButton + ErrorBanner |

#### P1 4 表单
| File | Change |
|---|---|
| `app/[locale]/login/page.tsx` | Form + FormField + ErrorBanner |
| `app/[locale]/forgot-password/page.tsx` | Form + FormField + ErrorBanner + CopyButton |
| `app/[locale]/reset-password/page.tsx` | Form + FormField + ErrorBanner |
| `app/[locale]/invite/[token]/page.tsx` | Form + FormField + ErrorBanner |

#### P2 业务 4 文件
| File | Change |
|---|---|
| `app/[locale]/evaluate/new/_components/EvaluateNewForm.tsx` | FileDropzone + DataTable (CSV 预览) + ErrorBanner |
| `app/[locale]/knowledge/qa/_components/QASubmitForm.tsx` | shadcn Checkbox + ErrorBanner |
| `app/[locale]/decode/page.tsx` | ErrorBanner + CopyButton + AppToggle (cards/llm 切换) |
| `app/[locale]/submissions/_components/RejectDialog.tsx` | AppSelect (REASONS 列表) |

#### P3 5 Select 用户侧
| File | Change |
|---|---|
| `components/knowledge/DatasetSwitcher.tsx` | AppSelect |
| `components/knowledge/DomainSwitcher.tsx` | AppSelect |
| `components/knowledge/SchemaFieldRenderer.tsx` | AppSelect |
| `components/settings/settings-dialog.tsx` | AppSelect (语言/主题) |

#### P4 16 处错误条 (部分跟 P0-P2 合并, 这里列纯 D 阶段)
| File | Line |
|---|---|
| `app/[locale]/output/_components/OutputListClient.tsx` | 195 |
| `app/[locale]/knowledge/triples/_components/TriplesForm.tsx` | 384 |
| `app/[locale]/knowledge/batch/page.tsx` | 142 |
| `app/[locale]/knowledge/documents/import/_components/ImportCommitCard.tsx` | 123 |
| `app/[locale]/output/new/page.tsx` | 145 |
| `app/[locale]/output/[task_id]/[file]/page.tsx` | 64 |
| `app/[locale]/output/[task_id]/_components/TaskDetailClient.tsx` | 156 |

### 修改文档
| File | Change |
|---|---|
| `packages/web/CLAUDE.md` | Modify: 加 3 段封装约定 |

---

## 通用约定 (所有 Task 遵守)

- **测跑**: `cd packages/web && bunx vitest run <path>` (按 [[feedback-no-full-vitest-during-dev]] 一次只测改过的, 不用 `bun run test` 触发 lint-staged 链)
- **TDD**: 先写失败测试 (vitest) → 实现 → 绿; lib 封装要单测 4-5 个 case 覆盖关键 API
- **i18n**: 不补缺失 key, 现状硬编码中文就保留硬编码
- **className 一致性**: 走 `cn()` from `@/lib/utils`; 不重复 tailwind
- **data-testid**: 新组件必填 `dataTestid?: string` prop, 默认走 `<component data-testid>`; 业务调用方必传
- **commit 拆分**: 按 [[feedback-commit-in-batches-for-large-changes]] 每个 lib 1 commit, 每个业务文件 1 commit
- **branch**: 全程在 `feature/shadcn-unification` (新分支, 从 master 拉)

---

# Phase 1: 新基础设施 5 commit (Task 1-5)

> 抽 5 个新封装 + 升级 FormItem, 每个 lib 1 commit. 先全部抽完再迁业务, 避免边迁边封装.

## Task 1: AppSelect (1 commit `feat(ui): AppSelect antd 风格 Select 包装`)

**Files:**
- Create: `packages/web/components/common/AppSelect.tsx`
- Create: `packages/web/components/common/app-select.test.tsx`

**Step 1: 写失败测试 (TDD-red)**

```typescript
// app-select.test.tsx — 5 case
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { AppSelect } from "./app-select";

const options = [
  { label: "全部", value: "all" },
  { label: "账号", value: "account" },
  { label: "anon", value: "anon" },
];

describe("AppSelect", () => {
  it("render trigger with dataTestid", () => {
    render(<AppSelect options={options} dataTestid="kind" />);
    expect(screen.getByTestId("kind")).toBeInTheDocument();
  });

  it("respect value prop as controlled (display selected label)", () => {
    render(<AppSelect options={options} value="anon" onChange={() => {}} dataTestid="kind" />);
    expect(screen.getByText("anon")).toBeInTheDocument();
  });

  it("show placeholder when value undefined", () => {
    render(<AppSelect options={options} placeholder="选类型" dataTestid="kind" />);
    expect(screen.getByText("选类型")).toBeInTheDocument();
  });

  it("disabled disable trigger", () => {
    render(<AppSelect options={options} disabled dataTestid="kind" />);
    expect(screen.getByTestId("kind")).toBeDisabled();
  });

  it("onChange prop accepted (smoke test, jsdom 测不到 portal)", () => {
    const onChange = vi.fn();
    render(<AppSelect options={options} value="all" onChange={onChange} dataTestid="kind" />);
    expect(screen.getByTestId("kind")).toBeInTheDocument();
  });
});
```

**Step 2: 实现 AppSelect**

```typescript
// AppSelect.tsx
"use client";
// antd 风格 Select 包装: 替 shadcn Select 6 子件 (Root/Trigger/Value/Content/Item/Icon) 模板
//   用法: <AppSelect options={[{value,label}]} value={x} onChange={setX} />
//   关联 [[feedback-no-shim-no-minimal-changes]] (shadcn 原始模板啰嗦, antd 风格 1 行)
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

export interface AppSelectOption {
  value: string;
  label: string;
  disabled?: boolean;
}

export interface AppSelectProps {
  options: AppSelectOption[];
  value?: string;
  defaultValue?: string;
  onChange?: (value: string) => void;
  placeholder?: string;
  disabled?: boolean;
  className?: string;
  dataTestid?: string;
}

export function AppSelect({
  options, value, defaultValue, onChange, placeholder, disabled, className, dataTestid,
}: AppSelectProps) {
  return (
    <Select value={value} defaultValue={defaultValue} onValueChange={onChange} disabled={disabled}>
      <SelectTrigger className={className} data-testid={dataTestid}>
        <SelectValue placeholder={placeholder} />
      </SelectTrigger>
      <SelectContent>
        {options.map((opt) => (
          <SelectItem key={opt.value} value={opt.value} disabled={opt.disabled}>
            {opt.label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
```

**Step 3: 跑测试 → 绿, 提 commit**

- `bunx vitest run app-select` 期望 5/5 绿
- commit: `feat(ui): AppSelect antd 风格 Select 包装`

## Task 2: AppToggle (1 commit `feat(ui): AppToggle 替 decode view 切换按钮组`)

**Files:**
- Create: `packages/web/components/common/AppToggle.tsx`
- Create: `packages/web/components/common/app-toggle.test.tsx`

**实现:**

```typescript
// AppToggle.tsx
"use client";
// shadcn ToggleGroup type="single" 包装: 替 decode/page.tsx 手写 button 按钮组
//   用法: <AppToggle options={[{value,label}]} value={x} onChange={setX} />
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";

export interface AppToggleOption { value: string; label: string; }
export interface AppToggleProps {
  options: AppToggleOption[];
  value?: string;
  defaultValue?: string;
  onChange?: (value: string) => void;
  className?: string;
  dataTestid?: string;
}

export function AppToggle({ options, value, defaultValue, onChange, className, dataTestid }: AppToggleProps) {
  return (
    <ToggleGroup type="single" value={value} defaultValue={defaultValue} onValueChange={onChange} className={className}>
      {options.map((opt) => (
        <ToggleGroupItem
          key={opt.value}
          value={opt.value}
          data-testid={dataTestid ? `${dataTestid}-${opt.value}` : undefined}
        >
          {opt.label}
        </ToggleGroupItem>
      ))}
    </ToggleGroup>
  );
}
```

3 case: render / value 受控 / disabled state.

## Task 3: ErrorBanner (1 commit `feat(ui): ErrorBanner shadcn Alert 包装, 5 variant`)

**Files:**
- Create: `packages/web/components/common/ErrorBanner.tsx`
- Create: `packages/web/components/common/error-banner.test.tsx`

```typescript
// ErrorBanner.tsx
"use client";
// 16 处 destructive 错误条 + 3 处 success/warning 统一
// 内部走 shadcn <Alert> (已装) + <AlertTitle> + <AlertDescription>
import { AlertCircle, AlertTriangle, CheckCircle2, Info, Loader2 } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { cn } from "@/lib/utils";

export type ErrorBannerVariant = "destructive" | "warning" | "info" | "success" | "loading";

export interface ErrorBannerProps {
  variant?: ErrorBannerVariant;
  title?: string;
  description: string;       // 必填
  action?: React.ReactNode;  // 右侧按钮 (例 "重试" / "复制")
  icon?: LucideIcon;
  className?: string;
  dataTestid?: string;
}

const defaultIcon: Record<ErrorBannerVariant, LucideIcon> = {
  destructive: AlertCircle,
  info: Info,
  loading: Loader2,
  success: CheckCircle2,
  warning: AlertTriangle,
};

export function ErrorBanner({
  variant = "destructive", title, description, action, icon, className, dataTestid,
}: ErrorBannerProps) {
  const Icon = icon ?? defaultIcon[variant];
  return (
    <Alert variant={variant === "loading" ? "default" : variant} className={className} data-testid={dataTestid}>
      <Icon className={cn("h-4 w-4", variant === "loading" && "animate-spin")} />
      {title && <AlertTitle>{title}</AlertTitle>}
      <AlertDescription className="flex items-center justify-between gap-3">
        <span>{description}</span>
        {action}
      </AlertDescription>
    </Alert>
  );
}
```

5 case: 5 variant 渲染各 1 个 + `action` slot 渲染.

## Task 4: CopyButton (1 commit `feat(ui): CopyButton clipboard + 反馈`)

**Files:**
- Create: `packages/web/components/common/CopyButton.tsx`
- Create: `packages/web/components/common/copy-button.test.tsx`

```typescript
// CopyButton.tsx
"use client";
// 4 处 navigator.clipboard 统一, 替手写 onClick={() => navigator.clipboard.writeText(...)}
// 失败走 sonner toast.error, 成功 1.5s "已复制 ✓" 反馈
import { useState, useTransition } from "react";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";

export interface CopyButtonProps {
  text: string;
  label?: string;
  successLabel?: string;
  variant?: "default" | "outline" | "ghost";
  size?: "default" | "sm" | "lg" | "icon";
  onCopied?: () => void;
  className?: string;
  dataTestid?: string;
}

export function CopyButton({
  text, label = "复制", successLabel = "已复制 ✓",
  variant = "default", size = "default",
  onCopied, className, dataTestid,
}: CopyButtonProps) {
  const [copied, setCopied] = useState(false);
  const [pending, startTransition] = useTransition();

  const onClick = () => {
    startTransition(async () => {
      try {
        await navigator.clipboard.writeText(text);
        setCopied(true);
        onCopied?.();
        setTimeout(() => setCopied(false), 1500);
      } catch (error) {
        toast.error(error instanceof Error ? error.message : "复制失败");
      }
    });
  };

  return (
    <Button type="button" variant={variant} size={size} onClick={onClick} disabled={pending} className={className} data-testid={dataTestid}>
      {copied ? successLabel : label}
    </Button>
  );
}
```

3 case: render label / click 复制后变 successLabel / 复制失败 (mock clipboard reject).

## Task 5: FormField + 升级 FormItem (1 commit `feat(ui): FormField + 升级 FormItem`)

**Files:**
- Modify: `components/common/form/form-item.tsx` (升级: 接 shadcn Label + 错误展示)
- Create: `packages/web/components/common/FormField.tsx`
- Create: `packages/web/components/common/form-field.test.tsx`

**Step 1: 升级 form-item.tsx**

加 shadcn Label + 错误展示 (改 form-item 内部, 不破坏现有调用方)

**Step 2: 抽 FormField**

```typescript
// FormField.tsx
"use client";
// 替 6 表单重复模板: <div><label.eyebrow>{label}</label>{children}</div>
// 内部接 Form context (从 form-context.ts 读 errors / values / setFieldValue)
import { type ReactNode } from "react";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";
import { useFormContext } from "./form/form-context";

export interface FormFieldProps {
  name: string;
  label: string;
  help?: string;
  required?: boolean;
  children: ReactNode;
  className?: string;
}

export function FormField({ name, label, help, required, children, className }: FormFieldProps) {
  const { errors, touched } = useFormContext();
  const error = touched[name] ? errors[name] : undefined;
  return (
    <div className={cn("space-y-1.5", className)}>
      <Label htmlFor={name}>
        {label}
        {required && <span className="text-destructive ml-1">*</span>}
      </Label>
      {children}
      {error && <p className="text-sm text-destructive">{error}</p>}
      {help && !error && <p className="text-sm text-muted-foreground">{help}</p>}
    </div>
  );
}
```

4 case: 渲染 label / required 星号 / error 展示 / help 展示.

**Phase 1 完**: 5 commit, 5 个新封装 + 1 个 FormItem 升级. 跑 `bunx vitest run common` 验证 20+ case 全绿.

---

# Phase 2: admin 4 文件 (Task 6-7, 2 commit)

## Task 6: AdminUsersTable + AdminInvitesTable 切 DataTable (1 commit)

**Files:**
- Modify: `app/[locale]/admin/users/_components/AdminUsersTable.tsx`
- Modify: `app/[locale]/admin/invites/_components/AdminInvitesTable.tsx`

**Step 1: AdminUsersTable**

- 删手写 `<input>` (line 59-67) → shadcn `<Input>` (包在 DataTable 外层)
- 删手写 `<select>` (line 68-81) → `<AppSelect options={[{value:"all",label:"全部"},...]} />`
- 删手写 `<table>` (line 87-109) → `<DataTable<AdminUser> columns={...} />`
- 删手写分页 (line 111-137) → 走 DataTable `pagination={...}` (受控) 或 `dataSource.slice()` 内部分页
- `confirm()` (line 23) → `<AppConfirm>`
- error 走 `QueryCache.onError` (删 catch Ignore)

**Step 2: AdminInvitesTable**

- 删手写 `<table>` → `<DataTable<InviteItem>>`
- `confirm()` → `<AppConfirm>`

**Step 3: 跑测试 → 绿, 提 commit**

- `bunx vitest run AdminUsersTable AdminInvitesTable`
- commit: `refactor(admin): tables → DataTable + AppSelect + AppConfirm`

## Task 7: CreateInviteDialog + ResetPasswordDialog 切 AppDialog (1 commit)

**Files:**
- Modify: `app/[locale]/admin/users/_components/CreateInviteDialog.tsx`
- Modify: `app/[locale]/admin/users/_components/ResetPasswordDialog.tsx`

**Step 1: CreateInviteDialog**

- 删手写遮罩 `<div className="fixed inset-0 z-50 ...">` → `<AppDialog title={t("创账号")} ...>`
- 删手写 `<input type="email">` → `<FormField name="email" label="邮箱"><Input type="email" /></FormField>`
- 删手写 `<input type="checkbox">` → shadcn `<Checkbox>` 直用 (跟 plan/CLAUDE.md 保持一致, 不走包装)
- 删手写 `navigator.clipboard` → `<CopyButton text={window.location.origin + inviteUrl} />`
- 删手写 error banner → `<ErrorBanner variant="destructive" description={err} />`
- 删手写 `<form onSubmit>` → `<Form schema={CreateInviteSchema} onFinish={onSubmit}>`

**Step 2: ResetPasswordDialog**

- 同型, 但**没 input** (只有触发按钮 + 复制), 改 `<AppDialog>` + `<CopyButton>` + `<ErrorBanner>`

**Step 3: 跑测试 + 提 commit**

- `bunx vitest run CreateInviteDialog ResetPasswordDialog`
- commit: `refactor(admin): dialogs → AppDialog + Form + FormField + CopyButton`

**Phase 2 完**: 2 commit, admin 4 文件全切完.

---

# Phase 3: 4 表单切 Form + FormField (Task 8-9, 2 commit)

## Task 8: login + forgot-password (1 commit)

**Files:**
- Modify: `app/[locale]/login/page.tsx`
- Modify: `app/[locale]/forgot-password/page.tsx`

**Step 1: login**

- 删手写 `<form onSubmit>` → `<Form schema={LoginSchema} onFinish={onSubmit}>`
- 删手写 `<input>` × 2 → `<FormField name="email" label="邮箱" required><Input type="email" /></FormField>` 同 password
- 删手写 error banner → `<ErrorBanner variant="destructive" description={err} />`
- LoginSchema (Zod): `email: z.string().email()`, `password: z.string().min(1)`

**Step 2: forgot-password**

- 同型, 1 input + CopyButton (替手写 clipboard)
- Schema: `email: z.string().email()`

**Step 3: 跑测试 + 提 commit**

- `bunx vitest run login forgot-password`
- commit: `refactor(auth): login + forgot 表单切 Form + FormField`

## Task 9: reset-password + invite/[token] (1 commit)

**Files:**
- Modify: `app/[locale]/reset-password/page.tsx`
- Modify: `app/[locale]/invite/[token]/page.tsx`

**Step 1: reset-password**

- 删手写 `<form onSubmit>` → `<Form schema={ResetSchema}>`
- 删 2 个 `<input type="password">` → 2 个 `<FormField name="password" label="新密码">` + `name="confirm"`
- ResetSchema: `password: z.string().min(8)`, `confirm: z.string().min(8)` + refine confirm === password

**Step 2: invite/[token]**

- 4 input (email readonly + displayName + password + confirm) → 4 个 FormField
- inviteSchema: `displayName: z.string().min(1)`, password/confirm + refine

**Step 3: 跑测试 + 提 commit**

- `bunx vitest run reset-password invite`
- commit: `refactor(auth): reset + invite 表单切 Form + FormField`

**Phase 3 完**: 2 commit, 4 表单全切 Form + FormField.

---

# Phase 4: 业务 + 16 错误条 + 5 Select (Task 10-13, 4 commit)

## Task 10: EvaluateNewForm (1 commit)

**Files:**
- Modify: `app/[locale]/evaluate/new/_components/EvaluateNewForm.tsx`

**Step 1:**

- 删手写 `<label>` dropzone (line 136-156) → `<FileDropzone accept={{"text/csv":[".csv"]}} onFile={onPick} maxSizeMB={5} />`
- 删手写 `<table>` CSV 预览 (line 179-196) → `<DataTable columns={[{key:"question",...},{key:"ground_truth",...}]} rowKey="id" maxHeight="400px" />`
- 删 2 处手写 error banner → 2 个 `<ErrorBanner variant="destructive">`
- 保留现有 `<Form>` (已用项目自有)

**Step 2: 跑测试 + 提 commit**

- `bunx vitest run EvaluateNewForm`
- commit: `refactor(evaluate): EvaluateNewForm 用 FileDropzone + DataTable + ErrorBanner`

## Task 11: QASubmitForm (1 commit)

**Files:**
- Modify: `app/[locale]/knowledge/qa/_components/QASubmitForm.tsx`

**Step 1:**

- 删手写 `<input type="checkbox">` (line 226-230) → shadcn `<Checkbox>` 直用
- 删条件 error/success 块 (line 182-200) → `<ErrorBanner variant={clientError || !state.ok ? "destructive" : "success"} description={submitResultMsg} />`

**Step 2: 跑测试 + 提 commit**

- `bunx vitest run QASubmitForm`
- commit: `refactor(qa): QASubmitForm 用 shadcn Checkbox + ErrorBanner`

## Task 12: decode/page.tsx (1 commit)

**Files:**
- Modify: `app/[locale]/decode/page.tsx`

**Step 1:**

- 删手写 view 切换按钮组 (line 233-256) → `<AppToggle options={[{value:"cards",label:"解码卡"},{value:"llm",label:"Dify 视图"}]} value={view} onChange={setView} dataTestid="view" />`
- 删手写 error banner (line 188-200) → `<ErrorBanner variant="destructive" description={err} />`
- 删手写 `navigator.clipboard.writeText` (line 140) → 复制按钮改 `<CopyButton text={buildCopyText(result, view)} label={view === "llm" ? "复制 LLM 文本" : "复制 JSON"} />`

**Step 2: 跑测试 + 提 commit**

- `bunx vitest run decode`
- commit: `refactor(decode): ErrorBanner + CopyButton + AppToggle`

## Task 13: 16 错误条 + 5 Select 用户侧 + RejectDialog (1 commit, 业务批量改)

**Files:**
- Modify: 7 个错误条业务文件 (OutputListClient / TriplesForm / batch / ImportCommitCard / output/new / output/[task_id]/[file] / TaskDetailClient)
- Modify: 5 个 Select 用户侧 (DatasetSwitcher / DomainSwitcher / SchemaFieldRenderer / settings-dialog)
- Modify: `submissions/_components/RejectDialog.tsx` (AppSelect REASONS)

**Step 1:**

- 16 处手写 error banner → `<ErrorBanner variant="destructive" description={...} />` 机械替换
- 5 个 Select shadcn 6-行模板 → `<AppSelect options={...} value={...} onChange={...} />` 一行

**Step 2: 跑测试 + 提 commit**

- `bunx vitest run OutputListClient TriplesForm batch ImportCommitCard output DatasetSwitcher DomainSwitcher SchemaFieldRenderer settings-dialog RejectDialog`
- commit: `refactor(components): 21 处统一封装 (16 错误条 + 5 Select)`

**Phase 4 完**: 4 commit, 业务扫尾全.

---

# Phase 5: 文档 (Task 14, 1 commit)

## Task 14: CLAUDE.md 加 3 段封装约定

**Files:**
- Modify: `packages/web/CLAUDE.md`

**Step 1: 加在 "表格组件" 段之后**

新增 3 段:

```markdown
## 封装组件 (2026-06-14)

项目已封装 + 新封装, 一律优先使用, 不许手写对应模板.

### 已有封装 (7)
- `<AppDialog>` (shadcn Dialog 包装) — 弹框, 替手写 `fixed inset-0 bg-black/50`
- `<AppConfirm>` (shadcn AlertDialog 包装) — 危险操作二次确认, 替 `window.confirm()`
- `<AppDrawer>` (shadcn Sheet 包装) — 抽屉, 业务暂无用
- `<Form>` + `<FormItem>` (项目自有, Zod) — 表单 + 字段, 替 `<form onSubmit>` 模板
- `<FileDropzone>` (react-dropzone 包装) — 文件拖拽, 替手写 `<label>` + `<input type="file">`
- `<DataTable<T>>` (shadcn Table 包装) — 表格, 替手写 `<table>/<thead>/<tr>/<th>/<td>`
- `<DataEmpty>` (shadcn Empty 包装) — 空态, 替 "暂无数据" 文本

### 新封装 (5, 2026-06-14)
- `<AppSelect>` (antd 风格, options + value + onChange 一行) — 替 shadcn Select 6-行模板
- `<AppToggle>` (shadcn ToggleGroup 单选) — 替手写 button 按钮组 (例 decode view 切换)
- `<ErrorBanner>` (shadcn Alert 包装, 5 variant) — 替 `<div className="border-destructive/30 bg-destructive/5 ...">` (16 处统一)
- `<CopyButton>` (clipboard + 1.5s 反馈) — 替 `navigator.clipboard.writeText` (4 处统一)
- `<FormField>` (FormItem 升级, Label + 错误展示) — 4 表单模板用

### 反模式 (禁止手写)
- `<input type="text|email|password|number">` → shadcn `<Input>` 或 `<FormField>` 包装
- shadcn `<Select>` 6-行模板 → `<AppSelect>` (antd 风格 1 行)
- `<input type="checkbox">` / shadcn `<Switch>` / shadcn `<RadioGroup>` / shadcn `<Textarea>` 直用 (跟 `<AppSelect>` 价值不同, 1 行就够, 不抽包装)
- `<table>/<thead>/<tbody>/<tr>/<th>/<td>` → `<DataTable<T>>`
- `<div className="fixed inset-0 z-50 bg-black/50">` (Dialog 遮罩) → `<AppDialog>`
- `<form onSubmit>` → `<Form>` (项目自有 + Zod)
- `<input type="file">` 包在 `<label>` → `<FileDropzone>`
- `<div className="border-destructive/30 bg-destructive/5 ...">` (错误条) → `<ErrorBanner>`
- `navigator.clipboard.writeText` → `<CopyButton>`
- `window.confirm(...)` → `<AppConfirm>`
- 手写 button 按钮组 (例 decode view 切换) → `<AppToggle>`

### 新增表格 / 表单 / 弹框 / 状态提示 时
1. 表格 → `<DataTable<T>>` + `<DataEmpty>` 空态
2. 表单 → `<Form>` + `<FormField>` 包装每字段, shadcn Input/Checkbox/Textarea 内嵌
3. 弹框 → `<AppDialog>` (二次确认 → `<AppConfirm>`)
4. 错误 → `<ErrorBanner>` (success/warning/destructive 走对应 variant)
5. 复制 → `<CopyButton>`
6. 状态切换按钮组 → `<AppToggle>`
```

**Step 2: 提 commit**

- `git add packages/web/CLAUDE.md`
- commit: `docs(web): CLAUDE.md 加封装约定, 强制走 17 个 antd/shadcn 风格组件`

**Phase 5 完**: 1 commit, 文档就位.

---

# 完成验证 (Definition of Done)

跑完 12 commit 后, 跑下面验收:

- [ ] `git log --oneline -12` 看到 12 commit 全部入库
- [ ] `bun run typecheck` 0 错
- [ ] `bunx vitest run common` 20+ 新封装 case 全绿
- [ ] `bunx vitest run <改过的业务文件>` 全部业务 test 绿
- [ ] 全项目 grep 12 类反模式 0 命中:
  ```bash
  grep -rn "<input\s" packages/web/app      # 0 命中 (除了测试 mock)
  grep -rn "<select\s" packages/web/app     # 0 命中
  grep -rn "<table\s" packages/web/app      # 0 命中
  grep -rn "fixed inset-0 z-50" packages/web/app  # 0 命中
  grep -rn "border-destructive/30 bg-destructive/5" packages/web/app  # 0 命中
  grep -rn "navigator.clipboard" packages/web/app  # 0 命中
  grep -rn "window.confirm" packages/web/app  # 0 命中
  ```
- [ ] Playwright spot-check 8 页打开 0 errors: login / forgot-password / admin/users / admin/invites / evaluate/new / decode / qa / submissions
- [ ] 净减行数 ≥ 1500 行 (每个 commit message 报告 diff stat)
- [ ] pre-commit hook 跑 lint-staged + tsgo + vitest 全部绿
- [ ] 写一条 memory 记录: 全项目 12 类反模式清零, 新增 5 个封装

---

## 关联

- [[feedback-no-shim-no-minimal-changes]] — 这次清的就是 30+ 文件隐性技术债
- [[feedback-no-full-vitest-during-dev]] — 阶段 1-4 实施时只测改过的, 不跑全量
- [[feedback-commit-in-batches-for-large-changes]] — 12 commit 按 Layer 拆
- [[feedback-record-errors-and-lessons]] — 遇错记 memory
- `packages/web/CLAUDE.md` 表格组件约定 (2026-06-14) — 这次扩展
- `docs/superpowers/specs/2026-06-14-shadcn-unification-design.md` — 设计 spec
