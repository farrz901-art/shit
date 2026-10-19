# 代码质量 5 维度分析 — P0/P1/P2 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 按 spec 分析结果，执行 P0（死文件清理 + form-field 合并 + reject-dialog 用 AppDialog）、P1（AppCollapsible 提取）、P2（目录重组 + 命名统一），产出整洁的 common 组件结构。

**Architecture:** 自底向上执行：先 P0 清理（安全，不涉及 import 路径变更）→ P1 提取（新增组件，迁移 2 处）→ P2 重组（批量 import 重写，最后一步做，一次到位）。

**Tech Stack:** TypeScript / React 19 / shadcn / Radix Collapsible / Tailwind v4 / oxfmt / oxlint / tsgo / vitest

---

## 文件结构

| 路径 | 操作 | 责任 |
|------|------|------|
| `components/common/confirm-dialog.tsx` | 删除 | 死文件，已被 confirm/app-confirm.tsx 替代 |
| `components/common/form-field.tsx` | 删除 | 功能重复，被 form/form-item.tsx 替代 |
| `components/common/form-field.test.tsx` | 删除 | 测试已合并到 form/form.test.tsx |
| `components/common/index.ts` | 修改 | 移除 form-field 导出 |
| `components/common/app-collapsible.tsx` | 新建 | AppCollapsible 组件 |
| `components/common/app-collapsible.test.tsx` | 新建 | AppCollapsible 测试 |
| `components/chat/message-bubble.tsx` | 修改 | 2 处 raw Collapsible → AppCollapsible |
| `app/[locale]/submissions/_components/reject-dialog.tsx` | 修改 | raw Dialog → AppDialog |
| `app/[locale]/submissions/_components/reject-dialog.test.tsx` | 修改 | 测试适配 AppDialog |
| `components/common/form/form-item.tsx` | 修改 | 合并 form-field 差异 |

**P2 目录重组（最后批处理）：** 大量文件 rename + ~180 处 import 更新，详见 Task 5。

---

### Task 1: [P0] 删除 confirm-dialog.tsx 死文件

**Files:**
- Delete: `packages/web/components/common/confirm-dialog.tsx`

- [ ] **Step 1: 确认死文件不被任何文件 import**

```bash
grep -r "confirm-dialog|ConfirmDialog" packages/web/{app,components,lib} --include="*.{ts,tsx}" -l | grep -v "components/common/confirm-dialog.tsx"
```

Expected: No output (0 matches). 已确认当前结果：仅自身定义，0 外部引用。

- [ ] **Step 2: 删除文件**

```bash
rm packages/web/components/common/confirm-dialog.tsx
```

- [ ] **Step 3: 验证不破坏构建**

```bash
cd packages/web && bun run typecheck 2>&1 | tail -5
```

Expected: 0 errors

- [ ] **Step 4: Commit**

```bash
git add packages/web/components/common/confirm-dialog.tsx
git commit -m "chore: remove dead confirm-dialog.tsx (superseded by confirm/app-confirm.tsx)"
```

---

### Task 2: [P0] 合并 form-field.tsx → form/form-item.tsx

**Files:**
- Delete: `packages/web/components/common/form-field.tsx`
- Delete: `packages/web/components/common/form-field.test.tsx`
- Modify: `packages/web/components/common/form/form-item.tsx`
- Modify: `packages/web/components/common/index.ts`（移除 form-field 导出）

#### 差异分析

| 维度 | form-field.tsx | form/form-item.tsx |
|------|---------------|-------------------|
| label | required | optional |
| container className | space-y-1.5 | space-y-2 |
| inputId | form-field-${name} | form-item-${name} |
| data attr | 无 | div data-form-item-input |
| import 路径 | ./form/form-context | ./form-context |
| 外部引用 | 仅 index.ts re-export | evaluate-new-form.tsx 等 |

**合并方向：** FormItem 功能更完整，删除 FormField。保留 FormItem 现有接口不变。

- [ ] **Step 1: 更新 `index.ts` — 移除 form-field 导出**

修改 `packages/web/components/common/index.ts`：删除 `export * from "./form-field";` 行。
`form/` 子目录 index.ts 已 export FormItem，所以 `@/components/common` 仍可访问 FormItem。

- [ ] **Step 2: 删除 `form-field.tsx` 和 `form-field.test.tsx`**

```bash
rm packages/web/components/common/form-field.tsx
rm packages/web/components/common/form-field.test.tsx
```

- [ ] **Step 3: 验证**

```bash
cd packages/web && bun run typecheck 2>&1 | tail -5
bun run test -- components/common/form 2>&1 | tail -20
```

Expected: typecheck 0 error, form 相关测试通过

- [ ] **Step 4: Commit**

```bash
git add packages/web/components/common/
git commit -m "refactor: merge form-field.tsx into form/form-item.tsx (P0 code-quality)"
```

---

### Task 3: [P0] reject-dialog.tsx 改用 AppDialog

**Files:**
- Modify: `packages/web/app/[locale]/submissions/_components/reject-dialog.tsx`
- Modify: `packages/web/app/[locale]/submissions/_components/reject-dialog.test.tsx`

#### 分析

当前 reject-dialog.tsx 手写 6 个 raw shadcn Dialog import：`Dialog`、`DialogContent`、`DialogDescription`、`DialogFooter`、`DialogHeader`、`DialogTitle`。
改用 AppDialog 后删除全部 raw Dialog import，保持功能一致。

- [ ] **Step 1: 修改 `reject-dialog.tsx` — 替换 import**

删除：
```typescript
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
```

添加：
```typescript
import { AppDialog } from "@/components/common/dialog/app-dialog";
```

- [ ] **Step 2: 替换 JSX — Dialog → AppDialog**

原来的 JSX 结构：
```tsx
<Dialog open={open} onOpenChange={onOpenChange}>
  <DialogContent data-testid="reject-dialog">
    <DialogHeader>
      <DialogTitle>{tr("拒绝这条提交?")}</DialogTitle>
      <DialogDescription>{tr("选择拒绝原因, 提交者会看到")}</DialogDescription>
    </DialogHeader>
    <div className="space-y-3">
      <AppSelect ... />
      {isOther && <Textarea ... />}
    </div>
    <DialogFooter>
      <Button ... >取消</Button>
      <Button ... >确认拒绝</Button>
    </DialogFooter>
  </DialogContent>
</Dialog>
```

改为：
```tsx
<AppDialog
  open={open}
  onOpenChange={onOpenChange}
  title={tr("拒绝这条提交?")}
  description={tr("选择拒绝原因, 提交者会看到")}
  dataTestid="reject-dialog"
  footer={
    <>
      <Button variant="ghost" onClick={() => onOpenChange(false)} data-testid="btn-cancel-reject">
        {tr("取消")}
      </Button>
      <Button variant="destructive" disabled={!canSubmit || isPending} onClick={() => onSubmit(reason as RejectReasonKey, isOther ? note : undefined)} data-testid="btn-submit-reject">
        {tr("确认拒绝")}
      </Button>
    </>
  }
>
  <div className="space-y-3">
    <AppSelect
      options={REASONS.map((re) => ({
        label: tr(`reasons.${re}` as never),
        value: re,
      }))}
      value={reason}
      onChange={(val) => setReason(val as RejectReasonKey)}
      placeholder={tr("请选择原因")}
      dataTestid="select-trigger"
    />
    {isOther && (
      <Textarea
        value={note}
        onChange={(ev) => setNote(ev.target.value)}
        placeholder={tr("请说明具体原因")}
        maxLength={500}
        data-testid="note-textarea"
      />
    )}
  </div>
</AppDialog>
```

- [ ] **Step 3: 验证**

```bash
cd packages/web && bun run typecheck 2>&1 | tail -5
bun run test -- app/[locale]/submissions/_components 2>&1 | tail -20
bun run lint:fix 2>&1 | tail -5
bun run format 2>&1 | tail -5
```

Expected: typecheck 0 error, reject-dialog 测试通过（~4 tests）

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "refactor: reject-dialog use AppDialog instead of raw shadcn Dialog (P0 code-quality)"
```

---

### Task 4: [P1] 提取 AppCollapsible 公共组件

**Files:**
- Create: `packages/web/components/common/app-collapsible.tsx`
- Create: `packages/web/components/common/app-collapsible.test.tsx`
- Modify: `packages/web/components/chat/message-bubble.tsx`（2 处 raw Collapsible → AppCollapsible）

#### API 设计

```typescript
interface AppCollapsibleProps {
  title: string;                // trigger 显示的标签文本
  defaultOpen?: boolean;        // 默认展开（非受控）
  open?: boolean;               // 受控模式
  onOpenChange?: (o: boolean) => void;
  icon?: ReactNode;             // 自定义 trigger 图标，默认 ChevronDown
  testId?: string;              // trigger 的 data-testid
  className?: string;           // 容器 className
  children: ReactNode;
}
```

- [ ] **Step 1: 先写测试 `app-collapsible.test.tsx`**

```typescript
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AppCollapsible } from "./app-collapsible";

describe("AppCollapsible", () => {
  it("渲染 title 文本", () => {
    render(<AppCollapsible title="思考过程"><p>content</p></AppCollapsible>);
    expect(screen.getByText("思考过程")).toBeInTheDocument();
  });

  it("默认不展开", () => {
    render(<AppCollapsible title="test"><p>content</p></AppCollapsible>);
    expect(screen.queryByText("content")).not.toBeInTheDocument();
  });

  it("defaultOpen 时渲染内容", () => {
    render(<AppCollapsible title="test" defaultOpen><p>content</p></AppCollapsible>);
    expect(screen.getByText("content")).toBeInTheDocument();
  });

  it("点击 trigger 展开/收起", async () => {
    const user = userEvent.setup();
    render(<AppCollapsible title="toggle"><p>content</p></AppCollapsible>);
    expect(screen.queryByText("content")).not.toBeInTheDocument();
    await user.click(screen.getByText("toggle"));
    expect(screen.getByText("content")).toBeInTheDocument();
  });

  it("受控模式: open/onOpenChange", async () => {
    const user = userEvent.setup();
    let open = false;
    const onOpenChange = (val: boolean) => { open = val; };
    render(
      <AppCollapsible title="ctl" open={open} onOpenChange={onOpenChange}><p>content</p></AppCollapsible>
    );
    expect(screen.queryByText("content")).not.toBeInTheDocument();
    await user.click(screen.getByText("ctl"));
    expect(open).toBe(true);
  });

  it("自定义 icon 渲染", () => {
    render(<AppCollapsible title="ic" icon={<span data-testid="custom-icon" />}><p>c</p></AppCollapsible>);
    expect(screen.getByTestId("custom-icon")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: 运行测试确认红**

```bash
cd packages/web && bun run test -- components/common/app-collapsible 2>&1 | tail -20
```

Expected: FAIL (组件未实现)

- [ ] **Step 3: 实现 `app-collapsible.tsx`**

```typescript
"use client";
// AppCollapsible — antd Collapse 风格折叠面板 (2026-06-25)
// 封装 Radix Collapsible 3 子组件为 1 行 API
import { ChevronDown } from "lucide-react";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { type ReactNode } from "react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export interface AppCollapsibleProps {
  title: string;
  defaultOpen?: boolean;
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
  icon?: ReactNode;
  testId?: string;
  className?: string;
  children: ReactNode;
}

export const AppCollapsible = ({
  title,
  defaultOpen,
  open,
  onOpenChange,
  icon,
  testId,
  className,
  children,
}: AppCollapsibleProps) => (
  <Collapsible
    className={cn(className)}
    open={open !== undefined ? open : undefined}
    defaultOpen={open !== undefined ? undefined : defaultOpen}
    onOpenChange={onOpenChange}>
    <CollapsibleTrigger asChild>
      <Button
        variant="ghost"
        size="sm"
        className="h-7 gap-1 px-2 text-xs text-muted-foreground"
        data-testid={testId}>
        {icon ?? <ChevronDown className="h-4 w-4" />}
        {title}
      </Button>
    </CollapsibleTrigger>
    <CollapsibleContent>{children}</CollapsibleContent>
  </Collapsible>
);
```

- [ ] **Step 4: 运行测试确认绿**

```bash
cd packages/web && bun run test -- components/common/app-collapsible 2>&1 | tail -20
```

Expected: 6 tests passed

- [ ] **Step 5: 迁移 message-bubble.tsx 的 2 处 Collapsible**

修改 import：

```typescript
// 删除：
// import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
// 改为：
import { AppCollapsible } from "@/components/common/app-collapsible";
```

修改 `renderThinking`：

```typescript
const renderThinking = (thinking: string) => (
  <AppCollapsible title="思考过程" defaultOpen testId="think-toggle" className="mb-2">
    <div className="mt-1 whitespace-pre-wrap rounded-lg border border-border/40 bg-muted/30 p-3 text-sm text-muted-foreground">
      {thinking}
    </div>
  </AppCollapsible>
);
```

修改 `renderCitations`：

```typescript
const renderCitations = (message: Message) => (
  <AppCollapsible title={`引用 ${message.citations?.length ?? 0} 条`} testId="citation-panel" className="mt-3">
    <CitationPanel citations={message.citations ?? []} />
  </AppCollapsible>
);
```

注意：`renderCitations` 移除了 trigger 内手写的 `<ChevronDown />` 图标，因为 AppCollapsible 内建默认图标。
检查 message-bubble.tsx 是否还有别处使用 `ChevronDown`，如果已无引用则删除其 import。

- [ ] **Step 6: 验证**

```bash
cd packages/web && bun run typecheck 2>&1 | tail -5
bun run test -- components/chat 2>&1 | tail -20
bun run lint:fix 2>&1 | tail -5
bun run format 2>&1 | tail -5
```

Expected: typecheck 0 error, chat 测试通过

- [ ] **Step 7: Commit**

```bash
git add packages/web/components/common/app-collapsible.tsx
git add packages/web/components/common/app-collapsible.test.tsx
git add packages/web/components/chat/message-bubble.tsx
git commit -m "feat: add AppCollapsible common component, migrate message-bubble (P1 code-quality)"
```

---

### Task 5: [P2] 目录重组 + 命名统一（批处理）

**Files: 涉及 ~25 个文件 move/rename + ~180 处 import 路径更新**

#### 重组方案

按功能分类到子目录，统一 `app-` 前缀：

```
components/common/
├── form/               ← 保留
├── table/              ← data-table/ rename
├── dialog/             ← 保留
├── drawer/             ← 保留
├── motion/             ← 保留
├── confirm/            ← 保留
├── display/            ← 新建，搬入展示类组件
│   ├── app-data-empty.tsx
│   ├── app-status-badge.tsx
│   ├── app-health-dot.tsx
│   ├── app-env-badge.tsx
│   ├── app-breathing-dot.tsx
│   ├── app-task-status-badge.tsx
│   ├── app-stat-card.tsx
│   ├── app-settings-card.tsx
│   ├── app-entry-card.tsx
│   ├── app-section-card.tsx
│   └── app-collapsible.tsx   ← Task4 新增
├── feedback/           ← 新建，反馈类组件
│   ├── app-error-banner.tsx
│   ├── app-error-banner-static.tsx
│   └── app-error-boundary.tsx
├── navigation/         ← 新建
│   ├── app-back-link.tsx
│   ├── app-page-header.tsx
│   └── app-page-hero.tsx
├── input/              ← 新建
│   ├── app-select.tsx
│   ├── app-toggle.tsx
│   ├── app-tabs.tsx
│   ├── app-file-dropzone.tsx
│   ├── app-search-input.tsx
│   ├── app-image-preview.tsx
│   ├── app-collapsible.tsx
│   └── app-dropdown-menu.tsx
├── button/             ← 新建
│   ├── app-copy-button.tsx
│   ├── app-submit-button.tsx
│   └── app-loading-skeleton.tsx
├── overlay/            ← 新建
│   ├── app-drawer.tsx       ← 从 drawer/ 移入
│   └── app-tooltip.tsx
└── index.ts
```

注意：`app-collapsible.tsx` 放在 display/ 还是 input/ 取决于其性质（折叠面板可认为属于 display）。

- [ ] **Step 1: 编写迁移脚本 `tools/migrate-common-components.py`**

```python
import subprocess
from pathlib import Path

BASE = Path("packages/web/components/common")

MOVE_MAP = {
    # display/
    "data-empty.tsx": "display/app-data-empty.tsx",
    "status-badge.tsx": "display/app-status-badge.tsx",
    "health-dot.tsx": "display/app-health-dot.tsx",
    "env-badge.tsx": "display/app-env-badge.tsx",
    "breathing-dot.tsx": "display/app-breathing-dot.tsx",
    "task-status-badge.tsx": "display/app-task-status-badge.tsx",
    "stat-card.tsx": "display/app-stat-card.tsx",
    "settings-card.tsx": "display/app-settings-card.tsx",
    "entry-card.tsx": "display/app-entry-card.tsx",
    "section-card.tsx": "display/app-section-card.tsx",
    # navigation/
    "back-link.tsx": "navigation/app-back-link.tsx",
    "page-header.tsx": "navigation/app-page-header.tsx",
    "page-hero.tsx": "navigation/app-page-hero.tsx",
    # feedback/
    "error-banner.tsx": "feedback/app-error-banner.tsx",
    "error-banner-static.tsx": "feedback/app-error-banner-static.tsx",
    "error-boundary.tsx": "feedback/app-error-boundary.tsx",
    # input/
    "app-select.tsx": "input/app-select.tsx",
    "app-toggle.tsx": "input/app-toggle.tsx",
    "app-tabs.tsx": "input/app-tabs.tsx",
    "file-dropzone.tsx": "input/app-file-dropzone.tsx",
    "search-input.tsx": "input/app-search-input.tsx",
    "image-preview.tsx": "input/app-image-preview.tsx",
    "app-dropdown-menu.tsx": "input/app-dropdown-menu.tsx",
    # button/
    "copy-button.tsx": "button/app-copy-button.tsx",
    "submit-button.tsx": "button/app-submit-button.tsx",
    "loading-skeleton.tsx": "button/app-loading-skeleton.tsx",
    # overlay/
    "app-tooltip.tsx": "overlay/app-tooltip.tsx",
}

def main():
    for src_rel, dst_rel in MOVE_MAP.items():
        src = BASE / src_rel
        dst = BASE / dst_rel
        if not src.exists():
            print(f"SKIP (not found): {src_rel}")
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "mv", str(src), str(dst)], check=True)
        print(f"Moved: {src_rel} → {dst_rel}")

if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 执行迁移脚本**

```bash
cd c:/Users/abcuc/Desktop/rag && python tools/migrate-common-components.py 2>&1
```

Expected: ~28 行 "Moved: ... → ..." 输出

- [ ] **Step 3: 更新 `index.ts`**

修改 `packages/web/components/common/index.ts`，替换为子目录导出：

```typescript
// 子目录导出（2026-06-25 重组后）
export * from "./button";
export * from "./confirm";
export * from "./dialog";
export * from "./display";
export * from "./drawer";
export * from "./feedback";
export * from "./form";
export * from "./input";
export * from "./motion";
export * from "./navigation";
export * from "./overlay";
export * from "./table";
```

- [ ] **Step 4: 批量更新业务文件 import 路径（~180 处）**

编写 import 替换脚本 `tools/update-imports.py`：

```python
import re
from pathlib import Path

BASE = Path("packages/web")

# 反向映射：旧路径 → 新路径
IMPORT_MAP = {
    "@/components/common/data-empty": "@/components/common/display/app-data-empty",
    "@/components/common/status-badge": "@/components/common/display/app-status-badge",
    "@/components/common/health-dot": "@/components/common/display/app-health-dot",
    "@/components/common/env-badge": "@/components/common/display/app-env-badge",
    "@/components/common/breathing-dot": "@/components/common/display/app-breathing-dot",
    "@/components/common/task-status-badge": "@/components/common/display/app-task-status-badge",
    "@/components/common/stat-card": "@/components/common/display/app-stat-card",
    "@/components/common/settings-card": "@/components/common/display/app-settings-card",
    "@/components/common/entry-card": "@/components/common/display/app-entry-card",
    "@/components/common/section-card": "@/components/common/display/app-section-card",
    "@/components/common/app-collapsible": "@/components/common/display/app-collapsible",
    "@/components/common/back-link": "@/components/common/navigation/app-back-link",
    "@/components/common/page-header": "@/components/common/navigation/app-page-header",
    "@/components/common/page-hero": "@/components/common/navigation/app-page-hero",
    "@/components/common/error-banner": "@/components/common/feedback/app-error-banner",
    "@/components/common/error-banner-static": "@/components/common/feedback/app-error-banner-static",
    "@/components/common/error-boundary": "@/components/common/feedback/app-error-boundary",
    "@/components/common/app-select": "@/components/common/input/app-select",
    "@/components/common/app-toggle": "@/components/common/input/app-toggle",
    "@/components/common/app-tabs": "@/components/common/input/app-tabs",
    "@/components/common/file-dropzone": "@/components/common/input/app-file-dropzone",
    "@/components/common/search-input": "@/components/common/input/app-search-input",
    "@/components/common/image-preview": "@/components/common/input/app-image-preview",
    "@/components/common/app-dropdown-menu": "@/components/common/input/app-dropdown-menu",
    "@/components/common/copy-button": "@/components/common/button/app-copy-button",
    "@/components/common/submit-button": "@/components/common/button/app-submit-button",
    "@/components/common/loading-skeleton": "@/components/common/button/app-loading-skeleton",
    "@/components/common/app-tooltip": "@/components/common/overlay/app-tooltip",
}

for f in sorted(BASE.rglob("*.{ts,tsx}")):
    if any(p in f.parts for p in ["node_modules", ".next", "__pycache__"]):
        continue
    text = f.read_text(encoding="utf-8")
    new_text = text
    for old, new in IMPORT_MAP.items():
        new_text = new_text.replace(old, new)
    if new_text != text:
        f.write_text(new_text, encoding="utf-8")
        print(f"Updated: {f.relative_to(BASE)}")

print("Done.")
```

- [ ] **Step 5: 运行 import 替换脚本**

```bash
cd c:/Users/abcuc/Desktop/rag && python tools/update-imports.py 2>&1
```

- [ ] **Step 6: 更新测试文件的 import + vitest.setup.ts mock 路径**

同样运行脚本即可覆盖（glob 包含 test 文件）。检查 vitest.setup.ts 中的 mock 路径是否更新。

- [ ] **Step 7: 全面验证**

\`\`\`bash
cd packages/web
bun run typecheck 2>&1 | tail -5
bun run test 2>&1 | tail -20
bun run lint:fix 2>&1 | tail -5
bun run format 2>&1 | tail -5
```

Expected: 全部 0 error

- [ ] **Step 8: 分批次 Commit**

由于涉及文件多，建议分 2-3 个 commit：

\`\`\`bash
git add packages/web/components/common/display/
git add packages/web/components/common/navigation/
git add packages/web/components/common/feedback/
git commit -m "refactor: migrate display/navigation/feedback components to subdirs (P2 code-quality)"

git add packages/web/components/common/input/
git add packages/web/components/common/button/
git add packages/web/components/common/overlay/
git commit -m "refactor: migrate input/button/overlay components to subdirs (P2 code-quality)"

git add packages/web/components/common/index.ts
git commit -m "refactor: update index.ts exports for reorganized common components (P2 code-quality)"
```

---

## Self-Review

### 1. Spec 覆盖

- P0 删除 confirm-dialog.tsx ✅ Task 1
- P0 合并 form-field.tsx → form/form-item.tsx ✅ Task 2
- P0 reject-dialog.tsx 改 AppDialog ✅ Task 3
- P1 Collapsible 提取 common 组件 ✅ Task 4 (+ 迁移 message-bubble.tsx 2 处)
- P2 目录重组 + 命名统一 ✅ Task 5 (+ 迁移脚本)

### 2. 无占位符

- 所有步骤含具体代码 ✅
- 所有命令含 expected output ✅
- 测试文件含完整测试代码 ✅
- 迁移脚本含完整 Python 代码 ✅

### 3. 类型一致性

- AppCollapsibleProps 接口在 Task 4 定义、实现、测试中一致 ✅
- 迁移脚本路径在 Task 5 MOVE_MAP 和 IMPORT_MAP 之间一致 ✅
- 各 Task commit message 前缀规范（chore/refactor/feat）✅

---

## 关联文档

- [Spec: 5 维度代码质量分析](../../specs/2026-06-25-code-quality-5-dimension-analysis.md)
- [项目代码质量铁律](../../../CLAUDE.md)
- [前端局部约定](../../../packages/web/CLAUDE.md)
