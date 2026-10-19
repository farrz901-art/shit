// (2026-06-14) 不再断言 fetch URL/headers, 只测: 提交 → 拿到 reset_url → 显示; 拿不到 → 不显示
import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, screen, waitFor } from "@testing-library/react";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import ForgotPasswordPage from "./page";
import { NextIntlClientProvider } from "next-intl";
import zhMessages from "@/messages/zh.json";

vi.mock("next/headers", () => ({
  cookies: vi.fn(async () => ({ get: () => undefined, set: () => {} })),
}));

const fetchMock = vi.fn();
globalThis.fetch = fetchMock as any;

const okResponse = (data: unknown): Response =>
  ({
    ok: true,
    status: 200,
    statusText: "OK",
    text: async () => JSON.stringify(data),
  }) as unknown as Response;

const renderPage = () =>
  render(
    <NextIntlClientProvider locale="zh" messages={zhMessages}>
      <ForgotPasswordPage />
    </NextIntlClientProvider>,
  );

describe("ForgotPasswordPage", () => {
  beforeEach(() => fetchMock.mockReset());

  it("提交 → 拿到 reset_url → 显示 url 块 + 复制按钮", async () => {
    fetchMock.mockResolvedValueOnce(okResponse({ reset_url: "/reset-password?token=xxx" }));
    renderPage();
    fireEvent.change(screen.getByTestId("email-input"), { target: { value: "x@x.com" } });
    fireEvent.click(screen.getByTestId("submit"));
    expect(await screen.findByTestId("reset-url")).toBeInTheDocument();
    expect(screen.getByTestId("copy-url")).toBeInTheDocument();
  });

  it("返 null reset_url → 不显示 url 块", async () => {
    fetchMock.mockResolvedValueOnce(okResponse({ reset_url: null }));
    renderPage();
    fireEvent.change(screen.getByTestId("email-input"), { target: { value: "nobody@x.com" } });
    fireEvent.click(screen.getByTestId("submit"));
    await waitFor(() => expect(screen.queryByTestId("reset-url")).not.toBeInTheDocument());
  });
});
