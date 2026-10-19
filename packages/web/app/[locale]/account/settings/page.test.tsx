// Page.test.tsx — 测 AccountSettingsClient (跳过 RSC + PageGuard, 太难直接测)
// (2026-06-18) 末尾加 RSC 测试: /api/account/me 必须带 x-user-token header,
//   否则后端返 dev anon (is_account: false) → page redirect /login (用户感觉"跳登录页")
import { beforeEach, describe, expect, it, vi } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import { AccountSettingsClient } from "./_components/account-settings-client";
import { IntlWrapper } from "@/lib/test-utils/intl-wrapper";

// ---- RSC 回归测试 (2026-06-18) ----
const { redirectMock, fetchMock } = vi.hoisted(() => ({
  fetchMock: vi.fn(),
  redirectMock: vi.fn((url: string) => {
    const err = new Error(`NEXT_REDIRECT: ${url}`);
    (err as Error & { digest?: string }).digest = "NEXT_REDIRECT";
    throw err;
  }),
}));

vi.mock("next/headers", () => ({
  cookies: vi.fn(async () => ({
    get: (key: string) => (key === "rag_user_token" ? { value: "real-user-tok" } : undefined),
  })),
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
    status: 200,
    statusText: "OK",
    text: async () => JSON.stringify(data),
  }) as unknown as Response;

const permsResponse = (role = "user"): Response =>
  okResponse({ allowed: ["chat"], pages: [], role });

globalThis.fetch = fetchMock as any;

import accountSettingsPage from "./page";
import { ONE } from "@/const";

describe("AccountSettingsClient", () => {
  it("renders 4 sections in non-pending state", () => {
    render(
      <IntlWrapper locale="zh">
        <AccountSettingsClient
          me={{
            avatar_url: null,
            deletion_expires_at: null,
            display_name: "Test User",
            email: "test@example.com",
            id: 1,
            is_pending_deletion: false,
          }}
        />
      </IntlWrapper>,
    );
    expect(screen.getByTestId("profile-section")).toBeInTheDocument();
    expect(screen.getByTestId("email-section")).toBeInTheDocument();
    expect(screen.getByTestId("password-section")).toBeInTheDocument();
    expect(screen.getByTestId("deletion-section")).toBeInTheDocument();
    expect(screen.getByTestId("deletion-active")).toBeInTheDocument();
    expect(screen.queryByTestId("deletion-pending")).not.toBeInTheDocument();
  });

  it("renders deletion-pending block when is_pending_deletion=true", () => {
    render(
      <IntlWrapper locale="zh">
        <AccountSettingsClient
          me={{
            avatar_url: null,
            deletion_expires_at: "2026-06-25T00:00:00Z",
            display_name: "Test User",
            email: "test@example.com",
            id: 1,
            is_pending_deletion: true,
          }}
        />
      </IntlWrapper>,
    );
    expect(screen.getByTestId("deletion-pending")).toBeInTheDocument();
    expect(screen.queryByTestId("deletion-active")).not.toBeInTheDocument();
  });

  it("pre-fills display_name input + falls back to empty when null", () => {
    // (2026-06-18) T3.3: display_name 进入 input.value, 不再是段落文本
    const { rerender } = render(
      <IntlWrapper locale="zh">
        <AccountSettingsClient
          me={{
            avatar_url: null,
            deletion_expires_at: null,
            display_name: "Alice",
            email: "x@x.com",
            id: 1,
            is_pending_deletion: false,
          }}
        />
      </IntlWrapper>,
    );
    const input = screen.getByTestId("profile-display-name") as HTMLInputElement;
    expect(input.value).toBe("Alice");
    rerender(
      <IntlWrapper locale="zh">
        <AccountSettingsClient
          me={{
            avatar_url: null,
            deletion_expires_at: null,
            display_name: null,
            email: "x@x.com",
            id: 1,
            is_pending_deletion: false,
          }}
        />
      </IntlWrapper>,
    );
    expect((screen.getByTestId("profile-display-name") as HTMLInputElement).value).toBe("");
  });
});

// ---- RSC 回归 (2026-06-18) ----
describe("AccountSettingsPage (RSC)", () => {
  beforeEach(() => {
    redirectMock.mockClear();
    fetchMock.mockReset();
  });

  it("/api/permissions/me 先调, /api/account/me 次调, 必须带 x-user-token header", async () => {
    // GetPermissions() 先 fetch /api/permissions/me
    fetchMock.mockResolvedValueOnce(permsResponse("user"));
    // 已登录账号: /api/account/me
    fetchMock.mockResolvedValueOnce(
      okResponse({
        account_id: 1,
        avatar_url: null,
        deletion_expires_at: null,
        display_name: "Alice",
        email: "alice@x.com",
        id: 1,
        is_account: true,
        is_active: true,
        is_pending_deletion: false,
      }),
    );
    await accountSettingsPage().catch(() => {});
    // 第二次 fetch = /api/account/me, 必须带 x-user-token
    const [url, init] = fetchMock.mock.calls[ONE];
    expect(url).toContain("/api/account/me");
    expect(init?.headers).toMatchObject({ "x-user-token": "real-user-tok" });
  });
});
