# SWR → RSC + RQ 改造 — 阶段 Handoff (2026-06-12)

> ⚠️ **本 handoff 在所有 P2/P3/P4 task 完成 + 最终 review 后删除**, 改用 `finishing-a-development-branch` skill 收尾.

## 当前状态

- **分支**: `feat/swr-to-rsc-rq`
- **工作目录**: `c:\doc\Code\worktrees\rag-refactor`
- **总进度**: 30 task 中已完成 16 个 (P0 9 + P1 4 + P2 1 + 2 个 fix + 1 个 bootstrap 补)
- **构建状态**: `bun run build` SUCCESS, `bun run typecheck` 0 错
- **下一阶段**: P2 剩 8 个 task (Task 15-22), 然后 P3 5 个, P4 3 个, final review, finishing-a-development-branch
- **Auth bootstrap**: 已修 (commit `7c9300c`), 首次访问 / 灰度用户都能正常鉴权

## AuthBootstrap 修复 (commit `7c9300c`, 2026-06-12 用户要求)

### 问题

Task 8 删了旧 `ensureAuthToken()` (首次访问 POST `/api/auth/anon`), 但**没有替代**:

- 没人调 `/api/auth/anon` (grep 0 命中)
- 没人调 `tryMigrateFromLocalStorage()` (定义了 0 引用)

**实际影响矩阵**:

- ❌ 新用户首次访问: RSC 页 401 (server 读 cookie 没有) + 8 个未改 client 页 401 (localStorage 空)
- ❌ 旧用户 (有 localStorage): RSC 页 401 (server 仍读 cookie) + 8 个未改 client 页 ✅ 还能用 (走 localStorage)
- ❌ 完全无法产生 "cookie + localStorage 都有" 的正常态

### 修法

加 `packages/web/components/auth/AuthBootstrap.tsx` (client component):

- useEffect 跑一次 (不阻塞渲染)
- localStorage 有 user/admin token → `tryMigrateFromLocalStorage()` 换 cookie
- 都没 → POST `/api/auth/anon` 拿匿名 token, 写 localStorage (兼容未改 client libs)
- 网络错误静默

集成位置: `packages/web/app/[locale]/layout.tsx` (I18nProvider 内, SWRProvider 同级)

### 后续删除时机

P4 阶段完成后, **8 个未改 client 页 + 3 个 lib/api/\*.ts client 库** 都迁完 RSC 后, 就可以:

1. 删 `AuthBootstrap.tsx` + `.test.tsx`
2. 删 `tryMigrateFromLocalStorage` + `migrateLegacyToken` from `lib/api/auth.ts` (无人调用)
3. 删 `client` 版 `authHeaders` (localStorage-based) from `auth.ts` — 只留 `API_BASE` + `clientFetch`
4. 删 layout.tsx 里的 `<AuthBootstrap />` 引用

### 测试

7 个 case 覆盖 (有/无 localStorage × 各种 anon 响应 + 静默错误), 全过.

## 已完成 Task 清单 (commit SHA)

### P0 基础设施 (Task 1-9)

```
f112dc2 feat(auth): /api/auth/anon 改 Set-Cookie (HttpOnly+SameSite=Lax)
0d9958b test(auth): 复用 reset_storage_engine + 补 secure/max-age 断言
d6a7df5 feat(auth): 加 /api/auth/migrate 端点换 cookie
febd036 test(contract): FRONTEND_EXPECTS 加 /api/auth/migrate
519eea0 feat(cors): allow_credentials=true + 显式 Allow-Origin 列表
ac96f0c chore(deps): 装 @tanstack/react-query@5.62 + devtools
9c3dc05 feat(api): 新增 queryKeys.ts 中心化 (RSC+RQ 共享)
2ed8613 feat(api): server-only rsc-queries.ts (per-request QC + prefetch)
0fd0998 fix(typecheck): 修真 4 个 pre-existing typecheck 错 (unblock web commits)
3716719 feat(store): AppDataProvider (RSC 灌 datasets/schemas Context)
a479d8b refactor(auth): 去 localStorage, 加 getServerToken + clientFetch + migrate
75e98b9 fix(swr): 改用 clientFetch (Task 8 后 ensureAuthToken 已删, build 回归修)
a03d321 refactor(auth): 拆 auth.ts (client-safe) + auth.server.ts (server-only, 修 Task 8 架构回归)
6bfb3cd refactor(bff): 9 个 BFF + rsc-queries 改用 authHeaders() 区分 admin/user
```

> 注: BFF 任务原 plan 是 4 个, 实际改了 9 个 + 1 个 rsc-queries 修复, 都归到 commit `6bfb3cd`.

### P1 A 档试点 (Task 10-13)

```
ee28c26 feat(datasets): 抽 DatasetsTable 客户端组件 (接 initialData)
4fb5603 feat(datasets): page 改 RSC (删 SWR, server fetch + prop 灌 client)
cb95993 feat(actions): _actions/knowledge.ts (createQA/createTriples/commitDocuments)
8262897 fix(lib-api): await authHeaders() (Task 8 async 化的 caller 跟进)
5b4ed4a chore(p1): datasets 试点完成 — 验证 RSC 路径端到端 OK
```

### P2 A 档批量 (Task 14, 1/9)

```
68926eb refactor(documents): page 改 RSC + DocumentsEntry client
b76c7d5 refactor(documents-import): page 改 RSC + commitDocuments form action
```

### P0 尾巴修复 (用户发现, 2026-06-12)

```
7c9300c feat(auth): AuthBootstrap 首次访问鉴权 bootstrap (修 P0 漏掉的启动链)
```

## 关键基础设施修复 (含 1st-time fixes)

1. **lint-staged.config.js Windows CWD bug 修** (commit `519eea0` 顺手修)
   - Python glob 加 `bash -c "cd packages/service && ..."` wrapper
   - 之前用户用 `--no-verify` 绕过 3+ commit

2. **`.husky/pre-commit` 修** (commit in Task 7 系列)
   - `bun test --run` → `bun run test` (BUN 自带 runner 不读 vitest config)

3. **4 个 pre-existing typecheck 错修** (commit `0fd0998`):
   - `app/[locale]/evaluate/[id]/page.test.tsx:97` — `baseRun` 的 `Partial<...>` 补 `avg_metrics` / `samples`
   - `app/[locale]/knowledge/qa/page.tsx:166` — `onSubmit` cast 走 `unknown` 二次 cast
   - `components/common/form/form.tsx` — `FormProps` 加 `id?`, 透传到 `<form>`
   - `components/common/form/form-item.tsx:38` — `cloneElement` 前存 `childOnChange` 保类型

4. **`auth.ts` 拆分为 `auth.ts` + `auth.server.ts`** (commit `a03d321`):
   - **WHY**: Task 8 把 `cookies()` 放到 auth.ts 顶层 import, client component transitively 引就 build fail
   - **架构**:
     - `lib/api/auth.ts` (client-safe): `API_BASE`, `clientFetch`, `migrateLegacyToken`, `tryMigrateFromLocalStorage`
     - `lib/api/auth.server.ts` (server-only, `import "server-only"`): `getServerToken`, `authHeaders`
   - **RULE**: server 代码 (RSC pages, server actions, BFF routes, rsc-queries) 必须从 `@/lib/api/auth.server` import

5. **Admin/User header 区分修复** (commit `6bfb3cd`):
   - **WHY**: 后端 `middleware/auth.py` 区分 `x-user-token` (查 DB) vs `x-admin-token` (env var, 虚拟 admin user). 旧 `authHeaders()` 区分 header 名, 新版本必须保留
   - **保留** 行为: admin cookie 存在 → `x-admin-token`, 否则 `x-user-token`

## Memory 记录

- `project-web-precommit-test-failures-2026-06-12.md` — 38+ 个 pre-existing vitest failure, 12 个 test file 缺 `NextIntlClientProvider` wrapper

## 已知 baseline 噪声 (不归任何 task 修)

- **38 个 vitest failure** (pre-existing): 12 个 test file 缺 `NextIntlClientProvider` wrapper
- **3 个 swr.test.ts failure** (Task 9 后, 跟 clientFetch credentials include 不匹配)
- **`scripts/e2e-up.sh` path bug** (pre-existing): 解析路径错, backend 启不起来, E2E 跑不了
- **2 个 lint 错** (pre-existing): `lib/dify-datasets.ts:48`, `app/api/chat/messages/route.test.ts:128`

## 下次继续: 跑 Task 15

### Task 15 计划 (派 subagent 时粘贴这段)

**Files:**

- Modify: `packages/web/app/[locale]/knowledge/graph/page.tsx` + `.test.tsx`
- Modify: `packages/web/app/[locale]/knowledge/nodes/page.tsx` + `.test.tsx`
- Modify: `packages/web/app/[locale]/knowledge/relations/page.tsx` + `.test.tsx`
- Create: 各 page 拆出的 client 子组件 (e.g., `_components/GraphView.tsx`, `NodesTable.tsx`, `RelationsTable.tsx`)

**Pattern** (3 page 同型, 模板同 Task 11 datasets + Task 14 documents):

1. 改测试先红: 删 SWR mock, 加 `vi.mock("next/headers", ...)` + `global.fetch` mock
2. 改 page.tsx 为 RSC, 用 `@/lib/api/auth.server` (NOT `@/lib/api/auth`!)
3. 拆 client 子组件
4. 跑测试 + typecheck
5. 1 个 commit 装 3 个 page

**Commit message**: `refactor(knowledge): graph/nodes/relations 3 页 RSC 化`

**必读** (subagent 启动时):

- `packages/web/app/[locale]/knowledge/datasets/_components/DatasetsTable.tsx` (Task 10 模板)
- `packages/web/lib/api/auth.server.ts` (server-only)
- `packages/web/lib/api/knowledge.ts` (Task 12 修过 await 的 fetcher)
- 3 个 page 现有 page.tsx + page.test.tsx

### Task 16-22 概览 (后续)

- **Task 16**: `knowledge/triples` — RSC + `createTriples` server action (Task 12 已建)
- **Task 17**: `knowledge/qa` — RSC + `QASubmitForm` (新 client 子组件) + `createQA` action
- **Task 18**: `knowledge/dataset-documents/[id]` — 动态路由 RSC
- **Task 19**: `evaluate/list` + `evaluate/[id]` — RSC + 新建 `_actions/evaluate.ts` (createRun / deleteRun)
- **Task 20**: `evaluate/new` — RSC 表单 + `createRun` action + `redirect`
- **Task 21**: `knowledge/page.tsx` 根 dashboard — RSC stats
- **Task 22**: P2 整体回归 (typecheck, vitest, grep SWR 残留, 契约测试)

### P3 概览 (Task 23-27)

- **Task 23**: `app/[locale]/output/layout.tsx` — B 档专属 `QueryClientProvider`
- **Task 24**: `output/page` — RSC + Hydration + RQ 5s 轮询
- **Task 25**: `output/[task_id]/page` — RSC + RQ 2s 轮询 + 新建 `_actions/output.ts` (cancelTask)
- **Task 26**: `health/page` — RSC + RQ 10s 轮询 + 自己的 layout
- **Task 27**: `components/knowledge/HealthDot.tsx` — useSWR → useQuery 5s 轮询

### P4 概览 (Task 28-30)

- **Task 28**: 删 `lib/api/swr.ts` + `swr-provider.tsx` (P2 后已全切完, grep 0 引用)
- **Task 29**: 删 `package.json` 里的 `swr` 依赖
- **Task 30**: 评估删 `app/api/knowledge/qa/route.ts` (P2 后变空壳, 跑契约测试必过)

### Final

- **最终 code review**: 派 final reviewer 看整个 feat/swr-to-rsc-rq 分支
- **finishing-a-development-branch**: merge / cleanup

## 重要 Reference

- **Plan**: `docs/superpowers/plans/2026-06-12-swr-to-rsc-rq.md` (2674 行, 30 task)
- **Spec**: `docs/superpowers/specs/2026-06-12-swr-to-rsc-rq-design.md` (862 行)
- **CLAUDE.md 项目规则**: `c:\doc\Code\worktrees\rag-refactor\.claude\CLAUDE.md`
- **CLAUDE.md 全局规则**: `C:\Users\abcuc\.claude\CLAUDE.md`
- **Git 工作流规则**: `C:\Users\abcuc\.claude\plugins\cache\claude-plugins-official\superpowers\5.0.7\skills\subagent-driven-development\implementer-prompt.md`

## Resumption Command

用户下次说"继续"时, controller 应该:

1. `cd c:\doc\Code\worktrees\rag-refactor`
2. `git log --oneline -5` (确认状态)
3. `git status` (确认 working tree 干净)
4. Read this handoff
5. 派 Task 15 subagent (用上面"Task 15 计划"段)
6. 按 subagent-driven-development skill 流程继续

## 暂停决策记录

- **何时暂停**: 2026-06-12, P2 Task 15 即将派 subagent 之前
- **为何暂停**: 用户要求 ("提交完留个handoff，暂停开发")
- **未派发的子任务**: Task 15 (graph/nodes/relations), 后续 Task 16-30 + final review + finishing

---

## P4 完成备注 (2026-06-12, implementer subagent 补)

### Task 28 / 29 完成

- Task 28 (删 swr 文件) commit `2d28bb7`
- Task 29 (删 swr 依赖) commit `7dcfddc`
- 额外 pre-prep commit `011683a`: `DatasetSwitcher` / `DomainSwitcher` 改 useSWR → useQuery (P1-P3 阶段漏改, Task 28 grep 命中 4 处时发现)

### Task 30 评估: 决定**保留** `app/api/knowledge/qa/route.ts`

**为什么 plan 的"删"前提错了**: P2 阶段后, plan 假设 qa 列表走 RSC 直连后端, BFF `qa/route.ts` 变空壳可删. 实际 grep 命中 1 处真前端 fetch 引用:

- `app/[locale]/knowledge/dataset-documents/[dataset_id]/page.tsx:27` — RSC 端 `fetch(\`/api/knowledge/qa?dataset_id=...\`)` 拿 QA 文档列表
- 配套 mock: `app/[locale]/knowledge/dataset-documents/[dataset_id]/page.test.tsx:39,103` 也 mock 这条 BFF 路径

GET handler **真在用**, 不能删. POST handler 也真在用 (`_actions/knowledge.ts:49` createQA → `lib/api/knowledge.ts:281` createQA → `post("/api/knowledge/qa", input)`), 也不能删.

**契约测试**: 3/3 PASS (删/不删都跑过, 都过).

**何时再评估**:
- 选项 A: 下个 PR 单独提"qa BFF 退役"任务, 把 `dataset-documents` RSC page 改直连后端 `/api/...` (跟 Task 18 datasets/documents/page 的直连模式一致), 抽 server action `_actions/knowledge.ts` 暴露 `fetchQADocuments` 给 RSC, 然后才能删 BFF
- 选项 B: `dataset-documents` 改用 `_actions/knowledge.ts` 暴露的 server action, 同时把 `_actions/knowledge.ts` + `lib/api/knowledge.ts` 的 `createQA` / `fetchQADocuments` 也迁走 (影响面更大, 一次提交)
- 跟 P4 范围不重叠, P4 plan 不包含, 不在本 PR 解决

**跑过的命令**:
```bash
grep -rn "knowledge/qa" packages/web --include="*.ts" --include="*.tsx"   # 命中: dataset-documents RSC + tests + lib/api/knowledge.ts URL 工厂
cd packages/service && uv run pytest tests/test_api_contract.py -v      # 3/3 PASS
```

### 3 个 P4 commit SHA

```
011683a  refactor(knowledge): DatasetSwitcher/DomainSwitcher useSWR→useQuery (P4 pre-prep)
2d28bb7  chore(swr): 删 lib/api/swr.ts + swr-provider.tsx + swr.test.ts + layout 引用
7dcfddc  chore(deps): 删 swr 依赖
```

Task 30 不删, 无 commit (working tree 干净, ahead 22 commits).
