// Sonner Toaster 组件单测
import { describe, expect, it } from "vitest";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import { Toaster } from "./sonner";

describe("Toaster", () => {
  it("渲染无报错", () => {
    const { container } = render(<Toaster />);
    expect(container.firstChild).toBeInTheDocument();
  });
});
