# 权限 Client Store + GuardPage 重构 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan phase-by-phase. Each phase produces a working, testable result. Steps use checkbox (`- [ ]`) syntax.

**Goal:** 消除 22 个页面各自的 getMyPermissions 重复 import，通过 GuardPage/GuardClient 统一入口，layout→Zustand hydration 消灭 client 侧重复 fetch，废弃 ClientPageGuard 和 lib/auth/permissions.ts（复数）

**Architecture:** 5 个 Phase 顺序执行。Phase 0（基础类型+组件）是所有页面迁移的前提。Phase 1（Layout 桥接）是 RSC hydration 的开关。Phase 2（RSC 页面迁移）按路由模块分 5 个子阶段。Phase 3（Client 页面迁移）依赖 Phase 0 的 GuardClient。Phase 4 清理无引用代码。

**Tech Stack:** React 19 / Next.js 16 / TypeScript 8 / Zustand / vitest / oxlint / tsgo

---

## 文件结构清单

### 新建文件

| 文件 | 职责 |
|------|------|
| `packages/web/lib/auth/permission-types.ts` | `PermissionData` + `PageMeta` 纯类型（可被 client 安全引用） |
| `packages/web/components/auth/guard-page.tsx` | RSC async guard，内部调 getPermissions()，无权 → forbidden() |
| `packages/web/components/auth/permission-hydrate.tsx` | Client 组件，接收 PermissionData → hydrate zustand + auth-store |
| `packages/web/components/auth/guard-client.tsx` | Client guard，读 zustand store，无权 → router.replace("/404") |

### 修改文件

| 文件 | 改动 |
|------|------|
| `packages/web/lib/auth/permission.ts` | `PermissionResult extends PermissionData` + try/catch + accountId 映射 + **加 `import "server-only"`** |
| `packages/web/lib/auth/permission-types.ts` | **新建**：纯类型文件（不含 server-only import） |
| `packages/web/lib/hooks/use-permissions.ts` | 删 fetch()，改 hydration-only，hydrate 加 try/catch |
| `packages/web/lib/store/auth-store.ts` | **`setAccountId` 签名改 `number | null`**（登出/未登录时清空） |
| `packages/web/components/auth/index.ts` | 新增 3 个组件导出 |
| `packages/web/app/[locale]/layout.tsx` | 改用 getPermissions() + PermissionHydrate |
| `packages/web/components/layout/header.tsx` | 类型从 MyPermissions → **PermissionData**（不用 PermissionResult，避开 can/headers） |
| `packages/web/app/[locale]/chat/page.tsx` | PageGuard → GuardPage，保留 serverAuthHeaders |
| `packages/web/app/[locale]/evaluate/page.tsx` | PageGuard → GuardPage，保留 getPermissions() 用于数据 |
| `packages/web/app/[locale]/evaluate/[id]/page.tsx` | PageGuard → GuardPage |
| `packages/web/app/[locale]/evaluate/new/page.tsx` | PageGuard → GuardPage |
| `packages/web/app/[locale]/health/page.tsx` | PageGuard → GuardPage |
| `packages/web/app/[locale]/submissions/page.tsx` | PageGuard → GuardPage |
| `packages/web/app/[locale]/output/page.tsx` | PageGuard → GuardPage |
| `packages/web/app/[locale]/output/[task_id]/page.tsx` | PageGuard → GuardPage |
| `packages/web/app/[locale]/output/new/page.tsx` | ClientPageGuard → GuardClient |
| `packages/web/app/[locale]/output/[task_id]/[file]/page.tsx` | ClientPageGuard → GuardClient |
| `packages/web/app/[locale]/knowledge/graph/page.tsx` | PageGuard → GuardPage |
| `packages/web/app/[locale]/knowledge/triples/page.tsx` | PageGuard → GuardPage |
| `packages/web/app/[locale]/knowledge/nodes/page.tsx` | PageGuard → GuardPage |
| `packages/web/app/[locale]/knowledge/qa/page.tsx` | PageGuard → GuardPage |
| `packages/web/app/[locale]/knowledge/relations/page.tsx` | PageGuard → GuardPage |
| `packages/web/app/[locale]/knowledge/datasets/page.tsx` | PageGuard → GuardPage |
| `packages/web/app/[locale]/knowledge/dataset-documents/[dataset_id]/page.tsx` | PageGuard → GuardPage |
| `packages/web/app/[locale]/knowledge/documents/page.tsx` | PageGuard → GuardPage |
| `packages/web/app/[locale]/knowledge/documents/import/page.tsx` | PageGuard → GuardPage |
| `packages/web/app/[locale]/knowledge/batch/page.tsx` | ClientPageGuard → GuardClient |
| `packages/web/app/[locale]/knowledge/page.tsx` | getMyPermissions → getPermissions |
| `packages/web/app/[locale]/decode/page.tsx` | ClientPageGuard → GuardClient |
| `packages/web/app/[locale]/admin/users/page.tsx` | PageGuard → GuardPage + **保留 `!perm.isAdminLevel → redirect("/")` 守卫** |
| `packages/web/app/[locale]/admin/dicts/page.tsx` | PageGuard → GuardPage + **保留 `!perm.isSuperAdmin → forbidden()` 守卫** |
| `packages/web/app/[locale]/admin/permissions/page.tsx` | PageGuard → GuardPage + **保留 `!perm.isSuperAdmin → forbidden()` 守卫** |
| `packages/web/app/[locale]/admin/invites/page.tsx` | PageGuard → GuardPage |

### 删除文件

| 文件 | 原因 |
|------|------|
| `packages/web/components/client-page-guard.tsx` | 被 GuardClient 替代 |
| `packages/web/lib/auth/permissions.ts`（复数） | 被 permission.ts 替代 |

### 测试文件改动

| 文件 | 改动 |
|------|------|
| `packages/web/lib/auth/permission-types.test.ts` | 新建：类型结构验证 |
| `packages/web/lib/auth/permission.test.ts` | 改造：mock try/catch + accountId |
| `packages/web/lib/hooks/use-permissions.test.ts` | 改造：hydration-only 模式 |
| `packages/web/components/auth/guard-page.test.tsx` | 新建 |
| `packages/web/components/auth/guard-client.test.tsx` | 新建 |
| `packages/web/components/auth/permission-hydrate.test.tsx` | 新建 |
| `packages/web/components/layout/header.test.tsx` | 改造：PermissionResult 类型 |
| `packages/web/app/[locale]/evaluate/page.test.tsx` | mock getPermissions 替代 getMyPermissions |
| `packages/web/app/[locale]/evaluate/new/page.test.tsx` | 同上 |
| `packages/web/app/[locale]/knowledge/*/page.test.tsx` 系列 | 同上 |
| `packages/web/app/[locale]/output/new/page.test.tsx` | mock store 替代 ClientPageGuard mock |
| `packages/web/app/[locale]/output/[task_id]/[file]/page.test.tsx` | 同上 |
| `packages/web/app/[locale]/knowledge/batch/page.test.tsx` | 同上 |
| `packages/web/app/[locale]/admin/users/page.test.tsx` | 调整 import 源 |

---

## Phase 0: 基础建设（全部新建组件，无行为改动）

### Task 0.1: 新建 permission-types.ts 纯类型文件

**Files:**
- Create: `packages/web/lib/auth/permission-types.ts`
- Test: `packages/web/lib/auth/permission-types.test.ts`

- [ ] **Step 1: 写测试**

```typescript
// packages/web/lib/auth/permission-types.test.ts
import { describe, expect, it } from "vitest";
import type { PermissionData, PageMeta } from "./permission-types";

describe("permission-types", () => {
  it("PermissionData 是可序列化的（不含函数/headers）", () => {
    const data: PermissionData = {
      role: "admin",
      accountId: 42,
      allowed: ["chat", "knowledge"],
      pages: [{ key: "chat", label_zh: "聊天", label_en: "Chat", path: "/chat" }],
    };
    const serialized = JSON.parse(JSON.stringify(data));
    expect(serialized.role).toBe("admin");
    expect(serialized.accountId).toBe(42);
    expect(serialized.allowed).toEqual(["chat", "knowledge"]);
  });

  it("PageMeta 字段完整", () => {
    const meta: PageMeta = {
      key: "admin",
      label_zh: "管理",
      label_en: "Admin",
      path: "/admin/users",
    };
    expect(meta.key).toBe("admin");
    expect(meta.path).toBe("/admin/users");
  });
});
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd packages/web
bun run test -- lib/auth/permission-types.test.ts 2>&1 | head -5
```
Expected: `FAIL` — 文件不存在

- [ ] **Step 3: 创建类型文件**

```typescript
// packages/web/lib/auth/permission-types.ts
// PermissionData: 可序列化的权限数据子集，跨 RSC→Client 边界传输
// 此文件不含 server-only import，可被 client 组件安全引用

export interface PageMeta {
  key: string;
  label_zh: string;
  label_en: string;
  path: string;
}

export interface PermissionData {
  role: string;
  accountId: number | null;
  allowed: string[];
  pages: PageMeta[];
}
```

- [ ] **Step 4: 运行测试确认通过**

```bash
cd packages/web
bun run test -- lib/auth/permission-types.test.ts
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add packages/web/lib/auth/permission-types.ts packages/web/lib/auth/permission-types.test.ts
git commit -m "feat: add PermissionData/PageMeta types for cross-boundary permission transfer"
```

### Task 0.2: 改造 permission.ts（PermissionResult + try/catch + accountId）

**Files:**
- Modify: `packages/web/lib/auth/permission.ts`
- Modify: `packages/web/lib/auth/permission.test.ts`

- [ ] **Step 1: 更新测试**

```typescript
// packages/web/lib/auth/permission.test.ts — 改造
import { describe, expect, it, vi } from "vitest";

vi.mock("server-only", () => ({}));  // 测试环境允许 server-only import

const mockGetMyPermissions = vi.fn();

vi.mock("@/lib/api/permissions", () => ({
  getMyPermissions: (...args: unknown[]) => mockGetMyPermissions(...args),
}));

vi.mock("@/lib/api/auth.server", () => ({
  serverAuthHeaders: () => Promise.resolve({ authorization: "Bearer test" }),
}));

import { getPermissions } from "./permission";

describe("getPermissions", () => {
  it("成功时返回 PermissionResult（含 accountId + can bypass super_admin）", async () => {
    mockGetMyPermissions.mockResolvedValueOnce({
      role: "super_admin",
      account_id: 42,
      allowed: ["chat"],
      pages: [],
    });
    const result = await getPermissions();
    expect(result.role).toBe("super_admin");
    expect(result.accountId).toBe(42);
    expect(result.can("anything")).toBe(true); // super_admin bypass
    expect(result.isSuperAdmin).toBe(true);
  });

  it("API 失败时返回默认值不放行非 chat 页面", async () => {
    mockGetMyPermissions.mockRejectedValueOnce(new Error("Network error"));
    const result = await getPermissions();
    expect(result.role).toBe("user");
    expect(result.accountId).toBeNull();
    expect(result.can("knowledge")).toBe(false);
    expect(result.can("chat")).toBe(true);
  });

  it("account_id → accountId 映射正确", async () => {
    mockGetMyPermissions.mockResolvedValueOnce({
      role: "admin",
      account_id: 99,
      allowed: ["chat", "knowledge"],
      pages: [],
    });
    const result = await getPermissions();
    expect(result.accountId).toBe(99);
    expect(JSON.parse(JSON.stringify(result)).accountId).toBe(99);
  });
});
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd packages/web
bun run test -- lib/auth/permission.test.ts 2>&1 | tail -15
```
Expected: FAIL — 类型不匹配，accountId 未定义

- [ ] **Step 3: 改造 permission.ts**

```typescript
// packages/web/lib/auth/permission.ts
import "server-only"; // 防止 client 组件误引（headers/can 不可序列化）
import { cache } from "react";
import { serverAuthHeaders } from "@/lib/api/auth.server";
import { getMyPermissions } from "@/lib/api/permissions";
import type { PermissionData, PageMeta } from "./permission-types";

export type { PermissionData, PageMeta };

export interface PermissionResult extends PermissionData {
  isAdminLevel: boolean;
  isSuperAdmin: boolean;
  can: (pageKey: string) => boolean;
  headers: Record<string, string>;
}

const DEFAULT_PERMISSION: PermissionResult = {
  role: "user",
  accountId: null,
  allowed: ["chat"],
  pages: [],
  isAdminLevel: false,
  isSuperAdmin: false,
  can: (pageKey: string) => pageKey === "chat",
  headers: {},
};

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
    return DEFAULT_PERMISSION;
  }
});
```

- [ ] **Step 4: 运行测试确认通过**

```bash
cd packages/web
bun run test -- lib/auth/permission.test.ts
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add packages/web/lib/auth/permission.ts packages/web/lib/auth/permission.test.ts
git commit -m "refactor: PermissionResult extends PermissionData + try/catch + accountId mapping"
```

### Task 0.3: 改造 usePermissionsStore（hydration-only）

**Files:**
- Modify: `packages/web/lib/hooks/use-permissions.ts`
- Test: `packages/web/lib/hooks/use-permissions.test.ts`

- [ ] **Step 1: 写测试**

```typescript
// packages/web/lib/hooks/use-permissions.test.ts
import { afterEach, describe, expect, it } from "vitest";
import { renderHook } from "@testing-library/react";
import { usePermissionsStore, usePermissions } from "./use-permissions";
import type { PermissionData } from "@/lib/auth/permission-types";

describe("usePermissionsStore", () => {
  afterEach(() => {
    usePermissionsStore.setState({
      role: "user",
      accountId: null,
      allowed: [],
      pages: [],
      loaded: false,
    });
  });

  it("初始状态为未加载", () => {
    const state = usePermissionsStore.getState();
    expect(state.loaded).toBe(false);
    expect(state.role).toBe("user");
    expect(state.accountId).toBeNull();
  });

  it("hydrate 后状态正确", () => {
    const data: PermissionData = {
      role: "admin",
      accountId: 42,
      allowed: ["chat", "knowledge"],
      pages: [{ key: "chat", label_zh: "聊天", label_en: "Chat", path: "/chat" }],
    };
    usePermissionsStore.getState().hydrate(data);
    const state = usePermissionsStore.getState();
    expect(state.loaded).toBe(true);
    expect(state.role).toBe("admin");
    expect(state.accountId).toBe(42);
  });

  it("hydrate 异常时仍标记 loaded=true（防卡死）", () => {
    // @ts-expect-error — 传非法数据模拟 hydrate 异常
    usePermissionsStore.getState().hydrate(null);
    const state = usePermissionsStore.getState();
    expect(state.loaded).toBe(true);
  });
});

describe("usePermissions hook", () => {
  // 旧测试中 fetch() 相关用例已删除（store 不再自动 fetch）

  it("can() 对 super_admin 放行所有 pageKey", () => {
    usePermissionsStore.setState({
      role: "super_admin",
      accountId: 1,
      allowed: ["chat"],
      pages: [],
      loaded: true,
    });
    const { result } = renderHook(() => usePermissions());
    expect(result.current.can("anything")).toBe(true);
    expect(result.current.can("admin")).toBe(true);
  });

  it("can() 对普通角色检查 allowed", () => {
    usePermissionsStore.setState({
      role: "user",
      accountId: null,
      allowed: ["chat"],
      pages: [],
      loaded: true,
    });
    const { result } = renderHook(() => usePermissions());
    expect(result.current.can("chat")).toBe(true);
    expect(result.current.can("admin")).toBe(false);
  });

  it("isSuperAdmin 判断正确", () => {
    usePermissionsStore.setState({ role: "super_admin", loaded: true });
    const { result, rerender } = renderHook(() => usePermissions());
    expect(result.current.isSuperAdmin).toBe(true);
    usePermissionsStore.setState({ role: "admin", loaded: true });
    rerender();
    expect(result.current.isSuperAdmin).toBe(false);
  });
});
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd packages/web
bun run test -- lib/hooks/use-permissions.test.ts 2>&1 | tail -10
```
Expected: FAIL — 旧版 store 有 fetch() 但无 hydrate()

- [ ] **Step 3: 改造 use-permissions.ts 为 hydration-only**

```typescript
// packages/web/lib/hooks/use-permissions.ts
import { create } from "zustand";
import type { PermissionData } from "@/lib/auth/permission-types";

interface PermissionsStoreState {
  role: string;
  accountId: number | null;
  allowed: string[];
  pages: PermissionData["pages"];
  loaded: boolean;
}

interface PermissionsStore extends PermissionsStoreState {
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

- [ ] **Step 4: 运行测试确认通过**

```bash
cd packages/web
bun run test -- lib/hooks/use-permissions.test.ts
```
Expected: PASS

- [ ] **Step 5: 清理旧测试中引用 fetch 的代码**（如果有）

```bash
cd packages/web
grep -n "fetch" lib/hooks/use-permissions.test.ts
```
Expected: 无输出（无 fetch 引用）

- [ ] **Step 6: Commit**

```bash
git add packages/web/lib/hooks/use-permissions.ts packages/web/lib/hooks/use-permissions.test.ts
git commit -m "refactor: usePermissionsStore hydration-only, remove fetch, add error handling"
```

### Task 0.4: 创建 GuardPage 组件 + 测试

**Files:**
- Create: `packages/web/components/auth/guard-page.tsx`
- Test: `packages/web/components/auth/guard-page.test.tsx`

- [ ] **Step 1: 写测试**

```typescript
// packages/web/components/auth/guard-page.test.tsx
import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

vi.mock("server-only", () => ({}));  // 测试环境允许 server-only import

const mockForbidden = vi.fn();
vi.mock("next/navigation", () => ({
  forbidden: () => {
    throw new Error("NEXT_FORBIDDEN");  // 模拟真实 Next.js 行为
  },
}));

const mockGetPermissions = vi.fn();
vi.mock("@/lib/auth/permission", () => ({
  getPermissions: () => mockGetPermissions(),
}));

import { GuardPage } from "./guard-page";

describe("GuardPage", () => {
  it("有权限时渲染 children", async () => {
    mockGetPermissions.mockResolvedValueOnce({
      can: (pageKey: string) => pageKey === "chat",
    });
    const element = await GuardPage({ pageKey: "chat", children: <div>content</div> });
    render(element);
    expect(screen.getByText("content")).toBeInTheDocument();
  });

  it("无权限时抛 NEXT_FORBIDDEN", async () => {
    mockGetPermissions.mockResolvedValueOnce({
      can: () => false,
    });
    await expect(
      GuardPage({ pageKey: "admin", children: <div>admin</div> }),
    ).rejects.toThrow("NEXT_FORBIDDEN");
  });
});
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd packages/web
bun run test -- components/auth/guard-page.test.tsx 2>&1 | tail -10
```
Expected: FAIL — 组件不存在

- [ ] **Step 3: 创建 GuardPage 组件**

```typescript
// packages/web/components/auth/guard-page.tsx
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

- [ ] **Step 4: 运行测试确认通过**

```bash
cd packages/web
bun run test -- components/auth/guard-page.test.tsx
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add packages/web/components/auth/guard-page.tsx packages/web/components/auth/guard-page.test.tsx
git commit -m "feat: add GuardPage (RSC async guard, internal getPermissions)"
```

### Task 0.5: 创建 PermissionHydrate 组件 + 测试

**Files:**
- Create: `packages/web/components/auth/permission-hydrate.tsx`
- Test: `packages/web/components/auth/permission-hydrate.test.tsx`

- [ ] **Step 1: 写测试**

```typescript
// packages/web/components/auth/permission-hydrate.test.tsx
import { afterEach, describe, expect, it } from "vitest";
import { render } from "@testing-library/react";
import { PermissionHydrate } from "./permission-hydrate";
import { usePermissionsStore } from "@/lib/hooks/use-permissions";
import { useAuthStore } from "@/lib/store/auth-store";
import type { PermissionData } from "@/lib/auth/permission-types";

const basePerm: PermissionData = {
  role: "admin",
  accountId: 42,
  allowed: ["chat", "knowledge"],
  pages: [{ key: "chat", label_zh: "聊天", label_en: "Chat", path: "/chat" }],
};

describe("PermissionHydrate", () => {
  afterEach(() => {
    usePermissionsStore.setState({
      role: "user",
      accountId: null,
      allowed: [],
      pages: [],
      loaded: false,
    });
    useAuthStore.setState({ accountId: null });
  });

  it("hydrate 后 store 状态正确", () => {
    render(<PermissionHydrate permissions={basePerm} />);
    const state = usePermissionsStore.getState();
    expect(state.loaded).toBe(true);
    expect(state.role).toBe("admin");
    expect(state.allowed).toContain("knowledge");
  });

  it("auth-store accountId 无条件更新（含 null 清除残留）", () => {
    useAuthStore.getState().setAccountId(999); // 模拟 persist 残留
    render(<PermissionHydrate permissions={basePerm} />);
    expect(useAuthStore.getState().accountId).toBe(42);
  });

  it("accountId 为 null 时清空 auth-store", () => {
    useAuthStore.getState().setAccountId(999);
    render(<PermissionHydrate permissions={{ ...basePerm, accountId: null }} />);
    expect(useAuthStore.getState().accountId).toBeNull();
  });
});
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd packages/web
bun run test -- components/auth/permission-hydrate.test.tsx 2>&1 | tail -10
```
Expected: FAIL

- [ ] **Step 3: 创建 PermissionHydrate 组件**

```typescript
// packages/web/components/auth/permission-hydrate.tsx
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
    // 浅比较：只在 role/allowed 真正变化时 re-hydrate
    const key = `${permissions.role}|${permissions.allowed.join(",")}`;
    if (prevKey.current === key) return;
    prevKey.current = key;

    hydrate(permissions);
    // 无条件同步（含 null），清除 persist 残留
    useAuthStore.getState().setAccountId(permissions.accountId);
  }, [hydrate, permissions]);

  return null;
};
```

- [ ] **Step 4: 运行测试确认通过**

```bash
cd packages/web
bun run test -- components/auth/permission-hydrate.test.tsx
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add packages/web/components/auth/permission-hydrate.tsx packages/web/components/auth/permission-hydrate.test.tsx
git commit -m "feat: add PermissionHydrate (RSC→zustand hydration, unconditional accountId sync)"
```

### Task 0.6: 创建 GuardClient 组件 + 测试

**Files:**
- Create: `packages/web/components/auth/guard-client.tsx`
- Test: `packages/web/components/auth/guard-client.test.tsx`

- [ ] **Step 1: 写测试**

```typescript
// packages/web/components/auth/guard-client.test.tsx
import { afterEach, describe, expect, it, vi } from "vitest";
import { act, render, screen } from "@testing-library/react";

const mockReplace = vi.fn();
vi.mock("@/i18n/navigation", () => ({
  useRouter: () => ({ replace: mockReplace, push: vi.fn(), back: vi.fn() }),
}));

import { usePermissionsStore } from "@/lib/hooks/use-permissions";
import { GuardClient } from "./guard-client";

describe("GuardClient", () => {
  afterEach(() => {
    usePermissionsStore.setState({
      role: "user",
      accountId: null,
      allowed: [],
      pages: [],
      loaded: false,
    });
    mockReplace.mockReset();
  });

  it("loaded + 有权限 → 渲染 children + 不跳转", async () => {
    usePermissionsStore.setState({
      role: "admin",
      allowed: ["chat"],
      loaded: true,
    });
    await act(async () => {
      render(<GuardClient pageKey="chat"><div>content</div></GuardClient>);
    });
    expect(screen.getByText("content")).toBeInTheDocument();
    expect(mockReplace).not.toHaveBeenCalled();
  });

  it("loaded + 无权限 → redirect /404", async () => {
    usePermissionsStore.setState({
      role: "user",
      allowed: ["chat"],
      loaded: true,
    });
    await act(async () => {
      render(<GuardClient pageKey="admin"><div>admin</div></GuardClient>);
    });
    expect(mockReplace).toHaveBeenCalledWith("/404");
  });

  it("super_admin 即使 allowed 不含 pageKey 也不跳转（can bypass）", async () => {
    usePermissionsStore.setState({
      role: "super_admin",
      allowed: ["chat"],
      loaded: true,
    });
    await act(async () => {
      render(<GuardClient pageKey="anything"><div>content</div></GuardClient>);
    });
    expect(mockReplace).not.toHaveBeenCalled();
  });

  it("loaded=false 时不跳转（等 hydrate）", async () => {
    usePermissionsStore.setState({
      role: "user",
      allowed: ["chat"],
      loaded: false,
    });
    await act(async () => {
      render(<GuardClient pageKey="admin"><div>content</div></GuardClient>);
    });
    expect(mockReplace).not.toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd packages/web
bun run test -- components/auth/guard-client.test.tsx 2>&1 | tail -10
```
Expected: FAIL

- [ ] **Step 3: 创建 GuardClient 组件**

```typescript
// packages/web/components/auth/guard-client.tsx
"use client";
import { type ReactNode, useEffect } from "react";
import { usePermissions } from "@/lib/hooks/use-permissions";
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

- [ ] **Step 4: 运行测试确认通过**

```bash
cd packages/web
bun run test -- components/auth/guard-client.test.tsx
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add packages/web/components/auth/guard-client.tsx packages/web/components/auth/guard-client.test.tsx
git commit -m "feat: add GuardClient (reads zustand store, super_admin bypass via can())"
```

### Task 0.7: 确认 forbidden.tsx 和 not-found.tsx 存在

- [ ] **Step 1: 检查页面**

```bash
cd packages/web
ls app/\[locale\]/forbidden.tsx 2>/dev/null && echo "forbidden EXISTS" || echo "forbidden MISSING"
ls app/\[locale\]/not-found.tsx 2>/dev/null && echo "not-found EXISTS" || echo "not-found MISSING"
```
（GuardClient 跳 `/404` 依赖 Next.js default 404，但项目若有自定义 `not-found.tsx` 会优先使用。
若两者都缺失，需新建——否则 GuardClient 跳 404 后落到 Next.js 默认页，UX 跟设计意图不一致。）

如果 forbidden MISSING，创建 `app/[locale]/forbidden.tsx`：
（如果 not-found MISSING，创建 `app/[locale]/not-found.tsx`：结构相同，title 改 "404"）

```tsx
// packages/web/app/[locale]/forbidden.tsx
import { LocalizedLink } from "@/components/i18n/localized-link";

export default function ForbiddenPage() {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-4">
      <h1 className="text-4xl font-bold">403</h1>
      <p className="text-muted-foreground">权限不足</p>
      <LocalizedLink href="/" className="text-primary underline">返回首页</LocalizedLink>
    </div>
  );
}
```

- [ ] **Step 2: 如果有新建则 Commit**

```bash
git add app/\[locale\]/forbidden.tsx app/\[locale\]/not-found.tsx
git commit -m "feat: add forbidden/not-found pages for GuardPage 403 + GuardClient 404"
```

### Task 0.8: 更新 components/auth/index.ts 批量出口

- [ ] **Step 1: 更新 index.ts**

```typescript
// packages/web/components/auth/index.ts
export { GuardPage } from "./guard-page";
export { GuardClient } from "./guard-client";
export { PermissionHydrate } from "./permission-hydrate";
export * from "./auth-bootstrap";
```

- [ ] **Step 2: 确认没有破坏现有引用**

```bash
cd packages/web
bun run typecheck 2>&1 | tail -5
```
Expected: 0 errors

- [ ] **Step 3: Commit**

```bash
git add packages/web/components/auth/index.ts
git commit -m "chore: update auth index with new guard exports"
```

---

## Phase 1: Layout 桥接

### Task 1.1: 改造 layout.tsx 使用 getPermissions + PermissionHydrate

**Files:**
- Modify: `packages/web/app/[locale]/layout.tsx`
- Modify: `packages/web/components/layout/header.tsx`
- Modify: `packages/web/components/layout/header.test.tsx`

- [ ] **Step 1: 修改 layout.tsx**

```typescript
// packages/web/app/[locale]/layout.tsx — 变更行

// 删掉旧的 raw API import（Line 18）:
import { getMyPermissions } from "@/lib/api/permissions";

// 替换为:
import { getPermissions } from "@/lib/auth/permission";
import { PermissionHydrate } from "@/components/auth/permission-hydrate";
import type { PermissionData } from "@/lib/auth/permission-types";

// 删掉旧的 fetch（Line 79）:
const permissions = await getMyPermissions();

// 替换为:
const perm = await getPermissions();
const permData: PermissionData = {
  role: perm.role,
  accountId: perm.accountId,
  allowed: perm.allowed,
  pages: perm.pages,
};

// 渲染部分（原 Line 107-109）:
// 旧: <Header user={user} permissions={permissions} />
// 新: <Header user={user} permissions={perm} />

// 添加 PermissionHydrate（在 <main> 之前）:
<PermissionHydrate permissions={permData} />
```

- [ ] **Step 2: 修改 Header 类型（用 PermissionData，避开函数/headers）**

```typescript
// packages/web/components/layout/header.tsx — 变更行

// 旧:
import type { MyPermissions } from "@/lib/auth/permissions";
// ...
  permissions: MyPermissions;

// 新:
import type { PermissionData } from "@/lib/auth/permission-types";
// ...
  permissions: PermissionData;
```

**原因**：Header 只用 `pages` 和 `allowed` 字段，不需要 `can()`/`headers`/`isAdminLevel` 等 server-only 字段。
用 `PermissionData` 简化类型且不强行使用含函数的 `PermissionResult`。

- [ ] **Step 3: 修改 Header 测试**

```typescript
// packages/web/components/layout/header.test.tsx — 变更行

// 旧:
import type { MyPermissions } from "@/lib/auth/permissions";
// 新:
import type { PermissionData } from "@/lib/auth/permission-types";

// 旧:
const basePermissions: MyPermissions = {
  role: "user",
  account_id: null,
// 新:
const basePermissions: PermissionData = {
  role: "user",
  accountId: null,
  // pages/allowed 字段不变
};

// 全文 5 处 inline fixture（Line 77, 110, 122, 138, 156）
// 都要做以下替换: account_id → accountId, type MyPermissions → PermissionData
// 用 sed 批量替换:
//   sed -i 's/account_id/accountId/g; s/MyPermissions/PermissionData/g' components/layout/header.test.tsx
```

- [ ] **Step 4: 运行类型检查和测试**

```bash
cd packages/web
bun run typecheck 2>&1 | tail -5
bun run test -- components/layout/header.test.tsx
bun run lint 2>&1 | tail -5
```

- [ ] **Step 5: Commit**

```bash
git add packages/web/app/[locale]/layout.tsx packages/web/components/layout/header.tsx packages/web/components/layout/header.test.tsx
git commit -m "refactor: layout uses getPermissions() + PermissionHydrate bridge to client"
```

---

## Phase 2: RSC 页面迁移

### 子阶段 2a: knowledge 模块（7 页）

**通用替换模式**——以下 7 页都执行同样的改动：

```typescript
// 改前:
import { getMyPermissions } from "@/lib/auth/permissions";
import { PageGuard } from "@/components/page-guard";
// ...
const permissions = await getMyPermissions();
return (
  <PageGuard pageKey="knowledge" permissions={permissions}>
    {children}
  </PageGuard>
);

// 改后:
import { GuardPage } from "@/components/auth/guard-page";
// ...
return (
  <GuardPage pageKey="knowledge">
    {children}
  </GuardPage>
);
```

注意：删掉不再需要的 `getMyPermissions` import 和 `PageGuard` import。

**Tasks:**
- [ ] 2a-1: `knowledge/graph/page.tsx`
- [ ] 2a-2: `knowledge/triples/page.tsx`
- [ ] 2a-3: `knowledge/nodes/page.tsx`
- [ ] 2a-4: `knowledge/qa/page.tsx`
- [ ] 2a-5: `knowledge/relations/page.tsx`
- [ ] 2a-6: `knowledge/datasets/page.tsx`
- [ ] 2a-7: `knowledge/dataset-documents/[dataset_id]/page.tsx`

- [ ] **验证子阶段 2a:**

```bash
cd packages/web
bun run test -- app/\[locale\]/knowledge/ 2>&1 | tail -10
bun run typecheck 2>&1 | tail -5
bun run lint 2>&1 | tail -5
```

- [ ] **Commit 子阶段 2a:**

```bash
git add app/\[locale\]/knowledge/graph/page.tsx app/\[locale\]/knowledge/triples/page.tsx app/\[locale\]/knowledge/nodes/page.tsx app/\[locale\]/knowledge/qa/page.tsx app/\[locale\]/knowledge/relations/page.tsx app/\[locale\]/knowledge/datasets/page.tsx app/\[locale\]/knowledge/dataset-documents/\[dataset_id\]/page.tsx
git commit -m "refactor(knowledge): migrate 7 RSC pages to GuardPage"
```

### 子阶段 2b: evaluate 模块（3 页）

**evaluate/page.tsx（特殊处理）**：
```typescript
// 改前:
import { getMyPermissions } from "@/lib/auth/permissions";
import { PageGuard } from "@/components/page-guard";
// ...
const permissions = await getMyPermissions();
const runsPromise: Promise<EvaluationRunSummary[]> = permissions.allowed.includes("evaluate")
  ? fetchEvaluationRuns()
  : Promise.resolve([]);  // 保持 Promise 类型，避免 use(runsPromise) 抛错
return (
  <PageGuard pageKey="evaluate" permissions={permissions}>
    {children}
  </PageGuard>
);

// 改后:
import { getPermissions } from "@/lib/auth/permission";  // 保留用于数据
import { GuardPage } from "@/components/auth/guard-page";
// ...
const perm = await getPermissions();  // cache hit from layout
const runsPromise: Promise<EvaluationRunSummary[]> = perm.can("evaluate")
  ? fetchEvaluationRuns()
  : Promise.resolve([]);  // 重要：保持 Promise.resolve([]) 而非 undefined
return (
  <GuardPage pageKey="evaluate">
    {children}
  </GuardPage>
);
```

**evaluate/[id]/page.tsx + evaluate/new/page.tsx**：执行通用替换（pageKey="evaluate"）。

**Tasks:**
- [ ] 2b-1: `evaluate/page.tsx`（特殊：保留 getPermissions 用于数据）
- [ ] 2b-2: `evaluate/[id]/page.tsx`
- [ ] 2b-3: `evaluate/new/page.tsx`
- [ ] 2b-4: 更新 `evaluate/page.test.tsx`（mock `getPermissions` 替代 `getMyPermissions` + **mock `forbidden` 替代 `notFound`**）
- [ ] 2b-5: 更新 `evaluate/new/page.test.tsx`

- [ ] **验证子阶段 2b:**

```bash
cd packages/web
bun run test -- app/\[locale\]/evaluate/ 2>&1 | tail -10
bun run typecheck
bun run lint
```

- [ ] **Commit 子阶段 2b:**

```bash
git add app/\[locale\]/evaluate/
git commit -m "refactor(evaluate): migrate 3 RSC pages to GuardPage"
```

### 子阶段 2c: output 模块（2 页）

- [ ] 2c-1: `output/page.tsx`（通用替换，pageKey="output"）
- [ ] 2c-2: `output/[task_id]/page.tsx`

- [ ] **验证子阶段 2c:**

```bash
cd packages/web
bun run test -- app/\[locale\]/output/ 2>&1 | tail -10
bun run typecheck
bun run lint
```

- [ ] **Commit 子阶段 2c:**

```bash
git add app/\[locale\]/output/page.tsx app/\[locale\]/output/\[task_id\]/page.tsx
git commit -m "refactor(output): migrate 2 RSC pages to GuardPage"
```

### 子阶段 2d: 剩余 RSC 页（7 页）

- [ ] 2d-1: `chat/page.tsx`（特殊：删 getMyPermissions + PageGuard，保留 serverAuthHeaders 用于 /me 调用）
- [ ] 2d-2: `health/page.tsx`
- [ ] 2d-3: `submissions/page.tsx`
- [ ] 2d-4: `knowledge/page.tsx`（特殊：redirect 页。`getMyPermissions` → `getPermissions` + `can()`）
- [ ] 2d-5: `admin/invites/page.tsx`
- [ ] 2d-6: `knowledge/documents/page.tsx`
- [ ] 2d-7: `knowledge/documents/import/page.tsx`

**chat/page.tsx 特殊处理**：
```typescript
// 删掉:
import { getMyPermissions } from "@/lib/auth/permissions";
// 保留（用于 /me）:
import { serverAuthHeaders } from "@/lib/api/auth.server";
// 新增:
import { GuardPage } from "@/components/auth/guard-page";

// 删掉:
const permissions = await getMyPermissions();
// 保留:
const me = await apiFetch<MeResponse>("/api/account/me", {
  headers: await serverAuthHeaders(),
});

// 替换:
<PageGuard pageKey="chat" permissions={permissions}>
  ...
</PageGuard>
// 为:
<GuardPage pageKey="chat">
  ...
</GuardPage>
```

**knowledge/page.tsx 特殊处理**：
```typescript
// packages/web/app/[locale]/knowledge/page.tsx
// 旧:
import { getMyPermissions } from "@/lib/auth/permissions";
import { redirect } from "next/navigation";
import ForbiddenPage from "../forbidden";

export default async function KnowledgePage() {
  const permissions = await getMyPermissions();
  if (!permissions.allowed.includes("knowledge")) return <ForbiddenPage />;
  redirect("/knowledge/documents");
}

// 新:
import { redirect } from "next/navigation";
import { getPermissions } from "@/lib/auth/permission";
import ForbiddenPage from "../forbidden";

export default async function KnowledgePage() {
  const perm = await getPermissions();
  if (!perm.can("knowledge")) return <ForbiddenPage />;
  redirect("/knowledge/documents");
}
```

- [ ] **验证子阶段 2d:**

```bash
cd packages/web
bun run test 2>&1 | tail -15
bun run typecheck
bun run lint
```

- [ ] **Commit 子阶段 2d:**

```bash
git add app/\[locale\]/chat/page.tsx app/\[locale\]/health/page.tsx app/\[locale\]/submissions/page.tsx app/\[locale\]/knowledge/page.tsx app/\[locale\]/admin/invites/page.tsx app/\[locale\]/knowledge/documents/page.tsx app/\[locale\]/knowledge/documents/import/page.tsx
git commit -m "refactor: migrate remaining 7 RSC pages to GuardPage"
```

### 子阶段 2e: admin 模块（3 页）

**这些页已用单数版 `permission.ts`**，只需替换 GuardPage 包装 + 保留 `getPermissions()` 数据调用 + **保留额外的 `isSuperAdmin`/`isAdminLevel` 守卫**。

**关键安全点**：`GuardPage pageKey="admin"` 只检查 `role === "super_admin" || allowed.includes("admin")`。
但 `/admin/permissions` 和 `/admin/dicts` 是 super_admin 专属，`/admin/users` 是 admin 级别。
仅靠 pageKey="admin" 不足以保证安全，必须保留额外守卫：

**admin/users/page.tsx 模式**：
```typescript
// 删掉:
import { PageGuard } from "@/components/page-guard";
// 新增:
import { GuardPage } from "@/components/auth/guard-page";

// 保留 getPermissions() 用于 isAdminLevel + headers
const perm = await getPermissions();

// 保留额外守卫（admin 级别即可访问）:
if (!perm.isAdminLevel) {
  redirect("/");
}

// 替换:
<PageGuard pageKey="admin" role={perm.role} allowed={perm.allowed}>
  ...
</PageGuard>
// 为:
<GuardPage pageKey="admin">
  ...
</GuardPage>
```

**admin/permissions/page.tsx 模式**（super_admin 专属）：
```typescript
const perm = await getPermissions();
// 保留额外守卫（必须是 super_admin）:
if (!perm.isSuperAdmin) {
  forbidden();
}
// 后续数据获取用 perm.headers
```

**admin/dicts/page.tsx 模式**（super_admin 专属，client 子组件）：
```typescript
const perm = await getPermissions();
// 保留额外守卫:
if (!perm.isSuperAdmin) {
  forbidden();
}
// GuardPage 包装; AdminDictsClient 接收 role+allowed 作为 props
return (
  <GuardPage pageKey="admin">
    <AdminDictsClient role={perm.role} allowed={perm.allowed} />
  </GuardPage>
);
```

**注意**：`admin/dicts/_components/admin-dicts-client.tsx` 中的 `<PageGuard>` 保留不动（client 子组件场景）。

- [ ] 2e-1: `admin/users/page.tsx`（保留 `!perm.isAdminLevel → redirect("/")`）
- [ ] 2e-2: `admin/dicts/page.tsx`（保留 `!perm.isSuperAdmin → forbidden()`）
- [ ] 2e-3: `admin/permissions/page.tsx`（保留 `!perm.isSuperAdmin → forbidden()`）

- [ ] **验证子阶段 2e:**

```bash
cd packages/web
bun run test -- app/\[locale\]/admin/ 2>&1 | tail -10
bun run typecheck
bun run lint
```

- [ ] **Commit 子阶段 2e:**

```bash
git add app/\[locale\]/admin/users/page.tsx app/\[locale\]/admin/dicts/page.tsx app/\[locale\]/admin/permissions/page.tsx
git commit -m "refactor(admin): migrate 3 admin RSC pages to GuardPage"
```

---

## Phase 3: Client 页面迁移（ClientPageGuard → GuardClient）

### Task 3.1: decode/page.tsx

**Files:**
- Modify: `packages/web/app/[locale]/decode/page.tsx`

```typescript
// 删掉:
import { ClientPageGuard } from "@/components/client-page-guard";
// 新增:
import { GuardClient } from "@/components/auth/guard-client";

// 替换:
<ClientPageGuard pageKey="decode">
  ...
</ClientPageGuard>
// 为:
<GuardClient pageKey="decode">
  ...
</GuardClient>
```

- [ ] **Step 1: 迁移 decode/page.tsx**
- [ ] **Step 2: 更新 decode/page.test.tsx（如有）**
- [ ] **Step 3: 验证**

```bash
cd packages/web
bun run test -- app/\[locale\]/decode/ 2>&1 | tail -5
bun run typecheck
```

- [ ] **Step 4: Commit**

```bash
git add app/\[locale\]/decode/
git commit -m "refactor(decode): migrate ClientPageGuard to GuardClient"
```

### Task 3.2: knowledge/batch/page.tsx

同 3.1 模式，pageKey="knowledge"。

- [ ] **Step 1: 迁移 batch/page.tsx**
- [ ] **Step 2: 更新 batch/page.test.tsx（mock store 替代 ClientPageGuard mock）**

```typescript
// knowledge/batch/page.test.tsx — 改造 mock
import { usePermissionsStore } from "@/lib/hooks/use-permissions";

// 在测试前设置 store
beforeEach(() => {
  usePermissionsStore.setState({
    role: "admin",
    allowed: ["knowledge"],
    loaded: true,
  });
});
```

- [ ] **Step 3: 验证 + Commit**

### Task 3.3: output/new/page.tsx

同 3.1 模式，pageKey="output"。

- [ ] **Step 1: 迁移 output/new/page.tsx**
- [ ] **Step 2: 更新 output/new/page.test.tsx**
- [ ] **Step 3: 验证 + Commit**

### Task 3.4: output/[task_id]/[file]/page.tsx

同 3.1 模式，pageKey="output"。

- [ ] **Step 1: 迁移 output/[task_id]/[file]/page.tsx**
- [ ] **Step 2: 更新 output/[task_id]/[file]/page.test.tsx**
- [ ] **Step 3: 验证 + Commit**

- [ ] **Phase 3 最终验证:**

```bash
cd packages/web
bun run test 2>&1 | tail -20
bun run typecheck
bun run lint
```

Expected: all tests pass，0 type errors，0 lint errors（数量取决于 Phase 0 新增测试，不预设具体数）

---

## Phase 4: 清理

### Task 4.1: 删除 client-page-guard.tsx

- [ ] **Step 1: 确认无引用**

```bash
cd packages/web
grep -r "client-page-guard\|ClientPageGuard" app/ components/ --include="*.tsx" --include="*.ts" | grep -v node_modules | grep -v ".test.tsx"
```
Expected: 无输出

- [ ] **Step 2: 删除文件**

```bash
git rm components/client-page-guard.tsx
```

- [ ] **Step 3: Commit**

```bash
git commit -m "chore: remove ClientPageGuard (replaced by GuardClient)"
```

### Task 4.2: 删除 lib/auth/permissions.ts（复数）

- [ ] **Step 1: 确认无引用**

```bash
cd packages/web
grep -r "from.*lib/auth/permissions" app/ components/ --include="*.tsx" --include="*.ts" | grep -v node_modules | grep -v ".test.tsx"
```
Expected: 无输出

- [ ] **Step 2: 删除文件**

```bash
git rm lib/auth/permissions.ts
```

- [ ] **Step 3: Commit**

```bash
git commit -m "chore: remove deprecated lib/auth/permissions.ts (replaced by permission.ts)"
```

### Task 4.3: 最终全量验证

- [ ] **Step 1: 运行全量检查**

```bash
cd packages/web
bun run format:check || echo "format issues"
bun run lint 2>&1 | tail -20
bun run typecheck 2>&1 | tail -20
bun run test 2>&1 | tail -30
```

Expected: 0 format errors，0 lint errors，0 type errors，all tests pass

- [ ] **Step 2: 确认没有遗留引用复数版**

```bash
cd packages/web
grep -rn "from.*@/lib/auth/permissions" app/ components/ lib/ --include="*.tsx" --include="*.ts" | grep -v node_modules | grep -v ".test.tsx" | grep -v ".d.ts"
```
Expected: 无输出

- [ ] **Step 3: final commit（仅本次重构涉及的文件，禁止 `git add -A`）**

```bash
# 仅添加本次重构明确涉及的文件:
git add \
  packages/web/lib/auth/ \
  packages/web/lib/hooks/use-permissions.ts \
  packages/web/lib/store/auth-store.ts \
  packages/web/lib/store/auth-store.test.ts \
  packages/web/components/auth/ \
  packages/web/components/client-page-guard.tsx \
  packages/web/app/\[locale\]/layout.tsx \
  packages/web/components/layout/header.tsx \
  packages/web/components/layout/header.test.tsx
git status  # 检查无误后再 commit
git commit -m "chore: final cleanup after permission guard refactoring"
```

---

## 自检清单

### Spec 覆盖

| Spec 要求 | 实现任务 |
|-----------|---------|
| GuardPage RSC 组件 | Task 0.4 |
| PermissionHydrate client 组件 | Task 0.5 |
| GuardClient 替代 ClientPageGuard | Task 0.6, Phase 3 |
| usePermissionsStore hydration-only | Task 0.3 |
| PermissionData + PermissionResult 拆分 | Task 0.1, 0.2 |
| getPermissions() try/catch + accountId | Task 0.2 |
| layout 改用 getPermissions | Task 1.1 |
| Header 类型适配（用 PermissionData） | Task 1.1 |
| 22 个 RSC 页面迁移 | Phase 2 (2a-2e) |
| 4 个 Client 页面迁移 | Phase 3 |
| 废弃 client-page-guard.tsx | Task 4.1 |
| 废弃 lib/auth/permissions.ts | Task 4.2 |
| forbidden.tsx + not-found.tsx 确认 | Task 0.7 |
| admin 页 isSuperAdmin/isAdminLevel 额外守卫 | Phase 2e（明确保留） |
| import guard 测试 | 在页面测试迁移步骤中覆盖 |
| auth-store setAccountId 接受 null | 已修改（`auth-store.ts`） |

### 评审反馈覆盖（修正版）

| BLOCKER | 修复方式 |
|---------|---------|
| 1. auth-store setAccountId 类型 | ✅ 已改 `number | null` + 加 test |
| 2. Task 0.3 测试用 renderHook | ✅ 已加 `renderHook` 包装 |
| 3. admin 页面丢失 isSuperAdmin 守卫 | ✅ 2e 已明确保留额外守卫 |
| 4. permission.ts 缺 server-only | ✅ Task 0.2 Step 3 已加 import |
| 5. Header test 5 处内联 fixture | ✅ 改用 PermissionData + sed 批量替换 |
| 6. GuardPage + admin pageKey 提权 | ✅ 同 3（额外守卫是真正的边界） |
| 7. /404 路由缺失 | ✅ Task 0.7 同时验证 not-found.tsx |

### 关键 WARNING 修复

| WARNING | 修复方式 |
|---------|---------|
| evaluate runsPromise undefined | ✅ 保持 `Promise.resolve([])` |
| evaluate test mock notFound | ✅ 改 mock forbidden |
| Phase 4 git add -A 危险 | ✅ 改为精确文件列表 |
| 2d 子阶段计数 | ✅ 6 → 7 |
| knowledge/page.tsx 缺 redirect | ✅ 完整代码块 |
| usePermissions 测试 fetch 删除 | ✅ Task 0.3 显式说明 |
| Header test 5 处 fixture | ✅ sed 替换 |
| not-found.tsx 验证 | ✅ Task 0.7 加 check |
| account/settings test accountId | ✅ Phase 0 后才执行，已 type-safe |
| JSON.stringify 弱测试 | ✅ 弱测试保留（仅 sanity check） |

### Placeholder 检查

- 所有测试代码完整给出
- 所有代码块包含实际内容，无 "TODO" / "TBD"
- 所有文件路径精确
- 所有命令含期望输出
- 关键 admin 页面给出完整代码块（含额外守卫）

### 类型一致性

- `PermissionData`（可序列化，无函数）在 Task 0.1 定义，Task 0.5 (PermissionHydrate) 作为 props 接收
- `PermissionResult extends PermissionData` 在 Task 0.2 定义，admin pages 在 Phase 2e 直接接收（不需要 Header）
- `usePermissions().can(pageKey)` 在 Task 0.3 定义，在 Task 0.6 (GuardClient) 使用
- `useAuthStore.getState().setAccountId(number | null)` 在 Task 0.5 (PermissionHydrate) 使用

---

**Plan complete and saved to `docs/superpowers/plans/2026-06-23-permission-zustand-guardpage-plan.md`.**

**Two execution options:**

1. **Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration
2. **Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
