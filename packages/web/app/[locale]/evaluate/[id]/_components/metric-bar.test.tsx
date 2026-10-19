// MetricBar 组件单测
import { describe, expect, it } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import { MetricBar } from "./metric-bar";

describe("MetricBar", () => {
  it("渲染 label + value", () => {
    render(<MetricBar label="准确率" value={0.85} />);
    expect(screen.getByText("准确率")).toBeInTheDocument();
    expect(screen.getByText("0.850")).toBeInTheDocument();
  });

  it("value=null 显示 —", () => {
    render(<MetricBar label="召回率" value={null} />);
    expect(screen.getByText("—")).toBeInTheDocument();
  });

  it("高值 (>=0.7) 用 moss 色", () => {
    const { container } = render(<MetricBar label="F1" value={0.75} />);
    const bar = container.querySelector(".bg-moss");
    expect(bar).toBeInTheDocument();
  });

  it("中值 (>=0.4) 用 warning 色", () => {
    const { container } = render(<MetricBar label="F1" value={0.5} />);
    expect(container.querySelector(".bg-status-warning")).toBeInTheDocument();
  });

  it("低值 (<0.4) 用 destructive 色", () => {
    const { container } = render(<MetricBar label="F1" value={0.2} />);
    expect(container.querySelector(".bg-destructive")).toBeInTheDocument();
  });

  it("自定义 max", () => {
    const { container } = render(<MetricBar label="分" value={80} max={100} />);
    expect(container.querySelector("[style*='width: 80%']")).toBeInTheDocument();
  });
});
