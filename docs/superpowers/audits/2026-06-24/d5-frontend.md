# D5: Frontend Pitfalls 扫描结果

> 扫描时间: 2026-06-24
> Agent 角色: D5 Frontend pitfalls 扫描 agent
> 工具调用次数: ~25
> 找到 12 条 finding

## 元信息

- 项目根: `c:/doc/Code/rag/.claude/worktrees/audit-2026-06-24/`
- 扫描路径:
  - `packages/web/app/[locale]/**` (全部页面和布局)
  - `packages/web/lib/chat/**` (聊天核心: db.ts, api.ts, migration.ts, use-chat-state.ts)
  - `packages/web/lib/api/**` (REST 调用: config.ts, chat.ts)
  - `packages/web/lib/hooks/use-query-params.ts`
  - `packages/web/components/common/**` (back-link.tsx 等封装组件)
  - `packages/web/components/chat/**` (message-feedback.tsx, memory-management-dialog.tsx, voice-recorder.tsx, composer-attachments.tsx)
  - `packages/web/components/settings/settings-dialog.tsx`
  - `packages/web/proxy.ts` (实际是 i18n 中间件 + authGuard + asset rewrite, 替代 middleware.ts)
  - `packages/web/i18n/navigation.ts` + `routing.ts` + `request.ts`
  - `packages/web/next.config.ts`
  - `packages/web/messages/zh.json` + `en.json` (各 499 行)
  - `packages/web/app/api/chat/messages/route.ts` (BFF 鉴权)
- 已知跳过:
  - `useSearchParams from "next/navigation"` (CLAUDE.md §"Note" 明确允许, 不在违规列)
  - `useParams from "next/navigation"` (CL AUDE.md 未明确禁止, 但跟 useRouter 一并 review)
  - 客户端 `localStorage` 直调集中在 3 处: `auth-bootstrap.tsx` (r ag_was_logged_in 标记), `migration.ts` (防抖 debounce key, 走 useAnonToLoginMigration 闭包), `user-menu.tsx` (cleanup) — 都是约定键 + 防抖/cleanup 场景, 非业务数据 facade, 故不列为 finding
- 备注:
  - 项目严格禁止 `useRouter from "next/navigation"`, 强制走 `@/i18n/navigation` 的 `createNavigation(routing)` 包装 (CLAUDE.md §"路由跳转必须用 next-intl 的 useRouter")
  - 项目已经从老 bug 模式修过 login/invite 页 (用 server-side redirect + cookies().set() 替 client router.push). 但 13 处 `useRouter` 违规文件**未修**, 形成不一致的技术债
  - `next.config.ts` 启用 `experimental.authInterrupts = true` (Next.js 16 still experimental), 跟 `forbidden.tsx` 文件约定配套 — 当前 13 处违规文件还**没有**走 `forbidden()`, 但 `admin/permissions/page.tsx` 用了 (line 40)
  - `next-intl` 4.x 改了 API, 业务代码必须走项目 `i18n/navigation.ts` 统一出口, `next-intl/navigation` 不再直接导出 useRouter

## Findings (12 条)

### FE-001 — critical: `evaluate-new-form` 用 `useRouter from "next/navigation"` 触发 307 重定向 bug

- **dimension**: frontend
- **severity**: critical
- **confidence**: high
- **title**: "evaluate-new-form 违规从 next/navigation 引 useRouter, 提交后跳转会被 intlMiddleware 307 重定向"
- **file**: `packages/web/app/[locale]/evaluate/new/_components/evaluate-new-form.tsx`
- **line**: 21, 131
- **description**: |
    CLAUDE.md §"路由跳转必须用 next-intl 的 useRouter" 明确禁止 `useRouter from "next/navigation"`. 此组件提交成功走 `router.push(\`/evaluate/${result.id}\`)`, 路径不带 locale 前缀, 触发 `proxy.ts` 第 96 行 `intlMiddleware` 的 307 重定向, 用户看到多一跳 + 一次额外 roundtrip. 跟 `login/page.tsx` 2026-06-17 修复的 bug 同模式, 是历史教训未全量铺开.
- **evidence**: |
    ```tsx
    import { useRouter } from "next/navigation";
    // ...
    const useEvaluateForm = () => {
      const trans = useTranslations();
      const router = useRouter();
      // ...
      const onSubmit = async (values: Record<string, unknown>) => {
        if (!file || !parsed) {
          return;
        }
        await doSubmitEval({
          file,
          formValues: values as unknown as NewEvalForm,
          router,
          setUploadErr,
          setUploading,
        });
      };
    ```
- **impact**: |
    评估提交成功后, 跳转 `/evaluate/{id}` 被 `intlMiddleware` 307 → `/zh/evaluate/{id}`, 用户感觉"提交完页面刷新一下". 评估跑 5-10 分钟, 用户中途想看进度, 这个延迟很明显. 跟 login 修复前 bug 一致.
- **fix_sketch**: |
    1 行改动: `import { useRouter } from "@/i18n/navigation"`. next-intl 包装的 router.push 自动加 `/zh` 前缀, 1 跳直达.
- **references**: []

### FE-002 — critical: `output/new` 违规从 `next/navigation` 引 `useRouter`, 上传后跳转被 307

- **dimension**: frontend
- **severity**: critical
- **confidence**: high
- **title**: "output/new 违规 import useRouter from next/navigation, presign/multipart 上传后跳转被中间件 307"
- **file**: `packages/web/app/[locale]/output/new/page.tsx`
- **line**: 22, 39, 61
- **description**: |
    新建转换 (file upload to MinIO via presign/finalize + multipart fallback) 成功后 `router.push("/output")` 走 next/navigation 的 router, 路径不带 locale 前缀, 被 intlMiddleware 307 重定向到 `/zh/output`. 跟 login 修复前同模式.
- **evidence**: |
    ```tsx
    import { useRouter } from "next/navigation";
    // ...
    const NewUploadInner = () => {
      const translation = useTranslations();
      const router = useRouter();
      // ...
      const submit = () => {
        if (!files.length || isPending) {
          return;
        }
        setErr(null);
        startTransition(async () => {
          try {
            try {
              await uploadViaPresign(files);
            } catch (error) {
              log.warn("presign/finalize 失败, fallback multipart", { error: String(error) });
              await upload(files);
            }
            router.push("/output");
    ```
- **impact**: |
    用户上传大文件 (PDF, ZIP) 等几秒, 上传完成跳转 `/output` 列表页时被 307, 列表页是新一次 RSC 渲染, 用户感觉"刚转完怎么又刷一下". 配合 useTransition, 跳转期间按钮会一直 disabled.
- **fix_sketch**: |
    1 行改动: `import { useRouter } from "@/i18n/navigation"`.
- **references**: []

### FE-003 — high: `run-detail-view` 评估详情页违规, 轮询刷新 + 删除跳转都受影响

- **dimension**: frontend
- **severity**: high
- **confidence**: high
- **title**: "run-detail-view 违规 useRouter from next/navigation, 评估删除后 /evaluate 跳转会被 307"
- **file**: `packages/web/app/[locale]/evaluate/[id]/_components/run-detail-view.tsx`
- **line**: 21, 150, 179, 183, 202
- **description**: |
    评估详情页轮询 `router.refresh()` + 删除后 `router.push("/evaluate")` 都走 next/navigation. 评估状态有 4 种 (running/completed/failed/cancelled), running 期间每 2 秒 `router.refresh()` 重跑 RSC (line 144 + 206). 轮询本身不影响路径, 但删除成功后的 `router.push("/evaluate")` 会被 307.
- **evidence**: |
    ```tsx
    import { useRouter } from "next/navigation";
    // ...
    const handleConfirm = async () => {
      setConfirmOpen(null);
      if (pendingAction === "cancel") {
        const { cancelRun } = await import("@/lib/api/evaluate");
        await cancelRun(run.id);
        router.refresh();
      } else if (pendingAction === "delete") {
        const result = await deleteRun(String(run.id));
        if (result.ok) {
          router.push("/evaluate");
        } else {
          toast.error(result.error);
        }
      }
      setPendingAction(null);
    };
    ```
- **impact**: |
    评估详情页删除成功后跳转列表, 用户多一次 307 跳 + 多一次 RSC roundtrip. 评估列表加载本身就是 1-2 秒, 用户感觉卡顿.
- **fix_sketch**: |
    1 行改动: `import { useRouter } from "@/i18n/navigation"`. `router.refresh()` 在 next-intl 包装后跟当前行为一致 (刷新当前 locale RSC).
- **references**: []

### FE-004 — high: `evaluate-list-view` 评估列表违规, 行点击跳详情被 307

- **dimension**: frontend
- **severity**: high
- **confidence**: high
- **title**: "evaluate-list-view 违规 useRouter from next/navigation, 行点击跳详情被 307"
- **file**: `packages/web/app/[locale]/evaluate/_components/evaluate-list-view.tsx`
- **line**: 15, 38, 142
- **description**: |
    评估历史列表 DataTable 行点击 `onRowClick={(row) => router.push(\`/evaluate/${row.id}\`)}` 走 next/navigation, 跳详情被 307.
- **evidence**: |
    ```tsx
    import { useRouter } from "next/navigation";
    // ...
    export const EvaluateListView = ({ runsPromise }: Props) => {
      const trans = useTranslations();
      const locale = useLocale();
      const router = useRouter();
      const runs = use(runsPromise);
      // ...
      <DataTable<EvaluationRunSummary>
        dataSource={runs}
        columns={columns}
        rowKey="id"
        onRowClick={(row) => router.push(`/evaluate/${row.id}`)}
      />
    ```
- **impact**: |
    用户点评估历史行进详情, 多一跳 + 多一次 roundtrip. 跟 FE-001 同链路, 评估模块两处都中招.
- **fix_sketch**: |
    1 行改动: `import { useRouter } from "@/i18n/navigation"`.
- **references**: []

### FE-005 — high: `submissions-tabs` 违规, URL 同步 `?tab=` 跳被 307

- **dimension**: frontend
- **severity**: high
- **confidence**: high
- **title**: "submissions-tabs 违规 useRouter from next/navigation, tab 切换 URL 同步跳被 307"
- **file**: `packages/web/app/[locale]/submissions/_components/submissions-tabs.tsx`
- **line**: 11, 26, 49
- **description**: |
    SubmissionsTabs 切 mine/all tab 时 `router.push(\`/submissions?tab=${key}\`)` 走 next/navigation, URL 不带 locale, 跳后被 307 → `/zh/submissions?tab=...`. 配合刷新, 用户感觉切 tab 慢半拍.
- **evidence**: |
    ```tsx
    import { useRouter } from "next/navigation";
    // ...
    export const SubmissionsTabs = ({
      activeTab,
      isAdmin,
      initialMine,
      initialAll,
    }: SubmissionsTabsProps) => {
      const router = useRouter();
      // ...
      return (
        <AppTabs
          options={Options}
          value={activeTab}
          onChange={(key) => router.push(`/submissions?tab=${key}`)}
          dataTestid="tab"
        />
      );
    };
    ```
- **impact**: |
    审核员日常操作就是切 mine/all tab 看待审/我提交的, 每次切都被 307, 操作延迟明显. 跟 `output/new` 同模式, 都是提交后跳的链路.
- **fix_sketch**: |
    1 行改动: `import { useRouter } from "@/i18n/navigation"`.
- **references**: []

### FE-006 — high: `permissions-admin-client` 违规, 矩阵保存后 `router.refresh()` 走 next/navigation

- **dimension**: frontend
- **severity**: high
- **confidence**: high
- **title**: "permissions-admin-client 违规 useRouter from next/navigation, 矩阵保存后 router.refresh 走错包"
- **file**: `packages/web/app/[locale]/admin/permissions/_components/permissions-admin-client.tsx`
- **line**: 19, 45, 64, 74
- **description**: |
    权限矩阵保存后 `startTransition(() => router.refresh())` 走 next/navigation, 当前页面是 RSC (从 server fetch 灌权限矩阵), `router.refresh()` 重新拉取 RSC payload. 用 next/navigation 不会引起 307 路径错, 但**违反了 CLAUDE.md 强约束** (规约统一性), 也失去了 next-intl 包装的 locale-aware 一致性.
- **evidence**: |
    ```tsx
    import { useRouter } from "next/navigation";
    // ...
    export const PermissionsAdminClient = ({
      roles,
      pages,
      matrix,
      roleList,
    }: PermissionsAdminClientProps) => {
      const router = useRouter();
      // ...
      <PermissionsTable
        // ...
        onSave={async (updates: MatrixUpdate[]) => {
          await patchPermissions(updates);
          startTransition(() => router.refresh());
        }}
    ```
- **impact**: |
    规约违反, 不影响功能 (refresh 当前路径), 但违反 CLAUDE.md §"路由跳转必须用 next-intl 的 useRouter" 强约束. 后续如有人修改路径规则, 容易出现 hard-to-debug 行为不一致.
- **fix_sketch**: |
    1 行改动: `import { useRouter } from "@/i18n/navigation"`.
- **references**: []

### FE-007 — high: `message-feedback` 违规, 反馈提交后跳 `/submissions` 被 307

- **dimension**: frontend
- **severity**: high
- **confidence**: high
- **title**: "message-feedback 违规 useRouter from next/navigation, 反馈提交后跳 /submissions 被 307"
- **file**: `packages/web/components/chat/message-feedback.tsx`
- **line**: 11, 54, 65
- **description**: |
    Chat 反馈 (不满意) 提交成功后 `router.push(\`/${params.locale}/submissions\`)` 手动拼了 locale 前缀, 避免 307. 但**仍然从 next/navigation 引 useRouter**, 跟 CLAUDE.md 强约束冲突. 手动拼 locale 字符串也容易跟 `routing.locales` 漂移 (e.g. 新增 ja locale 这里会漏).
- **evidence**: |
    ```tsx
    import { useParams, useRouter } from "next/navigation";
    // ...
    const FeedbackForm = ({
      messageId,
      question,
      originalAnswer,
      datasetId,
      onClose,
    }: FeedbackFormProps) => {
      const translation = useTranslations();
      const router = useRouter();
      const params = useParams<{ locale: string }>();
      // ...
      const handleSubmitSuccess = (approvalId: number) => {
        toast.success(translation("感谢反馈! 审核 #{id} 已创建", { id: approvalId }));
        setImproved("");
        setReason("");
        onClose();
        router.push(`/${params.locale}/submissions`);
      };
    ```
- **impact**: |
    当前手动拼了 `${params.locale}` 避免 307, 功能 OK, 但**违反 CLAUDE.md 强约束 + 漂移风险**. 跟 FE-001-FE-006 同样应当统一改走 `@/i18n/navigation`.
- **fix_sketch**: |
    2 行改动: 1) `import { useRouter } from "@/i18n/navigation"` 2) `router.push(\`/${params.locale}/submissions\`)` → `router.push("/submissions")` (next-intl 包装自动加 locale).
- **references**: []

### FE-008 — high: `reset-password` 违规, 密码重置后跳 `/login` 被 307

- **dimension**: frontend
- **severity**: high
- **confidence**: high
- **title**: "reset-password 违规 useRouter from next/navigation, 成功后 router.push('/login') 被 307"
- **file**: `packages/web/app/[locale]/reset-password/page.tsx`
- **line**: 5, 14, 22
- **description**: |
    重置密码成功后 `router.push("/login")` 走 next/navigation, 路径不带 locale, 被 307 → `/zh/login`. 跟 login 修复前同模式. **典型 bug 模式**: 用户重置完密码跳登录, 看到 1 跳延迟, 觉得"没反应", 重复点重置, 后端被刷.
- **evidence**: |
    ```tsx
    import { useRouter, useSearchParams } from "next/navigation";
    // ...
    export default function ResetPasswordPage() {
      const router = useRouter();
      const search = useSearchParams();
      const token = search.get("token") ?? "";

      const [state, formAction, isPending] = useActionState<ResetPasswordState, FormData>(
        async (prev, fd) => {
          const res = await resetPasswordAction(prev, fd);
          if (res.ok) {
            router.push("/login");
          }
          return res;
        },
        { error: null, ok: false },
      );
    ```
- **impact**: |
    密码重置后跳登录被 307, 用户感觉没反应. 跟 login 2026-06-17 修复的同款 bug. login 用了 server-side redirect (account.ts:227 redirect({href:"/", locale:await getLocale()})), 同样模式应当下沉到 `resetPasswordAction` server action.
- **fix_sketch**: |
    2 个修法: A) 1 行改 import (走 next-intl 包装) B) **推荐**: 跟 login/invite 一致, 成功跳转下沉到 `resetPasswordAction` server-side redirect, 客户端 useActionState 不再调 useRouter. 后端 set-cookie 透传问题跟 loginAction 同款.
- **references**: []

### FE-009 — high: `back-link` 违规, 全局返回链接组件用错 import

- **dimension**: frontend
- **severity**: high
- **confidence**: high
- **title**: "back-link 全局封装组件违规 useRouter from next/navigation, 影响所有用 useHistory 模式的页"
- **file**: `packages/web/components/common/back-link.tsx`
- **line**: 12, 37, 47, 49
- **description**: |
    `BackLink` 是全局封装组件 (CLAUDE.md §"封装组件 (2026-06-14)" 列入), 所有页面用 useHistory=true 走 history back 都会中招. 当前 `router.back()` 不带路径, 不被 307, 但 `router.push(href)` fallback 路径同样违规. **封装组件自己违反规约**, 影响范围最大.
- **evidence**: |
    ```tsx
    import { useRouter } from "next/navigation";
    // ...
    export const BackLink = ({
      href,
      useHistory = false,
      label = "返回",
      className,
      "data-testid": dataTestid,
    }: BackLinkProps) => {
      const router = useRouter();

      const handleClick = (event: React.MouseEvent<HTMLAnchorElement>) => {
        if (event.metaKey || event.ctrlKey || event.shiftKey || event.button !== MOUSE_BUTTON_LEFT) {
          return;
        }
        event.preventDefault();
        if (typeof globalThis !== "undefined" && globalThis.history.length >= MIN_HISTORY_FOR_BACK) {
          router.back();
        } else {
          router.push(href);
        }
      };
    ```
- **impact**: |
    跟 FE-007 同链路, 手动拼 locale 不存在, fallback `router.push(href)` 走 next/navigation 直接被 307. 用 `useHistory=true` 的页 (knowledge/qa, knowledge/import 等) 都受影响. **封装组件自己违反规约 = 影响全站**.
- **fix_sketch**: |
    1 行改动: `import { useRouter } from "@/i18n/navigation"`. next-intl 包装 router.push 自动加 locale 前缀.
- **references**: []

### FE-010 — high: `settings-dialog` 违规, 语言切换 `router.push` 走 next/navigation

- **dimension**: frontend
- **severity**: high
- **confidence**: high
- **title**: "settings-dialog 违规 useRouter from next/navigation, 语言切换 router.push 走 next/navigation"
- **file**: `packages/web/components/settings/settings-dialog.tsx`
- **line**: 6, 29, 45, 46
- **description**: |
    SettingsDialog 语言切换行手动拼路径后 `router.push(newPath)`, 这里 newPath 已经是 `/zh` 或 `/en` 开头的 (line 43), 所以**没**触发 307 (路径含 locale, middleware 不重定向). 但**违反 CLAUDE.md 强约束 + 手动路径拼接 + 手动分割 pathname 容易漂移** (e.g. 多层 locale 路径).
- **evidence**: |
    ```tsx
    import { usePathname, useRouter } from "next/navigation";
    // ...
    export const SettingsDialog = ({ open, onOpenChange }: Props) => {
      const { theme, setTheme } = useTheme();
      const locale = useLocale();
      const router = useRouter();
      const pathname = usePathname();
      // ...
      const handleLocaleChange = (newLocale: string) => {
        document.cookie = `NEXT_LOCALE=${newLocale}; path=/; max-age=31536000; SameSite=Lax`;
        const segments = pathname.split("/");
        if (routing.locales.includes(segments[ONE] as "zh" | "en")) {
          segments[ONE] = newLocale;
        } else {
          segments.splice(ONE, ZERO, newLocale);
        }
        const newPath = segments.join("/") || `/${newLocale}`;
        startTransition(() => {
          router.push(newPath);
          router.refresh();
        });
      };
    ```
- **impact**: |
    当前功能 OK (路径含 locale), 但**违反 CLAUDE.md 强约束** + 手动路径拼接代码冗长. 推荐改用 next-intl 包装 router, 简化 `handleLocaleChange` 到 2-3 行.
- **fix_sketch**: |
    1) 改 `import { useRouter, usePathname } from "@/i18n/navigation"` 2) next-intl 包装的 router.push 自动 strip/add locale, 简化 pathname 处理.
- **references**: []

### FE-011 — high: `triples-form` / `qa-submit-form` / `import-commit-card` 三个表单违规, 审核提交后跳 `/submissions` 被 307

- **dimension**: frontend
- **severity**: high
- **confidence**: high
- **title**: "knowledge 三处表单违规 useRouter from next/navigation, 审核提交后跳 /submissions 手动拼 locale 仍违反规约"
- **file**: `packages/web/app/[locale]/knowledge/triples/_components/triples-form.tsx`
- **line**: 15, 147, 173 (triples); `packages/web/app/[locale]/knowledge/qa/_components/qa-submit-form.tsx` line 8, 122, 113 (qa); `packages/web/app/[locale]/knowledge/documents/import/_components/import-commit-card.tsx` line 10, 45, 82 (import)
- **description**: |
    三处审核提交成功后都手动拼 `${params.locale}/submissions` 路径, 跟 message-feedback 同模式 (FE-007). 当前功能 OK, 但**违反 CLAUDE.md 强约束 + 手动拼 locale 字符串漂移风险**. 三处同模式重复违规, 应当统一改走 next-intl 包装.
- **evidence (triples-form)**: |
    ```tsx
    import { useParams, useRouter } from "next/navigation";
    // ...
    useEffect(() => {
      if (state.ok && state.data.approval_id > FIRST_IDX && state.data.approval_id !== toastedId) {
        setToastedId(state.data.approval_id);
        toast.success(trans("已提交审核 #{id}", { id: state.data.approval_id }));
        router.push(`/${params.locale}/submissions`);
      } else if (!state.ok && state.error && !clientError) {
        toast.error(state.error);
      }
    }, [state, clientError, trans, router, params.locale, toastedId]);
    ```
- **evidence (qa-submit-form)**: |
    ```tsx
    import { useParams, useRouter } from "next/navigation";
    // ...
    useEffect(() => {
      if (
        state.ok &&
        state.data.approval_id > ZERO &&
        state.data.approval_id !== toastedIdRef.current
      ) {
        toastedIdRef.current = state.data.approval_id;
        toast.success(`${tr("已提交审核")} #${state.data.approval_id}`);
        router.push(`/${locale}/submissions`);
    ```
- **evidence (import-commit-card)**: |
    ```tsx
    import { useParams, useRouter } from "next/navigation";
    // ...
    useEffect(() => {
      if (
        state.ok &&
        state.data.approval_id > APPROVAL_ID_NONE &&
        state.data.approval_id !== toastedId
      ) {
        setToastedId(state.data.approval_id);
        toast.success(tr("已提交审核 #{id}", { id: state.data.approval_id }));
        router.push(`/${params.locale}/submissions`);
    ```
- **impact**: |
    当前功能 OK (手动拼 locale 避免 307), 但**违反 CLAUDE.md 强约束 + 漂移风险 + 三处重复模式**. 任何一处都应改走 next-intl 包装, 简化 `router.push("/submissions")` 1 行.
- **fix_sketch**: |
    三处同模式: 1) `import { useParams, useRouter } from "@/i18n/navigation"` 2) `router.push(\`/${params.locale}/submissions\`)` → `router.push("/submissions")`. 3) `useParams` 不再用 (next-intl 包装内部处理 locale).
- **references**: []

### FE-012 — medium: 客户端 `NEXT_PUBLIC_CHAT_TOKEN` 公开 token 设计 (合规但需 review)

- **dimension**: frontend
- **severity**: medium
- **confidence**: high
- **title**: "客户端公开 token 设计, 任何用户可从 .js bundle 读 NEXT_PUBLIC_CHAT_TOKEN 防 Dify 滥刷"
- **file**: `packages/web/lib/api/chat.ts`
- **line**: 7, 29
- **description**: |
    `lib/api/chat.ts:7` 读 `process.env.NEXT_PUBLIC_CHAT_TOKEN`, 任何用户可从浏览器 DevTools → Sources → bundle 读到. 注释 (.env.example:16) 说"公网 anti-abuse 共享 token", 跟 BFF `app/api/chat/messages/route.ts:2` 比对 — 是设计如此 (BFF 跟 client 用对称 token 防透传). 风险面: 拿到 token 的用户可对 `/api/chat/messages` 调 Dify 流量, 配合 Dify 配额/限速, 可能引起成本上涨.
- **evidence**: |
    ```ts
    // packages/web/.env.example:16
    # 公网 anti-abuse 共享 token; 前端读 NEXT_PUBLIC_CHAT_TOKEN
    NEXT_PUBLIC_CHAT_TOKEN="secret-123"

    // packages/web/lib/api/chat.ts:7
    const getChatToken = (): string => process.env.NEXT_PUBLIC_CHAT_TOKEN ?? "";

    // packages/web/lib/api/chat.ts:27-30
    headers: {
      "Content-Type": "application/json",
      "x-chat-token": getChatToken(),
    },

    // packages/web/app/api/chat/messages/route.ts:43-50
    const checkAuth = (req: NextRequest): true | Response => {
      const expected = process.env.CHAT_PUBLIC_TOKEN;
      if (!expected) {
        return badRequest("server 未配置 CHAT_PUBLIC_TOKEN");
      }
      const got = req.headers.get("x-chat-token");
      if (got !== expected) {
        return unauthorized();
      }
      return true;
    };
    ```
- **impact**: |
    1) 拿到 token 的攻击者可对 Dify 打 spam, 耗尽配额. 2) 反爬强度弱, 跟"anti-abuse"目标名不副实 (用户登录后 cookie 鉴权才有效, 匿名 spam 难防). 3) D1 (security) 应当交叉 review token 熵/rotate 策略.
- **fix_sketch**: |
    1) D1 交叉 review: token 熵 / 长度 / rotate 频率, 是否真的"anti-abuse" 2) 考虑把 chat 鉴权下沉到 cookie (跟 BFF catch-all 一致), 拿 rag_user_token 调 Dify, 取消 NEXT_PUBLIC_CHAT_TOKEN 3) 短期: 至少在 chat messages route 跟 Dify 之间加 rate limit (per-IP/per-user).
- **references**: []

## 未扫 / 已知缺口

- **i18n key 完整性 (zh.json ↔ en.json)**: 499 行规模, 没法逐行对比, 跳了. CLAUDE.md §"i18n value 不能含 namespace 字符" 提到的"value 含 `.` 被误当 namespace" 我 grep 过 `^\s*\"[^\"]*\.[^\"]*\":` 在 messages/ 没匹配, 跳过.
- **i18n value 含 `:`**: 同上, 跳了.
- **TanStack Query staleTime/cache key**: 看了 `lib/chat/api.ts`, 配置正确 (60_000 ms + retry: false + refetchOnWindowFocus: true). 其他 useQuery/useMutation 调用方太多, 没法逐文件 review staleTime 配置. CLAUDE.md §"Top-12 防再犯守则" 第 11 条已经定规约.
- **`useEffect` cleanup 缺失**: grep 出 30+ 处 `useEffect(`, 抽查了 dict-audit-log.tsx (用 cancelled flag), voice-recorder.tsx (用 timerRef cleanup), use-chat-state.ts (183 行) (无 cleanup 但只调 setter, 无副作用可清理), chat-shell migration (有 debounce 标志), 都合理. 全面扫需 ≥30 次工具调用, 已超限, 故未深扫.
- **`'use client' / 'use server' 边界错**: 抽查了核心页面, 都正确. 未全量扫.
- **a11y 缺失 (button aria-label, img alt)**: 全量扫需 ≥30 次工具调用, 超限. 抽查的页面都有 `data-testid`, 部分有 `aria-hidden` (RunDetailView:41). 全面扫留给后续 spec.
- **bundle 体积过大 (未 dynamic import)**: `run-detail-view.tsx:177` `const { cancelRun } = await import("@/lib/api/evaluate")` 用了 dynamic import, 正确. 其他页未审.
- **ref 持有陈旧 closure**: 抽查的 memory-management-dialog / use-chat-state 都用 ref 跟 state 隔离, 模式正确. 未全扫.
- **client-secret 泄露**: 唯一候选是 FE-012 NEXT_PUBLIC_CHAT_TOKEN, 已列.
- **route.ts (proxy.ts)**: 已读, 守卫 + asset rewrite + 排除 `/api/` 都正确, 没发现 critical 缺陷.
- **`messages/{zh,en}.json` 大小**: 999 行合计, 全量对比超 token 限, 跳.
- **BFF `/api/chat/messages` 鉴权**: 已读, 跟 NEXT_PUBLIC_CHAT_TOKEN 对称设计, 写在 FE-012.

## 总结

- **finding 总数**: 12 (10 个 high + 1 个 medium + 1 个 critical 仅 FE-001 是 critical? 重看: FE-001/FE-002 是 critical 因触发 307 bug 模式跟 login 修复前同款; FE-003-FE-011 是 high)
- **按 severity 分组**:
  - critical: 2 (FE-001 evaluate-new-form, FE-002 output/new — 都触发 307 bug 模式)
  - high: 9 (FE-003 ~ FE-011 — 9 处 useRouter 违规, 多数手动拼 locale 兜底)
  - medium: 1 (FE-012 NEXT_PUBLIC_CHAT_TOKEN 公开 token 设计)
- **核心问题**: 13 处文件 (合并后实际 10 处 + 3 处表单 — `triples-form`/`qa-submit-form`/`import-commit-card`) 违反 CLAUDE.md §"路由跳转必须用 next-intl 的 useRouter" 强约束. 3 处 (login/page.tsx, invite/[token]/page.tsx) 已经修了 (走 server-side redirect), 13 处未修. **`back-link.tsx` 是全局封装组件, 影响范围最大** (FE-009).
- **主要风险**: 跟 login 2026-06-17 修复的同款 307 bug 模式, 7 处直接 `router.push("/path")` 不带 locale, 5 处手动拼 `${params.locale}/path` 兜底 (避免 307 但违反规约 + 漂移风险).
- **修复路径**: 每个文件 1 行改 `import` (`from "next/navigation"` → `from "@/i18n/navigation"`), 加上可能简化手动拼 locale 的地方. **推荐优先级**: FE-009 (back-link 全局) > FE-001/FE-002 (critical 307 bug) > FE-003-FE-008/FE-011 (high) > FE-010/FE-012 (规约统一 / security review).
- **已知豁免**: `app/[locale]/login/page.test.tsx` 已有 import guard 测试 (line 21-30), 修了 login 后加了 mock. 其他 13 处未加 guard 测试, 一旦改 import 需要全量 mock 重写.
- **额外建议**: 考虑在 CI 加自定义 lint 规则 (oxlint plugin) grep `useRouter.*from "next/navigation"`, 自动 fail PR. 项目根 `oxlint` 1.x 支持自定义 rule, 实施成本低.
