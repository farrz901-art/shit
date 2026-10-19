# UI 组件库封装 (Table + Dialog + Form) 设计

> 2026-06-10 · Brainstorming → Spec
> Status: 待用户 review

## 1. 目标

收口 web/ 下当前 4 处真表格、3 处 grid 假表、4 处弹框、3-4 处表单、9 处手写 button,
统一为 1 套 antd 风格封装组件, 同时补装 shadcn 缺失组件, 收敛样式风格.

不在范围 (后续 spec 处理):
- 主题系统 (Spec C: 白/夜主题 + 配置文件化)
- i18n (Spec D)
- 知识库文档/数据集表格页业务侧 (Spec E)
- 业务自研组件替换 (HealthDot / StatCard / EntryCard 等保留)

## 2. 目录结构

```
web/components/
├── ui/                         # shadcn 原生 (本次只补装, 不改现有)
│   └── (新装: sheet, popover, tooltip, separator, avatar, checkbox,
│         switch, command, form, radio-group, calendar)
│
├── common/                     # 本次新封装 (业务无关, antd 风格 API)
│   ├── data-table/
│   │   ├── data-table.tsx
│   │   ├── data-table.stories.tsx
│   │   └── data-table.test.tsx
│   ├── dialog/
│   │   ├── app-dialog.tsx
│   │   ├── app-dialog.stories.tsx
│   │   └── app-dialog.test.tsx
│   ├── confirm/
│   │   ├── app-confirm.tsx
│   │   ├── app-confirm.stories.tsx
│   │   └── app-confirm.test.tsx
│   ├── drawer/
│   │   ├── app-drawer.tsx
│   │   ├── app-drawer.stories.tsx
│   │   └── app-drawer.test.tsx
│   └── form/
│       ├── form.tsx            # 核心: <Form schema={ZodSchema} onFinish ...>
│       ├── form-item.tsx       # <FormItem name label required help>
│       ├── form-context.ts     # Form context + useFormContext
│       ├── form.stories.tsx
│       └── form.test.tsx
│
└── (knowledge/ chat/ evaluate/ 业务组件 — 不动结构, 只在本次需要时被替换)
```

**`ui/` 与 `common/` 边界**:
- `ui/` = shadcn 原生, 不动, 仅补装
- `common/` = 业务无关封装, 任何项目都能复用, 永远不依赖业务组件
- 业务组件 = 在 `knowledge/ chat/ evaluate/` 下, 业务专用

## 3. DataTable API

```tsx
<DataTable<Row>
  // 数据源 (二选一)
  dataSource={rows}                                // 客户端内置分页
  pagination={{ current, pageSize, total, onChange }}  // 受控

  // 列定义 (推荐)
  columns={[
    { key: "id",      title: "ID",     width: 80, align: "right" },
    { key: "name",    title: "名称",   render: (r) => <Link href={...}>{r.name}</Link> },
    { key: "state",   title: "状态",   render: (r) => <TaskStatusBadge state={r.state} /> },
  ]}

  // 高度 / 滚动
  maxHeight="60vh"        // 字符串/数字 → 容器加 max-h-[X] overflow-auto + sticky 表头
  maxHeight="auto"        // auto → 不限高, 仅 sticky 表头

  // 行交互
  rowKey="id"
  onRowClick={(r, i) => router.push(...)}
  rowClassName={(r) => r.error ? "bg-destructive/4" : ""}
  expandedRowRender={(r) => <DetailView row={r} />}  // 可选: 行可展开

  // 其他
  emptyText="暂无数据"
  loading={isLoading}
/>
```

**关键行为**:
- 双模式分页: 传 `dataSource` 自动客户端分页 (内部 `useState`), 传 `pagination` 对象走受控
- `maxHeight`: 字符串/数字 → 容器加 `max-h-[X] overflow-auto`, 启用 sticky 表头; `auto` → 不限, 仅 sticky
- 列 `render` 完全替代 antd `render` prop, 业务可塞任意 JSX
- 子组件插槽 (备选): 业务也可写 `<DataTableColumn id="name" header="名称" />`, 但 `columns` 是 v1 主推
- 保留 `motion.tr` 动画: 通过 `rowClassName` 业务侧控制
- 不引入 tanstack/react-table

## 4. AppDialog / AppConfirm / AppDrawer API

### AppDialog

```tsx
<AppDialog
  open={open} onOpenChange={setOpen}
  title="编辑用户"
  description="可修改名称与权限"           // 可选
  maxWidth="2xl"                          // sm | md | lg | xl | 2xl | 3xl, 默认 "lg"
  footer={<>
    <Button variant="ghost" onClick={() => setOpen(false)}>取消</Button>
    <Button onClick={handleSave}>保存</Button>
  </>}
>
  <YourForm ... />
</AppDialog>
```

### AppConfirm (走 shadcn AlertDialog)

```tsx
<AppConfirm
  open={confirmOpen} onOpenChange={setConfirmOpen}
  title="删除会话"
  description="此操作不可撤销"
  confirmText="删除"
  cancelText="取消"
  variant="destructive"                   // destructive | default
  onConfirm={handleDelete}
  onCancel={() => toast.info("已取消")}
/>
```

### AppDrawer (走 shadcn Sheet)

```tsx
<AppDrawer
  open={drawerOpen} onOpenChange={setDrawerOpen}
  title="任务详情"
  side="right"                            // right | left
  maxWidth="md"
  footer={<Button onClick={...}>完成</Button>}
>
  <DetailContent />
</AppDrawer>
```

**三个共有的内部结构** (标题固定 + 内容滚动):
```
DialogContent flex flex-col
  ├─ Header (sticky top-0 bg-card z-10, 静态)
  ├─ Body (flex-1 overflow-auto, 滚动)
  └─ Footer (sticky bottom-0 bg-card z-10, 静态, 可选)
```

**受控**: `open` + `onOpenChange(boolean)`, ESC 关闭 / 点外部触发 onOpenChange(false).

## 5. Form API (仿 antd 完整封装)

```tsx
const schema = z.object({
  email: z.string().email("邮箱格式不对"),
  role: z.enum(["user", "admin"]),
  tags: z.array(z.string()).min(1, "至少 1 个标签"),
});

<Form
  schema={schema}
  initialValues={{ email: "", role: "user", tags: [] }}
  onFinish={(values) => submitApi.mutate(values)}
  onFinishFailed={(errors) => toast.error("有字段不通过")}
  onValuesChange={(changed, all) => console.log(changed, all)}
  layout="vertical"                        // vertical | horizontal
>
  <FormItem name="email" label="邮箱" required help="用于登录">
    <Input type="email" />
  </FormItem>

  <FormItem name="role" label="角色" required>
    <Select>
      <SelectItem value="user">用户</SelectItem>
      <SelectItem value="admin">管理员</SelectItem>
    </Select>
  </FormItem>

  <FormItem name="tags" label="标签" required>
    {/* 任意业务组件, 只要能接 value + onChange */}
    <TagPicker />
  </FormItem>

  <Button type="submit">保存</Button>
</Form>
```

### Form 内部机制

- `<Form>` 内部: 自实现 `useForm({ initialValues, onFinish, onFinishFailed, onValuesChange })`
- **store**: `{ values, errors, touched, isSubmitting }` 内部 state + 字段订阅
- 通过 `FormContext` 暴露给子树
- `<FormItem name="email">` 注册到 store, 渲染 children 时 clone 注入 `{ value, onChange, onBlur, error }` 三个 prop
- 业务组件只需遵循"受控组件约定": 接 `value` + `onChange`. `Input`/`Textarea`/`Select`/`Checkbox`/`Switch` 已是
- 业务复合组件 (TagPicker 等) 需自查
- 提交: `schema.safeParse(values)` → 失败回填 `errors` 到 FormItem → 触发 `onFinishFailed`; 成功触发 `onFinish(values)`
- 嵌套路径: 支持 `name="user.email"` (点分路径)
- 不引入 react-hook-form, 自写
- shadcn form (依赖 react-hook-form) 仅作为参考, **不实际使用** — 因为我们要"任意受控组件都能用", shadcn form 仅支持 react-hook-form 注册的组件, 限制更严

### layout 切换

- `vertical` = label 在上, input 在下 (默认)
- `horizontal` = label 左 input 右 (CSS grid, label 列宽 140px)

### FormItem 必传

- `name` (string, 支持点分路径)
- 可选: `label`, `required`, `help` (灰色提示), `rules` (额外 Zod 规则, 跟 schema 合并)

## 6. 补装 shadcn 组件

`npx shadcn@latest add` (一次性):

```
sheet, popover, tooltip, separator, avatar, checkbox, switch, command,
form, radio-group, calendar
```

**注意**: `data-table` shadcn 官方示例也装上 (作参考), 但**不使用**, 我们的 DataTable 自写.

## 7. 替换清单

### 表格 (4 真 + 3 假 → DataTable)

| 路径 | 现状 | 替换为 |
|---|---|---|
| `app/knowledge/nodes/page.tsx` | shadcn Table + 手写分页 | `<DataTable columns dataSource />` |
| `app/knowledge/relations/page.tsx` | 同上 | `<DataTable>` |
| `app/knowledge/documents/import/page.tsx` | 手写 `<table>` | `<DataTable>` |
| `app/knowledge/triples/page.tsx` | 手写 `<table>` 行内编辑 | `<DataTable>` (列 render 内嵌受控 Input) |
| `components/evaluate/SampleTable.tsx` | shadcn Table 无分页 | `<DataTable>` (用 `expandedRowRender` 实现行展开) |
| `app/evaluate/page.tsx` + `EvalListRow` | grid 12 假表 | `<DataTable>` |
| `app/output/page.tsx` | grid 假表 | `<DataTable>` |
| `app/output/[task_id]/page.tsx` | flex 假表 | `<DataTable>` |

### 弹框 (4 Dialog + 1 AlertDialog → AppDialog / AppConfirm)

| 路径 | 现状 | 替换为 |
|---|---|---|
| `app/decode/SeriesDialog.tsx` | shadcn Dialog | `<AppDialog>` |
| `components/chat/SaveToKnowledgeDialog.tsx` | shadcn Dialog + 手写 useState | `<AppDialog>` + `<Form>` (内部) |
| `components/knowledge/SchemaBrowser.tsx` | shadcn Dialog | `<AppDialog>` |
| `app/knowledge/qa/page.tsx` 自测弹窗 | shadcn Dialog | `<AppDialog>` |
| `components/chat/ChatShell.tsx` 删除确认 | shadcn AlertDialog | `<AppConfirm>` |

### 表单 (4 处 → Form)

| 路径 | 现状 | 替换为 |
|---|---|---|
| `components/chat/SaveToKnowledgeDialog.tsx` | 手写 useState | `<Form schema={...}>` |
| `app/knowledge/qa/page.tsx` 录入表单 | 手写 useState | `<Form>` |
| `app/knowledge/triples/page.tsx` 行内编辑 | 手写 useState | 提交时一次性 `schema.safeParse(rows)` (不嵌 Form) |
| `app/evaluate/new/page.tsx` 文件+元信息 | 手写 useState | `<Form>` |

### Button (9 处 → shadcn Button)

`app/evaluate/page.tsx`, `app/output/page.tsx`, `app/output/new/page.tsx`,
`app/knowledge/batch/page.tsx`, `app/knowledge/qa/page.tsx`,
`app/knowledge/triples/page.tsx`, `app/decode/page.tsx` 中所有
`motion.button + 手写 Tailwind 套色` → `<Button variant="..." />`.

### 审计报告

`docs/superpowers/audit-2026-06-10-shadcn-coverage.md`:
- 哪些文件 100% shadcn / 哪些混用 / 哪些手写
- 未替换候选清单 (HealthDot / StatCard / EntryCard / 等)
- shadcn 缺失组件 + 补装状态
- 后续 spec 候选 (主题/i18n/...)

## 8. 测试

每个 common/* 组件:
- `.test.tsx` (vitest, 行为)
- `.stories.tsx` (3-5 个 demo 命名 export, 在 `.test.tsx` 里 `render(<DemoName />)` 验证不崩, 不强求视觉快照)

覆盖:
- `data-table.test.tsx`: 渲染空数据 / 列 render 调用 / 客户端分页 (4 page) / 受控分页 / `maxHeight` 启用 sticky / `rowKey` 重复警告 / `onRowClick` / `expandedRowRender`
- `app-dialog.test.tsx`: 受控 / title/description/footer 渲染 / ESC 关闭 / 滚动结构 (header 静态, body 滚动)
- `app-confirm.test.tsx`: onConfirm/onCancel / destructive 样式
- `app-drawer.test.tsx`: 侧拉方向 / 受控 / title/footer
- `form.test.tsx`: 受控 / 验证错误回填 / 任意业务组件 (mock TagPicker 测插槽) / onFinish / onFinishFailed / 嵌套路径 (`user.email`) / layout 切换

业务页 `page.test.tsx` 必须仍通过 (回归).

## 9. 文件结构 (新)

```
web/components/
├── ui/                          # shadcn 原生 (补装)
├── common/                      # 本次新封装
│   ├── data-table/{data-table.tsx, .stories.tsx, .test.tsx}
│   ├── dialog/{app-dialog.tsx, .stories.tsx, .test.tsx}
│   ├── confirm/{app-confirm.tsx, .stories.tsx, .test.tsx}
│   ├── drawer/{app-drawer.tsx, .stories.tsx, .test.tsx}
│   └── form/{form.tsx, form-item.tsx, form-context.ts, .stories.tsx, .test.tsx}
└── (业务组件目录不变)

docs/superpowers/
└── audit-2026-06-10-shadcn-coverage.md   # 审计报告
```

## 10. 风险与决策

- **Form 仿 antd 完整封装 = 复杂度高**: 自写 `useForm` hook, store + 字段订阅 + 嵌套路径, 跟 react-hook-form 类似但不引第三方
- **shadcn form 装了但不用**: 仅作参考, 实际实现自写 (因我们要"任意受控组件都能用", 不限于 react-hook-form 注册)
- **triples 行内编辑**: 列 render 内嵌受控 `<Input>`, 业务页维护 rows 状态, 提交时一次性 `schema.safeParse(rows)`. Form 不嵌表格
- **motion.tr 保留**: 动画层不动
- **不替换业务自研组件**: HealthDot / StatCard / EntryCard 等保留, 这次范围只到表格/弹框/form/button
- **DataTable 不引 tanstack**: 自家实现, 轻量
- **TypeScript**: 100% TS, 列定义泛型 `<DataTable<Row>>`, Form 泛型 `useForm<Values>`

## 11. 实施顺序 (TDD 任务)

按 writing-plans skill 拆分, 预计 14-18 个任务 (每任务 2-5 分钟, 都有 .test.tsx):

**Phase 1 — 基础设施**
1. 补装 shadcn 缺失组件 + 在 ui/ 下生成

**Phase 2 — DataTable (5 任务)**
2. DataTable 基础渲染 (dataSource + columns + 表格骨架)
3. DataTable 客户端分页 (内置 useState)
4. DataTable 受控分页 (pagination prop 接管)
5. DataTable maxHeight + sticky 表头
6. DataTable 行交互 (rowKey / onRowClick / rowClassName / expandedRowRender)

**Phase 3 — Dialog (4 任务)**
7. AppDialog 基础 (受控 + title/description)
8. AppDialog footer / maxWidth / 滚动结构 (header 静态 body 滚动)
9. AppConfirm (走 AlertDialog)
10. AppDrawer (走 Sheet)

**Phase 4 — Form (4 任务)**
11. Form 核心 (useForm + FormContext + FormItem, 无验证)
12. Form 验证 (Zod schema + 错误回填 + onFinishFailed)
13. Form 嵌套路径 (name="user.email") + 任意插槽组件测试
14. Form layout 切换 (vertical / horizontal)

**Phase 5 — 业务替换 (5 任务)**
15. 替换 4 处真表格 (nodes / relations / import / triples) + SampleTable
16. 替换 3 处 grid 假表 (evaluate 列表 / output 任务 / output 产物)
17. 替换 4 处 Dialog + 1 处 AlertDialog
18. 替换 4 处 Form + 9 处手写 button

**Phase 6 — 收尾**
19. 审计报告 (docs/superpowers/audit-2026-06-10-shadcn-coverage.md)
20. 回归测试 (全 vitest) + typecheck + lint
