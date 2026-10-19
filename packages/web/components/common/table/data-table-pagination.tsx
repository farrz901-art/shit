// DataTable 分页 UI 组件 (2026-06-25 拆分自 data-table.tsx, 2026-06-26 换底)
// 接收 TanStack table 实例, 从 table.getState().pagination 派生 current/totalPages.
// onPageChange 上抛 1-based page 给外部 (受控分页通过 DataTable 的 onPaginationChange).
// (2026-07-03) 中文: shadcn PaginationPrevious/Next 加了 text prop (默认 "Previous"/"Next"),
//   用 text= 传中文 + onClick 阻断默认 <a> 跳转.
import type { ReactNode } from "react";
import type { Table as TanstackTable } from "@tanstack/react-table";
import {
  Pagination,
  PaginationContent,
  PaginationItem,
  PaginationNext,
  PaginationPrevious,
} from "@/components/ui/pagination";
import { useTranslations } from "next-intl";
import { ONE } from "@/const/index";

/**
 * DataTablePagination 组件属性
 * @param props.table TanStack table 实例
 * @param props.onPageChange 受控分页回调 (1-based)
 * @client-bff
 */
export interface DataTablePaginationProps<TData> {
  table: TanstackTable<TData>;
  // (2026-06-26) 受控分页: 外部传 onPageChange (page 1-based) 接管, 非受控时内部 nextPage
  onPageChange?: (page: number) => void;
}

/** 分页步进值 (每次翻 1 页) */
const PAGE_STEP = 1;
/** 禁用态样式: 不响应指针 + 半透明 */
const DISABLED_OPACITY = "pointer-events-none opacity-50";
/** 启用态样式: 指针手型 */
const CURSOR_POINTER = "cursor-pointer";

/**
 * 构建上/下翻页按钮类名 — 首/末页分别置灰
 * @param current 当前页 (1-based)
 * @param totalPages 总页数
 * @returns 前后按钮类名对象
 */
const buildButtonClass = (current: number, totalPages: number): { next: string; prev: string } => {
  const isFirstPage = current === ONE;
  const isLastPage = current >= totalPages;
  const prevClass = isFirstPage ? DISABLED_OPACITY : CURSOR_POINTER;
  const nextClass = isLastPage ? DISABLED_OPACITY : CURSOR_POINTER;
  return { next: nextClass, prev: prevClass };
};

/**
 * DataTable 分页 UI — shadcn Pagination 包装, 支持受控/非受控双模式
 * 从 TanStack table.getState().pagination 派生 current/totalPages
 * onPageChange 上抛 1-based page
 * @param props.table TanStack table 实例
 * @param props.onPageChange 受控分页回调
 * @returns 分页 JSX (总条数 + 上/下翻页)
 */
// oxlint-disable-next-line max-statements -- handlePrev/handleNext 双分支 + 渲染 JSX 串行, 不拆 helper
export const DataTablePagination = <TData,>({
  table,
  onPageChange,
}: DataTablePaginationProps<TData>): ReactNode => {
  const translate = useTranslations();
  const { pageIndex } = table.getState().pagination;
  const totalPages = table.getPageCount();
  const total = table.getFilteredRowModel().rows.length;
  const current = pageIndex + ONE; // TanStack 0-based, 我们 1-based

  if (totalPages <= PAGE_STEP) {
    return null;
  }
  const classNames = buildButtonClass(current, totalPages);
  // 受控 vs 非受控双分支:
  //   - 受控 (onPageChange): 走外部 state, 同时 Math.max/Math.min clamp 防越界
  //   - 非受控: 调 TanStack table 内部方法, 它自己管边界
  const handlePrev = () => {
    if (current === ONE) {
      return;
    }
    if (onPageChange) {
      // Math.max(ONE, ...) 防止 current=1 时 prev 退到 0 (TanStack pageIndex 0-based 但我们 1-based)
      onPageChange(Math.max(ONE, current - PAGE_STEP));
    } else {
      table.previousPage();
    }
  };
  const handleNext = () => {
    if (current >= totalPages) {
      return;
    }
    if (onPageChange) {
      // Math.min(totalPages, ...) 防止 current=totalPages 时 next 越过末页
      onPageChange(Math.min(totalPages, current + PAGE_STEP));
    } else {
      table.nextPage();
    }
  };

  const prevLabel = translate("上一页");
  const nextLabel = translate("下一页");

  return (
    <div className="flex items-center justify-between border-t border-border/60 bg-muted/20 px-6 py-3">
      <span className="num text-sm text-muted-foreground">
        {translate("第 {current} / {totalPages} 页 · 共 {total} 条", {
          current: String(current),
          totalPages: String(totalPages),
          total: String(total),
        })}
      </span>
      <Pagination className="mx-0 w-auto">
        <PaginationContent>
          <PaginationItem>
            <PaginationPrevious
              aria-label={prevLabel}
              className={classNames.prev}
              data-testid="pagination-prev"
              text={prevLabel}
              onClick={(event) => {
                event.preventDefault();
                handlePrev();
              }}
            />
          </PaginationItem>
          <PaginationItem>
            <PaginationNext
              aria-label={nextLabel}
              className={classNames.next}
              data-testid="pagination-next"
              text={nextLabel}
              onClick={(event) => {
                event.preventDefault();
                handleNext();
              }}
            />
          </PaginationItem>
        </PaginationContent>
      </Pagination>
    </div>
  );
};
