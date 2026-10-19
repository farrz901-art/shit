# Admin Users 打通 RBAC 角色 (2026-06-26)

> 起源: 2026-06-26 用户报 "admin/users 角色没跟 admin/permissions 打通", 根因排查发现后端早已打通 (2026-06-17 RBAC migration), 前端还在用派生的 `is_admin: bool` 当唯一真值, 列渲染把 super_admin 显示成 "admin" badge.
> 范围: 前端 7 文件 + 2 测试文件 + i18n 4 key, **后端 0 改动** (端点齐了: PATCH `/api/admin/users/{id}` 接 `role: str`, GET `/api/roles` 返全 role 列表含 user_count).
> 不依赖: 任何其它 spec.

## 1. 背景与根因

### 1.1 当前两线状态

| 层 | 状态 |
|---|---|
| DB | ✅ 已统一: `accounts.role TEXT` (2026-06-17 删 `is_admin`, 老 `is_admin=TRUE` 全部迁 `role='super_admin'`) |
| 后端 API | ✅ 已统一: `UserItem.role: str` 真值, `is_admin: bool` 仅是派生 (注释 "兼容旧前端") |
| 后端 PATCH | ✅ 已统一: `PatchUserRequest.role: str` 接 PATCH, 自降 super_admin → 400 |
| 后端 roles 列表 | ✅ 存在: `GET /api/roles` 返全角色含 user_count |
| 前端 API 包装 | ❌ 缺: `lib/api/permissions.ts` 只包装了 `createRole` POST, 缺 get/update/delete; `lib/api/users.ts` 的 `createUser` 还在传老 `is_admin: bool` |
| 前端数据模型 | ❌ 缺: `AdminUser` interface 没声明 `role`, 派生的 `is_admin` 是死字段 |
| 前端 UI | ❌ 缺: "角色" 列渲染 `is_admin ? "admin" : "—"`, 把 super_admin 误显成 admin |
| 前端操作 | ❌ 缺: toggle 操作发 `{ is_admin: bool }`, 后端 PATCH 现在根本不接这字段, 实际无效 |

### 1.2 阻塞业务

1. **super_admin 看不出区别**: 用户表里 super_admin 跟 admin 都显示 "admin" badge, 误判角色等级
2. **自定义 role 不可见/不可用**: super_admin 在 `/admin/permissions` 创了新 role (e.g. "reviewer"), 用户表完全看不到, 也不能把现有 user 改到 reviewer
3. **前端 "提权" 按钮无效**: 点 "提权" 发 `{ is_admin: true }`, 后端 Pydantic 校验失败 (后端只接 `role`), 静默失败 — 用户看到 toast 成功但实际没改

## 2. 目标

| # | 目标 | 验收 |
|---|---|---|
| 1 | 前端 `AdminUser` 暴露 `role: string` 真值 | `is_admin: bool` 派生字段从前端代码里彻底删除 (TS strict 报错兜底) |
| 2 | 列表"角色"列显示真 role + i18n label | 列渲染读 `user.role` + `roleList` 查 label, e.g. "超级管理员" |
| 3 | 行内 `<AppSelect>` 改 role, 1 次点击到位 | 选完 PATCH `/api/admin/users/{id}` body `role=<selected>`, 乐观更新 + 失败回滚 |
| 4 | super_admin 不可被分配, 前端 UX 兜底 | `<AppSelect>` 的 `super_admin` 选项 `disabled` + AppTooltip "不可手动分配" |
| 5 | UserFilters 加 role 过滤 | 下拉值 = `all` + 全部 role, 选完 refetch |
| 6 | mount 强制 refetch roles 列表 | 用户管理页 mount 时 `queryClient.invalidateQueries(["roles"])` 一次, 拿权限页新建的最新 role |
| 7 | 后端 0 改动 | 本期不改任何 .py 文件, git diff 看 `packages/service/src/` 0 hit |
| 8 | TDD 红→绿顺序 | 2 测试文件先红 (hook + 组件), 后绿, 0 --no-verify |
| 9 | 跟项目规约 100% 对齐 | oxfmt/oxlint/tsgo/vitest 0 error, 1 commit 走 pre-commit 全套 |

## 3. 非目标 (YAGNI)

- ❌ 后端 schema 改动 (Pydantic model / migration / lookup 字典) — 端点全齐
- ❌ 改造 `UserItem.is_admin` 派生字段 (后端注释明写 "兼容旧前端", 移除等下次 spec)
- ❌ 加 `role_label_zh` / `role_label_en` 字段给 `UserItem` — 跟权限管理页 `role_list` 复用 GET `/api/roles` 即够, 单一事实源
- ❌ 改 `CreateInviteButton` 支持创邀请时选 role — 跟本期主线解耦, 另开 spec
- ❌ 加 role 多选过滤 (chip) — 跟 kind/role 列表对齐, 单选下拉够用
- ❌ TanStack Query 跨页 broadcast invalidation — 权限页改完通知用户页, 复杂度过高, mount 强制 refetch 1 次够
- ❌ 删 `lib/api/users.ts` 老的 `createUser` `{ is_admin: bool }` 入参 — 0 调用方 (前面 grep 已确认), 但**保留**函数 (向后兼容未来 ad-hoc 调用)
- ❌ 改匿名用户的 role 显示 (后端给 anon 写死 `role='user'`, 前端照显就行)

## 4. 设计

### 4.1 关键设计原则: 真值在前端, 派生字段在前后端都删

**前端是 Source of Truth for display, 后端是 Source of Truth for data.**

| 字段 | 来源 | 用法 |
|---|---|---|
| `role: string` | 后端 `UserItem.role` 真值 | UI 显示 / 过滤 / PATCH |
| `roleList[].name → label_zh/en` | 后端 `GET /api/roles` 列表 | UI label 查表 |
| ~~`is_admin: bool`~~ | 派生 (后端 + 前端都删) | 历史包袱, 1 刀切干净 |

`is_admin` 的移除路径:

- 后端 `UserItem.is_admin` 注释 "派生: role in ('admin', 'super_admin')" — **保留**, 后端 0 改动 (另 spec 处理)
- 前端 `AdminUser.is_admin` 字段 — **删** (本期)
- 前端所有用 `user.is_admin` 的地方 — **改 `user.role` + 查 `roleList`**

### 4.2 数据流

```
admin/users/page.tsx (RSC)
  ├── getPermissions() → 鉴权 + headers
  ├── apiFetch /api/admin/users → usersPromise (Suspense)
  └── apiFetch /api/roles → rolesList (同步 await, 透传 client)
        │
        ▼ AdminUsersTable (Client)
            │
            ├── useUserTable(initialData) → users state
            ├── useRoles(initialRoles) → roles state + mount invalidate
            │
            ▼ buildColumns()
                │
                ├── "角色" 列 → <AppSelect value=user.role options=roleList
                │                  onChange=(v) => onChangeRole(user, v)
                │                  (super_admin 项 disabled + tooltip)
                │
                └── "操作" 列 → onChangeRole / onToggleActive / setConfirmUser
                                (super_admin 用户的 onChangeRole 也禁用,
                                 防自降锁死, 跟后端 PATCH 守卫对齐)
```

### 4.3 useRoles hook 设计 (新)

```typescript
// packages/web/app/[locale]/admin/users/_hooks/use-roles.ts (新)
export interface RoleListItem {
  name: string;
  label_zh: string;
  label_en: string;
  is_system: boolean;
  is_deletable: boolean;
  user_count: number;
}

export const useRoles = (initial: RoleListItem[]) => {
  const query = useQuery({
    queryKey: ["roles"],
    queryFn: () => listRoles(),
    initialData: initial,
    staleTime: 60_000,
  });
  // mount 强制 refetch 一次 — 权限页新建 role 后能立刻看到
  useEffect(() => {
    query.refetch();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps
  return query.data ?? initial;
};
```

### 4.4 onChangeRole action 设计 (扩 use-user-table)

```typescript
// 跟现有 toggleActive / toggleAdmin 同模式: optimistic + reload
const changeRole = (user: AdminUser, newRole: string) => {
  const updated: AdminUser = { ...user, role: newRole };
  startTransition(async () => {
    onOptimisticUpdate(updated);
    try {
      await apiFetch(`/api/admin/users/${user.id}`, {
        body: { role: newRole },
        method: "PATCH",
      });
      toast.success(t("已改角色"));
      reload();
    } catch (err) {
      if (err instanceof ApiError) toast.error(err.message);
      else toast.error(t("操作失败"));
    }
  });
};
```

### 4.5 UI 形态: 列内 AppSelect (按用户决策 A)

```tsx
// "角色" 列
{
  key: "role",
  render: (user) => (
    <AppSelect
      value={user.role}
      onChange={(v) => onChangeRole(user, v)}
      disabled={user.id === currentUserId}  // 自降锁死, 跟后端守卫对齐
      options={roles.map(r => ({
        label: getLocalizedLabel(r, locale),  // zh→label_zh, en→label_en
        value: r.name,
        disabled: r.name === "super_admin",  // 防越权
      }))}
      data-testid={`role-select-${user.id}`}
    />
  ),
  title: "角色",
  width: 140,
}
```

super_admin 项的 disabled 走 AppSelect `options[].disabled` (封装已经支持, 2026-06-18 appform 验证过). AppTooltip 套外面解释原因.

### 4.6 过滤: role 下拉单选 (按用户决策 B)

```tsx
// UserFilters 加 role prop
<AppSelect
  options={[
    { label: t("所有角色"), value: "all" },
    ...roles.map(r => ({ label: r.label_zh, value: r.name })),
  ]}
  value={roleFilter}
  onChange={onRoleFilterChange}
  placeholder={t("角色")}
  dataTestid="role-filter"
  className="w-40"
/>
```

role 过滤走 URL query, 跟现有 search/kind 对齐. 后端 `/api/admin/users` 现在没接 `role` 过滤, 但本期不动后端 — **过滤 client 端做** (拿到全量后 .filter), 后续 spec 再下推 SQL.

### 4.7 mount 强制 refetch (按用户决策 C)

```tsx
// AdminUsersTable mount
useEffect(() => {
  queryClient.invalidateQueries({ queryKey: ["roles"] });
}, []); // 1 次, 拿权限页最新 role 列表
```

不走 `refetchOnWindowFocus` 模式 (老规矩, 项目 TanStack Query 默认 `refetchOnWindowFocus: false`).

### 4.8 PATCH /api/admin/users/{id} body 改动

**前端发**:

```typescript
{ role: "admin" }  // 替原 { is_admin: true }
```

**后端** (零改动, 引 [auth_admin_router.py:228-232](packages/service/src/auth/auth_admin_router.py#L228-L232) 验证):

```python
class PatchUserRequest(BaseModel):
    is_active: bool | None
    role: str | None  # 真字段
```

### 4.9 i18n 4 key

| zh | en | 用法 |
|---|---|---|
| `角色` | `Role` | 列头 (已存在, 不改) |
| `所有角色` | `All Roles` | 过滤下拉"all" |
| `已改角色` | `Role changed` | toast 成功 |
| `不可手动分配` | `Cannot be assigned manually` | AppTooltip 解释 super_admin 灰禁 |

zh.json 写中文作 key, en.json 翻译. 走项目 i18n 同步规范 ([packages/web/CLAUDE.md §i18n 同步检查](packages/web/CLAUDE.md)).

## 5. 改动文件清单

| 文件 | 性质 | 改动行(估) | 风险 |
|---|---|---|---|
| [packages/web/lib/api/permissions.ts](packages/web/lib/api/permissions.ts) | 改 | +18 | 0 |
| [packages/web/lib/api/users.ts](packages/web/lib/api/users.ts) | 改 | +10 / -2 | 0 |
| [packages/web/app/[locale]/admin/users/_hooks/use-user-table.ts](packages/web/app/[locale]/admin/users/_hooks/use-user-table.ts) | 改 | +30 / -15 | 中 |
| [packages/web/app/[locale]/admin/users/_hooks/use-roles.ts](packages/web/app/[locale]/admin/users/_hooks/use-roles.ts) | 新 | +25 | 低 |
| [packages/web/app/[locale]/admin/users/_hooks/use-roles.test.ts](packages/web/app/[locale]/admin/users/_hooks/use-roles.test.ts) | 新 | +40 | 中 |
| [packages/web/app/[locale]/admin/users/_components/admin-users-table.tsx](packages/web/app/[locale]/admin/users/_components/admin-users-table.tsx) | 改 | +60 / -30 | 高 |
| [packages/web/app/[locale]/admin/users/_components/user-filters.tsx](packages/web/app/[locale]/admin/users/_components/user-filters.tsx) | 改 | +25 / -5 | 低 |
| [packages/web/app/[locale]/admin/users/page.tsx](packages/web/app/[locale]/admin/users/page.tsx) | 改 | +18 / -3 | 低 |
| [packages/web/app/[locale]/admin/users/_components/admin-users-table.test.tsx](packages/web/app/[locale]/admin/users/_components/admin-users-table.test.tsx) | 改 | +50 | 中 |
| [packages/web/app/[locale]/admin/users/page.test.tsx](packages/web/app/[locale]/admin/users/page.test.tsx) | 改 | +30 | 中 |
| [packages/web/messages/zh.json](packages/web/messages/zh.json) | 改 | +4 | 0 |
| [packages/web/messages/en.json](packages/web/messages/en.json) | 改 | +4 | 0 |

**后端 0 改动** (`packages/service/src/` 0 hit).

**测试模式 1 (mock) 全程, 0 PG/Redis**.

## 6. 实施步骤 (TDD 红→绿顺序)

### Phase 1: API 包装 (0 风险, 直接绿)

1. 改 [lib/api/permissions.ts](packages/web/lib/api/permissions.ts) — 加 `getRoles` / `updateRole` / `deleteRole` 包装
2. 改 [lib/api/users.ts](packages/web/lib/api/users.ts) — `createUser` 注释标 deprecated (不删, 0 调用方但保留), 加 `patchUser` 包装

### Phase 2: Hook (TDD 红→绿)

3. **红**: 写 [use-roles.test.ts](packages/web/app/[locale]/admin/users/_hooks/use-roles.test.ts) — 测 mount 强制 refetch 1 次, staleTime 60s
4. **绿**: 写 [use-roles.ts](packages/web/app/[locale]/admin/users/_hooks/use-roles.ts) — 走 TanStack Query
5. **红**: 在 [use-user-table.test.ts](packages/web/app/[locale]/admin/users/_hooks/use-user-table.test.ts) (新建, 之前无) 加 `onChangeRole` 断言: 1) PATCH body 含 `role` 2) optimistic 更新 3) 失败 toast
6. **绿**: 改 [use-user-table.ts](packages/web/app/[locale]/admin/users/_hooks/use-user-table.ts) — 加 `changeRole` action, 删 `is_admin` 死字段, 加 `role: string` 到 `AdminUser`

### Phase 3: UI (TDD 红→绿)

7. **红**: 改 [admin-users-table.test.tsx](packages/web/app/[locale]/admin/users/_components/admin-users-table.test.tsx) — 加 AppSelect 渲染 + `super_admin` 项 disabled + 选中后 PATCH body 断言
8. **绿**: 改 [admin-users-table.tsx](packages/web/app/[locale]/admin/users/_components/admin-users-table.tsx) — 角色列换 AppSelect, 操作列去 is_admin 引用
9. **红**: 改 [user-filters.test.tsx](packages/web/app/[locale]/admin/users/_components/user-filters.test.tsx) (新建) — 测 role 过滤
10. **绿**: 改 [user-filters.tsx](packages/web/app/[locale]/admin/users/_components/user-filters.tsx) — 加 role 下拉

### Phase 4: 入口 + i18n

11. 改 [page.tsx](packages/web/app/[locale]/admin/users/page.tsx) — RSC 同步拉 `getRoles()` 透传 `initialRoles`, 不再 `Promise` (避免 Suspense 边界混乱)
12. 改 [page.test.tsx](packages/web/app/[locale]/admin/users/page.test.tsx) — 加 mock 端点
13. 改 [messages/zh.json](packages/web/messages/zh.json) + [en.json](packages/web/messages/en.json) — 4 key

### Phase 5: 验收

14. 跑 [packages/web/CLAUDE.md §顺序不可颠倒](packages/web/CLAUDE.md):
    - `bun run format`
    - `bun run lint:fix`
    - `bun run typecheck` (tsgo 0 error)
    - `bun run test` (vitest 0 新 fail)
    - `cd packages/service && uv run pytest tests/test_api_contract.py` (后端 0 改动也跑, 防 URL drift)
15. 1 commit: `feat(admin-users): wire RBAC role to users table + mount refetch roles` (含 i18n sync 标记)

## 7. 风险与回滚

| 风险 | 缓解 | 回滚 |
|---|---|---|
| `is_admin` 字段删除影响其它页面 | 实施前 `grep -r "is_admin" packages/web` 全量排查, 必只剩 admin/users 用 | git revert 单 commit |
| 删 is_admin 后乐观更新 race | 走 useOptimistic 自动回滚, 不引入新状态机 | 同上 |
| mount refetch 导致进页慢 100-300ms | 走 RSC 同步 await + initialData, 进页立即渲染, refetch 后台静默 | 删 useEffect 1 行 |
| super_admin 项 disabled 误禁 | 灰禁仅前端 UX, 后端 PATCH 真拒绝兜底, 双保险 | 前端去掉 disabled 即可 (但不推荐) |
| role 过滤 client 端 200+ 行 .filter 慢 | 用户量 < 5000, 一次拿全量 (现有 `kind` 过滤也走客户端) | 改 spec 下推 SQL (后续) |
| i18n 漏 key 报 MISSING_MESSAGE | commit 前 `git diff` 看 t() 字符串 + 同步 zh/en.json | git revert |

## 8. 验收 (跟 §2 目标对齐)

```bash
# 1. AdminUser 真值
grep -rn "is_admin" packages/web/app/[locale]/admin/users/  # 0 hit (除 is_active 派生不冲突)
grep -n "role: string" packages/web/app/[locale]/admin/users/_hooks/use-user-table.ts  # 1 hit

# 2. 角色列渲染
grep -n "AppSelect" packages/web/app/[locale]/admin/users/_components/admin-users-table.tsx  # ≥1 hit (角色列)

# 3. 行内改 role
grep -n "onChangeRole\|changeRole" packages/web/app/[locale]/admin/users/_hooks/use-user-table.ts  # 1 hit

# 4. super_admin 灰禁
grep -n "super_admin" packages/web/app/[locale]/admin/users/_components/admin-users-table.tsx  # 命中 disabled 上下文

# 5. role 过滤
grep -n "roleFilter\|role filter" packages/web/app/[locale]/admin/users/_components/user-filters.tsx  # 1 hit

# 6. mount refetch
grep -n "invalidateQueries" packages/web/app/[locale]/admin/users/_components/admin-users-table.tsx  # 1 hit (key=["roles"])

# 7. 后端 0 改动
git diff packages/service/src/  # 0 hit

# 8. TDD 顺序
git log --oneline -5  # 单 commit, message 含 TDD + i18n sync

# 9. 规约对齐
bun run format:check && bun run lint && bun run typecheck && bun run test  # 全 0 error
```

## 9. 关联

- 后端打通时间: [20260617_000000_add_roles_and_rbac.py](packages/service/src/storage/migrations/versions/20260617_000000_add_roles_and_rbac.py) (2026-06-17)
- 后端 RBAC router: [permissions/router.py](packages/service/src/permissions/router.py) (含 GET `/api/roles`)
- 用户报 bug 起源: 2026-06-26 用户口头 "admin/users 角色没跟 admin/permissions 打通"
- 相关 spec: 暂无 (本期独立)
- 相关 memory:
  - [feedback-i18n-sync-on-ui-changes](feedback-i18n-sync-on-ui-changes.md) — 改 UI 加 t() 必同步 zh/en.json
  - [feedback-no-shim-no-minimal-changes](feedback-no-shim-no-minimal-changes.md) — 删 is_admin 派生字段, 不留 shim
  - [feedback-debug-distinguish-root-causes](feedback-debug-distinguish-root-causes.md) — "两条线" 根因排查
  - [feedback-do-not-refactor-when-user-reports-bug](feedback-do-not-refactor-when-user-reports-bug.md) — 用户报 bug 时不擅自改设计
  - [feedback-verify-with-import-not-pip](feedback-verify-with-import-not-pip.md) — uv 验证包
  - [feedback-record-errors-and-lessons](feedback-record-errors-and-lessons.md) — spec 落档
  - [feedback-no-mock-for-external-systems](feedback-no-mock-for-external-systems.md) — 不 mock 外部, 但 RBAC 后端已经在端点, 本期不动后端 = 隐含 0 外部 mock
