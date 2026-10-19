// Checkbox 组件单测
import { describe, expect, it } from "vitest";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import { Checkbox } from "./checkbox";

describe("Checkbox", () => {
  it("渲染 Checkbox 无报错", () => {
    const { container } = render(<Checkbox />);
    expect(container.firstChild).toBeInTheDocument();
  });

  it("渲染 Checkbox 带有 checked 属性", () => {
    const { container } = render(<Checkbox checked />);
    expect(container.firstChild).toBeInTheDocument();
  });

  it("渲染 Checkbox 带有 disabled 属性", () => {
    const { container } = render(<Checkbox disabled />);
    expect(container.firstChild).toBeInTheDocument();
  });
});
