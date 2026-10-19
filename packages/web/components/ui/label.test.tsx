import { describe, expect, it } from "vitest";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import { Label } from "./label";

describe("Label", () => {
  it("渲染无报错", () => {
    const { container } = render(<Label>用户名</Label>);
    expect(container.firstChild).toBeInTheDocument();
  });
});
