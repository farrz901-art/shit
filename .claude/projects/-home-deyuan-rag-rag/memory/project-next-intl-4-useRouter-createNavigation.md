---
name: project-next-intl-4-userouter-createnavigation
description: "next-intl 4.x 不再直接导出 useRouter, 必须 createNavigation(routing) 包一层本地 wrapper"
metadata: 
  node_type: memory
  type: project
  originSessionId: e14df16a-a6ec-4603-b9f3-e9386f9c08e5
---

next-intl 4.x 改 API, **`next-intl/navigation` 不再直接导出 `useRouter`/`Link`/`redirect`/`usePathname`/`getPathname`**. 必须先 `createNavigation(routing)` 才能拿到.

**Why**: 2026-06-17 登录页 bug. 凭训练数据 (next-intl ≤3.x 老 API) 写 `import { useRouter } from "next-intl/navigation"` → 用户 dev server 编译报 "Export useRouter doesn't exist in target module". next-intl 4.13.0 里 `navigation.d.ts` 只导出 `createNavigation` 和 `QueryParams` 类型.

**How to apply** (在 web 项目里):
- 业务代码 import `useRouter` 永远走本地 wrapper: `import { useRouter, Link, redirect, usePathname, getPathname } from "@/i18n/navigation"`
- 本地 wrapper 文件 `packages/web/i18n/navigation.ts`:
  ```typescript
  import { createNavigation } from "next-intl/navigation";
  import { routing } from "./routing";
  export const { Link, redirect, usePathname, useRouter, getPathname } = createNavigation(routing);
  ```
- `useSearchParams` 仍然从 `next/navigation` 引 (next-intl 不重新导出)
- vitest mock `@/i18n/navigation` (本地 wrapper), **不** mock `next-intl/navigation` (第三方, mock 会替掉 broken import, 见 [[feedback-vitest-mock-third-party-hides-broken-import]])

**Why useRouter 必须用 next-intl 的** (2026-06-17 真实 bug):
- 项目 `i18n/routing.ts` 强制 `localePrefix: "always"`
- next/navigation 的 `useRouter` 不带 locale 前缀, `router.push("/")` 跳 `/` → next-intl middleware 307 → `/zh`. 多一跳 + 用户感觉"登录没反应"实际已成功
- next-intl 的 useRouter (createNavigation 出的) 自动加 `/zh` 前缀, 1 跳直达

**官方文档**: <https://next-intl.dev/docs/routing/navigation>
