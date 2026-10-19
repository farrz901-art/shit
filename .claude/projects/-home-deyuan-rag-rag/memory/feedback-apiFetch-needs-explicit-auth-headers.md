---
name: feedback-apifetch-needs-explicit-auth-headers
description: "apiFetch 不会自动从 cookies() 透传 token, server-side 调用必须显式 headers: await serverAuthHeaders(), 不然走 RAG_DEV_AUTH 返 dev anon"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: e14df16a-a6ec-4603-b9f3-e9386f9c08e5
---

`apiFetch()` 不会自动从 `cookies()` 读 token 拼 `x-user-token` header. Server-side (RSC / layout / server action) 调用必须**显式**传 `headers: await serverAuthHeaders()`.

**Why**: 2026-06-17 登录 UserMenu 永远显示 "登录" 按钮 (display_name 走 email fallback) 真案. layout.tsx 写 `user = await apiFetch<UserMenuUser>("/api/account/me")` 不传 headers, backend 收到的是 RAG_DEV_AUTH 模式下的 dev anon user (`is_account: false`), UserMenu 走 `!user.is_account` 分支显示登录按钮. bug 一直存在, 只是平时 dev 模式 anon 也能用, 没察觉是"假"登录态.

**How to apply**:
- 任何 server-side (RSC / layout / server action) 调 `apiFetch` 都必须 `headers: await serverAuthHeaders()`. 跟 client-side (BFF 同源 cookie 自动带) 不一样.
- 自查命令: `grep -rn "apiFetch(" packages/web/app/` 然后看每个调用有没有传 headers
- 旧注释里写"server 端自动从 cookies() 透传 token"是**错的**, 那时为啥没炸: dev 模式 RAG_DEV_AUTH 返 dev anon, 业务能跑 (UserMenu 走 fallback) 让人误以为 ok
- 验证: 写 e2e 一定要 assert "登录后 UserMenu 显示 display_name", 不能只看 "登录后 page 不报错"

**反模式**:
- ❌ `apiFetch("/api/account/me")` 漏 headers
- ❌ 注释里写"自动透传" (跟实际行为不符, 误导后来人)
- ❌ 单元测试 mock 一切, 验不到 server-side fetch 是否真带 token (layout 必须 e2e 验)

**真实代码** (修后):
```typescript
// layout.tsx
import { serverAuthHeaders } from "@/lib/api/auth.server";

let user: UserMenuUser | null = null;
try {
  user = await apiFetch<UserMenuUser>("/api/account/me", {
    headers: await serverAuthHeaders(),  // ← 必须显式传!
  });
} catch { user = null; }
```

**伴随修复** (2026-06-17): backend `CurrentUser` 加 `display_name` 字段, `auth_account_router.me()` 返它. 否则 UserMenu 只能 fallback 到 email.
