# vitest jsdom → happy-dom 全局迁移

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 vitest DOM 测试环境从 `jsdom` 换成 `happy-dom`，提升测试启动速度 3–10×。不通过的全部重写适配。

**Architecture:** vitest 4.1.10 已 peer-dep 支持 happy-dom。配置改一行 `vitest.config.ts` + package.json 换 dep + bun.lock 重生成 + 逐个修复 5 个新 fail 文件。pre-existing 8 fail (R1+R3) 选 1 个方案一并修。

**Tech Stack:** bun + vitest 4.x + happy-dom 17.x + Testing Library + React 19 + Next.js 16 + next-intl 4

---

## 文件结构

### 改动的文件

| 文件 | 改动类型 | 原因 |
|------|----------|------|
| `packages/web/package.json` | dep 替换 | 删 `jsdom`、加 `happy-dom` (devDeps) |
| `packages/web/vitest.config.ts` | 配置改一行 | `environment: "jsdom"` → `"happy-dom"` |
| `packages/web/vitest.setup.ts` | 注释清理 | 所有 "Jsdom" → "DOM environment"；去掉 `// Jsdom 没实现 XXX` 注释 |
| `packages/web/components/common/button/app-copy-button.test.tsx` | 测试重写 | `Object.assign(navigator, { clipboard })` 在 happy-dom 是 getter |
| `packages/web/components/common/table/data-table.test.tsx` | 断言改 | `"0px"` → `"0"` |
| `packages/web/proxy.test.ts` | 测试修复 (3 fail) | next-intl ESM 解析 mock 问题 (R1 表象) |
| `packages/web/app/api/[...path]/route.test.ts` | 测试修复 (1 fail) | Origin 白名单测试 mock 问题 |
| `packages/web/app/api/auth/anon/proxy.test.ts` | 测试修复 (1 fail) | `headers.get("set-cookie")` 行为差异 |

### 依赖 tree

```
package.json
  devDependencies
    + happy-dom@^17.6.2   (新增)
    - jsdom@^29.1.1       (移除)

vitest.config.ts
  test.environment: "jsdom"  →  "happy-dom"

vitest.setup.ts
  "// Jsdom 没有 XXX" 注释化 →  "// DOM environment 没有 XXX"
```

---

### Task 1: dep 替换 + 配置 + baseline 验证

**Files:**
- Modify: `packages/web/package.json` (line 101–103)
- Modify: `packages/web/vitest.config.ts` (line 49)
- Modify: `packages/web/vitest.setup.ts` (移除 "Jsdom" 字样注释)
- Auto: `bun.lock` (重生成)

- [ ] **Step 1: package.json — 删 jsdom + 加 happy-dom**

```json
// devDependencies 段 (line 101–103, 原 jsdom 位置 ± 行)
// 删:
"jsdom": "^29.1.1",
// 加:
"happy-dom": "^17.6.3",
```

- [ ] **Step 2: vitest.config.ts — 切 environment**

```ts
// line 49, 行内覆盖
environment: "happy-dom",
```

- [ ] **Step 3: vitest.setup.ts — 移除 Jsdom 字样注释, 保留 mock**

改 6 处注释, 不改 mock 代码:
- line 11: `// Jsdom 不支持 useFormStatus` → `// DOM environment 不支持 useFormStatus`
- line 34: `// (2026-06-14) Jsdom` → `// (2026-06-14) DOM 环境`
- line 44: `// Jsdom 没实现 IntersectionObserver` → `// DOM 环境没实现 IntersectionObserver`
- line 58: `// Jsdom 没实现 ResizeObserver` → `// DOM 环境没实现 ResizeObserver`
- line 67: `// Shadcn Select / Dialog 等 Radix 组件读 globalThis.matchMedia, jsdom 默认是 undefined` → `// Radix 组件读 globalThis.matchMedia`

- [ ] **Step 4: bun install 重生成 lockfile**

```bash
cd packages/web && bun install
```
预期: happy-dom 安装完成, jsdom 从 node_modules 移除。

- [ ] **Step 5: 跑全量测试 — 记录 baseline fail**

```bash
cd packages/web && bun run test 2>&1 | tee /tmp/vitest-happy-dom-baseline.txt | grep -E "Test Files|Tests|Failed|FAIL "
```

预期输出 (2026-07-09 实测):
```
Test Files  5 failed | 264 passed | 3 skipped (272)
     Tests  10 failed | 1316 passed | 1 skipped | 7 todo (1334)
```

**5 fail 文件、10 fail 测试**作为后续 Task 的 baseline。

- [ ] **Step 6: lint + typecheck + format**

```bash
cd packages/web && bun run lint && bun run typecheck && bun run format:check
```
预期: 0 error / 0 warning (替换 dep + config 不影响现有代码风格)。

- [ ] **Step 7: Commit**

```bash
git add packages/web/package.json packages/web/vitest.config.ts packages/web/vitest.setup.ts packages/web/bun.lock
git commit -m "chore(web): vitest jsdom → happy-dom 17.x (dep+config+setup)"
```

---

### Task 2: CopyButton 测试 — `Object.assign(navigator, { clipboard })` 修复

**Files:**
- Modify: `packages/web/components/common/button/app-copy-button.test.tsx`

- [ ] **Step 1: 改测试 — `Object.assign(navigator, { clipboard })` → `Object.defineProperty(navigator, "clipboard", { ... })`**

happy-dom 用 getter 暴露 `navigator.clipboard`，`Object.assign` 在 getter 上抛 "Cannot set property clipboard ... which has only a getter"。

**修复**：把测试中 4 处 `Object.assign(navigator, { clipboard: ... })` 替换成 `Object.defineProperty`，在 `beforeEach` 清理并用 `vi.spyOn` mock `clipboard.writeText`。

```typescript
// 改动范围: line 47–93 (4 个 it)
// 统一的 mock 方法——在 beforeEach 做

// 在 describe 顶部加:
const mockClipboard = vi.hoisted(() => ({
  writeText: vi.fn<[string], Promise<void>>(),
}));

// 在 beforeEach 加:
beforeEach(() => {
  mockClipboard.writeText.mockReset();
  Object.defineProperty(navigator, "clipboard", {
    value: { writeText: mockClipboard.writeText },
    configurable: true,
    writable: true,
  });
});
```

改动 4 个 it 块 (line 47, 58, 69, 83):

**it "点击触发 clipboard writeText" (line 47)**:
```typescript
it("点击触发 clipboard writeText", async () => {
  mockClipboard.writeText.mockResolvedValue(undefined);
  render(<CopyButton text="要复制的文本" />);
  await act(async () => {
    screen.getByRole("button").click();
  });
  expect(mockClipboard.writeText).toHaveBeenCalledTimes(CALL_ONCE);
  expect(mockClipboard.writeText).toHaveBeenCalledWith("要复制的文本");
});
```

**it "复制成功后显示 successLabel" (line 58)**:
```typescript
it("复制成功后显示 successLabel", async () => {
  mockClipboard.writeText.mockResolvedValue(undefined);
  render(<CopyButton text="hello" successLabel="已完成" />);
  await act(async () => {
    screen.getByRole("button").click();
  });
  expect(screen.getByText("已完成")).toBeInTheDocument();
});
```

**it "复制失败时 toast.error 被调用" (line 69)**:
```typescript
it("复制失败时 toast.error 被调用", async () => {
  const { toast } = await import("sonner");
  mockClipboard.writeText.mockRejectedValue(new Error("权限不足"));
  render(<CopyButton text="hello" />);
  await act(async () => {
    screen.getByRole("button").click();
  });
  expect(toast.error).toHaveBeenCalledWith("权限不足");
});
```

**it "onCopied 回调被调用" (line 83)**:
```typescript
it("onCopied 回调被调用", async () => {
  const onCopied = vi.fn();
  mockClipboard.writeText.mockResolvedValue(undefined);
  render(<CopyButton text="hello" onCopied={onCopied} />);
  await act(async () => {
    screen.getByRole("button").click();
  });
  expect(onCopied).toHaveBeenCalledTimes(CALL_ONCE);
});
```

- [ ] **Step 2: 跑单文件验证**

```bash
cd packages/web && bunx vitest run components/common/button/app-copy-button.test.tsx
```
预期: 7 passed (原 7 it, 0 fail)

- [ ] **Step 3: Commit**

```bash
git add packages/web/components/common/button/app-copy-button.test.tsx
git commit -m "test(web): CopyButton happy-dom — Object.defineProperty mock clipboard"
```

---

### Task 3: DataTable — `minWidth "0"` vs `"0px"` 断言修复

**Files:**
- Modify: `packages/web/components/common/table/data-table.test.tsx` (line 167)

- [ ] **Step 1: 看源码确认业务代码行为**

`data-table.tsx:76`:
```typescript
return { minWidth: "0", width: "100%" };
```

业务代码直接传字符串 `"0"`。jsdom 标准化成 `"0px"`，happy-dom 保留原值 `"0"`。

**修复**: 测试断言改从 `"0px"` → `"0"`。业务代码不动（`"0"` 是 valid CSS, 浏览器正确处理）。

- [ ] **Step 2: 改断言**

```typescript
// data-table.test.tsx line 167
expect(th?.style.minWidth).toBe("0px");  // 改前 — jsdom 标准化
expect(th?.style.minWidth).toBe("0");    // 改后 — happy-dom 原生
```

- [ ] **Step 3: 跑单文件验证**

```bash
cd packages/web && bunx vitest run components/common/table/data-table.test.tsx
```
预期: 22 passed (原 22 it, 0 fail)

- [ ] **Step 4: Commit**

```bash
git add packages/web/components/common/table/data-table.test.tsx
git commit -m "test(web): DataTable happy-dom — minWidth 0 → '0' 非 '0px'"
```

---

### Task 4: proxy.test.ts × 3 fail — next-intl ESM ordering

**Files:**
- Modify: `packages/web/proxy.test.ts`

- [ ] **Step 1: 诊断**

`proxy.test.ts` 3 个 fail: "有 token → 不重定向" 拿到 redirect URL 而非 null。root cause：happy-dom 下模块加载顺序变了，`next-intl/middleware` 的 mock 没拦截到 `proxy.ts` 内部的 `import`。

已有 mock (line 4–6):
```typescript
vi.mock("next-intl/middleware", () => ({
  default: () => () => undefined, // 透传: next-intl 不参与我们的 redirect 测试
}));
```

- [ ] **Step 2: 修 proxy.ts — 让 middleware 可 mock**

**方案**: 给 `proxy.ts` 加 `vitest` 条件编译分支, 在 happy-dom 下从测试代码 mock 一个全局标志让 proxy 跳过 next-intl middleware。

实际最简单方案: 改测试 mock `next-intl/middleware` → mock 整个 `next-intl` 命名空间, 让所有 `import("next-intl")` 都走 mock。

```typescript
// proxy.test.ts — 把 line 4–6 从:
vi.mock("next-intl/middleware", () => ({
  default: () => () => undefined,
}));
// 改成:
vi.mock("next-intl", () => ({
  createMiddleware: () => () => undefined,
}));
// 同时 mock next-intl/navigation 等 proxy 内部 import 的模块
vi.mock("next-intl/navigation", () => ({
  createNavigation: () => undefined,
}));
```

**注意**: 如果 mock 还不够, 需要看 `proxy.ts` 内部引用了什么 next-intl 模块。先单文件跑验证:

- [ ] **Step 3: 跑单文件验证**

```bash
cd packages/web && bunx vitest run proxy.test.ts
```
预期: 8 passed

如果仍有 fail, 读 `proxy.ts` 全文件找额外的 next-intl import。

- [ ] **Step 4: Commit**

```bash
git add packages/web/proxy.test.ts
git commit -m "test(web): proxy happy-dom — next-intl mock 兼容 ESM ordering"
```

---

### Task 5: route.test.ts × 1 fail — origin 白名单 403

**Files:**
- Modify: `packages/web/app/api/[...path]/route.test.ts`

- [ ] **Step 1: 分析**

fail 详情: `origin 不在白名单 → 403 Forbidden` — expected 403 got 200。root cause: happy-dom 下 `new Request` 行为差异影响 `route.ts` 内部的 origin 校验。

- [ ] **Step 2: 读完整 route.test.ts + route.ts**

读 `app/api/[...path]/route.ts` + 相关测试, 确认 origin 校验逻辑, 修测试 mock。

- [ ] **Step 3: 跑单文件验证**

```bash
cd packages/web && bunx vitest run app/api/[...path]/route.test.ts
```
预期: 该文件所有 it pass。

- [ ] **Step 4: Commit**

```bash
git add packages/web/app/api/[...path]/route.test.ts
git commit -m "test(web): route happy-dom — origin mock 兼容"
```

---

### Task 6: proxyAuthResponse — Set-Cookie header 行为修复

**Files:**
- Modify: `packages/web/app/api/auth/anon/proxy.test.ts`
- Modify: `packages/web/app/api/auth/anon/proxy.ts` (可能需要)

- [ ] **Step 1: 分析**

fail 详情: `expect(out.headers.get("set-cookie")).toContain("rag_user_token=abc123")` 报 "null and string invalid for assertion" — `out.headers.get("set-cookie")` 返 `null`。

Root cause: happy-dom 下 `NextResponse` 的 headers 行为变化 (`getSetCookie()` 取代 `get("set-cookie")`)。Node 18+ 要求用 `Headers.getSetCookie()` 来取多个 Set-Cookie 值, `get("set-cookie")` 只返回第一个。happy-dom 在 `Headers` 上强制了 spec 行为。

**修复方案**: 改业务代码 `proxy.ts` 使用 `Headers.getSetCookie()` 兼容模式, 或改测试。

先读 `proxy.ts` 源码:

- [ ] **Step 2: 根据源码决定修法**

- 如果 `proxy.ts` 用 `get("set-cookie")` → 改 `getSetCookie()` (业务代码适配)
- 如果 `proxy.ts` 用 `getSetCookie()` → 改测试 mock (测试适配)

- [ ] **Step 3: 跑单文件验证**

```bash
cd packages/web && bunx vitest run app/api/auth/anon/proxy.test.ts
```
预期: 4 passed (原 4 it, 0 fail)

- [ ] **Step 4: Commit**

```bash
git add packages/web/app/api/auth/anon/proxy.test.ts packages/web/app/api/auth/anon/proxy.ts
git commit -m "fix(web): proxyAuthResponse happy-dom — Set-Cookie headers.getSetCookie() 兼容"
```

---

### Task 7: 全量验证 + 8 pre-existing fail 处理

**Files:**
- Modify: `packages/web/vitest.config.ts` (加 resolve.alias 或 server.deps.inline)

- [ ] **Step 1: 全量跑一次看 baseline**

```bash
cd packages/web && bun run test 2>&1 | tee /tmp/vitest-happy-dom-final.txt | grep -E "Test Files|Tests|Failed|FAIL "
```

如果 Task 1–6 全对, 预期:
```
Test Files  0 failed | 269 passed | 3 skipped (272)
     Tests  0 failed | 1324 passed | 1 skipped | 7 todo (1334)
```
**无新增 fail** (5 个新文件全修)。

- [ ] **Step 2: 处理 pre-existing 8 fail (R1 + R3)**

根据 [docs/superpowers/plans/2026-06-27-pre-existing-test-failures.md], R1 是 next-intl ESM, R3 是 RSC apiFetch mock。在 happy-dom 下这些可能被遮住了也可能还在。

**方案**: vitest.config.ts 加 `server.deps.inline`:

```typescript
// vitest.config.ts test: 段加 (在 environment 之后):
server: {
  deps: {
    inline: ["next-intl"],
  },
},
```

这个配置把 next-intl 拉进 Vite 的 module graph, 让其内部 ESM import 不走 Node 解析器, 从而绕过 R1 问题。

- [ ] **Step 3: 验证 R1 修复**

```bash
cd packages/web && bunx vitest run <之前报 R1 error 的文件>
```
如果 inline 措施不解决问题, 改用备用方案: 在 `vitest.setup.ts` 加:
```typescript
vi.mock("next-intl/navigation", () => ({
  createNavigation: () => () => undefined,
}));
```

- [ ] **Step 4: 跑全量最终验证**

```bash
cd packages/web && bun run test 2>&1 | tail -20
```
预期: 0 failed (如果仍有 fail, 以 Happy-dom 不通过就重写原则继续修, 最多迭代 ≤3 轮避免陷入死循环)

- [ ] **Step 5: 更新 CLAUDE.md baseline (如果变)**

检查 `packages/web/CLAUDE.md` 中基线数字 (当前写旧数据), 更新:
- Test Files / Tests passed / fail 数字
- vitest coverage baseline (如果 coverage 也变了)

- [ ] **Step 6: Commit 最终批**

```bash
git add packages/web/vitest.config.ts packages/web/CLAUDE.md
git commit -m "chore(web): happy-dom 全量切换到 0 fail + pre-existing ESM fix"
```

---

## Self-Review Checklist

**1. Spec coverage:**
- ✅ Task 1: dep 替换 + config (全局切换 jsdom → happy-dom)
- ✅ Task 2–6: 5 个新 fail 文件逐个修复
- ✅ Task 7: 全量验证 + pre-existing R1+R3 处理

**2. Placeholder scan:**
- Task 5 的 Step 2 含 "读完整 route.test.ts + route.ts" — 这是代码阅读步骤, 不算 placeholder。但 Test 6 Step 1 也含 "先读源码" — 这是诊断步骤, 因为不读源码无法确定修业务还是修测试。**不需改**。

- Task 4 的方案依赖 Step 3 验证结果 (如果 mock 不够要加额外 mock)。这不是 placeholder — 这是多层级 mock 策略, 先试最轻的, 不够再放大。

**3. Type consistency:**
- 所有 test 文件名、组件的命名一致
- `beforeEach` 在所有 task 里一致使用
- `Object.defineProperty` / `vi.hoisted` / `vi.fn` 一致使用
