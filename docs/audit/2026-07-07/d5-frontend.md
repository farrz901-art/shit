# D5 Frontend Audit — 2026-07-07

扫描简档: `docs/audit/2026-07-07/scan-brief.md`
扫描路径: `packages/web/**` (排除 node_modules, e2e, .test.*, .spec.*)
扫描日期: 2026-07-07

---

## 概览

| 严重度 | 数量 |
| --- | --- |
| critical | 1 |
| high | 4 |
| medium | 5 |
| low | 2 |
| info | 1 |
| **总计** | **13** |

主发现:
- 1 处 critical — i18n 命名空间 + 英文 dotted key 双重违规, 影响 4 个生产文件
- 4 处 high — 项目规约违反: `useRouter`/RSC helpers 直引 `next/navigation` 致 307 重定向 (6 处), 表单组件未给 `aria-invalid`/`aria-describedby` (影响全站表单 a11y)
- 5 处 medium — TanStack Query 默认值未统一 (B-tier layout 默认 `refetchOnWindowFocus=true`), inline onClick 复杂表达式未抽命名函数 (12 处), 自实现 raw Sheet 而非 AppDrawer
- Temporal wrapper 已基本落地, 仅 2 处遗漏 (banner / formatClock), 1 处 wrapper 内部 `Date.now()` 自指
- React 19 新特性采纳良好 (useActionState × 5, useOptimistic × 2, use(promise) × 2), 唯一遗留是 `forwardRef` (React 19 已 deprecated)

---

## Findings

### FE-001 (critical)

```yaml
id: FE-001
dimension: frontend
severity: critical
confidence: high
title: "i18n 命名空间 + 英文 dotted key 双重违规 (submissions 模块 4 文件)"
file: "packages/web/app/[locale]/submissions/_components/approval-row.tsx"
line: 86
description: "submissions 模块 4 文件 (approval-row / all-approvals-table / my-submissions-list / reject-dialog) 使用了项目明确禁止的 useTranslations('namespace') 命名空间模式, 配合 dotted English key (如 actions.approve / filters.pending / reasons.${re}). 这违反 i18n 规约 (项目 memory 沉淀 feedback-no-namespace-i18n-flat-keys-only), 且这些英文 key 不在 zh.json (607 keys) 中, 必然触发 next-intl MISSING_MESSAGE → not-found.tsx 报错 (用户 2026-06-14 反馈过同类型 bug)."
evidence: |
  // approval-row.tsx:86
  const tr = useTranslations("submissions");
  ...
  // approval-row.tsx:125,135,140,149
  {tr("actions.approve")}
  {tr("actions.reject")}
  {tr("actions.retry")}
  {tr("rejectionReason")}

  // all-approvals-table.tsx:26,42-44
  const translation = useTranslations("submissions");
  { label: translation("filters.pending"), value: "pending" }
  { label: translation("filters.approved"), value: "approved" }
  { label: translation("filters.rejected"), value: "rejected" }

  // my-submissions-list.tsx:25 — dead code, useTranslations result 未使用
  useTranslations("submissions");

  // reject-dialog.tsx:48,86
  const tr = useTranslations("submissions.rejectDialog");
  label: tr(`reasons.${re}` as never),
impact: "运行后 next-intl 报 MISSING_MESSAGE, 严重时整个 submissions 子页无法渲染 (提交列表是 admin/用户必看页)."
fix_sketch: "4 文件统一改为 const t = useTranslations(); + 中文作 key (e.g. t('通过'), t('拒绝'), t('重新提交'), t('待审'), t('已通过'), t('已拒绝'), t('拒绝原因')). zh.json identity 同步加 (中文作 value), en.json 翻译. my-submissions-list.tsx:25 死调用直接删."
references:
  - "feedback-no-namespace-i18n-flat-keys-only.md"
  - "feedback-i18n-sync-on-ui-changes.md"
  - "feedback-next-intl-dev-messages-cache.md"
```

---

### FE-002 (high)

```yaml
id: FE-002
dimension: frontend
severity: high
confidence: high
title: "useRouter/useSearchParams/useParams/usePathname 从 next/navigation 而非 @/i18n/navigation (22 处)"
file: "packages/web/app/[locale]/submissions/page.tsx"
line: 15
description: "项目强制规约 (CLAUDE.md §'路由跳转必须用 next-intl 的 useRouter'): 路由跳转必须从 @/i18n/navigation 的 createNavigation(routing) 解构 useRouter/Link/redirect/usePathname/getPathname. 但扫描发现 22 处生产代码仍从 next/navigation 直引 redirect/forbidden/notFound/useParams/useSearchParams/usePathname. 用户 2026-06-17 已报过同类型 bug (登录 router.push('/') 不带 locale, intlMiddleware 307 → /zh, 用户以为登录失败)."
evidence: |
  // 1. app/[locale]/submissions/page.tsx:15 — RSC redirect
  import { redirect } from "next/navigation";

  // 2. app/[locale]/account/settings/page.tsx:12 — RSC redirect
  import { redirect } from "next/navigation";

  // 3. app/[locale]/account/restore/page.tsx:9 — RSC redirect
  import { redirect } from "next/navigation";

  // 4. app/[locale]/admin/users/page.tsx:7 — RSC redirect
  import { redirect } from "next/navigation";

  // 5. app/[locale]/admin/invites/page.tsx:11 — RSC redirect
  import { redirect } from "next/navigation";

  // 6. app/[locale]/admin/dicts/page.tsx:7 — RSC forbidden
  import { forbidden } from "next/navigation";

  // 7. app/[locale]/admin/permissions/page.tsx:20 — RSC forbidden
  import { forbidden } from "next/navigation";

  // 8. app/[locale]/knowledge/page.tsx:5 — RSC redirect
  import { redirect } from "next/navigation";

  // 9. app/[locale]/layout.tsx:23 — RSC notFound
  import { notFound } from "next/navigation";

  // 10. components/auth/guard-page.tsx:11 — RSC forbidden
  import { forbidden } from "next/navigation";

  // 11. components/page-guard.tsx:11 — RSC forbidden
  import { forbidden } from "next/navigation";

  // 12. components/knowledge/knowledge-tabs.tsx:9 — client usePathname
  import { usePathname } from "next/navigation";

  // 13-22. (其余 10 处) 均为 client component 混合 import:
  //   - app/[locale]/login/page.tsx:11 (useSearchParams)
  //   - app/[locale]/reset-password/page.tsx:9 (useSearchParams)
  //   - app/[locale]/invite/[token]/page.tsx:16 (useParams)
  //   - app/[locale]/knowledge/qa/_components/qa-submit-form.tsx:22 (useParams)
  //   - app/[locale]/knowledge/extract/[task_id]/_components/task-progress-client.tsx:9 (useSearchParams)
  //   - app/[locale]/knowledge/extract/[task_id]/preview/page.tsx:8 (useSearchParams)
  //   - app/[locale]/knowledge/triples/_components/triples-form.tsx:18 (useParams)
  //   - app/[locale]/knowledge/documents/import/_components/import-commit-card.tsx:9 (useParams)
  //   - components/chat/message-feedback.tsx:24 (useParams)
  //   - lib/hooks/use-query-params.ts:16 (useSearchParams)
impact: "RSC 文件 redirect/forbidden/notFound 触发后不带 locale 前缀 → intlMiddleware 307 → /zh, 用户看到两次跳转; client 文件 useParams/useSearchParams 返回值会带 locale 前缀 (/zh/admin/users/[id]), 调用方需手动 strip."
fix_sketch: "全部改为 import { redirect, forbidden, notFound, usePathname, useParams, useSearchParams } from '@/i18n/navigation'. 项目 CLAUDE.md 已明确规约; 部分 RSC 文件 (redirect) 用 createNavigation 包装后保持同语义."
references:
  - "packages/web/CLAUDE.md §路由跳转必须用 next-intl 的 useRouter"
  - "project-next-intl-4-useRouter-createNavigation.md"
  - "memory feedback: 2026-06-17 登录 router.push 不带 locale bug"
```

---

### FE-003 (high)

```yaml
id: FE-003
dimension: frontend
severity: high
confidence: high
title: "AppField 错误状态缺 aria-invalid + aria-describedby, 屏幕阅读器读不到错误信息"
file: "packages/web/components/common/form/app-field.tsx"
line: 87
description: "AppField (项目自有 Form 字段封装) 渲染错误信息 (line 169-174) 但 Input 元素没绑 aria-invalid / aria-describedby. 屏幕阅读器 (NVDA/JAWS/VoiceOver) 看不到 error message, 错误状态无法宣读. 表单提交失败时用户无法感知错误. 这是 4 处 useActionState 表单 (login / forgot-password / reset-password / invite) 跟 useApprovalMutations / buyer-profile / change-password 等多表单共有的根因."
evidence: |
  // app-field.tsx:87-98 — Input 渲染
  return (
    <Input
      id={inputId}
      name={name}
      type={type}
      value={value as string}
      onChange={handleChange}
      onBlur={handleBlur}
      placeholder={placeholder}
      required={required}
    />
  );

  // app-field.tsx:169-174 — 错误/帮助文本渲染, 无 id 绑定
  let helpOrErrorElement: ReactNode = null;
  if (errorMessage) {
    helpOrErrorElement = <p className="text-sm text-destructive">{errorMessage}</p>;
  } else if (help) {
    helpOrErrorElement = <p className="text-sm text-muted-foreground">{help}</p>;
  }
impact: "全站所有 AppField 使用处 (登录/重置密码/审批表单等) 错误反馈对辅助技术不可见, 触发 WCAG 2.1 1.3.1 (info and relationships) 不合规."
fix_sketch: "Input 元素加 aria-invalid={Boolean(errorMessage)} + aria-describedby={errorMessage ? `${inputId}-error` : help ? `${inputId}-help` : undefined}; 错误/帮助 <p> 加 id={...}. 抽一个 getDescribedBy helper. 一次性 fix 全站表单."
```

---

### FE-004 (high)

```yaml
id: FE-004
dimension: frontend
severity: high
confidence: high
title: "B-tier layout 默认 refetchOnWindowFocus=true, 跨 tab 切换会触发 8 个页面 refetch"
file: "packages/web/app/[locale]/submissions/layout.tsx"
line: 14
description: "TanStack Query 默认 refetchOnWindowFocus=true. 项目 chat 模块 (chat-api-provider.tsx:26) 显式覆盖 true 是合理设计 (chat 实时性高), 但其他 3 个 B-tier layout (output/health/submissions) 默认继承 true, 跟 use-lookup/tasks-list 显式 false 不统一. CLAUDE.md 顶部 11 条规约明文 'TanStack Query 5.x: staleTime 默认 60_000, refetchOnWindowFocus 默认 false (跟项目风格一致)'. 当前 3 个 layout 违反这条项目级规约."
evidence: |
  // app/[locale]/output/layout.tsx:14-17 — 没覆盖 refetchOnWindowFocus
  <QueryClientProvider client={...}>

  // app/[locale]/health/layout.tsx:12-16 — 没覆盖
  <QueryClientProvider client={...}>

  // app/[locale]/submissions/layout.tsx:14-18 — 没覆盖
  <QueryClientProvider client={...}>

  // 反例 (合规):
  // lib/hooks/use-lookup.ts:38,68 — 显式 false
  refetchOnWindowFocus: false,

  // components/chat/chat-api-provider.tsx:26 — 显式 true (chat 合理)
  refetchOnWindowFocus: true,
impact: "用户从 submissions/output/health 切到其他 tab 再切回来, 8 个 useQuery 自动 refetch, 浪费 backend 资源 + 列表闪烁 (审批列表/健康列表/任务列表都有此问题)."
fix_sketch: "在 lib/api/query-client.ts 的 createBrowserQueryClient defaultOptions.queries 全局设 refetchOnWindowFocus: false, 跟项目风格规约一致. Chat 模块仍可局部 override 为 true."
references:
  - "CLAUDE.md §代码质量清理总结 11 条"
```

---

### FE-005 (high)

```yaml
id: FE-005
dimension: frontend
severity: high
confidence: medium
title: "queryKey 传 inline object 引用, 跨 render 缓存失效 + 误 refetch"
file: "packages/web/app/[locale]/buyers/_lib/buyer-profile/hooks.ts"
line: 32
description: "useBuyerProfiles 把 params (Record<string, string>) 直接放 queryKey 数组. 每次 caller 渲染都 new 一个对象引用, TanStack Query 视为不同 cache key → 缓存命中失败 → 每次渲染都 refetch. 同时 React DevTools Profiler 会看到 cache miss 风暴. 这违反 TanStack Query 官方 key stability 原则."
evidence: |
  // app/[locale]/buyers/_lib/buyer-profile/hooks.ts:31-36
  export const useBuyerProfiles = (params?: Record<string, string>) =>
    useQuery<BuyerProfileListResponse>({
      queryFn: () => listProfiles(params) as Promise<BuyerProfileListResponse>,
      queryKey: ["buyer-profiles", params],
      staleTime: STALE_TIME_MS,
    });
  // params 在 caller 每次 render 都是新对象 (e.g. const p = {status:'active'}; useBuyerProfiles(p))
impact: "buyer-profile 列表页每次 setState 都 refetch, staleTime: 60_000 形同虚设, 浪费 backend 流量. 项目其他 22 个 useQuery 都用 stable primitive (string/number), 唯独这处例外."
fix_sketch: "改 queryKey 为序列化版本: queryKey: ['buyer-profiles', JSON.stringify(params) ?? 'all'], 或强制 caller 用 string. 在 hook 头部加 const stableKey = params ? new URLSearchParams(params).toString() : 'all';"
```

---

### FE-006 (medium)

```yaml
id: FE-006
dimension: frontend
severity: medium
confidence: high
title: "JSX 行内 onClick 多语句表达式违反规约, 12 处未抽命名函数"
file: "packages/web/app/[locale]/output/[task_id]/_components/task-detail-client.tsx"
line: 231
description: "项目规约明文禁止 JSX 行内 onClick={() => {}} 复杂表达式, 必须提取命名函数放在组件体内. 扫描发现 12 处违规, 包括 4 处 settings dialog 共用模式 (preventDefault + formRef.requestSubmit) 完全重复. 这违反 DRY + 命名函数便于单测 + 便于 React DevTools stack trace."
evidence: |
  // task-detail-client.tsx:231-234
  onClick={() => {
    setDownloadError(null);
    setCancelError(null);
  }}

  // avatar-uploader.tsx:99-105 — 嵌套 async transition
  onClick={() => {
    startRemoveTransition(async () => {
      await deleteAvatarAction();
      setPreviewUrl(null);
      useRouter().refresh();
    });
  }}

  // 4 处 settings dialog 同模式 (cancel-deletion-dialog.tsx:58-61,
  //   change-email-dialog.tsx:58-61, change-password-dialog.tsx:56-59,
  //   request-deletion-dialog.tsx:64-67):
  onClick={(event) => {
    event.preventDefault();
    formRef.current?.requestSubmit();
  }}

  // admin-pre-analysis-* 多处:
  // admin-pre-analysis-client.tsx:226-228
  onClick={() => { void handleRetry(ctx.row.original.id); }}
  // admin-pre-analysis-detail-client.tsx:160-162 + 249-251
  onClick={() => { void handleDownloadFile(...); }}
  onClick={() => { void handleDownloadZip(); }}

  // 3 处 .map() 内多语句:
  // step-indicator.tsx:37-63 (5+ 行计算 + return JSX)
  // permission-row.tsx:205-227 (state 计算 + return JSX)
  // profile-card.tsx:120-144 (null 守卫 + 转换 + return JSX)
impact: "代码可读性差, 同一段逻辑难复用, 单测覆盖不到. 4 处 dialog 同模式没抽出共用 hook."
fix_sketch: "1) 简单 setState 重置类抽 handleClearErrors / handleReset 等; 2) 4 处 dialog 的 (event) => { event.preventDefault(); formRef.current?.requestSubmit(); } 抽公共 hook useSubmitOnClick(formRef); 3) map 内多语句抽 renderStep(step, idx) 命名函数提到组件体外."
references:
  - "CLAUDE.md §代码规范 函数式编程"
```

---

### FE-007 (medium)

```yaml
id: FE-007
dimension: frontend
severity: medium
confidence: high
title: "MobileNavDrawer 手写 shadcn Sheet 而非项目 AppDrawer 包装"
file: "packages/web/components/layout/mobile-nav-drawer.tsx"
line: 14
description: "项目已封装 AppDrawer (shadcn Sheet 包装), 但 mobile-nav-drawer 直接 import shadcn Sheet 4 原语 (Sheet / SheetContent / SheetHeader / SheetTitle) 自己拼. 代码注释 (line 7-8) 自承 '用 shadcn Sheet 直实现, 没抽 AppDrawer 包装'. 这违反 CLAUDE.md §'封装组件'规约: '业务出现 ≥2 次都要考虑封装' 且 '复合 Radix 必抽 AppXxx'. Header.tsx:72 和 MobileNavDrawer 都有 NavLink 用 href={node.path ?? '#'} 兜底, 点击跳页首, a11y 失效."
evidence: |
  // mobile-nav-drawer.tsx:14
  import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";

  // mobile-nav-drawer.tsx:63-67 — 直接用 Sheet 4 原语
  <Sheet open={open} onOpenChange={onOpenChange}>
    <SheetContent side="left" className="w-80 overflow-y-auto p-0">
      <SheetHeader className="border-b border-border/60 p-4">
        <SheetTitle>{translate("导航")}</SheetTitle>
      </SheetHeader>

  // mobile-nav-drawer.tsx:74 — NavLink href 兜底 #
  <LocalizedLink key={node.key} href={node.path ?? "#"} ...>

  // header.tsx:27,72 — 同样 FALLBACK_HREF="#"
  const FALLBACK_HREF = "#";
  <NavLink key={node.key} href={node.path ?? FALLBACK_HREF}>
impact: "MobileNavDrawer 重复造轮子, 未来 Sheet 升级 (例如增加 size/dismissable ESC) 容易漏改; 移动端导航缺路径时跳页首, 用户体验糟糕, a11y 警告."
fix_sketch: "1) 改用 AppDrawer (跟 shadcn Sheet 1:1 包装, 业务代码 import 自 components/common/drawer); 2) FALLBACK_HREF='#' 改为 path 为 undefined 时不渲染 NavLink (改用 NavLink 的 disabled 态或 fallback 到 /)."
references:
  - "CLAUDE.md §封装组件"
  - "feedback-encapsulate-radix-composites-app-style-needs-approval.md"
```

---

### FE-008 (medium)

```yaml
id: FE-008
dimension: frontend
severity: medium
confidence: high
title: "账户设置 DeletionSection 手写 raw button, 应改用 Button variant=destructive"
file: "packages/web/app/[locale]/account/settings/_components/deletion-section.tsx"
line: 100
description: "账号注销 '申请注销' 按钮手写 <button type='button'> + 一长串 className 实现 destructive 样式. 项目已封装 shadcn Button (variant='destructive' size='sm' 即同效果), 且当前 import 已含 Button 同包 (input.tsx/Form/FormField 等). 手写 raw button 违反封装规约, 同时手写 raw Input (line 60-66) 没绑 label, AppField label prop 为空, 屏幕阅读器读不到字段名."
evidence: |
  // deletion-section.tsx:100-107
  <button
    type="button"
    onClick={() => toggleOpen(true)}
    className="mt-3 rounded-md border border-status-error/40 px-3 py-1.5 text-sm font-medium text-status-error hover:bg-status-error/5 disabled:pointer-events-none disabled:opacity-50"
    data-testid="deletion-request-button"
  >
    {tr("申请注销")}
  </button>

  // deletion-section.tsx:60-66 — AppField 缺 label
  <AppField name="current_password" type="password">
    <Input
      data-testid="deletion-cancel-password"
      placeholder={tr("当前密码")}
      type="password"
    />
  </AppField>
impact: "raw button 难以响应主题切换 (dark mode 颜色 token 不同); AppField 没 label 屏幕阅读器读不到 '当前密码', 用户体验不一致."
fix_sketch: "1) raw <button> → <Button variant='destructive' size='sm' type='button' onClick={...}>; 2) AppField 加 label={tr('当前密码')} prop, 同时删除 placeholder 同名字段防重复."
```

---

### FE-009 (medium)

```yaml
id: FE-009
dimension: frontend
severity: medium
confidence: high
title: "Temporal Wrapper 迁移遗漏 2 处业务 + 1 处 wrapper 内部自指"
file: "packages/web/app/[locale]/account/settings/_components/restore-deletion-banner.tsx"
line: 42
description: "CLAUDE.md §lib/date 强制: 业务时间计算/格式化走 wrapper (lib/date.ts 提供 nowMs/nowIso/toInstant/differenceInDays/formatRelativeTime 等), 禁止直接 Date.now()/new Date()/Date.parse()/Intl.DateTimeFormat. 扫描发现 3 处遗漏: 1) restore-deletion-banner.tsx:42-43 用 new Date() 当 now 基线; 2) hero-section.tsx:52 用 new Date(iso) 解析时间; 3) lib/date.ts:321 自身 fmtRelativeTime 默认参数用 Date.now()/MS_PER_SECOND 而非 nowMs() (wrapper 自指, 违反'wrapper 不依赖裸 Date'原则)."
evidence: |
  // restore-deletion-banner.tsx:41-43
  const exp = new Date(expiresAt);
  const days = Math.max(ZERO, differenceInDays(exp, new Date()));
  const hours = Math.max(ZERO, differenceInHours(exp, new Date()) % HOURS_PER_DAY);

  // hero-section.tsx:52 (健康页面)
  const date = new Date(iso);
  return `${padClock(date.getHours())}:${padClock(date.getMinutes())}:${padClock(date.getSeconds())}`;

  // lib/date.ts:321 — wrapper 内部自指裸 Date
  export const fmtRelativeTime = (
    epoch: number,
    now: number = Date.now() / MS_PER_SECOND,
  ): string => {
impact: "业务代码绕过 wrapper 走原生 Date, 主题/mocking/i18n 时区切换失去一致性; wrapper 自用 Date.now() 是单测 mock 拦截点, 未来切到 Temporal.Now.instant() 时还要再改一遍."
fix_sketch: "1) banner: nowMs() 替代 new Date() 后传给 differenceInDays/Hours (wrapper 签名 DateInput 已支持 string|number|Date|Instant); 2) hero: toInstant(iso).hour/minute/second; 3) date.ts:321 改 now: number = nowMs() / MS_PER_SECOND (内部也走 wrapper)."
references:
  - "CLAUDE.md §lib/date (2026-07-07 Temporal wrapper)"
```

---

### FE-010 (medium)

```yaml
id: FE-010
dimension: frontend
severity: medium
confidence: high
title: "AppForm 用 React 19 deprecated forwardRef, 应改 ref-as-prop 写法"
file: "packages/web/components/common/form/app-form.tsx"
line: 72
description: "React 19 已 deprecate forwardRef (RFC: ref-as-prop), 写法更简洁 (直接 {ref}: AppFormProps + 内部传 ref). 项目 CLAUDE.md §'This is NOT the Next.js you know' 提示项目用 React 19, 全站除 AppForm 外其余 forwardRef 都已迁 (主要是 shadcn 组件内置的, 等 shadcn 升级). AppForm 是项目自有封装, 现在不迁后面留为技术债."
evidence: |
  // app-form.tsx:72-86 — forwardRef 形式
  export const AppForm = forwardRef(
    <TFormData extends Record<string, unknown>>(
      {
        defaultValues,
        schema,
        action,
        onFinish,
        onFinishFailed: _onFinishFailed,
        layout = "vertical",
        encType,
        className,
        children,
      }: AppFormProps<TFormData>,
      ref: React.Ref<HTMLFormElement>,
    ) => {
  // ... 内部把 ref 传给 <form ref={ref}>
impact: "React 19.1+ forwardRef 触发 deprecation warning, 全站 20+ 调用方 (login/forgot-password/reset-password/invite/settings/restore 等表单) 都会 console 警告; 未来 React 20 移除 forwardRef 时一次性破坏."
fix_sketch: "改 AppFormProps 加 ref?: React.Ref<HTMLFormElement>; 函数签名直接 export const AppForm = <TFormData>({ref, ...}: AppFormProps) => { return <form ref={ref} ...> }, 删 forwardRef 包装. 验证 20+ 调用方不传 ref 也兼容."
```

---

### FE-011 (low)

```yaml
id: FE-011
dimension: frontend
severity: low
confidence: high
title: "avatar-uploader 头像 alt 用了英文 key 'avatar', 应改中文 key"
file: "packages/web/app/[locale]/account/settings/_components/avatar-uploader.tsx"
line: 62
description: "项目规约明文 i18n key 用中文 (zh.json identity, en.json 翻译). avatar-uploader.tsx:62 用 tr('avatar') 是英文 key, 不在 zh.json (607 keys) 也不在 en.json 中, 触发 next-intl MISSING_MESSAGE. 这是该文件 FE-001 同类型问题, 单列提醒."
evidence: |
  // avatar-uploader.tsx:62
  <AvatarImage alt={tr("avatar")} src={previewUrl} />
impact: "头像 alt 不会渲染, 屏幕阅读器读 'avatar' 而非 '头像'. 单点问题, 不影响其他 UI."
fix_sketch: "改 tr('头像') + zh.json 加 '头像': '头像' identity + en.json 'Avatar'."
references:
  - "feedback-i18n-sync-on-ui-changes.md"
```

---

### FE-012 (low)

```yaml
id: FE-012
dimension: frontend
severity: low
confidence: high
title: "global-error.tsx 全局错误 fallback 缺 type='button' + 内联 style"
file: "packages/web/app/global-error.tsx"
line: 26
description: "global-error.tsx 是 Next.js 顶层 error boundary (RSC error fallback). 当前手写 <button onClick={reset}> 没 type='button' (HTML5 默认 type='submit', 后续若误嵌入 form 会自动提交), 同时全用内联 style (background/border/color/padding) 而非 Tailwind className, 跟项目全站 Tailwind 主题系统脱节. 这是单点问题, 但放在 global error fallback (出现频率低) 上属于'等谁报再修'级别."
evidence: |
  // app/global-error.tsx:26-39
  <button
    onClick={reset}
    style={{
      background: "#111",
      border: "none",
      borderRadius: 8,
      color: "#fff",
      cursor: "pointer",
      fontSize: 14,
      padding: "10px 24px",
    }}
  >
    重试
  </button>
impact: "global-error 出现 (实际是 RSC 错误兜底, 触发率极低) 时按钮样式跟全站主题不一致 (硬编码 #111), dark mode 下反差强; 缺 type 偶发误触提交."
fix_sketch: "改 <Button type='button' onClick={reset} variant='default'>{translate('重试')}</Button>. hardcoded 文案 '出错了' / '应用遇到意外错误' / '重试' 走 next-intl t()."
```

---

### FE-013 (info)

```yaml
id: FE-013
dimension: frontend
severity: info
confidence: high
title: "React 19 新特性采纳整体良好 (信息性总结)"
file: "packages/web/app/[locale]/login/page.tsx"
line: 10
description: "扫描 React 19 新特性采纳情况, 整体合规:\n- useActionState: 5 处 (login / forgot-password / reset-password / invite / use-triple-form hook), 都跟 server action 配对, 合规.\n- use(promise): 2 处 (admin-invites-table / admin-users-table), RSC 传 promise 模式合规.\n- useOptimistic: 2 处 (admin-invites-table revoke / use-user-table toggle), 配 useTransition 合规.\n- useFormStatus: 1 处 (app-submit-button), 合规.\n- forwardRef: 仅 1 处 (app-form) 已 deprecated, 见 FE-010.\n唯一遗留: reset-password / invite 子页仍用 client router.push('/login') 切页, 不如 server-side redirect() 干净 (但这是设计选择, 不算违规)."
evidence: |
  // app/[locale]/login/page.tsx:10
  import { useActionState } from "react";

  // app/[locale]/admin/invites/_components/admin-invites-table.tsx:104
  const initialItems = use(invitesPromise);
  const [items, setItems] = useState(initialItems.items);
  const [optimisticItems, removeOptimistic] = useOptimistic(items, ...);

  // components/common/button/app-submit-button.tsx:44
  const { pending } = useFormStatus();
impact: "信息性记录, 当前 React 19 迁移完成度高 (5/5 主新特性都用上), 唯一遗留 forwardRef 见 FE-010."
fix_sketch: "无."
references:
  - "CLAUDE.md §'This is NOT the Next.js you know'"
```

---

## 修复优先级建议

| 优先级 | Finding | 估时 |
| --- | --- | --- |
| P0 (今天) | FE-001 | 30min (4 文件 + zh/en.json 同步) |
| P0 (今天) | FE-002 | 1.5h (22 处, 批量改) |
| P1 (本周) | FE-003 | 1h (AppField 一次性 + 全站表单受益) |
| P1 (本周) | FE-004 | 30min (query-client.ts 全局默认) |
| P1 (本周) | FE-005 | 15min (一行改 stable key) |
| P2 (下 sprint) | FE-006 | 1.5h (12 处, 部分可批量) |
| P2 (下 sprint) | FE-007 | 30min (改 AppDrawer) |
| P2 (下 sprint) | FE-008 | 20min (1 文件改 Button + label) |
| P2 (下 sprint) | FE-009 | 30min (3 处替换) |
| P3 (技术债) | FE-010 | 1h (验证 20+ 调用方) |
| P3 (低) | FE-011 | 5min (1 行) |
| P3 (低) | FE-012 | 15min (global-error 改 Button) |
| INFO | FE-013 | 0 (合规记录) |

**总估时: ~9 小时**

---

## 与其他维度关联

- FE-002 (useRouter 22 处违规) 也属于 D6 Architecture "规约违反", 建议在 D6 单列深扫
- FE-005 (queryKey 不稳定) 关联 D2 Concurrency (refetch 风暴)
- FE-006 (JSX inline 表达式) 关联 D3 Error handling (内联 async 易漏错误处理)
- FE-009 (Date.now 遗漏) 关联 D6 Architecture (Temporal 规约违反)