# P1 维度 ① div/span 提取样式组件 — Agent D (lib+const+i18n+scripts ~110 files)

> 扫描日期: 2026-06-28
> 范围: `packages/web/{lib,const,i18n,scripts,proxy.ts,next.config.ts}`, 排除 `.test.ts`/`.test.tsx` 与 `e2e/`/`tests/`/`messages/`/`components/`/`app/`
> 任务: 找 div/span 可被 `<AppXxx>` 封装替代的硬编码 markup 模式

## 扫描概览

- **总文件数 (非测试)**: 76
- **含 div/span 的文件**: 0 (生产代码)
- **无 UI 文件**: 76 (100%)
- **发现重复 pattern**: 0
- **可直接替换为已有封装**: 0
- **建议新封装组件**: 0

### 子目录分布

| 子目录                | 文件数 | JSX 类型                          | div/span 数 |
| --------------------- | ------ | --------------------------------- | ----------- |
| `lib/api/*`           | 22     | 纯 TS (fetch / 类型 / queryKeys) | 0           |
| `lib/chat/*`          | 15     | 纯 TS (Dify/OpenAI/SSE/storage)  | 0           |
| `lib/auth/*`          | 3      | 纯 TS (permission 工具)          | 0           |
| `lib/hooks/*`         | 9      | 纯 TS hooks                       | 0           |
| `lib/store/*`         | 5      | 1 个 Provider (.tsx) + 4 纯 TS    | 0           |
| `lib/theme/*`         | 3      | 纯 TS 配置 + re-export            | 0           |
| `lib/parse/*`         | 3      | 纯 TS (CSV/Excel/JSON 解析)       | 0           |
| `lib/dom/*`           | 2      | 纯 TS (download 工具)             | 0           |
| `lib/buyer-profile/*` | 2      | 纯 TS (hooks + types)             | 0           |
| `lib/evaluate/*`      | 2      | 纯 TS (barrel + types)            | 0           |
| `lib/server/*`        | 1      | 纯 TS (RSC fetch)                 | 0           |
| `lib/test-utils/*`    | 2      | 1 个 Provider (.tsx) + 1 barrel   | 0           |
| `lib/` 顶层            | 6      | 纯 TS (motion/utils/log/...)      | 0           |
| `const/index.ts`      | 1      | 纯常量                            | 0           |
| `i18n/*`              | 3      | 纯 TS (routing/navigation/request) | 0           |
| `scripts/*`           | 1      | 纯 TS (Node CLI, 无 React)        | 0           |
| `proxy.ts`            | 1      | Next.js middleware, 无 JSX       | 0           |
| `next.config.ts`      | 1      | Next config, 无 JSX              | 0           |

## 重点扫描结果 (按任务要求的重点关注区)

### lib/hooks/* (9 个非测试文件)

| 文件                  | 类型                | div/span | 备注                       |
| --------------------- | ------------------- | -------- | -------------------------- |
| `use-confirm.ts`      | hook (state)        | 0        | 仅 `useState` 控制 open     |
| `use-dialog.ts`       | hook (state)        | 0        | 仅 `useState` 控制 open     |
| `use-lookup.ts`       | hook (TanStack Q)   | 0        | 返回 `items/byKey/labelFor` |
| `use-permissions.ts`  | hook (zustand)      | 0        | 返回 `can/isAdminLevel`    |
| `use-datasets.ts`     | hook (TanStack Q)   | 0        | `fetchDatasets` 包装       |
| `use-nodes.ts`        | hook (TanStack Q)   | 0        | `fetchNodes` 包装          |
| `use-relations.ts`    | hook (TanStack Q)   | 0        | `fetchRelations` 包装      |
| `use-pagination.ts`   | hook (state)        | 0        | 分页 state + 计算         |
| `use-polling.ts`      | hook (react-use)    | 0        | `useInterval` 转封装       |
| `use-query-params.ts` | hook (URL params)   | 0        | `useSearchParams` 包装     |
| `index.ts`            | barrel              | 0        | export 集合                |

**结论**: hooks/ 全部为纯逻辑, 无任何 JSX 返回. 0 div/span.

### lib/chat/* (15 个非测试文件)

| 文件                   | 类型                       | div/span | 备注                       |
| ---------------------- | -------------------------- | -------- | -------------------------- |
| `use-chat-state.ts`    | 巨大 state/handler hook    | 0        | 408 行纯 TS state 编排    |
| `chat-utils.ts`        | 纯函数                     | 0        | `processStream`/`ensureConversation` 等 |
| `api.ts`               | TanStack Query hooks       | 0        | `useConversations` 等     |
| `dify.ts`/`openai.ts`/`sse.ts`/`factory.ts` | 客户端                      | 0        | Dify/OpenAI 适配器       |
| `storage.ts`/`db.ts`   | IDB/Dexie 持久化           | 0        | anon user IDB            |
| `migration.ts`/`memory-integration.ts` | 迁移/记忆                 | 0        | `performAnonToLoginMigration` |
| `types.ts`             | 类型                       | 0        | `Conversation`/`Message` |
| `index.ts`             | barrel                     | 0        | -                          |

**结论**: chat/ 全部为业务逻辑 + 网络/存储适配器, 0 div/span. JSX 渲染在 `components/chat/`, 已由 Agent A 范围覆盖.

### lib/store/app-data.tsx + lib/test-utils/intl-wrapper.tsx (仅有的 2 个非测试 .tsx)

| 文件                       | 类型                                  | div/span | 内容                                                                |
| -------------------------- | ------------------------------------- | -------- | ------------------------------------------------------------------- |
| `lib/store/app-data.tsx`   | React Context Provider                | 0        | `<Ctx value={...}>{children}</Ctx>` — 无包装 div                  |
| `lib/test-utils/intl-wrapper.tsx` | i18n 测试 wrapper              | 0        | `<NextIntlClientProvider ...>{children}</NextIntlClientProvider>` — Provider, 无包装 div |

**结论**: 这两个是 Context Provider / i18n Provider, 不是布局 markup. 无 div/span 包装可提取.

### lib/motion.ts (预想是 UI, 实际是配置)

`lib/motion.ts` 共 259 行, 全是 framer-motion 变体 (variants) 配置常量:
- `EASE` / `CSS_EASE` / `CSS_EASE_STR` — 缓动函数
- `DUR` / `RADIUS` / `SHADOW` / `LIFT` / `DELAY` / `PRESS` / `STAGGER_STEP` — 设计 token
- `TRANSITION_*` — 过渡模板
- `fadeUp`/`fadeIn`/`scaleIn`/`fadeUpGentle`/`fadeUpLarge`/`slideInTop`/`pulse`/`rowStagger` — 动画变体

返回的是 framer-motion variants object (`{ hidden, show }`), 不是 JSX. 无 div/span.

### lib/theme/* (3 个文件)

- `lib/theme/index.ts` — barrel re-export, 0 JSX
- `lib/theme/themes.ts` — `themes` / `getThemeConfig` 主题配置对象 (颜色 token), 0 JSX
- `lib/theme/use-theme.ts` — 纯 re-export 自 `components/theme-provider`, 0 JSX

### proxy.ts + next.config.ts + i18n/* + const/index.ts + scripts/*

- `proxy.ts` (105 行) — `authGuard` + `rewritePrefixedAsset` + `intlMiddleware` 路由守卫, 用 `NextResponse.redirect/rewrite`, 无任何 JSX
- `next.config.ts` (29 行) — NextConfig 配置, 无 JSX
- `i18n/routing.ts` (8 行) — `defineRouting({locales, defaultLocale, localePrefix})`, 无 JSX
- `i18n/navigation.ts` (14 行) — `createNavigation(routing)` 解构导出, 无 JSX
- `i18n/request.ts` (19 行) — `getRequestConfig`, 无 JSX
- `const/index.ts` (91 行) — `ZERO`/`ONE`/`HTTP_OK` 等常量, 无 JSX
- `scripts/duplication-report.ts` (128 行) — Node CLI 跑 jscpd 报告生成, 无 React 依赖

## 检查结论 (按严重度)

### 🔴 严重
**无**. 本范围 76 个文件全部为纯 TS 逻辑 / 配置 / Provider, **0 个 div/span**.

### 🟡 中等
**无**. 无需替换为 `<ErrorBanner>` / `<AppDialog>` 等封装组件.

### 🟢 建议
**无**. 无需新增封装组件.

## 扫描方法说明

1. **Grep 阶段**: 用 `<div|<span|<p[ >]|<h[1-6][ >]|<button|<input|<select|<form|<table` 全局扫描 lib/, const/, i18n/, scripts/, proxy.ts, next.config.ts, **生产代码 0 命中** (全部命中均在 `.test.tsx`).
2. **JSX 类型检查**: 用 `ReactElement|ReactNode|JSX\.Element` 匹配, 仅命中 15 处, 全部为 **注释引用** (e.g. `// 从 chat-shell.tsx 提取: 聊天状态 hooks`), 非实际 JSX.
3. **人工 Read 抽查**: 已逐一 Read `lib/hooks/use-*.ts` (10 个), `lib/chat/use-chat-state.ts` (408 行), `lib/motion.ts` (259 行), `lib/test-utils/intl-wrapper.tsx`, `lib/store/app-data.tsx`, `lib/theme/*` (3 个), `lib/buyer-profile/*` (2 个), `lib/parse/*` (3 个), `proxy.ts`, `next.config.ts`, `i18n/*` (3 个), `const/index.ts`, `scripts/duplication-report.ts`. 全部确认无 div/span markup.
4. **样本规律**: 此区是项目 **架构层** — API fetch、类型定义、Zustand store、React Query hooks、配置常量. **没有 1 个** div/span 是合理的, 因为 UI 渲染职责属于 `components/` 与 `app/`.

## 推荐后续 P1 工作

- ✅ **不再扫描 lib/, const/, i18n/, scripts/, proxy.ts, next.config.ts** — 本范围 100% 无 UI markup.
- 本报告可作为 P1 "Agent D 已扫描, 无发现" 的终态归档, 配合 Agent A (components/) 和 Agent B/C (app/) 形成完整覆盖.

## 关联文件路径 (供后续核查)

| 类型         | 关键文件路径                                                                  |
| ------------ | ----------------------------------------------------------------------------- |
| Provider     | `packages/web/lib/store/app-data.tsx`                                         |
| Provider     | `packages/web/lib/test-utils/intl-wrapper.tsx`                                |
| 配置         | `packages/web/lib/motion.ts` (framer-motion variants, 非 JSX)                |
| Hook         | `packages/web/lib/hooks/use-{confirm,dialog,pagination,polling,query-params}.ts` |
| Hook         | `packages/web/lib/hooks/use-{lookup,permissions,datasets,nodes,relations}.ts` |
| Hook         | `packages/web/lib/chat/use-chat-state.ts` (408 行 state 编排)                |
| 中间件       | `packages/web/proxy.ts`                                                       |
| Next config  | `packages/web/next.config.ts`                                                 |
| 常量         | `packages/web/const/index.ts`                                                 |
| i18n         | `packages/web/i18n/{routing,navigation,request}.ts`                           |
| 脚本         | `packages/web/scripts/duplication-report.ts`                                  |