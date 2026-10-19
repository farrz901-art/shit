---
name: feedback-test-must-be-100pct-mock-no-real-db
description: "Test 必须 100% mock, 0 真实 DB 连接 (包括 db_session 事务回滚也算\"碰\"), CLAUDE.md 强制规则"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: d365816f-f987-4fea-93d9-5415bde993bf
---

Test 必须 100% mock, 0 真实 DB 连接. 包括 db_session 事务回滚 — "连上又回滚" 也算碰.

**Why**: 2026-06-16 test isolation spec 用户纠错, CLAUDE.md 加规则 "不要连接真实数据库, 数据库 session 通过参数注入, 测试时传 Mock 对象, 只测试业务逻辑不测试 SQL 细节". 用户原话 "B, 反正禁止有一丁点清表的风险, 禁止碰数据库". 即使事务回滚 0 数据残留, "连 PG" 这个行为本身也禁止.

**How to apply**:
- 写新 test 用 mock (TestClient + dependency_overrides + AsyncMock + patch, 跟 tests/approvals/test_router.py 同一套)
- 已有 test 用 real DB (session_scope / db_session) 改成 mock
- db_session 模式 2 (事务回滚) **作废**, 即使 rollback 0 影响, 也不能连
- 模式 3/4 (临时 schema / 独立 DB) 也不接受 (虽然隔离, 但还连 PG)
- 跟 test_health_pgvector_env 那种验 env 解析 / connection string 的 test 区别: 那测不连, 只验 env → 保留
- 跑 test 完全不需要 `RAG_DB_URL`, 也不需要 alembic 跑过
- 简化: 跑 test 不用启 docker PG, 不用 alembic, 不用任何 DB 基础设施

**Test isolation 4 模式** (CLAUDE.md 已文档化, 但**仅适用**真要连 PG 的少数情况, 99% test 走模式 1):
- 1 纯单测 mock (99%, 强制)
- 2 集成事务回滚 (基本不用, 用户禁止连 DB)
- 3 临时 schema (不用)
- 4 独立 DB (不用, CI 阶段再说)
