---
name: feedback-bff-must-propagate-502-not-silently-zero
description: "BFF (Next.js route.ts) 调下游 API 失败时必须显式 check r.ok + 返 502, 不能用 ?? 0 静默兑底 — 隐藏错误让调试极费时"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: eec4f205-4669-4734-b77f-77c2e0b18e11
---

BFF 调下游 (FastAPI / 别的 service) 时, **必须显式 `if (!r.ok) return NextResponse.json({error: ...}, {status: 502})`**, 不能 `await r.json()` + `?? 0` 兜底.

症状:
- 下游 500/502 时, BFF `r.json()` 拿到 `{"detail": "Internal Server Error"}` — 不是抛错, 所以 `try/catch` 抓不到
- `counts.Product ?? 0` → 全 0
- 前端 useSWR 走 success 分支, 用户看到 "Product=0, Series=0" 以为"知识库是空的"
- 实际后端 Neo4j 挂了, 排查要 1 小时才发现"数字全是兜底的"

**Why:** fetch 在 4xx/5xx 时不抛, response.ok=false. `r.json()` 仍然能 parse. `?? 0` 把 {"detail": "..."} 里的数字字段全变 0.

**How to apply:**
- BFF 调下游第一行就是 `if (!r.ok) return NextResponse.json({error: ...}, {status: 502})`
- mock 测试要 verify: 下游返 500 → BFF 返 5xx + 错误体 (不是 200 + 全 0)
- mock `Response` 对象必须同时给 `ok/status/json/text` (因为代码可能调 text)
- 兜底 0 是合理的, 但只在 BFF **自己** parse 失败 (catch 块) 时用, 不能覆盖下游错误
