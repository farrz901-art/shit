import { describe, expect, it } from "vitest";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import { Input } from "./input";

describe("Input", () => {
  it("渲染无报错", () => {
    const { container } = render(<Input placeholder="请输入" />);
    expect(container.firstChild).toBeInTheDocument();
  });

  it("渲染不同类型", () => {
    const { container } = render(<Input type="email" placeholder="邮箱" />);
    expect(container.firstChild).toBeInTheDocument();
  });
});
