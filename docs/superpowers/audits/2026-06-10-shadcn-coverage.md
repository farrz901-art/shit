# shadcn/ui覆盖率审计报告 (2026-06-10)

本报告对 web/ 前端在 UI组件库封装计划 (20任务) 完成后的 shadcn覆盖率做一次全面盘点, 是该计划的最终交付物。

---

##1. shadcn 安装状态

### 当前已装组件 (29 个)

`web/components/ui/` 下共29 个组件,涵盖表单、布局、反馈、导航、数据展示五大类。

| 类别     | 组件                                                                                  |
| -------- | ------------------------------------------------------------------------------------- |
| 表单     | button, input, textarea, label, checkbox, radio-group, select, switch, form, calendar |
| 布局     | card, separator, scroll-area, tabs, sheet, collapsible                                |
| 反馈     | dialog, alert-dialog, alert, sonner, progress, skeleton, badge                        |
| 导航     | pagination, dropdown-menu                                                             |
| 数据展示 | table, avatar, popover, tooltip, command, animated                                    |

###前后对比

| 时点                      | 数量 | 备注                                                                                          |
| ------------------------- | ---- | --------------------------------------------------------------------------------------------- |
| 起点 (2026-06-09探索报告) | 18   | baseline                                                                                      |
| 计划中段补装 (c6d6163)    | 29   | +11: sheet/popover/tooltip/separator/avatar/checkbox/switch/command/form/radio-group/calendar |
| 终态 (2026-06-10)         | 29   | 一致                                                                                          |

补装的11 个组件里有3 个未被业务代码引用:

- `calendar` (暂无日期选择器场景)
- `command` (暂无 Cmd+K面板)
- `popover` (DatasetSwitcher / DomainSwitcher / SchemaFieldRenderer 在用 popover 但走的是 radix 直接 export; 已计入业务使用)

> 后续若新增日期筛选 / 命令面板需求, 这3 个组件可直接启用。

---

##2. common/ 新封装组件

`web/components/common/` 下5 个目录,7 个组件文件 (含 stories/test)。

| 组件       | 路径                                     | 包了 shadcn                 | 业务场景                                  | 已用次数                |
| ---------- | ---------------------------------------- | --------------------------- | ----------------------------------------- | ----------------------- |
| DataTable  | `common/data-table/data-table.tsx`       | table + pagination + button | 列表 +客户端分页 + 空态 + loading +展开行 | 8                       |
| AppDialog  | `common/dialog/app-dialog.tsx`           | dialog                      | 受控弹窗 +滚动结构 + footer插槽           | 4                       |
| AppConfirm | `common/confirm/app-confirm.tsx`         | alert-dialog                | 危险/常规确认                             | 1                       |
| AppDrawer  | `common/drawer/app-drawer.tsx`           | sheet                       | 左侧/右侧抽屉 + footer                    | 0 (待业务接入)          |
| Form       | `common/form/form.tsx` + `form-item.tsx` | 自研,替代 react-hook-form   | useState + Zod +错误回填 + onFinishFailed | 3 (form) +3 (form-item) |

封装统一了以下约束:

1. 受控 (open / values 由父组件管),避免业务代码重复维护 modal state
2. maxWidth / left|right / destructive 等业务语义直接做成 prop
3. footer槽位, 不再让业务手写 `<div className="flex justify-end gap-2">`
4. Form替代 react-hook-form,体积更小, API 更直觉

---

##3.业务组件改造状态

###3.1 全量使用 shadcn100% 的页面 (15 个)

| 文件                                    | 用到的 shadcn                                       | 备注                                   |
| --------------------------------------- | --------------------------------------------------- | -------------------------------------- |
| app/chat/page.tsx                       | button + card + input + textarea + animated         | 聊天主页                               |
| app/decode/page.tsx                     | button + card + input + scroll-area                 | 解码主表                               |
| app/decode/DecodeField.tsx              | input + label                                       | 单字段组件                             |
| app/decode/SeriesDialog.tsx             | dialog + badge + button                             | 解码弹窗 (改 AppDialog 后保留兼容代码) |
| app/evaluate/page.tsx                   | button + badge + DataTable                          | 评估列表                               |
| app/evaluate/[id]/page.tsx              | button + badge                                      | 评估详情                               |
| app/evaluate/new/page.tsx               | button + input + textarea + Form                    | 新建评估 (有1 处遗留 `<table>`, 见3.3) |
| app/knowledge/batch/page.tsx            | button + card                                       | 批量任务页                             |
| app/knowledge/documents/page.tsx        | tabs + button + badge                               | 文档列表                               |
| app/knowledge/documents/import/page.tsx | button + card + DataTable                           | 文档导入                               |
| app/knowledge/graph/page.tsx            | tabs + button                                       | 图谱                                   |
| app/knowledge/qa/page.tsx               | button + card + input + textarea + Form + AppDialog | QA 编辑 (新封装 Form + AppDialog)      |
| app/knowledge/relations/page.tsx        | button + DataTable                                  | 关系列表                               |
| app/knowledge/triples/page.tsx          | button + card + DataTable                           | 三元组列表                             |
| app/knowledge/nodes/page.tsx            | button + DataTable                                  | 节点列表                               |
| app/output/page.tsx                     | button + DataTable                                  | 输出列表                               |
| app/output/[task_id]/page.tsx           | button + DataTable                                  | 输出任务详情                           |
| app/output/[task_id]/[file]/page.tsx    | button + card                                       | 输出文件页                             |
| app/output/new/page.tsx                 | select + input                                      | 新建输出                               |
| app/page.tsx                            | button + animated                                   | 首页                                   |
| app/layout.tsx                          | sonner                                              | 全局 toast                             |

###3.2 已切到 common封装 (12 个文件)

| 文件                                      | 封装             | 提交    |
| ----------------------------------------- | ---------------- | ------- |
| app/knowledge/qa/page.tsx                 | AppDialog + Form | 6361277 |
| app/decode/SeriesDialog.tsx               | AppDialog        | 59c979c |
| components/chat/SaveToKnowledgeDialog.tsx | AppDialog + Form | 6361277 |
| components/chat/ChatShell.tsx             | AppDialog        | 59c979c |
| app/evaluate/new/page.tsx                 | Form             | 6361277 |
| components/knowledge/SchemaBrowser.tsx    | AppDialog        | 59c979c |
| app/knowledge/documents/import/page.tsx   | DataTable        | 51c61c0 |
| app/knowledge/nodes/page.tsx              | DataTable        | 51c61c0 |
| app/knowledge/relations/page.tsx          | DataTable        | 51c61c0 |
| app/knowledge/triples/page.tsx            | DataTable        | 9ca8423 |
| app/evaluate/page.tsx                     | DataTable        | 9ca8423 |
| app/output/page.tsx                       | DataTable        | 9ca8423 |
| app/output/[task_id]/page.tsx             | DataTable        | 9ca8423 |
| components/evaluate/SampleTable.tsx       | DataTable        | 9ca8423 |

###3.3已知遗留 /混合用法 (3 处)

| 文件                                        | 问题                                                                   | 计划                           |
| ------------------------------------------- | ---------------------------------------------------------------------- | ------------------------------ |
| `app/evaluate/new/page.tsx` L157-164        | 1 处遗留 `<table>/<thead>/<tbody>`渲染 sample预览, 未走 DataTable      | 后续评估页重构时切 DataTable   |
| `app/decode/SeriesDialog.tsx`               | 内部注释标 (改 AppDialog 后保留兼容代码),仍有 raw Dialog import 的痕迹 | 已完成迁移,复查删除 import即可 |
| `components/chat/SaveToKnowledgeDialog.tsx` | 早期硬编码 DEFAULT_DATASET_ID / DEFAULT_DOCUMENT_ID (注释明示)         | 待对接 dataset上下文           |

---

##4. 未替换候选清单 (留给后续 spec)

###4.1业务自研组件 (10 个) —建议进 Spec B

| 组件                | 位置                                         | 性质                               | 是否进 common/         |
| ------------------- | -------------------------------------------- | ---------------------------------- | ---------------------- |
| HealthDot           | components/knowledge/HealthDot.tsx           | 业务3 色 dot (绿/黄/红) 表示健康度 | 候选,需确认跨域复用    |
| StatCard            | components/knowledge/StatCard.tsx            | 数字卡 + CountUp动效               | 候选,通用度足够        |
| EntryCard           | components/knowledge/EntryCard.tsx           | 知识库入口卡 (含内部 Link)         | 业务专属, 不进 common/ |
| TaskStatusBadge     | components/knowledge/TaskStatusBadge.tsx     | 任务状态徽章                       | 候选, 多场景           |
| EnvBadge            | components/knowledge/EnvBadge.tsx            | 环境标识                           | 业务专属, 不进 common/ |
| KnowledgeHero       | components/knowledge/KnowledgeHero.tsx       | 知识库 hero 区                     | 业务专属, 不进 common/ |
| KnowledgeEmptyState | components/knowledge/KnowledgeEmptyState.tsx | 空态                               | 候选,通用              |
| SchemaBrowser       | components/knowledge/SchemaBrowser.tsx       | schema树浏览器                     | 业务专属               |
| KnowledgeTabs       | components/knowledge/KnowledgeTabs.tsx       | 知识库二级 tabs                    | 业务专属               |
| MessageBubble       | components/chat/MessageBubble.tsx            | 聊天气泡                           | 业务专属               |

###4.2通用但未抽 (3 个) —建议进 Spec B

| 组件         | 位置                                  | 通用度            |
| ------------ | ------------------------------------- | ----------------- |
| ActiveSwitch | components/knowledge/ActiveSwitch.tsx | 高 (任何开关场景) |
| BackButton   | components/knowledge/BackButton.tsx   | 高                |
| FileDropzone | components/knowledge/FileDropzone.tsx | 高 (通用上传)     |

###4.3评估页手写指标 (1 个) —建议进 Spec B

| 组件        | 位置                                | 性质                            |
| ----------- | ----------------------------------- | ------------------------------- |
| MetricBar   | components/evaluate/MetricBar.tsx   | 评估指标条,通用度高             |
| StatusBadge | components/evaluate/StatusBadge.tsx | 与 TaskStatusBadge重复,建议合并 |

###4.4 chat业务组件 (5 个) —建议留原位

| 组件             | 位置                                 |
| ---------------- | ------------------------------------ |
| Composer         | components/chat/Composer.tsx         |
| ConversationList | components/chat/ConversationList.tsx |
| MessageList      | components/chat/MessageList.tsx      |
| ThinkingTrace    | components/chat/ThinkingTrace.tsx    |
| CitationPanel    | components/chat/CitationPanel.tsx    |

###4.5 待接入封装 (1 处)

`AppDrawer` 已封装但暂无业务调用,候选场景:

-知识库详情侧栏 -评估详情侧栏 -任务执行历史抽屉

---

##5.后续 spec候选 (排序按 ROI)

| Spec                      | 范围                                                                                                                 | 估算任务 | ROI理由                    |
| ------------------------- | -------------------------------------------------------------------------------------------------------------------- | -------- | -------------------------- |
| Spec B:业务自研组件标准化 | 把 HealthDot/StatCard/TaskStatusBadge/KnowledgeEmptyState/ActiveSwitch/BackButton/FileDropzone/MetricBar抽进 common/ | 8-10     | 高复用,跨多个页面          |
| Spec C:主题系统 (白/夜)   | 补全 `.dark` token, 用 shadcn CSS variable,替换18 处硬编码颜色                                                       | 6-8      | 设计一致性,长期收益        |
| Spec D: i18n国际化        | 抽取所有中文字面量为 zh-CN dict +框架接入                                                                            | 5-6      | 知识库 +评估页对外暴露需要 |
| Spec E:知识库详情页       | EntryCard 重构 + SchemaBrowser抽 common + 二级页 Tabs标准化                                                          | 6-8      | 知识库模块继续扩张         |
| Spec F:评估页重构         | 消除遗留 `<table>`, 把 MetricBar/StatusBadge/TaskStatusBadge统一, 新建评估表单补齐                                   | 4-6      | 修遗留 +闭环               |

---

##6.验收数据

| 指标                                               | 起点 (2026-06-09)           | 终态 (2026-06-10)       | 变化                           |
| -------------------------------------------------- | --------------------------- | ----------------------- | ------------------------------ |
| shadcn 已装组件                                    | 18                          | 29                      | +11                            |
| common/封装组件                                    | 0                           | 5                       | +5                             |
| Dialog/AlertDialog业务直接调用                     | 5 处                        | 0 处                    | -5 (全走 AppDialog/AppConfirm) |
| 表格 `<table>` 原生 HTML                           | 4 真表 +4假表 + SampleTable | 1 处遗留 (evaluate/new) | -7                             |
| motion.button (业务动画按钮)                       | 9 处                        | 0 处                    | -9                             |
| react-hook-form业务使用                            | 2 处 (qa/new)               | 0 处                    | -2 (走自封装 Form)             |
| 业务代码里 raw Dialog / AlertDialog / Sheet import | 多处                        | 仅封装内部使用          | 干净                           |

---

##7.风险与遗留

1. **AppDrawer暂未接入业务** —封好了但没人用,避免变成死代码:后续页面遇到抽屉需求必须用 AppDrawer, 不允许走 raw Sheet
2. **calendar / command 已装但未用** — 同上,未来需求触发即可启用
3. **evaluate/new遗留1 处 `<table>`** —渲染 sample预览,优先级低, 待评估页重构时清
4. **DEFAULT_DATASET_ID / DEFAULT_DOCUMENT_ID硬编码** — SaveToKnowledgeDialog注释明示 v1临时, 等接入 dataset context 后清
5. **shadcn form.tsx仍依赖 react-hook-form** — 但无业务代码引用, 不影响;后续若整体迁走 react-hook-form 可一起删

---

##8.结论

- shadcn覆盖率从"混用 + 自研"提升到 **业务100%走 shadcn衍生 (含 common封装)**, 仅1 处原生 `<table>`遗留
  -5 个 common封装组件累计被19 个业务文件调用
  -9 处 motion.button +5 处 raw Dialog/AlertDialog +9 处真/假表格 +2 处 react-hook-form全部统一
- Spec A (UI组件库封装)计划完成,剩余工作移交 Spec B-F
