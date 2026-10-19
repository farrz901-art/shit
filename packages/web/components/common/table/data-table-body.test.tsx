// DataTableBody 单元测试 (2026-06-25 拆分, 2026-06-26 换底: BodyHarness 造 useReactTable 实例)
// BodyHarness 包装 useReactTable 喂 DataTableBody, 因为 DataTableBody 现在直接收 TanStack table 实例.
// 行为断言 (loading/empty/data rows/onRowClick/rowClassName/expanded rows/h-40) 跟换底前一致.
import { describe, expect, it, vi } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { getCoreRowModel, useReactTable, type Table as TanstackTable } from "@tanstack/react-table";
import { DataTableBody } from "./data-table-body";
import type { ColumnDef } from "./data-table";

interface User {
  id: string;
  name: string;
  age: number;
}

const FIRST_INDEX = 0;
const ROW_COUNT = 2;
const EXPANDED_SKIP_NULL_LENGTH = 1;
const EXPANDED_ABSENT_LENGTH = 0;
const EMPTY_HEIGHT_CLASS = "h-40";
const AGE_FIRST = 25;
const AGE_SECOND = 30;

const columns: ColumnDef<User>[] = [
  { accessorKey: "id", header: () => "ID" },
  { accessorKey: "name", header: () => "姓名" },
  {
    accessorKey: "age",
    cell: (ctx) => <span data-testid="age">{ctx.row.original.age}岁</span>,
    header: () => "年龄",
  },
];

const data: User[] = [
  { age: AGE_FIRST, id: "1", name: "张三" },
  { age: AGE_SECOND, id: "2", name: "李四" },
];

// (2026-06-26) DataTableBody 现在收 TanStack table 实例, 测试里用 useReactTable 造一个.
interface BodyHarnessProps<TData> {
  dataSource: TData[];
  columns: ColumnDef<TData>[];
  loading: boolean;
  emptyText: ReactNode;
  onRowClick?: (row: TData, index: number) => void;
  rowClassName?: (row: TData) => string;
  expandedRowRender?: (row: TData) => ReactNode;
  rowKey: keyof TData & string;
}

const BodyHarness = <TData,>(props: BodyHarnessProps<TData>): ReactNode => {
  const table: TanstackTable<TData> = useReactTable<TData>({
    columns: props.columns,
    data: props.dataSource,
    getCoreRowModel: getCoreRowModel(),
    getRowId: (row, index) => String((row as Record<string, unknown>)[props.rowKey] ?? index),
  });
  return (
    <DataTableBody
      columns={props.columns}
      emptyText={props.emptyText}
      expandedRowRender={props.expandedRowRender}
      loading={props.loading}
      onRowClick={props.onRowClick}
      rowClassName={props.rowClassName}
      table={table}
    />
  );
};

const renderInTable = (children: ReactNode) =>
  render(
    <table>
      <tbody>{children}</tbody>
    </table>,
  );

const getRowClassName = (row: User): string => {
  if (row.name === "张三") {
    return "bg-test";
  }
  return "";
};

const getExpandedRowRender = (row: User): ReactNode => (
  <div data-testid="expanded">{row.name} 详情</div>
);

const renderExpanded = (row: User): ReactNode =>
  row.id === "1" ? null : <div data-testid="expanded">{row.name} 详情</div>;

describe("DataTableBody", () => {
  describe("状态分支", () => {
    it("loading=true 渲染加载行", () => {
      renderInTable(
        <BodyHarness
          columns={columns}
          dataSource={[]}
          emptyText="暂无数据"
          loading={true}
          rowKey="id"
        />,
      );
      expect(screen.getByText("加载中…")).toBeInTheDocument();
    });

    it("空数据 + emptyText string 渲染文本", () => {
      renderInTable(
        <BodyHarness
          columns={columns}
          dataSource={[]}
          emptyText="暂无数据"
          loading={false}
          rowKey="id"
        />,
      );
      expect(screen.getByText("暂无数据")).toBeInTheDocument();
    });

    it("空数据 + emptyText ReactNode 渲染节点", () => {
      const emptyNode: ReactNode = (
        <div>
          <span data-testid="empty-icon" />
          <p>暂无数据集</p>
        </div>
      );
      renderInTable(
        <BodyHarness
          columns={columns}
          dataSource={[]}
          emptyText={emptyNode}
          loading={false}
          rowKey="id"
        />,
      );
      expect(screen.getByTestId("empty-icon")).toBeInTheDocument();
      expect(screen.getByText("暂无数据集")).toBeInTheDocument();
    });

    it("有数据渲染 N 行", () => {
      renderInTable(
        <BodyHarness
          columns={columns}
          dataSource={data}
          emptyText="暂无数据"
          loading={false}
          rowKey="id"
        />,
      );
      expect(screen.getAllByTestId("data-table-row")).toHaveLength(ROW_COUNT);
    });
  });

  describe("列渲染", () => {
    it("列 render 函数被调用", () => {
      renderInTable(
        <BodyHarness
          columns={columns}
          dataSource={data}
          emptyText="暂无数据"
          loading={false}
          rowKey="id"
        />,
      );
      expect(screen.getAllByTestId("age")).toHaveLength(ROW_COUNT);
      expect(screen.getAllByTestId("age")[FIRST_INDEX]).toHaveTextContent("25岁");
    });
  });

  describe("行交互", () => {
    it("onRowClick 触发, 接收 row 和 index", async () => {
      const user = userEvent.setup();
      const onClick = vi.fn();
      renderInTable(
        <BodyHarness
          columns={columns}
          dataSource={data}
          emptyText="暂无数据"
          loading={false}
          onRowClick={onClick}
          rowKey="id"
        />,
      );
      await user.click(screen.getAllByTestId("data-table-row")[FIRST_INDEX]);
      expect(onClick).toHaveBeenCalledWith(data[FIRST_INDEX], FIRST_INDEX);
    });

    it("rowClassName 附加到行", () => {
      renderInTable(
        <BodyHarness
          columns={columns}
          dataSource={data}
          emptyText="暂无数据"
          loading={false}
          rowClassName={getRowClassName}
          rowKey="id"
        />,
      );
      const rows = screen.getAllByTestId("data-table-row");
      expect(rows[FIRST_INDEX].className).toContain("bg-test");
    });
  });

  describe("展开行", () => {
    it("expandedRowRender 渲染 N 个展开行", () => {
      renderInTable(
        <BodyHarness
          columns={columns}
          dataSource={data}
          emptyText="暂无数据"
          expandedRowRender={getExpandedRowRender}
          loading={false}
          rowKey="id"
        />,
      );
      expect(screen.getAllByTestId("expanded-row")).toHaveLength(ROW_COUNT);
    });

    it("expandedRowRender 对某行返 null 时不渲染该行 <tr>", () => {
      renderInTable(
        <BodyHarness
          columns={columns}
          dataSource={data}
          emptyText="暂无数据"
          expandedRowRender={renderExpanded}
          loading={false}
          rowKey="id"
        />,
      );
      const expandedRows = screen.getAllByTestId("expanded-row");
      expect(expandedRows).toHaveLength(EXPANDED_SKIP_NULL_LENGTH);
      expect(expandedRows[FIRST_INDEX]).toHaveTextContent("李四 详情");
    });

    it("未传 expandedRowRender 时不渲染任何展开行", () => {
      renderInTable(
        <BodyHarness
          columns={columns}
          dataSource={data}
          emptyText="暂无数据"
          loading={false}
          rowKey="id"
        />,
      );
      expect(screen.queryAllByTestId("expanded-row")).toHaveLength(EXPANDED_ABSENT_LENGTH);
    });
  });

  describe("样式", () => {
    it("空态行 / 加载行 占满高度 (h-40)", () => {
      const { container } = renderInTable(
        <BodyHarness
          columns={columns}
          dataSource={[]}
          emptyText="暂无数据"
          loading={false}
          rowKey="id"
        />,
      );
      const td = container.querySelector("td");
      expect(td?.className).toContain(EMPTY_HEIGHT_CLASS);
    });
  });
});
