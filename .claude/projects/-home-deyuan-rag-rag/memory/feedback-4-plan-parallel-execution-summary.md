---
name: code-quality-4-plan-parallel-execution
description: 2026-07-08 4 plan 并行开发合并复盘 (4 worktree + 4 subagent + 4 merge)
metadata: 
  node_type: memory
  type: project
  originSessionId: 0eaa132e-ba77-44f2-a0b6-807b6fd66f8c
---

# 2026-07-08 code-quality 4 plan 并行开发合并复盘

## 概况

code-quality-scan 4 维度审计后, 拆 4 个 sub-plan 在 4 个 git worktree 并行开发, 主线程 merge.

| Plan | 范围 | 耗时 | commit | 净改 |
|---|---|---|---|---|
| A (P0) | useTranslations + ingest + 4 单点 | 28 min | 5 | 测试 fail 70→18 (-52, -74%) |
| B (P1) | pyright [dead] + PYR-034 + FC-01/02 | 49 min (撞 429 终止) | 5 | pyright 116→14 (-102), oxlint 218→206 (-12) + 2 fixable-code |
| C (P2) | oxlintrc overrides + 阈值 + sed stale | 21 min | 3 | oxlint 206→98 (-108) |
| D (P3) | pyright standard + 4 optional + ORM cast | 29 min | 4 | typeCheckingMode basic→standard, 4 规则开启, 0 new error |
| **合计** | 全 4 plan | ~30 min 平均 | **17 commit + 4 merge** | 测试 fail -52, ignore -222, pyright 升级 |

## 关键事件

### 1. Plan A 完成 1 commit 后发现 vitest fail 反而多了 25 个 (44→69)

**根因**: `renderWithIntl` wrapper 在 14 个 `vi.mock("next-intl", ...)` 把 `NextIntlClientProvider` 抹成 undefined 的测试里炸. Agent 补了 `NextIntlClientProvider: ({children}) => children` 桩.

**教训**: 测 wrapper 影响面, 必须先小批量试 (5-10 个) 再铺开. Plan 估算 41 个, 实际 150 个 (含隐式用 render 导入的).

### 2. Plan B 撞 429 quota 提前终止

**根因**: Anthropic API monthly quota 用完, agent 写到 Task 4-8 中途被强制 reject.

**应对**: 主线程 inline 补完:
- 工作树 6 个 staged 文件 (5 个是 plan B 优化 注释化 ignore, 1 个 `route.test.ts` require-yield→yield 方案 tsc 错 revert)
- 删 chat test 3 个 (X 单字符 id-length 在 Plan C overrides 后仍触发 warning, 改回原样)
- 写 Task 9 checklist 汇总

**教训**: Agent 报的"未完成 task"分清"可救"vs"不可救". 撞 quota 是**外部约束**不是 plan 错, 不要再派 agent (有记忆 [[feedback-stop-repeating-verification-commands]]).

### 3. Plan D 偏离 plan 3 处

- `permissions/router.py:312/314/315` + `service.py:51/52` 4 处 ORM Column `cast(str, value)` 失效 (cast 给 Column[str] 赋值), 保留 `# type: ignore[assignment]` (审计 L2 不报这 4 处, 验证 type:ignore 跨模式兼容)
- `kreuzberg.py` 错的是 `convert_batch` 参数 list 类型不匹配, 不是 `convert` 签名; `pymupdf_extractor.py` 错的是 `extract._pymupdf_doc: Document|None` vs ABC `object|None`
- pyright 1.1.410 不认 `reportOptionalContains`/`reportOptionalChain` (计划 1.1.411 才有), 实际启用 4/6 规则

**教训**: Plan 估算跟实际常有偏差, agent 报告时 disclose 偏离, 主线程需 verify 偏离是否合理.

### 4. Plan B/C/D 4 agent 派发撞 API 限流 (~50% 失败率)

3-4 个 `run_in_background: true` agent 同 message 派发, 部分会撞 "MiniMax-M3[512K] is temporarily unavailable" (auto mode classifier 暂时禁用). **立即 retry, 4 次内必成功**. 见 [[feedback-parallel-subagent-api-rate-limit]].

### 5. Merge 冲突: 4 plan 都在 `docs/audit/2026-07-08-findings.md` 加修复进度段

- Plan A 加 "P0 修复进度"
- Plan C 加 "历史快照 2026-07-08 (P2)"
- Plan D 加 "修复进度 (P3)"
- Plan B 加 "4 plan 全部完成" (汇总)

**策略**: A→C→D→B 顺序 merge, B 最后用它的"4 plan 汇总"作为最终版 (覆盖 A/C/D 各自的段). `--no-ff` 创 merge commit (master 跟 plan commit 倒挂, 不能 ff).

**其它 1 个冲突**: Plan A 改 `schema-field-renderer.test.tsx` import 加 sort-imports 注释, Plan C sed 删同条 ignore. **取 Plan C** (downgrade 删 stale 是 plan 目标, Plan A 加注释是 plan 副作用), 该文件不调 useTranslations, 删 ignore 不破坏测试.

### 6. 6 个 staged 优化文件 (Plan B 撞 quota 时未 commit)

- `route.test.ts` (require-yield→yield): **tsc 错**, async generator yield undefined 不能给 ChatEvent, **revert**
- `composer-attachments.test.tsx` + `memory-management-dialog.test.tsx` + `share-dialog.test.tsx` (X 单字符 id-length ignore→注释): Plan C overrides 后仍触发 warning, **revert** (留原 ignore)
- `memory-integration.ts` (max-statements ignore→注释): 真优化, **commit**
- `build-nav-tree.ts` (no-console ignore→注释): 真优化, **commit**

最终 Plan B 5 commit: Task 1 + Task 2 + Task 3 (FC-01) + Task 4 注释化 2 处 + Task 9 checklist.

## 5 步流程模板 (下次 code-quality 4 plan 用)

1. **Plan 拆分** (主线程): A 4 维度 → 4 独立 plan, 写 `docs/superpowers/plans/`, 互不依赖 (不同文件 / 不同 ignore 类)
2. **Worktree 创建** (主线程): `git worktree add .worktrees/plan-X -b plan-X-<scope> <base-ref>`, **必须显式指定 base-ref** (不然 worktree 之间 HEAD 不一致)
3. **派发** (主线程, 单 message 4 Agent): 都 `run_in_background: true`, 同 message 派 3-4 个, classifier 限流时立刻 retry
4. **接收完成通知** (主线程): 1-2 个撞 429 终止, inline 补完; 全部 done 后开始 merge
5. **Merge + cleanup** (主线程): `--no-ff` 4 次, 处理 findings.md 冲突取最终汇总版, 删 worktree + 删分支

**Why**: 17 commit 4 plan 30 min 平均, 比串行 4 周快 80 倍. 4 plan 互不依赖是 parallel 的前提 (改 ignore + 改 config + 改路径 + 改测试, 4 类无交叉).

**How to apply**: 任何 4 维度以上的 code quality scan 都走这个 5 步. 撞 429 终止时, 主线程 inline 补**剩下的**任务 (先 grep staged, 真优化就 commit, 倒退就 revert).
