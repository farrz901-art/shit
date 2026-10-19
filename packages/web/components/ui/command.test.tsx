// Command 组件单测
import { beforeAll, describe, expect, it, vi } from "vitest";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "./command";

// Jsdom 没有 scrollIntoView, cmdk 依赖它
beforeAll(() => {
  Element.prototype.scrollIntoView = vi.fn();
});

describe("Command", () => {
  it("渲染无报错", () => {
    const { container } = render(
      <Command>
        <CommandInput placeholder="搜索..." />
        <CommandList>
          <CommandEmpty>无结果</CommandEmpty>
          <CommandGroup heading="分组">
            <CommandItem>条目一</CommandItem>
          </CommandGroup>
        </CommandList>
      </Command>,
    );
    expect(container.firstChild).toBeInTheDocument();
  });
});
