# shadcn/ui 教程

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

shadcn/ui 不是传统的组件库，而是一套**可复制粘贴的组件代码**（Radix UI + Tailwind CSS + 项目内封装）。它的特点是：组件代码在你仓库里，100% 可改，没有 vendor lock-in。

**同类对比：**

| 库                    | 定位                   | 本项目选择理由              |
| --------------------- | ---------------------- | --------------------------- |
| **shadcn/ui**         | 复制粘贴式组件         | 100% 可定制，无版本升级痛苦 |
| **Material UI (MUI)** | Google Material Design | 风格固定，定制难            |
| **Ant Design**        | 企业级组件库           | 体积大，风格偏国内 B 端     |
| **Chakra UI**         | CSS-in-JS 主题化       | 性能不及 Tailwind 4         |
| **Mantine**           | 现代 React 组件        | 生态略小                    |

**shadcn/ui 解决的核心问题**：
- **可定制**：组件代码在你项目里，要改就改
- **依赖最小**：只引 Radix UI（无样式底层）+ Tailwind（原子化 CSS）
- **主题灵活**：CSS 变量驱动 light/dark，跟 Tailwind 集成
- **TypeScript 优先**：所有组件有完整类型
- **现代化**：用 React 19 的 `forwardRef` + `asChild` 模式

---

## 二、安装 & 开发环境

### 2.1 初始化（已配项目）

```bash
# 项目已装
cd packages/web

# 装一个组件
bunx shadcn@latest add button

# 装一批组件
bunx shadcn@latest add button card dialog dropdown-menu
```

会自动：
1. 装 Radix UI 依赖
2. 创建 `components/ui/button.tsx` 等
3. 装 `class-variance-authority` / `clsx` / `tailwind-merge` 工具

### 2.2 项目依赖

`packages/web/package.json`：

```json
"class-variance-authority": "^0.7.1",  // cva: 变体管理
"clsx": "^2.1.1",                       // clsx: 条件 className
"tailwind-merge": "^3.6.0",             // 合并去重 Tailwind 类
"lucide-react": "^1.21.0",              // 图标库
"@radix-ui/react-*":                    // 各种 Radix 原语
```

### 2.3 工具函数

`lib/utils.ts`（项目）：

```typescript
import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
```

---

## 三、基础语法 & 类型系统

### 3.1 Button 组件示例

`components/ui/button.tsx`（项目）：

```typescript
import { cva, type VariantProps } from "class-variance-authority";
import { Slot } from "@radix-ui/react-slot";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50",
  {
    variants: {
      variant: {
        default: "bg-primary text-primary-foreground shadow hover:bg-primary/90",
        destructive: "bg-destructive text-destructive-foreground shadow-sm hover:bg-destructive/90",
        outline: "border border-input bg-background shadow-sm hover:bg-accent",
        secondary: "bg-secondary text-secondary-foreground shadow-sm hover:bg-secondary/80",
        ghost: "hover:bg-accent hover:text-accent-foreground",
        link: "text-primary underline-offset-4 hover:underline",
      },
      size: {
        default: "h-9 px-4 py-2",
        sm: "h-8 rounded-md px-3 text-xs",
        lg: "h-10 rounded-md px-8",
        icon: "h-9 w-9",
      },
    },
    defaultVariants: { variant: "default", size: "default" },
  }
);

interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button";
    return <Comp className={cn(buttonVariants({ variant, size, className }))} ref={ref} {...props} />;
  }
);
Button.displayName = "Button";

export { Button, buttonVariants };
```

### 3.2 使用

```typescript
import { Button } from "@/components/ui/button";

<Button variant="default" size="default">提交</Button>
<Button variant="destructive">删除</Button>
<Button variant="ghost" size="icon"><Icon /></Button>
```

### 3.3 `asChild` 模式

shadcn 组件常用 `asChild`，把样式套到任意子元素上：

```typescript
import { Link } from "@/i18n/navigation";

<Button asChild>
  <Link href="/dashboard">去后台</Link>
</Button>
// 渲染为 <a> 带 button 样式
```

---

## 四、核心概念

### 4.1 Radix UI（无样式底层）

shadcn 基于 Radix UI 的 primitives，Radix 提供：
- 键盘可访问性（a11y）
- 焦点管理
- Portal 渲染（弹框到 body 末尾）
- ARIA 属性

但 Radix **完全没样式**，把样式自由留给上层。

### 4.2 CVA（Class Variance Authority）

```typescript
import { cva } from "class-variance-authority";

const button = cva("base-classes", {
  variants: { variant: { primary: "...", secondary: "..." }, size: { sm: "...", md: "..." } },
  defaultVariants: { variant: "primary", size: "md" },
  compoundVariants: [
    { variant: "primary", size: "lg", class: "..." },
  ],
});
```

替代 if-else 拼 className，类型安全。

### 4.3 cn() 工具

`lib/utils.ts` 的 `cn` 函数：

```typescript
cn("p-4", condition && "bg-red-500", className)
```

合并 + Tailwind 类去重（`twMerge`）。

### 4.4 CSS 变量主题

`app/globals.css`：

```css
@layer base {
  :root {
    --background: 0 0% 100%;
    --foreground: 222.2 47.4% 11.2%;
    --primary: 222.2 47.4% 11.2%;
    /* ... */
  }
  .dark {
    --background: 222.2 84% 4.9%;
    /* ... */
  }
}
```

Tailwind config 用 `hsl(var(--primary))` 引用，主题切换只改 CSS 变量。

### 4.5 项目主题系统

项目 `components/theme-provider.tsx` 自实现 ThemeProvider（不用 `next-themes`），

参考 [`packages/web/CLAUDE.md §主题系统`](../../packages/web/CLAUDE.md)。

```typescript
"use client";
import { createContext, useContext, useEffect, useState } from "react";

type Theme = "light" | "dark" | "system";
const ThemeContext = createContext<...>(null);

export const ThemeProvider = ({ children }) => {
  const [theme, setTheme] = useState<Theme>("system");
  useEffect(() => {
    // FOUC 防护
    const saved = localStorage.getItem("theme") as Theme | null;
    if (saved) setTheme(saved);
  }, []);
  // 同步 class 到 <html>
  useEffect(() => {
    document.documentElement.classList.toggle("dark", theme === "dark");
  }, [theme]);
  return <ThemeContext.Provider value={{ theme, setTheme }}>{children}</ThemeContext.Provider>;
};
```

---

## 五、常用命令 & 工具链

```bash
# 添加组件
bunx shadcn@latest add button

# 批量添加
bunx shadcn@latest add button card dialog dropdown-menu sheet tabs

# 升级组件（手动重装，shadcn 是源码）
bunx shadcn@latest add button --overwrite

# 搜索可用组件
bunx shadcn@latest search

# 项目格式化
bun run format         # oxfmt --write
```

### 项目 vs shadcn 默认主题

项目用了 **Default + Slate** 主题（shadcn 初始化时选择），CSS 变量在 `app/globals.css`。

---

## 六、项目集成点

### 6.1 项目封装（项目 CLAUDE.md 强制）

项目把 shadcn 原生组件 + 业务包装成 `<AppXxx>`，强制使用：

| 封装组件                | 替换的 shadcn 原生 | 用途                           |
| ----------------------- | ------------------ | ------------------------------ |
| `<DataTable<T>>`        | `<Table>`          | 表格 + 排序 + 分页 + loading   |
| `<AppDialog>`           | `<Dialog>`         | 弹框（避免手写 fixed overlay） |
| `<AppConfirm>`          | `<AlertDialog>`    | 危险操作二次确认               |
| `<AppDrawer>`           | `<Sheet>`          | 抽屉                           |
| `<Form>` / `<FormItem>` | `<form>`           | 表单（项目自有 + Zod）         |
| `<FileDropzone>`        | 自定义             | 文件拖拽                       |
| `<DataEmpty>`           | `<Empty>`          | 空态                           |
| `<AppSelect>`           | `<Select>`         | antd 风格 1 行调用             |
| `<AppToggle>`           | `<ToggleGroup>`    | 视图切换按钮组                 |
| `<ErrorBanner>`         | `<Alert>`          | 错误提示                       |
| `<CopyButton>`          | 自定义             | 复制 + 反馈                    |
| `<AppTooltip>`          | `<Tooltip>`        | Tooltip（4 子件）              |
| `<FormField>`           | 自定义             | Label + 错误展示               |

### 6.2 项目 Theme

项目 `web/CLAUDE.md` §主题系统：
- 用自实现 ThemeProvider，不用 next-themes（0.4.6 一年没更新，React 19 报警）
- 主题切换：齿轮按钮 → SettingsDialog
- 状态色：`bg-status-{success|warning|error|running}/10` 替代 `bg-{emerald|amber|rose|blue}-100`

### 6.3 项目 colors

`app/globals.css`：

```css
:root {
  --color-status-success: 142 71% 45%;   /* 绿色 */
  --color-status-warning: 38 92% 50%;    /* 橙色 */
  --color-status-error: 0 84% 60%;       /* 红色 */
  --color-status-running: 199 89% 48%;   /* 蓝色 */
  --color-ochre: 30 50% 50%;             /* 赭石（项目特有）*/
  --color-indigo: 240 60% 50%;
}
```

---

## 七、项目代码示例

### 7.1 业务封装：DataTable

`components/common/data-table/data-table.tsx`（项目风格）：

```typescript
"use client";
import { ColumnDef } from "@tanstack/react-table";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { DataEmpty } from "@/components/common/DataEmpty";
import { cn } from "@/lib/utils";

type DataTableProps<T> = {
  dataSource: T[];
  columns: ColumnDef<T>[];
  rowKey: keyof T;
  emptyText?: React.ReactNode;
  loading?: boolean;
  onRowClick?: (row: T) => void;
};

export const DataTable = <T,>({ dataSource, columns, rowKey, emptyText, loading, onRowClick }: DataTableProps<T>) => {
  if (loading) return <Skeleton className="h-32" />;
  if (dataSource.length === 0) return <>{emptyText ?? <DataEmpty />}</>;

  return (
    <Table>
      <TableHeader>
        {columns.map(c => <TableHead key={c.id as string}>{c.header as string}</TableHead>)}
      </TableHeader>
      <TableBody>
        {dataSource.map(row => (
          <TableRow key={String(row[rowKey])} onClick={() => onRowClick?.(row)}>
            {columns.map(c => <TableCell key={c.id as string}>{c.cell?.(row) ?? String(row[c.id as keyof T])}</TableCell>)}
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
};
```

### 7.2 业务封装：AppDialog

`components/common/dialog/app-dialog.tsx`（项目风格）：

```typescript
"use client";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";

type AppDialogProps = {
  title: string;
  description?: string;
  trigger?: React.ReactNode;
  children: React.ReactNode;
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
};

export const AppDialog = ({ title, description, trigger, children, open, onOpenChange }: AppDialogProps) => (
  <Dialog open={open} onOpenChange={onOpenChange}>
    {trigger && <DialogTrigger asChild>{trigger}</DialogTrigger>}
    <DialogContent>
      <DialogHeader>
        <DialogTitle>{title}</DialogTitle>
        {description && <DialogDescription>{description}</DialogDescription>}
      </DialogHeader>
      {children}
    </DialogContent>
  </Dialog>
);
```

### 7.3 Form + Zod（项目）

```typescript
"use client";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Form, FormField, FormItem, FormLabel, FormControl, FormMessage } from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";

const schema = z.object({
  name: z.string().min(1, "名字必填"),
  email: z.string().email(),
});

type Values = z.infer<typeof schema>;

export const UserForm = ({ onSubmit }: { onSubmit: (v: Values) => void }) => {
  const form = useForm<Values>({ resolver: zodResolver(schema) });
  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
        <FormField
          control={form.control}
          name="name"
          render={({ field }) => (
            <FormItem>
              <FormLabel>名字</FormLabel>
              <FormControl><Input {...field} /></FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
        <Button type="submit" disabled={form.formState.isSubmitting}>
          提交
        </Button>
      </form>
    </Form>
  );
};
```

### 7.4 主题切换按钮

```typescript
"use client";
import { Moon, Sun } from "lucide-react";
import { useTheme } from "@/components/theme-provider";
import { Button } from "@/components/ui/button";

export const ThemeToggle = () => {
  const { theme, setTheme } = useTheme();
  return (
    <Button
      variant="ghost"
      size="icon"
      onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
    >
      <Sun className="h-4 w-4 dark:hidden" />
      <Moon className="h-4 w-4 hidden dark:block" />
    </Button>
  );
};
```

### 7.5 lucide-react 图标

项目用 lucide-react（图标准备 tree-shake friendly 的 React 图标）：

```typescript
import { Trash2, Edit, Plus } from "lucide-react";

<Button><Plus className="h-4 w-4" /> 新建</Button>
<Button variant="destructive"><Trash2 className="h-4 w-4" /> 删除</Button>
```

---

## 八、项目没用到的能力 / 进阶方向

以下 shadcn/ui 能力项目当前未使用（**待评估**）：

| 能力                   | 用途                    | 集成建议                                |
| ---------------------- | ----------------------- | --------------------------------------- |
| **shadcn Charts**      | 基于 Recharts 封装      | 项目已用 recharts（`recharts: ^3.9.0`） |
| **shadcn Blocks**      | 营销页 / Dashboard 模板 | 项目是 B 端，不用                       |
| **shadcn Figma**       | 设计稿转代码            | 暂无 Figma                              |
| **shadcn CLI**         | 自动生成组件变体        | 项目手动管理                            |
| **手风琴 (Accordion)** | FAQ / 长列表折叠        | 项目用 `<Collapsible>` 替代             |
| **Date Picker**        | 日期选择                | 项目用 `react-day-picker`               |
| **Carousel**           | 轮播                    | 项目没轮播需求                          |
| **Command (cmdk)**     | 命令面板                | 项目已装 `cmdk: ^1.1.1`，待集成         |
| **Sonner**             | Toast 通知              | 项目已装 `sonner: ^2.0.7`，待集成       |
| **Resizable**          | 可拖拽分隔              | 后台 dashboard 可用                     |
| **Calendar**           | 日历视图                | 评估排期场景                            |

**建议关注**：Sonner toast 适合"操作完成"反馈，cmdk 适合"快捷命令面板"。

---

## 九、最佳实践 & 常见坑

### 项目风格指南（项目 CLAUDE.md 强制）

1. **优先使用项目封装**（DataTable / AppDialog / AppConfirm / ErrorBanner / CopyButton / AppTooltip / Form / FormField）
2. **shadcn 原生组件直接用**：Input / Textarea / Checkbox / Switch / RadioGroup（项目规则明确"1 行就够，不抽包装"）
3. **业务 enum 走 lookup 字典**（不要硬编 `variant="success"`）
4. **i18n key 用中文**：`t("提交")` 而非 `t("common.submit")`
5. **不要写 `<div className="fixed inset-0 bg-black/50">`**——用 `<AppDialog>`
6. **CSS 变量主题**：`bg-status-success/10` 而非 `bg-emerald-100`

### 最佳实践

1. **图标用 lucide-react**：1000+ 矢量图标，tree-shake 友好
2. **shadcn 升级**：直接 `bunx shadcn@latest add xxx --overwrite` 重装源码
3. **用 `asChild` 把样式套到其他元素**：`<Button asChild><Link>...</Link></Button>`
4. **server-only 组件**：纯 RSC 不需要 `"use client"`，但 shadcn 大多含交互 → 必须 client
5. **TypeScript 类型**：所有组件 prop 都有完整类型，IDE 提示齐全
6. **Portal 自动处理**：弹框 / Tooltip 渲染到 `<body>` 末尾，z-index 不会乱

### 常见坑

1. **shadcn 组件装完没生效**：检查 `components.json` 的 aliases 是否对（`@/components`, `@/lib/utils`）
2. **主题色不生效**：检查 `app/globals.css` 顶部是否 `@tailwind base; @tailwind components; @tailwind utilities;`
3. **shadcn Sheet/Dialog 不可见**：`z-index` 被父级 `overflow: hidden` 切了。shadcn 默认 Portal 到 body，但父容器 `transform` / `filter` 会创建新层叠上下文
4. **lucide-react icon 找不到**：项目用 `bunx shadcn add` 装的组件会自动 import，但手动写可能没装包
5. **`use client` 缺失**：shadcn 组件含 Radix（client only），忘记加 `"use client"` 会报 "useState is not a function"
6. **主题切换闪烁（FOUC）**：用 `useEffect` 在 mount 前注入 script（项目 ThemeProvider 做法），不要在 mount 后才设 className
7. **`asChild` 套错元素**：必须是单一子节点。`<Button asChild><div>1</div><div>2</div></Button>` 报错
8. **Tailwind v3 → v4 升级**：项目用 Tailwind v4（`@tailwindcss/postcss`），新 API 跟 v3 不兼容（`@import "tailwindcss"` 而非 `@tailwind`）

### 项目测试隔离

shadcn 组件测试要 mock Radix（避免 DOM 警告）：

```typescript
vi.mock("@radix-ui/react-dialog", () => ({
  Dialog: ({ children }: any) => <div>{children}</div>,
  DialogContent: ({ children }: any) => <div>{children}</div>,
  // ...
}));
```

---

## 📚 参考

- [shadcn/ui 官方文档](https://ui.shadcn.com/)
- [shadcn/ui 组件列表](https://ui.shadcn.com/docs/components)
- [Radix UI 文档](https://www.radix-ui.com/primitives)
- [Tailwind CSS 4](https://tailwindcss.com/)
- [class-variance-authority](https://cva.style/docs)
- [lucide-react 图标库](https://lucide.dev/)
- [项目 web/CLAUDE.md §封装组件](../../packages/web/CLAUDE.md)

---

**状态：** ✅ 已完成

**最后更新：** 2026-06-25

bunx --bun shadcn@latest add combobox hover-card item marker message message-scroller navigation-menu separator sheet spinner toggle-group bubble