import { describe, expect, it } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import userEvent from "@testing-library/user-event";
import { ThinkBlock } from "./think-block";

describe("ThinkBlock", () => {
  it("默认折叠, 显示 '思考过程' 标题", () => {
    render(<ThinkBlock>分析中...</ThinkBlock>);
    expect(screen.getByText("思考过程")).toBeInTheDocument();
    expect(screen.queryByText("分析中...")).not.toBeInTheDocument();
  });

  it("点击 trigger 展开, 显示 children", async () => {
    const user = userEvent.setup();
    render(<ThinkBlock>实际思考内容</ThinkBlock>);
    await user.click(screen.getByText("思考过程"));
    expect(screen.getByText("实际思考内容")).toBeInTheDocument();
  });

  it("defaultOpen=true 时默认展开", () => {
    render(<ThinkBlock defaultOpen>已展开内容</ThinkBlock>);
    expect(screen.getByText("已展开内容")).toBeInTheDocument();
  });

  it("数据 testId 透传到 AppCollapsible", () => {
    render(<ThinkBlock testId="think-toggle">x</ThinkBlock>);
    expect(screen.getByTestId("think-toggle")).toBeInTheDocument();
  });
});
