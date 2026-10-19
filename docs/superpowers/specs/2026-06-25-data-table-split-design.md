# DataTable 公共组件拆分 (2026-06-25)

> 起源: data-table.tsx 单文件 384 行, 含 6 段职责, 难读 + 难测 + 难复用
> 范围: 1 个公共组件拆 4 个内部模块 + 重整测试, **调用方 0 改动**
> 不依赖: 上游 [2026-06-23-datatable-refine-design.md](./2026-06-23-datatable-refine-design.md) (列宽 4 模式 + 双线修复, 已落 master)

## 1. 目标

| 目标 | 现状 | 验收 |
|---|---|---|
| 主文件瘦身 | data-table.tsx 384 行 | 拆后 ≤ 180 行 (含列宽工具 + types + 壳) |
| 分页逻辑独立测 | `useTablePagination` 在主文件内, 0 独立测试 | 新增 `use-table-pagination.test.ts`, 走 `renderHook` 纯函数测 (受控/非受控/pageData 切片/totalPages 计算) |
| 分页 UI 独立测 | `renderPaginationSection` 在主文件内, 混在 DataTable 测试里 | 新增 `data-table-pagination.test.tsx`, 测 totalPages ≤ 1 不渲染 + 边界页 disabled + onChange 触发 |
| 表体状态独立测 | loading/empty/data + stagger + expanded 4 函数混主文件 | 新增 `data-table-body.test.tsx`, 测 3 状态分支 + 列 render + stagger 触达 + expanded |
| DataTable 集成测试瘦身 | data-table.test.tsx 12 it 杂糅 | 保留 6 it (基础渲染 + sticky + 受控/非受控 + emptyText + onRowClick), 其余迁新文件 |
| 对外 API 不变 | DataTable / ColumnDef / ColumnWidth 4 模式 | 4 调用点 (DatasetsTable / DatasetDocumentsTable / NodesTable / RelationsTable) 0 改动 |
| 顺序约束 | 走项目铁律 format→lint→typecheck→test→commit | 1 个原子 commit `refactor:`, 0 中间状态 break 调用方 |

## 2. 非目标 (YAGNI)

- ❌ 引入 `@tanstack/react-table` — `@tanstack/react-table@8.21.3` 装了 1 年 0 业务使用, 装好备用而已; 当前自管分页 / 列宽 / 行渲染已是完整轻量实现, 换底层会同时拆 + 换引擎, 风险叠加 ([feedback-no-shim-no-minimal-changes])
- ❌ 改 `ColumnDef<T>` / `DataTableProps<T>` API — 4 调用点 + 12 测试断言全依赖现有 shape
- ❌ 加 sort / filter / column resize / jump-to-page / 列拖拽 — 跟现有需求无关, 留后续
- ❌ 改 sticky / stagger / 列宽 4 模式 / 分页栏样式行为 — 纯结构性拆分, 行为 0 变化
- ❌ 改 `DataTableSkeleton` — 独立组件, 行为正确, 不动
- ❌ 改 shadcn `Table` 原语 (`components/ui/table.tsx`) — 跨页影响
- ❌ 把 const 常量挪到 `const/index.ts` — 已命名, 不重复 ([CLAUDE.md §零 lint warning 规范] 已落地)
- ❌ 拆列宽工具到独立文件 — 列宽是 DataTable API 一部分, 跟分页/行/状态是不同抽象层, 不该跟它们平级拆

## 3. 设计

### 3.1 新文件结构

```
packages/web/components/common/table/
  ├── data-table.tsx                    # ~150 行: 列宽工具 + types + DataTable 壳
  ├── use-table-pagination.ts           # ~50 行: 纯 hook (无 JSX)
  ├── data-table-pagination.tsx         # ~80 行: <DataTablePagination /> UI
  ├── data-table-body.tsx               # ~120 行: <DataTableBody<T> /> 状态分支
  ├── data-table-skeleton.tsx           # 不动
  ├── data-table-skeleton.test.tsx      # 不动
  ├── data-table.test.tsx               # 瘦身: 保留 ~6 it 集成
  ├── use-table-pagination.test.ts      # 新
  ├── data-table-pagination.test.tsx    # 新
  ├── data-table-body.test.tsx          # 新
  └── index.ts                          # 加 4 个新 re-export (测试用)
```

### 3.2 模块边界 + 接口

#### `use-table-pagination.ts` (纯 hook, 无 JSX)

**职责**: 受控/非受控分页状态管理 + pageData 切片 + totalPages 计算

**输入**:
- `dataSource: TData[]`
- `pagination?: { current: number; pageSize: number; total: number; onChange: (page: number) => void }`

**输出**:
```ts
export interface UseTablePaginationReturn<TData> {
  current: number;          // 受控: 来自 prop; 非受控: 内部 state
  total: number;            // 受控: 来自 prop.total; 非受控: dataSource.length
  totalPages: number;       // Math.ceil(total / pageSize)
  pageData: TData[];        // 受控: 整个 dataSource; 非受控: 切片
  handleChangePage: (page: number) => void;  // 受控: 调 pagination.onChange; 非受控: setInternalPage
}
```

**保留行为** (0 变化):
- `PAGE_SIZE` 默认 20
- `pageSize` 从 `pagination.pageSize` 取, 否则 fallback 20
- 非受控 mode: `dataSource.slice(current * pageSize, (current + 1) * pageSize)`
- 受控 mode: `dataSource` 原样返回 (调用方应已切片)

#### `data-table-pagination.tsx`

**职责**: 分页栏 UI 渲染 (第 N / M 页 + 上下页按钮 + 总条数)

**输入**:
```ts
export interface DataTablePaginationProps {
  totalPages: number;
  current: number;
  total: number;
  onPageChange: (page: number) => void;
}
```

**行为** (从 data-table.tsx 的 `renderPaginationSection` 1:1 移过来):
- `totalPages <= 1` 返回 `null` (不渲染)
- 第 1 页: `PaginationPrevious` disabled (`pointer-events-none opacity-50`)
- 最后页: `PaginationNext` disabled
- 按钮 click → `onPageChange(Math.max(0, current - 1))` / `Math.min(totalPages - 1, current + 1)`
- 文案 `第 {current + 1} / {totalPages} 页 · 共 {total} 条`

#### `data-table-body.tsx`

**职责**: 表体状态分支 (loading / 空 / 数据) + stagger 行入场动画 + 展开行

**输入**:
```ts
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
```

**行为** (从 data-table.tsx 的 `getCellContent` + `renderDataRows` + `renderLoadingRow` + `renderEmptyRow` 1:1 移过来):
- `loading`: 渲染加载行 (1 行, colspan = columns.length, 脉冲动画)
- `pageData.length > 0`: 渲染数据行 (motion.tr stagger + expandedRowRender)
- 其他: 渲染空态行 (1 行, colspan = columns.length, emptyText)

#### `data-table.tsx` (瘦身, ≤ 180 行)

**保留**: 列宽工具 (`getFlexColStyle` / `getStringColStyle` / `getColStyle` + `ColumnWidth` 类型) + `ColumnDef<T>` + `DataTableProps<T>` + `resolveMaxHeight` + stickyEnabled 计算 + 所有 const 常量 + 调上面 3 个模块

**DataTable 组件体内**:
```tsx
const DataTable = <TData,>(props: DataTableProps<TData>) => {
  const { current, total, totalPages, pageData, handleChangePage } = useTablePagination(
    props.dataSource,
    props.pagination,
  );
  const containerStyle = resolveMaxHeight(props.maxHeight);
  const stickyEnabled = props.maxHeight !== "auto" && Boolean(props.maxHeight);

  return (
    <div className={cn("rounded-lg border border-border/60", props.className)}>
      <div className={cn("min-h-0 overflow-auto", stickyEnabled && "flex-1")} style={{ maxHeight: containerStyle }}>
        <Table>
          <TableHeader className={cn(stickyEnabled && "sticky top-0 z-10 bg-muted/80 backdrop-blur-sm")}>
            <TableRow>
              {props.columns.map(column => /* 列头渲染, 走 getColStyle */)}
            </TableRow>
          </TableHeader>
          <TableBody className="[&_tr:last-child]:border-0">
            <DataTableBody
              columns={props.columns}
              emptyText={props.emptyText}
              expandedRowRender={props.expandedRowRender}
              loading={props.loading}
              onRowClick={props.onRowClick}
              pageData={pageData}
              rowClassName={props.rowClassName}
              rowKey={props.rowKey}
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

### 3.3 index.ts 改动

```ts
// 之前
export * from "./data-table";
export * from "./data-table-skeleton";

// 之后
export * from "./data-table";
export * from "./use-table-pagination";
export * from "./data-table-pagination";
export * from "./data-table-body";
export * from "./data-table-skeleton";
```

### 3.4 测试拆分

| 测试文件 | 测什么 | 怎么测 |
|---|---|---|
| `use-table-pagination.test.ts` (新) | 受控 mode (pageData 原样 + onChange 透传 + total 用 prop); 非受控 mode (pageData 切片 + setInternalPage + total 用 dataSource.length); totalPages 计算 (25 条 / pageSize=20 → 2); pageSize 默认 20 | `renderHook` from `@testing-library/react`, 调 `result.current.handleChangePage(N)` 断言 |
| `data-table-pagination.test.tsx` (新) | totalPages ≤ 1 不渲染; 第 1 页 prev disabled; 最后页 next disabled; 中间页 onChange 调用 + 边界裁剪 | `render` + `screen.getByText` + `userEvent.click` |
| `data-table-body.test.tsx` (新) | loading → "加载中…"; 空 + emptyText string → 文本; 空 + emptyText ReactNode → DataEmpty; 数据 → 行数 = pageData.length; 列 render 函数被调; rowClassName 附加; expandedRowRender 渲染 | `render` + `screen.getAllByTestId("data-table-row")` + `screen.getByTestId("expanded-row")` |
| `data-table.test.tsx` (瘦身) | 保留: 渲染表头 (3 it: 列头文本 / 行数 / 列 render) + sticky (maxHeight) + 受控分页集成 + onRowClick + emptyText 2 个; 删除: 分页切片 / 上下页点击 (迁 `data-table-pagination.test.tsx`) / loading / empty / expanded (迁 `data-table-body.test.tsx`) / 列宽 4 模式 (迁 `data-table-body.test.tsx` 因列宽 + 列 render 同列定义职责) | 同上 |

### 3.5 顺序约束 (项目铁律)

1. `bun run format` (0 报错)
2. `bun run lint:fix` (0 报错)
3. `bun run typecheck` (0 error)
4. `bun run test` (0 新 fail; pre-existing fail 不算)
5. `git add` + commit (prefix `refactor:`)

中途不 commit (单原子重构, 中间状态会 break 调用点).

### 3.6 风险 + 缓解

| 风险 | 缓解 |
|---|---|
| 拆分过程中 4 调用点短暂 break | 1 个原子 commit, 中间不提交; commit 前跑全套 `bun run lint:fix && bun run typecheck && bun run test` |
| 测试 import 路径错 | 新测试文件 import 走 `./use-table-pagination` 等相对路径; `bun run typecheck` 兜底 |
| hook 测试需要 `renderHook` | `@testing-library/react` 14+ 内置 `renderHook`, 项目 vitest 装的是 16.x ([packages/web/package.json]), 直接 `import { renderHook } from "@testing-library/react"` |
| 受控/非受控 hook 行为漂移 | `use-table-pagination.test.ts` 覆盖**所有**当前场景 (受控/非受控/边界/pageSize 默认/total fallback), 0 行为变化 |
| 列宽工具移动导致循环 import | 不动, 留在 data-table.tsx |
| 拆分后导出顺序乱触发 lint | 4 文件 import 按字母排序 (项目 [CLAUDE.md §零 lint warning 规范] 要求) |
| stagger 动画在测试里触达 | `screen.getAllByTestId("data-table-row")` + `data-testid="expanded-row"` 跟当前一致 |

### 3.7 不做的事 (YAGNI 复述)

- ❌ 不动 `ColumnDef` / `ColumnWidth` / `DataTableProps`
- ❌ 不动 4 个调用点 (DatasetsTable / DatasetDocumentsTable / NodesTable / RelationsTable)
- ❌ 不引入 TanStack Table
- ❌ 不加 sort / filter / resize / jump-to-page / 列拖拽
- ❌ 不改 sticky / stagger / 列宽 4 模式 / 分页栏样式行为
- ❌ 不改 DataTableSkeleton

## 4. 关联文档

- 上游 [2026-06-23-datatable-refine-design.md](./2026-06-23-datatable-refine-design.md) — 列宽 4 模式 + 双线修复 (已落 master, 不动)
- 项目铁律: [packages/web/CLAUDE.md §零 lint warning 规范](../packages/web/CLAUDE.md)
- YAGNI: [[feedback-no-shim-no-minimal-changes]] — TanStack 装了未用, 不主动启用
- 表格约定: [packages/web/CLAUDE.md §表格组件] — DataTable 是项目封装, 4 调用点已对齐

## 5. 验收

### 5.1 文件结构验收

- [ ] 4 个新文件存在 (`use-table-pagination.ts` / `data-table-pagination.tsx` / `data-table-body.tsx` / `data-table-body.test.tsx` / `use-table-pagination.test.ts` / `data-table-pagination.test.tsx` — 实际 6 个新文件含 3 个测试)
- [ ] data-table.tsx 行数 ≤ 180 (用 `wc -l data-table.tsx` 验)
- [ ] index.ts 包含 4 个新 re-export
- [ ] data-table-skeleton.tsx / data-table-skeleton.test.tsx 0 改动

### 5.2 测试验收

- [ ] `bun run test` 0 新 fail (跟当前 master 对比: 拆分前跑一次记录 baseline fail 列表, 拆分后 fail 列表不变)
- [ ] 新增 3 测试文件 it 数分配: `use-table-pagination.test.ts` ≥ 6 it, `data-table-pagination.test.tsx` ≥ 4 it, `data-table-body.test.tsx` ≥ 8 it (合计 ≥ 18 it)
- [ ] 原 `data-table.test.tsx` it 数从 12 降到 ≤ 8 (具体删除的 it 见 §3.4 末尾表格)
- [ ] 4 调用点 0 改动 (`git diff DatasetsTable DatasetDocumentsTable NodesTable RelationsTable` 空)

### 5.3 质量验收

- [ ] `bun run format` 0 报错
- [ ] `bun run lint:fix` 0 报错
- [ ] `bun run typecheck` 0 error
- [ ] 0 行 `function` 声明 (项目 [CLAUDE.md §零 lint warning 规范] 要求 `const = () =>`)
- [ ] 0 单字符变量名 (val 替代 v, idx 替代 i)
- [ ] 0 魔法数字 (PAGE_SIZE / ZERO / 等已在 const 命名)
- [ ] 0 行内 `onClick={() => ...}` 复杂表达式
- [ ] 4 文件 import 按字母排序
- [ ] 1 个 commit `refactor: split DataTable into 4 modules + reorganize tests`

### 5.4 行为验收

- [ ] 列宽 4 模式行为不变 (number / string / `{min,max}` / `auto` / `fill`)
- [ ] sticky 表头行为不变 (maxHeight 启用 / "auto" 禁用)
- [ ] 分页受控/非受控 mode 行为不变
- [ ] stagger 行入场动画行为不变
- [ ] 展开行 (expandedRowRender) 行为不变
- [ ] loading 态 / empty 态渲染行为不变
- [ ] 4 调用点视觉 + 交互 0 变化

### 5.5 bundle 验收

- [ ] 0 新依赖
- [ ] 0 bundle 增长 (拆分是结构调整, 不引入新代码)

## 6. 实施边界

### 6.1 In scope

- 4 个新文件 (3 实现 + 3 测试, 算 6 文件)
- data-table.tsx 瘦身
- data-table.test.tsx 瘦身
- index.ts 加 3 个新 re-export

### 6.2 Out of scope

- 任何调用方改动
- 任何 shadcn / Radix 原语改动
- DataTableSkeleton 改动
- 任何新功能 (sort / filter / resize / etc.)
- TanStack Table 启用 / 迁移
- 列宽工具移动
- const 常量移到 `const/index.ts`

## 7. commit 信息模板

```
refactor(data-table): split into 4 modules + reorganize tests

- use-table-pagination.ts (50 行): 纯 hook, 受控/非受控 + pageData 切片
- data-table-pagination.tsx (80 行): <DataTablePagination /> UI
- data-table-body.tsx (120 行): <DataTableBody<T> /> 状态分支 + stagger
- data-table.tsx (150 行): 列宽工具 + types + 壳

测试:
- 新 3 文件 (use-table-pagination / data-table-pagination / data-table-body)
- 原 data-table.test.tsx 12 it → 8 it (迁分页/状态/展开测到新文件)

动机: data-table.tsx 384 行, 6 段职责混 1 文件. 拆后主文件 ≤ 180 行,
每个新模块 1 个明确职责 + 1 个独立测试文件.

对外 API 0 变化: 4 调用点 (DatasetsTable / DatasetDocumentsTable /
NodesTable / RelationsTable) 0 改动.
```
