// DataEmpty 组件单测
import { describe, expect, it } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import { Database } from "lucide-react";
import { DataEmpty } from "./app-data-empty";

describe("DataEmpty", () => {
  it("渲染 title", () => {
    render(<DataEmpty title="暂无数据" />);
    expect(screen.getByText("暂无数据")).toBeInTheDocument();
  });

  it("渲染 icon + description", () => {
    render(<DataEmpty icon={Database} title="空" description="还没有内容" />);
    expect(screen.getByText("空")).toBeInTheDocument();
    expect(screen.getByText("还没有内容")).toBeInTheDocument();
  });

  it("variant=page 加 border", () => {
    const { container } = render(<DataEmpty title="空" variant="page" />);
    // Variant page 不应该有 border-0 类
    expect(container.querySelector("[class*='border']")?.className).not.toContain("border-0");
  });

  it("variant=table (默认) 有 border-0", () => {
    const { container } = render(<DataEmpty title="空" />);
    expect(container.querySelector("[class*='border-0']")).toBeInTheDocument();
  });

  it("不传 icon 时不渲染图标区", () => {
    const { container } = render(<DataEmpty title="空" />);
    // 不传 icon 时 EmptyMedia 内部不应有 svg
    expect(container.querySelector("svg")).toBeNull();
  });
});
