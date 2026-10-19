# TanStack Table 教程

> 📅 创建日期：2026-06-25
> 📁 项目代码引用：本教程以 `c:/doc/Code/rag` 仓库当前代码为准，所有引用标注 `file_path:line_number`
> 🏷️ 类别：L-语言/框架
> 🎯 读者：中高级 TS 工程师

---

## 目录

- [一、是什么 & 适用场景](#一是什么--适用场景)
- [二、安装 & 开发环境](#二安装--开发环境)
- [三、基础语法 & 类型系统](#三基础语法--类型系统)
- [四、核心概念](#四核心概念)
- [五、常用命令 & 工具链](#五常用命令--工具链)
- [六、项目集成点](#六项目集成点)
- [七、项目代码示例](#七项目代码示例)
- [八、项目没用到的能力 / 进阶方向](#八项目没用到的能力--进阶方向)
- [九、最佳实践 & 常见坑](#九最佳实践--常见坑)

---

## 一、是什么 & 适用场景

TanStack Table（前身 React Table v8）是一个**无头（headless）表格库**，跟 TanStack Query / Form 同一个团队出品。它只管表格的状态机（排序 / 分页 / 筛选 / 列定义），UI 完全自己控制。

**同类对比：**

| 库 | 定位 | 本项目选择理由 |
|------|------|----------------|
| **TanStack Table** | Headless 表格 | TS 推断好，可控性高 |
| **AG Grid** | 商业表格 | 重，付费 |
| **MUI DataGrid** | 完整 UI 表格 | 绑 MUI，体积大 |
| **Ant Design Table** | 完整 UI 表格 | 绑 Antd |
| **react-table（旧版 v7）** | 旧版 TanStack | 升级到 v8 |

**TanStack Table 解决的核心问题**：
- **Headless**：完全控制 UI（项目用 shadcn `<Table>` 原语）
- **类型安全**：`ColumnDef<T>` 强类型列定义
- **状态机**：排序 / 分页 / 筛选 / 列显隐 / 行选择 / 列 resize
- **服务端分页 / 筛选**：支持受控 / 非受控两种模式
- **虚拟滚动**：`@tanstack/react-virtual` 配合，10 万行不卡

---

## 二、安装 & 开发环境

### 2.1 安装

```bash
# 项目已装 (@tanstack/react-table: ^8.21.3)
cd packages/web
bun install
```

### 2.2 项目风格

项目用 TanStack Table 配合 shadcn `<Table>` 原语，自己包装成 `<DataTable<T>>` 组件（项目 `web/CLAUDE.md` §封装组件强制使用）。

---

## 三、基础语法 & 类型系统

### 3.1 列定义

```typescript
import { ColumnDef } from "@tanstack/react-table";

type User = { id: number; name: string; email: string };

const columns: ColumnDef<User>[] = [
  {
    accessorKey: "id",                     // 数据字段名
    header: "ID",
  },
  {
    accessorKey: "name",
    header: "姓名",
    cell: (info) => <span className="font-medium">{info.getValue<string>()}</span>,
  },
  {
    accessorKey: "email",
    header: "邮箱",
  },
  {
    id: "actions",                          // 没有 accessorKey 也能用
    header: "操作",
    cell: ({ row }) => <Button onClick={() => deleteUser(row.original.id)}>删除</Button>,
  },
];
```

### 3.2 基础表格

```typescript
import { useReactTable, getCoreRowModel, flexRender } from "@tanstack/react-table";

export const UsersTable = ({ data }: { data: User[] }) => {
  const table = useReactTable({
    data,
    columns,
    getCoreRowModel: getCoreRowModel(),  // 必需：核心模型
  });

  return (
    <table>
      <thead>
        {table.getHeaderGroups().map(group => (
          <tr key={group.id}>
            {group.headers.map(h => (
              <th key={h.id}>{flexRender(h.column.columnDef.header, h.getContext())}</th>
            ))}
          </tr>
        ))}
      </thead>
      <tbody>
        {table.getRowModel().rows.map(row => (
          <tr key={row.id}>
            {row.getVisibleCells().map(cell => (
              <td key={cell.id}>{flexRender(cell.column.columnDef.cell, cell.getContext())}</td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
};
```

### 3.3 排序

```typescript
import { getSortedRowModel } from "@tanstack/react-table";

const table = useReactTable({
  data,
  columns,
  getCoreRowModel: getCoreRowModel(),
  getSortedRowModel: getSortedRowModel(),
});

// 表头加点击
<th onClick={header.column.getToggleSortingHandler()}>
  {flexRender(header.column.columnDef.header, header.getContext())}
  {{
    asc: " 🔼",
    desc: " 🔽",
  }[header.column.getIsSorted() as string] ?? null}
</th>
```

### 3.4 分页

```typescript
import { getPaginationRowModel } from "@tanstack/react-table";

const table = useReactTable({
  data,
  columns,
  getCoreRowModel: getCoreRowModel(),
  getPaginationRowModel: getPaginationRowModel(),
  initialState: { pagination: { pageSize: 20 } },
});

// 控制
<button onClick={() => table.previousPage()} disabled={!table.getCanPreviousPage()}>
  上一页
</button>
<button onClick={() => table.nextPage()} disabled={!table.getCanNextPage()}>
  下一页
</button>
```

### 3.5 筛选

```typescript
import { getFilteredRowModel } from "@tanstack/react-table";

const [filter, setFilter] = useState("");

const table = useReactTable({
  data,
  columns,
  state: { globalFilter: filter },
  onGlobalFilterChange: setFilter,
  getCoreRowModel: getCoreRowModel(),
  getFilteredRowModel: getFilteredRowModel(),
  getSortedRowModel: getSortedRowModel(),
  getPaginationRowModel: getPaginationRowModel(),
});
```

### 3.6 服务端分页 / 排序 / 筛选

```typescript
const [{ pageIndex, pageSize }, setPagination] = useState({ pageIndex: 0, pageSize: 20 });
const [sorting, setSorting] = useState<SortingState>([]);
const [filter, setFilter] = useState("");

const { data, isLoading } = useQuery({
  queryKey: ["users", { pageIndex, pageSize, sorting, filter }],
  queryFn: () => fetchUsers({ page: pageIndex + 1, pageSize, sort: sorting[0]?.id, order: sorting[0]?.desc ? "desc" : "asc", filter }),
});

const table = useReactTable({
  data: data?.items ?? [],
  columns,
  pageCount: data?.totalPages ?? -1,
  state: { pagination: { pageIndex, pageSize }, sorting, globalFilter: filter },
  onPaginationChange: setPagination,
  onSortingChange: setSorting,
  onGlobalFilterChange: setFilter,
  manualPagination: true,
  manualSorting: true,
  manualFiltering: true,
  getCoreRowModel: getCoreRowModel(),
});
```

---

## 四、核心概念

### 4.1 核心模型（RowModel）

TanStack Table 8 的核心是 **RowModel 管道**：

```
data → getCoreRowModel → getFilteredRowModel → getSortedRowModel → getPaginationRowModel → rows
```

每个 model 接收上一个的输出，添加一层处理。需要哪个就加哪个。

### 4.2 受控 vs 非受控

- **非受控**：TanStack 自己管 state（`initialState` + `state`）
- **受控**：外部管 state（`state` + `onStateChange`）

项目做服务端分页必须用受控。

### 4.3 ColumnDef

```typescript
{
  accessorKey: "name",      // 或 accessorFn: (row) => row.nested.field
  id: "actions",             // 可选，没 accessorKey 时必须有 id
  header: "姓名",            // 表头内容
  cell: (info) => ...,       // 单元格内容
  footer: (info) => ...,     // 表尾内容
  enableSorting: true,
  enableHiding: false,
  size: 200,                 // 宽度
  meta: { ... },             // 自定义 meta
}
```

### 4.4 flexRender

把 ColumnDef 的 `header` / `cell` / `footer` 渲染为 React 节点（支持字符串 / JSX / 函数）。

```typescript
flexRender(column.columnDef.header, header.getContext())
```

### 4.5 虚拟滚动（10 万行）

```bash
bun add @tanstack/react-virtual
```

```typescript
const rowVirtualizer = useVirtualizer({
  count: rows.length,
  getScrollElement: () => tableContainerRef.current,
  estimateSize: () => 35,
  overscan: 10,
});
```

---

## 五、常用命令 & 工具链

```bash
# 项目无专属命令
bun run typecheck
```

---

## 六、项目集成点

### 6.1 项目**强制**使用 `<DataTable<T>>` 封装

`packages/web/CLAUDE.md` §封装组件明确：

> 所有表格必须用 `<DataTable<T>>`，禁止直接用 shadcn `<Table>` 拼 markup

`<DataTable<T>>` 内部用 TanStack Table 8 + shadcn `<Table>` 原语：

- **API**：`dataSource` + `columns: ColumnDef<T>[]` + `rowKey` + `pagination` + `emptyText` + `loading` + `onRowClick`
- **能力**：列渲染（含 `render(row, i)`）、本地分页、sticky 表头、行 stagger 动画、loading、空态
- **空态**：优先 `<DataEmpty icon title description variant />`（来自 `@/components/common/DataEmpty`）

### 6.2 测试模式

```typescript
screen.getAllByTestId("data-table-row")
```

---

## 七、项目代码示例

### 7.1 项目 `<DataTable<T>>` 用法

`components/admin/users-table.tsx`：

```typescript
"use client";
import { ColumnDef } from "@tanstack/react-table";
import { DataTable } from "@/components/common/data-table";
import { useUsers } from "@/lib/api/users";

type User = { id: number; email: string; display_name: string; role: string };

const columns: ColumnDef<User>[] = [
  { accessorKey: "id", header: "ID" },
  { accessorKey: "email", header: "邮箱" },
  { accessorKey: "display_name", header: "显示名" },
  {
    accessorKey: "role",
    header: "角色",
    cell: ({ row }) => <Badge>{row.original.role}</Badge>,
  },
  {
    id: "actions",
    header: "操作",
    cell: ({ row }) => <Button onClick={() => editUser(row.original)}>编辑</Button>,
  },
];

export const UsersTable = () => {
  const { data, isLoading } = useUsers();

  return (
    <DataTable<User>
      dataSource={data?.items ?? []}
      columns={columns}
      rowKey="id"
      loading={isLoading}
      emptyText="暂无用户"
    />
  );
};
```

### 7.2 项目 `<DataTable<T>>` 内部实现

`components/common/data-table/data-table.tsx`（项目风格）：

```typescript
"use client";
import { useReactTable, getCoreRowModel, getPaginationRowModel, flexRender, ColumnDef } from "@tanstack/react-table";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { DataEmpty } from "@/components/common/DataEmpty";
import { cn } from "@/lib/utils";

type DataTableProps<T> = {
  dataSource: T[];
  columns: ColumnDef<T>[];
  rowKey: keyof T;
  emptyText?: React.ReactNode;
  loading?: boolean;
  onRowClick?: (row: T) => void;
  rowClassName?: (row: T) => string;
  expandedRowRender?: (row: T) => React.ReactNode;
};

export const DataTable = <T,>({
  dataSource, columns, rowKey, emptyText = <DataEmpty />, loading, onRowClick, rowClassName, expandedRowRender,
}: DataTableProps<T>) => {
  const table = useReactTable({
    data: dataSource,
    columns,
    getCoreRowModel: getCoreRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    initialState: { pagination: { pageSize: 20 } },
    getRowId: (row) => String(row[rowKey]),
  });

  if (loading) return <Skeleton className="h-32" />;
  if (dataSource.length === 0) return <>{emptyText}</>;

  return (
    <Table>
      <TableHeader className="sticky top-0 bg-background z-10">
        {table.getHeaderGroups().map(group => (
          <TableRow key={group.id}>
            {group.headers.map(h => (
              <TableHead key={h.id}>{flexRender(h.column.columnDef.header, h.getContext())}</TableHead>
            ))}
          </TableRow>
        ))}
      </TableHeader>
      <TableBody>
        {table.getRowModel().rows.map(row => (
          <TableRow
            key={row.id}
            onClick={() => onRowClick?.(row.original)}
            className={cn("cursor-pointer hover:bg-muted/50", rowClassName?.(row.original))}
            data-testid="data-table-row"
          >
            {row.getVisibleCells().map(cell => (
              <TableCell key={cell.id}>{flexRender(cell.column.columnDef.cell, cell.getContext())}</TableCell>
            ))}
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
};
```

### 7.3 自定义列渲染

```typescript
const columns: ColumnDef<Conversation>[] = [
  {
    accessorKey: "created_at",
    header: "创建时间",
    cell: ({ row }) => (
      <span className="text-muted-foreground text-sm">
        {formatDistanceToNow(new Date(row.original.created_at), { addSuffix: true, locale: zhCN })}
      </span>
    ),
  },
  {
    accessorKey: "title",
    header: "标题",
    cell: ({ row }) => (
      <div className="font-medium">{row.original.title || <span className="text-muted-foreground">新对话</span>}</div>
    ),
  },
  {
    id: "actions",
    header: "操作",
    cell: ({ row }) => (
      <div className="flex gap-2">
        <Button variant="ghost" size="sm" onClick={() => openConv(row.original)}>打开</Button>
        <Button variant="ghost" size="sm" onClick={() => deleteConv(row.original.id)}>删除</Button>
      </div>
    ),
  },
];
```

### 7.4 受控分页

```typescript
const [page, setPage] = useState(1);
const [pageSize, setPageSize] = useState(20);

const { data, isLoading } = useQuery({
  queryKey: ["conversations", page, pageSize],
  queryFn: () => fetchConversations({ page, pageSize }),
});

return (
  <DataTable
    dataSource={data?.items ?? []}
    columns={columns}
    rowKey="id"
    loading={isLoading}
    pagination={{
      page,
      pageSize,
      total: data?.total ?? 0,
      onPageChange: setPage,
      onPageSizeChange: setPageSize,
    }}
  />
);
```

### 7.5 行选择

```typescript
const [selection, setSelection] = useState<Record<string, boolean>>({});

const table = useReactTable({
  data,
  columns: [
    {
      id: "select",
      header: ({ table }) => (
        <Checkbox
          checked={table.getIsAllRowsSelected()}
          onCheckedChange={(v) => table.toggleAllRowsSelected(!!v)}
        />
      ),
      cell: ({ row }) => (
        <Checkbox
          checked={row.getIsSelected()}
          onCheckedChange={(v) => row.toggleSelected(!!v)}
        />
      ),
    },
    // ... 其他列
  ],
  enableRowSelection: true,
  state: { rowSelection: selection },
  onRowSelectionChange: setSelection,
  getCoreRowModel: getCoreRowModel(),
});
```

### 7.6 列显隐

```typescript
const [columnVisibility, setColumnVisibility] = useState<VisibilityState>({});

const table = useReactTable({
  data,
  columns,
  state: { columnVisibility },
  onColumnVisibilityChange: setColumnVisibility,
  getCoreRowModel: getCoreRowModel(),
});

// 切换列显隐
<Button onClick={() => table.setColumnVisibility({ id: false })}>隐藏 ID</Button>
<Button onClick={() => table.setColumnVisibility({ id: true })}>显示 ID</Button>
```

---

## 八、项目没用到的能力 / 进阶方向

以下 TanStack Table 能力项目当前未充分使用（**待评估**）：

| 能力 | 用途 | 集成建议 |
|------|------|----------|
| **虚拟滚动** | 10 万行表格 | 大数据列表场景 |
| **列拖拽排序** | 拖动改列顺序 | 复杂 dashboard |
| **列 resize** | 拖动改列宽 | Excel 式体验 |
| **列固定** | sticky left/right | 横向滚动表 |
| **行选择** | 批量操作 | 项目暂用 DataTable 默认未启 |
| **行展开** | `expandedRowRender` | master-detail 视图 |
| **聚合** | 列底 `footer` | 报表场景 |
| **数据导出** | CSV / Excel | `xlsx` 包已装，待集成 |
| **服务端筛选** | 搜索框 + 远程筛 | 复杂查询 |

**建议关注**：虚拟滚动 + 列固定是大数据表格的标配。

---

## 九、最佳实践 & 常见坑

### 项目风格指南（项目 CLAUDE.md 强制）

1. **必须用 `<DataTable<T>>`**：不要直接用 shadcn `<Table>` 拼 markup
2. **行 key 选唯一字段**：`rowKey="id"` 而非 index
3. **空态用 `<DataEmpty icon title description variant />`**：而非纯文本
4. **测试用 `data-testid="data-table-row"`**：断言行存在
5. **不重复包装**：DataTable 内置分页 / loading / 空态，不在外面再写一遍

### 最佳实践

1. **类型化 ColumnDef**：

```typescript
const columns: ColumnDef<User>[] = [...];
// 而不是 const columns = [...]  // any
```

2. **列定义放组件内**：

```typescript
// ✅ 列定义在组件内，t() hook 可用
export const UsersTable = () => {
  const t = useTranslations();
  const columns: ColumnDef<User>[] = [
    { accessorKey: "email", header: t("邮箱") },
  ];
  // ...
};

// ❌ 列定义在组件外，t() 拿不到
const columns = [{ header: t("邮箱") }];  // 报错
```

3. **受控状态放父组件**：用 `useState` + props 传入，DataTable 不存跨组件状态

4. **行 onClick + checkbox 互斥**：

```typescript
<TableRow
  onClick={(e) => {
    if ((e.target as HTMLElement).closest("button, input, a")) return;  // 排除按钮
    onRowClick?.(row.original);
  }}
>
```

5. **空态文案要传 i18n key**：

```typescript
emptyText={<DataEmpty title={t("暂无用户")} />}
```

### 常见坑

1. **没有 `getCoreRowModel()`**：表格不渲染任何行

2. **`accessorKey` 拼错**：表格不显示列。TypeScript 强类型会捕获

3. **`flexRender` 漏掉 `getContext()`**：

```typescript
// ❌ 错
flexRender(h.column.columnDef.header)

// ✅ 对
flexRender(h.column.columnDef.header, h.getContext())
```

4. **分页受控没传 `pageCount`**：服务端分页必须传 `pageCount: data.totalPages`

5. **服务端筛选时 `manualFiltering: true`**：不然 TanStack 会同时做客户端筛选，结果不对

6. **行 click + checkbox 互斥**：默认行 onClick 会触发，但点 checkbox 时也触发，要排除

7. **空数组不显示空态**：必须 `if (dataSource.length === 0) return <emptyText />`

8. **测试 mock data 用 `as` 断言**：

```typescript
const data = [{ id: 1, name: "Alice" }] as User[];
```

9. **column `id` 重复**：所有列 id 必须唯一，否则 `row.getVisibleCells()` 错乱

10. **`useReactTable` 不在循环里**：必须组件顶层调用

---

## 📚 参考

- [TanStack Table 官方文档](https://tanstack.com/table/latest)
- [TanStack Table v8 迁移指南](https://tanstack.com/table/latest/docs/guide/migrating)
- [TanStack Table Examples](https://tanstack.com/table/latest/docs/examples)
- [@tanstack/react-virtual](https://tanstack.com/virtual/latest)
- [项目 web/CLAUDE.md §表格组件](../../packages/web/CLAUDE.md)

---

**状态：** ✅ 已完成

**最后更新：** 2026-06-25
