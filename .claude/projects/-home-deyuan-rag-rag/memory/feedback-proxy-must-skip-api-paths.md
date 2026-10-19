---
name: feedback-proxy-must-skip-api-paths
description: "Next.js proxy.ts (Next 16 前身 middleware.ts) 必须显式 NextResponse.next() 跳过 /api/* BFF 路径, next-intl middleware 默认会强加 locale 前缀 (307 → /zh/api/... → 404)"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 1dfcdecb-84bb-4149-9ad1-d1b332effa26
---

**Next.js proxy.ts 必须显式 NextResponse.next() 跳过 /api/* BFF 路径, matcher 排除不生效.**

**Why:** 2026-06-14 web BFF 路由 307 redirect bug:

```bash
curl -X POST http://localhost:3000/api/auth/anon -i
# HTTP/1.1 307 Temporary Redirect
# location: /zh/api/auth/anon
# 
# curl -X POST http://localhost:3000/zh/api/auth/anon -i
# HTTP/1.1 404 Not Found (BFF 在 app/api/ 不在 app/[locale]/api/)
```

**根因**:
- BFF route 文件位置: `app/api/auth/anon/route.ts` (root level)
- next-intl middleware 默认行为: 看到不带 locale 前缀的路径就 307 redirect 加前缀
- proxy.ts matcher **写了** `/((?!api|_next|...).*)/` 排除 api,**但 next-intl 内部还有"加 locale 前缀"逻辑**,matcher 限制的是 "哪条 URL 进入 middleware",**不是 "middleware 怎么改 URL"**
- 结果: `/api/auth/anon` 进入 proxy.ts → intlMiddleware() → 307 到 `/zh/api/auth/anon` → 404

**修法** (proxy.ts):

```ts
export default function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // -1) /api/* BFF 路由直通 — 不能让 next-intl 强加 locale 前缀
  if (pathname.startsWith("/api/")) {
    return NextResponse.next();
  }
  // ... 其他分支
}
```

**Why matcher 不够**:
- `matcher` 是 Next.js 决定 "request 走不走过 proxy.ts" 的规则
- next-intl middleware 内部"加 locale prefix"逻辑**不**受 matcher 限制 — 它对**所有**进 proxy.ts 的请求都做
- 必须 proxy.ts 里**手动** NextResponse.next() 跳出

**关联**:
- [[feedback-bff-cookie-must-propagate]] — BFF 鉴权 cookie 透传
- [[feedback-bff-must-propagate-502-not-silently-zero]] — BFF 错误前向
- [[feedback-check-old-code-before-refactor]] — 改 BFF 前先 git show 老代码
