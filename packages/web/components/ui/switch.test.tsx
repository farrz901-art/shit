// Switch 组件单测
import { describe, expect, it } from "vitest";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import { Switch } from "./switch";

describe("Switch", () => {
  it("渲染无报错", () => {
    const { container } = render(<Switch />);
    expect(container.firstChild).toBeInTheDocument();
  });
});
