// AppTabs 单元测试 (antd 风格 Tabs 包装)
// 替 shadcn Tabs 三件套 (Tabs + TabsList + TabsTrigger) 为 1 行 API
// 两种用法: 1) 纯 trigger 模式 (无 content)  2) 带 content 模式 (有 content 自动包 TabsContent)
import { afterEach, describe, expect, it, vi } from "vitest";
import { fireEvent, screen } from "@testing-library/react";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";

import { AppTabs } from "./app-tabs";

describe("AppTabs", () => {
  afterEach(() => vi.restoreAllMocks());

  it("纯 trigger 模式: 渲染所有 options 为 trigger", () => {
    render(
      <AppTabs
        options={[
          { label: "全部", value: "all" },
          { label: "待审", value: "pending" },
        ]}
        value="all"
      />,
    );
    expect(screen.getByText("全部")).toBeInTheDocument();
    expect(screen.getByText("待审")).toBeInTheDocument();
  });

  it("受控 value: active trigger 标 data-state=active", () => {
    render(
      <AppTabs
        options={[
          { label: "全部", value: "all" },
          { label: "待审", value: "pending" },
        ]}
        value="pending"
      />,
    );
    expect(screen.getByText("全部").getAttribute("data-state")).toBe("inactive");
    expect(screen.getByText("待审").getAttribute("data-state")).toBe("active");
  });

  it("点 trigger 调 onChange(value)", async () => {
    const onChange = vi.fn();
    const userEventModule = await import("@testing-library/user-event");
    const userEvent = userEventModule.default;
    const user = userEvent.setup();
    render(
      <AppTabs
        options={[
          { label: "全部", value: "all" },
          { label: "待审", value: "pending" },
        ]}
        value="all"
        onChange={onChange}
      />,
    );
    // UserEvent 模拟真实点击, 触发 Radix Tabs onValueChange
    await user.click(screen.getByText("待审"));
    expect(onChange).toHaveBeenCalledWith("pending");
  });

  it("纯 trigger 模式: 任何 option 都没 content → 不渲染 TabsContent", () => {
    render(
      <AppTabs
        options={[
          { label: "全部", value: "all" },
          { label: "待审", value: "pending" },
        ]}
        value="all"
      />,
    );
    // TabsContent 默认 data-state="inactive" 且 hidden, 但 DOM 里应该没 content
    expect(screen.queryByTestId("panel-content")).toBeNull();
  });

  it("带 content 模式: 渲染 TabsContent 包裹 content", () => {
    render(
      <AppTabs
        options={[
          {
            content: <div data-testid="panel-content">我的列表</div>,
            label: "我的",
            value: "mine",
          },
          { content: <div>全部列表</div>, label: "全部", value: "all" },
        ]}
        value="mine"
      />,
    );
    // Active tab 的 TabsContent 显示 content (Radix 默认 active 内容显示)
    expect(screen.getByTestId("panel-content")).toBeInTheDocument();
    expect(screen.getByTestId("panel-content")).toHaveTextContent("我的列表");
  });

  it("dataTestid 前缀应用到 trigger (testid-{value})", () => {
    render(
      <AppTabs
        dataTestid="filter-tab"
        options={[
          { label: "全部", value: "all" },
          { label: "待审", value: "pending" },
        ]}
        value="all"
      />,
    );
    expect(screen.getByTestId("filter-tab-all")).toBeInTheDocument();
    expect(screen.getByTestId("filter-tab-pending")).toBeInTheDocument();
  });

  it("disabled option 不响应点击", () => {
    const onChange = vi.fn();
    render(
      <AppTabs
        options={[
          { label: "全部", value: "all" },
          { disabled: true, label: "待审", value: "pending" },
        ]}
        value="all"
        onChange={onChange}
      />,
    );
    fireEvent.click(screen.getByText("待审"));
    expect(onChange).not.toHaveBeenCalled();
  });
});
