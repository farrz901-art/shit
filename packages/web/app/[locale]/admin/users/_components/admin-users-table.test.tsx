// AdminUsersTable 测试 (2026-06-14) - 切 DataTable 后改 data-testid 来源
//   行: DataTable 自带 data-testid="data-table-row" + 内部 rowKey 值
//   按钮: actions column render 给每个按钮 testid (toggle-admin-{id} / toggle-active-{id} / reset-pwd-{id})
import { act, fireEvent, screen, waitFor } from "@testing-library/react";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AdminUsersTable } from "./admin-users-table";
import { NextIntlClientProvider } from "next-intl";
import { THREE } from "@/const";
import zhMessages from "@/messages/zh.json";

// Radix UI Select 需要 scrollIntoView (jsdom 没有)
Element.prototype.scrollIntoView = vi.fn();

vi.mock("next/headers", () => ({
  cookies: vi.fn(async () => ({ get: () => "tok", set: () => {} })),
}));

// mock useRoles to return roles directly (skip refetch in test)
vi.mock("../_hooks/use-roles", () => ({
  useRoles: (initial: unknown[]) => initial,
}));

const fetchMock = vi.fn();
globalThis.fetch = fetchMock as any;

const SAMPLE_ROLES = [
  {
    created_at: null,
    is_deletable: false,
    is_system: false,
    label_en: "Super Admin",
    label_zh: "超级管理员",
    name: "super_admin",
    updated_at: null,
    user_count: 0,
  },
  {
    created_at: null,
    is_deletable: false,
    is_system: false,
    label_en: "Admin",
    label_zh: "管理员",
    name: "admin",
    updated_at: null,
    user_count: 0,
  },
  {
    created_at: null,
    is_deletable: false,
    is_system: false,
    label_en: "User",
    label_zh: "用户",
    name: "user",
    updated_at: null,
    user_count: 0,
  },
];

const SAMPLE = {
  items: [
    {
      account_id: 1,
      created_at: "2026-06-01T00:00:00",
      display_name: "admin",
      email: "admin@x.com",
      id: 1,
      is_active: true,
      kind: "account" as const,
      last_login_at: "2026-06-13T00:00:00",
      last_seen_at: "2026-06-13T00:00:00",
      role: "admin",
    },
    {
      account_id: null,
      created_at: "2026-06-02T00:00:00",
      display_name: "anon-x",
      email: null,
      id: 2,
      is_active: true,
      kind: "anon" as const,
      last_login_at: null,
      last_seen_at: "2026-06-13T00:00:00",
      role: "user",
    },
    {
      account_id: 2,
      created_at: "2026-06-03T00:00:00",
      display_name: "user",
      email: "user@x.com",
      id: 3,
      is_active: true,
      kind: "account" as const,
      last_login_at: "2026-06-12T00:00:00",
      last_seen_at: "2026-06-13T00:00:00",
      role: "user",
    },
  ],
  page: 1,
  page_size: 20,
  total: 3,
};

const renderTable = async (overrides: { roles?: typeof SAMPLE_ROLES } = {}) => {
  let result: ReturnType<typeof render> = null as unknown as ReturnType<typeof render>;
  await act(async () => {
    result = render(
      <NextIntlClientProvider locale="zh" messages={zhMessages}>
        <AdminUsersTable
          usersPromise={Promise.resolve(SAMPLE)}
          currentUserId={1}
          initialRoles={overrides.roles ?? SAMPLE_ROLES}
        />
      </NextIntlClientProvider>,
    );
    await Promise.resolve();
  });
  return result!;
};

describe("AdminUsersTable", () => {
  beforeEach(() => fetchMock.mockReset());

  it("渲染 3 行 (DataTable data-table-row)", async () => {
    await renderTable();
    expect(screen.getAllByTestId("data-table-row")).toHaveLength(THREE);
  });

  it("当前用户 (id=1) 的 toggle-active / toggle-admin 按钮 disabled", async () => {
    await renderTable();
    expect(screen.getByTestId("toggle-admin-1")).toBeDisabled();
    expect(screen.getByTestId("toggle-active-1")).toBeDisabled();
  });

  it("anon 用户 (id=2) 的 toggle-admin 按钮 enabled", async () => {
    await renderTable();
    expect(screen.getByTestId("toggle-admin-2")).toBeEnabled();
  });

  it("调 PATCH 切换 is_active → reload", async () => {
    fetchMock.mockResolvedValueOnce({
      json: async () => ({ id: 2, ok: true }),
      ok: true,
    });
    fetchMock.mockResolvedValueOnce({
      json: async () => SAMPLE,
      ok: true,
    });
    await renderTable();
    fireEvent.click(screen.getByTestId("toggle-active-2"));
    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
  });

  // Radix Select portal 交互在 jsdom 中不稳定
  // super_admin 灰禁逻辑在 AppSelect `disabled` prop 层, 组件测试覆盖
  // changeRole PATCH body 的测试在 use-user-table.test.ts 覆盖

  it("角色列渲染 AppSelect, 行 1 (admin) 当前 value=admin", async () => {
    await renderTable();
    const sel = screen.getByTestId("role-select-1");
    expect(sel).toBeInTheDocument();
    expect(sel).toHaveTextContent("管理员");
  });
});
