# A2 TS Page/Component Audit — 13 files (`packages/web/app/`, `packages/web/components/`)

扫描日期: 2026-07-10
扫描工具: 只读 (Read / Grep / Bash wc -l)
库状态基准:
- React 19.2.7 / Next.js 16.2.10 (package.json:65-68)
- TypeScript 7.0.2 (package.json:107)
- shadcn 全套已装 (components/ui/ 下 35 个组件, 含 table / dialog / select / radio-group / toggle-group / tooltip / sonner 等)
- 项目封装 (`components/common/`): AppDialog / AppConfirm / AppDrawer / AppSelect / AppToggle / AppRadioGroup / ErrorBanner / CopyButton / AppTooltip / FileDropzone / DataTable / DataEmpty / FormField

每个文件一节, 行数降序, 严格 7 段模板.

---

### `app/[locale]/admin/pre-analysis/_components/pre-analysis-upload-dialog.tsx` (479 行)

**1. 拆分点**:
- L1-184 `useUploadState` 状态子 hook (8 state + reset effect + paramKeys 计算) -> `_hooks/use-upload-state.ts` (hook)
- L186-257 `useUploadHandlers` handler 子 hook (open/clear/upload + reset + toast) -> `_hooks/use-upload-handlers.ts` (hook)
- L259-296 `renderParamInput` 当前未用, export 保留 -> `_lib/render-param-input.tsx` (纯函数) [2026-07-09 注: UI 隐藏但导出保留, 拆走便于后续放开时单测]
- L298-478 `PreAnalysisUploadDialog` 主组件 (3 段式 JSX: dropzone/file-info/advanced-options) -> 留当前文件 (主组件, 已靠 hook 抽瘦)
- 副组件拆: L381-475 高级选项区 (backend radio + flavor description + chapter config L432-475) -> `advanced-options-section.tsx` (component)
- 副组件拆: L450-474 LLM 增强开关 -> `llm-refinement-toggle.tsx` (component)

**2. 纯函数/hook 化**:
- 可拆:
  - `getCamelotParamKeys(flavor)` L79-92 已模块级纯函数, OK
  - `BACKEND_OPTIONS` / `FLAVOR_OPTIONS` / `STRATEGY_OPTIONS` / `LEVEL_OPTIONS` 常量字典 L40-124 模块级, OK
  - `useUploadState` L145-183 已抽 hook, OK
  - `useUploadHandlers` L189-257 已抽 hook, OK
- 不可拆: 无 (主组件 JSX 已经被 3 段拼装, 但每段都可单独抽小组件)

**3. 库替代**:
- shadcn `<Table>` 已装 (components/ui/table) 但本文件没用 table, 用 Form/Dialog/Select/RadioGroup
- 无 — 表单 + Dialog + RadioGroup 都是现成的, 项目封装 AppDialog / AppRadioGroup / AppSelect / AppTooltip / FileDropzone / Switch / Label / Input 已 100% 用

**4. 对象替 if**:
- L104-115 `FLAVOR_OPTIONS` / L110-115 `STRATEGY_OPTIONS` / L118-124 `LEVEL_OPTIONS` 已是数组, OK
- L79-92 `getCamelotParamKeys` if 链 -> 可改 `flavorParamKeyMap: Record<string, string[]>` + `flavorParamKeyMap[flavor] ?? baseKeys`, 但链只有 4 分支, ROI 低, 留 if 链

**5. 数组替循环**:
- 无显式 for 循环, 已 .map() / .filter() / 数组迭代

**6. 预计减少**: 479 -> 主文件 ~250 (-48%); 拆到 5 个文件: use-upload-state.ts (~50), use-upload-handlers.ts (~80), render-param-input.tsx (~50), advanced-options-section.tsx (~110), llm-refinement-toggle.tsx (~40)

**7. 骨架伪代码**:
- `_hooks/use-upload-state.ts`:
```ts
import { useState, useEffect } from "react";
type TableBackend = "pymupdf" | "camelot" | "pdfplumber";

export const useUploadState = (): {
  pickedFile: File | null;
  setPickedFile: (file: File | null) => void;
  isUploading: boolean;
  setIsUploading: (val: boolean) => void;
  uploadError: string | null;
  setUploadError: (val: string | null) => void;
  backend: TableBackend;
  setBackend: (val: TableBackend) => void;
  params: Record<string, string | number>;
  setParams: (val: Record<string, string | number>) => void;
  paramKeys: string[];
  chapterMaxLevel: number;
  setChapterMaxLevel: (val: number) => void;
  enableLlmRefinement: boolean;
  setEnableLlmRefinement: (val: boolean) => void;
} => { /* 当前 L146-183 内容 */ };
```

- `advanced-options-section.tsx`:
```tsx
import { Label } from "@/components/ui/label";
import { AppRadioGroup } from "@/components/common/input";
import { AppSelect } from "@/components/common/input";
import { Switch } from "@/components/ui/switch";
import { AppTooltip } from "@/components/common/overlay/app-tooltip";
import { HelpCircle } from "lucide-react";

export function AdvancedOptionsSection(props: {
  backend: TableBackend;
  onBackendChange: (val: TableBackend) => void;
  chapterMaxLevel: number;
  onChapterMaxLevelChange: (val: number) => void;
  enableLlmRefinement: boolean;
  onEnableLlmRefinementChange: (val: boolean) => void;
  translate: (key: string, params?: Record<string, string | number>) => string;
}): JSX.Element;
```

---

### `app/[locale]/admin/users/_components/admin-users-table.tsx` (438 行)

**1. 拆分点**:
- L43-55 `buildRoleOptions` 纯函数 (48% 是这个组件辅助) -> 留, 模块级小函数, 可挪到 `_lib/role-options.ts`
- L57-62 `getAdminActionLabel` 纯函数 (提权/降权) -> `_lib/action-labels.ts`
- L63-68 `getActiveActionLabel` 纯函数 (启用/禁用) -> `_lib/action-labels.ts`
- L86-96 `renderRoleSelect` 渲染角色下拉 (4 props) -> `role-select.tsx` (component)
- L98-115 `renderKindBadge` 渲染账号/anon Badge (3 props) -> `kind-badge.tsx` (component)
- L117-134 `renderActiveBadge` 渲染启用/禁用 Badge (3 props) -> `active-badge.tsx` (component)
- L136-194 `renderActionButtons` 渲染 3 个操作按钮 (7 props, 39 行) -> `action-buttons.tsx` (component)
- L196-206 `getResetDescription` 纯函数 -> `_lib/reset-description.ts`
- L208-295 `buildColumns` 列定义 (88 行, 7 列) -> 留当前文件, 太耦合 props
- 副组件: L385-437 `AdminUsersTable` 主组件 JSX -> 留, 已经较瘦
- 子组件: `UserFilters` 已经抽到独立文件 `user-filters.tsx`, OK

**2. 纯函数/hook 化**:
- 可拆:
  - L43-55 `buildRoleOptions` -> 模块级, 已 OK
  - L57-68 两个 label getter -> 模块级, 已 OK
  - L196-206 `getResetDescription` -> 模块级, 已 OK
- 不可拆: 列定义 (L208-295) 需要 7 props, 拆出去 props 传递成本 > 模块内

**3. 库替代**:
- shadcn `<Table>` 已装 (components/ui/table), 已经用项目封装 `DataTable<T>` + `DataEmpty`
- shadcn `<Badge>` 已装 (components/ui/badge.tsx), 已用
- 项目封装 `AppConfirm` (components/common/confirm) 已用, OK
- 项目封装 `AppSelect` (components/common/input) 已用, OK
- 项目封装 `ErrorBanner` (components/common/feedback) 已用, OK
- 无

**4. 对象替 if**:
- L103-114 `renderKindBadge` 内 if/else 串 badgeVariant + label -> 可改 `KIND_LABEL: Record<AdminUser["kind"], { label, variant }>` 查表
- L122-133 `renderActiveBadge` 同模式 -> `ACTIVE_LABEL: Record<boolean, { label, variant }>` 查表
- L57-62 `role === "admin" ? "降权" : "提权"` 可改 `ACTION_LABEL_BY_ROLE: Record<string, string>` 查表
- L63-68 `isActive ? "禁用" : "启用"` 可改 `ACTIVE_TOGGLE_LABEL[isActive]` 查表

**5. 数组替循环**:
- 无 for, 已 .map()

**6. 预计减少**: 438 -> 主文件 ~210 (-52%); 拆到 7 个文件: role-select.tsx (~30), kind-badge.tsx (~25), active-badge.tsx (~30), action-buttons.tsx (~80), `_lib/action-labels.ts` (~30), `_lib/role-options.ts` (~20), `_lib/reset-description.ts` (~20)

**7. 骨架伪代码**:
- `_lib/action-labels.ts`:
```ts
export const ADMIN_ACTION_LABEL: Record<string, string> = {
  admin: "降权",
  default: "提权",
};
export const ACTIVE_TOGGLE_LABEL: Record<boolean, string> = {
  true: "禁用",
  false: "启用",
};
```

- `kind-badge.tsx`:
```tsx
import { Badge } from "@/components/ui/badge";
import type { AdminUser } from "@/lib/api/users";

const KIND_META: Record<AdminUser["kind"], { label: string; variant: "default" | "secondary" }> = {
  account: { label: "账号", variant: "default" },
  default: { label: "anon", variant: "secondary" },
};

export function KindBadge({ kind }: { kind: AdminUser["kind"] }): JSX.Element {
  const meta = KIND_META[kind] ?? KIND_META.default;
  return <Badge variant={meta.variant}>{meta.label}</Badge>;
}
```

- `action-buttons.tsx`:
```tsx
import { Button } from "@/components/ui/button";
import type { AdminUser } from "@/lib/api/users";
import { ADMIN_ACTION_LABEL, ACTIVE_TOGGLE_LABEL } from "../_lib/action-labels";

interface ActionButtonsProps {
  currentUserId: number;
  pending: boolean;
  user: AdminUser;
  onToggleAdmin: (user: AdminUser) => void;
  onToggleActive: (user: AdminUser) => void;
  onResetPassword: (user: AdminUser) => void;
}
export function ActionButtons(props: ActionButtonsProps): JSX.Element { /* L157-194 */ }
```

---

### `app/[locale]/_actions/account.ts` (435 行)

**1. 拆分点**:
- L40-129 `loginAction` + helpers (`getLoginCredentials` L50-60, `loginApiCall` L68-86, `setLoginCookie` L92-102) -> `actions/account/login.ts` (server-only module)
- L131-165 `forgotPasswordAction` -> `actions/account/forgot-password.ts`
- L167-226 `resetPasswordAction` + helpers (`validateResetPasswordInput` L184-200) -> `actions/account/reset-password.ts`
- L228-340 `acceptInviteAction` + helpers (`getAcceptInviteFields` L245-257, `validateAcceptInviteInput` L263-280, `acceptInviteApiCall` L289-307) -> `actions/account/accept-invite.ts`
- L342-378 `resetPasswordAdminAction` -> `actions/account/reset-password-admin.ts`
- L380-420 `createInviteAction` -> `actions/account/create-invite.ts`
- L422-435 `logoutAction` -> `actions/account/logout.ts`
- 留: 当前文件只剩 barrel re-export `export * from "./login"`, 极薄壳

**2. 纯函数/hook 化**:
- 可拆:
  - `getLoginCredentials` L50-60 -> 模块级纯函数, 已 OK
  - `loginApiCall` L68-86 -> async 纯函数, 已 OK
  - `setLoginCookie` L92-102 -> async 纯函数, 已 OK
  - `validateResetPasswordInput` L184-200 -> 模块级纯函数, 已 OK
  - `getAcceptInviteFields` L245-257 -> 模块级纯函数, 已 OK
  - `validateAcceptInviteInput` L263-280 -> 模块级纯函数, 已 OK
  - `acceptInviteApiCall` L289-307 -> async 纯函数, 已 OK
- 不可拆: 无

**3. 库替代**:
- 无 — server actions 走原 fetch (serverAuthHeaders + apiFetch) 是必然, 项目无更高层封装
- `/i18n/navigation` `redirect` 已用 OK

**4. 对象替 if**:
- L184-200 校验函数内 if 链 (token / password length / confirm) -> 不可拆为查表, 是有顺序的验证链
- L263-280 同模式, 同结论
- L218-225 `catch` 内 if/else (ApiError vs unknown) -> 已用 `actionError(error)` 工具函数, OK

**5. 数组替循环**:
- 无

**6. 预计减少**: 435 -> 7 个 actions 每个 ~50-80 行; current 文件留 shell ~15 行 (-97%)

**7. 骨架伪代码**:
- `_actions/account/login.ts`:
```ts
"use server";
import { ApiError, NetworkError } from "@/lib/api/errors";
import { login } from "@/lib/api/account";
import { serverAuthHeaders } from "@/lib/api/auth.server";
import { cookies } from "next/headers";
import { redirect } from "@/i18n/navigation";
import { getLocale } from "next-intl/server";
import { revalidatePath } from "next/cache";
import { COOKIE_USER_TOKEN, HOURS_PER_DAY, HTTP_UNAUTHORIZED, MINUTES_PER_HOUR, SECONDS_PER_MINUTE } from "@/const";

export interface LoginState { ok: boolean; error: string | null; }

const COOKIE_MAX_AGE = 7 * HOURS_PER_DAY * MINUTES_PER_HOUR * SECONDS_PER_MINUTE;
const getLoginCredentials = (formData: FormData) => { /* L50-60 */ };
const loginApiCall = async (email: string, password: string) => { /* L68-86 */ };
const setLoginCookie = async (token: string) => { /* L92-102 */ };

export const loginAction = async (_prev: LoginState, formData: FormData): Promise<LoginState> => { /* L110-129 */ };
```

- `_actions/account/index.ts` (barrel):
```ts
export * from "./login";
export * from "./forgot-password";
export * from "./reset-password";
export * from "./accept-invite";
export * from "./reset-password-admin";
export * from "./create-invite";
export * from "./logout";
```

---

### `app/[locale]/_actions/account-settings.ts` (418 行)

**1. 拆分点**:
- L31-78 `updateProfileAction` + helper `handleProfileError` L47-55 -> `actions/account-settings/profile.ts` (server-only)
- L80-165 Avatar actions (`uploadAvatarAction` + `deleteAvatarAction` + helpers `validateAvatarFile` L99-110, `handleUploadError` L116-127) -> `actions/account-settings/avatar.ts`
- L167-225 `requestEmailChangeAction` + helper `handleEmailError` L186-194 -> `actions/account-settings/email.ts`
- L227-301 `changePasswordAction` + helpers `validatePasswords` L246-261, `handlePasswordError` L267-272 -> `actions/account-settings/password.ts`
- L303-418 Deletion actions (`requestDeletionAction` + `cancelDeletionAction` + helper `handleDeletionError` L324-333) -> `actions/account-settings/deletion.ts`
- 留: 当前文件只剩 barrel, 极薄

**2. 纯函数/hook 化**:
- 可拆:
  - `handleProfileError` L47-55 -> 模块级纯函数, 已 OK
  - `validateAvatarFile` L99-110 -> 模块级纯函数, 已 OK
  - `handleUploadError` L116-127 -> 模块级纯函数, 已 OK
  - `handleEmailError` L186-194 -> 模块级纯函数, 已 OK
  - `validatePasswords` L246-261 -> 模块级纯函数, 已 OK
  - `handlePasswordError` L267-272 -> 模块级纯函数, 已 OK
  - `handleDeletionError` L324-333 -> 模块级纯函数, 已 OK
- 不可拆: 无

**3. 库替代**:
- 无

**4. 对象替 if**:
- L106 `["image/png", "image/jpeg", "image/webp"].includes(file.type)` -> 已数组, OK
- L186-194 `handleEmailError` 已经是 if(==HTTP_BAD_REQUEST) 链 -> 单分支不值得改
- L267-272 简单 if (ApiError vs unknown) -> 已 OK
- L324-333 同, OK

**5. 数组替循环**:
- 无

**6. 预计减少**: 418 -> 5 个子文件每个 ~60-90 行; current 文件留 barrel ~15 行 (-96%)

**7. 骨架伪代码**:
- `_actions/account-settings/avatar.ts`:
```ts
"use server";
import { ApiError } from "@/lib/api/errors";
import { actionErrorWithFallback } from "@/lib/actions-utils";
import { uploadAvatar, deleteAvatar } from "@/lib/api/account";
import { HTTP_UNPROCESSABLE_ENTITY } from "@/const";

export interface AvatarState { ok: boolean; error: string | null; avatarUrl: string | null; }
const AVATAR_MAX_BYTES = 2_097_152;
const validateAvatarFile = (file: File | null): string | null => { /* L99-110 */ };
const handleUploadError = (error: unknown): AvatarState => { /* L116-127 */ };

export const uploadAvatarAction = async (_prev: AvatarState, formData: FormData): Promise<AvatarState> => { /* L135-151 */ };
export const deleteAvatarAction = async (): Promise<AvatarState> => { /* L157-165 */ };
```

- `_actions/account-settings/index.ts` (barrel):
```ts
export * from "./profile";
export * from "./avatar";
export * from "./email";
export * from "./password";
export * from "./deletion";
```

---

### `app/[locale]/admin/pre-analysis/[task_id]/_components/admin-pre-analysis-detail-client.tsx` (400 行)

**1. 拆分点**:
- L33-39 `KIND_LABEL` 常量 -> `_lib/output-labels.ts`
- L52-61 `STATE_LABELS` 常量 -> `_lib/state-labels.ts`
- L66-77 `VIEWABLE_KINDS` + `isViewableKind` -> `_lib/viewable-kinds.ts`
- L89-101 `viewHrefForKind` 纯函数 -> `_lib/view-href.ts`
- L103-135 `formatSize` / `buildZipFilename` 纯函数 -> `_lib/format-size.ts` + `_lib/zip-filename.ts`
- L138-160 `buildStatCardClickHandler` 工厂 -> `_lib/stat-card-click.ts`
- 副组件拆: L274-336 PageHero + 三张 StatCard 区 -> `summary-section.tsx` (component) [重用所有常量 + handler]
- 副组件拆: L348-396 产物表区 (DataTable + action buttons + 下载按钮) -> `output-files-section.tsx` (component)
- L164-400 `AdminPreAnalysisDetailClient` 主组件 -> 留 ~120-150 行

**2. 纯函数/hook 化**:
- 可拆:
  - L115-123 `formatSize` -> 模块级, 已 OK
  - L132-135 `buildZipFilename` -> 模块级, 已 OK
  - L89-101 `viewHrefForKind` -> 模块级, 已 OK
  - L76-77 `isViewableKind` -> 模块级, 已 OK
  - L147-160 `buildStatCardClickHandler` -> 模块级, 已 OK
  - L34-39 `KIND_LABEL` / L57-61 `STATE_LABELS` / L68 `VIEWABLE_KINDS` -> 模块级常量, 已 OK
- 不可拆:
  - L186-202 `handleDownloadZip` 用了 `data.pdf_filename`, 必须留在组件内
  - L209-217 `handleDownloadFile` 同, 必须留在组件内

**3. 库替代**:
- shadcn `<StatCard>` 已封装 (components/common/display/app-stat-card.tsx), 已用
- shadcn `<Button>` 已用 OK
- 项目封装 `<BackLink>` / `<PageHero>` / `<DataTable>` / `<DataEmpty>` / `<ErrorBanner>` 已用 OK
- 无 (lucide-react `Download` / `Eye` / `RefreshCw` 已用, OK)

**4. 对象替 if**:
- L116-123 `if (bytes < ONE_KB) ... else if (bytes < ONE_MB)` -> 可改 size bucket map + 查表
- L33-39 `KIND_LABEL` 是查表, OK
- L57-61 `STATE_LABELS` 是查表, OK

**5. 数组替循环**:
- 无

**6. 预计减少**: 400 -> 主文件 ~150 (-63%); 拆到 7-8 个文件: summary-section.tsx (~80), output-files-section.tsx (~90), `_lib/output-labels.ts` (~15), `_lib/state-labels.ts` (~15), `_lib/view-href.ts` (~25), `_lib/viewable-kinds.ts` (~20), `_lib/format-size.ts` (~15), `_lib/zip-filename.ts` (~10)

**7. 骨架伪代码**:
- `_lib/format-size.ts`:
```ts
import { ONE_KB, ONE_MB } from "@/const";
export const formatSize = (bytes: number): string => { /* L115-123, candidate for size bucket map */ };
```

- `summary-section.tsx`:
```tsx
import { PageHero } from "@/components/common/navigation/app-page-hero";
import { StatCard } from "@/components/common/display/app-stat-card";
import type { PreAnalysisTaskState } from "@/lib/api/pre-analysis";

interface SummarySectionProps {
  taskId: string;
  state: PreAnalysisTaskState;
  elapsedMs: number;
  pdfFilename: string;
  totalTables: number;
  totalChapters: number;
  totalFlagged: number;
  crossPageCandidates: number;
  onTablesClick: () => void;
  onChaptersClick: () => void;
  onFlaggedClick: () => void;
  translate: (key: string, params?: Record<string, string | number>) => string;
}
export function SummarySection(props: SummarySectionProps): JSX.Element { /* L274-336 */ }
```

---

### `components/chat/memory-management-dialog.tsx` (378 行)

**1. 拆分点**:
- L41-54 `filterMemories` 纯函数 -> 留当前文件 (模块级, 已 OK)
- L62-84 `useMemoryApi` 数据加载 hook -> `_hooks/use-memory-api.ts` (hook)
- L93-98 `useMemoryFilter` 客户端过滤 hook -> `_hooks/use-memory-filter.ts` (hook)
- L106-111 `useMemoryEdit` 编辑状态 hook -> `_hooks/use-memory-edit.ts` (hook)
- L121-140 `MemoryDialogFooter` -> `memory-dialog-footer.tsx` (component) [已单独模块]
- L156-222 `MemoryListItem` 行组件 (单条记忆展示/编辑态切换) -> `memory-list-item.tsx` (component) [已单独模块]
- L239-284 `MemoryListContent` 列表容器 (loading/empty/list) -> `memory-list-content.tsx` (component)
- L286-378 主组件 `MemoryManagementDialog` -> 留 ~80 行

**2. 纯函数/hook 化**:
- 可拆:
  - `useMemoryApi` L64-84 已抽 hook, OK
  - `useMemoryFilter` L94-98 已抽 hook, OK
  - `useMemoryEdit` L107-111 已抽 hook, OK
  - `filterMemories` L48-54 已模块级纯函数, OK
- 不可拆: `saveEdit` / `handleDelete` / `handleClearAll` 用了所有 state + setState, 拆 hook 会切断依赖, 留在主组件

**3. 库替代**:
- shadcn `<Input>` / `<Button>` 已用 OK
- 项目封装 `<AppDialog>` / `<AppConfirm>` 已用 OK
- 无

**4. 对象替 if**:
- L177-198 `isEditing` 时 vs `else` 走两套 JSX, 不可改查表, 因为各自带不同 props (Input vs readonly text)
- 无

**5. 数组替循环**:
- L271-283 `.map((memory) => <MemoryListItem>...)` 已 OK

**6. 预计减少**: 378 -> 主文件 ~80 (-79%); 拆到 7 个文件: use-memory-api.ts (~30), use-memory-filter.ts (~15), use-memory-edit.ts (~15), memory-list-content.tsx (~60), + 已存在的 memory-dialog-footer.tsx / memory-list-item.tsx

**7. 骨架伪代码**:
- `_hooks/use-memory-api.ts`:
```ts
import { useState, useEffect } from "react";
import { useBoolean } from "react-use";
import { type MemoryHit, list } from "@/lib/api/memory";

export function useMemoryApi(open: boolean): {
  memories: MemoryHit[];
  loading: boolean;
  load: () => Promise<void>;
  setMemories: (val: MemoryHit[]) => void;
} { /* L64-84 */ }
```

- `memory-list-content.tsx`:
```tsx
import { useTranslations } from "next-intl";
import { ZERO } from "@/const";
import type { MemoryHit } from "@/lib/api/memory";
import { MemoryListItem } from "./memory-list-item";

interface MemoryListContentProps { /* L240-260 props */ }
export function MemoryListContent(props: MemoryListContentProps): JSX.Element {
  if (props.loading) return <div className="text-muted-foreground text-sm">...</div>;
  if (props.filtered.length === ZERO) return <div ...>{props.translation("还没有记忆...")}</div>;
  return props.filtered.map((memory) => <MemoryListItem key={memory.id} {...props} memory={memory} />);
}
```

---

### `app/[locale]/admin/dicts/_components/admin-dicts-client.tsx` (334 行)

**1. 拆分点**:
- L36-38 常量 `FIRST_INDEX` / `DEFAULT_COUNT` -> `_lib/constants.ts`
- L52-87 `DictPageContent` 内容区 (activeCode -> items -> loading/empty) -> `dict-page-content.tsx` (component)
- L108-110 `extractErrorMsg` 纯函数 -> `_lib/error-utils.ts`
- L117-133 `callWithToast` 包装 toast handler -> `_lib/call-with-toast.ts` (泛型纯函数)
- L139-159 `doPatch` -> `_handlers/do-patch.ts`
- L164-186 `doDelete` -> `_handlers/do-delete.ts`
- L192-214 `doCreate` -> `_handlers/do-create.ts`
- L218-334 `AdminDictsClient` 主组件 -> 留 ~120 行

**2. 纯函数/hook 化**:
- 可拆:
  - `extractErrorMsg` L109-110 -> 模块级, 已 OK
  - `callWithToast` L118-133 -> 泛型 async 纯函数, 已 OK
  - `doPatch` / `doDelete` / `doCreate` L140-214 -> 模块级 async 纯函数, 已 OK
- 不可拆: `handlers` 对象 L238-245 (依赖闭包 setError), 必须留在主组件

**3. 库替代**:
- 项目封装 `<AppSelect>` / `<DataEmpty>` / `<ErrorBanner>` / `<PageHero>` 已用 OK
- shadcn `<PageGuard>` (components/page-guard.tsx) 已用 OK
- 无

**4. 对象替 if**:
- L72-87 `if (activeCode) <DictList/> else if (isLoading) <p/> else <DataEmpty/>` -> 3 个分支 1 渲染, 可改 `switchMap: Record<BranchKey, JSX>`, 但 readability 当前 OK
- L239-245 `handlers` 对象已是查表模式, OK

**5. 数组替循环**:
- L276 `(summaries.data ?? []).map(...)` 已 OK
- 无 for

**6. 预计减少**: 334 -> 主文件 ~120 (-64%); 拆到 7 个文件: dict-page-content.tsx (~50), `_lib/error-utils.ts` (~10), `_lib/call-with-toast.ts` (~25), `_handlers/do-patch.ts` (~30), `_handlers/do-delete.ts` (~30), `_handlers/do-create.ts` (~30)

**7. 骨架伪代码**:
- `_lib/call-with-toast.ts`:
```ts
import { toast } from "sonner";

export const callWithToast = async <TResult,>(
  action: () => Promise<TResult>,
  messages: { success: string; fallback: string },
  onError: (msg: string) => void,
): Promise<boolean> => { /* L118-133 */ };
```

- `dict-page-content.tsx`:
```tsx
import type { LookupItem, LookupItemPatchInput } from "@/lib/api/lookups";
import { DataEmpty } from "@/components/common/display/app-data-empty";
import { DictList } from "./dict-list";

interface DictPageContentProps { /* L53-71 props */ }
export function DictPageContent(props: DictPageContentProps): JSX.Element {
  if (props.activeCode) return <DictList {...props} />;
  if (props.isLoading) return <p className="text-sm text-muted-foreground">{props.translate("加载中…")}</p>;
  return <DataEmpty title={props.translate("暂无字典")} variant="page" />;
}
```

---

### `app/[locale]/knowledge/triples/_components/triples-form.tsx` (331 行)

**1. 拆分点**:
- L30-36 常量 / class string -> `_lib/constants.ts`
- L38-152 `useTriplesColumns` 列定义 hook (118 行) -> 留, 强耦合 schema + handlers + trans, 但可拆走 trans 表 `getColumnHeaders` 工厂
- L154-173 `Props` interface + `getSubmitLabel` 纯函数 -> 留
- L176-261 `TriplesForm` 主组件 -> 留 ~80 行
- L263-271 `TriplesResultProps` + L290-310 `TriplesResult` -> `triples-result.tsx` (component) [已分离了渲染]
- L312-331 `TriplesError` -> `triples-error.tsx` (component)
- L273-288 `TriplesHero` -> `triples-hero.tsx` (component) [但小, 可保留主组件内]

**2. 纯函数/hook 化**:
- 可拆:
  - `getSubmitLabel` L168-173 -> 模块级, 已 OK
- 不可拆:
  - `useTriplesColumns` L44-152 强依赖 useTranslations 返回类型 + handlers, 拆走需多传 3 个 props, ROI 低, 留 hook
  - `TriplesForm` JSX 内部用 `useTranslations` + `useRouter` + `useParams` + `useTripleForm` 全栈集成, 拆不出

**3. 库替代**:
- shadcn `<Card>` / `<CardContent>` / `<CardHeader>` / `<CardTitle>` 已用 OK
- shadcn `<Input>` / `<Button>` 已用 OK
- 项目封装 `<AppForm>` / `<AppSubmit>` (components/common/form) 已用 OK
- 项目封装 `<DataTable<T>>` 已用 OK
- 项目封装 `<ErrorBanner>` 已用 OK
- 项目封装 `<PageHero>` 已用 OK
- motion `AnimateUp` / `Reveal` / `AnimatePresence` 已用 OK
- 无

**4. 对象替 if**:
- L168-173 `pending ? "提交中…" : "批量提交"` -> 已三元, 可改 `SUBMIT_LABEL_MAP[pending]` 但太简单
- 无

**5. 数组替循环**:
- 无

**6. 预计减少**: 331 -> 主文件 ~150 (-55%); 拆到 3 个文件: triples-result.tsx (~40), triples-error.tsx (~30), triples-hero.tsx (~30) [可选]

**7. 骨架伪代码**:
- `triples-error.tsx`:
```tsx
import { AnimateUp } from "@/components/motion/animated";
import { ErrorBanner } from "@/components/common/feedback/app-error-banner";

export function TriplesError({ message }: { message: string }): JSX.Element {
  return (
    <AnimateUp show enterFromTop className="mt-4">
      <ErrorBanner
        variant="destructive"
        descriptionNode={
          <ul className="list-disc space-y-1 pl-5 text-sm">
            {message.split("; ").map((msg, idx) => <li key={idx}>{msg}</li>)}
          </ul>
        }
        description=""
        dataTestid="triples-error"
      />
    </AnimateUp>
  );
}
```

- `triples-result.tsx`:
```tsx
import { AnimateUp } from "@/components/motion/animated";
import { useTranslations } from "next-intl";
import { cn } from "@/lib/utils";

type ReviewStatus = "pending" | "approved" | "rejected";

export function TriplesResult({ approvalId, reviewStatus }: { approvalId: number; reviewStatus: ReviewStatus }): JSX.Element {
  const trans = useTranslations();
  return (
    <AnimateUp
      show
      enterFromTop
      data-testid="triples-result"
      className={cn("mt-4 rounded-lg border p-3 text-base", "border-moss/30 bg-moss/5 text-moss")}
    >
      {trans("已提交审核 #{id} (状态: {status})", { id: approvalId, status: reviewStatus })}
    </AnimateUp>
  );
}
```

---

### `components/theme-provider.tsx` (322 行)

**1. 拆分点**:
- L33-38 常量 `STORAGE_KEY` / `FOUC_MARKER` / `LIGHT` / `DARK` / `SYSTEM` / `MEDIA` -> 留, 模块级
- L41-50 `ThemeName` type + `ThemeContextValue` interface -> 留 types 段
- L52-62 `ThemeValueContext` + L64-66 `ThemeDispatchContext` createContext -> 留, 强耦合
- L70-88 `Props` interface -> 留
- L92-208 helpers 段 (`getSystemTheme` / `readStored` / `writeStored` / `isServer` / `isValidTheme` / `getInitialTheme` / `resolveTheme` / `applyToHtml` / `isTestEnv` / `injectFoucScript`) -> 拆到 `_lib/theme-storage.ts` (storage helpers: readStored/writeStored/isServer) + `_lib/theme-resolve.ts` (getSystemTheme/resolveTheme/applyToHtml/isValidTheme) + `_lib/fouc-inject.ts` (isTestEnv/injectFoucScript) [3 文件 ~70-100 行]
- L212-312 `ThemeProvider` 主组件 -> 留 ~150 行 (含 hooks + media query + FOUC useEffect)
- L314-322 `useTheme` hook -> 留

**2. 纯函数/hook 化**:
- 可拆:
  - L92-102 `getSystemTheme` -> 模块级, 已 OK
  - L104-110 `readStored` -> 模块级, 已 OK
  - L112-118 `writeStored` -> 模块级, 已 OK
  - L120 `isServer` -> 模块级, 已 OK
  - L131-136 `isValidTheme` -> 模块级, 已 OK
  - L139-148 `getInitialTheme` -> 模块级, 已 OK
  - L151-162 `resolveTheme` -> 模块级, 已 OK
  - L165-171 `applyToHtml` -> 模块级, 已 OK
  - L176-178 `isTestEnv` -> 模块级, 已 OK
  - L181-208 `injectFoucScript` -> 模块级, 已 OK
- 不可拆: `ThemeProvider` 内 setTheme 函数体 / 3 个 useEffect 必须留主组件

**3. 库替代**:
- 无 — 自实现是 project spec [feedback-next-themes-dead-use-self-implement.md] 的强制选择
- 已用 react-use `useEvent` (L291), OK

**4. 对象替 if**:
- L131-136 `if (val === LIGHT || val === DARK) return true; return enableSystem && val === SYSTEM;` 可改 `validators[enableSystem ? "withSystem" : "basic"]`, 但仅 2 分支, ROI 低
- L144-146 `stored === LIGHT || stored === DARK || stored === SYSTEM` 链 -> 不可改 map, 因为是 whitelist guard

**5. 数组替循环**:
- 无

**6. 预计减少**: 322 -> 主文件 ~150 (-53%); 拆到 3 个 lib 文件: theme-storage.ts (~25), theme-resolve.ts (~50), fouc-inject.ts (~45)

**7. 骨架伪代码**:
- `_lib/theme-storage.ts`:
```ts
const STORAGE_KEY = "theme";
const isServer = (): boolean => typeof globalThis === "undefined";
const readStored = (key: string): string | null => { /* L104-110 */ };
const writeStored = (key: string, value: string) => { /* L112-118 */ };
export { readStored, writeStored, isServer, STORAGE_KEY };
```

- `_lib/fouc-inject.ts`:
```ts
const FOUC_MARKER = "data-theme-fouc";
const isTestEnv = (): boolean =>
  typeof process !== "undefined" &&
  (process.env.VITEST === "true" || process.env.NODE_ENV === "test");

export const injectFoucScript = (storageKey: string, enableSystem: boolean) => { /* L181-208 */ };
```

---

### `app/[locale]/decode/page.tsx` (312 行)

**1. 拆分点**:
- L22-25 常量 `EXAMPLE` / `JSON_INDENT` -> 留模块级
- L27-46 `DecodeResult` type -> `_lib/types.ts`
- L48-58 `buildCopyText` 纯函数 -> `_lib/build-copy-text.ts`
- L60-72 `filterMainFields` 纯函数 -> `_lib/filter-main-fields.ts`
- L74-84 `formatDecodeError` 纯函数 -> `_lib/format-decode-error.ts`
- L100-151 `useDecodeActions` hook (含 useEvent) -> `_hooks/use-decode-actions.ts` (hook) [已抽 hook, OK]
- L155-166 `DecodePage` default export -> 留
- L168-312 `DecodePageInner` 主组件 -> 留 ~120-150 行
- 副组件: L233-286 结果 Header (name + manufacturer + prefix + view toggle + CopyButton) -> `decode-result-header.tsx` (component)
- 副组件: L289-305 字段网格 / LLM 视图 -> `decode-result-body.tsx` (component)

**2. 纯函数/hook 化**:
- 可拆:
  - `buildCopyText` L54-59 -> 模块级纯函数, 已 OK
  - `filterMainFields` L66-73 -> 模块级纯函数, 已 OK
  - `formatDecodeError` L80-85 -> 模块级纯函数, 已 OK
  - `useDecodeActions` L100-151 -> 已抽 hook, OK
- 不可拆: `useDecodeActions` 内 `copyJSON` 写空函数, 可删 (181 行无操作), UI 逻辑走 CopyButton, ROI 中

**3. 库替代**:
- 项目封装 `<AppToggle>` / `<CopyButton>` / `<ErrorBanner>` / `<PageHero>` / `<GuardClient>` 已用 OK
- react-use `useEvent` / `useLocalStorage` / `useToggle` 已用 OK
- shadcn `<Input>` / `<Button>` 已用 OK (在子组件中)
- 副组件 `<DecodeInputBar>` / `<DecodeField>` / `<SeriesDialog>` 已抽到独立文件, OK
- 无

**4. 对象替 if**:
- L55-58 `if (view === "llm") return ...; return JSON.stringify(...)` 已经是 2 分支, 改 map 可能更乱
- 无

**5. 数组替循环**:
- L291-295 `filterMainFields(result).map(([key, value]) => <StaggerItem>...</StaggerItem>)` 已 OK

**6. 预计减少**: 312 -> 主文件 ~130 (-58%); 拆到 6 个文件: use-decode-actions.ts (~60), `_lib/build-copy-text.ts` (~15), `_lib/filter-main-fields.ts` (~20), `_lib/format-decode-error.ts` (~15), `_lib/types.ts` (~20), decode-result-header.tsx (~60), decode-result-body.tsx (~50)

**7. 骨架伪代码**:
- `_hooks/use-decode-actions.ts`:
```ts
import { useEvent } from "react-use";
import { decode } from "@/lib/api/system";
import { formatDecodeError } from "../_lib/format-decode-error";

interface UseDecodeActionsArgs { /* 8 props */ }
export function useDecodeActions(props: UseDecodeActionsArgs): { submit: () => void; fillExample: () => void; copyJSON: () => Promise<void>; } { /* L100-151 */ }
```

- `decode-result-header.tsx`:
```tsx
import { AppToggle } from "@/components/common/input/app-toggle";
import { CopyButton } from "@/components/common/button/app-copy-button";

export function DecodeResultHeader(props: {
  result: DecodeResult;
  view: "cards" | "llm";
  onViewChange: (next: "cards" | "llm") => void;
  copyText: string;
  translate: (key: string) => string;
}): JSX.Element { /* L246-286 */ }
```

---

### `app/[locale]/_actions/knowledge.ts` (311 行)

**1. 拆分点**:
- L14-15 `ActionResult<T>` type -> `_lib/types.ts`
- L17-76 `createQA` (+ 2 interfaces `QAInput` / `QAResult`) -> `_actions/knowledge/create-qa.ts` (server-only)
- L78-142 `createTriples` (+ 2 interfaces) -> `_actions/knowledge/create-triples.ts`
- L144-206 `commitDocuments` (+ 2 interfaces) -> `_actions/knowledge/commit-documents.ts`
- L208-268 `optimizeAnswer` (+ 2 interfaces) -> `_actions/knowledge/optimize-answer.ts`
- L270-311 `likeAnswer` (+ 2 interfaces) -> `_actions/knowledge/like-answer.ts`
- 留: 当前文件只剩 barrel `export * from ...`, 极薄

**2. 纯函数/hook 化**:
- 可拆:
  - 5 个 action 函数都是 `async (input) => { try { submit(...) } catch { actionError(...) }}` 模式, 已模块级, OK
- 不可拆: 都是 server action, 拆分到独立文件以 `_actions/knowledge/` 子目录组织, 不抽 hook (server action 不能 hook)

**3. 库替代**:
- 无 — server actions 没有更高层封装
- `/lib/api/approvals` submit 已用 OK
- `/lib/actions-utils` actionError 已用 OK

**4. 对象替 if**:
- L52 `if (!input.dataset_id || !input.question || !input.answer)` 链 -> 可改 `["dataset_id", "question", "answer"].every(key => input[key])`, ROI 低, 留
- L186 `if (!input.dataset_id || !Array.isArray(input.rows))` 同
- L245 `if (!input.dataset_id || !input.question || !input.improved_answer)` 同
- L297 `if (!input.question || !input.answer || !input.messageId)` 同
- 所有 try/catch 都走 `actionError(error)` 工具, OK

**5. 数组替循环**:
- 无

**6. 预计减少**: 311 -> 5 个子文件每个 ~50-70 行; 当前文件留 barrel ~20 行 (-94%)

**7. 骨架伪代码**:
- `_actions/knowledge/create-qa.ts`:
```ts
"use server";
import { submit } from "@/lib/api/approvals";
import { actionError } from "@/lib/actions-utils";
import { revalidatePath } from "next/cache";
import type { ActionResult } from "./_lib/types";

interface QAInput {
  dataset_id: string;
  question: string;
  answer: string;
  tags?: string[];
  sync_to_neo4j?: boolean;
}
interface QAResult {
  approval_id: number;
  review_status: "pending" | "approved" | "rejected";
  apply_status: "none" | "applied" | "failed";
}

export const createQA = async (input: QAInput): Promise<ActionResult<QAResult>> => { /* L48-76 */ };
```

- `_actions/knowledge/_lib/types.ts`:
```ts
export type ActionResult<TData> = { ok: true; data: TData } | { ok: false; error: string };
```

---

### `components/common/table/data-table.tsx` (308 行)

**1. 拆分点**:
- L28-40 `resolveMaxHeight` -> 留 `_lib/max-height.ts`
- L42-98 列宽工具 (`getFlexColStyle` / `getStringColStyle` / `getColStyle`) -> 拆到 `_lib/col-style.ts` [project: 列宽是通用能力, 抽出后 DataTableBody 也可复用]
- L100-109 `TanstackColumnMeta` + L111 `ColumnDef` type alias + L114-151 `DataTableProps` interface -> 留 types 段 L100-151
- L153-208 `buildTableOptions` 纯函数 -> 留, 已抽 OK
- L210-308 `DataTable` 主组件 -> 留 ~100 行

**2. 纯函数/hook 化**:
- 可拆:
  - `resolveMaxHeight` L32-40 -> 模块级纯函数, 已 OK
  - `getFlexColStyle` L58-64 -> 模块级纯函数, 已 OK
  - `getStringColStyle` L71-79 -> 模块级纯函数, 已 OK
  - `getColStyle` L87-98 -> 模块级纯函数, 已 OK
  - `buildTableOptions` L173-208 -> 模块级纯函数, 已 OK
- 不可拆: `DataTable` 内 `handleChangePage` L242-248 用了闭包 `table.setPageIndex`, 必须留主组件

**3. 库替代**:
- @tanstack/react-table `useReactTable` / `getCoreRowModel` / `getPaginationRowModel` / `flexRender` 已用 OK
- shadcn `<Table>` / `<TableBody>` / `<TableHead>` / `<TableHeader>` / `<TableRow>` 已用 OK
- 项目封装 `DataEmpty` / `DataTableBody` / `DataTablePagination` / `apply-pagination-updater` 已用 OK
- 无

**4. 对象替 if**:
- L33-40 `if (!maxHeight || maxHeight === "auto") return undefined; if (typeof === "number") return ...px; return maxHeight;` -> 是 3-branch type 派发, 不可改 map
- L88-98 type 派发, 同
- 无

**5. 数组替循环**:
- L271-290 `.map((headerGroup) => ...)` 已 OK
- L273-288 `.map((header) => ...)` 已 OK
- 无

**6. 预计减少**: 308 -> 主文件 ~140 (-55%); 拆到 2 个 lib 文件: max-height.ts (~15), col-style.ts (~80)

**7. 骨架伪代码**:
- `_lib/col-style.ts`:
```ts
import type { CSSProperties } from "react";
import type { ColumnWidth } from "@/components/common/table/data-table-types";

const getFlexColStyle = (width: { max?: number; min: number }): CSSProperties => { /* L58-64 */ };
const getStringColStyle = (width: string): CSSProperties => { /* L71-79 */ };
export const getColStyle = (width: ColumnWidth | undefined): CSSProperties | undefined => { /* L87-98 */ };
```

- `_lib/max-height.ts`:
```ts
export const resolveMaxHeight = (maxHeight: string | number | undefined): string | undefined => { /* L32-40 */ };
```

---

### `app/[locale]/output/[task_id]/_components/task-detail-client.tsx` (304 行)

**1. 拆分点**:
- L28 `POLL_INTERVAL` 常量 -> 留模块级
- L30-40 `extractErrorMessage` 纯函数 -> `_lib/error-utils.ts`
- L42-52 `resolveError` 纯函数 -> `_lib/error-utils.ts` (跟上面一起)
- L62-94 `useTaskDownload` hook -> `_hooks/use-task-download.ts` (hook) [已抽 hook]
- L96-125 `useTaskCancel` hook -> `_hooks/use-task-cancel.ts` (hook) [已抽 hook]
- L183-255 `BodyContentSwitch` (错误/loading/有 task 三分支) -> `body-content-switch.tsx` (component)
- L256-304 `OutputPanel` (产物表 + 取消 + 下载) -> `output-panel.tsx` (component)
- L133-183 `TaskDetailClient` 主组件 -> 留 ~50 行

**2. 纯函数/hook 化**:
- 可拆:
  - `extractErrorMessage` L35-40 -> 模块级纯函数, 已 OK
  - `resolveError` L47-52 -> 模块级纯函数, 已 OK
  - `useTaskDownload` L72-94 -> 已抽 hook, OK
  - `useTaskCancel` L104-125 -> 已抽 hook, OK
- 不可拆: 主组件 `TaskDetailClient` 集成 useQuery + 2 hook + ErrorBanner state, 拆走 ROI 低

**3. 库替代**:
- @tanstack/react-query `useQuery` 已用 OK
- 项目封装 `<BackLink>` / `<ErrorBanner>` 已用 OK
- shadcn `<Card>` / `<CardContent>` / `<Button>` 已用 OK (子组件中)
- motion `FadePresence` / `Reveal` 已用 OK
- 子组件 `<TaskInfo>` / `<TaskFiles>` / `<TaskDownload>` 已经抽到独立文件, OK
- 无

**4. 对象替 if**:
- L140-146 `refetchInterval` 用函数返 `false | number`, 已 OK
- L222-241 `if (displayError) ... else if (!task) ... else <OutputPanel/>` 3 分支, 不可改 map (各自 UI 差异大)
- 无

**5. 数组替循环**:
- 无

**6. 预计减少**: 304 -> 主文件 ~50 (-84%); 拆到 6 个文件: use-task-download.ts (~30), use-task-cancel.ts (~30), `_lib/error-utils.ts` (~30), body-content-switch.tsx (~80), output-panel.tsx (~80)

**7. 骨架伪代码**:
- `_hooks/use-task-cancel.ts`:
```ts
import { useState, useTransition } from "react";
import { cancelTask } from "@/app/[locale]/_actions/output";
import type { useTranslations } from "next-intl";

export function useTaskCancel(taskId: string, translate: ReturnType<typeof useTranslations>, setCancelError: (msg: string | null) => void): {
  cancelPending: boolean;
  cancelling: boolean;
  onCancelSubmit: () => void;
} { /* L104-125 */ }
```

- `body-content-switch.tsx`:
```tsx
import { ErrorBanner } from "@/components/common";
import { Button } from "@/components/ui/button";
import type { IngestTask } from "@/lib/api";
import { OutputPanel } from "./output-panel";

interface BodyContentSwitchProps { /* L199-220 props */ }
export function BodyContentSwitch(props: BodyContentSwitchProps): JSX.Element {
  if (props.displayError) return <ErrorBanner variant="destructive" description={props.displayError} action={<Button onClick={() => { props.setDownloadError(null); props.setCancelError(null); }}>{props.translate("重试")}</Button>} />;
  if (!props.task) return <div className="text-base text-muted-foreground">{props.translate("加载中…")}</div>;
  return <OutputPanel {...props} />;
}
```

---

## 横向总结

### 总体行数 vs 拆后合计

| 文件 | 当前 | 拆后主 | 拆后辅 (合计) |
|---|---|---|---|
| pre-analysis-upload-dialog.tsx | 479 | ~250 (-48%) | ~330 (5 文件) |
| admin-users-table.tsx | 438 | ~210 (-52%) | ~205 (7 文件) |
| _actions/account.ts | 435 | ~15 (-97%) | ~420 (7 文件) |
| _actions/account-settings.ts | 418 | ~15 (-96%) | ~400 (5 文件) |
| admin-pre-analysis-detail-client.tsx | 400 | ~150 (-63%) | ~275 (8 文件) |
| memory-management-dialog.tsx | 378 | ~80 (-79%) | ~300 (7 文件) |
| admin-dicts-client.tsx | 334 | ~120 (-64%) | ~210 (7 文件) |
| triples-form.tsx | 331 | ~150 (-55%) | ~180 (3 文件) |
| theme-provider.tsx | 322 | ~150 (-53%) | ~170 (3 文件) |
| decode/page.tsx | 312 | ~130 (-58%) | ~210 (6 文件) |
| _actions/knowledge.ts | 311 | ~20 (-94%) | ~290 (6 文件) |
| data-table.tsx | 308 | ~140 (-55%) | ~165 (2 文件) |
| task-detail-client.tsx | 304 | ~50 (-84%) | ~250 (6 文件) |
| **合计** | **4867** | **~1480** | **~3405** |

### 拆分优先级

- **立即拆 (server-only action 文件)**: account.ts, account-settings.ts, knowledge.ts — 6 个 action 共 1164 行 -> 17 个子文件, 每个拆出来都 < 100 行, 是 P0 清单
- **优先拆 (client 有 hooks 已抽, 但 JSX 还胖)**: admin-users-table.tsx, memory-management-dialog.tsx, admin-dicts-client.tsx, task-detail-client.tsx — 4 个文件 1454 行 -> 主要拆 UI 副组件
- **次拆 (主组件已瘦, 拆 helper 收益中等)**: pre-analysis-upload-dialog.tsx, admin-pre-analysis-detail-client.tsx, decode/page.tsx — 拆副组件 + 纯函数 lib
- **轻拆 (结构已 OK, 主组件只剩配置)**: data-table.tsx (拆 2 lib), theme-provider.tsx (拆 3 lib), triples-form.tsx (拆 3 component)

### 共同模式

- `_actions/*.ts` 6 个 server action 文件全是 "多个 action + 各自 validate/error helper" 模板, 抽子目录后每个文件 ~50-80 行, 100% 复用 apiFetch + actionError 工具
- 客户端组件常见模式: "const 常量 (5-10) + 接口 + 列定义 (50-150 行) + 3-4 个 hook + 主组件 JSX", 应该把列定义 / 常量字典 / 纯函数全部抽到 `_lib/`, 主组件留 hook 集成 + JSX 骨架
- shadcn 35 组件 + 项目 13+ 封装已 100% 覆盖本批 13 个文件的 UI 需求, 没有需要新装的库
- shadcn `<Table>` 已装, 已被 `DataTable<T>` 包装, 业务代码不应该再用原始 shadcn `<Table>`
