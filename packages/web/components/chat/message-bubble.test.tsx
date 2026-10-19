import { describe, expect, it, vi } from "vitest";
import { fireEvent, screen } from "@testing-library/react";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import type { Message } from "@/lib/chat/types";
import { MessageBubble } from "./message-bubble";
import { NextIntlClientProvider } from "next-intl";
import zhMessages from "@/messages/zh.json";

// Mock next/navigation (MessageFeedback 内 useRouter/useParams)
vi.mock("next/navigation", () => ({
  useParams: () => ({ locale: "zh" }),
  usePathname: () => "/chat",
  useRouter: () => ({ back: vi.fn(), push: vi.fn(), replace: vi.fn() }),
}));

const renderInI18n = (ui: React.ReactNode) =>
  render(
    <NextIntlClientProvider locale="zh" messages={zhMessages}>
      {ui}
    </NextIntlClientProvider>,
  );

const USER_MSG: Message = {
  content: "1LE 电机怎么选?",
  createdAt: 1_700_000_000_000,
  id: "m1",
  role: "user",
};

const AI_MSG: Message = {
  citations: [{ content: "选型依据功率", documentName: "1LE1023.pdf", score: 0.87 }],
  content: "根据功率选...",
  createdAt: 1_700_000_001_000,
  id: "m2",
  role: "assistant",
  thinking: [
    { node: "n1", status: "started" },
    { detail: "succeeded", node: "n1", status: "finished" },
  ],
};

describe("MessageBubble", () => {
  it("user 消息渲染内容, role=user 标识", () => {
    renderInI18n(<MessageBubble message={USER_MSG} />);
    expect(screen.getByTestId("message-m1")).toHaveTextContent("1LE 电机怎么选?");
    expect(screen.getByTestId("message-m1").dataset.role).toBe("user");
  });

  it("assistant 消息渲染内容 + role=assistant", () => {
    renderInI18n(<MessageBubble message={AI_MSG} />);
    expect(screen.getByTestId("message-m2")).toHaveTextContent("根据功率选...");
    expect(screen.getByTestId("message-m2").dataset.role).toBe("assistant");
  });

  it("有 citations 时显示折叠面板 (默认收起)", () => {
    renderInI18n(<MessageBubble message={AI_MSG} />);
    expect(screen.getByTestId("citation-panel")).toBeInTheDocument();
    expect(screen.queryByText("1LE1023.pdf")).not.toBeInTheDocument();
  });

  it("点击折叠面板展开, 显示引用", () => {
    renderInI18n(<MessageBubble message={AI_MSG} />);
    fireEvent.click(screen.getByTestId("citation-panel"));
    expect(screen.getByText("1LE1023.pdf")).toBeInTheDocument();
  });

  it("content 含  thinking 标签时提取思考过程并折叠显示", () => {
    const msg: Message = {
      content: "<think>分析中...</think>实际答案",
      createdAt: 1_700_000_002_000,
      id: "m3",
      role: "assistant",
    };
    renderInI18n(<MessageBubble message={msg} />);
    expect(screen.getByTestId("think-toggle")).toBeInTheDocument();
    expect(screen.getByText("分析中...")).toBeInTheDocument();
    expect(screen.getByText("实际答案")).toBeInTheDocument();
  });

  it("interrupted=true 时显示中断徽章", () => {
    renderInI18n(<MessageBubble message={{ ...AI_MSG, interrupted: true }} />);
    expect(screen.getByTestId("interrupted-badge")).toBeInTheDocument();
  });

  // (2026-06-13 Task 21) assistant 消息配对 user 问题 → 渲染 MessageFeedback
  it("assistant 消息配对 user 问题 → 渲染 MessageFeedback (不满意/满意)", () => {
    renderInI18n(<MessageBubble message={AI_MSG} pairedQuestion="1LE 电机怎么选?" />);
    expect(screen.getByTestId("btn-improve-m2")).toBeInTheDocument();
    expect(screen.getByTestId("btn-good-m2")).toBeInTheDocument();
  });

  // (2026-06-30 streamdown 迁移) GFM 启用回归
  // streamdown 内部将 bold 渲染为 <span> + role=strong, 不用原生 <strong>
  it("assistant 消息含 **bold** 时正确渲染 bold 元素", () => {
    const msg: Message = {
      content: "这是 **粗体** 文本",
      createdAt: 1_700_000_003_000,
      id: "m4",
      role: "assistant",
    };
    renderInI18n(<MessageBubble message={msg} />);
    // streamdown 用 <span data-streamdown="strong"> 或 <strong>
    const bold = screen.getByText("粗体");
    expect(["STRONG", "SPAN"]).toContain(bold.tagName);
  });

  it("assistant 消息含 <think> 时, 思考内容进 ThinkBlock, answer 进 MarkdownStream", () => {
    const msg: Message = {
      content: "<think>步骤 1\n步骤 2</think>**最终**答案",
      createdAt: 1_700_000_004_000,
      id: "m5",
      role: "assistant",
    };
    renderInI18n(<MessageBubble message={msg} />);
    // ThinkBlock 渲染
    expect(screen.getByTestId("think-toggle")).toBeInTheDocument();
    // 答案区有 bold 元素
    const bold = screen.getByText("最终");
    expect(["STRONG", "SPAN"]).toContain(bold.tagName);
  });
});
