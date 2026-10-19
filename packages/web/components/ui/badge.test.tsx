import { describe, expect, it } from "vitest";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import { Badge } from "./badge";

describe("Badge", () => {
  it("渲染无报错", () => {
    const { container } = render(<Badge>标签</Badge>);
    expect(container.firstChild).toBeInTheDocument();
  });

  it("渲染不同 variant", () => {
    const { container } = render(<Badge variant="destructive">危险</Badge>);
    expect(container.firstChild).toBeInTheDocument();
  });

  // (2026-07-09) pre-analysis 列表: running badge 用 running variant (绿色, 区分 completed/default 蓝)
  it("running variant 渲染绿色 class", () => {
    const { container } = render(<Badge variant="running">运行中</Badge>);
    const badge = container.firstChild as HTMLElement;
    expect(badge).toBeInTheDocument();
    expect(badge.className).toContain("bg-status-success");
  });
});
