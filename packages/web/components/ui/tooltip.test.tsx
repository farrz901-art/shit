// Tooltip 组件单测
import { describe, expect, it } from "vitest";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "./tooltip";

describe("Tooltip", () => {
  it("渲染 Tooltip 无报错", () => {
    const { container } = render(
      <TooltipProvider>
        <Tooltip>
          <TooltipTrigger asChild>
            <span>悬停</span>
          </TooltipTrigger>
          <TooltipContent>提示内容</TooltipContent>
        </Tooltip>
      </TooltipProvider>,
    );
    expect(container.firstChild).toBeInTheDocument();
  });
});
