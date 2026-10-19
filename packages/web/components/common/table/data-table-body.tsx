// DataTable 表体组件 (2026-06-25 拆分自 data-table.tsx)
// 状态分支 (loading / 空 / 数据) + stagger 行入场 + 展开行
// (2026-06-26) 换底: 接收 TanStack table 实例, 行用 table.getRowModel().rows + flexRender.
//   shadcn <TableCell> 保留. expandedRowRender 行级 null 跳过保留.
import { Fragment, type ReactNode } from "react";
import { TableCell, TableRow } from "@/components/ui/table";
import { Pulse, useReducedMotionSafe } from "@/components/motion/animated";
import { ZERO } from "@/const/index";
import { rowStagger, STAGGER_STEP } from "@/lib/motion";
import { cn } from "@/lib/utils";
import { motion } from "motion/react";
import { flexRender, type Table as TanstackTable } from "@tanstack/react-table";
import type { ColumnDef, TanstackColumnMeta } from "./data-table";

/**
 * DataTableBody 组件属性
 * @param props.table TanStack table 实例
 * @param props.columns 列定义
 * @param props.loading 加载态标志
 * @param props.emptyText 空态内容
 * @param props.onRowClick 行点击回调
 * @param props.rowClassName 行 className 工厂
 * @param props.expandedRowRender 展开行渲染函数
 * @client-bff
 */
export interface DataTableBodyProps<TData> {
  table: TanstackTable<TData>;
  columns: ColumnDef<TData>[];
  loading: boolean;
  emptyText: ReactNode;
  onRowClick?: (row: TData, index: number) => void;
  rowClassName?: (row: TData) => string;
  expandedRowRender?: (row: TData) => ReactNode;
}

/**
 * 渲染加载状态行 — Pulse 动画 "加载中…" 占满整行
 * @param columnsLength 列数 (用于 colSpan)
 * @returns 加载行 JSX
 * @client-bff
 */
const renderLoadingRow = (columnsLength: number): ReactNode => (
  <TableRow className="hover:bg-transparent [&>td]:border-0">
    <TableCell colSpan={columnsLength} className="h-40 text-center text-muted-foreground">
      <Pulse>加载中…</Pulse>
    </TableCell>
  </TableRow>
);

/**
 * 渲染空状态行 — 展示 emptyText 占满整行
 * @param columnsLength 列数 (用于 colSpan)
 * @param emptyText 空态内容
 * @returns 空行 JSX
 * @client-bff
 */
const renderEmptyRow = (columnsLength: number, emptyText: ReactNode): ReactNode => (
  <TableRow className="hover:bg-transparent [&>td]:border-0">
    <TableCell colSpan={columnsLength} className="h-40 text-center text-muted-foreground">
      {emptyText}
    </TableCell>
  </TableRow>
);

/**
 * renderDataRows 参数接口 — 列定义、table 实例、展开行渲染、行点击回调及行类名
 * @client-bff
 */
interface RenderDataRowsParams<TData> {
  columns: ColumnDef<TData>[];
  table: TanstackTable<TData>;
  expandedRowRender: ((row: TData) => ReactNode) | undefined;
  onRowClick: ((row: TData, index: number) => void) | undefined;
  rowClassName: ((row: TData) => string) | undefined;
}

/**
 * renderExpandedRow 参数接口 — 列定义、展开行渲染函数、行索引、动效标志及行数据
 * @client-bff
 */
interface RenderExpandedRowParams<TData> {
  columns: ColumnDef<TData>[];
  expandedRowRender: (row: TData) => ReactNode;
  index: number;
  key: string;
  reduced: boolean;
  rowData: TData;
}

/**
 * 渲染展开行 — 行级 render 返 null/undefined 时不渲染整行 <tr>, 避免空 <td> 配 border 视觉上画双线
 * @param params.columns 列定义
 * @param params.expandedRowRender 展开行渲染函数
 * @param params.index 行索引
 * @param params.key 行 key
 * @param params.reduced 是否减少动效
 * @param params.rowData 行数据
 * @returns 展开行 JSX 或 null
 * @client-bff
 */
const renderExpandedRow = <TData,>({
  columns,
  expandedRowRender,
  index,
  key,
  reduced,
  rowData,
}: RenderExpandedRowParams<TData>): ReactNode => {
  const expandedNode = expandedRowRender(rowData);
  // 行级 render 返 null/undefined 时不渲染整行 <tr>, 避免空 <td> 配 border 视觉上画双线
  if (expandedNode === null || expandedNode === undefined) {
    return null;
  }
  return (
    <motion.tr
      variants={rowStagger(index * STAGGER_STEP.row)}
      initial={reduced ? false : "hidden"}
      animate="show"
      className="border-b-0 bg-muted/30 [&>td]:border-b hover:bg-transparent"
      data-testid="expanded-row"
      key={`${key}-expanded`}
    >
      <TableCell colSpan={columns.length}>{expandedNode}</TableCell>
    </motion.tr>
  );
};

/**
 * 渲染数据行列表 — 遍历 table.getRowModel().rows, 每行带 stagger 入场动画 + 点击回调 + 展开行
 * @param params RenderDataRowsParams 参数集合
 * @returns 数据行 JSX 片段
 * @client-bff
 */
const renderDataRows = <TData,>(params: RenderDataRowsParams<TData>): ReactNode => {
  const { columns, table, expandedRowRender, onRowClick, rowClassName } = params;
  const { rows } = table.getRowModel();
  const reduced = useReducedMotionSafe();
  return (
    <>
      {rows.map((row, index) => {
        const rowData = row.original;
        const key = row.id;
        const handleClick = () => onRowClick?.(rowData, index);
        return (
          <Fragment key={key}>
            <motion.tr
              variants={rowStagger(index * STAGGER_STEP.row)}
              initial={reduced ? false : "hidden"}
              animate="show"
              className={cn(
                "border-b transition-colors hover:bg-muted/50",
                onRowClick && "cursor-pointer",
                rowClassName?.(rowData),
              )}
              data-testid="data-table-row"
              onClick={handleClick}
            >
              {row.getVisibleCells().map((cell) => {
                const meta = (cell.column.columnDef.meta ?? {}) as TanstackColumnMeta;
                // (2026-07-09) 列宽拖动: cell 用 column.getSize() 设固定宽度, 跟表头对齐
                return (
                  <TableCell
                    key={cell.id}
                    className={cn(
                      "text-sm",
                      meta.align === "right" && "text-right",
                      meta.align === "center" && "text-center",
                    )}
                    style={{ width: `${cell.column.getSize()}px` }}
                  >
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </TableCell>
                );
              })}
            </motion.tr>
            {expandedRowRender !== undefined &&
              renderExpandedRow({
                columns,
                expandedRowRender,
                index,
                key,
                reduced,
                rowData,
              })}
          </Fragment>
        );
      })}
    </>
  );
};

/**
 * DataTable 表体 — 状态分支处理 (loading / 空 / 数据) + stagger 行入场 + 展开行
 * 接收 TanStack table 实例, 用 table.getRowModel().rows + flexRender 渲染
 * @param props.table TanStack table 实例
 * @param props.columns 列定义
 * @param props.loading 加载态标志
 * @param props.emptyText 空态内容
 * @param props.onRowClick 行点击回调
 * @param props.rowClassName 行 className 工厂
 * @param props.expandedRowRender 展开行渲染
 * @returns 表体 JSX (TableRow 列表)
 */
export const DataTableBody = <TData,>({
  table,
  columns,
  loading,
  emptyText,
  onRowClick,
  rowClassName,
  expandedRowRender,
}: DataTableBodyProps<TData>): ReactNode => {
  if (loading) {
    return <>{renderLoadingRow(columns.length)}</>;
  }
  const { rows } = table.getRowModel();
  if (rows.length > ZERO) {
    return <>{renderDataRows({ columns, table, expandedRowRender, onRowClick, rowClassName })}</>;
  }
  return <>{renderEmptyRow(columns.length, emptyText)}</>;
};
