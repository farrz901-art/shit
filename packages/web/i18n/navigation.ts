/**
 * Next-intl 4.x 路由封装: 导出 locale-aware 路由工具
 *
 * 为什么不在 page 组件里直接 `import { useRouter } from "next-intl/navigation"`:
 *   Next-intl 4.x 删了直接导出, 必须先 createNavigation(routing) 才能拿到 useRouter/Link/redirect/getPathname
 *   (见 next-intl/dist/types/navigation/react-client/createNavigation.d.ts)
 *
 * 集中在一处, 业务代码统一 import "@/i18n/navigation", 避免每个组件都重复 createNavigation(routing) 初始化.
 * 同时也是"禁止 useRouter from next/navigation"强约束的执行点 — 改这里一份, 全部生效.
 * @shared
 */
import { createNavigation } from "next-intl/navigation";
import { routing } from "./routing";

// UseRouter 走 next-intl 的 locale-aware 实现: router.push("/") 自动变 /zh, 1 跳直达,
// 不被 intlMiddleware 307 重定向 (历史 bug: 2026-06-17 login 跳转走 next/navigation router → 多一跳 + 用户感"没反应")
export const { Link, redirect, usePathname, useRouter, getPathname } = createNavigation(routing);
