import { describe, expect, it } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import { FadeUp } from "./fade-up";

describe("FadeUp", () => {
  it("show=false 不渲染", () => {
    const { container } = render(<FadeUp show={false}>x</FadeUp>);
    expect(container.textContent).toBe("");
  });
  it("show=true 渲染 children", () => {
    render(<FadeUp show={true}>内容</FadeUp>);
    expect(screen.getByText("内容")).toBeInTheDocument();
  });
});
