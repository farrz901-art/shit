// API 模块对外 API (2026-06-14) 批量出口
//
// ============================================================
// 调用边界 (calling-boundary, 2026-06-19 audit)
// ============================================================
// `lib/api/` 跨 3 种调用边界, 各业务模块在函数 JSDoc 上自标注:
//   - `@client-bff`    浏览器端调用, 必须从 'use client' 组件用;
//                       走 Next.js BFF (专用 /api/* route 或 [...path] catch-all), cookie 自动带.
//                       典型场景: useQuery / useMutation 的 queryFn / mutationFn, 文件上传, 鉴权写操作.
//   - `@server-only`   仅 RSC / server action / route.ts 可用, 必须显式传 `headers` (auth token).
//                       直连 FastAPI, 绕过 BFF. 典型场景: 服务端 prefetch, server action, 拉初始数据.
//   - `@shared`        浏览器或 server 都可用. 浏览器走 BFF catch-all, server 直连 FastAPI.
//                       典型场景: 纯读 API, 列表/详情/统计查询, 鉴权要求不严.
// 选择依据: 函数接 `headers` 参数 = server 注入 token → server-only;
//           无 headers + URL 是专用 /api/* BFF route = client-bff;
//           无 headers + URL 是 /api/kg/* (无 BFF, 走 catch-all) = shared;
//           URL 工厂 (返字符串不发请求) = shared.
// 已 audit 标注: approvals.ts / evaluate.ts / knowledge.ts.
// 待 audit: account.ts / auth.ts / buyer-profile.ts / chat.ts / chat-share.ts /
//           health.ts / ingest.ts / lookups.ts / memory.ts / permissions.ts /
//           users.ts / system.ts (后续 task).
//
// (2026-06-14) server-only / next/headers 模块不走 barrel:
//   - auth.server (顶层 import "server-only" + "next/headers")
//   - rsc-queries (顶层 import "server-only")
//   即便只 export 某个 alias (serverAuthHeaders), ES module 静态解析仍会加载
//   源文件, 触发 server-only throw 跟 next/headers Pages Router 报错. 任何
//   拉 barrel 的 client component 链式触发 build error.
//   解法: server 端代码直连 "@/lib/api/auth.server" / "@/lib/api/rsc-queries".
//   跟 RSC + server actions 模式自然分离 (client 不该用).
//   Vitest 防御 (vitest.setup.ts): mock server-only + next/headers, 让 client
//   测试即使用到这些模块名也不会报错.
export * from "./account";
export * from "./approvals";
// Auth.ts / auth.server.ts: 不走 barrel (auth 已删, auth.server 是 server-only + next/headers)
export * from "./auth";
export * from "./buyer-profile";
export * from "./chat";
export * from "./chat-share";
export * from "./config";
export * from "./errors";
export * from "./evaluate";
export * from "./health";
export * from "./ingest";
export * from "./knowledge";
export * from "./lookups";
export * from "./memory";
export * from "./permissions";
export * from "./query-client";
export * from "./query-keys";
// Rsc-queries: 不走 barrel (server-only)
export * from "./system";
export * from "./users";
