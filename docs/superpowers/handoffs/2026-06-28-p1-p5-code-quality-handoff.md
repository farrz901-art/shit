# 代码质量审计 handoff (2026-06-28 P1-P5)

> 目标: 实施 [5 维度审计](docs/audit/2026-06-28-code-quality-5d/) 的 P1-P5 全部 plan. 在 master 直接 commit.
> 当前进度: **P4 (12/12) 完成**. P3 / P1 / P2 / P5 待跑.

## 5 个 plan 索引

| Plan | 文件 | Tasks | Status |
|------|------|-------|--------|
| P3 | [docs/superpowers/plans/2026-06-28-p3-patterns.md](docs/superpowers/plans/2026-06-28-p3-patterns.md) | 10 | 待跑 |
| P1 | [docs/superpowers/plans/2026-06-28-p1-div-span-extraction.md](docs/superpowers/plans/2026-06-28-p1-div-span-extraction.md) | 28 | 待跑 |
| P2 | [docs/superpowers/plans/2026-06-28-p2-cva-tokenize.md](docs/superpowers/plans/2026-06-28-p2-cva-tokenize.md) | 8 | 待跑 |
| P5 | [docs/superpowers/plans/2026-06-28-p5-comments-completion.md](docs/superpowers/plans/2026-06-28-p5-comments-completion.md) | 29 | 待跑 |
| **P4** | [docs/superpowers/plans/2026-06-28-p4-functional-refactor.md](docs/superpowers/plans/2026-06-28-p4-functional-refactor.md) | 12 | ✅ **完成** |

---

## ✅ P4 完成总结 (11 commits)

**Goal**: 5 个 🔴 高 ROI functional 重构 + es-toolkit 增量 (1→3 sites)

### 11 commits on master (d588406d..dac15314)

| Commit | 范围 | Net Δ | 备注 |
|--------|------|-------|------|
| `7663ce38` | feat(api): bffProxyResponse 工厂 + 单测 (4 tests) | +17 | Task 1 |
| `0f73a962` | refactor(bff): approvals + chat-files (6 files) | -21 | Task 2 |
| `d9bec2d4` | refactor(bff): evaluate + health (4 files; 1 skip) | -19 | Task 3 |
| `210f007d` | refactor(bff): ingest (6 files; auth/anon/proxy skipped) | -24 | Task 4 |
| `c90b22b0` | feat(api): promote getErrorMessage public helper (5 tests) | +25 | Task 5 |
| `2129fe8e` | refactor(lib): use getErrorMessage in 3 lib/api files | -9 | Task 6 (5→3 实际) |
| `17878252` | refactor(actions): extract actionError helper (5+2 files) | -13 | Task 7 (~10/17 替换) |
| `f8b228c3` | refactor(components): getErrorMessage in 4 component helpers | -11 | Task 8 (3/4 替换) |
| `36e6dcf8` | refactor(chat): thinking-trace Record lookup | -10 | Task 9 (2 status, spec 写 4) |
| `9aadc339` | refactor(theme): extract isValidTheme predicate | -8 | Task 10 (3 sites, spec 写 4) |
| `dac15314` | refactor(common): use es-toolkit range | -4 | Task 11 (es-toolkit 1→3) |
| **总计** | **38 files changed, +257 / -240, 净 +17 行** | | **ROI: 重复样板消除 + 类型安全 + 主题响应** |

### 净行数: 38 files, +257 / -240

P4 spec 估算 ~245 行净节省; 实际净 +17 (因新增了 helper, 测试, JSDoc). 真实价值在:
- 消除 17 处 `new NextResponse(...)` 模板 (bffProxyResponse)
- 消除 27 处 `error instanceof Error ? .message : String(error)` (getErrorMessage + actionError + 局部替换)
- 1 个 type predicate (theme) + 1 个 Record lookup (thinking-trace) + 2 个新 es-toolkit imports

### 验证结果

- typecheck: **0 errors**
- lint: **0 errors** (1 pre-existing warning in unrelated `app-dialog.test.tsx`)
- format: **clean** (oxfmt 0 changes)
- vitest: **1028 passed / 5 failed** (与 stash baseline 完全一致 — **0 新 fail**)
- 5 pre-existing fails 全部是 next-intl ERR_MODULE_NOT_FOUND + RSC mock 问题, 跟 P4 无关

### P4 跳过 / 部分替换说明 (subagent 正确识别)

1. **`evaluate/template/route.ts`** — 需加 `content-disposition: attachment` CSV header, factory API 不支持. 1 处跳过.
2. **`auth/anon/proxy.ts`** — 用 `upstream.body` stream + set-cookie 透传, factory 用 `.text()` 不支持. 1 处跳过.
3. **`lib/api/chat.ts:36` + `lib/dify-datasets.ts:57`** — 实际是从 `Response.text()` 构造 error, 不是从 `unknown`, 不需要 getErrorMessage. 2 处 N/A.
4. **`_actions/account.ts` 5 处 + `account-settings.ts` 5 处** — catch 块含自定义中文 status-code 映射 + 额外状态字段 (`tempPassword: null` / `verificationUrl: null` 等), 不适合 `actionError` 的 `{ ok, error }` 形状. 改用 `getErrorMessage` 部分替换.
5. **`app-field.tsx:78`** — tanstack-form 需要 `string \| undefined` signature (falsy → undefined), public helper 返回 `string`. 保留 thin wrapper.
6. **`admin-invites-table.tsx:31`** — 删了硬编码 `"撤销失败"` fallback (改走 `getErrorMessage` 显示真实 Error.message). UX 更好, 但行为变化.
7. **`dict-item-create-dialog.tsx:35`** — helper 含 `translate` 参数 (i18n fallback), 保留 wrapper 仅替换 Error 分支.
8. **`thinking-trace.tsx:12-29`** — spec 写 4 status (pending/running/completed/failed), 实际只有 2 status (started/finished). 用 `Record<Step["status"], string>` 推导出所有 status.
9. **`theme-provider.tsx:115`** — 是 union membership check (LIGHT \| DARK \| SYSTEM), 不需 `enableSystem` 语义. 3/4 sites 替换.
10. **es-toolkit import 1→3** (非 1→5). spec 算错了.

### es-toolkit `Array.from` 决策记录 (用户质疑)

P4 spec 列 4 处 (production code 2 文件), 实际 grep 发现 `packages/web/` 还有 6 处 `Array.from({length}, mapper)` 都在 `.test.ts(x)` 测试文件:

```
packages/web/app/[locale]/knowledge/datasets/_components/datasets-table.test.tsx:33,44
packages/web/components/common/table/data-table.test.tsx:69
packages/web/components/common/table/data-table-pagination.test.tsx:43
packages/web/lib/parse/parse-eval-csv.test.ts:73,80
```

**决策**: 不替代. `Array.from({length}, mapper)` 第二参数是构造 mapper (生成对象/字符串), 比 `range(N).map(idx => ({...}))` 更紧凑. `range` 适合纯索引场景 (Skeleton 渲染, Task 11 范围).

---

## 📋 接下来要跑的 plan

### P3 (10 tasks)

[P3 patterns](docs/superpowers/plans/2026-06-28-p3-patterns.md) — StandaloneQueryProvider + applyEvent 对象 dispatch + parseErrorDetail 导出

**Phase 1 (Tasks 1-4)**: StandaloneQueryProvider + 3 处替换
- Task 1: 新建 provider + test
- Task 2: 替换 dataset-switcher.tsx
- Task 3: 替换 domain-switcher.tsx
- Task 4: 替换 app-health-dot.tsx

**Phase 2 (Tasks 5-6)**: chat-utils.applyEvent 对象 dispatch
- Task 5: 加 MESSAGE_UPDATERS 查表
- Task 6: 测试 4 event types

**Phase 3 (Tasks 7-9)**: parseErrorDetail 导出 + 2 处复用
- Task 7: 导出 lib/api/config.ts:parseErrorDetail
- Task 8: 替换 lib/api/ingest.ts
- Task 9: 替换 lib/api/chat.ts

**Task 10**: 验证

### P1 (28 tasks)

[P1 div/span extraction](docs/superpowers/plans/2026-06-28-p1-div-span-extraction.md) — 6 phases
- ErrorBanner 迁移 (5 sites) + PageHero (4 sites) + BackLink (2 sites) + DialogFooter (9 sites) + AppDataEmpty variant (5 sites) + Badge 替换 (1 site)

### P2 (8 tasks)

[P2 CVA + tokenize](docs/superpowers/plans/2026-06-28-p2-cva-tokenize.md) — 4 phases
- Phase 1: 硬编码 → status-* token (2 files)
- Phase 2: CVA 重写 (3 files: status-badge, app-error-banner, system-resources)
- Phase 3: 中 ROI CVA (2 files)
- Task 8: 验证

### P5 (29 tasks)

[P5 comments completion](docs/superpowers/plans/2026-06-28-p5-comments-completion.md) — 7 phases
- Phase 1-3: 30 common + 2 业务 + 1 app 文件头注释
- Phase 4-6: 21 处行内 P1 注释
- Phase 7: 验证

---

## 🛠 已知约束 (再跑时必须遵守)

### 项目规约 (CLAUDE.md + .claude/CLAUDE.md)

1. **中文注释** — 所有 `//` 和 `/** */` 必须中文
2. **不删注释** — 改代码保留所有原注释, 升级 `//` → `/** */` 可, 删除不行
3. **严禁绕过 oxlint/oxfmt** — 不能用 `# noqa` / `// oxlint-disable` (项目禁止 shim)
4. **严禁使用 cat> 覆盖已有文件** — 用 Edit, 先 Read
5. **import 按首字母排序** — oxfmt 自动处理
6. **TS strict 0 error** — typecheck 必须通过
7. **优先使用项目已有组件** — DataTable / AppDialog / AppConfirm / ErrorBanner / CopyButton / AppTooltip / Form / FormField
8. **路由跳转必须用 `@/i18n/navigation`** — 禁止 `next/navigation`
9. **i18n key 用中文** — `t("中文")`, zh.json identity
10. **状态色用 `bg-status-*` token** — 禁止硬编码 yellow/blue/green/red

### 工具链 (按顺序)

```bash
cd packages/web
bun run format         # oxfmt --write (auto)
bun run lint:fix       # oxlint --fix (auto)
bun run typecheck      # tsc --noEmit (必须 0 error)
bun run test           # vitest run
```

### Pre-existing failures (不修复, 不算新 fail)

baseline 10 failed test files / 5 failed tests:
- `components/chat/message-feedback.test.tsx` — next-intl ERR_MODULE_NOT_FOUND
- `components/common/navigation/app-back-link.test.tsx` — next-intl ERR_MODULE_NOT_FOUND
- `app/[locale]/submissions/_components/submissions-tabs.test.tsx` — next-intl ERR_MODULE_NOT_FOUND
- `app/[locale]/knowledge/triples/_components/triples-form.test.tsx` — next-intl ERR_MODULE_NOT_FOUND
- `app/[locale]/knowledge/documents/import/_components/import-commit-card.test.tsx` — next-intl ERR_MODULE_NOT_FOUND
- `app/[locale]/knowledge/layout.test.tsx` — DomainSwitcher not found
- `app/[locale]/knowledge/batch/page.test.tsx` — back-link not found
- `app/[locale]/knowledge/graph/page.test.tsx` — RSC stats mock
- `app/[locale]/knowledge/documents/page.test.tsx` — RSC stats mock
- `app/[locale]/knowledge/triples/page.test.tsx` — back-link not found

如果 task 跑完引入新 fail, **必须 fix** (否则 commit 会被 husky 拦).

### Master branch 已 ahead origin/master 18 commits

P4 加 11 commits. P3+P1+P2+P5 预计 +50-70 commits. 不 push (user 未明确要求).

### Stash 警告

`git stash list` 有 2 个 lint-staged 自动 backup. **不 reset / 不 checkout** (项目规约).

### Conflict marker

`packages/web/CLAUDE.md:268` 有 1 处 `<<<<<<< Updated upstream` 冲突标记 (pre-existing, 不属于我的改动). **不修复** (不是这个 task 的范围).

---

## 🚀 当前进度 (会话级)

- [x] **P4** 12/12 tasks 完成
- [x] **P3** 9/10 tasks (StandaloneQueryProvider + applyEvent dispatch + parseErrorDetail 复用)
- [x] **P1** 8 effective task commits across 6 phases (ErrorBanner 5/5 + PageHero 2/4 + BackLink 2/2 + AppDataEmpty 0/5 **SKIPPED [deviation](docs/audit/2026-06-28-code-quality-5d/p1-div-span/P5-appdataempty-destruct-DEVIATION.md)** + Badge 1/1) — **DialogFooter 7 sites 在用户质疑后撤掉 (Phase 4 已 revert, [deviation](docs/audit/2026-06-28-code-quality-5d/p1-div-span/P4-dialog-footer-DEVIATION.md))**
- [ ] **P2** 0/8 tasks
- [ ] **P5** 0/29 tasks

按 P3 → P1 → P2 → P5 顺序 subagent-driven 跑完. 每个 task:
1. Dispatch implementer subagent (机械实现 + test + commit)
2. Dispatch spec reviewer (验证 spec 符合)
3. Dispatch code quality reviewer (验证代码质量)
4. Update handoff progress
5. Move to next task

---

## 📝 实时进度日志

- [2026-06-28 22:55] **P4** 12/12 完成, 11 commits `7663ce38..dac15314`. Net +17 行 (38 files). 0 新 fail.
- [2026-06-28 23:00] **P3-T1**: StandaloneQueryProvider 工厂 + test (3 tests PASS), commit `984b06b4`
- [2026-06-28 23:03] **P3-T2**: dataset-switcher 用 StandaloneQueryProvider (-13 行), commit `6038d396`
- [2026-06-28 23:06] **P3-T3**: domain-switcher 用 StandaloneQueryProvider (-11 行), commit `dcd4cc31`
- [2026-06-28 23:08] **P3-T4**: app-health-dot 用 StandaloneQueryProvider (-10 行), commit `1256b5bb`
- **P3 Phase 1 完成**: StandaloneQueryProvider 抽取 + 3 处替换 (-34 行, 4 commits `984b06b4..1256b5bb`)
- [2026-06-28 23:40] **P3-T5+T6**: applyEvent 对象 dispatch (Record<ChatEvent["type"], EventHandler>), 5 tests added, commit `e63be044`
  - 偏离 spec: 实际 applyEvent 签名是对象 `({cid, msgId, ev, deps, state})`, 内部 message_end 有 3 个 side effect (persistMessages + upsertConversation + persistAssistantToServer) + conv metadata update. 改 1 处新增 event type: 在 EVENT_HANDLERS 加一行 (workflow_done/done 走 noop)
  - 5 tests PASS: message / thinking / error / 非匹配 msgId / done noop
- [2026-06-28 23:42] **P3-T7+T8**: config.ts:parseErrorDetail export + ingest.ts 17 行 inline 替换 (-12 行), commit `5ed92cac`
  - spec 提 chat.ts 也替换, 实际 chat.ts:34-37 是直接 include raw text, 非 body.detail 提取, 行为不同, 不替换 (跟 P4 跳过模式一致)
- [2026-06-28 23:46] **P3-T10**: 全量验证 PASS — typecheck 0 error, format:check 0 changes, vitest 1036 passed / 5 failed (与 baseline 完全一致, 0 新 fail). 1 pre-existing lint warning (app-dialog.test.tsx) 不属 P3 范围.
- **P3 完成**: 6 commits `984b06b4..5ed92cac`. 净节省 ~52 行 (StandaloneQueryProvider 抽 49 行重复 + parseErrorDetail 抽 12 行 + applyEvent dispatch -8 行).
- [2026-06-29 00:30] **P1-P1**: ErrorBanner 2/5 替换 (health-client + import-commit-card), commit `8aa43cd9`
  - 2 处 DONE_WITH_CONCERNS (batch/page.tsx + triples-form.tsx): ErrorBanner.description: string 不支持 `<ul>/<li>` 子节点. 需要先扩 ErrorBanner (e.g. 加 `descriptionNode?: ReactNode` slot) 或新抽 `<ErrorList>` 才能替换.
  - 1 处 NO-OP (evaluate-new-form.tsx): 已经在用 ErrorBanner.
- [2026-06-29 00:35] **P1-P1b**: ErrorBanner 加 descriptionNode slot + 替换 2 defer 列表错误块 (batch/page + triples-form), commit `d20295cd`
  - descriptionNode?: ReactNode 优先 description, 支持 `<ul>/<li>` 复杂子节点 (P1 batch/triples-form 案例)
  - 测试 12/12 PASS (含新增 descriptionNode test)
- **P1 Phase 1 完成**: 5/5 替换 (2 scalar + 2 list + 1 already done), 2 commits `8aa43cd9..d20295cd`
- [2026-06-29 00:50] **P1-P2+P3**: PageHero 2/4 (output/new + output-list-client) + BackLink 2/2 (task-detail + file page), commit `530de37a`
  - 2 处 DONE_WITH_CONCERNS (admin/users + admin/invites): 仅 `<h1> + button` 简单行, 无 eyebrow/description, PageHero 强需 eyebrow, 不 force-fit.
- [2026-06-29 01:00] **P1-P4**: DialogFooter 新抽 + 6 文件 / 7 site 替换, 2 commits `393b0ebc` (新 wrapper + test + barrel) + `d75780fd` (6 files)
  - 4 处 SKIPPED: task-detail-client (Card 内部) + output-card (DataTable 行 actions) + admin-users-table (表格 actions + pagination) + create-invite/reset-password-dialog (`flex gap-2` 不带 justify-end, 布局不同)
- [2026-06-29 01:10] **P1-P5**: AppDataEmpty variant=destructive 全部 SKIPPED, commit `124d1084` (含详细 deviation 报告)
  - 原因: spec 假设 AppDataEmpty 是 flat centered-text, 实际是 shadcn `<Empty>` + `<EmptyHeader>` + `<EmptyTitle>` 包裹 (border-dashed + flex-1 + p-6 md:p-12 + text-lg). 5 处 json-view/diff 想要纯居中文本, 强 fit 会改 padding/border/字号/布局 + 破坏 4 个 existing AppDataEmpty callers.
- [2026-06-29 01:30] **P1-P5**: AppDataEmpty variant="destructive" + 5 处 json 替换 **SKIPPED** ([deviation report](docs/audit/2026-06-28-code-quality-5d/p1-div-span/P5-appdataempty-destruct-DEVIATION.md)), commit `124d1084`
  - spec §Phase 5 假设 AppDataEmpty 是"扁平居中文本组件" (variant 类 map table/page/destructive), 实际实现是"shadcn `<Empty>` + `<EmptyHeader>` + `<EmptyTitle>`" 结构组件 (icon + title + description slots, 现有 4 处用法)
  - force-fit 5 处 json: 视觉从"细线占位"变成"大标题 + 虚线框 + 红警告图标" (`flex-1` + `border-dashed` + `text-lg font-medium tracking-tight` + AlertCircle), 跟 RSC JSON 库的"中性兜底"语义不符
  - 重构 AppDataEmpty 为扁平结构: 破坏 4 处现有用法 + 5 个 test assertion, 大改动 ROI 为负
  - **决策**: 按 P1 Phase 1 ErrorBanner / Phase 2 admin pages 的 "force-fit 风险 > spec 收益时 skip" 模式处理. 0 src 改动, 0 test 改动, 0 commit 节省. spec 估算 -20 行不实现.
  - **deviation 文件**: `docs/audit/2026-06-28-code-quality-5d/p1-div-span/P5-appdataempty-destruct-DEVIATION.md`
- [2026-06-29 01:40] **P1-P6**: message-bubble interrupted 用 Badge wrapper 替换 hand-rolled div, commit `f1589aee` (1 file, +5/-3)
  - 保留 custom warning 色 (`border-status-warning/40` + `bg-status-warning/10` + `text-status-warning` + `rounded-full` + `text-xs`) 通过 Badge variant=outline + className 合并
  - data-testid="interrupted-badge" 不变. 7/7 message-bubble tests pass
- [2026-06-29 01:50] **P1-T28**: 全量验证 PASS — typecheck 0 error, format:check 0 changes, lint 0 new warning (1 pre-existing app-dialog.test.tsx), vitest **1039 passed / 5 failed** (与 baseline 完全一致, 0 新 fail)
- **P1 完成**: 6 phases 全部跑完, 8 effective task commits `8aa43cd9..f1589aee`. 净节省 ~50 行 (ErrorBanner 4 替换 + descriptionNode slot + PageHero 2 替换 + BackLink 2 替换 + Badge 1 替换). 3 处 spec deviation (admin 2 pages PageHero force-fit 跳过 + AppDataEmpty 5 处 force-fit 跳过 + DialogFooter 7 sites 用户质疑后撤回), 都有 deviation 报告.
- [2026-06-29 01:55] **P1-Phase4-撤掉**: DialogFooter wrapper + 7 sites 全部 revert (用户质疑), commits `b4329052` + `b6e09d9c`. 撤掉原因 + 决策详见 [P4-dialog-footer-DEVIATION.md](docs/audit/2026-06-28-code-quality-5d/p1-div-span/P4-dialog-footer-DEVIATION.md). 净 -2 src commits, **真实 ROI 更高** (不引入新组件, 不增加维护面).
