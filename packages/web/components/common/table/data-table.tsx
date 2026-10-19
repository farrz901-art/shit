"use client";
// DataTable — antd 风格表格封装 (2026-06-10, 2026-06-25 拆分)
//   3 模块: 本壳 + DataTablePagination + DataTableBody
// (2026-06-26) 换底: 内部用 @tanstack/react-table 的 useReactTable + flexRender,
//   shadcn Table/TableHead/TableRow/TableCell 全部保留, 对外 API 100% 不变.
//   适配层 to-tanstack-columns 翻译 ColumnDef[] → TanStack ColumnDef[].
//   受控分页通过 manualPagination + onPaginationChange 实现.
//   useTablePagination 已删除, 分页由 getPaginationRowModel 接管。
// (2026-07-09) 加列宽拖动: enableColumnResizing + columnResizeMode="onChange",
//   Thead 右侧加 4px 拖动手柄 (cursor-col-resize + mousedown 跟 TanStack getResizeHandler).
//   列宽 state 受控在组件内 (defaultColumnSize = 150), 父组件可通过 columnSizing prop 覆盖初始.
import { type CSSProperties, type ReactNode, useState } from "react";
import {
  flexRender,
  getCoreRowModel,
  getPaginationRowModel,
  useReactTable,
  type ColumnSizingState,
  type ColumnDef as TanstackColumnDef,
  type Table as TanstackTable,
  type TableOptions as TanstackTableOptions,
} from "@tanstack/react-table";
import { Table, TableBody, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { ONE } from "@/const/index";

/** (2026-07-09) 列宽默认值 (未指定列宽的兜底, 沿用项目表格观感) */
const DEFAULT_COLUMN_SIZE_PX = 150;
/** (2026-07-09) 列宽最小值 (防止拖到 0 看不见) */
const MIN_COLUMN_SIZE_PX = 50;
/** (2026-07-09) 拖动手柄宽度 (px) */
const RESIZE_HANDLE_WIDTH_PX = 4;
/** (2026-07-09) 拖动手柄右侧额外点击热区 (px, 用户友好) */
const RESIZE_HANDLE_HIT_AREA_PX = 8;
/** (2026-07-10) 字符串列宽正则捕获组索引 (named 唯一) */
const STRING_WIDTH_RE = /^(?<num>-?\d+(?:\.\d+)?)/;
import { cn } from "@/lib/utils";
import { DataEmpty } from "@/components/common/display/app-data-empty";
import { DataTableBody } from "./data-table-body";
import { DataTablePagination } from "./data-table-pagination";
import { buildControlledPaginationHandler } from "./apply-pagination-updater";

/**
 * 解析 maxHeight 属性为 CSS 标准值
 * @param maxHeight 最大高度值 (数字/字符串/undefined)
 * @returns CSS maxHeight 值或 undefined
 */
const resolveMaxHeight = (maxHeight: string | number | undefined): string | undefined => {
  if (!maxHeight || maxHeight === "auto") {
    return undefined;
  }
  if (typeof maxHeight === "number") {
    return `${maxHeight}px`;
  }
  return maxHeight;
};

/**
 * 列宽 4 种模式: number/string/弹性对象/"auto"/"fill"
 * @client-bff
 */
// 列宽 4 种模式 (2026-06-23 redesign):
//   - number / string: 旧 API, 固定宽度 (向后兼容)
//   - { min, max? }: 弹性宽度, e.g. { min: 150, max: 300 }
//   - "auto": 内容自适应, table-layout auto
//   - "fill": 抢占剩余空间, table-layout fixed (本 spec 暂不引入, YAGNI)
export type ColumnWidth = number | string | { max?: number; min: number } | "auto" | "fill";

/**
 * 获取弹性列宽样式 (min/max)
 * @param width 弹性列宽配置
 * @returns CSSProperties 样式对象
 */
const getFlexColStyle = (width: { max?: number; min: number }): React.CSSProperties => {
  const style: React.CSSProperties = { minWidth: `${width.min}px` };
  if (width.max !== undefined) {
    style.maxWidth = `${width.max}px`;
  }
  return style;
};

/**
 * 获取字符串列宽样式 (auto/fill/固定宽度)
 * @param width 字符串列宽配置
 * @returns CSSProperties 样式对象
 */
const getStringColStyle = (width: string): React.CSSProperties => {
  if (width === "auto") {
    return { width: "auto" };
  }
  if (width === "fill") {
    return { minWidth: "0", width: "100%" };
  }
  return { width };
};

/**
 * 解析列宽配置为 CSSProperties
 * @param width 列宽配置
 * @returns CSSProperties 对象
 * @client-bff
 */
export const getColStyle = (width: ColumnWidth | undefined): React.CSSProperties | undefined => {
  if (width === undefined) {
    return undefined;
  }
  if (typeof width === "number") {
    return { width: `${width}px` };
  }
  if (typeof width === "string") {
    return getStringColStyle(width);
  }
  return getFlexColStyle(width);
};

/**
 * TanStack 列元数据 — 对齐方式 + 列宽配置
 * @client-bff
 */
export interface TanstackColumnMeta {
  /** 列对齐方式 */
  align?: "left" | "center" | "right";
  /** 列宽配置 */
  width?: ColumnWidth;
  /** (2026-07-09) 关闭列宽拖动 (默认 true). 设为 false 时不渲染 resize handle. */
  enableResizing?: boolean;
}

/** 列定义类型 — 兼容 @tanstack/react-table 的 ColumnDef */
export type ColumnDef<TData> = TanstackColumnDef<TData>;

/**
 * DataTable 全部属性
 * @param props.dataSource 表格数据源
 * @param props.columns 列定义
 * @param props.rowKey 行唯一 key
 * @param props.pagination 受控分页配置
 * @param props.maxHeight 表格最大高度
 * @param props.onRowClick 行点击回调
 * @param props.rowClassName 行 className 工厂
 * @param props.expandedRowRender 展开行渲染
 * @param props.emptyText 空态内容
 * @param props.loading 加载态
 * @param props.className 外层类名
 * @client-bff
 */
export interface DataTableProps<TData> {
  /** 表格数据源 */
  dataSource: TData[];
  /** 列定义 */
  columns: ColumnDef<TData>[];
  /** 行唯一 key 字段名 */
  rowKey: keyof TData & string;
  /** 受控分页配置 (不传则使用内部非受控分页) */
  pagination?: {
    current: number;
    pageSize: number;
    total: number;
    onChange: (page: number) => void;
  };
  /** 表格最大高度 (超出滚动), 启用 sticky 表头 */
  maxHeight?: string | number;
  onRowClick?: (row: TData, index: number) => void;
  rowClassName?: (row: TData) => string;
  expandedRowRender?: (row: TData) => ReactNode;
  emptyText?: ReactNode;
  loading?: boolean;
  className?: string;
  /** (2026-07-09) 初始列宽映射 (key=column id, value=px). 不传走 TanStack 默认. */
  initialColumnSizing?: Record<string, number>;
}

// (2026-06-30) 拆自 DataTable: useReactTable 配置长 (受控/非受控分支) 抽成模块级纯函数.
//   - columns + dataSource: 列与数据
//   - rowKey: 行 id 提取
//   - pagination: 可选受控分页, 不传走非受控默认页大小
// (2026-07-09) 加列宽拖动: columnSizing state 走 component 受控, onColumnSizingChange
//   setState; initialState.columnSizing 走父组件传入 (initialColumnSizing).
/**
 * buildTableOptions 参数
 * @client-bff
 */
interface BuildTableOptionsArgs<TData> {
  columns: ColumnDef<TData>[];
  dataSource: TData[];
  pagination: DataTableProps<TData>["pagination"];
  rowKey: keyof TData & string;
  /** (2026-07-09) 列宽受控 state (TanStack 同时吃 state + onChange 实现双向) */
  columnSizing: ColumnSizingState;
  /** (2026-07-09) 列宽变更回调 (state 透传给父) */
  onColumnSizingChange: (
    updater: ColumnSizingState | ((old: ColumnSizingState) => ColumnSizingState),
  ) => void;
}

/**
 * 把 meta.width (ColumnWidth) 翻译成 TanStack columnDef.size 初始值.
 * - number: 直接用 (TanStack size 走 px)
 * - string "240px" / "12rem": parse 出数字 (TanStack size 只接受 number)
 * - { min, max }: 用 min 作为 size, max 落到 maxSize
 * - "auto" / "fill": undefined (TanStack 走 defaultColumn.size)
 * @param width meta.width 配置
 * @returns { size?, maxSize? } 给 TanStack 吃
 */
const toTanstackColumnSize = (
  width: ColumnWidth | undefined,
): { size?: number; maxSize?: number } => {
  if (width === undefined) {
    return {};
  }
  if (typeof width === "number") {
    return { size: width };
  }
  if (typeof width === "string") {
    // "auto" / "fill" 走 CSS 处理, 不喂给 TanStack
    if (width === "auto" || width === "fill") {
      return {};
    }
    // "240px" / "12rem" → parse number
    const match = width.match(STRING_WIDTH_RE);
    if (match?.groups?.num !== undefined) {
      return { size: Number(match.groups.num) };
    }
    return {};
  }
  // { min, max? } 弹性宽度
  return { size: width.min, ...(width.max !== undefined ? { maxSize: width.max } : {}) };
};

/**
 * 构建 TanStack useReactTable 配置项
 * @param args 配置参数
 * @returns TanStack TableOptions
 */
const buildTableOptions = <TData,>({
  columns,
  columnSizing,
  dataSource,
  onColumnSizingChange,
  pagination,
  rowKey,
}: BuildTableOptionsArgs<TData>): TanstackTableOptions<TData> => {
  // (2026-07-09) 列宽拖动: 把每列的 meta.width 翻译成 TanStack columnDef.size/maxSize 初始值,
  //   拖动后通过 columnSizing state 覆盖.
  const sizedColumns: ColumnDef<TData>[] = columns.map((col) => {
    const meta = (col.meta ?? {}) as TanstackColumnMeta;
    const { size, maxSize } = toTanstackColumnSize(meta.width);
    if (size === undefined && maxSize === undefined) {
      return col;
    }
    return {
      ...col,
      size,
      ...(maxSize !== undefined ? { maxSize } : {}),
    };
  });
  // (2026-07-09) 列宽拖动: onChange 模式实时反馈, defaultColumn.size 给未指定列兜底
  const baseOptions: TanstackTableOptions<TData> = {
    columns: sizedColumns,
    data: dataSource,
    enableColumnResizing: true,
    columnResizeMode: "onChange",
    defaultColumn: { size: DEFAULT_COLUMN_SIZE_PX, minSize: MIN_COLUMN_SIZE_PX },
    getCoreRowModel: getCoreRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    getRowId: (row, index) => String((row as Record<string, unknown>)[rowKey] ?? index),
    state: {
      columnSizing,
    },
    onColumnSizingChange,
  };
  // 受控分页叠加: manualPagination + onPaginationChange + state 接管
  if (pagination === undefined) {
    return baseOptions;
  }
  return {
    ...baseOptions,
    manualPagination: true,
    onPaginationChange: buildControlledPaginationHandler({
      current: pagination.current,
      onChange: pagination.onChange,
      pageSize: pagination.pageSize,
    }),
    pageCount: Math.ceil(pagination.total / pagination.pageSize),
    state: {
      columnSizing,
      pagination: {
        pageIndex: pagination.current - ONE,
        pageSize: pagination.pageSize,
      },
    },
  };
};

/**
 * 通用表格组件 — antd 风格, 内部使用 @tanstack/react-table + shadcn Table
 * 支持加载态 / 空态 / 分页 (受控/非受控) / 行点击 / 展开行 / sticky 表头
 * @param props.dataSource 数据源
 * @param props.columns 列定义
 * @param props.rowKey 行唯一 key
 * @param props.pagination 受控分页配置
 * @param props.maxHeight 最大高度 (带 sticky 表头)
 * @param props.loading 加载态
 * @param props.emptyText 空态内容
 * @param props.onRowClick 行点击回调
 * @returns DataTable JSX
 */
export const DataTable = <TData,>({
  dataSource,
  columns,
  rowKey,
  pagination,
  maxHeight = "auto",
  onRowClick,
  rowClassName,
  expandedRowRender,
  emptyText = <DataEmpty title="暂无数据" />,
  loading = false,
  className,
  initialColumnSizing,
}: DataTableProps<TData>): ReactNode => {
  // (2026-07-09) 列宽拖动: 受控 state, 初始走父组件传入 (initialColumnSizing).
  //   buildTableOptions 接 state.columnSizing + onColumnSizingChange, 把拖动后值回流到 React state,
  //   父组件读 columnSizing 让后续重渲染拿到最新宽度 (例如导出 CSV 时).
  const [columnSizing, setColumnSizing] = useState<ColumnSizingState>(initialColumnSizing ?? {});
  // (2026-06-26) useTablePagination 已删, 分页由 getPaginationRowModel 接管。
  // handleChangePage 仅作 onPageChange 透传 (1-based)。
  /**
   * 分页变更处理 (1-based → 0-based 转换)
   * @param pageNum 目标页码 (1-based)
   */
  const handleChangePage = (pageNum: number): void => {
    if (pagination !== undefined) {
      pagination.onChange(pageNum);
    } else {
      table.setPageIndex(pageNum - ONE);
    }
  };

  const containerStyle = resolveMaxHeight(maxHeight);
  const stickyEnabled = maxHeight !== "auto" && Boolean(maxHeight);

  // (2026-06-26) TanStack 分页:
  //   - getPaginationRowModel 放外面, 非受控/受控都需要它做数据切片
  //   - 受控分页 (pagination prop 传入) 再加 manualPagination + onPaginationChange
  // (2026-06-30) 配置项抽到 buildTableOptions, useReactTable 调用保持简洁
  const table: TanstackTable<TData> = useReactTable<TData>(
    buildTableOptions({
      columns,
      columnSizing,
      dataSource,
      onColumnSizingChange: setColumnSizing,
      pagination,
      rowKey,
    }),
  );

  return (
    <div className={cn("rounded-lg border border-border/60", className)}>
      <div
        className={cn("min-h-0 overflow-auto", stickyEnabled && "flex-1")}
        style={{ maxHeight: containerStyle }}
      >
        <Table>
          <TableHeader
            className={cn(stickyEnabled && "sticky top-0 z-10 bg-muted/80 backdrop-blur-sm")}
          >
            {table.getHeaderGroups().map((headerGroup) => (
              <TableRow key={headerGroup.id}>
                {headerGroup.headers.map((header) => {
                  const meta = (header.column.columnDef.meta ?? {}) as TanstackColumnMeta;
                  // (2026-07-09) 列宽优先级: 1) 复杂 CSS (auto/fill/{min,max}) → 走 getColStyle
                  //   静态样式; 2) number/px/rem → 走 TanStack getSize() 支持拖动
                  const useTanstackSize =
                    meta.width === undefined ||
                    typeof meta.width === "number" ||
                    (typeof meta.width === "string" &&
                      meta.width !== "auto" &&
                      meta.width !== "fill");
                  const columnStyle: CSSProperties | undefined = useTanstackSize
                    ? { width: `${header.column.getSize()}px` }
                    : getColStyle(meta.width);
                  const resizable = useTanstackSize && meta.enableResizing !== false;
                  return (
                    <TableHead
                      key={header.id}
                      className={cn(
                        "eyebrow relative whitespace-nowrap",
                        meta.align === "right" && "text-right",
                        meta.align === "center" && "text-center",
                      )}
                      data-testid={`data-table-header-${header.column.id}`}
                      style={columnStyle}
                    >
                      {flexRender(header.column.columnDef.header, header.getContext())}
                      {/* (2026-07-09) 列宽拖动手柄: 仅 TanStack 模式渲染 (复杂 CSS 模式不拖) */}
                      {resizable ? (
                        <div
                          aria-label={`拖动调整 ${header.column.id} 列宽`}
                          className={cn(
                            "absolute right-0 top-0 z-20 cursor-col-resize select-none touch-none",
                            header.column.getIsResizing() && "bg-primary/40 transition-colors",
                          )}
                          data-testid={`data-table-resize-${header.column.id}`}
                          onMouseDown={header.getResizeHandler()}
                          onTouchStart={header.getResizeHandler()}
                          role="separator"
                          style={{
                            height: "100%",
                            width: `${RESIZE_HANDLE_HIT_AREA_PX}px`,
                          }}
                        >
                          <div
                            className="ml-auto h-full bg-border/40"
                            style={{ width: `${RESIZE_HANDLE_WIDTH_PX}px` }}
                          />
                        </div>
                      ) : null}
                    </TableHead>
                  );
                })}
              </TableRow>
            ))}
          </TableHeader>
          <TableBody className="[&_tr:last-child]:border-0">
            <DataTableBody
              columns={columns}
              emptyText={emptyText}
              expandedRowRender={expandedRowRender}
              loading={loading}
              onRowClick={onRowClick}
              rowClassName={rowClassName}
              table={table}
            />
          </TableBody>
        </Table>
      </div>
      <DataTablePagination<TData> onPageChange={handleChangePage} table={table} />
    </div>
  );
};
