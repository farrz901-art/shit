# Tailwind CSS 4 教程

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

Tailwind CSS 是一个 utility-first 的 CSS 框架，提供 `flex` / `p-4` / `bg-red-500` 等原子类，让你在 HTML/JSX 直接写样式，不用维护单独的 `.css` 文件。**Tailwind 4**（2025 年发布）用 Rust 写的 Oxide 引擎重写，性能提升 10x，CSS-first 配置，CSS 变量驱动主题。

**同类对比：**

| 库 | 定位 | 本项目选择理由 |
|------|------|----------------|
| **Tailwind 4** | Utility-first CSS | 本项目**主力**（`tailwindcss: ^4.3.1`） |
| **CSS Modules** | 组件级 CSS | 样板代码多 |
| **styled-components** | CSS-in-JS | 运行时性能损失 |
| **Emotion** | CSS-in-JS | 类似 styled-components |
| **UnoCSS** | 类 Tailwind 替代 | 新项目，性能更好但生态小 |
| **Vanilla CSS** | 原生 | 大量自定义样式 |

**Tailwind 解决的核心问题**：
- **原子类**：不用想 className，写 `flex p-4` 即可
- **设计系统**：内置 spacing / color / typography 规范
- **零 CSS 文件**：全在 JSX 里
- **主题切换**：CSS 变量驱动，light/dark 一键切
- **按需生成**：只打包用到的类，体积小

---

## 二、安装 & 开发环境

### 2.1 安装

```bash
# 项目已装 (package.json)
"tailwindcss": "^4.3.1",
"@tailwindcss/postcss": "^4.3.1",
"@tailwindcss/typography": "^0.5.20",
"tailwind-merge": "^3.6.0",
"class-variance-authority": "^0.7.1",
"clsx": "^2.1.1",
```

### 2.2 PostCSS 配置

`postcss.config.mjs`：

```javascript
export default {
  plugins: {
    "@tailwindcss/postcss": {},  // Tailwind 4 PostCSS 插件
  },
};
```

### 2.3 CSS 入口

`app/globals.css`：

```css
@import "tailwindcss";

@theme {
  --color-primary: oklch(0.5 0.2 250);
  /* 自定义主题变量 */
}
```

---

## 三、基础语法 & 类型系统

### 3.1 布局

```tsx
<div className="flex flex-col gap-4 p-6">
  <div className="grid grid-cols-3 gap-2">
    <div className="col-span-2">左 2/3</div>
    <div className="col-span-1">右 1/3</div>
  </div>
</div>
```

### 3.2 间距

```
p-4       padding: 1rem
px-6      padding-x: 1.5rem
py-2      padding-y: 0.5rem
m-2       margin: 0.5rem
mx-auto   margin-x: auto
mt-8      margin-top: 2rem
```

### 3.3 颜色

```
bg-blue-500        background
text-red-600       color
border-gray-200    border-color
ring-indigo-300    ring-color (focus)
```

Tailwind 4 用 `oklch` 色彩空间：

```
bg-blue-50  →  bg-blue-100  →  ...  →  bg-blue-950
最浅         浅          中    深     最深
```

### 3.4 文字

```
text-sm         0.875rem
text-base       1rem
text-lg         1.125rem
text-2xl        1.5rem
font-bold       font-weight: 700
italic
underline
truncate        overflow: hidden; text-overflow: ellipsis; white-space: nowrap
```

### 3.5 响应式

```
sm:    @media (min-width: 640px)
md:    @media (min-width: 768px)
lg:    @media (min-width: 1024px)
xl:    @media (min-width: 1280px)
2xl:   @media (min-width: 1536px)

<div className="p-2 md:p-6 lg:p-8">
```

### 3.6 状态

```
hover:bg-blue-700   悬停
focus:ring-2        焦点
disabled:opacity-50 禁用
active:scale-95     按下
group-hover:visible 父 hover
peer-checked:bg-red 兄弟元素
```

### 3.7 暗色模式

```tsx
<div className="bg-white text-black dark:bg-gray-900 dark:text-white">
```

启用方式：

```css
/* globals.css */
@custom-variant dark (&:where(.dark, .dark *));
```

### 3.8 cn() 工具函数

```typescript
// lib/utils.ts (项目)
import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

// 使用
<button className={cn("p-2", isActive && "bg-blue-500", className)} />
```

---

## 四、核心概念

### 4.1 Utility-first

每个类直接对应一个 CSS 属性。`p-4` = `padding: 1rem`。不用想"我应该建一个叫 card 的 class"。

### 4.2 原子 + 组合

```tsx
// ❌ 不用建 .css class
.card { padding: 1rem; background: white; border-radius: 0.5rem; }

// ✅ 写 utility
<div className="p-4 bg-white rounded-lg">
```

### 4.3 设计系统 token

Tailwind 4 用 CSS 变量定义主题：

```css
@theme {
  --color-primary: oklch(0.5 0.2 250);
  --spacing-4: 1rem;
  --font-family-sans: "Inter", system-ui, sans-serif;
}
```

### 4.4 响应式 + 状态

`sm:md:lg:` 断点 + `hover:focus:active:` 状态，组合成 `md:hover:bg-blue-700`。

### 4.5 Dark Mode

`dark:` 前缀。配置用 `@custom-variant dark`。

### 4.6 配置文件

`tailwind.config.js`（v4 可选，主要用 `@theme` in CSS）：

```javascript
export default {
  content: ["./app/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        primary: "oklch(0.5 0.2 250)",
      },
    },
  },
};
```

v4 直接在 `globals.css` 写 `@theme`。

---

## 五、常用命令 & 工具链

```bash
# 项目命令
bun run format          # oxfmt --write
bun run lint            # oxlint
bun run typecheck       # tsc --noEmit

# Tailwind 调试
# 看生成的 CSS 大小
ls .next/static/css/

# Intellisense（VS Code）
# Tailwind CSS IntelliSense 插件
```

---

## 六、项目集成点

### 6.1 项目**主力** CSS 方案

`packages/web/package.json`：

```json
"tailwindcss": "^4.3.1",
"@tailwindcss/postcss": "^4.3.1",
"@tailwindcss/typography": "^0.5.20",
```

### 6.2 项目集成

- `postcss.config.mjs` 用 `@tailwindcss/postcss`
- `app/globals.css` import `tailwindcss`
- 全项目 utility-first + shadcn/ui 组件（也是 Tailwind）

### 6.3 项目主题系统

项目 `web/CLAUDE.md` §主题系统：

- 自实现 ThemeProvider（不用 next-themes）
- 主题配置：`web/lib/theme/themes.ts`（light/dark + set of CSS variables）
- 状态色：`bg-status-{success|warning|error|running}/10`
- 项目特有色：`--color-ochre` / `--color-indigo`

### 6.4 shadcn/ui 集成

shadcn/ui 默认 Tailwind 4，所有组件类都是 utility：

```tsx
<Button variant="destructive" size="sm">删除</Button>
// 实际渲染: <button class="bg-destructive text-destructive-foreground ...">
```

---

## 七、项目代码示例

### 7.1 业务组件

```tsx
"use client";
import { cn } from "@/lib/utils";

type CardProps = {
  title: string;
  variant?: "default" | "danger";
  className?: string;
  children: React.ReactNode;
};

export const Card = ({ title, variant = "default", className, children }: CardProps) => (
  <div className={cn(
    "rounded-lg border bg-white p-6 shadow-sm dark:bg-gray-900 dark:border-gray-800",
    variant === "danger" && "border-red-500 bg-red-50 dark:bg-red-950/30",
    className,
  )}>
    <h3 className="text-lg font-semibold mb-2">{title}</h3>
    {children}
  </div>
);
```

### 7.2 响应式布局

```tsx
// 移动端单列，桌面三列
<div className="grid grid-cols-1 md:grid-cols-3 gap-4 p-4 md:p-8">
  {items.map(item => (
    <Card key={item.id} title={item.name}>{item.description}</Card>
  ))}
</div>
```

### 7.3 Dark mode

```tsx
<div className="bg-white dark:bg-gray-900 text-gray-900 dark:text-gray-100">
  <p className="text-muted-foreground">次要文字</p>
  <Button variant="default">Primary</Button>
</div>
```

### 7.4 项目状态色（自定义 token）

```tsx
// 项目 web/lib/theme/themes.ts 定义
// --color-status-success / warning / error / running

<span className="bg-status-success/10 text-status-success px-2 py-1 rounded">
  成功
</span>
<span className="bg-status-error/10 text-status-error px-2 py-1 rounded">
  失败
</span>
```

### 7.5 hover / focus 状态

```tsx
<button className={cn(
  "px-4 py-2 rounded bg-blue-500 text-white",
  "hover:bg-blue-600 transition-colors",
  "focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2",
  "disabled:opacity-50 disabled:cursor-not-allowed",
)}>
```

### 7.6 动画

```tsx
// Tailwind 4 内置动画
<div className="animate-pulse">加载中...</div>
<div className="animate-spin h-4 w-4 border-2 border-blue-500 border-t-transparent rounded-full" />

// 自定义动画（globals.css）
@keyframes shimmer {
  0% { background-position: -200% 0; }
  100% { background-position: 200% 0; }
}

.animate-shimmer {
  background: linear-gradient(90deg, transparent, rgba(255,255,255,0.2), transparent);
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
}
```

### 7.7 排版（@tailwindcss/typography）

```tsx
<article className="prose prose-slate dark:prose-invert max-w-none">
  <h1>标题</h1>
  <p>正文...</p>
  <ul>
    <li>列表项</li>
  </ul>
</article>
```

### 7.8 cn() 处理条件类

```tsx
import { cn } from "@/lib/utils";

<button className={cn(
  "px-4 py-2 rounded font-medium",
  isPrimary && "bg-blue-500 text-white",
  isDanger && "bg-red-500 text-white",
  !isPrimary && !isDanger && "bg-gray-200 text-gray-900",
  disabled && "opacity-50 cursor-not-allowed",
)} />
```

---

## 八、项目没用到的能力 / 进阶方向

以下 Tailwind 4 能力项目当前未充分使用（**待评估**）：

| 能力 | 用途 | 集成建议 |
|------|------|----------|
| **CSS Variables 主题** | `@theme {}` | 项目已用 |
| **`@layer`** | 显式层级 | 复杂组件 |
| **`@apply`** | CSS 中复用 utility | 抽公共样式 |
| **Custom Plugin** | 自定义 utility | 业务特定 |
| **Container Queries** | 组件级响应式 | 卡片布局 |
| **`@tailwindcss/typography`** | 文章排版 | Markdown 渲染 |
| **`@tailwindcss/forms`** | 表单元素统一 | 表单项目 |
| **`@tailwindcss/aspect-ratio`** | 宽高比 | 视频 / 图片 |
| **`@tailwindcss/container-queries`** | 容器查询 | 项目未用 |
| **Tailwind Studio** | 商业 UI 编辑器 | 大团队 |

**建议关注**：Container Queries（`@container`）让组件自适应父容器宽度，比媒体查询更灵活。

---

## 九、最佳实践 & 常见坑

### 项目风格指南（项目 web/CLAUDE.md 强制）

1. **状态色用 `bg-status-*`**：替代 `bg-emerald-100`
2. **i18n 文案不写在 className 里**（动态文案走 t() 函数）
3. **优先用项目封装**（shadcn `<Button>` / `<Card>` 等已带样式）
4. **优先使用已安装的库**（Tailwind + clsx + cva + tailwind-merge）

### 最佳实践

1. **utility 优先于 @apply**：

```tsx
// ✅ 写 utility
<div className="p-4 bg-white rounded-lg">

// ❌ 别建 class
<div className="card">
```

2. **cn() 处理条件类**：

```typescript
className={cn("base", condition && "extra", className)}
```

3. **避免魔法值**：

```tsx
// ❌ 错
<div className="p-[13px] mt-[7px]">

// ✅ 用 theme token
<div className="p-3 mt-2">
```

4. **响应式 + 状态组合**：

```tsx
<button className="bg-blue-500 hover:bg-blue-600 active:bg-blue-700 disabled:opacity-50 md:bg-green-500">
```

5. **Dark mode 配套**：

```tsx
// 任何颜色都要配 dark: 变体
<div className="bg-white dark:bg-gray-900 text-black dark:text-white">
```

6. **复杂的 CSS 用 @layer**：

```css
@layer components {
  .card { @apply p-4 bg-white rounded-lg shadow; }
}
```

### 常见坑

1. **类名顺序问题**：

```tsx
// 重复属性，后写的覆盖先写的
className="p-2 p-4"  // 实际是 p-4

// cn() + tailwind-merge 会去重
cn("p-2", "p-4")  // → "p-4"
```

2. **响应式断点写反**：

```tsx
// ❌ 错：移动端 6 间距，桌面 2 间距
<div className="p-6 md:p-2">

// ✅ 对：移动端小，桌面大（一般情况）
<div className="p-2 md:p-6">
```

3. **group / peer 用错**：

```tsx
// ❌ 错：group 在子元素
<button className="group-hover:bg-blue-500">...</button>

// ✅ 对：group 在父，group-hover 在子
<div className="group">
  <button className="group-hover:bg-blue-500">...</button>
</div>
```

4. **动态 className 不被 PurgeCSS 扫描**：

```tsx
// ❌ 错：动态拼类名，Tailwind 不知道
<div className={`text-${color}-500`}>

// ✅ 对：完整类名
<div className={color === 'red' ? 'text-red-500' : 'text-blue-500'}>

// 或用 safelist
// tailwind.config.js
safelist: ['text-red-500', 'text-blue-500']
```

5. **Dark mode 没生效**：

```css
/* globals.css 缺这行 */
@custom-variant dark (&:where(.dark, .dark *));
```

6. **Tailwind 3 → 4 breaking**：

- `darkMode: 'class'` 在 `tailwind.config.js` → 在 CSS 用 `@custom-variant dark`
- `@tailwind base` 改成 `@import "tailwindcss"`
- `theme.extend.colors` 改成 `@theme { --color-xxx: ... }`
- 配置文件从 `tailwind.config.js` 移到 CSS

7. **PostCSS 没生效**：

```javascript
// postcss.config.mjs
export default {
  plugins: {
    "@tailwindcss/postcss": {},  // 必须用 @tailwindcss/postcss
  },
};
```

8. **类名拼写错不生效**：`text-bule-500`（bule 不是 blue），Tailwind 不报错但类无效

9. **`@apply` 在 v4 限制**：必须在 `@layer` 内用

---

## 📚 参考

- [Tailwind CSS 官方文档](https://tailwindcss.com/docs)
- [Tailwind CSS 4 升级指南](https://tailwindcss.com/docs/upgrade-guide)
- [shadcn/ui 集成 Tailwind](https://ui.shadcn.com/docs/installation)
- [@tailwindcss/typography](https://github.com/tailwindlabs/tailwindcss-typography)
- [class-variance-authority](https://cva.style/docs)
- [tailwind-merge](https://github.com/dcastil/tailwind-merge)
- [项目 web/CLAUDE.md §样式约定](../../packages/web/CLAUDE.md)

---

**状态：** ✅ 已完成

**最后更新：** 2026-06-25