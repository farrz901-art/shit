# tRPC 教程

> 📅 创建日期：2026-06-28
> 📁 项目代码引用：本教程以 `c:/doc/Code/rag` 仓库当前代码为准，所有引用标注 `file_path:line_number`
> 🏷️ 类别：A-AI 库（API 层类别参考，写作仍按 A 模板 9 节结构）
> 🎯 读者：中高级 TS 工程师，需要在 Next.js 全栈项目里选 API 通信方案、了解 tRPC 的取舍

---

## 目录

- [一、是什么 & 解决什么问题](#一是什么--解决什么问题)
- [二、安装 & 初始化](#二安装--初始化)
- [三、核心概念 & 抽象](#三核心概念--抽象)
- [四、常用 API & 命令速查](#四常用-api--命令速查)
- [五、项目集成点](#五项目集成点)
- [六、项目代码示例](#六项目代码示例)
- [七、项目没用到的能力](#七项目没用到的能力)
- [八、评测 & 调优技巧](#八评测--调优技巧)
- [九、最佳实践 & 常见坑](#九最佳实践--常见坑)

---

## 一、是什么 & 解决什么问题

tRPC（TypeScript Remote Procedure Call）是一个**无 schema、无 codegen** 的端到端类型安全 RPC 框架。它让前端直接调后端的 TS 函数，输入输出类型自动同步——后端改 procedure 的入参，前端编译期就报错。零运行时类型校验成本。

**同类对比：**

| 方案 | 定位 | 本项目选择理由 |
|------|------|----------------|
| **tRPC** | 端到端类型安全 RPC | 前后端同 TS 单仓库时 DX 最强，零 codegen |
| **REST + Zod** | 开放 API + 运行时校验 | 跨语言通用，但每次改 schema 都要同步两处类型 |
| **GraphQL (Apollo/Pothos)** | schema-first + resolver | 类型安全 + 查询灵活，但学习曲线 + N+1 调优成本 |
| **gRPC** | Protobuf 强 schema + HTTP/2 | 多语言 RPC 最强，但 web 生态弱，需要 grpc-web |
| **REST + OpenAPI Generator** | 自动生成 client | 类型能保证，但 OpenAPI schema 维护成本高 |

**tRPC 解决的核心问题**：
- **端到端类型推断**：后端 `procedure.input(z.object({id: z.string()})).query(...)`，前端 `trpc.user.getById.useQuery({id})`，TS 自动对齐
- **零 schema 双写**：不用维护 OpenAPI / GraphQL SDL，改后端 = 改类型
- **类本地函数调用**：`trpc.user.getById.query({id})` vs `apiFetch('/api/users/' + id)`
- **自动 batching**：同 tick 多个 query 自动合并成 1 个 HTTP 请求
- **中间件链路**：auth / logging / rate-limit 一行代码插

**不适用的场景**：
- 后端是另一种语言（Python / Go / Java）—— 类型无法共享
- 对外开放 API（公开给第三方）—— OpenAPI / GraphQL 更合适
- 移动端 / 第三方 client —— 不希望耦合内部 TS 类型

---

## 二、安装 & 初始化

### 2.1 安装

```bash
# 全栈 Next.js (App Router) 模式
bun add @trpc/server @trpc/client @trpc/react-query @trpc/next
# 配套
bun add @tanstack/react-query zod superjson
```

### 2.2 后端初始化 (`app/api/trpc/[trpc]/route.ts`)

```typescript
import { fetchRequestHandler } from "@trpc/server/adapters/fetch";
import { appRouter } from "@/server/routers";

const handler = (req: Request) =>
  fetchRequestHandler({
    endpoint: "/api/trpc",
    req,
    router: appRouter,
    createContext: () => ({}),
  });

export { handler as GET, handler as POST };
```

### 2.3 客户端初始化 (`app/_trpc/Provider.tsx`)

```tsx
"use client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { httpBatchLink } from "@trpc/client";
import { createTRPCReact } from "@trpc/react-query";
import superjson from "superjson";
import { useState } from "react";

import { AppRouter } from "@/server/routers/root";

export const trpc = createTRPCReact<AppRouter>();

export const TRPCProvider = ({ children }: { children: React.ReactNode }) => {
  const [queryClient] = useState(() => new QueryClient());
  const [trpcClient] = useState(() =>
    trpc.createClient({
      links: [httpBatchLink({ url: "/api/trpc", transformer: superjson })],
    }),
  );

  return (
    <trpc.Provider client={trpcClient} queryClient={queryClient}>
      <QueryClientProvider client={queryClient}>
        {children}
      </QueryClientProvider>
    </trpc.Provider>
  );
};
```

### 2.4 env 变量

| 变量 | 必填 | 说明 |
|------|------|------|
| `DATABASE_URL` | 后端用时必填 | 后端 DB 连接串 |
| `AUTH_SECRET` | 加 middleware 时必填 | JWT / session 密钥 |
| `NODE_ENV` | ✅ | `production` 关掉 query devtools |

---

## 三、核心概念 & 抽象

### 3.1 Router (后端)

```typescript
// server/routers/user.ts
import { z } from "zod";
import { router, publicProcedure, protectedProcedure } from "../trpc";

export const userRouter = router({
  getById: publicProcedure
    .input(z.object({ id: z.string().uuid() }))
    .query(async ({ ctx, input }) => {
      return ctx.db.user.findUnique({ where: { id: input.id } });
    }),

  list: publicProcedure
    .input(z.object({ limit: z.number().min(1).max(100).default(20) }))
    .query(async ({ ctx, input }) => {
      return ctx.db.user.findMany({ take: input.limit });
    }),

  create: protectedProcedure
    .input(z.object({ email: z.string().email(), name: z.string() }))
    .mutation(async ({ ctx, input }) => {
      return ctx.db.user.create({ data: input });
    }),

  delete: protectedProcedure
    .input(z.object({ id: z.string().uuid() }))
    .mutation(async ({ ctx, input }) => {
      await ctx.db.user.delete({ where: { id: input.id } });
      return { ok: true };
    }),
});
```

### 3.2 AppRouter 组合

```typescript
// server/routers/root.ts
import { router } from "../trpc";
import { userRouter } from "./user";
import { postRouter } from "./post";

export const appRouter = router({
  user: userRouter,
  post: postRouter,
});

export type AppRouter = typeof appRouter;  // 客户端 import 这个类型
```

### 3.3 Procedure 类型

| 类型 | HTTP 动词 | 用法 |
|------|-----------|------|
| `query` | GET | 读操作，可缓存 |
| `mutation` | POST/PUT/DELETE | 写操作 |
| `subscription` | WS / SSE | 实时推送 |

### 3.4 Procedure 鉴权层级

```typescript
// server/trpc.ts
import { initTRPC, TRPCError } from "@trpc/server";

const t = initTRPC.context<Context>().create();

export const router = t.router;
export const middleware = t.middleware;

// 公开 procedure — 任何人都能调
export const publicProcedure = t.procedure;

// 鉴权 middleware — 检查登录
const authMiddleware = t.middleware(async ({ ctx, next }) => {
  if (!ctx.session) throw new TRPCError({ code: "UNAUTHORIZED" });
  return next({ ctx: { ...ctx, user: ctx.session.user } });
});

// 登录后才能调
export const protectedProcedure = t.procedure.use(authMiddleware);

// 进一步限定角色
const adminMiddleware = t.middleware(async ({ ctx, next }) => {
  if (ctx.user.role !== "admin") throw new TRPCError({ code: "FORBIDDEN" });
  return next({ ctx });
});

export const adminProcedure = protectedProcedure.use(adminMiddleware);
```

### 3.5 Client 调用

```tsx
"use client";

// Query
const { data, isLoading, error } = trpc.user.getById.useQuery({ id });
const { data: users } = trpc.user.list.useQuery({ limit: 50 });

// Mutation
const create = trpc.user.create.useMutation({
  onSuccess: () => trpc.user.list.invalidate(),
});
create.mutate({ email: "x@y.z", name: "X" });

// Server-side 直调 (RSC + Server Action)
import { createCaller } from "@/server/routers";
const caller = createCaller({ session: req.session });
const user = await caller.user.getById({ id });
```

---

## 四、常用 API & 命令速查

### 4.1 标准错误码

```typescript
throw new TRPCError({
  code: "BAD_REQUEST",        // 400
  code: "UNAUTHORIZED",       // 401
  code: "FORBIDDEN",          // 403
  code: "NOT_FOUND",          // 404
  code: "CONFLICT",           // 409
  code: "INTERNAL_SERVER_ERROR", // 500
  message: "用户不存在",
});
```

### 4.2 superjson (Date / Map / BigInt 序列化)

```typescript
// 服务端
links: [httpBatchLink({ url, transformer: superjson })]

// 默认 JSON.stringify 丢 Date 类型 → 变 string
// superjson 保留 Date / Map / Set / BigInt / undefined
```

### 4.3 React Query 集成（tRPC 内部用 TanStack Query）

```tsx
// Query 带 options
const { data } = trpc.user.getById.useQuery(
  { id },
  {
    staleTime: 60_000,        // 1 min 内不重 fetch
    refetchOnWindowFocus: false,
    enabled: !!id,             // 条件触发
  },
);

// 乐观更新
const utils = trpc.useUtils();
const update = trpc.user.update.useMutation({
  onMutate: async (newData) => {
    await utils.user.getById.cancel();
    const prev = utils.user.getById.getData({ id });
    utils.user.getById.setData({ id }, newData);
    return { prev };
  },
  onError: (err, vars, ctx) => {
    utils.user.getById.setData({ id }, ctx?.prev);
  },
});
```

### 4.4 Middleware

```typescript
// 日志 middleware
const loggerMiddleware = t.middleware(async ({ path, type, next }) => {
  const start = Date.now();
  const result = await next();
  console.log(`[${type}] ${path} took ${Date.now() - start}ms`);
  return result;
});

// 速率限制 middleware
const rateLimitMiddleware = t.middleware(async ({ ctx, next }) => {
  const key = `rate:${ctx.ip}`;
  const count = await redis.incr(key);
  if (count > 100) throw new TRPCError({ code: "TOO_MANY_REQUESTS" });
  if (count === 1) await redis.expire(key, 60);
  return next();
});
```

### 4.5 Server-Side 直调 (RSC 友好)

```typescript
// server/trpc-server.ts
import { appRouter } from "./routers";

export const createServerCaller = (ctx: Context) => appRouter.createCaller(ctx);

// RSC 页面
import { createServerCaller } from "@/server/trpc-server";

export default async function Page() {
  const caller = createServerCaller({ session: null });
  const user = await caller.user.getById({ id: "..." });
  // 类型完整, 不用走 HTTP
}
```

---

## 五、项目集成点

本项目**未使用 tRPC**。架构是：
- 后端 Python FastAPI ([`packages/service/`](../../packages/service/))
- 前端 BFF (Next.js API Routes) [`packages/web/app/api/`](../../packages/web/app/api/)
- 通信协议：`fetch` + `apiFetch` ([`packages/web/lib/api/fetcher.ts`](../../packages/web/lib/api/fetcher.ts))
- 类型校验：后端 Pydantic + 前端 Zod ([`docs/cookbook/nextjs/zod.md](./zod.md))

**为什么不引 tRPC**：后端 Python 是 TS 异构语言，tRPC 端到端类型优势不存在。前端走 BFF + Zod 已经够用，BFF 充当翻译层（Pydantic → Zod schema）。

**潜在集成点（理论上）**：
- 若项目后端改为 Node TS（不太可能）—— 全栈 TS，tRPC 立刻是首选
- 若项目前端想跳 BFF 直接调后端 —— 反向代理 + OpenAPI codegen 是更通用的选择
- 若项目加独立 Node TS 微服务（AI agent worker 等）—— 服务间互调 tRPC 优于 REST

---

## 六、项目代码示例

项目仓库内**没有任何 tRPC 调用代码**。下面给出"如果本项目要引入 tRPC"的样例路径（伪代码，无现成代码可引用）：

**项目类似位置的对应代码**：

- 前端 `apiFetch` 封装：[`packages/web/lib/api/fetcher.ts`](../../packages/web/lib/api/fetcher.ts) — 类似 tRPC client 的角色
- 前端 TanStack Query hooks：[`packages/web/lib/api/`](../../packages/web/lib/api/) — 已用 Query，跟 tRPC 集成模式天然兼容
- 后端 schema 真值源：[`packages/service/src/storage/models/`](../../packages/service/src/storage/models/) — SQLAlchemy 模型（项目不会改成 tRPC，但结构对应 tRPC router 的 procedure 入参 schema）

**伪代码样例**（基于上述模式，本项目若引入）：

```typescript
// packages/web/server/trpc.ts — tRPC init
import { initTRPC } from "@trpc/server";

const t = initTRPC.create();

export const router = t.router;
export const publicProcedure = t.procedure;
```

```typescript
// packages/web/server/routers/user.ts
import { z } from "zod";
import { router, publicProcedure } from "../trpc";

// 注: 实际不会查本地 DB, 而是 fetch 后端 Python API
const backendFetch = (path: string) => fetch(`${process.env.BACKEND_URL}${path}`).then(r => r.json());

export const userRouter = router({
  getById: publicProcedure
    .input(z.object({ id: z.string() }))
    .query(async ({ input }) => backendFetch(`/api/admin/users/${input.id}`)),
});
```

> 📌 **架构提示**：伪代码里 procedure 内部仍是 fetch Python 后端——这相当于"BFF 的 BFF"，多一层。只有当后端迁 TS Node 时，procedure 才能直接拿 ctx.db 操作。

---

## 七、项目没用到的能力

### 7.1 Subscription (WebSocket / SSE)

```typescript
// 后端
export const chatRouter = router({
  onMessage: publicProcedure
    .input(z.object({ roomId: z.string() }))
    .subscription(async function* ({ input }) {
      while (true) {
        const msg = await getNextMessage(input.roomId);
        yield msg;
      }
    }),
});

// 前端
const { data } = trpc.chat.onMessage.useSubscription({ roomId });
```

项目聊天走 SSE ([`docs/superpowers/specs/2026-06-15-chat-sse-refactor-design.md`](../../superpowers/specs/2026-06-15-chat-sse-refactor-design.md))，没引 tRPC subscription。

### 7.2 Router Merging / Namespacing

```typescript
// 大项目拆 sub-router, 各自维护
// server/routers/admin/index.ts
export const adminRouter = router({
  user: userAdminRouter,
  permission: permissionAdminRouter,
});

// server/routers/root.ts
export const appRouter = router({
  admin: adminRouter,
  public: publicRouter,
});
```

### 7.3 React Query DevTools 集成

```tsx
import { ReactQueryDevtools } from "@tanstack/react-query-devtools";

<TRPCProvider>
  <QueryClientProvider client={queryClient}>
    {children}
    <ReactQueryDevtools initialIsOpen={false} />
  </QueryClientProvider>
</TRPCProvider>
```

### 7.4 DataLoader / 自动 batching (Dataloader 模式)

```typescript
// 同 tick 多个 query 自动合并
// 例: useQuery({a}) + useQuery({b}) + useQuery({c}) → 1 个 batch HTTP 请求
// 默认开启 (httpBatchLink), 单次 batch 最大 10 个 query
```

### 7.5 Error formatter (统一错误格式)

```typescript
t.initTRPC.create({
  errorFormatter({ shape, error }) {
    return {
      ...shape,
      data: {
        code: error.code,
        message: error.message,
        // 加 zod 错误详情
        zodError: error.cause instanceof ZodError ? error.cause.flatten() : null,
      },
    };
  },
});
```

---

## 八、评测 & 调优技巧

### 8.1 Batch link 配置

```typescript
httpBatchLink({
  url: "/api/trpc",
  maxURLLength: 2083,        // 超过这长度自动拆请求
  transformer: superjson,
});
```

### 8.2 Streaming (Server-Sent Events)

```typescript
// 服务端 (Node fetch adapter)
const handler = (req: Request) =>
  fetchRequestHandler({
    endpoint: "/api/trpc",
    req,
    router: appRouter,
    onError({ error, path }) {
      console.error(`tRPC error on ${path}: ${error.message}`);
    },
    createContext: () => ({}),
    responseMeta() {
      return { headers: { "cache-control": "no-store" } };
    },
  });
```

### 8.3 Query 缓存策略

```tsx
// 全局默认
const [queryClient] = useState(() => new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 60_000,            // 1 min
      gcTime: 5 * 60_000,          // 5 min
      refetchOnWindowFocus: false,  // 项目默认 false
    },
  },
}));

// 单 query 覆盖
trpc.user.list.useQuery({ limit: 50 }, { staleTime: 5 * 60_000 });
```

### 8.4 大对象返回分页

```typescript
// ❌ 错: 全量返回 10MB 列表
list: publicProcedure.query(() => db.user.findMany()),

// ✅ 对: cursor 分页
list: publicProcedure
  .input(z.object({ cursor: z.string().optional(), limit: z.number().default(20) }))
  .query(async ({ input }) => db.user.findMany({
    cursor: input.cursor ? { id: input.cursor } : undefined,
    take: input.limit + 1,  // 多取 1 个判断 hasMore
  })),
```

### 8.5 监控

```typescript
// 用 OpenTelemetry 自动埋点
import { trace } from "@opentelemetry/api";

const tracer = trace.getTracer("trpc");

const tracerMiddleware = t.middleware(async ({ path, type, next }) => {
  return tracer.startActiveSpan(`trpc.${type}.${path}`, async (span) => {
    const result = await next();
    span.end();
    return result;
  });
});
```

---

## 九、最佳实践 & 常见坑

### 9.1 procedure input 必填 zod schema

```typescript
// ❌ 错: 无 input, 客户端可任意调用
hello: publicProcedure.query(() => "world"),

// ✅ 对: 即便无参也声明 (强制空对象)
hello: publicProcedure
  .input(z.object({}).strict())
  .query(() => "world"),
```

### 9.2 不要在 procedure 里 catch 错

```typescript
// ❌ 错: 把 TRPCError 吞了, 客户端拿到 unclear 错
query: async ({ input }) => {
  try { return await db.user.findUnique(...); }
  catch (e) { return null; }
},

// ✅ 对: 让 TRPCError 自动冒泡
query: async ({ input }) => {
  const user = await db.user.findUnique(...);
  if (!user) throw new TRPCError({ code: "NOT_FOUND" });
  return user;
},
```

### 9.3 RSC + Server Action vs tRPC

| 场景 | 推荐 |
|------|------|
| 表单提交 + 跳转 | Server Action (`"use server"`) |
| RSC 页面 server-side fetch | tRPC Server-Side Caller |
| 客户端 query | tRPC React Query |
| 跨服务调用 | tRPC HTTP |
| 后端不是 TS | 不要 tRPC, 走 REST/OpenAPI |

项目当前是 Python 后端 + Next.js BFF，**Server Action 调用 BFF 的 fetch 是最自然的**，引 tRPC 反而割裂。

### 9.4 类型 cross-package 共享

```typescript
// server/routers/root.ts
export type AppRouter = typeof appRouter;

// 前端 (另一个 package)
import type { AppRouter } from "@myapp/server/routers";
// 必须用 monorepo (pnpm workspace / turborepo) 才能跨包 import TS 类型
```

项目后端 Python，AppRouter 类型无法给 Python 用，tRPC 优势无法落地。

### 9.5 version 兼容

- tRPC v10 → v11 是大版本升级 (改用 transformer, fetch adapter 默认, 移除 superjson 默认开启)
- React Query v4 → v5 tRPC 适配也跟着升级
- TanStack Query v5 + tRPC v11 是当前组合，本项目若引就锁这俩版本

### 9.6 不要把 tRPC 当 REST 公开

tRPC 类型是内部协议，公开 API 仍走 REST/OpenAPI/GraphQL（schema-first）更通用。tRPC 调客户端 = 你的 TS 代码。

### 9.7 superjson vs zod 序列化性能

- `superjson` JSON 序列化 + reviver 比 `JSON.parse` 慢 ~3-5x
- 不需要保留 Date/Map 时，省掉 transformer：

```typescript
httpBatchLink({ url: "/api/trpc" })  // 不传 transformer, 纯 JSON
```

---

## 📚 参考

- tRPC 官方文档：<https://trpc.io/docs>
- tRPC + Next.js App Router：<https://trpc.io/docs/client/nextjs>
- TanStack Query (tRPC 底层依赖)：<https://tanstack.com/query/latest>
- superjson：<https://github.com/blitz-js/superjson>
- 类型安全 API 选型对比：<https://trpc.io/docs/comparison>

---

**状态：** 🚧 部分完成（项目未引入 tRPC，第五/六节写"集成点 + 伪代码"，第七节列未用能力）