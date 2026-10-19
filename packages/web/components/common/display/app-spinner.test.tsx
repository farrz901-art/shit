import { describe, expect, it } from "vitest";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import { Spinner } from "./app-spinner";

describe("Spinner", () => {
  it("渲染元素", () => {
    const { container } = render(<Spinner />);
    expect(container.querySelector("span")).toBeTruthy();
  });
});
