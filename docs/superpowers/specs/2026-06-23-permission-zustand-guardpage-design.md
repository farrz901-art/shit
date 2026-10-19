# 权限 Client Store + GuardPage 重构

**日期**: 2026-06-23
**状态**: 待实施
**作者**: Claude

## Context

当前权限获取模式存在**代码冗余**问题：

1. 22 个 page.tsx 各自 import getMyPermissions，视觉重复，入口不统一
2. Zustand store（usePermissionsStore）已实现但未被任何组件引用（死代码）
3. ClientPageGuard 每次 mount 独立调 getMyPermissions() API，无缓存
4. RSC layout 查到的权限没有 hydrate 到 client 侧，client 组件必须重复 fetch

## 目标

- 页面层不再 import 任何权限函数，改走 GuardPage wrapper 统一入口
- Client 侧权限通过 RSC -> Zustand hydration，0 额外 fetch
- 废弃 ClientPageGuard，改走 GuardClient 读 store
- 统一 server 侧入口到 getPermissions()（permission.ts），内建派生方法
- layout 改用 RSC cached 版本，消除重复 API 调用

## 非目标

- 不动后端 /api/permissions/me 端点
- 不动 lib/api/permissions.ts（底层 API 调用层）
- 不动 lib/api/auth.server.ts（serverAuthHeaders 封装）
- 不动权限业务逻辑（allowed / role 判断规则不变）
- 不动测试基础设施（vitest mock 模式不变）

---

## 1. 当前状态审计

### 1.1 文件混淆现状

| 文件 | 角色 | 目标 |
|------|------|------|
| `lib/auth/permission.ts` | RSC cached `getPermissions()` → `PermissionResult`（带 can/isAdminLevel/isSuperAdmin） | **统一入口**，所有 RSC 页面应走这里 |
| `lib/auth/permissions.ts`（复数） | RSC cached `getMyPermissions()` → `MyPermissions`（原始 API shape，含 account_id） | **废弃**，被 `permission.ts` 替代 |
| `lib/api/permissions.ts` | 底层 fetch 层（`apiFetch("/api/permissions/me")`） | **保留**，非目标 |
| `lib/hooks/use-permissions.ts` | zustand store + `usePermissions()` hook，当前自动调 API fetch | **重写**为 hydration-only，从 RSC 接收数据 |

### 1.2 Layout 问题

`app/[locale]/layout.tsx` 第 18 行：
```ts
import { getMyPermissions } from "@/lib/api/permissions"; // 原始 API fetch，无 RSC cache
```
每次 layout 渲染都独立 API 调用，不被 RSC `cache()` 共享。应改用 `lib/auth/permission.ts` 的 `getPermissions()`。

### 1.3 Header 类型依赖

`components/layout/header.tsx` import `MyPermissions` from `lib/auth/permissions`（复数）。重构后需改为 `PermissionResult` 或 `PermissionData`。
`Header` 是 RSC layout 的子组件（非 `"use client"`），不存在序列化问题，可直接接收 `PermissionResult`。

### 1.4 页面权限使用清单

#### RSC 页面（使用 PageGuard + import getMyPermissions/getPermissions）

| 页面 | 当前 import | pageKey | 特殊行为 |
|------|-------------|---------|---------|
| `chat/page.tsx` | `lib/auth/permissions` | `chat` | 额外调 /api/account/me 判断 isAccount |
| `evaluate/page.tsx` | `lib/auth/permissions` | `evaluate` | 额外用 allowed.includes 控制数据渲染 |
| `evaluate/[id]/page.tsx` | `lib/auth/permissions` | `evaluate` | — |
| `evaluate/new/page.tsx` | `lib/auth/permissions` | `evaluate` | — |
| `health/page.tsx` | `lib/auth/permissions` | `health` | — |
| `submissions/page.tsx` | `lib/auth/permissions` | `submissions` | — |
| `output/page.tsx` | `lib/auth/permissions` | `output` | — |
| `output/[task_id]/page.tsx` | `lib/auth/permissions` | `output` | — |
| `knowledge/graph/page.tsx` | `lib/auth/permissions` | `knowledge` | 子路由共享 pageKey |
| `knowledge/triples/page.tsx` | `lib/auth/permissions` | `knowledge` | — |
| `knowledge/nodes/page.tsx` | `lib/auth/permissions` | `knowledge` | — |
| `knowledge/qa/page.tsx` | `lib/auth/permissions` | `knowledge` | — |
| `knowledge/relations/page.tsx` | `lib/auth/permissions` | `knowledge` | — |
| `knowledge/datasets/page.tsx` | `lib/auth/permissions` | `knowledge` | — |
| `knowledge/dataset-documents/[dataset_id]/page.tsx` | `lib/auth/permissions` | `knowledge` | — |
| `knowledge/documents/page.tsx` | `lib/auth/permissions` | `knowledge` | — |
| `knowledge/documents/import/page.tsx` | `lib/auth/permissions` | `knowledge` | — |
| `admin/invites/page.tsx` | `lib/auth/permissions` | `admin` | — |
| `admin/users/page.tsx` | `lib/auth/permission`（单数） | `admin` | 额外用 perm.isAdminLevel 守卫 + perm.headers 调 API |
| `admin/dicts/page.tsx` | `lib/auth/permission`（单数） | `admin` | 额外用 perm.isSuperAdmin 守卫，传 role+allowed 给 client |
| `admin/permissions/page.tsx` | `lib/auth/permission`（单数） | `admin` | 额外用 perm.isSuperAdmin 守卫 + perm.headers 调 API |

> 共 **21** 个 RSC 页面。其中 admin/* 3 页已用单数版，其他 18 页仍用复数版。

#### Client 页面（使用 ClientPageGuard）

| 页面 | pageKey | 说明 |
|------|---------|------|
| `decode/page.tsx` | `decode` | "use client" |
| `knowledge/batch/page.tsx` | `knowledge` | "use client" |
| `output/new/page.tsx` | `output` | "use client" |
| `output/[task_id]/[file]/page.tsx` | `output` | "use client" |

> 共 4 个 client 页面。ClientPageGuard 每次 mount 独立调 API，无缓存。

#### 特殊页面

| 页面 | 模式 | 说明 |
|------|------|------|
| `knowledge/page.tsx` | 直接 `allowed.includes("knowledge")` | redirect 页，不套 PageGuard，无权时返回 ForbiddenPage |
| `account/settings/page.tsx` | `getPermissions()` + 自定义鉴权 | 个人页，不适配 pageKey 体系，保持现有模式 |

#### 子组件中的 Guard

| 组件 | 模式 | 说明 |
|------|------|------|
| `admin/dicts/_components/admin-dicts-client.tsx` | "use client" 内嵌 `<PageGuard>` | 从 RSC parent 接收 `role`/`allowed` props，PageGuard 在 client 侧允许（同步组件，无 server-only 依赖） |

### 1.5 lib/auth/permission.ts vs permissions.ts 详细对比

**permission.ts（单数，保留）**：
```ts
getPermissions() → PermissionResult (extends PermissionData) {
  // 继承 PermissionData:
  role, accountId, allowed, pages,
  // 派生方法（server-only, 不可序列化）:
  isAdminLevel, isSuperAdmin,
  can(pageKey): boolean,     // 内建 super_admin bypass
  headers                    // 供后续 API 调用
}
```

**permission-types.ts（新增，纯类型文件）**：
```ts
PermissionData {
  role: string;
  accountId: number | null;
  allowed: string[];
  pages: PageMeta[];
}
```
此文件不含 `import "server-only"`，可被 client 组件安全引用。

**permissions.ts（复数，废弃）**：
```ts
getMyPermissions() → MyPermissions {
  role, allowed, pages,
  account_id                 // permission.ts/PermissionData 已有
}
```

**差异点**：
- `permission.ts` 含有 `headers` 字段（供后续 RSC 调后端 API）和派生方法（`can()`， `isAdminLevel`， `isSuperAdmin`）
- `permissions.ts` 含有 `account_id`（供 auth-store 使用）
- 两者都用了 React `cache()`，但 layout 用了底层 API 绕过了缓存

### 1.6 usePermissionsStore 当前状态

```ts
// 当前：自动 fetch，client 侧调 API
export const usePermissionsStore = create<PermissionsStore>((set) => ({
  fetch: async () => {
    const { getMyPermissions } = await import("@/lib/api/permissions");
    const data = await getMyPermissions();
    // 顺便写 auth-store
    if (data.account_id != null) useAuthStore.getState().setAccountId(data.account_id);
    set({ allowed: data.allowed, loaded: true, pages: data.pages, role: data.role });
  },
  // ...
}));

export const usePermissions = () => {
  // 自动触发 fetch（多次 render 重复调）
  if (!store.loaded) store.fetch();
  // ...
};
```

问题：
1. **重复 fetch**：每次卸载/重挂载都重新调 API
2. **竞态**：store 加载完成前渲染组件，先拿到 loaded=false，等 fetch 完才能用
3. **无关 RSC 数据**：layout 已经查过但被忽略

---

## 2. 架构

### 2.1 数据流（完整版）

```
HTTP 请求
  │
  ▼
layout.tsx (RSC)
  │  getPermissions() ← lib/auth/permission.ts (已 cache)
  │  ┌────────────────────────────────────────┐
  │  │ Header ← permissions (props)           │
  │  │ PermissionHydrate ← permissions        │
  │  │   ├─ usePermissionsStore.hydrate()     │
  │  │   └─ useAuthStore.setAccountId()       │
  │  └────────────────────────────────────────┘
  │
  ▼
子页面 (RSC)
  │  <GuardPage pageKey="xxx">   ← 内部调 getPermissions()，缓存命中
  │    <PageContent />
  │  </GuardPage>
  │
  ▼
子页面 ("use client")
  │  <GuardClient pageKey="xxx"> ← 读 usePermissionsStore，不 fetch
  │    <ClientContent />
  │  </GuardClient>
```

### 2.2 缓存共享

layout 和 GuardPage 都调 `getPermissions()`（RSC cached），只有第一次 hits API，后续复用缓存。
所有子页面共享 layout 的权限数据，0 额外 fetch。

---

## 3. 组件设计

### 3.1 GuardPage（RSC，新建）

```tsx
// components/auth/guard-page.tsx
import { type ReactNode } from "react";
import { getPermissions } from "@/lib/auth/permission";
import { forbidden } from "next/navigation";

export const GuardPage = async ({
  pageKey,
  children,
}: {
  pageKey: string;
  children: ReactNode;
}) => {
  const perm = await getPermissions();
  if (!perm.can(pageKey)) forbidden();
  return <>{children}</>;
};
```

**说明**：
- RSC async 组件，内部调 `getPermissions()`（已被 layout 的 cache 命中，不额外 API）
- 权限不足 → `forbidden()` → Next.js 403
- 页面使用：删掉 import `getMyPermissions` + `PageGuard` 封装，替换为 `<GuardPage>`
- 用 `forbidden()`（403）而非 `notFound()`（404）：语义准确，路由结构已在 bundle 中，没必要隐藏

### 3.2 PermissionHydrate（Client，新建）

```tsx
// components/auth/permission-hydrate.tsx
"use client";
import { useEffect, useRef } from "react";
import { useAuthStore } from "@/lib/store/auth-store";
import { usePermissionsStore } from "@/lib/hooks/use-permissions";
import type { PermissionData } from "@/lib/auth/permission-types";

export const PermissionHydrate = ({
  permissions,
}: {
  permissions: PermissionData;
}) => {
  const hydrate = usePermissionsStore((s) => s.hydrate);
  const prevKey = useRef("");

  useEffect(() => {
    // 只在数据真正变化时 hydrate（防 RSC 对象引用变化导致重复执行）
    const key = `${permissions.role}|${permissions.allowed.join(",")}`;
    if (prevKey.current === key) return;
    prevKey.current = key;

    hydrate(permissions);
    // accountId 无条件同步到 auth-store（包括 null，清除 persist 残留）
    useAuthStore.getState().setAccountId(permissions.accountId);
  }, [hydrate, permissions]);
  return null;
};
```

**说明**：
- 装在 layout.tsx，接收 `PermissionData`（纯字段，可序列化）
- 用 `useRef` 做浅比较：仅当 `role` 或 `allowed` 真正变化时才 re-hydrate
- 无条件调 `setAccountId()`（含传 `null`），避免 `auth-store persist` 残留陈旧 accountId
- 返回 null，不占渲染

### 3.3 usePermissionsStore（改造，hydration-only）

```ts
// lib/hooks/use-permissions.ts
import { create } from "zustand";
import type { PermissionData } from "@/lib/auth/permission-types";

interface PermissionsStoreData {
  role: string;
  accountId: number | null;
  allowed: string[];
  pages: { key: string; label_zh: string; label_en: string; path: string }[];
  loaded: boolean;
}

interface PermissionsStore extends PermissionsStoreData {
  hydrate: (data: PermissionData) => void;
}

export const usePermissionsStore = create<PermissionsStore>((set) => ({
  role: "user",
  accountId: null,
  allowed: [],
  pages: [],
  loaded: false,
  hydrate: (data) => {
    try {
      set({
        role: data.role,
        accountId: data.accountId ?? null,
        allowed: data.allowed,
        pages: data.pages,
        loaded: true,
      });
    } catch {
      // hydrate 失败时仍标记 loaded，避免 GuardClient 永远不触发
      set({ loaded: true });
    }
  },
}));

export const usePermissions = () => {
  const store = usePermissionsStore();
  return {
    allowed: store.allowed,
    can: (pageKey: string) =>
      store.role === "super_admin" || store.allowed.includes(pageKey),
    isAdminLevel: store.role !== "user",
    isSuperAdmin: store.role === "super_admin",
    loaded: store.loaded,
    pages: store.pages,
    role: store.role,
  };
};
```

**关键改动**：
- 删除 `fetch()` 方法 — 不再 client 侧调 API
- 改为纯 `hydrate()` — 从 RSC 接收 `PermissionData`
- `hydrate()` 包 try/catch：出错时仍设 `loaded: true`，避免 GuardClient 永远不触发 redirect
- `usePermissions()` 不再自动触发 fetch

### 3.4 类型系统：PermissionData + PermissionResult 双层设计

**关键修正**：`PermissionResult` 含有 `can()` 函数和 `headers` 对象，两者不可序列化。
从 RSC 传递到 `"use client"` 的 `PermissionHydrate` 时 React 会抛运行时错误，
且 `headers` 泄露服务端鉴权 token 到浏览器。
因此拆分为两层：

```ts
// lib/auth/permission-types.ts（纯类型，无 server-only import）
// 此文件可被 client 组件安全引用

export interface PageMeta {
  key: string;
  label_zh: string;
  label_en: string;
  path: string;
}

/** 可序列化的权限数据子集，跨 RSC→Client 边界传输 */
export interface PermissionData {
  role: string;
  accountId: number | null;
  allowed: string[];
  pages: PageMeta[];
}
```

```ts
// lib/auth/permission.ts（server-only，import "server-only"）
// PermissionResult 继承了可序列化字段 + 服务端方法

export interface PermissionResult extends PermissionData {
  isAdminLevel: boolean;
  isSuperAdmin: boolean;
  can: (pageKey: string) => boolean;
  headers: Record<string, string>;
}
```

**实现改动**：
- 新建 `lib/auth/permission-types.ts`，提取 `PageMeta` 和 `PermissionData`
- `getPermissions()` 从 API data 读取 `account_id` 并映射为 camelCase `accountId`
- 给 `getPermissions()` 加 try/catch：API 失败时返回默认 `PermissionResult`（`{ allowed: ["chat"], role: "user", accountId: null, pages: [] }`），确保 GuardPage 不崩溃
- layout.tsx 传给 `PermissionHydrate` 时，从 `PermissionResult` 提取 `PermissionData` 再传递：

```tsx
// layout.tsx
const perm = await getPermissions();
// 剥离函数/headers 再传给 client
const permData: PermissionData = {
  role: perm.role,
  accountId: perm.accountId,
  allowed: perm.allowed,
  pages: perm.pages,
};
// 也可直接从 API 原始返回中构造
```

**数据流**：
```
RSC getPermissions() → PermissionResult (含 can/headers)
  ├─ Header → PermissionResult (Server-side props, 无序列化问题)
  └─ PermissionHydrate → PermissionData (纯字段, 可序列化)
       └─ usePermissionsStore.hydrate()
```

### 3.5 GuardClient（新建，替代 ClientPageGuard）

```tsx
// components/auth/guard-client.tsx
"use client";
import { type ReactNode, useEffect } from "react";
import { usePermissions } from "@/lib/hooks/use-permissions";
// 项目规约：必须用 @/i18n/navigation，不可用 next/navigation（避免 307 重定向）
import { useRouter } from "@/i18n/navigation";

export const GuardClient = ({
  pageKey,
  children,
}: {
  pageKey: string;
  children: ReactNode;
}) => {
  const { can, loaded } = usePermissions();
  const router = useRouter();

  useEffect(() => {
    if (loaded && !can(pageKey)) {
      router.replace("/404");
    }
  }, [pageKey, can, loaded, router]);

  return <>{children}</>;
};
```

**跟 ClientPageGuard 的差异**：
- ❌ 不再 import `getMyPermissions` from `lib/api/permissions`（0 fetch）
- ❌ 不再有 `useRouterSafe` try/catch 包装（GuardClient 永远在 client component 内使用，Router 一定存在）
- ❌ 不再有 `cancelled` 标志和 `checked` state（不异步 fetch 了，无竞态）
- ✅ 用 `can(pageKey)` 而非 `allowed.includes(pageKey)`：super_admin 角色自动 bypass，不会被错误重定向
- ✅ 读 zustand store（已从 RSC hydrate）
- ✅ `loaded` 由 store 控制（RSC→hydrate 后变为 true，始终跟服务端一致）
- ✅ 用 `@/i18n/navigation` 的 useRouter（项目规约强制，避免 307 重定向 bug）

**重要**：GuardClient 是 UX 层防护。真正的安全边界在 GuardPage（RSC 403）。
Client 侧跳 404 是为了不给「闪一下内容」的体验。用户无法绕过 RSC 403。

### 3.6 现有 PageGuard 的处置

`components/page-guard.tsx`（同步，接受 props）**保留**：
- 用于 `admin-dicts-client.tsx` 这类 client 组件的场景（RSC 取到 role+allowed props 后在 client 侧二次防护）
- 它可从 `"use client"` 组件内使用（同步、无 server-only 依赖），这是其他选项无法替代的

**命名区分**：`PageGuard`（现有，同步 props）vs `GuardPage`（新建，RSC async 内部取数据）。
混淆风险可控：因为使用场景天然不同——RSC page.tsx 用 `GuardPage`，client 子组件用 `PageGuard`。
如果 `PageGuard` 最终只剩 `admin-dicts-client.tsx` 一个引用点，可考虑内联到该组件中彻底消除混淆。

### 3.7 组件选择指南

| 场景 | 使用的组件 |
|------|-----------|
| RSC page.tsx | `<GuardPage pageKey="xxx">` |
| "use client" page.tsx | `<GuardClient pageKey="xxx">` |
| Client 子组件（已从 RSC 拿到 props） | `<PageGuard ...>`（现有） |
| 无需 guard 的页面（login， register 等） | 什么也不用 |

---

## 4. Layout 改动

### 4.1 改动内容

```tsx
// app/[locale]/layout.tsx（改动部分）

// 旧:
import { getMyPermissions } from "@/lib/api/permissions";    // 移除
// ...
const permissions = await getMyPermissions();                  // 移除

// 新:
import { getPermissions } from "@/lib/auth/permission";       // RSC cached
import { PermissionHydrate } from "@/components/auth/permission-hydrate";
import type { PermissionData } from "@/lib/auth/permission-types";  // 新增
// ...
const perm = await getPermissions();   // 首次请求调用 API，后续子页面 cache 命中

// 剥离 server-only 字段再传给 client 组件
const permData: PermissionData = {
  role: perm.role,
  accountId: perm.accountId,
  allowed: perm.allowed,
  pages: perm.pages,
};

// 渲染部分：
<Header user={user} permissions={perm} />              // 传 PermissionResult（RSC → RSC props）
<PermissionHydrate permissions={permData} />            // 传 PermissionData（RSC → Client props）
<main>{children}</main>
```

### 4.2 Header 类型适配

`Header` 当前接收 `MyPermissions`（来自 `lib/auth/permissions`），改为接收 `PermissionResult`。
Header 在 layout 内渲染（RSC 侧），不存在序列化问题，可直接用完整的 `PermissionResult`。

```tsx
// components/layout/header.tsx
import type { PermissionResult } from "@/lib/auth/permission";  // 改 import

export const Header = ({
  user,
  permissions,
}: {
  user?: UserMenuUser | null;
  permissions: PermissionResult;  // 改类型
}) => {
  // permissions.pages 和 permissions.allowed 的字段名一致，代码不需要改
  const visibleNav = useMemo(
    () =>
      permissions.pages.filter(
        (pg) => pg.path && permissions.allowed.includes(pg.key),
      ),
    [permissions],
  );
  // ...
};
```

---

## 5. 迁移计划

### Phase 0：基础建设（无行为改动）

1. **新建 `lib/auth/permission-types.ts`**：提取 `PermissionData` + `PageMeta` 纯类型
2. **扩展 `PermissionResult`**：继承 `PermissionData`，加 `accountId` 字段
3. **改造 `getPermissions()`**：加 try/catch，加 `account_id` → `accountId` 映射，加 test 断言
4. **确认 `app/[locale]/forbidden.tsx` 存在**（`forbidden()` 所需的页面），不存在则新建
5. **改造 `usePermissionsStore`**：删除 fetch，加 hydrate（含 try/catch fallback）
6. **创建 `GuardPage`、`GuardClient`、`PermissionHydrate`**
7. **测试**：新组件单测先行

### Phase 1：Layout 桥接

1. layout.tsx 改用 `getPermissions()` + 加 `PermissionHydrate`
2. Header 类型从 `MyPermissions` 改为 `PermissionResult`
3. 验证：VRT / 手动检查导航菜单行为不变

### Phase 2：RSC 页面迁移（21 页）

每个子阶段后运行 `bun run test && bun run lint && bun run typecheck`，失败则 git reset 回退。

**子阶段 2a — knowledge 模块（7 页）**：
`knowledge/graph` / `triples` / `nodes` / `qa` / `relations` / `datasets` / `dataset-documents/[dataset_id]`
→ 迁移模式：删 getMyPermissions import + PageGuard 封装 → 替换为 `<GuardPage pageKey="knowledge">`
→ 测试文件：`knowledge/*/page.test.tsx`、`knowledge/documents/page.test.tsx`、`knowledge/documents/import/page.test.tsx`

**子阶段 2b — evaluate 模块（3 页）**：
`evaluate/page.tsx`（特殊：保留 `getPermissions()` 内部调用用于数据渲染）、`evaluate/[id]`、`evaluate/new`
→ 测试文件：`evaluate/page.test.tsx`、`evaluate/new/page.test.tsx`（mock `getPermissions` 替代 `getMyPermissions`）

**子阶段 2c — output 模块（2 页）**：
`output/page.tsx`、`output/[task_id]/page.tsx`
→ 测试文件：`output/new/page.test.tsx`、`output/[task_id]/[file]/page.test.tsx`

**子阶段 2d — 剩余 RSC 页（6 页）**：
`chat/page.tsx`（注意：保留 `serverAuthHeaders` 用于 /me，`getMyPermissions` 替换为 `getPermissions`）
`health/page.tsx`、`submissions/page.tsx`

**子阶段 2e — admin 模块（3 页）**：
`admin/users`、`admin/dicts`、`admin/permissions`、`admin/invites`
（已用 `lib/auth/permission` 单数版，只需 PageGuard → GuardPage + 保留 `getPermissions()` 数据调用）
→ 注意：`admin/dicts/_components/admin-dicts-client.tsx` 中的 `<PageGuard>` 保留不动（client 子组件模式）

### Phase 3：「use client」页面迁移（4 页）

1. `decode/page.tsx`：`<ClientPageGuard>` → `<GuardClient>`
2. `knowledge/batch/page.tsx`：同上
3. `output/new/page.tsx`：同上
4. `output/[task_id]/[file]/page.tsx`：同上

### Phase 4：清理

1. 删除 `components/client-page-guard.tsx`
2. 删除 `lib/auth/permissions.ts`（复数）（确认无引用后）
3. 更新 `components/auth/index.ts` 批量出口

---

## 6. 每个页面的迁移详情

### 6.1 RSC 页面批量替换模板

**替换前**（18 页通用模板）：
```tsx
import { getMyPermissions } from "@/lib/auth/permissions";
import { PageGuard } from "@/components/page-guard";

export default async function Page() {
  const permissions = await getMyPermissions();
  return (
    <PageGuard pageKey="xxx" permissions={permissions}>
      {/* content */}
    </PageGuard>
  );
}
```

**替换后**：
```tsx
import { GuardPage } from "@/components/auth/guard-page";

export default async function Page() {
  return (
    <GuardPage pageKey="xxx">
      {/* content */}
    </GuardPage>
  );
}
```

### 6.2 保留 `getPermissions()` 引用的页面

几页需要权限数据（非 guard 用途）：
- `chat/page.tsx`：需要 `serverAuthHeaders()` 调 /api/account/me
- `admin/users/page.tsx`：需要 `perm.headers` 调 /api/admin/users
- `admin/permissions/page.tsx`：需要 `perm.headers` 调 /api/permissions
- `admin/dicts/page.tsx`：需要 `perm.role` + `perm.allowed` 传子组件

这些页面在 GuardPage 内依然可调 `getPermissions()`（缓存命中）：
```tsx
export default async function AdminUsersPage() {
  const perm = await getPermissions();       // cache hit
  // 用 perm.headers, perm.isAdminLevel 等
  return (
    <GuardPage pageKey="admin">
      {/* ... */}
    </GuardPage>
  );
}
```

### 6.3 evaluate/page.tsx 特殊处理

该页用了 `permissions.allowed.includes("evaluate")` 控制数据渲染：
```tsx
const runsPromise = permissions.allowed.includes("evaluate")
  ? fetchEvaluationRuns()
  : undefined;
```
改为在 GuardPage 内部额外调 `getPermissions()` 保留此逻辑
（GuardPage 仅负责 guard，不感知数据需求）。

### 6.4 knowledge/page.tsx（redirect 页）

当前模式：
```tsx
const permissions = await getMyPermissions();
if (!permissions.allowed.includes("knowledge")) return <ForbiddenPage />;
redirect("/knowledge/documents");
```
改为：
```tsx
const perm = await getPermissions();
if (!perm.can("knowledge")) return <ForbiddenPage />;
redirect("/knowledge/documents");
```

### 6.5 account/settings/page.tsx（不迁移）

保持现有模式（个人页，不适配 pageKey 体系）。

---

## 7. 测试策略

### 7.1 新组件测试

| 组件 | 测试内容 | 测试方法 |
|------|---------|---------|
| `GuardPage` | 有权限 → render children；无权限 → 调 forbidden() | mock `getPermissions` + mock `next/navigation` |
| `PermissionHydrate` | hydrate 写 store、写 auth-store | mock store，验 useEffect 后 state |
| `GuardClient` | loaded + 有权限 → render；loaded + 无权限 → router.replace | mock store + mock next-intl router |
| `usePermissionsStore` | hydrate 后状态正确；初始值正确 | vitest 直接测 |

### 7.2 页面测试迁移

页面测试需更新（以下测试文件需同步迁移）：
- `evaluate/page.test.tsx` — mock `getPermissions` 替代 `getMyPermissions`
- `evaluate/new/page.test.tsx` — 同上
- `knowledge/*/page.test.tsx` 系列 — 同上
- `output/new/page.test.tsx` — 同上
- `output/[task_id]/[file]/page.test.tsx` — mock store 替代 `ClientPageGuard` mock
- `knowledge/batch/page.test.tsx` — 同上
- `admin/users/page.test.tsx` — 已用 `getPermissions` mock，只需调整 import 源

迁移步骤：
1. 删掉 mock `getMyPermissions`（不再在页面内调用）
2. GuardPage 的 mock 通过 mock `getPermissions` 实现（已有 `permission.test.ts` 模式）
3. ClientPageGuard 页面测试：转为 mock zustand store 设置 loaded=true + allowed

### 7.3 import guard 测试

参考现有 `login/page.test.tsx` 的 import guard 写法，新增测试：
- 禁止组件从 `lib/auth/permissions`（复数）import
- GuardClient 必须从 `@/i18n/navigation` import useRouter（禁止 `next/navigation`）
- 所有 `"use client"` 组件必须从 `lib/auth/permission-types` import `PermissionData`（禁止从 `lib/auth/permission` import 类型，后者含 server-only 依赖）

---

## 8. 边界情况 & 错误处理

### 8.1 getPermissions() 抛异常

`getPermissions()` 当前没有 try/catch（与复数版 `permissions.ts` 不同）。
**实现时必须在 `getPermissions()` 内加 try/catch**，失败时返回默认值并让调用者继续：

```ts
export const getPermissions = cache(async (): Promise<PermissionResult> => {
  try {
    const headers = await serverAuthHeaders();
    const data = await getMyPermissions(headers);
    return {
      role: data.role,
      accountId: data.account_id ?? null,
      allowed: data.allowed,
      pages: data.pages,
      isAdminLevel: data.role !== "user",
      isSuperAdmin: data.role === "super_admin",
      can: (pageKey: string) =>
        data.role === "super_admin" || data.allowed.includes(pageKey),
      headers,
    };
  } catch {
    // 默认只放行 chat、user 角色
    return {
      role: "user",
      accountId: null,
      allowed: ["chat"],
      pages: [],
      isAdminLevel: false,
      isSuperAdmin: false,
      can: (pageKey: string) => pageKey === "chat",
      headers: {},
    };
  }
});
```

GuardPage 调 `getPermissions()` 后，`can()` 在默认角色下只放行 `chat`，
其它 pageKey → `forbidden()`。不会再崩溃。

### 8.2 GuardClient loaded=false 时

初始状态 loaded=false，此时不跳转，直接渲染 children。
等 useEffect 检查时 loaded 可能已变为 true（layout 的 hydrate 已完成）。

**时序依赖**：React 18 useEffect 执行顺序按组件树深度先后：
PermissionHydrate（layout 层，较高）→ GuardClient（page 层，较深）。
因此 PermissionHydrate 的 effect 先执行 → hydrate store → store.loaded=true →
GuardClient 的 effect 后执行 → 读到 loaded=true → 正常检查。

如果 layout 从未 hydrate（如测试环境没跑 layout），loaded 一直 false → children 正常渲染但无 client 侧保护。
**测试环境下**：需 mock store 设置 loaded=true + 合适的 allowed。
**极端情况**：如果 API 极慢且 layout 比 page 先 hydrate 的假设被打破（React 18 目前保证，但未来不确定），
可在 GuardClient 加防御性 spinner：
```tsx
if (!loaded) return <div className="h-screen" />; // 或 Suspense fallback
```

### 8.3 client 侧 SPA 导航行为

| 场景 | 结果 |
|------|------|
| /chat（有权限）→ /admin（有权限） | store 已 loaded，GuardClient 瞬间通过，无闪烁 |
| /chat（有权限）→ /decode（无权限） | store 已 loaded，GuardClient 检查失败，跳 /404，无内容闪烁 |
| 首次直接访问 /decode | layout 先渲染 → hydrate store → GuardClient 检查 → 有权限则通过，无则跳 /404 |

### 8.4 和现有 4 层防护兼容

重构前：
1. /admin/* layout（未实现）
2. PageGuard（RSC）/ ClientPageGuard（client）
3. 后端端点鉴权
4. UI 隐藏（菜单不显示无权限入口）

重构后：
1. /admin/* layout（未实现）
2. **GuardPage（RSC）** / GuardClient（client）
3. 后端端点鉴权
4. UI 隐藏（Header 从 store 读 pages）

安全级别不变。

---

## 9. 安全考量

1. **RSC GuardPage 是真正的安全边界**：在服务器端拦截，用户无法绕过
2. **GuardClient 仅是 UX 优化**：只在 client 侧跳转，用户可通过 devtools 禁用 JS 绕过，但 RSC 层仍会 403
3. **永远不要只用 GuardClient 保护敏感页面**：所有敏感路由必须同时用 GuardPage（RSC）
4. **403 vs 404**：用 `forbidden()` 而非 `notFound()`。不暴露「页面是否存在」不是安全需求（路由结构已暴露在 bundle 中），语义准确更重要

---

## 10. 依赖关系

```
Phase 0 ───────────────────────────────────────
  ├─ 新建 permission-types.ts (PermissionData)
  ├─ 扩展 PermissionResult (继承 PermissionData + accountId)
  ├─ 改造 getPermissions() (try/catch + accountId 映射)
  ├─ 确认 forbidden.tsx 存在
  ├─ 改造 usePermissionsStore (hydration-only + try/catch)
  ├─ 创建 GuardPage 组件
  ├─ 创建 PermissionHydrate 组件
  ├─ 创建 GuardClient 组件
  └─ 所有新组件的测试
        │
Phase 1 ───────────────────────────────────────
  ├─ layout.tsx: 改用 getPermissions()
  ├─ layout.tsx: 添加 PermissionHydrate (传 PermissionData)
  └─ Header: 类型适配 PermissionResult
        │
Phase 2 ───────────────────────────────────────
  ├─ 21 个 RSC 页面迁移 (PageGuard → GuardPage)
  ├─ 4 个 admin/* 页面适配
  ├─ evaluate/page.tsx 数据逻辑调整
  └─ knowledge/page.tsx redirect 适配
        │
Phase 3 ───────────────────────────────────────
  └─ 4 个 client 页面迁移 (ClientPageGuard → GuardClient)
        │
Phase 4 ───────────────────────────────────────
  ├─ 删除 client-page-guard.tsx
  ├─ 删除 lib/auth/permissions.ts (复数)
  ├─ 更新 components/auth/index.ts
  └─ 验证全量 vitest 通过
```

---

## 11. 废弃计划

### components/auth/index.ts 批量出口

Phase 4 更新批量出口为：
```ts
export { GuardPage } from "./guard-page";
export { GuardClient } from "./guard-client";
export { PermissionHydrate } from "./permission-hydrate";
// 保留现有
export * from "./auth-bootstrap";
```

### lib/auth/permissions.ts（复数）

**废弃原因**：与 `lib/auth/permission.ts`（单数）功能重叠。单数版拥有更多派生方法且已是 admin 3 页的选择。

**步骤**：
1. Phase 2 迁移 RSC 页面不再引用
2. Phase 3 确认 Header 已改用 PermissionResult
3. 删除前全局 grep 确认无引用
4. 一次删除

### components/client-page-guard.tsx

**废弃原因**：被 GuardClient 替代。

**步骤**：
1. Phase 3 迁移 4 个 client 页面
2. 删除前全局 grep 确认无引用
3. 一次删除

---

## 12. 风险 & 缓解

| 风险 | 影响 | 缓解 |
|------|------|------|
| `getPermissions()` 被 22 页同时调，API 负载雪崩 | 高 | `cache()` 确保只有 layout 触发一次 API，其余 cache hit |
| `PermissionData` 跨 RSC→Client 边界序列化 | 高 | 已拆分出 `PermissionData`（纯字段）+ `PermissionResult`（含 can/headers），client 组件只接收 `PermissionData` |
| `forbidden()` 没有对应的 `forbidden.tsx` 页面 | 高 | **Phase 0 必须确认** `app/[locale]/forbidden.tsx` 存在。如果不存在，需在 `app/[locale]/forbidden.tsx` 创建与项目风格匹配的 403 页面 |
| Phase 2 一次性改 18 页，回归风险 | 中 | 按 5 个子阶段（knowledge → evaluate → output → 其他 → admin）分步，每阶段后跑 `bun run test && bun run lint && bun run typecheck` |
| `permissions.ts`（复数）的 account_id 在迁移中丢失 | 中 | `getPermissions()` 返回的 `PermissionResult` 含 `accountId` 字段，`PermissionData` 继承此字段 |
| Header 依赖 `MyPermissions` 改为 `PermissionData`，字段结构变化 | 低 | 两个类型 pages/allowed 字段名一致，只需改 import 行 |
| `auth-store` persist 残留陈旧 accountId | 高 | `PermissionHydrate` 无条件调 `setAccountId(permissions.accountId)`（含 null），已修复 |
| `knowledge/page.tsx` 返回 `<ForbiddenPage />`（client 组件）的兼容性 | 低 | 确认当前 Next.js 版本支持 RSC 直接返回 client 组件；如不支持，改为 `redirect("/forbidden")` |

---

## 13. 架构图（最终状态）

```
                    HTTP 请求
                        │
                        ▼
              ┌─────────────────┐
              │   layout.tsx    │
              │  getPermissions │──→ /api/permissions/me (1x, cache)
              └────┬────────────┘
                   │
          ┌────────┼────────────┐
          ▼        ▼            ▼
    ┌─────────┐ ┌────────┐ ┌──────────┐
    │  Header  │ │GuardPage│ │Permission│
    │ (props)  │ │ (403)   │ │ Hydrate  │
    └─────────┘ └────────┘ └────┬─────┘
                                │
                    ┌───────────▼───────────┐
                    │  Zustand Store        │
                    │  usePermissionsStore  │
                    └───┬───────────┬───────┘
                        │           │
                        ▼           ▼
                  ┌──────────┐ ┌──────────┐
                  │GuardClient│ │usePermis-│
                  │(redirect) │ │sions()   │
                  └──────────┘ └────┬─────┘
                                    │
                        ┌───────────▼───────────┐
                        │  业务 Components      │
                        │  (导航/按钮/数据渲染)  │
                        └───────────────────────┘
```
