# SWR → RSC + React Query 数据层重构 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `packages/web` 18 个 SWR 调用点从 "client fetch" 改成 "RSC 为主 + RQ 接管为辅", 提升首屏 LCP, 简化数据层。SWR 依赖彻底移除。

**Architecture:**
- **A 档 (13 处)**: server component 直接 fetch, prop 灌 client 子组件; 简单 mutation 走 server actions (`useActionState` + `<form action>`)
- **B 档 (4 处)**: RSC 入口 `prefetchQuery` + `<HydrationBoundary>`, client 端 `useQuery` 接管轮询/焦点 refetch
- **认证**: localStorage → httpOnly cookie, RSC 用 `cookies()` 读, BFF 透传 `x-user-token` header

**Tech Stack:** Next.js 16.2 App Router + React 19.2 + TypeScript, `@tanstack/react-query@^5.62`, zustand 5 (现状), vitest + jsdom, bun (不用 npm), tsgo/oxlint/oxfmt, Playwright E2E

**关联 Spec:** `docs/superpowers/specs/2026-06-12-swr-to-rsc-rq-design.md`

---

## 关键前置规则 (CLAUDE.md 摘录)

执行本计划前必须遵守:
- **包管理**: 用 `bun` 不用 `npm` / `pnpm` / `yarn`; 装包后 `bun.lock` 自动入库
- **Python 依赖**: 用 `uv` 不用 `pip`
- **TDD**: 单测同目录 `.test.ts` / `.test.tsx`; 单元测试用 `bun run test` (= `vitest run`); **不要**用 `bun test` (那是 bun 自带 runner, 不读 vitest.config)
- **commit 前**: husky 自动跑 lint-staged + tsgo + vitest + format:check
- **BFF route 删除前**: 必跑 `pytest tests/test_api_contract.py` (CLAUDE.md 强制, 红了不能删)
- **代码注释 / log**: 中文
- **emoji**: 禁止, 用 Lucide React 图标
- **React 单文件**: ≤300 行

---

## 文件结构总览

### 新增 (12)
```
packages/web/lib/api/queryKeys.ts                     # queryKey 中心化
packages/web/lib/api/queryKeys.test.ts                # queryKey 参数化测试
packages/web/lib/api/rsc-queries.ts                   # server-only RQ 单例 + prefetch
packages/web/lib/api/rsc-queries.test.ts              # server fetch + cookies 透传测试
packages/web/lib/store/app-data.tsx                   # datasets/schemas 列表 Context
packages/web/app/[locale]/_actions/knowledge.ts       # createQA/createTriples/commitDocuments
packages/web/app/[locale]/_actions/evaluate.ts        # createRun/deleteRun
packages/web/app/[locale]/_actions/output.ts          # cancelTask
packages/web/app/[locale]/_actions/knowledge.test.ts  # server actions 测试
packages/web/app/[locale]/_actions/evaluate.test.ts
packages/web/app/[locale]/_actions/output.test.ts
packages/web/app/[locale]/output/layout.tsx           # B 档专属 QueryClientProvider
```

### 改写 (~47)
- **(A) lib/api 工具层 (4)**: `auth.ts` (去 localStorage), `knowledge.ts`/`evaluate.ts`/`ingest.ts` (删 URL 工厂注释)
- **(B) page + 组件实现 (24)**: 13 A 档 page → RSC, 3 B 档 page → RSC + Hydration, HealthDot/Switchers 改写, 4 BFF route 改读 cookie
- **(C) 测试 (19)**: 13 A 档 + 3 B 档 + 3 组件测试

### 删除 (4, P4 阶段)
```
packages/web/lib/api/swr.ts                  # 整体删
packages/web/lib/api/swr-provider.tsx        # 整体删
packages/web/app/[locale]/providers.tsx      # 拆掉 SWRProvider 引用 (如有)
packages/web/app/api/knowledge/qa/route.ts   # P2 后变空壳, P4 评估删 (必跑契约测试)
```

### 后端改动
```
packages/service/src/rag/auth/router.py     # /api/auth/anon Set-Cookie
packages/service/src/rag/auth/migrate.py    # /api/auth/migrate 旧 token 换 cookie
packages/service/src/rag/main.py             # CORS allow_credentials + Allow-Origin 显式
packages/service/tests/test_auth_cookie.py  # cookie 设置测试
packages/service/tests/test_cors_credentials.py # CORS credentials 测试
```

---

## 阶段总览 (5 阶段, P0-P4)

| 阶段 | 内容 | Task 范围 |
|---|---|---|
| **P0 基础设施** | 后端 cookie + CORS; 前端 auth 改写; BFF 改 cookie; 装 RQ; queryKeys/rsc-queries/app-data | Task 1-9 |
| **P1 A 档试点** | `datasets/page` 全栈改造 + createQA server action | Task 10-13 |
| **P2 A 档批量** | 剩 12 个 A 档 page 改造 | Task 14-22 |
| **P3 B 档 4 页** | output / output[id] / health / HealthDot | Task 23-27 |
| **P4 清理** | 删 swr.ts + swr-provider.tsx; package.json 删 swr; qa/route 评估删 | Task 28-30 |

每阶段可独立回滚 (git revert 该阶段 commit)。

---

## P0 基础设施 (Task 1-9)

### Task 1: 后端 `/api/auth/anon` 改 Set-Cookie

**Files:**
- Modify: `packages/service/src/rag/auth/router.py` (或现有 anon 端点文件, 路径按实际)
- Test: `packages/service/tests/test_auth_cookie.py` (新建)

**Context:** 现有 `/api/auth/anon` POST 返回 `{ token }` 让前端存 localStorage. 改造后改为同时 `Set-Cookie: rag_user_token=...; HttpOnly; SameSite=Lax; Path=/` 设置 cookie, **保留** body 返 token (灰度期兼容).

- [ ] **Step 1: 写失败测试**

`packages/service/tests/test_auth_cookie.py`:
```python
"""验证 /api/auth/anon 响应设置 HttpOnly cookie."""
from fastapi.testclient import TestClient
from src.rag.main import app  # 按实际 import 路径

client = TestClient(app)


def test_anon_sets_http_only_cookie():
    """POST /api/auth/anon 必须 Set-Cookie HttpOnly."""
    res = client.post("/api/auth/anon")
    assert res.status_code == 200
    set_cookie = res.headers.get("set-cookie", "")
    assert "rag_user_token=" in set_cookie
    assert "HttpOnly" in set_cookie
    assert "SameSite=Lax" in set_cookie
    assert "Path=/" in set_cookie


def test_anon_response_body_still_returns_token_for_legacy():
    """灰度期 body 仍返 token, 后续 P4 删除."""
    res = client.post("/api/auth/anon")
    body = res.json()
    assert "token" in body
    assert isinstance(body["token"], str)
    assert len(body["token"]) > 0
```

- [ ] **Step 2: 跑测试, 确认红**

```bash
cd packages/service && uv run pytest tests/test_auth_cookie.py -v
```

预期: FAIL (当前端点不 Set-Cookie)

- [ ] **Step 3: 改造 anon 端点**

修改 `packages/service/src/rag/auth/router.py` (或对应文件, 找现有 anon handler):
```python
from fastapi import Response

@router.post("/api/auth/anon")
async def auth_anon(response: Response) -> dict:
    """生成匿名 token, 同时设置 HttpOnly cookie (灰度期保留 body)."""
    token = _generate_anon_token()  # 现有逻辑
    response.set_cookie(
        key="rag_user_token",
        value=token,
        httponly=True,
        samesite="lax",
        path="/",
        max_age=60 * 60 * 24 * 7,  # 7 天
        secure=False,  # dev 用 http://localhost:8000 不加 secure
    )
    return {"token": token}  # 灰度期保留
```

> 注: `secure` 走环境变量; prod 由 `ENV=production` 时设 `secure=True`.

- [ ] **Step 4: 跑测试, 确认绿**

```bash
cd packages/service && uv run pytest tests/test_auth_cookie.py -v
```

预期: PASS (2 个测试都过)

- [ ] **Step 5: 跑契约测试确认后端其他接口仍正常**

```bash
cd packages/service && uv run pytest tests/test_api_contract.py -v
```

预期: PASS (其他端点没被破坏)

- [ ] **Step 6: Commit**

```bash
cd c:/doc/Code/worktrees/rag-refactor
git add packages/service/src/rag/auth/router.py packages/service/tests/test_auth_cookie.py
git commit -m "feat(auth): /api/auth/anon 改 Set-Cookie (HttpOnly+SameSite=Lax)"
```

---

### Task 2: 后端加 `/api/auth/migrate` 端点 (旧 localStorage token 换 cookie)

**Files:**
- Modify: `packages/service/src/rag/auth/router.py`
- Test: `packages/service/tests/test_auth_migrate.py` (新建)

**Context:** 灰度期, 老用户 localStorage 里有 `rag_user_token` 但没 cookie. 首次访问前端 POST 这个端点, 后端验证旧 token 有效后 Set-Cookie.

- [ ] **Step 1: 写失败测试**

`packages/service/tests/test_auth_migrate.py`:
```python
"""验证 /api/auth/migrate 接收旧 token, 验证有效后 Set-Cookie."""
from fastapi.testclient import TestClient
from src.rag.main import app

client = TestClient(app)


def test_migrate_with_valid_token_sets_cookie():
    """带有效旧 token 调 migrate, 必须 Set-Cookie."""
    # 假设 0a7903f 之前的 anon 端点会生成有效 token
    anon_res = client.post("/api/auth/anon")
    legacy_token = anon_res.json()["token"]

    res = client.post(
        "/api/auth/migrate",
        json={"token": legacy_token},
    )
    assert res.status_code == 200
    set_cookie = res.headers.get("set-cookie", "")
    assert "rag_user_token=" in set_cookie
    assert "HttpOnly" in set_cookie


def test_migrate_with_invalid_token_returns_400():
    """无效 token 必须返 400, 不能 Set-Cookie."""
    res = client.post(
        "/api/auth/migrate",
        json={"token": "obviously-not-a-real-token"},
    )
    assert res.status_code == 400
    assert "set-cookie" not in {k.lower() for k in res.headers.keys()}
```

- [ ] **Step 2: 跑测试, 确认红**

```bash
cd packages/service && uv run pytest tests/test_auth_migrate.py -v
```

预期: FAIL (端点不存在, 404)

- [ ] **Step 3: 实现 migrate 端点**

在 `packages/service/src/rag/auth/router.py` 加:
```python
@router.post("/api/auth/migrate")
async def auth_migrate(payload: dict, response: Response) -> dict:
    """把旧 token (客户端 localStorage) 换成 Set-Cookie.

    Args:
        payload: {"token": "old_jwt_or_legacy_token"}

    Returns:
        {"ok": true} on success
    """
    legacy_token = payload.get("token", "")
    if not legacy_token:
        raise HTTPException(status_code=400, detail="token required")

    # 验证旧 token 有效 (复用 _validate_token 或 _generate_anon_token 的反向逻辑)
    if not _validate_legacy_token(legacy_token):
        raise HTTPException(status_code=400, detail="invalid token")

    response.set_cookie(
        key="rag_user_token",
        value=legacy_token,
        httponly=True,
        samesite="lax",
        path="/",
        max_age=60 * 60 * 24 * 7,
        secure=False,
    )
    return {"ok": True}


def _validate_legacy_token(token: str) -> bool:
    """验证 anon 端点生成的 token 仍有效. 复用 _generate_anon_token 的密钥 + 过期校验."""
    # 按实际 token 验证逻辑实现, 通常是 JWT 解码
    # 兜底: 空 / None / 长度 < 10 视为无效
    if not token or len(token) < 10:
        return False
    try:
        # 复用现有 token 验证 (按项目实际)
        return _verify_jwt(token)  # 按实际函数名
    except Exception:
        return False
```

> 实际函数名 `_verify_jwt` / `_validate_legacy_token` 按项目现有代码替换.

- [ ] **Step 4: 跑测试, 确认绿**

```bash
cd packages/service && uv run pytest tests/test_auth_migrate.py -v
```

预期: PASS

- [ ] **Step 5: 跑全量测试**

```bash
cd packages/service && uv run pytest -v
```

预期: PASS (无回归)

- [ ] **Step 6: Commit**

```bash
cd c:/doc/Code/worktrees/rag-refactor
git add packages/service/src/rag/auth/router.py packages/service/tests/test_auth_migrate.py
git commit -m "feat(auth): 加 /api/auth/migrate 端点换 cookie"
```

---

### Task 3: 后端 CORS allow_credentials + 显式 Allow-Origin

**Files:**
- Modify: `packages/service/src/rag/main.py` (CORS 配置)
- Test: `packages/service/tests/test_cors_credentials.py` (新建)

**Context:** 浏览器发跨域 fetch 时如果带 `credentials: "include"`, 后端 CORS 必须 `Access-Control-Allow-Credentials: true` + `Access-Control-Allow-Origin: 显式 origin (不能用 *)`.

- [ ] **Step 1: 写失败测试**

`packages/service/tests/test_cors_credentials.py`:
```python
"""验证 CORS 配置支持 credentials + 显式 origin."""
from fastapi.testclient import TestClient
from src.rag.main import app

client = TestClient(app)


def test_cors_allows_credentials_with_explicit_origin():
    """跨域带 credentials 时, 后端必须返 Allow-Credentials + 显式 Allow-Origin."""
    res = client.get(
        "/api/kg/health",
        headers={"Origin": "http://localhost:3000"},
    )
    allow_origin = res.headers.get("access-control-allow-origin", "")
    allow_creds = res.headers.get("access-control-allow-credentials", "")
    assert allow_origin == "http://localhost:3000", f"got {allow_origin!r}"
    assert allow_creds == "true", f"got {allow_creds!r}"


def test_cors_preflight_with_credentials():
    """OPTIONS 预检请求必须同时支持 credentials."""
    res = client.options(
        "/api/kg/health",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    allow_origin = res.headers.get("access-control-allow-origin", "")
    allow_creds = res.headers.get("access-control-allow-credentials", "")
    assert allow_origin == "http://localhost:3000"
    assert allow_creds == "true"
```

- [ ] **Step 2: 跑测试, 确认红**

```bash
cd packages/service && uv run pytest tests/test_cors_credentials.py -v
```

预期: FAIL (当前 CORS 没 allow_credentials)

- [ ] **Step 3: 改造 CORS 配置**

修改 `packages/service/src/rag/main.py` 找到 `CORSMiddleware` 配置:
```python
from fastapi.middleware.cors import CORSMiddleware
import os

# 显式 origin 列表, 不支持 *
ALLOWED_ORIGINS = os.environ.get(
    "CORS_ALLOWED_ORIGINS",
    "http://localhost:3000,http://127.0.0.1:3000",
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,    # 显式列表, 不用 *
    allow_credentials=True,            # 关键: 允许 cookie 跨域
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["content-type"],
    max_age=600,
)
```

> 如果项目用环境变量 `FRONTEND_ORIGIN` 而非 `CORS_ALLOWED_ORIGINS`, 按实际替换.

- [ ] **Step 4: 跑测试, 确认绿**

```bash
cd packages/service && uv run pytest tests/test_cors_credentials.py -v
```

预期: PASS

- [ ] **Step 5: 跑全量测试**

```bash
cd packages/service && uv run pytest -v
```

预期: PASS

- [ ] **Step 6: Commit**

```bash
cd c:/doc/Code/worktrees/rag-refactor
git add packages/service/src/rag/main.py packages/service/tests/test_cors_credentials.py
git commit -m "feat(cors): allow_credentials=true + 显式 Allow-Origin 列表"
```

---

### Task 4: 装 `@tanstack/react-query`

**Files:**
- Modify: `packages/web/package.json`
- Run: `bun install`

- [ ] **Step 1: 装包**

```bash
cd packages/web
bun add @tanstack/react-query@^5.62.0
bun add -d @tanstack/react-query-devtools@^5.62.0
```

预期: `bun.lock` 自动更新, 写入 `node_modules`.

- [ ] **Step 2: 验证 package.json**

```bash
cd packages/web && cat package.json | grep -A2 -E "react-query|swr"
```

预期看到:
```json
    "@tanstack/react-query": "^5.62.0",
    "@tanstack/react-query-devtools": "^5.62.0"
```
且**没有** `"swr"` 行 (SWR 还在, P4 才删).

- [ ] **Step 3: 验证安装**

```bash
cd packages/web && bun run -e "import { QueryClient } from '@tanstack/react-query'; console.log(QueryClient.name);"
```

预期: 输出 `QueryClient` (不报错)

- [ ] **Step 4: Commit**

```bash
cd c:/doc/Code/worktrees/rag-refactor
git add packages/web/package.json packages/web/bun.lock
git commit -m "chore(deps): 装 @tanstack/react-query@5.62 + devtools"
```

---

### Task 5: 新增 `lib/api/queryKeys.ts` + 参数化测试

**Files:**
- Create: `packages/web/lib/api/queryKeys.ts`
- Create: `packages/web/lib/api/queryKeys.test.ts`

**Context:** 所有 queryKey 中心化生成, RSC 预取 + RQ 客户端用同一 key, 避免双套缓存漂移.

- [ ] **Step 1: 写失败测试**

`packages/web/lib/api/queryKeys.test.ts`:
```ts
import { describe, it, expect } from "vitest";
import { qKeys } from "./queryKeys";

describe("qKeys", () => {
  it("root all 不变", () => {
    expect(qKeys.all).toEqual(["rag"]);
  });

  it("health.system 嵌套一致", () => {
    expect(qKeys.health.system()).toEqual(["rag", "health", "system"]);
  });

  it("output.list 和 output.detail 参数化正确", () => {
    expect(qKeys.output.list()).toEqual(["rag", "output", "list"]);
    expect(qKeys.output.detail("abc-123")).toEqual(["rag", "output", "detail", "abc-123"]);
  });

  it("batch.status 接收 taskId", () => {
    expect(qKeys.batch.status("task-1")).toEqual(["rag", "batch", "status", "task-1"]);
  });

  it("每次调用 list() 返新数组但内容相等 (避免误共享引用)", () => {
    const a = qKeys.output.list();
    const b = qKeys.output.list();
    expect(a).not.toBe(b);   // 不同引用
    expect(a).toEqual(b);    // 同内容
  });
});
```

- [ ] **Step 2: 跑测试, 确认红**

```bash
cd packages/web && bun run test lib/api/queryKeys.test.ts
```

预期: FAIL (queryKeys.ts 不存在)

- [ ] **Step 3: 实现 queryKeys.ts**

`packages/web/lib/api/queryKeys.ts`:
```ts
// 集中定义所有 queryKey, RSC 预取和 RQ 客户端必须用同一 key.
// 每次调用 factory 函数返回**新数组** (避免误共享引用, RQ 内部 hash 相同不影响).

export const qKeys = {
  all: ["rag"] as const,
  health: {
    all: ["rag", "health"] as const,
    system: () => [...qKeys.health.all, "system"] as const,
  },
  output: {
    all: ["rag", "output"] as const,
    list: () => [...qKeys.output.all, "list"] as const,
    detail: (id: string) => [...qKeys.output.all, "detail", id] as const,
  },
  batch: {
    all: ["rag", "batch"] as const,
    status: (id: string) => [...qKeys.batch.all, "status", id] as const,
  },
} as const;
```

- [ ] **Step 4: 跑测试, 确认绿**

```bash
cd packages/web && bun run test lib/api/queryKeys.test.ts
```

预期: PASS (5 个测试全过)

- [ ] **Step 5: Commit**

```bash
cd c:/doc/Code/worktrees/rag-refactor
git add packages/web/lib/api/queryKeys.ts packages/web/lib/api/queryKeys.test.ts
git commit -m "feat(api): 新增 queryKeys.ts 中心化 (RSC+RQ 共享)"
```

---

### Task 6: 新增 `lib/api/rsc-queries.ts` (server-only) + 测试

**Files:**
- Create: `packages/web/lib/api/rsc-queries.ts`
- Create: `packages/web/lib/api/rsc-queries.test.ts`

**Context:** server-only RQ 单例 + 预取工具, 供 RSC page 入口调用. `getServerToken` 走 cookie 读 token.

- [ ] **Step 1: 写失败测试**

`packages/web/lib/api/rsc-queries.test.ts`:
```ts
import { describe, it, expect, vi, beforeEach } from "vitest";
import { getRscQueryClient, prefetchQuery } from "./rsc-queries";

// mock next/headers
vi.mock("next/headers", () => ({
  cookies: vi.fn(async () => ({
    get: (key: string) => {
      if (key === "rag_user_token") return { value: "test-token-123" };
      return undefined;
    },
  })),
}));

describe("rsc-queries", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    // @ts-expect-error 全局 fetch mock
    global.fetch = vi.fn(async (url: string, init?: RequestInit) => {
      return new Response(JSON.stringify({ ok: true, url }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    });
  });

  it("getRscQueryClient 返新单例 per call", async () => {
    const a = await getRscQueryClient();
    const b = await getRscQueryClient();
    expect(a).toBe(b);  // cache 包过, 同 request 内同实例
  });

  it("prefetchQuery 透传 cookie token 到 fetch header", async () => {
    const qc = await getRscQueryClient();
    const fetchSpy = vi.mocked(global.fetch);

    await prefetchQuery(qc, ["test", "key"], "http://api.example.com/data");

    expect(fetchSpy).toHaveBeenCalledTimes(1);
    const [, init] = fetchSpy.mock.calls[0];
    expect(init?.headers).toEqual({ "x-user-token": "test-token-123" });
  });

  it("cookie 缺失时不带 x-user-token header (但不抛)", async () => {
    const { cookies } = await import("next/headers");
    vi.mocked(cookies).mockResolvedValueOnce({
      get: () => undefined,
    } as never);
    const qc = await getRscQueryClient();
    const fetchSpy = vi.mocked(global.fetch);

    await prefetchQuery(qc, ["test"], "http://api.example.com/x");

    const [, init] = fetchSpy.mock.calls[0];
    expect(init?.headers).toEqual({});
  });

  it("prefetchQuery 失败时抛错 (让 Next error.tsx 兜住)", async () => {
    // @ts-expect-error
    global.fetch = vi.fn(async () => new Response("bad", { status: 500 }));
    const qc = await getRscQueryClient();
    await expect(
      prefetchQuery(qc, ["test"], "http://api.example.com/x"),
    ).rejects.toThrow("HTTP 500");
  });
});
```

- [ ] **Step 2: 跑测试, 确认红**

```bash
cd packages/web && bun run test lib/api/rsc-queries.test.ts
```

预期: FAIL (rsc-queries.ts 不存在)

- [ ] **Step 3: 实现 rsc-queries.ts**

`packages/web/lib/api/rsc-queries.ts`:
```ts
// server-only RQ 工具: 单例 cache + 预取. 仅 server component 用.
import "server-only";
import { cache } from "react";
import { QueryClient } from "@tanstack/react-query";
import { cookies } from "next/headers";

/** Per-request 单例 QueryClient. cache() 保证同 request 内同实例. */
export const getRscQueryClient = cache(async (): Promise<QueryClient> => {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: Infinity,  // RSC 预取视为新鲜, client 不会立即重拉
        gcTime: 0,            // SSR 端不缓存, 避免污染下个 request
        retry: false,
      },
    },
  });
});

/** 从 cookie 读 user/admin token, 优先 admin. */
async function getServerToken(): Promise<string> {
  const c = await cookies();
  return (
    c.get("rag_admin_token")?.value ??
    c.get("rag_user_token")?.value ??
    ""
  );
}

/** 通用 server-side prefetch: 调 fetch(url) 带 cookie token, 写入 qc cache. */
export async function prefetchQuery<T>(
  qc: QueryClient,
  queryKey: readonly unknown[],
  url: string,
): Promise<void> {
  await qc.prefetchQuery({
    queryKey,
    queryFn: async () => {
      const token = await getServerToken();
      const res = await fetch(url, {
        headers: token ? { "x-user-token": token } : {},
        cache: "no-store",  // 不污染 Next.js data cache
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return res.json() as Promise<T>;
    },
  });
}
```

- [ ] **Step 4: 跑测试, 确认绿**

```bash
cd packages/web && bun run test lib/api/rsc-queries.test.ts
```

预期: PASS (4 个测试全过)

- [ ] **Step 5: Commit**

```bash
cd c:/doc/Code/worktrees/rag-refactor
git add packages/web/lib/api/rsc-queries.ts packages/web/lib/api/rsc-queries.test.ts
git commit -m "feat(api): server-only rsc-queries.ts (per-request QC + prefetch)"
```

---

### Task 7: 新增 `lib/store/app-data.tsx` (datasets/schemas Context)

**Files:**
- Create: `packages/web/lib/store/app-data.tsx`

**Context:** datasets / schemas 列表由 root layout RSC 灌给 client 端, Switcher 读 Context. **不进 zustand** (跨请求新鲜).

- [ ] **Step 1: 写测试 (RSC 端 -> root layout 由 P2 阶段引用, 这里先单独测 provider)**

`packages/web/lib/store/app-data.test.tsx`:
```tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { AppDataProvider, useAppData } from "./app-data";

function Probe() {
  const { datasets, schemas } = useAppData();
  return (
    <div>
      <span data-testid="ds-count">{datasets.length}</span>
      <span data-testid="schema-count">{schemas.length}</span>
    </div>
  );
}

describe("AppDataProvider", () => {
  it("提供 datasets + schemas 给子组件", () => {
    render(
      <AppDataProvider
        datasets={[{ id: "1", name: "DS1" }]}
        schemas={[{ name: "motor" }]}
      >
        <Probe />
      </AppDataProvider>,
    );
    expect(screen.getByTestId("ds-count")).toHaveTextContent("1");
    expect(screen.getByTestId("schema-count")).toHaveTextContent("1");
  });

  it("不在 Provider 内调 useAppData 抛错", () => {
    // 抑制 React 错误边界日志
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});
    expect(() => render(<Probe />)).toThrow(/useAppData must be used/);
    spy.mockRestore();
  });
});
```

> 顶部需 `import { vi } from "vitest"`.

- [ ] **Step 2: 跑测试, 确认红**

```bash
cd packages/web && bun run test lib/store/app-data.test.tsx
```

预期: FAIL (文件不存在)

- [ ] **Step 3: 实现 app-data.tsx**

`packages/web/lib/store/app-data.tsx`:
```tsx
"use client";
// RSC 灌 + 客户端读: datasets / schemas 列表.
// zustand 仍管 datasetId/domain (用户选择), 但列表数据本身不进 zustand (跨请求新鲜).
import { createContext, useContext, type ReactNode } from "react";

export interface DatasetRow {
  id: string;
  name: string;
  description?: string;
  document_count?: number;
  word_count?: number;
}

export interface AppData {
  datasets: DatasetRow[];
  schemas: { name: string }[];
}

const Ctx = createContext<AppData | null>(null);

export function AppDataProvider({
  datasets,
  schemas,
  children,
}: AppData & { children: ReactNode }) {
  return <Ctx.Provider value={{ datasets, schemas }}>{children}</Ctx.Provider>;
}

export function useAppData(): AppData {
  const v = useContext(Ctx);
  if (!v) {
    throw new Error("useAppData must be used inside <AppDataProvider>");
  }
  return v;
}
```

- [ ] **Step 4: 跑测试, 确认绿**

```bash
cd packages/web && bun run test lib/store/app-data.test.tsx
```

预期: PASS

- [ ] **Step 5: Commit**

```bash
cd c:/doc/Code/worktrees/rag-refactor
git add packages/web/lib/store/app-data.tsx packages/web/lib/store/app-data.test.tsx
git commit -m "feat(store): AppDataProvider (RSC 灌 datasets/schemas Context)"
```

---

### Task 8: 改写 `lib/api/auth.ts` (去 localStorage, 加 server util)

**Files:**
- Modify: `packages/web/lib/api/auth.ts`
- Create: `packages/web/lib/api/auth.test.ts`

**Context:** 现有 auth.ts 全部基于 localStorage; 改造为: server 端 `getServerToken()` 读 cookie; client 端 `clientFetch()` 自动 `credentials: "include"`; 删除 `getUserToken`/`getAdminToken`/`ensureAuthToken` 的 localStorage 写入.

- [ ] **Step 1: 写失败测试**

`packages/web/lib/api/auth.test.ts`:
```ts
import { describe, it, expect, vi, beforeEach } from "vitest";

// mock next/headers
vi.mock("next/headers", () => ({
  cookies: vi.fn(async () => ({
    get: (key: string) => {
      const m: Record<string, { value: string }> = {
        rag_user_token: { value: "user-tok" },
        rag_admin_token: { value: "admin-tok" },
      };
      return m[key];
    },
  })),
}));

import { getServerToken, clientFetch, API_BASE } from "./auth";

describe("getServerToken", () => {
  it("admin token 优先", async () => {
    expect(await getServerToken()).toBe("admin-tok");
  });

  it("无 admin 时回退 user token", async () => {
    const { cookies } = await import("next/headers");
    vi.mocked(cookies).mockResolvedValueOnce({
      get: (key: string) =>
        key === "rag_user_token" ? { value: "user-only" } : undefined,
    } as never);
    expect(await getServerToken()).toBe("user-only");
  });

  it("都没时返空字符串", async () => {
    const { cookies } = await import("next/headers");
    vi.mocked(cookies).mockResolvedValueOnce({
      get: () => undefined,
    } as never);
    expect(await getServerToken()).toBe("");
  });
});

describe("clientFetch", () => {
  beforeEach(() => {
    // @ts-expect-error
    global.fetch = vi.fn(async () => new Response("{}", { status: 200 }));
  });

  it("自动加 credentials: include", async () => {
    await clientFetch("http://x.example/y");
    const [, init] = vi.mocked(global.fetch).mock.calls[0];
    expect(init?.credentials).toBe("include");
  });

  it("JSON body 自动加 Content-Type", async () => {
    await clientFetch("http://x.example/y", {
      method: "POST",
      body: { foo: "bar" },
    });
    const [, init] = vi.mocked(global.fetch).mock.calls[0];
    expect(init?.headers).toMatchObject({ "Content-Type": "application/json" });
  });

  it("FormData body 不加 Content-Type (boundary 由浏览器填)", async () => {
    const fd = new FormData();
    fd.append("file", new File(["x"], "x.txt"));
    await clientFetch("http://x.example/y", { method: "POST", body: fd });
    const [, init] = vi.mocked(global.fetch).mock.calls[0];
    const headers = init?.headers as Record<string, string>;
    expect(headers["Content-Type"]).toBeUndefined();
  });
});
```

- [ ] **Step 2: 跑测试, 确认红**

```bash
cd packages/web && bun run test lib/api/auth.test.ts
```

预期: FAIL (旧 auth.ts 不导出 getServerToken / clientFetch)

- [ ] **Step 3: 改写 auth.ts (完全替换内容)**

`packages/web/lib/api/auth.ts`:
```ts
// 浏览器/服务端统一鉴权工具.
// 服务端: getServerToken() 从 cookie 读 token.
// 客户端: clientFetch() 自动 credentials: "include" 让浏览器带 same-origin cookie.
import { cookies } from "next/headers";

/** API base URL. */
export const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

/** Server 端: 从 cookie 读 user/admin token (admin 优先). */
export async function getServerToken(): Promise<string> {
  const c = await cookies();
  return (
    c.get("rag_admin_token")?.value ??
    c.get("rag_user_token")?.value ??
    ""
  );
}

/** Client 端: 跨域 fetch 自动 credentials: include. JSON body 自动 Content-Type. */
export function clientFetch(
  url: string,
  init: RequestInit = {},
): Promise<Response> {
  const headers: Record<string, string> = {
    ...(init.headers as Record<string, string> | undefined),
  };
  if (
    init.body &&
    !(init.body instanceof FormData) &&
    !headers["Content-Type"]
  ) {
    headers["Content-Type"] = "application/json";
  }
  return fetch(url, {
    ...init,
    credentials: "include",
    headers,
  });
}

/** 灰度期兼容: 旧 localStorage token 换 cookie. */
export async function migrateLegacyToken(legacyToken: string): Promise<boolean> {
  try {
    const res = await fetch(`${API_BASE}/api/auth/migrate`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ token: legacyToken }),
    });
    return res.ok;
  } catch {
    return false;
  }
}

/** 首次访问时若 localStorage 有旧 token, 尝试换 cookie. 客户端调用, 一次性. */
let _migrated = false;
export async function tryMigrateFromLocalStorage(): Promise<void> {
  if (typeof window === "undefined") return;
  if (_migrated) return;
  _migrated = true;
  const legacy = window.localStorage.getItem("rag_user_token");
  if (!legacy) return;
  const ok = await migrateLegacyToken(legacy);
  if (ok) {
    window.localStorage.removeItem("rag_user_token");
  }
}
```

- [ ] **Step 4: 跑测试, 确认绿**

```bash
cd packages/web && bun run test lib/api/auth.test.ts
```

预期: PASS (7 个测试全过)

- [ ] **Step 5: typecheck**

```bash
cd packages/web && bun run typecheck
```

预期: 0 错 (旧 fetcher.ts 可能引用了被删的 getUserToken, 编译会暴露)

- [ ] **Step 6: Commit**

```bash
cd c:/doc/Code/worktrees/rag-refactor
git add packages/web/lib/api/auth.ts packages/web/lib/api/auth.test.ts
git commit -m "refactor(auth): 去 localStorage, 加 getServerToken + clientFetch + migrate"
```

---

### Task 9: 4 个 BFF route 改读 cookie (透传 x-user-token)

**Files:**
- Modify: `packages/web/app/api/knowledge/qa/route.ts`
- Modify: `packages/web/app/api/knowledge/documents/upload/route.ts`
- Modify: `packages/web/app/api/knowledge/batch/route.ts`
- Modify: `packages/web/app/api/ingest/upload/route.ts`

**Context:** 所有 BFF route handler 调 FastAPI 时必须显式带 `x-user-token` header (server-to-server 不传 cookie).

- [ ] **Step 1: 改 qa/route.ts**

读 [packages/web/app/api/knowledge/qa/route.ts](packages/web/app/api/knowledge/qa/route.ts) 当前实现, 把**所有** `headers: authHeaders()` 或类似调用替换为:
```ts
import { cookies } from "next/headers";

const token = (await cookies()).get("rag_user_token")?.value
  ?? (await cookies()).get("rag_admin_token")?.value
  ?? "";

headers: token ? { "x-user-token": token } : {},
```

> 注: Next 16 的 `cookies()` 是 async, 必须 `await`. 如果项目有 helper, 复用 `getServerToken()` from [lib/api/auth.ts](packages/web/lib/api/auth.ts).

**示例完整改写** (假设 qa/route.ts 当前长这样):
```ts
// 旧:
import { authHeaders } from "@/lib/api/auth";

export async function GET(request: Request) {
  const res = await fetch(`${API_BASE}/api/knowledge/qa?${...}`, {
    headers: authHeaders(),
  });
  // ...
}

// 新:
import { getServerToken } from "@/lib/api/auth";

export async function GET(request: Request) {
  const token = await getServerToken();
  const res = await fetch(`${API_BASE}/api/knowledge/qa?${...}`, {
    headers: token ? { "x-user-token": token } : {},
  });
  // ...
}
```

- [ ] **Step 2: 同样改 documents/upload/route.ts**

读 [packages/web/app/api/knowledge/documents/upload/route.ts](packages/web/app/api/knowledge/documents/upload/route.ts) 当前实现, 替换 `authHeaders()` 为 `getServerToken()` 模式.

- [ ] **Step 3: 同样改 batch/route.ts**

读 [packages/web/app/api/knowledge/batch/route.ts](packages/web/app/api/knowledge/batch/route.ts) 当前实现, 替换同上.

- [ ] **Step 4: 同样改 ingest/upload/route.ts**

读 [packages/web/app/api/ingest/upload/route.ts](packages/web/app/api/ingest/upload/route.ts), 替换同上.

- [ ] **Step 5: grep 确认没漏**

```bash
cd packages/web && grep -rn "authHeaders" app/api/ 2>&1
```

预期: 0 命中 (所有 BFF 都改完)

- [ ] **Step 6: typecheck**

```bash
cd packages/web && bun run typecheck
```

预期: 0 错

- [ ] **Step 7: 跑契约测试 (CLAUDE.md 强制)**

```bash
cd packages/service && uv run pytest tests/test_api_contract.py -v
```

预期: PASS (后端契约未被破坏)

- [ ] **Step 8: Commit**

```bash
cd c:/doc/Code/worktrees/rag-refactor
git add packages/web/app/api/knowledge/qa/route.ts packages/web/app/api/knowledge/documents/upload/route.ts packages/web/app/api/knowledge/batch/route.ts packages/web/app/api/ingest/upload/route.ts
git commit -m "refactor(bff): 4 个 BFF route 改读 cookie + 透传 x-user-token"
```

---

## P1 A 档试点 (Task 10-13)

> 试点: 改 `knowledge/datasets/page` 一个 page, 验证完整链路 (RSC 预取 + cookie 鉴权 + client 表格分页 + 删 SWR + 测试跟着改).

### Task 10: 新增 `app/[locale]/knowledge/datasets/_components/DatasetsTable.tsx` (client)

**Files:**
- Create: `packages/web/app/[locale]/knowledge/datasets/_components/DatasetsTable.tsx`
- Create: `packages/web/app/[locale]/knowledge/datasets/_components/DatasetsTable.test.tsx`

**Context:** 现有 `datasets/page.tsx` 把表格 / 分页 / 错误处理全写在一个 `"use client"` 文件. 拆出 client 子组件: 接 prop `initialData: DatasetRow[]`, 内部管 page 状态 (useState).

- [ ] **Step 1: 写测试**

`packages/web/app/[locale]/knowledge/datasets/_components/DatasetsTable.test.tsx`:
```tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { DatasetsTable } from "./DatasetsTable";
import type { DatasetRow } from "@/lib/api/knowledge";

const sample: DatasetRow[] = [
  { id: "1", name: "DS1", document_count: 5, word_count: 100 },
  { id: "2", name: "DS2", document_count: 3, word_count: 60 },
];

describe("DatasetsTable", () => {
  it("渲染所有 dataset 名称", () => {
    render(<DatasetsTable initialData={sample} />);
    expect(screen.getByText("DS1")).toBeInTheDocument();
    expect(screen.getByText("DS2")).toBeInTheDocument();
  });

  it("分页: 5 条 / 页, 第 2 页含第 6 条", () => {
    const arr: DatasetRow[] = Array.from({ length: 12 }, (_, i) => ({
      id: String(i),
      name: `DS${i}`,
    }));
    render(<DatasetsTable initialData={arr} pageSize={5} />);
    // 默认第 1 页
    expect(screen.getByText("DS0")).toBeInTheDocument();
    expect(screen.queryByText("DS5")).not.toBeInTheDocument();
  });

  it("点击下一页, 显示后续数据集", async () => {
    const arr: DatasetRow[] = Array.from({ length: 12 }, (_, i) => ({
      id: String(i),
      name: `DS${i}`,
    }));
    render(<DatasetsTable initialData={arr} pageSize={5} />);
    await userEvent.click(screen.getByRole("button", { name: /next|下一页/i }));
    expect(screen.getByText("DS5")).toBeInTheDocument();
    expect(screen.queryByText("DS0")).not.toBeInTheDocument();
  });

  it("空数据时显示 '暂无数据集'", () => {
    render(<DatasetsTable initialData={[]} />);
    expect(screen.getByText(/暂无数据集/)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: 跑测试, 确认红**

```bash
cd packages/web && bun run test "app/[locale]/knowledge/datasets/_components/DatasetsTable.test.tsx"
```

预期: FAIL (文件不存在)

- [ ] **Step 3: 实现 DatasetsTable.tsx**

`packages/web/app/[locale]/knowledge/datasets/_components/DatasetsTable.tsx`:
```tsx
"use client";
// 客户端表格: 接 RSC 预取的 initialData, 管本地分页.
// 切 dataset/domain 时父级调 router.refresh() 触发 RSC 重跑.
import { useState } from "react";
import Link from "next/link";
import { motion, AnimatePresence } from "motion/react";
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "@/components/ui/table";
import { Pagination, PaginationContent, PaginationItem, PaginationPrevious, PaginationNext } from "@/components/ui/pagination";
import { CSS_EASE, DUR, Reveal } from "@/components/ui/animated";
import { KnowledgeHero } from "@/components/knowledge/KnowledgeHero";
import type { DatasetRow } from "@/lib/api/knowledge";

const DEFAULT_PAGE_SIZE = 20;

interface Props {
  initialData: DatasetRow[];
  pageSize?: number;
  error?: string;
}

export function DatasetsTable({ initialData, pageSize = DEFAULT_PAGE_SIZE, error }: Props) {
  const [page, setPage] = useState(0);
  const total = initialData.length;
  const totalPages = Math.ceil(total / pageSize);
  const rows = initialData.slice(page * pageSize, (page + 1) * pageSize);

  return (
    <div className="flex h-full flex-col gap-8">
      <KnowledgeHero
        eyebrow="Datasets"
        title="数据集"
        meta={total > 0 ? `共 ${total} 个` : undefined}
      />

      <AnimatePresence>
        {error && (
          <motion.div
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            transition={{ duration: DUR.normal, ease: CSS_EASE.outQuint }}
            className="rounded-xl border border-destructive/30 bg-destructive/5 p-4 text-base text-destructive"
          >
            加载数据集失败: {error}
          </motion.div>
        )}
      </AnimatePresence>

      <Reveal delay={0.2}>
        <div className="rounded-lg border border-border/40">
          <div className="min-h-0 flex-1 overflow-auto">
            <Table>
              <TableHeader className="sticky top-0 z-10 bg-muted/80 backdrop-blur-sm">
                <TableRow>
                  <TableHead className="eyebrow w-48">名称</TableHead>
                  <TableHead className="eyebrow">描述</TableHead>
                  <TableHead className="eyebrow w-24">文档数</TableHead>
                  <TableHead className="eyebrow w-24">字数</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.length > 0 ? (
                  rows.map((ds, i) => (
                    <motion.tr
                      key={ds.id}
                      data-testid="dataset-row"
                      initial={{ opacity: 0, y: 4 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ duration: DUR.normal, ease: CSS_EASE.outExpo, delay: i * 0.02 }}
                      className="border-b transition-colors hover:bg-muted/50"
                    >
                      <TableCell>
                        <Link
                          href={`/knowledge/dataset-documents/${ds.id}`}
                          className="text-base font-medium text-foreground hover:underline"
                        >
                          {ds.name}
                        </Link>
                      </TableCell>
                      <TableCell className="max-w-xs truncate text-muted-foreground">
                        {ds.description || "—"}
                      </TableCell>
                      <TableCell className="num text-muted-foreground">
                        {ds.document_count ?? "—"}
                      </TableCell>
                      <TableCell className="num text-muted-foreground">
                        {ds.word_count ?? "—"}
                      </TableCell>
                    </motion.tr>
                  ))
                ) : (
                  <TableRow>
                    <TableCell colSpan={4} className="h-24 text-center text-muted-foreground">
                      暂无数据集
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </div>

          {totalPages > 1 && (
            <div className="flex items-center justify-between border-t border-border/40 px-4 py-2">
              <span className="num text-sm text-muted-foreground">
                第 {page + 1} / {totalPages} 页 · 共 {total} 条
              </span>
              <Pagination className="mx-0 w-auto">
                <PaginationContent>
                  <PaginationItem>
                    <PaginationPrevious
                      onClick={() => setPage((p) => Math.max(0, p - 1))}
                      className={page === 0 ? "pointer-events-none opacity-50" : "cursor-pointer"}
                    />
                  </PaginationItem>
                  <PaginationItem>
                    <PaginationNext
                      onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
                      className={page >= totalPages - 1 ? "pointer-events-none opacity-50" : "cursor-pointer"}
                    />
                  </PaginationItem>
                </PaginationContent>
              </Pagination>
            </div>
          )}
        </div>
      </Reveal>
    </div>
  );
}
```

- [ ] **Step 4: 跑测试, 确认绿**

```bash
cd packages/web && bun run test "app/[locale]/knowledge/datasets/_components/DatasetsTable.test.tsx"
```

预期: PASS (4 个测试全过)

- [ ] **Step 5: Commit**

```bash
cd c:/doc/Code/worktrees/rag-refactor
git add "packages/web/app/[locale]/knowledge/datasets/_components/DatasetsTable.tsx" "packages/web/app/[locale]/knowledge/datasets/_components/DatasetsTable.test.tsx"
git commit -m "feat(datasets): 抽 DatasetsTable 客户端组件 (接 initialData)"
```

---

### Task 11: `app/[locale]/knowledge/datasets/page.tsx` 改 RSC + 删 SWR

**Files:**
- Modify: `packages/web/app/[locale]/knowledge/datasets/page.tsx` (从 client → RSC, 删 useSWR)
- Modify: `packages/web/app/[locale]/knowledge/datasets/page.test.tsx` (改写)

- [ ] **Step 1: 改写 page.test.tsx (先改测试)**

读 [packages/web/app/[locale]/knowledge/datasets/page.test.tsx](packages/web/app/[locale]/knowledge/datasets/page.test.tsx) 当前实现, 把对 `useSWR` 的 mock 删掉, 改为:

```tsx
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";

// mock next/headers cookies
vi.mock("next/headers", () => ({
  cookies: vi.fn(async () => ({
    get: (k: string) => (k === "rag_user_token" ? { value: "tok" } : undefined),
  })),
}));

// mock fetch
beforeEach(() => {
  global.fetch = vi.fn(async () =>
    new Response(
      JSON.stringify([
        { id: "1", name: "DS1", document_count: 5, word_count: 100 },
        { id: "2", name: "DS2", document_count: 3, word_count: 60 },
      ]),
      { status: 200, headers: { "Content-Type": "application/json" } },
    ),
  ) as never;
});

describe("DatasetsPage (RSC)", () => {
  it("渲染 RSC 预取的数据", async () => {
    const mod = await import("./page");
    const Page = mod.default;
    const element = await Page();
    const { container } = render(element as never);
    expect(container.textContent).toContain("DS1");
    expect(container.textContent).toContain("DS2");
  });

  it("fetch 失败时把错误透传 (RSC 抛错, error.tsx 兜住)", async () => {
    global.fetch = vi.fn(async () => new Response("bad", { status: 500 })) as never;
    const mod = await import("./page");
    const Page = mod.default;
    await expect(Page()).rejects.toThrow();
  });
});
```

> 注: 如果项目用 React Testing Library 渲染 RSC 有问题, 退化为"测试 DatasetsTable 子组件 + 测试 fetch 调用"分两个文件.

- [ ] **Step 2: 跑测试, 确认红**

```bash
cd packages/web && bun run test "app/[locale]/knowledge/datasets/page.test.tsx"
```

预期: FAIL (page 仍用 useSWR, 渲染逻辑变了)

- [ ] **Step 3: 重写 page.tsx 为 RSC**

完全替换 [packages/web/app/[locale]/knowledge/datasets/page.tsx](packages/web/app/[locale]/knowledge/datasets/page.tsx) 内容:
```tsx
// RSC: server 端 fetch datasets, prop 灌 client 子组件.
// 不再 "use client" — 真正的 server component.
import { getServerToken, API_BASE } from "@/lib/api/auth";
import type { DatasetRow } from "@/lib/api/knowledge";
import { DatasetsTable } from "./_components/DatasetsTable";

export const dynamic = "force-dynamic";  // 走 cookie, 每次请求取最新

async function fetchDatasets(): Promise<DatasetRow[]> {
  const token = await getServerToken();
  const res = await fetch(`${API_BASE}/api/kg/datasets`, {
    headers: token ? { "x-user-token": token } : {},
    cache: "no-store",
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}: ${await res.text()}`);
  return res.json() as Promise<DatasetRow[]>;
}

export default async function DatasetsPage() {
  const datasets = await fetchDatasets();
  return <DatasetsTable initialData={datasets} />;
}
```

- [ ] **Step 4: 跑测试, 确认绿**

```bash
cd packages/web && bun run test "app/[locale]/knowledge/datasets/page.test.tsx" "app/[locale]/knowledge/datasets/_components/DatasetsTable.test.tsx"
```

预期: PASS

- [ ] **Step 5: typecheck**

```bash
cd packages/web && bun run typecheck
```

预期: 0 错 (确认没遗留的 SWR 引用)

- [ ] **Step 6: 跑现有 e2e (1 个 datasets 烟测)**

```bash
cd packages/web && bun run test:e2e -- --grep "datasets"
```

预期: PASS

- [ ] **Step 7: Commit**

```bash
cd c:/doc/Code/worktrees/rag-refactor
git add "packages/web/app/[locale]/knowledge/datasets/page.tsx" "packages/web/app/[locale]/knowledge/datasets/page.test.tsx"
git commit -m "feat(datasets): page 改 RSC (删 SWR, server fetch + prop 灌 client)"
```

---

### Task 12: 新增 `_actions/knowledge.ts` (createQA/createTriples/commitDocuments)

**Files:**
- Create: `packages/web/app/[locale]/_actions/knowledge.ts`
- Create: `packages/web/app/[locale]/_actions/knowledge.test.ts`

**Context:** 3 个简单 mutation 改 server action. 统一 `ActionResult<T>` 包装, 成功才 revalidatePath.

- [ ] **Step 1: 写失败测试**

`packages/web/app/[locale]/_actions/knowledge.test.ts`:
```ts
import { describe, it, expect, vi, beforeEach } from "vitest";

vi.mock("next/headers", () => ({
  cookies: vi.fn(async () => ({
    get: (k: string) => (k === "rag_user_token" ? { value: "test-tok" } : undefined),
  })),
}));

vi.mock("next/cache", () => ({
  revalidatePath: vi.fn(),
}));

import { createQA, createTriples, commitDocuments } from "./knowledge";

beforeEach(() => {
  global.fetch = vi.fn(async () =>
    new Response(JSON.stringify({ ok: true }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    }),
  ) as never;
});

describe("createQA", () => {
  it("透传 dataset_id/question/answer 到后端", async () => {
    const result = await createQA({
      dataset_id: "ds-1",
      question: "Q?",
      answer: "A.",
    });
    expect(result.ok).toBe(true);
    const [url, init] = vi.mocked(global.fetch).mock.calls[0];
    expect(url).toContain("/api/knowledge/qa");
    expect(init?.method).toBe("POST");
    expect(JSON.parse(init?.body as string)).toEqual({
      dataset_id: "ds-1",
      question: "Q?",
      answer: "A.",
    });
    const headers = init?.headers as Record<string, string>;
    expect(headers["x-user-token"]).toBe("test-tok");
  });

  it("成功后调 revalidatePath", async () => {
    const { revalidatePath } = await import("next/cache");
    await createQA({ dataset_id: "x", question: "q", answer: "a" });
    expect(revalidatePath).toHaveBeenCalledWith("/[locale]/knowledge/qa");
  });

  it("失败时返 ActionResult { ok: false } 不抛异常", async () => {
    global.fetch = vi.fn(async () => new Response("bad", { status: 500 })) as never;
    const result = await createQA({ dataset_id: "x", question: "q", answer: "a" });
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.error).toContain("HTTP 500");
  });
});

describe("createTriples", () => {
  it("成功后 revalidatePath /triples", async () => {
    const { revalidatePath } = await import("next/cache");
    await createTriples({ rows: [] });
    expect(revalidatePath).toHaveBeenCalledWith("/[locale]/knowledge/triples");
  });
});

describe("commitDocuments", () => {
  it("成功后 revalidatePath /documents/import", async () => {
    const { revalidatePath } = await import("next/cache");
    await commitDocuments({ dataset_id: "x", rows: [] });
    expect(revalidatePath).toHaveBeenCalledWith("/[locale]/knowledge/documents/import");
  });
});
```

- [ ] **Step 2: 跑测试, 确认红**

```bash
cd packages/web && bun run test "app/[locale]/_actions/knowledge.test.ts"
```

预期: FAIL (文件不存在)

- [ ] **Step 3: 实现 _actions/knowledge.ts**

`packages/web/app/[locale]/_actions/knowledge.ts`:
```ts
"use server";
// 知识库相关 server actions: createQA / createTriples / commitDocuments.
// 简单数据 POST 用, 不用 BFF. multipart/流式/任务仍走 BFF.
import { revalidatePath } from "next/cache";
import { getServerToken, API_BASE } from "@/lib/api/auth";

/** 统一返回包装 — 永不抛, 错误走 error 字段. */
export type ActionResult<T> =
  | { ok: true; data: T }
  | { ok: false; error: string };

async function postJson<T>(path: string, body: unknown): Promise<ActionResult<T>> {
  const token = await getServerToken();
  try {
    const res = await fetch(`${API_BASE}${path}`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(token ? { "x-user-token": token } : {}),
      },
      body: JSON.stringify(body),
      cache: "no-store",
    });
    if (!res.ok) {
      const text = await res.text().catch(() => res.statusText);
      return { ok: false, error: `HTTP ${res.status}: ${text}` };
    }
    return { ok: true, data: (await res.json()) as T };
  } catch (e) {
    return { ok: false, error: e instanceof Error ? e.message : String(e) };
  }
}

interface QAInput {
  dataset_id: string;
  question: string;
  answer: string;
  tags?: string[];
  sync_to_neo4j?: boolean;
}

interface QA {
  id: string;
  question: string;
  answer: string;
}

export async function createQA(input: QAInput): Promise<ActionResult<QA>> {
  const result = await postJson<QA>("/api/knowledge/qa", input);
  if (result.ok) revalidatePath("/[locale]/knowledge/qa");
  return result;
}

interface TripleRowInput {
  from_label: string;
  from_key: string;
  from_value: string;
  rel_type: string;
  to_label: string;
  to_key: string;
  to_value: string;
  properties: Record<string, unknown>;
}

interface TriplesInput {
  rows: TripleRowInput[];
}

interface TriplesResponse {
  success: number;
  failed: number;
  errors: string[];
}

export async function createTriples(input: TriplesInput): Promise<ActionResult<TriplesResponse>> {
  const result = await postJson<TriplesResponse>("/api/kg/triples", input);
  if (result.ok) revalidatePath("/[locale]/knowledge/triples");
  return result;
}

interface CommitRowInput {
  question: string;
  answer: string;
  tags?: string;
}

interface CommitInput {
  dataset_id: string;
  rows: CommitRowInput[];
}

interface CommitResult {
  total: number;
  success: number;
  failed: number;
  results: { ok: boolean; name: string; error?: string }[];
}

export async function commitDocuments(input: CommitInput): Promise<ActionResult<CommitResult>> {
  const result = await postJson<CommitResult>("/api/knowledge/documents/commit", input);
  if (result.ok) revalidatePath("/[locale]/knowledge/documents/import");
  return result;
}
```

- [ ] **Step 4: 跑测试, 确认绿**

```bash
cd packages/web && bun run test "app/[locale]/_actions/knowledge.test.ts"
```

预期: PASS (5 个测试全过)

- [ ] **Step 5: typecheck**

```bash
cd packages/web && bun run typecheck
```

预期: 0 错

- [ ] **Step 6: Commit**

```bash
cd c:/doc/Code/worktrees/rag-refactor
git add "packages/web/app/[locale]/_actions/knowledge.ts" "packages/web/app/[locale]/_actions/knowledge.test.ts"
git commit -m "feat(actions): _actions/knowledge.ts (createQA/createTriples/commitDocuments)"
```

---

### Task 13: P1 端到端验证 + 整体回归

**Files:** 无 (纯验证)

- [ ] **Step 1: 跑 P0+P1 所有新加/改的测试**

```bash
cd packages/web && bun run test
```

预期: 全部 PASS (无回归)

- [ ] **Step 2: typecheck + lint**

```bash
cd packages/web && bun run typecheck && bun run lint
```

预期: 0 错

- [ ] **Step 3: 跑 E2E**

```bash
cd packages/web && bun run test:e2e
```

预期: 18 个 E2E 全过 (datasets 烟测在新 RSC 路径下仍工作)

- [ ] **Step 4: 手动 dev server 验证**

```bash
# 终端 1
cd packages/service && uv run python main.py

# 终端 2
cd packages/web && bun run dev
```

浏览器开 http://localhost:3000/zh/knowledge/datasets:
- 验证: 页面**首屏直接渲染数据** (无 "加载中..." 闪烁)
- 验证: 翻页正常
- 验证: devtools Network 面板, 切 dataset → 仅 1 次 RSC fetch, **无客户端 fetch**
- 验证: devtools Network 面板, 首屏无 SWR 或 RQ 请求

- [ ] **Step 5: 在 P0 阶段 commit 后追加一个 summary commit (可选)**

```bash
cd c:/doc/Code/worktrees/rag-refactor
git commit --allow-empty -m "chore(p1): datasets 试点完成 — 验证 RSC 路径端到端 OK"
```

---

## P2 A 档批量 (Task 14-22)

> 改造剩 12 个 A 档 page: 9 个 knowledge/* + 3 个 evaluate/* + 1 个 knowledge 根.
> 按"子领域分批"避免单 PR 太大 (CLAUDE.md 强调小步快跑).

### Task 14: 改造 `knowledge/documents` 2 页 (page + import)

**Files:**
- Modify: `packages/web/app/[locale]/knowledge/documents/page.tsx` (RSC 化)
- Modify: `packages/web/app/[locale]/knowledge/documents/page.test.tsx`
- Modify: `packages/web/app/[locale]/knowledge/documents/import/page.tsx` (RSC 化 + server action `commitDocuments`)
- Modify: `packages/web/app/[locale]/knowledge/documents/import/page.test.tsx`
- Create: `packages/web/app/[locale]/knowledge/documents/_components/*` (拆 client 子组件, 视情况)

**步骤模式同 Task 11 (datasets 试点). 简略列出, 具体代码按现有文件结构改写.**

- [ ] **Step 1: 改 page.test.tsx (先红)**

参考 Task 11 Step 1 的 RSC 测试模式, 删 SWR mock, 改 mock `next/headers` + `fetch`.

- [ ] **Step 2: 跑测试, 确认红**

```bash
cd packages/web && bun run test "app/[locale]/knowledge/documents/page.test.tsx"
```

预期: FAIL

- [ ] **Step 3: 改 page.tsx 为 RSC**

参考 Task 11 Step 3 的 RSC 模板. 该 page 用 `useSWR<{ documents: ... }>(knowledgeApi.documentsUrl(...))`, 改成:
```tsx
export const dynamic = "force-dynamic";

async function fetchDocuments() {
  const token = await getServerToken();
  const res = await fetch(`${API_BASE}/api/kg/documents?...`, { ... });
  if (!res.ok) throw new Error(...);
  return res.json();
}

export default async function DocumentsPage() {
  const data = await fetchDocuments();
  return <DocumentsTable initialData={data.documents} />;
}
```

- [ ] **Step 4: 同样改 import/page.tsx (RSC + server action)**

`import/page.tsx` 含上传 + 提交 Excel 行. 提交改 `<form action={formAction}>` + `commitDocuments` server action. 表格改 client 子组件.

- [ ] **Step 5: 跑测试 + typecheck + lint 全过**

```bash
cd packages/web && bun run test "app/[locale]/knowledge/documents/" && bun run typecheck && bun run lint
```

预期: PASS

- [ ] **Step 6: Commit**

```bash
cd c:/doc/Code/worktrees/rag-refactor
git add "packages/web/app/[locale]/knowledge/documents/"
git commit -m "refactor(documents): page+import 改 RSC + commitDocuments server action"
```

---

### Task 15: 改造 `knowledge/graph` + `knowledge/nodes` + `knowledge/relations` 3 页

**Files:**
- Modify: `packages/web/app/[locale]/knowledge/graph/page.tsx` + `.test.tsx`
- Modify: `packages/web/app/[locale]/knowledge/nodes/page.tsx` + `.test.tsx`
- Modify: `packages/web/app/[locale]/knowledge/relations/page.tsx` + `.test.tsx`

> 三页同型, 都是 useSWR + 表格, RSC 化模板同 Task 14.

- [ ] **Step 1-6**: 跟 Task 14 同模式, 三个 page 一次 PR.

- [ ] **Step 7: Commit**

```bash
cd c:/doc/Code/worktrees/rag-refactor
git add "packages/web/app/[locale]/knowledge/graph/" "packages/web/app/[locale]/knowledge/nodes/" "packages/web/app/[locale]/knowledge/relations/"
git commit -m "refactor(knowledge): graph/nodes/relations 3 页 RSC 化"
```

---

### Task 16: 改造 `knowledge/triples` (含 createTriples server action)

**Files:**
- Modify: `packages/web/app/[locale]/knowledge/triples/page.tsx` + `.test.tsx`

> triples 含 schema 拉取 + 三元组批量提交. RSC 拉 schema, 提交走 `createTriples` action (Task 12 已建).

- [ ] **Step 1-6**: 模式同 Task 14, 提交按钮改 `<form action={formAction}>` + `createTriples`.

- [ ] **Step 7: Commit**

```bash
cd c:/doc/Code/worktrees/rag-refactor
git add "packages/web/app/[locale]/knowledge/triples/"
git commit -m "refactor(triples): page RSC + createTriples server action"
```

---

### Task 17: 改造 `knowledge/qa` (含 createQA server action)

**Files:**
- Modify: `packages/web/app/[locale]/knowledge/qa/page.tsx` + `.test.tsx`
- Create: `packages/web/app/[locale]/knowledge/qa/_components/QASubmitForm.tsx` + `.test.tsx` (client 表单, 用 `useActionState`)

- [ ] **Step 1: 写 QASubmitForm 测试**

`packages/web/app/[locale]/knowledge/qa/_components/QASubmitForm.test.tsx`:
```tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

vi.mock("@/app/[locale]/_actions/knowledge", () => ({
  createQA: vi.fn(async () => ({ ok: true, data: { id: "x", question: "q", answer: "a" } })),
}));

import { QASubmitForm } from "./QASubmitForm";
import { createQA } from "@/app/[locale]/_actions/knowledge";

describe("QASubmitForm", () => {
  it("提交时调 createQA, 成功后展示 ok 状态", async () => {
    render(<QASubmitForm datasetId="ds-1" />);
    await userEvent.type(screen.getByRole("textbox", { name: /question/i }), "Q?");
    await userEvent.type(screen.getByRole("textbox", { name: /answer/i }), "A.");
    await userEvent.click(screen.getByRole("button", { name: /提交/ }));
    expect(vi.mocked(createQA)).toHaveBeenCalledWith(
      expect.objectContaining({ dataset_id: "ds-1", question: "Q?", answer: "A." }),
    );
  });
});
```

- [ ] **Step 2-6**: 跑测试红 → 写 QASubmitForm 实现 → 改 page.tsx RSC → 跑绿.

- [ ] **Step 7: Commit**

```bash
cd c:/doc/Code/worktrees/rag-refactor
git add "packages/web/app/[locale]/knowledge/qa/"
git commit -m "refactor(qa): page RSC + QASubmitForm (useActionState + createQA)"
```

---

### Task 18: 改造 `knowledge/dataset-documents/[id]`

**Files:**
- Modify: `packages/web/app/[locale]/knowledge/dataset-documents/[dataset_id]/page.tsx` + `.test.tsx`

> 含动态路由参数 `[dataset_id]`, RSC 化时用 `params.dataset_id` 拿参数.

- [ ] **Step 1-6**: 模式同 Task 14, 注意 params 异步拿 (Next 16 `params` 是 Promise).

- [ ] **Step 7: Commit**

```bash
cd c:/doc/Code/worktrees/rag-refactor
git add "packages/web/app/[locale]/knowledge/dataset-documents/"
git commit -m "refactor(dataset-documents): 动态路由 page RSC 化"
```

---

### Task 19: 改造 `evaluate/page` + `evaluate/[id]`

**Files:**
- Modify: `packages/web/app/[locale]/evaluate/page.tsx` + `.test.tsx`
- Modify: `packages/web/app/[locale]/evaluate/[id]/page.tsx` + `.test.tsx`
- Create: `packages/web/app/[locale]/_actions/evaluate.ts` + `.test.ts` (createRun/deleteRun)

- [ ] **Step 1: 写 _actions/evaluate.test.ts (先红)**

```ts
// 同 _actions/knowledge.test.ts 模式
import { createRun, deleteRun } from "./evaluate";

describe("createRun", () => {
  it("成功后 revalidatePath /evaluate", async () => {
    const { revalidatePath } = await import("next/cache");
    await createRun({ name: "test" });
    expect(revalidatePath).toHaveBeenCalledWith("/[locale]/evaluate");
  });
});

describe("deleteRun", () => {
  it("成功后 revalidatePath /evaluate/[id]", async () => {
    const { revalidatePath } = await import("next/cache");
    await deleteRun("run-1");
    expect(revalidatePath).toHaveBeenCalledWith("/[locale]/evaluate/run-1");
  });
});
```

- [ ] **Step 2-5**: 写 _actions/evaluate.ts → 改两 page → 测试绿.

- [ ] **Step 6: Commit**

```bash
cd c:/doc/Code/worktrees/rag-refactor
git add "packages/web/app/[locale]/evaluate/" "packages/web/app/[locale]/_actions/evaluate.ts" "packages/web/app/[locale]/_actions/evaluate.test.ts"
git commit -m "refactor(evaluate): list+detail 改 RSC + createRun/deleteRun actions"
```

---

### Task 20: 改造 `evaluate/new` (表单 + redirect)

**Files:**
- Modify: `packages/web/app/[locale]/evaluate/new/page.tsx` + `.test.tsx`

- [ ] **Step 1-6**: 模式同 Task 17, 提交后 `redirect(\`/evaluate/\${result.data.id}\`)`.

- [ ] **Step 7: Commit**

```bash
cd c:/doc/Code/worktrees/rag-refactor
git add "packages/web/app/[locale]/evaluate/new/"
git commit -m "refactor(evaluate): new 表单改 server action + redirect"
```

---

### Task 21: 改造 `knowledge/page.tsx` (根 Dashboard)

**Files:**
- Modify: `packages/web/app/[locale]/knowledge/page.tsx` + `.test.tsx`

- [ ] **Step 1-6**: 模式同 Task 14, 根页面用 RSC 拉 stats 概览.

- [ ] **Step 7: Commit**

```bash
cd c:/doc/Code/worktrees/rag-refactor
git add "packages/web/app/[locale]/knowledge/page.tsx" "packages/web/app/[locale]/knowledge/page.test.tsx"
git commit -m "refactor(knowledge): 根 dashboard RSC 化 (stats 概览)"
```

---

### Task 22: P2 整体回归

- [ ] **Step 1: 跑全量测试 + typecheck + lint**

```bash
cd packages/web && bun run test && bun run typecheck && bun run lint
```

预期: 全部 PASS, 0 错

- [ ] **Step 2: 跑 E2E**

```bash
cd packages/web && bun run test:e2e
```

预期: 18 个用例全过

- [ ] **Step 3: grep 确认 SWR 仅在 swr.ts 残留**

```bash
cd packages/web && grep -rn "from .*swr" --include="*.ts" --include="*.tsx" lib/ app/ components/ 2>&1
```

预期: 仅 `lib/api/swr.ts` 和 `lib/api/swr-provider.tsx` (P4 才删)

- [ ] **Step 4: 跑契约测试**

```bash
cd packages/service && uv run pytest tests/test_api_contract.py -v
```

预期: PASS

---

## P3 B 档 4 页 (Task 23-27)

> B 档 = RSC 入口 + HydrationBoundary + client `useQuery` 接管轮询.

### Task 23: 新增 `app/[locale]/output/layout.tsx` (B 档专属 RQ Provider)

**Files:**
- Create: `packages/web/app/[locale]/output/layout.tsx`

**Context:** `output` 和 `output/[task_id]` 都用 RQ, 共享一个 `QueryClientProvider`. 放 `output/layout.tsx` 范围内.

- [ ] **Step 1: 实现 layout**

`packages/web/app/[locale]/output/layout.tsx`:
```tsx
"use client";
// B 档专属: 包 QueryClientProvider, 避免 A 档页面加载 RQ 库.
import { useState, type ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

export default function OutputLayout({ children }: { children: ReactNode }) {
  const [qc] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: { staleTime: Infinity, gcTime: 0, retry: false },
        },
      }),
  );
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}
```

- [ ] **Step 2: typecheck**

```bash
cd packages/web && bun run typecheck
```

预期: 0 错

- [ ] **Step 3: Commit**

```bash
cd c:/doc/Code/worktrees/rag-refactor
git add "packages/web/app/[locale]/output/layout.tsx"
git commit -m "feat(output): B 档 layout 包 QueryClientProvider"
```

---

### Task 24: 改造 `output/page` (RSC + Hydration + RQ 轮询)

**Files:**
- Modify: `packages/web/app/[locale]/output/page.tsx` (RSC + Hydration)
- Create: `packages/web/app/[locale]/output/_components/OutputListClient.tsx` + `.test.tsx`

- [ ] **Step 1: 写 OutputListClient 测试**

`packages/web/app/[locale]/output/_components/OutputListClient.test.tsx`:
```tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { OutputListClient } from "./OutputListClient";

vi.mock("@/lib/api/ingest", () => ({
  ingestApi: {
    fetchTasks: vi.fn(async () => [
      { id: "t1", name: "task-1", state: "running", processed: 5, total: 10 },
    ]),
  },
}));

function wrap(ui: React.ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

describe("OutputListClient", () => {
  it("渲染任务列表", async () => {
    wrap(<OutputListClient />);
    await waitFor(() => {
      expect(screen.getByText("task-1")).toBeInTheDocument();
    });
  });
});
```

- [ ] **Step 2: 跑测试, 确认红**

```bash
cd packages/web && bun run test "app/[locale]/output/_components/OutputListClient.test.tsx"
```

预期: FAIL

- [ ] **Step 3: 实现 OutputListClient.tsx**

`packages/web/app/[locale]/output/_components/OutputListClient.tsx`:
```tsx
"use client";
// 任务列表: useQuery 接管, refetchInterval 5s.
import { useQuery } from "@tanstack/react-query";
import { qKeys } from "@/lib/api/queryKeys";
import { ingestApi, type IngestTask } from "@/lib/api/ingest";

export function OutputListClient() {
  const { data, isLoading, error } = useQuery<IngestTask[]>({
    queryKey: qKeys.output.list(),
    queryFn: () => ingestApi.fetchTasks(),
    refetchInterval: 5_000,
  });

  if (isLoading) return <div>加载中…</div>;
  if (error) return <div className="text-destructive">加载失败: {String(error)}</div>;
  if (!data || data.length === 0) return <div>暂无任务</div>;

  return (
    <ul>
      {data.map((t) => (
        <li key={t.id} data-testid="task-row">
          {t.name} - {t.state} ({t.processed}/{t.total})
        </li>
      ))}
    </ul>
  );
}
```

- [ ] **Step 4: 跑测试, 确认绿**

```bash
cd packages/web && bun run test "app/[locale]/output/_components/OutputListClient.test.tsx"
```

预期: PASS

- [ ] **Step 5: 改 page.tsx 为 RSC + Hydration**

`packages/web/app/[locale]/output/page.tsx`:
```tsx
import { HydrationBoundary, dehydrate } from "@tanstack/react-query";
import { getRscQueryClient, prefetchQuery } from "@/lib/api/rsc-queries";
import { qKeys } from "@/lib/api/queryKeys";
import { getServerToken, API_BASE } from "@/lib/api/auth";
import { OutputListClient } from "./_components/OutputListClient";

export const dynamic = "force-dynamic";

export default async function OutputPage() {
  const qc = await getRscQueryClient();
  await prefetchQuery(qc, qKeys.output.list(), `${API_BASE}/api/ingest/tasks`);

  return (
    <HydrationBoundary state={dehydrate(qc)}>
      <OutputListClient />
    </HydrationBoundary>
  );
}
```

- [ ] **Step 6: 改写 page.test.tsx (SWR 断言 → RSC 断言, 测 prefetch + Hydration)**

参考 Task 11 Step 1 模式改写, 加 mock dehydrate.

- [ ] **Step 7: 跑测试 + typecheck + lint**

```bash
cd packages/web && bun run test "app/[locale]/output/" && bun run typecheck && bun run lint
```

预期: PASS

- [ ] **Step 8: Commit**

```bash
cd c:/doc/Code/worktrees/rag-refactor
git add "packages/web/app/[locale]/output/"
git commit -m "feat(output): page 改 RSC + Hydration + RQ 5s 轮询"
```

---

### Task 25: 改造 `output/[task_id]/page` (进度轮询 2s) + 加 cancelTask action

**Files:**
- Modify: `packages/web/app/[locale]/output/[task_id]/page.tsx` + `.test.tsx`
- Create: `packages/web/app/[locale]/output/[task_id]/_components/TaskDetailClient.tsx` + `.test.tsx`
- Create: `packages/web/app/[locale]/_actions/output.ts` (cancelTask)
- Create: `packages/web/app/[locale]/_actions/output.test.ts`

**Context:** 任务详情, 轮询 2s. 完成后停止轮询 (refetchInterval 在 done 时改 false). "取消任务" 按钮调 `cancelTask` server action.

- [ ] **Step 1-4**: 模式同 Task 24, 区别:
  - `queryKey: qKeys.output.detail(task_id)`
  - `refetchInterval: (q) => (q.state.data?.state === "completed" ? false : 2_000)`

- [ ] **Step 5: 写 _actions/output.test.ts (先红)**

```ts
import { describe, it, expect, vi, beforeEach } from "vitest";

vi.mock("next/headers", () => ({
  cookies: vi.fn(async () => ({
    get: (k: string) => (k === "rag_user_token" ? { value: "test-tok" } : undefined),
  })),
}));

vi.mock("next/cache", () => ({
  revalidatePath: vi.fn(),
}));

import { cancelTask } from "./output";

beforeEach(() => {
  global.fetch = vi.fn(async () =>
    new Response(JSON.stringify({ ok: true }), { status: 200 }),
  ) as never;
});

describe("cancelTask", () => {
  it("成功后 revalidatePath /output/[task_id]", async () => {
    const { revalidatePath } = await import("next/cache");
    const result = await cancelTask("task-1");
    expect(result.ok).toBe(true);
    expect(revalidatePath).toHaveBeenCalledWith("/[locale]/output/task-1");
  });

  it("失败时不 revalidatePath", async () => {
    global.fetch = vi.fn(async () => new Response("bad", { status: 500 })) as never;
    const { revalidatePath } = await import("next/cache");
    vi.mocked(revalidatePath).mockClear();
    const result = await cancelTask("task-2");
    expect(result.ok).toBe(false);
    expect(revalidatePath).not.toHaveBeenCalled();
  });
});
```

- [ ] **Step 6: 跑测试, 确认红**

```bash
cd packages/web && bun run test "app/[locale]/_actions/output.test.ts"
```

预期: FAIL (文件不存在)

- [ ] **Step 7: 实现 _actions/output.ts**

`packages/web/app/[locale]/_actions/output.ts`:
```ts
"use server";
// Output 相关 server actions: cancelTask.
import { revalidatePath } from "next/cache";
import { getServerToken, API_BASE } from "@/lib/api/auth";
import type { ActionResult } from "./knowledge";  // 复用 _actions/knowledge.ts 的 ActionResult

export async function cancelTask(taskId: string): Promise<ActionResult<{ ok: true }>> {
  const token = await getServerToken();
  try {
    const res = await fetch(`${API_BASE}/api/ingest/tasks/${encodeURIComponent(taskId)}/cancel`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(token ? { "x-user-token": token } : {}),
      },
      cache: "no-store",
    });
    if (!res.ok) {
      const text = await res.text().catch(() => res.statusText);
      return { ok: false, error: `HTTP ${res.status}: ${text}` };
    }
    revalidatePath(`/[locale]/output/${taskId}`);
    return { ok: true, data: { ok: true } };
  } catch (e) {
    return { ok: false, error: e instanceof Error ? e.message : String(e) };
  }
}
```

> 复用 `_actions/knowledge.ts` 的 `ActionResult` 类型 (从该文件 re-export 也行, 或移去 `lib/api/action-result.ts`).

- [ ] **Step 8: 跑测试, 确认绿**

```bash
cd packages/web && bun run test "app/[locale]/_actions/output.test.ts"
```

预期: PASS

- [ ] **Step 9: TaskDetailClient 改用 cancelTask (form action)**

在 `TaskDetailClient.tsx` 加 "取消任务" 按钮:
```tsx
<form action={async () => {
  const r = await cancelTask(taskId);
  if (!r.ok) toast.error(r.error);
  else toast.success("已取消");
}}>
  <button type="submit" disabled={isPending}>取消任务</button>
</form>
```

- [ ] **Step 10: 跑测试 + typecheck + lint + E2E**

```bash
cd packages/web && bun run test "app/[locale]/output/[task_id]/" "app/[locale]/_actions/" && bun run typecheck && bun run lint && bun run test:e2e
```

预期: PASS

- [ ] **Step 11: Commit**

```bash
cd c:/doc/Code/worktrees/rag-refactor
git add "packages/web/app/[locale]/output/[task_id]/" "packages/web/app/[locale]/_actions/output.ts" "packages/web/app/[locale]/_actions/output.test.ts"
git commit -m "feat(output): task detail 改 RSC + RQ 2s 轮询 + cancelTask action"
```

---

### Task 26: 改造 `health/page` (10s 轮询)

**Files:**
- Modify: `packages/web/app/[locale]/health/page.tsx` + `.test.tsx`
- Create: `packages/web/app/[locale]/health/layout.tsx` (B 档专属, 放 QueryClientProvider)
- Create: `packages/web/app/[locale]/health/_components/HealthClient.tsx` + `.test.tsx`

- [ ] **Step 1-8**: 模式同 Task 24, 区别:
  - `queryKey: qKeys.health.system()`
  - `refetchInterval: 10_000`
  - **新**增 `health/layout.tsx` (B 档专属)

- [ ] **Step 9: Commit**

```bash
cd c:/doc/Code/worktrees/rag-refactor
git add "packages/web/app/[locale]/health/"
git commit -m "feat(health): page 改 RSC + RQ 10s 轮询"
```

---

### Task 27: 改造 `HealthDot.tsx` (navbar 5s 轮询)

**Files:**
- Modify: `packages/web/components/knowledge/HealthDot.tsx` (useSWR → useQuery)
- Modify: `packages/web/components/knowledge/HealthDot.test.tsx`

**Context:** HealthDot 嵌在 navbar, 父级已包 RQ Provider (B 档 layout 共享).

- [ ] **Step 1: 改 HealthDot.test.tsx (先红)**

参考 Task 24 Step 1 模式, mock useQuery.

- [ ] **Step 2: 跑测试, 确认红**

```bash
cd packages/web && bun run test components/knowledge/HealthDot.test.tsx
```

预期: FAIL

- [ ] **Step 3: 改 HealthDot.tsx**

`packages/web/components/knowledge/HealthDot.tsx`:
```tsx
"use client";
// 顶部健康指示灯: 5s 轮询, queryKey 跟 health page 共享.
import { useQuery } from "@tanstack/react-query";
import { qKeys } from "@/lib/api/queryKeys";
import { knowledgeApi } from "@/lib/api/knowledge";

export function HealthDot() {
  const { data, isLoading } = useQuery({
    queryKey: qKeys.health.system(),
    queryFn: () => knowledgeApi.fetchHealth(),
    refetchInterval: 5_000,
  });
  if (isLoading) return <span className="size-2 rounded-full bg-muted" />;
  return (
    <span
      className={
        data?.ok
          ? "size-2 rounded-full bg-emerald-500"
          : "size-2 rounded-full bg-rose-500"
      }
      title={data?.ok ? "健康" : "异常"}
    />
  );
}
```

> 注: `knowledgeApi.fetchHealth` 内部用 `clientFetch` (P0 改完), 浏览器自动带 cookie.

- [ ] **Step 4: 跑测试, 确认绿**

```bash
cd packages/web && bun run test components/knowledge/HealthDot.test.tsx
```

预期: PASS

- [ ] **Step 5: 跑全量回归**

```bash
cd packages/web && bun run test && bun run typecheck && bun run lint
```

预期: PASS

- [ ] **Step 6: 跑 E2E**

```bash
cd packages/web && bun run test:e2e
```

预期: 18 个用例全过

- [ ] **Step 7: Commit**

```bash
cd c:/doc/Code/worktrees/rag-refactor
git add packages/web/components/knowledge/HealthDot.tsx packages/web/components/knowledge/HealthDot.test.tsx
git commit -m "refactor(HealthDot): useSWR → useQuery (5s 轮询)"
```

---

## P4 清理 (Task 28-30)

> 删 SWR 文件, 删依赖, 评估删 qa/route.ts (CLAUDE.md 强制跑契约测试).

### Task 28: 删 `lib/api/swr.ts` + `lib/api/swr-provider.tsx`

**Files:**
- Delete: `packages/web/lib/api/swr.ts`
- Delete: `packages/web/lib/api/swr-provider.tsx`

- [ ] **Step 1: grep 确认无引用**

```bash
cd packages/web && grep -rn "from .*lib/api/swr" --include="*.ts" --include="*.tsx" 2>&1
```

预期: 0 命中 (P1-P3 阶段已全切完)

- [ ] **Step 2: 跑契约测试 (CLAUDE.md 强制, 删前必跑)**

```bash
cd packages/service && uv run pytest tests/test_api_contract.py -v
```

预期: PASS

- [ ] **Step 3: 删文件**

```bash
cd c:/doc/Code/worktrees/rag-refactor
git rm packages/web/lib/api/swr.ts packages/web/lib/api/swr-provider.tsx
```

- [ ] **Step 4: typecheck + 跑测试**

```bash
cd packages/web && bun run typecheck && bun run test
```

预期: 0 错, 测试全过

- [ ] **Step 5: E2E**

```bash
cd packages/web && bun run test:e2e
```

预期: PASS

- [ ] **Step 6: Commit**

```bash
cd c:/doc/Code/worktrees/rag-refactor
git commit -m "chore(swr): 删 lib/api/swr.ts + swr-provider.tsx"
```

---

### Task 29: 删 `package.json` 里的 `swr` 依赖

**Files:**
- Modify: `packages/web/package.json`

- [ ] **Step 1: 删包**

```bash
cd packages/web
bun remove swr
```

预期: `package.json` 移除 `"swr"` 行, `bun.lock` 更新.

- [ ] **Step 2: 验证**

```bash
cd packages/web && cat package.json | grep -E '"swr"|"@tanstack/react-query"' || echo "OK: swr 已删, RQ 在"
```

预期: `swr` 不在, `@tanstack/react-query` 在

- [ ] **Step 3: 跑全量回归**

```bash
cd packages/web && bun run test && bun run typecheck && bun run lint && bun run test:e2e
```

预期: 全过

- [ ] **Step 4: Commit**

```bash
cd c:/doc/Code/worktrees/rag-refactor
git add packages/web/package.json packages/web/bun.lock
git commit -m "chore(deps): 删 swr 依赖"
```

---

### Task 30: 评估删 `app/api/knowledge/qa/route.ts` (变空壳)

**Files:**
- Delete (条件性): `packages/web/app/api/knowledge/qa/route.ts`

**Context:** P2 阶段后, qa 列表走 RSC, qa POST 改 server action, BFF qa/route.ts 变空壳. 但 P2 阶段**不删**, 留到 P4 评估.

- [ ] **Step 1: grep 确认无前端引用**

```bash
cd packages/web && grep -rn "knowledge/qa" --include="*.ts" --include="*.tsx" 2>&1
```

预期: 仅 server action `createQA` 路径出现 `knowledge/qa` (POST 后端), **无 fetch 引用 `app/api/knowledge/qa`**

- [ ] **Step 2: 跑契约测试 (CLAUDE.md 强制, 红了不能删)**

```bash
cd packages/service && uv run pytest tests/test_api_contract.py -v
```

预期: PASS

- [ ] **Step 3: 删文件 (如果 Step 1+2 都过)**

```bash
cd c:/doc/Code/worktrees/rag-refactor
git rm packages/web/app/api/knowledge/qa/route.ts
```

> ⚠️ 如果 Step 1 还有引用或 Step 2 红了, **不删**, 改用空 handler 保留:
> ```ts
> // packages/web/app/api/knowledge/qa/route.ts
> import { NextResponse } from "next/server";
> export async function GET() {
>   return NextResponse.json(
>     { error: "moved to RSC, use server component" },
>     { status: 410 },  // Gone
>   );
> }
> ```
> 然后单独 commit 标识"deprecated"

- [ ] **Step 4: typecheck + E2E**

```bash
cd packages/web && bun run typecheck && bun run test:e2e
```

预期: PASS

- [ ] **Step 5: Commit**

```bash
cd c:/doc/Code/worktrees/rag-refactor
git commit -m "chore(bff): 删 app/api/knowledge/qa/route.ts (变空壳, RSC+action 已替代)"
```

---

## 验收检查清单 (DoD)

完成所有 Task 后, 跑一遍验收:

- [ ] **A1**: `git grep "from .*swr" -- packages/web` 0 命中
- [ ] **A2**: `git grep "useSWR\\b"` (源码) 0 命中
- [ ] **A3**: `package.json` 不含 `swr`, 含 `@tanstack/react-query@^5.62`
- [ ] **A4**: `lib/api/swr.ts` 和 `swr-provider.tsx` 已删
- [ ] **A5**: `lib/api/auth.ts` 不再读 `localStorage` 的 `rag_user_token`
- [ ] **A6**: 13 个 A 档 page 是 server component (无 `"use client"` 顶)
- [ ] **A7**: 4 个 B 档 page 有 `HydrationBoundary` + `useQuery` + `refetchInterval`
- [ ] **A8**: 18 份 `.test.tsx` 全部跟着改造, `bun run test` 全绿
- [ ] **A9**: 3 份 server action 测试 + 2 份 RQ utility 测试存在并绿
- [ ] **A10**: `tests/test_api_contract.py` 绿
- [ ] **A11**: E2E 18 个用例全过
- [ ] **A12**: `bun run typecheck` 0 错
- [ ] **A13**: `bun run lint` 0 错
- [ ] **A14**: A 档页面在 root layout 不挂 `QueryClientProvider` (devtools Network 面板验证)
- [ ] **A15**: 切 dataset 用 `router.refresh()`, 无新 fetch (devtools Network 面板验证)

---

## 自审 (writing-plans 自检)

按 writing-plans skill 要求做 4 角度自审:

1. **Spec 覆盖**: 设计 1-7 + 阶段安排 5 阶段 + 验收标准 15 项 — 全部对应到 Task 1-30. ✅
2. **占位符扫描**: 全文搜 "TBD|TODO|占位|待填" → 0 命中. ✅
3. **类型一致性**: `getServerToken / clientFetch / qKeys / prefetchQuery / getRscQueryClient / createQA / createTriples / commitDocuments / createRun / deleteRun / cancelTask` — 在 Task 5/6/7/8/12/19/30 中定义, 在 Task 14-27 中引用, 名称一致. ✅
4. **命令正确性**: `bun add` / `bun remove` / `bun run test` / `bun run typecheck` / `bun run lint` / `bun run test:e2e` / `uv run pytest` — 跟 web/CLAUDE.md 工具链一致. ✅

---

## 风险提醒 (执行时注意)

1. **P0 阶段后端先行**: 后端 Set-Cookie / migrate / CORS 改完**前**不删前端 localStorage, 灰度 1-2 周
2. **P1 试点**: 验证 dev server 首屏 LCP 改善, 跑 E2E 全过再进 P2
3. **P2 批量**: 一次 PR 不要超过 4 个 page (避免 review 难), 拆 Task 14-21
4. **P3 B 档**: HydrationBoundary 必须**包住** `useQuery` 调用的 client 子组件, 否则会"预取白做"
5. **P4 删 SWR**: 跑契约测试**必过**才删, 红了不删 (CLAUDE.md 强制)

---

**Plan 完成, 等用户选执行方式 (subagent-driven / inline).**

