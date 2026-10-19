// DropdownMenu 组件单测
import { describe, expect, it } from "vitest";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "./dropdown-menu";

describe("DropdownMenu", () => {
  it("渲染无报错", () => {
    const { container } = render(
      <DropdownMenu>
        <DropdownMenuTrigger>菜单</DropdownMenuTrigger>
        <DropdownMenuContent>
          <DropdownMenuItem>选项一</DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>,
    );
    expect(container.firstChild).toBeInTheDocument();
  });
});
