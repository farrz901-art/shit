# P2 - 数据完整性 spec 草稿 (2026-06-26)

> ⚠️ 草稿, 未实施.
> 来源: [AUDIT-REPORT.md](../AUDIT-REPORT.md) §Data integrity (D4) + Concurrency (D2 数据相关)
> 关联 checklist: [docs/audit/2026-06-26-findings.md](../../../../docs/audit/2026-06-26-findings.md)

## 范围

### 未 verify
- DATA-002 (medium) — approvals.models FK ondelete 未在 ORM 模型中表达
- DATA-003 (medium) — accounts.role / buyer_profiles.status 硬编码 CHECK 约束而非 lookups
- DATA-004 (medium) — 多个 JSONB 字段无 Pydantic schema 校验
- DATA-005 (low) — profile_change_logs.account_id FK 缺 B-tree 索引
- DATA-006 (medium) — chat_shares 初始 migration 未定义 FK 且列类型不匹配
- CONC-004 (medium) — Eval 取消信号跨 worker 失效
- CONC-005 (low) — Evaluation.status 无 CHECK 约束 (状态机)
- CONC-006 (low) — OFFSET pagination 漂移

### Refuted (排除)
- DATA-001 (high) — evaluations.user_id FK (故意 scope 限定, 20260624_120000 docstring 写明留后续)

## 修复策略

### 1. FK 表达完整性
- approvals.models 的 FK ondelete 在 ORM 模型中显式声明
- profile_change_logs.account_id 加 B-tree 索引

### 2. Enum 唯一事实源
- accounts.role / buyer_profiles.status 从硬编码 CHECK 约束迁移到 lookups 模块
- 新增 migration 改约束

### 3. JSONB Schema
- eval / approvals 的 JSONB 字段加 Pydantic model 校验
- 迁移: add column validation before write

### 4. Migration 修复
- chat_shares 初始 migration 修复 FK 定义
- 验证: upgrade+downgrade+upgrade 三遍回滚

### 5. 并发韧性
- Eval 取消信号改 Redis pub/sub (跨 worker)
- Evaluation.status 加 DB CHECK 约束
- Pagination 改 keyset pagination (WHERE updated_at < :cursor)

## 不在本文范围
- DATA-001 (refuted) — 排除
- P0/P1/P3/P4 finding
