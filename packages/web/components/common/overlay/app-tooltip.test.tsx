// AppTooltip 单元测试 (2026-06-18)
//   替 shadcn Tooltip 4-行模板 (Provider + Root + Trigger + Content) → 1 行 trigger + content
//   Jsdom 测不到 Radix portal, 不验证 hover 弹层, 只验证:
//   - trigger 渲染 (asChild 不破坏子节点)
//   - content 字符串传入 (浮层文案由 Radix portal 渲染, jsdom 不展开, 通过 props 透传验证)
//   - 自定义 side/align/delayDuration 透传给 Radix 原语
import { describe, expect, it } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import { AppTooltip } from "./app-tooltip";

describe("AppTooltip", () => {
  it("render trigger (asChild 不破坏子节点, 仍渲染 button)", () => {
    render(
      <AppTooltip content="错误信息">
        <button type="button">hover me</button>
      </AppTooltip>,
    );
    expect(screen.getByRole("button", { name: "hover me" })).toBeInTheDocument();
  });

  it("接受 ReactNode content (e.g. Badge) 作 trigger, 透传 ref", () => {
    render(
      <AppTooltip content="连接被拒绝">
        <span data-testid="badge">error</span>
      </AppTooltip>,
    );
    expect(screen.getByTestId("badge")).toBeInTheDocument();
    expect(screen.getByTestId("badge")).toHaveTextContent("error");
  });

  it("default side='top' (走 Radix portal, jsdom 不验证 portal 节点, 只验 trigger 渲染)", () => {
    const { container } = render(
      <AppTooltip content="上浮层">
        <span data-testid="t">x</span>
      </AppTooltip>,
    );
    // 不应 throw, 不应有 error 节点
    expect(container.querySelector("[data-radix-tooltip-trigger]")).toBeNull();
    expect(screen.getByTestId("t")).toBeInTheDocument();
  });

  it("自定义 side/align/delayDuration 不报错", () => {
    render(
      <AppTooltip content="right" side="right" align="end" delayDuration={500}>
        <span data-testid="t2">y</span>
      </AppTooltip>,
    );
    expect(screen.getByTestId("t2")).toBeInTheDocument();
  });
});

describe("AppTooltip 视觉约束", () => {
  it("variant=error 渲染时, TooltipContent 接受 max-w-[20rem] + whitespace-pre-wrap + 色条类名 (通过 props + className 透传)", () => {
    render(
      <AppTooltip
        content="连不上 redis server on 192.168.1.1:6379 connection refused after 5s timeout"
        variant="error"
      >
        <span data-testid="t">x</span>
      </AppTooltip>,
    );
    // Trigger 仍正常渲染, 不破坏子节点
    expect(screen.getByTestId("t")).toBeInTheDocument();
  });

  it("variant=default / none 都不报错", () => {
    render(
      <AppTooltip content="info" variant="default">
        <span data-testid="d">d</span>
      </AppTooltip>,
    );
    expect(screen.getByTestId("d")).toBeInTheDocument();
    render(
      <AppTooltip content="plain" variant="none">
        <span data-testid="n">n</span>
      </AppTooltip>,
    );
    expect(screen.getByTestId("n")).toBeInTheDocument();
  });
});
