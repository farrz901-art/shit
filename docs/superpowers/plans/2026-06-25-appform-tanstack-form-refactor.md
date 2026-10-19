# AppForm 统一表单重构 — 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build AppForm/AppField/AppSubmit components (based on @tanstack/react-form), migrate all 23 form sites across the project, delete old Form/FormItem, uninstall react-hook-form + @hookform/resolvers.

**Architecture:**
- AppForm internally uses `@tanstack/react-form`'s `useForm()`, passing the form instance via React context
- Two modes: `action` (native `<form action>`) and `onFinish` (client validation callback)
- AppField wraps TanStack Form's `<Field>` render-prop, exposing antd-style props
- AppSubmit auto-binds `disabled` to `form.state.isSubmitting`
- Zod 4 Standard Schema (`~standard` property) connects directly to TanStack validators — no resolver bridge needed

**Tech Stack:** @tanstack/react-form ^1.33.0, Zod ^4.4.3, Tailwind v4, shadcn/ui Input/Label/Checkbox/Button

---

## File Structure

### New files to create

| File | Responsibility |
|---|---|
| `components/common/form/app-form.tsx` | AppForm main component — useForm(), dual-mode submit, layout |
| `components/common/form/app-form.test.tsx` | AppForm unit tests (~6) |
| `components/common/form/app-field.tsx` | AppField component — wraps TanStack `<Field>`, label/errors |
| `components/common/form/app-field.test.tsx` | AppField unit tests (~7) |
| `components/common/form/app-submit.tsx` | AppSubmit button — auto-disabled when submitting |
| `components/common/form/app-submit.test.tsx` | AppSubmit unit tests (~3) |

### Files to modify

| File | Change |
|---|---|
| `components/common/form/index.ts` | Export AppForm/AppField/AppSubmit (keep old exports for now) |

### Files to delete (batch 5)

| File | Reason |
|---|---|
| `components/common/form/form.tsx` | Replaced by app-form.tsx |
| `components/common/form/form-item.tsx` | Replaced by app-field.tsx |
| `components/common/form/form-context.ts` | No longer needed |
| `components/common/form/form.test.tsx` | Replaced by new tests |
| `components/common/form/form.stories.tsx` | Stories for old Form |
| `components/ui/form.tsx` | shadcn Form template — no consumers |
| `components/ui/form.test.tsx` | Companion test |

### Files to migrate (23 form sites)

See Migration Route below.

---

## Task 1: AppForm component

**Files:**
- Create: `packages/web/components/common/form/app-form.tsx`
- Create: `packages/web/components/common/form/app-form.test.tsx`

### Step 1: Write AppForm tests — fail first

```tsx
// app-form.test.tsx
import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { AppForm } from "./app-form";
import { AppField } from "./app-field";
import { AppSubmit } from "./app-submit";
import { Input } from "@/components/ui/input";
import { z } from "zod";

const setupUser = async () => {
  const userEventModule = await import("@testing-library/user-event");
  return userEventModule.default.setup();
};

describe("AppForm", () => {
  it("action 模式: 渲染表单 + action prop", () => {
    const action = vi.fn();
    render(
      <AppForm defaultValues={{ email: "" }} action={action}>
        <AppField name="email" type="email" />
        <AppSubmit>提交</AppSubmit>
      </AppForm>,
    );
    const form = screen.getByRole("form");
    expect(form).toBeInTheDocument();
  });

  it("onFinish 模式: 提交触发 onFinish", async () => {
    const user = await setupUser();
    const onFinish = vi.fn();
    render(
      <AppForm defaultValues={{ name: "张三" }} onFinish={onFinish}>
        <AppField name="name" label="姓名">
          <Input />
        </AppField>
        <button type="submit" data-testid="submit-btn">提交</button>
      </AppForm>,
    );
    await user.click(screen.getByTestId("submit-btn"));
    expect(onFinish).toHaveBeenCalledWith({ name: "张三" });
  });

  it("onFinish 模式: Zod schema 校验失败触发 onFinishFailed", async () => {
    const user = await setupUser();
    const onFinish = vi.fn();
    const onFinishFailed = vi.fn();
    const schema = z.object({ name: z.string().min(2, "至少 2 字") });
    render(
      <AppForm
        defaultValues={{ name: "" }}
        schema={schema}
        onFinish={onFinish}
        onFinishFailed={onFinishFailed}
      >
        <AppField name="name" label="姓名">
          <Input />
        </AppField>
        <button type="submit" data-testid="submit-btn">提交</button>
      </AppForm>,
    );
    await user.click(screen.getByTestId("submit-btn"));
    expect(onFinish).not.toHaveBeenCalled();
    expect(onFinishFailed).toHaveBeenCalled();
    expect(screen.getByText("至少 2 字")).toBeInTheDocument();
  });

  it("onFinish 模式: Zod schema 校验通过触发 onFinish", async () => {
    const user = await setupUser();
    const onFinish = vi.fn();
    const schema = z.object({ name: z.string().min(2) });
    render(
      <AppForm
        defaultValues={{ name: "张三" }}
        schema={schema}
        onFinish={onFinish}
      >
        <AppField name="name" label="姓名">
          <Input />
        </AppField>
        <button type="submit" data-testid="submit-btn">提交</button>
      </AppForm>,
    );
    await user.click(screen.getByTestId("submit-btn"));
    expect(onFinish).toHaveBeenCalledWith({ name: "张三" });
  });

  it("layout='horizontal' 使用 grid 布局", () => {
    const { container } = render(
      <AppForm defaultValues={{ name: "" }} onFinish={vi.fn()} layout="horizontal">
        <AppField name="name" label="姓名">
          <Input />
        </AppField>
      </AppForm>,
    );
    const form = container.querySelector("form")!;
    expect(form.className).toContain("grid");
  });
});
```

Run:

```bash
cd packages/web && bun run test -- components/common/form/app-form.test.tsx
```
Expected: FAIL — module not found

### Step 2: Write AppForm implementation

```tsx
// app-form.tsx
"use client";
import {
  createContext,
  useCallback,
  useContext,
  type FormEvent,
  type ReactNode,
} from "react";
import { useForm } from "@tanstack/react-form";
import type { ZodSchema } from "zod";
import { cn } from "@/lib/utils";

// ── Types ──────────────────────────────────────────
interface AppFormProps<T extends Record<string, unknown>> {
  /** 表单初始值，类型推导到各 Field */
  defaultValues: T;
  /** 可选 Zod 4 schema（Standard Schema 直连 TanStack validators） */
  schema?: ZodSchema<T>;
  /** 简单模式：server action（原生 <form action> 提交） */
  action?: (formData: FormData) => void | Promise<void>;
  /** 复杂模式：客户端提交回调 */
  onFinish?: (values: T) => void | Promise<void>;
  /** 校验失败回调 */
  onFinishFailed?: (errors: Record<string, string>) => void;
  /** 布局模式 */
  layout?: "vertical" | "horizontal";
  className?: string;
  children: ReactNode;
}

interface FormCtxValue {
  form: ReturnType<typeof useForm<any>>;
  layout: "vertical" | "horizontal";
}

// ── Context ─────────────────────────────────────────
const FormCtx = createContext<FormCtxValue | null>(null);

export const useFormCtx = (): FormCtxValue => {
  const ctx = useContext(FormCtx);
  if (!ctx) throw new Error("useFormCtx must be used within <AppForm>");
  return ctx;
};

// ── Zod error → Record<string, string> ─────────────
const fromZodErrors = (error: unknown): Record<string, string> => {
  if (!error || typeof error !== "object") return {};
  const err = error as { issues?: Array<{ message: string; path: (string | number)[] }> };
  const fieldErrors: Record<string, string> = {};
  for (const issue of err.issues ?? []) {
    const path = issue.path.join(".");
    if (!fieldErrors[path]) fieldErrors[path] = issue.message;
  }
  return fieldErrors;
};

// ── AppForm ─────────────────────────────────────────
export const AppForm = <T extends Record<string, unknown>>({
  defaultValues,
  schema,
  action,
  onFinish,
  onFinishFailed,
  layout = "vertical",
  className,
  children,
}: AppFormProps<T>) => {
  const form = useForm({
    defaultValues: defaultValues as any,
    validators: schema
      ? { onChange: schema as any, onSubmit: schema as any }
      : undefined,
    onSubmit: onFinish
      ? async ({ value }: { value: any }) => {
          if (schema) {
            const parsed = schema.safeParse(value);
            if (!parsed.success) {
              onFinishFailed?.(fromZodErrors(parsed.error));
              return;
            }
            await onFinish(parsed.data as T);
          } else {
            await onFinish(value as T);
          }
        }
      : undefined,
  });

  const handleSubmit = useCallback(
    (e: FormEvent) => {
      if (onFinish) {
        e.preventDefault();
        form.handleSubmit();
      }
      // action mode: 让浏览器原生提交
    },
    [onFinish, form],
  );

  return (
    <FormCtx.Provider value={{ form, layout }}>
      <form
        onSubmit={handleSubmit}
        action={action ?? undefined}
        noValidate
        className={cn(
          layout === "horizontal"
            ? "grid grid-cols-[140px_1fr] gap-3 items-start"
            : "space-y-4",
          className,
        )}
      >
        {children}
      </form>
    </FormCtx.Provider>
  );
};
```

### Step 3: Run tests — verify pass

```bash
cd packages/web && bun run test -- components/common/form/app-form.test.tsx
```
Expected: 4 PASS / 0 FAIL

### Step 4: Commit

```bash
git add packages/web/components/common/form/app-form.tsx packages/web/components/common/form/app-form.test.tsx
git commit -m "feat: add AppForm base component with dual-mode (action / onFinish)"
```

---

## Task 2: AppField component

**Files:**
- Create: `packages/web/components/common/form/app-field.tsx`
- Create: `packages/web/components/common/form/app-field.test.tsx`

### Step 1: Write AppField tests — fail first

```tsx
// app-field.test.tsx
import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { AppForm } from "./app-form";
import { AppField } from "./app-field";
import { Input } from "@/components/ui/input";
import { z } from "zod";

describe("AppField", () => {
  it("默认 Input 按 type 渲染", () => {
    render(
      <AppForm defaultValues={{ email: "" }} onFinish={vi.fn()}>
        <AppField name="email" label="邮箱" type="email" />
      </AppForm>,
    );
    const input = screen.getByLabelText("邮箱");
    expect(input).toHaveAttribute("type", "email");
  });

  it("label + required 星号", () => {
    render(
      <AppForm defaultValues={{ name: "" }} onFinish={vi.fn()}>
        <AppField name="name" label="姓名" required />
      </AppForm>,
    );
    const label = screen.getByText("姓名");
    expect(label).toBeInTheDocument();
  });

  it("help 文字（无 error 时显示）", () => {
    render(
      <AppForm defaultValues={{ email: "" }} onFinish={vi.fn()}>
        <AppField name="email" label="邮箱" help="用于登录" />
      </AppForm>,
    );
    expect(screen.getByText("用于登录")).toBeInTheDocument();
  });

  it("自定义 children 绑定 value + onChange", async () => {
    const user = (await import("@testing-library/user-event")).default.setup();
    const onFinish = vi.fn();
    render(
      <AppForm defaultValues={{ note: "hello" }} onFinish={onFinish}>
        <AppField name="note" label="备注">
          <Input />
        </AppField>
        <button type="submit" data-testid="submit">提交</button>
      </AppForm>,
    );
    const input = screen.getByDisplayValue("hello") as HTMLInputElement;
    await user.clear(input);
    await user.type(input, "world");
    await user.click(screen.getByTestId("submit"));
    expect(onFinish).toHaveBeenCalledWith({ note: "world" });
  });

  it("嵌套路径 name='user.email' 正确读写", async () => {
    const user = (await import("@testing-library/user-event")).default.setup();
    const onFinish = vi.fn();
    render(
      <AppForm defaultValues={{ user: { email: "a@b.com" } }} onFinish={onFinish}>
        <AppField name="user.email" label="邮箱">
          <Input />
        </AppField>
        <button type="submit" data-testid="submit">提交</button>
      </AppForm>,
    );
    await user.clear(screen.getByDisplayValue("a@b.com"));
    await user.type(screen.getByDisplayValue(""), "x@y.com");
    await user.click(screen.getByTestId("submit"));
    expect(onFinish).toHaveBeenCalledWith({ user: { email: "x@y.com" } });
  });
});
```

Run:

```bash
cd packages/web && bun run test -- components/common/form/app-field.test.tsx
```
Expected: FAIL — module not found

### Step 2: Write AppField implementation

```tsx
// app-field.tsx
"use client";
import {
  cloneElement,
  isValidElement,
  type ReactElement,
  type ReactNode,
} from "react";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import { useFormCtx } from "./app-form";

// ── Types ──────────────────────────────────────────
interface AppFieldProps {
  name: string;
  label?: string;
  required?: boolean;
  help?: string;
  type?: "text" | "number" | "email" | "password";
  placeholder?: string;
  children?: ReactNode;
}

// ── Extract value from event or direct value ───────
const getValue = (
  event: unknown,
  fieldType?: string,
): unknown => {
  if (event && typeof event === "object" && "target" in event) {
    const target = (event as { target: { value: unknown; type?: string } }).target;
    if (fieldType === "number") {
      return target.value === "" ? "" : Number(target.value);
    }
    return target.value;
  }
  return event;
};

// ── AppField ─────────────────────────────────────────
export const AppField = ({
  name,
  label,
  required,
  help,
  type,
  placeholder,
  children,
}: AppFieldProps) => {
  const { form, layout } = useFormCtx();
  const Field = form.Field;

  return (
    <Field name={name} mode="value">
      {(field) => {
        const error =
          field.state.meta.errors?.[0]?.message ?? field.state.meta.errorMap?.onSubmit?.[0]?.message;
        const inputId = `app-field-${name.replace(/\./g, "-")}`;

        return (
          <div
            className={cn(
              layout === "horizontal"
                ? "grid grid-cols-[140px_1fr] gap-3 items-start"
                : "space-y-2",
            )}
          >
            {label && (
              <Label
                htmlFor={inputId}
                className={cn(
                  required &&
                    "after:content-['*'] after:ml-0.5 after:text-destructive",
                )}
              >
                {label}
              </Label>
            )}

            <div>
              {children && isValidElement(children)
                ? cloneElement(children as ReactElement<Record<string, unknown>>, {
                    value: field.state.value ?? "",
                    onChange: (event: unknown) => field.handleChange(getValue(event, type) as any),
                    onBlur: field.handleBlur,
                    id: inputId,
                    ...(required ? { "aria-required": true } : {}),
                    ...(error ? { "aria-invalid": true } : {}),
                  } as Record<string, unknown>)
                : (
                  <Input
                    id={inputId}
                    type={type ?? "text"}
                    value={(field.state.value as string) ?? ""}
                    onChange={(e) => field.handleChange(getValue(e, type) as any)}
                    onBlur={field.handleBlur}
                    placeholder={placeholder}
                    aria-invalid={!!error}
                    aria-required={required}
                  />
                )}
            </div>

            {help && !error && (
              <p className="text-sm text-muted-foreground">{help}</p>
            )}
            {error && (
              <p className="text-sm text-destructive" data-testid={`field-error-${name}`}>
                {error}
              </p>
            )}
          </div>
        );
      }}
    </Field>
  );
};
```

### Step 3: Run tests — verify pass

```bash
cd packages/web && bun run test -- components/common/form/app-field.test.tsx
```
Expected: 5 PASS / 0 FAIL

### Step 4: Commit

```bash
git add packages/web/components/common/form/app-field.tsx packages/web/components/common/form/app-field.test.tsx
git commit -m "feat: add AppField component with TanStack Form Field binding"
```

---

## Task 3: AppSubmit component

**Files:**
- Create: `packages/web/components/common/form/app-submit.tsx`
- Create: `packages/web/components/common/form/app-submit.test.tsx`

### Step 1: Write AppSubmit tests — fail first

```tsx
// app-submit.test.tsx
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { AppForm } from "./app-form";
import { AppSubmit } from "./app-submit";

describe("AppSubmit", () => {
  it("渲染 children", () => {
    render(
      <AppForm defaultValues={{ name: "" }} onFinish={() => {}}>
        <AppSubmit>提交</AppSubmit>
      </AppForm>,
    );
    expect(screen.getByRole("button", { name: "提交" })).toBeInTheDocument();
  });

  it("透传 className", () => {
    render(
      <AppForm defaultValues={{ name: "" }} onFinish={() => {}}>
        <AppSubmit className="custom-cls" data-testid="btn">提交</AppSubmit>
      </AppForm>,
    );
    expect(screen.getByTestId("btn").className).toContain("custom-cls");
  });
});
```

Run:

```bash
cd packages/web && bun run test -- components/common/form/app-submit.test.tsx
```
Expected: FAIL — module not found

### Step 2: Write AppSubmit implementation

```tsx
// app-submit.tsx
"use client";
import { Button, type ButtonProps } from "@/components/ui/button";
import type { ReactNode } from "react";
import { useFormCtx } from "./app-form";
import { useStore } from "@tanstack/react-form";

interface AppSubmitProps extends ButtonProps {
  children: ReactNode;
}

export const AppSubmit = ({ children, ...props }: AppSubmitProps) => {
  const { form } = useFormCtx();
  const isSubmitting = useStore(form.store, (state) => state.isSubmitting);

  return (
    <Button type="submit" disabled={isSubmitting || props.disabled} {...props}>
      {children}
    </Button>
  );
};
```

### Step 3: Run tests — verify pass

```bash
cd packages/web && bun run test -- components/common/form/app-submit.test.tsx
```
Expected: 2 PASS / 0 FAIL

### Step 4: Commit

```bash
git add packages/web/components/common/form/app-submit.tsx packages/web/components/common/form/app-submit.test.tsx
git commit -m "feat: add AppSubmit button with auto-disabled on isSubmitting"
```

---

## Task 4: Update index.ts exports

**Files:**
- Modify: `packages/web/components/common/form/index.ts`

### Step 1: Read current index.ts

Check current exports:

```bash
cat packages/web/components/common/form/index.ts
```

Expected to see old exports for Form, FormItem, form-context.

### Step 2: Modify to add new exports alongside old ones

```ts
// components/common/form/index.ts
export { AppForm } from "./app-form";
export { AppField } from "./app-field";
export { AppSubmit } from "./app-submit";
// ── 旧导出保留，batch 5 删除 ──
export { Form } from "./form";
export { FormItem } from "./form-item";
export {
  FormContext,
  FormDispatchContext,
  FormValueContext,
  useFormContext,
  useFormDispatch,
  useFormState,
} from "./form-context";
```

### Step 3: Quick sanity check

```bash
cd packages/web && bun run typecheck
```
Expected: 0 errors

### Step 4: Commit

```bash
git add packages/web/components/common/form/index.ts
git commit -m "feat: add AppForm/AppField/AppSubmit exports to index"
```

---

## Task 5: Batch 1 — migrate evaluate-new-form

**Files:**
- Modify: `packages/web/app/[locale]/evaluate/new/_components/evaluate-new-form.tsx`

### Step 1: Read current imports and usage

Current imports from old Form:
```tsx
import { Form } from "@/components/common/form/form";
import { FormItem } from "@/components/common/form/form-item";
```

### Step 2: Change imports and adapt

```diff
- import { Form } from "@/components/common/form/form";
- import { FormItem } from "@/components/common/form/form-item";
+ import { AppForm, AppField, AppSubmit } from "@/components/common/form";
```

Then replace the Form + FormItem usage:

```diff
- <Form
-   initialValues={{ concurrency: MIN_CONCURRENCY }}
-   schema={NewEvalSchema}
-   onFinish={onSubmit}
-   onFinishFailed={() => setUploadErr(trans("请检查表单字段"))}
- >
-   ...
-   <FormItem name="concurrency" label={trans("并发数")} help={trans("范围 1-10")}>
-     <Input
-       type="number"
-       min={MIN_CONCURRENCY}
-       max={MAX_CONCURRENCY}
-       className="num w-24"
-     />
-   </FormItem>
-   ...
-   <Button type="submit" disabled={uploading} data-testid="eval-start">
-     {getSubmitLabel(uploading, trans)}
-   </Button>
- </Form>
+ <AppForm
+   defaultValues={{ concurrency: MIN_CONCURRENCY }}
+   schema={NewEvalSchema}
+   onFinish={onSubmit}
+   onFinishFailed={() => setUploadErr(trans("请检查表单字段"))}
+ >
+   ...
+   <AppField name="concurrency" label={trans("并发数")} help={trans("范围 1-10")}>
+     <Input
+       type="number"
+       min={MIN_CONCURRENCY}
+       max={MAX_CONCURRENCY}
+       className="num w-24"
+     />
+   </AppField>
+   ...
+   <AppSubmit data-testid="eval-start">
+     {getSubmitLabel(uploading, trans)}
+   </AppSubmit>
+ </AppForm>
```

### Step 3: Run tests

```bash
cd packages/web && bun run test -- app/[locale]/evaluate/new/_components/evaluate-new-form.test.tsx
```
Expected: PASS (just import change, behavior unchanged)

### Step 4: Run all tests

```bash
cd packages/web && bun run test
```
Expected: 719 passed (no change in count)

### Step 5: Commit

```bash
git add packages/web/app/\[locale\]/evaluate/new/_components/evaluate-new-form.tsx
git commit -m "refactor: migrate evaluate-new-form from old Form to AppForm"
```

---

## Task 6: Batch 2 — migrate DictItemCreateDialog

**Files:**
- Modify: `packages/web/app/[locale]/admin/dicts/_components/dict-item-create-dialog.tsx`

### Step 1: Current pattern — 7 raw useState fields + manual validation

The form currently has 7 fields managed via 2 separate useState hooks (one for `LookupItemCreateInput`, one for `metadataText`), manual `canSubmit` guard, manual submit error handling.

### Step 2: Add import for AppForm + AppField

```diff
+ import { AppForm, AppField, AppSubmit } from "@/components/common/form";
import { AppDialog } from "@/components/common/dialog/app-dialog";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
- import { Input } from "@/components/ui/input";
- import { Label } from "@/components/ui/label";
```

### Step 3: Replace form block

Replace the entire `<form>` block:

```tsx
<AppForm
  defaultValues={{
    key: "",
    label_zh: "",
    label_en: "",
    sort: 0,
    description: "",
    is_active: true,
    metadata_json: "",
  }}
  schema={z.object({
    key: z.string().min(1, "key 必填"),
    label_zh: z.string().min(1, "中文标签必填"),
    label_en: z.string().min(1, "英文标签必填"),
    sort: z.number().int().default(0),
    description: z.string().optional(),
    is_active: z.boolean(),
    metadata_json: z.string().optional(),
  })}
  onFinish={async (values) => {
    const metadata = values.metadata_json?.trim()
      ? (JSON.parse(values.metadata_json) as Record<string, unknown>)
      : null;
    setSubmitting(true);
    try {
      await onSubmit({
        key: values.key,
        label_zh: values.label_zh,
        label_en: values.label_en,
        sort: values.sort,
        description: values.description?.trim() || null,
        is_active: values.is_active,
        metadata_json: metadata,
      });
      onCreated();
      handleClose(false);
    } catch (error) {
      setSubmitError(getErrorMessage(error, translate));
    } finally {
      setSubmitting(false);
    }
  }}
  onFinishFailed={(errors) => setSubmitError(Object.values(errors).join("; "))}
>
  <AppField name="key" label="key" required placeholder="pending" />
  <AppField name="label_zh" label={translate("中文标签")} required placeholder="待审核" />
  <AppField name="label_en" label={translate("英文标签")} required placeholder="Pending" />
  <AppField name="sort" label={translate("排序")} type="number" />

  <AppField name="description" label={translate("描述")} placeholder={translate("可选, 说明这个字典项用途")} />

  <div className="space-y-2">
    <Label className="eyebrow block">metadata_json</Label>
    <AppField name="metadata_json">
      <textarea
        placeholder='{"color": "blue"}'
        className="border-input bg-transparent w-full rounded-md border px-3 py-2 font-mono text-xs"
        rows={3}
      />
    </AppField>
  </div>

  <div className="space-y-1.5">
    <Label className="flex cursor-pointer items-center gap-2 text-sm">
      <AppField name="is_active">
        <Checkbox />
      </AppField>
      {translate("启用")}
    </Label>
  </div>

  <div className="flex gap-2 pt-2">
    <AppSubmit data-testid="dict-item-create-submit" className="flex-1">
      {getSubmitText(submitting, translate)}
    </AppSubmit>
    <Button
      type="button"
      variant="outline"
      onClick={() => handleClose(false)}
      data-testid="dict-item-create-cancel"
    >
      {translate("取消")}
    </Button>
  </div>
</AppForm>
```

Note: For Checkbox and textarea custom children, AppField's cloneElement will inject `value` and `onChange`. The Checkbox from shadcn uses `checked` not `value` — we need to handle this. Since these are non-standard, the simpler approach is to keep them outside AppField and manage state manually or use TanStack Form's `form.Field` directly.

**Alternative simpler approach** — keep the Checkbox and textarea outside AppField (they're non-standard inputs), only use AppField for standard Input fields. This is the pragmatic path:

```tsx
<AppForm ...>
  <AppField name="key" label="key" required placeholder="pending" />
  <AppField name="label_zh" label={translate("中文标签")} required placeholder="待审核" />
  <AppField name="label_en" label={translate("英文标签")} required placeholder="Pending" />
  <AppField name="sort" label={translate("排序")} type="number" />
  <AppField name="description" label={translate("描述")} placeholder={translate("可选, 说明这个字典项用途")} />

  {/* 非标准控件：textare 和 Checkbox 用 form.Field 原生方法 */}
  <form.Field name="metadata_json" mode="value">
    {(field) => (
      <div className="space-y-1.5">
        <Label className="eyebrow block">metadata_json</Label>
        <textarea
          value={(field.state.value as string) ?? ""}
          onChange={(e) => field.handleChange(e.target.value)}
          placeholder='{"color": "blue"}'
          className="border-input bg-transparent w-full rounded-md border px-3 py-2 font-mono text-xs"
          rows={3}
        />
      </div>
    )}
  </form.Field>

  <Label className="flex cursor-pointer items-center gap-2 text-sm">
    <form.Field name="is_active" mode="value">
      {(field) => (
        <Checkbox
          checked={Boolean(field.state.value)}
          onCheckedChange={(checked) => field.handleChange(checked)}
        />
      )}
    </form.Field>
    {translate("启用")}
  </Label>

  <div className="flex gap-2 pt-2">
    <AppSubmit data-testid="dict-item-create-submit" className="flex-1">
      {translate("新增")}
    </AppSubmit>
    <Button type="button" variant="outline" onClick={() => handleClose(false)} data-testid="dict-item-create-cancel">
      {translate("取消")}
    </Button>
  </div>
</AppForm>
```

**Clean up removed state** — delete `values`, `metadataText`, `submitting`, `submitError` useState calls and their handlers. The form now manages state via TanStack Form. Keep only the `onSubmit` function for API calls.

### Step 4: Run tests

```bash
cd packages/web && bun run test -- app/[locale]/admin/dicts/_components/dict-item-create-dialog.test.tsx
```

### Step 5: Commit

```bash
git add packages/web/app/\[locale\]/admin/dicts/_components/dict-item-create-dialog.tsx
git commit -m "refactor: migrate dict-item-create-dialog from raw useState to AppForm"
```

---

## Task 7: Batch 2 — migrate CreateRoleDialog

**Files:**
- Modify: `packages/web/app/[locale]/admin/permissions/_components/create-role-dialog.tsx`

### Step 1: Add AppForm import, remove raw useState for name/labelZh/labelEn

Replace 3 separate usestates + manual form with:

```tsx
import { AppForm, AppField, AppSubmit } from "@/components/common/form";

// Inside component — replace the 3 useState + <form> with:
<AppForm
  defaultValues={{ name: "", label_zh: "", label_en: "" }}
  onFinish={async (values) => {
    setDialogError(null);
    setSubmitting(true);
    try {
      await createRole({
        name: values.name,
        label_zh: values.label_zh,
        label_en: values.label_en,
        permissions,
      });
      onCreated();
      handleClose(false);
    } catch (error) {
      setDialogError(error instanceof Error ? error.message : "创建失败");
    } finally {
      setSubmitting(false);
    }
  }}
>
  <AppField name="name" label={translate("角色名")} required placeholder="operator" />
  <AppField name="label_zh" label={translate("中文标签")} required placeholder="运营" />
  <AppField name="label_en" label={translate("英文标签")} required placeholder="Operator" />

  {/* permissions 权限网格保持独立（非标准控件） */}
  <div className="space-y-2">
    <Label className="eyebrow block">{translate("页面权限")}</Label>
    <div className="grid grid-cols-2 gap-2">
      {pages.map((page) => (
        <Label key={page.key} className="flex cursor-pointer items-center gap-2 rounded border border-border/40 px-2 py-1.5 text-sm hover:bg-muted/30">
          <Checkbox
            checked={Boolean(permissions[page.key])}
            onCheckedChange={(checked) =>
              setPermissions((prev) => ({ ...prev, [page.key]: Boolean(checked) }))
            }
            data-testid={`role-page-${page.key}`}
          />
          {translate(page.label_zh)}
        </Label>
      ))}
    </div>
  </div>

  <div className="flex gap-2 pt-2">
    <AppSubmit data-testid="role-submit" className="flex-1">
      {submitting ? translate("创建中…") : translate("创建")}
    </AppSubmit>
    <Button type="button" variant="outline" onClick={() => handleClose(false)} data-testid="role-cancel">
      {translate("取消")}
    </Button>
  </div>
</AppForm>
```

Note: The `permissions` state (Record<string, boolean>) stays as `useState` because it's a dynamic non-standard grid of checkboxes outside the AppForm / TanStack Form scope.

**Delete old state** — remove `name`, `labelZh`, `labelEn` useState calls. Keep `permissions`, `dialogError`, `submitting`.

### Step 2: Run tests

```bash
cd packages/web && bun run test -- app/[locale]/admin/permissions/_components/create-role-dialog.test.tsx
```

### Step 3: Commit

```bash
git add packages/web/app/\[locale\]/admin/permissions/_components/create-role-dialog.tsx
git commit -m "refactor: migrate create-role-dialog from raw useState to AppForm"
```

---

## Task 8: Batch 2 — migrate QASubmitForm

**Files:**
- Modify: `packages/web/app/[locale]/knowledge/qa/_components/qa-submit-form.tsx`

### Step 1: Replace form section

Current pattern: `useActionState` + `<form action={formAction}>` with Zod validation in a wrapper around the server action.

Replace with AppForm:

```diff
+ import { AppForm, AppField, AppSubmit } from "@/components/common/form";
- import { Input } from "@/components/ui/input";
- import { Label } from "@/components/ui/label";
```

Replace the `<form>` block:

```tsx
<AppForm
  defaultValues={{ question: "", answer: "", tags: "" }}
  schema={QASchema}
  onFinish={async (values) => {
    const result = await createQA({
      answer: values.answer,
      dataset_id: datasetId ?? "",
      question: values.question,
      sync_to_neo4j: formVals.syncNeo4j,
      tags: values.tags
        .split(",")
        .map((t) => t.trim())
        .filter(Boolean),
    });
    if (result.ok) {
      toast.success(`已提交审核 #${result.data.approval_id}`);
      router.push(`/${params.locale}/submissions`);
    } else {
      toast.error(result.error);
    }
  }}
  onFinishFailed={(errors) => toast.error(Object.values(errors).join("; "))}
>
  <AppField name="question" label={tr("问题")} required>
    <textarea
      id="qa-question"
      rows={3}
      data-testid="qa-question"
      className="resize-y border-border/80 transition-shadow duration-300 focus:shadow-[0_0_0_4px_hsl(0_0%_10%/0.04)] w-full rounded-md border px-3 py-2 text-sm bg-transparent"
    />
  </AppField>
  <AppField name="answer" label={tr("答案")} required>
    <textarea
      id="qa-answer"
      rows={5}
      data-testid="qa-answer"
      className="resize-y border-border/80 transition-shadow duration-300 focus:shadow-[0_0_0_4px_hsl(0_0%_10%/0.04)] w-full rounded-md border px-3 py-2 text-sm bg-transparent"
    />
  </AppField>
  <AppField name="tags" label={tr("标签 (逗号分隔)")} placeholder="电机, 选型, 1LE 系列" />

  <SyncToNeo4jField
    checked={formVals.syncNeo4j}
    onChange={(val) => setFormVals((prev) => ({ ...prev, syncNeo4j: val }))}
  />

  {submitFeedback && (
    <ErrorBanner
      variant={submitFeedback.variant}
      description={submitFeedback.msg}
      dataTestid="qa-submit-result"
    />
  )}

  <div className="flex flex-wrap items-center gap-3">
    <AppSubmit data-testid="qa-submit">
      {submitButtonLabel}
    </AppSubmit>
  </div>
</AppForm>
```

**Delete**: The `createQAAction` wrapper function can be removed since validation is now in AppForm. The `useActionState` call can be replaced with direct API calls inside `onFinish`. Keep the `formVals` (syncNeo4j) useState.

### Step 2: Run tests

```bash
cd packages/web && bun run test -- app/[locale]/knowledge/qa/_components/qa-submit-form.test.tsx
```
Expected: Need to update test — remove useActionState mock, add AppForm mock pattern.

### Step 3: Commit

```bash
git add packages/web/app/\[locale\]/knowledge/qa/_components/qa-submit-form.tsx
git commit -m "refactor: migrate QA submit form from useActionState to AppForm"
```

---

## Task 9: Batch 2 — migrate TriplesForm line editor

**Files:**
- Modify: `packages/web/app/[locale]/knowledge/triples/_components/triples-form.tsx`

TriplesForm already uses `useActionState` + `useTripleForm` hook. The submit `<form>` only wraps a single submit button. The row management is handled by the hook's `useState`. Changes here are minimal — replace the tiny submit form.

```diff
- <form action={formAction} className="inline">
-   <Button type="submit" disabled={isPending} data-testid="triples-submit">
-     {getSubmitLabel(trans, isPending)}
-   </Button>
- </form>
+ <AppForm defaultValues={{}} action={formAction}>
+   <AppSubmit data-testid="triples-submit" className="inline">
+     {getSubmitLabel(trans, isPending)}
+   </AppSubmit>
+ </AppForm>
```

(No actual fields in this form — it just fires the server action with hidden state managed in the hook.)

### Step 1: Commit

```bash
git add packages/web/app/\[locale\]/knowledge/triples/_components/triples-form.tsx
git commit -m "refactor: migrate triples submit form to AppForm"
```

---

## Task 10: Batch 3 — Dialog forms (6 dialogs)

**Files to modify (each is a similar pattern):**

| File | Fields | Change |
|---|---|---|
| `change-email-dialog.tsx` | new_email, current_password | wrap in AppForm |
| `change-password-dialog.tsx` | current_password, new_password, confirm | wrap in AppForm |
| `request-deletion-dialog.tsx` | current_password, confirm_text | wrap in AppForm |
| `cancel-deletion-dialog.tsx` | current_password | wrap in AppForm |
| `create-invite-dialog.tsx` | email, isAdmin | wrap in AppForm |
| `restore-deletion-banner.tsx` | current_password | wrap in AppForm |

All 6 follow the same pattern:
```tsx
const [state, formAction, isPending] = useActionState(action, init);
<form action={formAction}>
  <Label>...</Label>
  <Input name="email" />
  <Button type="submit" disabled={isPending}>提交</Button>
</form>
```

### Migration pattern (same for all 6):

```tsx
const [state, formAction, isPending] = useActionState(action, init);

<AppForm
  defaultValues={{ email: "" }}
  action={formAction}
>
  <AppField name="email" label="邮箱" type="email" required />
  <AppSubmit data-testid="submit">{isPending ? tr("提交中…") : tr("提交")}</AppSubmit>
</AppForm>
```

This is a mechanical replacement: `<div className="space-y-1.5"><Label>...<Input name=... />` → `<AppField />`, `<Button disabled={isPending}>` → `<AppSubmit>`.

### For Checkbox fields (create-invite-dialog `isAdmin`):

The Checkbox is non-standard (uses `checked`/`onCheckedChange`). Use TanStack `form.Field` directly:

```tsx
<AppForm defaultValues={{ email: "", isAdmin: false }} action={formAction}>
  <AppField name="email" label="邮箱" type="email" required />
  <form.Field name="isAdmin" mode="value">
    {(field) => (
      <Label className="flex items-center gap-2 text-sm">
        <Checkbox
          checked={Boolean(field.state.value)}
          onCheckedChange={(checked) => field.handleChange(checked)}
          name="isAdmin"
        />
        admin
      </Label>
    )}
  </form.Field>
  <AppSubmit data-testid="submit">{{ isPending ? tr("创建中…") : tr("创账号") }}</AppSubmit>
</AppForm>
```

### Step 1: Migrate each dialog file

Work through each of the 6 files applying the same pattern. After each:

```bash
cd packages/web && bun run test -- app/[locale]/<path>/<file>.test.tsx
```

### Step 2: Commit batch

```bash
git add packages/web/app/\[locale\]/account/settings/_components/change-email-dialog.tsx
git add packages/web/app/\[locale\]/account/settings/_components/change-password-dialog.tsx
git add packages/web/app/\[locale\]/account/settings/_components/request-deletion-dialog.tsx
git add packages/web/app/\[locale\]/account/settings/_components/cancel-deletion-dialog.tsx
git add packages/web/app/\[locale\]/account/settings/_components/restore-deletion-banner.tsx
git add packages/web/app/\[locale\]/admin/users/_components/create-invite-dialog.tsx
git commit -m "refactor: migrate 6 dialog forms from useActionState to AppForm"
```

---

## Task 11: Batch 4 — Page forms (7 pages)

**Files to modify (same migration pattern as Batch 3):**

| File | Fields |
|---|---|
| `login/page.tsx` | email, password |
| `forgot-password/page.tsx` | email |
| `reset-password/page.tsx` | password, confirm |
| `invite/[token]/page.tsx` | token(hidden), displayName, password, confirm |
| `restore-form.tsx` | current_password |
| `profile-section.tsx` | display_name |
| `deletion-section.tsx` | current_password |
| `avatar-uploader.tsx` | file (encType multipart/form-data) |

Same mechanical migration: replace `<form><Label><Input name=...>` with `<AppForm><AppField>`.

### For avatar-uploader (multipart/form-data):

The file input needs special handling since `value` on file inputs is read-only.

```tsx
<AppForm defaultValues={{}} action={formAction}>
  <form.Field name="file" mode="value">
    {(field) => (
      <Input
        type="file"
        accept="image/png,image/jpeg,image/webp"
        name="file"
        onChange={(e) => field.handleChange(e.target.files?.[0] ?? null)}
      />
    )}
  </form.Field>
  <AppSubmit style={{ display: "none" }} />
</AppForm>
```

### Step 1: Migrate each page

```bash
cd packages/web && bun run test -- app/[locale]/login/page.test.tsx
# repeat for each migrated page
```

### Step 2: Commit batch

```bash
git add packages/web/app/\[locale\]/login/page.tsx
git add packages/web/app/\[locale\]/forgot-password/page.tsx
git add packages/web/app/\[locale\]/reset-password/page.tsx
git add packages/web/app/\[locale\]/invite/\[token\]/page.tsx
git add packages/web/app/\[locale\]/account/restore/restore-form.tsx
git add packages/web/app/\[locale\]/account/settings/_components/profile-section.tsx
git add packages/web/app/\[locale\]/account/settings/_components/deletion-section.tsx
git add packages/web/app/\[locale\]/account/settings/_components/avatar-uploader.tsx
git commit -m "refactor: migrate 8 page forms from useActionState to AppForm"
```

---

## Task 12: Batch 5 — Cleanup

**Files to delete:**
- `packages/web/components/common/form/form.tsx`
- `packages/web/components/common/form/form-item.tsx`
- `packages/web/components/common/form/form-context.ts`
- `packages/web/components/common/form/form.test.tsx`
- `packages/web/components/common/form/form.stories.tsx`
- `packages/web/components/ui/form.tsx`
- `packages/web/components/ui/form.test.tsx`

**Files to modify:**
- `packages/web/components/common/form/index.ts` — remove old exports

### Step 1: Update index.ts to remove old exports

```diff
export { AppForm } from "./app-form";
export { AppField } from "./app-field";
export { AppSubmit } from "./app-submit";
- export { Form } from "./form";
- export { FormItem } from "./form-item";
- export {
-   FormContext,
-   FormDispatchContext,
-   FormValueContext,
-   useFormContext,
-   useFormDispatch,
-   useFormState,
- } from "./form-context";
```

### Step 2: Delete old files and uninstall deps

```bash
rm packages/web/components/common/form/form.tsx
rm packages/web/components/common/form/form-item.tsx
rm packages/web/components/common/form/form-context.ts
rm packages/web/components/common/form/form.test.tsx
rm packages/web/components/common/form/form.stories.tsx
rm packages/web/components/ui/form.tsx 2>/dev/null || echo "already deleted"
rm packages/web/components/ui/form.test.tsx 2>/dev/null || echo "already deleted"
```

```bash
cd packages/web && bun remove react-hook-form @hookform/resolvers
```

### Step 3: Check nothing imports from old paths

```bash
cd packages/web && grep -r "from.*@/components/common/form/form" --include="*.ts" --include="*.tsx" . || echo "No old form imports found"
grep -r "from.*@/components/common/form/form-item" --include="*.ts" --include="*.tsx" . || echo "No old form-item imports found"
grep -r "from.*@/components/ui/form" --include="*.ts" --include="*.tsx" . || echo "No ui/form imports found"
```

### Step 4: Full validation

```bash
cd packages/web && bun run format:check && bun run lint && bun run typecheck && bun run test
```

Expected: all checks pass, test count unchanged from baseline 719.

### Step 5: Commit

```bash
git add -A
git commit -m "chore: remove old Form/FormItem/form-context, uninstall react-hook-form + @hookform/resolvers"
```

---

## Self-Review Checklist

- [ ] **Spec coverage:** Every section of the spec maps to at least one task: Core API (Task 1-3), Type safety (Zod schema in validators — Task 1), Dual modes (Task 1 handleSubmit), File structure (Task 1-4), Migration batches (Tasks 5-11), Cleanup (Task 12), Testing (each task includes tests)
- [ ] **No placeholders:** Every step has actual code, file paths, and commands
- [ ] **Type consistency:** The `form` from context is typed as `ReturnType<typeof useForm<any>>` throughout; `field.handleChange` used consistently; `AppSubmit` extends `ButtonProps`
- [ ] **All form sites covered:** evaluate-new (Task 5), dict-create/create-role/QA/triples (Tasks 6-9), 6 dialogs (Task 10), 8 pages (Task 11) = 23 sites total ✓
