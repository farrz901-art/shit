# PR6 — Permission Matrix Tree UI

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor `/admin/permissions` matrix from flat table to tree-shaped checkbox UI. Each role shows a tree of page_keys (parent → children), with parent disabled, leaves toggleable. Reuse existing `usePermissionsTable` hook data flow; only swap the UI renderer.

**Files:**
- Modify: `packages/web/app/[locale]/admin/permissions/_hooks/use-permissions-table.ts` (add `tree` getter + indeterminate helpers)
- Modify: `packages/web/app/[locale]/admin/permissions/_components/permissions-table.tsx` (replace Table with TreeCheckbox)
- Modify: `packages/web/app/[locale]/admin/permissions/_components/permissions-admin-client.tsx` (pass `pages` as PageMeta[] instead of MatrixPage[])
- Modify: `packages/web/app/[locale]/admin/permissions/page.tsx` (RSC, propagate data shape)

---

## Task 6.1: Understand current data flow

- [ ] **Step 1: Read current RSC + client wrapper**

Run:
```bash
cat packages/web/app/[locale]/admin/permissions/page.tsx
echo "---"
cat packages/web/app/[locale]/admin/permissions/_components/permissions-admin-client.tsx
```

Note the shape: `pages: MatrixPage[]` (with `key`, `label_zh`, `label_en`, `path`).

- [ ] **Step 2: Find the source feeding pages**

Run: `grep -r "MatrixPage\b" packages/web/app/[locale]/admin/permissions/ -l`

Note where pages originate (likely server-side from API response, transformed to MatrixPage[]).

- [ ] **Step 3: Decide migration strategy**

Per spec §5.4: keep `usePermissionsTable` hook data flow; only swap UI.

**Decision**: Add `PageMeta[]` (new prop type) alongside existing `pages: MatrixPage[]`. The new prop carries the tree-shape data; `MatrixPage[]` stays for any old consumers.

---

## Task 6.2: Extend usePermissionsTable with tree helpers

**Files:**
- Modify: `packages/web/app/[locale]/admin/permissions/_hooks/use-permissions-table.ts`

- [ ] **Step 1: Add tree computation**

Append the following to `usePermissionsTable.ts` (at the bottom, before the closing of file):

```typescript
// (2026-07-02 nav spec §5.4) 扩展: 提供 tree + indeterminate 计算, 给 TreeCheckbox UI 用
import { buildNavTree, type NavTree } from "@/lib/nav/build-nav-tree";
import type { PageMeta } from "@/lib/auth/permission-types";

/** 把 MatrixPage[] + metadata 转成 PageMeta[] (供 buildNavTree 用) */
export const pagesToPageMeta = (pages: MatrixPage[]): PageMeta[] =>
  pages.map((p) => ({
    key: p.key,
    label_zh: p.label_zh,
    label_en: p.label_en,
    path: p.path,
    metadata: (p as MatrixPage & { metadata?: PageMeta["metadata"] }).metadata,
  }));

/** 树形勾选: 给一个 role 计算 parent 节点的 indeterminate 集合 */
export const computeIndeterminate = (
  navTree: NavTree,
  role: string,
  getCellValue: (role: string, page: string) => boolean,
): Set<string> => {
  const result = new Set<string>();
  for (const root of navTree.roots) {
    if (root.children.length === 0) continue;
    const checkedCount = root.children.filter((c) => getCellValue(role, c.key)).length;
    if (checkedCount > 0 && checkedCount < root.children.length) {
      result.add(root.key);
    }
  }
  return result;
};

/** 树形勾选: 给一个 role 计算 checked 集合 (含父级, 当父级自己 allowed 时) */
export const computeChecked = (
  navTree: NavTree,
  role: string,
  getCellValue: (role: string, page: string) => boolean,
): Set<string> => {
  const result = new Set<string>();
  for (const root of navTree.roots) {
    if (root.children.length === 0) {
      // 叶子顶级
      if (getCellValue(role, root.key)) result.add(root.key);
    } else {
      // 父级: 自己 allowed 时 checked; 否则子项各自判断
      if (getCellValue(role, root.key)) {
        result.add(root.key);
        // 子项也算 checked (即使 cell value 是 false)
        for (const child of root.children) result.add(child.key);
      } else {
        for (const child of root.children) {
          if (getCellValue(role, child.key)) result.add(child.key);
        }
      }
    }
  }
  return result;
};
```

- [ ] **Step 2: Run existing hook tests**

Run: `cd packages/web && bun run test -- app/[locale]/admin/permissions/ 2>&1 | tail -10`

Expected: existing tests still pass (no behavior change, only new exports).

- [ ] **Step 3: Commit helper functions**

```bash
cd c:/doc/Code/rag
git add packages/web/app/[locale]/admin/permissions/_hooks/use-permissions-table.ts
git commit -m "feat(perm): add pagesToPageMeta + computeIndeterminate/Checked (PR6/1)

Tree helpers for new matrix UI. Pure functions, easy to test."
```

---

## Task 6.3: Add failing test for new matrix tree UI

**Files:**
- Modify: `packages/web/app/[locale]/admin/permissions/_components/permissions-table.tsx` (new tests inline OR new file)

- [ ] **Step 1: Write test file**

Create `packages/web/app/[locale]/admin/permissions/_components/permissions-table-tree.test.tsx`:

```tsx
/**
 * PermissionsTable 树形 UI 测试 (2026-07-02 nav spec §5.4)
 * 验证: 树形渲染 / 父级 disabled / 叶子 toggle / indeterminate / super_admin 豁免.
 */
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { PermissionsTable } from "./permissions-table";
import type { MatrixPage, MatrixRole, RoleListItem } from "../_hooks/use-permissions-table";

vi.mock("next-intl", () => ({
  useTranslations: () => (key: string) => key,
}));

const mkRole = (name: string): MatrixRole => ({
  name,
  label_zh: name,
  label_en: name,
  is_system: name !== "custom",
});

const mkPage = (overrides: Partial<MatrixPage & { metadata?: { parent_id?: string; is_group?: boolean } }>): MatrixPage & {
  metadata?: { parent_id?: string; is_group?: boolean };
} => ({
  key: "x",
  label_zh: "X",
  label_en: "X",
  path: "/x",
  ...overrides,
});

const mkRoleList = (roles: MatrixRole[]): RoleListItem[] =>
  roles.map((r) => ({ ...r, is_deletable: !r.is_system, user_count: 0 }));

describe("PermissionsTable 树形", () => {
  it("树形渲染: 父级 + 子项都显示", () => {
    const roles = [mkRole("user")];
    const pages: ReturnType<typeof mkPage>[] = [
      mkPage({ key: "admin", label_zh: "管理中心", metadata: { is_group: true } }),
      mkPage({ key: "admin_users", label_zh: "用户管理", metadata: { parent_id: "admin" } }),
      mkPage({ key: "chat", label_zh: "对话" }),
    ];
    const matrix = { user: { admin: false, admin_users: true, chat: true } };
    render(
      <PermissionsTable
        roles={roles}
        roleList={mkRoleList(roles)}
        pages={pages}
        matrix={matrix}
        selectedRole={null}
        onSelectRole={() => {}}
        onSave={async () => {}}
        onEditRole={() => {}}
        onDeleteRole={() => {}}
        onCreateRole={() => {}}
      />,
    );
    expect(screen.getByText("管理中心")).toBeInTheDocument();
    expect(screen.getByText("用户管理")).toBeInTheDocument();
    expect(screen.getByText("对话")).toBeInTheDocument();
  });

  it("父级 checkbox disabled", () => {
    const roles = [mkRole("user")];
    const pages = [
      mkPage({ key: "admin", label_zh: "管理中心", metadata: { is_group: true } }),
      mkPage({ key: "admin_users", label_zh: "用户管理", metadata: { parent_id: "admin" } }),
    ];
    const matrix = { user: { admin: false, admin_users: true } };
    render(
      <PermissionsTable
        roles={roles}
        roleList={mkRoleList(roles)}
        pages={pages}
        matrix={matrix}
        selectedRole={null}
        onSelectRole={() => {}}
        onSave={async () => {}}
        onEditRole={() => {}}
        onDeleteRole={() => {}}
        onCreateRole={() => {}}
      />,
    );
    const adminCheckbox = screen.getByRole("checkbox", { name: /管理中心/ });
    expect(adminCheckbox).toBeDisabled();
  });

  it("叶子 toggle 调 onSave 提交 updates", async () => {
    const onSave = vi.fn(async () => {});
    const user = userEvent.setup();
    const roles = [mkRole("user")];
    const pages = [
      mkPage({ key: "admin", label_zh: "管理中心", metadata: { is_group: true } }),
      mkPage({ key: "admin_users", label_zh: "用户管理", metadata: { parent_id: "admin" } }),
    ];
    const matrix = { user: { admin: false, admin_users: false } };
    render(
      <PermissionsTable
        roles={roles}
        roleList={mkRoleList(roles)}
        pages={pages}
        matrix={matrix}
        selectedRole={null}
        onSelectRole={() => {}}
        onSave={onSave}
        onEditRole={() => {}}
        onDeleteRole={() => {}}
        onCreateRole={() => {}}
      />,
    );
    // 进入编辑模式
    await user.click(screen.getByTestId("permissions-edit-toggle"));
    // 点击 admin_users 叶子
    await user.click(screen.getByRole("checkbox", { name: /用户管理/ }));
    // 保存
    await user.click(screen.getByTestId("permissions-save"));
    expect(onSave).toHaveBeenCalled();
    const updates = onSave.mock.calls[0]?.[0];
    expect(updates).toContainEqual(
      expect.objectContaining({ role_name: "user", page_key: "admin_users", allowed: true }),
    );
  });

  it("super_admin 行所有 checkbox 永远 checked + disabled", () => {
    const roles = [mkRole("user"), mkRole("super_admin")];
    const pages = [
      mkPage({ key: "admin", label_zh: "管理中心", metadata: { is_group: true } }),
      mkPage({ key: "admin_users", label_zh: "用户管理", metadata: { parent_id: "admin" } }),
    ];
    const matrix = { user: {}, super_admin: { admin: true, admin_users: true } };
    render(
      <PermissionsTable
        roles={roles}
        roleList={mkRoleList(roles)}
        pages={pages}
        matrix={matrix}
        selectedRole={null}
        onSelectRole={() => {}}
        onSave={async () => {}}
        onEditRole={() => {}}
        onDeleteRole={() => {}}
        onCreateRole={() => {}}
      />,
    );
    // 切换到 super_admin 行
    const superAdminCheckbox = screen.getAllByRole("checkbox", { name: /用户管理/ })[0];
    expect(superAdminCheckbox).toBeChecked();
    expect(superAdminCheckbox).toBeDisabled();
  });

  it("indeterminate: 部分子项勾选时父级显示 mixed", () => {
    const roles = [mkRole("user")];
    const pages = [
      mkPage({ key: "admin", label_zh: "管理中心", metadata: { is_group: true } }),
      mkPage({ key: "admin_users", label_zh: "用户管理", metadata: { parent_id: "admin" } }),
      mkPage({ key: "admin_dicts", label_zh: "字典管理", metadata: { parent_id: "admin" } }),
    ];
    const matrix = { user: { admin: false, admin_users: true, admin_dicts: false } };
    render(
      <PermissionsTable
        roles={roles}
        roleList={mkRoleList(roles)}
        pages={pages}
        matrix={matrix}
        selectedRole={null}
        onSelectRole={() => {}}
        onSave={async () => {}}
        onEditRole={() => {}}
        onDeleteRole={() => {}}
        onCreateRole={() => {}}
      />,
    );
    const adminCheckbox = screen.getByRole("checkbox", { name: /管理中心/ });
    expect(adminCheckbox).toHaveAttribute("aria-checked", "mixed");
  });
});
```

- [ ] **Step 2: Run test to verify it fails (RED)**

Run: `cd packages/web && bun run test -- "app/[locale]/admin/permissions/_components/permissions-table-tree.test" 2>&1 | tail -30`

Expected: tests fail because old PermissionsTable doesn't render tree.

- [ ] **Step 3: Commit failing tests**

```bash
cd c:/doc/Code/rag
git add "packages/web/app/[locale]/admin/permissions/_components/permissions-table-tree.test.tsx"
git commit -m "test(perm): add tree UI failing tests (PR6/2)"
```

---

## Task 6.4: Refactor PermissionsTable to tree UI

**Files:**
- Modify: `packages/web/app/[locale]/admin/permissions/_components/permissions-table.tsx`

- [ ] **Step 1: Replace Table with TreeCheckbox**

Replace entire file content with:

```tsx
"use client";
// PermissionsTable — 树形权限矩阵 (2026-07-02 nav spec §5)
// 旧版用 Table, 现改用 TreeCheckbox. 仍复用 usePermissionsTable hook 的数据流.
import { Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useTranslations } from "next-intl";
import {
  usePermissionsTable,
  computeChecked,
  computeIndeterminate,
  pagesToPageMeta,
  type MatrixPage,
  type MatrixRole,
  type MatrixUpdate,
  type RoleListItem,
} from "../_hooks/use-permissions-table";
import { TreeCheckbox, type TreeCheckboxNode } from "@/components/common/display/tree-checkbox";
import { buildNavTree } from "@/lib/nav/build-nav-tree";

export {
  type MatrixPage,
  type MatrixRole,
  type MatrixUpdate,
  type RoleListItem,
} from "../_hooks/use-permissions-table";

export interface PermissionsTableProps {
  roles: MatrixRole[];
  roleList: RoleListItem[];
  pages: MatrixPage[];
  matrix: Record<string, Record<string, boolean>>;
  selectedRole: string | null;
  onSelectRole: (name: string | null) => void;
  onSave: (updates: MatrixUpdate[]) => Promise<void>;
  onEditRole: (name: string) => void;
  onDeleteRole: (name: string) => void;
  onCreateRole: () => void;
}

const SUPER_ADMIN_ROLE = "super_admin";

export const PermissionsTable = ({
  roles,
  roleList,
  pages,
  matrix,
  selectedRole,
  onSelectRole,
  onSave,
  onEditRole,
  onDeleteRole,
  onCreateRole,
}: PermissionsTableProps) => {
  const translate = useTranslations();
  const { isEditMode, search, filteredRoles, dirtyCount, getCellValue, toggle, handlers } =
    usePermissionsTable(roles, matrix, onSave);

  const ZERO = 0;

  // (2026-07-02) 一次性建树, 跨 role 复用
  const navTree = buildNavTree(pagesToPageMeta(pages));
  const treeNodes: TreeCheckboxNode[] = navTree.roots.map((root) => ({
    key: root.key,
    label: translate(root.label_zh),
    children: root.children.map((c) => ({
      key: c.key,
      label: translate(c.label_zh),
    })),
  }));

  return (
    <div className="space-y-4">
      {/* Toolbar (不变) */}
      <div className="flex flex-wrap items-center justify-between gap-2">
        <Input
          placeholder={translate("搜索角色…")}
          value={search}
          onChange={handlers.searchChange}
          className="max-w-xs"
          data-testid="permissions-search"
        />
        <div className="flex items-center gap-2">
          {isEditMode && (
            <>
              <span className="text-xs text-status-warning">
                {translate("未保存")} ({dirtyCount})
              </span>
              <Button variant="ghost" onClick={handlers.cancel}>
                {translate("取消")}
              </Button>
            </>
          )}
          <Button
            variant={isEditMode ? "default" : "outline"}
            onClick={handlers.editToggle}
            data-testid="permissions-edit-toggle"
          >
            {isEditMode ? translate("退出编辑") : translate("编辑")}
          </Button>
          <Button onClick={onCreateRole} data-testid="permissions-create-role">
            <Plus className="mr-1 h-4 w-4" />
            {translate("新建角色")}
          </Button>
        </div>
      </div>

      {/* Edit mode banner */}
      {isEditMode && (
        <div className="flex items-center justify-between rounded-lg border border-status-warning/30 bg-status-warning/5 px-4 py-2 text-sm">
          <span className="font-medium text-status-warning">
            {translate("编辑模式")} · {translate("修改不会立即生效, 点击保存后提交")}
          </span>
          <Button
            onClick={handlers.save}
            disabled={dirtyCount === ZERO}
            data-testid="permissions-save"
          >
            {translate("保存更改")}
          </Button>
        </div>
      )}

      {/* (2026-07-02) 角色列表 + 树形 matrix 组合 */}
      <div className="space-y-4">
        {filteredRoles.map((role) => {
          const checked = computeChecked(navTree, role.name, getCellValue);
          const indeterminate = computeIndeterminate(navTree, role.name, getCellValue);
          const isSuperAdmin = role.name === SUPER_ADMIN_ROLE;
          return (
            <div
              key={role.name}
              data-testid={`permission-role-${role.name}`}
              className={`rounded-lg border p-4 ${
                selectedRole === role.name ? "border-status-info/40 bg-status-info/5" : "border-border/60 bg-card/40"
              } ${isSuperAdmin ? "opacity-80" : ""} cursor-pointer`}
              onClick={() => onSelectRole(role.name)}
            >
              <div className="mb-3 flex items-center justify-between">
                <span className="text-base font-semibold">{translate(role.label_zh)}</span>
                {isSuperAdmin && (
                  <span className="text-xs text-status-info">{translate("超级管理员 (所有权限)")}</span>
                )}
              </div>
              <TreeCheckbox
                nodes={treeNodes}
                checked={isSuperAdmin ? new Set(treeNodes.flatMap((n) => [n.key, ...(n.children?.map((c) => c.key) ?? [])])) : checked}
                indeterminate={isSuperAdmin ? new Set() : indeterminate}
                onToggle={(key) => {
                  if (!isEditMode) return;
                  toggle(role.name, key);
                }}
              />
            </div>
          );
        })}
      </div>
    </div>
  );
};
```

- [ ] **Step 2: Run test to verify GREEN**

Run: `cd packages/web && bun run test -- "app/[locale]/admin/permissions/_components/permissions-table-tree.test" 2>&1 | tail -30`

Expected: 5 tests pass.

- [ ] **Step 3: Run existing permissions tests (may have breakage)**

Run: `cd packages/web && bun run test -- "app/[locale]/admin/permissions/" 2>&1 | tail -30`

Expected: existing tests pass (some may need updates due to UI change).

If existing tests break:
- Read the error
- Update existing test assertions to use new selectors (e.g. `permission-role-${name}` instead of `permissions-matrix`)
- Common breakage: old tests checking `<Table>` → new tests use `<TreeCheckbox>`

- [ ] **Step 4: Run typecheck + lint**

Run: `cd packages/web && bun run typecheck && bun run lint:fix`

Expected: 0 errors.

- [ ] **Step 5: Commit PermissionsTable refactor**

```bash
cd c:/doc/Code/rag
git add "packages/web/app/[locale]/admin/permissions/_components/permissions-table.tsx" "packages/web/app/[locale]/admin/permissions/_components/permissions-table-tree.test.tsx"
git commit -m "feat(perm): refactor PermissionsTable to tree UI (PR6/3)

5 new tests green. Old table replaced with TreeCheckbox.
Reuses usePermissionsTable hook data flow unchanged."
```

---

## Task 6.5: Wire pages data through page.tsx

**Files:**
- Modify: `packages/web/app/[locale]/admin/permissions/page.tsx`

- [ ] **Step 1: Check API response shape**

Run: `grep -r "MatrixPage\|metadata" packages/web/lib/api/permissions.ts 2>/dev/null | head -20`

Note: If API doesn't yet include `metadata` field, this is a backend change for PR6 — escalate to user.

- [ ] **Step 2: Update page.tsx to pass full PageMeta shape**

Read `packages/web/app/[locale]/admin/permissions/page.tsx`, ensure the `pages` prop passed to `<PermissionsAdminClient>` carries `metadata` (from `pagesToPageMeta` if needed). If API gives `MatrixPage[]` only, transform at the RSC level.

- [ ] **Step 3: Run full test suite**

Run: `cd packages/web && bun run test -- "app/[locale]/admin/permissions/" 2>&1 | tail -10`

Expected: all pass.

- [ ] **Step 4: Commit**

```bash
cd c:/doc/Code/rag
git add "packages/web/app/[locale]/admin/permissions/page.tsx"
git commit -m "feat(perm): wire PageMeta metadata through RSC (PR6/4)"
```

---

## Task 6.6: Verify no regressions

- [ ] **Step 1: Run full frontend test suite**

Run: `cd packages/web && bun run test 2>&1 | tail -15`

Expected: baseline + 15 (PR2) + 10 (PR3) + 6 (PR4) + 7 (PR5) + 5 (PR6) = 764 passed.

- [ ] **Step 2: Run lint + format**

Run: `cd packages/web && bun run lint && bun run format:check`

Expected: 0 errors.

- [ ] **Step 3: Final commit if any fix**

```bash
cd c:/doc/Code/rag
git status
# 如有 lint/format, git add -u && git commit -m "chore(pr6): final lint/format"
```

---

## PR6 Definition of Done

- [ ] TreeCheckbox integrated into PermissionsTable
- [ ] 5 new matrix tree tests green
- [ ] Indeterminate state working for parents
- [ ] super_admin row all-checked + disabled
- [ ] Edit mode + batch save still works
- [ ] All previous tests pass
- [ ] Ready for PR7 (cache invalidation on dict edit)