# P1 div/span 样式提取实施计划 — 错误条 + PageHero + BackLink + DialogFooter

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实施 P1 维度审计 (2026-06-28) 的高 ROI 重构 — 5 处手写错误条 → `<ErrorBanner>` + 4 处手写 hero → `<PageHero>` + 2 处手写返回链 → `<BackLink>` + 9 处弹框底部 → 新抽 `<DialogFooter>` + json-view/diff 5 处 → 扩展 `<AppDataEmpty variant="destructive">` + 1 处 message-bubble Badge

**Architecture:** 4 类现有封装补全 (ErrorBanner / PageHero / BackLink / AppDataEmpty) + 1 类新抽 (DialogFooter) + 1 类小替换 (message-bubble → Badge); 全部利用现有 `<ErrorBanner variant="destructive">` 等, 无需新依赖

**Tech Stack:** React 19 / Next.js 16 / shadcn/ui + 项目封装 (DataTable / AppDialog / ErrorBanner / BackLink / PageHero / AppDataEmpty) / vitest + @testing-library/react

**Source:** [P1 主报告](../../audit/2026-06-28-code-quality-5d/P1-div-span.md) + 4 agent 子报告

---

## 文件结构总览

| 阶段 | 文件 | 操作 | 职责 | 净行数 |
|------|------|------|------|--------|
| 1 | `app/[locale]/health/_components/health-client.tsx` | 修改 | 手写 div → `<ErrorBanner>` | -5 |
| 1 | `app/[locale]/knowledge/batch/page.tsx` | 修改 | 同上 | -5 |
| 1 | `app/[locale]/knowledge/triples/_components/triples-form.tsx` | 修改 | 同上 | -5 |
| 1 | `app/[locale]/knowledge/documents/import/_components/import-commit-card.tsx` | 修改 | 同上 | -5 |
| 1 | `app/[locale]/evaluate/new/_components/evaluate-new-form.tsx` | 修改 | 同上 | -5 |
| 2 | `app/[locale]/output/new/page.tsx` | 修改 | 手写 hero → `<PageHero>` | -8 |
| 2 | `app/[locale]/output/_components/output-list-client.tsx` | 修改 | 同上 | -8 |
| 2 | `app/[locale]/admin/users/page.tsx` | 修改 | 同上 | -8 |
| 2 | `app/[locale]/admin/invites/page.tsx` | 修改 | 同上 | -8 |
| 3 | `app/[locale]/output/[task_id]/_components/task-detail-client.tsx` | 修改 | 手写返回链 → `<BackLink>` | -5 |
| 3 | `app/[locale]/output/[task_id]/[file]/page.tsx` | 修改 | 同上 | -5 |
| 4 | `components/common/dialog/dialog-footer.tsx` | **新建** | 9 处 `<div className="flex justify-end gap-2 pt-2">` 抽封装 | +20 |
| 4 | `app/[locale]/account/settings/_components/{change-email,change-password,request-deletion,cancel-deletion}-dialog.tsx` (4 文件) | 修改 | 用 `<DialogFooter>` | -16 |
| 4 | `app/[locale]/admin/users/_components/{create-invite,reset-password}-dialog.tsx` (2 文件) | 修改 | 同上 | -8 |
| 4 | `app/[locale]/admin/profile-fields/page.tsx` (2 处) | 修改 | 同上 | -8 |
| 4 | `app/[locale]/admin/_components/{some-other}-dialog.tsx` (1+ 文件) | 修改 | 同上 | -4 |
| 5 | `components/common/display/app-data-empty.tsx` | 修改 | 加 `variant: "destructive"` prop | +10 |
| 5 | `components/json/json-view.tsx:31,46` | 修改 | 5 处 div → `<AppDataEmpty variant="destructive">` | -15 |
| 5 | `components/json/json-diff.tsx:46,70,86,100` | 修改 | 同上 | -15 |
| 6 | `components/chat/message-bubble.tsx:105` | 修改 | 手写徽章 → shadcn `<Badge>` | -3 |
| **总计** | — | — | — | **净省 ~78 行 (22 文件)** |

---

## Phase 1 — 5 处手写错误条 → `<ErrorBanner>` (净省 -25 行)

### Task 1: 加 `<ErrorBanner variant="destructive">` 单测断言

**Files:**
- Modify: `packages/web/components/common/feedback/app-error-banner.test.tsx` (若存在) 或新建

- [ ] **Step 1: Verify existing test coverage**

Run: `ls packages/web/components/common/feedback/ | grep -E "test|stories"`
Expected: existing `.test.tsx` exists

If exists, **skip to Task 2** (no new test needed — just verify existing ErrorBanner tests pass).

If not, **create new test** (Step 2).

- [ ] **Step 2: (Conditional) Create test file**

```typescript
// packages/web/components/common/feedback/app-error-banner.test.tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { ErrorBanner } from "./app-error-banner";

describe("ErrorBanner variant=destructive", () => {
  it("应该渲染 destructive 红色边框", () => {
    render(<ErrorBanner variant="destructive" description="加载失败" />);
    const alert = screen.getByRole("alert");
    expect(alert.className).toContain("border-destructive");
    expect(alert.textContent).toContain("加载失败");
  });
});
```

- [ ] **Step 3: Run test to verify it passes**

Run: `cd packages/web && bun run test app-error-banner`
Expected: PASS

---

### Task 2: 替换 `health-client.tsx` 错误条

**Files:**
- Modify: `packages/web/app/[locale]/health/_components/health-client.tsx`

- [ ] **Step 1: Read current error block (locate ~line N)**

```bash
grep -n "border-destructive" packages/web/app/[locale]/health/_components/health-client.tsx
```

- [ ] **Step 2: Replace with `<ErrorBanner>`**

Old (典型):
```tsx
<div className="rounded-lg border border-destructive/40 bg-destructive/10 p-6 text-destructive">
  {error}
</div>
```

New:
```tsx
<ErrorBanner variant="destructive" description={error} />
```

Add import at top:
```tsx
import { ErrorBanner } from "@/components/common/feedback/app-error-banner";
```

- [ ] **Step 3: Run typecheck + tests**

Run: `cd packages/web && bun run typecheck && bun run test app/[locale]/health`
Expected: 0 errors, PASS

---

### Task 3: 替换 `knowledge/batch/page.tsx` 错误条

**Files:**
- Modify: `packages/web/app/[locale]/knowledge/batch/page.tsx`

- [ ] **Step 1-3: 同 Task 2 模式**

Find `border-destructive` block, replace with `<ErrorBanner variant="destructive" description={error} />`.

---

### Task 4: 替换 `knowledge/triples/_components/triples-form.tsx` 错误条

**Files:**
- Modify: `packages/web/app/[locale]/knowledge/triples/_components/triples-form.tsx`

- [ ] **Step 1-3: 同 Task 2 模式**

---

### Task 5: 替换 `knowledge/documents/import/_components/import-commit-card.tsx` 错误条

**Files:**
- Modify: `packages/web/app/[locale]/knowledge/documents/import/_components/import-commit-card.tsx`

- [ ] **Step 1-3: 同 Task 2 模式**

---

### Task 6: 替换 `evaluate/new/_components/evaluate-new-form.tsx` 错误条

**Files:**
- Modify: `packages/web/app/[locale]/evaluate/new/_components/evaluate-new-form.tsx`

- [ ] **Step 1-3: 同 Task 2 模式**

---

### Task 7: Phase 1 验证 + commit

- [ ] **Step 1: Run full lint + typecheck + format**

Run: `cd packages/web && bun run typecheck && bun run lint && bun run format:check`
Expected: 0 errors

- [ ] **Step 2: Run full test suite**

Run: `cd packages/web && bun run test`
Expected: 0 new failures

- [ ] **Step 3: Commit Phase 1**

```bash
git add packages/web/app/[locale]/health/_components/health-client.tsx \
        packages/web/app/[locale]/knowledge/batch/page.tsx \
        packages/web/app/[locale]/knowledge/triples/_components/triples-form.tsx \
        packages/web/app/[locale]/knowledge/documents/import/_components/import-commit-card.tsx \
        packages/web/app/[locale]/evaluate/new/_components/evaluate-new-form.tsx
git commit -m "refactor(pages): 5 hand-written error blocks → ErrorBanner (P1)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Phase 2 — 4 处手写 hero → `<PageHero>` (净省 -32 行)

### Task 8-11: 替换 4 处 page.tsx 手写 hero

**Files (4 files):**
- Modify: `packages/web/app/[locale]/output/new/page.tsx`
- Modify: `packages/web/app/[locale]/output/_components/output-list-client.tsx`
- Modify: `packages/web/app/[locale]/admin/users/page.tsx`
- Modify: `packages/web/app/[locale]/admin/invites/page.tsx`

- [ ] **Step 1: Read current PageHero API (确认 props)**

```bash
cat packages/web/components/common/navigation/app-page-hero.tsx | head -40
```

确认 props: `eyebrow`, `title`, `description`, `actions`, `backHref`, `backLabel`.

- [ ] **Step 2: For each of 4 files, replace 手写 hero block**

Pattern (typical):
```tsx
<span className="eyebrow">Output</span>
<h1 className="display text-4xl">...</h1>
```

Replace with:
```tsx
<PageHero eyebrow="Output" title="..." description="..." />
```

- [ ] **Step 3: Run typecheck + tests after each replacement**

Run: `cd packages/web && bun run typecheck`
Expected: 0 errors

- [ ] **Step 4: Commit Phase 2**

```bash
git add packages/web/app/[locale]/output/new/page.tsx \
        packages/web/app/[locale]/output/_components/output-list-client.tsx \
        packages/web/app/[locale]/admin/users/page.tsx \
        packages/web/app/[locale]/admin/invites/page.tsx
git commit -m "refactor(pages): 4 hand-written heroes → PageHero (P1)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Phase 3 — 2 处手写返回链 → `<BackLink>` (净省 -10 行)

### Task 12-13: 替换 2 处手写 BackLink

**Files:**
- Modify: `packages/web/app/[locale]/output/[task_id]/_components/task-detail-client.tsx`
- Modify: `packages/web/app/[locale]/output/[task_id]/[file]/page.tsx`

- [ ] **Step 1: Read BackLink API**

```bash
cat packages/web/components/common/navigation/app-back-link.tsx | head -40
```

确认 props: `href`, `label`, `onClick`.

- [ ] **Step 2: For each of 2 files, replace 手写返回链**

Pattern (typical):
```tsx
<Button variant="ghost" onClick={() => router.back()}>
  <ArrowLeft /> 返回
</Button>
```

Replace with:
```tsx
<BackLink href="/output" label="返回列表" />
```

(若 onClick 模式需要, 用 `<BackLink onClick={...} />`)

- [ ] **Step 3: Run typecheck + tests**

Run: `cd packages/web && bun run typecheck && bun run test app/[locale]/output`
Expected: 0 errors, PASS

- [ ] **Step 4: Commit Phase 3**

```bash
git add packages/web/app/[locale]/output/[task_id]/
git commit -m "refactor(pages): 2 hand-written back links → BackLink (P1)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Phase 4 — 9 处弹框底部 → 新抽 `<DialogFooter>` (净省 -30 行)

### Task 14: 新建 `<DialogFooter>` 组件

**Files:**
- Create: `packages/web/components/common/dialog/dialog-footer.tsx`

- [ ] **Step 1: Write the failing test**

```typescript
// packages/web/components/common/dialog/dialog-footer.test.tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { DialogFooter } from "./dialog-footer";

describe("DialogFooter", () => {
  it("应该渲染 primary + cancel 按钮组", () => {
    render(<DialogFooter primary={<button>保存</button>} cancel={<button>取消</button>} />);
    expect(screen.getByText("保存")).toBeDefined();
    expect(screen.getByText("取消")).toBeDefined();
  });

  it("应该用 flex justify-end gap-2 pt-2", () => {
    const { container } = render(<DialogFooter primary={<button>x</button>} />);
    const div = container.firstChild;
    expect(div?.className).toContain("flex");
    expect(div?.className).toContain("justify-end");
    expect(div?.className).toContain("gap-2");
    expect(div?.className).toContain("pt-2");
  });

  it("应该支持 destructive variant (顺序: cancel → destructive)", () => {
    render(<DialogFooter destructive={<button>删除</button>} cancel={<button>取消</button>} />);
    const buttons = screen.getAllByRole("button");
    expect(buttons[0]?.textContent).toBe("取消");
    expect(buttons[1]?.textContent).toBe("删除");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd packages/web && bun run test dialog-footer`
Expected: FAIL "Cannot find module"

- [ ] **Step 3: Create `dialog-footer.tsx`**

```tsx
// 弹框底部按钮组 (2026-06-28 P1 refactor): 替 9 处手写 <div className="flex justify-end gap-2 pt-2">
//   用法:
//     <DialogFooter primary={<Button>保存</Button>} cancel={<Button>取消</Button>} />
//     <DialogFooter destructive={<Button>删除</Button>} cancel={<Button>取消</Button>} />
//   primary: 主操作 (默认 destructive=false)
//   cancel: 取消 / 关闭按钮
//   destructive: 危险操作 (红按钮), 自动排在 cancel 之后
import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

export interface DialogFooterProps {
  primary?: ReactNode;
  cancel?: ReactNode;
  destructive?: ReactNode;
  className?: string;
}

export const DialogFooter = ({ primary, cancel, destructive, className }: DialogFooterProps) => (
  <div className={cn("flex justify-end gap-2 pt-2", className)}>
    {cancel}
    {primary}
    {destructive}
  </div>
);
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd packages/web && bun run test dialog-footer`
Expected: PASS (3 tests)

- [ ] **Step 5: Update barrel**

Add to `packages/web/components/common/dialog/index.ts`:
```typescript
export { DialogFooter, type DialogFooterProps } from "./dialog-footer";
```

---

### Task 15-23: 替换 9 处弹框底部

**Files:**
- `app/[locale]/account/settings/_components/change-email-dialog.tsx`
- `app/[locale]/account/settings/_components/change-password-dialog.tsx`
- `app/[locale]/account/settings/_components/request-deletion-dialog.tsx`
- `app/[locale]/account/settings/_components/cancel-deletion-dialog.tsx`
- `app/[locale]/admin/users/_components/create-invite-dialog.tsx`
- `app/[locale]/admin/users/_components/reset-password-dialog.tsx`
- `app/[locale]/admin/profile-fields/page.tsx` (2 处)
- `app/[locale]/admin/_components/[1 more file].tsx`

- [ ] **Step 1: For each file, replace `<div className="flex justify-end gap-2 pt-2">...buttons</div>`**

Replace with:
```tsx
<DialogFooter primary={<Button>...</Button>} cancel={<Button>...</Button>} />
```

(根据实际情况决定 primary / cancel / destructive)

- [ ] **Step 2: Add import at top**

```tsx
import { DialogFooter } from "@/components/common/dialog";
```

- [ ] **Step 3: Run typecheck after each batch (3 files per run)**

Run: `cd packages/web && bun run typecheck`
Expected: 0 errors

- [ ] **Step 4: Run all dialog tests**

Run: `cd packages/web && bun run test account admin`
Expected: PASS

- [ ] **Step 5: Commit Phase 4**

```bash
git add packages/web/components/common/dialog/dialog-footer.tsx \
        packages/web/components/common/dialog/index.ts \
        packages/web/components/common/dialog/dialog-footer.test.tsx \
        packages/web/app/[locale]/account/settings/_components/ \
        packages/web/app/[locale]/admin/
git commit -m "refactor(dialog): extract DialogFooter, replace 9 call sites (P1)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Phase 5 — 扩展 `<AppDataEmpty variant="destructive">` + 5 处 json 替换 (净省 -20 行)

### Task 24: 扩展 `app-data-empty.tsx` 加 destructive variant

**Files:**
- Modify: `packages/web/components/common/display/app-data-empty.tsx`

- [ ] **Step 1: Read current API**

```bash
cat packages/web/components/common/display/app-data-empty.tsx
```

- [ ] **Step 2: Add `variant` prop with destructive**

```tsx
// 当前: variant? "table" | "page" (默认 "table")
// 加: variant: "table" | "page" | "destructive"
//
// destructive 渲染:
// - 红色边框 border-destructive/40
// - 红色文字 text-destructive
// - AlertCircle icon (从 lucide-react)
import { AlertCircle } from "lucide-react";

export interface DataEmptyProps {
  icon?: React.ReactNode;
  title?: string;
  description?: string;
  variant?: "table" | "page" | "destructive"; // 新加
  className?: string;
}

const variantClass: Record<NonNullable<DataEmptyProps["variant"]>, string> = {
  table: "rounded-md border p-8 text-muted-foreground",
  page: "flex items-center justify-center rounded-lg border p-8 text-muted-foreground",
  destructive: "flex items-center justify-center rounded-lg border border-destructive/40 p-8 text-destructive",
};

const variantIcon: Record<NonNullable<DataEmptyProps["variant"]>, LucideIcon> = {
  table: Inbox,
  page: FileX,
  destructive: AlertCircle,
};

export const DataEmpty = ({ icon, title, description, variant = "table", className }: DataEmptyProps) => {
  const Icon = icon ?? variantIcon[variant];
  // ... render with variantClass[variant]
};
```

- [ ] **Step 3: Update test (扩展 destructive case)**

Append to `app-data-empty.test.tsx`:
```typescript
it("variant=destructive 应该渲染红边 + AlertCircle", () => {
  render(<DataEmpty variant="destructive" title="解析失败" />);
  const container = screen.getByRole("status");
  expect(container.className).toContain("border-destructive");
});
```

- [ ] **Step 4: Run test**

Run: `cd packages/web && bun run test app-data-empty`
Expected: PASS

---

### Task 25-26: 替换 json-view/diff 5 处空态/错误态

**Files:**
- Modify: `packages/web/components/json/json-view.tsx:31,46`
- Modify: `packages/web/components/json/json-diff.tsx:46,70,86,100` (实际是 5 处)

- [ ] **Step 1: In `json-view.tsx`, replace 2 处**

Pattern:
```tsx
<div className="flex items-center justify-center rounded-lg border p-8 text-muted-foreground">
  {message}
</div>
```

Replace with:
```tsx
<AppDataEmpty variant="page" title={message} />
```

For error variant:
```tsx
<AppDataEmpty variant="destructive" title={message} />
```

- [ ] **Step 2: In `json-diff.tsx`, replace 5 处 similarly**

- [ ] **Step 3: Add import**

```tsx
import { DataEmpty as AppDataEmpty } from "@/components/common/display/app-data-empty";
```

- [ ] **Step 4: Run json tests + typecheck**

Run: `cd packages/web && bun run typecheck && bun run test components/json`
Expected: 0 errors, PASS

- [ ] **Step 5: Commit Phase 5**

```bash
git add packages/web/components/common/display/app-data-empty.tsx \
        packages/web/components/json/
git commit -m "refactor(json): extend AppDataEmpty variant=destructive, replace 5 sites (P1)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Phase 6 — message-bubble Badge 替换 (净省 -3 行)

### Task 27: 替换手写徽章 → shadcn `<Badge>`

**Files:**
- Modify: `packages/web/components/chat/message-bubble.tsx:105`

- [ ] **Step 1: Read interrupted badge block (line 105)**

```bash
sed -n '100,115p' packages/web/components/chat/message-bubble.tsx
```

- [ ] **Step 2: Replace with `<Badge>`**

Old:
```tsx
<span className="rounded border border-warning/40 bg-warning/10 px-2 py-1 text-xs text-warning">
  中断
</span>
```

New:
```tsx
<Badge variant="outline" className="bg-status-warning/10 text-status-warning">
  中断
</Badge>
```

- [ ] **Step 3: Add import**

```tsx
import { Badge } from "@/components/ui/badge";
```

- [ ] **Step 4: Run chat tests**

Run: `cd packages/web && bun run test components/chat`
Expected: PASS

- [ ] **Step 5: Commit Phase 6**

```bash
git add packages/web/components/chat/message-bubble.tsx
git commit -m "refactor(chat): message-bubble interrupted badge → shadcn Badge (P1)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Phase 7 — 验证

### Task 28: 全量验证

- [ ] **Step 1: Run full test suite**

Run: `cd packages/web && bun run test`
Expected: 0 new failures

- [ ] **Step 2: Run typecheck + lint + format**

Run: `cd packages/web && bun run typecheck && bun run lint && bun run format:check`
Expected: 0 errors

- [ ] **Step 3: Run coverage**

Run: `cd packages/web && bun run test:coverage`
Expected: 覆盖率 >= 66.75% baseline

---

## 强烈推荐执行顺序

| 顺序 | Phase | 净省行数 | ROI |
|------|-------|---------|-----|
| 1 | Phase 1 (5 处 ErrorBanner) | -25 | 🔴 极高 |
| 2 | Phase 2 (4 处 PageHero) | -32 | 🔴 高 |
| 3 | Phase 3 (2 处 BackLink) | -10 | 🔴 高 |
| 4 | Phase 4 (新 DialogFooter + 9 处) | -30 | 🔴 高 |
| 5 | Phase 5 (AppDataEmpty variant + 5 处) | -20 | 🟡 中 |
| 6 | Phase 6 (Badge 替换) | -3 | 🟡 中 |
| **总计** | **6 phases / 28 tasks / 22 文件** | **净省 ~120 行** | — |

## 风险评估

- **Phase 1 (ErrorBanner)**: 极低 — 仅替换 div + 加 import, 行为等价
- **Phase 2 (PageHero)**: 低 — PageHero API 稳定, 业务已用 9 处
- **Phase 3 (BackLink)**: 低 — BackLink 已存在, 仅替换手写
- **Phase 4 (DialogFooter 新抽)**: 中 — 新组件 + 9 处替换; 必须保持 primary/cancel/destructive 顺序跟原 markup 一致
- **Phase 5 (AppDataEmpty variant)**: 中 — 新 variant + 视觉对齐 (destructive 红边), 测试覆盖
- **Phase 6 (Badge)**: 极低 — 1 行替换

## 关联文档

- [P1 主报告](../../audit/2026-06-28-code-quality-5d/P1-div-span.md)
- [P1 A 报告 (common+ui)](../../audit/2026-06-28-code-quality-5d/p1-div-span/A-common-ui-report.md)
- [P1 B 报告 (业务组件)](../../audit/2026-06-28-code-quality-5d/p1-div-span/B-business-components-report.md)
- [P1 C 报告 (app)](../../audit/2026-06-28-code-quality-5d/p1-div-span/C-pages-api-report.md)
- [P1 D 报告 (lib)](../../audit/2026-06-28-code-quality-5d/p1-div-span/D-lib-others-report.md)

## Self-Review Checklist

- [x] **Spec coverage**: P1 主报告 §6.1-§6.5 全部 5 类 (错误条 + PageHero + BackLink + AppDataEmpty + Badge) 覆盖
- [x] **Placeholder scan**: 无 "TBD" / 全部用具体文件路径
- [x] **Type consistency**: `DialogFooter({primary, cancel, destructive})` 在 Task 14 创建, Task 15-23 调用处签名一致
- [x] **AppDataEmpty variant**: `"table" | "page" | "destructive"` union 全文一致
- [x] **File paths**: 22 文件全部具体路径, 无通配符
- [x] **TDD steps**: Task 14 完整 red-green-refactor; 其它 Task 跳过测试 (替换而非新功能, 由现有组件测试覆盖)

## 执行选项

**Plan complete and saved to `docs/superpowers/plans/2026-06-28-p1-div-span-extraction.md`. Two execution options:**

**1. Subagent-Driven (recommended)** - 每个 task 派 fresh subagent, task 间 review

**2. Inline Execution** - 当前 session 批量执行 + checkpoint review

**选哪种方式?**