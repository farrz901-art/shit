import { ONE, ZERO } from "@/const";
import { describe, expect, it, vi } from "vitest";
import { fireEvent, screen } from "@testing-library/react";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import type { Conversation } from "@/lib/chat/types";
import { ConversationList } from "./conversation-list";

const CONVERSATIONS: Conversation[] = [
  {
    createdAt: 1_700_000_000_000,
    id: "a",
    messageCount: 5,
    title: "电机选型",
    updatedAt: 1_700_000_003_000,
  },
  {
    createdAt: 1_700_000_001_000,
    id: "b",
    messageCount: 3,
    title: "产品报价",
    updatedAt: 1_700_000_002_000,
  },
];

describe("ConversationList", () => {
  it("渲染所有会话 + 标题", () => {
    render(
      <ConversationList
        conversations={CONVERSATIONS}
        currentId="a"
        onSelect={vi.fn()}
        onCreate={vi.fn()}
        onDelete={vi.fn()}
      />,
    );
    expect(screen.getByText("电机选型")).toBeInTheDocument();
    expect(screen.getByText("产品报价")).toBeInTheDocument();
  });

  it("按 updatedAt 倒序", () => {
    render(
      <ConversationList
        conversations={CONVERSATIONS}
        currentId="a"
        onSelect={vi.fn()}
        onCreate={vi.fn()}
        onDelete={vi.fn()}
      />,
    );
    const items = screen.getAllByTestId(/^conv-/);
    expect(items[ZERO]).toHaveAttribute("data-testid", "conv-a");
    expect(items[ONE]).toHaveAttribute("data-testid", "conv-b");
  });

  it("currentId 高亮", () => {
    render(
      <ConversationList
        conversations={CONVERSATIONS}
        currentId="a"
        onSelect={vi.fn()}
        onCreate={vi.fn()}
        onDelete={vi.fn()}
      />,
    );
    expect(screen.getByTestId("conv-a").className).toContain("border-clay");
  });

  it("点新对话按钮触发 onCreate", () => {
    const onCreate = vi.fn();
    render(
      <ConversationList
        conversations={CONVERSATIONS}
        currentId="a"
        onSelect={vi.fn()}
        onCreate={onCreate}
        onDelete={vi.fn()}
      />,
    );
    fireEvent.click(screen.getByTestId("new-conv"));
    expect(onCreate).toHaveBeenCalled();
  });

  it("点会话触发 onSelect(id)", () => {
    const onSelect = vi.fn();
    render(
      <ConversationList
        conversations={CONVERSATIONS}
        currentId="a"
        onSelect={onSelect}
        onCreate={vi.fn()}
        onDelete={vi.fn()}
      />,
    );
    fireEvent.click(screen.getByTestId("conv-b"));
    expect(onSelect).toHaveBeenCalledWith("b");
  });

  it("无会话时显示空状态", () => {
    render(
      <ConversationList
        conversations={[]}
        currentId={null}
        onSelect={vi.fn()}
        onCreate={vi.fn()}
        onDelete={vi.fn()}
      />,
    );
    expect(screen.getByTestId("empty-conv")).toBeInTheDocument();
  });
});
