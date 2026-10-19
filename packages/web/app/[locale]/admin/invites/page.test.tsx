// (2026-06-14) 不再断言 fetch URL/headers, 只测: anon → redirect login, admin → 渲染列表
import { HTTP_OK, HTTP_UNAUTHORIZED } from "@/const";
import { act, screen, waitFor } from "@testing-library/react";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { NextIntlClientProvider } from "next-intl";
import zhMessages from "@/messages/zh.json";

const { redirectMock, fetchMock } = vi.hoisted(() => ({
  fetchMock: vi.fn(),
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

vi.mock("next/headers", () => ({
  cookies: vi.fn(async () => ({ get: () => "tok", set: () => {} })),
}));
vi.mock("next/navigation", () => ({
  redirect: redirectMock,
}));
vi.mock("next-intl/server", () => ({
  getTranslations: vi.fn(async () => (key: string) => key),
}));

const okResponse = (data: unknown): Response =>
  ({
    ok: true,
    status: HTTP_OK,
    statusText: "OK",
    text: async () => JSON.stringify(data),
  }) as unknown as Response;

const errResponse = (status: number): Response =>
  ({
    ok: false,
    status,
    statusText: "Err",
    text: async () => "",
  }) as unknown as Response;

// (2026-06-17) v2 RBAC: /api/permissions/me 返 admin 全权限 (测试用)
const adminPermissionsResponse = (): Response =>
  okResponse({
    allowed: [
      "chat",
      "output",
      "knowledge",
      "evaluate",
      "submissions",
      "decode",
      "health",
      "admin",
    ],
    pages: [],
    role: "admin",
  });

globalThis.fetch = fetchMock as typeof globalThis.fetch;
import adminInvitesPageFn from "./page";

describe("AdminInvitesPage", () => {
  beforeEach(() => {
    redirectMock.mockClear();
    fetchMock.mockReset();
  });

  it("anon (401) → redirect /login?next=/admin/invites", async () => {
    fetchMock.mockResolvedValueOnce(errResponse(HTTP_UNAUTHORIZED));
    await adminInvitesPageFn().catch(() => {});
    expect(redirectMock).toHaveBeenCalledWith("/login?next=/admin/invites");
  });

  it("admin → 渲染 invite 列表 + 删除按钮", async () => {
    fetchMock.mockResolvedValueOnce(
      okResponse({
        account_id: 1,
        email: "admin@x.com",
        id: 1,
        is_account: true,
        is_active: true,
        is_admin: true,
      }),
    );
    fetchMock.mockResolvedValueOnce(
      okResponse({
        items: [
          {
            created_at: "2026-06-13T00:00:00",
            email: "a@x.com",
            expires_at: "2026-06-20T00:00:00",
            id: 1,
            redeemed_at: null,
            token: "tok-aaa",
          },
        ],
        total: 1,
      }),
    );
    fetchMock.mockResolvedValueOnce(adminPermissionsResponse());
    const page = await adminInvitesPageFn();
    await act(async () => {
      render(
        <NextIntlClientProvider locale="zh" messages={zhMessages}>
          {page}
        </NextIntlClientProvider>,
      );
      await Promise.resolve();
    });
    await waitFor(() => expect(screen.getByTestId("data-table-row")).toBeInTheDocument());
    expect(screen.getByTestId("delete-tok-aaa")).toBeInTheDocument();
  });
});
