# Drizzle ORM 教程

> 📅 创建日期：2026-06-28
> 📁 项目代码引用：本教程以 `c:/doc/Code/rag` 仓库当前代码为准，所有引用标注 `file_path:line_number`
> 🏷️ 类别：A-AI 库（数据库 ORM 类别参考，写作仍按 A 模板 9 节结构）
> 🎯 读者：中高级 TS 工程师，需要在 Next.js 项目里选型 ORM、跟 RSC 集成、了解 Drizzle 与 Prisma 的取舍

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

Drizzle ORM 是一个 TypeScript 优先、无运行时依赖的 SQL ORM。它把 schema 定义写成 TS 对象，编译期生成强类型，运行时拼 SQL（不引入 ORM 中间抽象层）。**零运行时类型擦除**——Prisma 客户端在编译时丢类型，Drizzle 全程保留。

**同类对比：**

| 库 | 定位 | 本项目选择理由 |
|------|------|----------------|
| **Drizzle ORM** | TS 原生、轻 SQL 抽象 | 类型推断从 schema 到 query 全程不断；无运行时代理开销；RSC/BFF 友好 |
| **Prisma** | 全功能 ORM + GUI + 迁移工具 | 生态最大、DX 好，但运行时生成 client 体积大（~10MB），冷启动慢 |
| **Kysely** | Type-safe query builder | 只有 query，没有 schema/migration；需手写迁移 |
| **Sequelize / TypeORM** | 老牌装饰器风格 ORM | 历史包袱，TS 推断差，社区萎缩 |
| **手写 pg 直连 + raw SQL** | 最大灵活 | 类型全自己维护，开发慢 |

**Drizzle 解决的核心问题**：
- **端到端类型推断**：schema → 表类型 → `select` / `insert` / `where` 全部自动推断，不用写 DTO
- **零运行时代理**：不像 Prisma 那样启动时生成 query engine，部署 cold start 友好（Vercel / Cloudflare 关键）
- **RSC / Edge Runtime 兼容**：完全 serverless 兼容，没有 Node-only 依赖
- **透明 SQL**：生成的 SQL 可以打日志，性能可观测
- **轻量 migration**：drizzle-kit 提供 schema diff → SQL 迁移文件，跟 Alembic 思路一致

---

## 二、安装 & 初始化

### 2.1 安装

```bash
# 主包 (runtime)
bun add drizzle-orm
# 迁移工具 (dev)
bun add -d drizzle-kit
# 驱动 (根据数据库选一个)
bun add pg                # Postgres
bun add postgres          # 同上, 纯 JS 实现, edge 友好
bun add @libsql/client    # SQLite/libSQL/Turso
bun add mysql2            # MySQL
```

### 2.2 drizzle.config.ts

```typescript
import { defineConfig } from "drizzle-kit";

export default defineConfig({
  schema: "./db/schema.ts",
  out: "./db/migrations",
  dialect: "postgresql",            // 或 "mysql" / "sqlite"
  dbCredentials: {
    url: process.env.DATABASE_URL!, // "postgres://user:pass@host:5432/db"
  },
  verbose: true,
  strict: true,
});
```

### 2.3 env 变量

| 变量 | 必填 | 说明 |
|------|------|------|
| `DATABASE_URL` | ✅ | Postgres 连接串（含 `?sslmode=require` 之类） |
| `DATABASE_URL_DIRECT` | 可选 | 跑迁移的直连串（绕过 PgBouncer 事务模式） |
| `NODE_ENV` | ✅ | `production` 时禁用 `console.log` 输出 SQL |

---

## 三、核心概念 & 抽象

### 3.1 schema 定义 (`db/schema.ts`)

```typescript
import { pgTable, uuid, text, timestamp, integer, boolean } from "drizzle-orm/pg-core";

export const users = pgTable("users", {
  id: uuid("id").primaryKey().defaultRandom(),
  email: text("email").notNull().unique(),
  role: text("role").notNull().default("user"),    // 字符串字段
  isActive: boolean("is_active").notNull().default(true),
  createdAt: timestamp("created_at").notNull().defaultNow(),
});

export const posts = pgTable("posts", {
  id: uuid("id").primaryKey().defaultRandom(),
  authorId: uuid("author_id").notNull().references(() => users.id),
  title: text("title").notNull(),
  body: text("body"),
  views: integer("views").notNull().default(0),
});
```

### 3.2 query API

```typescript
import { db } from "./client";
import { users, posts } from "./schema";
import { eq, and, desc, sql } from "drizzle-orm";

// SELECT
const user = await db.select().from(users).where(eq(users.email, "x@y.z"));

// INSERT
const [newUser] = await db.insert(users).values({ email: "a@b.c" }).returning();

// UPDATE
await db.update(users).set({ isActive: false }).where(eq(users.id, id));

// DELETE
await db.delete(users).where(eq(users.id, id));

// JOIN
const result = await db
  .select({ user: users, post: posts })
  .from(posts)
  .innerJoin(users, eq(posts.authorId, users.id))
  .where(eq(users.isActive, true))
  .orderBy(desc(posts.createdAt));
```

### 3.3 transaction

```typescript
await db.transaction(async (tx) => {
  await tx.update(users).set({ isActive: false }).where(eq(users.id, fromId));
  await tx.update(users).set({ isActive: true }).where(eq(users.id, toId));
  // 抛错自动回滚
});
```

### 3.4 推断类型

```typescript
import { InferSelectModel, InferInsertModel } from "drizzle-orm";

export type User = InferSelectModel<typeof users>;      // SELECT 出来的形状
export type NewUser = InferInsertModel<typeof users>;   // INSERT 的入参形状
//   自动带 id / createdAt 为 optional (有 default)
```

---

## 四、常用 API & 命令速查

### 4.1 CLI

```bash
# 生成迁移 SQL (基于 schema 跟 DB 现状 diff)
bunx drizzle-kit generate

# 直接推 schema 到 DB (dev 快速, prod 严禁)
bunx drizzle-kit push

# 跑迁移 (prod 用)
bunx drizzle-kit migrate

# 打开 Drizzle Studio (类 Prisma Studio GUI)
bunx drizzle-kit studio
```

### 4.2 Next.js Server Action 模式

```typescript
"use server";
import { db } from "@/db/client";
import { users } from "@/db/schema";
import { eq } from "drizzle-orm";
import { revalidatePath } from "next/cache";

export const deactivateUser = async (id: string) => {
  await db.update(users).set({ isActive: false }).where(eq(users.id, id));
  revalidatePath("/admin/users");
};
```

### 4.3 RSC 直查模式

```typescript
// app/[locale]/admin/users/page.tsx
import { db } from "@/db/client";
import { users } from "@/db/schema";

export default async function UsersPage() {
  const rows = await db.select().from(users).limit(50);
  return <UsersTable rows={rows} />;
}
```

### 4.4 Edge runtime

```typescript
// app/api/edge/route.ts
import { drizzle } from "drizzle-orm/neon-http";  // 或 @neondatabase/serverless
import { users } from "@/db/schema";

export const runtime = "edge";

const db = drizzle(process.env.DATABASE_URL!);
const result = await db.select().from(users);
```

---

## 五、项目集成点

本项目**当前未使用 Drizzle ORM**。后端 (`packages/service/`) 用 Python FastAPI + SQLAlchemy + Alembic（[docs/cookbook/python/sqlalchemy.md](../python/sqlalchemy.md)），前端 (`packages/web/`) 用 `fetch` + TanStack Query 走 BFF，无任何 TS ORM。

- **BFF 路由**：[`packages/web/app/api/`](../../packages/web/app/api/) — 用 `apiFetch` 调后端，不直连 DB
- **后端 ORM 入口**：[`packages/service/src/db/`](../../packages/service/src/db/) — SQLAlchemy session, Alembic migrations
- **Schema 真值源**：SQLAlchemy model (`packages/service/src/storage/models/`)

**潜在集成点（未来若前端想直接 query DB）**：
- RSC 页面做 server-side prefetch — 可以引入 Drizzle 替代 fetch + 后端
- 内部工具页面（admin / system） — 可以绕过 BFF 走 Drizzle 直查，省一层

> 引入前评估：项目后端用 Python，后端是真值源。前端加 Drizzle 等于 schema 双写（TS schema + SQLAlchemy model），每次表结构改动两处都改。除非强烈需要前端直查，否则不推荐。

---

## 六、项目代码示例

项目仓库内**没有任何 Drizzle 调用代码**。下面给出"如果本项目要引入 Drizzle"的样例路径（伪代码，无现成代码可引用）：

**项目类似位置的对应代码**：

- 后端 session 工厂：[`packages/service/src/db/session.py`](../../packages/service/src/db/session.py) — `session_scope()` context manager
- 后端 Alembic 迁移：[`packages/service/src/storage/migrations/versions/`](../../packages/service/src/storage/migrations/versions/) — `20260617_000000_add_roles_and_rbac.py` 为最新一例
- 前端 apiFetch：[`packages/web/lib/api/fetcher.ts`](../../packages/web/lib/api/fetcher.ts) — BFF 调后端的薄封装

**伪代码样例**（基于上述模式，本项目若引入）：

```typescript
// packages/web/db/client.ts
import { drizzle } from "drizzle-orm/postgres-js";
import postgres from "postgres";
import * as schema from "./schema";

const sql = postgres(process.env.DATABASE_URL!, { ssl: "require" });
export const db = drizzle(sql, { schema });
```

```typescript
// packages/web/db/schema.ts
import { pgTable, uuid, text, timestamp, boolean } from "drizzle-orm/pg-core";

export const accounts = pgTable("accounts", {
  id: uuid("id").primaryKey().defaultRandom(),
  email: text("email").notNull().unique(),
  role: text("role").notNull().default("user"),
  isActive: boolean("is_active").notNull().default(true),
  createdAt: timestamp("created_at").notNull().defaultNow(),
});
```

> 📌 **真值源提醒**：上面 schema 是后端 SQLAlchemy 模型 [`Account`](../../packages/service/src/storage/models/account.py) 的 TS 镜像。任何字段变更必须**先改后端 Alembic 迁移 → 再同步 TS schema**，否则两端 drift。

---

## 七、项目没用到的能力

> 📌 严格说，本项目**整个没引入 Drizzle**，因此下列能力全部未使用。列出供未来选型参考。

### 7.1 Drizzle Relations (类型安全的 JOIN)

```typescript
import { relations } from "drizzle-orm";

export const usersRelations = relations(users, ({ many }) => ({
  posts: many(posts),
}));

export const postsRelations = relations(posts, ({ one }) => ({
  author: one(users, { fields: [posts.authorId], references: [users.id] }),
}));

// 查询时自动拿关联
const result = await db.query.users.findMany({
  with: { posts: true },
});
```

项目后端 SQLAlchemy 用 `relationship()` + `joinedload` 同模式，但前端无对应。

### 7.2 Drizzle Kit 高级 migration

- **Custom migrations**：手写 SQL 跟 Drizzle schema 混用
- **Snapshot diff**：CI 跑 `drizzle-kit generate --custom` 校验无意外 schema 漂移
- **数据迁移**：schema 迁移 + data backfill 在同一脚本里

### 7.3 prepared statement 缓存

```typescript
const getUserByEmail = db.select().from(users)
  .where(eq(users.email, sql.placeholder("email")))
  .prepare();

await getUserByEmail.execute({ email: "x@y.z" });
```

RSC 频繁访问同 query 时用 `prepare()` 减少解析开销。

### 7.4 Better Auth + Drizzle 集成

`bun.lock` 已经把 `@better-auth/drizzle-adapter@1.6.20` 作为 `better-auth` 的可选 peer 引入了（见 `bun.lock:154`）。如果项目后端从 Python 迁到 TS Node（不太可能但列在这），Better Auth 的用户表可以一键接 Drizzle schema。本项目用 Python 后端 + Better Auth 不走这条路径。

---

## 八、评测 & 调优技巧

### 8.1 SQL 日志

```typescript
// client.ts
export const db = drizzle(sql, { logger: process.env.NODE_ENV !== "production" });
// dev 模式自动打印 SQL + 参数, prod 关闭
```

### 8.2 N+1 防御

```typescript
// ❌ N+1: 先查 list, 再循环查每个 author
const postsList = await db.select().from(posts);
for (const post of postsList) {
  const author = await db.select().from(users).where(eq(users.id, post.authorId));
}

// ✅ 单 query JOIN
const result = await db
  .select({ post: posts, author: users })
  .from(posts)
  .innerJoin(users, eq(posts.authorId, users.id));
```

### 8.3 批量 INSERT

```typescript
// 单 statement 批量插入, 减少 round-trip
await db.insert(users).values([
  { email: "a@x" },
  { email: "b@x" },
  { email: "c@x" },
]);
```

### 8.4 索引决策

Drizzle 不强制索引，但可以声明：

```typescript
import { index } from "drizzle-orm/pg-core";

export const posts = pgTable("posts", {
  // ...
}, (table) => ({
  authorIdx: index("posts_author_idx").on(table.authorId),
  createdIdx: index("posts_created_idx").on(table.createdAt),
}));
```

跑 `EXPLAIN ANALYZE` 验证走索引。

### 8.5 Connection pooling

Postgres 直连数限制，用 PgBouncer 事务模式 + Neon serverless driver 是项目体量下的最佳实践。`postgres-js` 默认 connection 池 10，可调：

```typescript
const sql = postgres(url, { max: 20, idle_timeout: 30 });
```

---

## 九、最佳实践 & 常见坑

### 9.1 别用 `any` 强行绕过类型

```typescript
// ❌ 错: 类型丢失, 后续维护噩梦
const rows = await db.select().from(users as any);

// ✅ 对: 改 schema 让类型自然推断
```

### 9.2 JSON 字段用 `$type<T>()`

```typescript
import { jsonb } from "drizzle-orm/pg-core";

const metadata = jsonb("metadata").$type<{ tags: string[]; version: number }>();
// query 时 metadata 自动推断为 { tags: string[]; version: number }
```

不写 `$type` 会得到 `unknown`，每次都得 cast。

### 9.3 migration 跟 schema 双源

Drizzle schema 是 TS 真值源，但 Alembic/Prisma 各自有自己的 migration 历史。**项目体量下避免 TS + Python 双 schema**。要么全 TS（前后端都 Node），要么全 Python（维持现状）。混用必出 drift。

### 9.4 Soft delete 别用 `null: true`

```typescript
// ❌ 错: nullable 字段语义不清 (没填 vs 已删?)
deletedAt: timestamp("deleted_at"),  // nullable

// ✅ 对: 默认值约束语义
deletedAt: timestamp("deleted_at").default(sql`NULL`),
// 查询时显式过滤
.where(isNull(users.deletedAt))
```

### 9.5 RSC 缓存陷阱

```typescript
// app/admin/page.tsx — 默认 fetch 缓存, query 不缓存
export default async function Page() {
  const users = await db.select().from(users); // 每次请求都查 DB
  // ...
}

// 想缓存: 包 unstable_cache
import { unstable_cache } from "next/cache";
const getCachedUsers = unstable_cache(
  () => db.select().from(users).limit(50),
  ["users-list"],
  { revalidate: 60 },
);
```

### 9.6 版本兼容

- Drizzle 0.30 → 0.36 期间 API 有几次 breaking (`drizzle-orm/postgres-js` 改 default export 形式)
- Drizzle Kit 0.20+ 改 config schema，drizzle.config.ts 字段名变了
- 锁版本：本项目风格是在 `package.json` 固定 `"drizzle-orm": "0.36.x"`，避免 surprise

### 9.7 性能 vs Prisma

| 指标 | Drizzle | Prisma |
|------|---------|--------|
| Bundle size | ~30KB | ~10MB query engine |
| Cold start (Vercel) | <100ms | 500-1500ms |
| 查询性能 | 直拼 SQL, 接近原生 | 略低（中间抽象层） |
| 类型推断 | 端到端 | 编译后丢失, 需 Prisma.Generate |
| 生态 | 新, 但增长快 | 老, 文档最多 |

项目当前 Vercel 部署 + RSC 频繁访问的场景，Drizzle 优势明显；但只有当 TS Node 作为后端时才考虑。

---

## 📚 参考

- Drizzle 官方文档：<https://orm.drizzle.team/docs/overview>
- Drizzle Kit CLI：<https://orm.drizzle.team/docs/kit-overview>
- Better Auth + Drizzle：<https://www.better-auth.com/docs/adapters/drizzle>
- 性能对比 (Drizzle vs Prisma vs Kysely)：<https://orm.drizzle.team/docs/perf>

---

**状态：** 🚧 部分完成（项目未引入 Drizzle，第五/六节写"集成点 + 伪代码"，第七节列未用能力）