// DataTableSkeleton 组件单测
import { FIVE, FOUR, THREE } from "@/const";
import { describe, expect, it } from "vitest";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import { DataTableSkeleton } from "./data-table-skeleton";

describe("DataTableSkeleton", () => {
  it("默认 3 列 5 行", () => {
    const { container } = render(<DataTableSkeleton />);
    // 表头行: 3 个 skeleton
    const headerRow = container.firstChild?.firstChild as HTMLElement;
    expect(headerRow?.childElementCount).toBe(THREE);
    // 数据行: 5 行
    const rows = container.querySelectorAll("[class*='flex']");
    expect(rows.length).toBeGreaterThanOrEqual(FIVE);
  });

  it("自定义列数和行数", () => {
    const { container } = render(<DataTableSkeleton columns={4} rows={2} />);
    const headerRow = container.firstChild?.firstChild as HTMLElement;
    expect(headerRow?.childElementCount).toBe(FOUR);
  });
});
