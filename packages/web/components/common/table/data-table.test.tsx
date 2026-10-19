import { describe, expect, it, vi } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import { DataTable, type ColumnDef } from "./data-table";

interface User {
  id: string;
  name: string;
  age: number;
}

const TEST_DATA_COUNT = 2;
const FIRST_INDEX = 0;
const AGE_FIRST = 25;
const AGE_SECOND = 30;
const CONTROLLED_PAGE_INDEX = 2;
const CONTROLLED_PAGE_SIZE = 2;
const CONTROLLED_TOTAL = 5;
const COL_WIDTH_PX = 240;
const COL_MIN = 150;
const COL_MAX = 300;

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

describe("DataTable", () => {
  describe("基础渲染", () => {
    it("渲染表头", () => {
      render(<DataTable dataSource={data} columns={columns} rowKey="id" />);
      expect(screen.getByText("ID")).toBeInTheDocument();
      expect(screen.getByText("姓名")).toBeInTheDocument();
      expect(screen.getByText("年龄")).toBeInTheDocument();
    });

    it("渲染 N 行数据", () => {
      render(<DataTable dataSource={data} columns={columns} rowKey="id" />);
      expect(screen.getAllByTestId("data-table-row")).toHaveLength(TEST_DATA_COUNT);
    });

    it("列 render 函数被调用", () => {
      render(<DataTable dataSource={data} columns={columns} rowKey="id" />);
      expect(screen.getAllByTestId("age")).toHaveLength(TEST_DATA_COUNT);
      expect(screen.getAllByTestId("age")[FIRST_INDEX]).toHaveTextContent("25岁");
    });
  });

  describe("空数据", () => {
    it("空数据显示 emptyText", () => {
      render(<DataTable dataSource={[]} columns={columns} rowKey="id" emptyText="暂无数据" />);
      expect(screen.getByText("暂无数据")).toBeInTheDocument();
    });
  });

  describe("受控分页集成", () => {
    it("受控分页: pagination prop 接管", () => {
      const onChange = vi.fn();
      const pagedData = Array.from({ length: CONTROLLED_TOTAL }, (_unused, idx) => ({
        age: AGE_FIRST + idx,
        id: String(idx),
        name: `用户${idx}`,
      }));
      render(
        <DataTable
          dataSource={pagedData}
          columns={columns}
          rowKey="id"
          pagination={{
            current: CONTROLLED_PAGE_INDEX,
            onChange,
            pageSize: CONTROLLED_PAGE_SIZE,
            total: CONTROLLED_TOTAL,
          }}
        />,
      );
      expect(screen.getByText("用户2")).toBeInTheDocument();
      expect(screen.getByText(/第 2 \/ 3 页/)).toBeInTheDocument();
    });
  });

  describe("sticky 表头", () => {
    it("maxHeight 启用 sticky", () => {
      const { container } = render(
        <DataTable dataSource={data} columns={columns} rowKey="id" maxHeight="60vh" />,
      );
      const thead = container.querySelector("thead");
      expect(thead?.className).toContain("sticky");
    });

    it("maxHeight=auto 不启用 sticky", () => {
      const { container } = render(<DataTable dataSource={data} columns={columns} rowKey="id" />);
      const thead = container.querySelector("thead");
      expect(thead?.className).not.toContain("sticky");
    });
  });

  describe("列宽 4 模式", () => {
    it("列 width 为 number 时渲染 width: Npx", () => {
      const { container } = render(
        <DataTable
          dataSource={data}
          columns={[
            {
              accessorKey: "name",
              header: () => "姓名",
              meta: { width: COL_WIDTH_PX },
            },
          ]}
          rowKey="id"
        />,
      );
      const th = container.querySelector("th");
      expect(th?.style.width).toBe(`${COL_WIDTH_PX}px`);
    });

    it("列 width 为 { min, max } 时渲染 minWidth + 可选 maxWidth", () => {
      const { container } = render(
        <DataTable
          dataSource={data}
          columns={[
            {
              accessorKey: "name",
              header: () => "姓名",
              meta: { width: { max: COL_MAX, min: COL_MIN } },
            },
          ]}
          rowKey="id"
        />,
      );
      const th = container.querySelector("th");
      expect(th?.style.minWidth).toBe(`${COL_MIN}px`);
      expect(th?.style.maxWidth).toBe(`${COL_MAX}px`);
    });

    it("列 width 为 'auto' 时渲染 width: auto", () => {
      const { container } = render(
        <DataTable
          dataSource={data}
          columns={[{ accessorKey: "name", header: () => "姓名", meta: { width: "auto" } }]}
          rowKey="id"
        />,
      );
      const th = container.querySelector("th");
      expect(th?.style.width).toBe("auto");
    });

    it("列 width 为 'fill' 时渲染 minWidth: 0 + width: 100%", () => {
      const { container } = render(
        <DataTable
          dataSource={data}
          columns={[{ accessorKey: "name", header: () => "姓名", meta: { width: "fill" } }]}
          rowKey="id"
        />,
      );
      const th = container.querySelector("th");
      expect(th?.style.minWidth).toBe("0");
      expect(th?.style.width).toBe("100%");
    });
  });

  describe("行交互", () => {
    it("onRowClick 触发", async () => {
      const userEventModule = await import("@testing-library/user-event");
      const user = userEventModule.default;
      const onClick = vi.fn();
      render(<DataTable dataSource={data} columns={columns} rowKey="id" onRowClick={onClick} />);
      await user.click(screen.getAllByTestId("data-table-row")[FIRST_INDEX]);
      expect(onClick).toHaveBeenCalledWith(data[FIRST_INDEX], FIRST_INDEX);
    });
  });
});
