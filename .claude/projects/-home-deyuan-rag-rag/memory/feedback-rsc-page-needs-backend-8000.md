---
name: feedback-rsc-page-needs-backend-8000
description: "RSC 页面 server 端 fetch 后端 (port 8000) 失败时报 \"Unable to connect. Is the computer able to access the url?\" (node-fetch v2 错误格式), 跟 Turbopack panic 区分. 根因 = 后端没起, 不是代码 bug."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 298dc759-254d-43ee-a841-71ccb0b25682
---

RSC 页面 (e.g. `/zh/knowledge/documents`, `/zh/knowledge/dashboard`, `/zh/knowledge/graph`) 在 server 端调 `rscGet<...>("/api/kg/...")` → `apiFetch` → `fetch("http://localhost:8000/...")` (Node.js RSC 用 node-fetch v2).

**后端 (FastAPI, port 8000) 没启动时**:
- 浏览器报 `FetchError: request to http://localhost:8000/api/kg/stats?type=dify failed, reason: Unable to connect. Is the computer able to access the url?` (node-fetch v2 特定格式, **不是浏览器错也不是 Turbopack panic**)
- 错误通过 Next.js dev overlay 透传到浏览器, 用户看到的就是这句
- 区分: 跟 [[feedback-turbopack-postcss-panic-10054]] 不同, 那个是 `os error 10054` + PostCSS worker 死; 这个是后端没起

**Why**: 2026-06-15 用户访问 `/zh/knowledge/documents` 报 "Unable to connect. Is the computer able to access the url?". 排查发现 dev server (3000) 返 200, **后端 (8000) curl exit 7** (无法连接). RSC 页面 server-side fetch 调后端, 后端没起 → fetch 失败 → node-fetch 抛上面那条错.

**How to apply**:
- 看到 `Unable to connect. Is the computer able to access the url?` (后面跟 URL 形如 `http://localhost:8000/...`): **后端没起, 不是代码 bug**
- 验证: `curl http://localhost:8000/api/kg/stats?type=dify` → exit 7 = 后端 down
- 修复: 启动后端 `cd packages/service && uv run python main.py` (同时 [CLAUDE.md](packages/web/CLAUDE.md) 提示 dev 模式要开 2 个终端: 前端 + 后端)
- 跟 [[feedback-turbopack-postcss-panic-10054]] 区分: `os error 10054` 是 PostCSS worker 死 (前端问题, 重启 dev server), `Unable to connect ...localhost:8000` 是后端没起 (后端问题, 启动后端)
- 关联 [[feedback-debug-distinguish-root-causes]] (TCP 连接错有 2 类: 前端 dev server 内部 worker 死 vs 外部后端服务没起, 看 panic log 的 URL 区分)
