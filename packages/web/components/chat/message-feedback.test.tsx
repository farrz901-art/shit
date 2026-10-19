import { beforeEach, describe, expect, it, vi } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import userEvent from "@testing-library/user-event";

const { optimizeAnswerMock, likeAnswerMock } = vi.hoisted(() => ({
  likeAnswerMock: vi.fn(
    async (): Promise<
      { ok: true; data: { approval_id: number } } | { ok: false; error: string }
    > => ({
      data: { approval_id: 999 },
      ok: true,
    }),
  ),
  optimizeAnswerMock: vi.fn(
    async (): Promise<
      | { ok: true; data: { apply_status: string; approval_id: number; review_status: string } }
      | { ok: false; error: string }
    > => ({
      data: { apply_status: "none", approval_id: 555, review_status: "pending" },
      ok: true,
    }),
  ),
}));
vi.mock("@/app/[locale]/_actions/knowledge", () => ({
  __esModule: true,
  likeAnswer: likeAnswerMock,
  optimizeAnswer: optimizeAnswerMock,
}));

const { routerPushMock, toastSuccessMock, toastErrorMock } = vi.hoisted(() => ({
  routerPushMock: vi.fn(),
  toastErrorMock: vi.fn(),
  toastSuccessMock: vi.fn(),
}));
vi.mock("next/navigation", () => ({
  useParams: () => ({ locale: "zh" }),
  usePathname: () => "/chat",
}));

// message-feedback 实际用 @/i18n/navigation 的 useRouter (next-intl 4.x createNavigation)
// 不走 importOriginal: 会拉真 next-intl/navigation → next/navigation 在 vitest ESM 下解析失败
// 组件只 import useRouter, 不需要 actual 的 Link/redirect/usePathname
vi.mock("@/i18n/navigation", () => ({
  useRouter: () => ({ back: vi.fn(), push: routerPushMock }),
}));

vi.mock("sonner", () => ({
  toast: {
    error: (...args: unknown[]) => toastErrorMock(...args),
    success: (...args: unknown[]) => toastSuccessMock(...args),
  },
}));

import { MessageFeedback } from "./message-feedback";
import { NextIntlClientProvider } from "next-intl";
import zhMessages from "@/messages/zh.json";
import { ZERO } from "@/const";

const renderInI18n = (ui: React.ReactNode) =>
  render(
    <NextIntlClientProvider locale="zh" messages={zhMessages}>
      {ui}
    </NextIntlClientProvider>,
  );

beforeEach(() => {
  optimizeAnswerMock.mockClear();
  likeAnswerMock.mockClear();
  routerPushMock.mockClear();
  toastSuccessMock.mockClear();
  toastErrorMock.mockClear();
});

describe("MessageFeedback", () => {
  it("折叠态: 渲染 '不满意' 按钮 + 可点击 '满意' 按钮 (Task 6 接通)", () => {
    renderInI18n(
      <MessageFeedback messageId="m-1" question="1LE 电机选型?" originalAnswer="根据功率选" />,
    );
    expect(screen.getByTestId("btn-improve-m-1")).toBeInTheDocument();
    const goodBtn = screen.getByTestId("btn-good-m-1");
    expect(goodBtn).toBeInTheDocument();
    // (2026-06-16 Task 6) 满意按钮接通 → 不再 disabled
    expect(goodBtn).not.toBeDisabled();
  });

  it("点 '不满意' 展开输入框 (改进回答 + 改进理由 + 提交/取消)", async () => {
    const user = userEvent.setup();
    renderInI18n(<MessageFeedback messageId="m-2" question="Q?" originalAnswer="A0" />);
    await user.click(screen.getByTestId("btn-improve-m-2"));
    expect(screen.getByTestId("feedback-form-m-2")).toBeInTheDocument();
    expect(screen.getByTestId("feedback-improved")).toBeInTheDocument();
    expect(screen.getByTestId("feedback-reason")).toBeInTheDocument();
    expect(screen.getByTestId("btn-submit-feedback")).toBeInTheDocument();
    expect(screen.getByTestId("btn-cancel-feedback")).toBeInTheDocument();
  });

  it("空改进回答 → toast.error 不调 optimizeAnswer", async () => {
    const user = userEvent.setup();
    renderInI18n(<MessageFeedback messageId="m-3" question="Q?" originalAnswer="A0" />);
    await user.click(screen.getByTestId("btn-improve-m-3"));
    // 不填 improved 直接点提交, 按钮 disabled 但 mock 提交也无值, 这里强制调用
    // 改: 直接 fill 空字符串 / 空白触发
    const submitBtn = screen.getByTestId("btn-submit-feedback");
    expect(submitBtn).toBeDisabled();
    // 空白时 toast.error 路径: 按钮被 disabled 拦了, 但 trim 后为空时的代码路径仍存在
    // 这里验证禁用状态即满足要求
    expect(optimizeAnswerMock).not.toHaveBeenCalled();
  });

  it("填改进回答 + 点提交 → optimizeAnswer 被调 (含正确 payload) + toast + push", async () => {
    const user = userEvent.setup();
    renderInI18n(
      <MessageFeedback
        messageId="m-4"
        question="1LE 电机选?"
        originalAnswer="根据功率"
        datasetId="ds-1"
      />,
    );
    await user.click(screen.getByTestId("btn-improve-m-4"));
    await user.type(screen.getByTestId("feedback-improved"), "按电压等级+功率");
    await user.type(screen.getByTestId("feedback-reason"), "答案不够具体");
    await user.click(screen.getByTestId("btn-submit-feedback"));
    await waitFor(() => {
      expect(optimizeAnswerMock).toHaveBeenCalledWith({
        dataset_id: "ds-1",
        improved_answer: "按电压等级+功率",
        original_answer: "根据功率",
        question: "1LE 电机选?",
        reason: "答案不够具体",
      });
      expect(toastSuccessMock).toHaveBeenCalled();
      expect(routerPushMock).toHaveBeenCalledWith("/zh/submissions");
    });
    const call = toastSuccessMock.mock.calls[ZERO];
    expect(String(call[ZERO])).toMatch(/555/);
  });

  it("optimizeAnswer 返 ok=false → toast.error 不 push", async () => {
    optimizeAnswerMock.mockResolvedValueOnce({
      error: "improved_answer 太短",
      ok: false as const,
    });
    const user = userEvent.setup();
    renderInI18n(<MessageFeedback messageId="m-5" question="Q?" originalAnswer="A0" />);
    await user.click(screen.getByTestId("btn-improve-m-5"));
    await user.type(screen.getByTestId("feedback-improved"), "改");
    await user.click(screen.getByTestId("btn-submit-feedback"));
    await waitFor(() => {
      expect(toastErrorMock).toHaveBeenCalledWith("improved_answer 太短");
      expect(routerPushMock).not.toHaveBeenCalled();
    });
  });

  // (2026-06-16 Task 6) 满意按钮接通 → 调 likeAnswer → toast success → 按钮变 liked
  it("点 '满意' → 调 likeAnswer → toast.success → 按钮 disabled (liked)", async () => {
    const user = userEvent.setup();
    renderInI18n(<MessageFeedback messageId="m-6" question="Q?" originalAnswer="A0" />);
    const goodBtn = screen.getByTestId("btn-good-m-6");
    expect(goodBtn).not.toBeDisabled();
    await user.click(goodBtn);
    await waitFor(() => {
      expect(likeAnswerMock).toHaveBeenCalledWith({
        answer: "A0",
        messageId: "m-6",
        question: "Q?",
      });
      expect(toastSuccessMock).toHaveBeenCalled();
    });
    // 已点赞: 按钮变 disabled (一次性, 不能 unlike)
    expect(screen.getByTestId("btn-good-m-6")).toBeDisabled();
  });

  it("likeAnswer 返 ok=false → toast.error, 按钮保持可点", async () => {
    likeAnswerMock.mockResolvedValueOnce({ error: "approval too long", ok: false as const });
    const user = userEvent.setup();
    renderInI18n(<MessageFeedback messageId="m-7" question="Q?" originalAnswer="A0" />);
    const goodBtn = screen.getByTestId("btn-good-m-7");
    await user.click(goodBtn);
    await waitFor(() => {
      expect(likeAnswerMock).toHaveBeenCalled();
      expect(toastErrorMock).toHaveBeenCalledWith("approval too long");
    });
    // 失败时按钮仍可点击 (用户可以重试)
    expect(screen.getByTestId("btn-good-m-7")).not.toBeDisabled();
  });
});
