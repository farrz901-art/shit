# UI 组件库封装 (Table + Dialog + Form) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build antd-style DataTable / AppDialog / AppConfirm / AppDrawer / Form components on top of shadcn, then replace all existing tables, dialogs, forms, and hand-written buttons across the codebase.

**Architecture:** `web/components/common/` holds business-agnostic wrappers. Each component wraps shadcn primitives (Table, Dialog, AlertDialog, Sheet) with antd-style API (columns, dataSource, open/onOpenChange, schema/FormItem). Form uses self-implemented `useForm` hook (no react-hook-form). All components tested with vitest + stories.

**Tech Stack:** React 19, shadcn/ui, Radix UI, class-variance-authority, Zod, vitest 4, @testing-library/react 16

---

## File Structure

**Create (common/ components):**
- `web/components/common/data-table/data-table.tsx`
- `web/components/common/data-table/data-table.test.tsx`
- `web/components/common/data-table/data-table.stories.tsx`
- `web/components/common/dialog/app-dialog.tsx`
- `web/components/common/dialog/app-dialog.test.tsx`
- `web/components/common/dialog/app-dialog.stories.tsx`
- `web/components/common/confirm/app-confirm.tsx`
- `web/components/common/confirm/app-confirm.test.tsx`
- `web/components/common/confirm/app-confirm.stories.tsx`
- `web/components/common/drawer/app-drawer.tsx`
- `web/components/common/drawer/app-drawer.test.tsx`
- `web/components/common/drawer/app-drawer.stories.tsx`
- `web/components/common/form/form.tsx`
- `web/components/common/form/form-item.tsx`
- `web/components/common/form/form-context.ts`
- `web/components/common/form/form.test.tsx`
- `web/components/common/form/form.stories.tsx`

**Modify (shadcn install):**
- `web/components/ui/` — add: sheet, popover, tooltip, separator, avatar, checkbox, switch, command, form, radio-group, calendar

**Modify (business replacements):**
- `web/app/knowledge/nodes/page.tsx` — table → DataTable
- `web/app/knowledge/relations/page.tsx` — table → DataTable
- `web/app/knowledge/documents/import/page.tsx` — table → DataTable
- `web/app/knowledge/triples/page.tsx` — table → DataTable
- `web/components/evaluate/SampleTable.tsx` — table → DataTable
- `web/app/evaluate/page.tsx` — grid → DataTable
- `web/app/output/page.tsx` — grid → DataTable
- `web/app/output/[task_id]/page.tsx` — flex → DataTable
- `web/app/decode/SeriesDialog.tsx` — Dialog → AppDialog
- `web/components/chat/SaveToKnowledgeDialog.tsx` — Dialog → AppDialog
- `web/components/knowledge/SchemaBrowser.tsx` — Dialog → AppDialog
- `web/app/knowledge/qa/page.tsx` — Dialog → AppDialog
- `web/components/chat/ChatShell.tsx` — AlertDialog → AppConfirm
- 9 files with motion.button → Button

**Create (audit):**
- `docs/superpowers/audit-2026-06-10-shadcn-coverage.md`

---

### Task 1: 补装 shadcn 缺失组件

**Files:**
- Modify: `web/components/ui/` (add 11 components)

- [ ] **Step 1: Install shadcn components**

```bash
cd web && npx shadcn@latest add sheet popover tooltip separator avatar checkbox switch command form radio-group calendar -y
```

- [ ] **Step 2: Verify files created**

```bash
ls web/components/ui/sheet.tsx web/components/ui/popover.tsx web/components/ui/tooltip.tsx web/components/ui/separator.tsx web/components/ui/avatar.tsx web/components/ui/checkbox.tsx web/components/ui/switch.tsx web/components/ui/command.tsx web/components/ui/form.tsx web/components/ui/radio-group.tsx web/components/ui/calendar.tsx
```

Expected: All 11 files exist.

- [ ] **Step 3: Run typecheck**

Run: `cd web && bun run typecheck`
Expected: 0 errors

- [ ] **Step 4: Commit**

```bash
git add web/components/ui/
git commit -m "feat(ui): 补装 shadcn 11 组件 (sheet/popover/tooltip/separator/avatar/checkbox/switch/command/form/radio-group/calendar)"
```

---

### Task 2: DataTable 基础渲染 (dataSource + columns + 表格骨架)

**Files:**
- Create: `web/components/common/data-table/data-table.tsx`
- Create: `web/components/common/data-table/data-table.test.tsx`

- [ ] **Step 1: Write the failing tests**

```tsx
// web/components/common/data-table/data-table.test.tsx
import { render, screen, within } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { DataTable } from "./data-table";

interface User { id: string; name: string; age: number; }

const columns = [
  { key: "id", title: "ID" },
  { key: "name", title: "姓名" },
  { key: "age", title: "年龄", render: (r: User) => <span data-testid="age">{r.age}岁</span> },
];

const data: User[] = [
  { id: "1", name: "张三", age: 25 },
  { id: "2", name: "李四", age: 30 },
];

describe("DataTable", () => {
  it("渲染表头", () => {
    render(<DataTable dataSource={data} columns={columns} rowKey="id" />);
    expect(screen.getByText("ID")).toBeInTheDocument();
    expect(screen.getByText("姓名")).toBeInTheDocument();
    expect(screen.getByText("年龄")).toBeInTheDocument();
  });

  it("渲染 N 行数据", () => {
    render(<DataTable dataSource={data} columns={columns} rowKey="id" />);
    const rows = screen.getAllByTestId("data-table-row");
    expect(rows).toHaveLength(2);
  });

  it("列 render 函数被调用", () => {
    render(<DataTable dataSource={data} columns={columns} rowKey="id" />);
    expect(screen.getAllByTestId("age")).toHaveLength(2);
    expect(screen.getAllByTestId("age")[0]).toHaveTextContent("25岁");
  });

  it("空数据显示 emptyText", () => {
    render(<DataTable dataSource={[]} columns={columns} rowKey="id" emptyText="暂无数据" />);
    expect(screen.getByText("暂无数据")).toBeInTheDocument();
  });

  it("loading 态显示加载中", () => {
    render(<DataTable dataSource={[]} columns={columns} rowKey="id" loading={true} />);
    expect(screen.getByText("加载中…")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd web && bun run test -- --run components/common/data-table/data-table.test.tsx`
Expected: FAIL — `Cannot find module`

- [ ] **Step 3: Write minimal implementation**

```tsx
// web/components/common/data-table/data-table.tsx
"use client";
// DataTable — antd 风格表格封装 (2026-06-10)
//   在 shadcn Table 上轻度封装: columns + dataSource + 分页 + sticky + 行交互
import { useState, type ReactNode } from "react";
import { motion } from "motion/react";
import {
  Table, TableHeader, TableBody, TableRow, TableHead, TableCell,
} from "@/components/ui/table";
import {
  Pagination, PaginationContent, PaginationItem,
  PaginationPrevious, PaginationNext,
} from "@/components/ui/pagination";
import { CSS_EASE, DUR } from "@/lib/motion";
import { cn } from "@/lib/utils";

export interface ColumnDef<T> {
  key: string;
  title: string;
  width?: number | string;
  align?: "left" | "center" | "right";
  render?: (row: T, index: number) => ReactNode;
}

export interface DataTableProps<T> {
  dataSource: T[];
  columns: ColumnDef<T>[];
  rowKey: keyof T & string;
  pagination?: { current: number; pageSize: number; total: number; onChange: (page: number) => void };
  maxHeight?: string | number;
  onRowClick?: (row: T, index: number) => void;
  rowClassName?: (row: T) => string;
  expandedRowRender?: (row: T) => ReactNode;
  emptyText?: string;
  loading?: boolean;
  className?: string;
}

const PAGE_SIZE = 20;

export function DataTable<T>({
  dataSource,
  columns,
  rowKey,
  pagination,
  maxHeight,
  onRowClick,
  rowClassName,
  expandedRowRender,
  emptyText = "暂无数据",
  loading = false,
  className,
}: DataTableProps<T>) {
  const [internalPage, setInternalPage] = useState(0);

  // 双模式分页: 传 pagination 走受控, 否则客户端
  const isControlled = !!pagination;
  const current = isControlled ? pagination.current : internalPage;
  const pageSize = isControlled ? pagination.pageSize : PAGE_SIZE;
  const total = isControlled ? pagination.total : dataSource.length;
  const totalPages = Math.ceil(total / pageSize);
  const pageData = isControlled
    ? dataSource
    : dataSource.slice(current * pageSize, (current + 1) * pageSize);

  const handleChangePage = (p: number) => {
    if (isControlled) pagination!.onChange(p);
    else setInternalPage(p);
  };

  const containerStyle = maxHeight && maxHeight !== "auto"
    ? { maxHeight: typeof maxHeight === "number" ? `${maxHeight}px` : maxHeight }
    : undefined;

  const stickyEnabled = maxHeight !== "auto" && !!maxHeight;

  return (
    <div className={cn("rounded-lg border border-border/40", className)}>
      <div
        className={cn("min-h-0 overflow-auto", stickyEnabled && "flex-1")}
        style={containerStyle}
      >
        <Table>
          <TableHeader className={cn(stickyEnabled && "sticky top-0 z-10 bg-muted/80 backdrop-blur-sm")}>
            <TableRow>
              {columns.map((col) => (
                <TableHead
                  key={col.key}
                  className={cn("eyebrow", col.align === "right" && "text-right", col.align === "center" && "text-center")}
                  style={col.width ? { width: typeof col.width === "number" ? `${col.width}px` : col.width } : undefined}
                >
                  {col.title}
                </TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading ? (
              <TableRow>
                <TableCell colSpan={columns.length} className="h-24 text-center text-muted-foreground">
                  <motion.span
                    animate={{ opacity: [0.4, 1, 0.4] }}
                    transition={{ duration: 1.6, repeat: Infinity }}
                  >
                    加载中…
                  </motion.span>
                </TableCell>
              </TableRow>
            ) : pageData.length > 0 ? (
              pageData.map((row, i) => {
                const key = String(row[rowKey]);
                return (
                  <motion.tr
                    key={key}
                    data-testid="data-table-row"
                    initial={{ opacity: 0, y: 4 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: DUR.normal, ease: CSS_EASE.outExpo, delay: i * 0.02 }}
                    className={cn(
                      "border-b transition-colors hover:bg-muted/50",
                      onRowClick && "cursor-pointer",
                      rowClassName?.(row),
                    )}
                    onClick={() => onRowClick?.(row, i)}
                  >
                    {columns.map((col) => (
                      <TableCell
                        key={col.key}
                        className={cn(col.align === "right" && "text-right", col.align === "center" && "text-center")}
                      >
                        {col.render ? col.render(row, i) : String((row as Record<string, unknown>)[col.key] ?? "—")}
                      </TableCell>
                    ))}
                  </motion.tr>
                );
              })
            ) : (
              <TableRow>
                <TableCell colSpan={columns.length} className="h-24 text-center text-muted-foreground">
                  {emptyText}
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>

      {/* 分页 */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between border-t border-border/40 px-4 py-2">
          <span className="num text-sm text-muted-foreground">
            第 {current + 1} / {totalPages} 页 · 共 {total} 条
          </span>
          <Pagination className="mx-0 w-auto">
            <PaginationContent>
              <PaginationItem>
                <PaginationPrevious
                  onClick={() => handleChangePage(Math.max(0, current - 1))}
                  className={current === 0 ? "pointer-events-none opacity-50" : "cursor-pointer"}
                />
              </PaginationItem>
              <PaginationItem>
                <PaginationNext
                  onClick={() => handleChangePage(Math.min(totalPages - 1, current + 1))}
                  className={current >= totalPages - 1 ? "pointer-events-none opacity-50" : "cursor-pointer"}
                />
              </PaginationItem>
            </PaginationContent>
          </Pagination>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd web && bun run test -- --run components/common/data-table/data-table.test.tsx`
Expected: PASS (5/5)

- [ ] **Step 5: Commit**

```bash
git add web/components/common/data-table/data-table.tsx web/components/common/data-table/data-table.test.tsx
git commit -m "feat(common): DataTable 基础渲染 (columns + dataSource + 空态 + loading)"
```

---

### Task 3: DataTable 客户端分页

**Files:**
- Modify: `web/components/common/data-table/data-table.test.tsx`

- [ ] **Step 1: Add pagination tests**

```tsx
// 追加到 data-table.test.tsx
it("客户端分页: 25 条数据分 2 页, 第 1 页 20 条", () => {
  const bigData = Array.from({ length: 25 }, (_, i) => ({ id: String(i), name: `用户${i}`, age: 20 + i }));
  render(<DataTable dataSource={bigData} columns={columns} rowKey="id" />);
  const rows = screen.getAllByTestId("data-table-row");
  expect(rows).toHaveLength(20);
  expect(screen.getByText(/第 1 \/ 2 页/)).toBeInTheDocument();
});

it("客户端分页: 点下一页切到第 2 页", async () => {
  const { userEvent } = await import("@testing-library/user-event");
  const user = userEvent.setup();
  const bigData = Array.from({ length: 25 }, (_, i) => ({ id: String(i), name: `用户${i}`, age: 20 + i }));
  render(<DataTable dataSource={bigData} columns={columns} rowKey="id" />);
  await user.click(screen.getByText("Next"));
  const rows = screen.getAllByTestId("data-table-row");
  expect(rows).toHaveLength(5);
  expect(screen.getByText(/第 2 \/ 2 页/)).toBeInTheDocument();
});
```

- [ ] **Step 2: Run tests**

Run: `cd web && bun run test -- --run components/common/data-table/data-table.test.tsx`
Expected: PASS (7/7) — pagination already implemented in Task 2

- [ ] **Step 3: Commit**

```bash
git add web/components/common/data-table/data-table.test.tsx
git commit -m "test(common): DataTable 客户端分页测试 (2 cases)"
```

---

### Task 4: DataTable 受控分页

**Files:**
- Modify: `web/components/common/data-table/data-table.test.tsx`

- [ ] **Step 1: Add controlled pagination tests**

```tsx
it("受控分页: pagination prop 接管", () => {
  const onChange = vi.fn();
  const data = Array.from({ length: 5 }, (_, i) => ({ id: String(i), name: `用户${i}`, age: 20 + i }));
  render(
    <DataTable
      dataSource={data}
      columns={columns}
      rowKey="id"
      pagination={{ current: 2, pageSize: 2, total: 5, onChange }}
    />,
  );
  // 受控模式下显示第 2 页数据 (index 2-3)
  expect(screen.getByText("用户2")).toBeInTheDocument();
  expect(screen.getByText(/第 3 \/ 3 页/)).toBeInTheDocument();
});
```

- [ ] **Step 2: Run tests**

Run: `cd web && bun run test -- --run components/common/data-table/data-table.test.tsx`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add web/components/common/data-table/data-table.test.tsx
git commit -m "test(common): DataTable 受控分页测试 (1 case)"
```

---

### Task 5: DataTable maxHeight + sticky 表头

**Files:**
- Modify: `web/components/common/data-table/data-table.test.tsx`

- [ ] **Step 1: Add maxHeight tests**

```tsx
it("maxHeight 启用 sticky 表头", () => {
  const { container } = render(
    <DataTable dataSource={data} columns={columns} rowKey="id" maxHeight="60vh" />,
  );
  const thead = container.querySelector("thead");
  expect(thead?.className).toContain("sticky");
});

it("maxHeight=auto 不启用 sticky", () => {
  const { container } = render(
    <DataTable dataSource={data} columns={columns} rowKey="id" maxHeight="auto" />,
  );
  const thead = container.querySelector("thead");
  expect(thead?.className).not.toContain("sticky");
});
```

- [ ] **Step 2: Run tests**

Run: `cd web && bun run test -- --run components/common/data-table/data-table.test.tsx`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add web/components/common/data-table/data-table.test.tsx
git commit -m "test(common): DataTable maxHeight + sticky 测试 (2 cases)"
```

---

### Task 6: DataTable 行交互 (rowKey / onRowClick / rowClassName / expandedRowRender)

**Files:**
- Modify: `web/components/common/data-table/data-table.test.tsx`

- [ ] **Step 1: Add row interaction tests**

```tsx
it("onRowClick 触发", async () => {
  const { userEvent } = await import("@testing-library/user-event");
  const user = userEvent.setup();
  const onClick = vi.fn();
  render(<DataTable dataSource={data} columns={columns} rowKey="id" onRowClick={onClick} />);
  await user.click(screen.getAllByTestId("data-table-row")[0]);
  expect(onClick).toHaveBeenCalledWith(data[0], 0);
});

it("rowClassName 附加到行", () => {
  render(
    <DataTable
      dataSource={data}
      columns={columns}
      rowKey="id"
      rowClassName={(r) => (r as User).name === "张三" ? "bg-test" : ""}
    />,
  );
  const rows = screen.getAllByTestId("data-table-row");
  expect(rows[0].className).toContain("bg-test");
});

it("expandedRowRender 展开行内容", () => {
  render(
    <DataTable
      dataSource={data}
      columns={columns}
      rowKey="id"
      expandedRowRender={(r) => <div data-testid="expanded">{(r as User).name} 详情</div>}
    />,
  );
  // expandedRowRender 在 v1 中作为额外行渲染
  expect(screen.getAllByTestId("expanded")).toHaveLength(2);
});
```

- [ ] **Step 2: Run tests**

Run: `cd web && bun run test -- --run components/common/data-table/data-table.test.tsx`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add web/components/common/data-table/data-table.test.tsx
git commit -m "test(common): DataTable 行交互测试 (onRowClick / rowClassName / expandedRowRender)"
```

---

### Task 7: AppDialog 基础 (受控 + title/description)

**Files:**
- Create: `web/components/common/dialog/app-dialog.tsx`
- Create: `web/components/common/dialog/app-dialog.test.tsx`

- [ ] **Step 1: Write the failing tests**

```tsx
// web/components/common/dialog/app-dialog.test.tsx
import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { AppDialog } from "./app-dialog";

describe("AppDialog", () => {
  it("open=true 渲染 title + description", () => {
    render(
      <AppDialog open={true} onOpenChange={vi.fn()} title="编辑" description="修改信息">
        <p>内容</p>
      </AppDialog>,
    );
    expect(screen.getByText("编辑")).toBeInTheDocument();
    expect(screen.getByText("修改信息")).toBeInTheDocument();
    expect(screen.getByText("内容")).toBeInTheDocument();
  });

  it("open=false 不渲染内容", () => {
    render(
      <AppDialog open={false} onOpenChange={vi.fn()} title="编辑">
        <p>内容</p>
      </AppDialog>,
    );
    expect(screen.queryByText("内容")).not.toBeInTheDocument();
  });

  it("footer 渲染", () => {
    render(
      <AppDialog open={true} onOpenChange={vi.fn()} title="编辑" footer={<button>保存</button>}>
        <p>内容</p>
      </AppDialog>,
    );
    expect(screen.getByText("保存")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd web && bun run test -- --run components/common/dialog/app-dialog.test.tsx`
Expected: FAIL

- [ ] **Step 3: Write implementation**

```tsx
// web/components/common/dialog/app-dialog.tsx
"use client";
// AppDialog — antd 风格弹框封装 (2026-06-10)
//   标题固定 + 内容滚动 + 底部固定
import type { ReactNode } from "react";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle,
  DialogDescription, DialogFooter,
} from "@/components/ui/dialog";
import { cn } from "@/lib/utils";

export interface AppDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title?: string;
  description?: string;
  maxWidth?: "sm" | "md" | "lg" | "xl" | "2xl" | "3xl";
  footer?: ReactNode;
  children: ReactNode;
  className?: string;
}

const maxWidthClass: Record<string, string> = {
  sm: "max-w-sm", md: "max-w-md", lg: "max-w-lg",
  xl: "max-w-xl", "2xl": "max-w-2xl", "3xl": "max-w-3xl",
};

export function AppDialog({
  open, onOpenChange, title, description, maxWidth = "lg",
  footer, children, className,
}: AppDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className={cn("flex flex-col gap-0 p-0", maxWidthClass[maxWidth], className)}>
        {/* Header: 固定 */}
        {(title || description) && (
          <DialogHeader className="border-b border-border/40 px-6 py-4">
            {title && <DialogTitle>{title}</DialogTitle>}
            {description && <DialogDescription>{description}</DialogDescription>}
          </DialogHeader>
        )}
        {/* Body: 滚动 */}
        <div className="flex-1 overflow-auto px-6 py-4">
          {children}
        </div>
        {/* Footer: 固定 (可选) */}
        {footer && (
          <DialogFooter className="border-t border-border/40 px-6 py-4">
            {footer}
          </DialogFooter>
        )}
      </DialogContent>
    </Dialog>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd web && bun run test -- --run components/common/dialog/app-dialog.test.tsx`
Expected: PASS (3/3)

- [ ] **Step 5: Commit**

```bash
git add web/components/common/dialog/app-dialog.tsx web/components/common/dialog/app-dialog.test.tsx
git commit -m "feat(common): AppDialog 基础 (受控 + title/description/footer + 滚动结构)"
```

---

### Task 8: AppDialog maxWidth + stories

**Files:**
- Create: `web/components/common/dialog/app-dialog.stories.tsx`
- Modify: `web/components/common/dialog/app-dialog.test.tsx`

- [ ] **Step 1: Add maxWidth test**

```tsx
it("maxWidth 应用到 className", () => {
  const { container } = render(
    <AppDialog open={true} onOpenChange={vi.fn()} title="测试" maxWidth="2xl">
      <p>内容</p>
    </AppDialog>,
  );
  const content = container.querySelector("[data-state='open']");
  expect(content?.className).toContain("max-w-2xl");
});
```

- [ ] **Step 2: Create stories**

```tsx
// web/components/common/dialog/app-dialog.stories.tsx
"use client";
import { useState } from "react";
import { AppDialog } from "./app-dialog";
import { Button } from "@/components/ui/button";

export function BasicStory() {
  const [open, setOpen] = useState(false);
  return (
    <>
      <Button onClick={() => setOpen(true)}>打开弹框</Button>
      <AppDialog open={open} onOpenChange={setOpen} title="基础弹框" description="这是一个描述">
        <p>弹框内容</p>
      </AppDialog>
    </>
  );
}

export function WithFooterStory() {
  const [open, setOpen] = useState(false);
  return (
    <>
      <Button onClick={() => setOpen(true)}>打开弹框</Button>
      <AppDialog
        open={open} onOpenChange={setOpen}
        title="确认操作"
        footer={<><Button variant="ghost" onClick={() => setOpen(false)}>取消</Button><Button>保存</Button></>}
      >
        <p>表单内容</p>
      </AppDialog>
    </>
  );
}

export function MaxWidthStory() {
  const [open, setOpen] = useState(false);
  return (
    <>
      <Button onClick={() => setOpen(true)}>打开大弹框</Button>
      <AppDialog open={open} onOpenChange={setOpen} title="大弹框" maxWidth="3xl">
        <p>3xl 宽度</p>
      </AppDialog>
    </>
  );
}
```

- [ ] **Step 3: Run tests**

Run: `cd web && bun run test -- --run components/common/dialog/app-dialog.test.tsx`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add web/components/common/dialog/
git commit -m "feat(common): AppDialog maxWidth + stories (3 demos)"
```

---

### Task 9: AppConfirm (走 AlertDialog)

**Files:**
- Create: `web/components/common/confirm/app-confirm.tsx`
- Create: `web/components/common/confirm/app-confirm.test.tsx`
- Create: `web/components/common/confirm/app-confirm.stories.tsx`

- [ ] **Step 1: Write the failing tests**

```tsx
// web/components/common/confirm/app-confirm.test.tsx
import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { AppConfirm } from "./app-confirm";

describe("AppConfirm", () => {
  it("open=true 渲染 title + description + 按钮", () => {
    render(
      <AppConfirm open={true} onOpenChange={vi.fn()} title="删除" description="不可撤销"
        confirmText="删除" cancelText="取消" onConfirm={vi.fn()} />,
    );
    expect(screen.getByText("删除")).toBeInTheDocument();
    expect(screen.getByText("不可撤销")).toBeInTheDocument();
    expect(screen.getByText("取消")).toBeInTheDocument();
  });

  it("点确认触发 onConfirm", async () => {
    const { userEvent } = await import("@testing-library/user-event");
    const user = userEvent.setup();
    const onConfirm = vi.fn();
    render(
      <AppConfirm open={true} onOpenChange={vi.fn()} title="删除"
        confirmText="删除" onConfirm={onConfirm} />,
    );
    await user.click(screen.getByText("删除"));
    expect(onConfirm).toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd web && bun run test -- --run components/common/confirm/app-confirm.test.tsx`
Expected: FAIL

- [ ] **Step 3: Write implementation**

```tsx
// web/components/common/confirm/app-confirm.tsx
"use client";
// AppConfirm — 危险操作二次确认 (2026-06-10)
import {
  AlertDialog, AlertDialogContent, AlertDialogHeader, AlertDialogTitle,
  AlertDialogDescription, AlertDialogFooter, AlertDialogAction, AlertDialogCancel,
} from "@/components/ui/alert-dialog";
import { cn } from "@/lib/utils";

export interface AppConfirmProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description?: string;
  confirmText?: string;
  cancelText?: string;
  variant?: "default" | "destructive";
  onConfirm: () => void;
  onCancel?: () => void;
}

export function AppConfirm({
  open, onOpenChange, title, description,
  confirmText = "确认", cancelText = "取消",
  variant = "default", onConfirm, onCancel,
}: AppConfirmProps) {
  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>{title}</AlertDialogTitle>
          {description && <AlertDialogDescription>{description}</AlertDialogDescription>}
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel onClick={onCancel}>{cancelText}</AlertDialogCancel>
          <AlertDialogAction
            onClick={onConfirm}
            className={cn(variant === "destructive" && "bg-destructive text-destructive-foreground")}
          >
            {confirmText}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd web && bun run test -- --run components/common/confirm/app-confirm.test.tsx`
Expected: PASS

- [ ] **Step 5: Create stories + Commit**

```tsx
// web/components/common/confirm/app-confirm.stories.tsx
"use client";
import { useState } from "react";
import { AppConfirm } from "./app-confirm";
import { Button } from "@/components/ui/button";

export function BasicStory() {
  const [open, setOpen] = useState(false);
  return (
    <>
      <Button variant="destructive" onClick={() => setOpen(true)}>删除</Button>
      <AppConfirm open={open} onOpenChange={setOpen} title="删除会话"
        description="此操作不可撤销" variant="destructive" onConfirm={() => alert("已删除")} />
    </>
  );
}
```

```bash
git add web/components/common/confirm/
git commit -m "feat(common): AppConfirm (AlertDialog 封装 + destructive 变体)"
```

---

### Task 10: AppDrawer (走 Sheet)

**Files:**
- Create: `web/components/common/drawer/app-drawer.tsx`
- Create: `web/components/common/drawer/app-drawer.test.tsx`
- Create: `web/components/common/drawer/app-drawer.stories.tsx`

- [ ] **Step 1: Write the failing tests**

```tsx
// web/components/common/drawer/app-drawer.test.tsx
import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { AppDrawer } from "./app-drawer";

describe("AppDrawer", () => {
  it("open=true 渲染 title + children", () => {
    render(
      <AppDrawer open={true} onOpenChange={vi.fn()} title="详情">
        <p>内容</p>
      </AppDrawer>,
    );
    expect(screen.getByText("详情")).toBeInTheDocument();
    expect(screen.getByText("内容")).toBeInTheDocument();
  });

  it("open=false 不渲染", () => {
    render(
      <AppDrawer open={false} onOpenChange={vi.fn()} title="详情">
        <p>内容</p>
      </AppDrawer>,
    );
    expect(screen.queryByText("内容")).not.toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd web && bun run test -- --run components/common/drawer/app-drawer.test.tsx`
Expected: FAIL

- [ ] **Step 3: Write implementation**

```tsx
// web/components/common/drawer/app-drawer.tsx
"use client";
// AppDrawer — 侧拉抽屉封装 (2026-06-10)
import type { ReactNode } from "react";
import {
  Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription, SheetFooter,
} from "@/components/ui/sheet";
import { cn } from "@/lib/utils";

export interface AppDrawerProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title?: string;
  description?: string;
  side?: "left" | "right";
  maxWidth?: string;
  footer?: ReactNode;
  children: ReactNode;
  className?: string;
}

export function AppDrawer({
  open, onOpenChange, title, description,
  side = "right", maxWidth, footer, children, className,
}: AppDrawerProps) {
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side={side} className={cn("flex flex-col gap-0 p-0", className)}
        style={maxWidth ? { maxWidth } : undefined}>
        {(title || description) && (
          <SheetHeader className="border-b border-border/40 px-6 py-4">
            {title && <SheetTitle>{title}</SheetTitle>}
            {description && <SheetDescription>{description}</SheetDescription>}
          </SheetHeader>
        )}
        <div className="flex-1 overflow-auto px-6 py-4">
          {children}
        </div>
        {footer && (
          <SheetFooter className="border-t border-border/40 px-6 py-4">
            {footer}
          </SheetFooter>
        )}
      </SheetContent>
    </Sheet>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd web && bun run test -- --run components/common/drawer/app-drawer.test.tsx`
Expected: PASS

- [ ] **Step 5: Create stories + Commit**

```tsx
// web/components/common/drawer/app-drawer.stories.tsx
"use client";
import { useState } from "react";
import { AppDrawer } from "./app-drawer";
import { Button } from "@/components/ui/button";

export function RightDrawerStory() {
  const [open, setOpen] = useState(false);
  return (
    <>
      <Button onClick={() => setOpen(true)}>打开右侧抽屉</Button>
      <AppDrawer open={open} onOpenChange={setOpen} title="任务详情" footer={<Button>完成</Button>}>
        <p>抽屉内容</p>
      </AppDrawer>
    </>
  );
}
```

```bash
git add web/components/common/drawer/
git commit -m "feat(common): AppDrawer (Sheet 封装 + left/right + footer)"
```

---

### Task 11: Form 核心 (useForm + FormContext + FormItem, 无验证)

**Files:**
- Create: `web/components/common/form/form-context.ts`
- Create: `web/components/common/form/form.tsx`
- Create: `web/components/common/form/form-item.tsx`
- Create: `web/components/common/form/form.test.tsx`

- [ ] **Step 1: Write the failing tests**

```tsx
// web/components/common/form/form.test.tsx
import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { Form } from "./form";
import { FormItem } from "./form-item";
import { Input } from "@/components/ui/input";

describe("Form", () => {
  it("渲染 children", () => {
    render(
      <Form initialValues={{ name: "" }} onFinish={vi.fn()}>
        <FormItem name="name" label="姓名">
          <Input />
        </FormItem>
      </Form>,
    );
    expect(screen.getByLabelText("姓名")).toBeInTheDocument();
  });

  it("FormItem 注入 value + onChange", async () => {
    const { userEvent } = await import("@testing-library/user-event");
    const user = userEvent.setup();
    render(
      <Form initialValues={{ name: "张三" }} onFinish={vi.fn()}>
        <FormItem name="name" label="姓名">
          <Input />
        </FormItem>
      </Form>,
    );
    const input = screen.getByLabelText("姓名") as HTMLInputElement;
    expect(input.value).toBe("张三");
    await user.clear(input);
    await user.type(input, "李四");
    expect(input.value).toBe("李四");
  });

  it("onFinish 提交 values", async () => {
    const { userEvent } = await import("@testing-library/user-event");
    const user = userEvent.setup();
    const onFinish = vi.fn();
    render(
      <Form initialValues={{ name: "张三" }} onFinish={onFinish}>
        <FormItem name="name" label="姓名">
          <Input />
        </FormItem>
        <button type="submit">提交</button>
      </Form>,
    );
    await user.click(screen.getByText("提交"));
    expect(onFinish).toHaveBeenCalledWith({ name: "张三" });
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd web && bun run test -- --run components/common/form/form.test.tsx`
Expected: FAIL

- [ ] **Step 3: Write form-context.ts**

```tsx
// web/components/common/form/form-context.ts
"use client";
// FormContext — 表单状态共享 (2026-06-10)
import { createContext, useContext } from "react";

export interface FormContextValue {
  values: Record<string, unknown>;
  errors: Record<string, string>;
  touched: Record<string, boolean>;
  setFieldValue: (name: string, value: unknown) => void;
  setFieldTouched: (name: string, touched: boolean) => void;
  registerField: (name: string) => void;
}

export const FormContext = createContext<FormContextValue | null>(null);

export function useFormContext() {
  const ctx = useContext(FormContext);
  if (!ctx) throw new Error("useFormContext must be used within <Form>");
  return ctx;
}
```

- [ ] **Step 4: Write form.tsx**

```tsx
// web/components/common/form/form.tsx
"use client";
// Form — antd 风格表单封装 (2026-06-10)
import { useState, useCallback, useRef, type ReactNode, type FormEvent } from "react";
import { FormContext, type FormContextValue } from "./form-context";

export interface FormProps {
  initialValues?: Record<string, unknown>;
  onFinish?: (values: Record<string, unknown>) => void;
  onFinishFailed?: (errors: Record<string, string>) => void;
  onValuesChange?: (changed: Record<string, unknown>, all: Record<string, unknown>) => void;
  layout?: "vertical" | "horizontal";
  children: ReactNode;
}

// 点分路径读写
function getByPath(obj: Record<string, unknown>, path: string): unknown {
  return path.split(".").reduce<unknown>((o, k) => (o && typeof o === "object" ? (o as Record<string, unknown>)[k] : undefined), obj);
}
function setByPath(obj: Record<string, unknown>, path: string, value: unknown): void {
  const keys = path.split(".");
  let cur: Record<string, unknown> = obj;
  for (let i = 0; i < keys.length - 1; i++) {
    if (!cur[keys[i]] || typeof cur[keys[i]] !== "object") cur[keys[i]] = {};
    cur = cur[keys[i]] as Record<string, unknown>;
  }
  cur[keys[keys.length - 1]] = value;
}

export function Form({
  initialValues = {}, onFinish, onFinishFailed, onValuesChange, layout = "vertical", children,
}: FormProps) {
  const [values, setValues] = useState<Record<string, unknown>>({ ...initialValues });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [touched, setTouched] = useState<Record<string, boolean>>({});
  const fieldsRef = useRef<Set<string>>(new Set());

  const registerField = useCallback((name: string) => {
    fieldsRef.current.add(name);
  }, []);

  const setFieldValue = useCallback((name: string, value: unknown) => {
    setValues((prev) => {
      const next = { ...prev };
      setByPath(next, name, value);
      onValuesChange?.({ [name]: value }, next);
      return next;
    });
    // 清除该字段错误
    setErrors((prev) => {
      if (!(name in prev)) return prev;
      const next = { ...prev };
      delete next[name];
      return next;
    });
  }, [onValuesChange]);

  const setFieldTouched = useCallback((name: string, t: boolean) => {
    setTouched((prev) => ({ ...prev, [name]: t }));
  }, []);

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (onFinish) onFinish(values);
  };

  const ctx: FormContextValue = { values, errors, touched, setFieldValue, setFieldTouched, registerField };

  const formStyle = layout === "horizontal"
    ? { display: "grid", gridTemplateColumns: "140px 1fr", gap: "12px", alignItems: "center" }
    : undefined;

  return (
    <FormContext.Provider value={ctx}>
      <form onSubmit={handleSubmit} style={formStyle} noValidate>
        {children}
      </form>
    </FormContext.Provider>
  );
}
```

- [ ] **Step 5: Write form-item.tsx**

```tsx
// web/components/common/form/form-item.tsx
"use client";
// FormItem — 表单项 (2026-06-10)
import { useEffect, cloneElement, isValidElement, type ReactNode, type ReactElement } from "react";
import { useFormContext } from "./form-context";
import { cn } from "@/lib/utils";
import { Label } from "@/components/ui/label";

export interface FormItemProps {
  name: string;
  label?: string;
  required?: boolean;
  help?: string;
  children: ReactNode;
  className?: string;
}

// 点分路径读写
function getByPath(obj: Record<string, unknown>, path: string): unknown {
  return path.split(".").reduce<unknown>((o, k) => (o && typeof o === "object" ? (o as Record<string, unknown>)[k] : undefined), obj);
}

export function FormItem({ name, label, required, help, children, className }: FormItemProps) {
  const { values, errors, touched, setFieldValue, setFieldTouched, registerField } = useFormContext();

  useEffect(() => { registerField(name); }, [name, registerField]);

  const value = getByPath(values, name);
  const error = errors[name];
  const isTouched = touched[name];

  // clone children 注入受控 props
  const enhancedChildren = isValidElement(children)
    ? cloneElement(children as ReactElement<Record<string, unknown>>, {
        value: value ?? "",
        onChange: (e: unknown) => {
          // 支持直接值或 event.target.value
          const v = e && typeof e === "object" && "target" in e
            ? (e as { target: { value: unknown } }).target.value
            : e;
          setFieldValue(name, v);
          (children as ReactElement<Record<string, unknown>>).props.onChange?.(e);
        },
        onBlur: () => setFieldTouched(name, true),
      })
    : children;

  return (
    <div className={cn("space-y-2", className)}>
      {label && (
        <Label className={cn(required && "after:content-['*'] after:ml-0.5 after:text-destructive")}>
          {label}
        </Label>
      )}
      {enhancedChildren}
      {help && !error && <p className="text-sm text-muted-foreground">{help}</p>}
      {error && isTouched && <p className="text-sm text-destructive">{error}</p>}
    </div>
  );
}
```

- [ ] **Step 6: Run test to verify it passes**

Run: `cd web && bun run test -- --run components/common/form/form.test.tsx`
Expected: PASS (3/3)

- [ ] **Step 7: Commit**

```bash
git add web/components/common/form/
git commit -m "feat(common): Form 核心 (useForm + FormContext + FormItem, 无验证)"
```

---

### Task 12: Form 验证 (Zod schema + 错误回填 + onFinishFailed)

**Files:**
- Modify: `web/components/common/form/form.tsx`
- Modify: `web/components/common/form/form.test.tsx`

- [ ] **Step 1: Add validation tests**

```tsx
// 追加到 form.test.tsx
import { z } from "zod";

it("Zod schema 验证失败回填 errors", async () => {
  const { userEvent } = await import("@testing-library/user-event");
  const user = userEvent.setup();
  const onFinishFailed = vi.fn();
  const schema = z.object({ name: z.string().min(2, "至少 2 字") });
  render(
    <Form initialValues={{ name: "" }} schema={schema} onFinishFailed={onFinishFailed}>
      <FormItem name="name" label="姓名">
        <Input />
      </FormItem>
      <button type="submit">提交</button>
    </Form>,
  );
  await user.click(screen.getByText("提交"));
  expect(onFinishFailed).toHaveBeenCalled();
  expect(screen.getByText("至少 2 字")).toBeInTheDocument();
});

it("Zod schema 验证成功触发 onFinish", async () => {
  const { userEvent } = await import("@testing-library/user-event");
  const user = userEvent.setup();
  const onFinish = vi.fn();
  const schema = z.object({ name: z.string().min(2) });
  render(
    <Form initialValues={{ name: "张三" }} schema={schema} onFinish={onFinish}>
      <FormItem name="name" label="姓名">
        <Input />
      </FormItem>
      <button type="submit">提交</button>
    </Form>,
  );
  await user.click(screen.getByText("提交"));
  expect(onFinish).toHaveBeenCalledWith({ name: "张三" });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd web && bun run test -- --run components/common/form/form.test.tsx`
Expected: FAIL — `schema` prop not recognized

- [ ] **Step 3: Add schema prop to Form**

修改 `form.tsx` 的 `FormProps` 和 `handleSubmit`:

```tsx
import type { ZodSchema } from "zod";

export interface FormProps {
  initialValues?: Record<string, unknown>;
  schema?: ZodSchema;
  onFinish?: (values: Record<string, unknown>) => void;
  onFinishFailed?: (errors: Record<string, string>) => void;
  onValuesChange?: (changed: Record<string, unknown>, all: Record<string, unknown>) => void;
  layout?: "vertical" | "horizontal";
  children: ReactNode;
}
```

修改 `handleSubmit`:
```tsx
  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (!schema) {
      onFinish?.(values);
      return;
    }
    const result = schema.safeParse(values);
    if (result.success) {
      setErrors({});
      onFinish?.(result.data);
    } else {
      const fieldErrors: Record<string, string> = {};
      for (const issue of result.error.issues) {
        const path = issue.path.join(".");
        if (!fieldErrors[path]) fieldErrors[path] = issue.message;
      }
      setErrors(fieldErrors);
      // 标记所有字段为 touched
      const allTouched: Record<string, boolean> = {};
      for (const k of fieldsRef.current) allTouched[k] = true;
      setTouched((prev) => ({ ...prev, ...allTouched }));
      onFinishFailed?.(fieldErrors);
    }
  };
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd web && bun run test -- --run components/common/form/form.test.tsx`
Expected: PASS (5/5)

- [ ] **Step 5: Commit**

```bash
git add web/components/common/form/form.tsx web/components/common/form/form.test.tsx
git commit -m "feat(common): Form Zod 验证 (schema + 错误回填 + onFinishFailed)"
```

---

### Task 13: Form 嵌套路径 + 任意插槽组件

**Files:**
- Modify: `web/components/common/form/form.test.tsx`

- [ ] **Step 1: Add nested path + custom component tests**

```tsx
it("嵌套路径 name='user.email' 正确读写", async () => {
  const { userEvent } = await import("@testing-library/user-event");
  const user = userEvent.setup();
  const onFinish = vi.fn();
  render(
    <Form initialValues={{ user: { email: "a@b.com" } }} onFinish={onFinish}>
      <FormItem name="user.email" label="邮箱">
        <Input />
      </FormItem>
      <button type="submit">提交</button>
    </Form>,
  );
  const input = screen.getByLabelText("邮箱") as HTMLInputElement;
  expect(input.value).toBe("a@b.com");
  await user.clear(input);
  await user.type(input, "x@y.com");
  await user.click(screen.getByText("提交"));
  expect(onFinish).toHaveBeenCalledWith({ user: { email: "x@y.com" } });
});

it("任意受控组件 (mock TagPicker) 接收 value + onChange", () => {
  function TagPicker({ value, onChange }: { value: string[]; onChange: (v: string[]) => void }) {
    return (
      <div data-testid="tag-picker">
        <span>{value.join(",")}</span>
        <button onClick={() => onChange([...value, "new"])}>加标签</button>
      </div>
    );
  }
  render(
    <Form initialValues={{ tags: ["a", "b"] }} onFinish={vi.fn()}>
      <FormItem name="tags" label="标签">
        <TagPicker value={[]} onChange={() => {}} />
      </FormItem>
    </Form>,
  );
  expect(screen.getByTestId("tag-picker")).toHaveTextContent("a,b");
});
```

- [ ] **Step 2: Run tests**

Run: `cd web && bun run test -- --run components/common/form/form.test.tsx`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add web/components/common/form/form.test.tsx
git commit -m "test(common): Form 嵌套路径 + 任意插槽组件测试"
```

---

### Task 14: Form layout 切换 (vertical / horizontal)

**Files:**
- Modify: `web/components/common/form/form.test.tsx`

- [ ] **Step 1: Add layout test**

```tsx
it("layout='horizontal' 使用 grid 布局", () => {
  const { container } = render(
    <Form initialValues={{ name: "" }} onFinish={vi.fn()} layout="horizontal">
      <FormItem name="name" label="姓名">
        <Input />
      </FormItem>
    </Form>,
  );
  const form = container.querySelector("form")!;
  expect(form.style.display).toBe("grid");
  expect(form.style.gridTemplateColumns).toBe("140px 1fr");
});
```

- [ ] **Step 2: Run tests**

Run: `cd web && bun run test -- --run components/common/form/form.test.tsx`
Expected: PASS

- [ ] **Step 3: Create stories + Commit**

```tsx
// web/components/common/form/form.stories.tsx
"use client";
import { Form } from "./form";
import { FormItem } from "./form-item";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { z } from "zod";

export function VerticalStory() {
  return (
    <Form initialValues={{ name: "" }} onFinish={(v) => alert(JSON.stringify(v))}>
      <FormItem name="name" label="姓名" required>
        <Input placeholder="请输入" />
      </FormItem>
      <Button type="submit">提交</Button>
    </Form>
  );
}

export function HorizontalStory() {
  return (
    <Form initialValues={{ name: "" }} onFinish={(v) => alert(JSON.stringify(v))} layout="horizontal">
      <FormItem name="name" label="姓名" required>
        <Input placeholder="请输入" />
      </FormItem>
      <Button type="submit">提交</Button>
    </Form>
  );
}

export function WithValidationStory() {
  const schema = z.object({ email: z.string().email("邮箱格式不对") });
  return (
    <Form initialValues={{ email: "" }} schema={schema}
      onFinish={(v) => alert(JSON.stringify(v))}
      onFinishFailed={(e) => alert("验证失败: " + JSON.stringify(e))}>
      <FormItem name="email" label="邮箱" required help="用于登录">
        <Input type="email" placeholder="a@b.com" />
      </FormItem>
      <Button type="submit">提交</Button>
    </Form>
  );
}
```

```bash
git add web/components/common/form/
git commit -m "feat(common): Form layout 切换 (vertical/horizontal) + stories"
```

---

### Task 15: 替换 4 处真表格 + SampleTable → DataTable

**Files:**
- Modify: `web/app/knowledge/nodes/page.tsx`
- Modify: `web/app/knowledge/relations/page.tsx`
- Modify: `web/app/knowledge/documents/import/page.tsx`
- Modify: `web/app/knowledge/triples/page.tsx`
- Modify: `web/components/evaluate/SampleTable.tsx`

- [ ] **Step 1: 替换 nodes/page.tsx**

将 `nodes/page.tsx` 的手写 Table + 分页替换为 `<DataTable>`. 保留 hero / error / Stagger 结构不动.

```diff
- import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "@/components/ui/table";
- import { Pagination, PaginationContent, PaginationItem, PaginationPrevious, PaginationNext } from "@/components/ui/pagination";
+ import { DataTable, type ColumnDef } from "@/components/common/data-table/data-table";
```

定义 columns:
```tsx
const columns: ColumnDef<NodeRow>[] = [
  { key: "business_id", title: "编号", width: 80, render: (r) => <span className="num text-muted-foreground">{r.business_id || r.id}</span> },
  { key: "label", title: "类型", width: 128, render: (r) => <Badge variant="outline" className="font-normal">{r.label}</Badge> },
  { key: "name", title: "名称", width: 192, render: (r) => <span className="num text-base">{r.name || "—"}</span> },
  { key: "props", title: "属性", render: (r) => /* props badge 化 */ },
];
```

替换表格区域:
```diff
- <div className="rounded-lg border border-border/40">
-   <div className="min-h-0 flex-1 overflow-auto">
-     <Table>...</Table>
-   </div>
-   {totalPages > 1 && <Pagination>...</Pagination>}
- </div>
+ <DataTable
+   dataSource={data ?? []}
+   columns={columns}
+   rowKey="id"
+   maxHeight="auto"
+   loading={isLoading}
+   emptyText="暂无节点"
+ />
```

- [ ] **Step 2: 替换 relations/page.tsx**

同 nodes 模式, columns 改为 5 列 (类型/起点/→/终点/属性).

- [ ] **Step 3: 替换 documents/import/page.tsx**

手写 `<table>` → `<DataTable>`, columns: #/问题/答案/错误.

- [ ] **Step 4: 替换 triples/page.tsx**

手写 `<table>` → `<DataTable>`, columns render 内嵌受控 Input/Select (行内编辑).

- [ ] **Step 5: 替换 SampleTable.tsx**

shadcn Table → `<DataTable expandedRowRender={...}>`.

- [ ] **Step 6: Run existing tests**

Run: `cd web && bun run test`
Expected: All existing page tests PASS

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "refactor(web): 4 处真表格 + SampleTable 替换为 DataTable"
```

---

### Task 16: 替换 3 处 grid 假表 → DataTable

**Files:**
- Modify: `web/app/evaluate/page.tsx` + `web/components/evaluate/EvalListRow.tsx`
- Modify: `web/app/output/page.tsx`
- Modify: `web/app/output/[task_id]/page.tsx`

- [ ] **Step 1: 替换 evaluate/page.tsx**

grid 12 列假表 → `<DataTable>`, columns: #/名称/状态/题数/时间/→, onRowClick 跳转.

- [ ] **Step 2: 替换 output/page.tsx**

grid 假表 → `<DataTable>`, columns: ID/状态/进度/操作.

- [ ] **Step 3: 替换 output/[task_id]/page.tsx**

flex 假表 → `<DataTable>`, columns: 文件名/大小/操作.

- [ ] **Step 4: Run existing tests**

Run: `cd web && bun run test`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "refactor(web): 3 处 grid 假表替换为 DataTable"
```

---

### Task 17: 替换 4 处 Dialog + 1 处 AlertDialog

**Files:**
- Modify: `web/app/decode/SeriesDialog.tsx`
- Modify: `web/components/chat/SaveToKnowledgeDialog.tsx`
- Modify: `web/components/knowledge/SchemaBrowser.tsx`
- Modify: `web/app/knowledge/qa/page.tsx`
- Modify: `web/components/chat/ChatShell.tsx`

- [ ] **Step 1: 替换 SeriesDialog.tsx**

shadcn Dialog → `<AppDialog>`.

- [ ] **Step 2: 替换 SaveToKnowledgeDialog.tsx**

shadcn Dialog → `<AppDialog>`, 内部手写 useState → `<Form>`.

- [ ] **Step 3: 替换 SchemaBrowser.tsx**

shadcn Dialog → `<AppDialog>`.

- [ ] **Step 4: 替换 qa/page.tsx 自测弹窗**

shadcn Dialog → `<AppDialog>`.

- [ ] **Step 5: 替换 ChatShell.tsx 删除确认**

shadcn AlertDialog → `<AppConfirm variant="destructive">`.

- [ ] **Step 6: Run existing tests**

Run: `cd web && bun run test`
Expected: All PASS

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "refactor(web): 4 处 Dialog + 1 处 AlertDialog 替换为 AppDialog / AppConfirm"
```

---

### Task 18: 替换 4 处 Form + 9 处手写 button

**Files:**
- Modify: `web/components/chat/SaveToKnowledgeDialog.tsx` — Form
- Modify: `web/app/knowledge/qa/page.tsx` — Form
- Modify: `web/app/evaluate/new/page.tsx` — Form
- Modify: 9 files with motion.button → Button

- [ ] **Step 1: 替换 SaveToKnowledgeDialog Form**

手写 useState → `<Form schema={...}>` + `<FormItem>`.

- [ ] **Step 2: 替换 qa/page.tsx Form**

手写 useState → `<Form>`.

- [ ] **Step 3: 替换 evaluate/new/page.tsx Form**

手写 useState → `<Form>`.

- [ ] **Step 4: 替换 9 处 motion.button**

`motion.button className="rounded-md bg-ink ..."` → `<Button variant="default">` (或 `<Button variant="outline">` 视语义).

涉及文件:
- `app/evaluate/page.tsx`
- `app/output/page.tsx`
- `app/output/new/page.tsx`
- `app/knowledge/batch/page.tsx`
- `app/knowledge/qa/page.tsx`
- `app/knowledge/triples/page.tsx`
- `app/decode/page.tsx`

- [ ] **Step 5: Run existing tests**

Run: `cd web && bun run test`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "refactor(web): 4 处 Form + 9 处 motion.button 替换为 Form/Button"
```

---

### Task 19: 审计报告

**Files:**
- Create: `docs/superpowers/audit-2026-06-10-shadcn-coverage.md`

- [ ] **Step 1: 扫描并生成报告**

内容:
- 哪些文件 100% shadcn / 哪些混用 / 哪些手写
- 未替换候选清单 (HealthDot / StatCard / EntryCard / 等)
- shadcn 缺失组件 + 补装状态
- 后续 spec 候选 (主题/i18n/...)

- [ ] **Step 2: Commit**

```bash
git add docs/superpowers/audit-2026-06-10-shadcn-coverage.md
git commit -m "docs: shadcn 覆盖率审计报告"
```

---

### Task 20: 回归测试 + typecheck + lint

**Files:** None (verification only)

- [ ] **Step 1: Run full vitest**

Run: `cd web && bun run test`
Expected: All tests PASS (除 pre-existing `lib/chat/factory.test.ts`)

- [ ] **Step 2: Run typecheck**

Run: `cd web && bun run typecheck`
Expected: 0 errors

- [ ] **Step 3: Run lint**

Run: `cd web && bun run lint`
Expected: 0 errors (warnings OK)

- [ ] **Step 4: Commit (if any fix needed)**

```bash
git add -A
git commit -m "fix: 回归修复 (typecheck / lint / test)"
```
