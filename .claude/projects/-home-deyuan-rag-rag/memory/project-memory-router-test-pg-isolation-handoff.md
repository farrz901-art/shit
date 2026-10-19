---
name: project-memory-router-test-pg-isolation-handoff
description: "tests/memory/test_router.py 11 个 test 走真实 PG, 走 handoff 留给后续 (2026-06-17)"
metadata: 
  node_type: memory
  type: project
  originSessionId: 161305b2-7914-4a2d-beb5-1204cac2f2a4
---

`tests/memory/test_router.py` 的 11 个 test (`test_*_dev_mode` 系列) 设 `RAG_DEV_AUTH=true` → `resolve_user` → `_ensure_dev_user` → `session_scope` → `get_engine` 实际连 dev PG, 跟 docker 实际密码 `deyuan888` 冲突 → 11 failed. 跟 [[2026-06-16-test-isolation]] 的 pre-existing 30+ 失败同一类. 修法推荐在 `app_with_memory` fixture 加 `monkeypatch.setattr(auth, "_ensure_dev_user", lambda: None)` (1 行). 完整 handoff 见 `docs/superpowers/handoffs/2026-06-17-memory-router-test-pg-isolation.md`.

**Why:** 用户 2026-06-17 明确说 "走 handoff 留给后续", 不在 en_core_web_sm 修根因 spec 内一并修.

**How to apply:** 下次碰到 memory router test 失败, 别再花时间修, 直接看 handoff. 想修就改 fixture, 别动 `resolve_user` 业务代码 (生产 dev mode 还靠它创 dev user).
