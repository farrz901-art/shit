// TablesPaginationBar 组件测试 (mode 1 mock fetch + jsdom)

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { IntlWrapper } from "@/lib/test-utils/intl-wrapper";
import { TablesPaginationBar } from "./admin-pre-analysis-tables-pagination";

describe("TablesPaginationBar", () => {
  it("renders all page buttons (no ellipsis) when total count <= threshold", () => {
    const onPageChange = vi.fn();
    render(
      <IntlWrapper locale="zh">
        <TablesPaginationBar allPages={[3, 9, 12]} currentPage={9} onPageChange={onPageChange} />
      </IntlWrapper>,
    );
    const buttons = screen.getAllByTestId(/^page-button-/);
    expect(buttons).toHaveLength(3);
    expect(screen.queryByTestId("ellipsis-left")).toBeNull();
    expect(screen.queryByTestId("ellipsis-right")).toBeNull();
  });

  it("click page button → onPageChange 收到对应页号", async () => {
    const onPageChange = vi.fn();
    const user = userEvent.setup();
    render(
      <IntlWrapper locale="zh">
        <TablesPaginationBar allPages={[3, 9, 12]} currentPage={9} onPageChange={onPageChange} />
      </IntlWrapper>,
    );
    await user.click(screen.getByTestId("page-button-12"));
    expect(onPageChange).toHaveBeenCalledWith(12);
  });

  it("当前页按钮 aria-current=page", () => {
    render(
      <IntlWrapper locale="zh">
        <TablesPaginationBar allPages={[3, 9, 12]} currentPage={9} onPageChange={vi.fn()} />
      </IntlWrapper>,
    );
    const current = screen.getByTestId("page-button-9");
    expect(current.getAttribute("aria-current")).toBe("page");
  });

  it("空 pages 数组 → 渲染 null", () => {
    const { container } = render(
      <IntlWrapper locale="zh">
        <TablesPaginationBar allPages={[]} currentPage={null} onPageChange={vi.fn()} />
      </IntlWrapper>,
    );
    expect(container.querySelector('[data-testid="tables-pagination"]')).toBeNull();
  });

  it("页数较多且当前不在中段 → 至少触发一侧 ellipsis", () => {
    // 12 页 + 当前 P6: 算法实际不渲染左 ellipsis (P3 紧邻 siblings 起),
    // 只渲染右 ellipsis (P11, P12 在右半). 测该场景右 ellipsis 存在 + 左 ellipsis 不存在.
    const allPages = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12];
    render(
      <IntlWrapper locale="zh">
        <TablesPaginationBar allPages={allPages} currentPage={6} onPageChange={vi.fn()} />
      </IntlWrapper>,
    );
    expect(screen.getByTestId("ellipsis-right")).toBeTruthy();
    expect(screen.queryByTestId("ellipsis-left")).toBeNull();
  });

  it("页数较多且当前在中段 → 左右 ellipsis 都渲染", () => {
    // 20 页 + 当前 P10 (中段): 应同时触发左右 ellipsis.
    const allPages = Array.from({ length: 20 }, (_unused, idx) => idx + 1);
    render(
      <IntlWrapper locale="zh">
        <TablesPaginationBar allPages={allPages} currentPage={10} onPageChange={vi.fn()} />
      </IntlWrapper>,
    );
    expect(screen.getByTestId("ellipsis-left")).toBeTruthy();
    expect(screen.getByTestId("ellipsis-right")).toBeTruthy();
  });

  it("上一页 / 下一页 按钮存在", () => {
    render(
      <IntlWrapper locale="zh">
        <TablesPaginationBar allPages={[3, 9, 12]} currentPage={9} onPageChange={vi.fn()} />
      </IntlWrapper>,
    );
    expect(screen.getByTestId("page-prev")).toBeTruthy();
    expect(screen.getByTestId("page-next")).toBeTruthy();
  });
});
