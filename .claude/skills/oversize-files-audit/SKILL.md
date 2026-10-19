---
name: oversize-files-audit
description: "Use when scanning a Python + Next.js codebase for source files larger than 300 lines and producing a refactor-suggestion audit. Triggers: quarterly code-base inventory, before a major refactor spec, or as a follow-up after /code-quality-scan or /full-stack-audit. Do NOT use when you want to fix code (this skill NEVER writes to packages/*/src or tests/), or for a single-file lint question (use ruff/oxlint directly). Always 3 parallel subagents (Python / TS page-component / TS hook-util) + 1 synthesize + 1 verifier stage + 1 commit, output to docs/audit/<YYYY-MM-DD>/oversize-files-audit/."
---

# /oversize-files-audit

3-agent fan-out 只读扫描项目里所有 >300 行的 .py / .ts / .tsx 文件，出 1 份带 **7 段固定格式重构建议** + **库依赖验证** + **骨架伪代码** + **verifier 反驳**的 audit 报告。**不修任何业务代码，不写 spec 草稿，不调 LLM 增强 (v1)，不加 WebSearch (v2)**。

## Usage

```
/oversize-files-audit                              # 默认今天，默认阈值 300 行，跑 verifier
/oversize-files-audit --min-lines 200              # 调阈值
/oversize-files-audit --include fixtures           # 包含默认排除目录 (慎用)
/oversize-files-audit --only python                # 只跑 Python agent (TS 跳过)
/oversize-files-audit --only ts-page               # 只跑 TS page/component agent
/oversize-files-audit --only ts-hook               # 只跑 TS hook/util agent
/oversize-files-audit --skip-verify                # 跳过 verifier 阶段 (省 ~300k token)
/oversize-files-audit --max-verifier 60            # 限制 verifier 数量上限 (默认 60)
/oversize-files-audit --no-pseudo                  # 不出第 7 段骨架伪代码 (回退 v1 行为)
```

## When to Use

| 场景 | 说明 |
|---|---|
| **季度代码盘点** | 文件膨胀后批量列出，准备排 refactor 优先级 |
| **大重构之前** | 知道"哪里长"再下手，避免无目标动刀 |
| **跟其它 audit 互补** | `/code-quality-scan` 出 4 维度统计，`/full-stack-audit` 出 6 维度业务 finding + verifier，这个出**文件级 + 骨架可执行**清单 |
| **新成员加入** | 让报告作为"项目哪些文件值得拆 + 怎么拆"的导览 |

不适用:
- ❌ 想修代码 → 用对应 refactor skill
- ❌ 单文件 lint → 用 ruff / oxlint
- ❌ 想找 bug → 用 systematic-debugging
- ❌ 找跨文件重复代码 → 用 /full-stack-audit D6 Architecture

## What You Must Do When Invoked

**7 步强制流程，不可跳过**:

1. **Prepare** -- 拿日期，跑跨平台 Python 扫描脚本，拿文件清单
2. **Create output dir** -- mkdir -p docs/audit/<DATE>/oversize-files-audit/
3. **Dispatch 3 parallel subagents** -- 同一 message 派 A1/A2/A3，run_in_background: true, **输出变 7 段 (含骨架伪代码 + 库依赖验证)**
4. **Wait + verify .md** -- 等 3 个 background agent complete，验证 .md 存在且 ≥ 10 行 + 7 段格式
5. **Synthesize** -- 主线程读 3 份，按行数倒序合并去重，写 `oversize-files-audit.md` (顶部汇总表加 verified/confidence 列)
6. **Verify (verifier 阶段)** -- 派 N 个 verifier agent 反驳 6 段建议，写回 verified/confidence/refuted_reason (**默认跑，--skip-verify 跳过**)
7. **Update checklist + commit** -- 追加到 docs/audit/<DATE>-findings.md，1 commit

**Hard rules** (违反 = 重新跑，不可修复):

- ❌ 永不修改 packages/*/src/** 或 packages/*/tests/** 或 lockfile -- 包括"建议删代码"
- ❌ 永不修改项目根 CLAUDE.md / .claude/CLAUDE.md 阈值或规范 (调阈值走 --min-lines)
- ❌ 永不把主报告写到 docs/audit/<DATE>/ 根 → 必须嵌套到 oversize-files-audit/ 子目录
- ❌ 永不混合语种派给同一 agent (Python + TS 必须分 3 agent，派发后确认 < 3 则 exit 1)
- ❌ 永不跳过 6 段格式输出 -- v2 加第 7 段是**可选** (--no-pseudo 跳过)，6 段必填
- ❌ 永不静默跳过失败的 subagent → 留 TODO 占位 + 中文注释 + 退出码非 0
- ❌ 永不在 subagent prompt 硬编码文件行数 → 用 ${FILE_COUNT} placeholder
- ❌ 永不写 spec 草稿 (单一职责，留给 /full-stack-audit)
- ❌ 永不建议删代码 (只建议"移 / 拆 / 重构") -- 删除是 refactor 阶段的 action
- ❌ 永不在 bash 用 echo 写含中文的报告 (Windows 乱码，走 Write 工具)
- ❌ 主报告不按行数倒序排序 = 重新跑，排序必须在合成时做
- ❌ 主报告漏写顶部汇总表 = 重新跑，汇总表是必须字段
- ❌ 自检没跑完 = 没完成，自检是 Step 5 的原子部分
- ❌ **v2 新**: agent 不先 Read package.json / components.json / pyproject.toml 就写库替代段 = 重新跑
- ❌ **v2 新**: 伪代码含完整实现逻辑 (只允许骨架: 文件名 + import + 函数签名) = 重新跑
- ❌ **v2 新**: verifier 默认关闭 = 重新跑，--skip-verify 是显式 opt-out

## Step 1: Prepare

主线程执行 (快，不浪费 subagent 工具预算)。

调用 references/scan-script.py 扫描:

```bash
DATE=$(date +%Y-%m-%d)
cd c:/doc/Code/rag
python .claude/skills/oversize-files-audit/references/scan-script.py . 300 \
  > docs/audit/$DATE/oversize-files-audit/.scan-cache.json

FILE_COUNT=$(python -c "import json; d=json.load(open('docs/audit/$DATE/oversize-files-audit/.scan-cache.json')); print(len(d))")
PY_COUNT=$(python -c "import json; d=json.load(open('docs/audit/$DATE/oversize-files-audit/.scan-cache.json')); print(sum(1 for f in d if f['path'].endswith('.py')))")
TS_COUNT=$(python -c "import json; d=json.load(open('docs/audit/$DATE/oversize-files-audit/.scan-cache.json')); print(sum(1 for f in d if f['path'].endswith(('.ts', '.tsx'))))")
TOTAL_LINES=$(python -c "import json; d=json.load(open('docs/audit/$DATE/oversize-files-audit/.scan-cache.json')); print(sum(f['lines'] for f in d))")
```

.scan-cache.json 是临时文件**不进 git**。

```bash
if [ "$FILE_COUNT" -gt 240 ]; then
  echo "WARN: $FILE_COUNT files, consider --min-lines to raise threshold"
fi
```

## Step 2: Create output dir

```bash
mkdir -p docs/audit/$DATE/oversize-files-audit
```

后续所有 agent 输出 + 主报告 + checklist 都写到这个**子目录**。**写错目录 = 重新跑**。

## Step 3: Dispatch 3 parallel subagents

**同一 message 派发** (3 个 Agent tool call 并行，都 run_in_background: true，subagent_type: "general-purpose")。

| Agent | 语种 | 路径范围 | 库清单 | 产出 |
|---|---|---|---|---|
| A1 Python | .py | packages/service/src/，tests/ | pydantic / dataclass / functools / itertools / pathlib / pytest fixtures | a1-python.md |
| A2 TS Page/Component | .ts/.tsx | packages/web/app/，components/ | shadcn / zod / tanstack-query / lucide-react | a2-ts-page.md |
| A3 TS Hook/Util | .ts/.tsx | packages/web/hooks/，lib/，i18n/ | react-use / ahooks / es-toolkit / zod / dayjs / nuqs | a3-ts-hook.md |

**v2 启动步骤强制** (所有 agent prompt 都加这一段):

```
启动步骤 (强制):
1. Read packages/web/package.json (确认 React/Next/zod/shadcn 等已装)
2. Read packages/web/components.json (确认 shadcn 组件已注册)  [A1 跳过]
3. Read packages/service/pyproject.toml (确认 Python 库已装)    [A2/A3 跳过]
4. Read 真文件后才写库替代段 + 第 7 段骨架伪代码
```

完整 prompt 模板见 [references/agent-prompts.md](references/agent-prompts.md)。

Wait: 等 3 个 background agent 全部 complete。单 agent 文件上限 80。

## Step 4: Verify .md (主线程，升级)

```bash
for f in a1-python a2-ts-page a3-ts-hook; do
  target="docs/audit/$DATE/oversize-files-audit/$f.md"
  if [ -f "$target" ]; then
    lc=$(wc -l < "$target" 2>/dev/null || echo 0)
    [ "$lc" -lt 10 ] && echo "WARN: $f.md too short ($lc lines)"

    # v2 升级: 6 段必填检查 (仅当 --no-pseudo 未传)
    if ! grep -qE '^\*\*1\. 拆分点' "$target"; then
      echo "WARN: $f.md 缺第 1 段"
    fi
    if ! grep -qE '^\*\*6\. 预计减少' "$target"; then
      echo "WARN: $f.md 缺第 6 段"
    fi
  else
    echo "BLOCKED: $f.md missing"
    printf "## %s agent 失败\n\nTODO: 重跑 /oversize-files-audit\n" "$f" > "$target"
  fi
done
```

**绝不静默跳过。** 失败留 TODO 占位 + 主报告顶部加 Agent 失败段。

## Step 5: Synthesize

1. Read 3 份 a*.md
2. **按行数降序排序** -- 跳过排序 = 重新跑
3. 跳过 TODO 占位文件
4. 写 `oversize-files-audit.md`

**v2 每文件 7 段格式** (1-6 必填, 7 默认开 `--no-pseudo` 关):

```markdown
### `<相对路径>` (N 行)

**1. 拆分点**: L1-72 `<做什么>` -> `<拆后名>.ts` (pure func / hook)
**2. 纯函数/hook 化**: 可拆 (列具体) / 不可拆 (原因)
**3. 库替代**: ✅ shadcn <Table> 已装 (components.json:75) / ⚠️ 未装 (需 npx shadcn@latest add) / 无
**4. 对象替 if**: L152-260 switch -> actionMap[variant] / 无
**5. 数组替循环**: for -> .map() / 无
**6. 预计减少**: N -> M (-X%)
**7. 骨架伪代码** (可选): 文件名 + import + 函数签名 (不实现逻辑)
```

**顶部汇总表** (v2 加 verified/confidence 列):

| 路径 | 行数 | 语种 | verified | confidence | 拆后 | 建议 |
|---|---|---|---|---|---|---|
| packages/web/.../x.tsx | 412 | TSX | ✅ | high | 240 | P1 |
| packages/service/.../y.py | 500 | py | ❌ | high | 400 | P1 |

**自检**: (a) 每文件 6 段 (b) 有汇总表 (c) 降序 (d) 无"删代码"措辞 (e) 库替代段引 package.json 行号 (f) 伪代码不含表达式主体。

## Step 6: Verify (verifier 阶段，默认跑)

**跳过方式**: `--skip-verify` (省 ~300k token，但报告无 verified 字段)。

**数量限制**: `--max-verifier N` (默认 60)，防止 token 爆炸。派发前 assert:

```bash
# 估算 verifier 数量 = 文件数 × 6 段 (粗估)
EST_VERIFIERS=$((FILE_COUNT * 6))
if [ "$EST_VERIFIERS" -gt "$MAX_VERIFIER" ]; then
  echo "WARN: 估算 $EST_VERIFIERS verifier 超过上限 $MAX_VERIFIER, 只验证行数最大的 $MAX_VERIFIER 段"
  # 主线程从 a*.md 里按文件行数降序提取 finding, 截到 N 条
fi
```

**派发逻辑**:
- 主线程从 3 份 a*.md 提取每文件 6 段 finding (按行数降序排, 截到 max-verifier)
- 每条 finding 派 1 个 verifier agent (Read 文件 + 找反例 + JSON verdict)
- Verifier prompt 模板见 [references/verifier-prompt.md](references/verifier-prompt.md)
- Verifier 跟 /full-stack-audit Phase 3.2 同结构: 默认反驳, 找不到反例 verified=true

**写回**: 主线程用 Edit 写回每文件 verified/confidence/refuted_reason 字段 + 顶部汇总表更新 verified 列。

**降级规则** (跟 /full-stack-audit 一致):
- verifier 工具调用失败 → 默认 verified=true, confidence=low (不阻塞)
- verifier 找不到反例 → verified=true
- verifier 找到反例 → verified=false, refuted_reason ≥ 2 句

**refuted 标记格式** (v2 默认保留原段 + 加标记，不删除):

```markdown
### `<相对路径>` (412 行)

**1. 拆分点**: ... (原文)
...
**6. 预计减少**: ... (原文)

**verified**: false
**confidence**: high
**refuted_reason**: "L152-260 switch 的 case 是 [complex eval logic]，对象 lookup 无法表达；建议改用策略模式或多态而非 lookup 表"
```

## Step 7: Update checklist + commit

追加到 docs/audit/<DATE>-findings.md，更新 README，1 commit:

```bash
git add docs/audit/$DATE/oversize-files-audit/ docs/audit/$DATE-findings.md docs/audit/README.md
git commit -m "chore(audit): $DATE oversize-files v2 扫描 - N 个文件 + 拆分建议 + verifier"
```

(只有 .scan-cache.json 不在 staged 范围 -- 它是临时文件)

## Quick Reference

**3 个 agent 路径分配**: A1 Python -> `packages/service/src/`，A2 TS Page -> `packages/web/{app,components}/`，A3 TS Hook/Util -> `packages/web/{hooks,lib,i18n}/`

**默认排除**: `__generated__` / `migrations/versions/*` / `node_modules` / `.next` / `dist` / `build` / `.venv` / `coverage` / `fixtures/`

**6 段模板**: 见 Step 5

**verifier 上限**: 60 (可调 `--max-verifier N`)

**Anti-Patterns**:

| Rationalization | Reality |
|---|---|
| "顺手把大文件拆了吧" | 只读 audit，拆代码留到 refactor spec |
| "6 段格式太繁，拆点+估计就够" | 6 段是核心输出，跳段 = 失职能 |
| "300 太松，改 200" | 调阈值走 --min-lines flag |
| "Python+TS 给同一 agent" | baseline 证实混语种导致跳 6 段+ 库替代混淆 |
| "报告写根目录就行" | baseline 实测写到根目录；hard rule 禁止 |
| "先出 sprint plan 再补 6 段" | 6 段是原子单位，sprint 是合成产物 |
| "我建议删掉那些 dead code" | audit 只建议移/拆/重构，删不是 audit 范围 |
| "TS Hook agent 失败，跳过" | 必须留 TODO 占位，不静默 |
| "subagent prompt 写死 N 个文件" | 用 placeholder，数字漂移不会困惑 |
| **v2 "库替代估个大概就行"** | agent 必须 Read package.json/components.json，标"已装 (file:line)" 或 "未装 (需 npx add)" |
| **v2 "伪代码顺便写完整逻辑"** | 只骨架（文件名 + import + 签名），含实现 = 重新跑 |
| **v2 "verifier 太慢，默认跳过"** | 默认必跑，--skip-verify 是显式 opt-out |
| **v2 "verifier 找不到反例就 verified=false"** | 跟 /full-stack-audit 一致：找不到反例 = verified=true |
| **v2 "refuted 后原段删掉"** | 默认保留原段 + 加 refuted 标记；删除是 v3 决策 |

## Red Flags -- STOP and Restart

- Edit packages/*/src/** 或 tests/** → STOP，这是 audit
- 报告写到根目录 → STOP，必须嵌套
- 忘传 run_in_background: true → STOP，串行跑
- 混语种 1 agent → STOP，拆 3 个
- agent 失败不写 TODO → STOP，静默 = 漏报
- 硬编码文件数到 prompt → STOP，用 placeholder
- 合成无汇总表 / 无排序 / 缺 6 段 → STOP，自检不过
- 建议"删代码" → STOP，只建议拆分
- **v2**: agent 未 Read package.json 就写库替代 → STOP，先验证再写
- **v2**: 伪代码含 5+ 行表达式主体 → STOP，只写骨架
- **v2**: verifier 默认关闭 → STOP，除非显式 --skip-verify
- **v2**: refuted=true 直接删原段 → STOP，保留+标记
- **v2**: refuted_reason < 2 句 → STOP，强制 ≥ 2 句

## Reference Files

- [references/agent-prompts.md](references/agent-prompts.md) -- 3 份 subagent prompt (含库验证 + 第 7 段骨架伪代码模板)
- [references/scan-script.py](references/scan-script.py) -- 跨平台扫描脚本
- [references/verifier-prompt.md](references/verifier-prompt.md) -- verifier agent prompt 模板 (跟 /full-stack-audit Phase 3.2 同结构)
- 关系: /code-quality-scan (4 维度) + /full-stack-audit (6 维度 + verifier) + 本 skill (文件级 + 7 段 + verifier) = 三件套