// QASubmitForm 单元测试 (Task 17) — mock createQA server action, 验证 onFinish 调它.
// (2026-06-25) 迁移到 AppForm 后, 改用 onFinish 模式 (客户端提交), 不再依赖 form action prop.
import { beforeEach, describe, expect, it, vi } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import userEvent from "@testing-library/user-event";

// Mock createQA server action — 不发真后端, 可观察调用
// 用 vi.hoisted 把 mock 提到顶部, 避开 vi.mock hoist 限制
const { createQAMock } = vi.hoisted(() => ({
  createQAMock: vi.fn(async () => ({
    data: { apply_status: "none", approval_id: 42, review_status: "pending" },
    ok: true as const,
  })),
}));
vi.mock("@/app/[locale]/_actions/knowledge", () => ({
  __esModule: true,
  createQA: createQAMock,
}));

// Mock i18n navigation: QASubmitForm 用 useRouter (来自 @/i18n/navigation)
const { routerPushMock, toastSuccessMock, toastErrorMock } = vi.hoisted(() => ({
  routerPushMock: vi.fn(),
  toastErrorMock: vi.fn(),
  toastSuccessMock: vi.fn(),
}));
vi.mock("@/i18n/navigation", () => ({
  useRouter: () => ({ back: vi.fn(), push: routerPushMock }),
}));

// useParams 仍从 next/navigation 引 (next-intl 不重新导出)
vi.mock("next/navigation", () => ({
  useParams: () => ({ locale: "zh" }),
  usePathname: () => "/knowledge/qa",
}));

vi.mock("sonner", () => ({
  toast: {
    error: (...args: unknown[]) => toastErrorMock(...args),
    success: (...args: unknown[]) => toastSuccessMock(...args),
  },
}));

import { QASubmitForm } from "./qa-submit-form";
import { createQA } from "@/app/[locale]/_actions/knowledge";
import { NextIntlClientProvider } from "next-intl";
import zhMessages from "@/messages/zh.json";

const renderInI18n = (ui: React.ReactNode) =>
  render(
    <NextIntlClientProvider locale="zh" messages={zhMessages}>
      {ui}
    </NextIntlClientProvider>,
  );

beforeEach(() => {
  createQAMock.mockClear();
  routerPushMock.mockClear();
  toastSuccessMock.mockClear();
  toastErrorMock.mockClear();
});

describe("QASubmitForm", () => {
  it("提交时调 createQA, 透传 dataset_id / question / answer", async () => {
    const user = userEvent.setup();
    renderInI18n(<QASubmitForm datasetId="ds-1" />);
    // Question / answer 来自 form item label
    await user.type(screen.getByRole("textbox", { name: /问题/ }), "1LE0001 是什么?");
    await user.type(screen.getByRole("textbox", { name: /答案/ }), "西门子低压电机");
    await user.click(screen.getByTestId("qa-submit"));
    // 等待 server action 异步完成
    expect(vi.mocked(createQA)).toHaveBeenCalled();
    const [[callArg]] = vi.mocked(createQA).mock.calls;
    expect(callArg).toEqual(
      expect.objectContaining({
        answer: "西门子低压电机",
        dataset_id: "ds-1",
        question: "1LE0001 是什么?",
      }),
    );
  });

  it("未选 dataset 时, onFinish 提交仍走 createQA (server action 决定报错)", async () => {
    // 行为约束: QASubmitForm 不拦 datasetId, 透传给 createQA; RSC/父组件负责
    // 选 dataset. 避免 client 端 shim 检查.
    const user = userEvent.setup();
    renderInI18n(<QASubmitForm datasetId="" />);
    await user.type(screen.getByRole("textbox", { name: /问题/ }), "Q?");
    await user.type(screen.getByRole("textbox", { name: /答案/ }), "A.");
    await user.click(screen.getByTestId("qa-submit"));
    expect(vi.mocked(createQA)).toHaveBeenCalledWith(expect.objectContaining({ dataset_id: "" }));
  });

  it("form 渲染 (AppForm 包装) + onSubmit handler 存在", () => {
    renderInI18n(<QASubmitForm datasetId="ds-1" />);
    const submitBtn = screen.getByTestId("qa-submit");
    const form = submitBtn.closest("form");
    expect(form).not.toBeNull();
    // AppForm 走 onSubmit (客户端提交) 而非 form action prop
    const propsKey = Object.keys(form!).find((key) => key.startsWith("__reactProps$"))!;
    const props = (form as unknown as Record<string, { onSubmit?: unknown }>)[propsKey];
    expect(typeof props.onSubmit).toBe("function");
  });

  // (2026-06-12) bug: initialState.ok=true 误显示 "已写入 Dify" 绿色提示.
  // 用户没点提交就能看到这条, 误以为成功了. 加 2 个 case 锁住行为.
  it("初始渲染不显示 '已写入 Dify' 提示卡 (没提交过不能显示成功)", () => {
    renderInI18n(<QASubmitForm datasetId="ds-1" />);
    // Data-testid="qa-submit-result" 是 AnimatePresence 块, 不该出现
    expect(screen.queryByTestId("qa-submit-result")).toBeNull();
  });

  it("提交成功后显示 '已写入 Dify' 提示卡", async () => {
    const user = userEvent.setup();
    renderInI18n(<QASubmitForm datasetId="ds-1" />);
    await user.type(screen.getByRole("textbox", { name: /问题/ }), "Q?");
    await user.type(screen.getByRole("textbox", { name: /答案/ }), "A.");
    await user.click(screen.getByTestId("qa-submit"));
    // 等待 createQAMock 异步返回
    expect(await screen.findByTestId("qa-submit-result")).toBeInTheDocument();
    expect(await screen.findByTestId("qa-submit-result")).toHaveTextContent(/已写入 Dify/);
  });

  // (2026-06-13 Task 21) 提交成功后弹 toast + 跳 /submissions.
  it("提交成功后弹 toast.success (含 approval_id) + router.push 到 /submissions", async () => {
    const user = userEvent.setup();
    renderInI18n(<QASubmitForm datasetId="ds-1" />);
    await user.type(screen.getByRole("textbox", { name: /问题/ }), "Q?");
    await user.type(screen.getByRole("textbox", { name: /答案/ }), "A.");
    await user.click(screen.getByTestId("qa-submit"));
    await waitFor(() => {
      expect(toastSuccessMock).toHaveBeenCalled();
      expect(routerPushMock).toHaveBeenCalledWith("/zh/submissions");
    });
    // Toast 文案含 approval_id=42
    const [toastCall] = toastSuccessMock.mock.calls;
    const [firstArg] = toastCall;
    expect(String(firstArg)).toMatch(/42/);
  });
});
