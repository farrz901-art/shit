import { describe, expect, it } from "vitest";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import { Button } from "./button";

describe("Button", () => {
  it("渲染无报错", () => {
    const { container } = render(<Button>按钮</Button>);
    expect(container.firstChild).toBeInTheDocument();
  });

  it("渲染不同 variant", () => {
    const { container } = render(<Button variant="destructive">删除</Button>);
    expect(container.firstChild).toBeInTheDocument();
  });

  it("渲染不同 size", () => {
    const { container } = render(<Button size="sm">小按钮</Button>);
    expect(container.firstChild).toBeInTheDocument();
  });

  it("渲染 asChild 模式", () => {
    const { container } = render(
      <Button asChild>
        <a href="/test">链接</a>
      </Button>,
    );
    expect(container.firstChild).toBeInTheDocument();
  });
});
