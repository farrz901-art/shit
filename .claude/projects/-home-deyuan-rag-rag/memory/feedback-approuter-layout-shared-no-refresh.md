---
name: feedback-approuter-layout-shared-no-refresh
description: "【错误分析纠正】router.refresh() 实际会重跑 layout, 2026-06-17 登录 UserMenu 不更新真因是 apiFetch 漏传 auth headers 不是 layout 共享"
metadata:
  node_type: memory
  type: feedback
  originSessionId: e14df16a-a6ec-4603-b9f3-e9386f9c08e5
  status: superseded
  supersededBy: feedback-apiFetch-needs-explicit-auth-headers
---

# ⚠️ 这个 memory 是错误分析纠正, 已被 [[feedback-apiFetch-needs-explicit-auth-headers]] 取代

## 错在哪 (2026-06-17 复盘)

**错误结论**: App Router `[locale]/layout.tsx` 在 client navigation 之间共享, `router.refresh()` 不会重跑 layout, 所以 post-login 必须用 server-side `redirect()`.

**真实结论** (2026-06-17 后续 e2e 验证发现):
- `router.refresh()` 实际**会**重跑 layout (Next.js 15 官方行为: "Layouts: The current page (including its data) and all layouts in the current segment tree are re-rendered")
- UserMenu 不更新真因: `[locale]/layout.tsx` 的 `apiFetch("/api/account/me")` **漏传 `headers: await serverAuthHeaders()`**
- backend 收到的是 RAG_DEV_AUTH dev anon user (`is_account: false`), UserMenu 走 `!user.is_account` 分支显示 "登录" 按钮

## 为什么错 (debug 反模式)

1. 看到 UserMenu 不更新, 没有先验证 layout 的 `/me` 实际返什么 → 直接归因到 router.refresh (没证据)
2. "router.push + router.refresh" 改成 "server-side redirect" 后用户**仍报 user-menu 不更新** → 没反思"刚才的根因分析是错的", 而是又去分析 server-side redirect 实现细节
3. 跑 e2e/curl 验 backend /me response → **这一步才看到 display_name 缺 + RAG_DEV_AUTH 路径**, 真相浮出
4. layout 加 `headers: await serverAuthHeaders()` → user 立刻对了

## 教训 (写给未来的我)

**遇到"X 操作没生效"类 bug, 不要先猜是 X 的机制问题**:
1. **加 instrumentation 看到底走到哪一步** (network log, server log, 中间件 log)
2. **每层都看 actual data**, 不要"按理应该是 Y"
3. **修一次没生效 → 重新评估根因**, 不是再深入 X 机制
4. 写 memory 之前用 curl/E2E 真实验证根因, 不靠"看起来对"的分析

## 附带: server-side redirect 本身对不对

`redirect({ href, locale })` 走 server-side, **作为 post-auth 跳转** 是合理的 (跟 useActionState 集成最自然, 浏览器拿 Set-Cookie 跟 303 一起). 保留这个改动没问题, 理由:
- 跟 useActionState 集成好 (server action 抛 NEXT_REDIRECT, useActionState 自动 follow)
- 显式, 不会依赖 React 客户端 follow
- 不需要拆 commit 回滚

**不是**因为 "layout 不重跑" 才用 server-side redirect — 这个理由是错的, 真理由是 "标准 post-auth 模式".
