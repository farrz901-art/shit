# React 教程

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

React 是 Meta 维护的 UI 库，通过组件化、声明式编程和虚拟 DOM 让构建交互式 Web 界面更简单。React 19（2024 年 12 月发布）引入了 Server Components、`use` hook、Actions、`<Form>` 元素等新能力。

**同类对比：**

| 库 | 定位 | 本项目选择理由 |
|------|------|----------------|
| **React** | 组件化 UI 库 | 生态最大，团队熟悉 |
| **Vue** | 渐进式 UI 框架 | 团队用 React |
| **Solid.js** | 细粒度响应式 | 性能更强但生态小 |
| **Svelte** | 编译时框架 | 写法差异大，团队不熟 |
| **Preact** | React 兼容 3KB | 体积小但生态小 |

**React 解决的核心问题**：
- **组件化 UI**：可复用、易测试
- **声明式渲染**：描述状态 → UI，框架处理 DOM 操作
- **跨平台**：React DOM / React Native / React 3D

---

## 二、安装 & 开发环境

### 2.1 版本要求

- React ^19.2.7（项目 `packages/web/package.json`）
- TypeScript ^5.x

### 2.2 包管理

```bash
cd packages/web
bun install
```

### 2.3 开发工具链

项目用 oxlint + oxfmt + tsc：

```bash
bun run typecheck      # tsc --noEmit
bun run lint           # oxlint
bun run lint:fix       # oxlint --fix
bun run format         # oxfmt --write
```

---

## 三、基础语法 & 类型系统

### 3.1 函数组件

```typescript
type ButtonProps = {
  label: string;
  onClick: () => void;
  disabled?: boolean;
};

const Button = ({ label, onClick, disabled }: ButtonProps) => {
  return (
    <button onClick={onClick} disabled={disabled}>
      {label}
    </button>
  );
};
```

### 3.2 JSX

JSX 是 JavaScript 的语法扩展，`{}` 内嵌表达式：

```tsx
const Greeting = ({ name, count }: { name: string; count: number }) => (
  <div>
    <h1>Hello, {name}!</h1>
    <p>You have {count} messages.</p>
    {count > 0 && <Badge value={count} />}
  </div>
);
```

### 3.3 Hooks

```typescript
import { useState, useEffect, useMemo, useCallback } from "react";

const SearchBox = ({ onSearch }: { onSearch: (q: string) => void }) => {
  const [query, setQuery] = useState("");
  const debouncedQuery = useMemo(() => query, [query]);
  useEffect(() => {
    onSearch(debouncedQuery);
  }, [debouncedQuery, onSearch]);
  return <input value={query} onChange={e => setQuery(e.target.value)} />;
};
```

### 3.4 Props 类型

```typescript
// 必填 + 可选 + 子节点
type CardProps = {
  title: string;
  footer?: React.ReactNode;
  children: React.ReactNode;
  onAction?: (id: string) => void;
};
```

### 3.5 Discriminated Union（受控联合类型）

React 19 推荐用 union 表达组件状态：

```typescript
type AsyncState<T> =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "success"; data: T }
  | { status: "error"; error: Error };
```

---

## 四、核心概念

### 4.1 组件 + Props

UI 由组件树组成，父组件通过 props 传数据给子组件，props 是单向数据流。

### 4.2 State（useState）

组件内部的可变状态。状态变化触发重新渲染。

### 4.3 Effect（useEffect）

副作用钩子，组件 mount/update/unmount 时执行。**项目注意**：现代 React 优先用事件处理器 + Server Components，减少 useEffect 依赖。

### 4.4 Refs（useRef）

获取 DOM 节点或存储可变值，**不会**触发重渲染。

### 4.5 Context

跨组件传值（theme、auth、locale），避免 prop drilling。

### 4.6 渲染模型

- **Render 阶段**：纯函数计算虚拟 DOM
- **Commit 阶段**：把虚拟 DOM 应用到真实 DOM
- **Reconciliation**：diff 算法找最小更新

### 4.7 React 19 新能力

- **`use` hook**：读取 Promise / Context（条件分支里也可用）
- **Actions**：自动处理 pending / error / optimistic update
- **`<Form>` 元素**：浏览器级 form + 自动 reset
- **Server Components**：在服务端渲染，0 客户端 JS

---

## 五、常用命令 & 工具链

```bash
# 项目命令（packages/web）
bun run dev            # 开发
bun run build          # 生产构建
bun run typecheck      # 类型检查
bun run lint           # Lint
bun run format         # Format
bun run test           # vitest
```

---

## 六、项目集成点

### 6.1 项目用 React 19 + Next.js 16

- **Server Components（默认）**：直接 `await` 数据，无 useEffect
- **Client Components**：`"use client"` 显式声明
- **shadcn/ui**：基于 Radix UI + Tailwind 4，封装到 `components/ui/`

### 6.2 项目封装组件（项目 CLAUDE.md 强制使用）

| 封装组件 | 替代什么 |
|---------|---------|
| `<DataTable<T>>` | 手写 `<Table>` / `<thead>` / `<tr>` / `<td>` |
| `<AppDialog>` | 手写 `<div className="fixed inset-0 bg-black/50">` |
| `<AppConfirm>` | `window.confirm()` |
| `<AppDrawer>` | 抽屉业务 |
| `<Form>` / `<FormItem>` | `<form onSubmit>` 模板 |
| `<FormField>` | Label + 错误展示 |
| `<FileDropzone>` | 手写 `<label>` + `<input type="file">` |
| `<DataEmpty>` | "暂无数据" 文本 |
| `<AppSelect>` | shadcn 6-行 `<Select>` 模板 |
| `<AppToggle>` | 手写按钮组（view 切换） |
| `<ErrorBanner>` | `<div className="border-destructive/30 ...">` |
| `<CopyButton>` | `navigator.clipboard.writeText` |
| `<AppTooltip>` | Radix Tooltip 4-子件模板 |

### 6.3 React 19 关键应用

- **`useFormStatus` / `useActionState`**：表单提交状态（项目 `<Form>` 封装用）
- **`useOptimistic`**：乐观更新（适合 LLM 流式响应场景）
- **`use` hook**：读取 Server Component Promise

---

## 七、项目代码示例

### 7.1 函数组件 + Props

`components/common/data-table/data-table.tsx`（推测项目风格）：

```typescript
type DataTableProps<T> = {
  dataSource: T[];
  columns: ColumnDef<T>[];
  rowKey: keyof T;
  emptyText?: React.ReactNode;
  loading?: boolean;
};

export const DataTable = <T,>({
  dataSource,
  columns,
  rowKey,
  emptyText = "暂无数据",
  loading = false,
}: DataTableProps<T>) => {
  if (loading) return <Skeleton />;
  if (dataSource.length === 0) return <DataEmpty title={emptyText} />;
  return (
    <table>
      <thead>{/* ... */}</thead>
      <tbody>
        {dataSource.map((row, idx) => (
          <tr key={String(row[rowKey])}>{/* ... */}</tr>
        ))}
      </tbody>
    </table>
  );
};
```

### 7.2 Server Component

```typescript
// app/[locale]/page.tsx (无 "use client")
import { getTranslations } from "next-intl/server";

export default async function HomePage() {
  const t = await getTranslations();
  return (
    <main>
      <h1>{t("首页")}</h1>
      <Suspense fallback={<Skeleton />}>
        <RecentItems />
      </Suspense>
    </main>
  );
}
```

### 7.3 Client Component + TanStack Query

```typescript
"use client";
import { useQuery } from "@tanstack/react-query";

export const RecentItems = () => {
  const { data, isLoading } = useQuery({
    queryKey: ["recent-items"],
    queryFn: () => fetch("/api/recent").then(r => r.json()),
    staleTime: 60_000,        // 1 分钟内不重抓
    refetchOnWindowFocus: false,
  });
  if (isLoading) return <Skeleton />;
  return <DataList items={data} />;
};
```

### 7.4 Form + Server Action

```typescript
// 客户端 form
"use client";
import { useFormState } from "react-dom";
import { createUser } from "./actions";

export const UserForm = () => {
  const [state, action] = useFormState(createUser, { status: "idle" });
  return (
    <form action={action}>
      <input name="name" required />
      <button type="submit" disabled={state.status === "loading"}>
        {state.status === "loading" ? "提交中…" : "创建"}
      </button>
      {state.status === "error" && <ErrorBanner>{state.error}</ErrorBanner>}
    </form>
  );
};
```

### 7.5 ThemeProvider（项目自实现）

`components/theme-provider.tsx`：

```typescript
"use client";
import { createContext, useContext, useEffect, useState } from "react";

type Theme = "light" | "dark" | "system";
const ThemeContext = createContext<{ theme: Theme; setTheme: (t: Theme) => void } | null>(null);

export const ThemeProvider = ({ children }: { children: React.ReactNode }) => {
  const [theme, setTheme] = useState<Theme>("system");
  useEffect(() => {
    // FOUC 防护：客户端 hydration 前注入 script
    const saved = localStorage.getItem("theme") as Theme | null;
    if (saved) setTheme(saved);
  }, []);
  return <ThemeContext.Provider value={{ theme, setTheme }}>{children}</ThemeContext.Provider>;
};
```

---

## 八、项目没用到的能力 / 进阶方向

以下 React 19 能力项目当前未充分使用（**待评估**）：

| 能力 | 用途 | 集成建议 |
|------|------|----------|
| **`<Form>` 元素** | 浏览器级 form + 自动 reset | 项目用 react-hook-form + Server Actions 替代 |
| **`useActionState`** | 表单 + Action 状态机 | 同上 |
| **`useOptimistic`** | 乐观更新 | LLM 流式响应可考虑 |
| **`<Activity>` 元素** | 离屏缓存 UI 状态 | 多 Tab 切换场景 |
| **`<ViewTransition>`** | 视图过渡动画 | 增强 UX |
| **`use()` 读取 Promise** | 条件分支里 await | 项目用 TanStack Query 替代 |
| **Suspense for data fetching** | 流式 SSR | Next.js 16 已默认开启 |

**建议关注**：`useOptimistic` 适合 LLM 流式聊天回复场景（先显"已发送"再等真实响应）。

---

## 九、最佳实践 & 常见坑

### 项目风格指南（项目 CLAUDE.md 强制）

1. **函数声明用 const**：`const Component = () => {}`，禁止 `function Component(){}`（default export 例外）
2. **变量名禁止单字符**：`val` 替代 `v`，`idx` 替代 `i`
3. **禁止魔法数字**：用常量替代
4. **import 按字母排序**（oxlint sort-imports 规则）
5. **JSX 不写行内 `onClick={() => {}}` 复杂表达式**，提取命名函数
6. **优先用项目封装**：`DataTable` / `AppDialog` / `AppConfirm` / `ErrorBanner` 等
7. **优先使用已安装的库**：TanStack Query / zustand / react-use / es-toolkit / date-fns 等，不重复造轮子

### React 性能优化

1. **`memo` 包裹大组件**：避免不必要重渲染
2. **`useMemo` 缓存计算**：昂贵计算（如过滤大数据集）
3. **`useCallback` 缓存函数引用**：传给 memo 子组件
4. **不要滥用 Context**：频繁变化的 state 放进 Context 会让所有消费者重渲染
5. **列表用稳定 key**：`key={item.id}` 而不是 `key={idx}`

### 常见坑

1. **直接修改 state**：`state.value = 1` 不会重渲染，必须 `setState({...})`
2. **依赖数组漏填**：useEffect / useMemo 依赖没填全，eslint 报警
3. **闭包陷阱**：useEffect 拿到的 state 是创建时的快照，需要 ref 模式
4. **`<form onSubmit>` 不阻止默认行为**：会刷新页面，必须 `e.preventDefault()`
5. **Server Component 用了 `useState`**：报 "useState is not a function"，加 `"use client"`
6. **Strict Mode 双调用 effect**：React 19 dev 模式故意双跑，依赖清理函数要幂等
7. **状态提升过高**：兄弟组件共用 state 提到最近共同父组件即可，不要直接放根 layout

---

## 📚 参考

- [React 官方文档](https://react.dev/)
- [React 19 release notes](https://react.dev/blog/2024/12/05/react-19)
- [Thinking in React](https://react.dev/learn/thinking-in-react)
- [Hooks API 参考](https://react.dev/reference/react/hooks)
- [Server Components 原理](https://react.dev/reference/rsc/server-components)
- [项目 web/CLAUDE.md](../../packages/web/CLAUDE.md)

---

**状态：** ✅ 已完成

**最后更新：** 2026-06-25
