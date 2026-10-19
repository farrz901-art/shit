# React 19 + Next.js 16 改造点 Audit

> 范围: `packages/web/` 全部 Next.js 代码 (29 page.tsx + 47 "use client" + 4 "use server" + 30 shadcn UI 组件)
> 工具链: `react@19.2.0`, `next@16.2.0`, `react-dom@19.2.0`
> 资料: [./react19.md](./react19.md) (React 19 新特性 + Compiler 现状)
> 完成时间: 2026-06-14

## TL;DR — 推荐改造路线

| 优先级 | 改造点 | 影响面 | 工作量 | 风险 |
|---|---|---|---|---|
| 🔴 P0 | 新增 `error.tsx` / `loading.tsx` / `not-found.tsx` | 全站 (RSC 抛错现在直接 500) | 0.5d | 极低 |
| 🔴 P0 | `<form onSubmit>` + 手写 `useState(err)/useTransition` → `<form action={serverAction}>` + `useActionState` | 6-8 个表单页 | 1.5d | 低 (Server Action 已在 4 个文件) |
| 🟡 P1 | `useFormStatus` 抽取 `SubmitButton` 子组件, 干掉父子间 `pending` 透传 | 3-5 处 (TriplesForm, QASubmitForm, ImportCommitCard, login) | 0.5d | 极低 |
| 🟡 P1 | `useOptimistic` 改 chat 发送 + approvals 审批 | ChatShell, ApprovalRow, MessageFeedback | 1d | 中 (需改 hook 模式) |
| 🟡 P1 | Context `<Context value>` 简写 (7 处) | 4 项目自有 + 3 shadcn 上下文 | 0.2d | 极低 |
| 🟢 P2 | React Compiler v1.0 局部试点 (admin/users 路由) | 1 路由 → 全量 | 0.5d 试点 | 中 (生态不成熟) |
| 🟢 P2 | `generateMetadata` + 动态 `<title>` 改 React 19 metadata 提升 | 全站 SEO | 0.5d | 极低 |
| ⚪ 不做 | `forwardRef` 替换 (95+ 在 shadcn/ui 内部) | — | 2-3d | 高 (shadcn codemod 不在) |
| ⚪ 不做 | `React.memo` / `useMemo` 替换 | 0 处使用, 无意义 | — | — |

**关键约束**:
- React 19.2 + Next.js 16.2 全部目标能力可用 (RSC, Server Action, async params, useActionState, useFormStatus, useOptimistic, use(), ref-as-prop, Context 简写, document metadata)
- 项目已经走在正确的路上: 3 useActionState + 15+ useTransition + 4 "use server" + 全部 page 走 async params — 大量基础设施已具备
- 最大缺口: **error.tsx / loading.tsx / not-found.tsx 一个都没建**, 但代码注释多次写"失败抛错让 Next error.tsx 兜住" (实际没人兜 → 整页 500)
- React Compiler: 项目目前 0 useMemo / 0 React.memo / 19 useCallback, 收益有限, 建议**只试点, 不全量**

---

## 1. 项目现状快照 (审计基线)

| 指标 | 数量 | 备注 |
|---|---|---|
| `page.tsx` 总数 | 29 | App Router |
| `"use client"` 文件 | 47 | 客户端组件比预期多 (RSC 渗透不够) |
| `"use server"` 文件 | 4 | `_actions/{output,knowledge,evaluate,account}.ts` |
| `useActionState` 使用 | 3 | TriplesForm, QASubmitForm, ImportCommitCard (Task 12 引入) |
| `useTransition` 使用 | 15+ | TaskDetailClient / login / forgot / reset / invite / admin dialogs / settings |
| `useFormStatus` 使用 | 0 | 0 |
| `useOptimistic` 使用 | 0 | 0 |
| `use()` 使用 | 0 | 0 |
| `useMemo` 使用 | 0 | 0 |
| `React.memo` 使用 | 0 | 0 |
| `useCallback` 使用 | 15 | 多在 ChatShell (8) / form.tsx (3) / theme-provider (1) / output/new (2) / decode (1); 精确数字见 [§ 5.3](#53-usecallback-15-处精细审计--方案-ab-拆解) |
| `React.forwardRef` 使用 | 95+ | 全部在 `components/ui/*.tsx` (shadcn), 项目自有 0 |
| `<Context>.Provider>` 使用 | 7 | ToggleGroup, Theme, AppData, Form, FormField, FormItem, Form (1 测试) |
| `<form onSubmit={fn}>` 模式 | 5 | decode, login, forgot, reset, invite |
| `<form action={fn}>` 模式 | 5 | UserMenu logout, TaskDetailClient cancel, TriplesForm, ImportCommitCard, QASubmitForm |
| Async `params` / `searchParams` | 全部 page + 8 BFF route | 已采用 Next 15+ 模式 |
| `error.tsx` / `loading.tsx` / `not-found.tsx` | **0** | **没人兜错误** |
| React Compiler | 0 启用 | `next.config.ts` 无 `reactCompiler` 字段 |

---

## 2. 🔴 P0 — 必须做的改造

### 2.1 新增 error.tsx / loading.tsx / not-found.tsx (RSC 错误兜底)

**现状**:
- 0 个 `error.tsx` / `loading.tsx` / `not-found.tsx` / `global-error.tsx`
- RSC 抛错时**整页直接 500 崩溃** (Next 默认 error.tsx 仍要求用户自己建)
- 代码注释已经预设了这层兜底存在, 但实际没人建:
  - [app/[locale]/health/page.tsx:17](../packages/web/app/%5Blocale%5D/health/page.tsx) "失败抛错让 Next error.tsx 兜住"
  - [app/[locale]/output/page.tsx:16](../packages/web/app/%5Blocale%5D/output/page.tsx) "失败抛错让 Next error.tsx 兜住"
  - [app/[locale]/evaluate/page.tsx](../packages/web/app/%5Blocale%5D/evaluate/page.test.tsx) "fetch 失败时 RSC 抛错 (error.tsx 兜住)"
  - [app/[locale]/knowledge/{nodes,relations,graph,documents,datasets}/page.test.tsx](../packages/web/app/%5Blocale%5D/knowledge/datasets/page.test.tsx) 5 处 "RSC 抛错, error.tsx 兜住"

**改造建议**:
- 新建 `app/global-error.tsx` (根错误, RootLayout 崩溃兜底)
- 新建 `app/[locale]/error.tsx` (locale 错误, 客户端组件, 返"重试"按钮)
- 新建 `app/[locale]/loading.tsx` (Suspense fallback, 可用 shadcn Skeleton)
- 新建 `app/[locale]/not-found.tsx` (覆盖 root notFound(), 走 i18n)
- 知识库 + evaluate + output 子路由可加 `app/[locale]/knowledge/error.tsx` 进一步隔离

**示例** (app/[locale]/error.tsx):
```tsx
"use client";
// (2026-06-14) Next 15+ 要求 client component 才能用 useEffect
import { useEffect } from "react";
import { useTranslations } from "next-intl";
import { ErrorBanner } from "@/components/common/error-banner";
import { Button } from "@/components/ui/button";

export default function LocaleError({
  error,
  reset,
}: { error: Error & { digest?: string }; reset: () => void }) {
  const t = useTranslations();
  useEffect(() => {
    console.error("[locale error]", error);
  }, [error]);
  return (
    <div className="mx-auto mt-20 max-w-md space-y-4">
      <h1 className="display text-2xl">{t("出错了")}</h1>
      <ErrorBanner
        variant="destructive"
        description={error.message}
        data-testid="page-error"
      />
      <Button onClick={reset} data-testid="error-retry">{t("重试")}</Button>
    </div>
  );
}
```

**风险**: 极低 (Next.js 内建支持)

**关联**: [[feedback-rsc-throw-must-not-crash-page]] (RSC 抛错目前没人接)

---

### 2.2 表单提交: `useState(err) + useTransition` → `useActionState`

**现状** (6 个候选, 都是"手写 isPending + setError + startTransition + onSubmit 防默认"):

| 文件:行 | 现状 | 改后 |
|---|---|---|
| [app/[locale]/login/page.tsx:19-42](../packages/web/app/%5Blocale%5D/login/page.tsx) | `useState(err) + useState(email/pwd) + useTransition + onSubmit={e=>{e.preventDefault();startTransition(async()=>{const fd=new FormData();fd.append();await loginAction(fd);...})}}` | `useActionState(loginAction, {ok:false})` + `<form action={formAction}>` + 直接 `fd.append` 通过 hidden input 传 |
| [app/[locale]/forgot-password/page.tsx:15-16](../packages/web/app/%5Blocale%5D/forgot-password/page.tsx) | 同上模式 | 同上 |
| [app/[locale]/reset-password/page.tsx:19-20](../packages/web/app/%5Blocale%5D/reset-password/page.tsx) | 同上 | 同上 |
| [app/[locale]/invite/[token]/page.tsx:20-26](../packages/web/app/%5Blocale%5D/invite/%5Btoken%5D/page.tsx) | `useState(email) + useState(invalid) + useState(err) + useTransition` (3 状态机) | `useActionState(acceptInvite, {ok:false})` + 2 hidden inputs |
| [app/[locale]/admin/users/_components/ResetPasswordDialog.tsx:21-23](../packages/web/app/%5Blocale%5D/admin/users/_components/ResetPasswordDialog.tsx) | `useState(temp) + useState(err) + useTransition` | `useActionState(resetPassword, {ok:false, temp:null})` |
| [app/[locale]/admin/users/_components/CreateInviteDialog.tsx:33-35](../packages/web/app/%5Blocale%5D/admin/users/_components/CreateInviteDialog.tsx) | `useState(inviteUrl) + useState(err) + useTransition` | `useActionState(createInvite, {ok:false, inviteUrl:null})` |
| [app/[locale]/admin/users/_components/AdminUsersTable.tsx:57-58](../packages/web/app/%5Blocale%5D/admin/users/_components/AdminUsersTable.tsx) | `useState(data) + useState(error) + useTransition` (查询而非提交, **保留 useTransition**) | 保留 — 查询不属于 useActionState 场景 |
| [app/[locale]/admin/invites/_components/AdminInvitesTable.tsx:27-29](../packages/web/app/%5Blocale%5D/admin/invites/_components/AdminInvitesTable.tsx) | 同上, 查询保留 | 保留 |

**Server Actions 已存在的**:
- `loginAction` ([app/[locale]/_actions/account.ts:1](../packages/web/app/%5Blocale%5D/_actions/account.ts))
- 需新建 `forgotPasswordAction`, `resetPasswordAction`, `acceptInviteAction`, `resetPasswordAdminAction`, `createInviteAction` (在 `_actions/account.ts` 加, 因为都是账号域)

**改造示例** (login/page.tsx, 36 行 → 12 行):
```tsx
// 改造前: 36 行, 3 useState, 1 useTransition, 手写 FormData 拼装
// 改造后:
"use client";
import { useActionState } from "react";
import { useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
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
      <a href="/forgot-password" className="text-sm text-muted-foreground hover:underline">
        {t("忘记密码?")}
      </a>
    </div>
  );
}
```

**注意 — Server Action redirect**:
- loginAction 当前是返 `{ok:true} | {ok:false, error}` 然后客户端 router.push
- React 19 模式下, action 可直接 `redirect("/")` (next/navigation 抛 NEXT_REDIRECT)
- 这能省掉 `useRouter` + `useSearchParams` (route handler 决定)
- 但**测试 mock 路径要相应改**: `vi.mock("next/navigation")` 加 `redirect`

**风险**: 低
- Server Action 已在 4 个文件使用 (`output.ts`/`knowledge.ts`/`evaluate.ts`/`account.ts`), 模式已经稳
- 客户端测试要 mock server action 路径 (项目已有先例: `vi.mock("@/app/[locale]/_actions/knowledge", ...)`)
- 不影响其他业务流 (AdminUsersTable 的 useState(data) 仍要保留, query 模式不归 useActionState)

**收益**:
- 干掉 5-6 个 useState (err/temp/inviteUrl/email/password) + 5 个 startTransition
- 干掉 5 个 `e.preventDefault()` + 5 个 FormData 拼装
- 表单 reset 由 React 自动管 (form action 提交后浏览器自动 reset)

---

## 3. 🟡 P1 — 高价值, 风险低

### 3.1 `useFormStatus` 抽取 SubmitButton 子组件

**现状**:
- [app/[locale]/knowledge/triples/_components/TriplesForm.tsx:224](../packages/web/app/%5Blocale%5D/knowledge/triples/_components/TriplesForm.tsx) `useActionState` 拿 `isPending`, 在每处 submit button 上手动 `disabled={isPending}` + `{isPending ? t("提交中…") : t("批量提交")}`
- [app/[locale]/knowledge/qa/_components/QASubmitForm.tsx:64](../packages/web/app/%5Blocale%5D/knowledge/qa/_components/QASubmitForm.tsx) 同上
- [app/[locale]/knowledge/documents/import/_components/ImportCommitCard.tsx:50](../packages/web/app/%5Blocale%5D/knowledge/documents/import/_components/ImportCommitCard.tsx) 同上
- [app/[locale]/admin/users/_components/CreateInviteDialog.tsx:35](../packages/web/app/%5Blocale%5D/admin/users/_components/CreateInviteDialog.tsx) 同上 (但要跟 P0 改造一起做, 改 useActionState 后才能用 useFormStatus)
- [app/[locale]/login/page.tsx:20](../packages/web/app/%5Blocale%5D/login/page.tsx) 同上 (同 P0)
- 共 5+ 处父组件透传 `pending` 到子 button

**改造建议**:
- 抽 `<SubmitButton>` (来自 `react-dom`, 不需要新建, 但项目里没现成的) 通用组件
- 子组件: `const { pending } = useFormStatus();` → 父组件**不用传 pending**
- 父组件完全从 `pending` 状态机解放

**示例** (新建 `components/common/submit-button.tsx`):
```tsx
"use client";
// 替 5+ 处"父组件 useTransition 拿 pending 透传给子 Button"模板
// 父用 <form action={fn}>, 子用 <SubmitButton /> 即可, React 自动通过 DOM 上下文感知 pending
import { type ReactNode } from "react";
import { useFormStatus } from "react-dom";
import { Button } from "@/components/ui/button";

export interface SubmitButtonProps {
  children: ReactNode;
  pendingLabel?: ReactNode;
  variant?: "default" | "destructive" | "outline" | "secondary" | "ghost" | "link";
  size?: "default" | "sm" | "lg" | "icon";
  className?: string;
  disabled?: boolean;
  dataTestid?: string;
}

export function SubmitButton({
  children,
  pendingLabel,
  variant = "default",
  size = "default",
  className,
  disabled,
  dataTestid,
}: SubmitButtonProps) {
  const { pending } = useFormStatus();
  return (
    <Button
      type="submit"
      variant={variant}
      size={size}
      disabled={disabled || pending}
      className={className}
      data-testid={dataTestid}
    >
      {pending ? (pendingLabel ?? children) : children}
    </Button>
  );
}
```

**风险**: 极低 (官方 API)
- 测试: jsdom 不支持 `useFormStatus` → 需要在 `vitest.setup.ts` 加 `vi.mock("react-dom", () => ({ useFormStatus: () => ({ pending: false }) }))`
- shadcn 已经有现成模式

**收益**:
- 5+ 处的父组件 useState 干不掉 (form state 仍要) — 但 child 不用再接 prop
- 改完后父组件 `<form action={formAction}><SubmitButton>提交</SubmitButton></form>` 一行

---

### 3.2 `useOptimistic` 改造 chat 发送 + 审批流

**候选位置**:

#### A. ChatShell 发送消息 ([components/chat/ChatShell.tsx:58-130](../packages/web/components/chat/ChatShell.tsx))

**现状**:
- `handleSend` 是 `useCallback` 包 `async () => { await api.send(); appendMessage(assistant); }`
- 用户发送后**等几百毫秒 - 几秒**才看到 AI 消息, 体验差
- 已经有 `streamingConvId` 状态机在管"哪个会话在流式"

**改造建议**:
```tsx
// 改造前:
const [messages, setMessages] = useState<Message[]>(...);
const handleSend = useCallback(async (text) => {
  const userMsg = { role: "user", content: text, id: `tmp-${Date.now()}` };
  setMessages((prev) => [...prev, userMsg]);
  setStreamingConvId(currentId);
  const res = await api.send(text, currentId);
  setMessages((prev) => [...prev, { role: "assistant", content: res.answer, sources: res.sources }]);
  setStreamingConvId(null);
}, [currentId]);

// 改造后:
const [messages, setMessages] = useState<Message[]>(...);
const [optimisticMessages, addOptimistic] = useOptimistic(
  messages,
  (state, newMsg: Message) => [...state, newMsg],
);
const handleSend = async (text) => {
  const userMsg = { role: "user", content: text, id: `tmp-${Date.now()}` };
  addOptimistic(userMsg);  // 立刻显示
  startTransition(async () => {
    const res = await api.send(text, currentId);
    setMessages((prev) => [...prev, userMsg, { role: "assistant", content: res.answer, sources: res.sources }]);
  });
};
```

**风险**: 中
- 乐观更新后服务端返错 → 自动回滚, 用户看到消息消失会困惑
- 需要明确的 `currentId` 路由, chat 已有会话列表 → 失败保留 user 消息作为草稿 (跟 submissions Rejected 行为一致)

#### B. Approvals 审批 + Retry ([app/[locale]/submissions/_components/ApprovalRow.tsx:53-70](../packages/web/app/%5Blocale%5D/submissions/_components/ApprovalRow.tsx))

**现状**:
- 3 个 `useMutation` (approve / retry / reject), 全部 `onSuccess` 调 `qc.invalidateQueries`
- 失败时 mutation.isError 显 toast.error, 列表不更新

**改造建议**:
- `useOptimistic` 拿到 `approvals` 列表 + `applyOptimistic` 切换 review_status 立刻更新
- 服务端失败时 React 自动回滚 + mutation 弹错
- 减少 RQ 的 invalidateQueries 抖动

**风险**: 中 (跟 RQ 协同需要确认 invalidate 触发顺序)

#### C. MessageFeedback ([components/chat/MessageFeedback.tsx:36, 45-66](../packages/web/components/chat/MessageFeedback.tsx))

**现状**:
- `useState(pending)` + `setPending(true)` + `await optimizeAnswer()` + `setPending(false)` + `toast.success` + `router.push`
- 提交期间按钮 disabled + spinner, 跟 P0 表单改造一起做即可 (这本来就是个表单, 该走 useActionState)

**改造建议**:
- 用 `useFormStatus` + `useActionState` 替手动 setPending
- 不用 useOptimistic (反馈提交不像 chat 那样有"立刻看到效果"需求)

**风险**: 低

---

### 3.3 Context 简写 `<Context value={...}>` 替 `.Provider`

**现状** (7 处, 4 shadcn 内部 + 3 项目自有):

| 文件:行 | 现状 |
|---|---|
| [components/ui/toggle-group.tsx:25](../packages/web/components/ui/toggle-group.tsx) | `<ToggleGroupContext.Provider value={{ size, variant }}>{children}</ToggleGroupContext.Provider>` |
| [components/ui/form.tsx:35, 78](../packages/web/components/ui/form.tsx) | `<FormFieldContext.Provider>` / `<FormItemContext.Provider>` (2 处) |
| [components/theme-provider.tsx:254](../packages/web/components/theme-provider.tsx) | `<ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>` |
| [lib/store/app-data.tsx:26](../packages/web/lib/store/app-data.tsx) | `<Ctx.Provider value={{ datasets, schemas }}>{children}</Ctx.Provider>` |
| [components/common/form/form.tsx:116](../packages/web/components/common/form/form.tsx) | `<FormContext.Provider value={ctx}>` |
| [components/common/form-field.test.tsx:20, 66](../packages/web/components/common/form-field.test.tsx) | 测试里 2 处, 不动 |

**改造建议**:
```tsx
// 改造前:
return <Ctx.Provider value={{ datasets, schemas }}>{children}</Ctx.Provider>;

// 改造后:
return <Ctx value={{ datasets, schemas }}>{children}</Ctx>;
```

**风险**: 极低 (纯语法糖, 行为完全一致)
- shadcn UI 内部 3 处 (toggle-group, form) 改不改两可, 改了对齐 React 19 风格
- 项目自有 3 处 (ThemeProvider, AppDataProvider, FormContext) 必改
- form-field.test.tsx 2 处是测试代码, **不改** (保持跟被测代码同结构, 但其实测试是测 ProjectProvider 行为, Provider 改成 .value 后测试逻辑照样)

**收益**:
- 6 行 → 6 行 (省 0 字符), 但**可读性高** + 跟官方推荐对齐
- 项目自有 3 处可独立 commit

---

## 4. 🟢 P2 — 渐进采用, 需评估

### 4.1 React Compiler v1.0 局部试点

**现状**:
- `next.config.ts` 无 `reactCompiler: true`
- 项目 0 `useMemo` / 0 `React.memo` / 19 `useCallback` — 收益天然有限
- 19 useCallback 多在:
  - ChatShell (8 处) — 大型 hook 内部稳定化
  - form.tsx (3 处) — 自实现表单的字段注册
  - theme-provider (1 处) — setTheme
  - output/new (2 处) — useDropzone 集成
  - decode (1 处) — submit handler

**改造建议**:
1. **第一阶段**: 选 1 个路由 (建议 `admin/users`) 启用 Compiler, 观察
   ```ts
   // next.config.ts
   const nextConfig = {
     experimental: { reactCompiler: true },
   };
   ```
2. **第二阶段**: 跑 `bun run build` + `bun run dev` + `bun run test`, 看是否有 hooks 规则冲突报警
3. **第三阶段**: 用 React DevTools Profiler 对比启用前后重渲染次数
4. **第四阶段**: 没问题就全量开

**风险**: 中
- 官方 v1.0 稳定但**生态**仍在 mature (Next 16 + Compiler 兼容性)
- 跟 `<Form>` (项目自有) / `<FormField>` 协作可能有问题 (cloneElement 模式)
- 跟 shadcn (基于 forwardRef) 协作没报过错, 但要测

**收益**: 项目目前手动 memo 投入很少, 收益**有限** (主要好处是未来写新代码不用记 useCallback)

**建议**: **暂不开**, 等 React 生态 (尤其 shadcn + radix) 完整跟进再开。2026 年末再评估。

---

### 4.2 文档元数据改 React 19 `<title>`/`<meta>` 提升

**现状**:
- [app/[locale]/layout.tsx:38-41](../packages/web/app/%5Blocale%5D/layout.tsx) `export const metadata = { title: "RAG 管理后台", description: "..." }` (静态)
- 0 个 `generateMetadata` (动态 per-route 标题)
- 0 个 `<title>` / `<meta>` 写在组件里 (React 19 新支持)
- 0 个 `next/head` import (项目未用 next/head, 这是对的)

**改造建议**:
1. **动态 per-route 标题**: 新建 `generateMetadata` 在 [app/[locale]/knowledge/page.tsx](../packages/web/app/%5Blocale%5D/knowledge/page.tsx) 等, 跟 `getTranslations()` 联动 → 标题走 i18n
   ```tsx
   export async function generateMetadata({ params }: { params: Promise<{ locale: string }> }) {
     const { locale } = await params;
     const t = await getTranslations({ locale, namespace: undefined });
     return { title: `${t("知识库")} | RAG 管理后台` };
   }
   ```
2. **静态 metadata 改 React 19 in-body** (次要, Next 16 metadata API 已经是官方推荐, 不必改)

**风险**: 极低

**收益**:
- SEO 友好 (Google 索引 zh/en 各自标题)
- 浏览器 tab 标题更准

---

### 4.3 `use()` 在 render 里读 Promise

**现状**:
- 0 `use()` 调用
- 项目里 Promise 都走 `await` 模式 (RSC) 或 `useQuery` (client)
- 没有"render-time conditional promise read"场景

**评估**: **不做**
- 现有 RSC `await params` / `await apiFetch` 模式已经满足需求
- `use()` 主要服务于"客户端组件从 props 拿 Promise 然后 Suspense 挂起" — 业务没这需求

---

### 4.4 `<Activity>` (React 19 新组件)

**现状**:
- 0 `Activity` 使用
- 项目用 `display: none` 隐藏 tab 内部状态, 切换会丢 state

**候选位置**:
- SubmissionsTabs ([app/[locale]/submissions/_components/SubmissionsTabs.tsx](../packages/web/app/%5Blocale%5D/submissions/_components/SubmissionsTabs.tsx)) 切换"我提交的/全部待审/审核中心"时, 内部表单状态 / 滚动位置会丢
- KnowledgeTabs ([components/knowledge/KnowledgeTabs.tsx](../packages/web/components/knowledge/KnowledgeTabs.tsx)) 同上

**改造建议**:
```tsx
import { Activity } from "react";
<Activity mode={tab === "mine" ? "visible" : "hidden"}>
  <MySubmissionsList />
</Activity>
```

**风险**: 中
- React 19 新组件, **仍标 experimental** (在 `react/experimental` 路径)
- 跟 shadcn Tabs (Radix) 内部状态机可能冲突
- jsdom 测试需要 mock

**评估**: **暂不做**, 等 React 19.3+ Activity 稳定后评估

---

## 5. ⚪ 不做 / 已放弃

### 5.1 `React.forwardRef` → `ref` as prop 替换

**现状**:
- 95+ 处 `forwardRef` 全部在 `components/ui/*.tsx` (shadcn 装出来的)
- 项目自有 0 处
- shadcn 最新版 (2024 末) 已经**部分**支持 ref-as-prop (例如 `input.tsx`, `textarea.tsx`, `button.tsx` 新版本)
- 但**老 shadcn** 仍走 `forwardRef` 模式

**评估**: **不做**
- shadcn 是供应商代码, 改它就是 fork
- 维护成本: 未来 `bunx shadcn add` 会冲掉改动
- React 官方 codemod 也只对**项目自有**代码生效, 不动 vendor
- 等 shadcn 全部迁移完成 (预计 React 19.3 配套 shadcn 1.0 后) 再统一

### 5.2 `React.memo` / `useMemo` 替换

**现状**:
- 0 useMemo
- 0 React.memo
- **15 useCallback** (2026-06-14 精确 grep 修正: 之前估"19"偏高, 实际 5 文件 15 个调用)

**评估**: **Compiler 收益天然小, 不强求**
- 项目目前 0 useMemo / 0 React.memo 已经是"Compiler 友好"代码
- 15 useCallback 多在大型 hook 内部 (ChatShell 8 个稳定函数引用), 跟 Compiler 自动 memo 目标一致
- **建议**: 新代码不要再写 useMemo/useCallback, 老代码不动等 Compiler 试点结果

### 5.3 useCallback 15 处精细审计 + 方案 A/B 拆解

> 用户 2026-06-14 提的问题: "useCallback 能不能用 react19 新特性优化?"
> 答: React 19 本身**没有新 hook 替 useCallback** (react19.md 明确), 唯一替代是 **React Compiler** (Babel 插件, 远期, 不在 Sprint 1-3).
> 短期最大动作: **删空操作 useCallback + 拆 context**. 下面是逐处审计.

#### 5.3.1 15 处 useCallback 三档分类

| 档 | 数量 | 含义 | 处理 |
|---|---|---|---|
| **🟢 真稳定** | **5** | deps 稳定 + 真正有 useEffect 依赖 / 传给 div 事件 | 保留 |
| **❌ 空操作** | **6** | deps 几乎全 state, 每次变都返新函数; 或只 setState 没下游 React.memo | 方案 A 删 |
| **🟡 ctx 失效** | **4** | deps 稳定但走 context value, ctx 对象整体重建抵消 | 方案 B 拆 context |

#### 5.3.2 🟢 真稳定 (5 处, 保留)

| 文件:行 | 函数 | deps | 真用处 |
|---|---|---|---|
| [components/chat/ChatShell.tsx:58](../packages/web/components/chat/ChatShell.tsx) | `persistConv` | `[]` | 给 `handleNew` (deps 链 1 级稳定) + useEffect deps |
| [components/chat/ChatShell.tsx:72](../packages/web/components/chat/ChatShell.tsx) | `persistMessages` | `[]` | useEffect deps (streaming 结束写) |
| [components/chat/ChatShell.tsx:76](../packages/web/components/chat/ChatShell.tsx) | `handleNew` | `[persistConv]` | deps 链 2 级稳定, 间接有用 |
| [app/[locale]/output/new/page.tsx:36](../packages/web/app/%5Blocale%5D/output/new/page.tsx) | `add` | `[]` | 给 `onDrop` (deps 链 1 级稳定) |
| [app/[locale]/output/new/page.tsx:43](../packages/web/app/%5Blocale%5D/output/new/page.tsx) | `onDrop` | `[add]` | 传给 `<div onDrop={onDrop}>` (DOM 属性, 不参与 React.memo, 但保留 deps 稳定) |

#### 5.3.3 ❌ 空操作 (6 处, 方案 A: 改普通函数)

| 文件:行 | 函数 | deps | 为什么空操作 |
|---|---|---|---|
| [components/chat/ChatShell.tsx:89](../packages/web/components/chat/ChatShell.tsx) | `handleDelete` | `[]` | 只调 `setPendingDeleteId(id)`, 没传给 React.memo 子组件 |
| [components/chat/ChatShell.tsx:93](../packages/web/components/chat/ChatShell.tsx) | `confirmDelete` | `[pendingDeleteId, currentId, conversations]` | 3 个 deps 全是 state, 每次 state 变都返新函数 |
| [components/chat/ChatShell.tsx:115](../packages/web/components/chat/ChatShell.tsx) | `handleSelect` | `[]` | 只调 `setCurrentId(id)`, 同 handleDelete |
| [components/chat/ChatShell.tsx:119](../packages/web/components/chat/ChatShell.tsx) | `handleSend` | `[currentId, persistConv, conversations, persistMessages]` | 4 个 deps 频繁变 (currentId/conversations 是 state), useCallback 几乎每次返新函数 |
| [components/chat/ChatShell.tsx:298](../packages/web/components/chat/ChatShell.tsx) | `handleStop` | `[streamingConvId]` | streaming 状态每次流式都变, 必返新函数 |
| [app/[locale]/decode/page.tsx:115](../packages/web/app/%5Blocale%5D/decode/page.tsx) | `submit` | `[model]` | model 每次输入都变, 必返新函数 |

**改造模式** (统一):
```tsx
// 改造前:
const handleDelete = useCallback((id: string) => {
  setPendingDeleteId(id);
}, []);

// 改造后:
const handleDelete = (id: string) => {
  setPendingDeleteId(id);
};
```

**预期效果**:
- ChatShell.tsx: 8 → 3 useCallback (删 5 个)
- decode/page.tsx: 1 → 0 useCallback (删 1 个 + 删 `useCallback` import)
- 全项目 15 → 9 useCallback

**风险**: 极低
- 0 React.memo 下游, 函数引用稳定化无意义
- setState 行为完全不变
- 测试不依赖 useCallback 内部行为 (只测 onClick 触发结果)

**TDD 验证步骤** (实施时按此跑):
1. `bun run test -- ChatShell` — 跑 ChatShell 5 个 vitest 文件
2. `bun run test -- decode` — 跑 decode/page.test.tsx
3. `bun run typecheck` — 确认无新 TS 错
4. `bun run test:e2e -- chat` — Playwright 端到端确认 send/delete/select 交互无回归
5. `bun run lint 2>&1 | grep "error "` — 确认 oxlint 无 warning (lint-staged 会阻塞)

#### 5.3.4 🟡 ctx 失效 (4 处, 方案 B: 拆 context 跟 P1 3.3 合并)

| 文件:行 | 函数 | 失效根因 |
|---|---|---|
| [components/common/form/form.tsx:45](../packages/web/components/common/form/form.tsx) | `registerField` | ctx value `{values, errors, touched, registerField, setFieldValue, setFieldTouched}` 是对象, 每次 render 整体新建, 引用稳定化被抵消 |
| [components/common/form/form.tsx:49](../packages/web/components/common/form/form.tsx) | `setFieldValue` | 同上 |
| [components/common/form/form.tsx:69](../packages/web/components/common/form/form.tsx) | `setFieldTouched` | 同上 |
| [components/theme-provider.tsx:171](../packages/web/components/theme-provider.tsx) | `setTheme` | ctx value `{theme, setTheme, resolvedTheme, themes, systemTheme}` 同型 |

**根因不是 useCallback, 是 context value 是对象**:
- 修法 1: **拆 context** — `dispatch` 一个 context, `value` 一个 context, 子 useContext 只 use 它要的
- 修法 2: **useMemo 整个 ctx value** (项目目前 0 useMemo, 新增但场景合适)
- 修法 3: `<Ctx value={...}>` Context 简写 (P1 3.3)

**建议**: 跟 Sprint 2 的 P1 3.3 Context 简写合并到同一个 PR 做, 不单独立项

#### 5.3.5 方案 A 实施路线

**Pre-conditions** (项目规范):
- audit → spec → plan → dev, 审计已完, **下一步进 spec**
- spec 文件位置: `docs/superpowers/specs/use-callback-cleanup.md` (跟之前 spec 同目录)
- plan 文件位置: `docs/superpowers/plans/use-callback-cleanup.md`

**Sprint 估计**: 0.3d (改 6 处 + 删 1 import + 5 个测试文件验证)

### 5.4 `use()` 改造机会分析 (v2 修正: 6 处 initialData 表格漏报)

> **2026-06-14 v2 修正**: 初版 audit § 5.4 报"0 处, 不做", 用户追问后深度扫描发现 **6 处 RSC → client child initialData 表格** 适合 `use(promise)` 模式. 修正如下.
>
> React 19 新增 `use()` Hook, 主要两个能力:
> 1. 在 render 里直接 `use(promise)` 读 Promise, 配合 Suspense 挂起
> 2. 在条件/循环里 `use(Context)`, 比 `useContext` 灵活

**项目现状扫描结果** (v2, 2026-06-14):
- 0 `use()` 调用
- 5 处 `useContext` 调用 ([theme-provider.tsx:262](../packages/web/components/theme-provider.tsx), [ui/form.tsx:41-42](../packages/web/components/ui/form.tsx), [app-data.tsx:30](../packages/web/lib/store/app-data.tsx), [ui/toggle-group.tsx:36](../packages/web/components/ui/toggle-group.tsx), [common/form/form-context.ts:17](../packages/web/components/common/form/form-context.ts))
- **0 处在条件/循环里 useContext** (全在组件顶层)
- 0 处 "Promise as prop" 模式 (子组件接收 Promise 自行 await)
- 5 处 `params: Promise<...>` 类型声明 (Next 16 async params, **但全部已用 `await` 处理, 不需要 use())

**v2 修正结论**: 上面 5 useContext / 5 async params 维持"不立项", 但**漏报 6 处 RSC `await data` → `<Client initialData={data}>` 模式** 适合 `use(promise)`. 详见下面 "6 处 use() 候选" 表 + spec § 16 Sprint 1.6.

**v1 误报原因**: 初版 grep 只查字面 "Promise as prop", 漏了"父 RSC 拿数据 + 传 child" 模式 (initialData 是 resolved data, 不是 Promise 字面). 深度扫描应看**数据流方向**而非字面 string.

**原因**:
1. **Promise 消费**: 全部走 RSC `await` 模式 ([app/[locale]/knowledge/*/page.tsx](../packages/web/app/%5Blocale%5D/knowledge) 等) 或客户端 `useQuery` (RQ), 没有"父 RSC 把 Promise 传 client child" 场景
2. **条件 Context 读取**: 5 个 useContext 全部在组件顶层一次性读, 没有"在 if 里 useContext" 的需求
3. **Next 16 async params**: 已用 `await params` 模式 (项目规范见 [[feedback-rsc-fetch-no-browser-cookie]]), 改 `use(params)` 会破坏 RSC 数据预取流

**未来场景 (如果业务出现, 再考虑)**:
- 某 client component 需要"先弹确认框再读 token", token 是 Promise → `use(tokenPromise)` 配合 Suspense
- 某 RSC 拆分组件需要"按 prop 条件选不同 context provider" → `use(ContextA)` 或 `use(ContextB)` 条件分支

**风险**: 引入 use() 会让代码更"悬念" (谁控制 Suspense?), 项目当前简洁够用, 不引入复杂度

---

## 5.5 Non-shadcn 深度扫描 v2 (2026-06-14, 用户追问)

> **用户追问**: "分析项目现有的代码, 有没有能用 use() / useTransition / useActionState / useOptimistic 重构的, 替代 forwardRef, Context 简写. **注意不包含 shadcn 的任何组件, 不修改 shadcn**"
>
> 下面是**严格 non-shadcn** (排除 `components/ui/*`) 的 6 项深度扫描结论. 跟 § 2-4 的高层路线互补, 给"具体哪些文件 + 哪些行"清单.

### 5.5.1 `use()` 改造 (non-shadcn) — **6 处, 详见 § 5.4 v2**

**详细扫描** (排除 `components/ui/*` + `test/*` + `stories/*`):
- 0 个 `use(...)` 调用
- 5 个 `useContext` 调用:
  - [components/theme-provider.tsx:262](../packages/web/components/theme-provider.tsx) — 顶层
  - [lib/store/app-data.tsx:30](../packages/web/lib/store/app-data.tsx) — 顶层
  - [components/common/form/form-context.ts:17](../packages/web/components/common/form/form-context.ts) — 顶层
  - [components/knowledge/.../SchemaFieldRenderer.tsx (AppSelect 内部)](packages/web/components/knowledge/SchemaFieldRenderer.tsx) — 顶层
  - [components/chat/.../MessageFeedback.tsx](packages/web/components/chat/MessageFeedback.tsx) 等 — 顶层
- **0 处在条件/循环里 useContext** (全在组件顶层, 一行就 return)
- 0 处 "Promise as prop" 模式 (父 RSC 把 fetch promise 传 client child)
- 5 处 `params: Promise<...>` (Next 16 async params, **全用 `await` 处理**, 改 `use()` 破坏 RSC 数据流)
- 0 处条件分支里 useContext 满足 `use()` 唯一卖点

**结论**: `use()` 在本项目 (non-shadcn) 无改造价值. 跟 § 5.4 一致, **不立项**.

### 5.5.2 `useTransition` 改造 (non-shadcn) — **4 处新增候选**

**已有 15+ useTransition** (audit § 1 统计), 这里只看**新候选**: `useState(busy/loading) + await` 模式没走 startTransition 的.

| 文件:行 | 现状 | 改造 | 优先级 |
|---|---|---|---|
| [app/[locale]/decode/page.tsx:106-126](../packages/web/app/%5Blocale%5D/decode/page.tsx) | `useState(loading) + submit() { setLoading(true); try { await... } finally { setLoading(false) } }` | 改 `useTransition` 替 `useState(loading)`, pending 走 `isPending` | 🟡 P1 |
| [app/[locale]/output/new/page.tsx:33-86](../packages/web/app/%5Blocale%5D/output/new/page.tsx) | `useState(busy) + submit() { ... }` | 同上 | 🟡 P1 |
| [app/[locale]/knowledge/batch/page.tsx:24-90](../packages/web/app/%5Blocale%5D/knowledge/batch/page.tsx) | `useState(submitting) + onSubmit() { ... }` | 同上 | 🟡 P1 |
| [app/[locale]/output/[task_id]/_components/TaskDetailClient.tsx:39-50](../packages/web/app/%5Blocale%5D/output/%5Btask_id%5D/_components/TaskDetailClient.tsx) | `useTaskDownload` 自定义 hook 内部 `useState(downloading) + setDownloading(true) + await + setDownloading(false)` | 改 useTransition, `pending` 走 isPending | 🟢 P2 (cancel 已用 useTransition, 跟 download 一起改) |

**注意**: 
- 这 4 处**不是** form action, 不适合 useActionState (没 `<form>` 包装, 触发源是 button onClick 或 useEffect)
- 改 useTransition 的核心收益: **避免阻塞 UI** (mark pending 时不冻结输入框, 不延迟 click)
- **不替 useState(loading) → useActionState** (没 form 包装, 硬塞 useActionState 反而丑)

**跟现有 § 2.2 关系**: § 2.2 列的 6 个 form 用 useActionState (有 `<form>`); 这里的 4 个 non-form 用 useTransition. **两不冲突, 互补**.

### 5.5.3 `useActionState` 改造 (non-shadcn) — **比 § 2.2 多 1 处遗漏**

§ 2.2 列了 6 个 form (login / forgot / reset / invite / ResetPasswordDialog / CreateInviteDialog), 实际还有 **1 个遗漏**:

| 文件:行 | 现状 | 改造 |
|---|---|---|
| [app/[locale]/decode/page.tsx:180](../packages/web/app/%5Blocale%5D/decode/page.tsx) | `<form onSubmit={submit}>` (decode 是 form, 不是 button onClick) | 跟 § 2.2 同型, 改 `<form action={formAction}>` + `useActionState` 替手写 `useState(loading)+useState(err)+useTransition+submit useCallback` |

**说明**: 我之前 audit § 2.2 没列 decode 是因为 § 5.3.3 把它当作"非 form submit" (handleSend 同型) 处理, 但**实际上 decode 有 `<form onSubmit={submit}>`**, 是**真 form 模式**, 适合 useActionState.

**Total useActionState 候选 (修正)**: 7 处 (login / forgot / reset / invite / ResetPasswordDialog / CreateInviteDialog / **decode**), 不是 6.

**实现细节** (decode 走 form action 后, 跟其他 6 个 form 的不同):
- decode submit 是**纯客户端计算** (调 `systemApi.decode()` 是 client fetch), 不是 Server Action
- 两种选项:
  - **A**: 写一个 server action `_actions/system.ts` 包 `systemApi.decode()` (统一走 server-side fetch, 改最少)
  - **B**: 保留 client fetch, 但仍用 `useActionState` 模式 (form action 接受 client 函数, 不要求 server-only)
- **建议 A**, 跟其他 6 个 form 保持一致, 减少特例

### 5.5.4 `useOptimistic` 改造 (non-shadcn) — **比 § 3.2 多 3 处新候选**

§ 3.2 列了 3 个 (ChatShell 发送 / ApprovalRow 审批 / MessageFeedback). 实际还有 **3 个新候选**:

| 文件:行 | 现状 | useOptimistic 改造 |
|---|---|---|
| [app/[locale]/output/[task_id]/_components/TaskDetailClient.tsx:64-80](../packages/web/app/%5Blocale%5D/output/%5Btask_id%5D/_components/TaskDetailClient.tsx) `useTaskCancel` | `useTransition + setCancelling + await cancelTask + 失败 alert` | 用 `useOptimistic` 立刻把 `task.status` 改 `cancelled`, 服务端失败 React 自动回滚 |
| [app/[locale]/admin/users/_components/AdminUsersTable.tsx](../packages/web/app/%5Blocale%5D/admin/users/_components/AdminUsersTable.tsx) `reEnable / disable` | `useTransition + setError + await apiFetch` | 立刻把 `user.is_active` 翻面, 失败回滚 |
| [app/[locale]/admin/invites/_components/AdminInvitesTable.tsx](../packages/web/app/%5Blocale%5D/admin/invites/_components/AdminInvitesTable.tsx) `revoke` | `useTransition + setError + setConfirmToken(null) + await` | 立刻从列表移除该 invite, 失败回滚 |

**Total useOptimistic 候选 (修正)**: 6 处 (ChatShell / ApprovalRow / TaskDetailClient / AdminUsersTable / AdminInvitesTable + MessageFeedback 用 useActionState 不算)

**风险**: 中 (跟 RQ invalidateQueries 协同顺序要确认, 跟 § 3.2 同型)

### 5.5.5 替 `forwardRef` (non-shadcn) — **0 处, 不做**

**详细扫描** (排除 `components/ui/*`):
- 0 个项目自有 `React.forwardRef` 调用 (我们全部用 shadcn 包装, shadcn 内部用 forwardRef, 不动)
- 0 个项目自有函数组件接收 ref (没有 `function MyInput({ ..., ref })` 模式)

**结论**: 项目自有 0 处, **不立项**. 跟前 audit § 5.1 一致.

### 5.5.6 Context 简写 (non-shadcn) — **3 处, 比 § 3.3 范围缩小**

**严格 non-shadcn 的 `.Provider` 模式** (排除 `components/ui/*`):

| 文件:行 | 现状 | 改造 |
|---|---|---|
| [components/common/form/form.tsx:116-120](../packages/web/components/common/form/form.tsx) | `<FormContext.Provider value={ctx}>` / `</FormContext.Provider>` | 改 `<FormContext value={ctx}>{children}</FormContext>` |
| [components/theme-provider.tsx:254](../packages/web/components/theme-provider.tsx) | `<ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>` | 改 `<ThemeContext value={value}>{children}</ThemeContext>` |
| [lib/store/app-data.tsx:26](../packages/web/lib/store/app-data.tsx) | `<Ctx.Provider value={{ datasets, schemas }}>{children}</Ctx.Provider>` | 改 `<Ctx value={{ datasets, schemas }}>{children}</Ctx>` |

**Total Context 简写候选 (修正)**: 3 处 (比 § 3.3 报的 7 处少 4 处, 因为 § 3.3 混了 shadcn 内部 `toggle-group.tsx` `form.tsx` 2 处 + 1 测试. 严格 non-shadcn 实际是 3 处.)

**风险**: 极低 (纯语法糖, 行为完全一致)

**跟 § 5.3.4 方案 B 关系**: Context 简写**先做** (3 行改动, 0 风险), 方案 B 的"拆 context 替 ctx value 整体重建"是**后续**优化 (改 dispatch ctx / value ctx 拆分, 较大改动). 顺序: 简写 → 拆 context.

### 5.5.7 修正后的总数 (non-shadcn 严格 scope)

| 能力 | v1 audit 数 (§ 2-4) | v2 修正数 (本节) | delta |
|---|---|---|---|
| `use()` | 0 (不做) | 0 (不做) | 0 |
| `useTransition` (新增) | 0 (只提了 useActionState) | **4** | +4 |
| `useActionState` (form) | 6 | **7** | +1 (decode) |
| `useOptimistic` | 3 | **6** | +3 |
| 替 `forwardRef` | 0 (95+ 都在 shadcn) | 0 (non-shadcn 也 0) | 0 |
| Context 简写 | 7 (含 shadcn) | **3** (non-shadcn) | -4 (澄清范围) |

### 5.5.8 调整后的 Sprint 1 任务表 (non-shadcn only)

| Sprint | 任务 | 工作量 |
|---|---|---|
| Sprint 1.1 (新增) | 4 处 useTransition 替 useState(busy) (decode / output/new / batch / TaskDetailClient.download) | 0.3d |
| Sprint 1.2 | 7 个 form useActionState 化 (原 6 + decode) | 1.5d |
| Sprint 1.3 | 3 处 Context 简写 (form / theme-provider / app-data) | 0.1d |
| Sprint 1.4 | 方案 A 6 处 useCallback → 普通函数 (来自 § 5.3) | 0.3d |
| Sprint 1.5 | error.tsx / loading.tsx / not-found.tsx (原 P0 2.1) | 0.5d |
| Sprint 2 | useFormStatus SubmitButton + useOptimistic 6 处 (含 TaskDetailClient / AdminUsersTable / AdminInvitesTable) | 1.5d |
| Sprint 3 | React Compiler 试点 + 方案 B 拆 context | 1d |
| Sprint 4+ | generateMetadata / Activity 等渐进 | 滚动 |

---

## 6. 实施路线图

### Sprint 1 (本周, 1.5d) — 错误兜底 + 表单统一

- [ ] Day 1 上午: 4 个 error/loading/not-found 文件 (P0 2.1)
- [ ] Day 1 下午 - Day 2: 6 个表单迁移 (P0 2.2)
  - login, forgot-password, reset-password, invite, ResetPasswordDialog, CreateInviteDialog
  - 新建 3 个 server action (forgot/reset/acceptInvite/resetPwdAdmin/createInvite)
  - 测试重写: 用 `vi.mock("@/app/[locale]/_actions/account")` 替 client 端测试
- [ ] Day 2 下午: PR review + merge

### Sprint 2 (下周, 1.5d) — useFormStatus + Context 简写

- [ ] Day 1: 抽 SubmitButton 组件 (P1 3.1), 改 5 处使用方
- [ ] Day 2: 3 处项目自有 Context 简写 (ThemeProvider, AppDataProvider, FormContext)
- [ ] Day 2 下午: vitest.setup.ts 加 useFormStatus mock

### Sprint 3 (下下周, 1.5d) — useOptimistic

- [ ] Day 1: ChatShell 发送 (P1 3.2 A)
- [ ] Day 2: ApprovalRow approve/retry/reject (P1 3.2 B)
- [ ] 验证: 失败回滚 + 重试逻辑不破坏

### Sprint 4 (滚动, 0.5d/sprint) — 渐进

- [ ] generateMetadata 逐 page 补
- [ ] 关注 React 19.3+ 生态 (shadcn ref-as-prop 迁移, Activity 稳定)
- [ ] React Compiler: 选 1 路由试点, 跑 1 周没异常再扩

---

## 7. 风险与回退

| 改造 | 最大风险 | 回退方案 |
|---|---|---|
| error.tsx 等 | 错误信息泄露 (PII) | 不在 error.tsx 渲染 raw error, 只显示"出错了" + digest, 详细走 Sentry |
| useActionState 替 useState | 测试 mock 路径变 → CI 红 | 改前先 grep `vi.mock("...")` 列出所有依赖, 一次性改测试 |
| useFormStatus SubmitButton | jsdom 不支持 → vitest 红 | `vitest.setup.ts` 加 `vi.mock("react-dom", ...)` |
| useOptimistic | 失败回滚用户困惑 | toast.error + 保留乐观项作为草稿 (跟 submission reject 同) |
| Context 简写 | IDE TS 类型识别问题 (老 TS) | 升 tsgo (项目用 7.0+ 没问题) |
| React Compiler | hooks 规则冲突 | 局部 `@react-compiler-disable` 注释, 不影响全量 |

---

## 8. 与已有重构规范的关系

- **shadcn/ui 封装**: 5 个新封装 (AppSelect/AppToggle/ErrorBanner/CopyButton/FormField) 跟 React 19 改造**正交**, 改造时复用
- **表格规范**: DataTable 不动, 它是组件层抽象, 跟 React 19 渲染层无关
- **i18n**: zh.json 作 key 模式不动, React 19 metadata 改造跟 i18n 协同
- **TDD 流程**: 改造每个 hook 之前先红后绿, 测试 mock 路径要列全

---

## 9. 关键文件索引 (实施时按此排序)

```
P0 (必做):
  新建:
    packages/web/app/global-error.tsx
    packages/web/app/[locale]/error.tsx
    packages/web/app/[locale]/loading.tsx
    packages/web/app/[locale]/not-found.tsx
  改:
    packages/web/app/[locale]/login/page.tsx              (P0 2.2)
    packages/web/app/[locale]/forgot-password/page.tsx    (P0 2.2)
    packages/web/app/[locale]/reset-password/page.tsx     (P0 2.2)
    packages/web/app/[locale]/invite/[token]/page.tsx     (P0 2.2)
    packages/web/app/[locale]/_actions/account.ts         (新增 3-4 个 action)
    packages/web/app/[locale]/admin/users/_components/ResetPasswordDialog.tsx (P0 2.2)
    packages/web/app/[locale]/admin/users/_components/CreateInviteDialog.tsx (P0 2.2)

P1 (高价值):
  新建:
    packages/web/components/common/submit-button.tsx
  改:
    packages/web/vitest.setup.ts                          (useFormStatus mock)
    packages/web/components/theme-provider.tsx            (Context 简写)
    packages/web/lib/store/app-data.tsx                   (Context 简写)
    packages/web/components/common/form/form.tsx          (Context 简写)
    packages/web/app/[locale]/knowledge/triples/_components/TriplesForm.tsx (P1 3.1)
    packages/web/app/[locale]/knowledge/qa/_components/QASubmitForm.tsx     (P1 3.1)
    packages/web/app/[locale]/knowledge/documents/import/_components/ImportCommitCard.tsx (P1 3.1)
    packages/web/components/chat/ChatShell.tsx            (P1 3.2 A)
    packages/web/app/[locale]/submissions/_components/ApprovalRow.tsx      (P1 3.2 B)

P2 (渐进):
  packages/web/next.config.ts                             (Compiler 试点)
  packages/web/app/[locale]/knowledge/page.tsx           (generateMetadata)
  各 page 视情况补 generateMetadata

方案 A (useCallback 6 处空操作清理, 跟 Sprint 1 同步可做, 0.3d):
  改 (6 处 useCallback → 普通函数, 全项目 15 → 9):
    packages/web/components/chat/ChatShell.tsx             (5 处: handleDelete/confirmDelete/handleSelect/handleSend/handleStop)
    packages/web/app/[locale]/decode/page.tsx              (1 处: submit + 删 useCallback import)
  验证:
    bun run test -- ChatShell                              (5 个 vitest 文件)
    bun run test -- decode                                 (page.test.tsx)
    bun run typecheck
    bun run test:e2e -- chat                               (Playwright 端到端 send/delete/select)
    bun run lint 2>&1 | grep "error "                      (oxlint warning 阻塞 lint-staged)

方案 B (4 处 ctx useCallback 失效, 跟 Sprint 2 P1 3.3 Context 简写合并, 1d):
  改:
    packages/web/components/common/form/form.tsx           (3 处: registerField/setFieldValue/setFieldTouched)
    packages/web/components/theme-provider.tsx             (1 处: setTheme)
    + 跟 P1 3.3 合并做拆 context (dispatch 一个 ctx + value 一个 ctx)
```

---

## 10. 验证清单 (每个改造完成后跑)

```bash
# 1. 类型检查
bun run typecheck

# 2. 受影响文件测试
bun run test -- <pattern>

# 3. E2E 关键路径 (Login, Forgot, Invite Accept, Submissions 审批, Chat 发送)
bun run test:e2e -- login forgot submissions chat

# 4. 构建 (检查 Compiler / metadata 编译报错)
bun run build
```

---

**最后更新**: 2026-06-14
**作者**: Claude Code audit
**关联**: [./react19.md](./react19.md) (React 19 特性详解)
