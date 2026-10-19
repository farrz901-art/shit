# P0 - 安全修复 spec 草稿 (2026-06-24)

> ⚠️ 草稿, 未实施. 真正实施需走: brainstorm → spec → plan → implement 循环.
> 来源: [AUDIT-REPORT.md](../AUDIT-REPORT.md) §D1 Security + D2 Concurrency (并发安全相关)
> 关联 checklist: [docs/audit/2026-06-24-findings.md](../../../../docs/audit/2026-06-24-findings.md)

## 范围

### Critical (5)
- SEC-002 — chat_share presign path traversal
- SEC-003 — kg/router stats / health 无鉴权
- CON-001 — invite redeem 双重 session TOCTOU
- CON-002 — cancel_deletion 缺锁 + cron 误删
- (SEC-001 降级, 跟 high 一起修)

### High (5)
- SEC-004 — PII scrub 19 字段散落
- SEC-005 — CORS allow_origins env 默认 + localhost
- SEC-006 — 前端 bundle 误用 process.env (OPENAI_API_KEY)
- CON-003 — verify_email_change TOCTOU
- CON-004 — buyer_profile JSONB RMW 缺锁

### Medium (2)
- SEC-007 — forgot_password 无 rate limit
- SEC-008 — presign_get IDOR (URI 归属)
- CON-008 — token cache write-after-PG 无 invalidation

合计 12 条 finding.

## 修复策略

### Phase 1 (1-3 天) — 立即修

1. **SEC-002**: `PresignChatFileRequest.name` schema 加 `pattern=r"^[a-zA-Z0-9._-]+$"`, router 加 `Path(req.name).name` 兜底. 同步给 `presign_get` 加 URI 归属校验 (跟 SEC-008 一起).
2. **CON-001 + CON-002**: invite redeem + cancel_deletion 都加 `SELECT ... FOR UPDATE` 锁, 单事务完成状态变更.
3. **SEC-005**: `app_factory.py` CORS allow_origins 配置加 ENV=production 强制只读白名单, dev 默认值收紧.
4. **CON-003**: `verify_email_change` 流程加 row-level lock + 同事务 token 生成 + cache invalidation.
5. **SEC-006**: 前端检查 `lib/chat/openai.ts` 等是否有 process.env.NON_PUBLIC 误用, 改 server-only.

### Phase 2 (1 周) — 中期

6. **SEC-003**: kg/router 加 IP 白名单或 admin token 守卫, 或确认部署时 proxy 层已加.
7. **CON-004**: buyer_profile JSONB 改用 PG `||` 原子操作 (`profile_data || jsonb_build_object(...)`), 不在 app 层 read-modify-write.
8. **SEC-004**: 集中 PII 字段清单到 `src/core/pii_fields.py`, `logging.py` 引用单一来源.
9. **SEC-007**: forgot_password 加 `rate_limiter.check_and_increment("forgot_password", ip)`.
10. **CON-008**: `resolve_user` 改用 `safe_set` + 同步等待, 失败抛 401.

### Phase 3 (持续) — 加固

- 全局 `dependency_overrides` 加 audit 装饰器补全 (跟 ARCH-006 一起)
- 添加 pre-commit 钩子禁止裸 `except:` / `except ValueError, X:`

## 不在本文范围

- 实施代码 (留到 plan + implement 阶段)
- P1-P4 其他维度 finding
- ARCH-002/003 等纯架构技术债 (走 P4)
- FE-001~012 useRouter 违规 (走 P3)

## 验收标准

- 12 条 finding 全部 verified=true
- 新加 pytest 覆盖 path traversal / TOCTOU / CORS / rate limit
- 端到端 Playwright 验证邀请兑换 / 密码重置 / 忘记密码
- alembic 回到 20260623 之前能成功
