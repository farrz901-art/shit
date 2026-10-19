---
name: feedback-audited-wrapper-await-sync-handler
description: "@audited wrapper 兼容同步 handler, sync def 不能 await, 必须用 inspect.isawaitable 区分"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 8db049b2-35ef-4ba6-8d32-cb13c9b105fa
---

@audited decorator (src/core/audit.py) 的 wrapper 一律 await func(...) 是错的,
必须 inspect.isawaitable() 区分 sync / async handler.

**Why:** 2026-07-03 真实事故 /api/kg/extract/start 500. 根因: kg/router.py 的 4 个
端点 (start_extract / patch_extract_items / commit_extract / export_extract) 全
是 def 同步, 返回 dict / StreamingResponse, await dict → TypeError. 其他 audited
路由 (chat / auth / lookups / buyer_profile / memory / ingest / eval) 全 async
def, 这次没踩所以长期未暴露. 单元测试 test_audit.py 用 async def fake_endpoint,
也从未覆盖 sync 路径.

**How to apply:**
1. 写 async wrapper 包任意 handler, 一律要 `inspect.isawaitable(value)` 判断
2. 加 `-> Any` 让 pyright 不反推 handler 返回类型, 避免业务代码 type: ignore
3. decorator 写完必须补 1 个 sync def 端点测试, 防回归
4. 加 @audited 之前确认 handler 是 sync 还是 async, 端点签名是 `def` 还是 `async def`
5. 见 [[feedback-no-shim-no-minimal-changes]] — 修根因不绕开
