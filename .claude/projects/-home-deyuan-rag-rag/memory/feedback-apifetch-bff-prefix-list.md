---
name: feedback-apifetch-bff-prefix-list
description: "apiFetch() 必须区分 BFF 名单 vs 直连后端, 一刀切 \"/api/* 同源\" 会让 /api/kg/* 等 14 个 endpoint 404"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 1dfcdecb-84bb-4149-9ad1-d1b332effa26
---

`apiFetch()` 在浏览器端不能用 `path.startsWith("/api/")` 一刀切走同源 BFF. 必须用精确的 BFF 名单 (path → RegExp), 其他 `/api/*` 直连后端.

**Why:** 2026-06-14 用户报 `GET /api/kg/health 404`. 调查发现 [config.ts:74](packages/web/lib/api/config.ts#L74) 老逻辑是 `if (path.startsWith("/api/") && typeof window !== "undefined") return window.location.origin`, 浏览器调 `/api/kg/health` → `localhost:3000/api/kg/health` → Next 没这个 BFF 路由 (app/api/ 下没 kg/) → 404. **但后端 `/api/kg/health` 100% 存在**, curl 直连 200. **14 个 endpoint 同样 404**: `/api/kg/{health,datasets,stats,nodes,schema,schemas,segments,relationships,products,templates/excel}` + `/api/account/me` + `/api/admin/users` + `/api/output/files` + 部分 `/api/approvals/*`. 修法: 维护精确 BFF 名单 (7 个 RegExp), 加新 BFF 路由时同步加.

**How to apply:**
- BFF 名单 ([config.ts:76-84](packages/web/lib/api/config.ts#L76-L84)) 用 `RegExp[]`, 不要用 prefix 数组, 因为 BFF 路由是动态参数 (`/api/approvals/{id}/approve`), prefix 匹配会误中
- 当前 BFF 真存在的 7 个 path pattern:
  - `/^\/api\/approvals\/[^/]+\/(approve|reject|retry)(\/|\?|$)/`
  - `/^\/api\/auth\/anon(\/|\?|$)/`
  - `/^\/api\/chat\/messages(\/|\?|$)/`
  - `/^\/api\/evaluate(\/|\?|$)/`
  - `/^\/api\/health\/system(\/|\?|$)/`
  - `/^\/api\/ingest(\/|\?|$)/`
  - `/^\/api\/knowledge(\/|\?|$)/`
- 加新 BFF 时**两件事一起**: 1) 建 `app/api/.../route.ts` 2) 在 `BFF_PATTERNS` 加 RegExp
- 测试: `lib/api/config.test.ts` 15 个 case, 必须覆盖: BFF 命中 / 直连命中 / server 端走 host / 边界 path (如 `/api/approvals/me` 不在 BFF)
- 验证修复: 不能用 `curl http://localhost:3000/api/kg/health` (永远 404, 跟 apiFetch 修无关). 用 playwright 打开页面, `browser_network_requests` 过滤 `api/kg` 看是不是打到 `127.0.0.1:8000` 返 200
- 关联 [[feedback-bff-must-propagate-502-not-silently-zero]] (类似: BFF 透传 + 不掩盖错)
- 关联 [[feedback-must-test-both-ends]] (前端改了 fetch URL 逻辑, 必须端到端在浏览器验证)
