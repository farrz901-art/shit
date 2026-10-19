// BreathingDot 单元测试 (2026-06-15): 5 case
//   覆盖默认 render / color 枚举 / size 枚举 / title 透传 / className 透传
//   Tailwind 类名为字符串子串断言, 不依赖 jsdom 渲染样式
import { ONE, TWO, ZERO } from "@/const";
import { describe, expect, it } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";

import { BreathingDot } from "./app-breathing-dot";

describe("BreathingDot", () => {
  it("默认 render: moss 色 + sm 尺寸 + ping 层存在", () => {
    render(<BreathingDot data-testid="dot" />);
    const root = screen.getByTestId("dot");
    // 容器尺寸 sm = h-1.5 w-1.5
    expect(root.className).toContain("h-1.5");
    expect(root.className).toContain("w-1.5");
    // 内部应有 2 层 span: ping 层 + 实心层
    const inner = root.querySelectorAll("span");
    expect(inner.length).toBe(TWO);
    // Ping 层带 animate-ping + moss/60
    expect(inner[ZERO].className).toContain("animate-ping");
    expect(inner[ZERO].className).toContain("bg-moss/60");
    // 实心层 moss
    expect(inner[ONE].className).toContain("bg-moss");
  });

  it("color='success' 切到 status-success 色", () => {
    render(<BreathingDot color="success" data-testid="dot" />);
    const inner = screen.getByTestId("dot").querySelectorAll("span");
    expect(inner[ZERO].className).toContain("bg-status-success/60");
    expect(inner[ONE].className).toContain("bg-status-success");
  });

  it("color='error' 切到 status-error 色", () => {
    render(<BreathingDot color="error" data-testid="dot" />);
    const inner = screen.getByTestId("dot").querySelectorAll("span");
    expect(inner[ZERO].className).toContain("bg-status-error/60");
    expect(inner[ONE].className).toContain("bg-status-error");
  });

  it("size='md' 切到 2.5×2.5", () => {
    render(<BreathingDot size="md" data-testid="dot" />);
    const root = screen.getByTestId("dot");
    expect(root.className).toContain("h-2.5");
    expect(root.className).toContain("w-2.5");
  });

  it("title 透传到容器, className 合并到容器", () => {
    render(<BreathingDot title="Dify 监控" className="ml-1" data-testid="dot" />);
    const root = screen.getByTestId("dot");
    expect(root).toHaveAttribute("title", "Dify 监控");
    expect(root.className).toContain("ml-1");
  });
});
