// ErrorBanner 单元测试 (2026-06-14): 5 variant + title + action slot
import { describe, expect, it } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import { ErrorBanner } from "./app-error-banner";

describe("ErrorBanner", () => {
  it("destructive variant by default", () => {
    render(<ErrorBanner description="加载失败" dataTestid="banner" />);
    expect(screen.getByText("加载失败")).toBeInTheDocument();
    expect(screen.getByTestId("banner")).toBeInTheDocument();
  });

  it("success variant", () => {
    render(<ErrorBanner variant="success" description="保存成功" dataTestid="banner" />);
    expect(screen.getByText("保存成功")).toBeInTheDocument();
  });

  it("warning variant", () => {
    render(<ErrorBanner variant="warning" description="注意" dataTestid="banner" />);
    expect(screen.getByText("注意")).toBeInTheDocument();
  });

  it("info variant", () => {
    render(<ErrorBanner variant="info" description="提示" dataTestid="banner" />);
    expect(screen.getByText("提示")).toBeInTheDocument();
  });

  it("title 渲染", () => {
    render(<ErrorBanner title="标题" description="描述" dataTestid="banner" />);
    expect(screen.getByText("标题")).toBeInTheDocument();
    expect(screen.getByText("描述")).toBeInTheDocument();
  });

  it("action slot 渲染 (右侧按钮)", () => {
    render(
      <ErrorBanner
        description="失败"
        action={<button type="button">重试</button>}
        dataTestid="banner"
      />,
    );
    expect(screen.getByRole("button", { name: "重试" })).toBeInTheDocument();
  });

  it("descriptionNode 优先于 description (复杂子节点, 2026-06-29 P1)", () => {
    render(
      <ErrorBanner
        description="被忽略"
        descriptionNode={
          <ul data-testid="err-list">
            <li>错 1</li>
            <li>错 2</li>
          </ul>
        }
        dataTestid="banner"
      />,
    );
    expect(screen.getByTestId("err-list")).toBeInTheDocument();
    expect(screen.queryByText("被忽略")).not.toBeInTheDocument();
  });
});
