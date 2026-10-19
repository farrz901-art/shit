// Alert 组件单测
import { describe, expect, it } from "vitest";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import { Alert, AlertDescription, AlertTitle } from "./alert";

describe("Alert", () => {
  it("渲染 Alert 无报错", () => {
    const { container } = render(<Alert />);
    expect(container.firstChild).toBeInTheDocument();
  });

  it("渲染 Alert 带有 variant 属性", () => {
    const { container } = render(<Alert variant="destructive" />);
    expect(container.firstChild).toBeInTheDocument();
  });

  it("渲染 AlertTitle 无报错", () => {
    const { container } = render(<AlertTitle />);
    expect(container.firstChild).toBeInTheDocument();
  });

  it("渲染 AlertDescription 无报错", () => {
    const { container } = render(<AlertDescription />);
    expect(container.firstChild).toBeInTheDocument();
  });

  it("渲染 Alert 包含子元素", () => {
    const { getByText } = render(
      <Alert>
        <AlertTitle>标题</AlertTitle>
        <AlertDescription>描述内容</AlertDescription>
      </Alert>,
    );
    expect(getByText("标题")).toBeInTheDocument();
    expect(getByText("描述内容")).toBeInTheDocument();
  });
});
