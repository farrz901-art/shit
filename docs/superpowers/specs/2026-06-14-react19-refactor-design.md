# React 19 + Next.js 16 全面改造 设计

> 2026-06-14 · Audit → Spec
> Status: 待用户 review
> 配套 audit: [../../audit/2026-06-14-react19-refactor.md](../../audit/2026-06-14-react19-refactor.md) (868 行, 10 章)
> 配套 react19 知识: [../../refactor/react19.md](../../refactor/react19.md)
> 当前 commit: `c30ae69` (audit + React Compiler 试点 dep)

## 1. 目标

把项目从 React 18 风格 (手写 isPending + onSubmit + FormData 拼装 + useState(ctx) 对象整体重渲染) 全面升级到 React 19 + Next.js 16 模式 (useActionState / useFormStatus / useOptimistic / useTransition / Context 简写), 干掉 30+ 处历史模板, 让代码更声明式 + 更少 boilerplate.

不在范围 (后续 spec):
- shadcn 内部 forwardRef 替换 (vendor 代码, 不动)
- React 19.3+ Activity (仍 experimental)
- shadcn/radix 跟 React Compiler 兼容性升级
- 后端 Python (本 spec 仅 web 前端)

## 2. 实施分 Sprint (跟 audit § 5.5.8 一致)

| Sprint | 工作量 | 任务数 | 核心交付 |
|---|---|---|---|
| **1.1** | 0.3d | 4 | 4 处 useTransition 替 useState(busy) (non-form 场景) |
| **1.2** | 1.5d | 7 | 7 个 form useActionState 化 (含 decode 遗漏) |
| **1.3** | 0.1d | 3 | 3 处 Context 简写 `<Context value={...}>` |
| **1.4** | 0.3d | 6 | 方案 A: 6 处空操作 useCallback → 普通函数 |
| **1.5** | 0.5d | 4 | error.tsx / loading.tsx / not-found.tsx / global-error.tsx |
| **2** | 1.5d | 5 | useFormStatus SubmitButton + 6 处 useOptimistic |
| **3** | 1d | 2 | 方案 B 拆 context + React Compiler 评估调整 |
| **4+** | 0.5d/sprint | 滚动 | generateMetadata / Activity / Compiler 扩面 |
| **总计** | **5.7d** | **33** | |

---

## 3. Sprint 1.1 — useTransition 替 useState(busy) (4 处, 0.3d)

**目标**: non-form 场景的 `useState(busy) + setBusy(true) + await + setBusy(false)` 改 `useTransition` 替, 避免阻塞 UI.

**任务清单**:

### Task 1.1.1: decode/page.tsx submit
- **现状**: [packages/web/app/[locale]/decode/page.tsx:106-126](../packages/web/app/%5Blocale%5D/decode/page.tsx) `useState(loading) + submit() { setLoading(true); try { await... } finally { setLoading(false) } }`
- **改造**:
  ```ts
  // 改前
  const [loading, setLoading] = useState(false);
  const submit = useCallback(async () => { ... setLoading(true); ...; finally { setLoading(false); } }, [model]);
  
  // 改后
  const [isPending, startTransition] = useTransition();
  const submit = () => {
    startTransition(async () => { ... setResult(await systemApi.decode(model)); });
  };
  ```
- **下游** `useKeyboardSubmit(model, loading, submit)` 改 `useKeyboardSubmit(model, isPending, submit)`
- **下游** `<Button onClick={submit} disabled={loading}>` 改 `<Button onClick={submit} disabled={isPending}>`
- **验证**: `bun run test -- decode` (page.test.tsx) + `bun run test:e2e -- decode`
- **风险**: 低 (跟 useActionState 模式同源, 但走 transition 因为没 form 包装)

### Task 1.1.2: output/new/page.tsx submit
- **现状**: [packages/web/app/[locale]/output/new/page.tsx:33-86](../packages/web/app/%5Blocale%5D/output/new/page.tsx) `useState(busy) + submit() { ... }`
- **改造**: 跟 1.1.1 同型, 改 useTransition
- **验证**: `bun run test -- output/new`

### Task 1.1.3: knowledge/batch/page.tsx onSubmit
- **现状**: [packages/web/app/[locale]/knowledge/batch/page.tsx:24-90](../packages/web/app/%5Blocale%5D/knowledge/batch/page.tsx) `useState(submitting) + onSubmit() { ... }`
- **改造**: 同 1.1.1
- **验证**: `bun run test -- knowledge/batch`

### Task 1.1.4: TaskDetailClient useTaskDownload
- **现状**: [packages/web/app/[locale]/output/[task_id]/_components/TaskDetailClient.tsx:39-50](../packages/web/app/%5Blocale%5D/output/%5Btask_id%5D/_components/TaskDetailClient.tsx) 自定义 hook 内部 `useState(downloading) + setDownloading(true) + await + setDownloading(false)`
- **改造**: 改 `useTransition` (跟同文件 `useTaskCancel` 一致)
- **验证**: `bun run test -- output/[task_id]`

---

## 4. Sprint 1.2 — 7 个 form useActionState 化 (1.5d)

**目标**: 6 个 `<form onSubmit={fn}>` + 1 个遗漏 (decode 跟方案 A 同步) 全部改 `<form action={formAction}>`, 走 Server Action (或 client-server 桥接) + useActionState.

**任务清单**:

### Task 1.2.1: login/page.tsx + loginAction
- **现状**: [packages/web/app/[locale]/login/page.tsx:19-42](../packages/web/app/%5Blocale%5D/login/page.tsx) `useState(err) + useState(email/pwd) + useTransition + onSubmit={e=>{e.preventDefault();...}}` (36 行)
- **改造** (目标 12 行):
  ```tsx
  "use client";
  import { useActionState } from "react";
  import { useTranslations } from "next-intl";
  import { useSearchParams } from "next/navigation";
  import { Input } from "@/components/ui/input";
  import { Button } from "@/components/ui/button";
  import { ErrorBanner } from "@/components/common/error-banner";
  import { loginAction } from "@/app/[locale]/_actions/account";
  
  export default function LoginPage() {
    const t = useTranslations();
    const [state, formAction, isPending] = useActionState(loginAction, { ok: false, error: null });
    const search = useSearchParams();
    const next = search.get("next") ?? "/";
    return (
      <div className="mx-auto mt-20 max-w-sm space-y-6">
        <h1 className="display text-3xl">{t("登录")}</h1>
        {state.error && <ErrorBanner variant="destructive" description={state.error} />}
        <form action={formAction} className="space-y-4">
          <input type="hidden" name="next" value={next} />
          <Input name="email" type="email" required data-testid="email-input" />
          <Input name="password" type="password" required data-testid="password-input" />
          <Button type="submit" disabled={isPending} className="w-full" data-testid="login-submit">
            {isPending ? t("提交中…") : t("登录")}
          </Button>
        </form>
        <a href="/forgot-password" className="text-sm text-muted-foreground hover:underline">{t("忘记密码?")}</a>
      </div>
    );
  }
  ```
- **loginAction 改造**: 接收 `(prevState, formData)`, 内部从 `formData.get("email")` / `formData.get("password")` 取, 直接 `redirect("/")` (替 router.push)
- **测试改造**: 用 `vi.mock("@/app/[locale]/_actions/account")` 替 client 端 mock
- **验证**: `bun run test -- login` + `bun run test:e2e -- login`

### Task 1.2.2-1.2.6: forgot/reset/invite + 2 dialog
- 跟 1.2.1 同型, 5 个表单同步做
- Server Action 都在 `app/[locale]/_actions/account.ts` 加 (已有 loginAction)
- 测试 mock 路径统一替 `vi.mock("@/app/[locale]/_actions/account", ...)`
- **验证**: 5 个 form 各自跑 vitest + e2e (login, forgot, reset, invite, admin users/invites)

### Task 1.2.7: decode/page.tsx (补漏)
- **现状**: [packages/web/app/[locale]/decode/page.tsx:180](../packages/web/app/%5Blocale%5D/decode/page.tsx) `<form onSubmit={submit}>` (有 form 包装, 不是 button onClick)
- **注意**: decode submit 走 client fetch (`systemApi.decode()`), 不是 Server Action
- **方案 A** (推荐, 跟其他 6 个一致): 新建 `_actions/system.ts` 包 `systemApi.decode()`, 走 server-side fetch
- **方案 B** (备选): 保留 client fetch + `useActionState` 包装 (form action 接受 client 函数)
- **决策**: A (一致性 + 减少特例)
- **改造**: 1.1.1 + 1.2.1 组合 — useActionState 走 server action, submit 模式 (1.1.1 那部分 useTransition 跟 useActionState 的 isPending 共用)
- **验证**: `bun run test -- decode` + `bun run test:e2e -- decode`

---

## 5. Sprint 1.3 — Context 简写 3 处 (0.1d)

**目标**: `<Context.Provider value={...}>` 改 `<Context value={...}>` (React 19 简写, 行为完全一致)

**任务清单**:

### Task 1.3.1: theme-provider.tsx
- **现状**: [packages/web/components/theme-provider.tsx:254](../packages/web/components/theme-provider.tsx) `<ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>`
- **改造**: `<ThemeContext value={value}>{children}</ThemeContext>`
- **验证**: `bun run test -- theme-provider` + `bun run test -- header` (header 间接用)

### Task 1.3.2: app-data.tsx
- **现状**: [packages/web/lib/store/app-data.tsx:26](../packages/web/lib/store/app-data.tsx) `<Ctx.Provider value={{ datasets, schemas }}>{children}</Ctx.Provider>`
- **改造**: `<Ctx value={{ datasets, schemas }}>{children}</Ctx>`
- **验证**: `bun run test -- app-data` (无则跳过, typecheck 兜底)

### Task 1.3.3: form/form.tsx FormContext
- **现状**: [packages/web/components/common/form/form.tsx:116-120](../packages/web/components/common/form/form.tsx) `<FormContext.Provider value={ctx}>` / `</FormContext.Provider>`
- **改造**: `<FormContext value={ctx}>{children}</FormContext>` 一行
- **验证**: `bun run test -- form` (form.test.tsx 已有, 测 FormItem/FormField useFormContext)

---

## 6. Sprint 1.4 — 方案 A: 6 处 useCallback 清理 (0.3d)

**目标**: 6 个 100% 空操作的 useCallback 改普通函数. 全项目 15 → 9 useCallback.

**任务清单**:

### Task 1.4.1-1.4.5: ChatShell.tsx 5 处
| 文件:行 | 函数 | 改法 |
|---|---|---|
| [components/chat/ChatShell.tsx:89](../packages/web/components/chat/ChatShell.tsx) | `handleDelete` | `useCallback((id) => { setPendingDeleteId(id); }, [])` → `(id) => { setPendingDeleteId(id); }` |
| [components/chat/ChatShell.tsx:93](../packages/web/components/chat/ChatShell.tsx) | `confirmDelete` | `useCallback(() => { ... }, [3 state])` → 普通函数 |
| [components/chat/ChatShell.tsx:115](../packages/web/components/chat/ChatShell.tsx) | `handleSelect` | `useCallback((id) => { setCurrentId(id); }, [])` → 普通函数 |
| [components/chat/ChatShell.tsx:119](../packages/web/components/chat/ChatShell.tsx) | `handleSend` | `useCallback(async (text) => { ... }, [4 vars])` → 普通 async 函数 |
| [components/chat/ChatShell.tsx:298](../packages/web/components/chat/ChatShell.tsx) | `handleStop` | `useCallback(() => { ... }, [streamingConvId])` → 普通函数 |

**保留** (deps 稳定, 真有用): `persistConv`, `persistMessages`, `handleNew` — 不动

### Task 1.4.6: decode/page.tsx submit
- **现状**: [packages/web/app/[locale]/decode/page.tsx:115](../packages/web/app/%5Blocale%5D/decode/page.tsx) `useCallback(async () => { ... }, [model])` + 删 `useCallback` import
- **注意**: 跟 1.1.1 / 1.2.7 同步, submit 模式整体重写时一起删

**验证**: `bun run test -- ChatShell` (5 个 vitest 文件) + `bun run test -- decode` + `bun run test:e2e -- chat`

---

## 7. Sprint 1.5 — error.tsx / loading.tsx / not-found.tsx (0.5d)

**目标**: RSC 抛错时不再整页 500, 有合理 fallback

**任务清单**:

### Task 1.5.1: app/global-error.tsx
- **新建**: `packages/web/app/global-error.tsx`
- **内容**: 根 layout 崩溃兜底, "出错了" + 重启按钮
- **限制**: global-error.tsx 必须自带 `<html>` + `<body>`, 不能用 ThemeProvider
- **验证**: `bun run build` (编译通过)

### Task 1.5.2: app/[locale]/error.tsx
- **新建**: [packages/web/app/[locale]/error.tsx](../packages/web/app/%5Blocale%5D/error.tsx)
- **内容**: client component, ErrorBanner 展示 + 重试按钮 (用 audit § 2.1 模板)
- **验证**: 跑 1 个 RSC 抛错测试 (datasets/nodes/relations/datasets 已 mock, 验 .rejects.toThrow 路径)

### Task 1.5.3: app/[locale]/loading.tsx
- **新建**: [packages/web/app/[locale]/loading.tsx](../packages/web/app/%5Blocale%5D/loading.tsx)
- **内容**: Suspense fallback, shadcn Skeleton (如没装则简单 spinner)
- **验证**: typecheck

### Task 1.5.4: app/[locale]/not-found.tsx
- **新建**: [packages/web/app/[locale]/not-found.tsx](../packages/web/app/%5Blocale%5D/not-found.tsx)
- **内容**: 走 i18n, "未找到" + 返回首页
- **验证**: 跑 `curl /zh/no-such-page` 验证返 not-found 页面

---

## 8. Sprint 2 — useFormStatus + useOptimistic (1.5d)

**目标**: SubmitButton 子组件解放父组件 pending 透传 + 6 处乐观更新 (3 旧 + 3 新)

**任务清单**:

### Task 2.1: SubmitButton 子组件
- **新建**: `packages/web/components/common/submit-button.tsx`
- **内容**: 用 `useFormStatus()` 替父组件 pending 透传 (audit § 3.1 模板)
- **vitest.setup.ts**: 加 `vi.mock("react-dom", () => ({ useFormStatus: () => ({ pending: false }) }))`
- **改造 5 处**:
  - [TriplesForm.tsx](../packages/web/app/%5Blocale%5D/knowledge/triples/_components/TriplesForm.tsx)
  - [QASubmitForm.tsx](../packages/web/app/%5Blocale%5D/knowledge/qa/_components/QASubmitForm.tsx)
  - [ImportCommitCard.tsx](../packages/web/app/%5Blocale%5D/knowledge/documents/import/_components/ImportCommitCard.tsx)
  - login/page.tsx (跟 1.2.1 同步)
  - CreateInviteDialog.tsx (跟 1.2.6 同步)
- **验证**: 5 个 form 跑测试

### Task 2.2: ChatShell 发送 useOptimistic
- **现状**: [components/chat/ChatShell.tsx:58-130](../packages/web/components/chat/ChatShell.tsx) `handleSend` (已 useCallback, 改后用 useOptimistic)
- **改造** (audit § 3.2 A 模板):
  ```tsx
  const [optimisticMessages, addOptimistic] = useOptimistic(
    messages, (state, newMsg: Message) => [...state, newMsg],
  );
  const handleSend = async (text) => {
    const userMsg = { ... };
    addOptimistic(userMsg);
    startTransition(async () => { const res = await api.send(text, currentId); setMessages(...); });
  };
  ```
- **风险**: 中 (失败回滚, 用户看到消息消失)
- **验证**: `bun run test -- ChatShell` + e2e chat 路径

### Task 2.3: ApprovalRow 审批 useOptimistic
- **现状**: [app/[locale]/submissions/_components/ApprovalRow.tsx:53-70](../packages/web/app/%5Blocale%5D/submissions/_components/ApprovalRow.tsx) 3 个 useMutation
- **改造**: audit § 3.2 B 模板
- **风险**: 中 (跟 RQ invalidate 协同)
- **验证**: `bun run test -- submissions` + e2e submissions 路径

### Task 2.4: TaskDetailClient useTaskCancel useOptimistic
- **现状**: [app/[locale]/output/[task_id]/_components/TaskDetailClient.tsx:64-80](../packages/web/app/%5Blocale%5D/output/%5Btask_id%5D/_components/TaskDetailClient.tsx) `useTaskCancel` 内部 useTransition + setCancelling
- **改造**: 改 useOptimistic, 立刻把 task.status 改 cancelled, 失败回滚
- **验证**: `bun run test -- output/[task_id]`

### Task 2.5: AdminUsersTable reEnable useOptimistic
- **现状**: [app/[locale]/admin/users/_components/AdminUsersTable.tsx](../packages/web/app/%5Blocale%5D/admin/users/_components/AdminUsersTable.tsx) 内部 4 处 `useTransition` 调用
- **改造**: reEnable/disable 改 useOptimistic, 立刻翻 is_active, 失败回滚
- **验证**: `bun run test -- admin/users`

### Task 2.6: AdminInvitesTable revoke useOptimistic
- **现状**: [app/[locale]/admin/invites/_components/AdminInvitesTable.tsx](../packages/web/app/%5Blocale%5D/admin/invites/_components/AdminInvitesTable.tsx)
- **改造**: 改 useOptimistic, 立刻从列表移除
- **验证**: `bun run test -- admin/invites`

---

## 9. Sprint 3 — 方案 B 拆 context + Compiler 评估 (1d)

**目标**: 4 处 ctx useCallback 失效场景优化 + React Compiler 试点后评估

**任务清单**:

### Task 3.1: form/form.tsx 拆 context (3 处 useCallback)
- **现状**: [components/common/form/form.tsx:45-71](../packages/web/components/common/form/form.tsx) `registerField` / `setFieldValue` / `setFieldTouched` 走 ctx value 对象
- **改造**: 拆 `DispatchContext` (3 个 action) + `ValueContext` (values/errors/touched)
- **验证**: `bun run test -- form` (FormItem/FormField 重渲染次数下降)

### Task 3.2: theme-provider.tsx 拆 context (1 处 useCallback)
- **现状**: [components/theme-provider.tsx:171](../packages/web/components/theme-provider.tsx) `setTheme` 走 ctx value
- **改造**: 拆 `ThemeDispatchContext` (setTheme) + `ThemeValueContext` (theme/resolved/themes)
- **验证**: `bun run test -- theme-provider` + `bun run test -- header` + e2e theme 切换

### Task 3.3: React Compiler 评估
- **已启用**: `reactCompiler: true` + `babel-plugin-react-compiler@1.0.0` (commit `c30ae69`)
- **评估方法**:
  1. 跑 `bun run build` 看编译警告
  2. 跑 dev server 测 chat 发送 + 切换 tab
  3. 用 React DevTools Profiler 对比启用前后重渲染次数
- **预期**: 0 useMemo + 0 React.memo 项目天然受益小, 但未来新代码可省 memo
- **决策点**:
  - **如果全绿**: 保留, 不动
  - **如果有 hooks 规则报警**: 加 `@react-compiler-disable` 注释局部关
  - **如果 e2e 性能下降**: 整体回退 Compiler, 删 `reactCompiler: true`

---

## 10. Sprint 4+ — 滚动 (0.5d/sprint)

### Task 4.1: generateMetadata 逐 page 补
- **范围**: 29 个 page 视情况补 i18n-aware title/description
- **模板**:
  ```tsx
  export async function generateMetadata({ params }: { params: Promise<{ locale: string }> }) {
    const { locale } = await params;
    const t = await getTranslations({ locale });
    return { title: `${t("知识库")} | RAG 管理后台` };
  }
  ```
- **优先级**: knowledge/* + evaluate/* + admin/* (业务页先做)

### Task 4.2: Activity 评估
- **范围**: SubmissionsTabs / KnowledgeTabs 切 tab 内部状态保留
- **前置**: 跟 React 19.3+ 一起评估 (目前 Activity 在 `react/experimental`)

### Task 4.3: React Compiler 扩面
- **如果 Sprint 3 全绿**: 评估对第三方库 (radix/shadcn) 影响, 决定扩到全项目

---

## 11. 验收标准 (Definition of Done)

每 Sprint 完成必须满足:

1. **功能不变**: 受影响业务 e2e 全部通过
2. **类型 0 错**: `bun run typecheck` 通过
3. **测试 0 回归**: `bun run test -- <affected>` 全绿 (含改的 + 间接依赖的)
4. **Lint 0 阻塞**: `bun run lint 2>&1 | grep "error "` 0 error (warning 也修, lint-staged 阻塞)
5. **E2E 关键路径**: 至少跑 1 次完整 e2e (login + submissions + chat 端到端)
6. **代码行净变化**: 期望 net 负 (改后行数 < 改前行数, 干掉 boilerplate)
7. **commit 格式**: 走 conventional commits, type 取值 feat/fix/refactor/test, scope 单值
8. **commit 前**:
   - 跑针对性测试 (不全量, 按 memory rule)
   - 修真 warning (lint-staged 会因 warning 阻塞)
   - 不擅自撤用户代码 (按 memory rule)

## 12. 风险与回退

| 风险 | 触发 | 回退 |
|---|---|---|
| useActionState 跟 client 测试 mock 路径不兼容 | vi.mock 漏改, CI 全红 | 改前先 grep `vi.mock("...")` 列所有依赖, 一次性改测试 |
| useFormStatus 在 jsdom 下未实现 | vitest 红 | vitest.setup.ts 加 `vi.mock("react-dom", ...)` |
| useOptimistic 失败回滚用户困惑 | 提交后突然消失 | toast.error + 保留乐观项作为草稿 (跟 submission reject 同型) |
| React Compiler 跟 shadcn 报警 | `bun run build` 失败 | 局部 `@react-compiler-disable` 注释, 不影响全量 |
| Server Action redirect 测试 mock 漏 | `vi.mock("next/navigation")` 缺 `redirect` | 改 loginAction 测试时统一补 |
| 漏改 form 引用方 (component import) | build 失败 | typecheck 兜底 (TS 严格), 编译器会标 |
| Context 简写 + 旧 React types 不识别 | IDE 报红 | 项目用 tsgo 7.0+ 没问题, 退回 React 18 会失败, 不动 |

## 13. 测试计划 (TDD 流程)

每 Task 按此顺序:

1. **红**: 改前跑测试确认基线绿 (验证现有测试反映现状)
2. **改**: 实施改造
3. **绿**: 跑受影响的 vitest, 确认行为不变
4. **refactor**: 整理代码 + 跑 typecheck + lint
5. **e2e**: 业务关键路径跑 Playwright
6. **commit**: 走 conventional commits, 不擅自 commit 多个逻辑单元

## 14. 依赖关系 (Critical Path)

```
Sprint 1.1 ──┐
Sprint 1.2 ──┼─→ Sprint 1.4 (1.2 + 1.4 一起做, 都改 decode)
Sprint 1.3 ──┤
Sprint 1.5 ──┘ (独立, 可跟 1.1-1.4 并行)
        ↓
Sprint 2 (依赖 1.2 form 重构, 因为 SubmitButton 走 form action)
        ↓
Sprint 3 (依赖 1.3 Context 简写, 拆 context 后续)
        ↓
Sprint 4+ (滚动, 独立)
```

**关键路径**: 1.2 (1.5d) → 2 (1.5d) → 3 (1d) = 4d, 加上 1.1/1.3/1.4 并行 0.7d = 总 4.7d ≈ audit 估的 5.7d 接近 (audit 估含回归测试时间)。

## 15. 关联文档

- **Audit** (本 spec 配套): [../../audit/2026-06-14-react19-refactor.md](../../audit/2026-06-14-react19-refactor.md) (868 行, 10 章)
- **React 19 知识**: [../../refactor/react19.md](../../refactor/react19.md) (Actions / useActionState / useFormStatus / useOptimistic / use() / ref-as-prop / Context 简写 / Compiler 详解)
- **Web 项目规范**: [../../../packages/web/CLAUDE.md](../../../packages/web/CLAUDE.md) (表格/封装/主题/i18n 约定)
- **项目全局规范**: [../../../CLAUDE.md](../../../CLAUDE.md) (TDD / 中文注释 / 不删注释 / 不硬编码)
- **Memory 关联**:
  - [[feedback-no-shim-no-minimal-changes]] — 严禁 shim
  - [[feedback-clarify-ambiguous-instructions]] — 模糊指令先问
  - [[feedback-debug-search-before-loop]] — 查官方文档先
  - [[feedback-must-test-both-ends]] — 改 bug 自测前后端
  - [[feedback-no-full-vitest-during-dev]] — 开发不全量跑
  - [[feedback-lint-staged-warning-treats-as-error]] — warning 阻塞
  - [[feedback-stop-and-ask-dont-loop-on-infra]] — 卡住 30 分钟停
  - [[feedback-todo-not-red-acceptable-compromise]] — it.todo 站位
  - [[feedback-record-errors-and-lessons]] — 犯错过要记

---

## 16. Sprint 1.6 — `use(promise)` 替 RSC `await data → initialData` (0.5d, v2 补)

> **2026-06-14 v2 新增**: 用户追问 use() 后, audit § 5.4 v2 修正, 漏报 6 处 RSC `await data` → `<Client initialData={data}>` 模式适合 `use(promise)`. 补独立 Sprint 1.6 (跟 1.1-1.5 正交, 可独立做).

**目标**: 6 个 RSC 父灌数据模式改 use(promise) + Suspense, 让数据流更声明式 + 父 RSC 不阻塞.

**任务清单**:

### Task 1.6.1: DataTableSkeleton 通用 Suspense fallback
- **新建**: `packages/web/components/common/data-table/data-table-skeleton.tsx`
- **API**: `<DataTableSkeleton columns={3} rows={5} />` (跟 DataTable prop 风格对齐, columns 数组 or 数字, rows 数字)
- **样式**: 跟 shadcn Skeleton 一致, header 5 列 + 5 行占位
- **验证**: typecheck + 1 个 story (可选)

### Task 1.6.2: knowledge 4 处 (datasets / nodes / relations / dataset-documents)
- **改 RSC** ([datasets](../packages/web/app/%5Blocale%5D/knowledge/datasets/page.tsx), [nodes](../packages/web/app/%5Blocale%5D/knowledge/nodes/page.tsx), [relations](../packages/web/app/%5Blocale%5D/knowledge/relations/page.tsx), [dataset-documents](../packages/web/app/%5Blocale%5D/knowledge/dataset-documents/%5Bdataset_id%5D/page.tsx)):
  ```tsx
  // 改前
  export default async function Page() {
    const nodes = await fetchNodes();
    return <NodesTable initialData={nodes} />;
  }
  // 改后
  export default function Page() {  // 去掉 async
    const nodesPromise = fetchNodes();  // 去掉 await
    return (
      <Suspense fallback={<DataTableSkeleton columns={3} rows={10} />}>
        <NodesTable nodesPromise={nodesPromise} />
      </Suspense>
    );
  }
  ```
- **改 client child** (DatasetsTable / NodesTable / RelationsTable / DatasetDocumentsTable):
  ```tsx
  // 改前
  export function NodesTable({ initialData }: { initialData: NodeRow[] }) { ... }
  // 改后
  import { use } from "react";
  export function NodesTable({ nodesPromise }: { nodesPromise: Promise<NodeRow[]> }) {
    const initialData = use(nodesPromise);
    // 逻辑不变
  }
  ```
- **测试改造**: 4 个 `page.test.tsx` 改 mock 路径 (RSC 不再 await → mock fetchNodes/Promise 注入)
- **client child 测试** (`.test.tsx`): 改 `<NodesTable nodesPromise={Promise.resolve(mockData)} />` 替 `<NodesTable initialData={mockData} />`
- **验证**: 4 个 vitest 文件全跑, 1 个 e2e knowledge 路径

### Task 1.6.3: admin 2 处 (users / invites)
- **改 RSC** ([users](../packages/web/app/%5Blocale%5D/admin/users/page.tsx), [invites](../packages/web/app/%5Blocale%5D/admin/invites/page.tsx)): 跟 1.6.2 同型
- **改 client child** ([AdminUsersTable](../packages/web/app/%5Blocale%5D/admin/users/_components/AdminUsersTable.tsx), [AdminInvitesTable](../packages/web/app/%5Blocale%5D/admin/invites/_components/AdminInvitesTable.tsx)):
  - AdminUsersTable prop 改 `usersPromise: Promise<AdminUsersResponse>` 替 `initialData: AdminUsersResponse`
  - AdminInvitesTable prop 改 `invitesPromise: Promise<...>` 替 `initialItems: InviteItem[]`
- **测试改造**: 2 个 page.test.tsx + 2 个 table.test.tsx 改 mock
- **验证**: 2 个 vitest 文件全跑, 1 个 e2e admin 路径

### Task 1.6.4: 集成回归
- **影响面**: 6 个 page + 6 个 client child + 6 个 test 文件
- **风险**: 父 RSC 失去 await → Suspense 边界正确性, page.tsx 改 non-async 后 `params`/`searchParams` Promise 仍能 await
- **关键**: 6 个 page.tsx 仍然能访问 `await params` (Next 16 async params 模式), 因为 Suspense fallback 渲染时 params 已经 ready
- **验证**: `bun run test -- knowledge` + `bun run test -- admin` + `bun run test:e2e -- knowledge admin` + 完整 typecheck

**风险与回退** (Sprint 1.6 特有):
| 风险 | 触发 | 回退 |
|---|---|---|
| Suspense fallback 设计不一致 | 6 个 page 各自实现 fallback, 体验分裂 | 用 1.6.1 DataTableSkeleton 统一, 6 处共用 |
| 父 RSC `async function` 改 `function` 漏 await 报错 | 改 page.tsx 时手误 | typecheck 兜底, 编译失败立刻能发现 |
| 测试 mock Promise.resolve 漏 | vitest 跑 unresolved Promise timeout | test 改前先 red (跑挂), 改 Promise.resolve 后 green |
| 流式渲染反而更慢 | Suspense 边界多层嵌套 | 测 1 个 page 的 TTI, 跟改前对比; 真慢就回退 |

**预期收益**:
- 6 处 RSC 父从"await + 传 resolved data" 改"不 await + 传 Promise", 流式渲染准备
- 6 个 client child prop 类型从 `initialData: T` 改 `xxxPromise: Promise<T>`, 语义更明确
- 6 个 page.tsx `async function` 改 `function`, 减少 6 个 await 阻塞

**Sprint 顺序调整** (v2 修订):
```
1.1 useTransition      ─┐
1.2 useActionState      │
1.3 Context 简写         ├─→ 全并行 (1.1-1.6 互不依赖, 5.7d → 6.2d)
1.4 useCallback 清理    │
1.5 error.tsx 等       │
1.6 use(promise) 表格 ─┘
2   useFormStatus + useOptimistic
3   拆 context + Compiler
4+  滚动
```

---

**最后更新**: 2026-06-14 v2
**作者**: Claude Code
**下一步**: 等用户 review, 同意后进 plan (任务依赖图 + 风险评估 + 时间表) → dev (按 Sprint 1-3 顺序)
