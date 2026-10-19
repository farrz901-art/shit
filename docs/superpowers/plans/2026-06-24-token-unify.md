# Token & Env 统一化实现 Plan (2026-06-24)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 删前端 4 处 `rag_admin_token` cookie 死读取 + 1 处 E2E 死 set + 1 处 test 死 case,补 `.env.example` 2 个 env 注释。业务行为 0 变化。

**Architecture:**
- 后端 `RAG_DEV_AUTH` (dev super_admin bypass) 和 `RAG_ADMIN_TOKEN` (bootstrap 一次性) 都不动,只 doc 补清晰
- 前端 4 处 `rag_admin_token` cookie 读取全部删,因为后端业务不识别 `x-admin-token`,cookie 永远 undefined
- E2E 1 处 set 改用 user token,test 1 处 admin cookie 优先 case 删

**Tech Stack:** Next.js 16 / React 19 / TypeScript 8 (前端) + FastAPI / Python 3.14 (后端) + Playwright (E2E) + Vitest (单元) + oxlint / oxfmt / tsgo / ruff / pyright

**Spec:** [docs/superpowers/specs/2026-06-24-token-unify-design.md](docs/superpowers/specs/2026-06-24-token-unify-design.md)

---

## File Structure

**改 4 文件 + 改 1 文档 + 改 1 E2E + 改 1 test**(spec §2 完整列表):

| 文件 | 类别 | 改法 |
|---|---|---|
| `packages/service/.env.example` | doc | 2 个 env 加注释 (RAG_ADMIN_TOKEN / RAG_DEV_AUTH) |
| `packages/web/lib/api/auth.server.ts` | web 死代码 | 删 L11 admin cookie 读取 + L23-24 admin 变量 |
| `packages/web/app/api/[...path]/route.ts` | web 死代码 | 删 L62 admin cookie 读取 |
| `packages/web/lib/chat/memory-integration.ts` | web 死代码 | 删 L49 admin cookie + L53 死 header 注入 |
| `packages/web/e2e/04-evaluate.spec.ts` | E2E | L16 set 改 user token |
| `packages/web/lib/api/auth.server.test.ts` | test | 删 2 个 admin cookie case (L54-58 + L82) |

**不动 9+ 文件**(spec §3):
- `packages/service/src/middleware/auth.py` (主鉴权逻辑)
- `packages/service/src/auth/auth_account_router.py:237-239` (RAG_ADMIN_TOKEN 比较)
- `packages/service/src/auth/router.py` (x-user-token 业务发码)
- 任何用 `RAG_DEV_AUTH` 的 tests
- `RAG_ADMIN_TOKEN` 相关 tests

---

## Task 1: 删 `auth.server.ts` 死 cookie 读取

**Files:**
- Modify: `packages/web/lib/api/auth.server.ts:11,23-24`

- [ ] **Step 1: Read 现状,确认 user 路径完整**

读 `packages/web/lib/api/auth.server.ts` 全文,确认:
- L11 行有 `cookieStore.get("rag_admin_token")?.value ??`
- L23-24 行有 `const user = ...; const admin = ...`
- L28 行有 `out["x-user-token"] = tokenValue;` (user 优先, 保留)

- [ ] **Step 2: 改 L11 删 admin cookie 读取**

将 L11 改为:
```typescript
cookieStore.get("rag_user_token")?.value ?? ""
```

- [ ] **Step 3: 改 L23-24 删 admin 变量**

把 L23-24 整段:
```typescript
const user = cookieStore.get("rag_user_token")?.value;
const admin = cookieStore.get("rag_admin_token")?.value;
```

替换为:
```typescript
const user = cookieStore.get("rag_user_token")?.value;
```

- [ ] **Step 4: 改 L25-28 检查使用 admin 的地方 (若有 删)**

如果 L25-28 有 `admin` 变量使用,删了;保留 L28:
```typescript
out["x-user-token"] = tokenValue;
```

- [ ] **Step 5: 跑 lint + typecheck**

```bash
cd packages/web && bun run lint 2>&1 | tail -3
bun run typecheck 2>&1 | tail -3
```

Expected: 0 error / 0 warning (lint 仍可能因 test 红, 因为 test 还在 admin cookie case)

- [ ] **Step 6: Commit**

```bash
git add packages/web/lib/api/auth.server.ts
git commit -m "refactor(auth): 删 rag_admin_token cookie 死读取 (业务不识别 x-admin-token)"
```

---

## Task 2: 删 `[...path]/route.ts` 死 cookie 读取

**Files:**
- Modify: `packages/web/app/api/[...path]/route.ts:62`

- [ ] **Step 1: Read 现状**

读 `packages/web/app/api/[...path]/route.ts` 全文,确认:
- L62 行有 `const admin = jar.get("rag_admin_token")?.value;`
- L66 行有 `out["x-user-token"] = tokenValue;` (user 优先, 保留)

- [ ] **Step 2: 改 L62 删 admin cookie 读取**

把 L62:
```typescript
const admin = jar.get("rag_admin_token")?.value;
```

整行删了。保留 L66:
```typescript
out["x-user-token"] = tokenValue;
```

- [ ] **Step 3: 跑 lint**

```bash
cd packages/web && bun run lint 2>&1 | tail -3
```

Expected: 0 error / 0 warning

- [ ] **Step 4: Commit**

```bash
git add packages/web/app/api/\[...path\]/route.ts
git commit -m "refactor(bff): 删 rag_admin_token cookie 死读取"
```

---

## Task 3: 删 `memory-integration.ts` 死 cookie + 死 header 注入

**Files:**
- Modify: `packages/web/lib/chat/memory-integration.ts:49,53`

- [ ] **Step 1: Read 现状**

读 `packages/web/lib/chat/memory-integration.ts:40-60`,确认:
- L49 行有 `const adminToken = cookieJar.get("rag_admin_token")?.value;`
- L53 行有 `headers["x-admin-token"] = adminToken;` (后端不识别,死代码)

- [ ] **Step 2: 删 L49 admin cookie 读取**

把 L49 整行删了。L50 应该是:
```typescript
const userToken = cookieJar.get("rag_user_token")?.value;
```

- [ ] **Step 3: 删 L53 死 header 注入**

把 L53 整行 `headers["x-admin-token"] = adminToken;` 删了。L55 保留:
```typescript
headers["x-user-token"] = userToken;
```

- [ ] **Step 4: 跑 lint + typecheck**

```bash
cd packages/web && bun run lint 2>&1 | tail -3
bun run typecheck 2>&1 | tail -3
```

Expected: 0 error / 0 warning

- [ ] **Step 5: Commit**

```bash
git add packages/web/lib/chat/memory-integration.ts
git commit -m "refactor(chat): 删 x-admin-token 死 header 注入 (后端不识别)"
```

---

## Task 4: 改 E2E `04-evaluate.spec.ts` cookie 名

**Files:**
- Modify: `packages/web/e2e/04-evaluate.spec.ts:16`

- [ ] **Step 1: Read 现状**

读 `packages/web/e2e/04-evaluate.spec.ts:10-30`,确认:
- L16 行有 `globalThis.localStorage.setItem("rag_admin_token", tok);`
- 文件其它位置期望 header `x-user-token` (因为后端只认这个)

- [ ] **Step 2: 改 L16 改用 user token**

把 L16:
```typescript
globalThis.localStorage.setItem("rag_admin_token", tok);
```

替换为:
```typescript
globalThis.localStorage.setItem("rag_user_token", tok);
```

- [ ] **Step 3: 跑 lint**

```bash
cd packages/web && bun run lint 2>&1 | tail -3
```

Expected: 0 error / 0 warning

- [ ] **Step 4: Commit**

```bash
git add packages/web/e2e/04-evaluate.spec.ts
git commit -m "test(e2e): 04-evaluate 改用 user token (admin cookie 已死)"
```

---

## Task 5: 删 `auth.server.test.ts` admin cookie 死 case

**Files:**
- Modify: `packages/web/lib/api/auth.server.test.ts:54-58, 82`

- [ ] **Step 1: Read 现状**

读 `packages/web/lib/api/auth.server.test.ts:50-90`,确认:
- L54-58 有 "两 token 同存" case
- L82 有 "不会同时设 x-admin-token" case
- 保留 "只有 user token" + "都没时" 两个 case

- [ ] **Step 2: 删 L54-58 "两 token 同存" case**

把:
```typescript
it("两 token 同存: 返 x-user-token (user 优先, admin 不再单独注头)", async () => {
  expect(await authHeaders()).toEqual({ "x-user-token": "user-tok" });
});
```

整段删了。

- [ ] **Step 3: 删 L82 "不会同时设 x-admin-token" case**

把:
```typescript
it("不会同时设 x-admin-token 和 x-user-token (后端不会误判)", async () => {
  // ...
});
```

整段删了(具体代码 read 一下原文件,可能还有 1-2 行 setup, 跟着删)。

- [ ] **Step 4: 跑 vitest 验证**

```bash
cd packages/web && bun run test -- auth.server 2>&1 | tail -10
```

Expected: 全 pass (保留 case 数量 -2, 总数也 -2)

- [ ] **Step 5: Commit**

```bash
git add packages/web/lib/api/auth.server.test.ts
git commit -m "test(auth): 删 admin cookie 死 case (admin cookie 已不读)"
```

---

## Task 6: 补 `.env.example` 2 个 env 注释

**Files:**
- Modify: `packages/service/.env.example:13, 18`

- [ ] **Step 1: Read 现状**

读 `packages/service/.env.example:10-20`,确认:
- L13 是 `RAG_ADMIN_TOKEN=`
- L18 是 `RAG_DEV_AUTH=true`

- [ ] **Step 2: 改 L13 RAG_ADMIN_TOKEN 加注释**

把 L13 上方 (L11 或 L12) 加:
```bash
# (2026-06-24) bootstrap-only: 首次部署 DB 空时, 调 POST /api/account/seed-admin
# (header x-admin-token == RAG_ADMIN_TOKEN) 创首个 super_admin 账号.
# 创好 super_admin 后即可置空 env (置空后任何 seed-admin 请求 401).
# 跟业务主鉴权 x-user-token 完全独立, 仅作 bootstrap 一次性.
RAG_ADMIN_TOKEN=
```

- [ ] **Step 3: 改 L18 RAG_DEV_AUTH 加注释**

把 L18 上方加:
```bash
# (2026-06-24) dev-only: =true 时无 token 自动注入 super_admin(id=1) dev user.
# 等同于登录超级管理员, 0 真实账号. prod 必须 =false (默认).
# 测试基础设施: 15+ tests 依赖 RAG_DEV_AUTH=true 走真 resolve_user 链路.
RAG_DEV_AUTH=true
```

- [ ] **Step 4: 跑 ruff**

```bash
cd packages/service && uv run ruff check .env.example 2>&1 | tail -3
```

Expected: All checks passed

- [ ] **Step 5: Commit**

```bash
git add packages/service/.env.example
git commit -m "docs(env): 补 RAG_ADMIN_TOKEN (bootstrap-only) + RAG_DEV_AUTH (dev bypass) 注释"
```

---

## Task 7: 完整验证

**Files:** none (verification only)

- [ ] **Step 1: 前端全 pipeline**

```bash
cd packages/web && bun run format && bun run lint && bun run typecheck 2>&1 | tail -10
```

Expected: format 0 reformatted, lint 0 error / 0 warning, typecheck 0 error

- [ ] **Step 2: 前端全测**

```bash
cd packages/web && bun run test 2>&1 | tail -10
```

Expected: 全 pass (或 pre-existing 失败数不变)

- [ ] **Step 3: 后端全 pipeline**

```bash
cd packages/service && uv run ruff check src/ && uv run pyright src/ 2>&1 | tail -5
```

Expected: ruff 0 error, pyright 0 error

- [ ] **Step 4: 后端全测 (放过 pre-existing fail)**

```bash
cd packages/service && uv run pytest 2>&1 | tail -10
```

Expected: pre-existing 失败数不变 (跟 baseline 对比, 22 fail + 38 errors)

- [ ] **Step 5: 手动 e2e (optional)**

```bash
# 起前后端
cd packages/service && (uv run python main.py &)
cd packages/web && (bun run dev &)
sleep 20

# 登录 super_admin 拿 user token
# 调 /api/admin/* 验证 super_admin 角色够用
curl -H "x-user-token: <super_admin_user_token>" http://localhost:8000/api/admin/users
```

Expected: 200, 证明"只要 super_admin 角色"即可,不需要 admin token

---

## Task 8: 记 feedback memory + 更新 CLAUDE.md

**Files:**
- Create: `C:\Users\abcuc\.claude\projects\c--Users-abcuc-Desktop-rag\memory\feedback-rag-admin-token-bootstrap-only.md`
- Modify: `C:\Users\abcuc\.claude\projects\c--Users-abcuc-Desktop-rag\memory\MEMORY.md` (append)

- [ ] **Step 1: 写 memory 文件**

写 `feedback-rag-admin-token-bootstrap-only.md`:
```markdown
---
name: feedback-rag-admin-token-bootstrap-only
description: RAG_ADMIN_TOKEN / x-admin-token 是 bootstrap 一次性通道, 业务 100% 走 x-user-token, 前端 cookie rag_admin_token 永远 undefined 是死代码
metadata:
  type: feedback
---

`RAG_ADMIN_TOKEN` + `x-admin-token` header 是 **bootstrap-only**: 首次部署 DB 空时调 `POST /api/account/seed-admin` 创首个 super_admin 账号。**创好 super_admin 后即可置空 env** (置空后任何 seed-admin 请求 401)。**业务 100% 走 x-user-token (6h sliding)**, 跟 x-admin-token 完全独立。

前端 `rag_admin_token` cookie 是**死代码**: 业务不识别 x-admin-token (2026-06-24 Bug 4 修后), cookie 永远 undefined。`auth.server.ts:11` + `[...path]/route.ts:62` + `memory-integration.ts:49` 4 处读全部返回 undefined,删了 0 行为变化。

**Why**: 2026-06-24 token 统一化 spec 设计阶段确认: "现在只要超级管理员就够了" = 质疑 admin token 本身, 但锁定 含义 1 (admin token bootstrap 通道, 创好即弃) 而非 含义 2 (砍多用户)。RBAC 3 角色 (super_admin / operator / user) 保留, 主鉴权 x-user-token 不动。

**How to apply**:
1. **新加 admin 鉴权时**先问: "是不是 bootstrap? 是 → x-admin-token; 否 → 走 x-user-token + role 校验"
2. **前端读 cookie 时**只读 `rag_user_token`, 别读 `rag_admin_token`
3. **写测试时** admin 鉴权用 `RAG_ADMIN_TOKEN` env, 业务鉴权用 `x-user-token` header
4. **跟 [[feedback-no-shim-no-minimal-changes]] 一致**: 死代码不留, cookie 读 4 处删 4 处
5. **生产部署后**: `RAG_ADMIN_TOKEN` 可置空 (代码 os.getenv 读空字符串 → 401, 安全)
```

- [ ] **Step 2: append MEMORY.md 索引**

用 `Edit` 工具 + `replace_all: false` 在 MEMORY.md 末尾追加一行:
```
- [feedback-rag-admin-token-bootstrap-only](feedback-rag-admin-token-bootstrap-only.md) — RAG_ADMIN_TOKEN 是 bootstrap 一次性, 业务 100% 走 x-user-token, 前端 rag_admin_token cookie 死代码 (2026-06-24)
```

- [ ] **Step 3: 跑 lint 验证 memory 文件无 error**

```bash
ls "C:/Users/abcuc/.claude/projects/c--Users-abcuc-Desktop-rag/memory/feedback-rag-admin-token-bootstrap-only.md"
```

Expected: 文件存在

- [ ] **Step 4: Commit memory**

```bash
git add "C:/Users/abcuc/.claude/projects/c--Users-abcuc-Desktop-rag/memory/feedback-rag-admin-token-bootstrap-only.md" \
        "C:/Users/abcuc/.claude/projects/c--Users-abcuc-Desktop-rag/memory/MEMORY.md"
git commit -m "docs(memory): 记 RAG_ADMIN_TOKEN bootstrap-only + 死代码清理 feedback"
```

注意: memory 目录可能不在 git 里,跑前先 `git status` 看 memory 目录是否 tracked。

---

## Self-Review

**1. Spec coverage**:
- §2.1 docs 改 1 文件 (RAG_ADMIN_TOKEN + RAG_DEV_AUTH 注释) → Task 6 ✅
- §2.2 web 删 4 处死 cookie 读取 (auth.server.ts:11,23-24 + [...path]/route.ts:62 + memory-integration.ts:49) → Task 1, 2, 3 ✅
- §2.3 e2e 改 1 处 (04-evaluate.spec.ts:16) → Task 4 ✅
- §2.4 test 改 1 文件 (auth.server.test.ts:54-58,82) → Task 5 ✅
- §4 Token 架构终态 → 不动, 只 doc 补 ✅
- §5 验证 (lint/typecheck/format/test) → Task 7 ✅
- 未来 memory 记录 → Task 8 ✅

**2. Placeholder scan**: 0 个 TBD / TODO / "implement later"。

**3. Type consistency**:
- `authHeaders()` 函数签名 / 返回类型不变 (Task 1-3)
- `cookieJar.get("rag_user_token")?.value` 跟 `userToken` 变量名一致 (Task 3)
- E2E `localStorage.setItem("rag_user_token", tok)` 跟后端 cookie name 一致 (Task 4)
- Memory 文件名 slug `feedback-rag-admin-token-bootstrap-only` 跟现有 memory 命名风格一致 (Task 8)

**4. Bite-sized check**:
- 每个 Step 一个动作 (2-5 分钟)
- Code blocks 完整, 无 "类似" / "类似 Task N" 引用
- 文件路径 + 行号精确
- 命令 + 期望输出明确

**5. Pre-existing 行为保证**:
- 死代码本来返回 undefined, 删了 0 行为变化 ✅
- pre-existing backend test fail (22+38) 不在本 plan 范围, 跟 CLAUDE.md 一致
