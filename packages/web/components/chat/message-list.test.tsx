// MessageList 组件单测
import { describe, expect, it, vi } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import { MessageList } from "./message-list";

vi.mock("./message-bubble", () => ({
  MessageBubble: ({ message }: any) => (
    <div data-testid="msg-bubble">
      {message.role}: {message.content}
    </div>
  ),
}));

describe("MessageList", () => {
  it("空消息显示提示", () => {
    render(<MessageList messages={[]} />);
    expect(screen.getByText(/新对话/)).toBeInTheDocument();
  });

  it("有消息渲染气泡", () => {
    render(<MessageList messages={[{ id: "m1", role: "user", content: "你好", createdAt: 1 }]} />);
    expect(screen.getByTestId("msg-bubble")).toBeInTheDocument();
  });

  it("有 streamingMessageId 显示光标", () => {
    const { container } = render(
      <MessageList
        messages={[{ id: "m1", role: "user", content: "hi", createdAt: 1 }]}
        streamingMessageId="m1"
      />,
    );
    expect(container.querySelector(".animate-pulse")).toBeInTheDocument();
  });
});
