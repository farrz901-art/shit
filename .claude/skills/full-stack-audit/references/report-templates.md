# AUDIT-REPORT + Spec 草稿模板

> Phase 4 主线程在 synthesize 阶段使用. 不派 subagent, 主线程手动合并 6 个 d*.md.

---

## 1. AUDIT-REPORT.md — 汇总报告

**目标读者**: 决策者. 看完决定哪些 P0-P4 spec 进入下一个 brainstorm → spec → plan → implement 循环.

### 模板

```markdown
# 全栈审计报告 (YYYY-MM-DD)

> 来源: 6 维度并行扫描 + adversarial verify
> 原始 finding: [d1-security.md](d1-security.md) ... [d6-arch.md](d6-arch.md)
> 日常维护 checklist: [docs/audit/YYYY-MM-DD-findings.md](../../../docs/audit/YYYY-MM-DD-findings.md)
> Spec 草稿: [P0-security.md](specs/P0-security.md) ... [P4-architecture-debt.md](specs/P4-architecture-debt.md)

## 元信息

- 扫描时间: YYYY-MM-DD
- 维度: 6 (Security / Concurrency / Error / Data / Frontend / Architecture)
- 总 finding: N (含 M verified + K refuted + N-M-K 待 verify)
- 误报率: K / M %
- 平均 confidence: high=N / medium=N / low=N

## 汇总表 (按严重度)

| ID | 维度 | 严重度 | 置信度 | 标题 | file:line | verified | refuted |
|---|---|---|---|---|---|---|---|
| SEC-001 | security | critical | high | Redis cache TTL 永不过期 | src/core/redis_client.py:42 | ✓ | - |
| CONC-001 | concurrency | high | high | 软删+unique 约束冲突 | src/auth/models.py:55 | ✓ | - |
| ERR-001 | error | high | high | Bare except 吞掉异常 | src/storage/object_store.py:23 | ✓ | - |
| DATA-001 | data | high | medium | alembic migration 不可回滚 | src/storage/migrations/versions/abc.py | ✓ | - |
| FE-001 | frontend | medium | high | useRouter 从 next/navigation 引 | lib/chat/hooks.ts:15 | ✓ | - |
| ARCH-001 | architecture | medium | high | 业务 enum 硬编字符串 | src/auth/enums.py:12 | ✓ | - |
| ... | ... | ... | ... | ... | ... | ... | ... |

## 按严重度统计

| 严重度 | 总数 | verified | refuted |
|---|---|---|---|
| Critical | N | M | K |
| High | N | M | K |
| Medium | N | M | K |
| Low | N | M | K |
| Info | N | M | K |
| **合计** | N | M | K |

## 按维度统计

| 维度 | 总数 | verified | refuted | Critical | High | Medium | Low | Info |
|---|---|---|---|---|---|---|---|---|
| Security | N | M | K | N | N | N | N | N |
| Concurrency | N | M | K | N | N | N | N | N |
| Error | N | M | K | N | N | N | N | N |
| Data | N | M | K | N | N | N | N | N |
| Frontend | N | M | K | N | N | N | N | N |
| Architecture | N | M | K | N | N | N | N | N |
| **合计** | N | M | K | N | N | N | N | N |

## 按维度详情

### Security (D1) — N 条 finding

#### SEC-001: Redis cache TTL 永不过期

- **文件**: `src/core/redis_client.py:42`
- **严重度**: critical
- **置信度**: high
- **verified**: true
- **description**: 全文抄
- **evidence**: 全文抄
- **impact**: 全文抄
- **fix_sketch**: 全文抄
- **references**: [cwe-613, owasp-a05:2021]

#### SEC-002: ...

(所有 security finding 列完, 其他维度同理)

### Concurrency (D2) — N 条 finding
[同上结构]

### Error handling (D3) — N 条 finding
[同上结构]

### Data integrity (D4) — N 条 finding
[同上结构]

### Frontend (D5) — N 条 finding
[同上结构]

### Architecture (D6) — N 条 finding
[同上结构]

## Spec 草稿映射

| Spec 草稿 | 涵盖维度 | finding 数 | 优先级 |
|---|---|---|---|
| [P0-security.md](specs/P0-security.md) | D1 + D2 (安全相关) | N | P0 立即修 |
| [P1-error-resilience.md](specs/P1-error-resilience.md) | D3 | N | P1 高优 |
| [P2-data-integrity.md](specs/P2-data-integrity.md) | D4 | N | P1 高优 |
| [P3-frontend-quality.md](specs/P3-frontend-quality.md) | D5 | N | P2 中优 |
| [P4-architecture-debt.md](specs/P4-architecture-debt.md) | D6 + D2 (非安全) | N | P3 低优 |

## 决策日志

- YYYY-MM-DD: 启动审计, 6 维度并行
- YYYY-MM-DD: Phase 3 verify 完成, K 条 refuted
- YYYY-MM-DD: 5 份 P?-xxx spec 草稿生成
- YYYY-MM-DD: 提交 master
```

---

## 2. P0-security.md — Spec 草稿 (P0 优先级, 安全)

> ⚠️ **本文件是草稿**, 真正实施需走: brainstorm → spec → plan → implement 循环. 这里只是 audit 阶段的产出物, 列出 finding + 修复策略, 不含实施代码.

### 模板

```markdown
# P0 - 安全修复 spec 草稿 (YYYY-MM-DD)

> ⚠️ 草稿, 未实施. 真正实施需走: brainstorm → spec → plan → implement 循环.
> 来源: [AUDIT-REPORT.md](../AUDIT-REPORT.md) §Security (D1) + Concurrency (D2 安全相关)
> 关联 checklist: [docs/audit/YYYY-MM-DD-findings.md](../../../../docs/audit/YYYY-MM-DD-findings.md)
> 涵盖 finding 数: N 条 (N critical + N high + N medium)

## 范围

包含的 finding ID:
- SEC-001 (critical) — Redis cache TTL 永不过期
- SEC-002 (high) — 忘记密码接口无 rate limit
- CONC-005 (high) — TOCTOU 在权限检查
- ...

## 修复策略

### 1. 鉴权 / 授权

- [修复思路 1: 全端点加 `Depends(get_current_user)` 检查]
- [修复思路 2: 角色检查抽装为 guard]

### 2. 注入防护

- [修复思路 1: SQLAlchemy 参数化查询已用, 重点查 raw SQL]
- [修复思路 2: LLM prompt 用 system message 隔离]

### 3. SSRF / IDOR

- [修复思路 1: URL 白名单 + DNS 解析后 IP 校验]
- [修复思路 2: 资源访问前校验 user_id 所属]

### 4. 依赖漏洞

- [修复思路 1: `uv run pip-audit` 加到 CI]
- [修复思路 2: critical CVE 立即升级, 7 天内修 high CVE]

### 5. 韧性 + 监控

- [修复思路 1: 全局 5xx handler 补全]
- [修复思路 2: 关键鉴权路径加 metrics + 异常告警]

## 修复顺序 (建议)

1. **Week 1**: 所有 critical finding (SEC-001 等) — 阻断 release
2. **Week 2**: 所有 high finding — 影响生产
3. **Week 3+**: medium finding — 累积修复

## 不在本文范围

- 实施代码 — 留到 plan + implement 阶段
- 其他 P1-P4 维度 finding — 见对应 spec 草稿
- 已经是 false positive 的 finding — 已在 AUDIT-REPORT 标 refuted

## 验证标准

- [ ] 所有 critical finding 修复并通过 verify (跑 `verify-sec-critical.sh`)
- [ ] 鉴权相关单测覆盖率 ≥ 90%
- [ ] `uv run pip-audit` 输出 0 critical
- [ ] `bun audit --production` 输出 0 critical

## 关联文档

- [AUDIT-REPORT.md](../AUDIT-REPORT.md)
- [docs/audit/YYYY-MM-DD-findings.md](../../../../docs/audit/YYYY-MM-DD-findings.md)
- 实施 plan: TBD (从本 spec 派生)
```

---

## 3. P1-error-resilience.md — Spec 草稿 (P1 优先级, 错误处理)

> 同 P0 模板, 范围改成 D3 (Error handling).

```markdown
# P1 - 错误处理与韧性 spec 草稿 (YYYY-MM-DD)

> ⚠️ 草稿, 未实施.
> 来源: [AUDIT-REPORT.md](../AUDIT-REPORT.md) §Error handling (D3)
> 涵盖 finding 数: N 条

## 范围

- ERR-001 (high) — Bare except 吞掉异常
- ERR-002 (high) — 缺失 httpx timeout
- ERR-003 (medium) — Retry 风暴无指数退避
- ...

## 修复策略

### 1. 异常处理

- [修复思路 1: 禁止 bare `except:`, 全部加具体异常类型]
- [修复思路 2: `except: pass` 全部加 logger.exception + re-raise]

### 2. 超时与重试

- [修复思路 1: 全局 httpx 默认 timeout=30s]
- [修复思路 2: tenacity 库 + 指数退避 + max_retries=3]

### 3. 降级与熔断

- [修复思路 1: Redis 挂时降级到 DB, 不直接 5xx]
- [修复思路 2: 外部 SDK 调用加 circuit breaker]

### 4. 日志与可观测性

- [修复思路 1: PII 字段 (email/token/password) 加 log filter]
- [修复思路 2: 全局 @app.exception_handler 补全]

[其余段同 P0 模板]
```

---

## 4. P2-data-integrity.md — Spec 草稿 (P1 优先级, 数据)

```markdown
# P2 - 数据完整性 spec 草稿 (YYYY-MM-DD)

> ⚠️ 草稿, 未实施.
> 来源: [AUDIT-REPORT.md](../AUDIT-REPORT.md) §Data integrity (D4)
> 涵盖 finding 数: N 条

## 范围

- DATA-001 (high) — alembic migration 不可回滚
- DATA-002 (high) — FK 缺索引导致全表扫描
- DATA-003 (medium) — 业务 enum 硬编字符串
- ...

## 修复策略

### 1. Migration

- [修复思路 1: 所有 migration 加 downgrade 测试, CI 跑 upgrade+downgrade+upgrade]
- [修复思路 2: 禁止 migration 直接 DROP COLUMN, 必须两步 (rename + add + backfill + drop)]

### 2. FK 与索引

- [修复思路 1: 所有逻辑外键加索引]
- [修复思路 2: ondelete 全部走显式声明]

### 3. Enum 唯一事实源

- [修复思路 1: 所有 StrEnum 移到 [packages/service/src/lookups/](../../../service/src/lookups/)]
- [修复思路 2: 业务代码 import lookup, 禁止硬编字符串]

### 4. JSONB Schema

- [修复思路 1: 所有 JSONB 字段加 Pydantic model 校验]

[其余段同 P0 模板]
```

---

## 5. P3-frontend-quality.md — Spec 草稿 (P2 优先级, 前端)

```markdown
# P3 - 前端质量 spec 草稿 (YYYY-MM-DD)

> ⚠️ 草稿, 未实施.
> 来源: [AUDIT-REPORT.md](../AUDIT-REPORT.md) §Frontend (D5)
> 涵盖 finding 数: N 条

## 范围

- FE-001 (medium) — useRouter 从 next/navigation 引
- FE-002 (medium) — useEffect cleanup 缺失
- FE-003 (low) — next-intl 漏消息
- ...

## 修复策略

### 1. Router

- [修复思路 1: 全部 useRouter 改为从 `@/i18n/navigation` 引, 加 codemod 脚本]

### 2. React 19 / Next.js 16

- [修复思路 1: useEffect 加 cleanup function]
- [修复思路 2: use() 必须在 try/catch 内, 加 eslint 规则]

### 3. TanStack Query

- [修复思路 1: staleTime 默认改为 30s]
- [修复思路 2: cache key 全部用 [entity, id] 结构]

### 4. Bundle 优化

- [修复思路 1: lodash 全量 import 改为 named import]
- [修复思路 2: next.config.ts 加 bundle analyzer, CI 阻断 > 500KB 的 chunk]

### 5. A11y

- [修复思路 1: `<div onClick>` 全部改 `<button type="button">`]
- [修复思路 2: 加 @axe-core/playwright 到 E2E]

[其余段同 P0 模板]
```

---

## 6. P4-architecture-debt.md — Spec 草稿 (P3 优先级, 架构)

```markdown
# P4 - 架构债务 spec 草稿 (YYYY-MM-DD)

> ⚠️ 草稿, 未实施.
> 来源: [AUDIT-REPORT.md](../AUDIT-REPORT.md) §Architecture (D6) + Concurrency (D2 非安全)
> 涵盖 finding 数: N 条

## 范围

- ARCH-001 (medium) — 业务 enum 硬编字符串
- ARCH-002 (medium) — 重复代码 ≥ 3 处未抽装
- CONC-007 (low) — 锁顺序不一致
- ...

## 修复策略

### 1. 规约遵守

- [修复思路 1: 不删注释 / 中文注释 / TDD 走 PR 检查清单]
- [修复思路 2: 函数 > 100 行 / 重复 ≥ 3 处抽装, 加 ruff/oxlint 规则]

### 2. 跨层 import

- [修复思路 1: 加 pyright + oxlint 规则禁跨层]
- [修复思路 2: 重新整理模块边界文档]

### 3. 测试覆盖

- [修复思路 1: 4 模式覆盖检查加到 CI]
- [修复思路 2: 禁止连真 PG, 全走 mock session]

### 4. 可观测性

- [修复思路 1: 关键路径加 metrics (Counter/Histogram)]
- [修复思路 2: 错误日志结构化 (JSON + trace_id)]

### 5. 文档

- [修复思路 1: README 与代码同步检查加到 CI]
- [修复思路 2: 模块级 docstring 必填]

[其余段同 P0 模板]
```

---

## 7. YYYY-MM-DD-findings.md — Checklist 模板 (首次)

```markdown
# 全栈代码体检 — 发现清单 (YYYY-MM-DD)

> 来源: YYYY-MM-DD 全栈审计 (6 维度)
> 详细 finding + evidence + impact: 见 [docs/audit/YYYY-MM-DD/AUDIT-REPORT.md](YYYY-MM-DD/AUDIT-REPORT.md)
> 处理指南: 修完一个 → 改 `- [ ]` 为 `- [x] <commit-hash>`

**汇总**: 6 维度 / N 条 finding / M verified / K refuted (误报率 K/M %)

---

## Critical (必须修)

- [ ] **SEC-001** Redis cache TTL 永不过期 — `src/core/redis_client.py:42`
- [ ] **SEC-002** ... — `src/...:line`

## High (高优先)

- [ ] **CONC-001** 软删+unique 约束冲突 — `src/auth/models.py:55`
- [ ] **ERR-001** Bare except 吞掉异常 — `src/storage/object_store.py:23`
- [ ] **DATA-001** alembic migration 不可回滚 — `src/storage/migrations/versions/abc.py`
- [ ] ...

## Medium (中优先)

- [ ] **FE-001** useRouter 从 next/navigation 引 — `lib/chat/hooks.ts:15`
- [ ] **ARCH-001** 业务 enum 硬编字符串 — `src/auth/enums.py:12`
- [ ] ...

## Low (低优先)

- [ ] ...

## Info (提示性)

- [ ] ...

---

## 修复进度

| 维度 | 总数 | 已修 | 进度 |
|---|---|---|---|
| Security | N | 0 | 0% |
| Concurrency | N | 0 | 0% |
| Error handling | N | 0 | 0% |
| Data integrity | N | 0 | 0% |
| Frontend | N | 0 | 0% |
| Architecture | N | 0 | 0% |
| **合计** | **N** | **0** | **0%** |

---

## 处理流程

1. 修一个问题 → 改对应行 `- [ ]` → `- [x] <commit-hash>`
   例: `- [x] **SEC-001** Redis cache TTL 永不过期 — abc1234`
2. 改完进度表对应维度 +1
3. 大块修复 (≥ 10 条) 走 spec → plan → implement 循环, 完成后批量勾
4. 误报 / 不修: 保留 `- [ ]`, 在后面加 `(won't fix: 理由)` 标注, 不勾掉
```

---

## 报告长度参考

基于 2026-06-24 扫描 (已 commit `5dda3df9` + 后续) 的实际行数:

| 报告 | 行数 | finding 数量 |
|---|---|---|
| AUDIT-REPORT.md | ~400 | 60 |
| P0-security.md | ~80 | 18 (含 D1 + D2 安全) |
| P1-error-resilience.md | ~70 | 12 |
| P2-data-integrity.md | ~70 | 10 |
| P3-frontend-quality.md | ~80 | 14 |
| P4-architecture-debt.md | ~80 | 16 (含 D2 非安全) |
| YYYY-MM-DD-findings.md | ~150 | 60 |

**提示**: AUDIT-REPORT 较长是正常的, 它是 6 维度的汇总. spec 草稿保持精简, 重点是**修复策略**而非实施细节.
