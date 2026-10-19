---
name: feedback-server-fetch-needs-absolute-url-no-host-header
description: Server action / RSC fetch 永远用绝对 URL; 相对 URL 在 Node.js fetch 报 "Invalid URL"; 拼 host 又有 host header 攻击风险; 正确解法是直调业务代码不走 HTTP
metadata:
  node_type: memory
  type: feedback
  originSessionId: 676c65bd-7a50-4699-97de-77c402b8b1d8
---
**Server action / RSC fetch URL 规则 (2026-06-12 三连教训, 调试 /api/knowledge/qa 时踩):**

1. **相对 URL 在 server fetch 上下文非法** → `fetch("/api/foo")` 在 Node.js 抛 `Failed to construct 'Request': Invalid URL`. 只有浏览器 fetch 才接受相对路径. 调试 curl 200 (走浏览器) ≠ server action 也能用.
2. **拼 `headers().get('host')` 构造绝对 URL 有 host header attack 风险** → 攻击者可改 Host 头 (X-Forwarded-Host 注入), 让 server 调 evil.com BFF → SSRF / cookie 泄露. 被 Claude Code auto-classifier 主动拒绝 (Bash 拒绝理由引用).
3. **正解: server action / RSC 直调业务代码, 不走 HTTP** → 业务代码本身在 server 端 (有 env / cookies / 进程内 state), HTTP 中转只是为了在 client-side 调. 既然 server action 已经在 server, 直接 `import { DifyDatasets }` 调就行, 无 fetch → 无 host 风险 → 无绝对 URL 问题.

**Why:** 2026-06-12 调试 /api/knowledge/qa 404:
- Phase 1 修: `createQA` 从 `${API_BASE}/api/knowledge/qa` (404) 改成 `/api/knowledge/qa` 相对路径 → 实际生产报 `Invalid URL` (Node fetch 限制)
- Phase 2 试: `getBaseUrl()` 拼 `headers().get('host')` 绝对 URL → auto-classifier 拒绝, 警告 host header 攻击
- Phase 3 终: server action `import { DifyDatasets }` 直调, BFF route 删 (8 步重构, +287/-376, 净省 89 行)

**How to apply:**

```ts
// ❌ 错: server action fetch 相对 URL (Node.js 不接受)
"use server";
async function createQA(input) {
  return fetch("/api/knowledge/qa", { ... });  // Invalid URL
}

// ❌ 错: 拼 host header (host header attack 风险)
"use server";
import { headers } from "next/headers";
async function createQA(input) {
  const h = await headers();
  const base = `${h.get("x-forwarded-proto") ?? "http"}://${h.get("host")}`;
  return fetch(`${base}/api/knowledge/qa`, { ... });  // 攻击者可改 host
}

// ❌ 错: 拼 env 静态 base (可以但不优雅, 多环境配 env 烦)
const base = process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000";
return fetch(`${base}/api/knowledge/qa`, { ... });

// ✅ 对: server action 直调业务代码, 跳过 HTTP 中转
"use server";
import { DifyDatasets } from "@/lib/dify-datasets";
async function createQA(input) {
  const doc = await DifyDatasets.createDocumentByText(...);  // server 端函数调用, 无 fetch
  return { ok: true, data: { id: doc.id, ... } };
}
```

**判断 "BFF 该不该有" 的清单:**

| 场景 | 该走 | 不该走 |
|---|---|---|
| Client 端 fetch | BFF (同源, 鉴权) | 直连 FastAPI (跨域/CORS) |
| Server action / RSC 直调 Dify/第三方 | **server 端 import 业务代码** | BFF HTTP (除非有特殊理由) |
| Multipart 上传 (大文件, 流式) | BFF (浏览器直发 FastAPI 不行) | 直调 |
| 后台任务管理 (in-memory task map) | BFF (客户端要查 status) | 直调 (客户端 fetch 不到 server 内存) |
| 同源简单 JSON 业务调用 | **server 端 import 业务代码** | BFF HTTP (多此一举, 还引 host 风险) |

**重构规则配套** (跟 [CLAUDE.md](.claude/CLAUDE.md) 一致):
- 删 BFF 前必跑 `pytest tests/test_api_contract.py` (CLAUDE.md 原文), 红了不能删
- 改前端 URL 顺序: 先后端实现路由 → 再改前端 URL → 最后删 BFF
- 严禁 shim/兼容代码/兜底包装 (见 [[feedback-no-shim-no-minimal-changes]])

**自检 (写 server action / RSC fetch 前):**
- [ ] 这是 server 端调用吗? → 直调业务代码, 别 fetch
- [ ] 必须走 HTTP 吗? → 用绝对 URL (env 配, 别拼 host header)
- [ ] 是 client 端调吗? → 走 BFF (同源) 或 `${BASE}` 直连 FastAPI
- [ ] 真要删 BFF 吗? → 跑过 contract test 绿再删, 删后无引用

**关联:**
- [[project-server-action-bff-vs-direct-route]] — server action 走 BFF vs 直连的判断标准
- [[feedback-bff-must-propagate-502-not-silently-zero]] — BFF 错误传播
- [[feedback-uvicorn-must-restart-after-route-add]] — 加 router 后 uvicorn 不 reload (同样原理: dev server 不 unload 删的 route)
- [CLAUDE.md](.claude/CLAUDE.md) 重构规则 — "删 BFF route 前必须跑契约测试"
