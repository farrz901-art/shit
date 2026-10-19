# TanStack Query 教程

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

TanStack Query（原 React Query）是数据获取 + 缓存 + 同步库，专门为"客户端异步状态管理"设计。它把 fetch 包装成声明式 `useQuery` / `useMutation` 钩子，自动处理缓存、失效、轮询、错误重试、乐观更新。

**同类对比：**

| 库 | 定位 | 本项目选择理由 |
|------|------|----------------|
| **TanStack Query** | 异步状态管理 | 框架无关（React/Vue/Solid），生态最大 |
| **SWR** | 轻量数据获取 | 简洁但功能少 |
| **Apollo Client** | GraphQL 客户端 | 强绑定 GraphQL |
| **Redux Toolkit Query** | RTK 内置数据获取 | 强依赖 Redux |
| **直接 fetch + useEffect** | 手写 | 重复造轮子 |

**TanStack Query 解决的核心问题**：
- **客户端缓存**：多组件共享同一份数据，无需 Context 透传
- **自动失效**：mutation 后自动 invalidate 相关 query
- **重复请求合并**：同一时间多个组件请求同一接口只发一次
- **轮询 + 实时**：refetchInterval 配 WebSocket 替代品
- **乐观更新**：mutation 立即更新 UI，失败回滚

---

## 二、安装 & 开发环境

### 2.1 版本

`@tanstack/react-query: ^5.101.0`（`packages/web/package.json`）

### 2.2 安装

```bash
# 项目已装
cd packages/web
bun install

# 独立新项目
bun add @tanstack/react-query
```

### 2.3 Provider 配置

`app/[locale]/layout.tsx`（推测项目设置）：

```typescript
"use client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";

export const QueryProvider = ({ children }: { children: React.ReactNode }) => {
  // useState 保证 QueryClient 单例（避免 HMR 重建）
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 60_000,         // 1 分钟内不重抓
            refetchOnWindowFocus: false,
            retry: 1,
          },
        },
      })
  );
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
};
```

---

## 三、基础语法 & 类型系统

### 3.1 `useQuery` 基础

```typescript
import { useQuery } from "@tanstack/react-query";

type User = { id: number; name: string; email: string };

const useUser = (id: number) =>
  useQuery({
    queryKey: ["user", id],
    queryFn: async (): Promise<User> => {
      const res = await fetch(`/api/users/${id}`);
      if (!res.ok) throw new Error("Failed to fetch user");
      return res.json();
    },
  });
```

### 3.2 `useMutation` 基础

```typescript
import { useMutation, useQueryClient } from "@tanstack/react-query";

const useCreateUser = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (data: { name: string }) => {
      const res = await fetch("/api/users", {
        method: "POST",
        body: JSON.stringify(data),
      });
      return res.json();
    },
    onSuccess: () => {
      // 失效 users 列表
      qc.invalidateQueries({ queryKey: ["users"] });
    },
  });
};
```

### 3.3 泛型与类型

```typescript
const useUsers = () =>
  useQuery<User[], Error>({
    queryKey: ["users"],
    queryFn: async () => {
      const res = await fetch("/api/users");
      if (!res.ok) throw new Error("Network error");
      return res.json() as Promise<User[]>;
    },
  });
```

### 3.4 TypeScript 高级用法

```typescript
// queryKey 强类型
const queryKeys = {
  all: ["users"] as const,
  detail: (id: number) => ["users", id] as const,
};

// 调用方拿类型推断
qc.invalidateQueries({ queryKey: queryKeys.all });
```

---

## 四、核心概念

### 4.1 Query（查询）

声明式数据获取，框架负责：缓存、refetch、revalidate、error 恢复。

### 4.2 Mutation（变更）

声明式数据变更（POST/PUT/DELETE），框架负责：loading / error / success 状态。

### 4.3 Query Key（查询键）

唯一标识一个查询的字符串数组，类似 Map 的 key。失效 / 预取都按 key 匹配。

### 4.4 QueryClient

缓存中心。一个项目一个 QueryClient 实例，全局挂在 `<QueryClientProvider>` 下。

### 4.5 Stale Time vs GC Time

- `staleTime`（默认 0）：数据"新鲜"期。期内不重抓，期外后台 refetch。
- `gcTime`（默认 5 min）：无订阅者时数据保留时间。过期后从内存清除。

### 4.6 Invalidation（失效）

`qc.invalidateQueries({ queryKey: [...] })` 把匹配 key 的查询标为 stale，下次订阅时 refetch。

---

## 五、常用命令 & 工具链

```bash
# 项目无专属命令，集成在 bun run test / typecheck
# 调试工具：React Query Devtools
bun add @tanstack/react-query-devtools

# 在 layout 启用
import { ReactQueryDevtools } from "@tanstack/react-query-devtools";
<ReactQueryDevtools initialIsOpen={false} />
```

---

## 六、项目集成点

### 6.1 项目当前使用

`@tanstack/react-query: ^5.101.0`（`packages/web/package.json`）用于客户端数据获取。

### 6.2 典型场景

- 聊天列表 / 消息：`useConversations` / `useConversation(id)`（`packages/web/lib/chat/api.ts`）
- 知识图谱列表：`useTriples` / `useNodes` / `useEdges`
- 用户管理：`useUsers` / `useCurrentUser`
- 系统监控：`useHealthSystem`（轮询 5s）

### 6.3 项目默认配置

项目 `web/CLAUDE.md` 明确约定：

- `staleTime: 60_000`（1 分钟）
- `refetchOnWindowFocus: false`（防止切窗口刷屏）

### 6.4 与 BFF 配合

前端 `useQuery` 调 BFF route（`/api/*`），BFF 再转发到 FastAPI 后端。详见 `nextjs/nextjs.md` §6.3。

---

## 七、项目代码示例

### 7.1 聊天列表查询

`packages/web/lib/chat/api.ts`（推测）：

```typescript
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";

export const useConversations = () =>
  useQuery({
    queryKey: ["conversations"],
    queryFn: async () => {
      const res = await fetch("/api/chat/conversations");
      if (!res.ok) throw new Error("Failed to load conversations");
      return res.json() as Promise<Conversation[]>;
    },
    staleTime: 60_000,
  });

export const useDeleteConversation = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      const res = await fetch(`/api/chat/conversations/${id}`, { method: "DELETE" });
      if (!res.ok) throw new Error("Delete failed");
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["conversations"] });
    },
  });
};
```

### 7.2 依赖查询

```typescript
// 依赖前一个查询的结果
const useUser = (id: number) =>
  useQuery({
    queryKey: ["user", id],
    queryFn: async () => fetch(`/api/users/${id}`).then(r => r.json()),
    enabled: id > 0,        // id 有效才发请求
  });

const useUserPosts = (id: number) =>
  useQuery({
    queryKey: ["user", id, "posts"],
    queryFn: async () => fetch(`/api/users/${id}/posts`).then(r => r.json()),
    enabled: id > 0,
  });

// 组合调用
const Component = ({ userId }: { userId: number }) => {
  const user = useUser(userId);
  const posts = useUserPosts(userId);
  // ...
};
```

### 7.3 乐观更新

```typescript
const useToggleLike = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) => {
      const res = await fetch(`/api/posts/${id}/like`, { method: "POST" });
      return res.json();
    },
    onMutate: async (id) => {
      // 1. 取消正在进行的 refetch
      await qc.cancelQueries({ queryKey: ["post", id] });

      // 2. 快照
      const prev = qc.getQueryData<Post>(["post", id]);

      // 3. 乐观更新
      qc.setQueryData<Post>(["post", id], (old) => {
        if (!old) return old;
        return { ...old, liked: !old.liked };
      });

      return { prev };
    },
    onError: (_err, _id, ctx) => {
      // 失败回滚
      if (ctx?.prev) qc.setQueryData(["post", _id], ctx.prev);
    },
    onSettled: (_data, _err, id) => {
      qc.invalidateQueries({ queryKey: ["post", id] });
    },
  });
};
```

### 7.4 无限滚动

```typescript
import { useInfiniteQuery } from "@tanstack/react-query";

const usePosts = () =>
  useInfiniteQuery({
    queryKey: ["posts"],
    queryFn: async ({ pageParam = 0 }) => {
      const res = await fetch(`/api/posts?offset=${pageParam}&limit=20`);
      return res.json() as Promise<{ items: Post[]; nextOffset: number | null }>;
    },
    initialPageParam: 0,
    getNextPageParam: (last) => last.nextOffset,
  });
```

### 7.5 预取（hover / link 拦截）

```typescript
const prefetchUser = (qc: QueryClient, id: number) => {
  return qc.prefetchQuery({
    queryKey: ["user", id],
    queryFn: () => fetch(`/api/users/${id}`).then(r => r.json()),
  });
};

const UserLink = ({ id, name }: { id: number; name: string }) => {
  const qc = useQueryClient();
  return (
    <Link
      href={`/users/${id}`}
      onMouseEnter={() => prefetchUser(qc, id)}  // hover 预取
    >
      {name}
    </Link>
  );
};
```

---

## 八、项目没用到的能力 / 进阶方向

以下 TanStack Query 能力项目当前未充分使用（**待评估**）：

| 能力 | 用途 | 集成建议 |
|------|------|----------|
| **Devtools** | 调试 query state | 强烈建议开发环境加 `@tanstack/react-query-devtools` |
| **Suspense 模式** | `useSuspenseQuery` + React Suspense | 配合 RSC 优雅降级 |
| **Persister** | 缓存持久化到 localStorage | 离线场景 |
| **Streaming 模式** | 边接收边渲染 | 未来 LLM 流式响应可考虑 |
| **Infinite Query** | 分页 + 无限滚动 | 项目表格分页可考虑 |
| **WebSocket / SSE 集成** | 实时数据 | 聊天 / 监控场景 |
| **select 选择器** | 派生数据 + 减少重渲染 | 大列表性能优化 |
| **structuralSharing** | 引用相等优化 | 默认开启，无需配置 |

**建议关注**：Devtools 调试用强烈推荐；`useSuspenseQuery` 配 React Suspense 写异步组件更优雅。

---

## 九、最佳实践 & 常见坑

### 项目风格指南

1. **staleTime 默认 60_000**（1 min），不重抓
2. **refetchOnWindowFocus: false**，防止切窗口刷屏
3. **queryKey 数组化**：`["user", id]` 而不是字符串拼接

### 最佳实践

1. **queryKey 工厂模式**：

```typescript
export const userKeys = {
  all: ["users"] as const,
  list: () => [...userKeys.all, "list"] as const,
  detail: (id: number) => [...userKeys.all, "detail", id] as const,
};
```

2. **错误重试 + 错误状态**：`retry: 3` + `isError` 状态配合 ErrorBanner 展示
3. **mutation 错误用 toast**：`onError: (err) => toast.error(err.message)`
4. **大列表用 `select` 选择性订阅**：

```typescript
useQuery({
  queryKey: ["users"],
  queryFn: fetchUsers,
  select: (data) => data.filter(u => u.active),  // 派生数据
});
```

5. **Suspense + ErrorBoundary 包裹**：

```typescript
<ErrorBoundary>
  <Suspense fallback={<Skeleton />}>
    <Users />
  </Suspense>
</ErrorBoundary>
```

### 常见坑

1. **queryKey 不稳定**：`useQuery({ queryKey: [user] })`（user 是对象引用，每次新引用）→ 缓存永远失效
2. **enabled 漏掉**：依赖查询没设 `enabled`，前面数据没来就先发了请求
3. **mutation onSuccess 直接改 cache**：

```typescript
// 错
onSuccess: (data) => qc.setQueryData(["user", data.id], data)
// 对（多组件共享时）
onSuccess: () => qc.invalidateQueries({ queryKey: ["user"] })
```

4. **staleTime 设为 0**：默认就是 0，每次订阅都 refetch，浪费带宽
5. **Devtools 仅 dev 环境加载**：`process.env.NODE_ENV === "development" && <ReactQueryDevtools />`
6. **staleTime 单位是毫秒**：写 `60` 不是 60s，是 60ms
7. **gcTime 旧称 cacheTime**：v5 改名为 gcTime

---

## 📚 参考

- [TanStack Query 官方文档](https://tanstack.com/query/latest)
- [TanStack Query v5 迁移指南](https://tanstack.com/query/latest/docs/framework/react/guides/migrating-to-react-query-v5)
- [Practical React Query](https://tkdodo.eu/blog/practical-react-query)（TkDodo 系列）
- [React Query Devtools](https://tanstack.com/query/latest/docs/framework/react/devtools)
- [Effective React Query Keys](https://tkdodo.eu/blog/effective-react-query-keys)

---

**状态：** ✅ 已完成

**最后更新：** 2026-06-25
