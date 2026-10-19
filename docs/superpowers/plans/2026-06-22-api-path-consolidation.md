# API 路径统一实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 消除所有 `"/api/..."` 硬编码路径，统一走 `lib/api/` 封装。

**规则 1:** `"/api/..."` 路径只能出现在 `lib/api/config.ts` 和 `lib/api/<domain>.ts` 里，其他文件禁止出现。

**规则 2:** `lib/api/` 下禁止使用对象模式（`export const xxxApi = { ... }`），必须使用独立函数导出（`export const fnName = () => ...`）。已有对象模式的文件需要整改。

**示例（正确）：**
```typescript
// ✅ 正确 — 独立函数导出
export const fetchDifyHealth = (): Promise<{ ok: boolean }> =>
  apiFetch<{ ok: boolean }>("/api/kg/health");

export const fetchSystem = (): Promise<HealthPayload> =>
  apiFetch<HealthPayload>("/api/health/system");
```

**示例（错误）：**
```typescript
// ❌ 禁止 — 对象模式
export const healthApi = {
  fetchDifyHealth: () => apiFetch(...),
  fetchSystem: () => apiFetch(...),
};
```

**消费者示例：**
```typescript
// ✅ 正确 — 直接引用函数
import { fetchDifyHealth } from "@/lib/api/health";
fetchDifyHealth();
```

---

## 全量改动清单

### _actions（5 个文件，13 处）

| 文件 | 行数 | 硬编码 API 路径 | 应改为 |
|------|------|----------------|--------|
| `app/_actions/account-settings.ts` | 339 | 7 处: `/account/profile`, `/account/avatar` x2, `/account/email`, `/account/password` x2, `/account/deletion` x2 | `lib/api/` 无对应 wrapper，新建 `lib/api/account.ts` 后引用 |
| `app/[locale]/_actions/account.ts` | 328 | 5 处: `/account/login`, `/account/forgot-password`, `/account/reset-password`, `/admin/users`, `/account/logout` | 新建 `lib/api/account.ts` |
| `app/[locale]/_actions/evaluate.ts` | 62 | 1 处: `/evaluate/runs` | 改为调 `lib/api/evaluate.ts` |
| `app/[locale]/_actions/knowledge.ts` | 221 | 0 | ✅ 已通过 server action 直调 |
| `app/[locale]/_actions/output.ts` | 40 | 0 | ✅ |

### [locale] pages（20 个文件，24 处）

| 文件 | 处 | 硬编码路径 | 改为 |
|------|----|-----------|------|
| `account/restore/page.tsx` | 1 | `/account/deletion` | `lib/api/account.ts` |
| `account/settings/page.tsx` | 1 | `/account/profile` | `lib/api/account.ts` |
| `admin/invites/page.tsx` | 2 | `/admin/invites` | `lib/api/users.ts` |
| `admin/permissions/create-role-dialog.tsx` | 1 | `/permissions/me` | `lib/api/permissions.ts` |
| `admin/permissions/permissions-admin-client.tsx` | 1 | `/permissions` | `lib/api/permissions.ts` |
| `admin/permissions/page.tsx` | 1 | `/permissions/me` | `lib/api/permissions.ts` |
| `admin/users/page.tsx` | 2 | `/admin/users`, `/admin/invites` | `lib/api/users.ts` |
| `chat/page.tsx` | 1 | `/api/chat` | `lib/api/chat.ts` |
| `evaluate/page.tsx` | 1 | `/evaluate` | `lib/api/evaluate.ts` |
| `evaluate/evaluate-list-view.tsx` | 1 | `/evaluate/runs` | `lib/api/evaluate.ts` |
| `evaluate/evaluate-new-form.tsx` | 1 | `/evaluate/runs` | `lib/api/evaluate.ts` |
| `knowledge/dataset-documents/page.tsx` | 1 | `/kg/datasets` | `lib/api/knowledge.ts` |
| `knowledge/datasets/page.tsx` | 1 | `/kg/datasets` | `lib/api/knowledge.ts` |
| `knowledge/documents/page.tsx` | 1 | `/kg/documents` | `lib/api/knowledge.ts` |
| `knowledge/graph/page.tsx` | 1 | `/kg/graph` | `lib/api/knowledge.ts` |
| `layout.tsx` | 1 | `/api/permissions/me` | `lib/api/permissions.ts` |
| `submissions/page.tsx` | 3 | `/approvals` | `lib/api/approvals.ts` |

### components（4 个文件，5 处）

| 文件 | 处 | 硬编码路径 | 改为 |
|------|----|-----------|------|
| `auth-bootstrap.tsx` | 1 | `/api/auth/anon` | `lib/api/auth.ts` |
| `client-page-guard.tsx` | 1 | `/api/permissions/me` | `lib/api/permissions.ts` |
| `schema-browser.tsx` | 1 | `/api/kg/schema` | `lib/api/knowledge.ts` |
| `composer-attachments.tsx` | 2 | `/api/chat/files/presign`, `/api/chat/files/finalize` | `lib/api/chat.ts` |

### lib 非 api 目录（5 个文件，7 处）

| 文件 | 处 | 改为 |
|------|----|------|
| `lib/auth/permission.ts` | 1 | import from `lib/api/` |
| `lib/auth/permissions.ts` | 1 | import from `lib/api/` |
| `lib/chat/api.ts` | 3 | 已部分使用 lib/api/chat.ts |
| `lib/hooks/use-permissions.ts` | 1 | import from `lib/api/permissions.ts` |
| `lib/buyer-profile/api.ts` | 1 | 整体搬迁至 `lib/api/buyer-profile.ts` |

### 根目录（3 个文件）

| 文件 | 处理方式 |
|------|---------|
| `proxy.ts` | 保留（dev proxy 配置） |
| `hooks/use-lookup.ts` | 调 lib/api/lookups.ts |
| `app/middleware.ts` | 保留（路由中间件） |

---

### Task 0: lib/api/* 对象模式 → 独立函数导出 (2026-06-22 新规范)

整改 14 个 `lib/api/*.ts` 文件，把 `export const xxxApi = { ... }` 改为独立函数导出。同时更新所有消费者文件中的 import 和调用方式。

`lib/api/lookups.ts` 已经是独立函数导出，不在此列。

**受影响文件：**

| 文件 | 当前模式 | 消费者文件数 |
|------|---------|-------------|
| `lib/api/approvals.ts` | `export const approvalsApi = { ... }` | 3 |
| `lib/api/chat.ts` | `export const chatApi = { ... }` | 4 |
| `lib/api/chat-share.ts` | `export const chatShareApi = { ... }` | 3 |
| `lib/api/evaluate.ts` | `export const evaluateApi = { ... }` | 3 |
| `lib/api/health.ts` | `export const healthApi = { ... }` | 2 |
| `lib/api/ingest.ts` | `export const ingestApi = { ... }` | 4 |
| `lib/api/knowledge.ts` | `export const knowledgeApi = { ... }` | 5 |
| `lib/api/memory.ts` | `export const memoryApi = { ... }` | 2 |
| `lib/api/system.ts` | `export const systemApi = { ... }` | 2 |
| `lib/api/account.ts` | `export const accountApi = { ... }` | 3 |
| `lib/api/users.ts` | `export const usersApi = { ... }` | 0 |
| `lib/api/permissions.ts` | `export const permissionsApi = { ... }` | 0 |
| `lib/api/auth.ts` | `export const authApi = { ... }` | 0 |
| `lib/api/buyer-profile.ts` | `export const buyerProfileApi = { ... }` | 0 |

- [ ] **0a: 提取对象方法到独立函数 — 14 个 lib/api 文件**

每个文件将 `export const xxxApi = { fn1: ..., fn2: ... }` 改为：

```typescript
// 改前
export const healthApi = {
  fetchDifyHealth: (): Promise<{ ok: boolean }> => apiFetch<{ ok: boolean }>("/api/kg/health"),
  fetchSystem: (): Promise<HealthPayload> => apiFetch<HealthPayload>("/api/health/system"),
};

// 改后
export const fetchDifyHealth = (): Promise<{ ok: boolean }> => apiFetch<{ ok: boolean }>("/api/kg/health");
export const fetchSystem = (): Promise<HealthPayload> => apiFetch<HealthPayload>("/api/health/system");
```

**注意**：`chat.ts` 的 `sendMessage` 和 `chatApi.getToken()` 使用 `this` 引用内部方法，改为独立函数后需调整：

```typescript
// 改前
export const chatApi = {
  getToken(): string { return process.env.NEXT_PUBLIC_CHAT_TOKEN ?? ""; },
  async sendMessage(body: SendMessageInput): Promise<ReadableStream<Uint8Array>> {
    const res = await apiProxy("/api/chat/messages", {
      body,
      headers: { "Content-Type": "application/json", "x-chat-token": this.getToken() },
      method: "POST",
    });
    ...
  },
};

// 改后
const getChatToken = (): string => process.env.NEXT_PUBLIC_CHAT_TOKEN ?? "";

export const sendMessage = async (body: SendMessageInput): Promise<ReadableStream<Uint8Array>> => {
  const res = await apiProxy("/api/chat/messages", {
    body,
    headers: { "Content-Type": "application/json", "x-chat-token": getChatToken() },
    method: "POST",
  });
  ...
};

export const uploadFile = async (file: File): Promise<{ uploadFileId: string; uri: string }> => {
  const formData = new FormData();
  formData.append("file", file);
  return apiFetch("/api/chat/files", { body: formData, method: "POST" });
};
```

同样，`ingest.ts` 内部通过 `ingestApi.taskUrl(id)` 引用自身方法，改为独立函数后直调：

```typescript
// 改前
export const ingestApi = {
  fetchTask: (id) => apiFetch(ingestApi.taskUrl(id)),
  taskUrl: (id) => `/api/ingest/tasks/${encodeURIComponent(id)}`,
  ...
};

// 改后 — URL 工厂函数保持同文件，方法函数直接引用
export const taskUrl = (id: string): string => `/api/ingest/tasks/${encodeURIComponent(id)}`;
export const taskDownloadUrl = (id: string): string => `/api/ingest/tasks/${encodeURIComponent(id)}/download`;
export const taskFileUrl = (taskId: string, name: string): string =>
  `/api/ingest/tasks/${encodeURIComponent(taskId)}/files/${encodeURIComponent(name)}`;
export const tasksUrl = (): string => "/api/ingest/tasks";

export const fetchTask = (id: string): Promise<IngestTask> => apiFetch<IngestTask>(taskUrl(id));
export const fetchTasks = (): Promise<IngestTask[]> => apiFetch<IngestTask[]>(tasksUrl());
```

**Type exports 保持不变** — 接口/类型定义不挪动。

- [ ] **0b: 更新 barrel export**

`lib/api/index.ts` 加缺失的 barrel export（account, auth, buyer-profile, permissions, users）。

- [ ] **0c: 更新所有消费者 import**

批量替换每个消费者文件中的 `import { xxxApi } from "@/lib/api/xxx"` → `import { fn1, fn2 } from "@/lib/api/xxx"`，`xxxApi.xxx()` → `xxx()`。

完整消费者清单：

**evaluateApi:**
- `app/[locale]/evaluate/_components/evaluate-list-view.tsx` → `import { evaluateApi }` → `import { runsUrl, runDetailUrl, cancelRun }`
- `app/[locale]/evaluate/new/_components/evaluate-new-form.tsx` → `import { evaluateApi }` → `import { createRun }`
- `app/[locale]/evaluate/_components/evaluate-list-view.test.tsx` — 测试文件 mock 调整

**healthApi:**
- `components/common/health-dot.tsx` → `import { healthApi }` → `import { fetchDifyHealth }`
- `components/common/health-dot.test.tsx` — 测试 mock 调整
- `app/[locale]/health/_components/health-client.tsx` → `import { type HealthPayload, healthApi }` → `import { type HealthPayload, fetchSystem }`

**systemApi:**
- `app/[locale]/decode/series-dialog.tsx` → `import { systemApi }` → `import { decode }`
- `app/[locale]/decode/page.tsx` → `import { systemApi }` → `import { decode, listSeries }`
- `app/[locale]/decode/page.test.tsx` — 测试 mock 调整

**chatApi:**
- `components/chat/chat-shell.tsx` → `import { chatApi }` → `import { sendMessage }`
- `components/chat/composer-attachments.tsx` → `import { chatApi }` → `import { uploadFile }`
- `components/chat/chat-shell.test.tsx` — 测试 mock 调整
- `components/chat/composer-attachments.test.tsx` — 测试 mock 调整

**chatShareApi:**
- `components/chat/share-dialog.tsx` → `import { chatShareApi }` → `import { create, revoke }`
- `components/chat/share-dialog.test.tsx` — 测试 mock 调整
- `app/[locale]/chat/s/[shareId]/page.tsx` → `import { chatShareApi }` → `import { get }`

**memoryApi:**
- `components/chat/memory-management-dialog.tsx` → `import { memoryApi }` → `import { add, list, search, update, delete: deleteMemory }`
- `components/chat/memory-management-dialog.test.tsx` — 测试 mock 调整

**knowledgeApi:**
- `components/knowledge/dataset-switcher.tsx` → `import { knowledgeApi }` → `import { fetchDatasets }`
- `components/knowledge/domain-switcher.tsx` → `import { knowledgeApi }` → `import { fetchSchemas }`
- `app/[locale]/knowledge/batch/page.tsx` → `import { type BatchState, knowledgeApi }` → `import { type BatchState, fetchBatchStatus }`
- `app/[locale]/knowledge/dataset-documents/[dataset_id]/_components/dataset-documents-table.tsx` — 仅 type import
- `app/[locale]/admin/profile-fields/page.tsx` → `import { buyerProfileApi }` → `import { listFieldConfigs, createFieldConfig, updateFieldConfig, deleteFieldConfig }`

**approvalsApi (via barrel):**
- `app/[locale]/submissions/_components/approval-row.tsx` → `import { approvalsApi }` → `import { approve, reject }`
- 同上用的 `type Approval` / `type RejectReasonKey` 留给类型

**ingestApi (via barrel):**
- `app/[locale]/output/new/page.tsx` → `import { ingestApi }` → `import { upload }`
- `app/[locale]/output/new/page.test.tsx` — 测试 mock 调整
- `app/[locale]/output/_components/output-list-client.tsx` → `import { ingestApi }` → `import { fetchTasks, taskDownload }`
- `app/[locale]/output/[task_id]/_components/task-detail-client.tsx` → `import { ingestApi }` → `import { fetchTask, taskDownload, taskDownloadUrl }`
- `app/[locale]/output/[task_id]/[file]/page.tsx` → `import { ingestApi }` → `import { fetchTask, taskFileUrl }`

**accountApi:**
- `app/[locale]/account/restore/page.tsx` → `import { accountApi }` → `import { getDeletion, cancelDeletion, requestDeletion }`
- `app/[locale]/account/settings/page.tsx` → `import { accountApi }` → `import { getProfile, updateProfile, uploadAvatar, deleteAvatar, changeEmail, changePassword }`
- `app/_actions/account-settings.ts` → `import { accountApi }` → `import { updateProfile, uploadAvatar, deleteAvatar, changeEmail, changePassword, requestDeletion, cancelDeletion }`

**usersApi:**
- `app/[locale]/admin/users/page.tsx` → `import { usersApi }` → `import { list, createInvite }`
- `app/[locale]/admin/invites/page.tsx` → `import { usersApi }` → `import { createInvite }`

**permissionsApi:**
- `app/[locale]/admin/permissions/create-role-dialog.tsx` → `import { permissionsApi }` → `import { getMyPermissions }`
- `app/[locale]/admin/permissions/permissions-admin-client.tsx` → `import { permissionsApi }` → `import { getAll, patch }`
- `app/[locale]/admin/permissions/page.tsx` → `import { permissionsApi }` → `import { getMyPermissions }`

**authApi:**
- `components/auth/auth-bootstrap.tsx` → `import { authApi }` → `import { createAnonToken }`
- `components/auth/auth-bootstrap.test.tsx` — 测试 mock 调整

**buyerProfileApi:**
- `lib/buyer-profile/hooks.ts` → `import { buyerProfileApi }` → `import { list, get, update, archive, getChanges }`

- [ ] **0d: 更新 lib 下直接引用 apiFetch 的文件**

以下文件直接 import `apiFetch` 并有硬编码 `/api` 路径，改为调对应 `lib/api/xxx` 的函数：

- `lib/auth/permission.ts` → 改调 `permissionsApi` 函数
- `lib/auth/permissions.ts` → 改调 `permissionsApi` 函数
- `lib/chat/api.ts` → 已部分用 `chatApi`，完成剩余迁移
- `lib/hooks/use-permissions.ts` → 改调 `permissionsApi` 函数

- [ ] **0e: 验证**

```bash
cd packages/web
bun run test
# Expected: 0 new failed (允许 pre-existing 2 个 chat migration 失败)
bun x tsc --noEmit
bun x oxlint lib/api/ --deny-warnings
```

- [ ] **0f: Commit**

```bash
git add packages/web/lib/api/ packages/web/lib/ packages/web/components/ packages/web/app/
git commit -m "refactor: lib/api/* 对象模式改为独立函数导出 (Task 0)"
```

---

### Task 1: 新建缺失的 API wrapper

**新建 5 个 lib/api 文件（注意：使用独立函数导出模式）：**

- [ ] **1a: `lib/api/account.ts`** — 封装 `/account/*` 路径（profile, avatar, email, password, deletion, login, logout, forgot-password, reset-password）

```typescript
import { apiFetch } from "./config";

export const login = (body: { email: string; password: string }, headers?: Record<string, string>) =>
  apiFetch<{ token: string }>("/api/account/login", { body, headers, method: "POST" });

export const logout = (headers?: Record<string, string>) =>
  apiFetch<void>("/api/account/logout", { headers, method: "POST" });

export const forgotPassword = (email: string, headers?: Record<string, string>) =>
  apiFetch<{ reset_url?: string }>("/api/account/forgot-password", {
    body: { email }, headers, method: "POST",
  });

export const resetPassword = (body: { token: string; password: string }, headers?: Record<string, string>) =>
  apiFetch<void>("/api/account/reset-password", { body, headers, method: "POST" });

export const getProfile = (headers?: Record<string, string>) =>
  apiFetch("/api/account/profile", { headers });

export const updateProfile = (body: { display_name: string }, headers?: Record<string, string>) =>
  apiFetch<void>("/api/account/profile", { body, headers, method: "PATCH" });

export const uploadAvatar = (fd: FormData, headers?: Record<string, string>) =>
  apiFetch<{ avatar_url: string }>("/api/account/avatar", { body: fd, headers, method: "POST" });

export const deleteAvatar = (headers?: Record<string, string>) =>
  apiFetch<void>("/api/account/avatar", { headers, method: "DELETE" });

export const getDeletion = (headers?: Record<string, string>) =>
  apiFetch("/api/account/deletion", { headers });

export const requestDeletion = (
  body: { current_password: string; confirm_text: string },
  headers?: Record<string, string>,
) => apiFetch<{ restore_url: string; expires_at: string }>("/api/account/deletion", {
  body, headers, method: "POST",
});

export const cancelDeletion = (body: { current_password: string }, headers?: Record<string, string>) =>
  apiFetch<void>("/api/account/deletion", { body, headers, method: "DELETE" });

export const changeEmail = (
  body: { new_email: string; current_password: string },
  headers?: Record<string, string>,
) => apiFetch<{ verification_url: string }>("/api/account/email", {
  body, headers, method: "PATCH",
});

export const changePassword = (
  body: { current_password: string; new_password: string; confirm: string },
  headers?: Record<string, string>,
) => apiFetch<void>("/api/account/password", { body, headers, method: "PATCH" });
```

- [ ] **1b: `lib/api/users.ts`** — 封装 `/admin/users` 和 `/admin/invites` 路径

```typescript
import { apiFetch } from "./config";

export const list = () => apiFetch("/api/admin/users");

export const createInvite = (email: string, headers?: Record<string, string>) =>
  apiFetch("/api/admin/invites", { body: { email }, headers, method: "POST" });
```

- [ ] **1c: `lib/api/permissions.ts`** — 封装 `/permissions` 和 `/permissions/me` 路径

```typescript
import { apiFetch } from "./config";

export const getMyPermissions = () =>
  apiFetch<{ role: string; allowed: string[]; pages: any[] }>("/api/permissions/me");

export const getAll = () => apiFetch("/api/permissions");

export const patch = (updates: any[], headers?: Record<string, string>) =>
  apiFetch("/api/permissions", { body: { updates }, headers, method: "PATCH" });
```

- [ ] **1d: `lib/api/auth.ts`** — 封装 `/auth/anon` 路径

```typescript
import { apiFetch } from "./config";

export const createAnonToken = () =>
  apiFetch<{ token: string }>("/api/auth/anon", { method: "POST" });
```

- [ ] **1e: `lib/api/buyer-profile.ts`** — 从 `lib/buyer-profile/api.ts` 搬迁

```typescript
import { apiFetch } from "./config";

const BASE = "/api/buyer-profiles";

export const list = (params?: Record<string, string>) => apiFetch(BASE, { params });
export const get = (id: string) => apiFetch(`${BASE}/${id}`);
export const update = (id: string, body: any) => apiFetch(`${BASE}/${id}`, { method: "PATCH", body });
export const archive = (id: string) => apiFetch(`${BASE}/${id}`, { method: "DELETE" });
export const getChanges = (id: string) => apiFetch(`${BASE}/${id}/changes`);
export const listFieldConfigs = () => apiFetch(`${BASE}/fields`);
export const createFieldConfig = (body: any) => apiFetch(`${BASE}/fields`, { method: "POST", body });
export const updateFieldConfig = (code: string, body: any) =>
  apiFetch(`${BASE}/fields/${code}`, { method: "PATCH", body });
export const deleteFieldConfig = (code: string) =>
  apiFetch(`${BASE}/fields/${code}`, { method: "DELETE" });
```

- [ ] **1f: Run oxlint**

```bash
cd packages/web && bun x oxlint lib/api/{account,users,permissions,auth,buyer-profile}.ts --deny-warnings
```

- [ ] **1g: Commit**

```bash
git add packages/web/lib/api/{account,users,permissions,auth,buyer-profile}.ts
git commit -m "feat: add 5 API wrapper modules (account/users/permissions/auth/buyer-profile)"
```

---

### Task 2: 修改 _actions 文件（3 个文件，13 处）

- [ ] **2a: `app/_actions/account-settings.ts`**

改前:
```typescript
import { apiFetch } from "@/lib/api/config";
```
改后:
```typescript
import { updateProfile, uploadAvatar, deleteAvatar, changeEmail, changePassword, requestDeletion, cancelDeletion } from "@/lib/api/account";
```

改前: `apiFetch("/api/account/profile", { body: ..., headers: await serverAuthHeaders(), method: "PATCH" })`
改后: `updateProfile({ display_name })`（注意 server action 需要传 headers，所以每个函数需支持 headers 参数）

- [ ] **2b: `app/[locale]/_actions/account.ts`**

改前:
```typescript
import { apiFetch } from "@/lib/api/config";
```
改后:
```typescript
import { login, logout, forgotPassword, resetPassword } from "@/lib/api/account";
import { createInvite } from "@/lib/api/users";
```

替换 5 处 `apiFetch("/api/account/...")` 和 `apiFetch("/api/admin/users")`。

- [ ] **2c: `app/[locale]/_actions/evaluate.ts`**

改前: `apiFetch("/api/evaluate/runs")`
改后: 用 `lib/api/evaluate.ts` 中的 `createRun()` / `createRunJson()`

- [ ] **2d: 验证**

```bash
cd packages/web && bun run test
Expected: 0 new failed
bun x tsc --noEmit
bun x oxlint app/_actions/ app/\[locale\]/_actions/ --deny-warnings
```

- [ ] **2e: Commit**

```bash
git add packages/web/app/_actions/ packages/web/app/\[locale\]/_actions/
git commit -m "refactor: _actions use lib/api/ wrappers"
```

---

### Task 3: 修改 [locale] pages（20 个文件，24 处）

- [ ] **3a: knowledge/*（4 个文件）**

改前: `import { apiFetch } from "@/lib/api/config"`
改后: `import { fetchDatasets, ... } from "@/lib/api/knowledge"`

文件:
- `knowledge/dataset-documents/[dataset_id]/page.tsx`
- `knowledge/datasets/page.tsx`
- `knowledge/documents/page.tsx`
- `knowledge/graph/page.tsx`

- [ ] **3b: evaluate/*（3 个文件）**

改前: `import { apiFetch } from "@/lib/api/config"`
改后: `import { runsUrl, ... } from "@/lib/api/evaluate"`

文件:
- `evaluate/page.tsx`
- `evaluate/_components/evaluate-list-view.tsx`
- `evaluate/new/_components/evaluate-new-form.tsx`

- [ ] **3c: submissions/*（1 个文件）**

- `submissions/page.tsx` — 3 处 → 改调 `lib/api/approvals.ts`

- [ ] **3d: admin/*（4 个文件）**

- `admin/invites/page.tsx` — 2 处 → 改调 `lib/api/users.ts`
- `admin/permissions/*（3 个文件）` — 3 处 → 改调 `lib/api/permissions.ts`
- `admin/users/page.tsx` — 2 处 → 改调 `lib/api/users.ts`

- [ ] **3e: account/*（2 个文件）**

- `account/restore/page.tsx` → 改调 `lib/api/account.ts`
- `account/settings/page.tsx` → 改调 `lib/api/account.ts`

- [ ] **3f: 其他（2 个文件）**

- `chat/page.tsx` → 改调 `lib/api/chat.ts`
- `layout.tsx` → 改调 `lib/api/permissions.ts`

- [ ] **3g: 验证**

```bash
cd packages/web
grep -rn '"/api' app/\[locale\]/ --include="*.ts" --include="*.tsx" \
  | grep -v "node_modules\|\.test\|\.next\|_actions" || echo "✅ 0 violations"
bun run test
```

- [ ] **3h: Commit**

```bash
git add packages/web/app/\[locale\]/
git commit -m "refactor: [locale] pages use lib/api/ wrappers"
```

---

### Task 4: 修改 components（4 个文件，5 处）

- [ ] **4a: `auth/auth-bootstrap.tsx`**

改前: `import { apiFetch } from "@/lib/api/config"` → `apiFetch<{ token: string }>("/api/auth/anon", { method: "POST" })`
改后: `import { createAnonToken } from "@/lib/api/auth"` → `createAnonToken()`

- [ ] **4b: `client-page-guard.tsx`**

改前: `import { apiFetch } from "@/lib/api/config"`
改后: `import { getMyPermissions } from "@/lib/api/permissions"`

- [ ] **4c: `knowledge/schema-browser.tsx`**

改前: `apiFetch("/api/kg/schema?domain=")`
改后: `fetchSchema(domain)` from `@/lib/api/knowledge`

- [ ] **4d: `chat/composer-attachments.tsx`**

改前: `apiFetch("/api/chat/files/presign")`, `apiFetch("/api/chat/files/finalize")`
改后: 用已存在的 `uploadFile()` from `@/lib/api/chat`

- [ ] **4e: 验证**

```bash
cd packages/web
grep -rn '"/api' components/ --include="*.tsx" --include="*.ts" \
  | grep -v "node_modules\|\.test" || echo "✅ 0 violations"
bun run test
```

- [ ] **4f: Commit**

```bash
git add packages/web/components/
git commit -m "refactor: components use lib/api/ wrappers"
```

---

### Task 5: 修改 lib 非 api 目录（5 个文件）

- [ ] **5a: `lib/buyer-profile/api.ts`** → 搬迁到 `lib/api/buyer-profile.ts`

建造 `lib/api/buyer-profile.ts`（Task 1e 已创建）。然后在 `lib/buyer-profile/hooks.ts` 中改 import:

```typescript
// 改前
import * as api from "./api";
// 改后
import { list, get, update, archive, getChanges } from "@/lib/api/buyer-profile";
```

删除 `lib/buyer-profile/api.ts`。

- [ ] **5b: `lib/auth/permission.ts`**

改 `import { apiFetch }` → `import { getMyPermissions }` from `@/lib/api/permissions`

- [ ] **5c: `lib/hooks/use-permissions.ts`**

改 `import { apiFetch }` → `import { getMyPermissions }` from `@/lib/api/permissions`

- [ ] **5d: `lib/chat/api.ts`**

改 3 处 `"/api"` 引用 → 改为调现有 `lib/api/chat.ts` wrapper 的函数

- [ ] **5e: 验证**

```bash
cd packages/web
grep -rn '"/api' lib/ --include="*.ts" --include="*.tsx" \
  | grep -v "node_modules\|\.test\|/lib/api/" || echo "✅ 0 violations"
bun run test
```

- [ ] **5f: Commit**

```bash
git rm packages/web/lib/buyer-profile/api.ts
git add packages/web/lib/
git commit -m "refactor: migrate lib/ modules to lib/api/ wrappers"
```

---

### Task 6: 最终验证

- [ ] **6a: 零硬编码检查 + 零对象模式检查**

```bash
cd packages/web
# 硬编码路径检查
grep -rn '"/api' --include="*.ts" --include="*.tsx" app/ components/ lib/ \
  | grep -v "node_modules\|\.test\|\.next\|/app/api/\|/lib/api/\|\.d\.ts" \
  || echo "✅ 0 API path violations"

# 对象模式检查（允许 lookups.ts 的独立函数模式）
grep -rn 'export const.*Api = {' --include="*.ts" lib/api/ \
  | grep -v "node_modules\|\.test" || echo "✅ 0 object pattern violations"
```

- [ ] **6b: 全量测试 + lint**

```bash
bun run test && bun run lint
Expected: 0 failed, 0 warnings
```

- [ ] **6c: 更新 barrel export**

确认 `lib/api/index.ts` 包含所有模块（补 missing 的）:
```typescript
export * from "./approvals";
// Auth.ts / auth.server.ts: 不走 barrel (auth 已删, auth.server 是 server-only + next/headers)
export * from "./chat";
export * from "./chat-share";  // 新增
export * from "./config";
export * from "./errors";
export * from "./evaluate";
export * from "./health";
export * from "./ingest";
export * from "./knowledge";
export * from "./lookups";     // 新增
export * from "./memory";      // 新增
export * from "./query-client";
export * from "./query-keys";
export * from "./system";
export * from "./account";     // 新增
export * from "./auth";        // 新增
export * from "./buyer-profile"; // 新增
export * from "./permissions"; // 新增
export * from "./users";       // 新增
```

- [ ] **6d: Final commit**

```bash
git add packages/web/lib/api/index.ts
git commit -m "refactor: update barrel exports for new API wrappers"
```

---

## 执行统计

| Task | 文件数 | 改动处 |
|------|--------|--------|
| Task 0: 对象→函数 | 14 lib/api + ~40 消费者 | ~80 处 |
| Task 1: 新建 wrapper | 5 | — |
| Task 2: _actions | 3 | 13 处 |
| Task 3: [locale] pages | 20 | 24 处 |
| Task 4: components | 4 | 5 处 |
| Task 5: lib 非 api | 5 | 7 处 |
| Task 6: 收尾 | 2 | — |
| **总计** | **~93** | **~130 处** |
