---
name: project-server-action-bff-vs-direct-route
description: 区分 server action 该走 BFF (同源) 还是直连 FastAPI (${API_BASE}) 的判断标准; 2026-06-12 调试 /api/knowledge/qa 404 时发现 createQA 误直连 BFF-only 路径
metadata:
  node_type: memory
  type: project
  originSessionId: 676c65bd-7a50-4699-97de-77c402b8b1d8
---
**Next.js server action (app/[locale]/_actions/*) 调后端时, 怎么判断该走 BFF (同源 /api/...) 还是直连 FastAPI (${API_BASE}/api/...)?**

**Why:** 2026-06-12 调试 /api/knowledge/qa 404:
- 现象: 前端 QASubmitForm 提交后报错 404
- 根因: [_actions/knowledge.ts:48-54](packages/web/app/[locale]/_actions/knowledge.ts#L48-L54) `createQA` 用 `${API_BASE}/api/knowledge/qa` 直连 FastAPI, 但 `/api/knowledge/*` 路由族**只在 Next.js BFF** (app/api/knowledge/qa/route.ts) 存在, FastAPI 端 `register_routers` 注册的 prefix 是 `/api/kg/*`, `/api/auth/*`, `/api/evaluate/*`, `/api/ingest/*`, `/api/health/*`, `/api/v1/*` —— **没有 /api/knowledge/***

**判断标准 (按调用对象分类):**

| 调用对象 | 走法 | 例子 |
|---|---|---|
| FastAPI 真实端点 (有 /api/xxx 在后端) | `${API_BASE}${path}` 直连 | `/api/kg/stats`, `/api/kg/triples`, `/api/evaluate/runs`, `/api/auth/migrate` |
| Dify 第三方 API 或需要服务端中转 (multipart / 流式 / 跨域 cookie) | 同源 BFF `/api/...` | `/api/knowledge/qa`, `/api/knowledge/qa/retrieve`, `/api/knowledge/documents/commit`, `/api/knowledge/documents/upload`, `/api/knowledge/batch` |
| RSC 拉数据 (server component 内 fetch) | `${API_BASE}${path}` 直连 + `authHeaders()` 注入 token | 跟 server action 直连同 |

**How to apply:**
- 写新 server action 前, 先 `curl localhost:8000<path>` 验证后端有没有这个路由
- 后端有 → `${API_BASE}${path}`
- 后端没有但 Next.js BFF 有 → 同源 `/api/...`
- 不确定 → 查 `register_routers` 实际注册的 prefix 列表, 查 `web/app/api/` 现有 BFF 文件

**当前已知的路由族错配 (2026-06-12 调试时确认):**
- `/api/knowledge/*` → BFF only
- `/api/kg/*` → FastAPI only
- 这两套虽然都跟"知识库"相关, 但实现位置不同. 历史上**知识图谱 CRUD**走 `/api/kg/*` (Neo4j), **QA 对录入 / 文档导入** 走 `/api/knowledge/*` (Dify 中转)

**未修但同 bug 的位置 (用户没要求改, 待处理):**
- [_actions/knowledge.ts:103-109](packages/web/app/[locale]/_actions/knowledge.ts#L103-L109) `commitDocuments` 同样 `${API_BASE}/api/knowledge/documents/commit` → 404
- 修复: 调 `postJson("/api/knowledge/documents/commit", input, { base: "" })`

**contract test 增强建议 (未实施):**
- `tests/test_api_contract.py::FRONTEND_EXPECTS` 目前只列前端直连 FastAPI 路径, 不覆盖 server action 拼的路径
- 应该加一份 `SERVER_ACTION_EXPECTS` 列 server action 调的所有 `${API_BASE}/api/...` 路径, 跟 BFF 路径分两套断言
- 否则下次还会出现"server action 拼了个 BFF-only 路径, 直连 404" 这种 bug, contract test 抓不到

**关联:**
- [[feedback-bff-must-propagate-502-not-silently-zero]] — BFF 错误传播
- [[project-rag-shim-audit-2026-06-08]] — 业务路径命名不统一 (knowledge vs kg) 是历史债
- [[feedback-uvicorn-must-restart-after-route-add]] — 加 router 后 uvicorn 不 reload
