---
name: code-quality-scan
description: "Use when running a 4-dimension read-only code quality snapshot of this RAG project (pytest/vitest failures + pyright type:ignore + ruff/oxlint ignore + pyright strict feasibility). TRIGGER when: before/after a code-quality cleanup spec, weekly health check, or to baseline what's broken. DO NOT TRIGGER when: you want to fix code (this skill NEVER writes to packages/*/src or tests/) or for a single-file lint question (use ruff/oxlint directly). Always 4 parallel subagents + 1 synthesis, output to docs/audit/<YYYY-MM-DD>/."
---

# /code-quality-scan

4 路并行只读扫描本项目代码质量现状 (测试 fail / pyright ignore / lint ignore / pyright 严格模式), 出 5 份报告 + 1 份合成路线图. **不修任何业务代码**.

## Usage

```
/code-quality-scan                       # 默认今天, 扫描当前 master
/code-quality-scan --only tests          # 只跑 A1 测试维度
/code-quality-scan --only strict         # 只跑 A4 严格模式 (其他维度跳过)
```

## When to Use

| 场景 | 说明 |
|---|---|
| **Cleanup spec 之前** | 基线扫描, 知道"现状坏到什么程度" |
| **Cleanup spec 之后** | 验证修复效果, 对比基线 |
| **每周健康检查** | 跟踪回归, 防止坏代码累积 |
| **PR 模板** | 引用本次路线图作为 spec 起点 |

## What You Must Do When Invoked

**5 步强制流程, 不可跳过**:

1. **Prepare** — 拿日期, 跑基线 grep 统计当前 noqa / type:ignore / oxlint ignore 数量
2. **Create output dir** — `mkdir -p docs/audit/<DATE>/`
3. **Dispatch 4 parallel subagents** — 同一 message 派 A1/A2/A3/A4, `run_in_background: true`
4. **Synthesize** — 等全部完成后, 主线程读 4 报告, 合并去重, 6 级优先级排序, 写 `code-quality-plan.md`
5. **Update checklist + commit** — 追加到 `docs/audit/<DATE>-findings.md` (如不存在则创建), 1 commit

**Hard rules**:
- ❌ 永不修改 `packages/*/src/**` 或 `packages/service/tests/**`
- ❌ 永不修改 `pyrightconfig.json` / `oxlintrc.json` / `tsconfig.json` 持久状态 (A4 临时测试后必须 `git checkout` 恢复)
- ❌ 永不在 subagent prompt 里硬编码数字 (noqa/oxlint/type:ignore 数量每次扫描都会变)
- ✅ 报告输出严格按 [docs/audit/README.md §命名约定](../../audit/README.md) — `docs/audit/YYYY-MM-DD/` 子目录

## Step 1: Prepare

主线程执行 (快, 不浪费 subagent 工具预算):

```bash
DATE=$(date +%Y-%m-%d)
cd c:/doc/Code/rag

# 1. 拿当前数字
NOQA_COUNT=$(grep -r "noqa" packages/service/src/ --include="*.py" 2>/dev/null | wc -l)
PYRIGHT_IGNORE_SRC=$(grep -r "type: ignore" packages/service/src/ --include="*.py" 2>/dev/null | wc -l)
PYRIGHT_IGNORE_TEST=$(grep -r "type: ignore" packages/service/tests/ --include="*.py" 2>/dev/null | wc -l)
OXLINT_COUNT=$(grep -rE "eslint-disable|oxlint-disable" packages/web/app/ packages/web/lib/ packages/web/components/ packages/web/hooks/ packages/web/i18n/ --include="*.ts" --include="*.tsx" 2>/dev/null | wc -l)

echo "DATE=$DATE NOQA=$NOQA_COUNT PYR_SRC=$PYRIGHT_IGNORE_SRC PYR_TEST=$PYRIGHT_IGNORE_TEST OXLINT=$OXLINT_COUNT"
```

把上述 5 个数字**注入到每个 subagent prompt** 里 (作为 `${NOQA_COUNT}` 等 placeholder).

## Step 2: Create output dir

```bash
mkdir -p docs/audit/$DATE
```

后续所有 agent 输出写到 `docs/audit/$DATE/` 根 (不是 `docs/audit/` 根 — README 约定).

## Step 3: Dispatch 4 parallel subagents

**同一 message 派发** (4 个 Agent tool call 并行, 都 `run_in_background: true`):

| Agent | subagent_type | 工具限制 | 产出文件 | 关键差异 vs 昨天 |
|---|---|---|---|---|
| A1 Test Scanner | `general-purpose` | 30 | `$DATE-test-failures.md` | — |
| A2 Pyright Scanner | `Explore` | 30 | `$DATE-pyright-ignores.md` | — |
| A3 Lint Scanner | `Explore` | 30 | `$DATE-lint-ignores.md` | **数字 placeholder 注入** |
| A4 Pyright Strict | `Explore` | 20 | `$DATE-pyright-strict-audit.md` | **运行时读 pyrightconfig.json** |

完整 prompt 模板见 [references/agent-prompts.md](references/agent-prompts.md). 每个 agent 必须:
- 知道 `$DATE` 和项目根 (`c:/doc/Code/rag/`)
- 接收 Step 1 注入的 5 个数字 (A3 必须, 其他可选)
- 产出文件写到 `docs/audit/$DATE/` (不要写到根)
- A4 每次改 `pyrightconfig.json` 后 `git checkout packages/service/pyrightconfig.json` 恢复

**Wait**: 等 4 个 background agent 全部 complete (会收到 task notification).

## Step 4: Synthesize roadmap

主线程执行 (不派 subagent):

1. Read 4 份报告
2. 跨报告去重 (同一条 lint ignore 同时出现在 A2 和 A3 → 合并)
3. 按 6 级优先级排序:

| 优先级 | 来源 | 行动 |
|---|---|---|
| P0 | A1 [bug] + [regression] | 立即修复 |
| P1 | A2 [fixable] + A3 [dead] + A3 [downgrade] | 逐个清理 |
| P2 | A3 [fixable-config] + A4 可行建议 | 规则配置调整 |
| P3 | A3 [keep] | 不动 |
| P4 | A2 [stub] + A3 [keep] | 不动 |
| P-scan | A1 [pg-violation] | 专题: 重写为模式 1 mock |

4. 写 `docs/audit/$DATE/$DATE-code-quality-plan.md` (章节模板见 [references/report-templates.md §5](references/report-templates.md))

## Step 5: Update checklist + commit

**5.1** 追加到 `docs/audit/$DATE-findings.md` (如不存在则用本日 checklist 模板创建). 章节固定格式:

```markdown
---

## $DATE 代码质量快照扫描 (不修, 仅报告)

| 维度 | 找到 | 说明 |
|---|---|---|
| pytest fail | N | 详见 [docs/audit/$DATE/$DATE-test-failures.md]($DATE/$DATE-test-failures.md) |
| vitest fail | N | 同上 |
| pyright type:ignore 可修 | N | 详见 [...pyright-ignores.md]($DATE/$DATE-pyright-ignores.md) |
| lint ignore 可修 | N | 详见 [...lint-ignores.md]($DATE/$DATE-lint-ignores.md) |
| pyright 严格模式 | L2 standard | 详见 [...pyright-strict-audit.md]($DATE/$DATE-pyright-strict-audit.md) |
| **PG 违规测试** | N | 详见 [test-failures §pg-violation]($DATE/$DATE-test-failures.md#pg-violation) |
| 路线图 | 6 级 | 详见 [...code-quality-plan.md]($DATE/$DATE-code-quality-plan.md) |
```

**5.2** 更新 `docs/audit/README.md` (在文档列表加一行)

**5.3** Commit:

```bash
cd c:/doc/Code/rag
git add docs/audit/$DATE/ docs/audit/$DATE-findings.md docs/audit/README.md
git status
git commit -m "docs(audit): $DATE 代码质量快照 - 4 维度报告 + 路线图"
```

Expected: 1 commit, 5+ 个新文件 (4 报告 + 1 路线图), 1 个 checklist 更新, 1 个 README 更新.

## Quick Reference

**A1 类别标签**: `[bug] [env] [regression] [flaky] [config] [pg-violation]`
**A2 类别标签**: `[stub] [fixable] [dead] [rule-up] [test]`
**A3 类别标签**: `[keep] [fixable-code] [fixable-config] [downgrade] [dead]`
**A4 层级**: L0 (basic) → L1 (删 reportUnknown* none) → L2 (standard) → L3 (+optional rules) → L4 (strict)

**优先级映射**:

```
P0   = A1 [bug] + [regression]   → 立即修
P1   = A2 [fixable] + A3 [dead]  → 逐个清
P2   = A3 [fixable-config] + A4 L1/L2 → 调配置
P3/P4 = [keep] / [stub]          → 不动
P-scan = A1 [pg-violation]       → 强制规范, 优先级最高
```

**注意**:
- A1 输出按类别分段, **必须**有 [pg-violation] 专项 (项目强制规范)
- A2 输出按库分组 (Pillow / SQLAlchemy / FastAPI 等)
- A3 必须有 oxlintrc 当前配置 + 建议的 overrides 段
- A4 必须 L0-L4 全部测试, 即使跳过也要写"why skipped"

## Anti-Patterns

❌ 派 agent 后忘记传 `run_in_background: true` → 4 个 agent 串行, 浪费 10-20 min
❌ A4 agent 改 `pyrightconfig.json` 后没恢复 → 下次扫描基线污染
❌ 把报告写到 `docs/audit/` 根 → 违反 README 约定
❌ Subagent prompt 里硬编码 "23 处 noqa" → 下次数字已变, agent 困惑
❌ 改任何 `packages/*/src/**` 文件 → 这是只读扫描, 不是 fix
❌ 跳过 Step 1 注入数字 → A3 不知道要分析多少条
