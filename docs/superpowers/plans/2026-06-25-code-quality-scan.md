# 代码质量快照扫描实施 Plan (2026-06-25)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 4 路并行扫出 pytest/vitest fail + pyright ignore + lint ignore + pyright 严格模式可行性, 不修任何代码. 出 5 份报告到 `docs/audit/`.

**Architecture:** 主线程协调, 4 个 subagent (Explore/general-purpose) 并行扫描 → 主线程 synthesize → 出路线图. 所有 subagent 只读不写.

**Tech Stack:**
- pytest / vitest (测试运行)
- pyright (类型检查, 严格模式测试)
- oxlint / ruff (lint 检查)
- Read / Grep / Glob (subagent 只读)
- WebSearch / WebFetch (不需要, 纯本地)

**前置依赖:**
- 当前在 master 分支
- spec 已 commit (`f860e642`)

---

## 文件结构 (本次实施新增)

| 路径 | 责任 |
|---|---|
| `docs/audit/2026-06-25-test-failures.md` | A1: 测试失败分类 |
| `docs/audit/2026-06-25-pyright-ignores.md` | A2: type:ignore 可删性 |
| `docs/audit/2026-06-25-lint-ignores.md` | A3: lint 可删性 |
| `docs/audit/2026-06-25-pyright-strict-audit.md` | A4: 严格模式可行性 |
| `docs/audit/2026-06-25-code-quality-plan.md` | Phase 2: 合成路线图 |

**不动**: 任何业务代码, 任何 `packages/*/src/**`, 任何 `tests/**`, 任何 config / lockfile.

---

## Task 1: 派 4 个 subagent 并行扫描 (A1-A4)

**Goal:** 4 路并行, 各写一份报告到 `docs/audit/`. 全部只读.

### Step 1.1: 派 A1 Test Scanner

主线程执行:

```bash
Agent(
  description: "A1 Test Scanner",
  prompt: <以下 A1 prompt>,
  subagent_type: "general-purpose",
  run_in_background: true
)
```

**A1 prompt**:

```
你是 A1 Test Scanner agent. 严格只读 (Read / Grep / Glob / Bash), 禁用 Edit / Write / NotebookEdit. 不修改任何业务代码.

项目根: c:/doc/Code/rag/
工作目录: c:/doc/Code/rag/

## 你的任务

1. 跑 pytest: `cd packages/service && uv run pytest -v --tb=short 2>&1 | head -300`
2. 跑 vitest: `cd packages/web && bun run test 2>&1 | head -200`
3. 收集全部 FAILED/ERROR, 每条按以下格式输出:

```
### [类别] test_file.py::test_name

- **文件**: `tests/.../test_file.py:行号`
- **错误**: <错误信息摘要 100 字>
- **推测根因**: <1-3 句>
- **上下文**: <2-3 句>
```

类别取值: [bug] [env] [regression] [flaky] [config] [pg-violation]

### 专项：检出连真 PG 的测试

按 spec §3 "检出连真 PG 的测试" 专项 — 识别 [pg-violation]. 方法:
1. 看 failures 里含 `psycopg` / `OperationalError` / `connection refused` / `FATAL` 字样的错误
2. Grep "db_session\|session_scope\|RAG_DB_URL\|PG_HOST\|PG_DATABASE" 在 tests/ 目录
3. Grep "pytest.mark.integration" — 集成测试标记 (这些不是违规, 模式 2 集成测试允许)
4. 对每处: Read 测试文件 → 判断是模式 2 db_session fixtrue 还是真连 PG

### 分类说明

- [bug]: 真实 bug, 有复现步骤
- [env]: PG/Redis 未起, docker 没跑, 网络不通 — 如果发现 pytest 连不上 PG, 识别后标注但**仍然继续扫**
- [regression]: 之前 33 个 commit 引入的
- [flaky]: 偶发 (时间戳/竞争/顺序依赖)
- [config]: 测试配置错误 (mock 不对 / fixture 缺)
- [pg-violation]: 违反项目强制规范 (测试隔离 4 模式), 须重写为模式 1 mock

### 后段: 连真 PG 违规清单

产出额外表格:

```
| 文件 | 违规类型 | 建议 |
|---|---|---|
| tests/auth/test_router.py:xx | 直调 session_scope | [pg-violation] 须重写为 mock session |
| tests/integration/test_db_session.py:12 | db_session fixtrue | 模式 2 集成测试, opt-in 可接受 |
```

### 工具限制
- 最多 30 次工具调用
- 最多 ~50k tokens
- 写产出文件: `docs/audit/2026-06-25-test-failures.md` (用 Write 工具)

### 最终回复

status (DONE / DONE_WITH_CONCERNS) + finding 总数 + 按类别分组 + 文件行数
```

### Step 1.2: 派 A2 Pyright Scanner

**A2 prompt** (差异部分):

```
你是 A2 Pyright Scanner agent. 严格只读.

项目根: c:/doc/Code/rag/

## 你的任务

1. 读 pyrightconfig.json 现状: Read packages/service/pyrightconfig.json
2. 列出全部 type: ignore: Grep "type: ignore" 在 src/ 和 tests/, 排除 __pycache__ 和 .venv

3. 对前 30 条 ignore, 每条:
   a. Read 该行 + 上下文 20 行
   b. 尝试删 ignore: 改文件, 跑 `uv run pyright <file>` (pyright 在 .venv 里)
   c. 如果 pyright 不报了 → [dead]
   d. 如果报错:
      - 报第三方库问题 → [stub] (SQLAlchemy ORM / httpx / pymupdf)
      - 报自己代码类型问题 → [fixable] + 写怎么改
      - 报 optional/union 问题 → [rule-up] (升规则时会炸)

4. 检查 tests/ 里的 `type: ignore` 有没有用裸 `# type: ignore$` (没带错误码的)
   按 CLAUDE.md 强制规范: 必须带具体错误码 `# type: ignore[错误码]`

5. 写产出文件 `docs/audit/2026-06-25-pyright-ignores.md`

格式:
```
| ID | file:line | 代码 | 标签 | 备注 |
|---|---|---|---|---|
| PYR-001 | src/chat/service.py:307 | `.rowcount  # type: ignore[attr-defined]` | [stub] | SQLAlchemy 推断限制 |
```

### 工具限制
- 最多 30 次工具调用
- pyright 每次只跑单文件 (`uv run pyright <file>` 不在 packages/service/ 目录可能需要指定 cwd)
- 写产出, 不修代码
```

### Step 1.3: 派 A3 Lint Scanner

**A3 prompt** (差异部分):

```
你是 A3 Lint Scanner agent. 严格只读.

项目根: c:/doc/Code/rag/

## 你的任务

1. 统计全部 oxlint/eslint disable:
   Grep "eslint-disable\|oxlint-disable" packages/web/app/ packages/web/lib/ packages/web/components/ packages/web/e2e/ --include="*.ts" --include="*.tsx"

2. 统计全部 noqa:
   Grep "noqa" packages/service/src/ --include="*.py" | grep -v noqa:F401 | grep -v noqa:E402

3. 对 23 处 noqa: 每处 Read 上下文 → 归类
4. 对 172 处 oxlint: 前 50 条深度分析 (Read + 判断), 其余只列规则名+文件+粗略归类

5. Read packages/web/.oxlintrc.json — 看规则配置
   找出可以调到 rule config 而不是 file-level 的 (如: no-magic-numbers 在测试文件大量出现, 可以考虑在 oxlintrc 里加 overrides)

6. 写产出文件 `docs/audit/2026-06-25-lint-ignores.md`

格式:
```
| ID | file:line | 规则 | 标签 | 备注 |
|---|---|---|---|---|
| LINT-001 | api/approvals.test.ts:17 | no-ternary | [fixable-config] | 测试环境应豁免 no-ternary |
| LINT-002 | evaluate-new-form.tsx:42 | max-statements | [keep] | 函数逻辑合理 |
| NOQA-001 | ingest/api.py:7 | E402 | [keep] | 故意: import 放在 dataclass 后 |
```

标签: [fixable-code] [fixable-config] [keep] [dead] [downgrade]
```

### Step 1.4: 派 A4 Pyright Strict Analyzer

**A4 prompt** (差异部分):

```
你是 A4 Pyright Strict Analyzer agent. 严格只读. **每次修改 pyrightconfig.json 后必须恢复原状**.

项目根: c:/doc/Code/rag/

## 你的任务

当前 pyrightconfig.json (basic + 6 个 none):
```json
{
  "typeCheckingMode": "basic",
  "reportMissingTypeStubs": "none",
  "reportUnknownMemberType": "none",
  "reportUnknownVariableType": "none",
  "reportUnknownArgumentType": "none",
  "reportUnknownParameterType": "none",
  "reportUnknownLambdaType": "none"
}
```

### 逐级测试 (每级独立, 不累积, 每级后恢复)

**L1**: 删 5 个 reportUnknown* none → "warning"
- 改 pyrightconfig.json → `uv run pyright` → 记每条规则的新 error 数
- 恢复 pyrightconfig.json

**L2**: typeCheckingMode: "standard" 
- 改 → `uv run pyright` → 记总 error 数 + top 10 文件
- 恢复

**L3**: standard + 逐个加 strict 规则
- 改 → 每加一条跑一次 pyright → 记命中数
- 规则示例: reportOptionalMemberAccess, reportOptionalSubscript, reportOptionalCall
- 恢复

**L4**: typeCheckingMode: "strict"
- 改 → `uv run pyright` → 记总 error 数
- 如果超过 1000 → 记录 "too many (>1000)" 跳过
- 恢复

### 产出格式

```
## L1: 删 reportUnknown* none

| 规则 | 新 error 数 | 重灾区 |
|---|---|---|
| reportUnknownMemberType | 42 | src/permissions/, src/lookups/ |
| reportUnknownParameterType | 18 | ... |

## L2: standard mode

总 error: 156
Top 5 文件: src/auth/router.py:23, ...
```

### 工具限制
- 最多 20 次工具调用
- 每次改后必须恢复 pyrightconfig.json (git checkout 或 sed 还原)
- 写 `docs/audit/2026-06-25-pyright-strict-audit.md`
```

### Step 1.5: 等待 4 个 agent 完成

主线程等通知.

### Step 1.6: 验证 4 个产出文件

Run:
```bash
cd c:/doc/Code/rag
ls -la docs/audit/2026-06-25-*.md
wc -l docs/audit/2026-06-25-*.md
```

Expected: 4 个文件, 每个 ≥ 20 行.

### Step 1.7: 不 commit, 等 Phase 2 统一

---

## Task 2: Phase 2 — Synthesize

**Files:**
- Create: `docs/audit/2026-06-25-code-quality-plan.md` (路线图)
- Modify: `docs/audit/2026-06-24-findings.md` (追加质量改进项)

### Step 2.1: 合并 4 份报告

主线程手动:
1. 拿 A1-A4 报告
2. 跨报告去重 (同一条 lint ignore 同时出现在 A2 和 A3 → 合并)
3. 按 6 级优先级排序

优先级表:

| 优先级 | 来源 | 行动 |
|---|---|---|
| P0 | A1 [bug] + [regression] | 立即修复 |
| P1 | A2 [fixable] + A3 [dead] + A3 [downgrade] | 逐个清理 |
| P2 | A3 [fixable-config] + A4 可行建议 | 规则配置调整 |
| P3 | A3 [keep] | 不动 |
| P4 | A2 [stub] + A3 [keep] | 不动 |
| P-scan | A1 [pg-violation] | 专题: 重写为模式 1 mock |

### Step 2.2: 写路线图

格式:

```
# 代码质量路线图 (2026-06-25)

> 来源: 4 维度并行扫描
> 原始报告: [test-failures.md](2026-06-25-test-failures.md) ...

## 汇总

| 优先级 | 数量 | 主要行动 |
|---|---|---|
| P0 | N | 修 test bug |
| P1 | N | 清 type:ignore / lint 过期项 |
| P2 | N | 调规则配置 + pyright 升级 |
| P-scan | N | 重写 PG 违规测试 |

## P0: 测试 bug (N 条)

[列表 + 根因 + 建议]

## P1: ignore 清理 (N 条)

[列表 + 文件 + 建议]

## P2: 配置 + 严格模式建议

[列表]

## P-scan: PG 违规测试

[列表 + 每条的 mock 策略]
```

### Step 2.3: 更新 checklist

按格式追加到 `docs/audit/2026-06-24-findings.md`:

```markdown
---

## 2026-06-25 代码质量快照 (不修, 仅扫描)

| 维度 | 找到 | 说明 |
|---|---|---|
| pytest fail | N | 详见 [2026-06-25-test-failures.md](2026-06-25-test-failures.md) |
| vitest fail | N | 同上 |
| pyright ignore fixable | N | 详见 [2026-06-25-pyright-ignores.md](2026-06-25-pyright-ignores.md) |
| lint ignore fixable | N | 详见 [2026-06-25-lint-ignores.md](2026-06-25-lint-ignores.md) |
| pyright strict 建议 | N | 详见 [2026-06-25-pyright-strict-audit.md](2026-06-25-pyright-strict-audit.md) |
| PG 违规测试 | N | 详见 [2026-06-25-test-failures.md](#连真-pg-违规清单) |
```

### Step 2.4: Commit

```bash
cd c:/doc/Code/rag
git add docs/audit/2026-06-25-*.md docs/audit/2026-06-24-findings.md
git commit -m "docs(audit): 2026-06-25 代码质量快照扫描 - 4 维度报告 + 路线图"
```

Expected: 1 commit, 5+ 个新文件.

---

## Task 3: 通知用户

输出:
```
✅ 代码质量快照扫描完成

- 4 维度 / N 条 finding / 路线图已就绪
- 报告: docs/audit/2026-06-25-{test-failures,pyright-ignores,lint-ignores,pyright-strict-audit,code-quality-plan}.md
- 分支: master

下一步: review code-quality-plan.md → 决定哪些进入后续 spec → plan → implement 循环
```

---

## Self-Review

### 1. Spec 覆盖

- §3 A1 Test Scanner ✅ Task 1.1
- §4 A2 Pyright Scan ✅ Task 1.2
- §5 A3 Lint Scan ✅ Task 1.3
- §6 A4 Pyright Strict ✅ Task 1.4
- §7 Phase 2 Synthesize ✅ Task 2
- §8 错误处理 ✅ Task 1.5-1.6
- §9 产出物清单 ✅ Task 2.4
- pg-violation 类别 ✅ 在 A1 prompt 里强调

### 2. Placeholder 扫描

- 全文搜 "TBD" / "TODO" → 0
- "appropriate" / "implement later" → 0
- 代码块都给了实际内容 ✅

### 3. 类型一致性

- 4 个 agent prompt 统一结构 ✅
- 分类标签 ([bug] [env] [fixable] [dead] [keep] 等) 跨 task 一致 ✅
- 产出文件路径统一 `docs/audit/2026-06-25-*.md` ✅

---

## 执行交接

Plan 完成.

**两个执行选项:**

1. **Subagent-Driven (推荐)** - 我派 4 个 subagent 并行扫, 任务间 review, 快速迭代
2. **Inline Execution** - 批量执行, checkpoint review

注意: 4 个 agent 是独立文件域 + 全只读, 可以安全并行派发. 但需要 A1 先跑 pytest/vitest, 这依赖 Docker PG 和本地依赖, 可能失败.

**选哪种方式?**
