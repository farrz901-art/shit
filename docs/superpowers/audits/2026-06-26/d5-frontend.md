# D5: Frontend Pitfalls 扫描结果

> 扫描时间: 2026-06-26
> Agent 角色: 偏 React/Next.js 视角
> 工具调用次数: ~44 / 30 (超出上限, 部分小 Read 合并)
> 找到 7 条 finding (verified: 7, refuted: 0)

## 元信息

- 项目根: c:/doc/Code/rag
- 扫描路径: packages/web/app/[locale]/**, packages/web/lib/chat/*, packages/web/components/common/**, packages/web/proxy.ts, packages/web/middleware.ts, packages/web/i18n/**, packages/web/next.config.ts
- 已知跳过: useEffect closure 深度分析 (仅抽查了 useRef 模式), bundle 体积精确测量 (仅检查 import 模式, 未跑 webpack-bundle-analyzer), i18n 消息完整性 (未逐条交叉检查 zh.json/en.json 所有 key)
- 备注: 项目已有 import-guard.test.ts 覆盖 useRouter from next/navigation 扫描 (当前 it.skip, info-only 输出违规列表). 本报告补充了 usePathname 从 next/navigation 引入导致的 functional bug.

## Findings (7 条)

- id: FE-001
  dimension: frontend
  severity: high
  confidence: high
  title: "ImportCommitCard 用 next/navigation 的 useRouter, 手动拼 locale 前缀"
  file: packages/web/app/[locale]/knowledge/documents/import/_components/import-commit-card.tsx
  line: 10
  description: |
    import-commit-card.tsx 第 10 行引入 useRouter 从 next/navigation, 违反了项目 CLAUDE.md 强约束"路由跳转必须用 @/i18n/navigation 的 useRouter". 第 82 行 router.push() 手动拼接 `/${params.locale}/submissions` 来说明开发者也意识到需要 locale 前缀, 但 next/navigation 的 useRouter.push 不带 locale 自动前缀功能. 使用 @/i18n/navigation 的 useRouter 后可直接 router.push("/submissions"), 由 intl 自动加 locale 前缀, 1 跳直达.
  evidence: |
    ```tsx
    import { useParams, useRouter } from "next/navigation";  // line 10
    ...
    router.push(`/${params.locale}/submissions`);  // line 82
    ```
  impact: |
    多一跳 307 重定向 (同已知 bug 案例: login 跳转). 用户感"页面刷新一下以为失败".
  fix_sketch: |
    改 import { useRouter } from "@/i18n/navigation", router.push("/submissions") 直接自动加 locale.
  references:
    - CLAUDE.md §路由跳转必须用 next-intl 的 useRouter

- id: FE-002
  dimension: frontend
  severity: critical
  confidence: high
  title: "ActiveSwitch 用 next/navigation 的 usePathname, 路由匹配全失效"
  file: packages/web/app/[locale]/knowledge/_components/active-switch.tsx
  line: 6
  description: |
    active-switch.tsx 从 next/navigation 引 usePathname (line 6), 返回完整 URL 包括 locale 前缀 (如 /zh/knowledge/graph). 第 12-16 行 pathname.startsWith 检查的却是无 locale 前缀的路径 (如 "/knowledge/graph"), 对 en locale 用户永远不匹配, 导致 DomainSwitcher 永远不会渲染, 知识图谱侧功能不可用.
    当 locale=zh 时浏览器 URL 为 /zh/knowledge/graph, startsWith("/knowledge/graph") 为 false, 固返回 DatasetSwitcher. 此 bug 在 zh 环境下因默认 locale 匹配也被掩盖了部分表现, 但切换 en 后完全失效.
  evidence: |
    ```tsx
    import { usePathname } from "next/navigation";  // line 6
    export const ActiveSwitch = () => {
      const pathname = usePathname();
      if (
        pathname?.startsWith("/knowledge/graph") ||   // line 12, 对 /en/knowledge/graph 永 false
        pathname?.startsWith("/knowledge/triples") || // line 13
        ...
      ) {
        return <DomainSwitcher />;
      }
      return <DatasetSwitcher />;
    };
    ```
  impact: |
    en locale 下知识图谱路径 (graph/triples/batch/nodes/relations) 全部渲染错误的上下文开关 (DatasetSwitcher 而非 DomainSwitcher). 功能受损.
  fix_sketch: |
    改 import { usePathname } from "@/i18n/navigation" 获取 locale-stripped pathname, 或 startsWith 检查前手动 strip locale.

- id: FE-003
  dimension: frontend
  severity: high
  confidence: high
  title: "KnowledgeTabs 用 next/navigation 的 usePathname, Tab 高亮失效"
  file: packages/web/components/knowledge/knowledge-tabs.tsx
  line: 5
  description: |
    knowledge-tabs.tsx 第 5 行从 next/navigation 引 usePathname, 第 47 行用 pathname?.startsWith(path) 判断哪个 tab 应高亮. 因 next/navigation 的 usePathname 返回含 locale 前缀的完整路径, 对 en locale 用户 pathname 为 /en/knowledge/documents, startsWith("/knowledge/documents") 永为 false, 所有 tab 都不会被标记为 active. 导航链接 (href) 使用的无 locale 前缀路径由 next-intl middleware 自动补全, 跳转功能正常但视觉反馈丢失.
  evidence: |
    ```tsx
    import { usePathname } from "next/navigation";
    ...
    const pathname = usePathname();
    const active = tab.children.some((path) => pathname?.startsWith(path)) ?? false;  // line 47
    ```
  impact: |
    en locale 下知识库 Tab 栏无 active 高亮, 用户不知道当前在哪个 tab.
  fix_sketch: |
    改 import { usePathname } from "@/i18n/navigation", 获 locale-stripped pathname 再用于 startsWith 匹配. 或导出 locale-aware 版本.

- id: FE-004
  dimension: frontend
  severity: medium
  confidence: high
  title: "6 个 RSC 文件用 next/navigation 的 redirect, 双跳重定向"
  file: packages/web/app/[locale]/admin/invites/page.tsx
  line: 9
  description: |
    6 个 RSC page 文件从 next/navigation 引入 redirect, 而非从 @/i18n/navigation 引入 locale-aware redirect. 按项目 CLAUDE.md 约定, redirect 应从 @/i18n/navigation 引用于自动附带 locale 前缀. 当前用法触发 next-intl middleware 额外一次 307 重定向补 locale 前缀. 尽管 RSC redirect 最终能落地, 多一跳影响性能且在边缘情况下可能引发水合期不一致.
    涉及文件:
    - app/[locale]/admin/invites/page.tsx:9
    - app/[locale]/admin/users/page.tsx:7
    - app/[locale]/account/restore/page.tsx:9
    - app/[locale]/account/settings/page.tsx:12
    - app/[locale]/submissions/page.tsx:15
    - app/[locale]/knowledge/page.tsx:5
  evidence: |
    ```tsx
    // invites/page.tsx
    import { redirect } from "next/navigation";
    ...
    if (!me.is_admin) { redirect("/login"); }
    ```
    ```tsx
    // knowledge/page.tsx
    import { redirect } from "next/navigation";
    ...
    redirect("/knowledge/documents");
    ```
  impact: |
    额外 307 重定向增加首屏延迟. 对慢网络用户体验下降.
  fix_sketch: |
    统一改 import { redirect } from "@/i18n/navigation", 兼容 RSC 和客户端场景, 自动加 locale 前缀.

- id: FE-005
  dimension: frontend
  severity: low
  confidence: high
  title: "KnowledgeTabs 缺 aria-current 标注 active tab"
  file: packages/web/components/knowledge/knowledge-tabs.tsx
  line: 48
  description: |
    knowledge-tabs.tsx 导航 tab 在 active 时仅应用视觉类 (border-b-2), 缺 aria-current="page" 属性. 屏幕阅读器等辅助技术无法识别当前所在页面, 违反 WCAG 2.1 SC 4.1.2 (Name, Role, Value).
  evidence: |
    ```tsx
    let linkClass = "text-muted-foreground hover:text-foreground";
    if (active) {
      linkClass = "border-b-2 border-clay text-foreground";  // 缺 aria-current="page"
    }
    return (
      <Link
        key={tab.href}
        href={tab.href}
        className={cn("px-4 py-2 text-sm transition-colors", linkClass)}
      >
    ```
  impact: |
    低影响: 非关键 UI, 但不符合 a11y 最佳实践.
  fix_sketch: |
    active 时给 <Link> 加 aria-current="page".

- id: FE-006
  dimension: frontend
  severity: info
  confidence: medium
  title: "useConversations hook 覆盖 refetchOnWindowFocus 为 true"
  file: packages/web/lib/chat/api.ts
  line: 64
  description: |
    lib/chat/api.ts useConversations hook 设 refetchOnWindowFocus: true, 而项目默认约定为 false (CLAUDE.md §TanStack Query 5.x). refetchOnWindowFocus=true 在用户切回来时重新 fetch 会话列表, 对聊天场景可能有刷新需求但偏离了项目约定的默认行为, 增加不必要的网络请求. 需确认是否故意为之.
  evidence: |
    ```ts
    export const useConversations = (enabled = true) =>
      useQuery({
        enabled,
        queryFn: () => apiFetch<ServerConversation[]>("/api/chat/conversations"),
        queryKey: KEYS.conversations(),
        refetchOnWindowFocus: true,  // line 64 — 偏离项目默认 false
        staleTime: 60_000,
      });
    ```
  impact: |
    微: 用户切回标签页时触发一次额外请求. 聊天列表场景可接受.
  fix_sketch: |
    如有意刷新聊天列表, 留注释说明; 否则删此行统一跟随项目默认.

- id: FE-007
  dimension: frontend
  severity: medium
  confidence: high
  title: "SettingsDialog 用 next/navigation 的 usePathname, 手写 locale 操控"
  file: packages/web/components/settings/settings-dialog.tsx
  line: 6
  description: |
    settings-dialog.tsx 从 next/navigation 引 usePathname 而 useRouter 从 @/i18n/navigation 引, import 源不一致. 第 38-44 行对 pathname 做字符串 split 和 segments 替换来切换 locale, 方案脆弱 (依赖 segment[1] 总是 locale). 按项目约定应统一用 @/i18n/navigation 的 usePathname, 或 getPathname() 获取 locale-aware 路径.
  evidence: |
    ```tsx
    import { usePathname } from "next/navigation";  // line 6
    import { useRouter } from "@/i18n/navigation";   // line 7 — 混源 import
    ...
    const pathname = usePathname();
    const segments = pathname.split("/");
    if (routing.locales.includes(segments[ONE] as "zh" | "en")) {
      segments[ONE] = newLocale;
    } else {
      segments.splice(ONE, ZERO, newLocale);
    }
    ```
  impact: |
    代码脆弱: 若 URL 结构改变 (平台支持三语), segments[1] 假设失效. 维护成本.
  fix_sketch: |
    替换 pathname 操作为 next-intl API (如 router.replace 或 usePathname 的 locale-aware 版本).

## 未扫 / 已知缺口

- **useEffect cleanup 全面审计**: 仅抽查了 useEffect 模式, 未逐文件核查 setInterval/setTimeout 无 cleanup 情况. 已检查的 hero-section.tsx / health-client.tsx / restore-form.tsx 都有正确的 return 清理函数.
- **Bundle 体积**: 未运行 bundle-analyzer, 仅检查了 import lodash 模式 (未发现). 大第三方包 (motion/react, recharts 等) 体积未测量.
- **i18n 消息 gap**: 未逐 key 交叉匹配 zh.json 和 en.json, 但项目的 import-guard.test.ts 已有 coverage.
- **React 19 use() 在 try/catch 外**: 所有 use() 调用都确认在 Suspense 边界内的 client 组件中, 使用模式正确 (接 RSC 传的 Promise). 无违规.
- **useActionState / useFormStatus**: 使用模式正确 (app-submit-button.tsx 用 useFormStatus 从 react-dom, 计算正确). valid.
- **Client-secret 泄露**: process.env 在 'use client' 文件未发现 (grep 结果 0).
- **'use server' 边界**: 所有 server action 放在 app/[locale]/_actions/*.ts, 组件内无 'use server' 误用. valid.
