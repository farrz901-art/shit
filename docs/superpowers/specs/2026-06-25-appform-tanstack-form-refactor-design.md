# AppForm 统一表单重构 — 基于 @tanstack/react-form

> 2026-06-25 · @tanstack/react-form ^1.33.0 · Zod ^4.4.3

## 现状

### 项目表单分布（23 处）

| 模式 | 数量 | 代表文件 |
|---|---|---|
| 自定义 Form/FormItem（手写 useState + Context） | 1 | evaluate-new-form.tsx |
| useActionState + `<form action>`（React 19） | ~16 | login、QA、Triples、Dialogs |
| 手写 useState + onSubmit | 3 | dict-item-create-dialog.tsx、create-role-dialog.tsx、dict-item-delete-dialog.tsx |
| 纯 `<form action>`（0 可见字段） | 3 | reset-password-dialog.tsx、import-commit-card.tsx、task-detail-client.tsx |

### 当前自定义 Form 的问题

| 问题 | 说明 |
|---|---|
| Context 级联重渲染 | 拆了 Dispatch/Value 两 Context，但 Value 变时所有 FormItem 重渲染 |
| 类型不安全 | `values: Record<string, unknown>`，无 schema 类型推导 |
| 只 submit 校验 | 没有 onChange / onBlur 即时校验 |
| cloneElement 脆弱 | 只能包裹一个直接子元素 |
| 仅 1 个消费者 | 只用在了 evaluate-new-form.tsx（1 个字段） |
| 跟主流模式不搭 | 其他 ~16 处用 useActionState + `<form action>` |

## 目标

1. **删除** Form / FormItem / form-context.ts（逐批）
2. **新建** `<AppForm>` + `<AppField>` + `<AppSubmit>`，底层使用 @tanstack/react-form
3. **全项目统一**：23 处表单全部迁移到 AppForm
4. **可卸依赖**：react-hook-form、@hookform/resolvers

## 设计

### 核心 API

```tsx
// === AppForm — 顶层表单 ===
interface AppFormProps<T extends Record<string, unknown>> {
  /** 初始值，类型推导到各 Field */
  defaultValues: T;
  /** 可选 Zod schema（Zod 4 Standard Schema 直连 TanStack validators） */
  schema?: ZodSchema<T>;
  /** 简单模式：server action（原生 <form action> 提交） */
  action?: (formData: FormData) => void | Promise<void>;
  /** 复杂模式：客户端提交回调 */
  onFinish?: (values: T) => void | Promise<void>;
  /** 校验失败回调 */
  onFinishFailed?: (errors: Record<string, string>) => void;
  /** 布局 vertical | horizontal */
  layout?: "vertical" | "horizontal";
  className?: string;
  children: ReactNode;
}
```

```tsx
// === AppField — 单个字段 ===
interface AppFieldProps {
  name: string;          // 字段名，支持嵌套 "user.email"
  label?: string;
  required?: boolean;
  help?: string;         // 帮助文字（无错误时显示）
  // 快捷类型（不传 children 时按 type 渲染默认控件）
  type?: "text" | "number" | "email" | "password";
  placeholder?: string;
  children?: ReactNode;  // 自定义输入组件
}
```

```tsx
// === AppSubmit — 提交按钮 ===
interface AppSubmitProps extends ButtonProps {
  children: ReactNode;
}
// 自动绑定 disabled={form.state.isSubmitting}
```

### 用法示例

```tsx
// 模式 A：简单 action 表单
const [state, formAction, isPending] = useActionState(loginAction, init);

<AppForm defaultValues={{ email: "", password: "" }} action={formAction}>
  <AppField name="email" label="邮箱" type="email" required />
  <AppField name="password" label="密码" type="password" required />
  <AppSubmit>登录</AppSubmit>
</AppForm>

// 模式 B：复杂客户端校验表单
<AppForm
  defaultValues={{ name: "", email: "" }}
  schema={z.object({ name: z.string().min(1), email: z.string().email() })}
  onFinish={handleCreate}
  onFinishFailed={(errors) => toast.error("请检查表单")}
>
  <AppField name="name" label="名称" required />
  <AppField name="email" label="邮箱" type="email" />
  <AppSubmit>创建</AppSubmit>
</AppForm>
```

### 内部架构

```
AppForm
  useForm() from @tanstack/react-form
    ├─ action 模式 → 不 e.preventDefault()
    │  浏览器原生提交，TanStack 只管字段绑定 + 校验展示
    └─ onFinish 模式 → TanStack handleSubmit
       Zod schema 校验 → onFinish(values) | onFinishFailed(errors)

  <form onSubmit={handleSubmit} action={action} noValidate>
    <form.Field name="email">
      {(FieldApi) =>
        <AppLabel />
        <AppInput value={FieldApi.state.value}
                   onChange={FieldApi.handleChange}
                   onBlur={FieldApi.handleBlur} />
        {FieldApi.state.meta.errors?.map(err =>
          <p class="text-destructive">{err.message}</p>
        )}
      }
    </form.Field>
  </form>
```

**AppField 内部封装** `<form.Field>` 的 render-prop，对外暴露 antd 风格 props。不再有 cloneElement，不再有 Context 级联重渲染（TanStack Field 的 store 按字段名独立订阅）。

**Zod 4 + Standard Schema 直连**：Zod 4 实现了 Standard Schema 协议（`~standard` 属性），TanStack Form 1.x 原生支持 `validators.onChange: ZodSchema`，不需要 `@hookform/resolvers/zod` 桥接。

**Action 模式的 isPending**：依赖 TanStack 内建 `form.state.isSubmitting`。AppSubmit 自动绑定 `disabled`。不额外包装 `useActionState`。

## 文件结构

AppForm 新文件放 `components/common/form/`，跟旧文件共存，逐批删除旧文件：

```
components/common/form/
  index.ts            ← 重新导出 AppForm / AppField / AppSubmit
  app-form.tsx        ← 主组件
  app-form.test.tsx   ← 测试
  app-field.tsx       ← 字段组件
  app-field.test.tsx  ← 测试
  app-submit.tsx      ← 提交按钮
  app-submit.test.tsx ← 测试
```

## 迁移路线（5 批）

| 批 | 表单 | 涉及文件 | 动作 |
|---|---|---|---|
| 1 | evaluate-new-form | 1 | 直接换 AppForm（旧 Form 无其他消费者，后续 batch 5 统一删） |
| 2 | 复杂表单：dict-create、create-role、QA、triples 行编辑 | 4 | 手写 useState → AppForm，消掉"原始模式" |
| 3 | Dialog 表单：change-email / change-password / request-deletion / cancel-deletion / create-invite / reset-password | 6 | useActionState + 手写 Label → AppField |
| 4 | 页面表单：login / forgot-password / invite / restore / profile / deletion-section / avatar-uploader | 7 | useActionState + 手写 Label → AppField |
| 5 | 清理旧文件 + 卸依赖 | 4 | 删 form.tsx / form-item.tsx / form-context.ts / index.ts 旧导出 |

### 旧文件删除说明

旧的 Form / FormItem / form-context.ts 只有 1 个消费者（evaluate-new-form.tsx），第 1 批迁移后即无引用。直接在 batch 5 统一删除旧文件 + 卸依赖：

| 步 | 内容 |
|---|---|
| 旧文件清理 | `form.tsx` / `form-item.tsx` / `form-context.ts` / `index.ts` 旧导出 |
| 依赖卸载 | `bun remove react-hook-form @hookform/resolvers` |
| 条件 | 所有 23 处表单均已迁移到 AppForm，测试全绿 |

## 测试策略

### 新增组件测试（~16 个）

| 测试文件 | 覆盖点 | 用例数 |
|---|---|---|
| app-form.test.tsx | action 模式渲染 + action prop 传递、onFinish 模式提交回调、schema 校验通过/失败、layout horizontal 布局、isSubmitting 状态 | ~6 |
| app-field.test.tsx | 默认 Input 按 type 渲染、label/required/help/error、值读写绑定、onBlur 触校验、自定义 children 不 cloneElement、嵌套路径 | ~7 |
| app-submit.test.tsx | children 渲染、isSubmitting 时 disabled、透传 className/data-testid | ~3 |
| Zod Standard Schema 集成 | Zod 4 schema 直接传 validators、错误映射到 meta.errors | ~2 |

### 迁移时改动的测试

| 文件 | 动作 |
|---|---|
| form.test.tsx（10 测） | 删除（替换为新测试） |
| evaluate-new-form 相关测试 | 只改 import `Form` → `AppForm` |
| dict-item-create-dialog.test.tsx | 等第 2 批迁移时改 |
| create-role-dialog.test.tsx | 等第 2 批迁移时改 |
| QA / Triples 测试 | 换 import + 适配 |
| Login / Invite 等 action 测试 | 只换 import，逻辑不变 |

### 不改的测试

login、forgot-password、invite、reset-password 等 action 表单——`useActionState` 在消费端不变，测试逻辑完全不变。

## 验证条件

每批迁移完成后：

1. `bun run format` — 0 reformat
2. `bun run lint:fix` — 0 error
3. `bun run typecheck` — 0 error
4. `bun run test` — 719 passed（不新增失败）
5. `bun run test:coverage` — 覆盖率不降
6. 受影响表单的 E2E 测试通过

## 可卸依赖

| 包 | 原因 |
|---|---|
| `react-hook-form` | 仅 shadcn Form 模板引用，AppForm 不再需要 |
| `@hookform/resolvers` | Zod 4 Standard Schema 直连 TanStack，不需要 bridge |
