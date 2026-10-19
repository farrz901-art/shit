// user-filters 单元测试 (2026-06-26) RBAC wire
//   测 role 过滤: 1) 渲染 role 下拉 2) 点击 role 下拉, 选项含所有角色 + 具体 role
import { fireEvent, screen } from "@testing-library/react";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import { beforeAll, describe, expect, it, vi } from "vitest";
import { NextIntlClientProvider } from "next-intl";
import { UserFilters } from "./user-filters";
import zhMessages from "@/messages/zh.json";

// Radix UI Select 需要 scrollIntoView (jsdom 没有)
beforeAll(() => {
  Element.prototype.scrollIntoView = vi.fn();
});

const SAMPLE_ROLES = [
  {
    created_at: null,
    is_deletable: false,
    is_system: true,
    label_en: "Super Admin",
    label_zh: "超级管理员",
    name: "super_admin",
    updated_at: null,
    user_count: 1,
  },
  {
    created_at: null,
    is_deletable: false,
    is_system: true,
    label_en: "Admin",
    label_zh: "管理员",
    name: "admin",
    updated_at: null,
    user_count: 1,
  },
  {
    created_at: null,
    is_deletable: false,
    is_system: true,
    label_en: "User",
    label_zh: "用户",
    name: "user",
    updated_at: null,
    user_count: 1,
  },
];

const renderFilters = (props: Partial<React.ComponentProps<typeof UserFilters>> = {}) => {
  const onSearchChange = vi.fn();
  const onKindChange = vi.fn();
  const onRoleFilterChange = vi.fn();
  const onReload = vi.fn();
  render(
    <NextIntlClientProvider locale="zh" messages={zhMessages}>
      <UserFilters
        kind="all"
        onKindChange={onKindChange}
        onReload={onReload}
        onRoleFilterChange={onRoleFilterChange}
        onSearchChange={onSearchChange}
        roleFilter="all"
        roles={SAMPLE_ROLES}
        search=""
        {...props}
      />
    </NextIntlClientProvider>,
  );
  return { onKindChange, onReload, onRoleFilterChange, onSearchChange };
};

describe("UserFilters role filter", () => {
  it("渲染 role 下拉, placeholder 是「角色」", () => {
    renderFilters();
    expect(screen.getByTestId("role-filter")).toBeInTheDocument();
  });

  it("点击 role 下拉, 选项含所有角色 + 具体 role", async () => {
    renderFilters();
    fireEvent.click(screen.getByTestId("role-filter"));
    expect(await screen.findByRole("option", { name: "所有角色" })).toBeInTheDocument();
    expect(await screen.findByRole("option", { name: "超级管理员" })).toBeInTheDocument();
    expect(await screen.findByRole("option", { name: "管理员" })).toBeInTheDocument();
    expect(await screen.findByRole("option", { name: "用户" })).toBeInTheDocument();
  });
});
