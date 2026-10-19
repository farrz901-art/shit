# DataTable 内部换 TanStack Table 内核 (2026-06-26)

> 起源: 2026-06-26 admin/dicts "两条线" bug 暴露自管实现隐藏耦合, 同时 2026-06-25 拆 spec YAGNI 决定装 1 年 0 用变死库存
> 范围: DataTable 内部换 `@tanstack/react-table` 内核, **对外 API 100% 不变**, 10 调用方 0 改动
> 不依赖: 2026-06-25 拆 spec (已完成, 落在 master), 2026-06-26 bug 修复 (已落 DataTableBody 行级 nullish 跳过 `<tr>`)

## 1. 反驳 2026-06-25 拆 spec 的 YAGNI 决定

原 YAGNI 段（[2026-06-25-data-table-split-design.md §2](2026-06-25-data-table-split-design.md) 节选）:
> ❌ 引入 `@tanstack/react-table` — 装了 1 年 0 业务使用, 装好备用而已; 当前自管分页 / 列宽 / 行渲染已是完整轻量实现, 换底层会同时拆 + 换引擎, 风险叠加

**反驳论据** (2026-06-26 截至时点):

1. **2026-06-26 admin/dicts "两条线" bug 暴露自管实现的隐藏耦合**: 拆 spec 时只测了 "传函数 / 不传" 两种状态, **没测 "传函数但行级返 null" 这种半状态**. TanStack 内建 `row.getIsSelected()` / `row.getCanSelect()` 等显式状态机 API; 自管实现靠 className 字符串拼 `&[&>td]:border-b` 这种魔法, 出现隐性状态机会漏测.
2. **"装好备用" 1 年 0 用 = 死库存**: `@tanstack/react-table@8.21.3` 装 1 年没用, 每次 `bun install` 还在 lockfile 占空间. **要么用要么卸** — YAGNI 不能 "装好放着".
3. **未来 cell edit 不可避免**: dict-list 行内编辑 + evaluate 失败详情展开行 + 未来更多 inline edit 需求, TanStack 的 `column.columnDef.meta` + `row.meta` 模式是社区标准, 自管要重新发明.
4. **适配层吃 100% props 差异**: 现有 11 props 都有 1-to-1 TanStack 映射, 10 调用方 0 改动是**可达成的**, 不是 "风险叠加". 已逐个 props 验证映射路径 (见 §4.7 适配层).
5. **风险对比**: 保持自管 = 持续承担隐藏耦合风险 (如本 bug 暴露的); 换底 = 一次性的 200 行适配层 + 3 个公共测试验收. **长期风险换底更低**.

**结论**: 本 spec **推翻** 2026-06-25 拆 spec 的 YAGNI 决定, 但只换底 (不加 cell edit / sort / filter), 把 "换引擎" 和 "加功能" 解耦.

## 2. 目标

| # | 目标 | 验收 |
|---|---|---|
| 1 | DataTable 内部换 TanStack Table 内核 | 内部用 `useReactTable` + `flexRender`, 外部 API 100% 不变 |
| 2 | 10 调用方 0 改动 | 现有 156 测试文件 0 改动, 0 fail |
| 3 | 公共 3 个 DataTable 测试 0 改动充当 "行为不变" 验收 | data-table.test.tsx / data-table-body.test.tsx / data-table-pagination.test.tsx 全绿 |
| 4 | shadcn 为主, TanStack 为辅 (关键设计原则) | shadcn `<Table>` / `<TableHead>` / `<TableRow>` / `<TableCell>` 全部保留; TanStack 只提供 row model + flexRender |
| 5 | 适配层 1-to-1 透明 | `toTanstackColumns` 单元测试覆盖所有 5 种 column 形态 (string key / render fn / align / 4 种 width) |
| 6 | 总代码量 -80 行 | `use-table-pagination.ts` 删, `getPaginationRowModel` 替; 适配层 +200 行; 净 -80 |
| 7 | TDD 顺序: 适配层先测 | 写 `to-tanstack-columns.test.ts` 先红, 再写 `to-tanstack-columns.ts` 转绿 |

## 3. 非目标 (YAGNI)

- ❌ 加 cell edit / inline edit (另开 spec: `2026-06-26-cell-edit-on-tanstack-design.md`)
- ❌ 加 sort / filter / column resize / jump-to-page / 列拖拽
- ❌ 改 shadcn `Table` 原语 (`components/ui/table.tsx`)
- ❌ 改 `ColumnDef<T>` / `DataTableProps<T>` shape
- ❌ 改 10 个调用方任何业务代码
- ❌ 移除 `@tanstack/react-table` 依赖 (装好就装好)
- ❌ 加 `@tanstack/react-table` 周边包 (`@tanstack/react-virtual` 等)
- ❌ 改 sticky / stagger / 列宽 4 模式 / 分页栏样式行为 (纯结构性换底, 行为 0 变化)

## 4. 设计

### 4.1 关键设计原则: shadcn 为主, TanStack 为辅

**TanStack 只负责数据模型层**:
- `useReactTable` 算 row model / pagination
- `flexRender` 是头/cell 的渲染出口 (接受 ReactNode 或函数)

**shadcn 负责 DOM/CSS 层**:
- `<Table>` / `<TableHeader>` / `<TableBody>` / `<TableRow>` / `<TableHead>` / `<TableCell>` 全部用 shadcn 原语
- `border-b transition-colors hover:bg-muted/50 data-[state=selected]:bg-muted` 等所有 className 走 shadcn
- sticky / loading / empty 旁路不变

**`flexRender` 用法**:
- header: `flexRender(h.column.columnDef.header, h.getContext())` — header 是 `() => string` (我们 `() => col.title`)
- cell: `flexRender(cell.column.columnDef.cell, cell.getContext())` — cell 是 `(ctx) => col.render?.(ctx.row.original, ctx.row.index) ?? String(ctx.getValue())`

**好处**:
- 适配层只翻译**数据模型** (ColumnDef[] → TanStack ColumnDef[]), **不动 CSS**
- shadcn `Table` 原语不动 = 视觉 0 变化
- 未来换 shadcn 主题 / dark mode 不用碰 TanStack
- 10 调用方对 shadcn className 假设 (如 `cn(className)`) 继续工作

### 4.2 新文件结构

```
packages/web/components/common/table/
  ├── data-table.tsx                  # 改: 顶层 useReactTable, 接收 table 实例往下传
  ├── to-tanstack-columns.ts          # 新: 适配层 (ColumnDef[] → TanStack ColumnDef[])
  ├── to-tanstack-columns.test.ts     # 新: 适配层单元测试
  ├── use-table-pagination.ts         # 删 (被 getPaginationRowModel 替, 通过 hook wrapper 保留 API)
  ├── use-table-pagination.test.ts    # 删
  ├── data-table-pagination.tsx       # 改: 接收 table 实例派生分页状态
  ├── data-table-body.tsx             # 改: 用 table.getRowModel().rows + flexRender
  ├── data-table-skeleton.tsx         # 不动
  ├── data-table.test.tsx             # 不动 (公共行为验收)
  ├── data-table-body.test.tsx        # 不动
  └── data-table-pagination.test.tsx  # 不动
```

### 4.3 适配层 (`to-tanstack-columns.ts`)

```ts
import type { ColumnDef as TanstackColumnDef } from "@tanstack/react-table";
import type { CSSProperties } from "react";
import type { ColumnDef, ColumnWidth } from "./data-table";

// 复用 data-table.tsx 的列宽工具 (挪到独立文件, 或保留在 data-table.tsx 导出)
const getColStyle = (width: ColumnWidth | undefined): CSSProperties | undefined => { ... };

export const toTanstackColumns = <TData,>(
  columns: ColumnDef<TData>[],
): TanstackColumnDef<TData>[] => {
  return columns.map((col) => ({
    id: col.key,
    accessorKey: col.key,
    header: () => col.title,
    cell: (ctx: { row: { original: TData; index: number }; getValue: () => unknown }) =>
      col.render ? col.render(ctx.row.original, ctx.row.index) : String(ctx.getValue() ?? "—"),
    meta: { align: col.align, width: col.width },
    enableSorting: false,
    enableColumnFilter: false,
  }));
};
```

### 4.4 DataTable 顶层

```tsx
import { getCoreRowModel, getPaginationRowModel, useReactTable, flexRender } from "@tanstack/react-table";
import { Table, TableBody, TableHead, TableHeader, TableRow } from "@/components/ui/table";  // shadcn

export const DataTable = <TData,>({ dataSource, columns, rowKey, pagination, maxHeight, onRowClick, rowClassName, expandedRowRender, emptyText, loading, className }) => {
  const tanstackColumns = toTanstackColumns<TData>(columns);
  
  const table = useReactTable<TData>({
    data: dataSource,
    columns: tanstackColumns,
    getRowId: (row, idx) => String(row[rowKey] ?? idx),
    getCoreRowModel: getCoreRowModel(),
    ...(pagination ? {
      getPaginationRowModel: getPaginationRowModel(),
      manualPagination: true,
      pageCount: Math.ceil(pagination.total / pagination.pageSize),
      state: { pagination: { pageIndex: pagination.current - 1, pageSize: pagination.pageSize } },
      onPaginationChange: (updater) => {
        const next = typeof updater === "function" 
          ? updater({ pageIndex: pagination.current - 1, pageSize: pagination.pageSize }) 
          : updater;
        pagination.onChange(next.pageIndex + 1);
      },
    } : {}),
  });
  
  // 外壳不变 (sticky / maxHeight / 滚动 / 边框)
  return (
    <div className={cn("rounded-lg border border-border/60", className)}>
      <div className={cn("min-h-0 overflow-auto", stickyEnabled && "flex-1")} style={{ maxHeight: containerStyle }}>
        <Table>
          <TableHeader className={cn(stickyEnabled && "sticky top-0 z-10 bg-muted/80 backdrop-blur-sm")}>
            {table.getHeaderGroups().map((hg) => (
              <TableRow key={hg.id}>
                {hg.headers.map((h) => {
                  const colDef = columns.find((c) => c.key === h.column.id);
                  return (
                    <TableHead
                      key={h.id}
                      className={cn(
                        "eyebrow whitespace-nowrap",
                        colDef?.align === "right" && "text-right",
                        colDef?.align === "center" && "text-center",
                      )}
                      style={getColStyle(colDef?.width)}
                    >
                      {flexRender(h.column.columnDef.header, h.getContext())}
                    </TableHead>
                  );
                })}
              </TableRow>
            ))}
          </TableHeader>
          <TableBody className="[&_tr:last-child]:border-0">
            <DataTableBody
              table={table}
              columns={columns}     // 保留: expandedRowRender / loading / empty 旁路
              emptyText={emptyText}
              expandedRowRender={expandedRowRender}
              loading={loading}
              onRowClick={onRowClick}
              rowClassName={rowClassName}
            />
          </TableBody>
        </Table>
      </div>
      <DataTablePagination table={table} onPageChange={pagination?.onChange} />
    </div>
  );
};
```

### 4.5 DataTableBody 改

```tsx
// 内部: 仍用 shadcn <TableCell>, 但 data 来自 table.getRowModel().rows
import { TableCell } from "@/components/ui/table";  // shadcn

export const DataTableBody = <TData,>({ table, columns, loading, emptyText, expandedRowRender, onRowClick, rowClassName }) => {
  if (loading) {
    return <>{renderLoadingRow(columns.length)}</>;
  }
  
  const rows = table.getRowModel().rows;
  if (rows.length === 0) {
    return <>{renderEmptyRow(columns.length, emptyText)}</>;
  }
  
  return (
    <>
      {rows.map((row, index) => {
        const rowData = row.original;
        const key = row.id;
        const handleClick = () => onRowClick?.(rowData, index);
        return (
          <Fragment key={key}>
            <motion.tr
              className={cn("border-b transition-colors hover:bg-muted/50", onRowClick && "cursor-pointer", rowClassName?.(rowData))}
              data-testid="data-table-row"
              onClick={handleClick}
              {...motion props}
            >
              {row.getVisibleCells().map((cell) => {
                const colDef = columns.find((c) => c.key === cell.column.id);
                return (
                  <TableCell
                    key={cell.id}
                    className={cn("text-sm", colDef?.align === "right" && "text-right", colDef?.align === "center" && "text-center")}
                  >
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </TableCell>
                );
              })}
            </motion.tr>
            {expandedRowRender !== undefined && (() => {
              const node = expandedRowRender(rowData);
              if (node === null || node === undefined) return null;
              return (
                <motion.tr
                  className="border-b-0 bg-muted/30 [&>td]:border-b hover:bg-transparent"
                  data-testid="expanded-row"
                  key={`${key}-expanded`}
                  {...motion props}
                >
                  <TableCell colSpan={columns.length}>{node}</TableCell>
                </motion.tr>
              );
            })()}
          </Fragment>
        );
      })}
    </>
  );
};
```

### 4.6 useTablePagination 删 + DataTablePagination 改

**`use-table-pagination.ts` 删** — 被 `getPaginationRowModel` 替.

**`data-table-pagination.tsx` 改**:
```tsx
// 接收整个 table 实例, 从 table.getState().pagination 派生 current/totalPages
export const DataTablePagination = ({ table, onPageChange }) => {
  const { pageIndex, pageSize } = table.getState().pagination;
  const total = table.getFilteredRowModel().rows.length;  // or table.getRowCount()
  const totalPages = table.getPageCount();
  const current = pageIndex + 1;  // TanStack 0-based, 我们 1-based
  return (
    <Pagination ...>...</Pagination>
  );
};
```

### 4.7 props 映射表 (1-to-1 验证)

| DataTable 现有 prop | TanStack 映射 | 验证 |
|---|---|---|
| `dataSource: TData[]` | `data: dataSource` | ✓ |
| `columns: ColumnDef<T>[]` | `columns: toTanstackColumns(columns)` | 适配层 (4.3) |
| `rowKey: keyof T & string` | `getRowId: (row) => row[rowKey]` | ✓ |
| `pagination?` | `getPaginationRowModel` + `manualPagination` + `onPaginationChange` | 受控分页 (4.4) |
| `maxHeight?` | 不变 (外壳 div style) | ✓ |
| `onRowClick?` | DataTableBody 内 `onClick={handleClick}` | ✓ |
| `rowClassName?` | DataTableBody 内 `className={cn(..., rowClassName?.(rowData))}` | ✓ |
| `expandedRowRender?` | DataTableBody 内 旁路插额外 `<motion.tr>` | ✓ (行级 null 跳过保留) |
| `emptyText?` | DataTableBody 内 `rows.length === 0` 旁路 | ✓ |
| `loading?` | DataTableBody 内 `loading` 旁路 | ✓ |
| `className?` | 外壳 div className | ✓ |

**所有 11 props 都有 1-to-1 映射**, 0 兼容 shim 需求.

## 5. TDD 顺序

按 [project-rules §TDD](docs/superpowers/specs) 铁律:

1. **format** → `bun run format` 0 报错
2. **lint fix** → `bunx oxlint components/common/table` 0 报错
3. **类型检查** → `bun run typecheck` 0 error
4. **测试** → 0 新 fail (pre-existing fail 不算)
5. **commit** (message 前缀 `refactor:`)

**TDD 步骤细分**:
- Step 1: 写 `to-tanstack-columns.test.ts` (5 个 column 形态) → 红
- Step 2: 写 `to-tanstack-columns.ts` → 绿
- Step 3: 改 `data-table.tsx` 加 `useReactTable` 算 headerGroups, 头走 flexRender; **保留原 `useTablePagination` 的 pageData** 给 DataTableBody; Step 4 头测试应仍绿 (行数据源暂时仍来自 useTablePagination 的 pageData 切片, 跟 TanStack 解耦)
- Step 4: 跑公共 3 测试 → 应仍绿 (头换, 行数据源不变)
- Step 5: 改 `data-table-body.tsx` 用 `table.getRowModel().rows` + flexRender, **移除 pageData 引用**
- Step 6: 跑公共 3 测试 + 10 调用方测试 → 0 fail
- Step 7: 改 `data-table-pagination.tsx` 接 table 实例
- Step 8: 删 `use-table-pagination.ts` + `use-table-pagination.test.ts`
- Step 9: 跑全套测试 → 0 fail
- Step 10: oxlint 0 warning + typecheck 0 error + commit

## 6. 验收

| 验收项 | 命令 | 通过条件 |
|---|---|---|
| 公共 3 个测试 | `bun run test -- data-table data-table-body data-table-pagination` | 0 fail |
| 10 调用方测试 | `bun run test -- dict-list sample-table datasets-table ...` | 0 fail |
| 适配层单元测试 | `bun run test -- to-tanstack-columns` | 0 fail |
| oxlint 0 warning | `bunx oxlint components/common/table` | 0 output |
| typecheck | `bun run typecheck` | 0 error |
| i18n 0 改 | `git diff messages/` | 0 diff |
| 10 调用方 0 改 | `git diff packages/web/app/ components/...` (除 `components/common/table/`) | 0 diff |
| 总代码 -80 行 | `git diff --stat` | 净减少 ≥ 60 行 (适配层 +200 / useTablePagination -280 = -80) |

## 7. 风险

| 风险 | 缓解 |
|---|---|
| `flexRender` 嵌套 shadcn `<TableCell>` 在 React Portal 上下文出错 | 先跑现有 3 个测试 (会渲染表头/表体); 若 portal 出问题改用顶层变量预计算 JSX |
| `getRowId` 引用相等性, 每次 render 新函数 → TanStack 内部缓存失效 | React 19 Compiler 自动稳定函数引用, 不需 `useCallback` 包裹 |
| TanStack `getRowModel` 默认按 `data` 引用变化重算, 父组件每次 render 新数组 → 性能差 | 调用方已有 `useState` 数据源, 不动 |
| `manualPagination: true` + 受控 current, 受控 → 非受控切换时闪烁 | 调用方都是受控或非受控二选一, 不切换 |
| 适配层 1-to-1 漏某 props | §4.7 映射表已穷举 12 props, 实施时核对 |

## 8. 关联文档

- [2026-06-25-data-table-split-design.md](2026-06-25-data-table-split-design.md) — 上游拆分 (本 spec 推翻其 YAGNI 决定)
- [CLAUDE.md §TDD 流程](CLAUDE.md) — format→lint→typecheck→test→commit 顺序不可颠倒
- [project-rules §严禁 shim](feedback-no-shim-no-minimal-changes) — 本 spec 不留兼容代码, 10 调用方一次到位
- [feedback-do-not-refactor-when-user-reports-bug](feedback-do-not-refactor-when-user-reports-bug) — 本 spec 由用户提议开新 spec, 非擅自重构
