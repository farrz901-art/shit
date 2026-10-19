---
name: feedback-server-action-fetch-needs-explicit-content-type
description: "Next.js server action 用原生 fetch 调 FastAPI 必须显式带 Content-Type: application/json, 否则 Pydantic 422 model_attributes_type; 测试要断言 header 完整性"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 1f31d195-59f7-46d2-9621-643c2a513cbb
---

Next.js server action ("use server") 里用原生 `fetch()` POST JSON 到 FastAPI 后端时, **必须显式带 `Content-Type: application/json` header**, 不能只传 `body: JSON.stringify(...)`. 否则:

- FastAPI/Starlette 不按 JSON 解析 body
- Pydantic 收到的是 `JSON.stringify(body)` 出来的整个**字符串字面量** (不是 dict)
- 报 `HTTP 422 {"type":"model_attributes_type","msg":"Input should be a valid dictionary or object to extract fields from","input":"{\"rows\":[...]}"}`
- 关键识别特征: 报错的 `input` 字段是 **JSON 字符串字面量** (被反斜杠转义), 说明 body 整个被当字符串收了

**Why**: client 端有 `clientFetch()` ([packages/web/lib/api/auth.ts](packages/web/lib/api/auth.ts)) 自动补 Content-Type, 但 server action 不能用它 (clientFetch 是 client-only, 用 window/localStorage). server 端自己写 `fetch()` 时容易漏掉 Content-Type, 而 FastAPI 没 Content-Type 时不会自动按 JSON 解析.

**How to apply**:
1. 任何 server action 里手写 fetch POST/PUT JSON 时, headers 必须包含 `"Content-Type": "application/json"` —— 跟 auth headers 并列, 不能只传 auth:
   ```ts
   headers: {
     "Content-Type": "application/json",
     ...(await authHeaders()),
   }
   ```
2. 对应单元测试 (vitest) 必须断言 fetch 调用带 Content-Type, 不能只断言 auth token header:
   ```ts
   const headers = init?.headers as Record<string, string>;
   expect(headers["Content-Type"]).toBe("application/json");
   expect(headers["x-user-token"]).toBe("test-tok");
   ```
3. 多 action 共享 `postJson` helper 时一个 helper 修好 + 一个测试 case 断言就覆盖全部 action (如 [packages/web/app/[locale]/_actions/knowledge.ts](packages/web/app/[locale]/_actions/knowledge.ts) 的 createQA/createTriples/commitDocuments).
4. server action 测试文件必须 `vi.mock("server-only", () => ({}))`, 否则 import 链碰到 `import "server-only"` 直接 throw (vitest 跑在 jsdom 环境算 client).

**当时漏掉的原因**: 重构 BFF → server action 时把 fetch 抄了一份但没参考 `clientFetch` 自动加 Content-Type 的逻辑, husky 测试只断言了 auth header 没断言 Content-Type, 一路绿到生产才 422.

关联: [[feedback-must-test-both-ends]] (前后端都要测) · [[feedback-tdd-test-real-behavior-not-just-no-crash]] (测真行为不只是不崩) · [[feedback-front-end-api-must-have-tests]] (前端 API 必须有测试) · [[feedback-bff-must-propagate-502-not-silently-zero]] (BFF 错误必须传播)
