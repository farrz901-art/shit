import { describe, expect, it } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "./table";

describe("Table", () => {
  it("渲染无报错", () => {
    render(
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>列1</TableHead>
            <TableHead>列2</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          <TableRow>
            <TableCell>数据1</TableCell>
            <TableCell>数据2</TableCell>
          </TableRow>
        </TableBody>
      </Table>,
    );
    expect(screen.getByText("列1")).toBeInTheDocument();
    expect(screen.getByText("数据1")).toBeInTheDocument();
  });
});
