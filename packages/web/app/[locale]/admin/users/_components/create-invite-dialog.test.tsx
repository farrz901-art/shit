// (2026-06-14) 更新 mock 形状: apiFetch 调 res.text(), 旧 mock 只有 res.json() 跑不通
// 测行为: 提交 → 拿到 invite_url → 弹复制按钮; 409 → 错误
import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, screen, waitFor } from "@testing-library/react";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import { CreateInviteDialog } from "./create-invite-dialog";
import { NextIntlClientProvider } from "next-intl";
import zhMessages from "@/messages/zh.json";
import { HTTP_CONFLICT } from "@/const";

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
const errResponse = (status: number, detail?: string): Response =>
  ({
    ok: false,
    status,
    statusText: "Err",
    text: async () => (detail ? JSON.stringify({ detail }) : ""),
  }) as unknown as Response;

const fetchMock = vi.fn();
globalThis.fetch = fetchMock as any;

const renderDialog = (open = true) =>
  render(
    <NextIntlClientProvider locale="zh" messages={zhMessages}>
      <CreateInviteDialog open={open} onOpenChange={() => {}} />
    </NextIntlClientProvider>,
  );

describe("CreateInviteDialog", () => {
  beforeEach(() => {
    fetchMock.mockReset();
  });

  it("提交 → 拿到 invite_url → 弹 '复制 URL'", async () => {
    fetchMock.mockResolvedValueOnce(
      okResponse({
        email: "new@x.com",
        invite_token: "tok-123",
        invite_url: "/zh/invite/tok-123",
        is_admin: false,
      }),
    );
    renderDialog();
    fireEvent.change(screen.getByTestId("email-input"), { target: { value: "new@x.com" } });
    fireEvent.click(screen.getByTestId("submit"));
    await waitFor(() => expect(screen.getByTestId("invite-url")).toBeInTheDocument());
    expect(screen.getByTestId("copy-url")).toBeInTheDocument();
  });

  it("重复 email (HTTP_CONFLICT) → 顶部错误", async () => {
    fetchMock.mockResolvedValueOnce(errResponse(HTTP_CONFLICT, "email already registered"));
    renderDialog();
    fireEvent.change(screen.getByTestId("email-input"), { target: { value: "dup@x.com" } });
    fireEvent.click(screen.getByTestId("submit"));
    expect(await screen.findByText("email already registered")).toBeInTheDocument();
  });
});
