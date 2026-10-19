# RSC 权限统一 + PageGuard 重构

**日期**: 2026-06-18
**状态**: 待实施
**作者**: Claude

## Context

当前鉴权限路由每页至少 2 次 fetch + 2 层检查：

```ts
// 第 1 层 (页面级, 基于 is_admin)
me = await apiFetch("/api/account/me", {headers: serverAuthHeaders()})
if (!me.is_admin) redirect("/")

// 第 2 层 (组件级, 基于 role + allowed)
permissions = await getMyPermissions()
<PageGuard pageKey="admin" permissions={permissions} />
```

**弊端**:
- 每页重复 `serverAuthHeaders()` 拼装 + `/api/account/me` + `/api/permissions/me` 两次 fetch
- `is_admin` 跟 `role + allowed` 两套鉴权并行，`is_admin` 是 role 的派生字段，多此一举
- `serverAuthHeaders()` 在每个需要 apiFetch 的页面重复调用
- RSC 页无统一权限入口，每页自己写 try/catch + redirect

## 目标

- **RSC 页面**: 调一个 `getPermissions()` 函数拿到 role + allowed + headers + 派生方法
- **Client 组件**: Zustand store + hooks 拿同一份数据
- **PageGuard**: 不再收 permissions props，内部通过 role + allowed 判断
- **删 is_admin**: 前端全用 role + allowed 派生的 `isAdminLevel()`

## 非目标

- 不动 `account/settings/page.tsx` 的 `/api/account/me`（用户资料不走权限系）
- 不动后端 `/api/permissions/me` 端点
- 不动后端 `/api/account/me` 端点（倒可继续返 is_admin，前端不用就是）
- 不动 proxy.ts 的路由守卫
- 不动 forbidden.tsx（已是独立 403 页）
- 不动 `lib/auth/auth.server.ts`（serverAuthHeaders 内部封装不动）

## 架构

### 新文件

```
packages/web/
  lib/
    auth/
      permission.ts         → RSC 用: getPermissions()
    hooks/
      usePermissions.ts     → Client 用: Zustand store + hook
      index.ts              → 批量导出 hooks
```

### `lib/auth/permission.ts`（RSC 函数）

```ts
export interface PermissionResult {
  role: string;
  allowed: string[];
  pages: PageMeta[];
  isAdminLevel: boolean;
  isSuperAdmin: boolean;
  can(page: string): boolean;
  headers: Record<string, string>;
}

export async function getPermissions(): Promise<PermissionResult> {
  const headers = await serverAuthHeaders();
  const data = await apiFetch<MyPermissions>("/api/permissions/me", { headers });
  return {
    role: data.role,
    allowed: data.allowed,
    pages: data.pages,
    isAdminLevel: data.role !== "user",
    isSuperAdmin: data.role === "super_admin",
    can: (page: string) => data.role === "super_admin" || data.allowed.includes(page),
    headers,
  };
}
```

### `lib/hooks/usePermissions.ts`（Zustand + Client hook）

```ts
interface PermissionsState {
  role: string | null;
  allowed: string[];
  pages: PageMeta[];
  loaded: boolean;
}

export const usePermissionsStore = create<PermissionsState>((set) => ({
  role: null, allowed: [], pages: [], loaded: false,
  fetch: async () => {
    const data = await apiFetch<MyPermissions>("/api/permissions/me");
    set({ role: data.role, allowed: data.allowed, pages: data.pages, loaded: true });
  },
}));

export function usePermissions() {
  const store = usePermissionsStore();
  useEffect(() => { if (!store.loaded) store.fetch(); }, []);
  const isAdminLevel = store.role !== "user";
  const isSuperAdmin = store.role === "super_admin";
  const can = (page: string) => store.role === "super_admin" || store.allowed.includes(page);
  return { ...store, isAdminLevel, isSuperAdmin, can };
}
```

### 数据流

```
首屏 (RSC):
  getPermissions() → fetch /api/permissions/me → 返回 role + allowed + headers
    ↓
  PageGuard + 业务 apiFetch(perm.headers)  → 撑首屏

Hydrate 后 (Client):
  usePermissions() → Zustand.fetch() → fetch /api/permissions/me → store 填充
    ↓
  后续组件交互直接用 zustand (不 HTTP)
```

### `PageGuard` 重构

```tsx
// 旧
interface PageGuardProps { pageKey: string; permissions: { allowed: string[] }; children: ReactNode; }
export function PageGuard({ pageKey, permissions, children }: PageGuardProps) {
  if (!permissions.allowed.includes(pageKey)) notFound();
  return <>{children}</>;
}

// 新
interface PageGuardProps { pageKey: string; role: string; allowed: string[]; children: ReactNode; }
export function PageGuard({ pageKey, role, allowed, children }: PageGuardProps) {
  if (role !== "super_admin" && !allowed.includes(pageKey)) forbidden();
  return <>{children}</>;
}
```

## 组件

### 1. 新建 `lib/auth/permission.ts`
- `getPermissions()`: 取 serverAuthHeaders + fetch /api/permissions/me → 返回 PermissionResult
- React.cache() 自动 dedup，多页面并发只 fetch 一次

### 2. 新建 `lib/hooks/usePermissions.ts`
- Zustand store: role, allowed, pages, loaded
- `usePermissionsStore` (bare store, 给 Provider 用)
- `usePermissions()` (hook, 懒加载 + 派生)

### 3. 改 `components/PageGuard.tsx`
- props: `pageKey, role, allowed, children`（去 permissions: {allowed: string[]}）
- 内部: `role !== "super_admin" && !allowed.includes(pageKey) → forbidden()`
- 删 `notFound()` 改用 `forbidden()`（统一语义: 权限不足）

### 4. 改 `admin/users/page.tsx`
- 删 `import { serverAuthHeaders }` + `getMyPermissions`
- 删 `/api/account/me` fetch + `me.is_admin` check
- 开头:
```tsx
const perm = await getPermissions();
if (!perm.isAdminLevel) redirect("/");
```
- `apiFetch(...)` 直接传 `{ headers: perm.headers }`
- PageGuard: `<PageGuard pageKey="admin" role={perm.role} allowed={perm.allowed}>`

### 5. 改 `admin/permissions/page.tsx`
- 开头:
```tsx
const perm = await getPermissions();
if (!perm.isSuperAdmin) forbidden();
```
- apiFetch 用 perm.headers
- 删 console.log

### 6. 改 `account/settings/page.tsx`
- 保留 `/api/account/me`（需要 is_account + user 资料）
- apiFetch headers 改走 `perm.headers`
- PageGuard 改新签名

### 7. `lib/auth/permissions.ts`
- `getMyPermissions()` 内部改为调 `getPermissions()` 返回 same shape（向后兼容）
- 已有 22 个调用方不用改

### 8. 测试
| 文件 | 改动 |
|---|---|
| `tests/.../test_permission.ts` (新) | getPermissions 不抛/env 未设置兜底 |
| `tests/.../test_usePermissions.ts` (新) | store.fetch + hook 懒加载 |
| `test_PageGuard.tsx` | 新 props: role + allowed |
| admin users/permissions page test | mock 改新导入路径 |

## 实施批次

### Batch 1: 核心函数 + hook

- 新建 `lib/auth/permission.ts`
- 新建 `lib/hooks/usePermissions.ts`
- 跑测试确认

### Batch 2: PageGuard + 页面切接

- 改 `PageGuard.tsx`
- 删 `is_admin` 检查
- 改 admin/users + admin/permissions + account/settings
- 逐个页面测试

### Batch 3: 文档 + 清理

- 更新 `lib/auth/permissions.ts` 导出（保证向后兼容）
- 更新受影响测试
- 跑全量 vitest + 手动 curl E2E

## 风险 + 缓解

| 风险 | 缓解 |
|---|---|
| `getPermissions()` RSC 并发重复 fetch | `React.cache()` 包装自动 dedup |
| Zustand 在 SSR 时取不到 | hook 内 guard: `if (typeof window === "undefined") return fallback` |
| 已有 22 个 `getMyPermissions` 调用方 | 内部改为调用 getPermissions(), 签名不变 |
| account/settings 删 `/api/account/me` → 丢资料 | 保留（spec 明确非目标） |

---

## 附录 A：Token 存储 Redis 化分析（待实施）

**状态**: 分析完成，待独立 spec 实施

### 当前架构（PostgreSQL 直查）

```
请求 → resolve_user()
  → 读 cookie rag_user_token
  → SELECT * FROM users WHERE public_token = $1       (每次请求)
  → 有 account_id: SELECT * FROM accounts WHERE id = $1 (每次请求)
  → 返回 CurrentUser
```

**关键数字**：auth 中间件每请求 2 次 PG 查询（users + accounts），全站流量都经过。

### 当前问题

| 问题 | 影响度 | 说明 |
|---|---|---|
| **Token 永不过期** | 🔴 严重 | `users.public_token` 无 expiry 列，泄露即永久有效 |
| **无 token 轮换** | 🟡 中 | 每次 login 返回同一 token，无法应对 token 泄露 |
| **无撤销机制** | 🔴 严重 | `logout()` 只清浏览器 cookie，DB token 仍有效；无法"踢人下线" |
| **DB 查表鉴权** | 🟡 中 | 每请求查 users + accounts 表，高并发时 PG 压力 |
| **单表混存** | 🟢 低 | user 数据 + token 认证同列，schema 耦合 |
| **多设备难管理** | 🟡 中 | 不知道用户在哪登录、几个设备在线 |

### Redis 带来的好处

| 能力 | 实现 | 效果 |
|---|---|---|
| **TTL 自动过期** | `SETEX user_token:{hash} 604800 user_data_json` | 7 天自动过期，泄露窗口从"永久"→"7 天" |
| **Token 轮换** | 每次 login 生成新 hash，旧 key 自动过期 | 泄露后重新登录即修复 |
| **即时撤销** | `DEL user_token:{hash}` | logout / admin 踢人立即生效 |
| **O(1) 鉴权** | Redis 内存查找，无 DB 查询 | 高并发无压力 |
| **去耦合** | Redis 只存 session，users/accounts 只存业务数据 | Schema 干净 |
| **设备管理** | 一个 user 可绑定多个 token key，方便列出在线设备 | 安全审计 |

### Redis 引入成本

| 成本 | 说明 |
|---|---|
| **新基础设施** | docker-compose 加 redis 容器，CI 也要跑 |
| **数据持久化** | Redis 重启丢 session → 所有用户强制重新登录（可配 RDB/AOF 缓解） |
| **一致性** | 用户 role 变更 → Redis 缓存的 session 数据可能 stale（设较短 TTL 或主动 invalidate） |
| **迁移** | 现有 users.public_token 的存量用户 session 需要过渡期双写 |
| **运维** | 团队需要维护 Redis（监控、备份、扩容） |
| **部署** | 生产如果已有 Redis 可复用；没有就是新增依赖 |

### 推荐方案：Redis Session Cache（不代替 PG）

```
请求 → resolve_user()
  → 读 cookie rag_user_token:abc123
  → Redis: GET  user_session:abc123
  → 命中 → 返回 CurrentUser（0 PG 查询）
  → 未命中 → PG: SELECT ... FROM users/accounts → 写入 Redis + TTL → 返回
```

**不改 token 生成机制**（仍是 `secrets.token_hex(32)` 落 PG `users.public_token`）。  
**Redis 只做 session cache**：token → CurrentUser JSON，TTL = 3600s（1h，不是 7d）。  
**PG 是权威源**，Redis 是热缓存。缓存键 TTL 短，role 变更最多 1h 延迟。

**LD (Login Device) 管理用另一 key** `user_devices:{account_id}` → set of token hashes，支持"踢设备"。

### 实施的依赖

- 项目已有 Docker 编排 → docker-compose 加 `redis:7-alpine` 一行
- Python 端：`redis-py` 包（`uv add redis`）
- 后端 `middleware/auth.py` 改 `resolve_user()`：先读 Redis → 未命中回退 PG → 写回 Redis
- Login / Logout 端点改：login 写 Redis + 返 token，logout 删 Redis key
- Token 撤销端点（不需要立即发布，可后加）

### 不做 JWT 的理由

| 方案 | 问题 |
|---|---|
| **JWT + Redis 黑名单** | JWT 必须设短 TTL 才能撤销，黑名单抵消了无状态优势 |
| **JWT 无状态** | 无法踢人、无法实时反映 role 变更 |
| **Opaque token + Redis** (推荐) | 简洁，跟当前完全兼容，黑名单天然支持 |

### 建议时机

- **短期**（本周）：加 `users.token_expires_at` 列 + 设定 Login set TTL（不加 Redis）
- **中期**（1-2 月）：docker-compose 加 Redis → `resolve_user` 加 Redis cache 层
- **长期**（3 月+）：如果生产在线用户> 10k，`users.public_token` 彻底剪枝，Redis 做主 session store

### 小结

Token Redis 化必要但不紧急。**该加**：docker-compose 一行、Python `redis-py` 一个包、`resolve_user` 30 行改动。**暂缓**：当前 PG 架构在 dev + 小规模生产完全够用，Redis 是性能优化 + 安全增强，不是修复 bug。

要实施时，开独立 spec `2026-07-xx-token-redis-migration-design.md`。
