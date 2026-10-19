// ErrorBanner 变体单测 (纯渲染, 不测 ErrorBoundary 内部逻辑)
import { describe, expect, it } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import { ErrorBanner } from "./app-error-banner";

describe("ErrorBanner", () => {
  it("渲染标题", () => {
    render(<ErrorBanner title="错误" description="详情" />);
    expect(screen.getByText("错误")).toBeInTheDocument();
  });

  it("渲染描述", () => {
    render(<ErrorBanner title="错" description="详情" />);
    expect(screen.getByText("详情")).toBeInTheDocument();
  });

  it("success variant", () => {
    render(<ErrorBanner title="成功" variant="success" description="详情" />);
    expect(screen.getByText("成功")).toBeInTheDocument();
  });
});
