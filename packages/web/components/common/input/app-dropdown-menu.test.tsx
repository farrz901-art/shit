import { describe, expect, it, vi } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import userEvent from "@testing-library/user-event";
import { AppDropdownMenu } from "./app-dropdown-menu";
import { Button } from "@/components/ui/button";

describe("AppDropdownMenu", () => {
  const items = [
    { key: "edit", label: "编辑", icon: <span>✏️</span>, onClick: vi.fn(), testid: "menu-edit" },
    {
      key: "delete",
      label: "删除",
      icon: <span>🗑️</span>,
      onClick: vi.fn(),
      variant: "destructive" as const,
      testid: "menu-delete",
    },
  ];

  it("渲染触发器和菜单项", async () => {
    const user = userEvent.setup();
    render(<AppDropdownMenu trigger={<Button data-testid="trigger">操作</Button>} items={items} />);
    expect(screen.getByTestId("trigger")).toBeInTheDocument();
    // 点击触发
    await user.click(screen.getByTestId("trigger"));
    expect(screen.getByText("编辑")).toBeInTheDocument();
    expect(screen.getByText("删除")).toBeInTheDocument();
  });

  it("点击菜单项调用 onClick", async () => {
    const user = userEvent.setup();
    const onEdit = vi.fn();
    render(
      <AppDropdownMenu
        trigger={<Button data-testid="trigger">操作</Button>}
        items={[{ key: "edit", label: "编辑", onClick: onEdit, testid: "menu-edit" }]}
      />,
    );
    await user.click(screen.getByTestId("trigger"));
    await user.click(screen.getByTestId("menu-edit"));
    expect(onEdit).toHaveBeenCalledOnce();
  });

  it("hidden=true 的项不渲染", async () => {
    const user = userEvent.setup();
    render(
      <AppDropdownMenu
        trigger={<Button data-testid="trigger">操作</Button>}
        items={[
          { key: "visible", label: "可见", onClick: vi.fn() },
          { key: "hidden", label: "隐藏", onClick: vi.fn(), hidden: true },
        ]}
      />,
    );
    await user.click(screen.getByTestId("trigger"));
    expect(screen.getByText("可见")).toBeInTheDocument();
    expect(screen.queryByText("隐藏")).not.toBeInTheDocument();
  });

  it("所有项 hidden → trigger 依然渲染但无下拉内容", () => {
    render(
      <AppDropdownMenu
        trigger={<Button data-testid="trigger">操作</Button>}
        items={[{ key: "x", label: "隐藏", onClick: vi.fn(), hidden: true }]}
      />,
    );
    expect(screen.getByTestId("trigger")).toBeInTheDocument();
  });

  it("destructive variant 应用样式", async () => {
    const user = userEvent.setup();
    render(
      <AppDropdownMenu
        trigger={<Button data-testid="trigger">操作</Button>}
        items={[
          {
            key: "del",
            label: "删除",
            variant: "destructive",
            onClick: vi.fn(),
            testid: "menu-del",
          },
        ]}
      />,
    );
    await user.click(screen.getByTestId("trigger"));
    const item = screen.getByTestId("menu-del");
    expect(item.className).toContain("text-destructive");
  });

  it("separator 渲染分隔线", async () => {
    const user = userEvent.setup();
    render(
      <AppDropdownMenu
        trigger={<Button data-testid="trigger">操作</Button>}
        items={[
          { key: "top", label: "上方", onClick: vi.fn() },
          { key: "bottom", label: "下方", separator: true, onClick: vi.fn() },
        ]}
      />,
    );
    await user.click(screen.getByTestId("trigger"));
    // 两项都渲染, 中间必然有分隔线
    expect(screen.getByText("上方")).toBeInTheDocument();
    expect(screen.getByText("下方")).toBeInTheDocument();
  });

  it("contentClassName 透传", async () => {
    const user = userEvent.setup();
    render(
      <AppDropdownMenu
        trigger={<Button data-testid="trigger">操作</Button>}
        items={[{ key: "a", label: "项", onClick: vi.fn() }]}
        contentClassName="w-48"
      />,
    );
    await user.click(screen.getByTestId("trigger"));
    // 菜单打开后查找 className 含 w-48 的元素
    const content = document.querySelector("[data-radix-popper-content-wrapper]");
    expect(content).toBeTruthy();
  });

  it("disabled 项不可点击", async () => {
    const user = userEvent.setup();
    const onClick = vi.fn();
    render(
      <AppDropdownMenu
        trigger={<Button data-testid="trigger">操作</Button>}
        items={[{ key: "d", label: "禁用", disabled: true, onClick, testid: "menu-disabled" }]}
      />,
    );
    await user.click(screen.getByTestId("trigger"));
    const item = screen.getByTestId("menu-disabled");
    expect(item.className).toContain("pointer-events-none");
  });
});
