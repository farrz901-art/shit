---
name: feedback-next-themes-dead-use-self-implement
description: "next-themes 0.4.6 已停止维护 (1 年无更新), 对 React 19 报 'Encountered a script tag' warning. 替代品: 自实现 < 100 行 (ThemeContext + useTheme + applyClass)"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 1dfcdecb-84bb-4149-9ad1-d1b332effa26
---

**next-themes 0.4.6 已死, React 19 报警告; 自实现 < 100 行.**

**Why:** 2026-06-14 web 前端 dev console 报:

> Encountered a script tag while rendering React component. ... Consider using template tag instead.
> components/theme-provider.tsx (21:5) @ ThemeProvider

根因: next-themes 0.4.6 内部用 `<script dangerouslySetInnerHTML>` 注入 IIFE 防 FOUC, 这是 React 树里**渲染时**的 script 节点, React 19 检测报警. 查 npm + GitHub, **作者 1 年没更新**, 没新版本.

Next.js 官方没出主题切换的官方库.

**修法 (用户 2026-06-14 拍板): 自实现, 不找替代品.**

**How to apply:**

```ts
// components/theme-provider.tsx 自实现要点
// 1. ThemeContext + useTheme: 跟 next-themes 0.4.6 API 兼容
//    { theme, setTheme, resolvedTheme, themes, systemTheme }
// 2. applyClass: useEffect 内 el.classList.add("dark") / remove
// 3. FOUC prevention: **useEffect 里 document.head.appendChild(inline <script>)**,
//    IIFE 同步读 storage + matchMedia 切 <html class>.
//    **不在 React 渲染树里**, 不会触发 React 19 "script tag" 警告.
//    marker 属性 data-theme-fouc="1" 避免重复注入.
// 4. mediaQuery listener: 总是注册, 内部 if (theme === "system") 才响应
// 5. storage event 监听: 跨 tab 同步
// 6. cookie 透传: BFF 端用 Headers.getSetCookie() (Node 18+) 拷 set-cookie
```

**禁止**:
- ❌ `vi.mock("next-themes", ...)` 改 `vi.mock("@/components/theme-provider", ...)`
- ❌ 找替代品 (mode-watcher / kobalte / 等等) — 都要新依赖, 风险
- ❌ 用 next/script strategy="beforeInteractive" — 注入晚, 仍可能闪

**API 兼容 (SettingsDialog 无感迁移)**:
- `themes={themes.map(t=>t.name)}` — 用项目 `lib/theme/themes.ts` 的 Theme.name
- `defaultTheme="system"` + `enableSystem` — 支持 system 选项
- useTheme() 返 `{ theme, setTheme }` 跟 next-themes 一致

**迁移清单** (下次换项目时):
1. `components/theme-provider.tsx` — 自实现
2. `lib/theme/useTheme.ts` — `export { useTheme } from "@/components/theme-provider"`
3. 3 个 test 改 mock: `vi.mock("@/components/theme-provider", ...)` (header / settings-dialog / lib/theme/index)
4. `settings-dialog.tsx` — `import { useTheme } from "@/lib/theme"` (从 lib 拿, 不要直拿 component)
5. `app/[locale]/layout.tsx` — `<ThemeProvider>` 调用不变 (API 兼容)
6. `package.json` — 删 `"next-themes": "^0.4.6"` 依赖, `bun install` 自动 prune lockfile

**关联**:
- [[feedback-debug-search-before-loop]] — 查官方/查 npm/查 GitHub 确认项目状态, 别凭印象
- [[feedback-no-shim-no-minimal-changes]] — 自实现不是 shim, 是替代. 禁兜底包装, 禁 "use next-themes if installed" 那种 polyfill
