# DataTable TanStack Table 内核化 (2026-06-26) — 完成 handoff

## 当前状态

**Task 1-6 完成 (Task 4 用户直接 commit, Task 5/6 无 review), Task 7 最终验证通过. 剩余: 去掉适配层.**

- 10 commits (base: `21eb7b6d` → HEAD: `ba734ae2`), +430/-274 行
- master HEAD 干净, 工作树 clean
- 全量 vitest: **1002 passed, 0 failed, 1 skipped** (pre-existing)
- oxlint 0 warning, typecheck 0 error
- DatasetsTable 非受控分页 bug 已修 (`ba734ae2`)

## 文件结构 (当前)

```
components/common/table/
  ├── data-table.tsx                    # 顶层 useReactTable 驱动, 对外 API 不变
  ├── data-table-body.tsx              # table.getRowModel().rows + flexRender
  ├── data-table-pagination.tsx        # 接 table 实例派生分页状态
  ├── to-tanstack-columns.ts           # [待删] 适配层: ColumnDef → TanStack ColumnDef
  ├── to-tanstack-columns.test.tsx     # [待删] 适配层 8 个测试
  ├── index.ts
  ├── data-table-skeleton.tsx          # 未动
  ├── data-table.test.tsx              # 改: 分页断言修正 (1-based)
  ├── data-table-body.test.tsx         # 改: BodyHarness 模式
  ├── data-table-pagination.test.tsx   # 改: Harness 模式
  ├── data-table-skeleton.test.tsx     # 未动
  └── use-table-pagination.ts          # [已删]
  └── use-table-pagination.test.ts     # [已删]
```

## 验收

- [x] 公共 3 测试通过 (data-table / data-table-body / data-table-pagination) — 31 passed
- [x] 适配层 8 个测试通过
- [x] 14 个调用方 0 改动
- [x] oxlint 0 warning
- [x] typecheck 0 error
- [x] 非受控分页回归 (DatasetsTable 25 条翻页)

## Commits (本分支新加)

| SHA | Title | 行数变化 |
|---|---|---|
| `6f6885fc` | feat(table): add to-tanstack-columns adapter for TanStack Table | +41 |
| `823d2271` | fix(table): correct doc comment reference to data-table-body.tsx | ±2 |
| `7a8220ae` | refactor: 加注释说明 TanStack 8.x ColumnDef 多态 cast 原因 | +2 |
| `351db1da` | refactor(table): use useReactTable for header rendering (parallel) | +86/-17 |
| `e930543a` | refactor(table): drop useMemo per React 19 Compiler rule | -2 |
| `e3e473df` | refactor: drop redundant colDef fallback in DataTable header render | -2/+1 |
| `36f8d53a` | refactor(table): use table.getRowModel() + flexRender in DataTableBody | +93/-65 |
| `909ecae4` | refactor(table): DataTablePagination takes TanStack table instance | +109/-47 |
| `857bb2ac` | refactor(table): remove useTablePagination (replaced by TanStack) | +5/-100 |
| `ba734ae2` | fix(table): 非受控分页 getPaginationRowModel 无条件加载, 默认 pageSize=20 | +7/-3 |

**基准**: `21eb7b6d` (bug 修复: expandedRowRender null 跳过)

## 关键设计决策

1. **shadcn 为主, TanStack 为辅** — shadcn `<Table>`/`<TableHead>`/`<TableRow>`/`<TableCell>` 全部保留, TanStack 只提供 row model + flexRender (用户明确定义)
2. **适配层 `to-tanstack-columns.ts`** — 翻译 `ColumnDef[]` → TanStack `ColumnDef[]`, 14 个调用方 0 改动
3. **React 19 Compiler** — 不用 useMemo/useCallback (用户明确要求)
4. **受控分页**: `manualPagination: true` + `onPaginationChange` — TanStack pageIndex (0-based) ↔ 外部 page (1-based)
5. **非受控分页**: `getPaginationRowModel()` 无条件加载 + `initialState.pagination.pageSize = DEFAULT_PAGE_SIZE (20)`
6. **并行期**: Task 3 头走 TanStack + 体走 useTablePagination 并行, Task 5 合并, Task 6 删

## 剩余工作 (待实现)

### 去掉适配层 (用户要求)

**思路**: 删 `to-tanstack-columns.ts` / `.test.tsx`, 自定义 `ColumnDef<T>` 改成 TanStack 原生的 `ColumnDef<T>`. 14 个调用方每列改字段名:

| 当前 | TanStack 直接 |
|---|---|
| `key: "name"` | `id: "name"` + `accessorKey: "name"` |
| `title: "姓名"` | `header: () => "姓名"` |
| `render: (row) => ...` | `cell: (ctx) => ctx.getValue()` |
| `width: 160` | `size: 160` (TanStack 内建) |
| `align: "right"` | `meta: { align: "right" }` |
| `width: "auto"/{min,max}/"fill"` | `meta: { width: ... }` (保留自定义类型) |

**净减 ~142 行** (减适配层 162 - 调用方膨胀 ~20).

**文件改动**:
- 删: `to-tanstack-columns.ts`, `to-tanstack-columns.test.tsx`
- 改: `data-table.tsx` (删适配层 import + 调用, ColumnDef 改 TanStack)
- 改: `data-table-body.tsx` (TanstackColumnMeta import 路径变)
- 改: 14 个调用方每个列定义

### Cell edit (原计划, 未开始)

另开 spec: `2026-06-26-cell-edit-on-tanstack-design.md` — 不在 handoff 范围内.

## 已知遗留

| # | 问题 | 影响 | 优先级 |
|---|---|---|---|
| 1 | 适配层存在, 代码净增 156 行 (用户指出) | 多余概念层 | **高** (用户要求去掉) |
| 2 | `data-table.tsx` 分页逻辑 1-based ↔ 0-based 转换较绕 | 需维护注意 | 低 |
| 3 | meta `as TanstackColumnMeta` cast (2 处) | TS 类型安全损失 | 低 |

## 项目文档

- **Spec**: `docs/superpowers/specs/2026-06-26-datatable-tanstack-internal-design.md`
- **Plan**: `docs/superpowers/plans/2026-06-26-datatable-tanstack-internal.md`
- **Handoff**: 本文
- **上游拆 spec**: `docs/superpowers/specs/2026-06-25-data-table-split-design.md`

## Next

1. 去掉适配层 (接本 handoff 的"剩余工作")
2. Cell edit (另开 spec)
3. `export * from "./to-tanstack-columns"` 从 index.ts 移除

## 接手提示

- 工具链: `bun run test` (vitest 全量), `bunx oxlint --deny-warnings`, `tsc --noEmit`
- vitest config: testTimeout 15000 (RSC 测试需要)
- 非受控分页 `DEFAULT_PAGE_SIZE = 20` 在 `@/const/index.ts`
- `getPaginationRowModel` **必须无条件加载** — 非受控场景也要它做切片 (已在 `data-table.tsx:133` 外置, `ba734ae2` 修复)
- React 19 Compiler: 不用 useMemo/useCallback
