import { describe, expect, it, vi } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import { AppDrawer } from "./app-drawer";

describe("AppDrawer", () => {
  it("open=true 渲染 title + children", () => {
    render(
      <AppDrawer open={true} onOpenChange={vi.fn()} title="详情">
        <p>内容</p>
      </AppDrawer>,
    );
    expect(screen.getByText("详情")).toBeInTheDocument();
    expect(screen.getByText("内容")).toBeInTheDocument();
  });

  it("open=false 不渲染", () => {
    render(
      <AppDrawer open={false} onOpenChange={vi.fn()} title="详情">
        <p>内容</p>
      </AppDrawer>,
    );
    expect(screen.queryByText("内容")).not.toBeInTheDocument();
  });
});
