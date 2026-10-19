// Calendar 组件单测
import { describe, expect, it } from "vitest";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import { Calendar } from "./calendar";

describe("Calendar", () => {
  it("渲染无报错", () => {
    const { container } = render(<Calendar mode="single" />);
    expect(container.firstChild).toBeInTheDocument();
  });
});
