---
name: feedback-rag-admin-token-bootstrap-only
description: "RAG_ADMIN_TOKEN / x-admin-token 是 bootstrap 一次性通道, 业务 100% 走 x-user-token, 前端 cookie rag_admin_token 永远 undefined 是死代码"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 623e8a0b-5f11-4892-8333-52384121101e
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
6. **清理死代码要 grep 完整**: spec 列了 4 处, grep 后还发现 7 处残留 (3 test mock + 4 注释) — spec coverage gap, 需补 Task 9
7. **改 test mock 不要凭空捏造 token 值**: 改 `key === "rag_admin_token"` 整 if 块时, 看清原 if 块结构: 只匹配 admin → 删整块 (L24-28); 匹配 admin OR user → 改 key (submissions L24)
