// Separator 组件单测
import { describe, expect, it } from "vitest";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import { Separator } from "./separator";

describe("Separator", () => {
  it("渲染无报错", () => {
    const { container } = render(<Separator />);
    expect(container.firstChild).toBeInTheDocument();
  });
});
