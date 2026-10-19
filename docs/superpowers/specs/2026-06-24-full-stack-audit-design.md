# 全栈代码体检设计 (2026-06-24)

> 状态: 设计中
> 范围: 后端 (packages/service) + 前端 (packages/web), 排除 workflow/scripts/docs
> 目标: 找出代码 bug、安全漏洞、设计不合理、不是最佳实践、项目明显欠缺的地方
> 交付: 多个分阶段 spec/plan, 不在本文档实施任何修复

---

## 1. 背景与动机

项目经过 ~40 个 sprint (~10 周) 开发, 后端 1093 pytest pass, 前端 719 vitest pass, 已知问题沉淀在 `packages/service/KNOWN_ISSUES.md`. 但 codebase 已具规模 (后端 30+ 模块 / 前端 5 主模块 / 30+ 历史 spec), 单点人工 review 难覆盖全. 这次做一次**全方位体检**, 输出可执行的修复清单.

**不做什么**:
- ❌ 实施任何代码修复 (本 spec 只扫描 + 报告)
- ❌ 重构 / 改规约 / 改配置
- ❌ 加新功能
- ❌ 修改历史 spec

**做什么**:
- ✅ 用 6 维度并行扫描找问题
- ✅ adversarial verify 排除误报
- ✅ 输出一份体检报告 + 5 份 spec 草稿 (P0-P4)
- ✅ 由你决定哪些 spec 真正进入 plan + 实施

---

## 2. 总体架构

```
Phase 1: 准备
  └─ 我写 scan-brief.md (统一 agent prompt 模板)
  └─ 创建 .claude/audit/2026-06-24/ 目录

Phase 2: 6 路并行扫描 (6 个 Explore/General agent, 全部只读)
  ├─ D1 Security        → d1-security.md
  ├─ D2 Concurrency     → d2-concurrency.md
  ├─ D3 Error handling  → d3-error.md
  ├─ D4 Data integrity  → d4-data.md
  ├─ D5 Frontend        → d5-frontend.md
  └─ D6 Architecture    → d6-arch.md

Phase 3: Adversarial verify (我对 high/critical finding, 可派 subagent)
  └─ 标 verified / refuted + confidence
  └─ 目标: 剔除 30-50% 误报

Phase 4: Dedup + Synthesize
  └─ 跨维度去重 (file:line + issue_signature)
  └─ 出 AUDIT-REPORT.md
  └─ 切 5 份 spec 草稿 (P0-P4)

Phase 5: 用户 review AUDIT-REPORT.md → 决定走哪几个 spec
```

---

## 3. 6 个维度的扫描范围

### D1: Security (安全)

**必扫文件/路径**:
- `packages/service/src/auth/*` (account_service, account_settings_*, auth_*_router, models)
- `packages/service/src/middleware/auth.py`
- `packages/service/src/permissions/*` (cache, guards, router)
- `packages/service/src/api/routes.py`
- `packages/service/src/ingest/*` (含 converters, analyzers, presign)
- `packages/service/src/storage/object_store.py`
- `packages/service/src/core/redis_client.py`
- `packages/web/app/api/**` (BFF)
- `packages/web/proxy.ts`, `packages/web/middleware.ts`

**检查项**:
- 鉴权缺失 / 绕过 (anon 访问受保护资源)
- SQL / NoSQL 注入
- SSRF (URL 构造再请求)
- IDOR (基于 user_id 越权访问)
- path traversal (文件路径拼接)
- 不安全 deserialization (pickle / yaml.load)
- MinIO presign URL scope 过大
- cookie / CSRF 配置
- 缺失 rate limit 的敏感端点
- PII 泄露到日志
- CORS 配置错
- env / secret 泄露到前端 bundle
- 弱密码 hash (bcrypt? rounds?)
- token 长度 / 熵 / 过期

### D2: Concurrency & State (并发与状态)

**必扫文件/路径**:
- `packages/service/src/chat/service.py`
- `packages/service/src/memory/*`
- `packages/service/src/ingest/tasks.py`
- `packages/service/src/auth/account_service.py`
- `packages/service/src/eval/*`
- 所有 router 中的 session 用法
- `packages/service/src/scheduler/*`

**检查项**:
- TOCTOU (check-then-act 竞态)
- double-commit / 事务回滚失败
- 软删 + 唯一约束冲突
- cron 重入
- JSONB 并发覆盖 (read-modify-write 缺锁)
- 长事务 (持有锁过久)
- 缓存一致性 (PG 改后 Redis 旧值)
- 状态机缺失 (例: invite 状态机)
- list/pagination 期间插入新数据导致 offset 漂移

### D3: Error handling & Resilience (错误处理与韧性)

**必扫文件/路径**:
- `packages/service/src/core/redis_client.py`
- `packages/service/src/storage/object_store.py`
- `packages/service/src/middleware/*`
- 所有 `try/except` 块 (Grep `except Exception` / `except:` / bare except)
- FastAPI exception handlers (grep `@app.exception_handler`)
- 第三方 SDK 调用 (OpenAI, Anthropic, Dify, Neo4j, MinIO)

**检查项**:
- bare except / Exception 吞掉
- 缺失超时 (无 timeout 参数)
- retry 风暴 (无退避无上限)
- fallback 缺失 (Redis 挂了整体挂)
- 错误响应泄露 stacktrace
- PII 进日志
- 5xx 没有全局 handler
- circuit breaker 缺失
- LLM 调用无 max_tokens / token 预算

### D4: Data integrity & Migrations (数据完整性与迁移)

**必扫文件/路径**:
- `packages/service/src/storage/migrations/versions/*.py`
- 所有 `models.py` (auth, chat, eval, approvals, kg, lookups, db)
- `packages/service/src/lookups/*`
- 所有 FK 关系 (grep `ForeignKey`, `relationship`)
- alembic downgrade (每个 migration 必查)

**检查项**:
- alembic 可回滚性 (downgrade 干净不丢数据)
- ORM / SQL 字段不一致
- FK 缺失 / 错配 / ondelete 错
- enum 硬编字符串 (违反 lookups 唯一事实源)
- JSONB 无 schema (Pydantic 验)
- 软删 + 唯一约束冲突
- 迁移顺序依赖
- deprecated column 残留
- 测试用真 migration 缺 isolation

### D5: Frontend pitfalls (前端陷阱)

**必扫文件/路径**:
- `packages/web/app/[locale]/**`
- `packages/web/lib/chat/*`
- `packages/web/lib/api/*`
- `packages/web/components/common/**`
- `packages/web/proxy.ts`
- `packages/web/middleware.ts`
- `packages/web/i18n/**`
- `packages/web/next.config.ts`

**检查项**:
- React 19 / Next.js 16 误用 (use(), useFormStatus 等)
- useEffect cleanup 缺失 (内存泄漏)
- TanStack Query staleTime / cache key 错配
- useRouter 从 `next/navigation` 引 (已知 bug 模式)
- next-intl 漏消息 (zh.json 没注册)
- bundle 体积过大 (未 dynamic import)
- ref 持有陈旧 closure
- a11y 缺失 (button 缺 aria-label, img 缺 alt)
- 'use client' / 'use server' 边界错
- client-secret 泄露到 client bundle
- 路由跳转 SSR 串 locale

### D6: Architecture & Convention (架构与规约)

**必扫文件/路径**:
- 全局
- 对比 `CLAUDE.md` / `packages/service/CLAUDE.md` / `packages/web/CLAUDE.md` 全部规则
- `packages/service/pyproject.toml`
- `packages/web/package.json`
- `bun.lock` / `uv.lock`
- `tests/` 覆盖率报告
- `.env.example` / `.env.local`

**检查项**:
- 重复代码 (相同 ≥3 行 ≥3 处)
- 未抽装 (组件 / hook 模板化)
- 模块边界违反 (跨层 import)
- 规约违反 (CLAUDE.md 已定但代码未遵守)
- 测试缺口 (4 模式覆盖)
- env 散落 (缺集中管理)
- 监控 / 可观测性缺失 (metrics, tracing)
- 文档与代码脱节
- package.json scripts 不一致
- pre-commit 钩子绕过

---

## 4. Finding Schema (统一)

每条 finding 必须满足:

```yaml
- id: SEC-001                    # {DIM}-{NNN}
  dimension: security            # security|concurrency|error|data|frontend|arch
  severity: critical             # critical|high|medium|low|info
  confidence: high               # high|medium|low (verify 阶段填)
  verified: true                 # bool (verify 阶段填)
  refuted_reason: null           # string|null
  title: "Redis cache key contains user_id but cached payload not scoped"
  file: packages/service/src/core/permission_cache_redis.py
  line: 42
  description: |
    详细描述 (中文, ≥2 句)
  evidence: |
    ```python
    代码引用 (≥3 行)
    ```
  impact: |
    影响范围 / 攻击场景
  fix_sketch: |
    修复思路 (不实施, 仅作参考)
  references: [cwe-862, owasp-a01]  # 可选
```

Agent 用 schema 强制输出 JSON, 验证失败 retry 1 次, 仍失败降级成纯 md 输出.

---

## 5. Phase 3: Adversarial Verify

**触发条件**: severity ∈ {critical, high} 的 finding

**流程**:
1. 我对每条 critical/high finding 派 1-2 个 verifier (Explore agent)
2. Verifier prompt 模板: "尝试反驳这条 finding: `{title}`. 读 `{file}` 行 `{line}`, 找出反例 / 错配 / 误判的证据. 如果找不出, 保留; 如果能 refute, 给具体理由"
3. 每条 finding 追加字段: `verified: bool`, `confidence: high|medium|low`, `refuted_reason: string|null`
4. **降级**:
   - verifier 工具调用失败 → 默认 verified=true, confidence=low
   - verifier 找不到反例 → verified=true
   - verifier 找到反例 → verified=false, 标 refuted_reason

**目标**: 剔除 30-50% 误报 (历史 spec 经验, high/critical 中常有 ~30% 误判)

---

## 6. Phase 4: Dedup + Synthesize

**Dedup 规则**:
1. **精确去重**: 同 `file:line` 跨维度合并, 保留 severity 最高维度
2. **模糊去重**: 不同位置但同 issue_signature (description 关键词 hash) 合并, 加 `related_files: []` 列出所有位置
3. 输出唯一 ID `{DIM}-{NNN}`, 跨维度按 severity 重排

**Synthesize 产出** (`AUDIT-REPORT.md`):
- 顶部: 元信息 (扫描时间, 维度数, 总 finding 数, verified 数, refuted 数)
- 表格: id | dimension | severity | title | file:line | verified | refuted
- 按维度分组详情
- 5 份 spec 草稿的"摘要 + 范围 + 修复策略" 引用

**5 份 spec 草稿建议**:
- `specs/P0-security.md` (所有 critical/high verified security + 部分 concurrency 安全相关)
- `specs/P1-error-resilience.md` (medium/high error handling)
- `specs/P2-data-integrity.md` (migration / FK / 软删)
- `specs/P3-frontend-quality.md` (frontend pitfalls)
- `specs/P4-architecture-debt.md` (arch + 规约违反)

---

## 7. 错误处理 / 防失速

- **任一 agent 失败** → 整批不阻塞, 记录到 `AUDIT-REPORT.md` 顶部"未完成维度", 该维度降级为"已知未扫, 建议下一轮重试"
- **agent 超时 / 死循环** → 工具 max 30 calls / max 50k tokens, 超限自动 stop
- **subagent 失败 retry 1 次**, 仍失败降级成 1 份"已发现 + 已知未扫"小报告
- **网络失败** (查 CVE) → D1 标"已知未查 CVE, 需后续人工", 不阻塞

---

## 8. 产出物清单

| 路径 | 内容 | 谁写 |
|---|---|---|
| `docs/superpowers/specs/2026-06-24-full-stack-audit-design.md` | 本 spec | 我 (本文) |
| `.claude/audit/2026-06-24/scan-brief.md` | 6 个 agent 统一 prompt 模板 | Phase 1 我写 |
| `.claude/audit/2026-06-24/d1-security.md` | D1 原始 finding | D1 agent |
| `.claude/audit/2026-06-24/d2-concurrency.md` | D2 原始 finding | D2 agent |
| `.claude/audit/2026-06-24/d3-error.md` | D3 原始 finding | D3 agent |
| `.claude/audit/2026-06-24/d4-data.md` | D4 原始 finding | D4 agent |
| `.claude/audit/2026-06-24/d5-frontend.md` | D5 原始 finding | D5 agent |
| `.claude/audit/2026-06-24/d6-arch.md` | D6 原始 finding | D6 agent |
| `.claude/audit/2026-06-24/AUDIT-REPORT.md` | 汇总报告 (用户主要看这份) | Phase 4 我写 |
| `.claude/audit/2026-06-24/specs/P0-security.md` | 修复 spec 草稿 (安全) | Phase 4 我写 |
| `.claude/audit/2026-06-24/specs/P1-error-resilience.md` | 修复 spec 草稿 (错误处理) | Phase 4 我写 |
| `.claude/audit/2026-06-24/specs/P2-data-integrity.md` | 修复 spec 草稿 (数据) | Phase 4 我写 |
| `.claude/audit/2026-06-24/specs/P3-frontend-quality.md` | 修复 spec 草稿 (前端) | Phase 4 我写 |
| `.claude/audit/2026-06-24/specs/P4-architecture-debt.md` | 修复 spec 草稿 (架构) | Phase 4 我写 |
| `docs/audit/2026-06-24-findings.md` | **问题列表 (用户日常维护用)** | Phase 4 我写, 你日常 - [x] 勾掉 |

**总 commit**: `chore(audit): 2026-06-24 full-stack audit — 6 dimensions, N findings, M verified`

**分支策略**: `audit/2026-06-24-full-stack-audit` (单次合并)

---

## 9. 测试 / 质量门禁

本 spec **不实施任何修复**, 无 pytest / vitest 输出. 质量门禁仅在产出物本身:

| 门禁 | 规则 |
|---|---|
| evidence 引用 | 每条 finding `evidence` ≥ 3 行代码引用 |
| verified 标签 | critical/high finding 必填 verified / refuted_reason |
| confidence 字段 | 每条 finding 必填 high/medium/low |
| file:line 存在 | `file:line` 必须在 git HEAD 存在 (我用 Read 验) |
| 跨维度去重 | 同一 `file:line` 出现 ≥2 次必合并 |
| spec 草稿覆盖 | AUDIT-REPORT 中所有 verified high/critical 至少落到 1 份 spec 草稿 |

---

## 10. 不在本文范围

- 修复任何 finding (留到 P0-P4 spec 各自实施)
- 修改业务代码 / 规约 / 配置
- 加新功能 / 新依赖
- 改历史 spec
- 改 CI / 部署 / docker

---

## 11. 风险与缓解

| 风险 | 缓解 |
|---|---|
| Agent 扫到 false positive | Phase 3 verify 阶段剔除 30-50% |
| Agent 漏扫关键路径 | scan-brief.md 强制列"必扫文件/路径", 缺一扣分 |
| Spec 草稿被当 plan 实施 | 草稿标题前缀 `specs/P?-xxx.md`, 强调"草稿" + "未实施"; 真正 plan 走 writing-plans |
| 误把"项目规约"当 bug | finding 标 dimension=arch 时明确"违反 {CLAUDE.md §X}"; 你 review 时可拒绝 |
| token 消耗大 | 6 agent × 50k 上限 = 300k 预估, 可接受 |
| 扫描期间代码变动 | 在 audit 分支上做, base = HEAD 锁定, 不并行 rebase |
| 网络受限无法查 CVE | D1 标"已知未查 CVE, 需后续人工", 不阻塞; 改 D6 arch 维度里加一行 finding "CVE 监控缺失" |
| scan-brief.md 决策遗漏 | 明确: D1 允许 WebSearch/WebFetch 查 deps CVE (用户已授权), D2-D6 仅用本地 Read/Grep/Glob |
| spec 草稿被当 plan 实施 | 草稿标题前缀 `specs/P?-xxx.md`, 强调"草稿" + "未实施"; 真正 plan 走 writing-plans |

---

## 13. 问题列表文档格式 (`docs/audit/2026-06-24-findings.md`)

**目的**: 用户日常维护用, 看到问题就勾掉, 跟现有 `KNOWN_ISSUES.md` 风格对齐.

**路径**: `docs/audit/2026-06-24-findings.md`

**checkbox 语义** (二态):
- `- [ ]` 未处理 (默认状态)
- `- [x]` 已处理 (修复 commit 后由你勾掉)

**文档结构**:

```markdown
# 全栈代码体检 — 发现清单 (2026-06-24)

> 来源: 2026-06-24 全栈审计 (6 维度)
> 详细发现 + evidence + impact: 见 [.claude/audit/2026-06-24/AUDIT-REPORT.md](../../.claude/audit/2026-06-24/AUDIT-REPORT.md)
> 处理指南: 修完一个 → 改 `- [ ]` 为 `- [x]` + 在后面加 commit hash

**汇总**: 6 维度 / N 条 finding / M 条已验证 / 0 条已修 (持续更新)

---

## Critical (必须修)

- [ ] **SEC-001** Redis cache key contains user_id but cached payload not scoped — `src/core/permission_cache_redis.py:42` — [AUDIT-REPORT §D1](../../.claude/audit/2026-06-24/AUDIT-REPORT.md#sec-001)
- [ ] **CON-002** double-commit in soft-delete conversation — `src/chat/service.py:128` — [AUDIT-REPORT §D2](../../.claude/audit/2026-06-24/AUDIT-REPORT.md#con-002)

## High (高优先)

- [ ] **ERR-005** bare `except Exception:` swallows LLM 429 — `src/integrations/llm.py:88` — [AUDIT-REPORT §D3](../../.claude/audit/2026-06-24/AUDIT-REPORT.md#err-005)
- [ ] **FE-012** `useRouter` from `next/navigation` 在 6 个文件违规 — `app/[locale]/login/page.tsx:34` (等) — [AUDIT-REPORT §D5](../../.claude/audit/2026-06-24/AUDIT-REPORT.md#fe-012)

## Medium (中优先)

- [ ] **DATA-018** alembic migration `20260615_000000` 缺 downgrade 验证 — `src/storage/migrations/versions/20260615_000000_*.py:1` — [AUDIT-REPORT §D4](../../.claude/audit/2026-06-24/AUDIT-REPORT.md#data-018)

## Low (低优先)

- [ ] **ARCH-023** 重复代码 ≥3 行出现 5 次未抽装 — `src/chat/service.py:50,80,110,...` — [AUDIT-REPORT §D6](../../.claude/audit/2026-06-24/AUDIT-REPORT.md#arch-023)

## Info (提示性)

- [ ] **ARCH-030** 三方包 `pydantic-extra-types` 已弃用, 建议替换 — [AUDIT-REPORT §D6](../../.claude/audit/2026-06-24/AUDIT-REPORT.md#arch-030)

---

## 修复进度

| 维度 | 总数 | 已修 | 进度 |
|---|---|---|---|
| Security | X | 0 | 0% |
| Concurrency | X | 0 | 0% |
| Error handling | X | 0 | 0% |
| Data integrity | X | 0 | 0% |
| Frontend | X | 0 | 0% |
| Architecture | X | 0 | 0% |
| **合计** | **N** | **0** | **0%** |

---

## 处理流程

1. 修一个问题 → 改对应行 `- [ ]` → `- [x] <commit-hash>`
   例: `- [x] **SEC-001** ... — abc1234`
2. 改完进度表对应维度 +1
3. 大块修复 (≥10 条) 走 spec → plan → implement 循环, 完成后批量勾
4. 误报 / 不修: 保留 `- [ ]`, 在后面加 `(won't fix: 理由)` 标注, 不勾掉
```

**维护规则**:
- 这份文档**只增不删** (审计快照, 历史可追溯)
- 改 `- [ ]` → `- [x]` + commit hash 是**唯一**的"已修"信号
- 跟 `KNOWN_ISSUES.md` 区别: KNOWN_ISSUES.md 记 pre-existing pytest fail, 这份记审计 finding
- 后续 P0-P4 spec 实施后, 由你或后续 spec 自己勾 checkbox + 更新进度表

1. 你 review 本 spec → 批准
2. 我走 writing-plans skill → 写**实施 plan** (Phase 1-4 的执行步骤, 含 6 个 agent prompt)
3. 你 review plan → 批准
4. 我执行 plan: Phase 1 准备 → Phase 2 并行扫描 → Phase 3 verify → Phase 4 synthesize
5. 你 review `AUDIT-REPORT.md` + `docs/audit/2026-06-24-findings.md` → 决定哪些 P0-P4 spec 真正进入下一个 brainstorm → spec → plan → implement 循环
6. 修完一个 finding, 在 `docs/audit/2026-06-24-findings.md` 把对应行 `- [ ]` 改 `- [x] <commit-hash>`

**本 spec 不直接进入实施**, 实施 plan 由 writing-plans skill 生成.
