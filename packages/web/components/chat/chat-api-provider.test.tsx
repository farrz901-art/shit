// ChatApiProvider 组件单测
import { describe, expect, it } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import { ChatApiProvider } from "./chat-api-provider";

describe("ChatApiProvider", () => {
  it("包裹子组件", () => {
    render(
      <ChatApiProvider>
        <div data-testid="child">内容</div>
      </ChatApiProvider>,
    );
    expect(screen.getByTestId("child")).toHaveTextContent("内容");
  });
});
