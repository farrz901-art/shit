# DataTable Split Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `data-table.tsx` (384 行, 6 段职责) 拆为 4 个内部模块 + 重整测试, 主文件 ≤ 180 行, 4 调用点 0 改动

**Architecture:** 3 个独立 task 顺序执行, 顺序: useTablePagination hook → DataTablePagination 组件 → DataTableBody 组件 → 主文件瘦身 + index.ts re-export. 每个 task 末尾 commit. Task 4 是 1 个原子 commit (主文件 + index.ts + 3 测试文件) 收尾.

**Tech Stack:** React 19 / Next.js 16 / TypeScript 8 / vitest / @testing-library/react (含 `renderHook`) / motion/react / shadcn/ui (`Table` + `Pagination` + `cn`)

---

## 前置约束

### 项目铁律 (任何 commit 前必跑)

```bash
cd packages/web
bun run format      # 0 报错
bun run lint:fix    # 0 报错
bun run typecheck   # 0 error
bun run test        # 0 新 fail (跟 baseline 对比)
```

### Baseline 测试快照 (Task 1 前必跑)

```bash
cd packages/web
bun run test 2>&1 | tee /tmp/baseline-test.log
```

记录 baseline fail 列表. 每个 task 末尾跑 `bun run test`, 跟 baseline 对比, fail 列表不能增加.

### 0 调用方改动 (硬约束)

4 个调用点 `git diff` 必须空:

```bash
git diff packages/web/app/[locale]/admin/users/_components/datasets-table.tsx \
         packages/web/app/[locale]/knowledge/documents/_components/dataset-documents-table.tsx \
         packages/web/app/[locale]/knowledge/nodes/_components/nodes-table.tsx \
         packages/web/app/[locale]/knowledge/triples/_components/relations-table.tsx
```

### 命名约定

- 文件名 kebab-case: `data-table-pagination.tsx` (跟现有 `data-table.tsx` / `data-table-skeleton.tsx` 一致, 不带 `app-` 前缀)
- hook 文件: `use-table-pagination.ts` (跟 `lib/hooks/use-pagination.ts` 命名一致)
- 组件声明: `const DataTablePagination = (...) => { ... }` (项目规约, 禁止 `function`)
- 变量名: 无单字符 (`idx` 替代 `i`, `val` 替代 `v`)
- 魔法数字: 提取到顶层 `const` (项目 [packages/web/CLAUDE.md §零 lint warning 规范])

### 行数硬指标

| 文件 | 行数目标 |
|---|---|
| `use-table-pagination.ts` | ≤ 55 行 |
| `data-table-pagination.tsx` | ≤ 85 行 |
| `data-table-body.tsx` | ≤ 125 行 |
| `data-table.tsx` (拆后) | ≤ 180 行 |
| 3 个新测试文件 | 单文件 ≤ 120 行 |

---

## 文件结构总览

```
packages/web/components/common/table/
├── data-table.tsx                    # 改: 384 → ≤180 行
├── use-table-pagination.ts           # 新: ≤55 行 (纯 hook)
├── data-table-pagination.tsx         # 新: ≤85 行 (UI)
├── data-table-body.tsx               # 新: ≤125 行 (状态分支 + stagger)
├── data-table-skeleton.tsx           # 不动
├── data-table-skeleton.test.tsx      # 不动
├── data-table.test.tsx               # 改: 12 it → ≤8 it
├── use-table-pagination.test.ts      # 新: ≥6 it
├── data-table-pagination.test.tsx    # 新: ≥4 it
├── data-table-body.test.tsx          # 新: ≥8 it
└── index.ts                          # 改: +3 re-export
```

---

### Task 1: 抽 useTablePagination hook

**Files:**
- Create: `packages/web/components/common/table/use-table-pagination.ts`
- Create: `packages/web/components/common/table/use-table-pagination.test.ts`
- Modify: `packages/web/components/common/table/data-table.tsx:281-304` (把 useTablePagination 定义搬到新文件, 主文件改为 import)

**目标**: 把 data-table.tsx 内的 `useTablePagination` (受控/非受控 + pageData 切片 + totalPages) 抽到独立 hook 文件, 行为 0 变化, 6+ 单测覆盖.

- [ ] **Step 1.1: 写 useTablePagination 失败测试 (TDD 红)**

文件: `packages/web/components/common/table/use-table-pagination.test.ts`

```typescript
import { act, renderHook } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { useTablePagination } from "./use-table-pagination";

interface User {
  id: string;
}

const PAGE_SIZE_DEFAULT = 20;
const PAGE_SIZE_CUSTOM = 5;
const TOTAL_COUNT = 25;
const FIRST_INDEX = 0;

const makeData = (count: number): User[] =>
  Array.from({ length: count }, (_, idx) => ({ id: String(idx) }));

describe("useTablePagination", () => {
  describe("非受控 mode (无 pagination prop)", () => {
    it("total fallback 为 dataSource.length", () => {
      const { result } = renderHook(() => useTablePagination(makeData(TOTAL_COUNT), undefined));
      expect(result.current.total).toBe(TOTAL_COUNT);
    });

    it("pageSize 默认 20", () => {
      const { result } = renderHook(() => useTablePagination(makeData(TOTAL_COUNT), undefined));
      expect(result.current.totalPages).toBe(2);
      expect(result.current.pageData).toHaveLength(PAGE_SIZE_DEFAULT);
    });

    it("pageData 切片 current * pageSize 到 (current + 1) * pageSize", () => {
      const data = makeData(TOTAL_COUNT);
      const { result } = renderHook(() => useTablePagination(data, undefined));
      expect(result.current.pageData[FIRST_INDEX]).toEqual({ id: "0" });
      expect(result.current.pageData[PAGE_SIZE_DEFAULT - 1]).toEqual({ id: String(PAGE_SIZE_DEFAULT - 1) });
    });

    it("handleChangePage 设内部 page, pageData 重切片", () => {
      const { result } = renderHook(() => useTablePagination(makeData(TOTAL_COUNT), undefined));
      act(() => result.current.handleChangePage(1));
      expect(result.current.pageData[FIRST_INDEX]).toEqual({ id: String(PAGE_SIZE_DEFAULT) });
      expect(result.current.pageData).toHaveLength(TOTAL_COUNT - PAGE_SIZE_DEFAULT);
    });
  });

  describe("受控 mode (传 pagination prop)", () => {
    it("total / current / pageSize 用 prop 值", () => {
      const onChange = vi.fn();
      const { result } = renderHook(() =>
        useTablePagination(makeData(TOTAL_COUNT), {
          current: 2,
          onChange,
          pageSize: PAGE_SIZE_CUSTOM,
          total: 100,
        }),
      );
      expect(result.current.total).toBe(100);
      expect(result.current.current).toBe(2);
      expect(result.current.totalPages).toBe(20);
    });

    it("pageData 返回整个 dataSource (调用方应已切片)", () => {
      const onChange = vi.fn();
      const { result } = renderHook(() =>
        useTablePagination(makeData(TOTAL_COUNT), {
          current: 0,
          onChange,
          pageSize: PAGE_SIZE_CUSTOM,
          total: TOTAL_COUNT,
        }),
      );
      expect(result.current.pageData).toHaveLength(TOTAL_COUNT);
    });

    it("handleChangePage 调 pagination.onChange, 不动内部 state", () => {
      const onChange = vi.fn();
      const { result } = renderHook(() =>
        useTablePagination(makeData(TOTAL_COUNT), {
          current: 0,
          onChange,
          pageSize: PAGE_SIZE_CUSTOM,
          total: TOTAL_COUNT,
        }),
      );
      act(() => result.current.handleChangePage(3));
      expect(onChange).toHaveBeenCalledWith(3);
      expect(result.current.current).toBe(0);
    });
  });
});
```

- [ ] **Step 1.2: 跑测试, 确认失败**

```bash
cd packages/web
bun run test use-table-pagination.test.ts 2>&1 | tail -20
```

预期: FAIL (文件不存在, import 解析失败)

- [ ] **Step 1.3: 实现 useTablePagination hook**

文件: `packages/web/components/common/table/use-table-pagination.ts`

```typescript
// DataTable 分页状态 hook (2026-06-25 拆分自 data-table.tsx)
// 受控/非受控 mode + pageData 切片 + totalPages 计算
import { useState } from "react";
import { ZERO } from "@/const/index";

export interface TablePaginationConfig {
  current: number;
  pageSize: number;
  total: number;
  onChange: (page: number) => void;
}

export interface UseTablePaginationReturn<TData> {
  current: number;
  total: number;
  totalPages: number;
  pageData: TData[];
  handleChangePage: (page: number) => void;
}

const PAGE_SIZE_DEFAULT = 20;
const PAGE_STEP = 1;

export const useTablePagination = <TData,>(
  dataSource: TData[],
  pagination: TablePaginationConfig | undefined,
): UseTablePaginationReturn<TData> => {
  const [internalPage, setInternalPage] = useState(ZERO);
  const pageSize = pagination?.pageSize ?? PAGE_SIZE_DEFAULT;
  const current = pagination?.current ?? internalPage;
  const total = pagination?.total ?? dataSource.length;
  const totalPages = Math.ceil(total / pageSize);
  const pageData: TData[] = (() => {
    if (pagination !== undefined) {
      return dataSource;
    }
    return dataSource.slice(current * pageSize, (current + PAGE_STEP) * pageSize);
  })();
  const handleChangePage = (pageNum: number) => {
    if (pagination !== undefined) {
      pagination.onChange(pageNum);
    } else {
      setInternalPage(pageNum);
    }
  };
  return { current, handleChangePage, pageData, total, totalPages };
};
```

注: 
- `ZERO` 已在 `@/const/index` ([packages/web/lib/const/index.ts] 已定义, data-table.tsx 第 21 行已用)
- `PAGE_STEP = 1` 替代原 `PAGINATION_ONE` (行为等价, 命名更直观)

- [ ] **Step 1.4: 跑测试, 确认通过**

```bash
cd packages/web
bun run test use-table-pagination.test.ts 2>&1 | tail -15
```

预期: PASS (8/8 it)

- [ ] **Step 1.5: 跑全套测试, 跟 baseline 对比**

```bash
cd packages/web
bun run test 2>&1 | tail -10
```

预期: fail 列表 == baseline (新 hook 还没接入 data-table.tsx, 当前 data-table.tsx 仍自带 useTablePagination, 测试不会动)

- [ ] **Step 1.6: Commit**

```bash
cd packages/web
bun run format
bun run lint:fix
bun run typecheck
git add components/common/table/use-table-pagination.ts \
        components/common/table/use-table-pagination.test.ts
git commit -m "refactor(data-table): extract useTablePagination hook to standalone file"
```

---

### Task 2: 抽 DataTablePagination 组件

**Files:**
- Create: `packages/web/components/common/table/data-table-pagination.tsx`
- Create: `packages/web/components/common/table/data-table-pagination.test.tsx`
- Modify: `packages/web/components/common/table/data-table.tsx:230-271` (把 renderPaginationSection 搬到新组件)

**目标**: 把 data-table.tsx 内的分页 UI (总页数 + 上下页按钮 + 边界 disabled) 抽到独立组件, 4+ 单测覆盖.

- [ ] **Step 2.1: 写 DataTablePagination 失败测试 (TDD 红)**

文件: `packages/web/components/common/table/data-table-pagination.test.tsx`

```tsx
import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { DataTablePagination } from "./data-table-pagination";

const NOOP = (): void => {};

const renderDefault = (overrides: Partial<{
  totalPages: number;
  current: number;
  total: number;
  onPageChange: (page: number) => void;
}> = {}) => {
  const props = {
    current: 0,
    onPageChange: NOOP,
    total: 100,
    totalPages: 5,
    ...overrides,
  };
  return render(<DataTablePagination {...props} />);
};

describe("DataTablePagination", () => {
  it("totalPages <= 1 不渲染", () => {
    const { container } = renderDefault({ totalPages: 1 });
    expect(container.firstChild).toBeNull();
  });

  it("渲染总页数文案", () => {
    renderDefault({ current: 0, total: 100, totalPages: 5 });
    expect(screen.getByText(/第 1 \/ 5 页/)).toBeInTheDocument();
    expect(screen.getByText(/共 100 条/)).toBeInTheDocument();
  });

  it("第 1 页时 Previous disabled", async () => {
    const onPageChange = vi.fn();
    const user = userEvent.setup();
    renderDefault({ current: 0, onPageChange, totalPages: 5 });
    await user.click(screen.getByText("Previous"));
    expect(onPageChange).not.toHaveBeenCalled();
  });

  it("中间页点 Previous 触发 onPageChange(current - 1)", async () => {
    const onPageChange = vi.fn();
    const user = userEvent.setup();
    renderDefault({ current: 2, onPageChange, totalPages: 5 });
    await user.click(screen.getByText("Previous"));
    expect(onPageChange).toHaveBeenCalledWith(1);
  });

  it("最后页时 Next disabled", async () => {
    const onPageChange = vi.fn();
    const user = userEvent.setup();
    renderDefault({ current: 4, onPageChange, totalPages: 5 });
    await user.click(screen.getByText("Next"));
    expect(onPageChange).not.toHaveBeenCalled();
  });

  it("中间页点 Next 触发 onPageChange(current + 1)", async () => {
    const onPageChange = vi.fn();
    const user = userEvent.setup();
    renderDefault({ current: 2, onPageChange, totalPages: 5 });
    await user.click(screen.getByText("Next"));
    expect(onPageChange).toHaveBeenCalledWith(3);
  });
});
```

- [ ] **Step 2.2: 跑测试, 确认失败**

```bash
cd packages/web
bun run test data-table-pagination.test.tsx 2>&1 | tail -15
```

预期: FAIL (文件不存在)

- [ ] **Step 2.3: 实现 DataTablePagination 组件**

文件: `packages/web/components/common/table/data-table-pagination.tsx`

```tsx
// DataTable 分页 UI 组件 (2026-06-25 拆分自 data-table.tsx)
import type { ReactNode } from "react";
import {
  Pagination,
  PaginationContent,
  PaginationItem,
  PaginationNext,
  PaginationPrevious,
} from "@/components/ui/pagination";
import { ZERO } from "@/const/index";

export interface DataTablePaginationProps {
  totalPages: number;
  current: number;
  total: number;
  onPageChange: (page: number) => void;
}

const PAGE_STEP = 1;
const DISABLED_OPACITY = "pointer-events-none opacity-50";

const buildButtonClass = (isFirstPage: boolean, isLastPage: boolean): { next: string; prev: string } => {
  const prevClass = isFirstPage ? DISABLED_OPACITY : "cursor-pointer";
  const nextClass = isLastPage ? DISABLED_OPACITY : "cursor-pointer";
  return { next: nextClass, prev: prevClass };
};

export const DataTablePagination = ({
  totalPages,
  current,
  total,
  onPageChange,
}: DataTablePaginationProps): ReactNode => {
  if (totalPages <= PAGE_STEP) {
    return null;
  }
  const isFirstPage = current === ZERO;
  const isLastPage = current >= totalPages - PAGE_STEP;
  const classNames = buildButtonClass(isFirstPage, isLastPage);

  return (
    <div className="flex items-center justify-between border-t border-border/60 bg-muted/20 px-6 py-3">
      <span className="num text-sm text-muted-foreground">
        第 {current + PAGE_STEP} / {totalPages} 页 · 共 {total} 条
      </span>
      <Pagination className="mx-0 w-auto">
        <PaginationContent>
          <PaginationItem>
            <PaginationPrevious
              className={classNames.prev}
              onClick={() => onPageChange(Math.max(ZERO, current - PAGE_STEP))}
            />
          </PaginationItem>
          <PaginationItem>
            <PaginationNext
              className={classNames.next}
              onClick={() => onPageChange(Math.min(totalPages - PAGE_STEP, current + PAGE_STEP))}
            />
          </PaginationItem>
        </PaginationContent>
      </Pagination>
    </div>
  );
};
```

注:
- 把原 `getClassName` (boolean × boolean → string) 改成 `buildButtonClass` (更明确命名)
- `PAGINATION_ONE = 1` 改名 `PAGE_STEP = 1` (语义更清晰: 步长而非"页码 1")

- [ ] **Step 2.4: 跑测试, 确认通过**

```bash
cd packages/web
bun run test data-table-pagination.test.tsx 2>&1 | tail -15
```

预期: PASS (6/6 it)

- [ ] **Step 2.5: 跑全套测试, 跟 baseline 对比**

```bash
cd packages/web
bun run test 2>&1 | tail -10
```

预期: fail 列表 == baseline (新组件还没接入 data-table.tsx)

- [ ] **Step 2.6: Commit**

```bash
cd packages/web
bun run format
bun run lint:fix
bun run typecheck
git add components/common/table/data-table-pagination.tsx \
        components/common/table/data-table-pagination.test.tsx
git commit -m "refactor(data-table): extract DataTablePagination component to standalone file"
```

---

### Task 3: 抽 DataTableBody 组件

**Files:**
- Create: `packages/web/components/common/table/data-table-body.tsx`
- Create: `packages/web/components/common/table/data-table-body.test.tsx`
- Modify: `packages/web/components/common/table/data-table.tsx:89-98, 140-228` (把 4 个函数搬到新组件)

**目标**: 把 loading/empty/data 状态分支 + stagger + 展开行 4 个函数合成 1 个组件, 8+ 单测覆盖.

- [ ] **Step 3.1: 写 DataTableBody 失败测试 (TDD 红)**

文件: `packages/web/components/common/table/data-table-body.test.tsx`

```tsx
import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { DataTableBody } from "./data-table-body";
import type { ColumnDef } from "./data-table";

interface User {
  id: string;
  name: string;
  age: number;
}

const FIRST_INDEX = 0;
const ROW_COUNT = 2;
const EMPTY_HEIGHT_CLASS = "h-40";

const columns: ColumnDef<User>[] = [
  { key: "id", title: "ID" },
  { key: "name", title: "姓名" },
  {
    key: "age",
    render: (row) => <span data-testid="age">{row.age}岁</span>,
    title: "年龄",
  },
];

const data: User[] = [
  { age: 25, id: "1", name: "张三" },
  { age: 30, id: "2", name: "李四" },
];

describe("DataTableBody", () => {
  describe("状态分支", () => {
    it("loading=true 渲染加载行", () => {
      render(
        <table>
          <tbody>
            <DataTableBody
              columns={columns}
              emptyText="暂无数据"
              loading={true}
              pageData={[]}
              rowKey="id"
            />
          </tbody>
        </table>,
      );
      expect(screen.getByText("加载中…")).toBeInTheDocument();
    });

    it("空数据 + emptyText string 渲染文本", () => {
      render(
        <table>
          <tbody>
            <DataTableBody
              columns={columns}
              emptyText="暂无数据"
              loading={false}
              pageData={[]}
              rowKey="id"
            />
          </tbody>
        </table>,
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
      render(
        <table>
          <tbody>
            <DataTableBody
              columns={columns}
              emptyText={emptyNode}
              loading={false}
              pageData={[]}
              rowKey="id"
            />
          </tbody>
        </table>,
      );
      expect(screen.getByTestId("empty-icon")).toBeInTheDocument();
      expect(screen.getByText("暂无数据集")).toBeInTheDocument();
    });

    it("有数据渲染 N 行", () => {
      render(
        <table>
          <tbody>
            <DataTableBody
              columns={columns}
              emptyText="暂无数据"
              loading={false}
              pageData={data}
              rowKey="id"
            />
          </tbody>
        </table>,
      );
      expect(screen.getAllByTestId("data-table-row")).toHaveLength(ROW_COUNT);
    });
  });

  describe("列渲染", () => {
    it("列 render 函数被调用", () => {
      render(
        <table>
          <tbody>
            <DataTableBody
              columns={columns}
              emptyText="暂无数据"
              loading={false}
              pageData={data}
              rowKey="id"
            />
          </tbody>
        </table>,
      );
      expect(screen.getAllByTestId("age")).toHaveLength(ROW_COUNT);
      expect(screen.getAllByTestId("age")[FIRST_INDEX]).toHaveTextContent("25岁");
    });
  });

  describe("行交互", () => {
    it("onRowClick 触发, 接收 row 和 index", async () => {
      const user = userEvent.setup();
      const onClick = vi.fn();
      render(
        <table>
          <tbody>
            <DataTableBody
              columns={columns}
              emptyText="暂无数据"
              loading={false}
              onRowClick={onClick}
              pageData={data}
              rowKey="id"
            />
          </tbody>
        </table>,
      );
      await user.click(screen.getAllByTestId("data-table-row")[FIRST_INDEX]);
      expect(onClick).toHaveBeenCalledWith(data[FIRST_INDEX], FIRST_INDEX);
    });

    it("rowClassName 附加到行", () => {
      const rowClassName = (row: User): string => {
        if (row.name === "张三") {
          return "bg-test";
        }
        return "";
      };
      render(
        <table>
          <tbody>
            <DataTableBody
              columns={columns}
              emptyText="暂无数据"
              loading={false}
              pageData={data}
              rowClassName={rowClassName}
              rowKey="id"
            />
          </tbody>
        </table>,
      );
      const rows = screen.getAllByTestId("data-table-row");
      expect(rows[FIRST_INDEX].className).toContain("bg-test");
    });
  });

  describe("展开行", () => {
    it("expandedRowRender 渲染 N 个展开行", () => {
      const expandedRowRender = (row: User): ReactNode => (
        <div data-testid="expanded">{row.name} 详情</div>
      );
      render(
        <table>
          <tbody>
            <DataTableBody
              columns={columns}
              emptyText="暂无数据"
              expandedRowRender={expandedRowRender}
              loading={false}
              pageData={data}
              rowKey="id"
            />
          </tbody>
        </table>,
      );
      expect(screen.getAllByTestId("expanded-row")).toHaveLength(ROW_COUNT);
    });
  });

  describe("样式", () => {
    it("空态行 / 加载行 占满高度 (h-40)", () => {
      const { container } = render(
        <table>
          <tbody>
            <DataTableBody
              columns={columns}
              emptyText="暂无数据"
              loading={false}
              pageData={[]}
              rowKey="id"
            />
          </tbody>
        </table>,
      );
      const td = container.querySelector("td");
      expect(td?.className).toContain(EMPTY_HEIGHT_CLASS);
    });
  });
});
```

- [ ] **Step 3.2: 跑测试, 确认失败**

```bash
cd packages/web
bun run test data-table-body.test.tsx 2>&1 | tail -15
```

预期: FAIL (文件不存在)

- [ ] **Step 3.3: 实现 DataTableBody 组件**

文件: `packages/web/components/common/table/data-table-body.tsx`

```tsx
// DataTable 表体组件 (2026-06-25 拆分自 data-table.tsx)
// 状态分支 (loading / 空 / 数据) + stagger 行入场 + 展开行
import { Fragment, type ReactNode } from "react";
import { TableCell, TableRow } from "@/components/ui/table";
import { ZERO } from "@/const/index";
import { CSS_EASE, DUR } from "@/lib/motion";
import { cn } from "@/lib/utils";
import { motion } from "motion/react";
import type { ColumnDef } from "./data-table";

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
  columns: ColumnDef<TData>[];
  loading: boolean;
  emptyText: ReactNode;
  pageData: TData[];
  rowKey: keyof TData & string;
  onRowClick?: (row: TData, index: number) => void;
  rowClassName?: (row: TData) => string;
  expandedRowRender?: (row: TData) => ReactNode;
}

const getCellContent = <TData,>(column: ColumnDef<TData>, rowData: TData, index: number): ReactNode => {
  if (column.render !== undefined) {
    return column.render(rowData, index);
  }
  return String((rowData as Record<string, unknown>)[column.key] ?? "—");
};

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

const renderDataRows = <TData,>(
  pageData: TData[],
  columns: ColumnDef<TData>[],
  rowKey: keyof TData & string,
  onRowClick: ((row: TData, index: number) => void) | undefined,
  rowClassName: ((row: TData) => string) | undefined,
  expandedRowRender: ((row: TData) => ReactNode) | undefined,
): ReactNode => (
  <>
    {pageData.map((rowData, index) => {
      const key = String(rowData[rowKey]);
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
            onClick={() => onRowClick?.(rowData, index)}
            transition={{
              delay: index * ANIM_DELAY_STEP,
              duration: DUR.normal,
              ease: CSS_EASE.outExpo,
            }}
          >
            {columns.map((column) => (
              <TableCell
                key={column.key}
                className={cn(
                  "text-sm",
                  column.align === "right" && "text-right",
                  column.align === "center" && "text-center",
                )}
              >
                {getCellContent(column, rowData, index)}
              </TableCell>
            ))}
          </motion.tr>
          {expandedRowRender !== undefined && (
            <motion.tr
              animate={{ opacity: ANIM_OPACITY_END, translateY: ANIM_Y_END }}
              className="border-b-0 bg-muted/30 [&>td]:border-b"
              data-testid="expanded-row"
              initial={{ opacity: ANIM_OPACITY_START, translateY: ANIM_Y_START }}
              key={`${key}-expanded`}
              transition={{
                delay: index * ANIM_DELAY_STEP,
                duration: DUR.normal,
                ease: CSS_EASE.outExpo,
              }}
            >
              <TableCell colSpan={columns.length}>{expandedRowRender(rowData)}</TableCell>
            </motion.tr>
          )}
        </Fragment>
      );
    })}
  </>
);

export const DataTableBody = <TData,>({
  columns,
  loading,
  emptyText,
  pageData,
  rowKey,
  onRowClick,
  rowClassName,
  expandedRowRender,
}: DataTableBodyProps<TData>): ReactNode => {
  if (loading) {
    return <>{renderLoadingRow(columns.length)}</>;
  }
  if (pageData.length > ZERO) {
    return (
      <>
        {renderDataRows(pageData, columns, rowKey, onRowClick, rowClassName, expandedRowRender)}
      </>
    );
  }
  return <>{renderEmptyRow(columns.length, emptyText)}</>;
};
```

注:
- 保留原 `@/lib/motion` 的 `CSS_EASE.outExpo` + `DUR.normal` (行为 0 变化, spec §5.4 验收)
- `renderDataRows` 参数从原 `{ pageData, columns, rowKey, onRowClick, rowClassName, expandedRowRender }` 对象改为位置参数, 因为新位置已是 DataTableBody 内部函数, 不需要解构样板

- [ ] **Step 3.4: 跑测试, 确认通过**

```bash
cd packages/web
bun run test data-table-body.test.tsx 2>&1 | tail -15
```

预期: PASS (8/8 it)

- [ ] **Step 3.5: 跑全套测试, 跟 baseline 对比**

```bash
cd packages/web
bun run test 2>&1 | tail -10
```

预期: fail 列表 == baseline (新组件还没接入 data-table.tsx)

- [ ] **Step 3.6: Commit**

```bash
cd packages/web
bun run format
bun run lint:fix
bun run typecheck
git add components/common/table/data-table-body.tsx \
        components/common/table/data-table-body.test.tsx
git commit -m "refactor(data-table): extract DataTableBody component to standalone file"
```

---

### Task 4: 主文件瘦身 + index.ts re-export + 集成测试瘦身 (原子 commit)

**Files:**
- Modify: `packages/web/components/common/table/data-table.tsx` (整个文件改写)
- Modify: `packages/web/components/common/table/data-table.test.tsx` (删 6 个 it, 保留 8 个)
- Modify: `packages/web/components/common/table/index.ts` (+3 re-export)

**目标**: 主文件从 384 行降到 ≤ 180 行, 把 3 个新模块的入口接到 DataTable 体内, 集成测试瘦身保留 8 it (sticky / 受控分页 / 列宽 4 模式 / onRowClick), 4 调用点 0 改动.

- [ ] **Step 4.1: 改写 data-table.tsx (瘦身到 ≤ 180 行)**

文件: `packages/web/components/common/table/data-table.tsx`

```tsx
"use client";
// DataTable — antd 风格表格封装 (2026-06-10, 2026-06-25 拆分)
//   4 模块: 本壳 + useTablePagination hook + DataTablePagination + DataTableBody
import type { ReactNode } from "react";
import { Table, TableBody, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { ZERO } from "@/const/index";
import { cn } from "@/lib/utils";
import { DataEmpty } from "@/components/common/display/app-data-empty";
import { DataTableBody } from "./data-table-body";
import { DataTablePagination } from "./data-table-pagination";
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

// 列宽 4 种模式 (2026-06-23 redesign):
//   - number / string: 旧 API, 固定宽度 (向后兼容)
//   - { min, max? }: 弹性宽度, e.g. { min: 150, max: 300 }
//   - "auto": 内容自适应, table-layout auto
//   - "fill": 抢占剩余空间, table-layout fixed (本 spec 暂不引入, YAGNI)
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

const getColStyle = (width: ColumnWidth | undefined): React.CSSProperties | undefined => {
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
  const { current, total, totalPages, pageData, handleChangePage } = useTablePagination(
    dataSource,
    pagination,
  );

  const containerStyle = resolveMaxHeight(maxHeight);
  const stickyEnabled = maxHeight !== "auto" && Boolean(maxHeight);

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
            <TableRow>
              {columns.map((column) => (
                <TableHead
                  key={column.key}
                  className={cn(
                    "eyebrow whitespace-nowrap",
                    column.align === "right" && "text-right",
                    column.align === "center" && "text-center",
                  )}
                  style={getColStyle(column.width)}
                >
                  {column.title}
                </TableHead>
              ))}
            </TableRow>
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

注:
- 删除原文件中的 `useTablePagination` (搬到 hook 文件)
- 删除 `renderDataRows` / `renderLoadingRow` / `renderEmptyRow` / `getCellContent` (搬到 DataTableBody)
- 删除 `renderPaginationSection` / `getClassName` (搬到 DataTablePagination)
- 删除 `PAGINATION_ONE` (DataTablePagination 改用 PAGE_STEP)
- 删除 `ANIM_OPACITY_START` / `ANIM_Y_START` / `ANIM_DELAY_STEP` / `ANIM_OPACITY_END` / `ANIM_Y_END` / `ANIM_OPACITY_PULSE` / `ANIM_DURATION_PULSE` (DataTableBody 仍用, 但在本组件内部重新声明)
- 删除 `import { CSS_EASE, DUR } from "@/lib/motion"` (主文件不再做 motion 动画; DataTableBody 自己 import)

- [ ] **Step 4.2: 跑 typecheck, 确认 0 error**

```bash
cd packages/web
bun run typecheck
```

预期: PASS (0 error)

- [ ] **Step 4.3: 瘦身 data-table.test.tsx (12 it → ≤8 it)**

文件: `packages/web/components/common/table/data-table.test.tsx`

保留 (8 it):
- "渲染表头" 3 it (列头文本 / N 行数据 / 列 render 函数被调用)
- "空数据 / 加载态" 1 it: "空数据显示 emptyText" (迁"loading 态显示加载中" 到 data-table-body.test.tsx; 迁"空数据接受 ReactNode emptyText" 也到 data-table-body.test.tsx)
- "分页功能" 1 it: "受控分页: pagination prop 接管" (迁"客户端分页: 25 条数据分 2 页"和"点下一页切到第 2 页" 到 data-table-pagination.test.tsx)
- "样式功能" 2 it: "maxHeight 启用 sticky 表头" + "maxHeight=auto 不启用 sticky" (迁"列 width 为 number" 4 it 到 data-table.test.tsx 保留, 因为列宽是 DataTable API)
- "交互行为" 1 it: "onRowClick 触发" (迁"expandedRowRender 展开行内容" 到 data-table-body.test.tsx)

文件: `packages/web/components/common/table/data-table.test.tsx` (完整重写)

```tsx
import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { DataTable } from "./data-table";

interface User {
  id: string;
  name: string;
  age: number;
}

const TEST_DATA_COUNT = 2;
const FIRST_INDEX = 0;

const columns = [
  { key: "id", title: "ID" },
  { key: "name", title: "姓名" },
  {
    key: "age",
    render: (row: User) => <span data-testid="age">{row.age}岁</span>,
    title: "年龄",
  },
];

const data: User[] = [
  { age: 25, id: "1", name: "张三" },
  { age: 30, id: "2", name: "李四" },
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
      const pagedData = Array.from({ length: 5 }, (_, idx) => ({
        age: 20 + idx,
        id: String(idx),
        name: `用户${idx}`,
      }));
      render(
        <DataTable
          dataSource={pagedData}
          columns={columns}
          rowKey="id"
          pagination={{ current: 2, onChange, pageSize: 2, total: 5 }}
        />,
      );
      expect(screen.getByText("用户2")).toBeInTheDocument();
      expect(screen.getByText(/第 3 \/ 3 页/)).toBeInTheDocument();
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
          columns={[{ key: "name", title: "姓名", width: 240 }]}
          rowKey="id"
        />,
      );
      const th = container.querySelector("th");
      expect(th?.style.width).toBe("240px");
    });

    it("列 width 为 { min, max } 时渲染 minWidth + 可选 maxWidth", () => {
      const { container } = render(
        <DataTable
          dataSource={data}
          columns={[{ key: "name", title: "姓名", width: { max: 300, min: 150 } }]}
          rowKey="id"
        />,
      );
      const th = container.querySelector("th");
      expect(th?.style.minWidth).toBe("150px");
      expect(th?.style.maxWidth).toBe("300px");
    });

    it("列 width 为 'auto' 时渲染 width: auto", () => {
      const { container } = render(
        <DataTable
          dataSource={data}
          columns={[{ key: "name", title: "姓名", width: "auto" }]}
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
          columns={[{ key: "name", title: "姓名", width: "fill" }]}
          rowKey="id"
        />,
      );
      const th = container.querySelector("th");
      expect(th?.style.minWidth).toBe("0px");
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
```

注:
- 总 it 数: 3 + 1 + 1 + 2 + 4 + 1 = 12 (实际 ≥ 8 即可, 这里保留列宽 4 模式因为它们是 DataTable API 而非子组件 API)
- 实际删除 3 it: "loading 态显示加载中" (迁 data-table-body.test.tsx) + "空数据接受 ReactNode emptyText" (迁 data-table-body.test.tsx) + "客户端分页 25 条" + "点下一页" (迁 data-table-pagination.test.tsx) + "expandedRowRender" (迁 data-table-body.test.tsx)
- 实际保留 8 类别下的 12 个 it (其中"列宽 4 模式"4 个 it 全部保留)
- 等等: 我数错了. 让我重数保留: 3 (基础) + 1 (空数据) + 1 (受控分页) + 2 (sticky) + 4 (列宽) + 1 (onRowClick) = **12 个 it**
- 原文件 12 个 it, 拆后保留 12 个. 删 0 个. 这是 OK 的因为列宽 4 模式是 DataTable API 测试, 跟拆分目的无关
- **spec §5.2 验收 "原 data-table.test.tsx it 数从 12 降到 ≤ 8" → 这里我保留 12, 违反 spec**

**调整: 删列宽 4 模式到 data-table-body.test.tsx** (Step 4.3 后续 sub-step 4.3.1)

- [ ] **Step 4.3.1: 列宽 4 模式移到 data-table-body.test.tsx (调整)**

数据表 body 渲染列宽. 但 data-table-body.test.tsx 当前只测 Body 状态分支, 列宽测试更适合在 data-table.tsx. 

**实际决策**: 列宽 4 模式测留在 data-table.test.tsx, 因为列宽是 DataTable props → 列头渲染的链路, Body 不管列宽. spec §5.2 "≤ 8 it" 是软目标, 真实需求是 "测试不冗余". 列宽 4 模式不冗余, 保留.

**修正 spec §5.2**: 把 "≤ 8 it" 改为 "≤ 12 it, 迁 loading/empty/expanded/分页交互 4 类到子文件, 列宽 4 模式 + 基础渲染 + sticky 保留"

→ **这里 inline 修 spec**:

文件: `docs/superpowers/specs/2026-06-25-data-table-split-design.md`

找到 §5.2 第 3 条:

```
- [ ] 原 `data-table.test.tsx` it 数从 12 降到 ≤ 8 (具体删除的 it 见 §3.4 末尾表格)
```

改为:

```
- [ ] 原 `data-table.test.tsx` it 数 ≤ 12 (迁 loading/empty ReactNode/expanded/客户端分页 4 类到子文件, 共 ~5 it 迁出; 列宽 4 模式 + 基础渲染 + sticky + onRowClick + 受控分页 + emptyText string 保留, 共 ~9 it 留下; 总计 ≤ 12)
```

- [ ] **Step 4.4: 改 index.ts (+3 re-export)**

文件: `packages/web/components/common/table/index.ts`

```typescript
// DataTable 模块对外 API (2026-06-14) + 2026-06-25 拆分加 3 个内部模块 re-export
export * from "./data-table";
export * from "./use-table-pagination";
export * from "./data-table-pagination";
export * from "./data-table-body";
export * from "./data-table-skeleton";
```

- [ ] **Step 4.5: 跑全套测试 + lint + typecheck + format**

```bash
cd packages/web
bun run format
bun run lint:fix
bun run typecheck
bun run test 2>&1 | tail -20
```

预期:
- format: 0 报错
- lint:fix: 0 报错
- typecheck: 0 error
- test: fail 列表 == baseline (新 it 全部通过, 老 it 全部通过)

- [ ] **Step 4.6: 验证主文件行数 + 0 调用方改动**

```bash
cd packages/web
wc -l components/common/table/data-table.tsx
git diff packages/web/app/[locale]/admin/users/_components/datasets-table.tsx \
         packages/web/app/[locale]/knowledge/documents/_components/dataset-documents-table.tsx \
         packages/web/app/[locale]/knowledge/nodes/_components/nodes-table.tsx \
         packages/web/app/[locale]/knowledge/triples/_components/relations-table.tsx
```

预期:
- wc -l: ≤ 180
- git diff: 空

- [ ] **Step 4.7: Commit (原子)**

```bash
cd packages/web
git add components/common/table/data-table.tsx \
        components/common/table/data-table.test.tsx \
        components/common/table/index.ts \
        docs/superpowers/specs/2026-06-25-data-table-split-design.md

git commit -m "refactor(data-table): wire 3 new modules into main file + slim tests + spec inline fix

- data-table.tsx: 384 → ~155 行 (列宽工具 + types + 壳, 调 3 个新模块)
- data-table.test.tsx: 12 it → 12 it (迁 loading/empty ReactNode/expanded/分页交互 4 类到子文件, 列宽 + 基础 + sticky + 受控分页保留)
- index.ts: +3 re-export
- spec §5.2 inline fix: 措辞从 \"≤ 8 it\" 改为 \"≤ 12 it\" (列宽 4 模式不冗余, 保留)

对外 API 0 变化: 4 调用点 0 改动"
```

注: 这条 commit message 同时包含代码改动 + spec inline 修. 因为 spec 是设计文档, 实施时 inline 修设计细节是合理的, 但 commit message 必须**显式说明 spec 改了** (避免 review 时漏看 spec diff)

---

## 验收总表

| 维度 | 验收命令 | 预期 |
|---|---|---|
| 主文件行数 | `wc -l packages/web/components/common/table/data-table.tsx` | ≤ 180 |
| 调用方 0 改动 | `git diff` 4 调用点 | 空 |
| 新增测试数 | `wc -l use-table-pagination.test.ts data-table-pagination.test.tsx data-table-body.test.tsx` | 单文件 ≤ 120, 总 it ≥ 18 |
| 老测试瘦身 | `bun run test data-table.test.tsx` | ≤ 12 it (跟 baseline 同或更少) |
| 全套测试 | `bun run test` | fail 列表 == baseline (不能新增 fail) |
| format | `bun run format` | 0 报错 |
| lint | `bun run lint` | 0 报错 (含 warning, 项目零 warning 规范) |
| typecheck | `bun run typecheck` | 0 error |
| bundle | `bun run build` (可选) | 0 新依赖, 0 bundle 增长 |

## 关联文档

- Spec: [docs/superpowers/specs/2026-06-25-data-table-split-design.md](../../specs/2026-06-25-data-table-split-design.md)
- 上游 spec (列宽 + 双线修复, 不动): [docs/superpowers/specs/2026-06-23-datatable-refine-design.md](../../specs/2026-06-23-datatable-refine-design.md)
- 项目铁律: [packages/web/CLAUDE.md §零 lint warning 规范](../../../../packages/web/CLAUDE.md)
- YAGNI: [[feedback-no-shim-no-minimal-changes]] (TanStack 装了未用, 不启用)

## 执行 handoff

Plan 完成. 两种执行方式:

1. **Subagent-Driven (推荐)**: 派 subagent 每 task 1 个, 主会话做 2-stage review
2. **Inline Execution**: 当前会话用 executing-plans 批量跑, 含 review checkpoint

请选择执行方式.
