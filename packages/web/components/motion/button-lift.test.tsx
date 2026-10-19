import { describe, expect, it } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import { ButtonLift } from "./button-lift";

describe("ButtonLift", () => {
  it("渲染子元素", () => {
    render(
      <ButtonLift>
        <span data-testid="child">x</span>
      </ButtonLift>,
    );
    expect(screen.getByTestId("child")).toBeInTheDocument();
  });
});
