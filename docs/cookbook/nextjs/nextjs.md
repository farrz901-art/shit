# Next.js 教程

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

Next.js 是 Vercel 维护的 React 全栈框架，集路由（App Router）、服务端渲染（SSR）、静态生成（SSG）、Server Components、Server Actions、API Routes 于一身。

**同类对比：**

| 框架 | 定位 | 本项目选择理由 |
|------|------|----------------|
| **Next.js** | React 全栈框架 | App Router + RSC 性能强，生态最成熟 |
| **Remix** | 路由优先的 React 框架 | 嵌套路由设计优雅，但生态略小 |
| **Astro** | 内容站优先（少 JS） | 内容站 + Island 架构，App 场景弱 |
| **Vite + React Router** | 纯 SPA | 没 SSR 优势，SEO 和首屏慢 |
| **Nuxt** | Vue 全栈框架 | 团队用 React，不选 |

**Next.js 解决的核心问题**：
- **路由**：文件系统路由（`app/page.tsx` = `/`）
- **渲染策略**：Server Component（默认）+ Client Component（按需 `"use client"`）
- **数据获取**：RSC 端直接 await，零客户端 fetch
- **后端集成**：API Routes、Server Actions、middleware

---

## 二、安装 & 开发环境

### 2.1 版本要求

- Node.js ≥ 22.x（Next.js 16 要求）
- Bun ≥ 1.x（项目用 bun 作为包管理器）

### 2.2 包管理

项目用 bun：

```bash
cd packages/web
bun install
```

### 2.3 开发工具链

- **类型检查**：`bun run typecheck`（`tsc --noEmit`，必须 0 error）
- **Lint**：`bun run lint`（`oxlint`，极快）
- **Format**：`bun run format`（`oxfmt --write`）
- **测试**：`bun run test`（vitest + jsdom）
- **E2E**：`bun run test:e2e`（Playwright）

---

## 三、基础语法 & 类型系统

### 3.1 App Router 文件系统

```typescript
// app/[locale]/page.tsx → 路由 /:locale
export default function Home() {
  return <main>Hello</main>;
}

// app/[locale]/admin/users/page.tsx → /:locale/admin/users
```

### 3.2 Server Component（默认）

无 `"use client"` 指令的组件在服务端渲染，可以直接 await 数据库：

```typescript
// app/users/page.tsx (RSC)
import { db } from "@/lib/db";

export default async function UsersPage() {
  const users = await db.user.findMany();  // 服务端 await
  return <UserList users={users} />;
}
```

### 3.3 Client Component

需要交互（`useState`、`useEffect`、事件处理器）时加 `"use client"`：

```typescript
"use client";
import { useState } from "react";

export function Counter() {
  const [count, setCount] = useState(0);
  return <button onClick={() => setCount(c => c + 1)}>{count}</button>;
}
```

### 3.4 动态路由参数

```typescript
// app/posts/[id]/page.tsx
export default async function PostPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;  // Next 15+ params 是 Promise
  return <Post id={id} />;
}
```

### 3.5 中间件

`app/middleware.ts`（项目根目录）：

```typescript
import { NextResponse, type NextRequest } from "next/server";
import createMiddleware from "next-intl/middleware";

export async function middleware(request: NextRequest) {
  // intl 中间件处理 locale 前缀
  return createMiddleware(routing)(request);
}

export const config = {
  matcher: ["/((?!api|_next|.*\\..*).*)"],
};
```

---

## 四、核心概念

### 4.1 路由（App Router）

文件系统路由，`app/` 下的文件夹就是 URL 段：

```
app/
  [locale]/
    page.tsx              → /:locale
    admin/
      users/
        page.tsx          → /:locale/admin/users
        [id]/
          page.tsx        → /:locale/admin/users/:id
    api/
      revalidate/route.ts → /:locale/api/revalidate
  layout.tsx              → 根 layout
  global-error.tsx        → 错误边界
```

### 4.2 Server Component / Client Component

- **Server Component**（默认）：无状态，async，安全（API keys 不泄露）
- **Client Component**（`"use client"`）：浏览器运行，可交互
- 二者通过 props 序列化传递数据

### 4.3 数据获取

- RSC 内直接 `await fetch()` / `await db.query()`，无 useEffect
- 自动 dedupe 同一请求
- 可用 `cache()` / `unstable_cache` 做进程内缓存

### 4.4 Server Actions

服务端函数，被客户端组件调用，自动序列化：

```typescript
"use server";
export async function createUser(formData: FormData) {
  await db.user.create({ data: { name: formData.get("name") } });
  revalidatePath("/users");
}
```

### 4.5 Middleware

在请求到达 page 前运行。用途：locale 路由、auth 检查、redirect。

### 4.6 Layout

`app/layout.tsx` 是根 layout，包裹所有页面。`app/[locale]/layout.tsx` 是 locale 维度 layout。

---

## 五、常用命令 & 工具链

```bash
cd packages/web

# 开发
bun run dev            # localhost:3000
# 自动 kill 占用进程（Windows: Get-Process node | Stop-Process）

# 构建
bun run build          # 生产构建
bun run start          # 跑生产构建

# 类型检查 / Lint / Format
bun run typecheck      # tsc --noEmit
bun run lint           # oxlint
bun run lint:fix       # 自动修
bun run format         # oxfmt --write
bun run format:check   # 只检查

# 测试
bun run test           # vitest
bun run test:watch     # 监听模式
bun run test:coverage  # 覆盖率报告
bun run test:e2e       # Playwright E2E
```

---

## 六、项目集成点

### 6.1 项目结构

```
packages/web/
├── app/                       # App Router
│   ├── [locale]/              # locale 段（zh/en）
│   │   ├── page.tsx           # 首页
│   │   ├── admin/             # 后台
│   │   ├── chat/              # 聊天
│   │   ├── knowledge/         # 知识图谱
│   │   └── layout.tsx         # locale layout
│   ├── _actions/              # Server Actions
│   ├── api/                   # BFF API Routes
│   ├── global-error.tsx
│   ├── globals.css
│   ├── middleware.ts          # 根中间件（intl）
│   └── middleware.test.ts
├── components/                # 共享组件
├── lib/                       # 业务库
├── i18n/                      # 国际化配置
├── messages/                  # i18n 文案
├── vitest.config.ts
├── playwright.config.ts
└── package.json
```

### 6.2 关键依赖

| 依赖 | 版本 | 用途 |
|------|------|------|
| `next` | ^16.2.9 | 主框架 |
| `react` | ^19.2.7 | UI 库 |
| `next-intl` | ^4.13.0 | 国际化 |
| `@tanstack/react-query` | ^5.101.0 | 客户端数据获取 |
| `@tanstack/react-form` | ^1.33.0 | 表单 |
| `@tanstack/react-table` | ^8.21.3 | 表格 |
| `zustand` | ^5.0.14 | 全局状态 |
| `react-dropzone` | ^15.0.0 | 文件拖拽 |

### 6.3 BFF 模式

`app/api/*` 路径是 BFF（Backend for Frontend），转发请求到 FastAPI：

```typescript
// app/api/users/route.ts
export async function GET(request: Request) {
  const res = await fetch(`${process.env.BACKEND_URL}/api/admin/users`, {
    headers: {
      cookie: request.headers.get("cookie") ?? "",
    },
  });
  return res.json();
}
```

---

## 七、项目代码示例

### 7.1 Locale 路由与中间件

`app/middleware.ts` 用 next-intl 中间件强制带 `/zh` / `/en` 前缀：

```typescript
import createMiddleware from "next-intl/middleware";
import { routing } from "@/i18n/routing";

export default createMiddleware(routing);

export const config = {
  matcher: ["/((?!api|_next|.*\\..*).*)"],
};
```

### 7.2 国际化 Provider

`app/[locale]/layout.tsx` 嵌套 ThemeProvider + I18nProvider（项目 `packages/web/CLAUDE.md` 强制）：

```typescript
// app/[locale]/layout.tsx
import { NextIntlClientProvider } from "next-intl";
import { getMessages } from "next-intl/server";
import { ThemeProvider } from "@/components/theme-provider";

export default async function LocaleLayout({ children, params }: {...}) {
  const { locale } = await params;
  const messages = await getMessages();
  return (
    <html lang={locale} suppressHydrationWarning>
      <body>
        <ThemeProvider>
          <NextIntlClientProvider messages={messages}>
            {children}
          </NextIntlClientProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
```

### 7.3 Server Component 数据获取

```typescript
// app/[locale]/knowledge/page.tsx (RSC, 服务端 await)
import { getTranslations } from "next-intl/server";
import { fetchBackend } from "@/lib/api/server";

export default async function KnowledgePage() {
  const t = await getTranslations();
  const data = await fetchBackend("/api/kg/triples");
  return <TripleList data={data} title={t("知识图谱")} />;
}
```

### 7.4 Client Component 用 React Query

```typescript
"use client";
import { useQuery } from "@tanstack/react-query";
import { fetchFrontend } from "@/lib/api/client";

export function UserList() {
  const { data, isLoading } = useQuery({
    queryKey: ["users"],
    queryFn: () => fetchFrontend("/api/users"),
  });
  if (isLoading) return <Skeleton />;
  return <ul>{data?.map(u => <li key={u.id}>{u.name}</li>)}</ul>;
}
```

### 7.5 next.config.ts 配置

`packages/web/next.config.ts` 启用 standalone 模式（用于 Docker 部署）：

```typescript
const nextConfig: NextConfig = {
  output: "standalone",  // 生成自包含的 Node 服务
  experimental: {
    typedRoutes: true,   // 路由类型安全
  },
  // ... 其他配置
};
```

---

## 八、项目没用到的能力 / 进阶方向

以下 Next.js 能力项目当前未使用（**待评估**）：

| 能力 | 用途 | 集成建议 |
|------|------|----------|
| **Server Actions** | 服务端函数替代 API Routes | 项目用 BFF API Routes 风格，Server Actions 更现代 |
| **PPR（Partial Prerendering）** | 静态外壳 + 动态片段混合渲染 | 16.x 默认开启，可评估效果 |
| **Server Components HMR Cache** | 加快开发热更新 | 默认开启 |
| **Turbopack** | Rust 写的 bundler，比 webpack 快 10x | 16.x 已默认 Turbopack |
| **Parallel Routes** | 同 URL 多 slot 渲染 | 复杂 dashboard 场景用 |
| **Intercepting Routes** | 模态弹框 URL 同步 | 项目用 shadcn Dialog 已够 |
| **Edge Runtime** | 在边缘节点跑（Vercel） | 本项目自部署用不上 |
| **Vercel Deployment** | 一键部署到 Vercel | 项目用 Docker 自部署 |

**建议关注**：Server Actions 替换部分 API Routes，减少客户端 fetch 逻辑。

---

## 九、最佳实践 & 常见坑

### 项目风格指南（项目 CLAUDE.md 强制）

1. **函数声明用 const**：`const Component = () => {}`，禁止 `function Component(){}`（React 组件 default export 例外）
2. **变量名禁止单字符**：`val` 替代 `v`，`idx` 替代 `i`
3. **禁止魔法数字**：用 `const/index.ts` 定义命名常量
4. **import 按字母排序**（oxlint sort-imports 规则）
5. **JSX 不写行内 `onClick={() => {}}` 复杂表达式**，提取命名函数
6. **i18n key 用中文**：`t("中文 key")`，zh.json identity，en.json 翻译
7. **路由跳转用 `@/i18n/navigation` 的 useRouter**，禁止 `next/navigation`（强制 locale 前缀）
8. **优先用项目封装**：`DataTable` / `AppDialog` / `AppConfirm` / `ErrorBanner` / `CopyButton` / `AppTooltip` / `Form` / `FormField`

### 常见坑

1. **dev 模式改 messages/\*.json 不 HMR**：next-intl cache 翻译，报 `IntlError: MISSING_MESSAGE` 时**不是代码 bug**，先 `Ctrl+C` 停 `bun run dev` + 重新 `bun run dev` + 浏览器 hard refresh（`Ctrl+Shift+R`）
2. **useRouter 用了 `next/navigation`**：跳到 `/foo` 被 middleware 307 重定向到 `/zh/foo`，多一跳。必须用 `@/i18n/navigation`
3. **Turbopack PostCSS 报错**：dev infra 偶尔抓不到某些改动，重启 dev 即好
4. **params 是 Promise**（Next 15+）：`{ params: { id } }` 改成 `await params`
5. **Server Component 误用 Client API**：`useState` / `useEffect` 在 RSC 里用 → 编译报 `"use client"` 错
6. **next-themes + React 19 报警**：项目用自实现 `ThemeProvider`（`components/theme-provider.tsx`），不用 next-themes
7. **Standalone 模式漏掉 .next/static**：Dockerfile 必须显式 COPY `packages/web/Dockerfile:51`

---

## 📚 参考

- [Next.js 官方文档](https://nextjs.org/docs)
- [Next.js 16 release notes](https://nextjs.org/blog)
- [App Router 深入](https://nextjs.org/docs/app)
- [Server Components 原理](https://nextjs.org/docs/app/building-your-application/rendering/server-components)
- [next-intl 4.x 文档](https://next-intl.dev/)
- [TanStack Query 5.x](https://tanstack.com/query/latest)
- [项目 web/CLAUDE.md](../../packages/web/CLAUDE.md)

---

**状态：** ✅ 已完成

**最后更新：** 2026-06-25
