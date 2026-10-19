---
name: feedback-bff-cookie-must-propagate
description: "BFF 转发鉴权 cookie 路由 (e.g. /api/auth/anon) 必须用 Headers.getSetCookie() 透传 set-cookie 头, 否则浏览器永远拿不到 token, 后续请求全 401"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 1dfcdecb-84bb-4149-9ad1-d1b332effa26
---

**BFF 转发鉴权 cookie 路由必须透传 set-cookie 头, 用 Headers.getSetCookie() 拷贝.**

**Why:** 2026-06-14 web 启动报 "缺少 x-user-token":

```bash
curl http://localhost:3000/api/auth/anon
# 404 Not Found (Next dev server 找不到 route)
```

根因链路:
1. AuthBootstrap.tsx 调 `apiFetch("/api/auth/anon", { method: "POST" })`
2. 浏览器 → Next dev server `/api/auth/anon` → **没 BFF route** → 404
3. 后端 Set-Cookie 永远没设上 → cookie 为空
4. 后续 `/api/ingest/*` BFF 转发到后端时, 后端 `_check_token` 拿不到 `rag_user_token` → 401 "缺少 x-user-token"
5. 前端 `apiFetch` 抛 ApiError(401, "缺少 x-user-token") → stack 报 config.ts:93

**漏建 BFF route 是真因**, **不是后端**:
- 后端 `packages/service/src/auth/router.py:67 @router.post("/anon", ...)` ✅ 在
- 后端 contract test FRONTEND_EXPECTS L39 列出 anon ✅
- 唯独 web 端 `app/api/auth/anon/route.ts` **缺失** (被我大改时漏了)

**修法 (用户拍板 A 方案): 直 fetch + 透传 set-cookie**

```ts
// app/api/auth/anon/route.ts
import { NextRequest } from "next/server";
import { API_BASE } from "@/lib/api/config";
import { proxyAuthResponse } from "./proxy";

export const dynamic = "force-dynamic";

export async function POST(_req: NextRequest) {
  const upstream = await fetch(`${API_BASE}/api/auth/anon`, {
    method: "POST",
    cache: "no-store",
  });
  return proxyAuthResponse(upstream);
}
```

```ts
// proxy.ts 纯函数, 便于 vitest 测
import { NextResponse } from "next/server";

export function proxyAuthResponse(upstream: Response): NextResponse {
  const headers = new Headers();
  const ct = upstream.headers.get("content-type");
  if (ct) headers.set("content-type", ct);
  // Node 18+ 标准 API, 多个 set-cookie 不会合并
  for (const cookie of upstream.headers.getSetCookie()) {
    headers.append("set-cookie", cookie);
  }
  return new NextResponse(upstream.body, {
    status: upstream.status,
    headers,
  });
}
```

**关键点**:
- ❌ `headers.get("set-cookie")` 只返**第一个** cookie, 多个 set-cookie (e.g. refresh + access) 会丢
- ❌ `Object.fromEntries(headers)` 把同名 header 合并成逗号串, set-cookie 含 `,` (expires) 会被切碎
- ✅ **`headers.getSetCookie()`** (Node 18+) 返 string[] 完整保留

**How to apply:**
- 凡是后端用 `response.set_cookie()` 的路由, BFF **必须** 透传 set-cookie
- 后端常用 set-cookie 端点: /api/auth/anon, /api/auth/migrate (登录), /api/auth/logout (清 cookie)
- TDD: 抽纯函数 `proxyAuthResponse(upstream: Response) => NextResponse`, 喂 mock Response 测 status / body / set-cookie 透传

**验证**:
```bash
# 后端先启 (uv run python main.py)
curl -X POST http://127.0.0.1:8000/api/auth/anon -i
# 应该返: 200 + set-cookie: rag_user_token=...; HttpOnly; ...
```

**关联**:
- [[feedback-bff-must-propagate-502-not-silently-zero]] — 4xx/5xx 必须前向, 不要兜底
- [[feedback-check-old-code-before-refactor]] — 改 BFF 前先 git show 老代码确认
- [[feedback-windows-lint-staged-cwd-bug]] — 测试跑不起来别死循环, 肉眼核 + curl 也行
