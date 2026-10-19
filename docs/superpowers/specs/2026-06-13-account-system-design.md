# 账号系统 + Admin 用户管理

**日期**: 2026-06-13
**状态**: 设计已批准, 待实施
**作者**: Claude (brainstorming with user)

## Context

RAG 项目当前是**匿名 token 系统** (32 字节 hex, HttpOnly cookie, `users` 表里的 anon 行).
没有真账号, 没有密码, 没有注册流程.
Admin 是**虚拟的** (`RAG_ADMIN_TOKEN` env, id=0, 不入库).

用户要加真账号系统, 满足:

1. Admin 角色 + 用户管理 UI (CRUD + 禁用 + 改角色 + 重设密码)
2. Invite-only 注册 (内部/B2B 场景, 不开放公开注册)
3. 现有 anon 系统不破坏, anon 降级为"游客"身份

**Why**: 当前 anon token 给 mem0/eval 提供"用户隔离"标识, 但没有真账号概念.
Dify BFF 删了之后, 前端需要 session/账号支撑长期用户.
加 admin UI 是给运维一个管理入口, 不用每次都 ssh 上去手改 DB.

## 目标

- 真账号系统: email + password 登录, session cookie
- Admin invite-only 注册, 一次性 token + 7 天过期
- Admin 角色 (`accounts.is_admin`), 全局生效
- Admin UI: 列表 + 创 invite + 改 is_admin/is_active/display_name + 重设密码
- 三种身份并存: anon / 账号 / bootstrap admin, 用统一 `CurrentUser` 抽象
- 现有 anon token 流程 0 破坏

## 非目标

- 不发邮件 (admin 复制 invite URL / 临时密码手工发给用户)
- 不删用户 (禁用 `is_active=False` 代替)
- 不做 audit log (改什么 / 何时 / 谁, 留 follow-up)
- 不做 password reset 邮件流 (admin 复制 URL 同 invite 一样手工发)
- 不做 2FA / SSO / 多租户
- 不替换 anon 系统为真账号 (anon 永久保留)
- 不改 anon 流程的接口 / 表结构

## 架构

### 身份模型 (3 种共存)

| 身份                | 标识                                  | 存储                                                                  | 何时用                  |
| ------------------- | ------------------------------------- | --------------------------------------------------------------------- | ----------------------- |
| **游客** (anon)     | 32 字节 hex `public_token`            | `users` 表, `account_id IS NULL`                                      | 首次访问, 没账号        |
| **账号** (account)  | 同样 32 字节 hex token (跟 anon 兼容) | `users` 表 + `accounts` 表 1:1 关联 (`user.account_id → accounts.id`) | email 登录后            |
| **Bootstrap admin** | `RAG_ADMIN_TOKEN` env                 | 不入库, 虚拟 user (id=0)                                              | 首次部署, 运维 recovery |

**统一 `CurrentUser` 抽象** (middleware 输出):

```python
class CurrentUser(BaseModel):
    id: int                      # 跟现有兼容
    public_token: str            # 现有
    is_admin: bool = False       # 现有 (从 account.is_admin 派生或 env)
    is_account: bool = False     # 新: 区分 anon vs 真账号
    account_id: int | None       # 新: 关联 accounts.id (anon 是 None)
    email: str | None = None     # 新: 账号才有
    is_active: bool = True       # 新: 禁用状态 (默认 True 给 anon)
    is_bootstrap_admin: bool = False  # 新: 区分 env-admin 跟 真 admin 账号
```

### 中间件优先级升级

1. `RAG_ADMIN_TOKEN` 命中 → bootstrap admin (id=0, is_admin=True, is_bootstrap_admin=True, is_account=False)
2. `x-user-token` (或 cookie `rag_user_token`) 查 `users` 表 → 拿 user:
   - `user.account_id IS NULL` → anon (is_account=False, is_admin=False, is_active=True)
   - `user.account_id IS NOT NULL` → 查 account, 拿 is_admin/is_active, 同步到 CurrentUser
3. `account.is_active == False` → 401 "account disabled"
4. `RAG_DEV_AUTH=1` + 无 token → dev user (id=1, is_admin=True, is_account=False)

**Why 分 bootstrap admin 跟 真 admin**:

- bootstrap admin 是 `RAG_ADMIN_TOKEN` env 的, 永远在 (给运维)
- 真 admin 是 accounts 表里 `is_admin=True` 的, 可被 admin 面板管理
- 前端 `is_bootstrap_admin=True` 时, UI 提示 "请尽快 seed 真 admin 账号"

### 组件

| 组件                                               | 职责                                                                                         | 文件                                                |
| -------------------------------------------------- | -------------------------------------------------------------------------------------------- | --------------------------------------------------- |
| `Account` / `Invite` / `PasswordReset` models      | 3 张新表 + users 加列                                                                        | `src/auth/account_models.py`                        |
| `account_service.py`                               | 密码 hash, 登录, invite 逻辑                                                                 | `src/auth/`                                         |
| `auth_account_router.py`                           | `/api/account/login`, `/logout`, `/me`, `/seed-admin`, `/forgot-password`, `/reset-password` | `src/auth/`                                         |
| `auth_invite_router.py`                            | `/api/invites/<token>` (GET), `/redeem` (POST)                                               | `src/auth/`                                         |
| `auth_admin_router.py`                             | `/api/admin/users` (GET/POST/PATCH), `/reset-password`, `/invites` (GET/DELETE)              | `src/auth/`                                         |
| middleware 升级                                    | `CurrentUser` 7 字段, anon/账号/bootstrap 三路径                                             | `src/middleware/auth.py`                            |
| Alembic migration                                  | 新 3 表 + users.account_id                                                                   | `src/storage/migrations/versions/2a3b4c5d6e7f_*.py` |
| `seed_admin.py`                                    | 调 `POST /api/account/seed-admin` 创首个 admin                                               | `scripts/`                                          |
| `LoginPage.tsx`                                    | 邮箱 + 密码登录 + 忘记密码链接                                                               | `packages/web/app/[locale]/login/`                  |
| `InviteRedeemPage.tsx`                             | Invite 兑换 (填 display_name + 密码)                                                         | `packages/web/app/[locale]/invite/[token]/`         |
| `ForgotPasswordPage.tsx` / `ResetPasswordPage.tsx` | 申请重置 / 重置页                                                                            | `packages/web/app/[locale]/`                        |
| `AdminUsersPage.tsx`                               | 用户管理 UI (表格 + 行操作)                                                                  | `packages/web/app/[locale]/admin/users/`            |
| `AdminInvitesPage.tsx`                             | Invite 列表 + 撤销                                                                           | `packages/web/app/[locale]/admin/invites/`          |
| `UserMenu.tsx`                                     | 顶部右上角登录/账号下拉                                                                      | `packages/web/components/`                          |
| Server Actions                                     | `loginAction`, `logoutAction`                                                                | `app/[locale]/_actions/account.ts`                  |

## 数据模型

### users 表 (现有, 加 1 列)

```sql
ALTER TABLE users ADD COLUMN account_id INTEGER REFERENCES accounts(id);
-- account_id NULL = 纯 anon; 非 NULL = 关联到真账号
-- ondelete SET NULL (防御性, 本期不删 account)
```

`display_name` / `last_seen_at` / `created_at` / `public_token` 全保留不动.

### accounts 表 (新)

```sql
CREATE TABLE accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE NOT NULL,                    -- login 用
    password_hash TEXT NOT NULL,                    -- bcrypt (12 rounds)
    display_name TEXT,                              -- 跟 users.display_name 同步
    is_admin BOOLEAN NOT NULL DEFAULT FALSE,        -- 全局 admin 角色
    is_active BOOLEAN NOT NULL DEFAULT TRUE,        -- 禁用 = FALSE, 拒绝登录 + token 失效
    created_at DATETIME NOT NULL,
    last_login_at DATETIME,                         -- 审计/管理用
    CONSTRAINT email_format CHECK (email LIKE '%_@_%._%')  -- 防御性, 严格校验在 Pydantic
);
CREATE INDEX idx_accounts_email ON accounts(email);
CREATE INDEX idx_accounts_is_active ON accounts(is_active);
```

### invites 表 (新)

```sql
CREATE TABLE invites (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    token TEXT UNIQUE NOT NULL,                     -- 32 字节 hex, 一次性
    email TEXT NOT NULL,                            -- 预填, 收件人
    invited_by_account_id INTEGER NOT NULL REFERENCES accounts(id),
    expires_at DATETIME NOT NULL,                   -- 7 天 (env: INVITE_EXPIRES_DAYS)
    redeemed_at DATETIME,                           -- NULL = 未用
    account_id INTEGER REFERENCES accounts(id),     -- redeem 后填, 关联新账号
    created_at DATETIME NOT NULL
);
CREATE INDEX idx_invites_token ON invites(token);
CREATE INDEX idx_invites_email ON invites(email);
```

### password_resets 表 (新)

```sql
CREATE TABLE password_resets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL REFERENCES accounts(id),
    token TEXT UNIQUE NOT NULL,
    expires_at DATETIME NOT NULL,                   -- 1 小时 (env: PASSWORD_RESET_EXPIRES_HOURS)
    used_at DATETIME,
    created_at DATETIME NOT NULL
);
CREATE INDEX idx_password_resets_token ON password_resets(token);
```

**Why 3 张表分**:

- `invites` 跟 `password_resets` 都是"一次性 token" 但语义不同, 混一起会难查
- `users` 不动, anon 不破坏

## 鉴权流

### A. 登录

```
POST /api/account/login
  body: { email, password }
  200: { token, account: { id, email, display_name, is_admin } }
       + Set-Cookie: rag_user_token=<token>  HttpOnly, SameSite=Lax, 7d
  401: 密码错 / 账号禁用 / 邮箱不存在 (统一 "invalid credentials")
```

**实现**:

1. 查 `accounts` 表 email → 拿到 `password_hash` + `is_active`
2. `is_active == False` → 401
3. `bcrypt.verify(password, password_hash)` → False → 401
4. 找/创 `users` 行 (email 唯一对应一个 user, account_id 关联):
   - 已存在 (旧 anon 升级场景) → 绑 `user.account_id = account.id`
   - 不存在 → `User(public_token=<new_hex>, display_name=<email_prefix>, account_id=<new_id>)` 创
5. 更新 `accounts.last_login_at = now()`
6. 返 `public_token` (同 anon 格式, 跟现有 `x-user-token` 兼容) + Set-Cookie

### B. 登出

```
POST /api/account/logout
  Auth: x-user-token OR cookie rag_user_token
  200: { ok: true }
       + Set-Cookie: rag_user_token=; Max-Age=0
```

**仅清 cookie**, 不删 `users` 行 (anon 还在, 账号不删历史). 软登出, 后续重登直接用.

### C. Invite 流程 (admin → 新账号)

```
1. Admin 调:
   POST /api/admin/users
   body: { email, is_admin: false, display_name?: "张三" }
   Auth: require_admin
   200: { invite_token, invite_url: "/<locale>/invite/<token>", email, is_admin }
   409: email 已被注册 / 有未用 invite

2. 用户点 invite URL, 进 redeem 页:
   GET /api/invites/<token>  →  { email, expires_at }
   渲染表单: email (read-only), display_name, password, confirm
   提交 POST /api/invites/<token>/redeem
     body: { display_name, password }
     → 创 account, 创/绑 user, 标 invite.redeemed_at + account_id
     → 返 Set-Cookie + token, redirect /

3. Token 过期/已用 → 400 "invite token invalid" (不区分过期 vs 已用, 防探测)
```

### D. Password reset

```
1. 登录页 "忘记密码?" → /forgot-password
2. POST /api/account/forgot-password
   body: { email }
   - 总是返 200 "如果邮箱存在, 重置链接已生成" (不暴露邮箱是否存在)
   - 实际: 查 account → 生成 token → 写 password_resets 表 → 返 URL 路径 (admin 复制发, 无邮件)
3. POST /api/account/reset-password
   body: { token, new_password }
   - 验证 token 未过期未用 → 改 password_hash → 标 used_at
   - 登出所有 device: 不做 (本期软)
```

### E. Bootstrap admin (首次部署)

```
POST /api/account/seed-admin
  鉴权: RAG_ADMIN_TOKEN header 必须 (env)
  body: { email, password, display_name }
  200: { account_id, email }
  409: 已存在 is_admin=True 账号, 或 email 占用
  401: token 错
```

**仅首次可用**: 已经有 `is_admin=True` 的 account 时返 409.
走完此步后, admin 用真账号登录, `RAG_ADMIN_TOKEN` 仅作运维 recovery.

### F. 错误码统一

| 状态 | 触发                    | message                                      |
| ---- | ----------------------- | -------------------------------------------- |
| 401  | token 缺                | `missing x-user-token`                       |
| 401  | token 错                | `invalid user token`                         |
| 401  | account.is_active=False | `account disabled`                           |
| 400  | 登录密码错              | `invalid credentials` (不区分 user 存不存在) |
| 400  | invite 过期/已用        | `invite token invalid`                       |
| 400  | reset token 过期/已用   | `reset token invalid`                        |
| 403  | 非 admin 调 admin API   | `admin required`                             |
| 400  | 自禁自 admin            | `cannot disable self`                        |
| 400  | 改 anon 的 is_admin     | `anon user cannot be admin`                  |
| 409  | 重复 email              | `email already registered`                   |
| 409  | 有未用 invite           | `pending invite exists`                      |
| 409  | bootstrap 已跑过        | `admin already initialized`                  |

## Admin 操作 API

所有 admin 端点共用 `Depends(require_admin)` 守卫.

### A. 用户列表

```
GET /api/admin/users
  Auth: require_admin
  Query: ?search=foo&kind=account|anon&is_active=true&page=1&page_size=20
  200: {
    items: [
      { id, email, display_name, is_admin, is_active,
        kind: "account" | "anon",
        account_id: int | null,
        created_at, last_seen_at, last_login_at,
      },
      ...
    ],
    total, page, page_size,
  }
```

**`kind` 派生规则**:

- `account_id IS NULL` → `"anon"`
- `account_id IS NOT NULL` → `"account"`

**Query 过滤**:

- `search` → `email LIKE '%foo%' OR display_name LIKE '%foo%'`
- `kind` → account / anon
- `is_active` → accounts 表的 is_active
- `page` / `page_size` → 标准分页 (上限 100)
- **anon 行的 is_admin 永远 False** (UI 显示禁用 "提权" 按钮)

### B. 创 invite

```
POST /api/admin/users
  Auth: require_admin
  body: { email, is_admin: false, display_name?: "张三" }
  200: { invite_token, invite_url: "/zh/invite/<token>", email, is_admin }
  409: email 已被注册 / 有未用 invite
```

**不立即创 account** (等 redeem 阶段). 创 invite 行 (token=secrets.token_hex(32), expires_at=now+7d, invited_by=admin.account_id).

### C. 改用户

```
PATCH /api/admin/users/{user_id}
  Auth: require_admin
  body: { is_active?: bool, is_admin?: bool, display_name?: str }
  200: { id, ... updated fields }
  400: 自禁自 admin / 改 anon is_admin
  404: user 不存在
```

**`user_id` 是 `users.id`**. 修改路径:

- `is_active` 走 accounts 表 (anon 行无此字段, **本期不支持改 anon is_active, UI 标灰**)
- `is_admin` 走 accounts 表; 切换后**新请求立即生效** (token 重新查就行)
- `display_name` 走 users 表
- **不能改 email** (本期不开放, 改 email 涉及登出所有 device + 重发验证)

### D. 重设密码

```
POST /api/admin/users/{user_id}/reset-password
  Auth: require_admin
  body: {}
  200: { temp_password: "ab12-cd34-..." }
  400: user 无 account (anon 不能重设)
```

**临时密码**: `secrets.token_urlsafe(12)` (16 字符, 难猜 + 易复制), `password_hash` 直接覆盖.
**不**用 invite 流程 (无 email 确认). 用户首次登录建议自己改.

### E. Invite 管理

```
GET /api/admin/invites?status=pending|redeemed|expired|all
  返 invites 列表 (id, email, invited_by, created_at, expires_at, redeemed_at)

DELETE /api/admin/invites/{id}  # 撤销未redeem 的 invite
```

### F. 删用户 (本期不做)

按决策: 不删. 禁用 (is_active=False) 代替.

## 前端

### A. 路由 / 页面

```
packages/web/app/[locale]/
  login/page.tsx              # 登录页
  invite/[token]/page.tsx     # Invite 兑换页
  forgot-password/page.tsx    # 申请重置
  reset-password/page.tsx     # 重置 (用 token)
  admin/
    users/page.tsx            # 用户列表 + 行操作
    invites/page.tsx          # Invite 列表 + 撤销
  layout-changes:
    layout.tsx: UserMenu (anon: 登录, 账号: display_name 下拉, admin: 多 "用户管理")
```

**Auth-gate**:

- `middleware.ts` 检查 cookie `rag_user_token`
- 无 token + 访问 `/admin/*` → 重定向 `/login?next=/zh/admin/users`
- 有 token + 访问 `/login` → 重定向 `/`

### B. LoginPage

```tsx
// 字段: email, password
// 主按钮: "登录" (shadcn Button, full width)
// 副链接: "忘记密码?" → /forgot-password
// 错误: 顶部红条, 401 → "邮箱或密码错", 不区分
// 成功后: router.push(next || "/")
```

**i18n keys** (4 个):

- `登录` / `Sign in`
- `邮箱` / `Email`
- `密码` / `Password`
- `忘记密码?` / `Forgot password?`

### C. InviteRedeemPage

```tsx
// 服务端 (RSC): fetch GET /api/invites/<token> 拿 email + 校验
//   401/404 → 错误页 (不区分过期/已用)
// 表单: email (read-only), display_name, password, confirm_password
// 提交: POST /api/invites/<token>/redeem
//   成功 → 返 cookie + token, redirect /
//   失败 → 顶部错误
```

**i18n keys** (3 个):

- `接受邀请` / `Accept invitation`
- `显示名称` / `Display name`
- `确认密码` / `Confirm password`

### D. AdminUsersPage

**布局** (RSC + Client 子组件):

```
+--------------------------------------------------------+
| [搜索]  [is_active ▼]  [account/anon ▼]  [+ 创账号]   |
+--------------------------------------------------------+
| 邮箱 | 类型 | 角色 | 状态 | 创建 | 最近活动 | 操作    |
| alice | account | admin | 活跃 | ... | ... | [禁][改][重设] |
| bob   | account | 用户  | 活跃 | ... | ... | [禁][提权][重设] |
| anon-123 | anon | - | - | ... | ... | [—]              |
+--------------------------------------------------------+
|        [上一页] 1/8 [下一页]                           |
+--------------------------------------------------------+
```

**组件拆**:

- `AdminUsersPage.tsx` (RSC): 拉数据 + 鉴权 guard
- `AdminUsersTable.tsx` (client): 表格 + 过滤
- `AdminUserRow.tsx` (client): 行 + 操作按钮
- `CreateInviteDialog.tsx` (client, shadcn Dialog): 创账号 invite
- `ResetPasswordDialog.tsx` (client): 重设密码后显示临时密码

**操作流**:

1. **创账号** → Dialog → email + is_admin 复选 → 提交 → 弹"复制 invite URL"
2. **禁用/启用** → 行内按钮 → 确认 → PATCH → 乐观更新 (失败回滚)
3. **提权/降权** → 改 is_admin → 确认 (改自己 → disabled)
4. **重设密码** → Dialog → 调 API → 弹"复制临时密码"

**权限 UX**:

- 当前用户行: "禁用" / "重设" 按钮 disabled (防自锁), tooltip "不能禁自己"
- anon 行: "提权" 按钮 disabled, tooltip "anon 不能是 admin"
- `is_bootstrap_admin=True` 用户看自己: 顶部 banner "请尽快 seed 真 admin 账号"

**i18n keys** (8 个):

- `用户管理` / `User management`
- `创账号` / `Create account`
- `禁用` / `Disable`
- `启用` / `Enable`
- `重设密码` / `Reset password`
- `提权` / `Grant admin`
- `取消权限` / `Revoke admin`
- `复制邀请链接` / `Copy invite link`

### E. UserMenu (Header 右上角)

- anon: `登录` 按钮 (→ /login)
- 账号: display_name / email, 下拉 `账号设置` / `登出`
- admin: 下拉多一项 `用户管理` (→ /admin/users)
- bootstrap admin: 顶部 banner "请尽快 seed 真 admin 账号"

**Header 组件** (现有 `components/header.tsx`) 改: 加 user menu.
数据来源: `app/[locale]/layout.tsx` 调 `GET /api/account/me` 拿当前 CurrentUser (cookie 自动带).

### F. 鉴权守卫 (双层)

**前端**:

1. RSC `app/[locale]/admin/users/page.tsx`: `GET /api/account/me` → 没账号 → `redirect("/login?next=...")`; 不是 admin → `redirect("/")` + toast "无权访问"
2. Client 子组件: 操作按钮 disabled 当前 row.id === me.id
3. **后端 401/403 是兜底** (前端 guard 防 UX 跳, 后端 guard 防直接 curl)

## 测试

### A. 后端 (pytest)

| 测试文件                                    | 测什么                                             | 关键 case                                                                                                                      |
| ------------------------------------------- | -------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------ |
| `tests/auth/test_account_models.py`         | accounts / invites / password_resets 表结构 + 约束 | email unique 重复 → IntegrityError; is_active 默认 True; FK                                                                    |
| `tests/auth/test_password.py`               | bcrypt hash + verify                               | 同密码两次 hash 不同; 错密码 verify False; 长度边界 8                                                                          |
| `tests/auth/test_login.py`                  | `POST /api/account/login`                          | 正确 → 200 + token + cookie; 错密码 → 401; 禁用 → 401; 不存在 → 401 (不区分); 空 body → 422                                    |
| `tests/auth/test_logout.py`                 | `POST /api/account/logout`                         | 清 cookie; 已登出再调 → 200 idempotent                                                                                         |
| `tests/auth/test_invite_flow.py`            | 完整 invite → redeem                               | admin 创 invite → 拿 token; redeem → 创 account + 绑 user; **重 redeem** → 400; 过期 → 400                                     |
| `tests/auth/test_password_reset.py`         | 申请 + 重置                                        | 不存在 email → 200 (不暴露); 有效 token → 改 hash + 标 used; 重用 used → 400                                                   |
| `tests/auth/test_admin_users_api.py`        | admin CRUD                                         | 列表分页 + 过滤; 创 invite + 重复 email 409; 改 is_admin 立即生效; 改 is_active=False → 旧 token 401; 自禁 → 400               |
| `tests/auth/test_middleware_integration.py` | `CurrentUser` 解析                                 | anon → is_account=False; 账号 → is_account=True + email; 禁用 → 401; bootstrap admin → is_admin=True; 真 admin → is_admin=True |
| `tests/auth/test_seed_admin.py`             | `POST /api/account/seed-admin`                     | 首次: 创 account + user; 已有 admin → 409; 错 RAG_ADMIN_TOKEN → 401                                                            |

**关键 mock / fixture**:

- `tmp_db_url` (已有) 隔离 DB
- `make_account()` / `make_user()` fixture 工厂
- `bypass_admin_token(monkeypatch)` 设 `RAG_ADMIN_TOKEN=test-admin-token` + 客户端加 header
- **不 mock bcrypt** (用真 hash, 慢一点但更真)
- **不 mock time** (用 freezegun 或 datetime.now 注入, 验 token 过期)

### B. 前端 (vitest + @testing-library)

| 测试文件                                                            | 测什么         | 关键 case                                                                            |
| ------------------------------------------------------------------- | -------------- | ------------------------------------------------------------------------------------ |
| `app/[locale]/login/page.test.tsx`                                  | 登录表单       | 输错密码 → 顶部错误; 成功 → redirect `/`; 接受 `?next=...`; 空字段按钮 disabled      |
| `app/[locale]/invite/[token]/page.test.tsx`                         | Invite 兑换    | token 失效 → 错误页; 密码 < 8 → 客户端校验; 密码不匹配 → 错误; 成功 → redirect       |
| `app/[locale]/admin/users/page.test.tsx`                            | 用户管理页     | anon → redirect /login; 账号非 admin → redirect /; admin → 看到列表; 当前 row 按钮灰 |
| `app/[locale]/admin/users/_components/CreateInviteDialog.test.tsx`  | 创 invite 弹框 | 提交 → 调 API + 弹"复制 URL"; 重复 email → 错误                                      |
| `app/[locale]/admin/users/_components/ResetPasswordDialog.test.tsx` | 重设密码弹框   | 调 API → 显示临时密码 + 复制                                                         |
| `components/header.test.tsx` (扩展)                                 | UserMenu 增项  | anon → "登录"; 账号 → display_name + 下拉; admin → 下拉多 "用户管理"                 |
| `app/[locale]/_actions/account.test.ts`                             | Server Actions | loginAction: 正确 → revalidate; 错密码 → throw; logoutAction                         |

**关键 mock**:

- `next/navigation`: `useRouter`, `redirect`
- `next/headers`: `cookies()` 拿 rag_user_token
- 同源 fetch: `vi.mock("@/lib/api/account", ...)` 返 mock response
- **不 mock** 整个 layout (避免 mock 漏)

### C. E2E (Playwright, 留 follow-up)

- 登录 E2E: 创 invite → redeem → 用新账号登录 → 看到 nav 改
- Admin E2E: admin 登录 → 创 invite → 看到 invite 在列表
- 守卫 E2E: anon 直接访问 /admin/users → 重定向

**Why E2E 留 follow-up**: pytest + vitest 单元覆盖 + 集成测试 (TestClient) 够; Playwright 跑慢 + 难维护. 现有 web-e2e 也就冒烟.

### D. 验收 checklist

- [ ] 9 个后端 pytest 文件 0 fail
- [ ] 7 个前端 vitest 文件 0 fail
- [ ] `curl` 跑完 invite 完整流: admin 创 → user 兑换 → 用新密码登录 → /api/account/me 返 is_admin
- [ ] 浏览器手测: anon 进 /admin/users → 重定向; admin 进 → 看到列表
- [ ] 旧 anon token 仍 work (E2E 全过)
- [ ] README 更新到位

## 部署 / 迁移

### A. 启动顺序 (首次部署)

```
1. 部署代码 + 跑 migration (创 accounts/invites/password_resets 3 表 + users.account_id 列)
2. 配环境变量 (RAG_ADMIN_TOKEN 必须设, 旧项目已有)
3. 调 POST /api/account/seed-admin (admin token 鉴权) 创首个真 admin 账号
4. 用真 admin 账号登录, 在 /admin/users 邀请其他用户
5. (可选) 撤掉 RAG_ADMIN_TOKEN env, 之后只走真账号; 或保留作运维 recovery
```

### B. 现有项目迁移 (已部署的)

**当前生产数据**:

- `users` 表已有 N 个 anon 行
- `RAG_ADMIN_TOKEN` env 在用
- 旧 `RAG_DEV_AUTH=1` 开发模式

**迁移步骤**:

1. 部署新代码 (含 migration)
2. **anon 行不动** — 继续走 `x-user-token`, 行为完全不变
3. admin 调 `POST /api/account/seed-admin` 创首个真 admin
4. (可选) 给现有用户发 invite: 跑一次性脚本 `python -m scripts.invite_existing_users --dry-run`, 看到列表后 `--apply`. **本期脚本不写**, 留 follow-up.

### C. Alembic Migration

**新 revision** `2a3b4c5d6e7f_add_accounts_and_invites.py`:

- `op.create_table("accounts", ...)` 含 email/password_hash/is_admin/is_active/created_at/last_login_at
- `op.create_table("invites", ...)` 含 token/email/invited_by/expires_at/redeemed_at
- `op.create_table("password_resets", ...)` 含 account_id/token/expires_at/used_at
- `op.add_column("users", sa.Column("account_id", sa.Integer, nullable=True))`
- `op.create_foreign_key("fk_users_account_id_accounts", "users", "accounts", ["account_id"], ["id"], ondelete="SET NULL")`
- 多个 index (email, is_active, token, account_id)

**可逆**: `downgrade()` 完整 reverse. dev 库跑一遍 upgrade + downgrade 验证.

### D. Seed Script

`scripts/seed_admin.py`:

- 调 `POST /api/account/seed-admin` (RAG_ADMIN_TOKEN header 鉴权)
- 用 `RAG_SEED_ADMIN_EMAIL` + `RAG_SEED_ADMIN_PASSWORD` env
- 200 → 成功; 409 → 已存在 (idempotent); 401 → 错 token

### E. .env 增量

```bash
# .env.local (追加, 现有保留)
PASSWORD_MIN_LENGTH=8                    # 密码最小长度
INVITE_EXPIRES_DAYS=7                    # invite token 寿命
PASSWORD_RESET_EXPIRES_HOURS=1           # reset token 寿命
# RAG_ADMIN_TOKEN 已有, 保留作 bootstrap
# RAG_DEV_AUTH 已有, 保留
```

**新配置项走 `os.getenv()` + 合理 default**, 不强求 .env 必填.

### F. README 更新

加一节 "账号系统":

- 首次部署: 跑 seed script
- Admin 操作: 创 invite / 禁用 / 重设密码
- 开发模式: `RAG_DEV_AUTH=1` 仍工作 (anon), 跟真账号并存

## 风险 + 缓解

| 风险                                         | 缓解                                                                 |
| -------------------------------------------- | -------------------------------------------------------------------- |
| Migration 失败导致表不存在 → 后端崩          | migration 跑前 smoke test (启服务, 跑 GET /health); 失败回滚 alembic |
| 现有 anon token 失效                         | 0 改动 anon 表 schema, 中间件 anon 路径不变; 集成测试覆盖            |
| 首次 admin 没创 → 锁死                       | seed-admin 端点永远接受 `RAG_ADMIN_TOKEN`; UI 顶部 banner 提示       |
| 密码 hash 慢 (bcrypt 12 rounds)              | 12 rounds 平衡 (1 hash ~250ms); login 限流 (本期不做) 留给 follow-up |
| 现有 `users` 行加 account_id 列可能慢 (大表) | SQLite `ALTER TABLE ADD COLUMN` 瞬时; Alembic 跑 ~10ms               |
| invite 链接泄露 (手工发错)                   | 7 天过期 + 一次性 redeem; 跟 secret link 一样风险                    |
| 临时密码泄露                                 | 16 字符 urlsafe; 不存明文; UI 提示尽快改                             |
| bcrypt cost 误配                             | 12 rounds 标准, 走 env 配; 单元测覆盖                                |
| 并发 invite 同一 email                       | unique constraint + 409; UI 友好提示                                 |

## 实施 Phase (建议 4 phase)

**Phase 1 - 后端 backbone** (1 周):

- Alembic migration (3 表 + users 加列)
- Account/Invite/PasswordReset models
- 密码 hash 工具
- `POST /api/account/login`, `/logout`, `/me`
- middleware 升级 + 集成测

**Phase 2 - Invite + reset + admin API** (1 周):

- `POST /api/admin/users` (创 invite)
- `GET /api/invites/<token>`, `POST /redeem`
- `POST /api/account/forgot-password`, `POST /reset-password`
- `GET /api/admin/users`, `PATCH`, `/reset-password`
- `POST /api/account/seed-admin`
- 完整 pytest 覆盖

**Phase 3 - 前端基础** (1 周):

- LoginPage + Server Action
- InviteRedeemPage
- ForgotPasswordPage / ResetPasswordPage
- Header UserMenu
- 鉴权 middleware (next middleware.ts)
- 7 个 vitest 文件

**Phase 4 - Admin UI + Seed script + 文档** (3 天):

- AdminUsersPage + Table + Row + Dialogs
- AdminInvitesPage
- `seed_admin.py` script
- README 更新
- 浏览器手测

**Total**: ~3-4 周, 1 人.

## 安全 / 兼容

- **API 向后兼容**: 现有 `/api/auth/anon` / `/migrate` 不动; 现有 anon token 仍 work
- **不写入新代码路径外的字段**: `CurrentUser` 7 字段是 additive (现有 3 字段 + 新 4 字段), 现有依赖 `id`/`public_token`/`is_admin` 的代码 0 改动
- **不引入新依赖**: bcrypt 是 Python stdlib 通过 `passlib` 或 `bcrypt` 包, 二选一 (倾向 `bcrypt` 原生, 简单)
- **密码策略**: min 8 字符 (Pydantic 校验), 不强求复杂度 (UX 优先)
- **CSRF**: 同源 cookie SameSite=Lax, 跨站 GET 不带 cookie; admin PATCH 走服务端 action
- **不存明文密码**: bcrypt hash only, 临时密码也不入库 (UI 显示一次)

## Follow-up (本期外)

- E2E Playwright 覆盖完整流
- Login 限流 (防爆破)
- Email 发送 (invite / reset)
- 删除用户 (替代禁用)
- Audit log (谁在何时改了什么)
- 2FA / SSO
- 多租户
- 改 email 流 (重发验证 + 登出所有 device)
