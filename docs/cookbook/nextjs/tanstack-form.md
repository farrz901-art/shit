# TanStack Form 教程

> 📅 创建日期：2026-06-25
> 📁 项目代码引用：本教程以 `c:/doc/Code/rag` 仓库当前代码为准，所有引用标注 `file_path:line_number`
> 🏷️ 类别：L-语言/框架
> 🎯 读者：中高级 TS 工程师

---

## 目录

- [一、是什么 & 适用场景](#一是什么--适用场景)
- [二、安装 & 开发环境](#二安装--开发环境)
- [三、基础语法 & 类型系统](#三基础语法--类型系统)
- [四、核心概念](#四核心概念)
- [五、常用命令 & 工具链](#五常用命令--工具链)
- [六、项目集成点](#六项目集成点)
- [七、项目代码示例](#七项目代码示例)
- [八、项目没用到的能力 / 进阶方向](#八项目没用到的能力--进阶方向)
- [九、最佳实践 & 常见坑](#九最佳实践--常见坑)

---

## 一、是什么 & 适用场景

TanStack Form 是 TanStack Query 团队出品的无头（headless）表单库。它的核心是**框架无关的状态机** + 完全自定义 UI，跟 react-hook-form 一样，TypeScript 推断和性能都是顶配。

**同类对比：**

| 库 | 定位 | 本项目选择理由 |
|------|------|----------------|
| **TanStack Form** | Headless 表单状态机 | TS 推断极好，可控性高 |
| **react-hook-form** | 老牌 Headless 表单 | 项目**主力**，生态成熟 |
| **Formik** | 老牌表单 | 体积大，性能弱 |
| **react-final-form** | 订阅式表单 | 学习曲线陡 |
| **Mantine Form** | 跟 Mantine UI 绑定 | 跟项目栈不匹配 |

**TanStack Form 解决的核心问题**：
- **类型安全**：Field-level 类型推断，无需手写泛型
- **Headless**：UI 完全自己控制
- **多框架**：React / Vue / Solid / Angular 一套 API
- **异步验证**：`onChange` / `onBlur` / `onSubmit` 三种触发时机
- **数组字段**：`useField` + 嵌套表单原生支持

---

## 二、安装 & 开发环境

### 2.1 安装

```bash
# 项目已装 (@tanstack/react-form: ^1.33.0)
cd packages/web
bun install
```

### 2.2 项目风格

项目目前用 **react-hook-form**（`@hookform/resolvers` 跟 Zod 集成）。TanStack Form 已装但暂未广泛使用，本教程作为新功能/复杂表单的备选。

---

## 三、基础语法 & 类型系统

### 3.1 最简表单

```typescript
import { useForm } from "@tanstack/react-form";

type FormValues = { name: string; email: string };

export const MyForm = () => {
  const form = useForm({
    defaultValues: { name: "", email: "" } as FormValues,
    onSubmit: async ({ value }) => {
      console.log("submit", value);
    },
  });

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        e.stopPropagation();
        form.handleSubmit();
      }}
    >
      <form.Field
        name="name"
        children={(field) => (
          <input
            value={field.state.value}
            onChange={(e) => field.handleChange(e.target.value)}
          />
        )}
      />
      <button type="submit">提交</button>
    </form>
  );
};
```

### 3.2 验证

```typescript
form.Field(
  name="email"
  validators={{
    onChange: ({ value }) => (!value.includes("@") ? "Invalid email" : undefined),
    onBlur: ({ value }) => (value.length < 5 ? "Too short" : undefined),
  }}
  children={(field) => (
    <>
      <input value={field.state.value} onChange={(e) => field.handleChange(e.target.value)} onBlur={field.handleBlur} />
      {field.state.meta.errors.map((err) => <span key={err}>{err}</span>)}
    </>
  )}
)
```

### 3.3 Zod 适配

`@tanstack/zod-form-adapter`：

```typescript
import { zodValidator } from "@tanstack/zod-form-adapter";
import { z } from "zod";

const FormSchema = z.object({
  name: z.string().min(1),
  email: z.string().email(),
});

const form = useForm({
  defaultValues: { name: "", email: "" },
  validatorAdapter: zodValidator(),
  validators: {
    onChange: FormSchema,
  },
  onSubmit: async ({ value }) => {...},
});
```

### 3.4 数组字段

```typescript
<form.Field
  name="items"
  mode="array"
  children={(field) => (
    <>
      {field.state.value.map((_, i) => (
        <form.Field
          key={i}
          name={`items[${i}].name`}
          children={(subField) => (
            <input value={subField.state.value} onChange={(e) => subField.handleChange(e.target.value)} />
          )}
        />
      ))}
      <button onClick={() => field.pushValue({ name: "" })}>添加</button>
    </>
  )}
/>
```

### 3.5 异步提交 + 状态

```typescript
<form.Subscribe
  selector={(state) => ({ isSubmitting: state.isSubmitting, canSubmit: state.canSubmit })}
  children={(state) => (
    <button disabled={!state.canSubmit}>
      {state.isSubmitting ? "提交中..." : "提交"}
    </button>
  )}
/>
```

---

## 四、核心概念

### 4.1 Headless

不绑 UI，只管表单状态机和验证。UI 自己写（一般配合 shadcn `<Form>` + `<FormField>`）。

### 4.2 Field

`form.Field` 是核心组件，订阅单个字段状态，传入 `children` 函数获得 `field` 对象。

```typescript
<form.Field name="email" children={(field) => {
  field.state.value;     // 当前值
  field.handleChange();  // 改值
  field.handleBlur();    // blur
  field.state.meta;      // 错误 / 触摸状态 / 验证状态
}} />
```

### 4.3 FormState

```typescript
form.state.values;        // 全部值
form.state.errors;        // 表单级错误
form.state.isSubmitting;  // 提交中
form.state.canSubmit;     // 是否可提交
form.state.isDirty;       // 是否被改过
form.state.isValid;       // 是否验证通过
form.reset();             // 重置到 defaultValues
form.validateAllFields(); // 主动验证全部
```

### 4.4 验证时机

```typescript
validators: {
  onChange: ...,   // 值变化时
  onBlur: ...,     // 失焦时
  onSubmit: ...,   // 提交时
  onMount: ...,    // 组件挂载时
}
```

### 4.5 Subscribe

`form.Subscribe` 订阅 form 状态（不订阅字段）：

```typescript
<form.Subscribe
  selector={(state) => ({ isSubmitting: state.isSubmitting })}
  children={(state) => <button disabled={state.isSubmitting}>...</button>}
/>
```

---

## 五、常用命令 & 工具链

```bash
# 项目无专属命令
bun run typecheck
```

---

## 六、项目集成点

### 6.1 项目当前主要用 react-hook-form

`packages/web/CLAUDE.md` §聊天/表单：

- 项目用 `<Form>` + `<FormField>` + react-hook-form 封装
- Zod 验证（`@hookform/resolvers/zod`）
- 跟 shadcn UI 集成（项目 `<FormField>` 包装）

### 6.2 TanStack Form 已装待启用

`@tanstack/react-form: ^1.33.0` 已装，但**项目当前主用 react-hook-form**。TanStack Form 适合：

- 跨框架共享表单逻辑
- 极复杂嵌套（树形 / 列表）
- 想要更细粒度的 state 订阅

### 6.3 切换建议

新功能可以选 TanStack Form，老功能保持 react-hook-form。混用没问题（不同组件互不影响）。

---

## 七、项目代码示例

### 7.1 用户注册表单（基础）

```typescript
"use client";
import { useForm } from "@tanstack/react-form";
import { zodValidator } from "@tanstack/zod-form-adapter";
import { z } from "zod";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";

const FormSchema = z.object({
  email: z.string().email(),
  password: z.string().min(8),
  display_name: z.string().min(2).max(50),
});

type FormValues = z.infer<typeof FormSchema>;

export const RegisterForm = () => {
  const form = useForm({
    defaultValues: { email: "", password: "", display_name: "" } as FormValues,
    validatorAdapter: zodValidator(),
    validators: { onChange: FormSchema },
    onSubmit: async ({ value }) => {
      await fetch("/api/auth/register", { method: "POST", body: JSON.stringify(value) });
    },
  });

  return (
    <form onSubmit={(e) => { e.preventDefault(); form.handleSubmit(); }} className="space-y-4">
      <form.Field
        name="email"
        children={(field) => (
          <div>
            <Input
              value={field.state.value}
              onChange={(e) => field.handleChange(e.target.value)}
              onBlur={field.handleBlur}
              type="email"
              placeholder="邮箱"
            />
            {field.state.meta.errors.map((err) => <p key={err as string} className="text-destructive text-sm">{err}</p>)}
          </div>
        )}
      />
      {/* password + display_name 同上 */}
      <form.Subscribe
        selector={(s) => ({ canSubmit: s.canSubmit, isSubmitting: s.isSubmitting })}
        children={({ canSubmit, isSubmitting }) => (
          <Button type="submit" disabled={!canSubmit || isSubmitting}>
            {isSubmitting ? "提交中..." : "注册"}
          </Button>
        )}
      />
    </form>
  );
};
```

### 7.2 数组字段（订单行）

```typescript
<form.Field
  name="items"
  mode="array"
  children={(field) => (
    <div className="space-y-2">
      {field.state.value.map((_, i) => (
        <div key={i} className="flex gap-2">
          <form.Field
            name={`items[${i}].sku`}
            children={(skuField) => (
              <Input
                value={skuField.state.value}
                onChange={(e) => skuField.handleChange(e.target.value)}
                placeholder="SKU"
              />
            )}
          />
          <form.Field
            name={`items[${i}].qty`}
            children={(qtyField) => (
              <Input
                type="number"
                value={qtyField.state.value}
                onChange={(e) => qtyField.handleChange(Number(e.target.value))}
                placeholder="数量"
              />
            )}
          />
          <Button variant="ghost" onClick={() => field.removeValue(i)}>删除</Button>
        </div>
      ))}
      <Button variant="outline" onClick={() => field.pushValue({ sku: "", qty: 1 })}>
        添加行
      </Button>
    </div>
  )}
/>
```

### 7.3 异步验证（查 SKU 是否存在）

```typescript
<form.Field
  name="sku"
  validators={{
    onChangeAsync: async ({ value }) => {
      if (!value) return undefined;
      const exists = await checkSKU(value);
      return exists ? "SKU 已存在" : undefined;
    },
    // 防抖
    onChangeAsyncDebounceMs: 500,
  }}
  children={(field) => (
    <Input value={field.state.value} onChange={(e) => field.handleChange(e.target.value)} />
  )}
/>
```

### 7.4 跨字段验证（密码确认）

```typescript
const form = useForm({
  defaultValues: { password: "", confirm: "" },
  validators: {
    onChange: z.object({
      password: z.string().min(8),
      confirm: z.string(),
    }).refine(data => data.password === data.confirm, {
      message: "Passwords don't match",
      path: ["confirm"],
    }),
  },
});
```

### 7.5 项目 FormField 包装（项目风格）

如果项目用 TanStack Form 替代 react-hook-form，需要类似包装：

```typescript
// components/common/form/tanstack-form-field.tsx
"use client";
import { useFormContext } from "...";  // TanStack 没内置，但容易封装

export const FormField = ({ name, children }: { name: string; children: (field: any) => React.ReactNode }) => {
  const form = useFormContext();
  return (
    <form.Field name={name} children={children} />
  );
};
```

---

## 八、项目没用到的能力 / 进阶方向

以下 TanStack Form 能力项目当前未使用（**待评估**）：

| 能力 | 用途 | 集成建议 |
|------|------|----------|
| **跨字段验证** | 密码确认、关联字段 | 复杂表单 |
| **数组字段** | 订单行、列表 | 多行表单 |
| **Field Group** | 字段分组 + 共享 validation | 复杂 UI |
| **Async Validation** | 服务端校验 | 检查重复 / 远程验证 |
| **Standard Schema 适配** | Zod / Yup / Valibot 通用 | 跟 zod-form-adapter 集成 |
| **React 19 `useActionState` 集成** | Server Actions 提交 | 新 RSC 模式 |
| **多步骤表单** | Wizard / Stepper | 复杂注册流程 |
| **动态默认值** | `defaultValues: async () => {...}` | 异步初始化 |

**建议关注**：跨字段验证（密码确认）+ 数组字段是项目最可能用到的能力。

---

## 九、最佳实践 & 常见坑

### 1. form.handleSubmit 调用

```typescript
// ❌ 错：忘记 preventDefault
<form onSubmit={form.handleSubmit}>
  // 浏览器会刷新页面
</form>

// ✅ 对
<form onSubmit={(e) => { e.preventDefault(); e.stopPropagation(); form.handleSubmit(); }}>
```

### 2. 异步 onSubmit

```typescript
// ✅ 异步自动管理 isSubmitting
onSubmit: async ({ value }) => {
  await api.post(value);
  // isSubmitting 自动 true → false
},
```

### 3. 默认值类型断言

```typescript
// ✅ 用 as 断言类型
defaultValues: { name: "", email: "" } as FormValues

// 否则 TS 推为 { name: string; email: string }，缺字段会报错
```

### 4. onChange 验证触发频率

`onChange` 验证每次按键都跑，性能差。用 `onBlur` 或 `onChangeAsyncDebounceMs`：

```typescript
validators: {
  onChange: ...,                     // 每键
  onBlur: ...,                       // 失焦
  onChangeAsyncDebounceMs: 500,     // 防抖
}
```

### 5. 嵌套对象字段

```typescript
<form.Field name="address.city" children={(field) => ...} />
// 嵌套对象 { address: { city: string } }
```

### 6. `form.Subscribe` 避免重渲染

只订阅需要的 state：

```typescript
// ❌ 错：订阅全部
<form.Subscribe>{(state) => <span>{state.values.name}</span>}</form.Subscribe>

// ✅ 对：用 selector
<form.Subscribe selector={(s) => s.values.name}>{(name) => <span>{name}</span>}</form.Subscribe>
```

### 7. Field-level 错误 vs Form-level 错误

- `field.state.meta.errors`：单个字段错误
- `form.state.errors`：整个表单错误（如 cross-field validation）

### 8. 与项目 `<Form>` 封装集成

项目用 react-hook-form 包装的 `<Form>` 组件，TanStack Form 不能直接复用。如果要切到 TanStack Form，需要新建 `<TanForm>` + `<TanFormField>` 包装。

### 9. 跟 Zod 一起用

`@tanstack/zod-form-adapter` 跟 v1.x 兼容，Zod 4.x 还在适配中。版本匹配：

```json
"@tanstack/react-form": "^1.33.0",
"@tanstack/zod-form-adapter": "^1.x"  // 跟 react-form 同 minor
```

---

## 📚 参考

- [TanStack Form 官方文档](https://tanstack.com/form/latest)
- [TanStack Form GitHub](https://github.com/TanStack/form)
- [react-hook-form 教程](https://react-hook-form.com/)（项目主力）
- [Zod 适配器](https://tanstack.com/form/latest/docs/framework/react/guides/validation)
- [项目 web/CLAUDE.md](../../packages/web/CLAUDE.md)

---

**状态：** ✅ 已完成

**最后更新：** 2026-06-25
