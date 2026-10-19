# React 19 + Next.js 16 全面改造 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `packages/web` 从 React 18 风格 (手写 isPending + onSubmit + FormData 拼装 + useState(ctx) 对象整体重渲染) 全面升级到 React 19 + Next.js 16 模式 (useActionState / useFormStatus / useOptimistic / useTransition / `use(promise)` / Context 简写), 干掉 30+ 处历史模板.

**Architecture:**
- **3 个层**: Server Action (server 端入口) / RSC 父 (数据预取) / Client child (交互态)
- **数据流方向**:
  - 一次性数据 → `use(promise)` + Suspense (Sprint 1.6, 6 处表格)
  - 轮询数据 → 保留 RQ `useQuery` (health/output/task detail 不变)
  - 表单提交 → `useActionState` + `<form action={serverAction}>` (Sprint 1.2, 7 个 form)
  - 异步操作 → `useTransition` (Sprint 1.1, 4 处 non-form)
  - 乐观更新 → `useOptimistic` (Sprint 2, 6 处)
  - 父子 pending 透传 → `useFormStatus` (Sprint 2.1, 5+ 处)
- **Context 简写**: `<Ctx value={...}>` 替 `<Ctx.Provider value={...}>` (Sprint 1.3, 3 处)
- **空 useCallback 清理**: deps 变 / 只 setState 的 6 处改普通函数 (Sprint 1.4)
- **错误兜底**: error.tsx / loading.tsx / not-found.tsx (Sprint 1.5, 4 文件)
- **拆 context** (方案 B): 4 处 ctx value 拆 dispatch / value 俩 ctx (Sprint 3.1-3.2)

**Tech Stack:**
- React 19.2 + React DOM 19.2
- Next.js 16.2 (App Router + RSC + Server Action)
- TypeScript 5.x + tsgo
- vitest 4.x + jsdom
- @tanstack/react-query 5.x (保留, 不替)
- bun (package manager)
- shadcn/ui (不动, 95+ forwardRef 保持)

**Spec:** [../specs/2026-06-14-react19-refactor-design.md](../specs/2026-06-14-react19-refactor-design.md) (15+1 章)
**Audit:** [../../audit/2026-06-14-react19-refactor.md](../../audit/2026-06-14-react19-refactor.md) (868 行)
**当前 commit:** `403da21` (audit v2 + spec § 16 Sprint 1.6)

---

## 文件结构总览 (33 任务, 6.2d 估)

| Sprint | 任务数 | 工作量 | 核心文件改动 |
|---|---|---|---|
| 1.1 useTransition | 4 | 0.3d | decode/output-new/batch/TaskDetailClient |
| 1.2 useActionState | 7 | 1.5d | login/forgot/reset/invite + 2 dialog + decode (含新建 4-5 server actions) |
| 1.3 Context 简写 | 3 | 0.1d | form/theme-provider/app-data |
| 1.4 useCallback 清理 | 6 | 0.3d | ChatShell×5 + decode×1 |
| 1.5 error.tsx 等 | 4 | 0.5d | 新建 global-error/error/loading/not-found |
| 1.6 use(promise) | 4 | 0.5d | DataTableSkeleton 新建 + knowledge 4 + admin 2 + 回归 |
| 2 useFormStatus + useOptimistic | 6 | 1.5d | SubmitButton 新建 + 5 form + ChatShell/ApprovalRow/TaskDetail/AdminUsers/AdminInvites |
| 3 拆 context + Compiler | 3 | 1.0d | form/theme-provider 拆 ctx + Compiler 评估 |
| 4+ 滚动 | 滚动 | 0.5d/sprint | generateMetadata 逐 page + Activity 评估 + Compiler 扩面 |

**并行性**: Sprint 1.1-1.6 互不依赖, 可并行做; Sprint 2 依赖 1.2 (form 重构); Sprint 3 依赖 1.3 (Context 简写).

---

## Sprint 1.1: useTransition 替 useState(busy) (4 处, 0.3d)

### Task 1.1.1: decode/page.tsx submit 改 useTransition

**Files:**
- Modify: `packages/web/app/[locale]/decode/page.tsx:103-130`
- Test: `packages/web/app/[locale]/decode/page.test.tsx`

- [ ] **Step 1: 改前跑测试确认基线绿**

```bash
cd packages/web && bun x vitest run app/\[locale\]/decode/page.test.tsx
```

- [ ] **Step 2: 改造**

改前 (`page.tsx:103-130`):
```tsx
const [model, setModel] = useState("");
const [result, setResult] = useState<DecodeResult | null>(null);
const [err, setErr] = useState<string | null>(null);
const [loading, setLoading] = useState(false);
...
const submit = useCallback(async () => {
  setErr(null);
  setResult(null);
  setLoading(true);
  try {
    setResult(await systemApi.decode(model));
  } catch (error) {
    setErr(formatDecodeError(error));
  } finally {
    setLoading(false);
  }
}, [model]);
```

改后:
```tsx
import { useEffect, useRef, useState, useTransition } from "react";
...
const [model, setModel] = useState("");
const [result, setResult] = useState<DecodeResult | null>(null);
const [err, setErr] = useState<string | null>(null);
const [isPending, startTransition] = useTransition();
...
const submit = () => {
  startTransition(async () => {
    setErr(null);
    setResult(null);
    try {
      setResult(await systemApi.decode(model));
    } catch (error) {
      setErr(formatDecodeError(error));
    }
  });
};
```

下游引用: `useKeyboardSubmit(model, loading, submit)` → `useKeyboardSubmit(model, isPending, submit)`; `<Button onClick={submit} disabled={loading}>` → `<Button onClick={submit} disabled={isPending}>`.

- [ ] **Step 3: 跑测试确认绿 + typecheck**

```bash
bun x vitest run app/\[locale\]/decode/page.test.tsx
bun x tsc --noEmit
```

- [ ] **Step 4: e2e decode 路径**

```bash
cd ../.. && bun run test:e2e -- decode
```

### Task 1.1.2-1.1.4: 同步改 output/new + knowledge/batch + TaskDetailClient.download

3 处同型, 跟 1.1.1 同流程. 唯一区别:
- 1.1.2 output/new: `useState(busy)` + `<Button onClick={submit} disabled={busy}>`
- 1.1.3 knowledge/batch: `useState(submitting)` + `onClick={onSubmit}`
- 1.1.4 TaskDetailClient: 自定义 `useTaskDownload` hook 内部 `useState(downloading)` + `setDownloading(true) + await + setDownloading(false)`, 改 useTransition (跟同文件 `useTaskCancel` 一致)

**每处 TDD 步骤**:
- [ ] 改前跑测试绿
- [ ] 改 useTransition
- [ ] 改测试 (如 hook 内部 pending 暴露)
- [ ] 跑测试 + typecheck + e2e

---

## Sprint 1.2: 7 个 form useActionState 化 (1.5d)

### Task 1.2.1: login/page.tsx + loginAction (模板)

**Files:**
- Modify: `packages/web/app/[locale]/login/page.tsx`
- Modify: `packages/web/app/[locale]/_actions/account.ts:loginAction`
- Test: `packages/web/app/[locale]/login/page.test.tsx`

- [ ] **Step 1: 改前跑测试确认基线绿**

```bash
cd packages/web && bun x vitest run app/\[locale\]/login/page.test.tsx
```

- [ ] **Step 2: loginAction 改造** (`_actions/account.ts`)

改前 (可能 `useState(email) + useState(password) + useTransition` 调 server action):
```ts
export async function loginAction(formData: FormData) {
  // 旧签名
}
```

改后 (接 useActionState 的 `(prevState, formData) => state` 签名):
```ts
import { redirect } from "next/navigation";

export type LoginState = { ok: boolean; error: string | null };

export async function loginAction(
  _prev: LoginState,
  formData: FormData,
): Promise<LoginState> {
  const email = formData.get("email");
  const password = formData.get("password");
  const next = formData.get("next") ?? "/";
  if (!email || !password) {
    return { ok: false, error: "邮箱或密码错" };
  }
  try {
    const r = await apiPost("/api/account/login", { email, password });
    // 写 cookie + redirect 替 router.push
    (await cookies()).set("rag_user_token", r.token, { httpOnly: true, secure: true });
    redirect(next as string);
  } catch (e) {
    return { ok: false, error: e instanceof Error ? e.message : "邮箱或密码错" };
  }
}
```

- [ ] **Step 3: page.tsx 改造**

改前 (36 行):
```tsx
"use client";
import { useState, useTransition } from "react";
...
const [email, setEmail] = useState("");
const [password, setPassword] = useState("");
const [err, setErr] = useState<string | null>(null);
const [pending, startTransition] = useTransition();
const onSubmit = (e: React.FormEvent) => {
  e.preventDefault();
  setErr(null);
  startTransition(async () => {
    const fd = new FormData();
    fd.append("email", email);
    fd.append("password", password);
    const res = await loginAction(fd);
    if (!res.ok) { setErr(res.error ?? t("邮箱或密码错")); return; }
    const next = search.get("next") ?? "/";
    router.push(next);
    router.refresh();
  });
};
return (
  <div>
    <h1>{t("登录")}</h1>
    {err && <ErrorBanner variant="destructive" description={err} />}
    <form onSubmit={onSubmit}>
      <label>{t("邮箱")}</label>
      <Input type="email" value={email} onChange={...} required />
      <label>{t("密码")}</label>
      <Input type="password" value={password} onChange={...} required />
      <Button type="submit" disabled={pending || !email || !password}>{t("登录")}</Button>
    </form>
  </div>
);
```

改后 (12 行):
```tsx
"use client";
import { useActionState } from "react";
import { useSearchParams } from "next/navigation";
import { loginAction, type LoginState } from "@/app/[locale]/_actions/account";
import { SubmitButton } from "@/components/common/submit-button";  // Sprint 2.1 建
...
export default function LoginPage() {
  const t = useTranslations();
  const [state, formAction, isPending] = useActionState<LoginState, FormData>(loginAction, { ok: false, error: null });
  const search = useSearchParams();
  const next = search.get("next") ?? "/";
  return (
    <div>
      <h1>{t("登录")}</h1>
      {state.error && <ErrorBanner variant="destructive" description={state.error} />}
      <form action={formAction}>
        <input type="hidden" name="next" value={next} />
        <label>{t("邮箱")}</label>
        <Input name="email" type="email" required />
        <label>{t("密码")}</label>
        <Input name="password" type="password" required />
        <SubmitButton pendingLabel={t("提交中…")} className="w-full">{t("登录")}</SubmitButton>
      </form>
    </div>
  );
}
```

**注**: Sprint 1.2 阶段, SubmitButton 还没建 (Sprint 2.1 才建), 暂时用普通 `<Button disabled={isPending}>{isPending ? t("提交中…") : t("登录")}</Button>`.

- [ ] **Step 4: 测试改造**

`page.test.tsx` 改 mock 路径: `vi.mock("next/navigation", () => ({ useSearchParams: ..., redirect: vi.fn() }))` + `vi.mock("@/app/[locale]/_actions/account", () => ({ loginAction: vi.fn(async () => ({ ok: false, error: "mock err" })) }))`

- [ ] **Step 5: 跑测试 + typecheck + e2e login**

```bash
bun x vitest run app/\[locale\]/login/page.test.tsx
bun x tsc --noEmit
cd ../.. && bun run test:e2e -- login
```

### Task 1.2.2-1.2.6: forgot / reset / invite / ResetPasswordDialog / CreateInviteDialog

5 处 form 同 1.2.1 模板. 每处:
- [ ] 改前测试基线
- [ ] 加 server action (在 `_actions/account.ts`)
- [ ] 改 page/dialog: useActionState + `<form action>`
- [ ] 测试改 mock
- [ ] 跑测试 + typecheck + e2e

**Server Action 命名 (5 个新增)**:
- `forgotPasswordAction` (forgot-password/page.tsx)
- `resetPasswordAction` (reset-password/page.tsx)
- `acceptInviteAction` (invite/[token]/page.tsx)
- `resetPasswordAdminAction` (admin users dialog, 改 user id 密码)
- `createInviteAction` (admin users dialog, 创 invite)

### Task 1.2.7: decode/page.tsx (补漏) — 跟 1.1.1 合并

decode 是 form 但走 client fetch, 改方案 A (新建 `_actions/system.ts` 包 `systemApi.decode()`). 跟 1.1.1 同步做 (都改 submit).

- [ ] 新建 `_actions/system.ts` 包含 `decodeAction(prevState, formData)`
- [ ] 改 decode/page.tsx: useActionState + `<form action>`, 删 `useState(loading)` + `useTransition` + `submit` useCallback
- [ ] 删 `useCallback` import (跟 1.4.6 同步)
- [ ] 测试改 mock: `vi.mock("@/app/[locale]/_actions/system", ...)`
- [ ] 跑测试 + typecheck + e2e

---

## Sprint 1.3: Context 简写 3 处 (0.1d)

### Task 1.3.1: theme-provider.tsx

**Files:** `packages/web/components/theme-provider.tsx:254`

- [ ] **Step 1: 改前跑测试**

```bash
cd packages/web && bun x vitest run components/theme-provider.test.tsx components/header.test.tsx
```

- [ ] **Step 2: 改造**

```tsx
// 改前
return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;

// 改后
return <ThemeContext value={value}>{children}</ThemeContext>;
```

- [ ] **Step 3: 跑测试 + typecheck**

### Task 1.3.2: app-data.tsx

`packages/web/lib/store/app-data.tsx:26`

- [ ] 改前测试 (无 .test.tsx, typecheck 兜底)
- [ ] 改造: `<Ctx.Provider value={...}>` → `<Ctx value={...}>`
- [ ] typecheck

### Task 1.3.3: form/form.tsx FormContext

`packages/web/components/common/form/form.tsx:116-120`

- [ ] 改前跑 `bun x vitest run components/common/form/`
- [ ] 改造: `<FormContext.Provider value={ctx}>...</FormContext.Provider>` → `<FormContext value={ctx}>...{children}...</FormContext>`
- [ ] 跑测试 + typecheck

---

## Sprint 1.4: 方案 A 6 处 useCallback → 普通函数 (0.3d)

### Task 1.4.1-1.4.5: ChatShell.tsx 5 处

`packages/web/components/chat/ChatShell.tsx`

- [ ] 改前跑 `bun x vitest run components/chat/`
- [ ] 改造 5 处 (89/93/115/119/298 行):
  - `handleDelete` deps=[] 只 setState → 普通函数
  - `confirmDelete` deps=[3 state] 变 → 普通函数
  - `handleSelect` deps=[] 只 setState → 普通函数
  - `handleSend` deps=[4 vars] 变 → 普通 async 函数
  - `handleStop` deps=[streamingConvId] 变 → 普通函数
- [ ] 保留: `persistConv` / `persistMessages` / `handleNew` (deps 稳定)
- [ ] 跑测试 + typecheck + e2e chat

### Task 1.4.6: decode/page.tsx (跟 1.1.1 / 1.2.7 同步)

- [ ] 跟 1.2.7 一起删 `useCallback` import + `submit` useCallback 改普通函数

---

## Sprint 1.5: error.tsx / loading.tsx / not-found.tsx (0.5d)

### Task 1.5.1: global-error.tsx

- [ ] 新建 `packages/web/app/global-error.tsx`:
  ```tsx
  "use client";
  // 根 layout 崩溃兜底, 自带 <html>+<body>
  export default function GlobalError({ error, reset }: { error: Error; reset: () => void }) {
    return (
      <html><body>
        <h1>出错了</h1>
        <button onClick={reset}>重试</button>
      </body></html>
    );
  }
  ```
- [ ] 验证: `bun x tsc --noEmit`

### Task 1.5.2: app/[locale]/error.tsx

- [ ] 新建 `packages/web/app/[locale]/error.tsx` (用 audit § 2.1 模板)
- [ ] 验证: 跑 1 个 RSC 抛错测试 (datasets/nodes 任一)

### Task 1.5.3: app/[locale]/loading.tsx

- [ ] 新建 `packages/web/app/[locale]/loading.tsx` (Suspense fallback, shadcn Skeleton)

### Task 1.5.4: app/[locale]/not-found.tsx

- [ ] 新建 `packages/web/app/[locale]/not-found.tsx` (走 i18n)
- [ ] 验证: `curl /zh/no-such-page` 返 not-found 页面

---

## Sprint 1.6: use(promise) 替 RSC `await data → initialData` (0.5d, 4 task)

### Task 1.6.1: DataTableSkeleton 通用 Suspense fallback

**Files:** `packages/web/components/common/data-table/data-table-skeleton.tsx` (新建)

- [ ] 新建组件:
  ```tsx
  import { Skeleton } from "@/components/ui/skeleton";
  export function DataTableSkeleton({ columns = 3, rows = 5 }: { columns?: number; rows?: number }) {
    return (
      <div className="space-y-2">
        <Skeleton className="h-10 w-full" />  {/* header */}
        {Array.from({ length: rows }).map((_, i) => (
          <Skeleton key={i} className="h-12 w-full" />
        ))}
      </div>
    );
  }
  ```
- [ ] 验证: typecheck

### Task 1.6.2: knowledge 4 处 (datasets / nodes / relations / dataset-documents)

**Files:**
- Modify: `packages/web/app/[locale]/knowledge/datasets/page.tsx:11` + `_components/DatasetsTable.tsx`
- Modify: `packages/web/app/[locale]/knowledge/nodes/page.tsx:15` + `_components/NodesTable.tsx`
- Modify: `packages/web/app/[locale]/knowledge/relations/page.tsx:15` + `_components/RelationsTable.tsx`
- Modify: `packages/web/app/[locale]/knowledge/dataset-documents/[dataset_id]/page.tsx:65` + `_components/DatasetDocumentsTable.tsx`
- Tests: 4 个 `page.test.tsx` + 4 个 `*.test.tsx` (client child)

- [ ] **Step 1: 改前跑知识库 4 处测试 (确认基线绿)**

```bash
cd packages/web && bun x vitest run app/\[locale\]/knowledge/datasets app/\[locale\]/knowledge/nodes app/\[locale\]/knowledge/relations app/\[locale\]/knowledge/dataset-documents
```

- [ ] **Step 2: 改 RSC (4 处同型, 用 nodes 为例)**

```tsx
// 改前
export default async function Page() {
  const nodes = await fetchNodes();
  return <NodesTable initialData={nodes} />;
}

// 改后
import { Suspense } from "react";
import { DataTableSkeleton } from "@/components/common/data-table/data-table-skeleton";
export default function Page() {  // 去掉 async
  const nodesPromise = fetchNodes();  // 去掉 await
  return (
    <Suspense fallback={<DataTableSkeleton columns={3} rows={10} />}>
      <NodesTable nodesPromise={nodesPromise} />
    </Suspense>
  );
}
```

- [ ] **Step 3: 改 client child (4 处同型)**

```tsx
// 改前
export function NodesTable({ initialData }: { initialData: NodeRow[] }) { ... }

// 改后
import { use } from "react";
export function NodesTable({ nodesPromise }: { nodesPromise: Promise<NodeRow[]> }) {
  const initialData = use(nodesPromise);
  // 内部逻辑不变
}
```

- [ ] **Step 4: 测试改 mock (RSC 4 个 + client 4 个)**

RSC test 不再 await → mock fetchNodes 返 Promise.resolve
Client test: `<NodesTable nodesPromise={Promise.resolve(mockData)} />` 替 `<NodesTable initialData={mockData} />`

- [ ] **Step 5: 跑测试 + typecheck + e2e knowledge 路径**

```bash
bun x vitest run app/\[locale\]/knowledge
bun x tsc --noEmit
cd ../.. && bun run test:e2e -- knowledge
```

### Task 1.6.3: admin 2 处 (users / invites)

**Files:**
- Modify: `packages/web/app/[locale]/admin/users/page.tsx:44` + `_components/AdminUsersTable.tsx`
- Modify: `packages/web/app/[locale]/admin/invites/page.tsx` + `_components/AdminInvitesTable.tsx`

- [ ] 跟 1.6.2 同流程, 区别:
  - AdminUsersTable prop 改 `usersPromise: Promise<AdminUsersResponse>` (不是数组, 是 `{items, total, page, page_size}`)
  - AdminInvitesTable prop 改 `invitesPromise: Promise<...>` 替 `initialItems: InviteItem[]`
- [ ] 跑测试 + typecheck + e2e admin

### Task 1.6.4: 集成回归

- [ ] 完整 typecheck: `cd packages/web && bun x tsc --noEmit`
- [ ] 完整 vitest (按 memory 不全量, 但 1.6 涉及 6 处, 跑全量 1 次): `bun run test`
- [ ] e2e 关键路径: login + submissions + chat + knowledge + admin
- [ ] 跟 1.6.1-1.6.3 集成测试报告

---

## Sprint 2: useFormStatus + useOptimistic (1.5d)

### Task 2.1: SubmitButton 子组件 (5 处使用方)

**Files:**
- New: `packages/web/components/common/submit-button.tsx`
- Modify: `packages/web/vitest.setup.ts` (加 useFormStatus mock)
- Modify: 5 个 form (TriplesForm / QASubmitForm / ImportCommitCard / CreateInviteDialog / login (来自 1.2))

- [ ] **Step 1: 新建 SubmitButton 组件** (用 audit § 3.1 模板)
- [ ] **Step 2: vitest.setup.ts 加 mock**
  ```ts
  vi.mock("react-dom", () => ({ useFormStatus: () => ({ pending: false }) }));
  ```
- [ ] **Step 3: 5 处 form 替换 `<Button disabled={isPending}>` → `<SubmitButton>`**
- [ ] **Step 4: 跑 5 个 form 测试 + typecheck**

### Task 2.2: ChatShell handleSend useOptimistic

`packages/web/components/chat/ChatShell.tsx:58-130`

- [ ] 改前跑 `bun x vitest run components/chat/`
- [ ] 改造 (audit § 3.2 A 模板): `useOptimistic(messages, (state, newMsg) => [...state, newMsg])`
- [ ] `handleSend` 改: `addOptimistic(userMsg) + startTransition + await api.send`
- [ ] 跑测试 + e2e chat

### Task 2.3: ApprovalRow 审批 useOptimistic

`packages/web/app/[locale]/submissions/_components/ApprovalRow.tsx:53-70`

- [ ] 改前跑 `bun x vitest run app/\[locale\]/submissions/`
- [ ] 改造 (audit § 3.2 B 模板): useOptimistic + 3 个 mutation 协同样板
- [ ] 跑测试 + e2e submissions

### Task 2.4: TaskDetailClient.useTaskCancel useOptimistic

`packages/web/app/[locale]/output/[task_id]/_components/TaskDetailClient.tsx:64-80`

- [ ] 改前测试
- [ ] 改 useOptimistic, 立刻改 task.status, 失败回滚
- [ ] 跑测试

### Task 2.5: AdminUsersTable reEnable useOptimistic

`packages/web/app/[locale]/admin/users/_components/AdminUsersTable.tsx`

- [ ] 改前测试
- [ ] reEnable/disable 改 useOptimistic, 翻 is_active
- [ ] 跑测试

### Task 2.6: AdminInvitesTable revoke useOptimistic

`packages/web/app/[locale]/admin/invites/_components/AdminInvitesTable.tsx`

- [ ] 改前测试
- [ ] revoke 改 useOptimistic, 立刻从列表移除
- [ ] 跑测试

---

## Sprint 3: 拆 context + Compiler 评估 (1.0d)

### Task 3.1: form/form.tsx 拆 Dispatch + Value context

`packages/web/components/common/form/form.tsx`

- [ ] 改前跑 `bun x vitest run components/common/form/`
- [ ] 拆 `DispatchContext` (registerField/setFieldValue/setFieldTouched 3 个 action) + `ValueContext` (values/errors/touched)
- [ ] 改 useFormContext 暴露俩 ctx
- [ ] 改 FormItem/FormField 用 useContext(DispatchContext) 拿 action
- [ ] 跑测试 + Profiler 对比重渲染次数

### Task 3.2: theme-provider.tsx 拆 ThemeDispatch + ThemeValue

`packages/web/components/theme-provider.tsx`

- [ ] 改前测试
- [ ] 拆 `ThemeDispatchContext` (setTheme) + `ThemeValueContext` (theme/resolved/themes)
- [ ] 改 useTheme 暴露俩 ctx
- [ ] 跑测试 + e2e theme 切换

### Task 3.3: React Compiler 评估

`reactCompiler: true` + `babel-plugin-react-compiler@1.0.0` 已在 commit `c30ae69` 启用.

- [ ] 跑 `cd packages/web && bun x tsc --noEmit` (编译检查)
- [ ] 跑 `bun run build` (Next 编译检查, 看 hooks 报警)
- [ ] 起 dev server 测 chat 发送 + 切换 tab (功能)
- [ ] React DevTools Profiler 对比重渲染 (性能)
- [ ] 决策:
  - 全绿 → 保留, 不动
  - 有 hooks 报警 → 加 `@react-compiler-disable` 注释
  - e2e 性能下降 → 整体回退 (删 `reactCompiler: true`)

---

## Sprint 4+: 滚动 (0.5d/sprint)

### Task 4.1: generateMetadata 逐 page 补

- [ ] 从 knowledge/* + evaluate/* + admin/* 开始, 每 page 加 `generateMetadata` 走 i18n
- [ ] 验证 typecheck

### Task 4.2: Activity 评估

- [ ] 等 React 19.3+ Activity 稳定 (目前仍 `react/experimental`)
- [ ] 评估 SubmissionsTabs / KnowledgeTabs 切 tab 内部状态保留

### Task 4.3: React Compiler 扩面

- [ ] Sprint 3 评估全绿后, 决定是否对 radix/shadcn 加兼容性注释
- [ ] 考虑 Vite/vitest 环境下的 Compiler 兼容性

---

## 最终验证 (Definition of Done)

每 Sprint 完成前必跑:

```bash
# 1. Typecheck
cd packages/web && bun x tsc --noEmit

# 2. 受影响文件测试
bun x vitest run <pattern>

# 3. Lint (修真 warning, 不依赖 --no-verify)
bun x oxlint . 2>&1 | grep "error "

# 4. E2E 关键路径
cd ../.. && bun run test:e2e -- login chat submissions knowledge admin

# 5. Build
cd packages/web && bun x next build
```

**整体完成标志** (Sprint 1-3 全部):
- 30+ 处 boilerplate 干掉
- 7 个 form 全部走 Server Action
- 6 个 useOptimistic 全部上线
- 5+ 个 SubmitButton 替代父组件 pending 透传
- 3 个 Context 简写
- 6 个 RSC `await data → initialData` 改 `use(promise)`
- React Compiler 评估决策落地
- 完整 typecheck / vitest / e2e / build 全绿

---

## 风险与回退 (汇总)

| 风险 | 触发 | 回退 |
|---|---|---|
| Server Action 测试 mock 路径不兼容 | vi.mock 漏改 | 改前 grep `vi.mock("...")` 一次性列 |
| useFormStatus jsdom 不支持 | vitest 红 | vitest.setup.ts 加 mock |
| useOptimistic 失败回滚用户困惑 | toast.error + 保留草稿 | 跟 submission reject 同型 |
| React Compiler 跟 shadcn 报警 | build 失败 | `@react-compiler-disable` 局部关 |
| 6 处 use() 改 Suspense 边界后流式反而慢 | TTI 测量 | 1 处回退, 5 处保留 |
| `decode` form 改 server action 走 server-side fetch | 跟 client fetch 行为不一致 | 单元测试覆盖, typecheck 兜底 |

---

## Memory 关联 (实施时遵守)

- [[feedback-no-shim-no-minimal-changes]] — 严禁 shim
- [[feedback-no-full-vitest-during-dev]] — 开发不全量, 改啥跑啥
- [[feedback-lint-staged-warning-treats-as-error]] — warning 阻塞, 修真
- [[feedback-stop-and-ask-dont-loop-on-infra]] — 卡 30 分钟停
- [[feedback-todo-not-red-acceptable-compromise]] — it.todo 站位
- [[feedback-verify-with-import-not-pip]] — 改完用 import 验证
- [[feedback-check-pyproject-deps-match-actual-imports]] — 新依赖同步
- [[feedback-debug-search-before-loop]] — 报错先查文档
- [[feedback-must-test-both-ends]] — 改 bug 自测前后端

---

**最后更新**: 2026-06-14
**作者**: Claude Code
**配套 spec**: [../specs/2026-06-14-react19-refactor-design.md](../specs/2026-06-14-react19-refactor-design.md)
**配套 audit**: [../../audit/2026-06-14-react19-refactor.md](../../audit/2026-06-14-react19-refactor.md)
**当前 commit**: `403da21`
