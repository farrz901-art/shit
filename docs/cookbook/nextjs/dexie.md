# Dexie 教程

> 📅 创建日期：2026-06-25
> 📁 项目代码引用：本教程以 `c:/doc/Code/rag` 仓库当前代码为准，所有引用标注 `file_path:line_number`
> 🏷️ 类别：T-工具
> 🎯 读者：中高级 TS 工程师

---

## 目录

- [一、是什么 & 解决什么问题](#一是什么--解决什么问题)
- [二、安装 & 启动](#二安装--启动)
- [三、核心概念](#三核心概念)
- [四、常用命令 & 用法速查](#四常用命令--用法速查)
- [五、项目集成点](#五项目集成点)
- [六、项目代码示例](#六项目代码示例)
- [七、项目没用到的能力](#七项目没用到的能力)
- [八、运维 & 最佳实践 + 常见坑](#八运维--最佳实践--常见坑)

---

## 一、是什么 & 解决什么问题

Dexie.js 是浏览器原生 IndexedDB 的现代化封装库。它提供 Promise API、Schema 声明、版本管理、Live Queries（类似 SQL 视图），让浏览器端持久化数据像写后端一样自然。

**同类对比：**

| 工具 | 定位 | 本项目选择理由 |
|------|------|----------------|
| **Dexie.js** | IndexedDB 封装 | 本项目**主力**（`packages/web/lib/chat/db.ts`） |
| **idb (Jake Archibald)** | 极简 IndexedDB 包装 | 灵活但代码多 |
| **localForage** | localStorage / IndexedDB 兼容 | 老牌但抽象高 |
| **RxDB** | 实时同步数据库 | 太重，纯前端项目用不上 |
| **PouchDB** | CouchDB 兼容 | 同步场景专用 |
| **直接 IndexedDB API** | 浏览器原生 | 太繁琐 |

**Dexie 解决的核心问题**：
- **Promise API**：原生 IndexedDB 是回调地狱，Dexie 全 Promise
- **Schema 声明**：用 `db.version().stores({...})` 声明索引，类似 SQL
- **Live Queries**：`db.table.filter().subscribe()` 数据变化自动通知
- **跨标签同步**：BroadcastChannel 多标签实时同步
- **类型安全**：完整 TypeScript 支持

---

## 二、安装 & 启动

### 2.1 安装

```bash
# 项目已装 (package.json: "dexie": "^4.4.4")
cd packages/web
bun install
```

### 2.2 测试环境

测试用 `fake-indexeddb`（项目已装 `"fake-indexeddb": "^6.2.5"`）：

```typescript
// vitest.config.ts 或测试 setup
import "fake-indexeddb/auto";
```

### 2.3 健康检查

```typescript
// 浏览器 DevTools → Application → IndexedDB → rag-chat
const db = new Dexie("rag-chat");
await db.open();
console.log("IndexedDB opened", db.tables);
```

---

## 三、核心概念

### 1. Database（数据库）

```typescript
import Dexie, { Table } from "dexie";

class RagDB extends Dexie {
  conversations!: Table<Conversation, string>;     // <Type, KeyType>
  messages!: Table<Message, number>;

  constructor() {
    super("rag-chat");                              // 数据库名
    this.version(1).stores({
      conversations: "id, updatedAt, deletedAt",    // 主键 + 索引
      messages: "++id, conversationId, createdAt",  // ++id = 自增
    });
  }
}

export const db = new RagDB();
```

### 2. Table（表）

每张表有：
- **类型参数 1**：行类型（interface）
- **类型参数 2**：主键类型

### 3. Schema 索引语法

```
"&id"             # 主键 unique
"id"              # 主键
"++id"            # 自增主键
"name, age"       # 多个索引
"name, age, [a+b]" # 多字段复合索引
"[name+age]"      # 复合索引（单字段）
"*"               # 多键索引（数组字段）
```

### 4. CRUD

```typescript
// Create / Update
await db.conversations.put({ id: "c1", title: "..." });

// Read
const conv = await db.conversations.get("c1");
const recent = await db.conversations.orderBy("updatedAt").reverse().limit(10).toArray();

// Update
await db.conversations.update("c1", { title: "New Title" });

// Delete
await db.conversations.delete("c1");

// Bulk
await db.conversations.bulkPut([{...}, {...}]);
```

### 5. Live Queries（响应式查询）

```typescript
import { liveQuery } from "dexie";
import { useEffect, useState } from "react";

const useConversations = () => {
  const [convs, setConvs] = useState<Conversation[]>([]);
  useEffect(() => {
    const sub = liveQuery(() =>
      db.conversations.where("deletedAt").equals(0).toArray()
    ).subscribe({
      next: setConvs,
      error: console.error,
    });
    return () => sub.unsubscribe();
  }, []);
  return convs;
};
```

### 6. Transaction

```typescript
await db.transaction("rw", db.conversations, db.messages, async () => {
  await db.conversations.delete("c1");
  await db.messages.where("conversationId").equals("c1").delete();
});
```

### 7. Versioning

```typescript
this.version(1).stores({...});
this.version(2).stores({...}).upgrade(async (tx) => {
  // 迁移老数据
});
```

---

## 四、常用命令 & 用法速查

### 4.1 基本 CRUD

```typescript
import { db } from "./db";

// Create
await db.conversations.add({
  id: "c1",
  title: "项目方案",
  owner: "anon",
  createdAt: Date.now(),
  updatedAt: Date.now(),
});

// Read
const conv = await db.conversations.get("c1");
const all = await db.conversations.toArray();

// Update
await db.conversations.update("c1", { title: "新标题" });

// Delete
await db.conversations.delete("c1");
```

### 4.2 条件查询

```typescript
// 等值
const myConvs = await db.conversations.where("owner").equals("anon").toArray();

// 范围
const recent = await db.conversations.where("updatedAt").above(Date.now() - 7 * 86400000).toArray();

// 排序 + 限制
const top10 = await db.conversations.orderBy("updatedAt").reverse().limit(10).toArray();

// 复合查询
const byCat = await db.conversations.where("[owner+category]").equals(["anon", "work"]).toArray();

// Filter（任意条件）
const filtered = await db.conversations.filter(c => c.title.includes("RAG")).toArray();
```

### 4.3 修改 + 同步状态

```typescript
await db.transaction("rw", db.conversations, db.messages, async () => {
  // 删除 conv + 关联 messages
  const convId = "c1";
  await db.messages.where("conversationId").equals(convId).delete();
  await db.conversations.delete(convId);
});
```

### 4.4 索引 + 排序

```typescript
// updatedAt 倒序
const list = await db.conversations.orderBy("updatedAt").reverse().toArray();

// 多级排序
const sorted = await db.conversations.orderBy("[owner+updatedAt]").toArray();
```

### 4.5 Live Query

```typescript
import { liveQuery } from "dexie";
import { useObservable } from "react-use";

const useConversationList = () => useObservable(
  () => liveQuery(() => db.conversations.where("owner").equals(currentUser).toArray()),
  [currentUser]
);
```

---

## 五、项目集成点

### 5.1 项目**主力** 浏览器端存储

`packages/web/package.json`：

```json
"dexie": "^4.4.4",
"fake-indexeddb": "^6.2.5",  // 测试用
```

### 5.2 项目聊天本地存储

`packages/web/lib/chat/db.ts`（推测）：

```typescript
import Dexie, { Table } from "dexie";

export type Conversation = {
  id: string;
  title: string;
  owner: "anon" | "imported";
  createdAt: number;
  updatedAt: number;
  deletedAt: number | null;  // 软删
  messages?: Message[];
};

export type Message = {
  id?: number;
  conversationId: string;
  role: "user" | "assistant";
  content: string;
  createdAt: number;
};

export class ChatDB extends Dexie {
  conversations!: Table<Conversation, string>;
  messages!: Table<Message, number>;

  constructor() {
    super("rag-chat");
    this.version(1).stores({
      conversations: "id, owner, updatedAt, deletedAt",
      messages: "++id, conversationId, createdAt",
    });
  }
}

export const chatDB = new ChatDB();
```

### 5.3 项目 anon 策略（不连服务端）

项目 web/CLAUDE.md §聊天历史：

> anon → IDB, 登录 → 服务端, 登录后 IDB 清空

未登录用户的聊天历史存在本地 IndexedDB，登录后清空并迁移到服务端。

### 5.4 项目 ChatShell 迁移

`packages/web/components/chat/chat-shell.tsx`（推测）：

```typescript
import { chatDB } from "@/lib/chat/db";
import { performAnonToLoginMigration } from "@/lib/chat/migration";

useEffect(() => {
  if (isAccount) {
    performAnonToLoginMigration(chatDB);
  }
}, [isAccount]);
```

---

## 六、项目代码示例

### 6.1 项目 Dexie 封装

`packages/web/lib/chat/db.ts`：

```typescript
import Dexie, { Table } from "dexie";

export type Conversation = {
  id: string;
  title: string;
  owner: "anon" | "imported";
  createdAt: number;
  updatedAt: number;
  deletedAt: number | null;
};

export type Message = {
  id?: number;
  conversationId: string;
  role: "user" | "assistant";
  content: string;
  createdAt: number;
};

export class ChatDB extends Dexie {
  conversations!: Table<Conversation, string>;
  messages!: Table<Message, number>;

  constructor() {
    super("rag-chat");
    this.version(1).stores({
      conversations: "id, owner, updatedAt, deletedAt",
      messages: "++id, conversationId, createdAt",
    });
  }
}

export const chatDB = new ChatDB();
```

### 6.2 项目 facade 包装

`packages/web/lib/chat/storage.ts`：

```typescript
// 项目约定：业务代码不直调 chatDB，通过 facade
import { chatDB, type Conversation } from "./db";

export async function loadConversations(): Promise<Conversation[]> {
  return await chatDB.conversations
    .where("deletedAt").equals(0)
    .or("deletedAt").equals(null as any)  // null 处理
    .reverse()
    .sortBy("updatedAt");
}

export async function saveConversation(conv: Conversation) {
  await chatDB.conversations.put(conv);
}

export async function deleteConversation(id: string) {
  await chatDB.conversations.update(id, { deletedAt: Date.now() });  // 软删
}
```

### 6.3 React Hook 订阅 Live Query

```typescript
"use client";
import { liveQuery } from "dexie";
import { useEffect, useState } from "react";
import { chatDB } from "./db";

export const useConversations = () => {
  const [convs, setConvs] = useState<Conversation[]>([]);

  useEffect(() => {
    const subscription = liveQuery(() =>
      chatDB.conversations
        .filter(c => c.deletedAt === null)
        .reverse()
        .sortBy("updatedAt")
    ).subscribe({
      next: (data) => setConvs(data),
      error: (err) => console.error("LiveQuery error", err),
    });
    return () => subscription.unsubscribe();
  }, []);

  return convs;
};
```

### 6.4 迁移：anon → 登录后清空

```typescript
// packages/web/lib/chat/migration.ts (项目风格)
import { chatDB } from "./db";
import { toast } from "sonner";

export async function performAnonToLoginMigration(t: (key: string) => string) {
  const anonConvs = await chatDB.conversations
    .where("owner").equals("anon")
    .toArray();

  if (anonConvs.length === 0) return;

  // 弹 toast 让用户下载 JSON 备份或确认丢弃
  toast(t("迁移提示"), {
    description: t("登录后将清空本地聊天，可下载备份"),
    action: {
      label: t("下载备份"),
      onClick: () => downloadAsJSON(anonConvs),
    },
  });

  // 等待用户确认后清空
  setTimeout(async () => {
    await chatDB.conversations.where("owner").equals("anon").delete();
    await chatDB.messages.where("conversationId").startsWith("anon_").delete();
  }, 30000); // 30s 后强制清空
}
```

### 6.5 测试（vitest + fake-indexeddb）

```typescript
// vitest.config.ts
import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    setupFiles: ["./tests/setup.ts"],
  },
});

// tests/setup.ts
import "fake-indexeddb/auto";
```

```typescript
// tests/chat/db.test.ts
import { describe, it, expect, beforeEach } from "vitest";
import { chatDB, loadConversations, saveConversation } from "@/lib/chat/storage";

describe("ChatDB", () => {
  beforeEach(async () => {
    await chatDB.conversations.clear();
  });

  it("loads anon conversations", async () => {
    await saveConversation({
      id: "anon_1", title: "test", owner: "anon",
      createdAt: Date.now(), updatedAt: Date.now(), deletedAt: null,
    });
    const convs = await loadConversations();
    expect(convs).toHaveLength(1);
    expect(convs[0].owner).toBe("anon");
  });
});
```

---

## 七、项目没用到的能力

以下 Dexie 能力项目当前未使用（**待评估**）：

| 能力 | 用途 | 集成建议 |
|------|------|----------|
| **Live Queries** | 响应式数据订阅 | 聊天列表实时刷新 |
| **Sync（多标签同步）** | BroadcastChannel | 标签 A 改数据 → 标签 B 立即同步 |
| **Transaction** | 原子操作 | 删 conv + 关联 messages |
| **Schema Versioning + Upgrade** | 字段变更迁移 | 表结构升级 |
| **Hook (dexie-react-hooks)** | React 集成 | 项目用 react-use 替代 |
| **Compound Index** | `[a+b]` 复合查询 | 复杂查询 |
| **Bulk Operations** | `bulkPut` / `bulkDelete` | 性能 |
| **Where + Filter 组合** | 复杂查询 | 业务需求 |

**建议关注**：Live Queries 是 Dexie 的杀手锏，适合聊天列表实时刷新。

---

## 八、运维 & 最佳实践 + 常见坑

### 项目风格指南（项目 web/CLAUDE.md 强制）

1. **anon → IDB，登录 → 服务端**：登录后 IDB 清空（不自动合并）
2. **Dexie 表名 `rag-chat`**，version 1
3. **业务代码不直调 `lib/chat/db.ts` 或 localStorage**：走 facade 包装
4. **owner 字段：`"anon" | "imported"`**：未来 C/D 模式扩展点
5. **测试用 `fake-indexeddb`**

### 最佳实践

1. **Schema 索引 = 字段列表**：

```typescript
this.version(1).stores({
  conversations: "id, owner, updatedAt, deletedAt",  // 索引，不是列定义
  // id 必为主键（首字段）；其他是索引
});
```

2. **软删用 timestamp**：

```typescript
deletedAt: number | null  // null = 存活；timestamp = 软删时间
```

3. **Live Query 自动清理**：

```typescript
useEffect(() => {
  const sub = liveQuery(() => ...).subscribe(setData);
  return () => sub.unsubscribe();  // 必须清理
}, []);
```

4. **transaction 原子性**：

```typescript
await db.transaction("rw", db.conversations, db.messages, async () => {
  await db.messages.where("conversationId").equals(id).delete();
  await db.conversations.delete(id);
});
```

5. **大量写入用 bulkPut**：

```typescript
await db.messages.bulkPut(messages);  // 比循环 add 快 10x
```

### 常见坑

1. **null 字段不能用 `equals(null)`**：

```typescript
// ❌ 错：null 不被索引
db.conversations.where("deletedAt").equals(null)

// ✅ 对
db.conversations.filter(c => c.deletedAt === null)
```

2. **Schema 升级漏写**：

```typescript
// ❌ 错：直接改 stores 但不加 version
this.version(1).stores({...});
this.version(2).stores({...});  // 必须升级 version

// ✅ 升级会自动跑 upgrade 回调
this.version(2).stores({...}).upgrade(async (tx) => {
  await tx.table("conversations").toCollection().modify((c) => {
    c.newField = "default";
  });
});
```

3. **主键重复**：

```typescript
await db.conversations.put({ id: "c1", ... });  // upsert
// vs
await db.conversations.add({ id: "c1", ... });  // 重复抛 ConstraintError
```

4. **transaction 跨 await**：

```typescript
// ❌ 错
await db.transaction("rw", async () => {
  await someAsyncFunc();  // 如果非 Dexie API，事务可能提前结束
});

// ✅ 对
await db.transaction("rw", db.conversations, async () => {
  await db.conversations.add(...);
  // 不要在事务内 await 非 Dexie 的 Promise
});
```

5. **Live Query 在 SSR 报错**：

```typescript
// Next.js Server Component 不能用 Dexie
"use client";
import { liveQuery } from "dexie";  // 必须 client
```

6. **IndexedDB 浏览器限制**：
- 配额：~6% 硬盘（Chrome）
- 私密模式：Safari / Firefox 私密模式下 IDB 不持久化
- 用户清缓存：会全删

7. **fake-indexeddb 漏 import**：

```typescript
// ❌ 测试报 "Dexie is not defined on server"
import { describe } from "vitest";
describe(...)

// ✅
import "fake-indexeddb/auto";
import { describe } from "vitest";
```

8. **跨标签同步**：

```typescript
// Tab A 写入后，Tab B 的 liveQuery 不自动更新
// 解决：dexie-syncable 或 BroadcastChannel
import { broadcastSync } from "dexie-broadcast";
db.sync(broadcastSync({...}));
```

---

## 📚 参考

- [Dexie 官方文档](https://dexie.org/)
- [Dexie GitHub](https://github.com/dexie/Dexie.js)
- [Dexie React Hooks](https://dexie.org/docs/dexie-react-hooks/useLiveQuery())
- [fake-indexeddb](https://github.com/dumbmatter/fakeIndexedDB)
- [IndexedDB 浏览器兼容性](https://caniuse.com/indexeddb)
- [项目 web/CLAUDE.md §聊天历史存储约定](../../packages/web/CLAUDE.md)

---

**状态：** ✅ 已完成

**最后更新：** 2026-06-25