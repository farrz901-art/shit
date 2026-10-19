# P2 - 数据完整性与迁移 spec 草稿 (2026-06-24)

> ⚠️ 草稿, 未实施.
> 来源: [AUDIT-REPORT.md](../AUDIT-REPORT.md) §D4 Data integrity & Migrations
> 关联 checklist: [docs/audit/2026-06-24-findings.md](../../../../docs/audit/2026-06-24-findings.md)

## 范围

### Critical (3)
- DATA-001 — 20260623 migration downgrade 必失败
- DATA-002 — Account ORM/migration 约束名不一致
- DATA-003 — conversations.user_id FK 缺 ondelete

### High (5)
- DATA-004 — accounts.role 无 FK 跟 lookup 字典
- DATA-005 — buyer_profiles FK 缺 ondelete
- DATA-006 — buyer_profiles.status 硬编 String
- DATA-007 — chat_shares 类型 / 长度跟实际表不匹配
- DATA-008 — JSONB 字段无 Pydantic schema

### Medium (3)
- DATA-009 — Dictionary ORM/migration UniqueConstraint 名不一致
- DATA-010 — ingest_tasks / kg_audit 无 FK
- DATA-011 — dictionaries_seed.yaml 路径文档不一致

合计 11 条 finding.

## 修复策略

### Phase 1 (1 周) — 修 migration 必崩

1. **DATA-001**: 20260623 migration downgrade 重写: 用 `WITH (col_default) AS (UPDATE ...)` 先回填再 DROP, 避免 `server_default=0` 跟 UNIQUE 冲突.
2. **DATA-002**: Account ORM `email_format` → `ck_accounts_email_format`, `idx_accounts_email` → `ix_accounts_email`, 跟 migration 对齐. 加 CI 步骤 `uv run alembic check` 验 drift.
3. **DATA-003**: 加 migration `20260624_000000_add_conversations_user_fk_ondelete.py` (CASCADE, 跟 GDPR 删账号流程一致).

### Phase 2 (2 周) — FK 完整性 + lookup 字典

4. **DATA-004 + DATA-006**: roles / status 走 lookup 字典模块, 加 `roles` dictionary seed, 改 migration 加 FK.
5. **DATA-005**: buyer_profiles / profile_change_logs / profile_field_configs 3 张表 FK 全加 ondelete CASCADE.
6. **DATA-007**: chat_shares 改用 `conv_id: Mapped[str] = mapped_type(String(36), ForeignKey("conversations.id", ondelete="CASCADE"))`, user_id 改 Integer.
7. **DATA-008**: profile_data / change_logs JSONB 字段加 Pydantic schema, 在 `buyer_profile/schemas.py` 集中定义.

### Phase 3 (持续) — 残留清理

8. **DATA-009**: Dictionary ORM `uq_dict_item` → `uq_dictionary_items_dict_code_key`, 跟 migration 对齐.
9. **DATA-010**: ingest_tasks / kg_audit 加 user_hash FK (或注: 设计上是匿名, 接受无 FK, 加 docstring 注明).
10. **DATA-011**: README 改 `config/dictionaries_seed.yaml` 路径 (跟实际一致).

## 不在本文范围

- 实施代码 (留到 plan + implement 阶段)
- P0/P1/P3/P4 其他维度 finding
- buyer_profile 整模块重构成 ORM model (技术债, 走 P4)

## 验收标准

- 11 条 finding 全部 verified=true
- `uv run alembic upgrade head && uv run alembic downgrade -1` 全部成功
- `uv run alembic check` 0 drift
- JSONB 字段 100% 有 Pydantic schema
- lookup 字典覆盖率 ≥ 90% (业务 enum 走字典)
- pytest 模式 2 覆盖 11 个 migration 全部路径
