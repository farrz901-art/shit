// ============================================================
// 调用边界 (calling-boundary, 2026-06-30 audit)
// ============================================================
// `lib/chat/` 跨 2 种执行边界, 顶部 marker 标记:
//   - `"use client"`           文件仅在浏览器执行 (Dexie IDB / React hooks /
//                              localStorage / TanStack Query hooks).
//   - `import "server-only"`   文件仅在 server 执行 (BFF route / RSC), 走
//                              process.env secret / next/headers cookies().
//                              vitest setup 已 mock server-only 为空模块.
//   - (无 marker)              shared — 纯类型 / 纯函数, 不读 env 不碰 DOM.
// 选择依据: 模块含 Dexie / IDB / useState / useEffect / window / localStorage
//           / TQ hooks = client-only;
//           模块含 next/headers / process.env secret / apiProxy 调外部 = server-only;
//           纯 type 或 async generator = shared.
//
// 13 文件 boundary 清单 (2026-06-30):
//   - api.ts                 client     (TQ hooks)
//   - use-chat-state.ts      client     (React hooks 集合)
//   - migration.ts           client     (useEffect + localStorage + sonner)
//   - db.ts                  shared*    (Dexie ChatDB module-level new, 不加
//                                       marker — 防止 server bundle 拉入
//                                       indexedDB; 仅 client 代码 import)
//   - storage.ts             shared*    (re-export ./db, 同上)
//   - chat-utils.ts          shared*    (混 localStorage + 纯函数, 拆文件后
//                                       再分别加 marker, 见 2026-06-30 plan)
//   - dify.ts                server     (process.env DIFY_* + apiProxy)
//   - factory.ts             server     (process.env CHAT_PROVIDER)
//   - memory-integration.ts  server     (next/headers cookies + 记忆 fetch)
//   - openai.ts              server     (process.env OPENAI_* + apiProxy)
//   - sse.ts                 shared     (async generator)
//   - types.ts               shared     (纯类型)
//   - index.ts               shared     (barrel)
//
export * from "./dify";
export * from "./factory";
export * from "./openai";
export * from "./storage";
export * from "./types";
