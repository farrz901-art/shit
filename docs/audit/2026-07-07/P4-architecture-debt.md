# P4 — 架构债务 修复 spec 草稿 (2026-07-07)

> ⚠️ 草稿, 未实施. 来源: [AUDIT-REPORT.md §D6 §D2-non-security](../AUDIT-REPORT.md)

## 范围
- **CONC-004** (high, verified) — APScheduler 多实例 cron 重复执行
- **CONC-005** (high, verified) — append_message 无 client_msg_id 唯一约束
- **ARCH-002** (high, verified) — memory-management-dialog.tsx 378 行超限
- **ARCH-003** (high, verified) — kg/router.py 1045 行 5 职责混合
- D6 其余 6 条 medium/low (ARCH-004/005/006/007/008/009/010)

## 修复策略

### 1. Scheduler 分布式化 (CONC-004)
- 改 `AsyncIOScheduler` → `BackgroundScheduler` + `SQLAlchemyJobStore("postgresql+psycopg://...")`
- 全实例共享同一 jobstore, 调度表加 unique constraint 防止重复 trigger
- 验证: 多 worker 起动, 03:00 任务只跑 1 次

### 2. Chat Message 幂等 (CONC-005)
- `messages` 表 schema 加 `client_msg_id` (UUID) + unique `(conversation_id, role, client_msg_id)`
- 客户端发消息时生成 client_msg_id (UUIDv7), retry 重发用同 id
- server `append_message` 走 INSERT ON CONFLICT DO NOTHING

### 3. memory-management-dialog 拆分 (ARCH-002)
- 拆 4 文件: < 200 行/文件
  - `memory-management-dialog.tsx` (主 dialog UI)
  - `memory-list.tsx` (列表)
  - `memory-edit-form.tsx` (编辑)
  - `use-memory-state.ts` (state hook)

### 4. kg/router 拆分 (ARCH-003) — 大型重构
- 拆 5 文件:
  - `kg/router.py` (FastAPI endpoints, 瘦身后 ~250 行)
  - `kg/schema.py` (Pydantic TripleRowIn / TriplesRequest)
  - `kg/cypher.py` (Cypher utils: datasets, templates, client)
  - `kg/extractor.py` (提取触发)
  - `kg/audit.py` (audit store 单例)

## 不在本文范围
- 实施代码
- D2 中等及以下 finding (在 P1/P2 spec)
- ARCH-001 已 refuted
