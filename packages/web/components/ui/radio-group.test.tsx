// RadioGroup 组件单测
import { describe, expect, it } from "vitest";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import { RadioGroup, RadioGroupItem } from "./radio-group";

describe("RadioGroup", () => {
  it("渲染无报错", () => {
    const { container } = render(
      <RadioGroup>
        <RadioGroupItem value="a" />
      </RadioGroup>,
    );
    expect(container.firstChild).toBeInTheDocument();
  });
});
