/**
 * TreeCheckbox 通用组件测试 (2026-07-02 nav spec §5.3)
 */
/* eslint-disable id-length, no-magic-numbers -- test fixture */
import { screen } from "@testing-library/react";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
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
    render(
      <TreeCheckbox
        nodes={tree}
        checked={new Set()}
        indeterminate={new Set()}
        onToggle={() => {}}
      />,
    );
    expect(screen.getByText("管理中心")).toBeInTheDocument();
    expect(screen.getByText("用户管理")).toBeInTheDocument();
    expect(screen.getByText("字典管理")).toBeInTheDocument();
  });

  it("父级 checkbox disabled (不可点)", () => {
    const tree: TreeCheckboxNode<ItemData>[] = [
      mkNode({
        key: "admin",
        label: "管理中心",
        children: [mkNode({ key: "admin_users", label: "用户管理" })],
      }),
    ];
    render(
      <TreeCheckbox
        nodes={tree}
        checked={new Set()}
        indeterminate={new Set()}
        onToggle={() => {}}
      />,
    );
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
    render(
      <TreeCheckbox
        nodes={tree}
        checked={new Set()}
        indeterminate={new Set()}
        onToggle={onToggle}
      />,
    );
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
    render(
      <TreeCheckbox
        nodes={tree}
        checked={new Set(["admin_users"])}
        indeterminate={new Set()}
        onToggle={() => {}}
      />,
    );
    const leafCheckbox = screen.getByRole("checkbox", { name: /用户管理/ });
    expect(leafCheckbox).toBeChecked();
  });

  it("indeterminate 集合里的 key → checkbox aria-checked=mixed", () => {
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
    render(
      <TreeCheckbox
        nodes={tree}
        checked={new Set(["admin_users"])}
        indeterminate={new Set(["admin"])}
        onToggle={() => {}}
      />,
    );
    const parentCheckbox = screen.getByRole("checkbox", { name: /管理中心/ });
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
    render(
      <TreeCheckbox
        nodes={tree}
        checked={new Set()}
        indeterminate={new Set()}
        onToggle={() => {}}
      />,
    );
    expect(screen.getByText("用户管理")).toBeInTheDocument();
    const chevron = screen.getByTestId("tree-chevron-admin");
    await user.click(chevron);
    expect(screen.queryByText("用户管理")).toBeNull();
  });

  it("键盘可达: Space toggle", async () => {
    const onToggle = vi.fn();
    const user = userEvent.setup();
    const tree: TreeCheckboxNode<ItemData>[] = [
      mkNode({
        key: "admin",
        label: "管理中心",
        children: [mkNode({ key: "admin_users", label: "用户管理" })],
      }),
    ];
    render(
      <TreeCheckbox
        nodes={tree}
        checked={new Set()}
        indeterminate={new Set()}
        onToggle={onToggle}
      />,
    );
    const leafCheckbox = screen.getByRole("checkbox", { name: /用户管理/ });
    leafCheckbox.focus();
    expect(leafCheckbox).toHaveFocus();
    await user.keyboard(" ");
    expect(onToggle).toHaveBeenCalledWith("admin_users");
  });
});
