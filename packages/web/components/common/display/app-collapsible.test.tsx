import { describe, expect, it } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import userEvent from "@testing-library/user-event";
import { AppCollapsible } from "./app-collapsible";

describe("AppCollapsible", () => {
  it("渲染 title 文本", () => {
    render(
      <AppCollapsible title="思考过程">
        <p>content</p>
      </AppCollapsible>,
    );
    expect(screen.getByText("思考过程")).toBeInTheDocument();
  });

  it("默认不展开", () => {
    render(
      <AppCollapsible title="test">
        <p>content</p>
      </AppCollapsible>,
    );
    expect(screen.queryByText("content")).not.toBeInTheDocument();
  });

  it("defaultOpen 时渲染内容", () => {
    render(
      <AppCollapsible title="test" defaultOpen>
        <p>content</p>
      </AppCollapsible>,
    );
    expect(screen.getByText("content")).toBeInTheDocument();
  });

  it("点击 trigger 展开/收起", async () => {
    const user = userEvent.setup();
    render(
      <AppCollapsible title="toggle">
        <p>content</p>
      </AppCollapsible>,
    );
    expect(screen.queryByText("content")).not.toBeInTheDocument();
    await user.click(screen.getByText("toggle"));
    expect(screen.getByText("content")).toBeInTheDocument();
  });

  it("受控模式: open/onOpenChange", async () => {
    const user = userEvent.setup();
    let open = false;
    const onOpenChange = (val: boolean) => {
      open = val;
    };
    render(
      <AppCollapsible title="ctl" open={open} onOpenChange={onOpenChange}>
        <p>content</p>
      </AppCollapsible>,
    );
    expect(screen.queryByText("content")).not.toBeInTheDocument();
    await user.click(screen.getByText("ctl"));
    expect(open).toBe(true);
  });

  it("自定义 icon 渲染", () => {
    render(
      <AppCollapsible title="ic" icon={<span data-testid="custom-icon" />}>
        <p>c</p>
      </AppCollapsible>,
    );
    expect(screen.getByTestId("custom-icon")).toBeInTheDocument();
  });
});
