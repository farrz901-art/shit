# Pre-existing Test Failures 修复计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复 10 个 pre-existing vitest test fail，把 baseline 从 `719 passed + 10 fail` 恢复到 `729 passed + 0 fail`。

**Architecture:** 三类根因：
1. **R1（5 fail）**：`next/navigation` 在 next 16 + vitest 下 ESM 解析失败 → 一行 `resolve.alias` 修所有
2. **R2（2 fail）**：`SettingsDialog` 缺 "账号" 行是用户主动决定（不是 bug）→ 删 2 个过时测试
3. **R3（3 fail）**：RSC `apiFetch` 在 jsdom 下 URL 分流/数据未达 StatCard → 需读 `documents/page.tsx` / `graph/page.tsx` / `knowledge/layout.tsx` 找根因，备两套方案

**Tech Stack:** Bun + vitest 4.x + jsdom + next 16 + next-intl 4.x + TanStack Query

**前置约束（来自 CLAUDE.md）**：
- `bun run lint` 必须 0 warning
- `bun run typecheck` 必须 0 error
- 改前先 `git status` 看工作树, **不要 `git reset --hard`**
- 单次 `--fix` 改 > 500 行 → 停下来问用户
- pre-existing test fail 列 `KNOWN_ISSUES.md` / 进度文件, **不雪崩修**（本任务例外：用户明确要求修）
- 跑 `bun run test` 必须**单次**拿到 (file:line + assertion) 定位 (memory: `feedback-bun-run-test-no-redundant-runs`)

---

## ⚠️ 执行状态（2026-06-27）

| Task | 状态 | Commit | Fail 减少 |
|------|------|--------|----------|
| Task 1 (vitest alias) | ⏭️ **跳过** | — | 0（方案不解决问题） |
| Task 2 (删 SettingsDialog 死回归) | ✅ 完成 | `7a1439c2` | -2（2 pass） |
| Task 3 (R3 诊断) | ⏭️ **跳过**（用户 2026-06-27 决定整体跳过 Task 1+3） | — | 0 |
| Task 4 (全量验证 + docs 更新) | ✅ 完成 | 本次 commit | — |

**最终 baseline**：719 + 2 = 721 passed + 8 fail（R1: 5 + R3: 3，deferred 待新 spec 处理）

### Task 1 跳过原因

试过 2 个方案都不能解决 `Cannot find module 'next/navigation' imported from next-intl/dist/esm/development/navigation/react-client/createNavigation.js`：

1. **方案 A**（plan 写的）：`resolve.alias: { "next/navigation": ".../navigation.js" }` → **失败**
2. **方案 B**（实际跑的，加 Vite plugin `resolveId` 也 alias）→ **失败**

**根因**：vitest jsdom 环境下 next-intl 4.x 内部 `import("next/navigation")` 走 **Node ESM loader**，**绕开 Vite 的 resolve.alias 和 resolveId plugin**。`vitest.setup.ts` 的 `vi.mock("@/i18n/navigation")` 也只能挡测试代码 import，挡不住 next-intl 内部已经加载的 module。

**可能正确方案**（未验证，留给后续 spec）：
- `vitest.config.ts` `server.deps.inline: ["next-intl"]` 拉进 Vite module graph
- `vitest.setup.ts` `vi.mock("next-intl/navigation", { createNavigation: () => ... })` mock 整个 next-intl/navigation
- 降级 next-intl 到 3.x

### Task 3 跳过原因

R3 3 个 fail 根因未诊断（Plan 给了 3 个候选方案 A/B/C），用户判断 R1 + R3 整体复杂度超出本次范围，决定**只保留 Task 2** 提交。8 fail 状态延后到新 spec 处理。

### 改动文件清单

- `packages/web/components/settings/settings-dialog.test.tsx`（Task 2：删 2 个 it + 1 个 unused import）
- `docs/superpowers/plans/2026-06-27-pre-existing-test-failures.md`（本次：加执行状态段）
- `packages/web/CLAUDE.md`（Task 4 step 3：更新 baseline 表格）

---

## Task 1: vitest config 加 `next/navigation` 别名（R1, 5 fail 一并修）

**Files:**
- Modify: `packages/web/vitest.config.ts:10-19`（resolve.alias 段）

**根因**：
next 16 把 `exports["./navigation"]` 配成 `{ default: "./navigation.js" }`，但 next-intl 4.x 的 `createNavigation.js` 内部用 `import("next/navigation")`（不带 .js 后缀）。Vitest + Node ESM 解析 `next/navigation` 失败，错误：

```
Error: Cannot find module '.../node_modules/next/navigation' imported from
.../node_modules/next-intl/dist/esm/development/navigation/react-client/createNavigation.js
Did you mean to import "next/navigation.js"?
```

`vitest.setup.ts:11-26` 已经有 workaround（mock `next/navigation` 和 `@/i18n/navigation`），但**挡不住** `createNavigation.js` 内部 import 触发（vitest vi.mock 只能挡从测试代码触发的 import 链）。

**修复**：在 `vitest.config.ts` 加 `resolve.alias`，让 ESM 解析直接找到 `.js` 文件。一行 alias 解决 5 个测试。

### Steps

- [ ] **Step 1: 验证 alias 修复方向**

```bash
cd c:/doc/Code/rag/packages/web && \
  node -e "console.log(require.resolve('next/navigation'))"
```

预期：打印 `.../node_modules/next/navigation.js`

如果打印 `navigation.d.ts` 路径，ESM 解析不会接受 d.ts —— 必须 alias 到 `navigation.js`。

- [ ] **Step 2: 改 vitest.config.ts**

**文件**：`packages/web/vitest.config.ts`

找到 `resolve.alias` 段（line 10-19），在 `zod:` 这行**下面**加一行：

```ts
    resolve: {
      alias: {
        "@": path.resolve(__dirname, "."),
        // Server-only 是个 marker module, 在测试环境 (jsdom/client) 引入会抛错.
        // RSC prefetch 工具的测试需要导入它, 所以在 vitest 把它 alias 成空模块.
        "server-only": path.resolve(__dirname, "test-shims/server-only-empty.ts"),
        // Zod v4 ESM 在 vitest jsdom 下 re-export 为 undefined, 强制走 CJS 入口
        zod: path.resolve(__dirname, "node_modules/zod/index.cjs"),
        // (2026-06-27 R1 修复) next 16 + next-intl 4.x: createNavigation.js 内部
        //   import("next/navigation") (无 .js 后缀), vitest + Node ESM 解析失败
        //   (Cannot find module 'next/navigation'). 强制 alias 到 .js 文件, 让 ESM
        //   解析直接命中. 5 个使用 useRouter 的测试同时修复.
        "next/navigation": path.resolve(__dirname, "node_modules/next/navigation.js"),
      },
    },
```

- [ ] **Step 3: 跑单文件确认 R1 修复**

```bash
cd c:/doc/Code/rag/packages/web && \
  bunx vitest run components/chat/message-feedback.test.tsx components/common/navigation/app-back-link.test.tsx app/\[locale\]/submissions/_components/submissions-tabs.test.tsx app/\[locale\]/knowledge/triples/_components/triples-form.test.tsx app/\[locale\]/knowledge/documents/import/_components/import-commit-card.test.tsx
```

预期：5 个文件全部 PASS（之前 0 测试运行就被 setup 错误拦了，现在 5 个文件跑出实际测试结果 + 5 个文件全 pass）。

如果仍有 fail:
- 错误若仍说 `Cannot find module 'next/navigation'` → 确认 alias 写对位置
- 错误若说新问题 → 记下文件:行号, 不重跑, Read 报错堆栈

- [ ] **Step 4: Commit**

```bash
cd c:/doc/Code/rag && \
  git add packages/web/vitest.config.ts && \
  git commit -m "fix(vitest): alias next/navigation → navigation.js 修 ESM 解析

next 16 的 exports 配 { default: './navigation.js' }, next-intl 4.x
createNavigation.js 内部用 import('next/navigation') (无后缀), vitest + Node
ESM 解析失败. 加一行 resolve.alias 强制命中 .js 文件.

修 5 个 pre-existing fail:
- components/chat/message-feedback.test.tsx
- components/common/navigation/app-back-link.test.tsx
- app/[locale]/submissions/_components/submissions-tabs.test.tsx
- app/[locale]/knowledge/triples/_components/triples-form.test.tsx
- app/[locale]/knowledge/documents/import/_components/import-commit-card.test.tsx"
```

---

## Task 2: 删 SettingsDialog 2 个过时测试（R2）

**Files:**
- Modify: `packages/web/components/settings/settings-dialog.test.tsx:34-40, 48-56`

**根因**：
`SettingsDialog` 当前**故意只有 2 行**（主题 + 语言），没有"账号"行 / `settings-account-link` testid。这是用户 2026-06-27 conversation 明确决定。T4.3 规划时写过 2 个测试（"渲染 3 行" + "账号行激活"），但实现后来被删，**测试没同步删**，变成死回归。

详见 memory: `project-settings-dialog-no-account-row`。

### Steps

- [ ] **Step 1: 读测试文件确认要删的 2 个 it 块**

读 `packages/web/components/settings/settings-dialog.test.tsx` line 34-40 + 48-56，确认是这 2 个 `it(...)`：

- `it("渲染 3 行: 主题 (活) / 语言 (disabled) / 账号 (disabled)", ...)`
- `it("语言行可交互, 账号行激活 (链 /account/settings) — T4.3", ...)`

- [ ] **Step 2: 删 2 个过时 it 块**

**文件**：`packages/web/components/settings/settings-dialog.test.tsx`

**改 1**：删 `it("渲染 3 行...")` 整个块：

```diff
-  it("渲染 3 行: 主题 (活) / 语言 (disabled) / 账号 (disabled)", () => {
-    renderDialog({ onOpenChange: vi.fn(), open: true });
-    const dialog = screen.getByRole("dialog");
-    expect(within(dialog).getByText("主题")).toBeInTheDocument();
-    expect(within(dialog).getByText("语言")).toBeInTheDocument();
-    expect(within(dialog).getByText("账号")).toBeInTheDocument();
-  });
```

**改 2**：删 `it("语言行可交互, 账号行激活...")` 整个块：

```diff
-  it("语言行可交互, 账号行激活 (链 /account/settings) — T4.3", () => {
-    renderDialog({ onOpenChange: vi.fn(), open: true });
-    expect(screen.getByText("中文")).toBeInTheDocument();
-    expect(screen.getByTestId("settings-account-link")).toBeInTheDocument();
-    // ... 后续 expect ...
-  });
```

**注意**：用 Edit 工具的 `old_string` 必须是文件**当前**完整字符串（从 Read 拿），不要凭记忆。

- [ ] **Step 3: 跑单文件确认**

```bash
cd c:/doc/Code/rag/packages/web && \
  bunx vitest run components/settings/settings-dialog.test.tsx
```

预期：剩 4 个 test 全部 PASS（"受控: open=true" / "受控: open=false" / "主题 Select 存在" / "语言行可交互"）。

- [ ] **Step 4: Commit**

```bash
cd c:/doc/Code/rag && \
  git add packages/web/components/settings/settings-dialog.test.tsx && \
  git commit -m "test(settings-dialog): 删 T4.3 账号行已删功能的死回归测试

SettingsDialog 2026-06-27 用户主动删除 '账号' 行实现 (确认于 conversation),
但 2 个 '渲染 3 行' / '账号行激活' 测试没同步删, 变成死回归. 删除这 2 个
it 块让测试反映真实行为."
```

---

## Task 3: 诊断 R3 根因（3 fail）

**Files:**
- Read only: `packages/web/app/[locale]/knowledge/documents/page.tsx`
- Read only: `packages/web/app/[locale]/knowledge/graph/page.tsx`
- Read only: `packages/web/app/[locale]/knowledge/_components/knowledge-tabs.tsx`
- Read only: `packages/web/app/[locale]/knowledge/_components/active-switch.tsx`
- Read only: `packages/web/components/knowledge/domain-switcher.tsx`

**失败清单**（来自 `bun run test` 单次输出，不重跑）：
1. `app/[locale]/knowledge/layout.test.tsx > KnowledgeLayout > /knowledge/graph → 渲染 DomainSwitcher`
   错误：`Unable to find an element by: [data-testid="domain-switcher"]`
2. `app/[locale]/knowledge/documents/page.test.tsx > DocumentsPage (RSC) > 渲染 RSC 预取的 stats (dify.datasets/documents)`
   错误：`textContent expected to contain '42'`, 实际 `0`
3. `app/[locale]/knowledge/graph/page.test.tsx > GraphPage (RSC) > 渲染 RSC 预取的 stats (neo4j.nodes/relations)`
   错误：`textContent expected to contain '100'`, 实际 `0`

**假设根因**（基于代码阅读，待验证）：
- Layout 失败：KnowledgeLayout 顶层用 `<ErrorBoundary>` 包裹，jsdom + React 19 可能在 ErrorBoundary fallback 时不渲染 children → DomainSwitcher 不可见
- RSC page 失败：`apiFetch` 在 jsdom 下走 `${host}${path}` 直连（`typeof window !== "undefined"` 但 `window.location` 路径异常），或 fetch mock 时序问题（`beforeEach` 注册太晚，RSC `await import("./page")` 触发的 fetch 不走 mock）

### Steps

- [ ] **Step 1: Read 3 个 page 实现**

读 3 个文件并把**关键代码段**贴回来分析：
- `packages/web/app/[locale]/knowledge/documents/page.tsx`（24 行全文）
- `packages/web/app/[locale]/knowledge/graph/page.tsx`（全文）
- `packages/web/app/[locale]/knowledge/layout.tsx`（24 行全文）

**特别注意**：`graph/page.tsx` 跟 `documents/page.tsx` 是否同模式（prefetch + RSC 渲染 StatCard）

- [ ] **Step 2: 读子组件实现确认数据流**

读：
- `packages/web/app/[locale]/knowledge/documents/_components/documents-entry.tsx`（看 StatCard 怎么消费 `stats`）
- `packages/web/app/[locale]/knowledge/graph/_components/graph-view.tsx` 或类似入口

确认 mock 数据 `{ dify: { datasets: 7, documents: 42 } }` 是否真能流到 StatCard 渲染 "42"。

- [ ] **Step 3: 单文件跑测试 + 拿诊断信息（单次）**

```bash
cd c:/doc/Code/rag/packages/web && \
  bunx vitest run app/\[locale\]/knowledge/documents/page.test.tsx --reporter=verbose 2>&1 | head -100
```

输出**已包含**失败 trace 完整信息（vitest 默认 verbose）。**不要重跑**。

期望诊断：
- 若 RSC `fetch` 真实调到了 `http://127.0.0.1:8000/api/kg/stats`（mock 没拦住）→ 根因：apiFetch 在 jsdom 下走 server 分支，绕开 `globalThis.fetch` mock
- 若 RSC fetch mock 成功拿到数据但 StatCard 渲染 0 → 根因：StatCard 内部又有 useQuery / useEffect 链路拉新数据
- 若 ErrorBoundary 触发 → jsdom 控制台应有 error log（**vitest 不会自动 dump**，但 `bunx vitest run --reporter=verbose` 会显示 stderr）

- [ ] **Step 4: 根据根因选修复方案**

**方案 A：RSC fetch mock 失效** → 修测试：在 `vi.mock("server-only")` 旁边加 `vi.mock("@/lib/api/knowledge", () => ({ fetchStats: vi.fn().mockResolvedValue({...}) }))`，不 mock fetch

**方案 B：StatCard 内部 useQuery 拉新数据** → 读 StatCard 实现, 改测试 mock TanStack Query 返回 RSC 数据

**方案 C：ErrorBoundary fallback** → 测试加 `<ErrorBoundary>` 自己的 mock 或改 KnowledgeLayout 不用 ErrorBoundary（这要业务同意）

每个失败**单独**选方案, 不批量修。

- [ ] **Step 5: 实施修复（按 step 4 方案）**

按选定的方案编辑测试文件 + 必要的 mock 模块。

**⚠️ 不要改 page.tsx / layout.tsx 实现** —— 修测试，不是改业务代码（除非 root cause 确认是业务 bug，需要单独 task）

- [ ] **Step 6: 跑单文件确认**

```bash
cd c:/doc/Code/rag/packages/web && \
  bunx vitest run app/\[locale\]/knowledge/documents/page.test.tsx app/\[locale\]/knowledge/graph/page.test.tsx app/\[locale\]/knowledge/layout.test.tsx
```

预期：3 个文件全 PASS.

- [ ] **Step 7: Commit**

```bash
cd c:/doc/Code/rag && \
  git add packages/web/app/\[locale\]/knowledge/ && \
  git commit -m "test(knowledge): 修 RSC mock 失效 3 个 pre-existing fail

修 3 个文件:
- app/[locale]/knowledge/documents/page.test.tsx
- app/[locale]/knowledge/graph/page.test.tsx
- app/[locale]/knowledge/layout.test.tsx

根因: (此处填 step 4 实际根因)

修法: (此处填实际方案 A/B/C)"
```

---

## Task 4: 全量验证 0 新增 fail

**Files:** 无

### Steps

- [ ] **Step 1: 跑全量测试（单次）**

```bash
cd c:/doc/Code/rag/packages/web && \
  bun run test 2>&1 | tail -20
```

预期：
```
 Test Files  0 failed | N passed (M)
      Tests  0 failed | (719 + 10) = 729 passed (729)
```

- [ ] **Step 2: 跑 lint + typecheck（单次）**

```bash
cd c:/doc/Code/rag/packages/web && \
  bun run lint 2>&1 | tail -5 && \
  bun run typecheck 2>&1 | tail -5
```

预期：lint 0 error 0 warning, typecheck 0 error

- [ ] **Step 3: 更新 CLAUDE.md baseline 段**

**文件**：`packages/web/CLAUDE.md`

找到 "代码质量清理总结 (2026-06-19 code-quality spec)" 段下的 "vitest 起始 vs 结束" 表格，把 14 fail 改为 0 fail（如果 step 1 全过）：

```diff
-| Failed     | 14                   | **0**          | -14 (修了 4 个测试文件) |
+| Failed     | 14                   | **0**          | -14 (修了 7 个测试文件) |
```

并把 "本轮发现 top-12 防再犯守则" 段加 1 条:

```markdown
13. **vitest config 加 `next/navigation` alias**：next 16 + next-intl 4.x 在 vitest jsdom 下 `createNavigation.js` 内部 `import("next/navigation")` ESM 解析失败。在 `vitest.config.ts` 加 `"next/navigation": path.resolve(__dirname, "node_modules/next/navigation.js")` 解决。
```

- [ ] **Step 4: 验证 git 状态**

```bash
cd c:/doc/Code/rag && \
  git status --short
```

预期：3 个 commit 已经在 master/分支上, working tree clean (除了 untracked `docs/audit/`, `docs/superpowers/plans/` 这些 2026-06-27 motion 相关 doc)。

- [ ] **Step 5: 汇报结果**

回用户：
- "10 fail → 0 fail"
- 列 3 个 commit hash + 标题
- 标注"下次 vitest 跑前可看本 plan 复用 Task 1 的 alias 修复"

---

## Self-Review

**1. Spec coverage**:
- ✅ 10 pre-existing test fail → 0 fail（已覆盖）
- ✅ R1 (5), R2 (2), R3 (3) 三类根因分别处理
- ⚠️ Task 3 是**诊断任务**，不是"已知修复"任务 — 实施时如果 root cause 跟假设不一致，agent 必须灵活调整

**2. Placeholder scan**:
- "TBD" / "TODO" / "implement later" — 0 个
- "add appropriate error handling" — 0 个
- "Similar to Task N" — 0 个
- Task 3 step 4-5 有"按 step 4 实际根因填"的占位，**这是必要的**（诊断任务在诊断前不能写死方案）

**3. Type consistency**:
- Task 1 修 `vitest.config.ts` 改 `resolve.alias` 字段，跟现 config 文件结构一致
- Task 2 用 Edit 工具，old_string 必须 Read 后再写（避免 stale 字符串）
- Task 3 强调 "**不要改业务代码**"，防止 agent 误改 page.tsx

**潜在风险**：
- R1 alias 修法依赖 next 16 的 `navigation.js` 文件路径。如果 next 17 改成别的文件名，需要 task 1 step 1 先验证 `require.resolve('next/navigation')` 输出
- R3 诊断如果根因是业务 bug（不是测试问题），plan 不覆盖 — 需要回用户确认是否开新 task
