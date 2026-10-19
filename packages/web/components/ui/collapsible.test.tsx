// Collapsible 组件单测
import { describe, expect, it } from "vitest";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "./collapsible";

describe("Collapsible", () => {
  it("渲染 Collapsible 无报错", () => {
    const { container } = render(<Collapsible />);
    expect(container.firstChild).toBeInTheDocument();
  });

  it("渲染 Collapsible 含 Trigger 和 Content", () => {
    const { container } = render(
      <Collapsible>
        <CollapsibleTrigger asChild>
          <span>展开</span>
        </CollapsibleTrigger>
        <CollapsibleContent>折叠内容</CollapsibleContent>
      </Collapsible>,
    );
    expect(container.firstChild).toBeInTheDocument();
  });
});
