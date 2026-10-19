# 2026-07-09 oversize-files-audit v2 design — verifier + pseudo-code

> 合产 spec. 给已存在的 [oversize-files-audit skill](../../../.claude/skills/oversize-files-audit/SKILL.md) 加 2 个 v2 能力:
> 1. **Verifier 阶段** — 仿 `/full-stack-audit Phase 3`, 每文件 6 段逐条派 verifier agent 反驳, 减误报
> 2. **库依赖验证 + 骨架伪代码** — agent Read 真 package.json/components.json, 库替代段加"已装/未装"标记, 拆点提议加骨架伪代码
>
> **不破坏 v1**: 现有 6 段格式保留, 加 1 段 (7. 骨架伪代码) + 全局 verified/confidence 字段. 加 `--skip-verify` flag 可选跳过 verifier 阶段.

## 背景与动机

v1 ([spec 链接](../../specs/2026-07-09-oversize-files-audit-skill-design.md)) 已 commit `e0bcae78`, 跑过 RED baseline, 暴露 5 个漏洞已堵. v1 的核心限制:

- **误报率 ~30%**: "建议 shadcn <Table>" 但文件已经用 / 库替代估错 / "拆后减 42%" 但实际拆后只减 20%
- **库替代建议不可执行**: agent 不读 `package.json`, 推荐的库可能根本没装
- **缺拆后骨架**: 用户读报告要自己脑补新文件结构

跑过一次 baseline (42 文件 / 18669 行), 人工抽样 5 个文件, 实测 ~6 段里 ~30% 有小错, 100% 库替代没标"已装/未装". v2 解决这 2 类问题.

## 目标

### Feature 1: Verifier 阶段
- **定量**: 6 段建议经 verifier 反驳后, 误报率从 ~30% 降到 < 10%
- **定性**: 每条 6 段建议带 verified/confidence/refuted_reason 字段
- **可关闭**: `--skip-verify` flag 跳过 verifier 阶段 (节省 ~40k token)
- **可降级**: verifier 工具超限 → 默认 verified=true + confidence=low (不阻塞报告)

### Feature 2: 库依赖验证 + 骨架伪代码
- **库验证**: 库替代段从 "✅ shadcn <Table>" 升级成 "✅ shadcn <Table> 已装 (components.json:75)" 或 "⚠️ 未装, 需 npx shadcn@latest add table"
- **骨架伪代码**: 每文件新增 7 段 "骨架伪代码" — 文件名 + import + 函数签名 (不实现逻辑)
- **可执行性**: 用户能照骨架起手拆, 不用再脑补

## 非目标 (out of scope)

- ❌ 修任何业务代码 (沿用 v1 hard rule)
- ❌ 升级到完整实现伪代码 (留 v3, 当前只骨架)
- ❌ WebSearch 验证库 API (沿用 v1 "禁止 WebSearch")
- ❌ 自动 PR 创建 / git apply 拆后骨架 (留 v3)
- ❌ 改 v1 的 6 段基础结构 (向后兼容)

## 设计

### Feature 1: Verifier 阶段

#### 位置

在 v1 Step 5 (Synthesize) 之后, Step 6 (commit) 之前, 加 **Step 5.5: Verify**.

#### 流程

```
Step 1: Prepare (v1)
Step 2: Create output dir (v1)
Step 3: Dispatch 3 agents (v1, 输出变 7 段)
Step 4: Verify .md 存在 (v1)
Step 5: Synthesize 1 份主报告 (v1, 字段扩展 verified/confidence)
Step 5.5: Verify (新) -- 派 N 个 verifier agent, 反驳 6 段建议
Step 6: Commit (v1)
```

#### Verifier Agent Prompt (跟 `/full-stack-audit Phase 3.2` 同模板)

```
你是 verifier, 尝试反驳这条 finding (默认反驳):

finding 全文:
<paste 单文件 6 段 markdown>

文件: {file} (项目根: c:/doc/Code/rag/)

任务:
1. Read {file} 上下文 (前后 30 行)
2. 找出反例 / 错配 / 误判的证据:
   - 库替代段: 该库真的没装? (Read package.json / components.json)
   - 拆点提议: 行号对不对? 拆后预计减少 % 是否虚高?
   - 对象替 if: switch 是真存在? switch 不可被对象替 (case 复杂)?
   - 数组替循环: 循环里真有副作用? 不能改 .map()?
3. 如果找不出反例 → verified=true, 保留 finding
4. 如果找到反例 → verified=false, 给具体 refuted_reason (≥ 2 句)

工具调用 ≤ 5 次, tokens ≤ 5k. 最终回复必须是 JSON:
{"verified": bool, "confidence": "high|medium|low", "refuted_reason": "string|null"}
```

#### 降级规则

- **verifier 工具调用失败** → 默认 verified=true, confidence=low (跟 `/full-stack-audit §降级规则` 一致)
- **verifier 找不到反例** → verified=true
- **verifier 找到反例** → verified=false

#### Token 预算

- **保守估算**: 42 文件 × 6 段 ≈ 252 条 finding
- **全量跑**: 252 × 5k token = **1.26M token** (爆炸, 拒)
- **方案**: 加 `--max-verifier=N` flag (默认 60), 主线程派发前 assert 限制. 超过则**只验证最高优先级 60 条** (按文件行数降序, 行数越大越优先)
- **成本**: 60 × 5k = 300k token, 跟 default audit 同量级

#### 主报告字段扩展

每文件 6 段后追加元数据:

```markdown
### `<相对路径>` (N 行)

**1. 拆分点**: ...
**2-6**: ...
**verified**: true
**confidence**: high
**refuted_reason**: null

<!-- 如果 verified=false: -->
**verified**: false
**confidence**: high
**refuted_reason**: "L152-260 switch 的 case 是 [complex eval logic], 对象 lookup 无法表达"
```

#### 顶部汇总表加列

| 路径 | 行数 | 语种 | verified | confidence | 拆后预计 | 建议 |
|---|---|---|---|---|---|---|
| x.tsx | 412 | TSX | ✅ | high | 240 (-42%) | P1 |
| y.py | 500 | py | ❌ | high | 400 (-20%) | P1 |

#### 步骤 4 升级

v1 Step 4 只验证 .md 存在. v2 加行数检查: 缺 6 段或 refuted_reason 缺失 → 警告.

### Feature 2: 库依赖验证 + 骨架伪代码

#### Agent Prompt 升级

通用 frontmatter 加启动步骤:

```
启动步骤 (强制):
1. Read packages/web/package.json 确认 React/Next/zod/shadcn 等已装
2. Read packages/web/components.json 确认 shadcn 组件已注册
3. Read packages/service/pyproject.toml 确认 Python 库已装 (A1 用)
```

#### 库替代段升级格式 (原 6 段格式不变, "3. 库替代" 行加修饰)

```markdown
**3. 库替代**:
- ✅ shadcn `<Table>` 已装 (components.json:75) → 直接替换手写 table
- ⚠️ shadcn `<DataTable>` 未装, 需 `npx shadcn@latest add data-table`
- ✅ es-toolkit `pick` 已装 (package.json:dependencies) → 替手写
- ❌ 无其他
```

#### 第 7 段: 骨架伪代码 (新增)

每文件 6 段后加第 7 段:

```markdown
**7. 骨架伪代码** (拆后文件结构示意):

`use-debounce-search.ts` (新文件):
```typescript
import { useDebounce } from "react-use";

export function useDebouncedSearch(initialValue: string): {
  input: string;
  debouncedInput: string;
  setInput: (v: string) => void;
};
```

`table-content.tsx` (新文件):
```typescript
import { Table } from "@/components/ui/table";

export function TableContent<T>(props: {
  rows: T[];
  columns: Column<T>[];
}): JSX.Element;
```

**注意**: 只骨架, 不实现. 用户照此起手.
```

伪代码规则:
- **不含表达式主体** (只函数签名)
- **import 列表用真实路径** (基于 Read 验证后的 package.json/components.json)
- **不写 100 行以上的伪代码** (超过则拆段)

#### Token 影响

- v1 agent 输出 ~50 行/文件 → v2 ~80 行/文件 (60% 增长)
- 42 文件 × 80 行 ≈ 3360 行 markdown, 仍然可控

### 完整流程图

```
┌─────────────────────┐
│ 1. Prepare          │ (v1 不变)
└──────────┬──────────┘
           │
┌──────────▼──────────┐
│ 2. Create output    │ (v1 不变)
└──────────┬──────────┘
           │
┌──────────▼──────────┐
│ 3. Dispatch 3 agents│ (输出变 7 段, 启动步骤加 Read package.json)
│   run_in_background │
└──────────┬──────────┘
           │
┌──────────▼──────────┐
│ 4. Verify .md       │ (升级: 加 6 段 + refuted_reason 格式检查)
└──────────┬──────────┘
           │
┌──────────▼──────────┐
│ 5. Synthesize       │ (顶部汇总表加 verified/confidence 列)
└──────────┬──────────┘
           │
┌──────────▼──────────┐
│ 5.5 Verify (新)     │
│  - 派 N verifier    │
│  - 写回 verified    │
│  - 顶部加 ⚠️ 段    │
└──────────┬──────────┘
           │
┌──────────▼──────────┐
│ 6. Commit (v1)      │ (commit message 加 "v2 verified")
└─────────────────────┘
```

## 实施检查清单

- [ ] SKILL.md: 加 Step 5.5 (Verify), 改 Step 3/4/5, 加 `--skip-verify` / `--max-verifier` flag
- [ ] agent-prompts.md: 加启动 Read 步骤, 库替代段升级格式, 加第 7 段模板
- [ ] SKILL.md: Anti-Patterns 加 5 条 (v2 baseline 实证)
- [ ] SKILL.md: Red Flags 加 4 条 (verified 跳过 / 库未验证 / 伪代码含逻辑 / refuted_reason 漏)
- [ ] 跑 1 轮 full audit, 抽样 5 文件对比 v1 误报率
- [ ] commit message: `feat(skill): oversize-files-audit v2 — verifier 阶段 + 库验证 + 骨架伪代码`

## 风险与未决项

| 风险 | 缓解 |
|---|---|
| verifier 全量 252 条 finding 跑 → token 爆炸 1.26M | `--max-verifier=60` 默认限制; 派发前 assert 警告 |
| 库验证读 package.json 增 10-20% agent token | 可接受, 跟 60% 输出增长同量级 |
| 骨架伪代码被 LLM 编造不存在的 import | 强制 agent Read 后才能写 import (前置步骤) |
| refuted_reason 写得太短 (1 句) 无信息量 | 模板强制 ≥ 2 句, verifier 阶段格式检查 |
| `--skip-verify` 默认跳过 = v2 退化 v1 | 默认开 verify, --skip-verify 是 opt-out |
| 误报率 < 10% 目标难达成 | 抽样对比, 不达标则强制改 agent prompt |
| verifier 跟 /full-stack-audit 同结构, 用户维护 2 处 | 文档加交叉链接, 不抽公共 (YAGNI) |

## 关联文档

- v1 spec: [docs/superpowers/specs/2026-07-09-oversize-files-audit-skill-design.md](2026-07-09-oversize-files-audit-skill-design.md)
- v1 SKILL.md: [.claude/skills/oversize-files-audit/SKILL.md](../../../.claude/skills/oversize-files-audit/SKILL.md)
- v1 commit: `e0bcae78`
- baseline 数据: [docs/audit/2026-07-09-test/baseline-test.md](../../../audit/2026-07-09-test/baseline-test.md)
- 模板: [/full-stack-audit Phase 3.2 verifier 模板](../../../.claude/skills/full-stack-audit/SKILL.md)
