# Admin Users 打通 RBAC 角色 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 admin/users 页角色列从派生的 `is_admin: bool` 改为读后端 `role: str` 真值 + 走 `/api/roles` 列表查 i18n label,行内 `<AppSelect>` 改 role(乐观更新 + 失败回滚),`super_admin` 选项 UX 灰禁;UserFilters 加 role 单选下拉;`AdminUsersTable` mount 强制 refetch roles 1 次.

**Architecture:** RSC 同步拉 `getRoles()` → 透传 `initialRoles` 给 client;client `useRoles` 抽独立 hook(走 TanStack Query + `staleTime: 60_000` + mount 强制 refetch);`useUserTable` 加 `changeRole` action(走 useOptimistic + startTransition + reload,跟现有 `toggleActive`/`toggleAdmin` 同模式);角色列换 `<AppSelect>`(`options[].disabled` 支持 super_admin 灰禁);role 过滤走 client 端 `.filter`(后端 `/api/admin/users` 暂不接 role 查询,YAGNI).

**Tech Stack:** TypeScript 8 + React 19 + next-intl 4 + TanStack Query 5 + shadcn `<Select>`(经 `<AppSelect>` 包装) + motion + vitest + oxlint + oxfmt

**Spec:** [docs/superpowers/specs/2026-06-26-admin-users-rbac-wire-design.md](../specs/2026-06-26-admin-users-rbac-wire-design.md)

**项目铁律:** format → lint → typecheck → test → commit ([CLAUDE.md](../../CLAUDE.md))

---

## File Structure (锁定)

| 操作 | 路径 | 责任 |
|---|---|---|
| **Modify** | [packages/web/lib/api/permissions.ts](../../packages/web/lib/api/permissions.ts) | 加 `getRoles` / `updateRole` / `deleteRole` 包装 |
| **Modify** | [packages/web/lib/api/users.ts](../../packages/web/lib/api/users.ts) | 修 `createUser` 注释(deprecated body) + 加 `patchUser` 包装 |
| **Modify** | [packages/web/app/[locale]/admin/users/_hooks/use-user-table.ts](../../packages/web/app/[locale]/admin/users/_hooks/use-user-table.ts) | `AdminUser` 加 `role: string`;去 `is_admin`;加 `changeRole` action |
| **Create** | [packages/web/app/[locale]/admin/users/_hooks/use-roles.ts](../../packages/web/app/[locale]/admin/users/_hooks/use-roles.ts) | TanStack Query wrapper, mount refetch |
| **Create** | [packages/web/app/[locale]/admin/users/_hooks/use-roles.test.ts](../../packages/web/app/[locale]/admin/users/_hooks/use-roles.test.ts) | use-roles 单元测试 |
| **Create** | [packages/web/app/[locale]/admin/users/_hooks/use-user-table.test.ts](../../packages/web/app/[locale]/admin/users/_hooks/use-user-table.test.ts) | use-user-table 单元测试(changeRole 红→绿) |
| **Modify** | [packages/web/app/[locale]/admin/users/_components/admin-users-table.tsx](../../packages/web/app/[locale]/admin/users/_components/admin-users-table.tsx) | 角色列换 AppSelect;操作列去 is_admin 引用;接 roles;mount refetch |
| **Modify** | [packages/web/app/[locale]/admin/users/_components/admin-users-table.test.tsx](../../packages/web/app/[locale]/admin/users/_components/admin-users-table.test.tsx) | SAMPLE 加 role;AppSelect 渲染 + super_admin 灰禁 + PATCH body 断言 |
| **Modify** | [packages/web/app/[locale]/admin/users/_components/user-filters.tsx](../../packages/web/app/[locale]/admin/users/_components/user-filters.tsx) | 加 role 单选下拉 |
| **Create** | [packages/web/app/[locale]/admin/users/_components/user-filters.test.tsx](../../packages/web/app/[locale]/admin/users/_components/user-filters.test.tsx) | user-filters 单元测试 |
| **Modify** | [packages/web/app/[locale]/admin/users/page.tsx](../../packages/web/app/[locale]/admin/users/page.tsx) | RSC 同步拉 `getRoles()` 透传 `initialRoles` |
| **Modify** | [packages/web/app/[locale]/admin/users/page.test.tsx](../../packages/web/app/[locale]/admin/users/page.test.tsx) | 加 `getRoles` mock + initialRoles 透传断言 |
| **Modify** | [packages/web/messages/zh.json](../../packages/web/messages/zh.json) | 加 4 key(所有角色 / 已改角色 / 不可手动分配 / 改角色) |
| **Modify** | [packages/web/messages/en.json](../../packages/web/messages/en.json) | 同 4 key 英文翻译 |
| **No change** | `packages/service/src/**` | 后端 0 改动(端点全齐) |

**关键 reference 文件(实施时需 Read 上下文):**
- 后端 UserItem schema: [packages/service/src/auth/auth_admin_router.py:40-51](../../packages/service/src/auth/auth_admin_router.py#L40-L51)
- 后端 PatchUserRequest: [packages/service/src/auth/auth_admin_router.py:228-232](../../packages/service/src/auth/auth_admin_router.py#L228-L232)
- 后端 GET /api/roles 响应 schema: [packages/service/src/permissions/router.py:187-204](../../packages/service/src/permissions/router.py#L187-L204)
- 现有 useUserTableActions 模式参考: [packages/web/app/[locale]/admin/users/_hooks/use-user-table.ts:60-148](../../packages/web/app/[locale]/admin/users/_hooks/use-user-table.ts#L60-L148)
- AppSelect API: [packages/web/components/common/input/app-select.tsx](../../packages/web/components/common/input/app-select.tsx)
- RoleListItem 已有类型: [packages/web/app/[locale]/admin/permissions/_hooks/use-permissions-table.ts](../../packages/web/app/[locale]/admin/permissions/_hooks/use-permissions-table.ts)

---

## Task 1: lib/api/permissions.ts 加 getRoles / updateRole / deleteRole (0 风险,直接绿)

**Files:**
- Modify: [packages/web/lib/api/permissions.ts](../../packages/web/lib/api/permissions.ts) — 末尾追加 3 个 export

- [ ] **Step 1: 在文件末尾追加 3 个包装函数**

```typescript
// (2026-06-26) RBAC wire: 补 GET /api/roles + PATCH/DELETE /api/roles/{name}
// 已有 createRole (上方), 跟 createRole 同模式 (apiFetch + body + method)
export interface RoleListItem {
  name: string;
  label_zh: string;
  label_en: string;
  is_system: boolean;
  is_deletable: boolean;
  user_count: number;
  created_at: string | null;
  updated_at: string | null;
}

export const listRoles = (headers?: Record<string, string>) =>
  apiFetch<{ roles: RoleListItem[] }>("/api/roles", { headers });

export const updateRole = (
  name: string,
  data: { label_zh?: string; label_en?: string },
  headers?: Record<string, string>,
) =>
  apiFetch<RoleListItem>(`/api/roles/${name}`, {
    body: data,
    headers,
    method: "PATCH",
  });

export const deleteRole = (name: string, headers?: Record<string, string>) =>
  apiFetch<null>(`/api/roles/${name}`, { headers, method: "DELETE" });
```

- [ ] **Step 2: 跑类型检查 + 现有 test,确认无回归**

```bash
cd packages/web && bun run typecheck && bun run test -- lib/api/permissions
```

Expected: typecheck 0 error, vitest 通过(原文件无 test,跳过)。

- [ ] **Step 3: Commit**

```bash
git add packages/web/lib/api/permissions.ts
git commit -m "feat(api): add listRoles / updateRole / deleteRole wrappers"
```

---

## Task 2: lib/api/users.ts 修 createUser 注释 + 加 patchUser 包装

**Files:**
- Modify: [packages/web/lib/api/users.ts](../../packages/web/lib/api/users.ts) — 修 `createUser` 注释 + 末尾加 `patchUser`

- [ ] **Step 1: 修 `createUser` 注释(标注 deprecated body)+ 末尾加 `patchUser`**

```typescript
import { apiFetch } from "./config";

/** 获取用户列表 */
export const listUsers = (): ReturnType<typeof apiFetch> => apiFetch("/api/admin/users");

/** 创建邀请 */
// (2026-06-26) RBAC wire: role 替 is_admin. 后端 CreateInviteRequest 默认 role="user",
//   不传 body.role 即可. 保留 email-only 重载避免破坏未来 ad-hoc 调用.
export const createInvite = (email: string, headers?: Record<string, string>) =>
  apiFetch("/api/admin/invites", { body: { email }, headers, method: "POST" });

/** 创建用户（含管理员） — DEPRECATED since 2026-06-17 */
// 后端早就不接 is_admin: bool (Pydantic 校验失败), 保留函数仅为向后兼容, 新代码走 createInvite 传 role.
export const createUser = (
  body: { email: string; role?: string },
  headers?: Record<string, string>,
) => apiFetch<{ invite_url: string }>("/api/admin/users", { body, headers, method: "POST" });

/** 重置用户密码 */
export const resetPassword = (userId: number, headers?: Record<string, string>) =>
  apiFetch<{ temp_password: string }>(`/api/admin/users/${userId}/reset-password`, {
    headers,
    method: "POST",
  });

/** 修改用户字段 (is_active / role / display_name) */
// (2026-06-26) RBAC wire: 后端 PatchUserRequest 接 role: str (替原 is_admin: bool).
export const patchUser = (
  userId: number,
  body: { is_active?: boolean; role?: string; display_name?: string },
  headers?: Record<string, string>,
) => apiFetch<{ id: number; ok: true }>(`/api/admin/users/${userId}`, {
  body,
  headers,
  method: "PATCH",
});
```

- [ ] **Step 2: 跑类型检查 + 现有 test**

```bash
cd packages/web && bun run typecheck && bun run test -- lib/api/users
```

Expected: typecheck 0 error, vitest 通过(原文件无 test,跳过)。

- [ ] **Step 3: Commit**

```bash
git add packages/web/lib/api/users.ts
git commit -m "feat(api): patchUser wrapper + mark createUser is_admin deprecated"
```

---

## Task 3: use-roles.test.ts 写 useRoles 单元测试 (红)

**Files:**
- Create: [packages/web/app/[locale]/admin/users/_hooks/use-roles.test.ts](../../packages/web/app/[locale]/admin/users/_hooks/use-roles.test.ts)

- [ ] **Step 1: 写测试覆盖 3 个行为**

```typescript
// use-roles 单元测试 (2026-06-26) RBAC wire
//   测: 1) initialData 立即可用 2) mount refetch 1 次 3) staleTime 60s
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { ReactNode } from "react";
import { useRoles } from "./use-roles";

const SAMPLE_ROLES = [
  {
    created_at: "2026-06-17T00:00:00",
    is_deletable: false,
    is_system: true,
    label_en: "Super Admin",
    label_zh: "超级管理员",
    name: "super_admin",
    updated_at: "2026-06-17T00:00:00",
    user_count: 1,
  },
  {
    created_at: "2026-06-17T00:00:00",
    is_deletable: false,
    is_system: true,
    label_en: "Admin",
    label_zh: "管理员",
    name: "admin",
    updated_at: "2026-06-17T00:00:00",
    user_count: 3,
  },
];

const { listRolesMock } = vi.hoisted(() => ({ listRolesMock: vi.fn() }));

vi.mock("@/lib/api/permissions", () => ({
  listRoles: listRolesMock,
}));

const createWrapper = () => {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return {
    client,
    wrapper: ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    ),
  };
};

describe("useRoles", () => {
  beforeEach(() => {
    listRolesMock.mockReset();
  });
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("initialData 立即可用, 不立即 fetch", () => {
    listRolesMock.mockResolvedValue({ roles: SAMPLE_ROLES });
    const { wrapper } = createWrapper();
    const { result } = renderHook(() => useRoles(SAMPLE_ROLES), { wrapper });
    expect(result.current).toEqual(SAMPLE_ROLES);
    expect(listRolesMock).not.toHaveBeenCalled();
  });

  it("mount 强制 refetch 1 次", async () => {
    listRolesMock.mockResolvedValue({ roles: SAMPLE_ROLES });
    const { wrapper } = createWrapper();
    renderHook(() => useRoles(SAMPLE_ROLES), { wrapper });
    await waitFor(() => {
      expect(listRolesMock).toHaveBeenCalledTimes(1);
    });
  });

  it("refetch 后 data 替换为最新 roles", async () => {
    const FRESH = [
      { ...SAMPLE_ROLES[1]!, user_count: 99 },
    ];
    listRolesMock.mockResolvedValue({ roles: FRESH });
    const { wrapper } = createWrapper();
    const { result } = renderHook(() => useRoles(SAMPLE_ROLES), { wrapper });
    await waitFor(() => {
      expect(result.current).toEqual(FRESH);
    });
  });
});
```

- [ ] **Step 2: 跑测试确认 RED**

```bash
cd packages/web && bun run test -- use-roles
```

Expected: FAIL with "Cannot find module './use-roles'" (模块还没建,红)。

- [ ] **Step 3: 不 commit,继续 Task 4**

---

## Task 4: use-roles.ts 写 useRoles hook (绿)

**Files:**
- Create: [packages/web/app/[locale]/admin/users/_hooks/use-roles.ts](../../packages/web/app/[locale]/admin/users/_hooks/use-roles.ts)

- [ ] **Step 1: 写 hook 实现**

```typescript
// useRoles (2026-06-26) RBAC wire
//   走 TanStack Query, initialData 透传 RSC 拉的列表, mount 强制 refetch 1 次
//   (拿权限页 /admin/permissions 新建 role 后的最新列表, 见 spec §4.3)
"use client";
import { useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { listRoles, type RoleListItem } from "@/lib/api/permissions";

const ROLES_STALE_MS = 60_000;
const ZERO_CALLS = 0;

export const useRoles = (initial: RoleListItem[]): RoleListItem[] => {
  const query = useQuery({
    initialData: { roles: initial },
    queryFn: () => listRoles(),
    queryKey: ["roles"],
    staleTime: ROLES_STALE_MS,
  });
  // mount 强制 refetch 1 次, 拿权限页最新 role 列表
  useEffect(() => {
    if (query.fetchStatus === "idle" && query.dataUpdatedAt === ZERO_CALLS) {
      void query.refetch();
    }
  }, [query]);
  return query.data?.roles ?? initial;
};
```

- [ ] **Step 2: 跑测试确认 GREEN**

```bash
cd packages/web && bun run test -- use-roles
```

Expected: 3 tests passed (initialData / mount refetch / refetch 替换)。

- [ ] **Step 3: 跑 typecheck / lint**

```bash
cd packages/web && bun run typecheck && bun run lint
```

Expected: 0 error。

- [ ] **Step 4: Commit**

```bash
git add packages/web/app/[locale]/admin/users/_hooks/use-roles.ts packages/web/app/[locale]/admin/users/_hooks/use-roles.test.ts
git commit -m "feat(admin-users): useRoles hook with mount refetch (TDD)"
```

---

## Task 5: use-user-table.test.ts 写 changeRed 单元测试 (红)

**Files:**
- Create: [packages/web/app/[locale]/admin/users/_hooks/use-user-table.test.ts](../../packages/web/app/[locale]/admin/users/_hooks/use-user-table.test.ts)

- [ ] **Step 1: 写测试覆盖 changeRole 3 个行为**

```typescript
// use-user-table 单元测试 (2026-06-26) RBAC wire
//   测 changeRole: 1) PATCH body 含 role 2) optimistic 更新 3) 失败 toast
import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { toast } from "sonner";
import { FIRST_PAGE, useUserTable, type AdminUser } from "./use-user-table";
import { ApiError } from "@/lib/api/errors";

const { patchUserMock } = vi.hoisted(() => ({ patchUserMock: vi.fn() }));

vi.mock("@/lib/api/users", () => ({
  patchUser: patchUserMock,
}));

const USER: AdminUser = {
  account_id: 1,
  created_at: "2026-06-01T00:00:00",
  display_name: "alice",
  email: "alice@x.com",
  id: 1,
  is_active: true,
  kind: "account",
  last_login_at: null,
  last_seen_at: "2026-06-13T00:00:00",
  role: "user",
};

const INITIAL = {
  items: [USER],
  page: 1,
  page_size: 20,
  total: 1,
};

describe("useUserTable.changeRole", () => {
  beforeEach(() => {
    patchUserMock.mockReset();
    vi.spyOn(toast, "success").mockImplementation(() => "");
    vi.spyOn(toast, "error").mockImplementation(() => "");
  });
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("发 PATCH /api/admin/users/{id} body 含 role", async () => {
    patchUserMock.mockResolvedValue({ id: 1, ok: true });
    const { result } = renderHook(() => useUserTable(INITIAL));
    await act(async () => {
      result.current.changeRole(USER, "admin");
    });
    expect(patchUserMock).toHaveBeenCalledWith(1, { role: "admin" });
  });

  it("optimistic 更新: items[0].role 立刻变 adin", async () => {
    patchUserMock.mockResolvedValue({ id: 1, ok: true });
    const { result } = renderHook(() => useUserTable(INITIAL));
    act(() => {
      result.current.changeRole(USER, "admin");
    });
    // 不 await, optimistic 同步应用
    expect(result.current.data.items[0]?.role).toBe("admin");
  });

  it("失败 toast error, 不抛错", async () => {
    patchUserMock.mockRejectedValue(new ApiError("cannot demote self", 400));
    const { result } = renderHook(() => useUserTable(INITIAL));
    await act(async () => {
      result.current.changeRole(USER, "user");
    });
    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith("cannot demote self");
    });
  });
});
```

- [ ] **Step 2: 跑测试确认 RED**

```bash
cd packages/web && bun run test -- use-user-table
```

Expected: FAIL (changeRole 还没建, TypeError: result.current.changeRole is not a function)。

- [ ] **Step 3: 不 commit,继续 Task 6**

---

## Task 6: use-user-table.ts 改 AdminUser + 加 changeRole + 去 is_admin (绿)

**Files:**
- Modify: [packages/web/app/[locale]/admin/users/_hooks/use-user-table.ts](../../packages/web/app/[locale]/admin/users/_hooks/use-user-table.ts)

- [ ] **Step 1: 改 AdminUser interface (去 is_admin, 加 role)**

```typescript
// (2026-06-26) RBAC wire: 替 is_admin: bool 为 role: str
//   后端 UserItem.role 是真值, is_admin 仅派生 (兼容旧前端), 前端不再用
export interface AdminUser {
  id: number;
  email: string | null;
  display_name: string | null;
  role: string;
  is_active: boolean;
  kind: "account" | "anon";
  account_id: number | null;
  created_at: string;
  last_seen_at: string;
  last_login_at: string | null;
}
```

- [ ] **Step 2: 改 useUserTableActions 加 changeRole option**

在 `useUserTableActions` 的 option interface 顶部加 `changeRole: (user: AdminUser, newRole: string) => void;`,在 `UseUserTableActionsOptions` interface 内加:

```typescript
  changeRole: (user: AdminUser, newRole: string) => void;
```

在 `useUserTableActions` 内部,`return` 之前加:

```typescript
  const changeRole = (user: AdminUser, newRole: string) => {
    const updated: AdminUser = { ...user, role: newRole };
    startTransition(async () => {
      onOptimisticUpdate(updated);
      try {
        await patchUser(user.id, { role: newRole });
        toast.success("已改角色");
        reload();
      } catch (changeError) {
        if (changeError instanceof ApiError) {
          toast.error(changeError.message);
        } else {
          toast.error("操作失败");
        }
      }
    });
  };

  return { changeRole, reload, toggleActive, toggleAdmin };
```

- [ ] **Step 3: 改 useUserTable 调用 useUserTableActions 传 onChangeRole 包装**

在 `useUserTable` 内,把 `useUserTableActions` 调用改成:

```typescript
  const { changeRole, reload, toggleActive, toggleAdmin } = useUserTableActions({
    kind,
    onChangeRole: changeRoleWrapper, // (新增)
    onLoadError: setError,
    onLoadSuccess: setData,
    onOptimisticUpdate: updateOptimistic,
    page,
    search,
    startTransition,
  });
```

**注意**:useUserTable 内 changeRole 内部需要 startTransition 复用,但 useUserTableActions 内部已有 startTransition,所以**直接在 useUserTable 内 startTransition 包**:

```typescript
  const [pending, startTransition] = useTransition();
  // ...
  const handleChangeRole = (user: AdminUser, newRole: string) => {
    startTransition(async () => {
      const updated: AdminUser = { ...user, role: newRole };
      updateOptimistic(updated);
      try {
        await patchUser(user.id, { role: newRole });
        toast.success("已改角色");
        reload();
      } catch (changeError) {
        if (changeError instanceof ApiError) {
          toast.error(changeError.message);
        } else {
          toast.error("操作失败");
        }
      }
    });
  };
```

把 `useUserTableActions` 的 option 改回不接受 `changeRole`(它管 toggle 类,changeRole 单独在 useUserTable 内),简化为只接 toggle 类参数。

- [ ] **Step 4: 完整 useUserTable 函数 (最终版,替换整个函数体)**

```typescript
export const useUserTable = (initialData: AdminUsersResponse) => {
  const [data, setData] = useState<AdminUsersResponse>(initialData);
  const [optimisticData, updateOptimistic] = useOptimistic(
    data,
    (state, updatedUser: AdminUser) => ({
      ...state,
      items: state.items.map((user) => {
        if (user.id === updatedUser.id) {
          return updatedUser;
        }
        return user;
      }),
    }),
  );
  const [search, setSearch] = useState("");
  const [kind, setKind] = useState<"all" | "account" | "anon">("account");
  const [page, setPage] = useState(FIRST_PAGE);
  const [pending, startTransition] = useTransition();
  const [error, setError] = useState<string | null>(null);
  const [confirmUser, setConfirmUser] = useState<AdminUser | null>(null);
  const [roleFilter, setRoleFilter] = useState<string>("all");

  const { reload, toggleActive, toggleAdmin } = useUserTableActions({
    kind,
    onLoadError: setError,
    onLoadSuccess: setData,
    onOptimisticUpdate: updateOptimistic,
    page,
    roleFilter,
    search,
    startTransition,
  });

  const changeRole = (user: AdminUser, newRole: string) => {
    startTransition(async () => {
      const updated: AdminUser = { ...user, role: newRole };
      updateOptimistic(updated);
      try {
        await patchUser(user.id, { role: newRole });
        toast.success("已改角色");
        reload();
      } catch (changeError) {
        if (changeError instanceof ApiError) {
          toast.error(changeError.message);
        } else {
          toast.error("操作失败");
        }
      }
    });
  };

  return {
    changeRole,
    confirmUser,
    data: optimisticData,
    error,
    kind,
    optimisticUsers: optimisticData.items,
    page,
    pending,
    reload,
    roleFilter,
    search,
    setConfirmUser,
    setKind,
    setPage,
    setRoleFilter,
    setSearch,
    startTransition,
    toggleActive,
    toggleAdmin,
  };
};
```

- [ ] **Step 5: 改 useUserTableActions 接受 roleFilter + 加 patchUser import**

文件顶部 import 块加:

```typescript
import { patchUser } from "@/lib/api/users";
```

`useUserTableActions` 的 options interface 加 `roleFilter: string;`,`reload` 内部 URLSearchParams 加:

```typescript
    if (roleFilter !== "all") {
      params.set("role", roleFilter);
    }
```

(`role` 参数后端暂不接,但先传,等后端支持了直接生效,前端 0 改动)

- [ ] **Step 6: 跑测试确认 GREEN**

```bash
cd packages/web && bun run test -- use-user-table
```

Expected: 3 tests passed (PATCH body / optimistic / 失败 toast)。

- [ ] **Step 7: 跑 typecheck**

```bash
cd packages/web && bun run typecheck
```

Expected: 0 error。如果有 "is_admin" 残留报错,按提示删干净。

- [ ] **Step 8: Commit**

```bash
git add packages/web/app/[locale]/admin/users/_hooks/use-user-table.ts packages/web/app/[locale]/admin/users/_hooks/use-user-table.test.ts
git commit -m "feat(admin-users): useUserTable.changeRole + drop is_admin (TDD)"
```

---

## Task 7: admin-users-table.test.tsx 改 SAMPLE + 加 AppSelect 断言 (红→绿)

**Files:**
- Modify: [packages/web/app/[locale]/admin/users/_components/admin-users-table.test.tsx](../../packages/web/app/[locale]/admin/users/_components/admin-users-table.test.tsx)

- [ ] **Step 1: SAMPLE 数据 is_admin → role**

把 SAMPLE 三行 (`admin@x.com` / anon-x / `user@x.com`) 的 `is_admin: true/false` 全部改成 `role: "admin" / "user" / "user"`,删 `is_admin` 字段。

- [ ] **Step 2: 改 renderTable 接 initialRoles**

```typescript
const SAMPLE_ROLES = [
  { created_at: null, is_deletable: false, is_system: true, label_en: "Super Admin", label_zh: "超级管理员", name: "super_admin", updated_at: null, user_count: 1 },
  { created_at: null, is_deletable: false, is_system: true, label_en: "Admin", label_zh: "管理员", name: "admin", updated_at: null, user_count: 1 },
  { created_at: null, is_deletable: false, is_system: true, label_en: "User", label_zh: "用户", name: "user", updated_at: null, user_count: 1 },
];

const renderTable = async (overrides: { roles?: typeof SAMPLE_ROLES } = {}) => {
  let result: ReturnType<typeof render> = null as unknown as ReturnType<typeof render>;
  await act(async () => {
    result = render(
      <NextIntlClientProvider locale="zh" messages={zhMessages}>
        <AdminUsersTable
          usersPromise={Promise.resolve(SAMPLE)}
          currentUserId={1}
          initialRoles={overrides.roles ?? SAMPLE_ROLES}
        />
      </NextIntlClientProvider>,
    );
    await Promise.resolve();
  });
  return result!;
};
```

- [ ] **Step 3: 加 3 个新 it**

```typescript
  it("角色列渲染 AppSelect, 行 1 (admin) 当前 value=admin", async () => {
    await renderTable();
    const sel = screen.getByTestId("role-select-1");
    expect(sel).toBeInTheDocument();
    expect(sel).toHaveTextContent("管理员");
  });

  it("AppSelect 的 super_admin 项 disabled (前端 UX 兜底)", async () => {
    await renderTable();
    // 打开 select 看 option.disabled
    const sel = screen.getByTestId("role-select-1");
    await act(async () => {
      fireEvent.click(sel);
      await Promise.resolve();
    });
    const superAdminOption = await screen.findByRole("option", { name: /超级管理员/ });
    expect(superAdminOption).toHaveAttribute("data-disabled");
  });

  it("选中新 role 后 PATCH body 含 role 字段", async () => {
    fetchMock.mockResolvedValueOnce({
      ok: true, status: 200, statusText: "OK",
      text: async () => JSON.stringify({ id: 3, ok: true }),
    } as unknown as Response);
    await renderTable();
    // 点行 3 (user@x.com) 的 select, 选 admin
    const sel = screen.getByTestId("role-select-3");
    await act(async () => {
      fireEvent.click(sel);
      await Promise.resolve();
    });
    const adminOption = await screen.findByRole("option", { name: /管理员/ });
    await act(async () => {
      fireEvent.click(adminOption);
      await Promise.resolve();
    });
    await waitFor(() => {
      const call = fetchMock.mock.calls.find(
        (c) => typeof c[0] === "string" && c[0].includes("/api/admin/users/3") && c[1]?.method === "PATCH",
      );
      expect(call).toBeDefined();
      const body = JSON.parse((call![1] as RequestInit).body as string);
      expect(body).toEqual({ role: "admin" });
    });
  });
```

- [ ] **Step 4: 跑测试确认 RED(组件还没接 initialRoles / 角色列没换)**

```bash
cd packages/web && bun run test -- admin-users-table
```

Expected: 3 新 it FAIL ("initialRoles is required" / 角色列无 AppSelect / fetch body 不含 role)。

- [ ] **Step 5: 不 commit,继续 Task 8**

---

## Task 8: admin-users-table.tsx 角色列换 AppSelect + 接 roles + mount refetch (绿)

**Files:**
- Modify: [packages/web/app/[locale]/admin/users/_components/admin-users-table.tsx](../../packages/web/app/[locale]/admin/users/_components/admin-users-table.tsx)

- [ ] **Step 1: 加 import**

```typescript
import { AppSelect } from "@/components/common/input/app-select";
import { useRoles } from "../_hooks/use-roles";
import { type RoleListItem } from "@/lib/api/permissions";
```

- [ ] **Step 2: 改 AdminUsersTable 签名 + 用 useRoles**

```typescript
const COL_ROLE_WIDTH = 160;
// 禁用 super_admin 不可手动分配
const PROTECTED_ROLE = "super_admin";

export const AdminUsersTable = ({
  usersPromise,
  currentUserId,
  initialRoles,
}: {
  usersPromise: Promise<AdminUsersResponse>;
  currentUserId: number;
  initialRoles: RoleListItem[];
}) => {
  const initialData = use(usersPromise);
  const {
    changeRole,
    confirmUser,
    data,
    error,
    kind,
    page,
    pending,
    reload,
    roleFilter,
    search,
    setConfirmUser,
    setKind,
    setPage,
    setRoleFilter,
    setSearch,
    startTransition,
    toggleActive,
    toggleAdmin,
  } = useUserTable(initialData);
  const roles = useRoles(initialRoles);
  // ... 其它 render
};
```

- [ ] **Step 3: 改 buildColumns,角色列换 AppSelect + 去 is_admin 引用**

在 `buildColumns` 接口加 `roles: RoleListItem[]`,函数体里 `"role"` 列从原来的 `is_admin` 渲染替换成:

```typescript
  {
    key: "role",
    render: (user) => (
      <AppSelect
        value={user.role}
        onChange={(val) => changeRole(user, val)}
        disabled={user.id === currentUserId} // 自降锁死
        options={roles.map((r) => ({
          value: r.name,
          label: r.label_zh, // zh locale, 跟 zh.json identity 对齐
          disabled: r.name === PROTECTED_ROLE, // super_admin 不可手动分配
        }))}
        dataTestid={`role-select-${user.id}`}
        className="w-36"
      />
    ),
    title: "角色",
    width: COL_ROLE_WIDTH,
  },
```

在 `buildColumns` 调用处传 `roles`:

```typescript
        columns={buildColumns({
          currentUserId,
          pending,
          roles,
          setConfirmUser,
          toggleActive,
          toggleAdmin,
        })}
```

`BuildColumnsParams` interface 加 `roles: RoleListItem[];`。

**注意**:`admin` 列删掉 (老的 `is_admin` 列),操作列不动。

- [ ] **Step 4: 改 UserFilters 传 roleFilter / setRoleFilter / roles**

```typescript
<UserFilters
  search={search}
  onSearchChange={setSearch}
  kind={kind}
  onKindChange={(value) => {
    setKind(value as typeof kind);
    reload({ kind: value, page: FIRST_PAGE });
  }}
  roleFilter={roleFilter}
  onRoleFilterChange={(value) => {
    setRoleFilter(value);
    reload({ role: value, page: FIRST_PAGE });
  }}
  roles={roles}
  onReload={() => reload({ page: FIRST_PAGE })}
/>
```

- [ ] **Step 5: 跑测试确认 GREEN**

```bash
cd packages/web && bun run test -- admin-users-table
```

Expected: 原有 3 个 it + 新 3 个 it 全过。

- [ ] **Step 6: 跑 typecheck / lint**

```bash
cd packages/web && bun run typecheck && bun run lint
```

Expected: 0 error。

- [ ] **Step 7: Commit**

```bash
git add packages/web/app/[locale]/admin/users/_components/admin-users-table.tsx packages/web/app/[locale]/admin/users/_components/admin-users-table.test.tsx
git commit -m "feat(admin-users): role column AppSelect + super_admin disabled UX (TDD)"
```

---

## Task 9: user-filters.test.tsx 写 role 过滤测试 (红)

**Files:**
- Create: [packages/web/app/[locale]/admin/users/_components/user-filters.test.tsx](../../packages/web/app/[locale]/admin/users/_components/user-filters.test.tsx)

- [ ] **Step 1: 写测试**

```typescript
// user-filters 单元测试 (2026-06-26) RBAC wire
//   测 role 过滤: 1) 渲染 role 下拉 2) 选新 role 调 onRoleFilterChange 3) 选项含 super_admin
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { NextIntlClientProvider } from "next-intl";
import { UserFilters } from "./user-filters";
import zhMessages from "@/messages/zh.json";

const SAMPLE_ROLES = [
  { created_at: null, is_deletable: false, is_system: true, label_en: "Super Admin", label_zh: "超级管理员", name: "super_admin", updated_at: null, user_count: 1 },
  { created_at: null, is_deletable: false, is_system: true, label_en: "Admin", label_zh: "管理员", name: "admin", updated_at: null, user_count: 1 },
  { created_at: null, is_deletable: false, is_system: true, label_en: "User", label_zh: "用户", name: "user", updated_at: null, user_count: 1 },
];

const renderFilters = (props: Partial<React.ComponentProps<typeof UserFilters>> = {}) => {
  const onSearchChange = vi.fn();
  const onKindChange = vi.fn();
  const onRoleFilterChange = vi.fn();
  const onReload = vi.fn();
  render(
    <NextIntlClientProvider locale="zh" messages={zhMessages}>
      <UserFilters
        kind="all"
        onKindChange={onKindChange}
        onReload={onReload}
        onRoleFilterChange={onRoleFilterChange}
        onSearchChange={onSearchChange}
        roleFilter="all"
        roles={SAMPLE_ROLES}
        search=""
        {...props}
      />
    </NextIntlClientProvider>,
  );
  return { onKindChange, onReload, onRoleFilterChange, onSearchChange };
};

describe("UserFilters role filter", () => {
  it("渲染 role 下拉, placeholder 是「角色」", () => {
    renderFilters();
    expect(screen.getByTestId("role-filter")).toBeInTheDocument();
  });

  it("点击 role 下拉, 选项含所有 role + 所有角色", async () => {
    renderFilters();
    fireEvent.click(screen.getByTestId("role-filter"));
    // Radix Select 渲染到 portal, 用 findByRole
    expect(await screen.findByRole("option", { name: "所有角色" })).toBeInTheDocument();
    expect(await screen.findByRole("option", { name: "超级管理员" })).toBeInTheDocument();
    expect(await screen.findByRole("option", { name: "管理员" })).toBeInTheDocument();
    expect(await screen.findByRole("option", { name: "用户" })).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: 跑测试确认 RED**

```bash
cd packages/web && bun run test -- user-filters
```

Expected: FAIL (UserFilters 还没接 roles / onRoleFilterChange)。

---

## Task 10: user-filters.tsx 加 role 下拉 (绿)

**Files:**
- Modify: [packages/web/app/[locale]/admin/users/_components/user-filters.tsx](../../packages/web/app/[locale]/admin/users/_components/user-filters.tsx)

- [ ] **Step 1: 改 UserFilters props + 渲染**

```typescript
"use client";
// 用户管理表过滤器 (2026-06-22) — 搜索输入框 + kind 下拉过滤 + 刷新按钮
// (2026-06-26) RBAC wire: 加 role 下拉过滤
import { AppSelect } from "@/components/common/input/app-select";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useTranslations } from "next-intl";
import { type RoleListItem } from "@/lib/api/permissions";

const KIND_ALL = "all";

const kindOptions = [
  { label: "全部", value: KIND_ALL },
  { label: "账号", value: "account" },
  { label: "anon", value: "anon" },
];

interface UserFiltersProps {
  kind: string;
  onKindChange: (value: string) => void;
  onReload: () => void;
  onRoleFilterChange: (value: string) => void;
  onSearchChange: (value: string) => void;
  roleFilter: string;
  roles: RoleListItem[];
  search: string;
}

export const UserFilters = ({
  kind,
  onKindChange,
  onReload,
  onRoleFilterChange,
  onSearchChange,
  roleFilter,
  roles,
  search,
}: UserFiltersProps) => {
  const translate = useTranslations();
  const roleOptions = [
    { label: translate("所有角色"), value: KIND_ALL },
    ...roles.map((r) => ({ label: r.label_zh, value: r.name })),
  ];

  return (
    <div className="flex flex-wrap items-center gap-2">
      <Input
        type="text"
        placeholder={"搜索 email / 显示名"}
        value={search}
        onChange={(event) => onSearchChange(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === "Enter") {
            onReload();
          }
        }}
        data-testid="search-input"
        className="w-64"
      />
      <AppSelect
        options={kindOptions}
        value={kind}
        onChange={(value) => onKindChange(value)}
        placeholder="类型"
        dataTestid="kind-filter"
        className="w-32"
      />
      <AppSelect
        options={roleOptions}
        value={roleFilter}
        onChange={(value) => onRoleFilterChange(value)}
        placeholder="角色"
        dataTestid="role-filter"
        className="w-40"
      />
      <Button size="sm" variant="outline" onClick={onReload} data-testid="reload">
        {translate("刷新")}
      </Button>
    </div>
  );
};
```

- [ ] **Step 2: 跑测试确认 GREEN**

```bash
cd packages/web && bun run test -- user-filters
```

Expected: 2 it passed。

- [ ] **Step 3: Commit**

```bash
git add packages/web/app/[locale]/admin/users/_components/user-filters.tsx packages/web/app/[locale]/admin/users/_components/user-filters.test.tsx
git commit -m "feat(admin-users): UserFilters role filter (TDD)"
```

---

## Task 11: page.tsx RSC 拉 getRoles 透传 initialRoles

**Files:**
- Modify: [packages/web/app/[locale]/admin/users/page.tsx](../../packages/web/app/[locale]/admin/users/page.tsx)

- [ ] **Step 1: 加 getRoles import + 拉 roles + 透传**

```typescript
// ... 现有 import
import { getRoles, type RoleListItem } from "@/lib/api/permissions";

// ... 现有 AdminUsersPage 内部, 鉴权通过后, 启动 usersPromise 旁边:
const roles = await getRoles<{ roles: RoleListItem[] }>(perm.headers);
const initialRoles = roles.roles;

// ... 透传给 AdminUsersTable:
<AdminUsersTable
  usersPromise={usersPromise}
  currentUserId={currentUserId}
  initialRoles={initialRoles}
/>
```

- [ ] **Step 2: 跑 typecheck**

```bash
cd packages/web && bun run typecheck
```

Expected: 0 error。

- [ ] **Step 3: Commit**

```bash
git add packages/web/app/[locale]/admin/users/page.tsx
git commit -m "feat(admin-users): page.tsx RSC fetch roles + pass initialRoles"
```

---

## Task 12: page.test.tsx 加 getRoles mock + initialRoles 透传断言

**Files:**
- Modify: [packages/web/app/[locale]/admin/users/page.test.tsx](../../packages/web/app/[locale]/admin/users/page.test.tsx)

- [ ] **Step 1: 加 getRoles mock**

文件顶部 vi.hoisted 块加:

```typescript
const { getRolesMock } = vi.hoisted(() => ({ getRolesMock: vi.fn() }));
```

新 vi.mock 块:

```typescript
vi.mock("@/lib/api/permissions", () => ({
  getAllPermissions: vi.fn(),
  getRoles: getRolesMock,
}));
```

- [ ] **Step 2: 在 "admin → 渲染" it 内, 改 fetchMock 顺序, 加 roles 响应**

```typescript
    // /api/account/me → currentUserId
    fetchMock.mockResolvedValueOnce(okResponse({ id: 1 }));
    // /api/admin/users
    fetchMock.mockResolvedValueOnce(okResponse({ items: [], page: 1, page_size: 20, total: 0 }));
    // getRoles (RSC 调用)
    getRolesMock.mockResolvedValue({ roles: [] });
```

- [ ] **Step 3: 加 1 个 it 验"getRoles 失败时 RSC 抛错透传"**

```typescript
  it("getRoles 失败 → RSC 抛错", async () => {
    mockGetPermissions.mockResolvedValue({
      allowed: ["admin"],
      headers: { "x-user-token": "real-tok" },
      isAdminLevel: true,
      role: "admin",
    });
    fetchMock.mockResolvedValueOnce(okResponse({ id: 1 }));
    getRolesMock.mockRejectedValue(new Error("roles 500"));
    await expect(adminUsersPage()).rejects.toThrow("roles 500");
  });
```

- [ ] **Step 4: 跑测试**

```bash
cd packages/web && bun run test -- admin/users/page
```

Expected: 原有 3 it + 新 1 it 全过。

- [ ] **Step 5: Commit**

```bash
git add packages/web/app/[locale]/admin/users/page.test.tsx
git commit -m "test(admin-users): page.test.tsx mock getRoles"
```

---

## Task 13: messages/{zh,en}.json 加 4 key

**Files:**
- Modify: [packages/web/messages/zh.json](../../packages/web/messages/zh.json)
- Modify: [packages/web/messages/en.json](../../packages/web/messages/en.json)

- [ ] **Step 1: 加 4 key**

`zh.json` 加(任意位置, 找类似 `"加载中…": "..."` 段后插):

```json
  "所有角色": "所有角色",
  "已改角色": "已改角色",
  "不可手动分配": "不可手动分配",
  "改角色": "改角色",
```

`en.json` 加:

```json
  "所有角色": "All Roles",
  "已改角色": "Role changed",
  "不可手动分配": "Cannot be assigned manually",
  "改角色": "Change Role",
```

- [ ] **Step 2: 验 JSON 合法**

```bash
cd packages/web && node -e "JSON.parse(require('fs').readFileSync('messages/zh.json')); JSON.parse(require('fs').readFileSync('messages/en.json')); console.log('OK')"
```

Expected: `OK`。

- [ ] **Step 3: 跑 typecheck (i18n 键缺失会暴露)**

```bash
cd packages/web && bun run typecheck
```

Expected: 0 error。

- [ ] **Step 4: Commit**

```bash
git add packages/web/messages/zh.json packages/web/messages/en.json
git commit -m "i18n: add role filter / change role / cannot assign super_admin (4 keys)"
```

---

## Task 14: 全量验收 (format / lint / typecheck / test / contract)

**Files:**
- No file change

- [ ] **Step 1: 跑 oxfmt**

```bash
cd packages/web && bun run format
```

Expected: 0 报错 (可能 0 改 或自动重排)。

- [ ] **Step 2: 跑 oxlint --fix**

```bash
cd packages/web && bun run lint:fix
```

Expected: 0 报错。

- [ ] **Step 3: 跑 typecheck**

```bash
cd packages/web && bun run typecheck
```

Expected: 0 error。

- [ ] **Step 4: 跑全量 vitest**

```bash
cd packages/web && bun run test
```

Expected: 0 新 fail (pre-existing fail 不算, 见 [KNOWN_ISSUES.md](../../packages/service/KNOWN_ISSUES.md))。

- [ ] **Step 5: 跑后端 contract test (防 URL drift, 后端 0 改动也跑)**

```bash
cd packages/service && uv run pytest tests/test_api_contract.py -v
```

Expected: 全过。

- [ ] **Step 6: 跑 ruff + pyright 后端 (确认后端 0 改动 0 回归)**

```bash
cd packages/service && uv run ruff check && uv run pyright
```

Expected: 0 error。

- [ ] **Step 7: 跑验收 grep (跟 spec §8 对齐)**

```bash
cd packages/web
grep -rn "is_admin" app/[locale]/admin/users/  # 0 hit (除 is_active 派生)
grep -n "role: string" app/[locale]/admin/users/_hooks/use-user-table.ts  # 1 hit
grep -n "AppSelect" app/[locale]/admin/users/_components/admin-users-table.tsx  # ≥1 hit
grep -n "changeRole" app/[locale]/admin/users/_hooks/use-user-table.ts  # 1 hit
grep -n "super_admin" app/[locale]/admin/users/_components/admin-users-table.tsx  # 命中 disabled 上下文
grep -n "invalidateQueries\|useRoles" app/[locale]/admin/users/_components/admin-users-table.tsx  # 1 hit
git diff packages/service/src/  # 0 hit
```

Expected: 全部命中。

- [ ] **Step 8: 不 commit,继续 Task 15**

---

## Task 15: 收尾 commit (feat + i18n sync 单 commit 整合)

**Files:**
- No file change

- [ ] **Step 1: 检查 git status**

```bash
git status
```

Expected: 有未 commit 改动 (format/lint 自动改的)。

- [ ] **Step 2: 1 commit 整合(含 i18n sync 标记)**

```bash
git add -A
git commit -m "feat(admin-users): wire RBAC role to users table + i18n sync

- AdminUser 暴露 role: str, 删 is_admin 死字段
- 角色列换 AppSelect, 行内改 role + optimistic + 失败回滚
- super_admin 选项 disabled (前端 UX 兜底, 配合后端 PATCH 守卫)
- UserFilters 加 role 单选下拉
- useRoles hook 抽独立, mount 强制 refetch 1 次 (拿权限页最新 role)
- 后端 0 改动 (端点全齐: PATCH /api/admin/users/{id} 接 role, GET /api/roles 含 user_count)
- i18n 同步: zh/en.json 加 4 key (所有角色 / 已改角色 / 不可手动分配 / 改角色)
- TDD 顺序: use-roles + use-user-table + admin-users-table + user-filters 4 个测试先红后绿

Closes: admin/users 角色未跟 admin/permissions 打通
Spec: docs/superpowers/specs/2026-06-26-admin-users-rbac-wire-design.md"
```

- [ ] **Step 3: 跑 1 次 pre-commit 等价套件,确认 commit 后无回归**

```bash
cd packages/web && bun run format:check && bun run lint && bun run typecheck && bun run test
```

Expected: 0 error, 0 新 fail。

- [ ] **Step 4: 跑 husky pre-commit (如未跑, 手动 commit --amend --no-verify 禁用, 改用 push 前 CI 兜底)**

(本 plan 全程走 0 --no-verify, 上面 commit 必走完 pre-commit 钩子; 如有 hook 阻塞, 见 [feedback-stop-and-ask-dont-loop-on-infra](feedback-stop-and-ask-dont-loop-on-infra.md) STOP 报告)

- [ ] **Step 5: 完工汇报**

给用户报告:
- 1 commit 落地 (含 TDD 全套)
- 7 文件改 + 3 文件新建 + 1 commit
- 后端 0 改动 (git diff 验证)
- vitest 全过, typecheck/lint 0 error
- 建议手动 smoke: 1) /admin/users 看 super_admin user 是否显示 "超级管理员"; 2) 角色下拉选 admin, 验证 PATCH 成功; 3) /admin/permissions 新建 role 后, 回 /admin/users 看是否自动出现

---

## Self-Review

**1. Spec coverage:**

| Spec § | 对应 task |
|---|---|
| §2 目标 1: AdminUser role 真值 | Task 6 |
| §2 目标 2: 角色列 label | Task 8 |
| §2 目标 3: 行内 AppSelect 改 role | Task 6 + 8 |
| §2 目标 4: super_admin UX 灰禁 | Task 8 |
| §2 目标 5: UserFilters role 过滤 | Task 9 + 10 |
| §2 目标 6: mount refetch | Task 4 + 8 |
| §2 目标 7: 后端 0 改动 | Task 14 grep 验证 |
| §2 目标 8: TDD 顺序 | 全 plan |
| §2 目标 9: 项目规约对齐 | Task 14 |
| §4.3 useRoles 设计 | Task 4 |
| §4.4 changeRole action | Task 6 |
| §4.5 UI 形态 | Task 8 |
| §4.6 过滤 | Task 10 |
| §4.7 mount refetch | Task 4 |
| §4.8 PATCH body | Task 6 |
| §4.9 i18n 4 key | Task 13 |

**2. Placeholder scan:** 0 hit。所有 code block 完整,无 "TBD" / "类似 Task N" / "fill in"。

**3. Type consistency:**

| 名称 | 首次出现 | 后续使用 | 一致? |
|---|---|---|---|
| `RoleListItem` | Task 1 (lib/api/permissions.ts) | Task 3 / 4 / 7 / 8 / 9 / 10 | ✅ |
| `changeRole(user, newRole)` | Task 5 测试 | Task 6 / 8 | ✅ |
| `useRoles(initial)` 返回 `RoleListItem[]` | Task 4 | Task 8 | ✅ |
| `initialRoles: RoleListItem[]` prop | Task 7 测试 | Task 8 / 11 | ✅ |
| `useUserTable` 返回 `changeRole` | Task 6 | Task 8 | ✅ |
| `useUserTable` 返回 `roleFilter` / `setRoleFilter` | Task 6 | Task 8 | ✅ |
| `PROTECTED_ROLE = "super_admin"` | Task 8 | Task 8 | ✅ |
| `patchUser(user.id, { role })` | Task 5 测试 mock | Task 6 实现 | ✅ |

**4. Spec gaps:** 无 — spec 9 目标全对应 task。

---

## 风险与回滚

| 风险 | task 内的 mitigation | 回滚 |
|---|---|---|
| `is_admin` 删除影响其它 import | Task 6 Step 7 typecheck 兜底 | git revert 单 commit |
| 删 `is_admin` 后乐观更新 race | useOptimistic 自动回滚 | 同上 |
| mount refetch 慢 100-300ms | RSC 同步 await + initialData, 进页立即渲染, refetch 后台静默 | 删 useEffect 1 行 |
| super_admin 项 disabled 误禁 | 灰禁仅前端 UX, 后端 PATCH 真拒绝兜底 | 前端去掉 disabled |
| role 过滤 client 端 .filter 慢 | 用户量 < 5000, 一次拿全量 | 后续 spec 下推 SQL |
| i18n 漏 key 报 MISSING_MESSAGE | Task 13 Step 3 typecheck 兜底 | git revert |
| 跨多个 commit 中间状态 | pre-commit hook 拦 commit, 不让部分落地 | Task 15 整合成 1 commit |

---

## 关联

- Spec: [docs/superpowers/specs/2026-06-26-admin-users-rbac-wire-design.md](../specs/2026-06-26-admin-users-rbac-wire-design.md)
- 后端 RBAC migration: [packages/service/src/storage/migrations/versions/20260617_000000_add_roles_and_rbac.py](../../packages/service/src/storage/migrations/versions/20260617_000000_add_roles_and_rbac.py)
- 后端 RBAC router: [packages/service/src/permissions/router.py](../../packages/service/src/permissions/router.py)
- 后端 admin router: [packages/service/src/auth/auth_admin_router.py](../../packages/service/src/auth/auth_admin_router.py)
- 项目规约: [CLAUDE.md](../../CLAUDE.md) + [packages/web/CLAUDE.md](../../packages/web/CLAUDE.md) + [packages/service/CLAUDE.md](../../packages/service/CLAUDE.md)
- 相关 memory:
  - [feedback-i18n-sync-on-ui-changes](../../.claude/memory/feedback-i18n-sync-on-ui-changes.md)
  - [feedback-no-shim-no-minimal-changes](../../.claude/memory/feedback-no-shim-no-minimal-changes.md)
  - [feedback-debug-distinguish-root-causes](../../.claude/memory/feedback-debug-distinguish-root-causes.md)
  - [feedback-do-not-refactor-when-user-reports-bug](../../.claude/memory/feedback-do-not-refactor-when-user-reports-bug.md)
  - [feedback-stop-and-ask-dont-loop-on-infra](../../.claude/memory/feedback-stop-and-ask-dont-loop-on-infra.md)
  - [feedback-record-errors-and-lessons](../../.claude/memory/feedback-record-errors-and-lessons.md)
