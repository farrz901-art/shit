# shadcn 迁移 Batch 2 + 批量出口 (components/lib barrel)

**日期**: 2026-06-14
**状态**: 待批准
**范围**: 19 个业务文件 shadcn 重构 + 13 个 index.ts 批量出口 + 19 文件改走 barrel
**关联**: `web/CLAUDE.md` 封装组件表 (2026-06-14) + Sprint shadcn 1-2 (前 2 轮修了 7 个)

## Context

CLAUDE.md (2026-06-14) 列了 7+5 共 12 个封装组件 (`<AppDialog>`, `<AppConfirm>`, `<Form>`, `<FileDropzone>`, `<DataTable>`, `<DataEmpty>`, `<AppSelect>`, `<AppToggle>`, `<ErrorBanner>`, `<CopyButton>`, `<FormField>`, `<SubmitButton>`) + 反模式表 (手写 `<input>`/`<button>`/`<form onSubmit>`/`<table>`/`<select>` 等要替换).

前 2 轮 Sprint (commits `becb825` `206027d`) 修了 7 个文件. 用户 2026-06-14 提"还有大量漏改", 全量扫描后**剩 19 文件需改** (含 5 文件含 confirm/alert).

第二诉求: 跟 shadcn `components/ui/*` 一样, 在 `components/{auth,chat,common,evaluate,i18n,knowledge,settings}/index.ts` 和 `lib/{api,chat,dom,evaluate,store,test-utils}/index.ts` (lib/theme 已存在) 加批量出口, 外部引用 `from "@/components/knowledge"` 代替 `from "@/components/knowledge/StatCard"`.

## 全量扫描结果

排除 `components/ui/*` (shadcn) + `.test.*` + `.stories.*` 后, 4 类反模式涉及 19 文件:

### A. 原生 HTML 元素 — 19 文件 (全待改, 之前 2 轮修了 7 个其他文件)

| 文件 | 原生元素 | 替换为 | 状态 |
|------|----------|--------|------|
| `app/[locale]/admin/users/_components/AdminUsersTable.tsx` | `<button>` × 2 | `<Button>` | 待改 |
| `app/[locale]/admin/users/_components/CreateInviteDialog.tsx` | `<Input>`, `<Button>` | shadcn (已部分改, 实施前 diff) | 待改 |
| `app/[locale]/admin/users/_components/ResetPasswordDialog.tsx` | `<Input>`, `<Button>`, `<label>` | shadcn (已部分改, 实施前 diff) | 待改 |
| `app/[locale]/error.tsx` | `<button>` 重置 | `<Button>` | 待改 |
| `app/[locale]/forgot-password/page.tsx` | `<label>`, `<Input>`, `<Button>` | shadcn | 待改 |
| `app/[locale]/invite/[token]/page.tsx` | `<Input>` × 4, `<Button>`, `<label>` × 4 | shadcn | 待改 |
| `app/[locale]/knowledge/batch/page.tsx` | `<button>` (新增发现) | `<Button>` | 待改 |
| `app/[locale]/knowledge/documents/import/_components/ImportCommitCard.tsx` | `<button>`, `<input>`, `<label>` | shadcn | 待改 |
| `app/[locale]/knowledge/qa/_components/QASubmitForm.tsx` | `<Input>`, `<Button>`, `<label>` | shadcn | 待改 |
| `app/[locale]/knowledge/triples/_components/TriplesForm.tsx` | `<Input>`, `<Button>`, `<label>` | shadcn | 待改 |
| `app/[locale]/login/page.tsx` | `<label>`, `<Input>`, `<Button>` | shadcn | 待改 |
| `app/[locale]/output/[task_id]/_components/TaskDetailClient.tsx` | `<form>`, `<button>` × 2 | `<Button>` | 待改 |
| `app/[locale]/output/_components/OutputListClient.tsx` | `<button>` | `<Button>` | 待改 |
| `app/[locale]/output/new/page.tsx` | `<input type="file">` (新增发现) | shadcn `<Input>` 或项目 `<FileDropzone>` | 待改 |
| `app/[locale]/reset-password/page.tsx` | `<Input>`, `<label>`, `<Button>` | shadcn | 待改 |
| `app/global-error.tsx` | `<button>` 重置 | **保留 inline style** (用户决策) | 跳过 |
| `components/UserMenu.tsx` | `<details>/<summary>`, `<button>` | shadcn `<DropdownMenu>` + `<Button>` | 待改 |
| `components/chat/ConversationList.tsx` | `<button>` × 1 (新增发现) | `<Button variant="ghost" size="icon">` | 待改 |
| `components/common/form-field.tsx` | `<label>` (项目自有 `<FormField>`, 内部渲染) | 检查现状 | 待改 |
| `components/knowledge/ErrorBoundary.tsx` | `<button>` 重试 | `<Button variant="link">` | 待改 |
| `components/common/form/form.tsx` | (项目自有 `<Form>`, 排除) | — | 跳过 |
| `components/knowledge/FileDropzone.tsx` | (项目自有 `<FileDropzone>`, 内部用 `<label>`, 排除) | — | 跳过 |

### B. `confirm()` / `window.alert()` — 5 文件

| 文件 | 调用 | 替换为 |
|------|------|--------|
| `app/[locale]/admin/invites/_components/AdminInvitesTable.tsx` (跟 A 重叠) | `confirm()` 1 处 | `<AppConfirm>` 弹框 |
| `app/[locale]/admin/users/_components/AdminUsersTable.tsx` | `confirm()` 1 处 | `<AppConfirm>` 弹框 |
| `app/[locale]/evaluate/[id]/_components/RunDetailView.tsx` | `confirm()` × 2, `alert()` × 1 | `<AppConfirm>` + toast (shadcn `sonner`) |
| `app/[locale]/output/[task_id]/_components/TaskDetailClient.tsx` | `window.alert()` 1 处 | `<ErrorBanner variant="destructive">` 渲染 (页内, 不弹窗) |
| `app/[locale]/output/_components/OutputListClient.tsx` | `window.alert()` 1 处 | `<ErrorBanner variant="destructive">` 渲染 |

### C. `<details>/<summary>` — 3 文件

| 文件 | 替换为 |
|------|--------|
| `components/UserMenu.tsx` | shadcn `<DropdownMenu>` (UserMenu 重做) |
| `app/[locale]/knowledge/batch/page.tsx` | 检查是否要 DropdownMenu (还是展开式) |
| `app/[locale]/health/_components/HealthClient.tsx` | 同上 |

### D. `<form onSubmit={...}>` — 3 文件 (1 排除)

| 文件 | 替换为 |
|------|--------|
| `app/[locale]/decode/page.tsx` | 项目 `<Form>` + Zod (走 server action 模式) |
| `app/[locale]/submissions/_components/ApprovalRow.tsx` | 项目 `<Form>` + Zod |
| `components/common/form/form.tsx` | (项目自有 `<Form>`, 排除) |

**合计**: A 19 文件 + B 5 文件 (全跟 A 重叠, 无新增) + C 1 文件 (UserMenu 跟 A 重叠) + D 2 文件 (decode + ApprovalRow 跟 A 不重叠).

**真实改动文件: 19 个** (A 19 含 B/C 重叠, D 多 2 个 = 21 待改位置, 跟 19 文件去重后还是 19).

**之前 Sprint 1-2 已修的 7 文件 (排除)**: ResetPasswordDialog (部分), DecodeInputBar, knowledge/batch 部分, ImportCommitCard 部分, login 部分, invite/[token] 部分, output/new 部分.

注: 上表 `ResetPasswordDialog/CreateInviteDialog/knowledge/batch/ImportCommitCard/login/invite/[token]/output/new` 列在"待改"是 baseline 扫描命中 (有残余反模式), Sprint 1-2 已改了一部分; 实施前要 diff 确认.

## 关键设计

### 1. shadcn 替换规则 (跟 Sprint 1-2 一致)

| 反模式 | 替换为 |
|--------|--------|
| `<input type="text\|email\|password\|number">` | shadcn `<Input>` |
| `<button type="button\|submit">` | shadcn `<Button variant="outline\|ghost\|destructive" size="sm\|icon">` |
| `<label>` | shadcn `<Label>` |
| `<form onSubmit={handler}>` | 项目 `<Form>` + Zod (Form 走 server action 时保留 `<form action={action}>`) |
| `<select>` | shadcn `<Select>` 或项目 `<AppSelect>` |
| `confirm(msg)` | 项目 `<AppConfirm>` (弹框) |
| `alert(msg)` | `<ErrorBanner variant="destructive">` (页内) 或 `toast.error()` (shadcn sonner) |
| `<details>/<summary>` | shadcn `<DropdownMenu>` 或 `<Collapsible>` |
| `<table>/<thead>/<tr>` | 项目 `<DataTable>` (CLAUDE.md 强制) |
| `<div className="fixed inset-0 ...">` (Dialog 遮罩) | 项目 `<AppDialog>` |
| `navigator.clipboard.writeText` | 项目 `<CopyButton>` |
| `<div className="border-destructive/30 ...">` (错误条) | 项目 `<ErrorBanner>` |

### 2. `<Form>` / `<FormField>` 适配

CLAUDE.md 表说"表单 → `<Form>` + `<FormField>` 包装每字段". 但 `<Form>` 项目自有 (`components/common/form/form.tsx`), 用 Zod. 改 5 个 form (decode/submissions) 时:
- 简单表单 (1-2 字段, 一次性) → 项目 `<Form>` + Zod schema
- 复杂表单 (QASubmitForm / TriplesForm) → 检查现状, 可能保持手写 useState (form 行增删逻辑复杂, Form 不太适合)

不强制所有 form 用 `<Form>`, 跟 QASubmitForm / TriplesForm 现状评估.

### 3. Confirm/Alert 决策

| 文件 | confirm/alert | 改法 |
|------|---------------|------|
| `AdminInvitesTable` | 撤回确认 | `<AppConfirm>` 弹框 |
| `AdminUsersTable` | 切换 admin 确认 | `<AppConfirm>` 弹框 |
| `RunDetailView` | 取消/删除评估确认 | `<AppConfirm>` 弹框 |
| `RunDetailView` | 删除失败反馈 | `toast.error()` (sonner) |
| `OutputListClient` | 下载失败反馈 | `<ErrorBanner variant="destructive">` 渲染在 list 上方 |
| `TaskDetailClient` | 取消/下载失败反馈 | `<ErrorBanner>` 渲染 (跟 RunDetailView 一致) |

**统一规则**: 二次确认 → `<AppConfirm>` 弹框; 失败反馈 (页内停留) → `<ErrorBanner>`; 失败反馈 (瞬时消失) → `toast`.

### 4. DropdownMenu (UserMenu)

`<details>/<summary>` → shadcn `<DropdownMenu>`. 项目 `components/ui/dropdown-menu.tsx` 已装, 不用新装. 改后:
- trigger: `<DropdownMenuTrigger asChild><Button variant="ghost">...</Button></DropdownMenuTrigger>`
- 内容: `<DropdownMenuContent><DropdownMenuItem>...</DropdownMenuItem></DropdownMenuContent>`

**例外**: `app/[locale]/knowledge/batch/page.tsx` 和 `app/[locale]/health/_components/HealthClient.tsx` 的 `<details>` 是展开式 (折叠面板), 改 shadcn `<Collapsible>` (项目已装, 不用新装).

### 5. barrel 批量出口 (Part 2)

**13 个 index.ts** (7 个 components + 6 个 lib - 1 lib/theme 已存在 = 12 新建 + 1 已存在, 简称 13):

#### components/

| index.ts | 包含文件 |
|----------|----------|
| `components/auth/index.ts` | `AuthBootstrap` |
| `components/chat/index.ts` | `ChatShell`, `CitationPanel`, `Composer`, `ConversationList`, `MessageBubble`, `MessageFeedback`, `MessageList`, `ThinkingTrace` |
| `components/common/index.ts` | 顶层 8 (`DataEmpty`, `app-select`, `app-toggle`, `copy-button`, `error-banner`, `form-field`, `submit-button`) + 5 sub-dir (`confirm`, `data-table`, `dialog`, `drawer`, `form`) |
| `components/evaluate/index.ts` | `MetricBar`, `SampleTable`, `StatusBadge`, `strip-think` |
| `components/i18n/index.ts` | `LocalizedLink` |
| `components/knowledge/index.ts` | 16 文件 (ActiveSwitch, BackButton, DatasetSwitcher, DomainSwitcher, EntryCard, EnvBadge, ErrorBoundary, FileDropzone, HealthDot, KnowledgeEmptyState, KnowledgeHero, KnowledgeTabs, SchemaBrowser, SchemaFieldRenderer, StatCard, TaskStatusBadge) |
| `components/settings/index.ts` | `settings-dialog`, `theme-toggle` |

#### lib/

| index.ts | 包含文件 |
|----------|----------|
| `lib/api/index.ts` | 14 (approvals, auth, auth.server, chat, config, errors, evaluate, health, ingest, knowledge, query-client, queryKeys, rsc-queries, system) |
| `lib/chat/index.ts` | 5 (dify, factory, openai, storage, types) |
| `lib/dom/index.ts` | 1 (download) |
| `lib/evaluate/index.ts` | 2 (headers, types) |
| `lib/store/index.ts` | 2 (app-data, app-store) |
| `lib/test-utils/index.ts` | 1 (intl-wrapper) |

**跳过** (根文件, 不为根目录建 index):
- `components/UserMenu.tsx`, `components/header.tsx`, `components/theme-provider.tsx`
- `lib/utils.ts`, `lib/dify-datasets.ts`, `lib/parse-eval-csv.ts`, `lib/parse-excel.ts`, `lib/parse-json.ts`, `lib/schema-types.ts`, `lib/motion.ts`
- `lib/theme/index.ts` (已存在)

#### barrel 模板

```ts
// 例: components/knowledge/index.ts
export * from "./ActiveSwitch";
export * from "./BackButton";
// ... 一行一个, 按字母序
```

```ts
// 例: components/common/index.ts
export * from "./DataEmpty";
export * from "./app-select";
// ... 顶层
export * from "./confirm";
export * from "./data-table";
// ... sub-dir 整包
```

**排除规则**: `.test.tsx` / `.test.ts` / `.stories.tsx` 不 export (测试/storybook 文件不进 barrel).

### 6. 引用改造

**改 19 文件 (shadcn 重构后, 跟 A 表 19 文件对齐) 的 import, 走 barrel**:

```ts
// Before
import { TaskStatusBadge } from "@/components/knowledge/TaskStatusBadge";
import { BackButton } from "@/components/knowledge/BackButton";
import { FileDropzone } from "@/components/knowledge/FileDropzone";

// After
import { TaskStatusBadge, BackButton, FileDropzone } from "@/components/knowledge";
```

```ts
// Before
import { ApiError } from "@/lib/api/errors";
import { apiFetch } from "@/lib/api/config";

// After
import { ApiError, apiFetch } from "@/lib/api";
```

**不改** 96+158 个其他文件 (渐进改, 不全仓 sweep). 跟 Sprint 1-2 策略一致: 改一处扫一处, 不批量.

### 7. 风险 / 不做

- **不做** `components/index.ts` / `lib/index.ts` (跟 shadcn 风格, 不污染根目录)
- **不做** codegen barrel (手写, 13 文件可控, 自动 codegen 易漏)
- **不做** 全仓 import 改写 (改 N 文件 + 跑全量 1+ 分钟 vitest, 风险收益比低)
- **不强制**所有 form 用 `<Form>` 包装 (QASubmitForm / TriplesForm 业务逻辑复杂, 评估现状决定)
- **不改** shadcn `components/ui/*` (已是最简 import)
- **不改** 已 barrel 的 `lib/theme`
- **保留** `global-error.tsx` inline style (用户决策, 根 layout 崩溃无 ThemeProvider context)

### 8. Commit 拆分 (按 memory `feedback-commit-in-batches-for-large-changes`)

| # | 范围 | 文件数 | 风险 |
|---|------|--------|------|
| 1 | shadcn: error UI 类 (ErrorBoundary + app/[locale]/error.tsx) | 2 | 低 |
| 2 | shadcn: 表单类 (forgot-password, invite/[token], login, reset-password, QASubmitForm, TriplesForm, ImportCommitCard, ResetPasswordDialog, CreateInviteDialog) | 9 | 中 (form 重构) |
| 3 | shadcn: 列表/业务类 (OutputListClient, TaskDetailClient, AdminInvitesTable, AdminUsersTable, RunDetailView) | 5 | 中 (confirm/alert 替换) |
| 4 | shadcn: UserMenu (DropdownMenu 引入) | 1 | 中 (新模式) |
| 5 | barrel: 7 components index.ts | 7 | 低 (新增) |
| 6 | barrel: 6 lib index.ts | 6 | 低 (新增) |
| 7 | 19 文件 import 改走 barrel (合并 #1-6 改 import) | 19 | 中 (改 path) |

**或者合并**: 1-4 合并为 "shadcn: 全量替换" 单个 commit, 5-6 合并为 "barrel: 13 index.ts" 单个 commit, 7 单独. 总共 3 commit.

### 9. 验证

每 commit 后:
1. `bun run typecheck` (0 错误)
2. `bun run test -- <pattern>` (改的文件 + related)
3. `bun run lint <files>` (oxlint, warning 不阻塞, error 必须修)
4. pre-commit 钩子跑 lint-staged + tsc + vitest --changed; vitest 失败 4 个 unhandled rejection 模式已知, 跟之前一样 `--no-verify` + 文档化

### 10. 文档更新

- `web/CLAUDE.md` "封装组件 (2026-06-14)" 节加一行: "批量出口: components/{dir}/index.ts + lib/{dir}/index.ts 走 barrel, 跨子目录 1 行 import"
- 17 个有 `.test.tsx` 的文件, import 改后跑 `bun run test -- <filename>` 验证 selector 仍命中

## 关键代码例子

### 例子 1: barrel import 改 (QASubmitForm 或 AdminUsersTable)

**Before** (`app/[locale]/admin/invites/_components/AdminInvitesTable.tsx`):
```ts
import { Button } from "@/components/ui/button";
import { CopyButton } from "@/components/common/copy-button";
import { LocalizedLink } from "@/components/i18n/LocalizedLink";
import { apiFetch } from "@/lib/api/config";
import { ApiError } from "@/lib/api/errors";
import { qKeys } from "@/lib/api/queryKeys";
import { useConfirm } from "@/components/common/confirm/app-confirm";
```

**After** (按钮 + confirm 都换 shadcn, 走 barrel):
```ts
import { Button } from "@/components/ui/button";
import { CopyButton, useConfirm } from "@/components/common";
import { LocalizedLink } from "@/components/i18n";
import { apiFetch, ApiError, qKeys } from "@/lib/api";
```

### 例子 2: confirm() 替 AppConfirm (RunDetailView)

**Before**:
```tsx
async function onDelete() {
  if (!confirm(t("确认删除这次评估?"))) {
    return;
  }
  const result = await deleteRun(String(run.id));
  if (result.ok) {
    router.push("/evaluate");
  } else {
    alert(result.error);
  }
}
```

**After**:
```tsx
import { toast } from "sonner";
import { AppConfirm } from "@/components/common/confirm/app-confirm";

const { confirm } = useConfirm();

async function onDelete() {
  const ok = await confirm({
    title: t("确认删除这次评估?"),
    description: t("该评估的所有结果将被永久删除, 不可恢复。"),
    variant: "destructive",
  });
  if (!ok) return;
  const result = await deleteRun(String(run.id));
  if (result.ok) {
    router.push("/evaluate");
  } else {
    toast.error(result.error);
  }
}

// JSX 末尾
<AppConfirm />  // hook 配套, 全局挂一份
```

### 例子 3: DropdownMenu 替 details/summary (UserMenu)

**Before**:
```tsx
<details className="relative" data-testid="user-menu">
  <summary className="cursor-pointer rounded-md border border-border bg-card px-3 py-1.5 text-sm">
    {user.display_name ?? user.email}
  </summary>
  <div className="absolute right-0 mt-2 w-48 space-y-1 rounded-md border border-border bg-card p-2 shadow-lg">
    {user.is_admin && (
      <Link href="/admin/users" ...>用户管理</Link>
    )}
    <Link href="/">账号设置</Link>
    <form action={logoutAction}>
      <button type="submit">登出</button>
    </form>
  </div>
</details>
```

**After**:
```tsx
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";

<DropdownMenu>
  <DropdownMenuTrigger asChild>
    <Button variant="ghost" size="sm" data-testid="user-menu">
      {user.display_name ?? user.email}
      <ChevronDown className="ml-1 h-3 w-3" />
    </Button>
  </DropdownMenuTrigger>
  <DropdownMenuContent align="end" className="w-48">
    {user.is_admin && (
      <DropdownMenuItem asChild>
        <Link href="/admin/users" data-testid="menu-admin-users">{t("用户管理")}</Link>
      </DropdownMenuItem>
    )}
    <DropdownMenuItem asChild>
      <Link href="/">{t("账号设置")}</Link>
    </DropdownMenuItem>
    <DropdownMenuSeparator />
    <DropdownMenuItem asChild>
      <form action={logoutAction}>
        <button type="submit" data-testid="menu-logout" className="w-full text-left">
          {t("登出")}
        </button>
      </form>
    </DropdownMenuItem>
  </DropdownMenuContent>
</DropdownMenu>
```

### 例子 4: 原生 button → shadcn (AdminUsersTable)

**Before**:
```tsx
<button
  type="button"
  onClick={() => onToggleAdmin(row)}
  className="rounded-md border border-border/60 px-2 py-0.5 text-xs hover:bg-muted/30"
>
  {row.is_admin ? t("取消 admin") : t("设为 admin")}
</button>
```

**After**:
```tsx
<Button
  type="button"
  variant="outline"
  size="sm"
  onClick={() => onToggleAdmin(row)}
>
  {row.is_admin ? t("取消 admin") : t("设为 admin")}
</Button>
```

### 例子 5: ErrorBanner 替 alert (OutputListClient)

**Before**:
```tsx
const onDownload = async (taskId: string) => {
  // ...
  try {
    const { blob, filename } = await ingestApi.taskDownload(taskId);
    triggerBrowserDownload(blob, filename);
  } catch (error) {
    const msg = error instanceof ApiError || error instanceof NetworkError ? error.message : String(error);
    window.alert(t("下载失败: {msg}", { msg }));
  }
};
```

**After**:
```tsx
const [downloadError, setDownloadError] = useState<string | null>(null);

const onDownload = async (taskId: string) => {
  // ...
  try {
    const { blob, filename } = await ingestApi.taskDownload(taskId);
    triggerBrowserDownload(blob, filename);
    setDownloadError(null);
  } catch (error) {
    const msg = error instanceof ApiError || error instanceof NetworkError ? error.message : String(error);
    setDownloadError(t("下载失败: {msg}", { msg }));
  }
};

// JSX 顶部
{downloadError && (
  <ErrorBanner variant="destructive" description={downloadError} onDismiss={() => setDownloadError(null)} />
)}
```

## 验收

- [ ] 19 文件 shadcn 重构完, 全量 `bun run typecheck` 0 错误
- [ ] 13 index.ts 落盘, vitest 全量 547+ 测试通过
- [ ] 19 文件 import 走 barrel, 同名 export 不冲突
- [ ] 没用 `<input>`/`<button>` (shadcn Button 例外)/`<label>`/`<form onSubmit>`/`<details>`/`<table>`/`<select>` 6 类反模式 (除已知例外: `<details>` Collapsible, `<Form>` form 内部)
- [ ] **全量 grep 验证** (改后跑, 期望 0 命中):
  ```bash
  # 排除 components/ui/* (shadcn) + components/common/form/* (项目 Form) + components/knowledge/FileDropzone + 已知 4 例外
  grep -rE '<input |<button |<label |<select |<textarea |<table |<thead |<tbody |<tr |<th |<td ' app/ components/ \
    --include='*.tsx' --include='*.ts' \
    | grep -v 'components/ui/' \
    | grep -v 'components/common/form/' \
    | grep -v 'FileDropzone' \
    | grep -v '\.test\.' \
    | grep -v '\.stories\.'
  ```
  跟 `confirm(` / `window.alert(` 同样 0 命中. 若有, 列出来逐个修.
- [ ] pre-commit `--no-verify` 3 commit, 后续 lint-cleanup commit 单独提
