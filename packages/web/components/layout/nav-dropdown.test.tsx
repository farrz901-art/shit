/**
 * NavDropdown 测试 (2026-07-02 nav spec §4.3)
 */
/* eslint-disable id-length, no-magic-numbers -- test fixture */
import { screen } from "@testing-library/react";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import { describe, expect, it, vi } from "vitest";
import type { NavNode } from "@/lib/nav/nav-types";
import { NavDropdown } from "./nav-dropdown";

vi.mock("@/i18n/navigation", () => ({
  Link: ({ href, children, ...rest }: { href: string; children: React.ReactNode }) => (
    <a href={href} {...rest}>
      {children}
    </a>
  ),
}));

vi.mock("next-intl", () => ({
  useTranslations: () => (key: string) => key,
  NextIntlClientProvider: ({ children }: { children: React.ReactNode }) => children,
}));

vi.mock("@/components/common/input/app-dropdown-menu", () => ({
  AppDropdownMenu: ({
    trigger,
    items,
  }: {
    trigger: React.ReactNode;
    items: { key: string; label: string; href?: string }[];
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

  it("trigger 是 button (a11y)", () => {
    const node = mkNode({ key: "admin", label_zh: "管理中心" });
    render(<NavDropdown node={node} />);
    expect(screen.getByTestId("nav-dropdown-admin").tagName).toBe("BUTTON");
  });

  it("trigger 不可跳 (父级不可点)", () => {
    const node = mkNode({ key: "admin", label_zh: "管理中心", path: "/admin" });
    render(<NavDropdown node={node} />);
    expect(screen.getByTestId("nav-dropdown-admin").tagName).toBe("BUTTON");
    expect(screen.queryByRole("link", { name: "管理中心" })).toBeNull();
  });

  it("trigger 含 ChevronDown svg 图标", () => {
    const node = mkNode({ key: "admin", label_zh: "管理中心" });
    const { container } = render(<NavDropdown node={node} />);
    expect(container.querySelector("svg")).toBeInTheDocument();
  });
});
