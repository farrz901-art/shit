# PR4 — Mobile Hamburger Drawer

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add mobile (< sm breakpoint) hamburger button that opens a drawer with the same nav tree, using AppDrawer + collapsible accordion.

**Files:**
- Create: `packages/web/components/layout/mobile-nav-drawer.tsx`
- Create: `packages/web/components/layout/mobile-nav-drawer.test.tsx`
- Modify: `packages/web/components/layout/header.tsx` (add hamburger, hide desktop nav on < sm)

---

## Task 4.1: Add failing test for MobileNavDrawer

**Files:**
- Create: `packages/web/components/layout/mobile-nav-drawer.test.tsx`

- [ ] **Step 1: Write failing test**

Create `packages/web/components/layout/mobile-nav-drawer.test.tsx`:

```tsx
/**
 * MobileNavDrawer 测试 (2026-07-02 nav spec §4.4)
 * 验证:
 * - 默认关闭状态不渲染内容
 * - 打开后显示所有可见顶级节点
 * - 父级节点点击展开 / 折叠子项
 * - 叶子节点渲染为 link
 * - 路由切换自动关闭
 */
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { NavTree } from "@/lib/nav/nav-types";
import { MobileNavDrawer } from "./mobile-nav-drawer";

vi.mock("@/i18n/navigation", () => ({
  Link: ({ href, children, ...rest }: { href: string; children: React.ReactNode }) => (
    <a href={href} {...rest}>
      {children}
    </a>
  ),
}));

// Mock AppDrawer 为受控测试组件
vi.mock("@/components/common/dialog/app-drawer", () => ({
  AppDrawer: ({
    open,
    onOpenChange,
    title,
    children,
  }: {
    open: boolean;
    onOpenChange: (v: boolean) => void;
    title: string;
    children: React.ReactNode;
  }) =>
    open ? (
      <div role="dialog" aria-label={title}>
        <button data-testid="drawer-close" onClick={() => onOpenChange(false)}>
          close
        </button>
        {children}
      </div>
    ) : null,
}));

const mkTree = (): NavTree => ({
  roots: [
    {
      key: "admin",
      label_zh: "管理中心",
      label_en: "Admin",
      path: "/admin",
      isGroup: true,
      sort: 50,
      children: [
        {
          key: "admin_users",
          label_zh: "用户管理",
          label_en: "Users",
          path: "/admin/users",
          isGroup: false,
          sort: 51,
          children: [],
        },
        {
          key: "admin_dicts",
          label_zh: "字典管理",
          label_en: "Dicts",
          path: "/admin/dicts",
          isGroup: false,
          sort: 54,
          children: [],
        },
      ],
    },
    {
      key: "chat",
      label_zh: "对话",
      label_en: "Chat",
      path: "/chat",
      isGroup: false,
      sort: 10,
      children: [],
    },
  ],
  orphans: [],
});

describe("MobileNavDrawer", () => {
  it("open=false 时不渲染内容", () => {
    render(<MobileNavDrawer tree={mkTree()} open={false} onOpenChange={() => {}} />);
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("open=true 时显示所有顶级节点", () => {
    render(<MobileNavDrawer tree={mkTree()} open={true} onOpenChange={() => {}} />);
    expect(screen.getByText("管理中心")).toBeInTheDocument();
    expect(screen.getByText("对话")).toBeInTheDocument();
  });

  it("父级节点默认折叠子项 (展开前不显示子菜单)", () => {
    render(<MobileNavDrawer tree={mkTree()} open={true} onOpenChange={() => {}} />);
    // 默认折叠, 子项不可见
    expect(screen.queryByText("用户管理")).toBeNull();
    expect(screen.queryByText("字典管理")).toBeNull();
  });

  it("点击父级 trigger 展开子项", async () => {
    const user = userEvent.setup();
    render(<MobileNavDrawer tree={mkTree()} open={true} onOpenChange={() => {}} />);
    const adminTrigger = screen.getByRole("button", { name: /管理中心/ });
    await user.click(adminTrigger);
    expect(screen.getByText("用户管理")).toBeInTheDocument();
    expect(screen.getByText("字典管理")).toBeInTheDocument();
  });

  it("叶子节点渲染为 link, 不可展开", () => {
    render(<MobileNavDrawer tree={mkTree()} open={true} onOpenChange={() => {}} />);
    const chatLink = screen.getByRole("link", { name: "对话" });
    expect(chatLink).toHaveAttribute("href", "/chat");
  });

  it("drawer 关闭时调 onOpenChange(false)", async () => {
    const onChange = vi.fn();
    const user = userEvent.setup();
    render(<MobileNavDrawer tree={mkTree()} open={true} onOpenChange={onChange} />);
    await user.click(screen.getByTestId("drawer-close"));
    expect(onChange).toHaveBeenCalledWith(false);
  });
});
```

- [ ] **Step 2: Run test to verify it fails (RED)**

Run: `cd packages/web && bun run test -- components/layout/mobile-nav-drawer.test.tsx`

Expected: FAIL — `mobile-nav-drawer.tsx` not found.

- [ ] **Step 3: Commit failing test**

```bash
cd c:/doc/Code/rag
git add packages/web/components/layout/mobile-nav-drawer.test.tsx
git commit -m "test(nav): add MobileNavDrawer failing tests (PR4/1)"
```

---

## Task 4.2: Implement MobileNavDrawer

**Files:**
- Create: `packages/web/components/layout/mobile-nav-drawer.tsx`

- [ ] **Step 1: Check AppDrawer exists**

Run: `ls packages/web/components/common/dialog/app-drawer.tsx 2>/dev/null && echo "exists" || echo "missing"`

If `exists`: continue to Step 2.
If `missing`: read `app-dialog.tsx` instead and adapt the import. Per CLAUDE.md, `<AppDrawer>` is shadcn Sheet wrapper (line 31 of CLAUDE.md). If truly missing, escalate to user before continuing.

- [ ] **Step 2: Implement MobileNavDrawer**

Create `packages/web/components/layout/mobile-nav-drawer.tsx`:

```tsx
/**
 * MobileNavDrawer: < sm 断点汉堡菜单 (2026-07-02 nav spec §4.4)
 * - 父级节点默认折叠, 点击展开 (避免抽屉太长)
 * - 叶子节点直接 link
 * - 路由切换由父组件 close (Header 在 usePathname 变化时设 open=false)
 */
"use client";
import { useState } from "react";
import { ChevronDown } from "lucide-react";
import { AppDrawer } from "@/components/common/dialog/app-drawer";
import { LocalizedLink } from "@/components/i18n/localized-link";
import type { NavTree } from "@/lib/nav/nav-types";
import { useTranslations } from "next-intl";
import { cn } from "@/lib/utils";

export const MobileNavDrawer = ({
  tree,
  open,
  onOpenChange,
}: {
  tree: NavTree;
  open: boolean;
  onOpenChange: (v: boolean) => void;
}) => {
  const translate = useTranslations();
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  const toggleExpanded = (key: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  };

  return (
    <AppDrawer open={open} onOpenChange={onOpenChange} title={translate("导航")}>
      <div className="flex flex-col gap-1 p-4">
        {tree.roots.map((node) => {
          if (node.children.length === 0) {
            // 叶子: 直接 link
            return (
              <LocalizedLink
                key={node.key}
                href={node.path ?? "#"}
                onClick={() => onOpenChange(false)}
                data-testid={`mobile-nav-link-${node.key}`}
                className="rounded-md px-4 py-3 text-base font-medium text-foreground hover:bg-muted/40"
              >
                {translate(node.label_zh)}
              </LocalizedLink>
            );
          }
          // 父级: 可展开折叠面板
          const isExpanded = expanded.has(node.key);
          return (
            <div key={node.key} data-testid={`mobile-nav-group-${node.key}`}>
              <button
                type="button"
                onClick={() => toggleExpanded(node.key)}
                aria-expanded={isExpanded}
                data-testid={`mobile-nav-toggle-${node.key}`}
                className="flex w-full items-center justify-between rounded-md px-4 py-3 text-left text-base font-semibold text-foreground hover:bg-muted/40"
              >
                <span>{translate(node.label_zh)}</span>
                <ChevronDown
                  className={cn("h-4 w-4 transition-transform", isExpanded && "rotate-180")}
                />
              </button>
              {isExpanded && (
                <div className="ml-4 mt-1 flex flex-col gap-1 border-l border-border/40 pl-2">
                  {node.children.map((child) => (
                    <LocalizedLink
                      key={child.key}
                      href={child.path ?? "#"}
                      onClick={() => onOpenChange(false)}
                      data-testid={`mobile-nav-item-${child.key}`}
                      className="rounded-md px-3 py-2 text-sm text-muted-foreground hover:bg-muted/40 hover:text-foreground"
                    >
                      {translate(child.label_zh)}
                    </LocalizedLink>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </AppDrawer>
  );
};
```

- [ ] **Step 3: Run test to verify GREEN**

Run: `cd packages/web && bun run test -- components/layout/mobile-nav-drawer.test.tsx`

Expected: 6 tests PASS.

- [ ] **Step 4: Run lint**

Run: `cd packages/web && bun run lint:fix -- components/layout/mobile-nav-drawer.tsx`

Expected: 0 errors.

- [ ] **Step 5: Commit MobileNavDrawer**

```bash
cd c:/doc/Code/rag
git add packages/web/components/layout/mobile-nav-drawer.tsx
git commit -m "feat(nav): add MobileNavDrawer for < sm breakpoint (PR4/2)

Collapsible parent groups, direct links for leaves.
6 tests green."
```

---

## Task 4.3: Wire MobileNavDrawer into Header

**Files:**
- Modify: `packages/web/components/layout/header.tsx`

- [ ] **Step 1: Add hamburger button + drawer to Header**

In `packages/web/components/layout/header.tsx`, replace the `<header>` JSX with:

```tsx
      <header className="shrink-0 border-b border-border/60 bg-paper/80 backdrop-blur-sm">
        <div className="mx-auto flex max-w-7xl items-center gap-8 px-6 py-4">
          <LocalizedLink
            href="/"
            className="display text-xl tracking-tight transition-opacity hover:opacity-70"
          >
            RAG<span className="text-clay"> · </span>
            {translate("德源通泰")}
          </LocalizedLink>
          {/* (2026-07-02) 桌面端 nav: ≥ sm 显示, 移动端隐藏 */}
          <nav className="ml-auto hidden items-center gap-1 text-base sm:flex">
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
          {/* (2026-07-02) 移动端 hamburger: < sm 显示, 桌面隐藏 */}
          <button
            type="button"
            onClick={() => setMobileOpen(true)}
            aria-label={translate("打开导航菜单")}
            data-testid="mobile-hamburger"
            className="ml-auto rounded-md p-2 text-muted-foreground hover:text-foreground sm:hidden"
          >
            <MenuIcon className="h-5 w-5" />
          </button>
          <div className="hidden items-center gap-2 sm:flex">
            <span className="eyebrow">v0.1</span>
            <EnvBadge />
            <ThemeToggle onOpen={() => setSettingsOpen(true)} />
          </div>
          <UserMenu user={user ?? null} />
        </div>
      </header>
      <SettingsDialog open={settingsOpen} onOpenChange={setSettingsOpen} />
      {/* (2026-07-02) 移动端抽屉 */}
      <MobileNavDrawer tree={visible} open={mobileOpen} onOpenChange={setMobileOpen} />
```

Add imports and state:

```tsx
import { Menu as MenuIcon } from "lucide-react";
import { MobileNavDrawer } from "@/components/layout/mobile-nav-drawer";
import { usePathname } from "@/i18n/navigation";

// In Header component:
const pathname = usePathname();
const [mobileOpen, setMobileOpen] = useState(false);

// Close drawer on route change (useEffect in client component)
useEffect(() => {
  setMobileOpen(false);
}, [pathname]);
```

Also import `useEffect` from React (top of file).

- [ ] **Step 2: Update header.test.tsx mocks**

In `packages/web/components/layout/header.test.tsx`, add mock:

```tsx
vi.mock("@/i18n/navigation", async () => {
  const actual = await vi.importActual<typeof import("@/i18n/navigation")>("@/i18n/navigation");
  return {
    ...actual,
    usePathname: () => "/",
    Link: ({ href, children, ...rest }: { href: string; children: React.ReactNode }) => (
      <a href={href} {...rest}>
        {children}
      </a>
    ),
  };
});

vi.mock("@/components/layout/mobile-nav-drawer", () => ({
  MobileNavDrawer: () => null,
}));
```

- [ ] **Step 3: Run header tests**

Run: `cd packages/web && bun run test -- components/layout/header.test.tsx`

Expected: all tests pass.

- [ ] **Step 4: Run typecheck**

Run: `cd packages/web && bun run typecheck 2>&1 | head -30`

Expected: 0 errors.

- [ ] **Step 5: Commit Header wiring**

```bash
cd c:/doc/Code/rag
git add packages/web/components/layout/header.tsx packages/web/components/layout/header.test.tsx
git commit -m "feat(header): wire mobile hamburger + MobileNavDrawer (PR4/3)

< sm breakpoint shows hamburger; ≥ sm shows desktop nav.
Drawer closes on route change (usePathname effect)."
```

---

## Task 4.4: Verify no regressions

- [ ] **Step 1: Run full frontend test suite**

Run: `cd packages/web && bun run test 2>&1 | tail -15`

Expected: baseline + 15 (PR2) + 10 (PR3) + 6 (PR4) = 752 passed.

- [ ] **Step 2: Run lint + format**

Run: `cd packages/web && bun run lint && bun run format:check`

Expected: 0 errors.

- [ ] **Step 3: Final commit if any fix**

```bash
cd c:/doc/Code/rag
git status
# 如有 lint/format 改动, git add -u && git commit -m "chore(pr4): final lint/format"
```

---

## PR4 Definition of Done

- [ ] `MobileNavDrawer` component implemented + 6 tests green
- [ ] Header wires hamburger button (visible < sm only)
- [ ] Drawer closes on route change
- [ ] All previous tests pass (746 baseline + 6 = 752)
- [ ] typecheck / lint / format 0 errors
- [ ] Ready for PR5 (TreeCheckbox generic component)