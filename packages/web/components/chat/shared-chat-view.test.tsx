// SharedChatView 单测 (2026-06-16) — 公开 share 只读视图
// 验证: 渲染 messages; 不渲染 MessageFeedback; 不渲染 Composer
import { describe, expect, it } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";

import { SharedChatView } from "./shared-chat-view";

describe("SharedChatView", () => {
  it("渲染 messages (user + assistant)", () => {
    render(
      <SharedChatView
        shareId="x"
        title="t"
        messages={[
          { content: "hi", role: "user" },
          { content: "hello", role: "assistant" },
        ]}
        model="gpt-4o-mini"
        createdAt="2026-06-16"
      />,
    );
    expect(screen.getByText("hi")).toBeInTheDocument();
    expect(screen.getByText("hello")).toBeInTheDocument();
  });

  it("不渲染 MessageFeedback (无 data-testid 包含 'feedback')", () => {
    render(
      <SharedChatView
        shareId="x"
        title="t"
        messages={[{ content: "x", role: "assistant" }]}
        model=""
        createdAt=""
      />,
    );
    expect(screen.queryByTestId(/message-feedback/i)).not.toBeInTheDocument();
  });

  it("不渲染 Composer (无 data-testid='composer-textarea')", () => {
    render(<SharedChatView shareId="x" title="t" messages={[]} model="" createdAt="" />);
    expect(screen.queryByTestId("composer-textarea")).not.toBeInTheDocument();
  });
});
