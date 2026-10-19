# Handoff — Web 前端架构优化 (执行中)

**接手时间**: 2026-06-10
**执行方式**: subagent-driven-development (subagent 派发 + spec review + code quality review)
**原始 plan**: [docs/superpowers/plans/2026-06-10-web-frontend-architecture.md](2026-06-10-web-frontend-architecture.md) (1866 行, 11 task)
**原始 spec**: [docs/superpowers/specs/2026-06-10-web-frontend-architecture.md](2026-06-10-web-frontend-architecture.md) (429 行)

---

## ✅ 已完成 (Tasks 1, 2, 3, 4, 4.5, 5, 6a, 6b, 6c, 7)

### 1. Task 1 — `lib/api/auth.ts` (地基)

- **Commit**: `e0fdc9f` — `feat(web): 加 lib/api/auth 鉴权头工具 (admin 优先)`
- **Files**: `web/lib/api/auth.ts` (3 函数: getUserToken/getAdminToken/authHeaders), `web/lib/api/auth.test.ts` (7 cases)
- **结果**: 7/7 PASS, typecheck0错

### 2. Task 2 — `lib/api/swr.ts` 升级 fetcher

- **Commit**: `4fef6c3` — `feat(web): swr fetcher 注入 admin/user token, 抛 ApiError/NetworkError`
- **Files**: `web/lib/api/swr.ts` (fetcher + swrConfig + useApi), `web/lib/api/swr.test.ts` (4 cases)
- **结果**: 4/4 PASS, typecheck0错
- **Note**: fetcher 在 throw 现场把 `HTTP <status>: <text>` 拼成字符串传 `ApiError(status, formattedText)` — 与 spec snippet 略有偏差但合理 (test 期望 `HTTP 401: Unauthorized` 格式)

### 3. Task 3 — `lib/api/knowledge.ts` 业务客户端

- **Commit**: `cf6b983` — `feat(web): knowledgeApi 业务客户端 (统计直连 / multipart+BFF / Dify 走 BFF)`
- **Files**: `web/lib/api/knowledge.ts` (URL 工厂 + fetchStats/fetchQADocuments/createQA/uploadDocument/retrieveQA), `web/lib/api/knowledge.test.ts` (9 cases)
- **结果**: 9/9 PASS, typecheck0错
- **Note**: spec 描述"10 个用例"实际代码9个,按 code 走

### 4. Task 4 — `lib/api/chat.ts` + 删 `lib/api.ts`

- **Commit**: `f19bc17` — `feat(web): chatApi 客户端 (从 lib/api.ts 移过来) + 删 lib/api.ts`
- **Files**: `web/lib/api/chat.ts` (chatApi), `web/lib/api/errors.ts` (ApiError/NetworkError), `web/lib/api/chat.test.ts` (5 cases), `swr.ts` + `knowledge.ts` 改 import, `ChatShell.tsx` + ChatShell.test.tsx 改 import
- **结果**: 5/5 PASS, 25 总 lib/api tests pass
- **删除**: `web/lib/api.ts`, `web/lib/api.test.ts` (自动孤儿)

### 4.5. Plan Gap Fix — `lib/api/system.ts` (Task 4 发现的 plan 漏算)

- **Commit**: `bea4c7e` — `fix(web): 提取 systemApi 到 lib/api/system (Task 4 plan 漏掉 api 对象)`
- **触发**: Task 4 删 lib/api.ts 后 typecheck 12 错,因为旧 `lib/api.ts` 还导出 `api` 对象 (health/listSeries/decode/listOutputFiles/readOutputFile),被 4 个 app page 引用,plan 没覆盖
- **Files**: `web/lib/api/system.ts` (systemApi + private request<T> helper with AbortController 10s timeout), 4 个 app page + 2 个 page test 改 import
- **删除**: `web/lib/api.test.ts` (旧孤儿)
- **结果**: typecheck **0 errors**, 138 tests pass + 7 pre-existing failures 不变
- **关键决策**: implementer 从 git history (`HEAD~2:web/lib/api.ts`) 读出真实路径,不用我 task 描述里的伪造路径 (e.g. 实际是 `/api/output/files/${name}` 不是 `/api/output/${name}`)

### 5. Task 5 — `lib/api/evaluate.ts` 业务客户端

- **Commit**: `fcbe14c` — `feat(web): evaluateApi 业务客户端 (multipart 走 BFF + 鉴权后多用户)`
- **Files**: `web/lib/api/evaluate.ts` (4 URL factories + createRun/cancelRun), `web/lib/api/evaluate.test.ts` (7 cases)
- **结果**: 7/7 PASS, typecheck0错
- **类型决策**: page 用 `EvaluationRunSummary` (旧 `lib/evaluate/types.ts`),新 `EvalRunSummary` (lib/api/evaluate.ts) 没被 page 用 — reviewer 标 minor 类型 divergence 不阻塞

### 6a. Task 6a — knowledge 页面切 `knowledgeApi`

- **Commit**: `a0cf620` — `refactor(web): knowledge 页面切到 knowledgeApi (直连 FastAPI)`
- **Files**: 6 个 page (`qa/nodes/relations/triples/documents/batch`) + `knowledge.ts` 加 8 新方法 (URL 工厂 + fetchers + mutations) + 13 新 test cases (共 22)
- **结果**: typecheck0错, 22/22 knowledge tests, 158 pass / 5 pre-existing failures
- **关键发现**: FastAPI 实际路由是 `/api/kg/*` 不是 `/api/knowledge/*` (`src/rag/kg/router.py:26` 的 `prefix="/api/kg"`),implementer 用 first-principle 修了 plan 的路径错误
- **Reviewer 标 Important issues (未修,留 Task 9 处理)**:
  1. `qa/page.tsx:4` 死 import `import useSWR from "swr";` 需要删
  2. `knowledge.ts` 4 种 POST pattern 不一致 (postDirect vs inline vs post<T>) 建议统一
- **Reviewer 标 Minor issues (未修)**:
  1. URL factory (`nodesUrl/relationsUrl/schemaUrl`) 返回 `/api/knowledge/*` 但 fetcher 用 `/api/kg/*` — 不一致
  2. 3 个 page (nodes/relations/triples) 用 `useSWR` 直接带 closure 而非 spec 推荐的 `useApi(urlFactory)` — 但因为 fetcher 不能直接吃绝对 URL,这个 closure pattern 是唯一合理做法
  3. `fetchSchema` 缺 4xx ApiError test

### 6b. Task 6b — chat 页面切 `chatApi` (no-op)

- **结果**: Task4 已经迁移完所有 consumer (`ChatShell.tsx`),`app/chat/page.tsx` 通过 `<ChatShell>` 间接用 chatApi,不需要改
- **没新 commit**

### 6c. Task 6c — evaluate 页面切 `evaluateApi`

- **Commit**: `41e49f6` — `refactor(web): evaluate 页面切到 evaluateApi`
- **Files**: 3 个 page (`evaluate/page.tsx`, `evaluate/new/page.tsx`, `evaluate/[id]/page.tsx`)
- **结果**: typecheck0错, 7/7 evaluate tests pass
- **类型决策**: 用旧 `EvaluationRunSummary/EvaluationRun` from `lib/evaluate/types.ts` (一致 with `EvalListRow` + `StatusBadge`)
- **Reviewer 标 Minor (未修,留 follow-up)**:
  1. `EvalRunSummary` vs `EvaluationRunSummary` 两个 type name 相同 shape 但不同 module — future divergence 风险
  2. `refreshInterval: 0` 注释"列表不轮询"略 misleading (revalidateOnFocus 仍触发)
  3. `[id]/page.tsx` 的 `cancelRun` 没 try/catch (pre-existing)

### 7. Task 7 — 抽 KnowledgeHero/EmptyState + 移 StatCard/EntryCard

- **Commit**: `c8f6ed7` — `refactor(web): 抽 KnowledgeHero + KnowledgeEmptyState, 移 StatCard/EntryCard 到 components/knowledge`
- **Files**: 4 个新文件 (`KnowledgeHero.tsx` + test, `KnowledgeEmptyState.tsx` + test)
- **结果**: 18/18 components tests, 8/8 app/knowledge tests, typecheck0错
- **Step 9 no-op**: StatCard/EntryCard 在 Task6a 时已经移到 `components/knowledge/`,所有 consumer 已经在用新 path

---

## 🔄 当前阶段 — 待恢复执行

### Task 7 review (待派)

按 subagent-driven-development 流程,**Task 7 的 spec review + code quality review 还没派**。在派发 Task 8 之前需要补:

- 派 spec reviewer 验证 Task 7 (4 个新文件 + 2+2 test cases)
- 派 code quality reviewer 验证 Task 7 质量

### Task 8 — BFF 裁剪 11 个 route.ts ⏸️ (派发时被用户中断)

- **状态**: implementer prompt 已写好,但 agent call 被用户中断
- **要做的**:
  1. grep 验证 0 调用残留 (排除 `qa/retrieve` 和 `documents/upload` 保留 BFF)
  2. `git rm` 12 个文件:
     - `web/app/api/knowledge/datasets/route.ts`
     - `web/app/api/knowledge/documents/commit/route.ts`
     - `web/app/api/knowledge/health/route.ts`
     - `web/app/api/knowledge/nodes/route.ts`
     - `web/app/api/knowledge/qa/route.ts`
     - `web/app/api/knowledge/relations/route.ts`
     - `web/app/api/knowledge/schemas/route.ts`
     - `web/app/api/knowledge/schema/route.ts`
     - `web/app/api/knowledge/segments/route.ts`
     - `web/app/api/knowledge/stats/route.ts`
     - `web/app/api/knowledge/stats/route.test.ts`
     - `web/app/api/knowledge/templates/[format]/route.ts` (需移到 public/)
  3. 处理 `templates/[format]` route:
     - 检查 client 是否有 `/api/knowledge/templates/...` 调用
     - 如果有,把模板文件移到 `web/public/templates/` 改 `<a href>`
  4. 跑 `bun run typecheck && bun run test` 确认 0 错
  5. commit: `chore(web): 裁 11 个只转发 BFF (页面已直连 FastAPI)`
- **预期 commit**: 紧随 `c8f6ed7` 之后

---

## 📋 待办 (4 个)

### Task 8 — BFF 裁剪

- 见上文 "当前阶段"

### Task 9 — `/knowledge` 拆 documents + graph + KnowledgeTabs

- **Files**:
  - Create: `web/components/knowledge/KnowledgeTabs.tsx` + test (3 cases: 渲染 2 link, active 高亮, 非 active muted)
  - Create: `web/app/knowledge/page.test.tsx` (1 case: redirect to /knowledge/documents)
  - Create: `web/app/knowledge/documents/page.test.tsx` (3 cases: 渲染 KnowledgeHero title=向量库, 渲染 KnowledgeTabs, 不显示空态)
  - Create: `web/app/knowledge/graph/page.test.tsx` (2 cases: 渲染 KnowledgeHero title=知识图谱, 渲染 StatCard 节点数 + 关系数)
  - Modify: `web/app/knowledge/page.tsx` → redirect 到 `/knowledge/documents`
  - Modify: `web/app/knowledge/documents/page.tsx` → 用 KnowledgeHero + KnowledgeTabs + KnowledgeEmptyState (只留"向量库"section)
  - Modify: `web/app/knowledge/graph/page.tsx` → 用 KnowledgeHero + KnowledgeTabs (只留"知识图谱"section, 用 neo4j 数据)
- **plan 里的 KnowledgeTabs 实现**:

  ```tsx
  // 用 Link + usePathname 替代 shadcn Tabs
  const TABS = [
    { href: "/knowledge/documents", label: "向量库" },
    { href: "/knowledge/graph", label: "知识图谱" },
  ] as const;

  export function KnowledgeTabs() {
    const pathname = usePathname();
    return (
      <nav className="flex gap-1 border-b border-border/60">
        {TABS.map((t) => {
          const active = pathname?.startsWith(t.href) ?? false;
          return (
            <Link
              key={t.href}
              href={t.href}
              data-testid={`tab-${t.href.split("/").pop()}`}
              className={cn(
                "px-4 py-2 text-sm transition-colors",
                active
                  ? "border-b-2 border-clay text-foreground"
                  : "text-muted-foreground hover:text-foreground",
              )}
            >
              {t.label}
            </Link>
          );
        })}
      </nav>
    );
  }
  ```

- **顺带清理 Task 6a/6c 标 Minor issues (在 documents/graph page 重写时一并做)**:
  - `qa/page.tsx:4` 死 import `useSWR` 删
  - `knowledge.ts` 4 种 POST pattern 统一
  - URL factory 死代码清理
- **预期 commit**: Task 9 的子 commit 1 (KnowledgeTabs + redirect) → 子 commit 2 (documents + graph page)

### Task 10 — E2E `05-knowledge-routes.spec.ts`

- **File**: `web/e2e/05-knowledge-routes.spec.ts`
- **5 cases**:
  1. `/knowledge` 重定向到 `/knowledge/documents`
  2. 点"知识图谱"tab → URL 跳 `/knowledge/graph`,heading visible
  3. 浏览器后退回 `/knowledge/documents`,SWR 缓存命中不重请求 `/api/kg/stats`
  4. 直连 `/knowledge/graph` 显示知识图谱,不经 redirect
  5. `tab-documents` active 高亮 (border-clay class)
- **前提**: Task 9 完成才能跑

### Task 11 — 最终验证

- **Files**: 无 (只跑验证 + 改 to-do)
- **Step**:
  1. `cd web && bun run test` (期望: 全部 PASS, `lib/api/*.ts` 覆盖率 ≥ 80%)
  2. `bun run typecheck && bun run lint && bun run format:check` (期望: 0 错)
  3. `bun run test:e2e` (期望: 18 旧 + 5 新 全绿)
  4. 后端 `uv run --no-sync python -m pytest tests/ -q` (保险,虽然前端不影响后端)
  5. 划掉 `docs/to-do.md` 第1行:
     ```bash
     sed -i 's|^- \[\] http://localhost:3000/knowledge页面切换向量库和知识图谱用不同的路由|^- [x] http://localhost:3000/knowledge页面切换向量库和知识图谱用不同的路由 (2026-06-10 spec cb34b9d 已规划)|' docs/to-do.md
     git add docs/to-do.md
     git commit -m "chore: 划掉 knowledge 路由化待办 (本 spec 覆盖)"
     ```
  6. `git log --oneline -15` 看 commit

---

## ⚠️ 已知问题 / Pre-existing

### Pre-existing test failures (不在本 spec scope,不要修)

1. `web/lib/dify-datasets.test.ts > createDocumentByText 走 POST 带 indexing_mode`
2. `web/app/decode/page.test.tsx > DecodePage > 输入型号 + 提交 → 渲染结果`
3. `web/app/decode/page.test.tsx > DecodePage > decode 抛错 → 渲染错误信息`
4. `web/lib/chat/factory.test.ts > getChatProvider > CHAT_PROVIDER=dify`
5. `web/app/knowledge/triples/page.test.tsx > TriplesPage > 加载 schema 后渲染表格`
6. `web/app/knowledge/triples/page.test.tsx > TriplesPage > schema 加载失败时显示错误态`
7. `web/app/api/chat/messages/route.test.ts > provider 抛错 → 流里 yield error 事件 + [DONE]`

### Pre-existing lint bug (不在 scope)

- `web/.oxlintrc.json` 用 `ignore` 字段但 oxlint 1.x 需要 `ignorePatterns`
- `bun run lint` 因此会失败
- Pre-commit hook 也受这个影响

### 已记录 Minor issues (Task 9 顺带清理)

1. `qa/page.tsx:4` 死 import `useSWR`
2. `knowledge.ts` POST pattern 不统一 (4 种)
3. URL factory 死代码 (`nodesUrl/relationsUrl/schemaUrl`)
4. `EvalRunSummary` vs `EvaluationRunSummary` 类型 divergence
5. `[id]/page.tsx` 的 `cancelRun` 没 try/catch (pre-existing)

---

## 📦 当前 Git 状态

```
master 领先 origin/master 11 commits:
- aa0f119 docs(plan): web 前端架构优化 11 task
- cb34b9d docs(spec): web 前端架构优化
- 927f462 docs: update to-do list, remove completed items and add new task
- 287df3f chore(web): 删旧 /api/evaluate/reports BFF
- 7d46829 merge: 评估页重设计 + 异步后端 + admin token

执行 commit (新):
- e0fdc9f Task 1: auth.ts
- 4fef6c3 Task 2: swr.ts
- cf6b983 Task 3: knowledge.ts
- f19bc17 Task 4: chat.ts + 删 lib/api.ts
- bea4c7e Task 4.5: systemApi (plan gap fix)
- fcbe14c Task 5: evaluate.ts
- a0cf620 Task 6a: knowledge 页面切直连
- (none) Task 6b: no-op
- 41e49f6 Task 6c: evaluate 页面
- c8f6ed7 Task 7: KnowledgeHero/EmptyState 抽取

待做:
- Task 8 (即将恢复)
- Task 9, 10, 11
```

工作树: **clean**

---

## 🚀 继续执行的 Step-by-Step

### Step 1: 补 Task 7 的 review (被跳过)

派 1 个 spec reviewer + 1 个 code quality reviewer 对 commit `c8f6ed7` 验证

### Step 2: 重新派 Task 8 implementer (用上次的 prompt)

Agent call 已写好,可以直接派 (prompt 在 conversation history 里)

### Step 3: Task 8 spec review + code quality review

### Step 4: 派 Task 9 implementer

注意:

- Task 9 是 serial,独立可一次完成 (3 个 page + KnowledgeTabs + 4 test files)
- Implementer 在 documents/graph page 重写时**顺带清理** Task 6a/6c 标 Minor issues
- commit 分两个: 子 commit 1 (KnowledgeTabs + redirect + page.test.tsx), 子 commit 2 (documents + graph page)

### Step 5: Task 9 spec review + code quality review

### Step 6: 派 Task 10 implementer (E2E)

- Task 10 需要 next dev server 起来,确保 `bun run test:e2e` 环境能跑
- 5 个 E2E cases

### Step 7: Task 10 review (仅 spec review,E2E 一般不需要 quality review)

### Step 8: 派 Task 11 implementer (最终验证)

- 跑全量验证
- 划 to-do
- 最终 commit

### Step 9: final code review

派 1 个 reviewer 验证整个 PR (从 `aa0f119` 到 HEAD)

---

## 📝 关键 File Path 速查

```
web/lib/api/
├── auth.ts          (Task 1, 7 cases)
├── auth.test.ts     (Task 1)
├── swr.ts           (Task 2, 4 cases)
├── swr.test.ts      (Task 2)
├── chat.ts          (Task 4, 5 cases)
├── chat.test.ts     (Task 4)
├── chat.ts          (Task 4)
├── errors.ts        (Task 4, no test — pure classes)
├── knowledge.ts     (Task 3+6a, 22 cases)
├── knowledge.test.ts(Task 3+6a)
├── evaluate.ts      (Task 5, 7 cases)
├── evaluate.test.ts (Task 5)
└── system.ts        (Task 4.5, no test — covered by app tests)

web/components/knowledge/
├── KnowledgeHero.tsx + test (Task 7, 2 cases)
├── KnowledgeEmptyState.tsx + test (Task 7, 2 cases)
├── KnowledgeTabs.tsx (Task 9, 待创建)
├── KnowledgeTabs.test.tsx (Task 9, 待创建, 3 cases)
├── StatCard.tsx (已存在,Task 6a 移过来)
└── EntryCard.tsx (已存在,Task 6a 移过来)

web/app/api/knowledge/
├── qa/retrieve/route.ts        (保留, Dify)
├── documents/upload/route.ts   (保留, multipart)
├── batch/route.ts              (保留, background task)
└── [11 个待删 — 见 Task 8 清单]

web/app/knowledge/
├── page.tsx        (Task 9 → redirect)
├── page.test.tsx   (Task 9, 1 case)
├── documents/page.tsx (Task 9 → KnowledgeHero + Tabs + EmptyState)
├── documents/page.test.tsx (Task 9, 3 cases)
├── graph/page.tsx (Task 9 → KnowledgeHero + Tabs)
├── graph/page.test.tsx (Task 9, 2 cases)
├── qa/page.tsx     (Task 6a 已迁,Task 9 顺带删死 import)
├── nodes/page.tsx  (Task 6a 已迁)
├── relations/page.tsx (Task 6a 已迁)
├── triples/page.tsx (Task 6a 已迁)
└── batch/page.tsx  (Task 6a 已迁)

web/app/evaluate/
├── page.tsx        (Task 6c 已迁)
├── new/page.tsx    (Task 6c 已迁)
└── [id]/page.tsx   (Task 6c 已迁)

web/e2e/
└── 05-knowledge-routes.spec.ts (Task 10, 5 cases)
```

---

## 🛠 常用命令

```bash
# 跑单个 test 文件
cd web && bun run test lib/api/knowledge.test.ts

# 跑全部
cd web && bun run test

# typecheck
cd web && bun run typecheck

# lint (pre-existing bug,会失败但可观察)
cd web && bun run lint

# E2E (Task 10 才用)
cd web && bun run test:e2e

# 看 git log
cd /c/doc/Code/worktrees/rag-refactor && git log --oneline -15

# 验证 BFF 路径残留 (Task 8)
cd web && grep -rn "/api/knowledge/datasets\|/api/knowledge/documents/commit\|/api/knowledge/health\|/api/knowledge/nodes\|/api/knowledge/qa\b\|/api/knowledge/relations\|/api/knowledge/schemas\|/api/knowledge/schema\b\|/api/knowledge/segments\|/api/knowledge/stats\|/api/knowledge/templates" app/ components/ lib/ 2>&1 | grep -v "qa/retrieve\|documents/upload"
```

---

## ✅ 最终验收 (Task 11 完成时)

- `bun run test` 全部 PASS (除 7 pre-existing)
- `bun run typecheck` 0 errors
- `bun run lint` 仍然因 pre-existing config bug 失败 (不在 scope)
- `bun run test:e2e` 18 旧 + 5 新 全绿
- `docs/to-do.md` knowledge 行划掉
- 后端 `uv run python -m pytest tests/ -q` PASS

---

## 💡 接手 Tips

1. **不要修改 pre-existing failures** — 它们在 spec 范围外,改坏会拖长工期
2. **Task 8 要先 grep 验证 0 调用残留** — 如果有,先在 `knowledgeApi` 加方法走直连,再删 route
3. **Task 9 是 serial** — 不能并行,因为 KnowledgeTabs 要先于 documents/graph page
4. **Task 9 顺带清理 Task 6a/6c 标 Minor issues** — 节省 follow-up 工作
5. **Task 10 E2E 需要 dev server** — 跑 `bun run test:e2e` 自动起 next dev + 后端
6. **每个 task 完成后做 spec review + code quality review** — 不要跳,这是 subagent-driven-development 的核心质量门
7. **如果 implementer 报 BLOCKED 或 NEEDS_CONTEXT** — 先看上下文,补信息后重新派,不要手动改 (避免 context pollution)
