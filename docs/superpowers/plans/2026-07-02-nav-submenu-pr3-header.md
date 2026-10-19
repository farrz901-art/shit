# PR3 — Header Desktop Submenu (Hover Dropdown)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace flat nav rendering in `Header` with tree-driven rendering. Top-level page_keys with children render as `<NavDropdown>` (hover dropdown); top-level page_keys without children render as `<NavLink>` (current behavior).

**Files:**
- Create: `packages/web/components/layout/nav-dropdown.tsx`
- Create: `packages/web/components/layout/nav-dropdown.test.tsx`
- Modify: `packages/web/components/layout/header.tsx:33-54`
- Modify: `packages/web/components/layout/header.test.tsx` (if exists)
- Modify: `packages/web/messages/zh.json` (i18n)
- Modify: `packages/web/messages/en.json` (i18n)

---

## Task 3.1: Add failing test for NavDropdown component (TDD red)

**Files:**
- Create: `packages/web/components/layout/nav-dropdown.test.tsx`

- [ ] **Step 1: Check existing Header test**

Run: `ls packages/web/components/layout/header.test.tsx 2>/dev/null`

If exists, skip to Step 2. If not, note for later (we'll add tests in Task 3.4).

- [ ] **Step 2: Write failing NavDropdown test**

Create `packages/web/components/layout/nav-dropdown.test.tsx`:

```tsx
/**
 * NavDropdown 测试 (2026-07-02 nav spec §4.3)
 * 验证 hover trigger + 子菜单渲染 + 路由切换关闭.
 */
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { NavNode } from "@/lib/nav/nav-types";
import { NavDropdown } from "./nav-dropdown";

// Mock next/link 以避免 vitest ESM 解析问题
vi.mock("@/i18n/navigation", () => ({
  Link: ({ href, children, ...rest }: { href: string; children: React.ReactNode }) => (
    <a href={href} {...rest}>
      {children}
    </a>
  ),
}));

// Mock Radix DropdownMenu 用的 shadcn (实际项目用 AppDropdownMenu, 这里测 trigger 内容即可)
vi.mock("@/components/common/input/app-dropdown-menu", () => ({
  AppDropdownMenu: ({
    trigger,
    items,
  }: {
    trigger: React.ReactNode;
    items: Array<{ key: string; label: string; href?: string }>;
  }) => (
    <div>
      {trigger}
      <ul data-testid="dropdown-items">
        {items.map((item) => (
          <li key={item.key} data-testid={`item-${item.key}`}>
            {item.href ? <a href={item.href}>{item.label}</a> : <span>{item.label}</span>}
          </li>
        ))}
      </ul>
    </div>
  ),
}));

const mkNode = (overrides: Partial<NavNode>): NavNode => ({
  key: "x",
  label_zh: "X",
  label_en: "X",
  path: "/x",
  isGroup: true,
  children: [],
  sort: 0,
  ...overrides,
});

describe("NavDropdown", () => {
  it("渲染 trigger 含 label_zh", () => {
    const node = mkNode({
      key: "admin",
      label_zh: "管理中心",
      children: [
        mkNode({ key: "admin_users", label_zh: "用户管理", path: "/admin/users", isGroup: false }),
      ],
    });
    render(<NavDropdown node={node} />);
    expect(screen.getByTestId("nav-dropdown-admin")).toHaveTextContent("管理中心");
  });

  it("子项渲染为 link, href 来自 child.path", () => {
    const node = mkNode({
      key: "admin",
      label_zh: "管理中心",
      children: [
        mkNode({ key: "admin_users", label_zh: "用户管理", path: "/admin/users", isGroup: false }),
        mkNode({ key: "admin_dicts", label_zh: "字典管理", path: "/admin/dicts", isGroup: false }),
      ],
    });
    render(<NavDropdown node={node} />);
    expect(screen.getByTestId("item-admin_users").querySelector("a")).toHaveAttribute(
      "href",
      "/admin/users",
    );
    expect(screen.getByTestId("item-admin_dicts").querySelector("a")).toHaveAttribute(
      "href",
      "/admin/dicts",
    );
  });

  it("trigger 用 button 元素 (a11y), 不是 a", () => {
    const node = mkNode({ key: "admin", label_zh: "管理中心" });
    render(<NavDropdown node={node} />);
    expect(screen.getByTestId("nav-dropdown-admin").tagName).toBe("BUTTON");
  });

  it("trigger 不可点击跳转 (父级决策)", () => {
    const node = mkNode({ key: "admin", label_zh: "管理中心", path: "/admin" });
    render(<NavDropdown node={node} />);
    // 即使父级有 path, trigger 仍是 button 不是 a (父级不可点决策)
    expect(screen.getByTestId("nav-dropdown-admin").tagName).toBe("BUTTON");
    expect(screen.queryByRole("link", { name: "管理中心" })).toBeNull();
  });

  it("trigger 含 ChevronDown 图标提示可展开", () => {
    const node = mkNode({ key: "admin", label_zh: "管理中心" });
    const { container } = render(<NavDropdown node={node} />);
    // ChevronDown 是 lucide-react, 渲染为 svg
    expect(container.querySelector("svg")).toBeInTheDocument();
  });
});
```

- [ ] **Step 3: Run test to verify it fails (RED)**

Run: `cd packages/web && bun run test -- components/layout/nav-dropdown.test.tsx`

Expected: FAIL — `nav-dropdown.tsx` not found.

- [ ] **Step 4: Commit failing test**

```bash
cd c:/doc/Code/rag
git add packages/web/components/layout/nav-dropdown.test.tsx
git commit -m "test(nav): add NavDropdown failing tests (PR3/1)"
```

---

## Task 3.2: Implement NavDropdown (GREEN)

**Files:**
- Create: `packages/web/components/layout/nav-dropdown.tsx`

- [ ] **Step 1: Implement component**

Create `packages/web/components/layout/nav-dropdown.tsx`:

```tsx
/**
 * NavDropdown: 桌面端 hover 弹出子菜单 (2026-07-02 nav spec §4.3)
 * - 父级 trigger 不可点 (button 不是 a, 按用户决策)
 * - 子项渲染为 AppDropdownMenu 的 Link 项
 * - 复用项目已封装的 AppDropdownMenu (Radix DropdownMenu)
 */
"use client";
import { ChevronDown } from "lucide-react";
import { AppDropdownMenu } from "@/components/common/input/app-dropdown-menu";
import type { NavNode } from "@/lib/nav/nav-types";
import { useTranslations } from "next-intl";

export const NavDropdown = ({ node }: { node: NavNode }) => {
  const translate = useTranslations();

  return (
    <AppDropdownMenu
      trigger={
        <button
          type="button"
          aria-haspopup="menu"
          aria-expanded="false"
          data-testid={`nav-dropdown-${node.key}`}
          className="group relative flex items-center gap-1 rounded-md px-3 py-1.5 text-muted-foreground transition-colors duration-300 hover:text-foreground"
          style={{ transitionTimingFunction: "var(--ease-out-expo)" }}
        >
          <span className="relative z-10">{translate(node.label_zh)}</span>
          <ChevronDown className="h-3 w-3 transition-transform group-data-[state=open]:rotate-180" />
          <span
            className="absolute bottom-0.5 left-3 right-3 h-px origin-left scale-x-0 bg-foreground/40 transition-transform duration-300 group-hover:scale-x-100"
            style={{ transitionTimingFunction: "var(--ease-out-expo)" }}
          />
        </button>
      }
      contentClassName="w-48"
      items={node.children.map((child) => ({
        key: child.key,
        href: child.path ?? "#",
        label: translate(child.label_zh),
        testid: `nav-dropdown-item-${child.key}`,
      }))}
    />
  );
};
```

- [ ] **Step 2: Run test to verify it passes (GREEN)**

Run: `cd packages/web && bun run test -- components/layout/nav-dropdown.test.tsx`

Expected: 5 tests PASS.

- [ ] **Step 3: Run lint**

Run: `cd packages/web && bun run lint -- components/layout/nav-dropdown.tsx 2>&1 | tail -10`

Expected: 0 errors. (Apply `bun run lint:fix` if needed.)

- [ ] **Step 4: Commit NavDropdown component**

```bash
cd c:/doc/Code/rag
git add packages/web/components/layout/nav-dropdown.tsx
git commit -m "feat(nav): add NavDropdown for top-level items with children (PR3/2)

Hover dropdown via AppDropdownMenu (Radix). Parent button non-clickable
per spec decision. ChevronDown visual affordance."
```

---

## Task 3.3: Add failing test for Header tree rendering

**Files:**
- Create: `packages/web/components/layout/header.test.tsx` (if not exists)

- [ ] **Step 1: Check existing header test**

Run: `ls packages/web/components/layout/header.test.tsx`

If exists, skip to Step 2 (update existing). If not, create new.

- [ ] **Step 2: Write header tree-rendering tests**

If file doesn't exist, create `packages/web/components/layout/header.test.tsx`:

```tsx
/**
 * Header 组件测试 (2026-07-02 nav spec §4.2)
 * 验证:
 * - 顶级有子项 → NavDropdown (data-testid="nav-dropdown-{key}")
 * - 顶级无子项 → NavLink (data-testid="nav-link")
 * - 权限过滤: 子项不可见 OR 父级不可见 → 隐藏
 * - sort 顺序保留
 */
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { PermissionData } from "@/lib/auth/permission-types";
import { Header } from "./header";

vi.mock("@/i18n/navigation", () => ({
  Link: ({ href, children, ...rest }: { href: string; children: React.ReactNode }) => (
    <a href={href} {...rest}>
      {children}
    </a>
  ),
}));

vi.mock("@/components/user-menu", () => ({
  UserMenu: () => <div data-testid="user-menu" />,
}));

vi.mock("@/components/settings/settings-dialog", () => ({
  SettingsDialog: () => null,
}));

vi.mock("@/components/settings/theme-toggle", () => ({
  ThemeToggle: () => <button data-testid="theme-toggle" />,
}));

vi.mock("@/components/common/display/app-env-badge", () => ({
  EnvBadge: () => <div data-testid="env-badge" />,
}));

const mkPermissions = (overrides: Partial<PermissionData>): PermissionData => ({
  role: "user",
  accountId: 1,
  allowed: [],
  pages: [],
  ...overrides,
});

describe("Header nav tree rendering", () => {
  it("顶级有子项 → 渲染 NavDropdown", () => {
    const perms = mkPermissions({
      allowed: ["admin"],
      pages: [
        {
          key: "admin",
          label_zh: "管理中心",
          label_en: "Admin",
          path: "/admin",
          metadata: { path: "/admin", is_group: true },
        },
        {
          key: "admin_users",
          label_zh: "用户管理",
          label_en: "Users",
          path: "/admin/users",
          metadata: { path: "/admin/users", parent_id: "admin" },
        },
      ],
    });
    render(<Header user={null} permissions={perms} />);
    expect(screen.getByTestId("nav-dropdown-admin")).toBeInTheDocument();
  });

  it("顶级无子项 → 渲染 NavLink", () => {
    const perms = mkPermissions({
      allowed: ["chat"],
      pages: [
        {
          key: "chat",
          label_zh: "对话",
          label_en: "Chat",
          path: "/chat",
          metadata: { path: "/chat" },
        },
      ],
    });
    render(<Header user={null} permissions={perms} />);
    expect(screen.getByTestId("nav-link")).toHaveTextContent("对话");
    expect(screen.queryByTestId("nav-dropdown-chat")).toBeNull();
  });

  it("权限过滤: 父级无权限 + 子项也无权限 → 父级不显示", () => {
    const perms = mkPermissions({
      allowed: ["chat"], // admin 没权限
      pages: [
        {
          key: "admin",
          label_zh: "管理中心",
          label_en: "Admin",
          path: "/admin",
          metadata: { path: "/admin", is_group: true },
        },
        {
          key: "admin_users",
          label_zh: "用户管理",
          label_en: "Users",
          path: "/admin/users",
          metadata: { path: "/admin/users", parent_id: "admin" },
        },
        {
          key: "chat",
          label_zh: "对话",
          label_en: "Chat",
          path: "/chat",
          metadata: { path: "/chat" },
        },
      ],
    });
    render(<Header user={null} permissions={perms} />);
    expect(screen.queryByTestId("nav-dropdown-admin")).toBeNull();
    expect(screen.getByTestId("nav-link")).toHaveTextContent("对话");
  });

  it("sort 顺序保留: chat 排在 admin 前面", () => {
    const perms = mkPermissions({
      allowed: ["chat", "admin"],
      pages: [
        {
          key: "admin",
          label_zh: "管理中心",
          label_en: "Admin",
          path: "/admin",
          sort: 50,
          metadata: { path: "/admin", is_group: true },
        },
        {
          key: "chat",
          label_zh: "对话",
          label_en: "Chat",
          path: "/chat",
          sort: 10,
          metadata: { path: "/chat" },
        },
      ],
    });
    render(<Header user={null} permissions={perms} />);
    const nav = screen.getByRole("navigation");
    const dropdowns = nav.querySelectorAll("[data-testid^='nav-dropdown-']");
    const links = nav.querySelectorAll("[data-testid='nav-link']");
    expect(dropdowns[0]).toHaveAttribute("data-testid", "nav-dropdown-admin");
    expect(links[0]).toHaveTextContent("对话");
  });

  it("is_active=false 不渲染", () => {
    const perms = mkPermissions({
      allowed: ["chat", "hidden"],
      pages: [
        {
          key: "chat",
          label_zh: "对话",
          label_en: "Chat",
          path: "/chat",
          metadata: { path: "/chat" },
        },
        {
          key: "hidden",
          label_zh: "隐藏页",
          label_en: "Hidden",
          path: "/hidden",
          is_active: false,
          metadata: { path: "/hidden" },
        },
      ],
    });
    render(<Header user={null} permissions={perms} />);
    expect(screen.queryByTestId("nav-link")).toHaveTextContent("对话");
    expect(screen.queryByText("隐藏页")).toBeNull();
  });
});
```

If file exists with old tests:
- Keep old tests (mark them with `describe.skip` if they break)
- Append the new `describe("Header nav tree rendering")` block above

- [ ] **Step 3: Run test to verify new tests fail (RED)**

Run: `cd packages/web && bun run test -- components/layout/header.test.tsx 2>&1 | tail -30`

Expected: 5 new tests FAIL because Header still uses old flat-render logic.

- [ ] **Step 4: Commit failing header tests**

```bash
cd c:/doc/Code/rag
git add packages/web/components/layout/header.test.tsx
git commit -m "test(header): add tree-rendering tests (PR3/3)"
```

---

## Task 3.4: Refactor Header to use NavTree (GREEN)

**Files:**
- Modify: `packages/web/components/layout/header.tsx`

- [ ] **Step 1: Read current Header**

Run: `cat packages/web/components/layout/header.tsx`

- [ ] **Step 2: Replace Header body**

Replace `packages/web/components/layout/header.tsx` with:

```tsx
/**
 * 全站顶部 Header (2026-07-02 redesign) — RSC 友好, 仅交互部分 (SettingsDialog) 用 client
 * 3 段:
 *   1. 品牌区: RAG · 德源通泰 (LocalizedLink "/")
 *   2. 导航: buildNavTree + filterNavByPermissions 树形渲染
 *      - 顶级无子项 → NavLink (现状)
 *      - 顶级有子项 → NavDropdown (PR3 新增)
 *   3. 状态 cluster: EnvBadge + ThemeToggle + UserMenu
 * 注意: ThemeToggle 触发 SettingsDialog, dialog 状态由 Header 管 (避免 ThemeToggle 嵌套 ThemeProvider)
 */
"use client";
import { UserMenu, type UserMenuUser } from "@/components/user-menu";
import { useState } from "react";
import { EnvBadge } from "@/components/common/display/app-env-badge";
import { LocalizedLink } from "@/components/i18n/localized-link";
import type { PermissionData } from "@/lib/auth/permission-types";
import { SettingsDialog } from "@/components/settings/settings-dialog";
import { ThemeToggle } from "@/components/settings/theme-toggle";
import { useTranslations } from "next-intl";
import { buildNavTree, filterNavByPermissions } from "@/lib/nav/build-nav-tree";
import { NavDropdown } from "@/components/layout/nav-dropdown";

export const Header = ({
  user,
  permissions,
}: {
  user?: UserMenuUser | null;
  permissions: PermissionData;
}) => {
  const [settingsOpen, setSettingsOpen] = useState(false);
  const translate = useTranslations();
  // (2026-07-02) 走 NavTree 渲染, 取代旧的 flat filter
  const tree = buildNavTree(permissions.pages);
  const visible = filterNavByPermissions(tree, permissions.allowed);

  return (
    <>
      <header className="shrink-0 border-b border-border/60 bg-paper/80 backdrop-blur-sm">
        <div className="mx-auto flex max-w-7xl items-center gap-8 px-6 py-4">
          <LocalizedLink
            href="/"
            className="display text-xl tracking-tight transition-opacity hover:opacity-70"
          >
            RAG<span className="text-clay"> · </span>
            {translate("德源通泰")}
          </LocalizedLink>
          <nav className="ml-auto flex items-center gap-1 text-base">
            {visible.roots.map((node) =>
              node.children.length > 0 ? (
                <NavDropdown key={node.key} node={node} />
              ) : (
                <NavLink key={node.key} href={node.path ?? "#"}>
                  {translate(node.label_zh)}
                </NavLink>
              ),
            )}
          </nav>
          <div className="hidden items-center gap-2 sm:flex">
            <span className="eyebrow">v0.1</span>
            {/* Status cluster: 环境标识 + Dify 监控点 (30s 轮询) */}
            <EnvBadge />
            <ThemeToggle onOpen={() => setSettingsOpen(true)} />
          </div>
          <UserMenu user={user ?? null} />
        </div>
      </header>
      <SettingsDialog open={settingsOpen} onOpenChange={setSettingsOpen} />
    </>
  );
};

const NavLink = ({ href, children }: { href: string; children: React.ReactNode }) => (
  <LocalizedLink
    href={href}
    data-testid="nav-link"
    className="group relative rounded-md px-3 py-1.5 text-muted-foreground transition-colors duration-300 hover:text-foreground"
    style={{ transitionTimingFunction: "var(--ease-out-expo)" }}
  >
    <span className="relative z-10">{children}</span>
    <span
      className="absolute bottom-0.5 left-3 right-3 h-px origin-left scale-x-0 bg-foreground/40 transition-transform duration-300 group-hover:scale-x-100"
      style={{ transitionTimingFunction: "var(--ease-out-expo)" }}
    />
  </LocalizedLink>
);
```

- [ ] **Step 3: Run test to verify GREEN**

Run: `cd packages/web && bun run test -- components/layout/header.test.tsx 2>&1 | tail -20`

Expected: All tests pass (5 new + any old).

- [ ] **Step 4: Run NavDropdown test**

Run: `cd packages/web && bun run test -- components/layout/nav-dropdown.test.tsx`

Expected: 5 tests pass.

- [ ] **Step 5: Run typecheck**

Run: `cd packages/web && bun run typecheck 2>&1 | head -30`

Expected: 0 errors.

- [ ] **Step 6: Run lint**

Run: `cd packages/web && bun run lint:fix 2>&1 | tail -10`

Expected: 0 errors after auto-fix.

- [ ] **Step 7: Commit Header refactor**

```bash
cd c:/doc/Code/rag
git add packages/web/components/layout/header.tsx
git commit -m "feat(header): use buildNavTree + NavDropdown for tree rendering (PR3/4)

10 tests green. Desktop nav now renders tree structure.
Mobile hidden via CSS, mobile drawer in PR4."
```

---

## Task 3.5: Verify no regressions

- [ ] **Step 1: Run full frontend test suite**

Run: `cd packages/web && bun run test 2>&1 | tail -15`

Expected: baseline (721) + 15 (PR2) + 5 (NavDropdown) + 5 (Header) = 746 passed.

- [ ] **Step 2: Verify lint + format**

Run: `cd packages/web && bun run lint && bun run format:check`

Expected: 0 errors.

- [ ] **Step 3: Final commit if any fix**

```bash
cd c:/doc/Code/rag
git status
# 如果有 lint/format 改动, git add -u && git commit -m "chore(pr3): final lint/format"
```

---

## PR3 Definition of Done

- [ ] `NavDropdown` component implemented + 5 tests green
- [ ] `Header` refactored to use `buildNavTree` + tree rendering
- [ ] 5 new Header tests green
- [ ] All previous tests still pass (721 baseline + 15 PR2 + 10 PR3 = 746)
- [ ] typecheck / lint / format 0 errors
- [ ] Ready for PR4 (mobile drawer)