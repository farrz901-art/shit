/**
 * MobileNavDrawer 测试 (2026-07-02 nav spec §4.4)
 * 6 个用例覆盖折叠面板 + 路由切换关闭.
 */
/* eslint-disable id-length, no-magic-numbers, max-statements -- test fixture */
import { screen } from "@testing-library/react";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { NavTree } from "@/lib/nav/nav-types";
import { MobileNavDrawer } from "./mobile-nav-drawer";

vi.mock("@/components/i18n/localized-link", () => ({
  LocalizedLink: ({ href, children, ...rest }: { href: string; children: React.ReactNode }) => (
    <a href={href} {...rest}>
      {children}
    </a>
  ),
}));

vi.mock("next-intl", () => ({
  useTranslations: () => (key: string) => key,
  NextIntlClientProvider: ({ children }: { children: React.ReactNode }) => children,
}));

// shadcn Sheet 是 Radix Dialog 之上包装, jsdom 下不用真渲染抽屉逻辑
vi.mock("@/components/ui/sheet", () => ({
  Sheet: ({ children, open }: { children: React.ReactNode; open: boolean }) =>
    open ? <div data-testid="sheet-root">{children}</div> : null,
  SheetContent: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="sheet-content">{children}</div>
  ),
  SheetHeader: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  SheetTitle: ({ children }: { children: React.ReactNode }) => <h2>{children}</h2>,
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
  it("open=false 时不渲染 sheet", () => {
    render(<MobileNavDrawer tree={mkTree()} open={false} onOpenChange={() => {}} />);
    expect(screen.queryByTestId("sheet-root")).toBeNull();
  });

  it("open=true 时显示顶级节点", () => {
    render(<MobileNavDrawer tree={mkTree()} open={true} onOpenChange={() => {}} />);
    expect(screen.getByText("管理中心")).toBeInTheDocument();
    expect(screen.getByText("对话")).toBeInTheDocument();
  });

  it("父级节点默认折叠子项", () => {
    render(<MobileNavDrawer tree={mkTree()} open={true} onOpenChange={() => {}} />);
    expect(screen.queryByTestId("mobile-nav-item-admin_users")).toBeNull();
  });

  it("点击父级 trigger 展开子项", async () => {
    const user = userEvent.setup();
    render(<MobileNavDrawer tree={mkTree()} open={true} onOpenChange={() => {}} />);
    await user.click(screen.getByTestId("mobile-nav-toggle-admin"));
    expect(screen.getByTestId("mobile-nav-item-admin_users")).toBeInTheDocument();
    expect(screen.getByTestId("mobile-nav-item-admin_dicts")).toBeInTheDocument();
  });

  it("叶子节点渲染为 link, 不可展开", () => {
    render(<MobileNavDrawer tree={mkTree()} open={true} onOpenChange={() => {}} />);
    const chatLink = screen.getByTestId("mobile-nav-link-chat");
    expect(chatLink).toHaveAttribute("href", "/chat");
  });

  it("点叶子 link → 调 onOpenChange(false)", async () => {
    const onChange = vi.fn();
    const user = userEvent.setup();
    render(<MobileNavDrawer tree={mkTree()} open={true} onOpenChange={onChange} />);
    await user.click(screen.getByTestId("mobile-nav-link-chat"));
    expect(onChange).toHaveBeenCalledWith(false);
  });
});
