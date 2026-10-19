# 2026-07-05-web-jsdoc-coverage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 给 `packages/web/` 下所有生产 TS/TSX 文件补 JSDoc + 调用边界注释,让 909 个 export 全部有规范文档,沉淀规约进 `packages/web/CLAUDE.md`。

**Architecture:**
- 标准:每个 export 函数/接口/常量补 `/** 中文单行 + @param/@returns + 调用边界 */`
- 调用边界 3 选 1:`@server-only` (RSC/Server Action/route.ts) / `@client-bff` (前端调 BFF) / `@shared` (纯函数)
- 文件头: 缺 header 时补 `// 文件名 — 中文意图 // (日期) refactor 上下文`
- 执行: 12 个 batch 按目录切,每 batch 一个 subagent,顺序跑避免文件冲突
- 验证: 每批 `bun run format && lint && typecheck` 全绿, 12 批后跑全量 `bun run test`

**Tech Stack:**
- bun (runtime + 包管理)
- oxfmt (formatter)
- oxlint (linter, 0.53.0)
- tsc --noEmit (typecheck, typescript 6)
- vitest (unit tests, jsdom)
- ts-morph (新增 scanner 脚本的 AST 解析)

---

## File Structure

**新增文件 (1 个):**
- `packages/web/scripts/check-jsdoc-coverage.ts` — AST 扫描脚本,注册为 `bun run check:jsdoc`

**修改文件 (2 类):**
- `packages/web/CLAUDE.md` — 加 `## JSDoc 注释规约` 章节 (~30 行)
- `packages/web/{app,components,lib}/**/*.ts(x)` — 252 个文件加 JSDoc 块

**新建临时目录:**
- `packages/web/.jsdoc-coverage/` — scanner 输出报告 (`report.txt`, gitignored)

---

## 豁免清单 (不要补)

| 模式 | 例子 | 处理 |
|---|---|---|
| `*.test.ts` / `*.test.tsx` | `lib/hooks/use-confirm.test.ts` | 跳过 |
| `*.stories.tsx` | `components/common/button/button.stories.tsx` | 跳过 |
| `components/ui/*` | `components/ui/button.tsx` | 跳过 (shadcn 自动生成) |
| barrel export `index.ts` 仅一行 `export { x } from "./x"` | `lib/api/index.ts` | 跳过 (无新文档需求) |
| anonymous arrow (非 `export const = ...`) | `(x: number) => x + 1` | 跳过 |
| 类型守卫 `function isFoo(x): x is Foo` | 内部谓词 | 跳过 |
| 简单 setter/getter | `get foo() { return this._foo }` | 跳过 |

---

## 注释模板

### 模板 A: 简单函数 (单行 + @param)

参考 [lib/hooks/use-polling.ts:5-9](packages/web/lib/hooks/use-polling.ts#L5-L9)

```ts
/**
 * 中文单行动词开头 (做什么)
 * @param paramName  参数说明
 * @returns          返回值说明 (无返回时省)
 */
export const foo = (paramName: string) => { ... };
```

### 模板 B: 调用边界 (BFF client / Server-only)

参考 [lib/api/permissions.ts:1-15](packages/web/lib/api/permissions.ts#L1-L15)

```ts
/**
 * 函数中文单行描述
 * @param headers 服务端 auth headers (从 cookies 解出)
 * @returns      返回值说明
 *
 * 调用边界 (calling-boundary):
 *   - @server-only   RSC / Server Action / route.ts 专用
 *   - @client-bff    前端组件可用 (调 /api/* BFF)
 *   - @shared        前后端通用
 */
```

### 模板 C: 文件头 (缺 header 时)

参考 [app/[locale]/account/restore/restore-form.tsx:2-5](packages/web/app/[locale]/account/restore/restore-form.tsx#L2-L5)

```ts
// 文件名 — 一句话中文意图
// (YYYY-MM-DD) refactor 上下文 (为什么改 / 修了什么 bug)
import ...
```

---

## 执行前必读 (per subagent)

每个 subagent 进入工作前必读:
- **不动的**: import 顺序,现有逻辑,export 签名,文件名
- **加的**: 仅 `/** */` 块 + 可选 `//` 文件头
- **不删**: 任何现有注释 (项目铁律: 改代码保留原注释, 除非明确要求删)
- **不 commit**: 留 working tree, orchestrator 统一按 batch commit

---

## Task 1: 基线检查 (确认项目当前干净)

**Files:**
- Read-only: 无

- [ ] **Step 1.1: 看 git 状态确认无他人工作残留**

Run:
```bash
cd c:/doc/Code/rag && git stash list && git status --short
```
Expected: `git stash list` 输出为空或仅有自己之前的 stash; `git status --short` 输出干净或仅有未跟踪文件。

如果有他人 stash → **STOP**, 不要 reset/checkout (项目 CLAUDE.md §覆盖别人 worktree 残留警告)。

- [ ] **Step 1.2: 跑 format + lint + typecheck 看基线**

Run:
```bash
cd c:/doc/Code/rag/packages/web && bun run format && bun run lint && bun run typecheck
```
Expected: 三步均 0 错。如果任一步红, 把 baseline 写下来, 后续 task 出错就对照 baseline (不一定是本次改动导致的)。

- [ ] **Step 1.3: 跑全量测试看基线 (耗时 1+ 分钟, 只跑 1 次)**

Run:
```bash
cd c:/doc/Code/rag/packages/web && bun run test 2>&1 | tail -30
```
Expected: 719 passed (或当前 baseline 数), 0 新 fail。记录到日志 `packages/web/.jsdoc-coverage/baseline-test.txt`。

如果已有 fail (项目有 8 pre-existing fail 2026-06-27 deferred), 记录数, 后续 task 不能引入新 fail。

- [ ] **Step 1.4: 创建 .gitignore 临时目录**

Run:
```bash
cd c:/doc/Code/rag/packages/web && mkdir -p .jsdoc-coverage && echo ".jsdoc-coverage/" >> .git/info/exclude
```
Expected: `.jsdoc-coverage/` 被本地 git 排除, 不进 commit。

---

## Task 2: 写 JSDoc scanner 脚本 (前置工具)

**Files:**
- Create: `packages/web/scripts/check-jsdoc-coverage.ts`

**Why 先做这个**: 后续 12 个 batch 都用它验证覆盖率, 没它就没客观依据。

- [ ] **Step 2.1: 写 scanner 脚本 (TypeScript, 跑 bun 直接执行)**

文件: `packages/web/scripts/check-jsdoc-coverage.ts`

完整代码:

```ts
/**
 * JSDoc 覆盖率扫描器
 *
 * 扫 packages/web/{app,components,lib} 下所有 .ts/.tsx 文件,
 * 检查每个 export 是否上方有 /** */ 块.
 *
 * 豁免: *.test.*, *.stories.*, components/ui/*, barrel re-export
 *
 * 用法:
 *   bun run scripts/check-jsdoc-coverage.ts                  # 报告并 exit 1 若有缺失
 *   bun run scripts/check-jsdoc-coverage.ts --report-only    # 仅报告, exit 0
 */
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, relative, sep } from "node:path";

const ROOT = join(import.meta.dir, "..");
const SCAN_DIRS = ["app", "components", "lib"] as const;
const EXEMPT_PATTERNS = [
  /\.test\.[jt]sx?$/,
  /\.stories\.[jt]sx?$/,
  /[\\/]components[\\/]ui[\\/]/,
];

interface MissingEntry {
  file: string;
  line: number;
  export: string;
}

const EXPORT_RE = /^export\s+(?:async\s+)?(?:function|const|default\s+function|interface|type|class)\s+([A-Za-z_$][\w$]*)/;

const isExempt = (relPath: string) => EXEMPT_PATTERNS.some((re) => re.test(relPath));

const walk = (dir: string, files: string[] = []) => {
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry);
    const stat = statSync(full);
    if (stat.isDirectory()) walk(full, files);
    else if (/\.[jt]sx?$/.test(entry) && !entry.endsWith(".d.ts")) files.push(full);
  }
  return files;
};

const hasJsdocAbove = (lines: string[], lineIdx: number): boolean => {
  // 往上找最近的 /** */ 块 (允许中间有空行, 但不能有 export/const/function 声明)
  for (let idx = lineIdx - 1; idx >= 0; idx--) {
    const trimmed = lines[idx].trim();
    if (trimmed.startsWith("*/")) {
      // 找到块结束, 再往上找 /** 起点
      for (let back = idx; back >= 0; back--) {
        if (lines[back].trim().startsWith("/**")) return true;
        if (lines[back].trim() && !lines[back].trim().startsWith("*")) break;
      }
      return false;
    }
    if (trimmed && !trimmed.startsWith("//") && !trimmed.startsWith("*") && !trimmed.startsWith("/*")) {
      return false;
    }
  }
  return false;
};

const isReExportOnly = (content: string): boolean => {
  // 整个文件全是 `export { ... } from ...` 或 `export * from ...`
  const exports = content.match(/^export\s+.+$/gm) ?? [];
  if (exports.length === 0) return false;
  return exports.every((line) => /from\s+["']/.test(line));
};

const main = () => {
  const reportOnly = process.argv.includes("--report-only");
  const allFiles = SCAN_DIRS.flatMap((dir) => walk(join(ROOT, dir)));
  const missing: MissingEntry[] = [];
  let totalExports = 0;
  let exemptCount = 0;

  for (const file of allFiles) {
    const rel = relative(ROOT, file);
    if (isExempt(rel)) {
      exemptCount++;
      continue;
    }
    const content = readFileSync(file, "utf-8");
    if (isReExportOnly(content)) {
      exemptCount++;
      continue;
    }
    const lines = content.split("\n");
    for (let idx = 0; idx < lines.length; idx++) {
      const match = lines[idx].match(EXPORT_RE);
      if (!match) continue;
      totalExports++;
      if (!hasJsdocAbove(lines, idx)) {
        missing.push({ file: rel, line: idx + 1, export: match[1] ?? "?" });
      }
    }
  }

  const covered = totalExports - missing.length;
  const pct = totalExports ? ((covered / totalExports) * 100).toFixed(1) : "100.0";

  console.log(`\n=== JSDoc Coverage Report ===`);
  console.log(`Total exports:   ${totalExports}`);
  console.log(`Covered:         ${covered} (${pct}%)`);
  console.log(`Missing:         ${missing.length}`);
  console.log(`Exempt files:    ${exemptCount}\n`);

  if (missing.length) {
    console.log(`First 50 missing entries:`);
    for (const entry of missing.slice(0, 50)) {
      console.log(`  [MISSING] ${entry.file}:${entry.line} (export ${entry.export})`);
    }
    if (missing.length > 50) console.log(`  ... and ${missing.length - 50} more`);
  }

  if (!reportOnly && missing.length > 0) {
    process.exit(1);
  }
};

main();
```

- [ ] **Step 2.2: 注册 scanner 到 package.json scripts**

**Files:**
- Modify: `packages/web/package.json`

在 `"scripts"` 段加一行:

```json
"check:jsdoc": "bun run scripts/check-jsdoc-coverage.ts",
"check:jsdoc:report": "bun run scripts/check-jsdoc-coverage.ts --report-only"
```

- [ ] **Step 2.3: 跑 scanner 看 baseline**

Run:
```bash
cd c:/doc/Code/rag/packages/web && bun run check:jsdoc:report 2>&1 | tee .jsdoc-coverage/baseline-jsdoc.txt
```
Expected: 输出 baseline 报告 (约 909 个 export, 多数 missing)。记录到 `.jsdoc-coverage/baseline-jsdoc.txt`。

- [ ] **Step 2.4: Commit scanner**

Run:
```bash
cd c:/doc/Code/rag && git add packages/web/scripts/check-jsdoc-coverage.ts packages/web/package.json && git commit -m "feat(web): add JSDoc coverage scanner script"
```

---

## Task 3: B1 — 补 `lib/api/*` (30 文件, 已有 calling-boundary 范例)

**Files:**
- Modify: `packages/web/lib/api/*.ts` (约 30 个, 排除 `*.test.ts`)

**Why 先做这个**: 这目录已有标准 calling-boundary 范例,补起来最一致,做模板供后续 batch 参考。

**参考范例**:
- [lib/api/permissions.ts:1-15](packages/web/lib/api/permissions.ts#L1-L15)
- [lib/api/auth.ts](packages/web/lib/api/auth.ts)

- [ ] **Step 3.1: 用 Explore 列出本 batch 的目标文件清单**

```bash
cd c:/doc/Code/rag/packages/web && ls lib/api/*.ts | grep -v test
```

记录 30 个文件名到 `.jsdoc-coverage/b1-files.txt`。

- [ ] **Step 3.2: 派 subagent 处理 (用 superpowers:subagent-driven-development)**

派一个 subagent (worktree 模式 `isolation: "worktree"`), prompt:

```
角色: 给 packages/web/lib/api/*.ts 下 30 个生产文件补 JSDoc + 可选文件头.

豁免: *.test.*, *.stories.*, 纯 barrel re-export
参考:
  - lib/api/permissions.ts (calling-boundary 段落)
  - lib/api/auth.ts (单行 + @param/@returns)
  - lib/hooks/use-polling.ts (简洁风格)

标准:
  - 每个 export 函数/接口/常量顶头加 /** 中文单行 + @param/@returns + 调用边界 (@server-only / @client-bff / @shared) */
  - 缺文件头时加 1-2 行 // 中文 + (YYYY-MM-DD) refactor 上下文
  - 不动 import 顺序, 不动现有逻辑, 不改文件名, 不改 export 签名

验证:
  1. cd packages/web
  2. bun run format && bun run lint && bun run typecheck 必须全 0
  3. bun run test -- lib/api 必须 0 新 fail
  4. 不允许 commit, 改动留 working tree

输出: 改了 N 个文件, 跳过了 N 个文件 (及原因), 任何意外情况.
```

- [ ] **Step 3.3: Orchestrator 复核 — 跑 scanner 看覆盖率**

Run:
```bash
cd c:/doc/Code/rag/packages/web && bun run check:jsdoc:report 2>&1 | tee .jsdoc-coverage/b1-jsdoc.txt
```
Expected: B1 的 missing 数明显下降. 如果 lib/api 还有 missing → STOP, 让 subagent 补完再继续.

- [ ] **Step 3.4: 跑测试**

Run:
```bash
cd c:/doc/Code/rag/packages/web && bun run test -- lib/api 2>&1 | tail -20
```
Expected: 0 新 fail (跟 baseline 对比).

- [ ] **Step 3.5: Commit B1**

Run:
```bash
cd c:/doc/Code/rag && git add packages/web/lib/api/ && git commit -m "docs(web): 补 JSDoc — B1 lib/api/* (calling-boundary)"
```

---

## Task 4: B2 — 补 `lib/chat/*` (20 文件, 复杂度高)

**Files:**
- Modify: `packages/web/lib/chat/*.ts` (排除 test)

**Why 这个 batch**: chat-event-decoder / openai / dify 等核心 transport, 调用边界多, JSDoc 价值高。

- [ ] **Step 4.1: 列文件**

```bash
cd c:/doc/Code/rag/packages/web && ls lib/chat/*.ts | grep -v test
```

记录到 `.jsdoc-coverage/b2-files.txt`。

- [ ] **Step 4.2: 派 subagent (isolation: worktree), prompt 同 B3, 路径改 lib/chat/*.ts**

- [ ] **Step 4.3: 跑 scanner + test**

```bash
cd c:/doc/Code/rag/packages/web && bun run check:jsdoc:report 2>&1 | tee .jsdoc-coverage/b2-jsdoc.txt
cd c:/doc/Code/rag/packages/web && bun run test -- lib/chat 2>&1 | tail -20
```

- [ ] **Step 4.4: Commit B2**

```bash
cd c:/doc/Code/rag && git add packages/web/lib/chat/ && git commit -m "docs(web): 补 JSDoc — B2 lib/chat/* (transport/decoder)"
```

---

## Task 5: B3 — 补 `lib/hooks/*` + `lib/store/*` + `lib/auth/*` + `lib/parse/*` (22 文件)

**Files:**
- Modify: `packages/web/lib/{hooks,store,auth,parse}/*.ts` (排除 test)

- [ ] **Step 5.1: 列文件**

```bash
cd c:/doc/Code/rag/packages/web && ls lib/hooks/*.ts lib/store/*.ts lib/auth/*.ts lib/parse/*.ts | grep -v test
```

- [ ] **Step 5.2: 派 subagent, prompt 同 B3, 路径改 `lib/{hooks,store,auth,parse}/*.ts`**

- [ ] **Step 5.3: 跑 scanner + test**

```bash
cd c:/doc/Code/rag/packages/web && bun run check:jsdoc:report 2>&1 | tee .jsdoc-coverage/b3-jsdoc.txt
cd c:/doc/Code/rag/packages/web && bun run test -- lib/hooks lib/store lib/auth lib/parse 2>&1 | tail -20
```

- [ ] **Step 5.4: Commit B3**

```bash
cd c:/doc/Code/rag && git add packages/web/lib/hooks/ packages/web/lib/store/ packages/web/lib/auth/ packages/web/lib/parse/ && git commit -m "docs(web): 补 JSDoc — B3 lib/{hooks,store,auth,parse}/*"
```

---

## Task 6: B4 — 补剩余 `lib/*` (12 文件)

**Files:**
- Modify:
  - `packages/web/lib/server/*.ts`
  - `packages/web/lib/nav/*.ts`
  - `packages/web/lib/dom/*.ts`
  - `packages/web/lib/evaluate/*.ts`
  - `packages/web/lib/theme/*.ts`
  - `packages/web/lib/rate-limiter.ts`
  - `packages/web/lib/schema-types.ts`

- [ ] **Step 6.1: 列文件**

```bash
cd c:/doc/Code/rag/packages/web && ls lib/server lib/nav lib/dom lib/evaluate lib/theme 2>&1
```

- [ ] **Step 6.2: 派 subagent, prompt 同 B3, 路径改上述目录 + 2 个单文件**

- [ ] **Step 6.3: 跑 scanner + test**

```bash
cd c:/doc/Code/rag/packages/web && bun run check:jsdoc:report 2>&1 | tee .jsdoc-coverage/b4-jsdoc.txt
cd c:/doc/Code/rag/packages/web && bun run test -- lib 2>&1 | tail -20
```

- [ ] **Step 6.4: Commit B4**

```bash
cd c:/doc/Code/rag && git add packages/web/lib/ && git commit -m "docs(web): 补 JSDoc — B4 lib/server|nav|dom|evaluate|theme + rate-limiter + schema-types"
```

---

## Task 7: B5 — 补 `components/common/*` (60 文件, 复杂度中)

**Files:**
- Modify: `packages/web/components/common/**/*.tsx` (排除 test/stories/ui)

**为什么分到独立 batch**: 这目录最大, 单独做便于监控进度。

- [ ] **Step 7.1: 列文件**

```bash
cd c:/doc/Code/rag/packages/web && find components/common -type f -name "*.tsx" -not -name "*.test.tsx" -not -name "*.stories.tsx" | sort
```

记录到 `.jsdoc-coverage/b5-files.txt`。

- [ ] **Step 7.2: 派 subagent (worktree), prompt:**

```
角色: 给 packages/web/components/common/**/*.tsx 下约 60 个生产组件文件补 JSDoc.
豁免: *.test.*, *.stories.*, components/ui/*
参考:
  - lib/hooks/use-confirm.ts (interface + 函数 JSDoc)
  - 任何现有 components/common/* 已加 JSDoc 的文件

标准:
  - 每个 export const Component / interface 顶头加 /** 中文 + @param (props) + 调用边界 */
  - 默认 export 的 React 组件: 用 default export 风格 (/** 组件描述 + 调用边界 */)
  - 简单 app-* wrapper 组件 (如 AppButton) 一行 /** 描述 */ 即可
  - 不动 props 类型 (不写 @param {type}), 只写描述

验证:
  1. cd packages/web
  2. bun run format && bun run lint && bun run typecheck 必须全 0
  3. bun run test -- components/common 必须 0 新 fail
  4. 不允许 commit
```

- [ ] **Step 7.3: 跑 scanner + test**

```bash
cd c:/doc/Code/rag/packages/web && bun run check:jsdoc:report 2>&1 | tee .jsdoc-coverage/b5-jsdoc.txt
cd c:/doc/Code/rag/packages/web && bun run test -- components/common 2>&1 | tail -20
```

- [ ] **Step 7.4: Commit B5**

```bash
cd c:/doc/Code/rag && git add packages/web/components/common/ && git commit -m "docs(web): 补 JSDoc — B5 components/common/* (app-* wrappers)"
```

---

## Task 8: B6 — 补 `components/{auth,decode,evaluate,json,knowledge,layout,markdown,motion,settings,i18n}/*` (50 文件)

**Files:**
- Modify: 上述 10 个 components 子目录的 `*.tsx` (排除 test/stories)

- [ ] **Step 8.1: 列文件**

```bash
cd c:/doc/Code/rag/packages/web && ls components/{auth,decode,evaluate,json,knowledge,layout,markdown,motion,settings,i18n}/*.tsx 2>/dev/null | grep -vE "test|stories"
```

- [ ] **Step 8.2: 派 subagent, prompt 同 B5, 路径改上述 10 个目录**

- [ ] **Step 8.3: 跑 scanner + test**

```bash
cd c:/doc/Code/rag/packages/web && bun run check:jsdoc:report 2>&1 | tee .jsdoc-coverage/b6-jsdoc.txt
cd c:/doc/Code/rag/packages/web && bun run test -- components/auth components/decode components/evaluate components/json components/knowledge components/layout components/markdown components/motion components/settings components/i18n 2>&1 | tail -20
```

- [ ] **Step 8.4: Commit B6**

```bash
cd c:/doc/Code/rag && git add packages/web/components/auth packages/web/components/decode packages/web/components/evaluate packages/web/components/json packages/web/components/knowledge packages/web/components/layout packages/web/components/markdown packages/web/components/motion packages/web/components/settings packages/web/components/i18n && git commit -m "docs(web): 补 JSDoc — B6 components/{auth,decode,evaluate,json,knowledge,layout,markdown,motion,settings,i18n}"
```

---

## Task 9: B7 — 补 `components/chat/*` (38 文件, 复杂度高)

**Files:**
- Modify: `packages/web/components/chat/*.tsx` (排除 test)

**Why 单独 batch**: chat-shell.tsx 238 行是项目最大单文件, 调用边界面广, 需要专门 attention。

- [ ] **Step 9.1: 列文件**

```bash
cd c:/doc/Code/rag/packages/web && ls components/chat/*.tsx | grep -v test
```

- [ ] **Step 9.2: 派 subagent, prompt:**

```
角色: 给 packages/web/components/chat/*.tsx 下 38 个组件文件补 JSDoc.
豁免: *.test.*, *.stories.*
参考: 现有 chat/ 已加 JSDoc 的文件 (例如 compose.tsx, chat-shell.tsx 头注释)

标准:
  - chat-shell.tsx (238 行): 文件头加 // 中文意图 + (YYYY-MM-DD) refactor 上下文; 每个 export 加 /** 中文 + @param props + 调用边界 */
  - 38 个文件统一调用边界:
    - "use client" 组件: @client-bff
    - 不带 "use client": @shared (RSC/通用)
  - 不动现有 file header 中文注释 (项目铁律: 保留原注释)

验证: 同前 (format + lint + typecheck + test)
```

- [ ] **Step 9.3: 跑 scanner + test**

```bash
cd c:/doc/Code/rag/packages/web && bun run check:jsdoc:report 2>&1 | tee .jsdoc-coverage/b7-jsdoc.txt
cd c:/doc/Code/rag/packages/web && bun run test -- components/chat 2>&1 | tail -20
```

- [ ] **Step 9.4: Commit B7**

```bash
cd c:/doc/Code/rag && git add packages/web/components/chat/ && git commit -m "docs(web): 补 JSDoc — B7 components/chat/* (chat-shell 大组件)"
```

---

## Task 10: B8 — 补 `app/[locale]/**/page.tsx` + `_components` + `_lib` (80 文件)

**Files:**
- Modify: `packages/web/app/[locale]/**/*.tsx` (排除 test)

**Why 单独 batch**: pages 量大, 调用边界容易标错 (RSC vs Client)。

- [ ] **Step 10.1: 列文件**

```bash
cd c:/doc/Code/rag/packages/web && find "app/[locale]" -type f \( -name "*.ts" -o -name "*.tsx" \) -not -name "*.test.*" | sort
```

- [ ] **Step 10.2: 派 subagent, prompt:**

```
角色: 给 packages/web/app/[locale]/** 下 ~80 个生产文件补 JSDoc.
豁免: *.test.*, *.stories.*
参考: 现有 page.tsx 已加 JSDoc 的范例

判断调用边界 (重要):
  - 文件顶有 "use client": @client-bff
  - 无 "use client" + 包含 server-only API (cookies, headers, db): @server-only
  - 无 "use client" + 仅纯渲染/import: @shared
  - _components/ 子目录通常是 client (看 "use client" 判断)
  - _actions/ 子目录总是 @server-only
  - _lib/ 子目录看内容 (可能是 server-only util)

标准:
  - page.tsx (默认 export): /** 页面中文意图 + 调用边界 + i18n namespace (如有) */
  - _components/*.tsx (client 组件): /** 组件中文 + props + @client-bff */
  - _lib/*.ts (util): /** util 中文 + @param + @returns + 调用边界 */

验证: 同前
```

- [ ] **Step 10.3: 跑 scanner + test**

```bash
cd c:/doc/Code/rag/packages/web && bun run check:jsdoc:report 2>&1 | tee .jsdoc-coverage/b8-jsdoc.txt
cd c:/doc/Code/rag/packages/web && bun run test -- "app/[locale]" 2>&1 | tail -20
```

- [ ] **Step 10.4: Commit B8**

```bash
cd c:/doc/Code/rag && git add "packages/web/app/[locale]/" && git commit -m "docs(web): 补 JSDoc — B8 app/[locale]/** (pages + _components + _lib)"
```

---

## Task 11: B9 — 补 `app/[locale]/_actions/*` (7 文件, 必标 @server-only)

**Files:**
- Modify:
  - `packages/web/app/[locale]/_actions/account.ts`
  - `packages/web/app/[locale]/_actions/account-settings.ts`
  - `packages/web/app/[locale]/_actions/evaluate.ts`
  - `packages/web/app/[locale]/_actions/knowledge.ts`
  - `packages/web/app/[locale]/_actions/output.ts`
  - 其他 `_actions/*.ts` 文件

- [ ] **Step 11.1: 列文件**

```bash
cd c:/doc/Code/rag/packages/web && ls "app/[locale]/_actions/"
```

- [ ] **Step 11.2: 派 subagent, prompt:**

```
角色: 给 packages/web/app/[locale]/_actions/*.ts 补 JSDoc.
所有这些文件都是 server actions, 必须标 @server-only.

参考: lib/api/permissions.ts 的 calling-boundary 段落

标准:
  - 每个 server action 函数加 /** 中文 + @param FormData/args + @returns + @throws + @server-only */
  - 文件头加 // 文件名 — server actions 集合 // (YYYY-MM-DD) refactor 上下文

验证: 同前
```

- [ ] **Step 11.3: 跑 scanner + test**

```bash
cd c:/doc/Code/rag/packages/web && bun run check:jsdoc:report 2>&1 | tee .jsdoc-coverage/b9-jsdoc.txt
cd c:/doc/Code/rag/packages/web && bun run test -- "app/[locale]/_actions" 2>&1 | tail -20
```

- [ ] **Step 11.4: Commit B9**

```bash
cd c:/doc/Code/rag && git add "packages/web/app/[locale]/_actions/" && git commit -m "docs(web): 补 JSDoc — B9 app/[locale]/_actions/* (server actions, @server-only)"
```

---

## Task 12: B10 — 补 `app/api/**/route.ts` (23 个 BFF route, 必标 @client-bff)

**Files:**
- Modify: `packages/web/app/api/**/*.ts` (排除 test, 排除 [...path] catch-all)

**Why 单独 batch**: BFF route 是外部契约, JSDoc 是文档源。

- [ ] **Step 12.1: 列文件**

```bash
cd c:/doc/Code/rag/packages/web && find app/api -type f -name "route.ts" | sort
```

- [ ] **Step 12.2: 派 subagent, prompt:**

```
角色: 给 packages/web/app/api/**/route.ts 下约 23 个 BFF route handler 补 JSDoc.
所有 GET/POST/PATCH/DELETE/PUT handler 必须标 @client-bff.

参考: 现有 api/approvals/[id]/approve/route.ts 头部注释风格

标准:
  - 每个 export async function GET/POST/etc 加 /** 中文 + @param Request + @returns Response + @client-bff */
  - 文件头加 // 文件路径 — BFF 路由 // (YYYY-MM-DD) refactor 上下文

验证: 同前
```

- [ ] **Step 12.3: 跑 scanner + test**

```bash
cd c:/doc/Code/rag/packages/web && bun run check:jsdoc:report 2>&1 | tee .jsdoc-coverage/b10-jsdoc.txt
cd c:/doc/Code/rag/packages/web && bun run test -- app/api 2>&1 | tail -20
```

- [ ] **Step 12.4: Commit B10**

```bash
cd c:/doc/Code/rag && git add packages/web/app/api/ && git commit -m "docs(web): 补 JSDoc — B10 app/api/**/route.ts (BFF routes, @client-bff)"
```

---

## Task 13: B11 — 补顶层配置 (8 文件)

**Files:**
- Modify:
  - `packages/web/proxy.ts`
  - `packages/web/const/index.ts`
  - `packages/web/i18n/navigation.ts`
  - `packages/web/i18n/provider.tsx`
  - `packages/web/i18n/request.ts`
  - `packages/web/i18n/routing.ts`
  - `packages/web/app/global-error.tsx`

- [ ] **Step 13.1: 列文件**

```bash
cd c:/doc/Code/rag/packages/web && ls proxy.ts const/index.ts i18n/*.ts* app/global-error.tsx
```

- [ ] **Step 13.2: 派 subagent (inline 即可, 8 文件不大), prompt:**

```
角色: 给上述 8 个顶层配置文件补 JSDoc.
文件性质:
  - proxy.ts: Next.js proxy (项目用 proxy.ts 不用 middleware.ts)
  - const/index.ts: 项目常量集合
  - i18n/*: next-intl 配置
  - app/global-error.tsx: 全局错误页

参考: 现有 i18n/request.ts 等已加 JSDoc 的范例

标准:
  - 每个文件头加 // 文件名 — 一句话中文意图
  - 每个 export 加 /** 中文 + @param + @returns + 调用边界 */
  - const/index.ts 的常量也补 (/** 常量用途 + 取值范围 */)

验证: 同前
```

- [ ] **Step 13.3: 跑 scanner + test**

```bash
cd c:/doc/Code/rag/packages/web && bun run check:jsdoc 2>&1 | tee .jsdoc-coverage/b11-jsdoc.txt
cd c:/doc/Code/rag/packages/web && bun run test -- i18n const proxy 2>&1 | tail -20
```

Expected: scanner `bun run check:jsdoc` (无 `--report-only`) 应当 pass, exit 0.

- [ ] **Step 13.4: Commit B11**

```bash
cd c:/doc/Code/rag && git add packages/web/proxy.ts packages/web/const/ packages/web/i18n/ packages/web/app/global-error.tsx && git commit -m "docs(web): 补 JSDoc — B11 顶层配置 (proxy/const/i18n/global-error)"
```

---

## Task 14: 全量验证 (format + lint + typecheck + test + scanner)

**Files:**
- Read-only: 无 (verify only)

- [ ] **Step 14.1: format + lint + typecheck 全跑**

```bash
cd c:/doc/Code/rag/packages/web && bun run format && bun run lint && bun run typecheck 2>&1 | tail -30
```
Expected: 全 0 错。如果有错 → STOP, 看是哪个 batch 引入的, 让对应 subagent 重做。

- [ ] **Step 14.2: 全量测试 (耗时 1+ 分钟)**

```bash
cd c:/doc/Code/rag/packages/web && bun run test 2>&1 | tail -30
```
Expected: 跟 baseline (Task 1.3) 同样的 pass 数 + 同样的 fail 数 (pre-existing 8 fail 不算新 fail). 不能引入新 fail。

- [ ] **Step 14.3: JSDoc scanner 跑全量验证**

```bash
cd c:/doc/Code/rag/packages/web && bun run check:jsdoc 2>&1 | tee .jsdoc-coverage/final-jsdoc.txt
```
Expected: exit 0, "Covered: 100.0%" 或缺失数 = 0. 如果有 missing → 看是否豁免清单漏了某类, 补豁免。

- [ ] **Step 14.4: 出最终报告**

写 `packages/web/.jsdoc-coverage/final-report.md`:

```md
# JSDoc Coverage Final Report

- Baseline: {N} exports, {M} missing ({P}%)
- Final: {N} exports, 0 missing (100%)
- Batches: 12 (B1-B11, 各 1 commit)
- Pre-existing test fails: 8 (未引入新 fail)
- 新增文件: scripts/check-jsdoc-coverage.ts
- 修改文件: 252 个生产 TS/TSX
- 总 commit 数: 13 (B1-B11 + scanner)

报告生成时间: 2026-07-05
```

---

## Task 15: 写 `packages/web/CLAUDE.md` JSDoc 规约章节

**Files:**
- Modify: `packages/web/CLAUDE.md`

- [ ] **Step 15.1: Read 现有 CLAUDE.md 找好插入位置**

```bash
grep -n "^## " c:/doc/Code/rag/packages/web/CLAUDE.md | tail -20
```

找一个合适的位置 (推荐在 `## 工具链` 段后或 `## TDD 流程` 段后)。

- [ ] **Step 15.2: 在选好位置插入新章节**

完整内容 (插入到合适位置):

````markdown
## JSDoc 注释规约 (2026-07-05 沉淀)

**所有 export 函数 / interface / const 必须有 JSDoc 块** (test/stories/components/ui 豁免).

```ts
/**
 * 中文单行动词开头 (做什么)
 * @param name  参数说明
 * @returns     返回值说明
 *
 * 调用边界 (3 选 1):
 *   - @server-only   RSC / Server Action / route.ts 用
 *   - @client-bff    前端调 BFF 用
 *   - @shared        前后端通用 (纯函数)
 */
export const foo = ...
```

参考实现:
- [lib/hooks/use-polling.ts:5-9](packages/web/lib/hooks/use-polling.ts#L5-L9) — 简洁单行 + @param
- [lib/api/permissions.ts:1-15](packages/web/lib/api/permissions.ts#L1-L15) — calling-boundary 段落
- [lib/hooks/use-confirm.ts](packages/web/lib/hooks/use-confirm.ts) — interface + 函数块

豁免清单: `*.test.*`, `*.stories.*`, `components/ui/*`, 纯 barrel re-export, anonymous arrow, 类型守卫, 简单 setter/getter.

扫描工具: `bun run check:jsdoc` (scanner 在 `scripts/check-jsdoc-coverage.ts`, exit 1 若有缺失).

**Why**: 909 个 export 缺文档,新人 onboarding 慢 + AI 上下文缺失.

**How to apply**: 新加 export 必须有 JSDoc 块, PR review 把这条当 lint 级别校验 (跟 `bun run typecheck` 同等对待).
````

- [ ] **Step 15.3: 跑 lint 看格式**

```bash
cd c:/doc/Code/rag/packages/web && bun run lint
```
Expected: 0 错.

- [ ] **Step 15.4: Commit CLAUDE.md**

```bash
cd c:/doc/Code/rag && git add packages/web/CLAUDE.md && git commit -m "docs(web): 加 JSDoc 注释规约章节 (2026-07-05 沉淀)"
```

---

## Task 16: 推送 + 收尾

- [ ] **Step 16.1: 看 commit log**

```bash
cd c:/doc/Code/rag && git log --oneline -15
```
Expected: 看到 13 个新 commit (B1-B11 + scanner + CLAUDE.md).

- [ ] **Step 16.2: 跑 E2E 烟囱 1 个 (knowledge tab, 1 分钟内)**

```bash
cd c:/doc/Code/rag/packages/web && bun run test:e2e -- --grep "knowledge" 2>&1 | tail -20
```
Expected: pass (E2E 仅做冒烟, 不跑全套).

- [ ] **Step 16.3: 报告最终状态给用户**

输出包含:
- 13 个 commit hash + 标题
- JSDoc 覆盖率: baseline X% → final 100%
- 全量测试: pass 数 + fail 数对比 baseline
- E2E: pass
- 新增文件: scripts/check-jsdoc-coverage.ts
- 修改文件: 252 个生产 TS/TSX + CLAUDE.md

---

## Self-Review Checklist (作者自查)

- [x] **Spec coverage**: 909 个 export → 12 batch 全覆盖,豁免清单明确
- [x] **No placeholders**: 每步有具体命令,具体文件路径,具体 commit message
- [x] **Type consistency**: scanner 函数名 / package.json scripts 名 / batch 名全程一致
- [x] **TDD 顺序**: Task 1 (基线) → Task 2 (scanner) → Task 3-13 (补) → Task 14 (验证) → Task 15 (文档) → Task 16 (收尾)
- [x] **频繁 commit**: 13 个 commit, 每个 batch 一个, 符合项目铁律
- [x] **豁免明确**: Task 顶部表格列出 6 类豁免 + 例子