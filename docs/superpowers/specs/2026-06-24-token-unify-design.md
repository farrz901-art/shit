# Token & Env 变量统一化设计 (2026-06-24)

> 用户原问: "RAG_DEV_AUTH 和 RAG_ADMIN_TOKEN 这种环境变量是否还有意义, 现在只要超级管理员不就够了"
>
> 锁定结论 (brainstorming 2026-06-24 4 轮澄清):
> 1. 项目范式 = 多用户 + super_admin 角色 (现状, 不动)
> 2. `RAG_DEV_AUTH` = dev super_admin bypass, 保留
> 3. `RAG_ADMIN_TOKEN` + `x-admin-token` = bootstrap 一次性通道, 保留
> 4. RBAC 3 角色 (super_admin / operator / user) 保留
> 5. 删前端死代码 `rag_admin_token` cookie + `x-admin-token` 接收 + E2E 1 处

## 1. 范围

### 1.1 做 (4 项)

| # | 类别 | 改动 |
|---|---|---|
| A | docs | `packages/service/.env.example` 2 个 env 补注释 |
| B | web 代码 | 删 4 处 `rag_admin_token` cookie 死读取 |
| C | e2e | `04-evaluate.spec.ts` 1 处 `localStorage.setItem` 改 user token |
| D | test | `auth.server.test.ts` 删 admin cookie 优先相关 case |

### 1.2 不做 (7 项)

- ❌ 砍 `RAG_ADMIN_TOKEN` env
- ❌ 砍 `RAG_DEV_AUTH` env
- ❌ 改 RBAC 3 角色 (super_admin / operator / user)
- ❌ 改 `x-user-token` 主鉴权 (6h sliding)
- ❌ 改 `seed-admin` 端点鉴权流程
- ❌ 改 `RAG_ADMIN_TOKEN` 比较逻辑
- ❌ 改后端 `middleware/auth.py` 整文件

## 2. 改动清单 (按文件)

### 2.1 docs 改 1 文件

`packages/service/.env.example`:

```bash
# RAG_ADMIN_TOKEN
# (2026-06-24) bootstrap-only: 首次部署 DB 空时, 调 POST /api/account/seed-admin
# (header x-admin-token == RAG_ADMIN_TOKEN) 创首个 super_admin 账号.
# 创好 super_admin 后即可置空 env (置空后任何 seed-admin 请求 401).
# 跟业务主鉴权 x-user-token 完全独立, 仅作 bootstrap 一次性.
RAG_ADMIN_TOKEN=

# RAG_DEV_AUTH
# (2026-06-24) dev-only: =true 时无 token 自动注入 super_admin(id=1) dev user.
# 等同于登录超级管理员, 0 真实账号. prod 必须 =false (默认).
# 测试基础设施: 15+ tests 依赖 RAG_DEV_AUTH=true 走真 resolve_user 链路.
RAG_DEV_AUTH=true
```

### 2.2 web 代码删 4 处死 cookie 读取

`packages/web/lib/api/auth.server.ts`:
- L11: `cookieStore.get("rag_admin_token")?.value ??` 删
- L23-24: 删 `const user = ...` + `const admin = ...` 整段 admin 读取
- L28: 保留 `out["x-user-token"] = tokenValue;` (user 优先, 跟注释一致)

`packages/web/app/api/[...path]/route.ts`:
- L62: 删 `const admin = jar.get("rag_admin_token")?.value;`
- L66: 保留 `out["x-user-token"] = tokenValue;` (现 user 优先)

`packages/web/lib/chat/memory-integration.ts`:
- L49: 删 `const adminToken = cookieJar.get("rag_admin_token")?.value;`
- L53: 删 `headers["x-admin-token"] = adminToken;` (后端不识别,死代码)

### 2.3 e2e 改 1 处

`packages/web/e2e/04-evaluate.spec.ts`:
- L16: `localStorage.setItem("rag_admin_token", tok)` → `localStorage.setItem("rag_user_token", tok)`
- 期望 header 跟着改 (后端只认 x-user-token, 原本期望就是 x-user-token, 仅 cookie 名字)

### 2.4 test 改 1 文件

`packages/web/lib/api/auth.server.test.ts`:
- L54-58: 删 "两 token 同存" case
- L82: 删 "不会同时设 x-admin-token" case
- 保留 "只有 user token" + "都没时" 两个 case

## 3. 不动的代码

- `packages/service/src/middleware/auth.py` 整文件 — `x-user-token` 6h + `RAG_DEV_AUTH` bypass 现状完美
- `packages/service/src/auth/auth_account_router.py:237-239` — `RAG_ADMIN_TOKEN` env 比较不动
- `packages/service/src/auth/router.py` — `x-user-token` 业务发码不动
- 任何用 `RAG_DEV_AUTH` 的 tests — 不动, 15+ 处测试基础设施保留
- `RAG_ADMIN_TOKEN` 相关 tests (test_seed_admin.py, test_admin_users_api.py 等) — 不动, bootstrap 鉴权测试保留
- `RAG_DEV_AUTH` 相关 tests (test_router.py, test_auth_cookie.py 等) — 不动, 真 resolve_user 链路验证

## 4. Token 架构终态 (项目 2026-06-24)

```
┌────────────┬──────────────────────┬──────────────────────┐
│            │ x-user-token         │ x-admin-token         │
├────────────┼──────────────────────┼──────────────────────┤
│ 位置       │ Header + cookie      │ Header (cookie 死代码)│
│            │ rag_user_token       │ (本 spec 删 cookie)   │
├────────────┼──────────────────────┼──────────────────────┤
│ 后端验证   │ users.token 查表      │ == RAG_ADMIN_TOKEN    │
│            │ 6h Redis cache       │ env 字符串比较          │
├────────────┼──────────────────────┼──────────────────────┤
│ 生命周期   │ 6h sliding 过期       │ 永久 (env 不动就不动)   │
├────────────┼──────────────────────┼──────────────────────┤
│ 身份标识   │ users.id (1=dev,     │ 无 (仅作 bootstrap      │
│            │ 2=acc 等)            │ 验证, 不指代 user)       │
├────────────┼──────────────────────┼──────────────────────┤
│ 用途       │ 一切业务请求          │ 唯一: POST             │
│            │                      │ /api/account/seed-admin│
│            │                      │ 创 首个 super_admin     │
├────────────┼──────────────────────┼──────────────────────┤
│ 存在意义   │ 唯一鉴权              │ bootstrap 残骸,        │
│            │ (100% 业务 走它)      │ "建好 首 super 即可 弃"   │
├────────────┼──────────────────────┼──────────────────────┤
│ 本 spec 后 │ 不动                  │ 保留 env + header,     │
│            │                      │ 删前端 cookie 残留      │
└────────────┴──────────────────────┴──────────────────────┘

Dev bypass (RAG_DEV_AUTH=true):
- 优先级 2: 无 token → 自动注入 super_admin(id=1) dev user
- 跟 x-user-token 互斥 (有 token 走 token, 无 token 才 bypass)
- 跟 x-admin-token 互斥 (bootstrap 端点不走 RAG_DEV_AUTH)
```

## 5. 验证 (跟 CLAUDE.md 5 步)

| 步 | 命令 | 期望 |
|---|---|---|
| 1 | `bun run format` | 0 reformatted |
| 2 | `bun run lint` | 0 error / 0 warning |
| 3 | `bun run typecheck` | 0 error |
| 4 | `bun run test` (前端) | 0 新 fail |
| 5 | `uv run ruff check --fix` + `uv run pyright` + `uv run pytest` (后端) | 0 新 fail |
| 手动 | 登录 → 拿 user token → 调 /api/admin/* → 200 | super_admin role 够用 |

## 6. 影响面

- **行为变化**: 0 (死代码本来就返回 undefined)
- **代码净减少**: ~10 行 (删 4 处 cookie 读取 + 1 处死 header 注入)
- **E2E 改 1 处**: cookie 名字 (语义不变)
- **文档净增加**: 2 个 env 注释
- **依赖**: 无新增
- **数据库**: 无变更
- **API**: 无变化
- **RBAC**: 无变化

## 7. 关联文档

- `packages/service/CLAUDE.md` — 后端鉴权规范
- `packages/web/CLAUDE.md` — 前端 BFF / cookie 规范
- [[feedback-no-shim-no-minimal-changes]] — 死代码不留原则
- [[feedback-rsc-fetch-no-browser-cookie]] — RAG_DEV_AUTH dev bypass
- [[feedback-apiFetch-needs-explicit-auth-headers]] — RAG_DEV_AUTH 与 server apiFetch 关系
- 2026-06-24 fix(chat) commit 1 — Bug 4 修后端不识别 x-admin-token, 已统一注 x-user-token (本 spec 跟进清理前端残留)

## 8. 风险 & 缓解

| 风险 | 缓解 |
|---|---|
| 误删 `rag_user_token` 路径 (跟 `rag_admin_token` 长得像) | 改动前 grep "rag_user_token" 验证 user 路径完整 |
| E2E 04 改 cookie 名后漏改期望 header | 改完跑 e2e 验证 (虽然本次不要求 e2e 通过, 但起码解析过 expect) |
| 删 `[...path]/route.ts:62` 后 BFF 漏传 | 保留 L66 `out["x-user-token"] = tokenValue;` (user 优先) |
| 文档注释过长 | 注释控制在 5 行内, 跟现有 .env.example 风格一致 |

## 9. 不在本 spec 范围 (future work)

1. **种子 super_admin 后** 真正置空 `RAG_ADMIN_TOKEN` env (用户操作, 非代码)
2. **`RAG_DEV_AUTH` 改用真 super_admin 登录** (15+ tests 需 dependency override, 工作量大, 当前不动)
3. **`RAG_ADMIN_TOKEN` 改用 key 文件而非 env** (更安全, 跟 secret manager 集成, 当前 YAGNI)
4. **seed-admin 端点响应体加 audit log** (现仅有 service 层 @audited, 端点本身无 audit, 当前 YAGNI)
