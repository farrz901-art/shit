# shadcn 化 + 抽封装大方案

**日期**: 2026-06-14
**状态**: 设计已批准, 待实施
**作者**: Claude (跟 user 讨论)

## Context

项目 [shadcn/ui](https://ui.shadcn.com/) 装得很全 (33 套件 in `components/ui/`), 项目自身也封装了 4 个 antd 风格组件 (`AppDialog` / `AppConfirm` / `AppDrawer` / `Form`+`FormItem`) + 3 个领域封装 (`DataTable` / `DataEmpty` / `FileDropzone`).

但 30+ 业务文件**没用这些封装**, 反而手写 `<input>`/`<select>`/`<table>`/`<div className="fixed inset-0 bg-black/50">`/`<form onSubmit>` 等等, 跟 shadcn 风格组件相比, 又冗长又 a11y 差. 同时 shadcn 原始组件调用方模板啰嗦 (Select 10 行模板, Checkbox 还要手拼), 跟 antd 风格 `options={[{value,label}]}` + `value` + `onChange` 一行调用不一致.

[[feedback-no-shim-no-minimal-changes]] 已经定调 "新项目零技术债", 但封装约定在 CLAUDE.md 缺位, 写新页不知道有封装可复用.

**Why**: 这次是 2026-06-10 一波抽封装 (`DataTable` / `AppDialog` / `Form` 等) 的**续**——封装已抽, 但**未迁移** + **未文档化**, 老页仍手写. 一次性扫清 + 加 CLAUDE.md 约定, 避免下次写页又走回手写老路.

## 目标

- 30+ 业务文件**全切到 shadcn 或项目自有封装**
- 抽 **5 个新 antd 风格封装** (`AppSelect` / `` / `` / `` / ``), 跟现有 `AppDialog` / `AppConfirm` 风格一致
- 抽 **3 个通用工具** (`ErrorBanner` / `CopyButton` / `FormField`), 16 处错误条 + 4 处 clipboard + 6 表单模板归一
- CLAUDE.md 加 3 段封装约定 (已有 + 新增 + 反模式)
- 净减 ~1500-2000 行
- 一致性: 错误条 / 复制按钮 / Dialog / 表单 / Select / Checkbox 行为全项目视觉一致

## 非目标

- 不换 antd 风格 `<Form>` 为 react-hook-form / shadcn Form (项目自有 antd 风格已经稳定, 升级保留, 不换库)
- 不动 chat (MessageBubble 等专属组件, 不是 shadcn 模板)
- 不动 `components/knowledge/*` 业务封装 (BackButton / KnowledgeHero 等自身已封装)
- 不动 `output/*` 业务客户端 (TaskDetailClient / OutputListClient) 内部结构, 只换错误条 / 复制按钮 / Select / Checkbox 部分
- 不重做 i18n (zh.json 缺 key 的就留 fallback)
- 不加 a11y 测试 (jsdom 测不到, 真实测要 Playwright + NVDA, 单独 follow-up)

## 现状扫描 (按违反模式, 全清单)

### 1. 手写 `<input>` (7 文件)
- `app/[locale]/login/page.tsx:48,59`
- `app/[locale]/forgot-password/page.tsx:54`
- `app/[locale]/reset-password/page.tsx:57,67`
- `app/[locale]/invite/[token]/page.tsx:84,95,105,117`
- `app/[locale]/admin/users/_components/CreateInviteDialog.tsx:95`
- `app/[locale]/evaluate/new/_components/EvaluateNewForm.tsx:137` (type="file")
- `app/[locale]/knowledge/triples/page.test.tsx:46,49` (测试 mock, 留)

### 2. 手写 `<select>` (0 文件)
- **0 处**, 但 AdminUsersTable kind 过滤是手写 `<select>`, 改用 `AppSelect`

### 3. shadcn `<Select>` 原始 6 行模板 (6 文件)
- `app/[locale]/submissions/_components/RejectDialog.tsx:66-77` (REASONS 列表)
- `components/knowledge/DatasetSwitcher.tsx:9-14, 27-50` (选 dataset)
- `components/knowledge/DomainSwitcher.tsx` (选 domain)
- `components/knowledge/SchemaFieldRenderer.tsx` (选 schema field type)
- `components/settings/settings-dialog.tsx` (语言/主题切换)
- (其他 `components/ui/select.tsx` 自身不算)

### 4. 手写 `<input type="checkbox">` (2 文件)
- `app/[locale]/admin/users/_components/CreateInviteDialog.tsx:105` (admin)
- `app/[locale]/knowledge/qa/_components/QASubmitForm.tsx:226` (SyncToNeo4j)

### 5. 手写 `<table>`/`<thead>`/`<tbody>` (3 文件)
- `app/[locale]/admin/users/_components/AdminUsersTable.tsx:87`
- `app/[locale]/admin/invites/_components/AdminInvitesTable.tsx:37`
- `app/[locale]/evaluate/new/_components/EvaluateNewForm.tsx:179` (CSV 预览)

### 6. 手写 Dialog 遮罩 (2 文件)
- `app/[locale]/admin/users/_components/CreateInviteDialog.tsx:49`
- `app/[locale]/admin/users/_components/ResetPasswordDialog.tsx:44`

### 7. 手写 `<form onSubmit>` (6 文件)
- login / forgot-password / reset-password / invite / CreateInviteDialog / ResetPasswordDialog
- (EvaluateNewForm / QASubmitForm 走项目自有 `<Form>` 或 server action, 留)

### 8. 手写 file input + dropzone label (1 文件)
- `EvaluateNewForm.tsx:136-156` (有项目自有 `<FileDropzone>`, 不用)

### 9. shadcn `<Textarea>` 直接用 (2 文件, 不抽)
- `app/[locale]/submissions/_components/RejectDialog.tsx:79`
- `app/[locale]/knowledge/qa/_components/QASubmitForm.tsx`
- (textarea 模板不长, 不强抽 antd 风格, **保留 shadcn 直接用**; 但纳入 `<FormField>` 包装)

### 10. destructive 错误条 16 处
- `app/[locale]/admin/users/_components/CreateInviteDialog.tsx:56`
- `app/[locale]/admin/users/_components/ResetPasswordDialog.tsx:50`
- `app/[locale]/invite/[token]/page.tsx:77`
- `app/[locale]/output/_components/OutputListClient.tsx:195`
- `app/[locale]/knowledge/triples/_components/TriplesForm.tsx:384`
- `app/[locale]/evaluate/new/_components/EvaluateNewForm.tsx:160, 204`
- `app/[locale]/knowledge/batch/page.tsx:142`
- `app/[locale]/decode/page.tsx:194`
- `app/[locale]/login/page.tsx:41`
- `app/[locale]/knowledge/documents/import/_components/ImportCommitCard.tsx:123`
- `app/[locale]/output/new/page.tsx:145`
- `app/[locale]/reset-password/page.tsx:52`
- `app/[locale]/knowledge/qa/_components/QASubmitForm.tsx:193` (条件 variant)
- `app/[locale]/output/[task_id]/[file]/page.tsx:64`
- `app/[locale]/output/[task_id]/_components/TaskDetailClient.tsx:156`

### 11. `navigator.clipboard` (4 文件)
- `CreateInviteDialog.tsx:72`
- `ResetPasswordDialog.tsx:66`
- `forgot-password/page.tsx:44`
- `decode/page.tsx:140`

### 12. `window.confirm()` (1 文件)
- `AdminInvitesTable.tsx:23` (有项目自有 `<AppConfirm>`, 不用)

---

## 整改文件全清单 (按优先级, 全部要改)

### P0: admin 4 文件 (用户点名, 价值最大)
| # | 文件 | 改动 |
|---|---|---|
| 1 | `app/[locale]/admin/users/_components/AdminUsersTable.tsx` | DataTable + AppSelect + Input + Pagination + AppConfirm + ErrorBanner |
| 2 | `app/[locale]/admin/invites/_components/AdminInvitesTable.tsx` | DataTable + AppConfirm + ErrorBanner |
| 3 | `app/[locale]/admin/users/_components/CreateInviteDialog.tsx` | AppDialog + AppInput +  + CopyButton + ErrorBanner + Form + FormField |
| 4 | `app/[locale]/admin/users/_components/ResetPasswordDialog.tsx` | AppDialog + CopyButton + ErrorBanner |

### P1: 6 表单切 Form + FormField
| # | 文件 | 改动 |
|---|---|---|
| 5 | `app/[locale]/login/page.tsx` | Form + FormField + ErrorBanner |
| 6 | `app/[locale]/forgot-password/page.tsx` | Form + FormField + ErrorBanner + CopyButton |
| 7 | `app/[locale]/reset-password/page.tsx` | Form + FormField + ErrorBanner |
| 8 | `app/[locale]/invite/[token]/page.tsx` | Form + FormField + ErrorBanner |

### P2: 业务组件 (扫尾)
| # | 文件 | 改动 |
|---|---|---|
| 9 | `app/[locale]/evaluate/new/_components/EvaluateNewForm.tsx` | FileDropzone + DataTable (CSV 预览) + ErrorBanner |
| 10 | `app/[locale]/knowledge/qa/_components/QASubmitForm.tsx` |  + ErrorBanner |
| 11 | `app/[locale]/decode/page.tsx` | ErrorBanner + CopyButton + AppToggle (cards/llm 切换) |
| 12 | `app/[locale]/submissions/_components/RejectDialog.tsx` | AppSelect (REASONS 列表) |

### P3: Select 用户侧 (5 文件切 AppSelect)
| # | 文件 | 改动 |
|---|---|---|
| 13 | `components/knowledge/DatasetSwitcher.tsx` | AppSelect |
| 14 | `components/knowledge/DomainSwitcher.tsx` | AppSelect |
| 15 | `components/knowledge/SchemaFieldRenderer.tsx` | AppSelect |
| 16 | `components/settings/settings-dialog.tsx` | AppSelect (语言/主题) |

### P4: 16 处 destructive 错误条 (Layer D 集中改)
| # | 文件 | 行 |
|---|---|---|
| 17 | `app/[locale]/output/_components/OutputListClient.tsx` | 195 |
| 18 | `app/[locale]/knowledge/triples/_components/TriplesForm.tsx` | 384 |
| 19 | `app/[locale]/knowledge/batch/page.tsx` | 142 |
| 20 | `app/[locale]/knowledge/documents/import/_components/ImportCommitCard.tsx` | 123 |
| 21 | `app/[locale]/output/new/page.tsx` | 145 |
| 22 | `app/[locale]/output/[task_id]/[file]/page.tsx` | 64 |
| 23 | `app/[locale]/output/[task_id]/_components/TaskDetailClient.tsx` | 156 |

(注: QASubmitForm line 193 条件 variant, 单独处理; 其他 8 个错误条跟上面合并到 P0/P1/P2 跟改)

---

## 架构

### 已存在 vs 新建 封装总清单 (5 个新封装 + 1 升级)

| 已有 (7) — 这次只迁移, 不改 | 待新建 (5) — 全要抽 |
|---|---|
| `<AppDialog>` (shadcn Dialog 包装) | **`<AppSelect>`** (shadcn Select 6 子件压 1 行 antd 风格) |
| `<AppConfirm>` (shadcn AlertDialog 包装) | **`<AppToggle>`** (shadcn ToggleGroup 单选, 替 decode view 切换按钮组) |
| `<AppDrawer>` (shadcn Sheet 包装, 业务没用) | **`<ErrorBanner>`** (shadcn Alert 包装, 5 variant) |
| `<Form>` + `<FormItem>` (项目自有, Zod, 升级) | **`<CopyButton>`** (clipboard + 反馈) |
| `<FileDropzone>` (react-dropzone 包装) | **`<FormField>`** (FormItem 升级 + 错误展示) |
| `<DataTable<T>>` (shadcn Table 包装) | |
| `<DataEmpty>` (shadcn Empty 包装) | |

**撤掉的 4 个 form 控件 (AppTextarea/AppCheckbox/AppSwitch/AppRadioGroup)**: 用户审视发现 shadcn `<Textarea>` / `<Checkbox>` / `<Switch>` / `<RadioGroup>` 本身就是 1 行, 不像 `<Select>` 那 6-行模板, 抽包装零收益. 业务直接用, 跟"AppDialog 包装 Radix 解决真啰嗦"标准一致: 只在 shadcn 调用方语法显著冗长时才抽.

### 新建 1 个 antd 风格 form 控件 + 4 个工具 详细 API

**1. `components/common/AppSelect.tsx`**

```typescript
interface AppSelectOption {
  value: string;
  label: string;            // 接受 ReactNode 也行, 跟 antd 一致
  disabled?: boolean;
}
interface AppSelectProps {
  options: AppSelectOption[];   // 必填, antd 风格
  value?: string;               // 受控
  defaultValue?: string;
  onChange?: (value: string) => void;
  placeholder?: string;
  disabled?: boolean;
  className?: string;
  dataTestid?: string;
}
```

内部: shadcn `<Select>` + `<SelectTrigger>` + `<SelectValue>` + `<SelectContent>` + `.map(options → <SelectItem>)`, 1 行调用.

对比现 shadcn 模板 (RejectDialog 10 行) → 改 1 行.



### 通用工具 3 个详细 API

**1. `components/common/ErrorBanner.tsx`**

```typescript
type ErrorBannerVariant = "destructive" | "warning" | "info" | "success" | "loading";
interface ErrorBannerProps {
  variant?: ErrorBannerVariant;     // 默认 "destructive"
  title?: string;
  description: string;              // 必填
  action?: ReactNode;               // 右侧放按钮 (例 "重试" / "复制")
  icon?: LucideIcon;                // variant=loading 强制 Loader2
  className?: string;
  dataTestid?: string;
}
```

内部走 shadcn `<Alert>` (已装) + `<AlertTitle>` + `<AlertDescription>`.

**2. `components/common/CopyButton.tsx`**

```typescript
interface CopyButtonProps {
  text: string;                     // 要复制的文本
  label?: string;                   // 默认 "复制"
  successLabel?: string;            // 默认 "已复制 ✓"
  variant?: "default" | "outline" | "ghost";
  size?: "default" | "sm" | "lg" | "icon";
  onCopied?: () => void;
  className?: string;
  dataTestid?: string;
}
```

**3. `components/common/FormField.tsx`**

```typescript
interface FormFieldProps {
  name: string;                     // 跟 Form.values 对应
  label: string;
  help?: string;                    // 提示文案
  required?: boolean;
  children: ReactNode;              // 实际 input (AppInput/AppSelect/...)
}
```

内部: shadcn `<Label>` (for) + `<div>` + `{children}` + 错误消息 (从 Form context 读 `errors[name]`) + `<p help>`. 6 表单模板用.

---

## 改动 Scope (按 Layer 顺序, 全清单)

### Layer A: 新基础设施 (5 封装 + 1 升级, 预计 5 commit)

- A1: `AppSelect` + `app-select.test.tsx` (5 case: render/onChange/disabled/placeholder/dataTestid)
- A2: `` + 单测 (3 case)
- A3: `` + 单测 (4 case)
- A4: `` + 单测 (3 case)
- A5: `` + 单测 (4 case)
- A6: `ErrorBanner` + 单测 (5 variant)
- A7: `CopyButton` + 单测 (mock clipboard)
- A8: 升级 `form-item.tsx` + 抽 `form-field.tsx` + 单测

预计 5 commit, 每个 lib 1 commit (`feat(ui)`).

### Layer B: admin 4 文件 (预计 2 commit, 半天)

- B1: `AdminUsersTable` + `AdminInvitesTable` (1 commit `refactor(admin): tables → DataTable`)
- B2: `CreateInviteDialog` + `ResetPasswordDialog` (1 commit `refactor(admin): dialogs → AppDialog`)

### Layer C: 6 表单切 Form + FormField (预计 2 commit, 半天)

- C1: `login` + `forgot-password` (1 commit `refactor(auth): login + forgot`)
- C2: `reset-password` + `invite/[token]` (1 commit `refactor(auth): reset + invite`)

### Layer D: 业务组件 (预计 4 commit, 1 天)

- D1: `EvaluateNewForm` (1 commit `refactor(evaluate): EvaluateNewForm`)
- D2: `QASubmitForm` (1 commit `refactor(qa): QASubmitForm`)
- D3: `decode/page.tsx` (1 commit `refactor(decode): ErrorBanner + CopyButton + AppToggle`)
- D4: 16 处 destructive 错误条 + 5 Select 用户侧切 AppSelect (1 commit `refactor(components): 21 处统一封装`)

### Layer E: 文档 (1 commit, 10 分钟)

- `packages/web/CLAUDE.md` 加 3 段约定:
  - 复用清单 (7 已有 + 5 新增)
  - 强制规则 (不许手写)
  - 反模式 (12 类)

---

## 总规模估算

- **~25 个文件改** (P0-P4 全清单)
- **~5 个新封装** (1 form 控件 + 4 工具) + 1 FormItem 升级
- **~20+ 测试更新** (5 新封装单测 + 业务 ~15 个 test 改断言)
- **~1500-2000 行净减**
- **预计 12 commit**, 按 Layer A→B→C→D→E 顺序

## 实施顺序 (5 阶段, 全做)

### 阶段 1: 5 新封装 + 1 升级 (预计 5 commit, 1 天)
- 一次到位, 5 commit 走完

### 阶段 2: admin 4 文件整改 (预计 2 commit, 半天)
- 用户点名优先

### 阶段 3: 6 表单 (预计 2 commit, 半天)

### 阶段 4: 业务组件 + 16 处错误条 + 5 Select 用户侧 (预计 4 commit, 1 天)

### 阶段 5: 文档 (1 commit)

## 风险 / 决策点

### 风险 1: `<AppDialog>` 切换 test 断言
切到 `<AppDialog>` (基于 shadcn `<Dialog>` Radix), 渲染在 `<div role="dialog">` 容器内, 现 `CreateInviteDialog.test.tsx` 断言 `getByTestId("create-invite-dialog")` 仍然过 (data-testid 保留), 但 ESC 关闭 / 焦点陷阱 / 背景滚动锁 test 没写. 接受遗留, 留 follow-up.

### 风险 2: `<Form>` 升级 FormItem
`<FormItem>` 升级接 shadcn `<Label>` + 错误展示, 现有 `<FormItem>` 调用方 1 个 (EvaluateNewForm line 198) 可能 break. 接受风险, 切完跑测验证.

### 风险 3: 16 处错误条改动量大但机械
全是 1:1 替换. 风险低, 警惕 QASubmitForm line 193 条件 variant (`clientError || !state.ok` 时 destructive, 否则 success) → ErrorBanner 也支持 variant prop, OK.

### 风险 4: `AdminUsersTable` 切 DataTable
DataTable 没原生搜索 / 过滤栏 prop. 改法: 外层包 Input + AppSelect, DataTable 只管表格本身. 不扩展 DataTable (YAGNI).

### 风险 5: 5 个 Select 用户侧切 AppSelect, 测试 mock 全要改
- `DatasetSwitcher.test.tsx` / `DomainSwitcher.test.tsx` / `SchemaFieldRenderer.test.tsx` / `settings-dialog.test.tsx` / `RejectDialog.test.tsx`
- 断言从 `getByRole("combobox")` 变 `getByTestId("select-trigger")` 或保持 role (shadcn Select 内部 `<SelectTrigger role="combobox">`, 改 AppSelect 后保留)
- 接受, 跑测验证

### 风险 6: 业务用 shadcn `<Badge>` 已经够, `<AppBadge>` 可能不必要
- 看 `components/knowledge/TaskStatusBadge.tsx` / `StatusBadge.tsx` 等已经封装 status 语义, 业务 `<Badge>` 散用少
- **决策点: AppBadge 这次不抽**, 业务用 shadcn `<Badge>` 直, 等真有重复再说

## 决策点 (实施前问)

1. **5 个新 form 控件全抽** (AppSelect), 还是只抽当前在用的 (AppSelect 不在用也抽, 留以后)?
2. **`<AppDrawer>` 这次不动** (业务没用, YAGNI), 接受 — 还是顺手扫一次所有 dialog 切?
3. **`<ErrorBanner>` variant 5 个** (destructive/warning/info/success/loading) 还是 2 个就够?
4. **`<CopyButton>` 失败走 sonner toast** 还是**console.warn 静默**?
5. **`<AppBadge>` 不抽**, 接受 — 还是抽?
6. **5 Select 用户侧 (DatasetSwitcher 等) 改在阶段 4** (跟 16 错误条合并) 还是**单独阶段 5**?

## 完成定义 (Definition of Done)

- [ ] Layer A 5 commit 全部入库, 5 个新/升级封装都有单测, vitest 跑过
- [ ] Layer B admin 4 文件全部切完, DataTable/AppDialog/AppSelect/CopyButton 全部用到
- [ ] Layer C 6 表单全部切 `<Form>` + `<FormField>`, 错误展示统一
- [ ] Layer D 16 处 destructive 错误条全部 `<ErrorBanner>`, 4 处 `navigator.clipboard` 全部 `<CopyButton>`, 5 Select 用户侧切 AppSelect, EvaluateNewForm / QASubmitForm / decode 扫尾
- [ ] Layer E CLAUDE.md 加 3 段约定
- [ ] 全项目 grep 反模式 0 命中 (12 类全 0)
- [ ] `bun run typecheck` 0 错
- [ ] 跑改过的文件 vitest (按 [[feedback-no-full-vitest-during-dev]], **不**跑全量)
- [ ] Playwright spot-check: login / forgot-password / admin/users / admin/invites / evaluate/new / decode / qa / submissions 8 页打开 0 errors
- [ ] 净减行数 ≥ 1500 行 (commit message 里报告实际)
- [ ] 全部 commit 各自跑 pre-commit (lint-staged + tsgo + vitest changed) 全绿

## 关联

- [[feedback-no-shim-no-minimal-changes]] — 严禁 shim/兼容, 这次要清的就是 30+ 文件的 "不知有封装" 隐性技术债
- [[feedback-no-full-vitest-during-dev]] — 阶段 1-4 实施时只测改过的, 不跑全量
- [[feedback-commit-in-batches-for-large-changes]] — 12 commit 按 Layer A→B→C→D→E 拆
- [[feedback-react-file-size-and-dialog-naming]] — CreateInviteDialog / ResetPasswordDialog 已抽为独立 component, 符合
- [[feedback-record-errors-and-lessons]] — 实施时遇错记到 memory
- `packages/web/CLAUDE.md` 表格组件约定 (2026-06-14) — 这次扩展 3 段封装约定
