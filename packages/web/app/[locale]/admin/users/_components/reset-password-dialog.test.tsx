// (2026-06-14) 更新 mock 形状: apiFetch 调 res.text(), 旧 mock 只有 res.json() 跑不通
// 测行为: 调 API → 拿到 temp_password → 弹复制按钮
import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, screen, waitFor } from "@testing-library/react";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import { NextIntlClientProvider } from "next-intl";
import { ResetPasswordDialog } from "./reset-password-dialog";
import zhMessages from "@/messages/zh.json";

vi.mock("next/headers", () => ({
  cookies: vi.fn(async () => ({ get: () => "tok", set: () => {} })),
}));

const okResponse = (data: unknown): Response =>
  ({
    ok: true,
    status: 200,
    statusText: "OK",
    text: async () => JSON.stringify(data),
  }) as unknown as Response;

const fetchMock = vi.fn();
globalThis.fetch = fetchMock as any;

const renderDialog = (open = true) =>
  render(
    <NextIntlClientProvider locale="zh" messages={zhMessages}>
      <ResetPasswordDialog userId={42} open={open} onOpenChange={() => {}} />
    </NextIntlClientProvider>,
  );

describe("ResetPasswordDialog", () => {
  beforeEach(() => fetchMock.mockReset());

  it("调 API → 拿到 temp_password → 弹复制按钮", async () => {
    fetchMock.mockResolvedValueOnce(okResponse({ temp_password: "abc123-very-long-temp" }));
    renderDialog();
    fireEvent.click(screen.getByTestId("submit"));
    await waitFor(() => expect(screen.getByTestId("temp-password")).toBeInTheDocument());
    expect(screen.getByTestId("temp-password").textContent).toBe("abc123-very-long-temp");
    expect(screen.getByTestId("copy-temp")).toBeInTheDocument();
  });
});
