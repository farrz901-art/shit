# DataTable 公共组件精修 — 列宽自适应 + 双线修复 + 微美化

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复 /admin/users 表格"列挤前、空白在后"+"行间双线"问题, 集中改 1 个公共组件 (`data-table.tsx`), 调用方 0 改动.

**Architecture:** 升级 `ColumnDef.width` 为 `ColumnWidth` union (4 种模式, 向后兼容), 修复末行/展开行/空态行的 border-b 双线 (用 `[&_tr:last-child]:border-0` 跟 `[&>td]:border-0` CSS 选择器), 统一外层/分页栏边框色 `border-border/60`, 表格内 text-sm + 表头 whitespace-nowrap.

**Tech Stack:** Next.js 15 (App Router) + React 19 + TypeScript 8 + Tailwind CSS 4 + shadcn/ui + framer-motion + vitest + @testing-library/react

**Spec:** [docs/superpowers/specs/2026-06-23-datatable-refine-design.md](../specs/2026-06-23-datatable-refine-design.md)

---

## File Structure

| 文件 | 类型 | 职责 |
|---|---|---|
| `packages/web/components/common/data-table/data-table.tsx` | 改 | 公共 DataTable 组件: ColumnDef 类型 + 列宽样式 + 表格行渲染 + 分页栏 |
| `packages/web/components/common/data-table/data-table.test.tsx` | 改 | 单元测试: 基础渲染/空态/分页/样式/交互 + 4 个新增 case |

**调用方 0 改动** (12+ 文件, 向后兼容). 修改通过 `git diff --name-only` 验证只动 2 个文件.

---

## Task 1: ColumnWidth 类型定义 + getColStyle 4 模式

**Files:**
- Modify: `packages/web/components/common/data-table/data-table.tsx:69-75` (ColumnDef interface) + `48-56` (getColStyle helper)

- [ ] **Step 1: 添加 ColumnWidth 类型导出**

在 `data-table.tsx` 顶部, `export interface ColumnDef` 上方, 加:

```ts
// 列宽 4 种模式 (2026-06-23 redesign):
//   - number / string: 旧 API, 固定宽度 (向后兼容)
//   - { min, max? }: 弹性宽度, e.g. { min: 150, max: 300 }
//   - "auto": 内容自适应, table-layout auto
//   - "fill": 抢占剩余空间, table-layout fixed (本 spec 暂不引入, YAGNI)
export type ColumnWidth =
  | number
  | string
  | { max?: number; min: number }
  | "auto"
  | "fill";
```

- [ ] **Step 2: 升级 ColumnDef.width 类型**

修改 `data-table.tsx:72`:

```ts
export interface ColumnDef<TData> {
  align?: "left" | "center" | "right";
  key: string;
  render?: (row: TData, index: number) => ReactNode;
  title: string;
  width?: ColumnWidth;
}
```

- [ ] **Step 3: 重写 getColStyle 函数**

替换 `data-table.tsx:48-56` 的 `getColStyle`:

```ts
const getColStyle = (width: ColumnWidth | undefined): React.CSSProperties | undefined => {
  if (width === undefined) {
    return undefined;
  }
  if (typeof width === "number") {
    return { width: `${width}px` };
  }
  if (typeof width === "string") {
    if (width === "auto") {
      return { width: "auto" };
    }
    if (width === "fill") {
      // 配合 table-layout: fixed, 抢占剩余空间
      return { minWidth: "0", width: "100%" };
    }
    return { width };
  }
  // 弹性 { min, max? }
  const style: React.CSSProperties = { minWidth: `${width.min}px` };
  if (width.max !== undefined) {
    style.maxWidth = `${width.max}px`;
  }
  return style;
};
```

- [ ] **Step 4: 跑类型检查**

Run: `cd packages/web && bun run typecheck`
Expected: 0 error (tsgo 通过)

- [ ] **Step 5: 跑现有测试 (验证向后兼容)**

Run: `cd packages/web && bun run test -- components/common/data-table/data-table.test.tsx`
Expected: 12 case 全部 pass (旧 API 完全兼容)

- [ ] **Step 6: Commit**

```bash
git add packages/web/components/common/data-table/data-table.tsx
git commit -m "feat(datatable): ColumnWidth union 4 模式 (向后兼容)"
```

---

## Task 2: 新增 4 个 ColumnWidth 单元测试 case

**Files:**
- Modify: `packages/web/components/common/data-table/data-table.test.tsx` (在 describe("样式功能") 块加 4 case)

- [ ] **Step 1: 在 "样式功能" describe 末尾加 4 个 case**

找到 `describe("样式功能", ...)` 块, 在 `rowClassName` 测试之后加:

```ts
// (2026-06-23) ColumnWidth 4 模式
it("列 width 为 number (旧 API) 时, 渲染 width: Npx", () => {
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

it("列 width 为 { min, max } 时, 渲染 minWidth + 可选 maxWidth", () => {
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

it("列 width 为 'auto' 时, 渲染 width: auto", () => {
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

it("列 width 为 'fill' 时, 渲染 minWidth: 0 + width: 100%", () => {
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
```

- [ ] **Step 2: 跑新测试**

Run: `cd packages/web && bun run test -- components/common/data-table/data-table.test.tsx -t "列 width"`
Expected: 4 case 全部 pass

- [ ] **Step 3: Commit**

```bash
git add packages/web/components/common/data-table/data-table.test.tsx
git commit -m "test(datatable): 4 个 ColumnWidth case"
```

---

## Task 3: 末行 tr 去掉 border-b (双线 bug fix #1)

**Files:**
- Modify: `packages/web/components/common/data-table/data-table.tsx:344-346` (TableBody 渲染)

- [ ] **Step 1: 修改 TableBody className**

在 `data-table.tsx` 找 `<TableBody>{bodyContent}</TableBody>`, 改成:

```tsx
<TableBody className="[&_tr:last-child]:border-0">{bodyContent}</TableBody>
```

**原理**: `tbody` 内最后一个 `tr` (含数据行/展开行/空态行) 的 `border-b` 全部去掉, 避免跟外层 div 1px 底边 + 分页栏 `border-t` 紧贴成双线.

- [ ] **Step 2: 跑现有测试**

Run: `cd packages/web && bun run test -- components/common/data-table/data-table.test.tsx`
Expected: 12 case + 4 new case 全部 pass (行为不破坏)

- [ ] **Step 3: 跑 typecheck + lint**

Run: `cd packages/web && bun run typecheck && bun run lint`
Expected: 0 error

- [ ] **Step 4: Commit**

```bash
git add packages/web/components/common/data-table/data-table.tsx
git commit -m "fix(datatable): 末行 tr 去 border-b 消除跟外层底边双线"
```

---

## Task 4: 展开行 border 策略重写 (双线 bug fix #2)

**Files:**
- Modify: `packages/web/components/common/data-table/data-table.tsx:154-169` (展开行 motion.tr)

- [ ] **Step 1: 改展开行 className**

找到 `data-table.tsx:155-169` (展开行 motion.tr), 修改 className:

```tsx
{expandedRowRender !== undefined && (
  <motion.tr
    key={`${key}-expanded`}
    data-testid="expanded-row"
    initial={{ opacity: ANIM_OPACITY_START, translateY: ANIM_Y_START }}
    animate={{ opacity: ANIM_OPACITY_END, translateY: ANIM_Y_END }}
    transition={{
      delay: index * ANIM_DELAY_STEP,
      duration: DUR.normal,
      ease: CSS_EASE.outExpo,
    }}
    className="border-b-0 bg-muted/30 [&>td]:border-b"
  >
    <TableCell colSpan={columns.length}>{expandedRowRender(rowData)}</TableCell>
  </motion.tr>
)}
```

**原理**:
- 展开行 tr 自身 `border-b-0` (去掉原 `border-b`)
- 展开行内 `<TableCell>` 通过 `[&>td]:border-b` 重新加底边
- 数据行 (第 1 个 motion.tr) 的 `border-b` 保留
- 末行策略 (Task 3) 让最后一行的 border-b 失效, 展开行自身的底边靠 `[&>td]:border-b` 提供

- [ ] **Step 2: 跑现有测试**

Run: `cd packages/web && bun run test -- components/common/data-table/data-table.test.tsx`
Expected: 全 pass (展开行 testid 保留)

- [ ] **Step 3: 跑 typecheck + lint**

Run: `cd packages/web && bun run typecheck && bun run lint`
Expected: 0 error

- [ ] **Step 4: Commit**

```bash
git add packages/web/components/common/data-table/data-table.tsx
git commit -m "fix(datatable): 展开行 border 移到 td 避免双线夹灰条"
```

---

## Task 5: 空态/Loading 行加 `[&>td]:border-0` (双线 bug fix #3)

**Files:**
- Modify: `packages/web/components/common/data-table/data-table.tsx:177-196` (renderLoadingRow + renderEmptyRow)

- [ ] **Step 1: 改 renderLoadingRow**

找到 `data-table.tsx:177-188` (renderLoadingRow), 修改为:

```tsx
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
```

- [ ] **Step 2: 改 renderEmptyRow**

找到 `data-table.tsx:190-196` (renderEmptyRow), 修改为:

```tsx
const renderEmptyRow = (columnsLength: number, emptyText: ReactNode): ReactNode => (
  <TableRow className="hover:bg-transparent [&>td]:border-0">
    <TableCell colSpan={columnsLength} className="h-40 text-center text-muted-foreground">
      {emptyText}
    </TableCell>
  </TableRow>
);
```

**原理**:
- `hover:bg-transparent` 避免空态/loading 整行 hover 灰底
- `[&>td]:border-0` 去掉空态/loading cell 底边 (跟外层 1px 紧贴成双线)
- `h-24` → `h-40` 增加行高, 跟 DataEmpty 图标更舒展 (spec §3.3)

- [ ] **Step 3: 跑现有测试**

Run: `cd packages/web && bun run test -- components/common/data-table/data-table.test.tsx`
Expected: 12 case + 4 new case 全部 pass (loading test 验 `加载中…` 文本仍存在)

- [ ] **Step 4: 跑 typecheck + lint**

Run: `cd packages/web && bun run typecheck && bun run lint`
Expected: 0 error

- [ ] **Step 5: Commit**

```bash
git add packages/web/components/common/data-table/data-table.tsx
git commit -m "fix(datatable): 空态/Loading 行 td 去 border 跟外层统一"
```

---

## Task 6: 外层容器 + 分页栏颜色统一 `border-border/60`

**Files:**
- Modify: `packages/web/components/common/data-table/data-table.tsx:215` (分页栏) + `:320` (外层容器)

- [ ] **Step 1: 改外层容器**

找到 `data-table.tsx:320` 外层 div:

```tsx
<div className={cn("rounded-lg border border-border/40", className)}>
```

改成:

```tsx
<div className={cn("rounded-lg border border-border/60", className)}>
```

- [ ] **Step 2: 改分页栏**

找到 `data-table.tsx:215` 分页栏 div:

```tsx
<div className="flex items-center justify-between border-t border-border/40 px-4 py-2">
```

改成:

```tsx
<div className="flex items-center justify-between border-t border-border/60 bg-muted/20 px-6 py-3">
```

**原理**:
- `border-border/40` → `border-border/60`: 颜色加深, 跟 tr 内部 `border-b` (100% 透) 接近, 紧贴时减少"双线"感
- 分页栏加 `bg-muted/20` 跟表格区视觉分层
- 分页栏 padding `px-4 py-2` → `px-6 py-3` 跟表格内 padding 协调

- [ ] **Step 3: 跑现有测试**

Run: `cd packages/web && bun run test -- components/common/data-table/data-table.test.tsx`
Expected: 全 pass

- [ ] **Step 4: 跑 typecheck + lint**

Run: `cd packages/web && bun run typecheck && bun run lint`
Expected: 0 error

- [ ] **Step 5: Commit**

```bash
git add packages/web/components/common/data-table/data-table.tsx
git commit -m "style(datatable): 外层/分页栏 border-border/60 统一, 分页栏加 bg + padding"
```

---

## Task 7: 表格内 text-sm + 表头 whitespace-nowrap (微美化)

**Files:**
- Modify: `packages/web/components/common/data-table/data-table.tsx` (TableCell 渲染 + TableHead 渲染)

- [ ] **Step 1: 数据行 TableCell 加 text-sm**

找到 `data-table.tsx:142-152` (columns.map 内的 TableCell), 修改:

```tsx
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
```

- [ ] **Step 2: 表头 TableHead 加 whitespace-nowrap**

找到 `data-table.tsx:330-342` (TableHeader 内的 TableHead), 修改 className:

```tsx
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
```

**原理**:
- 数据行 `text-sm` (14px) 跟项目数据表惯例一致 (admin/dicts, knowledge/relations 已用)
- 表头 `whitespace-nowrap` 防止 i18n 长标题换行

- [ ] **Step 3: 跑现有测试**

Run: `cd packages/web && bun run test -- components/common/data-table/data-table.test.tsx`
Expected: 全 pass (text-sm / whitespace-nowrap 不影响断言)

- [ ] **Step 4: 跑 typecheck + lint**

Run: `cd packages/web && bun run typecheck && bun run lint`
Expected: 0 error

- [ ] **Step 5: Commit**

```bash
git add packages/web/components/common/data-table/data-table.tsx
git commit -m "style(datatable): 数据行 text-sm, 表头 whitespace-nowrap"
```

---

## Task 8: 视觉抽检 5 个核心调用方 + 全量验证

**Files:**
- 不修改代码, 跑手工验证

- [ ] **Step 1: 跑完整 vitest (data-table + 12+ 调用方测试)**

Run: `cd packages/web && bun run test -- components/common/data-table`
Expected: data-table.test.tsx (16 case) 全 pass

- [ ] **Step 2: 跑前端 format + lint + typecheck + test**

按 CLAUDE.md 顺序:
```bash
cd packages/web
bun run format
bun run lint:fix
bun run typecheck
bun run test
```

Expected: 0 error, 0 new fail (pre-existing fail 不算新 fail)

- [ ] **Step 3: 启动 dev server, 视觉抽检 5 个核心页**

启动前端: `cd packages/web && bun run dev` (后台), 浏览器访问:

| 页面 | URL | 验证项 |
|---|---|---|
| 用户管理 | /admin/users | 5 列(邮箱/类型+角色/状态/最近活动/操作) 占满, 操作列右对齐, 行间无双线 |
| 字典管理 | /admin/dicts | 展开 dict-item 编辑时无双线, 末行干净 |
| 数据集 | /knowledge/datasets | 列少时 fill 列自适应 |
| 任务列表 | /output | maxHeight sticky 状态线条不双线 |
| 评估 | /evaluate | 分页栏 padding 跟表格协调 |

每页手工检查:
- 末行 tr 跟外层 div 底边无视觉双线
- 展开行 (如适用) 展开/收起无视觉双线
- 空态行底边干净
- 操作列右对齐, 按钮组 justify-end
- 列宽分布合理, 前后不留大片空白

- [ ] **Step 4: 跑 git diff 确认只动了 2 个文件**

Run: `git diff --name-only master`
Expected:
- `packages/web/components/common/data-table/data-table.tsx` (modified)
- `packages/web/components/common/data-table/data-table.test.tsx` (modified)
- **不应有其它文件** (调用方零改动)

- [ ] **Step 5: 验证完毕, 准备合并**

如果所有验证通过, 准备合并到 master (走 superpowers:finishing-a-development-branch).

---

## 关联文档

- Spec: [docs/superpowers/specs/2026-06-23-datatable-refine-design.md](../specs/2026-06-23-datatable-refine-design.md)
- 现状: [data-table.tsx (2026-06-10 redesign)](../../../packages/web/components/common/data-table/data-table.tsx)
- 调用的 12+ 表格: admin/users, admin/dicts, admin/invites, admin/profile-fields, knowledge/datasets, knowledge/dataset-documents, knowledge/documents/import, knowledge/nodes, knowledge/relations, output, evaluate, evaluate/new, evaluate/sample, buyers
- 项目规范: [CLAUDE.md](../../../CLAUDE.md) + [.claude/CLAUDE.md](../../../.claude/CLAUDE.md) + [packages/web/CLAUDE.md](../../../packages/web/CLAUDE.md)
