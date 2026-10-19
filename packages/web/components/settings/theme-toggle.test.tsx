import { describe, expect, it, vi } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import { ONE } from "@/const";
import { ThemeToggle } from "./theme-toggle";
import userEvent from "@testing-library/user-event";

describe("ThemeToggle", () => {
  it("渲染齿轮图标按钮", () => {
    const onOpen = vi.fn();
    render(<ThemeToggle onOpen={onOpen} />);
    const btn = screen.getByRole("button", { name: /设置/ });
    expect(btn).toBeInTheDocument();
  });

  it("点击触发 onOpen 回调", async () => {
    const onOpen = vi.fn();
    render(<ThemeToggle onOpen={onOpen} />);
    await userEvent.click(screen.getByRole("button", { name: /设置/ }));
    expect(onOpen).toHaveBeenCalledTimes(ONE);
  });
});
