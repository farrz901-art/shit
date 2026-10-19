// (2026-06-14) 更新 mock 形状: apiFetch 调 res.text(), 旧 mock 只有 res.json() 跑不通
// 测行为: token 失效 → 错误页; 密码 < 8 → 客户端校验; 不匹配 → 错误; 成功 → server action 被调
// (2026-06-24) 删 router.push 断言: server action 改走 server-side redirect (抛 NEXT_REDIRECT),
//   page 不再调 router.push, 改 mock acceptInviteAction 验调用 + 入参.
import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, screen, waitFor } from "@testing-library/react";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import { HTTP_NOT_FOUND } from "@/const";
import InviteRedeemPage from "./page";
import { NextIntlClientProvider } from "next-intl";
import zhMessages from "@/messages/zh.json";

vi.mock("next/headers", () => ({
  cookies: vi.fn(async () => ({ get: () => undefined, set: () => {} })),
}));

vi.mock("next/navigation", () => ({
  useParams: () => ({ token: "test-tok-123" }),
}));

const acceptInviteMock = vi.fn();
vi.mock("@/app/[locale]/_actions/account", () => ({
  acceptInviteAction: (...args: unknown[]) => acceptInviteMock(...args),
}));

const okResponse = (data: unknown): Response =>
  ({
    ok: true,
    status: 200,
    statusText: "OK",
    text: async () => JSON.stringify(data),
  }) as unknown as Response;
const errResponse = (status: number, detail?: string): Response => {
  const buildText = async () => {
    if (detail) {
      return JSON.stringify({ detail });
    }
    return "";
  };
  return {
    ok: false,
    status,
    statusText: "Err",
    text: buildText,
  } as unknown as Response;
};

const fetchMock = vi.fn();
globalThis.fetch = fetchMock as any;

beforeEach(() => {
  fetchMock.mockReset();
  acceptInviteMock.mockReset();
  // 默认 server action 不抛, 返失败态 (走客户端校验失败分支也走这里)
  acceptInviteMock.mockResolvedValue({ error: null, ok: false });
  // 默认 GET invite 返 ok
  fetchMock.mockResolvedValueOnce(
    okResponse({ email: "new@x.com", expires_at: "2026-06-20T00:00:00" }),
  );
});

const renderPage = () =>
  render(
    <NextIntlClientProvider locale="zh" messages={zhMessages}>
      <InviteRedeemPage />
    </NextIntlClientProvider>,
  );

describe("InviteRedeemPage", () => {
  it("token 失效 (404) → 错误页", async () => {
    fetchMock.mockReset();
    fetchMock.mockResolvedValueOnce(errResponse(HTTP_NOT_FOUND));
    renderPage();
    expect(await screen.findByText("邀请链接无效")).toBeInTheDocument();
  });

  it("密码 < 8 → 客户端校验", async () => {
    acceptInviteMock.mockResolvedValueOnce({ error: "密码至少 8 位", ok: false });
    renderPage();
    await waitFor(() => expect(screen.getByTestId("email-input")).toHaveValue("new@x.com"));
    fireEvent.change(screen.getByTestId("name-input"), { target: { value: "u" } });
    fireEvent.change(screen.getByTestId("password-input"), { target: { value: "short" } });
    fireEvent.change(screen.getByTestId("confirm-input"), { target: { value: "short" } });
    fireEvent.click(screen.getByTestId("submit"));
    expect(await screen.findByText("密码至少 8 位")).toBeInTheDocument();
  });

  it("密码不匹配 → 错误", async () => {
    acceptInviteMock.mockResolvedValueOnce({ error: "两次密码不一致", ok: false });
    renderPage();
    await waitFor(() => expect(screen.getByTestId("email-input")).toHaveValue("new@x.com"));
    fireEvent.change(screen.getByTestId("name-input"), { target: { value: "u" } });
    fireEvent.change(screen.getByTestId("password-input"), { target: { value: "longpassword" } });
    fireEvent.change(screen.getByTestId("confirm-input"), { target: { value: "otherpassword" } });
    fireEvent.click(screen.getByTestId("submit"));
    expect(await screen.findByText("两次密码不一致")).toBeInTheDocument();
  });

  // eslint-disable-next-line max-statements -- 表单测试天然 setup + 5 字段 + 4 断言, 拆函数反而难读
  it("成功 → acceptInviteAction 被调", async () => {
    // 成功路径: server action 真实场景会抛 NEXT_REDIRECT (server-side redirect),
    // 测试里只验 action 被调 + 入参正确 — redirect 副作用单独在 account.test.ts 覆盖.
    acceptInviteMock.mockResolvedValueOnce({ error: null, ok: true });
    renderPage();
    await waitFor(() => expect(screen.getByTestId("email-input")).toHaveValue("new@x.com"));
    fireEvent.change(screen.getByTestId("name-input"), { target: { value: "u" } });
    fireEvent.change(screen.getByTestId("password-input"), { target: { value: "longpassword" } });
    fireEvent.change(screen.getByTestId("confirm-input"), { target: { value: "longpassword" } });
    fireEvent.click(screen.getByTestId("submit"));
    await waitFor(() => expect(acceptInviteMock).toHaveBeenCalled());
    // 第一次调用第二个参数 = useActionState 注入的 FormData
    const FIRST_CALL = 0;
    const FORM_DATA_ARG = 1;
    const formData = acceptInviteMock.mock.calls[FIRST_CALL]?.[FORM_DATA_ARG] as FormData;
    expect(formData.get("token")).toBe("test-tok-123");
    expect(formData.get("displayName")).toBe("u");
    expect(formData.get("password")).toBe("longpassword");
  });
});
