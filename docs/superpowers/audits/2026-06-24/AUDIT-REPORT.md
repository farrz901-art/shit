# 全栈审计报告 (2026-06-24)

> 来源: 6 维度并行扫描 + 主线程 adversarial verify
> 原始 finding: [d1-security.md](d1-security.md) ... [d6-arch.md](d6-arch.md)
> 日常维护 checklist: [docs/audit/2026-06-24-findings.md](../../../docs/audit/2026-06-24-findings.md)

## 元信息

- **扫描时间**: 2026-06-24
- **维度**: 6 (Security / Concurrency / Error / Data / Frontend / Architecture)
- **总 finding**: 62
- **verified**: 61
- **refuted / 降级**: 1 (SEC-001)
- **重复**: 1 (ARCH-001 ⊂ FE-001~011)
- **跨维度 dedup**: 1 (ARCH-001 → 归到 D5)
- **净 finding**: 60

### Severity 分布

| 维度 | critical | high | medium | low | 合计 |
|---|---|---|---|---|---|
| Security (D1) | 2 (SEC-001 降级后) | 3 | 2 | 1 | 8 |
| Concurrency (D2) | 2 | 4 | 3 | 0 | 9 |
| Error handling (D3) | 0 | 3 | 4 | 2 | 9 |
| Data integrity (D4) | 3 | 5 | 3 | 0 | 11 |
| Frontend (D5) | 2 | 9 | 1 | 0 | 12 |
| Architecture (D6) | 0 (1 dedup) | 4 | 4 | 2 | 10 (ARCH-001 归 D5) |
| **合计** | **9** | **28** | **17** | **5** | **59** (dedup 后) |

### 已知缺口 (后续 spec 补)

- D1: 未跑 `uv run pip-audit` + `bun audit --production` 查 deps CVE 库
- D2: orchestration/retrieval/product_decoders 内部并发未深入
- D3: PII scrub 字段清单 (logging.py:22) 缺运行时测试
- D5: i18n key 完整性 (zh.json vs en.json 999 行), a11y 全量, useEffect cleanup 全量, bundle 体积/dynamic import 全量
- D6: 测试覆盖率 (各 module 实际 74.1% 已知, 未扫哪些 module 缺测)

---

## 汇总表 (按 severity 降序)

> ✅ = verified, ⚠️ = 降级 (refuted / 重复), 🔍 = 主线程人工 review 重点

### Critical (9)

| ID | 维度 | 标题 | file:line | verified | 备注 |
|---|---|---|---|---|---|
| SEC-002 | security | chat_share presign path traversal | `packages/service/src/chat_share/router.py:293` | ✅ | 已 verify, 经典 presign 越权 |
| SEC-003 | security | kg/router stats / health 无鉴权 | `packages/service/src/kg/router.py:103` | ✅ | 已 verify, 已文档化"内部用", 降级风险依赖部署 |
| CON-001 | concurrency | invite redeem 双重 session TOCTOU | `packages/service/src/auth/auth_invite_router.py:115` | ✅ | 经典 TOCTOU, 业务翻译 409→500 |
| CON-002 | concurrency | cancel_deletion 缺锁 + cron 误删 | `packages/service/src/auth/account_settings_service.py:188` | ✅ | 双 bug 集中, 必修 |
| DATA-001 | data | 20260623 migration downgrade 必失败 | `packages/service/src/storage/migrations/versions/20260623_000000_drop_account_id_from_field_configs.py:31` | ✅ | `server_default=0` + UNIQUE 冲突 |
| DATA-002 | data | Account ORM / migration 约束名不一致 | `packages/service/src/auth/account_models.py:36` | ✅ | alembic autogenerate 必出 diff |
| DATA-003 | data | conversations.user_id FK 缺 ondelete | `packages/service/src/storage/migrations/versions/20260615_000000_consolidated_pg_init.py:114` | ✅ | 跟 GDPR 删账号流程冲突 |
| FE-001 | frontend | evaluate-new-form useRouter 违规 | `packages/web/app/[locale]/evaluate/new/_components/evaluate-new-form.tsx:21` | ✅ | 跟 login/invite 已修同模式 |
| FE-002 | frontend | output/new useRouter 违规 | `packages/web/app/[locale]/output/new/page.tsx:22` | ✅ | 同上 |

### High (28)

| ID | 维度 | 标题 | file:line | verified | 备注 |
|---|---|---|---|---|---|
| SEC-004 | security | PII scrub 19 字段散落 | `packages/service/src/core/logging.py:22` | ✅ | 跨模块重复, 应集中 |
| SEC-005 | security | CORS allow_origins env 默认 + localhost | `packages/service/src/core/app_factory.py:125` | ✅ | ENV=production 未剔除 dev |
| SEC-006 | security | 前端 bundle 误用 process.env (OPENAI_API_KEY) | `packages/web/lib/chat/openai.ts:9` | ✅ | 跟 ARCH-003 互补 (D6 架构层, D1 具体点) |
| CON-003 | concurrency | verify_email_change TOCTOU | `packages/service/src/auth/account_settings_service.py:121` | ✅ | |
| CON-004 | concurrency | buyer_profile JSONB RMW 缺锁 | `packages/service/src/buyer_profile/service.py:63` | ✅ | 跨 session 丢字段 |
| CON-005 | concurrency | run_evaluation cancel_event 不持久化 | `packages/service/src/eval/runner.py:158` | ✅ | |
| CON-006 | concurrency | finalize_upload 状态机缺原子 | `packages/service/src/ingest/api.py:358` | ✅ | 重复 add_task |
| ERR-001 | error | evaluator 静默吞错返 None | `packages/service/src/eval/llama_eval.py:109` | ✅ | |
| ERR-002 | error | memory search/list 异常吞 | `packages/service/src/memory/service.py:134` | ✅ | |
| ERR-005 | error | Dify 集成无 retry / 超时 | `packages/service/src/integrations/dify_datasets.py:42` | ✅ | 偶发 5xx |
| DATA-004 | data | accounts.role 无 FK 跟 lookup 字典 | `packages/service/src/storage/migrations/versions/20260617_000000_add_roles_and_rbac.py:27` | ✅ | 违反 CLAUDE.md 强制规范 |
| DATA-005 | data | buyer_profiles FK 缺 ondelete | `packages/service/src/storage/migrations/versions/20260622_000000_create_buyer_profiles.py:43` | ✅ | |
| DATA-006 | data | buyer_profiles.status 硬编 String | `packages/service/src/storage/migrations/versions/20260622_000000_create_buyer_profiles.py:31` | ✅ | 违反 lookup 唯一事实源 |
| DATA-007 | data | chat_shares 类型 / 长度跟实际表不匹配, 无 FK | `packages/service/src/chat_share/models.py:23` | ✅ | |
| DATA-008 | data | JSONB 字段无 Pydantic schema | `packages/service/src/storage/migrations/versions/20260622_000000_create_buyer_profiles.py:32` | ✅ | |
| FE-003 | frontend | run-detail-view useRouter 违规 | `packages/web/app/[locale]/evaluate/[id]/_components/run-detail-view.tsx:21` | ✅ | |
| FE-004 | frontend | evaluate-list-view useRouter 违规 | `packages/web/app/[locale]/evaluate/_components/evaluate-list-view.tsx:15` | ✅ | |
| FE-005 | frontend | submissions-tabs useRouter 违规 | `packages/web/app/[locale]/submissions/_components/submissions-tabs.tsx:11` | ✅ | |
| FE-006 | frontend | permissions-admin-client useRouter 违规 | `packages/web/app/[locale]/admin/permissions/_components/permissions-admin-client.tsx:19` | ✅ | |
| FE-007 | frontend | message-feedback useRouter 违规 | `packages/web/components/chat/message-feedback.tsx:11` | ✅ | |
| FE-008 | frontend | reset-password useRouter 违规 | `packages/web/app/[locale]/reset-password/page.tsx:5` | ✅ | |
| FE-009 | frontend | back-link 封装组件 useRouter 违规 | `packages/web/components/common/back-link.tsx:12` | ✅ | **全局封装组件, 影响范围最大** |
| FE-010 | frontend | settings-dialog useRouter 违规 | `packages/web/components/settings/settings-dialog.tsx:6` | ✅ | |
| FE-011 | frontend | 3 个表单 useRouter 违规 (triples/qa/import) | `triples-form.tsx:15` 等 | ✅ | |
| ARCH-002 | arch | ingest/pipeline.py 47 处 print() | `packages/service/src/ingest/pipeline.py:36` | ✅ | 违反 CLAUDE.md loguru 统一 |
| ARCH-003 | arch | os.getenv 散落 20+ 文件 | `packages/service/src/health/checks.py:269` | ✅ | 应走 config facade |
| ARCH-004 | arch | 裸 `# type: ignore` (违反 CLAUDE.md) | `packages/service/tests/lookups/test_audit.py:47` | ✅ | 必修 |
| ARCH-005 | arch | datetime.utcnow() + # type: ignore | `packages/service/src/permissions/service.py:50` | ✅ | Py3.14 deprecation |

### Medium (17)

| ID | 维度 | 标题 | file:line | verified |
|---|---|---|---|---|
| SEC-007 | security | forgot_password 无 rate limit | `packages/service/src/auth/auth_account_router.py:300` | ✅ |
| SEC-008 | security | presign_get IDOR (URI 归属) | `packages/service/src/ingest/api.py:630` | ✅ |
| CON-007 | concurrency | chat list offset 漂移 | `packages/service/src/chat/service.py:73` | ✅ |
| CON-008 | concurrency | token cache write-after-PG 无 invalidation | `packages/service/src/middleware/auth.py:162` | ✅ |
| CON-009 | concurrency | MemoryService 单例线程安全 | `packages/service/src/memory/service.py:75` | ✅ |
| ERR-003 | error | CAD 转换器 print 当日志 | `packages/service/src/ingest/converters/cad.py:304` | ✅ |
| ERR-004 | error | ingest task 失败丢 stacktrace | `packages/service/src/ingest/api.py:516` | ✅ |
| ERR-006 | error | approval executor Neo4j 失败 pass | `packages/service/src/approvals/executor.py:60` | ✅ |
| ERR-007 | error | object_store 全 except 抹错误码 | `packages/service/src/storage/object_store.py:331` | ✅ |
| ERR-009 | error | lookup cache subscriber 30s 静默 | `packages/service/src/lookups/cache.py:150` | ✅ |
| DATA-009 | data | Dictionary ORM/migration UniqueConstraint 名不一致 | `packages/service/src/lookups/models.py:79` | ✅ |
| DATA-010 | data | ingest_tasks / kg_audit 无 FK | `packages/service/src/storage/migrations/versions/20260615_000000_consolidated_pg_init.py:211` | ✅ |
| DATA-011 | data | dictionaries_seed.yaml 路径文档不一致 | `packages/service/config/dictionaries_seed.yaml:1` | ✅ |
| FE-012 | frontend | NEXT_PUBLIC_CHAT_TOKEN 公开 | `.env.example:18` | ✅ |
| ARCH-006 | arch | 4 处 TODO 提示加 @audited | `packages/service/src/api/routes.py:7` | ✅ |
| ARCH-007 | arch | `any[]` 滥用 (前 Pydantic 等价) | `packages/web/lib/api/permissions.ts:12` | ✅ |
| ARCH-008 | arch | scripts/e2e 用 console 而非 log | `packages/web/scripts/duplication-report.ts:54` | ✅ |
| ARCH-009 | arch | package.json 用 tsc 不用 tsgo | `packages/web/package.json:15` | ✅ |
| ARCH-010 | arch | package.json 缺 lint:check | `packages/web/package.json:16` | ✅ |

### Low (5)

| ID | 维度 | 标题 | file:line | verified |
|---|---|---|---|---|
| SEC-009 | security | get_invite 端点信息泄露 | `packages/service/src/auth/auth_invite_router.py:75` | ✅ |
| ERR-008 | error | embedder_ready 静默期 | `packages/service/src/retrieval/embedder.py:141` | ✅ |
| ARCH-011 | arch | SubmissionsTabs 53 行 useState 套层 | `packages/web/app/[locale]/submissions/_components/submissions-tabs.tsx:11` | ✅ |
| ARCH-012 | arch | conftest autouse mock 缺文档 | `packages/service/tests/conftest.py:1` | ✅ |

### 降级 / Refuted / 重复 (3)

| ID | 原始 | 降级 | 原因 |
|---|---|---|---|
| SEC-001 | critical | medium (confidence low) | Python 3.14 实测不报 SyntaxError (`except ValueError, TypeError:` 等价于 `except ValueError as TypeError:`, 能执行但代码仍歧义). 仍需改 `(ValueError, TypeError)`, 严重度降 medium. |
| ARCH-001 | critical | (归 D5) | 完全跟 FE-001~011 重叠 (12 个 useRouter 违规). 主修走 D5. 标 DEDUPED. |

---

## Spec 草稿映射

| 草稿 | 范围 | 严重度 | 包含 finding |
|---|---|---|---|
| [P0-security](specs/P0-security.md) | 鉴权 / 注入 / IDOR / path traversal / secret 泄露 | critical + high | SEC-002, SEC-003, SEC-004, SEC-005, SEC-006, SEC-007, SEC-008 (跟 D2 CON-001/CON-003 一起修并发安全) |
| [P1-error-resilience](specs/P1-error-resilience.md) | 静默吞错 / retry / fallback / 全局 handler | high + medium | ERR-001, ERR-002, ERR-005, ERR-003, ERR-004, ERR-006, ERR-007, ERR-009, ERR-008 |
| [P2-data-integrity](specs/P2-data-integrity.md) | migration 可回滚 / FK 完整性 / lookup 字典 | critical + high + medium | DATA-001~011 |
| [P3-frontend-quality](specs/P3-frontend-quality.md) | useRouter 违规 / 路由跳转 / bundle / a11y | critical + high | FE-001~011, FE-012 (主修 useRouter, 11+ 文件批量修) |
| [P4-architecture-debt](specs/P4-architecture-debt.md) | 规约违反 / 重复代码 / 散落 env / 类型逃避 | high + medium + low | ARCH-002, ARCH-003, ARCH-004, ARCH-005, ARCH-006, ARCH-007, ARCH-008, ARCH-009, ARCH-010, ARCH-011, ARCH-012, SEC-001 (降级) |

---

## 修复优先级建议

### 🔴 P0 立即修 (1-2 周)

1. **SEC-002 (chat_share presign path traversal)** — 经典越权写, 必修
2. **CON-001 + CON-002 (invite redeem TOCTOU + cancel_deletion 锁)** — auth 流程并发安全
3. **DATA-001 (migration downgrade 必失败)** — 当前 migration 不能回滚, 阻塞后续运维
4. **DATA-002 (ORM/migration 约束名漂移)** — alembic autogenerate 不可信
5. **FE-001 + FE-002 (useRouter critical 文件)** — 已修 login/invite 同模式, 11 个文件批量改
6. **SEC-005 (CORS ENV=production 未剔 dev)** — 部署前必修

### 🟡 P1 中期修 (1 个月)

7. **ERR-001/002/005 (静默吞错 + Dify 集成 retry)** — 业务失败无感知
8. **DATA-003 (conversations FK ondelete)** — GDPR 流程
9. **DATA-004/006 (role/status 走 lookup 字典)** — 规约违反
10. **ARCH-002/003 (print + os.getenv 散落)** — 大型重构
11. **ARCH-009 (tsc → tsgo)** — 0 风险高收益

### 🟢 P2 长期清理 (持续)

12. 其他 medium / low 项
13. SEC-001 (降级 medium, 跟 SEC-005 一起小批量修)
14. ARCH-011/012 (技术债, 增量修)

---

## 关联文档

- 原始 finding: [d1](d1-security.md) / [d2](d2-concurrency.md) / [d3](d3-error.md) / [d4](d4-data.md) / [d5](d5-frontend.md) / [d6](d6-arch.md)
- 日常 checklist: [docs/audit/2026-06-24-findings.md](../../../docs/audit/2026-06-24-findings.md)
- 修复 spec 草稿: [specs/P0-security.md](specs/P0-security.md) ... [P4-arch.md](specs/P4-architecture-debt.md)
- 设计 spec: [docs/superpowers/specs/2026-06-24-full-stack-audit-design.md](../../../docs/superpowers/specs/2026-06-24-full-stack-audit-design.md)
- 实施 plan: [docs/superpowers/plans/2026-06-24-full-stack-audit.md](../../../docs/superpowers/plans/2026-06-24-full-stack-audit.md)
