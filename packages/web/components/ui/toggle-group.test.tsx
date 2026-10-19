// ToggleGroup 组件单测
import { describe, expect, it } from "vitest";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import { ToggleGroup, ToggleGroupItem } from "./toggle-group";

describe("ToggleGroup", () => {
  it("渲染 ToggleGroup 无报错", () => {
    const { container } = render(<ToggleGroup type="single" />);
    expect(container.firstChild).toBeInTheDocument();
  });

  it("渲染 ToggleGroup 包含多个 ToggleGroupItem", () => {
    const { getByText } = render(
      <ToggleGroup type="single">
        <ToggleGroupItem value="a">选项A</ToggleGroupItem>
        <ToggleGroupItem value="b">选项B</ToggleGroupItem>
        <ToggleGroupItem value="c">选项C</ToggleGroupItem>
      </ToggleGroup>,
    );
    expect(getByText("选项A")).toBeInTheDocument();
    expect(getByText("选项B")).toBeInTheDocument();
    expect(getByText("选项C")).toBeInTheDocument();
  });
});
