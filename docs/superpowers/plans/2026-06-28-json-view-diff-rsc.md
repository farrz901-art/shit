# JSON 高亮 + Diff 高亮 RSC 组件 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 两个 RSC 组件 (`JsonView` + `JsonDiff`), shiki 高亮单 JSON, diffLines 行级 diff 双 JSON, 服务端渲染零 JS 开销. ~412 行新代码, 3 测试文件, 投入功能域下一用即可.

**Architecture:** `shiki` `codeToHtml` → JsonView (单个 JSON 高亮, `dangerouslySetInnerHTML` 渲染 shiki 产出 HTML); `diffLines` + `codeToTokens` → JsonDiff (行级 diff, `<table>` + 红绿背景 + +/- gutter). 全 RSC (async), 客户端 0 JS 运行时. `theme` prop 显式指定 (默认 `github-dark`).

**Tech Stack:** shiki v3 + diff + TypeScript 8 + React 19 (RSC) + vitest + @testing-library/react + oxlint + oxfmt

**Spec:** [docs/superpowers/specs/2026-06-28-json-view-diff-rsc-design.md](../specs/2026-06-28-json-view-diff-rsc-design.md)

**项目铁律:** format → lint → typecheck → test → commit ([CLAUDE.md](../../CLAUDE.md))

---

## File Structure (锁定)

| 操作 | 路径 | 责任 |
|---|---|---|
| **Modify** | [packages/web/package.json](../../packages/web/package.json) | 加 `shiki` + `diff` 依赖 |
| **Create** | [packages/web/components/json/types.ts](../../packages/web/components/json/types.ts) | `ShikiTheme` union 类型 |
| **Create** | [packages/web/components/json/utils.ts](../../packages/web/components/json/utils.ts) | `safeStringify` / `resolveCssDimension` |
| **Create** | [packages/web/components/json/utils.test.ts](../../packages/web/components/json/utils.test.ts) | 工具函数单元测试 |
| **Create** | [packages/web/components/json/diff-row.tsx](../../packages/web/components/json/diff-row.tsx) | DiffRow 纯函数渲染组件 |
| **Create** | [packages/web/components/json/json-view.tsx](../../packages/web/components/json/json-view.tsx) | JsonView RSC async 组件 |
| **Create** | [packages/web/components/json/json-view.test.tsx](../../packages/web/components/json/json-view.test.tsx) | JsonView 测试 |
| **Create** | [packages/web/components/json/json-diff.tsx](../../packages/web/components/json/json-diff.tsx) | JsonDiff RSC async 组件 |
| **Create** | [packages/web/components/json/json-diff.test.tsx](../../packages/web/components/json/json-diff.test.tsx) | JsonDiff 测试 |
| **Create** | [packages/web/components/json/index.ts](../../packages/web/components/json/index.ts) | 重导出 `{ JsonView, JsonDiff }` |

**后端 / i18n / const: 0 改动**

---

## Task 1: 装依赖

**Files:**
- Modify: [packages/web/package.json](../../packages/web/package.json) (bun add 自动改)

- [ ] **Step 1: 安装 shiki + diff**

```bash
cd packages/web
bun add shiki diff
```

- [ ] **Step 2: 确认依赖已注册**

```bash
cd packages/web
bun pm ls shiki diff
```

Expected: shiki 3.x, diff 7.x

- [ ] **Step 3: commit**

```bash
git add packages/web/package.json packages/web/bun.lock
git commit -m "chore(deps): add shiki diff for json view/diff components"
```

---

## Task 2: 工具函数 — types + utils (TDD)

**Files:**
- Create: [packages/web/components/json/types.ts](../../packages/web/components/json/types.ts)
- Create: [packages/web/components/json/utils.ts](../../packages/web/components/json/utils.ts)
- Create: [packages/web/components/json/utils.test.ts](../../packages/web/components/json/utils.test.ts)

**测试覆盖:**
- `safeStringify` — 正常 object / null / undefined / 循环引用 (catch 返回 null)
- `resolveCssDimension` — 数字 `100` → `"100px"` / 字符串 `"500px"` → `"500px"` / 边界 0 / 负数

- [ ] **Step 1 (红): 写 utils.test.ts**

先写测试断言, 含 4+ case (正常、null、undefined、循环引用、数字、字符串、边界). 跑 `bun run test -- utils.test` → 预期 3 fail (safeStringify ×2 + resolveCssDimension ×1)

- [ ] **Step 2 (绿): 写 types.ts + utils.ts**

```typescript
// types.ts
export type ShikiTheme = "github-dark" | "github-light";
```

```typescript
// utils.ts
export const safeStringify = (data: unknown): string | null => { ... };
export const resolveCssDimension = (v: string | number): string => { ... };
```

跑测试 → 全绿

- [ ] **Step 3: commit**

```bash
git add packages/web/components/json/types.ts packages/web/components/json/utils.ts packages/web/components/json/utils.test.ts
git commit -m "feat(json): add json utils (safeStringify, resolveCssDimension)"
```

---

## Task 3: JsonView 组件 (TDD)

**Files:**
- Create: [packages/web/components/json/json-view.tsx](../../packages/web/components/json/json-view.tsx)
- Create: [packages/web/components/json/json-view.test.tsx](../../packages/web/components/json/json-view.test.tsx)

**测试覆盖:**
- `data=null` → 渲染占位符 `"—"` (不调 shiki)
- `data=undefined` → 渲染占位符 `"—"`
- `data=有效 object` → 调 `codeToHtml` 1 次, 包含 `<pre>` 容器
- `data=循环引用` → 渲染错误提示 `"JSON 序列化失败"`
- `maxHeight` 数字 → 容器 style 含 `max-height: 500px`
- `theme="github-light"` → 传给 `codeToHtml`

- [ ] **Step 1 (红): 写 json-view.test.tsx**

```typescript
vi.mock("shiki", async (importOriginal) => ({
  ...(await importOriginal<typeof import("shiki")>()),
  codeToHtml: vi.fn().mockResolvedValue('<pre><code><span style="color:#fff">{"a":1}</span></code></pre>'),
}));
```

跑测试 → 红 (组件不存在)

- [ ] **Step 2 (绿): 写 json-view.tsx**

RSC async component:
- 空/undefined → 占位 div
- try JSON.stringify → catch 显示失败
- `codeToHtml(jsonStr, { lang: "json", theme })` → HTML
- 外层 div `overflow-auto rounded-lg border font-mono text-sm`
- `[&_pre]:m-0 [&_pre]:p-4` 垫 shiki 默认 `<pre>` 内外边距

跑测试 → 绿

- [ ] **Step 3: commit**

```bash
git add packages/web/components/json/json-view.tsx packages/web/components/json/json-view.test.tsx
git commit -m "feat(json): add JsonView RSC component with shiki highlighting"
```

---

## Task 4: JsonDiff 组件 (TDD)

**Files:**
- Create: [packages/web/components/json/diff-row.tsx](../../packages/web/components/json/diff-row.tsx)
- Create: [packages/web/components/json/json-diff.tsx](../../packages/web/components/json/json-diff.tsx)
- Create: [packages/web/components/json/json-diff.test.tsx](../../packages/web/components/json/json-diff.test.tsx)

**测试覆盖:**
- `oldData=null & newData=null` → 占位符
- `oldStr === newStr` → "无差异" 提示
- 有效不同 JSON → diffLines 被调 1 次, table 渲染 ≥2 行, gutter 含 +/- 字符
- 主题传递 → `codeToTokens` 收到正确 theme
- `maxHeight` → 容器 style 正确

- [ ] **Step 1 (红): 写 json-diff.test.tsx**

mock:
```typescript
vi.mock("shiki", async (importOriginal) => ({
  ...(await importOriginal<typeof import("shiki")>()),
  codeToTokens: vi.fn().mockResolvedValue({
    tokens: [[{ content: '{"a": 1}', color: "#fff" }]],
  }),
}));

vi.mock("diff", () => ({
  diffLines: vi.fn(() => [
    { value: '{"a": 1}\n', removed: true, count: 1 },
    { value: '{"a": 2}\n', added: true, count: 1 },
    { value: '{"b": 3}\n', count: 1 },
  ]),
}));
```

跑测试 → 红

- [ ] **Step 2 (绿): 写 diff-row.tsx**

纯函数组件:
- `line.type` → 背景色 (add/remove/none)
- `line.type` → gutter 字符 (+ / - / 空格) + 颜色
- token 有内容 → 渲染 `<span style={{color}}>`; 空 → `&nbsp;` 占位

- [ ] **Step 3 (绿): 写 json-diff.tsx**

RSC async component:
- 空兜底 (同 JsonView 逻辑)
- `safeStringify` 双份 → 任一为空则失败提示
- 完全相同 → "无差异" 占位
- `diffLines(oldStr, newStr)` → 逐段 tokenize → 构建 lines 数组
- `<table>` + `<tbody>` + 每行 `<tr>` 引用 `<DiffRow>`
- 外层 div 同 JsonView 容器样式

跑测试 → 绿

- [ ] **Step 4: 写 index.ts**

```typescript
export { JsonView } from "./json-view";
export { JsonDiff } from "./json-diff";
export type { ShikiTheme } from "./types";
```

- [ ] **Step 5: commit**

```bash
git add packages/web/components/json/
git commit -m "feat(json): add JsonDiff RSC component with line-level diff highlighting"
```

---

## Task 5: 验收

- [ ] **Step 1: format**

```bash
cd packages/web
bun run format
# expected: 0 files reformatted 或仅新增文件被格式
```

- [ ] **Step 2: lint fix**

```bash
cd packages/web
bun run lint:fix
# expected: oxlint 0 warnings 剩余
```

- [ ] **Step 3: typecheck**

```bash
cd packages/web
bun run typecheck
# expected: 0 errors
```

- [ ] **Step 4: 跑 json 组件测试**

```bash
cd packages/web
bun run test -- json
# expected: 3 test files, 0 fail
```

- [ ] **Step 5: 全量测试**

```bash
cd packages/web
bun run test
# expected: 0 新 fail (pre-existing fail 不变)
```

- [ ] **Step 6: 最终 commit**

如果上面各 step 的 commit 已经独立完成, 这一步只是确认状态。否则 squash 成一个 commit:

```bash
git add -A
git commit -m "feat(json): add JsonView and JsonDiff RSC components with shiki

- JsonView: single JSON syntax highlight via shiki codeToHtml
- JsonDiff: two-JSON line-level diff via diffLines + shiki codeToTokens
- Both RSC async, zero client JS runtime
- Full test coverage for empty/identical/error/diff states"
```

- [ ] **Step 7: 验收检查**

```bash
# 组件存在
ls packages/web/components/json/json-view.tsx packages/web/components/json/json-diff.tsx

# 测试覆盖
grep -c "describe(" packages/web/components/json/json-view.test.tsx  # ≥3
grep -c "describe(" packages/web/components/json/json-diff.test.tsx  # ≥3

# 后端/i18n/const 0 改动
git diff packages/service/ | wc -l   # 0
git diff messages/ | wc -l          # 0
git diff const/ | wc -l             # 0
```

---

## 风险 & 应对

| 风险 | 应对 |
|---|---|
| `shiki` `codeToHtml` 在 Next.js RSC 环境因模块加载方式报错 | Task 1 后立即在任意 page.tsx 写 `await codeToHtml("test", {lang:"json",theme:"github-dark"})` 验证, 失败则换 `react-syntax-highlighter` 降级方案 |
| `diff` 库 `diffLines` 类型不兼容 TypeScript 8 类型定义 | 用 `@types/diff` 或手动类型声明 |
| vitest mock shiki 后 `importOriginal` 模式在 jsdom 下失败 | 改用 `vi.mock("shiki", () => ({ codeToHtml: vi.fn() }))` 全 mock 模式 (尽管会缺其他导出, 但本组件只用这 2 个 API) |
| `codeToTokens` 在 shiki 3.x 返回结构跟预期不符 | 实施前在独立 .ts 文件 `await codeToTokens(...)` 打印类型验证 |
| RSC 组件在 vitest/jsdom 中不能直接 render | 测试只测 mock 后的逻辑层, 不测实际 RSC 渲染管道 (shiki mock 返回预设 HTML, 断言 HTML 片段包含关系即可) |
