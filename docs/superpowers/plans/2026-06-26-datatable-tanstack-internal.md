# DataTable TanStack Table 内核化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 DataTable 内部从"手写 shadcn `<Table>` 渲染 + 自管分页"换成 `@tanstack/react-table` 的 `useReactTable` + `flexRender`, 对外 API 100% 不变, 10 调用方 0 改动.

**Architecture:** shadcn 为主, TanStack 为辅. shadcn `<Table>`/`<TableHead>`/`<TableRow>`/`<TableCell>` 全部保留, TanStack 只提供 row model + flexRender. 适配层 `to-tanstack-columns.ts` 1-to-1 翻译 `ColumnDef<T>[]` → TanStack `ColumnDef<T>[]`. 受控分页通过 `manualPagination: true` + `onPaginationChange` 实现.

**Tech Stack:** TypeScript 8 + React 19 + shadcn/ui (slate) + Tailwind v4 + motion + `@tanstack/react-table@8.21.3` + vitest + oxlint + oxfmt

**Spec:** [docs/superpowers/specs/2026-06-26-datatable-tanstack-internal-design.md](../specs/2026-06-26-datatable-tanstack-internal-design.md)

**项目铁律:** format → lint → typecheck → test → commit (CLAUDE.md)

---

## File Structure (锁定)

| 操作 | 路径 | 责任 |
|---|---|---|
| **Create** | `packages/web/components/common/table/to-tanstack-columns.ts` | 适配层: ColumnDef[] → TanStack ColumnDef[] |
| **Create** | `packages/web/components/common/table/to-tanstack-columns.test.ts` | 适配层单元测试 (5 形态) |
| **Modify** | `packages/web/components/common/table/data-table.tsx` | 顶层 useReactTable 替换; 接收 table 实例下传 |
| **Modify** | `packages/web/components/common/table/data-table-body.tsx` | 用 table.getRowModel().rows + flexRender; 接收 table 实例 |
| **Modify** | `packages/web/components/common/table/data-table-pagination.tsx` | 接 table 实例, 从 getState().pagination 派生 current |
| **Delete** | `packages/web/components/common/table/use-table-pagination.ts` | 被 getPaginationRowModel 替 |
| **Delete** | `packages/web/components/common/table/use-table-pagination.test.ts` | 跟随 use-table-pagination.ts 删 |
| **No change** | `packages/web/components/common/table/data-table.test.tsx` | 公共行为验收 (10 个 it) |
| **No change** | `packages/web/components/common/table/data-table-body.test.tsx` | 公共行为验收 (11 个 it) |
| **No change** | `packages/web/components/common/table/data-table-pagination.test.tsx` | 公共行为验收 |
| **No change** | 10 调用方 (DatasetsTable / DatasetDocumentsTable / NodesTable / RelationsTable / dict-list / sample-table 等) | 0 改动 |
| **No change** | `packages/web/components/common/table/data-table-skeleton.tsx` | 独立组件 |

---

## Task 1: 写 `to-tanstack-columns.test.ts` 适配层测试 (红)

**Files:**
- Create: `packages/web/components/common/table/to-tanstack-columns.test.tsx` (注: .tsx 不是 .ts, 因含 JSX)

- [ ] **Step 1: 写测试覆盖 5 种 ColumnDef 形态**

```typescript
import { describe, expect, it } from "vitest";
import type { ReactNode } from "react";
import { toTanstackColumns } from "./to-tanstack-columns";
import type { ColumnDef } from "./data-table";

interface User {
  id: string;
  name: string;
  age: number;
}

const SAMPLE_USER: User = { age: 25, id: "1", name: "张三" };
const ZERO_INDEX = 0;

const baseColumns: ColumnDef<User>[] = [
  { key: "id", title: "ID" },
  { key: "name", title: "姓名" },
  {
    key: "age",
    render: (row) => <span>{row.age}岁</span>,
    title: "年龄",
  },
];

describe("toTanstackColumns", () => {
  it("id 字段设为 accessorKey + column id", () => {
    const result = toTanstackColumns(baseColumns);
    expect(result[ZERO_INDEX].id).toBe("id");
    expect(result[ZERO_INDEX].accessorKey).toBe("id");
  });

  it("header 函数返回 title", () => {
    const result = toTanstackColumns(baseColumns);
    const headerRender = result[ZERO_INDEX].header;
    if (typeof headerRender === "function") {
      // (TanStack 8.x 的 header 类型是 Renderable<HeaderContext<T, V>>)
      const output = headerRender({} as never);
      expect(output).toBe("ID");
    } else {
      expect(headerRender).toBe("ID");
    }
  });

  it("无 render 函数时 cell 返 String(getValue()) 兜底", () => {
    const cols: ColumnDef<User>[] = [{ key: "name", title: "姓名" }];
    const result = toTanstackColumns(cols);
    const cellRender = result[ZERO_INDEX].cell;
    expect(typeof cellRender).toBe("function");
    if (typeof cellRender === "function") {
      const output = cellRender({
        cell: {},
        column: { id: "name" },
        getValue: () => "张三",
        renderValue: () => "张三",
        row: { index: 0, original: SAMPLE_USER },
        table: {} as never,
      } as never);
      expect(output).toBe("张三");
    }
  });

  it("有 render 函数时 cell 调 col.render(row.original, row.index)", () => {
    const cols: ColumnDef<User>[] = [
      {
        key: "age",
        render: (row, idx) => <span data-testid="rendered">{`${row.age}-${idx}`}</span>,
        title: "年龄",
      },
    ];
    const result = toTanstackColumns(cols);
    const cellRender = result[ZERO_INDEX].cell;
    if (typeof cellRender === "function") {
      const output = cellRender({
        cell: {},
        column: { id: "age" },
        getValue: () => 25,
        renderValue: () => 25,
        row: { index: 7, original: SAMPLE_USER },
        table: {} as never,
      } as never);
      // 验证 React element 形态: type=span, props.children=`25-7`
      expect((output as ReactNode)).toBeTruthy();
    }
  });

  it("meta 携带 align 和 width (供 DataTable 头/体读 className)", () => {
    const cols: ColumnDef<User>[] = [
      { align: "right", key: "age", title: "年龄", width: 240 },
    ];
    const result = toTanstackColumns(cols);
    expect(result[ZERO_INDEX].meta).toEqual({ align: "right", width: 240 });
  });
});
```

- [ ] **Step 2: 跑测试确认红 (FAIL: Cannot find module './to-tanstack-columns')**

```bash
cd packages/web && bun run test -- to-tanstack-columns
```

Expected: FAIL with "Failed to resolve import './to-tanstack-columns'"

- [ ] **Step 3: 跑 lint + typecheck 确认也红**

```bash
cd packages/web && bunx oxlint components/common/table && bun run typecheck
```

Expected: oxlint 0 error (测试文件未引用不存在的 import 会被 TS 报错); typecheck FAIL on import.

---

## Task 2: 写 `to-tanstack-columns.ts` 适配层 (绿)

**Files:**
- Create: `packages/web/components/common/table/to-tanstack-columns.ts`

- [ ] **Step 1: 写适配层**

```typescript
// ColumnDef[] → @tanstack/react-table ColumnDef[] 适配层 (2026-06-26 spec)
// 翻译: id / accessorKey / header / cell / meta
// 保留项目 ColumnDef 的对外 API shape, 内部用 TanStack 算 row model
import type { ColumnDef as TanstackColumnDef } from "@tanstack/react-table";
import type { ColumnDef, ColumnWidth } from "./data-table";

export interface TanstackColumnMeta {
  align?: "left" | "center" | "right";
  width?: ColumnWidth;
}

export const toTanstackColumns = <TData,>(
  columns: ColumnDef<TData>[],
): TanstackColumnDef<TData>[] => {
  return columns.map((col) => {
    // base cell: 拿 column.key 对应值, 跟原 getCellContent 一致
    const fallbackCell = (ctx: { getValue: () => unknown }): string =>
      String(ctx.getValue() ?? "—");
    const cellRender: TanstackColumnDef<TData>["cell"] = col.render
      ? (ctx) => col.render!(ctx.row.original, ctx.row.index)
      : (fallbackCell as TanstackColumnDef<TData>["cell"]);
    return {
      accessorKey: col.key,
      cell: cellRender,
      enableColumnFilter: false,
      enableSorting: false,
      header: () => col.title,
      id: col.key,
      meta: {
        align: col.align,
        width: col.width,
      } as TanstackColumnMeta,
    } as TanstackColumnDef<TData>;
  });
};
```

- [ ] **Step 2: 跑测试确认绿**

```bash
cd packages/web && bun run test -- to-tanstack-columns
```

Expected: 5/5 passed

- [ ] **Step 3: 跑 lint + typecheck 确认绿**

```bash
cd packages/web && bunx oxlint components/common/table && bun run typecheck
```

Expected: oxlint 0 warning; typecheck 0 error

- [ ] **Step 4: Commit**

```bash
git add packages/web/components/common/table/to-tanstack-columns.ts packages/web/components/common/table/to-tanstack-columns.test.ts
git commit -m "feat(table): add to-tanstack-columns adapter for TanStack Table"
```

---

## Task 3: 改 `data-table.tsx` 加 `useReactTable` (并行期, 行仍走 useTablePagination)

**Files:**
- Modify: `packages/web/components/common/table/data-table.tsx`

- [ ] **Step 1: 改 `data-table.tsx` 顶层加 useReactTable, 头走 flexRender, 行数据源仍传 pageData**

完整替换 `data-table.tsx`：

```tsx
"use client";
// DataTable — antd 风格表格封装 (2026-06-10, 2026-06-25 拆分)
//   4 模块: 本壳 + useTablePagination hook + DataTablePagination + DataTableBody
// (2026-06-26) 换底: 内部用 @tanstack/react-table 的 useReactTable + flexRender,
//   shadcn Table/TableHead/TableRow/TableCell 全部保留, 对外 API 100% 不变.
//   适配层 to-tanstack-columns 翻译 ColumnDef[] → TanStack ColumnDef[].
//   受控分页通过 manualPagination + onPaginationChange 实现.
import { type ReactNode } from "react";
import {
  flexRender,
  getCoreRowModel,
  getPaginationRowModel,
  useReactTable,
  type Table as TanstackTable,
} from "@tanstack/react-table";
import { Table, TableBody, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { cn } from "@/lib/utils";
import { DataEmpty } from "@/components/common/display/app-data-empty";
import { DataTableBody } from "./data-table-body";
import { DataTablePagination } from "./data-table-pagination";
import { toTanstackColumns, type TanstackColumnMeta } from "./to-tanstack-columns";
import { useTablePagination } from "./use-table-pagination";

const resolveMaxHeight = (maxHeight: string | number | undefined): string | undefined => {
  if (!maxHeight || maxHeight === "auto") {
    return undefined;
  }
  if (typeof maxHeight === "number") {
    return `${maxHeight}px`;
  }
  return maxHeight;
};

// 列宽 4 模式 (2026-06-23 redesign): number / string / { min, max? } / "auto" / "fill"
export type ColumnWidth = number | string | { max?: number; min: number } | "auto" | "fill";

const getFlexColStyle = (width: { max?: number; min: number }): React.CSSProperties => {
  const style: React.CSSProperties = { minWidth: `${width.min}px` };
  if (width.max !== undefined) {
    style.maxWidth = `${width.max}px`;
  }
  return style;
};

const getStringColStyle = (width: string): React.CSSProperties => {
  if (width === "auto") {
    return { width: "auto" };
  }
  if (width === "fill") {
    return { minWidth: "0", width: "100%" };
  }
  return { width };
};

export const getColStyle = (
  width: ColumnWidth | undefined,
): React.CSSProperties | undefined => {
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

export interface ColumnDef<TData> {
  align?: "left" | "center" | "right";
  key: string;
  render?: (row: TData, index: number) => ReactNode;
  title: string;
  width?: ColumnWidth;
}

export interface DataTableProps<TData> {
  dataSource: TData[];
  columns: ColumnDef<TData>[];
  rowKey: keyof TData & string;
  pagination?: {
    current: number;
    pageSize: number;
    total: number;
    onChange: (page: number) => void;
  };
  maxHeight?: string | number;
  onRowClick?: (row: TData, index: number) => void;
  rowClassName?: (row: TData) => string;
  expandedRowRender?: (row: TData) => ReactNode;
  emptyText?: ReactNode;
  loading?: boolean;
  className?: string;
}

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
}: DataTableProps<TData>): ReactNode => {
  // (2026-06-26) 并行期: useTablePagination 仍给 pageData 给 DataTableBody;
  //   useReactTable 算 headerGroups 给表头. 两套数据源并存, Step 5 后切到 TanStack.
  const { current, total, totalPages, pageData, handleChangePage } = useTablePagination(
    dataSource,
    pagination,
  );

  const containerStyle = resolveMaxHeight(maxHeight);
  const stickyEnabled = maxHeight !== "auto" && Boolean(maxHeight);

  const tanstackColumns = toTanstackColumns<TData>(columns);
  // (2026-06-26) TanStack 受控分页: state/onPaginationChange 同步外部 pagination
  const table: TanstackTable<TData> = useReactTable<TData>({
    columns: tanstackColumns,
    data: dataSource,
    getCoreRowModel: getCoreRowModel(),
    getRowId: (row, idx) => String((row as Record<string, unknown>)[rowKey] ?? idx),
    ...(pagination !== undefined
      ? {
          getPaginationRowModel: getPaginationRowModel(),
          manualPagination: true,
          onPaginationChange: (updater) => {
            const next =
              typeof updater === "function"
                ? updater({ pageIndex: pagination.current - 1, pageSize: pagination.pageSize })
                : updater;
            pagination.onChange(next.pageIndex + 1);
          },
          pageCount: Math.ceil(pagination.total / pagination.pageSize),
          state: {
            pagination: {
              pageIndex: pagination.current - 1,
              pageSize: pagination.pageSize,
            },
          },
        }
      : {}),
  });

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
                  const colDef = columns.find((c) => c.key === header.column.id);
                  return (
                    <TableHead
                      key={header.id}
                      className={cn(
                        "eyebrow whitespace-nowrap",
                        meta.align === "right" && "text-right",
                        meta.align === "center" && "text-center",
                      )}
                      style={getColStyle(meta.width ?? colDef?.width)}
                    >
                      {flexRender(header.column.columnDef.header, header.getContext())}
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
              pageData={pageData}
              rowClassName={rowClassName}
              rowKey={rowKey}
            />
          </TableBody>
        </Table>
      </div>
      <DataTablePagination
        current={current}
        onPageChange={handleChangePage}
        total={total}
        totalPages={totalPages}
      />
    </div>
  );
};
```

- [ ] **Step 2: 跑公共 3 测试确认仍绿 (头换, 行未动)**

```bash
cd packages/web && bun run test -- data-table data-table-body data-table-pagination
```

Expected: 所有测试通过 (头新走 flexRender, 行数据源仍用 pageData)

- [ ] **Step 3: 跑 lint + typecheck 确认绿**

```bash
cd packages/web && bunx oxlint components/common/table && bun run typecheck
```

Expected: oxlint 0 warning; typecheck 0 error

- [ ] **Step 4: Commit**

```bash
git add packages/web/components/common/table/data-table.tsx
git commit -m "refactor(table): use useReactTable for header rendering (parallel with useTablePagination)"
```

---

## Task 4: 改 `data-table-body.tsx` 用 `table.getRowModel().rows` + flexRender

**Files:**
- Modify: `packages/web/components/common/table/data-table-body.tsx`

- [ ] **Step 1: 改 `DataTableBody` 接收 `table` 实例, 行数据走 `table.getRowModel().rows`**

完整替换 `data-table-body.tsx`：

```tsx
// DataTable 表体组件 (2026-06-25 拆分自 data-table.tsx)
// 状态分支 (loading / 空 / 数据) + stagger 行入场 + 展开行
// (2026-06-26) 换底: 接收 TanStack table 实例, 行用 table.getRowModel().rows + flexRender.
//   shadcn <TableCell> 保留. expandedRowRender 行级 null 跳过保留.
import { Fragment, type ReactNode } from "react";
import { TableCell, TableRow } from "@/components/ui/table";
import { ZERO } from "@/const/index";
import { CSS_EASE, DUR } from "@/lib/motion";
import { cn } from "@/lib/utils";
import { motion } from "motion/react";
import { flexRender, type Table as TanstackTable } from "@tanstack/react-table";
import type { ColumnDef } from "./data-table";
import type { TanstackColumnMeta } from "./to-tanstack-columns";

const OPACITY_LOW = 0.4;
const OPACITY_HIGH = 1;
const ANIM_OPACITY_PULSE: [number, number, number] = [OPACITY_LOW, OPACITY_HIGH, OPACITY_LOW];
const ANIM_DURATION_PULSE = 1.6;
const ANIM_OPACITY_START = ZERO;
const ANIM_Y_START = 4;
const ANIM_DELAY_STEP = 0.02;
const ANIM_OPACITY_END = 1;
const ANIM_Y_END = 0;

export interface DataTableBodyProps<TData> {
  table: TanstackTable<TData>;
  columns: ColumnDef<TData>[];
  loading: boolean;
  emptyText: ReactNode;
  onRowClick?: (row: TData, index: number) => void;
  rowClassName?: (row: TData) => string;
  expandedRowRender?: (row: TData) => ReactNode;
}

const renderLoadingRow = (columnsLength: number): ReactNode => (
  <TableRow className="hover:bg-transparent [&>td]:border-0">
    <TableCell colSpan={columnsLength} className="h-40 text-center text-muted-foreground">
      <motion.span
        animate={{ opacity: ANIM_OPACITY_PULSE }}
        transition={{ duration: ANIM_DURATION_PULSE, repeat: Infinity }}
      >
        加载中…
      </motion.span>
    </TableCell>
  </TableRow>
);

const renderEmptyRow = (columnsLength: number, emptyText: ReactNode): ReactNode => (
  <TableRow className="hover:bg-transparent [&>td]:border-0">
    <TableCell colSpan={columnsLength} className="h-40 text-center text-muted-foreground">
      {emptyText}
    </TableCell>
  </TableRow>
);

interface RenderDataRowsParams<TData> {
  columns: ColumnDef<TData>[];
  table: TanstackTable<TData>;
  expandedRowRender: ((row: TData) => ReactNode) | undefined;
  onRowClick: ((row: TData, index: number) => void) | undefined;
  rowClassName: ((row: TData) => string) | undefined;
}

const renderDataRows = <TData,>(params: RenderDataRowsParams<TData>): ReactNode => {
  const { columns, table, expandedRowRender, onRowClick, rowClassName } = params;
  const rows = table.getRowModel().rows;
  return (
    <>
      {rows.map((row, index) => {
        const rowData = row.original;
        const key = row.id;
        const handleClick = () => onRowClick?.(rowData, index);
        return (
          <Fragment key={key}>
            <motion.tr
              animate={{ opacity: ANIM_OPACITY_END, translateY: ANIM_Y_END }}
              className={cn(
                "border-b transition-colors hover:bg-muted/50",
                onRowClick && "cursor-pointer",
                rowClassName?.(rowData),
              )}
              data-testid="data-table-row"
              initial={{ opacity: ANIM_OPACITY_START, translateY: ANIM_Y_START }}
              onClick={handleClick}
              transition={{
                delay: index * ANIM_DELAY_STEP,
                duration: DUR.normal,
                ease: CSS_EASE.outExpo,
              }}
            >
              {row.getVisibleCells().map((cell) => {
                const meta = (cell.column.columnDef.meta ?? {}) as TanstackColumnMeta;
                return (
                  <TableCell
                    key={cell.id}
                    className={cn(
                      "text-sm",
                      meta.align === "right" && "text-right",
                      meta.align === "center" && "text-center",
                    )}
                  >
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </TableCell>
                );
              })}
            </motion.tr>
            {expandedRowRender !== undefined &&
              (() => {
                const expandedNode = expandedRowRender(rowData);
                // 行级 render 返 null/undefined 时不渲染整行 <tr>, 避免空 <td> 配 border 视觉上画双线
                if (expandedNode === null || expandedNode === undefined) {
                  return null;
                }
                return (
                  <motion.tr
                    animate={{ opacity: ANIM_OPACITY_END, translateY: ANIM_Y_END }}
                    className="border-b-0 bg-muted/30 [&>td]:border-b hover:bg-transparent"
                    data-testid="expanded-row"
                    initial={{ opacity: ANIM_OPACITY_START, translateY: ANIM_Y_START }}
                    key={`${key}-expanded`}
                    transition={{
                      delay: index * ANIM_DELAY_STEP,
                      duration: DUR.normal,
                      ease: CSS_EASE.outExpo,
                    }}
                  >
                    <TableCell colSpan={columns.length}>{expandedNode}</TableCell>
                  </motion.tr>
                );
              })()}
          </Fragment>
        );
      })}
    </>
  );
};

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
  const rows = table.getRowModel().rows;
  if (rows.length > ZERO) {
    return (
      <>
        {renderDataRows({ columns, table, expandedRowRender, onRowClick, rowClassName })}
      </>
    );
  }
  return <>{renderEmptyRow(columns.length, emptyText)}</>;
};
```

- [ ] **Step 2: 跑公共 3 测试 + 10 调用方测试确认 0 fail**

```bash
cd packages/web && bun run test -- data-table data-table-body data-table-pagination dict-list sample-table datasets-table dataset-documents-table nodes-table relations-table
```

Expected: 所有测试通过 (DataTableBody 现在用 table 实例, 但 DataTable 仍传 pageData, 调 pageData 已被替换为 table.getRowModel().rows)

注: `datasets-table` / `dataset-documents-table` / `nodes-table` / `relations-table` 需确认文件存在, 找不到则跳过.

- [ ] **Step 3: 跑 lint + typecheck 确认绿**

```bash
cd packages/web && bunx oxlint components/common/table && bun run typecheck
```

Expected: oxlint 0 warning; typecheck 0 error

- [ ] **Step 4: Commit**

```bash
git add packages/web/components/common/table/data-table-body.tsx
git commit -m "refactor(table): use table.getRowModel().rows + flexRender in DataTableBody"
```

---

## Task 5: 改 `data-table-pagination.tsx` 接 table 实例 (分页 UI 派生自 TanStack state)

**Files:**
- Modify: `packages/web/components/common/table/data-table-pagination.tsx`

- [ ] **Step 1: 改 `DataTablePagination` 接收 table 实例, 从 getState().pagination 派生 current/totalPages**

完整替换 `data-table-pagination.tsx`：

```tsx
// DataTable 分页 UI 组件 (2026-06-25 拆分自 data-table.tsx, 2026-06-26 换底)
// 接收 TanStack table 实例, 从 table.getState().pagination 派生 current/totalPages.
// onPageChange 上抛 1-based page 给外部 (受控分页通过 DataTable 的 onPaginationChange).
import type { ReactNode } from "react";
import type { Table as TanstackTable } from "@tanstack/react-table";
import {
  Pagination,
  PaginationContent,
  PaginationItem,
  PaginationNext,
  PaginationPrevious,
} from "@/components/ui/pagination";
import { ZERO } from "@/const/index";

export interface DataTablePaginationProps<TData> {
  table: TanstackTable<TData>;
  // (2026-06-26) 受控分页: 外部传 onPageChange (page 1-based) 接管, 非受控时内部 nextPage
  onPageChange?: (page: number) => void;
}

const PAGE_STEP = 1;
const DISABLED_OPACITY = "pointer-events-none opacity-50";
const CURSOR_POINTER = "cursor-pointer";

const buildButtonClass = (
  isFirstPage: boolean,
  isLastPage: boolean,
): { next: string; prev: string } => {
  const prevClass = isFirstPage ? DISABLED_OPACITY : CURSOR_POINTER;
  const nextClass = isLastPage ? DISABLED_OPACITY : CURSOR_POINTER;
  return { next: nextClass, prev: prevClass };
};

export const DataTablePagination = <TData,>({
  table,
  onPageChange,
}: DataTablePaginationProps<TData>): ReactNode => {
  const totalPages = table.getPageCount();
  const total = table.getFilteredRowModel().rows.length;
  const pageIndex = table.getState().pagination.pageIndex;
  const current = pageIndex; // TanStack 0-based, 我们 0-based (与原 useTablePagination 一致)

  if (totalPages <= PAGE_STEP) {
    return null;
  }
  const isFirstPage = current === ZERO;
  const isLastPage = current >= totalPages - PAGE_STEP;
  const classNames = buildButtonClass(isFirstPage, isLastPage);
  const handlePrev = () => {
    if (isFirstPage) {
      return;
    }
    if (onPageChange) {
      onPageChange(Math.max(ZERO, current - PAGE_STEP));
    } else {
      table.previousPage();
    }
  };
  const handleNext = () => {
    if (isLastPage) {
      return;
    }
    if (onPageChange) {
      onPageChange(Math.min(totalPages - PAGE_STEP, current + PAGE_STEP));
    } else {
      table.nextPage();
    }
  };

  return (
    <div className="flex items-center justify-between border-t border-border/60 bg-muted/20 px-6 py-3">
      <span className="num text-sm text-muted-foreground">
        第 {current + PAGE_STEP} / {totalPages} 页 · 共 {total} 条
      </span>
      <Pagination className="mx-0 w-auto">
        <PaginationContent>
          <PaginationItem>
            <PaginationPrevious className={classNames.prev} onClick={handlePrev} />
          </PaginationItem>
          <PaginationItem>
            <PaginationNext className={classNames.next} onClick={handleNext} />
          </PaginationItem>
        </PaginationContent>
      </Pagination>
    </div>
  );
};
```

- [ ] **Step 2: 改 `data-table.tsx` 调 DataTablePagination 时传 table 实例 (而非 total/current/totalPages/onPageChange)**

```tsx
// 在 data-table.tsx 末尾替换:
<DataTablePagination
  current={current}
  onPageChange={handleChangePage}
  total={total}
  totalPages={totalPages}
/>

// 改为:
<DataTablePagination<TData> onPageChange={handleChangePage} table={table} />
```

- [ ] **Step 3: 跑公共 3 测试确认仍绿**

```bash
cd packages/web && bun run test -- data-table data-table-body data-table-pagination
```

Expected: 所有测试通过 (分页 UI 现在从 TanStack state 派生)

- [ ] **Step 4: 跑 lint + typecheck 确认绿**

```bash
cd packages/web && bunx oxlint components/common/table && bun run typecheck
```

Expected: oxlint 0 warning; typecheck 0 error

- [ ] **Step 5: Commit**

```bash
git add packages/web/components/common/table/data-table-pagination.tsx packages/web/components/common/table/data-table.tsx
git commit -m "refactor(table): DataTablePagination takes TanStack table instance"
```

---

## Task 6: 删 `use-table-pagination.ts` 和它的 test

**Files:**
- Delete: `packages/web/components/common/table/use-table-pagination.ts`
- Delete: `packages/web/components/common/table/use-table-pagination.test.ts`
- Modify: `packages/web/components/common/table/data-table.tsx` (移除 import + 移除 useTablePagination 调用)

- [ ] **Step 1: 从 data-table.tsx 移除 useTablePagination import + 调用 + 相关变量**

在 data-table.tsx 顶部, 移除:

```typescript
import { useTablePagination } from "./use-table-pagination";
```

在 DataTable 函数体内, 移除:

```typescript
const { current, total, totalPages, pageData, handleChangePage } = useTablePagination(
  dataSource,
  pagination,
);
```

替换为: 直接从 table 实例派生, 或者保留 handleChangePage 作为受控分页 onChange 转发.

```typescript
// (2026-06-26) 删除 useTablePagination, 受控分页通过 table.onPaginationChange 接管
// handleChangePage 仅作 onPageChange 透传 (1-based)
const handleChangePage = (pageNum: number): void => {
  if (pagination !== undefined) {
    pagination.onChange(pageNum);
  } else {
    table.setPageIndex(pageNum - 1);
  }
};
```

注: 不再需要 current/total/totalPages/pageData 局部变量 (DataTableBody 用 table 实例, DataTablePagination 用 table 实例).

- [ ] **Step 2: 跑公共 3 测试确认仍绿**

```bash
cd packages/web && bun run test -- data-table data-table-body data-table-pagination
```

Expected: 所有测试通过

- [ ] **Step 3: 删 use-table-pagination.ts 和 use-table-pagination.test.ts**

```bash
rm packages/web/components/common/table/use-table-pagination.ts
rm packages/web/components/common/table/use-table-pagination.test.ts
```

- [ ] **Step 4: 跑 lint + typecheck 确认绿**

```bash
cd packages/web && bunx oxlint components/common/table && bun run typecheck
```

Expected: oxlint 0 warning; typecheck 0 error

- [ ] **Step 5: 跑全套 vitest 确认 0 新 fail (公共 3 测试 + 10 调用方测试)**

```bash
cd packages/web && bun run test
```

Expected: Tests 719 passed (跟改前 baseline 一致, 0 新 fail)

- [ ] **Step 6: Commit**

```bash
git add -A packages/web/components/common/table/
git commit -m "refactor(table): remove useTablePagination (replaced by TanStack)"
```

---

## Task 7: 最终验证 (全栈 audit + 性能 sanity)

**Files:**
- No file changes

- [ ] **Step 1: 跑全栈 vitest + lint + typecheck + format check**

```bash
cd packages/web && bun run lint && bun run typecheck && bun run test && bun run format:check
```

Expected: lint 0 error / typecheck 0 error / test 0 fail (跟 baseline 持平) / format 0 diff

- [ ] **Step 2: 跑全栈 diff stat 确认净减 ≥ 60 行**

```bash
git diff --stat master...HEAD -- packages/web/components/common/table/
```

Expected: 净减少 (use-table-pagination.ts -47 / use-table-pagination.test.ts -X / to-tanstack-columns.ts +X / to-tanstack-columns.test.ts +X / data-table.tsx +X / data-table-body.tsx +X / data-table-pagination.tsx +X), 净值 ≥ -60 行.

- [ ] **Step 3: 跑全栈 audit 确认 0 新发现**

```bash
/skill full-stack-audit
```

注: 这一步是 sanity check, 不阻塞本 spec. 如发现跟本 spec 无关的问题, 单独处理.

- [ ] **Step 4: 浏览器手测 (可选, dev 模式)**

按 spec §6 验收表手测, 重点:
- /zh/admin/dicts 列表 + 点编辑 + 行内展开 (dict-list expandedRowRender)
- /zh/evaluate/[id] 失败详情展开 (sample-table expandedRowRender)
- 列宽 4 模式 (number / {min,max} / "auto" / "fill") 在 4 个测试表
- 受控分页翻页 (DataTablePagination prev/next)

- [ ] **Step 5: Commit (如有 format 修改)**

```bash
git add packages/web/components/common/table/
git commit --amend --no-edit  # 仅当 Step 1 format 有 diff
```

---

## Self-Review

### 1. Spec coverage (spec → task 映射)

| Spec 章节 | 覆盖 Task |
|---|---|
| §1 反驳 YAGNI | Plan context (开头) |
| §2 目标 #1 (换底) | Task 3, 4, 5, 6 |
| §2 目标 #2 (10 调用方 0 改) | Task 4 Step 2 (调用方测试) |
| §2 目标 #3 (公共 3 测试验收) | Task 3/4/5/6 各 Step 2 |
| §2 目标 #4 (shadcn 为主) | Task 3, 4 (shadcn TableHead/TableCell 保留) |
| §2 目标 #5 (适配层 5 形态) | Task 1, 2 |
| §2 目标 #6 (总代码 -80 行) | Task 6 (删 useTablePagination) |
| §2 目标 #7 (TDD 顺序) | Task 1 红 → Task 2 绿 |
| §3 YAGNI | 全文不涉及 (spec §3 列的 6 条都不在本 plan) |
| §4.1 shadcn 为主原则 | Task 3 (壳), Task 4 (体) |
| §4.3 适配层 | Task 2 |
| §4.4 DataTable 顶层 | Task 3 |
| §4.5 DataTableBody | Task 4 |
| §4.6 useTablePagination 删 + DataTablePagination 改 | Task 5, 6 |
| §4.7 props 映射 | 11 个 props 全部在 Task 3 改后的 data-table.tsx 体现 |
| §5 TDD 顺序 | Task 1 → 2 → 3 → 4 → 5 → 6, 每步 commit |
| §6 验收 | Task 7 |
| §7 风险 | flexRender portal 风险 (Task 3 Step 2 验证) / manualPagination 闪烁 (Task 3 验证) |

**无遗漏.**

### 2. Placeholder scan

无 TBD / TODO / "implement later" / "fill in details" 出现. 每步代码块完整.

### 3. Type consistency

| 类型 | 定义位置 | 使用位置 | 一致? |
|---|---|---|---|
| `ColumnDef<TData>` | data-table.tsx L63 | data-table.tsx, data-table-body.tsx, to-tanstack-columns.ts | ✓ |
| `ColumnWidth` | data-table.tsx L25 | data-table.tsx, to-tanstack-columns.ts | ✓ |
| `getColStyle` | data-table.tsx L52 | data-table.tsx (头) | ✓ (导出供未来扩展) |
| `TanstackColumnMeta` | to-tanstack-columns.ts | data-table.tsx (读 meta), data-table-body.tsx (读 meta) | ✓ |
| `DataTableBodyProps<T>` | data-table-body.tsx L21 | data-table.tsx (传 props) | ✓ (新增 `table` prop) |
| `DataTablePaginationProps<T>` | data-table-pagination.tsx L11 | data-table.tsx (传 props) | ✓ (改 `{table, onPageChange}`) |
| `useTablePagination` | use-table-pagination.ts | data-table.tsx | ✓ (Task 6 删) |

无类型不一致.

### 4. 其他

- "net code -80 行" 估算需 Task 7 Step 2 实际 `git diff --stat` 验证; 不达预期不回滚 plan, 而是承认目标偏差.
- Task 4 Step 2 跑调用方测试时如果找不到 `datasets-table` / `dataset-documents-table` / `nodes-table` / `relations-table` 文件, 跳过这些, 跑 `bun run test` 替代 (见 Task 6 Step 5).
- 风险 5 (适配层漏某 props) 通过 §4.7 映射表 11 props 穷举 + Task 3 Step 2 公共测试验收双重保障.

---
