import { describe, expect, it } from "vitest";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import { Textarea } from "./textarea";

describe("Textarea", () => {
  it("渲染无报错", () => {
    const { container } = render(<Textarea placeholder="请输入" />);
    expect(container.firstChild).toBeInTheDocument();
  });
});
