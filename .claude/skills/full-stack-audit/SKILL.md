---
name: full-stack-audit
description: "Use when running a 6-dimension adversarial-verified full-stack audit of this RAG project (Security / Concurrency / Error / Data / Frontend / Architecture). TRIGGER when: weekly security review, pre-release audit, before a major refactor spec, or to baseline cross-cutting tech debt. DO NOT TRIGGER when: you want to fix code (this skill NEVER writes to packages/*/src or tests/), or for a single-dimension quick scan (use /code-quality-scan instead). Always 6 parallel subagents + adversarial verify + synthesize, output to docs/audit/<YYYY-MM-DD>/."
---

# /full-stack-audit

6 维度全栈深度审计 (Security / Concurrency / Error / Data / Frontend / Architecture), 含 adversarial verify 阶段过滤误报, 出 AUDIT-REPORT + 5 份 spec 草稿 + 1 份日常 checklist. **不修任何业务代码**.

## Usage

```
/full-stack-audit                        # 跑全部 6 维度 + verify + synthesize
/full-stack-audit --only d1              # 只跑 Security 维度 (跳过 verify + spec 草稿)
/full-stack-audit --only d3              # 只跑 Error handling 维度
```

**可用维度** (`--only`):
- `d1` Security — 鉴权/注入/SSRF/IDOR/CORS/deps CVE
- `d2` Concurrency — TOCTOU/双写/cron 重入/锁/缓存一致性
- `d3` Error handling — bare except/超时/retry/stacktrace 泄露/PII 进日志
- `d4` Data integrity — alembic 可回滚/FK 错配/enum 硬编/JSONB schema
- `d5` Frontend — React 19 误用/useRouter bug/TanStack Query/next-intl/a11y
- `d6` Architecture — 重复代码/模块边界/规约违反/测试缺口/可观测性

## When to Use

| 场景 | 说明 |
|---|---|
| **每周安全审计** | D1 是最优先 (鉴权/注入) |
| **大重构之前** | 看清债务再动, 避免越改越乱 |
| **Release 前体检** | 阻断 P0 critical |
| **新成员加入** | 让 audit 报告作为项目导览 |
| **代码质量专项之后** | 跟 `/code-quality-scan` 互补 — 那个看"什么坏了", 这个看"为什么坏" |

**跟 `/code-quality-scan` 的区别**:
- `code-quality-scan` 看 4 维度 (测试/type/lint/严格模式), 出**路线图** (P0-P5 + 建议)
- `full-stack-audit` 看 6 维度 (业务/安全/数据/架构), 出**finding 列表** + 5 份 spec 草稿
- 前者快 (10-15 min), 后者深 (30-60 min, 因有 verify 阶段)

## What You Must Do When Invoked

**4 阶段强制流程**:

1. **Phase 1: Prepare** — 拿日期, 创建目录, 写 scan-brief.md (含 finding schema)
2. **Phase 2: Dispatch 6 parallel subagents** — D1-D6 同一 message 派发, `run_in_background: true`
3. **Phase 3: Adversarial verify** — 只对 verified=true 的 high/critical finding 派 verifier agent
4. **Phase 4: Synthesize** — dedup + AUDIT-REPORT.md + 5 份 P?-xxx spec 草稿 + 更新 checklist, 1 commit

**Hard rules**:
- ❌ 永不修改 `packages/*/src/**` / `packages/service/tests/**` / 任何 lockfile / CI 配置
- ❌ 永不在 subagent prompt 里硬编码 finding 数字 / 路径列表 (用 scan-brief.md 模板化)
- ✅ 报告输出到 `docs/audit/<DATE>/` (符合 README 约定)
- ✅ Finding 必须满足 schema (id/dimension/severity/confidence/title/file/line/description/evidence/impact/fix_sketch)
- ✅ evidence 段必须含 ≥3 行真实代码引用 (用 Read 复制, 不编)

## Phase 1: Prepare

主线程执行:

```bash
DATE=$(date +%Y-%m-%d)
cd c:/doc/Code/rag
mkdir -p docs/audit/$DATE

# 把今天日期 + 输出路径注入到所有 subagent prompt
echo "DATE=$DATE OUTPUT_DIR=docs/audit/$DATE"
```

**写 scan-brief.md** 到 `docs/audit/$DATE/scan-brief.md`, 含:
- 通用 finding schema (YAML)
- 6 个维度的必扫路径 + 网络策略 (D1 允许网络, D2-D6 禁止)
- 工具限制 (30 次 / 50k tokens / agent)
- 质量门禁 (evidence ≥ 3 行 / file:line 必在 git HEAD / severity 必填)

详细模板见 [references/scan-brief-template.md](references/scan-brief-template.md).

## Phase 2: Dispatch 6 parallel subagents

**同一 message 派发 6 个 Agent** (都 `run_in_background: true`, 都 `subagent_type: "general-purpose"`):

| Agent | 维度 | 网络 | 产出文件 |
|---|---|---|---|
| D1 | Security | ✅ 允许 (查 deps CVE) | `docs/audit/$DATE/d1-security.md` |
| D2 | Concurrency | ❌ | `docs/audit/$DATE/d2-concurrency.md` |
| D3 | Error handling | ❌ | `docs/audit/$DATE/d3-error.md` |
| D4 | Data integrity | ❌ | `docs/audit/$DATE/d4-data.md` |
| D5 | Frontend | ❌ | `docs/audit/$DATE/d5-frontend.md` |
| D6 | Architecture | ❌ | `docs/audit/$DATE/d6-arch.md` |

完整 prompt 模板见 [references/dim-prompts.md](references/dim-prompts.md) — 每个维度的 prompt 是 scan-brief.md 模板 + 该维度的"必扫路径 + 检查项 + 角色提示".

**Wait**: 等 6 个 background agent 全部 complete (会收到 task notification).

**验证**: 6 个 .md 都存在, 每个 ≥ 30 行.

## Phase 3: Adversarial verify (high/critical finding only)

**只对 high/critical finding 派 verifier**, 目的: 反驳误报, 提升置信度.

### Step 3.1: 提取 high/critical finding

主线程 (用 Read 读 6 个 d*.md, 不是 grep):
- 解析每条 finding 的 YAML frontmatter
- 收集 severity ∈ {critical, high} 的所有 finding
- 预估 ~20-50 条 (视项目规模)

### Step 3.2: 派 verifier agent (每条 finding 1 个)

每个 verifier 的 prompt 模板:

```
你是 verifier, 尝试反驳这条 finding (默认反驳):

finding 全文:
<paste YAML>

文件: {file} 行: {line}

任务:
1. Read {file} 上下文 (前后 30 行)
2. 找出反例 / 错配 / 误判的证据
3. 如果找不出反例 → verified=true, 保留 finding
4. 如果找到反例 → verified=false, 给具体 refuted_reason (≥2 句)

工具调用 ≤ 5 次, tokens ≤ 5k. 最终回复必须是 JSON:
{"verified": bool, "confidence": "high|medium|low", "refuted_reason": "string|null"}
```

**降级规则**:
- verifier 工具调用失败 → 默认 verified=true, confidence=low
- verifier 找不到反例 → verified=true
- verifier 找到反例 → verified=false

### Step 3.3: 写回 d*.md

主线程 Edit 每条 high/critical finding 的 YAML, 加字段:
- `verified: bool`
- `confidence: "high|medium|low"`
- `refuted_reason: "string|null"`

medium/low/info finding 不做 verify, 保留原 confidence.

## Phase 4: Synthesize

主线程执行 (不派 subagent):

### Step 4.1: Dedup

1. 收集 6 个 d*.md 中所有 finding (verified=true 优先, refuted 排除)
2. 按 `file:line` 精确去重, 保留 severity 最高
3. 按 description 关键词 hash 模糊去重, 加 `related_files: []`
4. 重新编号 ID: `{DIM}-{NNN}` 跨维度统一 (例: SEC-001, CONC-001, ERR-001, DATA-001, FE-001, ARCH-001)

### Step 4.2: 写 AUDIT-REPORT.md

格式见 [references/report-templates.md §AUDIT-REPORT](references/report-templates.md). 关键字段:
- 元信息 (日期 / 维度数 / finding 总数 / verified / refuted / 误报率)
- 汇总表 (按严重度, 含 ID / 维度 / 标题 / file:line / verified)
- 6 个维度详情段 (每段: finding 列表 + evidence + impact + fix_sketch)
- Spec 草稿映射 (P0-P4 ↔ finding 范围)

### Step 4.3: 写 5 份 P?-xxx spec 草稿

每份 spec 草稿格式 (强调"未实施"):

```markdown
# P{N} - {主题} 修复 spec 草稿 (YYYY-MM-DD)

> ⚠️ 草稿, 未实施. 真正实施需走: brainstorm → spec → plan → implement 循环.
> 来源: [AUDIT-REPORT.md](../AUDIT-REPORT.md) §D{?}
> 关联 checklist: [docs/audit/YYYY-MM-DD-findings.md](../../YYYY-MM-DD-findings.md)

## 范围
- {ID}-001, {ID}-002, ... (N 条)

## 修复策略
1. [修复思路 1]
2. [修复思路 2]

## 不在本文范围
- 实施代码 (留到 plan + implement 阶段)
- 其他 P 维度 finding
```

5 份 spec 草稿的命名 (按优先级):
- `P0-security.md` (D1 + D2 的安全相关)
- `P1-error-resilience.md` (D3)
- `P2-data-integrity.md` (D4)
- `P3-frontend-quality.md` (D5)
- `P4-architecture-debt.md` (D6 + D2 的非安全部分)

### Step 4.4: 填充 checklist

创建 `docs/audit/YYYY-MM-DD-findings.md` (首次扫描) 或追加到现有文件 (后续扫描). 格式:

```markdown
# 全栈代码体检 — 发现清单 (YYYY-MM-DD)

> 来源: 6 维度并行扫描 + adversarial verify
> 详细 finding: [docs/audit/YYYY-MM-DD/AUDIT-REPORT.md](YYYY-MM-DD/AUDIT-REPORT.md)
> 处理指南: 修完一个 → 改 `- [ ]` 为 `- [x]` + commit hash

**汇总**: 6 维度 / N 条 finding / M verified / K refuted

---

## Critical (必须修)
- [ ] **SEC-001** ... — `src/...:42`

## High (高优先)
- ...

## Medium / Low / Info
- ...

## 修复进度
| 维度 | 总数 | 已修 | 进度 |
|---|---|---|---|
| Security | N | 0 | 0% |
| ... | ... | ... | ... |
```

### Step 4.5: 更新 README + commit

```bash
cd c:/doc/Code/rag
# 更新 docs/audit/README.md 文档列表 (加新一行)
git add docs/audit/$DATE/ docs/audit/$DATE-findings.md docs/audit/README.md
git status
git commit -m "chore(audit): $DATE 全栈审计完成 - 6 维度 N 条 finding + 5 份 spec 草稿 + checklist"
```

Expected: 1 commit, 6+ 个 d*.md + 1 AUDIT-REPORT + 5 spec 草稿 + 1 checklist + 1 README 更新.

## Quick Reference

**6 维度对应 ID 前缀**:
- D1 Security → `SEC-NNN`
- D2 Concurrency → `CONC-NNN`
- D3 Error → `ERR-NNN`
- D4 Data → `DATA-NNN`
- D5 Frontend → `FE-NNN`
- D6 Architecture → `ARCH-NNN`

**Finding schema (强制)**:
```yaml
- id: SEC-001                # 必填, 3 位数字
  dimension: security        # 必填, 6 选 1
  severity: critical         # 必填, 5 选 1
  confidence: high           # 必填, 3 选 1
  title: "一句话 ≤ 80 字符"
  file: packages/service/src/...  # 相对项目根
  line: 42
  description: |             # ≥ 2 句中文
    ...
  evidence: |                # ≥ 3 行真实代码引用
    ```python
    ...
    ```
  impact: |                  # 解释影响范围
    ...
  fix_sketch: |              # 修复思路, 1-3 句
    ...
  references: []             # 可选, cwe-xxx 等
  verified: bool             # Phase 3 加
  confidence_after: ...      # Phase 3 加
  refuted_reason: ...        # Phase 3 加 (verified=false 时)
```

**P0-P4 spec 草稿映射**:
```
P0-security.md       ← D1 (全部) + D2 (安全相关, 如 TOCTOU 鉴权)
P1-error-resilience.md  ← D3 (全部)
P2-data-integrity.md    ← D4 (全部)
P3-frontend-quality.md  ← D5 (全部)
P4-architecture-debt.md ← D6 (全部) + D2 (非安全, 如 cron 重入)
```

## Anti-Patterns

❌ 派 6 个 agent 时不传 `run_in_background: true` → 串行, 浪费 30+ min
❌ D1 agent 不用 WebSearch 查 deps CVE → 漏掉 1/3 的安全 finding
❌ finding 的 `evidence` 段写 "代码看起来像..." 而非真实 Read 复制 → 主线程 verify 时找不到原文件
❌ 跳过 Phase 3 adversarial verify → 误报率 50%+, 浪费 spec 作者时间
❌ 把所有 finding 都塞进 P0 spec → spec 太大无法 review
❌ 修改业务代码 → 违反只读原则, 这是 audit 不是 fix
❌ 漏掉 medium/low/info finding → 这些往往揭示技术债, 比 critical 更值得归档
