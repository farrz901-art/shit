// StatusBadge 测试 (2026-06-15) — 重构成 shadcn Badge + 保留 5 evaluation 状态
// 覆盖: 5 状态渲染 / 默认中文 label / shadcn destructive variant / animate-pulse
// 跟 task-status-badge 风格统一 (用 @/components/ui/badge)
import { describe, expect, it } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import { StatusBadge } from "./status-badge";

describe("StatusBadge", () => {
  it("completed 状态显示中文 '完成' + 用 moss 自定义色 (shadcn 无 success variant)", () => {
    const { container } = render(<StatusBadge status="completed" />);
    expect(screen.getByText("完成")).toBeInTheDocument();
    expect(container.querySelector("div")?.className).toContain("bg-moss");
  });

  it("running 状态显示 '跑中' + 带 animate-pulse", () => {
    const { container } = render(<StatusBadge status="running" />);
    expect(screen.getByText("跑中")).toBeInTheDocument();
    expect(container.querySelector("div")?.className).toContain("animate-pulse");
  });

  it("failed 状态显示 '失败' + 用 destructive variant", () => {
    const { container } = render(<StatusBadge status="failed" />);
    expect(screen.getByText("失败")).toBeInTheDocument();
    expect(container.querySelector("div")?.className).toContain("bg-destructive");
  });

  it("cancelled 状态显示 '已取消'", () => {
    render(<StatusBadge status="cancelled" />);
    expect(screen.getByText("已取消")).toBeInTheDocument();
  });

  it("pending 状态显示 '排队'", () => {
    render(<StatusBadge status="pending" />);
    expect(screen.getByText("排队")).toBeInTheDocument();
  });

  it("className 透传 (override 默认 + 加 margin)", () => {
    const { container } = render(<StatusBadge status="completed" className="ml-2" />);
    expect(container.querySelector("div")?.className).toContain("ml-2");
  });
});
