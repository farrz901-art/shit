import { describe, expect, it, vi } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import {
  getCoreRowModel,
  getPaginationRowModel,
  useReactTable,
  type Table as TanstackTable,
} from "@tanstack/react-table";
import { DataTablePagination } from "./data-table-pagination";
import { ONE } from "@/const/index";
import { IntlWrapper } from "@/lib/test-utils/intl-wrapper";

interface User {
  id: string;
  name: string;
  age: number;
}

const TOTAL_PAGES_FIVE = 5;
const TOTAL_PAGES_ONE = 1;
const TOTAL_COUNT = 100;
const EXPECTED_PREV_PAGE = 2;
const EXPECTED_NEXT_PAGE = 4;
const DISPLAY_PAGE_FIRST = 1;
const DISPLAY_PAGE_MIDDLE = 3;
const DISPLAY_PAGE_LAST = 5;
const AGE_BASE = 25;

const NOOP = (): void => {};

// (2026-06-26) DataTablePagination 现在收 TanStack table 实例, 测试里用 useReactTable 造一个.
//   displayPage 是用户视角 1-based 当前页, 内部 pageIndex = displayPage - 1.
interface HarnessProps {
  displayPage: number;
  totalPages: number;
  total: number;
  onPageChange?: (page: number) => void;
}

const Harness = ({ displayPage, totalPages, total, onPageChange }: HarnessProps): ReactNode => {
  const pageSize = Math.ceil(total / totalPages);
  const data: User[] = Array.from({ length: total }, (_unused, idx) => ({
    age: AGE_BASE + idx,
    id: String(idx),
    name: `用户${idx}`,
  }));
  const table: TanstackTable<User> = useReactTable<User>({
    columns: [],
    data,
    getCoreRowModel: getCoreRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    getRowId: (_row, index) => String(index),
    pageCount: totalPages,
    state: {
      pagination: { pageIndex: displayPage - ONE, pageSize },
    },
  });
  return (
    <DataTablePagination table={table} {...(onPageChange !== undefined ? { onPageChange } : {})} />
  );
};

interface RenderProps {
  totalPages: number;
  current: number;
  total: number;
  onPageChange: (page: number) => void;
}

const renderDefault = (overrides: Partial<RenderProps> = {}) => {
  const props: RenderProps = {
    current: DISPLAY_PAGE_FIRST,
    onPageChange: NOOP,
    total: TOTAL_COUNT,
    totalPages: TOTAL_PAGES_FIVE,
    ...overrides,
  };
  return render(
    <IntlWrapper locale="zh">
      <Harness
        displayPage={props.current}
        onPageChange={props.onPageChange}
        total={props.total}
        totalPages={props.totalPages}
      />
    </IntlWrapper>,
  );
};

describe("DataTablePagination", () => {
  it("totalPages <= 1 不渲染", () => {
    const { container } = renderDefault({ totalPages: TOTAL_PAGES_ONE });
    expect(container.firstChild).toBeNull();
  });

  it("渲染总页数文案", () => {
    renderDefault({
      current: DISPLAY_PAGE_FIRST,
      total: TOTAL_COUNT,
      totalPages: TOTAL_PAGES_FIVE,
    });
    expect(screen.getByText(/第 1 \/ 5 页/)).toBeInTheDocument();
    expect(screen.getByText(/共 100 条/)).toBeInTheDocument();
  });

  it("第 1 页时 Previous disabled", async () => {
    const onPageChange = vi.fn();
    const user = userEvent.setup();
    renderDefault({ current: DISPLAY_PAGE_FIRST, onPageChange, totalPages: TOTAL_PAGES_FIVE });
    await user.click(screen.getByLabelText("上一页"));
    expect(onPageChange).not.toHaveBeenCalled();
  });

  it("中间页点 Previous 触发 onPageChange(current - 1)", async () => {
    const onPageChange = vi.fn();
    const user = userEvent.setup();
    renderDefault({ current: DISPLAY_PAGE_MIDDLE, onPageChange, totalPages: TOTAL_PAGES_FIVE });
    await user.click(screen.getByLabelText("上一页"));
    expect(onPageChange).toHaveBeenCalledWith(EXPECTED_PREV_PAGE);
  });

  it("最后页时 Next disabled", async () => {
    const onPageChange = vi.fn();
    const user = userEvent.setup();
    renderDefault({ current: DISPLAY_PAGE_LAST, onPageChange, totalPages: TOTAL_PAGES_FIVE });
    await user.click(screen.getByLabelText("下一页"));
    expect(onPageChange).not.toHaveBeenCalled();
  });

  it("中间页点 Next 触发 onPageChange(current + 1)", async () => {
    const onPageChange = vi.fn();
    const user = userEvent.setup();
    renderDefault({ current: DISPLAY_PAGE_MIDDLE, onPageChange, totalPages: TOTAL_PAGES_FIVE });
    await user.click(screen.getByLabelText("下一页"));
    expect(onPageChange).toHaveBeenCalledWith(EXPECTED_NEXT_PAGE);
  });
});
