# RBAC 权限系统 (v2: 权限组)

**日期**: 2026-06-17
**状态**: 设计 v2 已批准, 待实施
**作者**: Claude (brainstorming with user)
**基于**: [2026-06-13-account-system-design.md](2026-06-13-account-system-design.md) (账号系统已实施)
**v1 → v2 变更**: 固定 3 角色 (user/admin/super_admin) 升级到 **N 角色权限组**, super-admin 可在 UI 任意创建/删除自定义角色。

## Context

RAG 项目账号系统已实施 (3 种身份: 游客/账号/admin), 但 admin 角色粒度太粗:
单一 `is_admin` boolean 不能区分 "产品运营" vs "平台运维"。

产品/运营应该能看知识库 + 评估 + 文档结构化, 但**不能**管用户账号 + 不能看系统健康指标。
只有平台运维 (super_admin) 才看得到 `/admin/*` + `/health` + 改用户角色。

加上未来要做的"按角色开放/关闭页面"诉求, 需要**完整 RBAC + 运行时可配置 + 任意角色**:
超级管理员在权限管理页面**创建任意角色** (例: "运营", "客服", "审计"), 跟 7 个页面权限点任意勾选。

**v2 升级原因**: v1 spec 是 14 cell 固定矩阵, 不能加新角色。要支持"运营", "客服" 这种业务角色, 必须升级到 N 角色权限组。

**Why 现在做**:
- 账号系统已就绪, 加 `roles` 表 + 改 `accounts.role` 为 str 不会破坏现有 14 处 `is_admin` 引用
- v2 比 v1 多 1 周工作量, 但能避免未来"加角色就要发版"的运维成本
- 不做的话每次新业务角色都要发版 + 改代码

## 目标

- 4 种状态: 游客 (anon) / 用户 (user) / 管理员 (admin) / 超级管理员 (super_admin) + **任意自定义角色**
- 3 个预设系统角色 (user/admin/super_admin) + N 个 super-admin 创建的自定义角色 (例: 运营, 客服)
- 7 个页面权限点 (chat/output/knowledge/evaluate/submissions/decode/health), 父路径粒度
- 完整 RBAC: roles 表 + role_permissions 表, 运行时可配置, 30s TTL 缓存
- Super-admin 上帝权限, 不受 DB 限
- Anon 不支持记忆 (前端 UI 隐藏 + 后端 403)
- 超级管理员权限管理页 (`/admin/permissions`): N 角色行 × 7 页面列 checkbox matrix
- 角色管理: super-admin 可 CRUD 自定义角色 (`/admin/permissions/roles`)
- 现有 `is_admin=true` 账号全部升级为 `super_admin`

## 非目标

- 不做资源级权限 (例 "user A 看不到 user B 的文档") — 留给 follow-up
- 不做 audit log — 单独 spec
- 不做权限继承/层级 (例 "运营继承自用户") — 角色间独立, super-admin 显式勾选
- 不做 2FA / SSO / 多租户
- 不删 `accounts` 表任何字段 (只删 `is_admin`, 加 `role`)
- 不改 anon 流程的接口 / 表结构
- 不做 ABAC (基于属性的访问控制) — 留 follow-up

## 角色矩阵

### A. 状态 (4 种身份)

| 状态 | 标识 | 角色 | 记忆 |
|---|---|---|---|
| 游客 (anon) | `user.account_id IS NULL` | — | ❌ 禁 |
| 账号 | `account.role = 'user'` | user | ✅ |
| 管理员 | `account.role = 'admin'` | admin | ✅ |
| 超级管理员 | `account.role = 'super_admin'` | super_admin | ✅ |
| 任意自定义角色 | `account.role = 'operator'` 等 | 自定义 | ✅ |

### B. 预设 3 角色 (系统内置, alembic 种子)

| name | label_zh | label_en | is_system | 默认权限 (role_permissions) |
|---|---|---|---|---|
| `user` | 用户 | User | true | chat=true, decode=true, 其它 5 个=false |
| `admin` | 管理员 | Admin | true | chat, output, knowledge, evaluate, submissions, decode=true, health=false |
| `super_admin` | 超级管理员 | Super Admin | true | **代码层豁免, 不入库** |

**super_admin 行为**:
- `role_permissions` 表里**不**给 super_admin 写行
- 代码层守卫: `if user.role == "super_admin": return True` 提前 return, 跳过 cache
- 系统角色: 不能改 name, 不能删, label 可改

### C. 自定义角色 (super-admin 创建)

- 例: `operator` (运营) → chat + output + knowledge
- 例: `support` (客服) → chat + decode + submissions
- 完全由 super-admin 通过 UI 创建
- 任意 name (字母数字下划线, 2-32 字符, 不与系统重名)
- 创建时填: name, label_zh, label_en, 7 个 page_key 初始权限
- 删角色: 校验 "没人用这个 role 才能删", 否则 409 "role in use"

### D. 角色→页面权限矩阵 (动态 N×7)

```
                chat  output  knowledge  evaluate  submissions  decode  health
user             ✓     ✗       ✗          ✗         ✗            ✓       ✗
admin            ✓     ✓       ✓          ✓         ✓            ✓       ✗
super_admin      ✓     ✓       ✓          ✓         ✓            ✓       ✓ (meta)
operator         ✓     ✓       ✓          ✗         ✗            ✓       ✗  (例)
support          ✓     ✗       ✗          ✗         ✓            ✓       ✗  (例)
```

## 7 个页面权限点

| page_key | 路径 | 父路径粒度包含 |
|---|---|---|
| `chat` | `/chat`, `/chat/s/[shareId]` | 含公开分享页 |
| `output` | `/output`, `/output/new`, `/output/[task_id]`, `/output/[task_id]/[file]` | 4 个子页 |
| `knowledge` | `/knowledge/*` | 7 个子页 (datasets/documents/graph/qa/triples/nodes/relations/batch/dataset-documents) |
| `evaluate` | `/evaluate`, `/evaluate/new`, `/evaluate/[id]` | 3 个子页 |
| `submissions` | `/submissions` | 审核中心 |
| `decode` | `/decode` | 型号解析 |
| `health` | `/health` | 系统健康 |

**`/admin/*` (用户管理 + 邀请管理)** 走资源级 `require_super_admin`, 不作为独立 page_key。

## 架构

### A. 后端模块

```
packages/service/src/
├── auth/
│   ├── account_models.py        # 改: Account.role: str
│   └── auth_admin_router.py     # 改: invite body 加 role; require_admin → require_super_admin
├── permissions/                  # 新模块
│   ├── __init__.py
│   ├── models.py                # Role, RolePermission models
│   ├── service.py               # CRUD 业务逻辑
│   ├── router.py                # /api/permissions + /api/roles GET/PATCH
│   ├── cache.py                 # 进程内存 cache + 30s TTL (含 roles)
│   └── guards.py                # require_page / require_super_admin / require_account
├── middleware/
│   └── auth.py                  # 改: CurrentUser role: str
├── memory/router.py             # 改: 加 require_account Depends
├── health/router.py             # 改: 加 require_super_admin
├── knowledge/router.py          # 改: 加 require_page("knowledge")
├── output/router.py             # 改: 加 require_page("output")
├── evaluate/router.py           # 改: 加 require_page("evaluate")
├── submissions/router.py        # 改: 加 require_page("submissions")
├── decode/router.py             # 改: 加 require_page("decode")
└── chat/router.py               # 改: 加 require_page("chat")
```

### B. 前端模块

```
packages/web/
├── lib/auth/
│   ├── role.ts                  # 新: hasRoleAccess(user, pageKey), isSuperAdmin
│   └── role.test.ts
├── components/
│   ├── PageGuard.tsx            # 新: RSC 守卫
│   ├── PageGuard.test.tsx
│   ├── header.tsx               # 改: nav 数组化 + filter
│   ├── UserMenu.tsx             # 改: 用 helper
│   └── ... (其他不动)
├── app/[locale]/
│   ├── layout.tsx               # 改: 拉 /api/permissions/me + /api/roles
│   ├── chat/page.tsx            # 改: 记忆 UI 对 anon 隐藏
│   ├── admin/permissions/       # 新: 权限管理页 (矩阵 + 角色管理)
│   │   ├── page.tsx
│   │   ├── _components/
│   │   │   ├── PermissionsMatrix.tsx
│   │   │   ├── RoleList.tsx
│   │   │   ├── CreateRoleDialog.tsx
│   │   │   └── ...
│   │   └── page.test.tsx
│   └── ... (22 个 page.tsx 都加 PageGuard)
```

### C. 数据流 (PATCH 权限后生效)

```
1. Super-admin 在 /admin/permissions 改 role × page cell
2. Client 调 PATCH /api/permissions { updates: [{ role_name, page_key, allowed }, ...] }
3. Backend: UPSERT role_permissions, cache.invalidate()
4. 下个请求 → guard 查 cache → _loaded_at 已重置 → _refresh() → 新矩阵生效
5. 其它用户当前页: 30s TTL 内还是旧 (TTL 到自动 refetch)
```

**创建/删除角色后同样触发 cache invalidate** (因为 role 列表变, 前端 nav filter 也要重算)。

## 数据模型

### A. accounts 表改造

```sql
-- 加 role 列, str 类型 (无 CHECK, 由 Pydantic 写时校验)
ALTER TABLE accounts ADD COLUMN role TEXT NOT NULL DEFAULT 'user';

-- 数据迁移
UPDATE accounts SET role = 'super_admin' WHERE is_admin = TRUE;
-- is_admin = FALSE 走默认 'user'

-- 删 is_admin
ALTER TABLE accounts DROP COLUMN is_admin;
```

**`CurrentUser` model** ([packages/service/src/middleware/auth.py:49-64](../../packages/service/src/middleware/auth.py#L49-L64) 改):

```python
class CurrentUser(BaseModel):
    id: int
    public_token: str
    role: str = "user"  # 替 Literal, validated against roles 表
    is_account: bool = False
    account_id: int | None = None
    email: str | None = None
    display_name: str | None = None
    is_active: bool = True
    # 不留 is_admin 字段, 派生用 helper
```

**Helper**:
```python
def is_super_admin(user: CurrentUser) -> bool:
    return user.role == "super_admin"
```

### B. roles 表 (新)

```sql
CREATE TABLE roles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,                    -- 'user' | 'admin' | 'super_admin' | 'operator' | ...
    label_zh TEXT NOT NULL,
    label_en TEXT NOT NULL,
    is_system BOOLEAN NOT NULL DEFAULT FALSE,    -- 系统内置 TRUE, 自定义 FALSE
    is_deletable BOOLEAN NOT NULL DEFAULT FALSE,  -- 系统内置 FALSE, 自定义 TRUE
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL
);
CREATE INDEX idx_roles_name ON roles(name);
```

**预设 3 行** (alembic 插入):

```python
# 用户
("user", "用户", "User", is_system=True, is_deletable=False)
# 管理员
("admin", "管理员", "Admin", is_system=True, is_deletable=False)
# 超级管理员
("super_admin", "超级管理员", "Super Admin", is_system=True, is_deletable=False)
```

### C. role_permissions 表 (新, 替代原 page_permissions)

```sql
CREATE TABLE role_permissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    role_name TEXT NOT NULL,                       -- 关联 roles.name (不级联, 防御性)
    page_key TEXT NOT NULL,                        -- 7 个 page_key
    allowed BOOLEAN NOT NULL DEFAULT TRUE,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    UNIQUE(role_name, page_key)                    -- 同角色同页面只 1 行
);
CREATE INDEX idx_role_perms_name ON role_permissions(role_name);
```

**初始 8 行** (alembic 插入, **不**含 super_admin):

| role_name | page_key | allowed |
|---|---|---|
| user | chat | true |
| user | decode | true |
| user | output, knowledge, evaluate, submissions, health | false |
| admin | chat, output, knowledge, evaluate, submissions, decode | true |
| admin | health | false |

**Super-admin 不入库**: 代码层 `if user.role == "super_admin": return True` 提前 return, 跳过 cache。

### D. Alembic Migration

新 revision `20260617_add_roles_and_rbac.py`:

1. `op.add_column("accounts", sa.Column("role", TEXT, nullable=False, server_default="user"))`
2. `op.execute("UPDATE accounts SET role = 'super_admin' WHERE is_admin = TRUE")`
3. `op.drop_column("accounts", "is_admin")`
4. `op.create_table("roles", ...)`
5. `op.bulk_insert(roles, [...3 rows...])`
6. `op.create_table("role_permissions", ...)`
7. `op.bulk_insert(role_permissions, [...8 rows for user + admin...])`

可逆: `downgrade()` 完整 reverse (重加 is_admin, role → is_admin 转换, 删 2 表)。

## 鉴权流

### A. 后端守卫 (FastAPI Depends)

```python
# permissions/guards.py
from functools import lru_cache

def require_page(page_key: str):
    """工厂: 返 FastAPI Depends 闭包"""
    def _dep(user: CurrentUser = Depends(resolve_user)) -> CurrentUser:
        if user.role == "super_admin":
            return user  # meta 豁免
        if not permission_cache.get(user.role, page_key):
            raise HTTPException(403, f"page '{page_key}' not allowed for role '{user.role}'")
        return user
    return _dep


def require_super_admin(user: CurrentUser = Depends(resolve_user)) -> CurrentUser:
    if user.role != "super_admin":
        raise HTTPException(403, "super_admin required")
    return user


def require_account(user: CurrentUser = Depends(resolve_user)) -> CurrentUser:
    """记忆端点用, 禁 anon"""
    if not user.is_account:
        raise HTTPException(403, "login required")
    return user
```

**应用映射**:

| 端点 | 守卫 |
|---|---|
| `GET /api/health` | `require_super_admin` |
| `GET /api/knowledge/*` | `require_page("knowledge")` |
| `GET /api/evaluate/*` | `require_page("evaluate")` |
| `GET /api/output/*` | `require_page("output")` |
| `GET /api/submissions/*` | `require_page("submissions")` |
| `GET /api/decode/*` | `require_page("decode")` |
| `GET /api/chat/*` | `require_page("chat")` (anon 也可) |
| `GET/POST /api/memory/*` | `require_account` |
| `GET /api/admin/users` | `require_super_admin` |
| `POST /api/admin/users` (创 invite) | `require_super_admin` |
| `PATCH /api/admin/users/{id}` | `require_super_admin` |
| `GET /api/admin/invites` | `require_super_admin` |
| `POST /api/admin/invites/{id}` | `require_super_admin` |
| `GET /api/permissions` | `require_super_admin` |
| `PATCH /api/permissions` | `require_super_admin` |
| `GET /api/roles` | `require_super_admin` |
| `POST /api/roles` | `require_super_admin` |
| `PATCH /api/roles/{name}` | `require_super_admin` |
| `DELETE /api/roles/{name}` | `require_super_admin` |
| `POST /api/account/seed-admin` | `RAG_ADMIN_TOKEN` header (现有, 不变) |
| `POST /api/account/login` 等公开端点 | 无守卫 |

### B. 权限管理 API (矩阵)

```
GET /api/permissions
  Auth: require_super_admin
  200: {
    roles: [
      { name: "user", label_zh: "用户", label_en: "User", is_system: true },
      { name: "admin", label_zh: "管理员", label_en: "Admin", is_system: true },
      { name: "operator", label_zh: "运营", label_en: "Operator", is_system: false },
      ... N 角色
    ],
    matrix: {
      "user":    { "chat": true, "decode": true, "output": false, ... },
      "admin":   { "chat": true, "decode": true, "output": true, ... },
      "operator":{ "chat": true, "decode": true, "output": true, ... }
    },
    pages: [
      { key: "chat", label_zh: "对话", label_en: "Chat", path: "/chat" },
      ... 7 行
    ]
  }

PATCH /api/permissions
  Auth: require_super_admin
  body: { updates: [{ role_name, page_key, allowed }, ...] }
  200: { updated: int }
  副作用: cache.invalidate()
  约束:
    - role_name 必须在 roles 表 → 400 "unknown role"
    - role_name == "super_admin" → 400 "cannot modify super_admin permissions" (代码层)
    - page_key 不在 7 列表 → 400 "unknown page_key"
```

### C. 角色管理 API (新增)

```
GET /api/roles
  Auth: require_super_admin
  200: { roles: [{ name, label_zh, label_en, is_system, is_deletable, user_count }, ...] }

POST /api/roles
  Auth: require_super_admin
  body: { name, label_zh, label_en, permissions: { page_key: bool }[] }
  201: { name, label_zh, label_en, ... }
  409: name 已存在
  400: name 格式错 (非 [a-z0-9_]{2,32} 或重名系统)

PATCH /api/roles/{name}
  Auth: require_super_admin
  body: { label_zh?, label_en? }  -- name 不可改 (系统角色防 rename)
  200: { name, label_zh, label_en, ... }
  400: 系统角色改 name → 400 "cannot rename system role"
  404: 不存在

DELETE /api/roles/{name}
  Auth: require_super_admin
  204: No Content
  400: 系统角色 → 400 "cannot delete system role"
  409: 仍有用户用此 role → 409 "role in use by N users"
  404: 不存在
```

### D. 现有端点改造 (role 字段改 str)

| 端点 | body 改动 |
|---|---|
| `POST /api/account/seed-admin` | 创 super_admin 账号 (硬编码) |
| `POST /api/admin/users` (创 invite) | body: `{ email, role: str, display_name? }` (从 roles 挑; 拒 super_admin, 避免 invite 创 super_admin) |
| `PATCH /api/admin/users/{id}` | body: `{ is_active?, role?: str, display_name? }` (role 改: 必须是 roles 表中存在的; 拒 super_admin 改非 super_admin) |
| `POST /api/account/login` | LoginResponse 加 `role: str` 字段 (additive) |
| `GET /api/account/me` | 返 `role: str` 字段 (替 is_admin) |

### E. `/api/permissions/me` 新端点 (layout 拉)

```python
@router.get("/api/permissions/me")
def my_permissions(user: CurrentUser = Depends(resolve_user)) -> dict:
    if user.role == "super_admin":
        allowed = ALL_PAGE_KEYS
    else:
        allowed = [
            pk for pk in ALL_PAGE_KEYS
            if permission_cache.get(user.role, pk) is True
        ]
    return {"role": user.role, "allowed": allowed, "pages": PAGE_METADATA}
```

**anon** 也能调: `role="user"`, `allowed=["chat"]` (走 user 路径, 命中 role_permissions)。

## 缓存层

```python
# permissions/cache.py
import threading
import time

from ..storage.session import session_scope

ALL_PAGE_KEYS = ("chat", "output", "knowledge", "evaluate", "submissions", "decode", "health")
PAGE_METADATA = [
    {"key": k, "label_zh": ..., "label_en": ..., "path": f"/{k}"}
    for k in ALL_PAGE_KEYS
]


class PermissionCache:
    """进程内存 dict cache, 30s TTL sliding"""
    def __init__(self, ttl_seconds: int = 30) -> None:
        self._lock = threading.RLock()
        self._matrix: dict[str, dict[str, bool]] = {}  # {role_name: {page_key: allowed}}
        self._loaded_at: float = 0.0
        self._ttl = ttl_seconds

    def get(self, role: str, page_key: str) -> bool | None:
        with self._lock:
            if time.time() - self._loaded_at > self._ttl:
                self._refresh()
            return self._matrix.get(role, {}).get(page_key)

    def invalidate(self) -> None:
        with self._lock:
            self._loaded_at = 0.0

    def _refresh(self) -> None:
        with self._lock:
            new_matrix: dict[str, dict[str, bool]] = {}
            with session_scope() as s:
                rows = s.execute(
                    "SELECT role_name, page_key, allowed FROM role_permissions"
                ).fetchall()
            for role_name, page_key, allowed in rows:
                new_matrix.setdefault(role_name, {})[page_key] = allowed
            self._matrix = new_matrix
            self._loaded_at = time.time()


permission_cache = PermissionCache()
```

**失效触发点**:
- `PATCH /api/permissions` 改 cell → invalidate
- `POST /api/roles` 创角色 → invalidate
- `PATCH /api/roles/{name}` 改 label → invalidate (label 变了前端要刷)
- `DELETE /api/roles/{name}` 删角色 → invalidate

**关键点**:
- 单进程单例, 启动后第一次读触发 `_refresh()`
- TTL 30s 滑动过期, 过期后下次读触发重读
- 写后 `cache.invalidate()`, 下一个请求强制 `_refresh()`
- 读路径 = lock + dict get, **不查 DB**
- **不**做多进程同步 (gunicorn 多 worker 各自持 30s 缓存, 可接受)

## 前端

### A. 4 层防护 (defense in depth)

| 层 | 文件 | 作用 |
|---|---|---|
| 1. Nav 过滤 | `header.tsx` | 不显示无权限的 nav link |
| 2. RSC 守卫 | 22 个 `page.tsx` 套 `PageGuard` | 无权直接 404 |
| 3. Server Action 守卫 | `_actions/*` | 写操作前再校验 |
| 4. Proxy 守卫 | `proxy.ts` | 鉴权 cookie 缺失早 redirect |

### B. PageGuard 组件

```typescript
// components/PageGuard.tsx
import { notFound } from "next/navigation";

export function PageGuard({
  pageKey,
  permissions,
  children,
}: {
  pageKey: string;
  permissions: { allowed: string[] };
  children: React.ReactNode;
}) {
  if (!permissions.allowed.includes(pageKey)) {
    notFound();
  }
  return <>{children}</>;
}
```

**用法** (每个受保护 page.tsx 顶部):

```typescript
export default async function KnowledgePage() {
  const permissions = await getPermissions();
  return (
    <PageGuard pageKey="knowledge" permissions={permissions}>
      {/* 原有内容 */}
    </PageGuard>
  );
}
```

### C. 权限管理页 UI (N 行 × 7 列)

**布局**:

```
+----------------------------------------------------------+
| 标题: 权限管理                                            |
| 描述: 配置每个页面对每个角色的访问权限                       |
+----------------------------------------------------------+
| 角色管理                                                 |
| 角色列表:                                                |
|   [用户] (系统)        3 个用户  [编辑]                   |
|   [管理员] (系统)      1 个用户  [编辑]                   |
|   [运营] (自定义)      2 个用户  [编辑] [删除]            |
|   [客服] (自定义)      0 个用户  [编辑] [删除]            |
| [+ 新建角色]                                             |
+----------------------------------------------------------+
| 权限矩阵                                                 |
| 角色 ▼ | chat | decode | output | knowledge | ... 7 列    |
|------|------|--------|--------|-----------|------+
| 用户  |  ☑   |  ☑    |  ☐    |   ☐      | ...  |
| 管理员|  ☑   |  ☑    |  ☑    |   ☑      | ...  |
| 运营  |  ☑   |  ☑    |  ☑    |   ☑      | ...  |
| 客服  |  ☑   |  ☑    |  ☐    |   ☐      | ...  |
+----------------------------------------------------------+
[保存]  [重置默认]
```

**实现拆 4 个组件**:
- `<RoleList>`: 列所有角色, 标记系统/自定义, 显示用户数, 编辑/删除按钮
- `<CreateRoleDialog>`: 弹框填 name + label_zh + label_en + 7 checkbox
- `<PermissionsMatrix>`: 渲染 N 行 × 7 列 checkbox
- `<PermissionManagementPage>` (RSC): 拉数据, 组装

**约束**:
- 系统角色不能删除 (按钮 disabled)
- 系统角色 label 可改 (弹框)
- 自定义角色 0 用户时可删, ≥1 用户时按钮 disabled + tooltip "N 个用户正在使用"
- 保存: 收集 dirty cell 调 PATCH
- 重置默认: 调 PATCH 把 user + admin 两行改回初始 8 行

### D. UserMenu 改造

```typescript
// 用 helper
function isAdminLevel(user: { role: string } | null | undefined): boolean {
  // 非 user 角色都视为 "管理级别" (admin / super_admin / 自定义如 operator)
  return user != null && user.role !== "user";
}

function isSuperAdmin(user: { role: string } | null | undefined): boolean {
  return user?.role === "super_admin";
}
```

- admin 级别: 多 "用户管理" 链接 (按 admin 页面权限)
- super_admin: 多 "权限管理" 链接
- user: 仅登出
- anon: 登录按钮

### E. Chat 记忆 UI 隐藏 (anon)

```typescript
// chat/page.tsx
{user?.is_account ? (
  <MemoryToggle />
) : (
  <Button variant="ghost" disabled>
    {t("记忆 (登录后可用)")}
  </Button>
)}
```

### F. i18n keys (12 个新增)

```
权限管理 / Permission management
角色 / Roles
新建角色 / Create role
编辑角色 / Edit role
删除角色 / Delete role
系统角色 / System role
自定义角色 / Custom role
N 个用户正在使用 / N users using this role
确认删除角色? / Confirm delete role?
保存 / Save
重置默认 / Reset to default
修改后立即生效 / Changes take effect within 30s
```

## 测试

### A. 后端 pytest (8 个新 + 改 5 个 = 13)

| 文件 | 测什么 | 关键 case |
|---|---|---|
| `tests/permissions/test_models.py` | Role + RolePermission 表结构 | roles unique(name); role_permissions unique(role_name, page_key); 初始 3 角色 + 8 权限行 |
| `tests/permissions/test_cache.py` | PermissionCache 行为 | TTL 过期重读; invalidate 后立即重读; 并发 100 读 1 写无 race |
| `tests/permissions/test_guards.py` | 3 装饰器 | 4 角色 × 7 页面矩阵 28 case (parametrize); anon /api/memory → 403; 自定义角色权限生效 |
| `tests/permissions/test_router.py` | PATCH /api/permissions | super_admin 改 cell → 200 + 失效; 改 super_admin 行 → 400; 未知 role → 400 |
| `tests/roles/test_models.py` | Role model 字段约束 | name 格式; is_system 不可改 (代码层); user_count 派生 |
| `tests/roles/test_router.py` | GET/POST/PATCH/DELETE /api/roles | 创建/编辑/删除; 系统角色删 → 400; 0 用户删 → 204; N 用户删 → 409; 名称重名 → 409 |
| `tests/integration/test_rbac_e2e.py` | 端到端 4 身份 × 7 页面 | 启 TestClient, 走通 28 case |
| `tests/auth/test_account_role.py` | Account role: str 字段 | seed_admin → role=super_admin; invite body role=admin → 创 admin; invite body role=super_admin → 400 |
| `tests/auth/test_admin_router_role.py` (改) | admin router 改 super_admin 守 | user 访 → 403; admin 访 → 403; super_admin → 200 |
| `tests/auth/test_login_role.py` (改) | login 返 role 字段 | LoginResponse 有 role; user 登录返 role=user |
| `tests/middleware/test_auth_role.py` (改) | CurrentUser.role: str | 4 身份路径都返 role |
| `tests/memory/test_anon_block.py` (改) | 记忆端点禁 anon | anon 调 → 403; user 调 → 200 |
| `tests/health/test_super_admin.py` (改) | health 端点 super_admin 守 | user/admin/自定义角色 访 → 403; super_admin → 200 |

**关键 fixture**:
- `make_account(role="user"|"admin"|"super_admin"|"operator")` factory
- `with_clean_permissions_cache` (重置 cache)
- `bypass_super_admin_token(monkeypatch)` (RAG_ADMIN_TOKEN 头)
- **不 mock cache** (用真内存 cache, 配 invalidation)
- **不 mock bcrypt**

### B. 前端 vitest (5 个新 + 改 5 个 = 10)

| 文件 | 测什么 | 关键 case |
|---|---|---|
| `lib/auth/role.test.ts` | `isAdminLevel` / `isSuperAdmin` helper | 4 状态布尔 |
| `components/PageGuard.test.tsx` | PageGuard 渲染 | allowed → children; 不在 allowed → notFound |
| `components/header.test.tsx` (改) | nav filter | user → 2 link; admin → 6 link; super_admin → 8 link; anon → 1 link; 自定义角色 (例 operator) → 自己权限的子集 |
| `components/UserMenu.test.tsx` (改) | role-based menu | super_admin → 多 "权限管理"; admin → 多 "用户管理"; user → 仅登出 |
| `app/[locale]/admin/permissions/page.test.tsx` | 权限管理页 RSC | 加载 roles + matrix; 创建/删除角色调 POST/DELETE; toggle cell 调 PATCH |
| `app/[locale]/admin/permissions/_components/PermissionsMatrix.test.tsx` | matrix 组件 | N 行 × 7 列渲染; 勾选调 onChange; 保存按钮 |
| `app/[locale]/admin/permissions/_components/CreateRoleDialog.test.tsx` | 新建角色弹框 | 填表提交 → POST; name 重名 → 错误; name 格式错 → 客户端校验 |
| `app/[locale]/admin/permissions/_components/RoleList.test.tsx` | 角色列表 | 系统角色删按钮 disabled; 自定义角色 N>0 删按钮 disabled; 0 用户可删 |
| `app/[locale]/chat/page.test.tsx` (改) | 记忆 UI | anon → disabled; user → 正常 |
| `app/[locale]/admin/users/page.test.tsx` (改) | 守卫 | user → notFound; admin → notFound; super_admin → 看到列表 |

### C. E2E (Playwright, 留 follow-up)

- 4 身份登录后看到不同 nav
- super_admin 创建 "运营" 角色 → 给某用户 role=operator → 该用户重登后看到运营的 nav 子集
- super_admin 删 "运营" 角色 (0 用户) → 成功
- super_admin 改 user 角色 output 权限 → user 重载后 output 不见 (30s 内可能仍可见)
- anon 访 /health → 404; admin 访 /health → 404; super_admin 访 → 200

**Why E2E 留 follow-up**: pytest + vitest + 集成测 够, Playwright 慢 + 难维护。

### D. 验收 Checklist

- [ ] 8 个后端 pytest 文件 0 fail
- [ ] 8 个前端 vitest 文件 0 fail
- [ ] 端到端 curl 矩阵走通 4 身份 × 7 页面 (28 case)
- [ ] super_admin PATCH 后下个请求立即生效
- [ ] super_admin 创建/删除自定义角色走通
- [ ] anon 访 /api/memory → 403; 登录后 → 200
- [ ] 旧 is_admin 账号已迁 super_admin (curl /api/account/me 验 role)
- [ ] 浏览器手测: 4 身份 + 自定义角色登录看到不同 nav
- [ ] i18n messages/{zh,en}.json 12 个新 key 同步
- [ ] README 更新到位

## 部署 / 迁移

### A. 启动顺序

1. 部署代码 + 跑 migration (加 accounts.role, 迁 is_admin, 删 is_admin, 创 roles + 3 行, 创 role_permissions + 8 行)
2. 配环境变量 (无新增)
3. **首个 super_admin 创建**: `RAG_ADMIN_TOKEN` 配好后, 跑 `uv run python scripts/seed_admin.py` 创首个 super_admin 账号 (跟原 is_admin 账号等效)
4. 重启后端 (新 role 字段生效)
5. 重启前端 (新 PageGuard + 权限管理 UI 生效)
6. 浏览器手测: 4 身份登录 + 创建自定义角色

### B. 现有项目迁移

**当前生产数据**:
- `accounts` 表已有 N 行, 部分 `is_admin=TRUE`
- `users` 表 + anon token 流程不变
- `RAG_DEV_AUTH=1` 模式不变

**迁移步骤**:
1. 部署新代码 (含 migration)
2. migration 自动跑: is_admin=TRUE → role='super_admin', 删 is_admin, 创 roles + 3 行, 创 role_permissions + 8 行
3. **anon 行不动** — `role` 不影响 anon (anon 没 account_id)
4. 现有 super_admin 账号 (原 admin) 登录后看到 nav 多了 "权限管理" + "健康"
5. 现有 user 账号登录后看到 nav 只剩 chat + decode

### C. Alembic Migration 可逆

```python
# 20260617_add_roles_and_rbac.py

def upgrade() -> None:
    op.add_column("accounts", sa.Column("role", sa.Text, nullable=False, server_default="user"))
    op.execute("UPDATE accounts SET role = 'super_admin' WHERE is_admin = TRUE")
    op.drop_column("accounts", "is_admin")
    op.create_table("roles", ...)
    op.bulk_insert(roles_table, [
        {"name": "user", "label_zh": "用户", "label_en": "User",
         "is_system": True, "is_deletable": False, ...},
        {"name": "admin", "label_zh": "管理员", "label_en": "Admin",
         "is_system": True, "is_deletable": False, ...},
        {"name": "super_admin", "label_zh": "超级管理员", "label_en": "Super Admin",
         "is_system": True, "is_deletable": False, ...},
    ])
    op.create_table("role_permissions", ...)
    op.bulk_insert(role_permissions_table, [
        {"role_name": "user", "page_key": "chat", "allowed": True, ...},
        ... 8 rows for user + admin
    ])

def downgrade() -> None:
    op.drop_table("role_permissions")
    op.drop_table("roles")
    op.add_column("accounts", sa.Column("is_admin", sa.Boolean, nullable=False, server_default=sa.false()))
    op.execute("UPDATE accounts SET is_admin = TRUE WHERE role = 'super_admin'")
    op.drop_column("accounts", "role")
```

dev 库跑 `alembic upgrade head + downgrade base + upgrade head` 验证可逆。

### D. Seed Script 改造

`scripts/seed_admin.py`:
- 调 `POST /api/account/seed-admin`
- 后端 `seed_admin` handler 改: 创 `role='super_admin'` 账号 (硬编码, 不走 roles 表)
- 不改脚本本身

### E. .env 增量

```bash
# 无新增
# 现有 RAG_ADMIN_TOKEN / RAG_DEV_AUTH 保留
```

### F. README 更新

加一节 "权限系统":
- 3 预设角色 + 自定义角色说明
- 角色权限矩阵 (默认 3 角色)
- 超级管理员可创建自定义角色 (步骤)
- 现有 admin 账号已自动迁为 super_admin
- anon 记忆限制

## 风险 + 缓解

| 风险 | 缓解 |
|---|---|
| 现有 is_admin 列删了, 老代码引用崩 | grep 14 文件全列在 plan, 一次性改完 |
| Cache 不失效导致改后不生效 | 30s TTL + PATCH/POST/DELETE 后立即 invalidate 双保险 |
| Anon 记忆端点漏拦截, 用户能搜 | 后端 require_account 必加, vitest 断言 anon 返 403 |
| 4 身份 × 7 页面 28 case 漏测 | pytest.mark.parametrize 走全矩阵 |
| 误把 super_admin 角色删了 | is_deletable=False 守, 系统角色 0 个的 user_count 强制守 |
| 角色名重名 (例 自定义叫 "user") | 创角色时校验 roles 表无此 name + 拒系统重名 |
| 删角色时还有用户在用 | 校验 user_count=0, 否则 409 "N users using this role" |
| PATCH role 时把 super_admin 写到 accounts | PATCH /api/admin/users body.role 校验 != "super_admin" 除非操作者本人是 super_admin 改自己 |
| 4 + 12 i18n key 漏改 | git diff 校验, commit message 标注 "i18n: add 12 keys" |
| 22 page.tsx 加 PageGuard 时漏一个 | 写一个 grep 测试: 每个 page.tsx 必须 import PageGuard |
| 多 worker 进程缓存不一致 | gunicorn 多 worker 各自持 30s 缓存, 可接受 |
| PATCH 时 cache invalidate + DB commit 顺序错 | 顺序: DB commit → invalidate (不反过来) |

## 实施 Phase (4 phase, ~10 工作日)

**Phase 1 — 后端 backbone (3 天)**:
- Alembic migration
- Role + RolePermission models
- CurrentUser.role 改 str (14 文件改 is_admin → role)
- PermissionCache 实现 (含 roles)
- require_page / require_super_admin / require_account 装饰器
- 4 身份 × 7 页面守卫测试 (参数化)

**Phase 2 — 权限 + 角色 API + 端点改造 (3 天)**:
- `/api/permissions` GET/PATCH
- `/api/roles` GET/POST/PATCH/DELETE (新建)
- `/api/permissions/me` 新端点
- 10 个 router 加 require_page Depends
- `seed_admin.py` 创 super_admin
- 现有 require_admin → require_super_admin
- invite body 加 role 字段

**Phase 3 — 前端 nav + guard (2 天)**:
- PageGuard 组件
- role helper
- 22 page.tsx 加 PageGuard
- header.tsx nav filter
- UserMenu 改造
- chat 记忆 UI 隐藏
- 10 个 vitest 文件

**Phase 4 — 权限管理 UI + 文档 (2 天)**:
- /admin/permissions/page.tsx (RSC)
- PermissionsMatrix 组件
- RoleList 组件
- CreateRoleDialog 组件
- 12 i18n key 同步
- README 更新
- 浏览器手测

**Total**: ~10 个工作日, 1 人

## 安全 / 兼容

- **API 向后兼容**: 现有 anon / login / invite 流程不变; `LoginResponse` 加 role 字段是 additive
- **不引入新依赖**: 0 个新 pip 包
- **不写 shim**: 不留 `is_admin` 影子字段, 不用 if/else 散落 (用 helper)
- **审计**: 不做 audit log, 留 follow-up
- **CSRF**: 同源 cookie SameSite=Lax
- **角色名约束**: `[a-z0-9_]{2,32}` (防注入, 跟 username 风格一致)
- **PII**: role 不算 PII, 直接进 token / log

## Follow-up (本期外)

- E2E Playwright 覆盖完整流
- Audit log (谁在何时改了什么)
- Login 限流 (防爆破)
- 资源级权限 (例 "user A 看不到 user B 的私有文档")
- 权限继承/层级 (例 "运营继承自用户")
- 2FA / SSO
- 多租户
- ABAC (基于属性的访问控制)
- 改 email 流 (重发验证 + 登出所有 device)
