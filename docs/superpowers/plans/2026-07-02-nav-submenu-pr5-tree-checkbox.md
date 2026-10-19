# PR5 — Generic TreeCheckbox Component

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a generic, reusable `<TreeCheckbox<T>>` component that handles nested tree rendering with checkbox states (checked / indeterminate / unchecked). Decoupled from permission business logic — PR6 wires it to the role/page matrix.

**Files:**
- Create: `packages/web/components/common/display/tree-checkbox.tsx`
- Create: `packages/web/components/common/display/tree-checkbox.test.tsx`
- Create: `packages/web/components/common/display/index.ts` (if missing, re-export)

---

## Task 5.1: Check shadcn Checkbox availability

- [ ] **Step 1: Verify shadcn Checkbox component exists**

Run: `ls packages/web/components/ui/checkbox.tsx 2>/dev/null && echo "exists" || echo "missing"`

If `exists`: continue to Task 5.2.
If `missing`: per CLAUDE.md shadcn project, this should exist. If truly missing, install via:
```bash
cd packages/web && bunx shadcn@latest add checkbox
```

Then continue.

---

## Task 5.2: Add failing test for TreeCheckbox (TDD red)

**Files:**
- Create: `packages/web/components/common/display/tree-checkbox.test.tsx`

- [ ] **Step 1: Write failing test**

Create `packages/web/components/common/display/tree-checkbox.test.tsx`:

```tsx
/**
 * TreeCheckbox 通用组件测试 (2026-07-02 nav spec §5.3)
 * 验证: 树渲染 / indeterminate / toggle / 折叠 / 键盘可达.
 */
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { TreeCheckbox, type TreeCheckboxNode } from "./tree-checkbox";

interface ItemData {
  id: number;
  category: string;
}

const mkNode = (overrides: Partial<TreeCheckboxNode<ItemData>>): TreeCheckboxNode<ItemData> => ({
  key: "x",
  label: "X",
  children: [],
  ...overrides,
});

describe("TreeCheckbox", () => {
  it("渲染嵌套树结构", () => {
    const tree: TreeCheckboxNode<ItemData>[] = [
      mkNode({
        key: "admin",
        label: "管理中心",
        children: [
          mkNode({ key: "admin_users", label: "用户管理" }),
          mkNode({ key: "admin_dicts", label: "字典管理" }),
        ],
      }),
    ];
    render(<TreeCheckbox nodes={tree} checked={new Set()} indeterminate={new Set()} onToggle={() => {}} />);
    expect(screen.getByText("管理中心")).toBeInTheDocument();
    expect(screen.getByText("用户管理")).toBeInTheDocument();
    expect(screen.getByText("字典管理")).toBeInTheDocument();
  });

  it("父级 checkbox disabled (不可点, 按决策父级不入权限表)", () => {
    const tree: TreeCheckboxNode<ItemData>[] = [
      mkNode({
        key: "admin",
        label: "管理中心",
        children: [mkNode({ key: "admin_users", label: "用户管理" })],
      }),
    ];
    render(<TreeCheckbox nodes={tree} checked={new Set()} indeterminate={new Set()} onToggle={() => {}} />);
    const parentCheckbox = screen.getByRole("checkbox", { name: /管理中心/ });
    expect(parentCheckbox).toBeDisabled();
  });

  it("叶子 checkbox 可点, 触发 onToggle", async () => {
    const onToggle = vi.fn();
    const user = userEvent.setup();
    const tree: TreeCheckboxNode<ItemData>[] = [
      mkNode({
        key: "admin",
        label: "管理中心",
        children: [mkNode({ key: "admin_users", label: "用户管理" })],
      }),
    ];
    render(<TreeCheckbox nodes={tree} checked={new Set()} indeterminate={new Set()} onToggle={onToggle} />);
    const leafCheckbox = screen.getByRole("checkbox", { name: /用户管理/ });
    await user.click(leafCheckbox);
    expect(onToggle).toHaveBeenCalledWith("admin_users");
  });

  it("checked 集合里的 key → checkbox checked", () => {
    const tree: TreeCheckboxNode<ItemData>[] = [
      mkNode({
        key: "admin",
        label: "管理中心",
        children: [mkNode({ key: "admin_users", label: "用户管理" })],
      }),
    ];
    render(<TreeCheckbox nodes={tree} checked={new Set(["admin_users"])} indeterminate={new Set()} onToggle={() => {}} />);
    const leafCheckbox = screen.getByRole("checkbox", { name: /用户管理/ });
    expect(leafCheckbox).toBeChecked();
  });

  it("indeterminate 集合里的 key → checkbox indeterminate", () => {
    const tree: TreeCheckboxNode<ItemData>[] = [
      mkNode({
        key: "admin",
        label: "管理中心",
        children: [
          mkNode({ key: "admin_users", label: "用户管理" }),
          mkNode({ key: "admin_dicts", label: "字典管理" }),
        ],
      }),
    ];
    render(<TreeCheckbox nodes={tree} checked={new Set(["admin_users"])} indeterminate={new Set(["admin"])} onToggle={() => {}} />);
    const parentCheckbox = screen.getByRole("checkbox", { name: /管理中心/ });
    // indeterminate 通过 aria-checked="mixed" 表达
    expect(parentCheckbox).toHaveAttribute("aria-checked", "mixed");
  });

  it("Chevron 默认展开, 点击折叠", async () => {
    const user = userEvent.setup();
    const tree: TreeCheckboxNode<ItemData>[] = [
      mkNode({
        key: "admin",
        label: "管理中心",
        children: [mkNode({ key: "admin_users", label: "用户管理" })],
      }),
    ];
    render(<TreeCheckbox nodes={tree} checked={new Set()} indeterminate={new Set()} onToggle={() => {}} />);
    expect(screen.getByText("用户管理")).toBeInTheDocument();
    const chevron = screen.getByTestId("tree-chevron-admin");
    await user.click(chevron);
    expect(screen.queryByText("用户管理")).toBeNull();
  });

  it("键盘可达: Tab focus, Space toggle", async () => {
    const onToggle = vi.fn();
    const user = userEvent.setup();
    const tree: TreeCheckboxNode<ItemData>[] = [
      mkNode({
        key: "admin",
        label: "管理中心",
        children: [mkNode({ key: "admin_users", label: "用户管理" })],
      }),
    ];
    render(<TreeCheckbox nodes={tree} checked={new Set()} indeterminate={new Set()} onToggle={onToggle} />);
    const leafCheckbox = screen.getByRole("checkbox", { name: /用户管理/ });
    leafCheckbox.focus();
    expect(leafCheckbox).toHaveFocus();
    await user.keyboard(" ");
    expect(onToggle).toHaveBeenCalledWith("admin_users");
  });
});
```

- [ ] **Step 2: Run test to verify it fails (RED)**

Run: `cd packages/web && bun run test -- components/common/display/tree-checkbox.test.tsx`

Expected: FAIL — `tree-checkbox.tsx` not found.

- [ ] **Step 3: Commit failing test**

```bash
cd c:/doc/Code/rag
git add packages/web/components/common/display/tree-checkbox.test.tsx
git commit -m "test(nav): add TreeCheckbox failing tests (PR5/1)"
```

---

## Task 5.3: Implement TreeCheckbox component

**Files:**
- Create: `packages/web/components/common/display/tree-checkbox.tsx`

- [ ] **Step 1: Implement component**

Create `packages/web/components/common/display/tree-checkbox.tsx`:

```tsx
/**
 * TreeCheckbox: 通用树形 checkbox 组件 (2026-07-02 nav spec §5.3)
 *
 * 通用, 不耦合业务. 业务用法:
 * - 权限矩阵: checked = cell value, indeterminate = 子项部分勾
 * - 未来: 角色组 / 功能开关 / 标签
 *
 * 视觉规格 (spec §5.3):
 * - 缩进 24px/级
 * - 行高 32px
 * - 父级 label 加粗 + 600 字重
 * - hover 整行高亮 bg-muted/40
 */
"use client";
import { useState } from "react";
import { ChevronDown } from "lucide-react";
import { Checkbox } from "@/components/ui/checkbox";
import { cn } from "@/lib/utils";

export interface TreeCheckboxNode<T = unknown> {
  key: string;
  label: string;
  children?: TreeCheckboxNode<T>[];
  data?: T;
}

export interface TreeCheckboxProps<T = unknown> {
  nodes: TreeCheckboxNode<T>[];
  /** 已勾选的 key 集合 */
  checked: Set<string>;
  /** indeterminate 状态的 key 集合 (父级部分勾) */
  indeterminate: Set<string>;
  /** toggle 一个 key (一般是叶子, 父级 disabled) */
  onToggle: (key: string) => void;
  /** 自定义 label 渲染 (e.g. 加 icon / 翻译) */
  renderLabel?: (node: TreeCheckboxNode<T>) => React.ReactNode;
  /** 默认是否全部展开 (default true) */
  defaultExpanded?: boolean;
}

const INDENT_PX_PER_LEVEL = 24;
const ROW_HEIGHT_PX = 32;

export const TreeCheckbox = <T,>({
  nodes,
  checked,
  indeterminate,
  onToggle,
  renderLabel,
  defaultExpanded = true,
}: TreeCheckboxProps<T>) => {
  const [expanded, setExpanded] = useState<Set<string>>(() => {
    if (!defaultExpanded) return new Set();
    return new Set(nodes.map((n) => n.key));
  });

  const toggleExpanded = (key: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  return (
    <div role="tree" className="flex flex-col">
      {nodes.map((node) => (
        <TreeRow
          key={node.key}
          node={node}
          level={0}
          checked={checked}
          indeterminate={indeterminate}
          onToggle={onToggle}
          renderLabel={renderLabel}
          expanded={expanded}
          onToggleExpand={toggleExpanded}
        />
      ))}
    </div>
  );
};

interface TreeRowProps<T> {
  node: TreeCheckboxNode<T>;
  level: number;
  checked: Set<string>;
  indeterminate: Set<string>;
  onToggle: (key: string) => void;
  renderLabel?: (node: TreeCheckboxNode<T>) => React.ReactNode;
  expanded: Set<string>;
  onToggleExpand: (key: string) => void;
}

const TreeRow = <T,>({
  node,
  level,
  checked,
  indeterminate,
  onToggle,
  renderLabel,
  expanded,
  onToggleExpand,
}: TreeRowProps<T>) => {
  const hasChildren = node.children && node.children.length > 0;
  const isExpanded = expanded.has(node.key);
  const isChecked = checked.has(node.key);
  const isIndeterminate = indeterminate.has(node.key);
  // 父级 checkbox 永远 disabled (按决策父级不入权限表)
  const isDisabled = hasChildren === true;

  return (
    <div role="treeitem" aria-expanded={hasChildren ? isExpanded : undefined}>
      <div
        className="flex items-center gap-2 rounded-md px-2 hover:bg-muted/40"
        style={{ paddingLeft: `${level * INDENT_PX_PER_LEVEL + 8}px`, minHeight: `${ROW_HEIGHT_PX}px` }}
      >
        {hasChildren ? (
          <button
            type="button"
            onClick={() => onToggleExpand(node.key)}
            data-testid={`tree-chevron-${node.key}`}
            aria-label={isExpanded ? "折叠" : "展开"}
            className="flex h-5 w-5 items-center justify-center"
          >
            <ChevronDown
              className={cn("h-3 w-3 transition-transform", isExpanded ? "rotate-0" : "-rotate-90")}
            />
          </button>
        ) : (
          <span className="inline-block h-5 w-5" />
        )}
        <Checkbox
          checked={isIndeterminate ? "indeterminate" : isChecked}
          disabled={isDisabled}
          onCheckedChange={() => onToggle(node.key)}
          aria-label={node.label}
        />
        <span className={cn(hasChildren && "font-semibold")}>{renderLabel ? renderLabel(node) : node.label}</span>
      </div>
      {hasChildren && isExpanded && (
        <div role="group">
          {node.children!.map((child) => (
            <TreeRow
              key={child.key}
              node={child}
              level={level + 1}
              checked={checked}
              indeterminate={indeterminate}
              onToggle={onToggle}
              renderLabel={renderLabel}
              expanded={expanded}
              onToggleExpand={onToggleExpand}
            />
          ))}
        </div>
      )}
    </div>
  );
};
```

- [ ] **Step 2: Run test to verify GREEN**

Run: `cd packages/web && bun run test -- components/common/display/tree-checkbox.test.tsx`

Expected: 7 tests PASS.

- [ ] **Step 3: Run lint + typecheck**

Run: `cd packages/web && bun run lint:fix -- components/common/display/tree-checkbox.tsx && bun run typecheck`

Expected: 0 errors.

- [ ] **Step 4: Commit TreeCheckbox**

```bash
cd c:/doc/Code/rag
git add packages/web/components/common/display/tree-checkbox.tsx
git commit -m "feat(nav): add generic TreeCheckbox component (PR5/2)

Decoupled from business. 7 tests green. Indeterminate support,
keyboard accessible, collapsible rows."
```

---

## Task 5.4: Update display/index.ts (if needed)

- [ ] **Step 1: Check display index**

Run: `cat packages/web/components/common/display/index.ts 2>/dev/null || echo "missing"`

- [ ] **Step 2: Add TreeCheckbox export if index exists**

If `index.ts` exists, append:

```typescript
export { TreeCheckbox, type TreeCheckboxNode, type TreeCheckboxProps } from "./tree-checkbox";
```

- [ ] **Step 3: Run final tests**

Run: `cd packages/web && bun run test -- components/common/display/ 2>&1 | tail -10`

Expected: All tests pass.

- [ ] **Step 4: Commit index update if any**

```bash
cd c:/doc/Code/rag
git add packages/web/components/common/display/index.ts
git commit -m "chore(nav): export TreeCheckbox from display index (PR5/3)"
```

---

## PR5 Definition of Done

- [ ] `<TreeCheckbox<T>>` generic component implemented + 7 tests green
- [ ] Visual spec met: 24px/级 indent, 32px row height, parent font-semibold
- [ ] Indeterminate state via shadcn Checkbox "indeterminate" prop
- [ ] Keyboard accessible (Space toggles)
- [ ] Ready for PR6 (wire to permission matrix)