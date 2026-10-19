---
name: theme-state-baseline-2026-06-10
description: "web/ 主题现状基线 — 零主题切换基础设施, .dark 块不完整, 18 处硬编码颜色"
metadata: 
  node_type: memory
  type: project
  originSessionId: e231d327-c644-4a6c-949e-d3f999036ee1
---

**2026-06-10 web/ 主题现状** (探索结果, Spec C 决策输入):

- **零运行时主题切换**: 无 ThemeProvider / next-themes / useTheme / dark class 注入 / localStorage 主题键 / cookie 主题键
- **`.dark` 块不完整** (`app/globals.css:81-94`): 9 token 缺覆盖 (ring / secondary / secondary-foreground / accent / accent-foreground / destructive / destructive-foreground / clay-foreground / moss) — 当前即使加 dark class, 视觉差异仅 4-5 套改了
- **19 个 shadcn 语义 token** + **5 个品牌扩展** (ink/paper/clay/clay-foreground/moss) + 3 字体 + 2 缓动 — 全部 HSL 三元组, 单一来源 `:root` / `.dark`
- **82% 颜色走变量** (277 处/54 文件), **18 处硬编码** 集中在 10 个组件: MetricBar / SampleTable / StatusBadge / EnvBadge / HealthDot / ErrorBoundary / FileDropzone / MessageBubble / ThinkingTrace / TaskStatusBadge + StatCard (内联 hsl ochre/indigo)
- **2 处 `bg-black/80`**: dialog / alert-dialog overlay
- **4 处 `text-white`**: output 三个页面的主操作按钮 (clay 背景)
- **Tailwind Typography 依赖可疑**: `prose` 类在 output/[task_id]/[file]/page.tsx 用, 但 `@tailwindcss/typography` 不在 package.json
- **零运行时配置目录**: 没 `lib/config/` `lib/theme/`, 走 zustand persist 复用 (已有 `useAppStore` + `partialize` 模式)
- **可扩展方案**: next-themes (shadcn 推) / tailwindcss-themer / 自写 Provider / shadcn CLI 生成
- **测试脆弱点**: `HealthDot.test.tsx` 锁了 `bg-emerald-500` / `bg-rose-500` 字符串, token 化时要同步改断言
- **`prose-neutral dark:prose-invert` 在 output/[task_id]/[file]/page.tsx:86** — Tailwind v4 prose 插件可能未生效

**Why:** Spec C 决策事实
**How to apply:** 设计主题时直接对照, 见 `docs/superpowers/specs/2026-06-10-theme-system-design.md` (待写)
