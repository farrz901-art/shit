# 全栈代码体检 — 实施 Plan (2026-06-24)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 按 [2026-06-24-full-stack-audit-design.md](../specs/2026-06-24-full-stack-audit-design.md) 实施 6 维度全栈代码体检, 输出 findings + 汇总报告 + 5 份 spec 草稿 + 1 份日常维护 checklist. **不修改任何业务代码.**

**Architecture:** 主线程 (我) 协调, 6 个 subagent 并行扫描 → 主线程做 verify + dedup + synthesize. 所有 subagent 只读不写, 输出统一 JSON. 产出物落 `.claude/audit/2026-06-24/` + `docs/audit/2026-06-24-findings.md`.

**Tech Stack:**
- Claude Code subagent (Agent tool) — 用 Explore/General-purpose, 6 路并行
- Read / Grep / Glob (subagent 只读)
- Write / Edit (仅主线程写产出物)
- WebSearch / WebFetch (仅 D1 Security 允许, 查 deps CVE)
- workflow MCP (可选, 跑 Pipeline 模式)

**Worktree:** `.claude/worktrees/audit-2026-06-24/` (branch: `audit/2026-06-24-full-stack-audit`)

**前置依赖:**
- 已在 `audit/2026-06-24-full-stack-audit` worktree
- spec 已 commit (`d6c7e85c`)
- 不联网也可行 (D1 查 CVE 降级即可)

---

## 文件结构 (本次实施新增/修改)

| 路径 | 类型 | 责任 |
|---|---|---|
| `.claude/audit/2026-06-24/README.md` | 新建 | 目录索引 + 决策日志 |
| `.claude/audit/2026-06-24/scan-brief.md` | 新建 | 6 个 agent 统一 prompt 模板 |
| `.claude/audit/2026-06-24/d1-security.md` | 新建 | D1 原始 finding (6 个 agent 之一) |
| `.claude/audit/2026-06-24/d2-concurrency.md` | 新建 | D2 原始 finding |
| `.claude/audit/2026-06-24/d3-error.md` | 新建 | D3 原始 finding |
| `.claude/audit/2026-06-24/d4-data.md` | 新建 | D4 原始 finding |
| `.claude/audit/2026-06-24/d5-frontend.md` | 新建 | D5 原始 finding |
| `.claude/audit/2026-06-24/d6-arch.md` | 新建 | D6 原始 finding |
| `.claude/audit/2026-06-24/AUDIT-REPORT.md` | 新建 | 汇总报告 (verify 后) |
| `.claude/audit/2026-06-24/specs/P0-security.md` | 新建 | 修复 spec 草稿 (安全) |
| `.claude/audit/2026-06-24/specs/P1-error-resilience.md` | 新建 | 修复 spec 草稿 (错误处理) |
| `.claude/audit/2026-06-24/specs/P2-data-integrity.md` | 新建 | 修复 spec 草稿 (数据) |
| `.claude/audit/2026-06-24/specs/P3-frontend-quality.md` | 新建 | 修复 spec 草稿 (前端) |
| `.claude/audit/2026-06-24/specs/P4-architecture-debt.md` | 新建 | 修复 spec 草稿 (架构) |
| `docs/audit/2026-06-24-findings.md` | 新建 | **日常维护 checklist (- [ ] / - [x])** |
| `docs/audit/README.md` | 新建 | docs/audit/ 目录说明 |

**不动**: 任何业务代码, 任何 `packages/*/src/**`, 任何 `tests/**`, 任何 config / lockfile / CI.

---

## Task 1: 创建目录 + scan-brief + README

**Files:**
- Create: `.claude/audit/2026-06-24/README.md`
- Create: `.claude/audit/2026-06-24/scan-brief.md`
- Create: `docs/audit/README.md`
- Create: `docs/audit/2026-06-24-findings.md` (空模板, Phase 4 填)
- Create: `.claude/audit/2026-06-24/specs/.gitkeep` (占位, 防止空目录 commit 失败)

### Step 1.1: 创建目录结构

Run:
```bash
cd c:/doc/Code/rag/.claude/worktrees/audit-2026-06-24
mkdir -p .claude/audit/2026-06-24/specs
mkdir -p docs/audit
touch .claude/audit/2026-06-24/specs/.gitkeep
```

Expected: 4 个 mkdir/create 成功, 0 错误.

### Step 1.2: 写 `docs/audit/README.md`

```markdown
# docs/audit/ — 审计与代码体检目录

> 维护说明: 每次全栈审计创建一份日期命名的 checklist 文档, 走 `- [ ]` / `- [x]` 维护.

## 文档列表

| 文档 | 用途 | 状态 |
|---|---|---|
| [2026-06-24-findings.md](2026-06-24-findings.md) | 2026-06-24 全栈审计 — 日常维护 checklist | 活跃 |

## 命名约定

- 文件名: `YYYY-MM-DD-findings.md` (一份审计一份)
- checkbox 语义:
  - `- [ ]` 未处理 (默认)
  - `- [x]` 已处理 (后面跟 commit hash)
- 严重度分组: Critical / High / Medium / Low / Info

## 处理流程

1. 修一个问题 → 改对应行 `- [ ]` → `- [x] <commit-hash>`
2. 大块修复 (≥10 条) 走 spec → plan → implement 循环, 完成后批量勾
3. 误报 / 不修: 保留 `- [ ]`, 在后面加 `(won't fix: 理由)`, 不勾掉

## 关联文档

- 详细 audit 报告: `.claude/audit/YYYY-MM-DD/AUDIT-REPORT.md`
- 设计 spec: `docs/superpowers/specs/2026-06-24-full-stack-audit-design.md`
- 实施 plan: `docs/superpowers/plans/2026-06-24-full-stack-audit.md`
```

### Step 1.3: 写 `.claude/audit/2026-06-24/README.md`

```markdown
# 2026-06-24 全栈审计 — 工作目录

> 内部目录, 不入 docs/ 但 git 追踪. spec 决策来源: [2026-06-24-full-stack-audit-design.md](../../../docs/superpowers/specs/2026-06-24-full-stack-audit-design.md)

## 文件索引

| 文件 | 阶段 | 状态 |
|---|---|---|
| scan-brief.md | Phase 1 | pending |
| d1-security.md | Phase 2 D1 | pending |
| d2-concurrency.md | Phase 2 D2 | pending |
| d3-error.md | Phase 2 D3 | pending |
| d4-data.md | Phase 2 D4 | pending |
| d5-frontend.md | Phase 2 D5 | pending |
| d6-arch.md | Phase 2 D6 | pending |
| AUDIT-REPORT.md | Phase 4 | pending |
| specs/P0-security.md | Phase 4 | pending |
| specs/P1-error-resilience.md | Phase 4 | pending |
| specs/P2-data-integrity.md | Phase 4 | pending |
| specs/P3-frontend-quality.md | Phase 4 | pending |
| specs/P4-architecture-debt.md | Phase 4 | pending |

## 决策日志

- 2026-06-24: 启动审计, master 锁, 分支 audit/2026-06-24-full-stack-audit
```

### Step 1.4: 写 `scan-brief.md` (核心! 6 个 agent 用同一份模板)

```markdown
# scan-brief.md — 6 维度 agent 统一 prompt 模板

> 用法: 主线程 copy 此模板, 替换 {{DIM}} {{DIM_LABEL}} {{SCAN_FOCUS}} 后, 作为 Agent tool 的 prompt.

## 通用约束 (所有维度共用)

### 你的角色

你是 [{{DIM}}] 维度的扫描 agent. 严格只读 (Read / Grep / Glob / WebSearch / WebFetch), 禁用 Edit / Write / NotebookEdit. 不修改任何业务代码.

### 工作目录

- 项目根: `c:/doc/Code/rag/.claude/worktrees/audit-2026-06-24/`
- 你的产出文件: `c:/doc/Code/rag/.claude/worktrees/audit-2026-06-24/.claude/audit/2026-06-24/d{{N}}-{{DIM_FILE}}.md`
- 模板文件: `c:/doc/Code/rag/.claude/worktrees/audit-2026-06-24/.claude/audit/2026-06-24/scan-brief.md`

### Finding Schema (严格)

每条 finding 必须满足:

```yaml
- id: {{DIM_PREFIX}}-001          # 必填, 3 位数字
  dimension: {{DIM}}              # security|concurrency|error|data|frontend|arch
  severity: critical              # critical|high|medium|low|info
  confidence: high                # high|medium|low (你的初判, verify 阶段会改)
  title: "一句话, ≤ 80 字符"
  file: packages/service/src/...  # 相对项目根
  line: 42                        # 整数
  description: |
    中文, ≥2 句, 解释问题本质.
  evidence: |
    \`\`\`python
    代码引用 ≥3 行 (用 Read 复制)
    \`\`\`
  impact: |
    中文, 解释影响范围 / 攻击场景 / 故障场景.
  fix_sketch: |
    中文, 修复思路 (不实施, 1-3 句).
  references: []                  # 可选, 数组 (cwe-xxx, owasp-xxx, etc.)
```

### 工具限制

- 最多 30 次工具调用
- 最多 ~50k tokens
- 超限自动 stop, 不报错

### 网络限制

{{NETWORK_POLICY}}

### 输出格式

你的**最终回复**必须是 markdown 文本, 顶部带元信息 + finding 列表. 结构:

```markdown
# D{{N}}: {{DIM_LABEL}} 扫描结果

> 扫描时间: 2026-06-24
> Agent 角色: {{ROLE}}
> 工具调用次数: X
> 找到 N 条 finding

## 元信息

- 项目根: ...
- 扫描路径: ...
- 已知跳过: ...
- 备注: ...

## Findings (N 条)

[每条 finding 按 schema 输出]

## 未扫 / 已知缺口

- (列出因工具限制 / 时间限制 / 网络限制无法覆盖的路径)
```

### 质量门禁 (主线程会用)

1. 每条 finding `evidence` ≥ 3 行代码引用
2. `file:line` 必须在 git HEAD 存在 (主线程会验)
3. severity 必填, 必 ∈ {critical, high, medium, low, info}
4. `id` 维度内唯一, 3 位数字

---

## 维度特定指令

### D1: Security

#### 必扫路径

- `packages/service/src/auth/*` (account_service.py, account_settings_*.py, auth_*_router.py, models.py, account_models.py)
- `packages/service/src/middleware/auth.py`
- `packages/service/src/permissions/*` (cache.py, guards.py, router.py)
- `packages/service/src/api/routes.py`
- `packages/service/src/ingest/*` (含 converters/, analyzers/)
- `packages/service/src/storage/object_store.py`
- `packages/service/src/core/redis_client.py`
- `packages/web/app/api/**` (BFF)
- `packages/web/proxy.ts`, `packages/web/middleware.ts`
- `pyproject.toml` + `package.json` (deps)

#### 网络策略

**允许**: WebSearch / WebFetch 查依赖 CVE.
**优先级**: 必扫代码 > 必扫 deps > 可选扩展.

#### 检查项

(详见 spec §3 D1)

#### 角色

- 偏向攻击者视角: 假设每个端点都可能被绕过
- 重点关注: 鉴权缺失/绕过, 注入, SSRF, IDOR, path traversal, 不安全 deserialization, MinIO presign scope, cookie/CSRF, rate limit, PII 泄露, CORS, env/secret 泄露, 弱密码 hash, token 长度/熵/过期

### D2: Concurrency & State

#### 必扫路径

- `packages/service/src/chat/service.py`
- `packages/service/src/memory/*`
- `packages/service/src/ingest/tasks.py`
- `packages/service/src/auth/account_service.py`
- `packages/service/src/eval/*`
- `packages/service/src/scheduler/*`
- 所有 router 中 `session_scope` 用法 (Grep "session_scope")
- 所有 service 层函数 (Grep "def.*session")

#### 网络策略

**禁止**: 不需要网络, 纯本地只读.

#### 检查项

- TOCTOU, double-commit, 软删+唯一约束, cron 重入, JSONB read-modify-write 缺锁, 长事务, 缓存一致性, 状态机缺失, pagination 期间 offset 漂移

### D3: Error handling & Resilience

#### 必扫路径

- `packages/service/src/core/redis_client.py`
- `packages/service/src/storage/object_store.py`
- `packages/service/src/middleware/*`
- 所有 `try/except` 块 (Grep "except Exception" / "except:" / "except BaseException")
- FastAPI exception handlers (Grep "@app.exception_handler")
- 第三方 SDK 调用 (OpenAI, Anthropic, Dify, Neo4j, MinIO)

#### 网络策略

**禁止**: 不需要网络.

#### 检查项

- bare except, 异常吞掉, 缺失超时, retry 风暴, fallback 缺失, 错误响应泄露 stacktrace, PII 进日志, 5xx 缺全局 handler, circuit breaker 缺失, LLM 无 max_tokens 预算

### D4: Data integrity & Migrations

#### 必扫路径

- `packages/service/src/storage/migrations/versions/*.py`
- 所有 `models.py` (auth, chat, eval, approvals, kg, lookups, db)
- `packages/service/src/lookups/*`
- 所有 FK 关系 (Grep "ForeignKey" / "relationship")
- 每个 alembic migration 的 downgrade 段

#### 网络策略

**禁止**: 不需要网络.

#### 检查项

- alembic 可回滚性, ORM/SQL 字段不一致, FK 缺失/错配/ondelete 错, enum 硬编字符串 (违反 lookups 唯一事实源), JSONB 无 schema, 软删+唯一约束冲突, 迁移顺序依赖, deprecated column 残留, 测试用真 migration 缺 isolation

### D5: Frontend pitfalls

#### 必扫路径

- `packages/web/app/[locale]/**`
- `packages/web/lib/chat/*`
- `packages/web/lib/api/*`
- `packages/web/components/common/**`
- `packages/web/proxy.ts`
- `packages/web/middleware.ts`
- `packages/web/i18n/**`
- `packages/web/next.config.ts`

#### 网络策略

**禁止**: 不需要网络.

#### 检查项

- React 19 / Next.js 16 误用 (use(), useFormStatus), useEffect cleanup 缺失, TanStack Query staleTime / cache key 错配, useRouter 从 `next/navigation` 引 (已知 bug 模式), next-intl 漏消息 (zh.json 没注册), bundle 体积过大, ref 持有陈旧 closure, a11y 缺失, 'use client' / 'use server' 边界错, client-secret 泄露到 client bundle, 路由跳转 SSR 串 locale

### D6: Architecture & Convention

#### 必扫路径

- 全局 (但用 Grep 高效, 不全读)
- 对比 `CLAUDE.md`, `packages/service/CLAUDE.md`, `packages/web/CLAUDE.md` 全部规则
- `packages/service/pyproject.toml`
- `packages/web/package.json`
- `bun.lock` + `uv.lock`
- `tests/` 覆盖率报告 (有的话)
- `.env.example` / `.env.local`

#### 网络策略

**禁止**: 不需要网络.

#### 检查项

- 重复代码 (相同 ≥3 行 ≥3 处), 未抽装, 模块边界违反 (跨层 import), 规约违反 (CLAUDE.md 已定但代码未遵守), 测试缺口 (4 模式覆盖), env 散落, 监控/可观测性缺失, 文档与代码脱节, package.json scripts 不一致, pre-commit 钩子绕过
```

### Step 1.5: 写 `docs/audit/2026-06-24-findings.md` (空模板, Phase 4 填)

```markdown
# 全栈代码体检 — 发现清单 (2026-06-24)

> 来源: 2026-06-24 全栈审计 (6 维度)
> 详细发现 + evidence + impact: 见 [.claude/audit/2026-06-24/AUDIT-REPORT.md](../../.claude/audit/2026-06-24/AUDIT-REPORT.md)
> 处理指南: 修完一个 → 改 `- [ ]` 为 `- [x]` + 在后面加 commit hash

**汇总**: 6 维度 / 0 条 finding / 0 条已验证 / 0 条已修 (持续更新, Phase 4 填充)

---

## Critical (必须修)

_(待 Phase 4 填充)_

## High (高优先)

_(待 Phase 4 填充)_

## Medium (中优先)

_(待 Phase 4 填充)_

## Low (低优先)

_(待 Phase 4 填充)_

## Info (提示性)

_(待 Phase 4 填充)_

---

## 修复进度

| 维度 | 总数 | 已修 | 进度 |
|---|---|---|---|
| Security | 0 | 0 | 0% |
| Concurrency | 0 | 0 | 0% |
| Error handling | 0 | 0 | 0% |
| Data integrity | 0 | 0 | 0% |
| Frontend | 0 | 0 | 0% |
| Architecture | 0 | 0 | 0% |
| **合计** | **0** | **0** | **0%** |

---

## 处理流程

1. 修一个问题 → 改对应行 `- [ ]` → `- [x] <commit-hash>`
   例: `- [x] **SEC-001** ... — abc1234`
2. 改完进度表对应维度 +1
3. 大块修复 (≥10 条) 走 spec → plan → implement 循环, 完成后批量勾
4. 误报 / 不修: 保留 `- [ ]`, 在后面加 `(won't fix: 理由)` 标注, 不勾掉
```

### Step 1.6: Commit Task 1

Run:
```bash
cd c:/doc/Code/rag/.claude/worktrees/audit-2026-06-24
git add .claude/audit/2026-06-24/ docs/audit/
git status
git commit -m "chore(audit): 2026-06-24 启动全栈审计 - 目录 + scan-brief + checklist 模板"
```

Expected: 1 commit, 5 个新文件.

---

## Task 2: Phase 2 — 派 6 个 subagent 并行扫描

**Files:**
- Create: `.claude/audit/2026-06-24/d1-security.md` (D1 agent 写)
- Create: `.claude/audit/2026-06-24/d2-concurrency.md` (D2 agent 写)
- Create: `.claude/audit/2026-06-24/d3-error.md` (D3 agent 写)
- Create: `.claude/audit/2026-06-24/d4-data.md` (D4 agent 写)
- Create: `.claude/audit/2026-06-24/d5-frontend.md` (D5 agent 写)
- Create: `.claude/audit/2026-06-24/d6-arch.md` (D6 agent 写)

### Step 2.1: 派 D1 Security agent

主线程 (我) 执行:

```
Agent(
  description: "D1 Security 扫描",
  prompt: <替换 {{}} 后的 D1 prompt, 来自 scan-brief.md §D1>,
  subagent_type: "general-purpose"
)
```

**D1 prompt 模板** (主线程从 scan-brief.md §D1 copy, 替换变量后用):

```
你是 D1 Security 维度的扫描 agent. 严格只读 (Read / Grep / Glob / WebSearch / WebFetch), 禁用 Edit / Write / NotebookEdit.

工作目录: c:/doc/Code/rag/.claude/worktrees/audit-2026-06-24/
你的产出文件: c:/doc/Code/rag/.claude/worktrees/audit-2026-06-24/.claude/audit/2026-06-24/d1-security.md

必扫路径:
- packages/service/src/auth/* (account_service.py, account_settings_*.py, auth_*_router.py, models.py, account_models.py)
- packages/service/src/middleware/auth.py
- packages/service/src/permissions/* (cache.py, guards.py, router.py)
- packages/service/src/api/routes.py
- packages/service/src/ingest/* (含 converters/, analyzers/)
- packages/service/src/storage/object_store.py
- packages/service/src/core/redis_client.py
- packages/web/app/api/** (BFF)
- packages/web/proxy.ts, packages/web/middleware.ts
- pyproject.toml + package.json (deps)

网络策略: 允许 WebSearch / WebFetch 查依赖 CVE.

检查项: 鉴权缺失/绕过, 注入 (SQL/NoSQL/command), SSRF, IDOR, path traversal, 不安全 deserialization, MinIO presign scope, cookie/CSRF, rate limit, PII 泄露, CORS, env/secret 泄露, 弱密码 hash, token 长度/熵/过期.

Finding schema 和输出格式严格按 scan-brief.md §通用约束. 工具调用 ≤ 30 次, tokens ≤ 50k.

写完整 finding 列表到 d1-security.md, 最终回复包含元信息 + finding 数 + 已知跳过.
```

### Step 2.2-2.6: 派 D2-D6 agent (模式同 D1)

D2 模板:
```
你是 D2 Concurrency & State 维度的扫描 agent. 严格只读.

工作目录: c:/doc/Code/rag/.claude/worktrees/audit-2026-06-24/
产出: .claude/audit/2026-06-24/d2-concurrency.md

必扫:
- packages/service/src/chat/service.py
- packages/service/src/memory/*
- packages/service/src/ingest/tasks.py
- packages/service/src/auth/account_service.py
- packages/service/src/eval/*
- packages/service/src/scheduler/*
- Grep "session_scope" / "def.*session" 找所有 session 用法

网络: 禁止.

检查项: TOCTOU, double-commit, 软删+唯一约束, cron 重入, JSONB read-modify-write 缺锁, 长事务, 缓存一致性, 状态机缺失, pagination 期间 offset 漂移.

(其余约束同 D1)
```

D3 模板: 网络禁止, 必扫见 scan-brief.md §D3.
D4 模板: 网络禁止, 必扫见 scan-brief.md §D4.
D5 模板: 网络禁止, 必扫见 scan-brief.md §D5.
D6 模板: 网络禁止, 必扫见 scan-brief.md §D6.

### Step 2.7: 验证 6 个文件都生成

Run:
```bash
cd c:/doc/Code/rag/.claude/worktrees/audit-2026-06-24/.claude/audit/2026-06-24
ls -la d*.md
wc -l d*.md
```

Expected: 6 个 .md 文件, 每个 ≥ 30 行.

### Step 2.8: Commit Task 2 (不 commit 原始 finding, 等 Phase 4 统一)

**不 commit**. 留到 Phase 4 synthesize 时一起 commit.

---

## Task 3: Phase 3 — Adversarial verify (high/critical finding)

**Files:**
- Modify: 6 个 `d*.md` 文件 — 给每条 high/critical finding 加 `verified` + `confidence` + `refuted_reason` 字段

### Step 3.1: 收集所有 high/critical finding

主线程 (我) 执行:

```bash
cd c:/doc/Code/rag/.claude/worktrees/audit-2026-06-24/.claude/audit/2026-06-24
# 提取所有 severity: critical 或 high 的 finding, 输出到 .high-critical-tmp.txt
for f in d1-security.md d2-concurrency.md d3-error.md d4-data.md d5-frontend.md d6-arch.md; do
  echo "=== $f ==="
  awk '/^- id:/{block=$0; getline; while($0 !~ /^- id:/ && NR<=200) {block=block"\n"$0; if($0~/severity: (critical|high)/) {print block; print "---"; block=""} getline}}' $f
done | head -200
```

Expected: ~20-50 条 high/critical finding (预估).

### Step 3.2: 对每条 high/critical finding 派 verifier agent

对每条 finding 派 1 个 Explore agent, prompt:

```
你是 verifier, 尝试反驳这条 finding (默认反驳):

finding 全文:
<paste finding>

文件: {file} 行: {line}

任务:
1. Read {file} 上下文 (前后 30 行)
2. 找出反例 / 错配 / 误判的证据
3. 如果找不出反例 → verified=true, 保留 finding
4. 如果找到反例 → verified=false, 给具体 refuted_reason (≥2 句)

工具调用 ≤ 5 次, tokens ≤ 5k. 最终回复必须是 JSON: {"verified": bool, "confidence": "high|medium|low", "refuted_reason": "string|null"}
```

**降级规则**:
- verifier 工具调用失败 → 默认 verified=true, confidence=low
- verifier 找不到反例 → verified=true
- verifier 找到反例 → verified=false

### Step 3.3: 把 verify 结果写回 d*.md

主线程手动 update 每条 finding 的 YAML frontmatter, 加 `verified: bool`, `confidence: ...`, `refuted_reason: ...` 字段.

工具: 用 Edit, 单条单条改.

### Step 3.4: 统计 verify 结果

Run:
```bash
cd c:/doc/Code/rag/.claude/worktrees/audit-2026-06-24/.claude/audit/2026-06-24
for f in d*.md; do
  verified=$(grep -c "verified: true" $f)
  refuted=$(grep -c "verified: false" $f)
  echo "$f: verified=$verified refuted=$refuted"
done
```

Expected: verified 数 ≥ refuted 数. refuted 率 30-50%.

### Step 3.5: 不 commit, 留 Phase 4 统一

---

## Task 4: Phase 4 — Dedup + Synthesize

**Files:**
- Create: `.claude/audit/2026-06-24/AUDIT-REPORT.md` (汇总报告)
- Create: `.claude/audit/2026-06-24/specs/P0-security.md`
- Create: `.claude/audit/2026-06-24/specs/P1-error-resilience.md`
- Create: `.claude/audit/2026-06-24/specs/P2-data-integrity.md`
- Create: `.claude/audit/2026-06-24/specs/P3-frontend-quality.md`
- Create: `.claude/audit/2026-06-24/specs/P4-architecture-debt.md`
- Modify: `docs/audit/2026-06-24-findings.md` (填充真实 finding)

### Step 4.1: Dedup (同 file:line + issue_signature)

主线程手动:

1. 收集 6 个 d*.md 中所有 verified=true 的 finding
2. 按 `file:line` 精确去重, 保留 severity 最高
3. 按 description 关键词 hash 模糊去重, 加 `related_files: []`
4. 重新编号 ID: `{DIM}-{NNN}` 跨维度统一

工具: 不用脚本, 主线程人工处理 ~50-100 条 (可控).

### Step 4.2: 写 AUDIT-REPORT.md

格式: 见 spec §6 Synthesize 段.

```markdown
# 全栈审计报告 (2026-06-24)

> 来源: 6 维度并行扫描 + adversarial verify
> 原始 finding: [d1-security.md](d1-security.md) ... [d6-arch.md](d6-arch.md)
> 日常维护 checklist: [docs/audit/2026-06-24-findings.md](../../../docs/audit/2026-06-24-findings.md)

## 元信息

- 扫描时间: 2026-06-24
- 维度: 6 (Security / Concurrency / Error / Data / Frontend / Architecture)
- 总 finding: N
- verified: M
- refuted: K
- 误报率: K/M %

## 汇总表 (按严重度)

| ID | 维度 | 严重度 | 标题 | file:line | verified | refuted |
|---|---|---|---|---|---|---|
| SEC-001 | security | critical | Redis cache ... | src/core/...:42 | ✓ | - |
| ... | | | | | | |

## 按维度详情

### Security (D1)
[N 条 finding 详情, 含 evidence + impact + fix_sketch]

### Concurrency (D2)
...

(其余维度类同)

## Spec 草稿映射

- [P0-security](specs/P0-security.md): N 条 finding
- [P1-error-resilience](specs/P1-error-resilience.md): N 条
- [P2-data-integrity](specs/P2-data-integrity.md): N 条
- [P3-frontend-quality](specs/P3-frontend-quality.md): N 条
- [P4-architecture-debt](specs/P4-architecture-debt.md): N 条
```

### Step 4.3: 写 5 份 P?-xxx.md spec 草稿

每份 spec 草稿格式 (简化, 强调是草稿):

```markdown
# P0 - 安全修复 spec 草稿 (2026-06-24)

> ⚠️ 草稿, 未实施. 真正实施需走: brainstorm → spec → plan → implement 循环.
> 来源: [AUDIT-REPORT.md](../AUDIT-REPORT.md) §D1 + D2 (并发安全相关)
> 关联 checklist: [docs/audit/2026-06-24-findings.md](../../../../docs/audit/2026-06-24-findings.md)

## 范围

- SEC-001, SEC-002, ... (N 条)

## 修复策略

1. [修复思路 1]
2. [修复思路 2]
...

## 不在本文范围

- 实施代码 (留到 plan + implement 阶段)
- P1-P4 其他维度 finding
```

(P1-P4 模式相同, 范围不同)

### Step 4.4: 填充 `docs/audit/2026-06-24-findings.md`

按 spec §13 格式, 把所有 verified finding 填进去, 按严重度分组, 每个带 `- [ ]` checkbox + file:line + 链接.

### Step 4.5: Commit Task 4

Run:
```bash
cd c:/doc/Code/rag/.claude/worktrees/audit-2026-06-24
git status
git add .claude/audit/2026-06-24/ docs/audit/
git commit -m "chore(audit): 2026-06-24 全栈审计完成 - 6 维度 N 条 finding + 5 份 spec 草稿 + checklist"
```

Expected: 1 commit, 14+ 个新文件.

---

## Task 5: 合并回 master + 通知

**Files:**
- Modify: master 分支 — merge audit 分支

### Step 5.1: Push audit 分支

Run:
```bash
cd c:/doc/Code/rag/.claude/worktrees/audit-2026-06-24
git push -u origin audit/2026-06-24-full-stack-audit
```

Expected: push 成功, branch 在 origin 可见.

### Step 5.2: 通知用户

主线程输出:

```
✅ 全栈审计完成

- 6 维度 / N 条 finding / M 条 verified
- 汇总报告: .claude/audit/2026-06-24/AUDIT-REPORT.md
- 日常维护 checklist: docs/audit/2026-06-24-findings.md
- 5 份 spec 草稿: .claude/audit/2026-06-24/specs/P0-P4.md
- 分支: audit/2026-06-24-full-stack-audit (已 push)

下一步: review AUDIT-REPORT.md, 决定哪些 P0-P4 spec 进入下一个 brainstorm → spec → plan → implement 循环.
修完一个 finding, 在 checklist 把对应行 `- [ ]` 改 `- [x] <commit-hash>`.
```

### Step 5.3: 清理 worktree (可选)

让用户决定. 不自动删, 等你 review 完再说.

---

## Self-Review (写完 plan 自查)

### 1. Spec 覆盖

- §1 背景 ✅ Task 1 Step 1.3 README 写明来源
- §2 总体架构 ✅ Task 1-5 完整覆盖 Phase 1-5
- §3 6 维度扫描范围 ✅ Task 2 Step 2.1-2.6, scan-brief.md 完整列必扫路径
- §4 Finding Schema ✅ scan-brief.md §通用约束强制要求
- §5 Adversarial Verify ✅ Task 3 完整覆盖
- §6 Dedup + Synthesize ✅ Task 4 Step 4.1-4.2
- §7 错误处理 / 防失速 ✅ scan-brief.md 工具限制 + Task 2 Step 2.7 验证
- §8 产出物清单 ✅ Task 1-4 文件结构完整, 14 个文件
- §9 测试 / 质量门禁 ✅ scan-brief.md §质量门禁 + Task 3 Step 3.4 统计
- §10 不在范围 ✅ Task 1-5 全部不涉及业务代码
- §11 风险与缓解 ✅ Task 1-5 内置降级
- §12 后续流程 ✅ Task 5 Step 5.2 通知
- §13 问题列表格式 ✅ Task 1 Step 1.5 + Task 4 Step 4.4

### 2. Placeholder 扫描

- 全文搜 "TBD" / "TODO" / "implement later" / "fill in details" → 0 命中
- 全文搜 "appropriate" / "handle edge cases" / "similar to" → 0 命中
- 必填代码段都给了实际内容 ✅

### 3. 类型一致性

- 文件名一致: d1-security.md ... d6-arch.md (跨 Task 1-4 一致) ✅
- ID 格式一致: {DIM}-{NNN} ✅
- spec 引用一致: 2026-06-24-full-stack-audit-design.md (跨 Task 1-5 一致) ✅
- finding schema 字段一致: id/dimension/severity/confidence/title/file/line/description/evidence/impact/fix_sketch/references (跨 scan-brief.md 和验证段一致) ✅

### 4. 修复 1 处

Task 2 Step 2.8 写"不 commit", 但 Task 4 Step 4.5 又 commit — 逻辑 OK, 因为 d*.md 在 Phase 4 synthesize 时一起 commit, 避免中间状态污染. 不修复.

---

## 执行交接

Plan 完成并保存到 `docs/superpowers/plans/2026-06-24-full-stack-audit.md`.

**两个执行选项**:

1. **Subagent-Driven (推荐)** - 我每个 Task 派 1 个 fresh subagent, 任务间 review, 快速迭代
2. **Inline Execution** - 在本会话用 executing-plans 批量执行, checkpoint review

**选哪种方式?**
