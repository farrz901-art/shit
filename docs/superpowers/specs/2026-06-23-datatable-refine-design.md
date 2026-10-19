# DataTable 公共组件精修 — 列宽自适应 + 双线修复 + 微美化

> 2026-06-23 沉淀
> 起源: /admin/users 表格"列挤前、空白在后" + 表格行间偶发"两条 black 黑线"
> 范围: 1 个公共组件 + 1 个测试, **调用方 0 改动**

## 1. 目标

| 目标 | 现状 | 验收 |
|---|---|---|
| 列宽自适应 | width 只能传固定 px; 未设 width 的列被自动等分剩余空间, 出现"前面挤后面空" | 新增 4 种 width 语义: 固定 / 弹性 `{min,max}` / `auto` / `fill` |
| 行间双线 | 末行 tr 的 `border-b` 跟外层 `border-border/40` + 分页栏 `border-t` 紧贴, 出现"双线"; 展开行有两层 `border-b` | 末行 tr 去掉 border-b; 展开行边线策略重写; 外层/分页栏颜色统一为 `border-border/60` |
| 视觉降噪 | 行高 16px (text-base) 偏大; 空态 h-24 偏窄; 分页栏 padding 偏小 | 表格行 text-sm; 空态 h-40; 分页栏 px-6 py-3 |

## 2. 非目标 (YAGNI)

- ❌ 改 shadcn `Table` 原语 (`components/ui/table.tsx`) — 风险外溢, 跨页影响
- ❌ 改 `DataTableSkeleton` — 独立组件, 行为正确
- ❌ 改任何调用方 (12+ 文件) — 公共组件向后兼容, 调用方不动
- ❌ 引入新依赖 / 新 motion 动画 — 现状够用
- ❌ 列虚拟化 (virtualization) — 项目数据量未到瓶颈, YAGNI
- ❌ 列拖拽 / 列固定 / 列排序 — 跟现有 spec 无冲突, 留作后续

## 3. 设计

### 3.1 列宽 API 升级 (ColumnWidth union)

`ColumnDef.width` 由 `number | string` 升级为 `ColumnWidth` union 类型, **4 种模式**, 完全向后兼容:

```ts
// 新增类型
export type ColumnWidth =
  | number              // 固定 px (旧 API 完全兼容)
  | string              // CSS 宽度值, e.g. "20%" (旧 API 完全兼容)
  | { min: number; max?: number }   // 弹性: 最小 px, 可选最大
  | "auto"              // 内容自适应 (table-layout: auto, 由内容决定)
  | "fill";             // 抢占剩余空间 (flex: 1 1 0)
```

**渲染映射表** (`getColStyle` 内部):

| 输入 | 输出 CSS |
|---|---|
| `120` | `{ width: "120px" }` |
| `"20%"` | `{ width: "20%" }` |
| `{ min: 150, max: 300 }` | `{ minWidth: "150px", maxWidth: "300px" }` |
| `"auto"` | `{ width: "auto" }` (浏览器 table-layout 决定) |
| `"fill"` | `{ width: "auto", minWidth: "0" }` + 父 table 设 `table-layout: fixed` |

**关键约束**:
- `table-layout: auto` (默认): 支持 `auto` / `{min,max}` 弹性, 但列总和 < 容器时无法均分剩余空间
- `table-layout: fixed`: 支持 `fill` 列抢占剩余, 但内容超长会被截断 (除非配合 `truncate`)
- → **本 spec 采用 auto** 为主, `fill` 不引入 (YAGNI, 现有 12+ 调用方无此需求)

### 3.2 双线 bug 根因

| 现象 | 根因 | 修法 |
|---|---|---|
| 末行 tr `border-b` 跟外层 div 底边 + 分页栏 `border-t` 紧贴 | DataTable 外层 `border-border/40` (40% 透) + tr `border-b` (100% 透) + 分页栏 `border-t` (40% 透) 三条线在不同颜色 + 紧贴 | 末行 tr 加 `[&_tr:last-child]:border-0`; 外层 + 分页栏统一 `border-border/60` |
| 展开行 (expandedRowRender) 数据行 + 展开行各 1 条 `border-b`, 中间只隔 0px padding | 两行 `border-b` 紧贴 + `bg-muted/30` 灰底 → "两黑线夹一浅灰条" | 展开行 (第 2 个 motion.tr) 的 `border-b` 改为 `<TableCell>` 的 `border-b`; 数据行 (第 1 个 motion.tr) 保留; 展开行 tr 自身不画边线 (`border-b-0`), 展开行内单元格底部画线作为分隔 |
| 空态/Loading 行整行画了 `border-b` | 跟外层 1px 贴在一起视觉成双线 | 空态行加 `[&>td]:border-0`; loading 行加 `[&>td]:border-0` |
| 外层 `border-border/40` (40% 透) 跟 tr `border-b` (100% 透) 色差明显 | 颜色不一致, 贴一起就是"双线" | 统一 `border-border/60` |

### 3.3 微美化清单

| 项 | 改前 | 改后 | 理由 |
|---|---|---|---|
| 表格行字号 | 跟随 shadcn `text-base` (16px) | `<TableCell>` 加 `text-sm` (14px) | 项目数据密集, 14px 更合适 |
| 表头防换行 | 默认无 `whitespace-nowrap` | `TableHead` 加 `whitespace-nowrap` | 防止 i18n 长标题换行 |
| 空态行高 | `h-24` (96px) | `h-40` (160px) | 跟 DataEmpty 图标 + 描述更舒展 |
| Loading 居中 | 单纯 `<td>` | `flex flex-col items-center justify-center` | 视觉对齐 |
| 分页栏 padding | `px-4 py-2` | `px-6 py-3` | 跟表格内 padding 一致, 更舒展 |
| 分页栏背景 | 无 | `bg-muted/20` | 跟表格区视觉分层 |
| 外层圆角 + 边框 | `rounded-lg border border-border/40` | `rounded-lg border border-border/60` | 颜色统一, 跟 tr 边线同色阶 |

### 3.4 不动的东西

- shadcn `Table` 原语 (`components/ui/table.tsx`) — 头部 `TableHeader` 的 `[&_tr]:border-b` 保留 (头部需要底线)
- `motion` framer-motion 动画 — 现状流畅
- `DataTableSkeleton` — 独立组件, 行为正确
- 所有 12+ 调用方 — **完全零改动**, 通过新 `ColumnWidth` API 向后兼容

## 4. 涉及文件

| 文件 | 类型 | 估计行数 |
|---|---|---|
| [components/common/data-table/data-table.tsx](packages/web/components/common/data-table/data-table.tsx) | 改 | +60 / -30 |
| [components/common/data-table/data-table.test.tsx](packages/web/components/common/data-table/data-table.test.tsx) | 改 | +80 (4 个新 case) |

**调用方 0 改动** (向后兼容).

## 5. 测试覆盖

### 5.1 现有测试 (data-table.test.tsx, 12 case)

全部保留, 验证向后兼容:
- 基础渲染 (3 case): 表头 / 行数 / render 函数
- 空数据/加载 (3 case): emptyText / ReactNode emptyText / loading
- 分页 (3 case): 客户端分页 / 切页 / 受控分页
- 样式 (3 case): maxHeight sticky / auto 不 sticky / rowClassName

### 5.2 新增 case (4 case)

| Case | 验证 |
|---|---|
| 列 width 为 `{ min: 150 }` 时, th/td 渲染出 `min-w-[150px]` | 弹性宽度 CSS 正确 |
| 列 width 为 `"auto"` 时, th/td 无 width 约束 (但受 table-layout 影响, 只验证 className 不含 `w-` 类) | auto 模式不强制 |
| 列 width 为数字 (旧 API) 时, 行为不变 | 向后兼容 |
| 末行 tr 渲染后, className 不含 `border-b` (用 `:last-child` 选择器在 TableBody 上实现) | 双线 bug 修复 |

### 5.3 视觉抽检 (手工, 不写测试)

跑 5 个核心调用方, **截图**确认无视觉回归:
- `/admin/users` (列最复杂, 7 列)
- `/admin/dicts` (dict-list 有 expandedRowRender, 验证展开行无双线)
- `/knowledge/datasets` (列少, 验证 fill 行为)
- `/output` (有 maxHeight sticky, 验证 sticky 表头线条)
- `/evaluate` (有分页, 验证分页栏 padding)

## 6. 风险评估

| 风险 | 等级 | 缓解 |
|---|---|---|
| 公共组件改动影响 12+ 调用方 | 中 | API 完全向后兼容, 现有测试全过; 视觉抽检 5 个核心页 |
| 边框颜色变更影响主题 (深色模式) | 低 | 统一 `border-border/60` 是 shadcn semantic token, 自动适配主题 |
| 字号 text-sm 影响信息密度 | 低 | 14px 是项目数据表惯例 (admin/dicts, knowledge/relations 已用) |
| 末行 border-b 缺失导致视觉不连续 | 极低 | 外层 div 1px border 自然形成底部边界 |

## 7. 落地步骤 (概要, 详细见 plan)

1. 升级 `ColumnDef.width` 类型为 `ColumnWidth` union
2. 重写 `getColStyle` 处理 4 种模式
3. 修双线: 末行 tr `last:border-0` + 展开行 border 策略 + 空态行 border 策略
4. 改外层容器 border 颜色 + 圆角
5. 改分页栏 padding + 背景
6. 加 text-sm / whitespace-nowrap
7. 加 4 个新测试 case
8. 跑 oxlint + tsgo + vitest + 视觉抽检
9. commit

## 8. 关联文档

- 现状基线: [project 结构 / pages](project-structure.md)
- i18n 规范: [project-i18n-use-chinese-as-t-key](project-i18n-use-chinese-as-t-key.md)
- 主题: [project-theme-system-design (2026-06-10)](docs/superpowers/specs/2026-06-10-theme-system-design.md)
- DataTable 起源: [data-table.tsx 注释 (2026-06-10 redesign)](packages/web/components/common/data-table/data-table.tsx)
