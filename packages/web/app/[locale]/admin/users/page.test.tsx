// (2026-06-18) v3 RBAC: 改用 mock getPermissions, 替换 mock /api/account/me + adminPermissionsResponse
// 测试: anon → page throw, 非 admin → redirect /, admin → 渲染表格
// (2026-06-23) GuardPage mock 成 sync passthrough: 权限拒绝的 redirect("/") 路径仍由 getPermissions mock 覆盖.
import { beforeEach, describe, expect, it, vi } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import { NextIntlClientProvider } from "next-intl";
import zhMessages from "@/messages/zh.json";

const { redirectMock, fetchMock, mockGetPermissions } = vi.hoisted(() => ({
  fetchMock: vi.fn(),
  mockGetPermissions: vi.fn(),
  redirectMock: vi.fn((url: string) => {
    const err = new Error(`NEXT_REDIRECT: ${url}`);
    (err as Error & { digest?: string }).digest = "NEXT_REDIRECT";
    throw err;
  }),
}));

// (2026-06-23) GuardPage 是 RSC async 组件, jsdom + RTL 不能渲染 server component.
//   Mock 成 sync passthrough 透传 children — 渲染层只测页面结构, 权限逻辑由 guard-page.test.tsx 覆盖.
vi.mock("@/components/auth/guard-page", () => ({
  GuardPage: ({ children }: { children: React.ReactNode }) => children,
}));

vi.mock("next/navigation", () => ({
  redirect: redirectMock,
}));
vi.mock("next-intl/server", () => ({
  getTranslations: vi.fn(async () => (key: string) => key),
}));
vi.mock("@/lib/auth/permission", () => ({
  getPermissions: mockGetPermissions,
}));

const okResponse = (data: unknown): Response =>
  ({
    ok: true,
    status: 200,
    statusText: "OK",
    text: async () => JSON.stringify(data),
  }) as unknown as Response;

globalThis.fetch = fetchMock as any;
import adminUsersPage from "./page";

describe("AdminUsersPage", () => {
  beforeEach(() => {
    redirectMock.mockClear();
    fetchMock.mockReset();
    mockGetPermissions.mockReset();
  });

  it("anon (getPermissions 401) → page 抛错", async () => {
    mockGetPermissions.mockRejectedValue(new Error("401"));
    await expect(adminUsersPage()).rejects.toThrow();
  });

  it("账号非 admin (isAdminLevel=false) → redirect /", async () => {
    mockGetPermissions.mockResolvedValue({
      allowed: [],
      headers: {},
      isAdminLevel: false,
      role: "user",
    });
    await adminUsersPage().catch(() => {});
    expect(redirectMock).toHaveBeenCalledWith("/");
  });

  it("admin → 渲染 AdminUsersTable + 创 invite 按钮", async () => {
    mockGetPermissions.mockResolvedValue({
      allowed: ["admin"],
      headers: { "x-user-token": "real-tok" },
      isAdminLevel: true,
      role: "admin",
    });
    // /api/account/me → currentUserId
    fetchMock.mockResolvedValueOnce(okResponse({ id: 1 }));
    // /api/admin/users
    fetchMock.mockResolvedValueOnce(okResponse({ items: [], page: 1, page_size: 20, total: 0 }));
    // /api/roles (RSC 同步拉)
    fetchMock.mockResolvedValueOnce(okResponse({ roles: [] }));
    const Page = await adminUsersPage();
    render(
      <NextIntlClientProvider locale="zh" messages={zhMessages}>
        {Page}
      </NextIntlClientProvider>,
    );
    expect(screen.getByTestId("create-invite-btn")).toBeInTheDocument();
  });

  it("getRoles 失败 → RSC 抛错", async () => {
    mockGetPermissions.mockResolvedValue({
      allowed: ["admin"],
      headers: { "x-user-token": "real-tok" },
      isAdminLevel: true,
      role: "admin",
    });
    fetchMock.mockResolvedValueOnce(okResponse({ id: 1 }));
    // listRoles 的 /api/roles 返回 500
    fetchMock.mockResolvedValueOnce(okResponse({ items: [], page: 1, page_size: 20, total: 0 }));
    fetchMock.mockRejectedValueOnce(new Error("roles 500"));
    await expect(adminUsersPage()).rejects.toThrow("roles 500");
  });
});
