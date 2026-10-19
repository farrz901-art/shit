# Zod 教程

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

Zod 是一个 TypeScript 优先的运行时 + 静态类型校验库。用一个 schema 既能验证运行时数据，又能推断出静态类型，零类型冗余。Zod 3.x 是事实标准（v4 还在 RC 阶段），覆盖 string/number/object/array/union/record/refine 等 100+ 验证器。

**同类对比：**

| 库 | 定位 | 本项目选择理由 |
|------|------|----------------|
| **Zod** | TS 优先校验 | 推断强，生态大，react-hook-form / tRPC 集成 |
| **Yup** | 老牌校验 | 旧项目用得多，TS 推断弱 |
| **Joi** | Node 端校验 | 不支持 TS 推断 |
| **Valibot** | 轻量校验 | 新项目，体积小但生态小 |
| **Zod 4 (RC)** | 下一代 Zod | 性能更好，API 略变，本项目观望 |

**Zod 解决的核心问题**：
- **运行时验证**：用户输入 / API 响应 / 配置 → 不合法直接抛错
- **类型推断**：`type User = z.infer<typeof UserSchema>`，schema 即类型源
- **统一前后端契约**：后端 Pydantic 模型 + 前端 Zod schema 一一对应
- **表单验证**：跟 react-hook-form + @hookform/resolvers 集成

---

## 二、安装 & 开发环境

### 2.1 安装

```bash
# 项目已装 (package.json: "zod": "^4.4.3")
cd packages/web
bun install
```

### 2.2 基础使用

```typescript
import { z } from "zod";

const UserSchema = z.object({
  name: z.string().min(1),
  email: z.string().email(),
  age: z.number().int().min(0).max(150),
});

type User = z.infer<typeof UserSchema>;
// type User = { name: string; email: string; age: number }

const user: User = UserSchema.parse({
  name: "Alice", email: "alice@x.com", age: 30,
});
```

---

## 三、基础语法 & 类型系统

### 3.1 基本类型

```typescript
import { z } from "zod";

z.string();                       // string
z.number();                       // number
z.boolean();                      // boolean
z.date();                         // Date
z.bigint();                       // bigint
z.symbol();                       // symbol
z.null();                         // null
z.undefined();                    // undefined
z.any();                          // any
z.unknown();                      // unknown
z.void();                         // void
z.never();                        // never
```

### 3.2 字符串验证

```typescript
z.string().min(1).max(50);
z.string().email();
z.string().url();
z.string().uuid();
z.string().regex(/^\d+$/);
z.string().trim().toLowerCase();   // 转换
z.string().datetime();            // ISO 8601
```

### 3.3 数字验证

```typescript
z.number().int();
z.number().min(0).max(100);
z.number().positive();
z.number().nonnegative();
z.number().multipleOf(5);
z.number().finite();              // 排除 NaN / Infinity
```

### 3.4 对象

```typescript
const UserSchema = z.object({
  name: z.string(),
  email: z.string().email(),
  role: z.enum(["user", "admin"]),
});

// 部分字段
UserSchema.partial();              // 所有字段 optional
UserSchema.pick({ name: true });   // { name: string }
UserSchema.omit({ email: true });  // 去掉 email

// 嵌套
const PostSchema = z.object({
  title: z.string(),
  author: UserSchema,
});
```

### 3.5 数组 / 元组

```typescript
z.array(z.string());                    // string[]
z.array(z.number()).min(1).max(10);     // 1-10 个数字
z.tuple([z.string(), z.number()]);      // [string, number]
```

### 3.6 联合 / 字面量

```typescript
z.literal("admin");                     // type: "admin"
z.union([z.string(), z.number()]);      // string | number
z.enum(["a", "b", "c"]);                // "a" | "b" | "c"
z.discriminatedUnion("type", [          // discriminated union
  z.object({ type: z.literal("user"), name: z.string() }),
  z.object({ type: z.literal("admin"), permissions: z.array(z.string()) }),
]);
```

### 3.7 可选 / 默认值

```typescript
z.string().optional();      // string | undefined
z.string().nullable();      // string | null
z.string().default("hi");   // 缺省时填 "hi"，type 是 string（不含 undefined）
```

### 3.8 Refine（自定义验证）

```typescript
z.string().refine(s => s !== "forbidden", { message: "Forbidden word" });
z.object({
  password: z.string(),
  confirm: z.string(),
}).refine(data => data.password === data.confirm, {
  message: "Passwords don't match",
  path: ["confirm"],
});
```

### 3.9 转换

```typescript
z.string().transform(s => parseInt(s, 10));   // string → number
z.string().transform(s => s.toLowerCase());
z.coerce.number();                              // 强制转 number（z.coerce.*）
```

### 3.10 类型推断

```typescript
const Schema = z.object({ name: z.string() });
type T = z.infer<typeof Schema>;            // { name: string }
type Input = z.input<typeof Schema>;        // 输入类型（transform 前）
type Output = z.output<typeof Schema>;      // 输出类型（transform 后）
```

---

## 四、核心概念

### 4.1 Schema（模式）

Zod 的核心，用链式 API 描述数据类型 + 验证规则。

### 4.2 parse vs safeParse

```typescript
// parse：失败抛 ZodError
const user = UserSchema.parse(data);

// safeParse：返 { success, data | error }
const result = UserSchema.safeParse(data);
if (result.success) {
  result.data;   // User
} else {
  result.error;  // ZodError
}
```

### 4.3 错误处理

```typescript
const result = UserSchema.safeParse(data);
if (!result.success) {
  // result.error.issues: { code, path, message }
  for (const issue of result.error.issues) {
    console.log(`${issue.path.join(".")}: ${issue.message}`);
  }
}
```

### 4.4 TypeScript 类型 vs 运行时校验

Zod 的革命性在于：**一份 schema，两种用途**。

```typescript
const UserSchema = z.object({ name: z.string() });
type User = z.infer<typeof UserSchema>;   // 编译时类型

const data: unknown = await fetchUser();
const user = UserSchema.parse(data);       // 运行时校验
// 此后 user 是 User 类型，TS 完全信任
```

### 4.5 组合（composition）

```typescript
const BaseSchema = z.object({ id: z.number(), created_at: z.string() });
const UserSchema = BaseSchema.extend({ name: z.string() });
const AdminSchema = UserSchema.extend({ permissions: z.array(z.string()) });
```

---

## 五、常用命令 & 工具链

Zod 不需要单独命令。配合 TypeScript 推断：

```bash
bun run typecheck   # tsc --noEmit
```

---

## 六、项目集成点

### 6.1 项目当前用法

`packages/web/package.json:67`：`"zod": "^4.4.3"`

项目用 Zod 做：

1. **API 响应类型**：用 Zod schema 校验 BFF 响应，自动推断 TypeScript 类型
2. **表单验证**：跟 react-hook-form + @hookform/resolvers/zod 集成
3. **类型守卫**：`UserSchema.parse(data)` 后 TypeScript 自动收窄类型

### 6.2 业务 enum 必须走 lookup

项目 `service/CLAUDE.md` 明确：**业务 enum 走 lookup 字典**（详见 `python/lookup.md`），不允许硬编 `StrEnum`。前端 Zod 配合时：

```typescript
// ❌ 错：硬编 enum
const StatusSchema = z.enum(["pending", "approved", "rejected"]);

// ✅ 对：从后端 lookup 拉，动态生成
const statuses = await fetchLookups("approval_status");
const StatusSchema = z.enum(statuses.map(s => s.code));
```

### 6.3 Pydantic ↔ Zod 协作

后端 Pydantic 模型是 schema 源，前端 Zod 校验响应。可以用 `zod-to-json-schema` + `json-schema-to-pydantic` 双向同步，但本项目暂时手动维护。

---

## 七、项目代码示例

### 7.1 API 响应校验

`lib/api/schemas.ts`（项目模式）：

```typescript
import { z } from "zod";

export const UserSchema = z.object({
  id: z.number().int().positive(),
  email: z.string().email(),
  display_name: z.string().min(1).max(50),
  role: z.enum(["user", "admin", "super_admin"]),
  is_active: z.boolean(),
  created_at: z.string().datetime(),
});

export type User = z.infer<typeof UserSchema>;

export const UserListResponseSchema = z.object({
  items: z.array(UserSchema),
  total: z.number().int().min(0),
});

export type UserListResponse = z.infer<typeof UserListResponseSchema>;
```

### 7.2 BFF 响应解析

```typescript
import { UserListResponseSchema } from "@/lib/api/schemas";

export const fetchUsers = async (): Promise<UserListResponse> => {
  const res = await fetch("/api/admin/users");
  const json = await res.json();
  return UserListResponseSchema.parse(json);   // 运行时校验
};
```

### 7.3 Form 验证（react-hook-form + zod）

`components/admin/user-form.tsx`：

```typescript
"use client";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Form, FormField, FormItem, FormLabel, FormControl, FormMessage } from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";

const FormSchema = z.object({
  email: z.string().email("邮箱格式不对"),
  display_name: z.string().min(2, "至少 2 个字").max(50),
  role: z.enum(["user", "admin"]),
  password: z.string().min(8, "密码至少 8 位").optional(),
}).refine(data => data.role === "user" || !!data.password, {
  message: "非普通用户必须设密码",
  path: ["password"],
});

type FormValues = z.infer<typeof FormSchema>;

export const UserForm = ({ onSubmit }: { onSubmit: (v: FormValues) => void }) => {
  const form = useForm<FormValues>({ resolver: zodResolver(FormSchema) });
  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
        <FormField control={form.control} name="email" render={({ field }) => (
          <FormItem>
            <FormLabel>邮箱</FormLabel>
            <FormControl><Input {...field} type="email" /></FormControl>
            <FormMessage />
          </FormItem>
        )} />
        <Button type="submit" disabled={form.formState.isSubmitting}>提交</Button>
      </form>
    </Form>
  );
};
```

### 7.4 Environment 变量校验

`lib/env.ts`（项目最佳实践）：

```typescript
import { z } from "zod";

const EnvSchema = z.object({
  NEXT_PUBLIC_API_URL: z.string().url(),
  NEXT_PUBLIC_LOCALE: z.enum(["zh", "en"]).default("zh"),
  LANGFUSE_PUBLIC_KEY: z.string().optional(),
});

export const env = EnvSchema.parse({
  NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL,
  NEXT_PUBLIC_LOCALE: process.env.NEXT_PUBLIC_LOCALE,
  LANGFUSE_PUBLIC_KEY: process.env.NEXT_PUBLIC_LOCALE,
});
```

启动时校验，缺关键 env 直接报错。

### 7.5 业务 enum 动态生成

```typescript
// 拉 lookup 字典
const items = await fetchLookups("approval_status");
const ApprovalStatusSchema = z.enum(items.map(i => i.code) as [string, ...string[]]);
```

### 7.6 Discriminated Union（业务事件）

```typescript
const ChatEventSchema = z.discriminatedUnion("type", [
  z.object({ type: z.literal("user_message"), text: z.string() }),
  z.object({ type: z.literal("ai_chunk"), text: z.string() }),
  z.object({ type: z.literal("done"), message_id: z.string() }),
]);

type ChatEvent = z.infer<typeof ChatEventSchema>;

// 收 SSE / WebSocket 时按 type 收窄
const event: ChatEvent = ChatEventSchema.parse(json);
if (event.type === "ai_chunk") {
  console.log(event.text);   // type 收窄后，event.text 存在
}
```

### 7.7 深嵌套 + 默认值

```typescript
const ConfigSchema = z.object({
  pagination: z.object({
    page_size: z.number().int().min(1).max(100).default(20),
    page: z.number().int().min(1).default(1),
  }).default({}),
  filters: z.array(z.string()).default([]),
});
```

---

## 八、项目没用到的能力 / 进阶方向

以下 Zod 能力项目当前未充分使用（**待评估**）：

| 能力 | 用途 | 集成建议 |
|------|------|----------|
| **`z.brand<"UserId">()`** | 强类型 ID | 防止不同 ID 混用 |
| **`z.codec`**（v4 新）| 自定义 encode/decode | 跟 protobuf 集成 |
| **`z.discriminatedUnion`** | 多态事件 | SSE / WebSocket 流 |
| **`z.lazy()`** | 递归 schema | 树形数据（评论 / 知识图谱） |
| **`z.preprocess`** | 输入前转换 | 兼容老 API 字段名 |
| **`z.record(z.string(), z.unknown())`** | 字典 | 通用 JSON 解析 |
| **`z.coerce.*`** | 强制类型转换 | 表单字符串转数字 |
| **Zod 4** | 性能 + 体积优化 | 项目观望中 |

**建议关注**：`z.brand` 适合 ID 类型化（如 `UserId` vs `OrderId` 都是 number，但语义不同）。

---

## 九、最佳实践 & 常见坑

### 项目风格指南（项目 CLAUDE.md 强制）

1. **业务 enum 走 lookup 字典**：不要硬编 Zod `z.enum(["a", "b", "c"])`
2. **类型注解用 `z.infer`**：不要手写 `interface User { ... }` 后再 `z.object({...})` 重复维护
3. **后端 Pydantic + 前端 Zod**：schema 字段名要严格对齐
4. **i18n 错误消息**：错误 message 可以是 i18n key，由 `<FormMessage />` 翻译

### 最佳实践

1. **导出 schema + type**：

```typescript
export const UserSchema = z.object({...});
export type User = z.infer<typeof UserSchema>;
```

2. **复用 schema**：

```typescript
const BaseUser = z.object({ id: z.number(), email: z.string().email() });
export const UserCreateSchema = BaseUser.extend({ password: z.string() });
export const UserUpdateSchema = BaseUser.partial();
```

3. **safeParse 优于 parse**（业务代码）：
   - `parse`：开发 / 测试环境，失败要立即看到错
   - `safeParse`：生产环境，优雅降级

4. **错误格式化**：

```typescript
const formatZodError = (err: z.ZodError) =>
  err.issues.map(i => `${i.path.join(".")}: ${i.message}`).join("; ");
```

5. **环境变量 / 配置**用 Zod 校验：启动即报，避免运行时才出错

### 常见坑

1. **`z.string()` 默认允许空字符串**：要 `min(1)`

```typescript
z.string();              // ""
z.string().min(1);       // 至少 1 字符
z.string().regex(/\S/);  // 至少 1 非空白
```

2. **`z.number()` 不接受 NaN**：

```typescript
z.number().parse(NaN);   // ❌ 报错
z.number().finite();     // 明确拒绝 NaN
```

3. **`z.object().strict()` 禁止额外字段**：

```typescript
z.object({ name: z.string() }).parse({ name: "Alice", age: 30 });
// 错：unknown field "age"
// 默认会剥掉额外字段（silent strip），strict 模式会报错
```

4. **transform 链注意类型变化**：

```typescript
const Schema = z.string().transform(s => parseInt(s, 10));
type T = z.infer<typeof Schema>;   // number
type I = z.input<typeof Schema>;  // string
```

5. **嵌套对象错误路径**：

```typescript
const Schema = z.object({ user: z.object({ name: z.string() }) });
Schema.parse({ user: { name: 123 } });
// 错误路径是 "user.name"，不是 "name"
```

6. **`z.record(z.string(), z.number())`** 跟 `Record<string, number>` 一样，**不限制 key 集合**

7. **Zod 4 兼容性**：项目 v4 是 4.4.3。Zod 3 → 4 有 breaking（error.issues 改 error.errors 等），升级前看 migration guide

8. **Pydantic ↔ Zod 字段名差异**：

| Python | Zod |
|--------|-----|
| `user_id` | `userId`（默认）/ `user_id`（配 alias）|
| `is_active: bool` | `isActive: z.boolean()` |
| `Optional[str]` | `z.string().optional()` |

如果前端想直接复用后端 Pydantic 字段名（snake_case），需要 Zod schema 加 `.transform()` 或用 `snake_case` 字段名。

---

## 📚 参考

- [Zod 官方文档](https://zod.dev/)
- [Zod GitHub](https://github.com/colinhacks/zod)
- [Zod 4 迁移指南](https://zod.dev/v4/changelog)
- [react-hook-form + Zod 集成](https://react-hook-form.com/get-started#SchemaValidation)
- [Zod vs Yup vs Joi](https://zod.dev/?id=comparison)
- [项目 web/CLAUDE.md](../../packages/web/CLAUDE.md)

---

**状态：** ✅ 已完成

**最后更新：** 2026-06-25
