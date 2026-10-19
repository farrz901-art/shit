// StatCard 组件单测
import { describe, expect, it } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import { StatCard } from "./app-stat-card";

describe("StatCard", () => {
  it("渲染 label + 数字 value (CountUp 从 0 开始)", () => {
    render(<StatCard label="总数" value={42} />);
    expect(screen.getByText("总数")).toBeInTheDocument();
    // CountUp jsdom 下从 0 开始动画
    const numSpan = screen.getByText("0");
    expect(numSpan).toBeInTheDocument();
    expect(numSpan.className).toContain("num");
  });

  it("渲染 hint", () => {
    render(<StatCard label="延迟" value="10ms" hint="P95" />);
    expect(screen.getByText("10ms")).toBeInTheDocument();
    expect(screen.getByText("P95")).toBeInTheDocument();
  });

  it("字符串 value 不套 CountUp", () => {
    const { container } = render(<StatCard label="状态" value="正常" />);
    expect(container.querySelector("[class*='num']")).toHaveTextContent("正常");
  });
});
