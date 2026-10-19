# Payload CMS 教程

> 📅 创建日期：2026-06-28
> 📁 项目代码引用：本教程以 `c:/doc/Code/rag` 仓库当前代码为准，所有引用标注 `file_path:line_number`
> 🏷️ 类别：A-AI 库（Headless CMS 类别参考，写作按 A 模板 9 节结构）
> 🎯 读者：中高级 TS 工程师，需要在 Next.js 全栈项目里评估 Payload CMS、自带 admin / auth / storage 的取舍

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

Payload CMS 是一个 **Next.js 原生**的 TypeScript Headless CMS。它把"内容管理后台 + REST/GraphQL API + 鉴权 + 文件存储"打包成一个 npm 包，直接装进 Next.js App Router 项目，**不开新仓库**。编辑器是现成的 admin UI，开发者只写 schema。

**同类对比：**

| 方案 | 定位 | 本项目选择理由 |
|------|------|----------------|
| **Payload CMS** | Next.js 原生 Headless CMS | 自带 admin UI + auth + 媒体库，单仓库一站式 |
| **Strapi** | 独立 CMS 仓库 + REST/GraphQL | 生态成熟，但**独立服务**，要单独部署 |
| **Sanity** | 托管 CMS + GROQ 查询 | SaaS 体验好，但 vendor lock-in |
| **Contentful** | 商业 SaaS CMS | 团队工作流强，免费版限额 |
| **Directus** | 独立 Node CMS + 自带 admin | 数据库可视化思维，但独立部署 |
| **Prismic** | SaaS + Slice 组件 | DX 流畅，免费版限额 |

**Payload 解决的核心问题**：
- **零基础设施**：不用单独部署 CMS 服务，跟主应用同一进程同一数据库
- **代码即 schema**：用 TS 对象声明 collections，编译期类型推断，运行时自动生成 admin UI + REST/GraphQL
- **自带 RBAC + 鉴权**：内置 users collection + access control 钩子，不用自己写 auth
- **媒体文件管理**：Upload collection 处理图片/PDF，集成 S3 / R2 / GCS
- **关系 + 嵌套文档**：`relationship` / `array` / `blocks` 字段，复杂内容建模
- **Hooks + Endpoints**：beforeChange / afterRead 等钩子能改写行为，custom endpoint 写业务逻辑

**不适用的场景**：
- 多语言内容编辑复杂（Payload 有 i18n 但配置繁琐）—— 跟项目 [next-intl](https://next-intl.dev/) 模式冲突
- 已经有自己的后端（项目当前 Python FastAPI）—— Payload 是 Node + Postgres 全套
- 需要极简的静态内容（markdown 仓库就够）—— Payload 是重量级方案

---

## 二、安装 & 初始化

### 2.1 安装

```bash
# Payload 3.x 是 Next.js 原生包, 装到现有 Next.js 项目
bun add payload @payloadcms/next @payloadcms/db-postgres @payloadcms/richtext-lexical
```

### 2.2 目录结构 (Payload 3.x 装到现有 Next.js)

```
my-app/
├── app/
│   ├── (frontend)/        # 现有业务页面
│   └── (payload)/         # Payload admin + API 路由
│       ├── admin/
│       │   ├── [[...segments]]/page.tsx
│       │   └── not-found.tsx
│       └── api/
│           ├── [...slug]/
│           │   └── route.ts
│           ├── graphql/
│           └── graphql-playground/
├── payload.config.ts      # Payload 配置
└── src/
    ├── collections/        # Collection 定义
    │   ├── Users.ts
    │   ├── Posts.ts
    │   └── Media.ts
    └── access/             # 访问控制函数
```

### 2.3 payload.config.ts 最小化配置

```typescript
import { buildConfig } from "payload";
import { postgresAdapter } from "@payloadcms/db-postgres";
import { lexicalEditor } from "@payloadcms/richtext-lexical";

import { Users } from "./src/collections/Users";
import { Posts } from "./src/collections/Posts";
import { Media } from "./src/collections/Media";

export default buildConfig({
  admin: {
    user: Users.slug,           // admin 登录用 users collection
    meta: { titleSuffix: " - MyApp CMS" },
  },
  collections: [Users, Posts, Media],
  editor: lexicalEditor({}),    // 默认富文本编辑器
  secret: process.env.PAYLOAD_SECRET!,
  typescript: {
    outputFile: "./src/payload-types.ts",  // 自动生成 collection 类型
  },
  db: postgresAdapter({
    pool: {
      connectionString: process.env.DATABASE_URL!,
    },
  }),
  sharp: undefined,             // 不需要图片处理可以省
});
```

### 2.4 env 变量

| 变量 | 必填 | 说明 |
|------|------|------|
| `DATABASE_URL` | ✅ | Postgres 连接串 |
| `PAYLOAD_SECRET` | ✅ | JWT 签名密钥, `openssl rand -hex 32` 生成 |
| `NEXT_PUBLIC_SERVER_URL` | ✅ | admin UI 用, 例 `https://cms.example.com` |
| `S3_ACCESS_KEY_ID` | 可选 | 用 S3/R2 存媒体时 |
| `S3_SECRET_ACCESS_KEY` | 可选 | 同上 |
| `S3_BUCKET` | 可选 | bucket 名 |

### 2.5 数据库初始化

```bash
# 第一次启动自动建表 (默认 push schema)
bun run dev
# 访问 http://localhost:3000/admin, 第一个注册的 user 自动成为 admin
```

---

## 三、核心概念 & 抽象

### 3.1 Collection (内容表)

```typescript
// src/collections/Posts.ts
import { CollectionConfig } from "payload";

export const Posts: CollectionConfig = {
  slug: "posts",
  admin: {
    useAsTitle: "title",        // admin 列表显示字段
    defaultColumns: ["title", "author", "status", "publishedAt"],
  },
  access: {
    read: () => true,           // 公开可读
    create: ({ req: { user } }) => !!user,
    update: ({ req: { user }, id }) => user?.role === "admin" || user?.id === id,
    delete: ({ req: { user } }) => user?.role === "admin",
  },
  fields: [
    { name: "title", type: "text", required: true },
    { name: "slug", type: "text", unique: true, index: true },
    {
      name: "status",
      type: "select",
      options: [
        { label: "Draft", value: "draft" },
        { label: "Published", value: "published" },
      ],
      defaultValue: "draft",
      admin: { position: "sidebar" },
    },
    {
      name: "content",
      type: "richText",
    },
    {
      name: "author",
      type: "relationship",
      relationTo: "users",
      required: true,
    },
    {
      name: "tags",
      type: "array",
      fields: [
        { name: "tag", type: "text" },
      ],
    },
    {
      name: "coverImage",
      type: "upload",
      relationTo: "media",
    },
  ],
  timestamps: true,             // 自动 createdAt / updatedAt
};
```

### 3.2 Field 类型速查

| 类型 | 用法 | 存什么 |
|------|------|--------|
| `text` | 短文本 (标题) | string |
| `textarea` | 多行文本 | string |
| `richText` | Lexical 富文本 | JSON |
| `number` | 数字 | number |
| `checkbox` | 布尔 | boolean |
| `date` | 日期 | ISO string |
| `select` | 单选下拉 | enum string |
| `radio` | 单选按钮 | enum string |
| `relationship` | 关联另一 collection | FK id |
| `upload` | 文件上传 | media id |
| `array` | 嵌套数组 | JSON array |
| `blocks` | 异构块 (布局 + 文本 + 图) | JSON |
| `group` | 字段分组 | nested object |
| `json` | 任意 JSON | JSON |
| `code` | 代码高亮 | string |

### 3.3 Access Control (RBAC)

```typescript
// 角色: 'admin' | 'editor' | 'user'
import { Access } from "payload";

export const isAdmin: Access = ({ req: { user } }) => user?.role === "admin";

export const isAdminOrSelf: Access = ({ req: { user } }) => {
  if (!user) return false;
  if (user.role === "admin") return true;
  return { id: { equals: user.id } };  // 限定条件
};
```

### 3.4 Hooks

```typescript
// 自动生成 slug
import { CollectionConfig } from "payload";
import { slugify } from "../utils";

export const Posts: CollectionConfig = {
  slug: "posts",
  hooks: {
    beforeChange: [
      ({ data, operation }) => {
        if (operation === "create" && !data.slug) {
          data.slug = slugify(data.title);
        }
        return data;
      },
    ],
    afterChange: [
      async ({ doc, req }) => {
        // 发通知 / 写日志 / 触发 webhook
        await req.payload.create({
          collection: "audit-logs",
          data: { action: "post.update", docId: doc.id, user: req.user.id },
        });
      },
    ],
  },
  fields: [
    { name: "title", type: "text" },
    { name: "slug", type: "text" },
  ],
};
```

### 3.5 Local API (服务端直调)

```typescript
import { getPayload } from "payload";
import config from "@payload-config";

const payload = await getPayload({ config });

// 查询
const posts = await payload.find({
  collection: "posts",
  where: { status: { equals: "published" } },
  limit: 10,
  sort: "-publishedAt",
  depth: 2,                    // populate relationship 字段深度
});

// 创建
const newPost = await payload.create({
  collection: "posts",
  data: { title: "Hello", slug: "hello", status: "draft" },
});

// 更新
await payload.update({
  collection: "posts",
  id: "...",
  data: { status: "published" },
});

// 删除
await payload.delete({ collection: "posts", id: "..." });
```

### 3.6 REST + GraphQL 自动生成

```bash
# REST API (默认开启, 无需配置)
GET    /api/posts
GET    /api/posts/:id
POST   /api/posts
PATCH  /api/posts/:id
DELETE /api/posts/:id
# 支持 ?where[status][equals]=published 等查询参数

# GraphQL (在 payload.config.ts 开启)
graphql: { schemaOutputFile: "./src/generated-schema.graphql" }
# 访问 /api/graphql-playground
```

---

## 四、常用 API & 命令速查

### 4.1 启动 admin UI

```bash
bun run dev
# 访问 http://localhost:3000/admin
# 第一个注册的 user 自动是 admin role
```

### 4.2 Next.js 集成 (RSC 调 Local API)

```tsx
// app/(frontend)/posts/page.tsx
import { getPayload } from "payload";
import config from "@payload-config";

export default async function PostsPage() {
  const payload = await getPayload({ config });
  const { docs } = await payload.find({
    collection: "posts",
    where: { status: { equals: "published" } },
    limit: 20,
  });

  return (
    <ul>
      {docs.map((post) => (
        <li key={post.id}>
          <h2>{post.title}</h2>
          <p>{post.publishedAt}</p>
        </li>
      ))}
    </ul>
  );
}
```

### 4.3 上传文件到 S3 / R2

```typescript
// payload.config.ts
import { s3Storage } from "@payloadcms/storage-s3";

export default buildConfig({
  plugins: [
    s3Storage({
      collections: {
        media: true,
      },
      bucket: process.env.S3_BUCKET!,
      config: {
        endpoint: process.env.S3_ENDPOINT!,
        credentials: {
          accessKeyId: process.env.S3_ACCESS_KEY_ID!,
          secretAccessKey: process.env.S3_SECRET_ACCESS_KEY!,
        },
        region: "auto",
      },
    }),
  ],
});
```

### 4.4 Drafts + Versions

```typescript
export const Posts: CollectionConfig = {
  slug: "posts",
  versions: {
    drafts: {
      autosave: { interval: 800 },  // 0.8s 自动保存草稿
    },
    maxPerDoc: 25,                  // 保留 25 个历史版本
  },
  fields: [{ name: "title", type: "text" }],
};
```

### 4.5 Custom Endpoint

```typescript
// src/collections/Posts.ts
endpoints: [
  {
    path: "/:id/publish",
    method: "post",
    handler: async ({ req, params }) => {
      const post = await req.payload.update({
        collection: "posts",
        id: params.id as string,
        data: { status: "published", publishedAt: new Date().toISOString() },
      });
      return Response.json(post);
    },
  },
],
```

### 4.6 CLI 命令

```bash
bunx payload secret --rotate        # 轮换 JWT secret
bunx payload migrate                # 跑 migration
bunx payload generate:types         # 重生成 payload-types.ts
bunx payload migrate:create         # 新建 migration 文件
```

---

## 五、项目集成点

本项目**未使用 Payload CMS**。架构是：
- 后端 Python FastAPI ([`packages/service/`](../../packages/service/))
- 前端 Next.js + 业务功能 ([`packages/web/`](../../packages/web/))
- 数据建模 SQLAlchemy + Alembic ([`docs/cookbook/python/sqlalchemy.md`](../python/sqlalchemy.md))
- 鉴权 better-auth ([`packages/web/lib/auth/`](../../packages/web/lib/auth/))
- 内容/资源管理：项目没有传统 CMS 需求，文档/知识用 RAG 检索 ([`docs/cookbook/rag/`](../../rag/))

**为什么不引 Payload**：
- 后端是 Python — Payload 是 Node + Postgres 全套 TS，schema 双源风险
- 项目知识/文档走 RAG pipeline（解析 + 向量 + LLM 生成）— 不需要传统 CMS
- 用户/权限用 better-auth + 后端 RBAC — Payload 自带 auth 是冗余
- Admin 需求：内部管理页用 shadcn + 后端 REST 解决（[`docs/cookbook/nextjs/nextjs.md`](./nextjs.md) 业务流）

**潜在场景（理论上）**：
- 项目加"市场内容 / 营销页"—— 营销团队需要可视化编辑，硬编码到 Next.js 维护成本高，Payload 自带 admin 能让非工程师改文案
- 项目加"博客 / 文档站点"—— Payload 的 drafts/versions/lexical 富文本很合适
- 项目加"产品目录 / 客户案例展示"—— Payload 的 relationship + blocks 字段适合结构化内容

> 📌 **结论**：项目当前业务（知识管理 + RAG + 审批流）不适用 Payload。引入前评估：业务是不是真的有"非技术用户在线编辑内容"的场景，否则成本不划算。

---

## 六、项目代码示例

项目仓库内**没有任何 Payload 调用代码**。下面给出"如果本项目要引入 Payload"的样例路径（伪代码，无现成代码可引用）：

**项目类似位置的对应代码**：

- 后端 schema 定义：[`packages/service/src/storage/models/`](../../packages/service/src/storage/models/) — SQLAlchemy model，类似 Payload collection 的 role
- 后端 FastAPI router：[`packages/service/src/kg/router.py`](../../packages/service/src/kg/router.py) — REST 端点定义
- 前端 admin 页面：[`packages/web/app/[locale]/admin/`](../../packages/web/app/[locale]/admin/) — 内部管理 UI，可作为"业务 admin"参照（非内容 CMS）

**伪代码样例**（基于上述模式，本项目若引入）：

```typescript
// src/collections/Articles.ts — 对应项目 "知识文章" 表
import { CollectionConfig } from "payload";

export const Articles: CollectionConfig = {
  slug: "articles",
  admin: {
    useAsTitle: "title",
    defaultColumns: ["title", "author", "status", "publishedAt"],
  },
  access: {
    read: () => true,                              // 公开读
    create: ({ req: { user } }) => user?.role === "admin" || user?.role === "editor",
    update: ({ req: { user } }) => user?.role === "admin" || user?.role === "editor",
    delete: ({ req: { user } }) => user?.role === "admin",
  },
  fields: [
    { name: "title", type: "text", required: true, localized: true },
    { name: "slug", type: "text", unique: true, index: true },
    {
      name: "status",
      type: "select",
      options: [
        { label: "草稿", value: "draft" },
        { label: "已发布", value: "published" },
      ],
      defaultValue: "draft",
    },
    {
      name: "content",
      type: "richText",
    },
    {
      name: "author",
      type: "relationship",
      relationTo: "users",
      required: true,
    },
    {
      name: "tags",
      type: "array",
      fields: [{ name: "name", type: "text" }],
    },
    {
      name: "relatedDataset",
      type: "relationship",
      relationTo: "datasets",     // 跟项目 dataset 概念对应
    },
  ],
  versions: { drafts: { autosave: { interval: 1500 } } },
  timestamps: true,
};
```

```typescript
// app/(frontend)/articles/page.tsx — RSC 调 Payload Local API
import { getPayload } from "payload";
import config from "@payload-config";

export default async function ArticlesPage() {
  const payload = await getPayload({ config });
  const { docs } = await payload.find({
    collection: "articles",
    where: { status: { equals: "published" } },
    limit: 20,
    sort: "-publishedAt",
  });

  return (
    <ul>
      {docs.map((article) => (
        <li key={article.id}>
          <h2>{article.title}</h2>
          <time>{article.publishedAt}</time>
        </li>
      ))}
    </ul>
  );
}
```

> 📌 **架构提示**：上面伪代码假设项目从 Python 后端迁 TS Node（或新增一个 TS Node 旁路服务）。当前 Python + SQLAlchemy 架构下，Payload 不能直接接入。

---

## 七、项目没用到的能力

### 7.1 国际化字段 (`localized: true`)

```typescript
// 字段声明
{ name: "title", type: "text", localized: true }

// 写入: 不同 locale 不同值
await payload.create({
  collection: "posts",
  data: { title: { en: "Hello", zh: "你好" } },
  locale: "en",                  // 当前请求 locale
});

// 读取
const post = await payload.findByID({ collection: "posts", id, locale: "zh" });
```

项目 [next-intl](https://next-intl.dev/) 在前端做翻译，跟 Payload 的"字段级别 i18n"模型不同——Payload 适合内容多语言，项目用 next-intl 适合 UI 字符串。

### 7.2 Block 内容 (异构内容布局)

```typescript
{
  name: "pageContent",
  type: "blocks",
  blocks: [
    { slug: "hero", fields: [{ name: "headline", type: "text" }] },
    { slug: "imageGallery", fields: [{ name: "images", type: "array", fields: [...] }] },
    { slug: "cta", fields: [{ name: "buttonText", type: "text" }, { name: "url", type: "text" }] },
  ],
}
```

适合营销页/落地页等"自由排版"内容。

### 7.3 自定义 Dashboard Widgets

```typescript
// payload.config.ts
admin: {
  components: {
    graphics: {
      Navigation: CustomNav,
      beforeDashboard: [
        MyCustomDashboardWidget,    // 注入到 admin 首页
      ],
    },
  },
}
```

### 7.4 Webhook + Outgoing 集成

```typescript
// 文档变更时通知外部系统
endpoints: [
  {
    path: "/webhook-trigger",
    method: "post",
    handler: async (req) => {
      await fetch(process.env.WEBHOOK_URL!, {
        method: "POST",
        body: JSON.stringify(req.body),
      });
      return Response.json({ ok: true });
    },
  },
],
```

### 7.5 Live Preview (RSC 实时预览)

```typescript
// payload.config.ts
admin: {
  livePreview: {
    breakpoints: [
      { name: "mobile", width: 375, height: 667, label: "Mobile" },
      { name: "desktop", width: 1440, height: 900, label: "Desktop" },
    ],
  },
}
```

项目知识管理页用 RAG 生成内容，不适用 Live Preview；适合营销页/博客编辑流。

### 7.6 Field-level Conditional Logic

```typescript
{
  name: "premiumContent",
  type: "richText",
  admin: {
    condition: (data) => data.tier === "premium",   // 只在 premium 模式显示
  },
}
```

---

## 八、评测 & 调优技巧

### 8.1 Depth (populate 关联)

```typescript
// depth 默认 0, 关联字段不返回完整对象
// depth: 1 = 1 层 populate, depth: 2 = 嵌套, 以此类推
// 越深越慢, 最多 5

const post = await payload.findByID({
  collection: "posts",
  id,
  depth: 1,                // 拿 author 完整对象
});
```

### 8.2 Query 优化

```typescript
// 只 select 需要的字段
const { docs } = await payload.find({
  collection: "posts",
  select: { id: true, title: true, slug: true },   // 省传输
  limit: 20,
});

// 默认查询条件 (类似 middleware)
defaultPopulate: { status: true },                 // 强制只查 published
```

### 8.3 Cache (Next.js RSC + Payload)

```tsx
// app/(frontend)/posts/page.tsx
import { unstable_cache } from "next/cache";

const getPosts = unstable_cache(
  async () => {
    const payload = await getPayload({ config });
    return payload.find({ collection: "posts", where: { status: { equals: "published" } } });
  },
  ["posts-list"],
  { revalidate: 60 },                              // 60s 缓存
);

export default async function PostsPage() {
  const { docs } = await getPosts();
  return <PostList posts={docs} />;
}
```

### 8.4 批量操作

```typescript
// 批量更新
await payload.update({
  collection: "posts",
  where: { status: { equals: "draft" }, createdAt: { less_than: "2026-01-01" } },
  data: { status: "archived" },
});

// 批量删除
await payload.delete({
  collection: "audit-logs",
  where: { createdAt: { less_than: "2026-01-01" } },
});
```

### 8.5 监控 / 审计

```typescript
// Payload 自带 operation 钩子, 加审计日志
hooks: {
  afterChange: [
    async ({ doc, operation, req }) => {
      await req.payload.create({
        collection: "audit-logs",
        data: {
          action: `${collection}.${operation}`,
          user: req.user?.id,
          docId: doc.id,
          timestamp: new Date().toISOString(),
        },
      });
    },
  ],
},
```

### 8.6 Payload Admin 性能

- admin UI 是客户端 React bundle, 首次加载 ~1.5MB
- 大量 collections 时 admin dashboard 渲染慢, 建议用 sidebar group 分组
- 用 `admin.components.beforeListTable` 注入虚拟化列表避免 1000+ 行卡顿

---

## 九、最佳实践 & 常见坑

### 9.1 用 Local API, 不要走 HTTP 自调

```typescript
// ❌ 错: RSC 里发 fetch 调自己的 /api
const res = await fetch(`http://localhost:3000/api/posts/${id}`);

// ✅ 对: 用 getPayload 直调
const payload = await getPayload({ config });
const post = await payload.findByID({ collection: "posts", id });
```

走 HTTP 自调等于 HTTP overhead + auth check + 序列化，Pure function 调用快 5-10x。

### 9.2 不要在 hook 里 await 业务异步

```typescript
// ❌ 错: 写操作 + 慢业务耦合, 客户端等
afterChange: [
  async ({ doc }) => {
    await sendEmailToSubscribers(doc);              // 阻塞响应
  },
],

// ✅ 对: 队列化, 不阻塞
afterChange: [
  ({ doc, req }) => {
    req.payloadQueue?.create({ task: "sendNewsletter", data: { postId: doc.id } });
  },
],
```

### 9.3 i18n 字段慎用

`localized: true` 字段在 DB 里存 `{ en: "...", zh: "..." }` JSON，查询比普通字段慢 + 索引复杂。如果只是 UI 字符串走 next-intl，只有"内容字段"（标题/正文）才用 Payload localized。

### 9.4 Access Control 别用 ctx.db

```typescript
// ❌ 错: 直接 query DB, 绕过 access control
access: {
  read: async ({ req }) => {
    return req.payload.find({ collection: "posts", limit: 0 }).then(r => r.docs);
  },
},

// ✅ 对: 纯 query 表达式
access: {
  read: () => true,
  // 或
  read: ({ req: { user } }) => user?.role === "admin" || { status: { equals: "published" } },
},
```

### 9.5 Migrations

```bash
# Payload 3.x 用 Drizzle/Prisma-style migrations
bunx payload migrate                  # 跑 pending migrations
bunx payload migrate:create           # 新建 migration 文件

# Schema 改动后:
#   1. 改 collections/*.ts
#   2. bunx payload migrate:create    生成 SQL 迁移
#   3. review SQL, 提交
#   4. CI / 部署时 bunx payload migrate
```

### 9.6 Type 生成

```typescript
// payload.config.ts
typescript: {
  outputFile: "./src/payload-types.ts",
}

// 引用类型
import type { Post, User } from "./payload-types";

const post: Post = ...;                  // 强类型
```

CI 应该加 `bunx payload generate:types --check` 校验类型同步。

### 9.7 version 兼容

- Payload 2.x → 3.x 是 Next.js App Router 重写，**breaking**：必须迁移 `(payload)` route group
- 3.x 还在快速迭代，**锁版本**：固定 `payload@3.x` + `@payloadcms/next@3.x` + `@payloadcms/db-postgres@3.x`
- 自定义字段类型 API 经常变，写插件时要盯 changelog

### 9.8 部署注意事项

- Payload 跟 Next.js 一同部署, 不需要独立服务
- 数据库必须是 Postgres / MongoDB / SQLite（看你装的 adapter）
- `sharp` 库需要系统 libvips, Docker 部署加 `apt-get install libvips`
- `PAYLOAD_SECRET` 必须用 `openssl rand -hex 32` 生成, 32 字符短密钥会被 warn

---

## 📚 参考

- Payload 官方文档：<https://payloadcms.com/docs/getting-started/what-is-payload>
- Payload + Next.js 集成：<https://payloadcms.com/docs/getting-started/installation>
- Access Control：<https://payloadcms.com/docs/access-control/overview>
- Hooks：<https://payloadcms.com/docs/hooks/overview>
- Local API：<https://payloadcms.com/docs/local-api/overview>
- Plugin 列表：<https://payloadcms.com/docs/plugins/overview>

---

**状态：** 🚧 部分完成（项目未引入 Payload CMS，第五/六节写"集成点 + 伪代码"，第七节列未用能力）