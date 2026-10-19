import { describe, expect, it } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import { AnimateUp } from "./animate-up";

describe("AnimateUp", () => {
  it("show=false 不渲染", () => {
    const { container } = render(<AnimateUp show={false}>x</AnimateUp>);
    expect(container.textContent).toBe("");
  });
  it("show=true 渲染 children", () => {
    render(<AnimateUp show={true}>内容</AnimateUp>);
    expect(screen.getByText("内容")).toBeInTheDocument();
  });
  it("enterFromTop 模式 (通知条)", () => {
    const { container } = render(
      <AnimateUp show={true} enterFromTop>
        提示
      </AnimateUp>,
    );
    expect(container.querySelector("div")).toBeTruthy();
  });
});
