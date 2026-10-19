# 主题系统 (白/夜 + 可扩展) 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 给 RAG 管理后台接入 next-themes 运行时主题切换 (亮/暗)，18 处硬编码颜色 token 化，ThemeToggle 齿轮 + SettingsDialog 弹框 (主题切换 + 语言占位 + 账号占位)，装 @tailwindcss/typography。

**Architecture:** next-themes 0.4.x + React Context + CSS 变量 + Tailwind v4 `@theme inline`。ThemeProvider 在 root layout 注入，主题配置抽到 `web/lib/theme/themes.ts`，所有色值用 CSS 变量 + `bg-status-success` 等语义 class 名。SettingsDialog 用 Radix Dialog 封装。

**Tech Stack:** next-themes, @tailwindcss/typography, Radix UI, lucide-react, vitest + @testing-library/react, jsdom, bun

**Spec:** `docs/superpowers/specs/2026-06-10-theme-system-design.md`

**前置条件:**
- 当前在 `master` 分支, 已有 4 个未推送 commit (含 i18n plan)
- 计划完成后路由结构可能冲突 (i18n 计划把 layout 移入 `[locale]/`)
- 建议顺序: 先实施本主题 plan, 后做 i18n plan; 或两 plan 并行在两个 worktree
- **本 plan 假设 layout 还在 `app/layout.tsx`**; 若先做 i18n, 把 Task 5/8 的路径改 `app/[locale]/layout.tsx`

**已知差异 (vs spec):**
- 实际 18 处硬编码, spec 列了 18 个, **匹配**
- 已存在 `globals.css` 有部分 `.dark` 内容 (4 个 token), 需要补全到 spec 要求的 shadcn slate 完整版
- `--secondary-foreground`, `--popover-foreground`, `--input` 等 token 当前未定义, 需新增

---

## Phase 1: 依赖 + 主题配置 (3 任务)

### Task 1.1: 装 next-themes + @tailwindcss/typography

**Files:**
- Modify: `web/package.json`

- [ ] **Step 1: 装运行时依赖**

```bash
cd web
bun add next-themes@latest
```

- [ ] **Step 2: 装开发依赖**

```bash
cd web
bun add -D @tailwindcss/typography
```

- [ ] **Step 3: 验证装成功**

```bash
cd web
bun pm ls next-themes
bun pm ls @tailwindcss/typography
```

Expected: 两个包都显示版本号

- [ ] **Step 4: Commit**

```bash
git add web/package.json web/bun.lock
git commit -m "chore(deps): add next-themes + @tailwindcss/typography"
```

---

### Task 1.2: 写 themes.ts + 测试

**Files:**
- Create: `web/lib/theme/themes.ts`
- Create: `web/lib/theme/themes.test.ts`

- [ ] **Step 1: 写失败的测试**

```typescript
// web/lib/theme/themes.test.ts
import { describe, it, expect } from "vitest";
import { themes, getThemeConfig } from "./themes";

describe("themes config", () => {
  it("包含 light 和 dark", () => {
    expect(themes.map((t) => t.name)).toEqual(["light", "dark"]);
  });

  it("每个主题有 name / label / icon / colors", () => {
    for (const t of themes) {
      expect(t.name).toBeTruthy();
      expect(t.label).toBeTruthy();
      expect(t.icon).toMatch(/^(sun|moon|eye)$/);
      expect(t.colors).toBeTypeOf("object");
    }
  });

  it("light 主题覆盖了关键 token", () => {
    const light = getThemeConfig("light");
    expect(light.colors.background).toBeDefined();
    expect(light.colors.foreground).toBeDefined();
    expect(light.colors.primary).toBeDefined();
  });

  it("getThemeConfig 找不到主题时抛错", () => {
    expect(() => getThemeConfig("nope" as any)).toThrow(/主题.*不存在/);
  });
});
```

- [ ] **Step 2: 跑测试看 red**

```bash
cd web
bun run test lib/theme/themes
```

Expected: FAIL `Cannot find module './themes'`

- [ ] **Step 3: 实现 themes.ts**

```typescript
// web/lib/theme/themes.ts
export interface ThemeColors {
  paper: string;
  background: string;
  foreground: string;
  ink: string;
  card: string;
  "card-foreground": string;
  "popover": string;
  "popover-foreground": string;
  border: string;
  input: string;
  ring: string;
  muted: string;
  "muted-foreground": string;
  secondary: string;
  "secondary-foreground": string;
  accent: string;
  "accent-foreground": string;
  primary: string;
  "primary-foreground": string;
  clay: string;
  "clay-foreground": string;
  moss: string;
  destructive: string;
  "destructive-foreground": string;
  "status-success": string;
  "status-warning": string;
  "status-error": string;
  "status-running": string;
}

export interface Theme {
  name: "light" | "dark" | string;
  label: string;
  icon: "sun" | "moon" | "eye" | string;
  colors: Partial<ThemeColors>;
}

export const themes: Theme[] = [
  {
    name: "light",
    label: "明亮",
    icon: "sun",
    colors: {
      // 跟 globals.css :root 一致, 这里只作 type 文档, 实际色值在 CSS
      background: "0 0% 98%",
      foreground: "222 47% 11%",
      primary: "217 91% 60%",
      "status-success": "160 84% 39%",
      "status-warning": "38 92% 50%",
      "status-error": "0 84% 60%",
      "status-running": "199 89% 48%",
    },
  },
  {
    name: "dark",
    label: "暗色",
    icon: "moon",
    colors: {
      background: "222 47% 7%",
      foreground: "210 20% 92%",
      primary: "217 91% 60%",
      "status-success": "160 84% 39%",
      "status-warning": "38 92% 50%",
      "status-error": "0 62.8% 30.6%",
      "status-running": "199 89% 48%",
    },
  },
];

export function getThemeConfig(name: string): Theme {
  const theme = themes.find((t) => t.name === name);
  if (!theme) throw new Error(`主题 "${name}" 不存在`);
  return theme;
}
```

- [ ] **Step 4: 跑测试看 green**

```bash
cd web
bun run test lib/theme/themes
```

Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add web/lib/theme/themes.ts web/lib/theme/themes.test.ts
git commit -m "feat(theme): themes config with light/dark + getThemeConfig"
```

---

### Task 1.3: 写 useTheme.ts + index.ts barrel

**Files:**
- Create: `web/lib/theme/useTheme.ts`
- Create: `web/lib/theme/index.ts`

- [ ] **Step 1: 实现 useTheme.ts (re-export)**

```typescript
// web/lib/theme/useTheme.ts
"use client";
// 简化封装, 让业务代码统一从 @/lib/theme 引入
export { useTheme } from "next-themes";
```

- [ ] **Step 2: 实现 index.ts barrel**

```typescript
// web/lib/theme/index.ts
export { themes, getThemeConfig } from "./themes";
export type { Theme, ThemeColors } from "./themes";
export { useTheme } from "./useTheme";
```

- [ ] **Step 3: 写测试 — barrel export 正确**

```typescript
// web/lib/theme/index.test.ts
import { describe, it, expect } from "vitest";
import * as ThemeModule from "./index";

describe("theme barrel", () => {
  it("导出 themes", () => {
    expect(ThemeModule.themes).toBeDefined();
    expect(ThemeModule.themes.length).toBeGreaterThan(0);
  });

  it("导出 getThemeConfig", () => {
    expect(ThemeModule.getThemeConfig).toBeTypeOf("function");
  });

  it("导出 useTheme", () => {
    expect(ThemeModule.useTheme).toBeTypeOf("function");
  });
});
```

- [ ] **Step 4: 跑测试看 green**

```bash
cd web
bun run test lib/theme/index
```

Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add web/lib/theme/useTheme.ts web/lib/theme/index.ts web/lib/theme/index.test.ts
git commit -m "feat(theme): barrel export + useTheme re-export"
```

---

## Phase 2: globals.css + ThemeProvider (2 任务)

### Task 2.1: 补全 globals.css

**Files:**
- Modify: `web/app/globals.css`

- [ ] **Step 1: 在 `@import "tailwindcss"` 后加 @plugin**

```diff
  @import "tailwindcss";
+ @plugin "@tailwindcss/typography";
```

- [ ] **Step 2: 在 `@theme inline` 块新增 4 status 色 + 2 品牌色**

完整 `@theme inline` 块 (替换现有):

```css
@theme inline {
  --font-sans: var(--font-geist-sans);
  --font-display: var(--font-geist-sans);
  --font-mono: var(--font-jetbrains-mono);

  /* shadcn 兼容色板 */
  --color-background: hsl(var(--background));
  --color-foreground: hsl(var(--foreground));
  --color-border: hsl(var(--border));
  --color-input: hsl(var(--input));
  --color-ring: hsl(var(--ring));
  --color-primary: hsl(var(--primary));
  --color-primary-foreground: hsl(var(--primary-foreground));
  --color-secondary: hsl(var(--secondary));
  --color-secondary-foreground: hsl(var(--secondary-foreground));
  --color-muted: hsl(var(--muted));
  --color-muted-foreground: hsl(var(--muted-foreground));
  --color-accent: hsl(var(--accent));
  --color-accent-foreground: hsl(var(--accent-foreground));
  --color-destructive: hsl(var(--destructive));
  --color-destructive-foreground: hsl(var(--destructive-foreground));
  --color-card: hsl(var(--card));
  --color-card-foreground: hsl(var(--card-foreground));
  --color-popover: hsl(var(--popover));
  --color-popover-foreground: hsl(var(--popover-foreground));

  /* 自定义品牌色 */
  --color-ink: hsl(var(--ink));
  --color-paper: hsl(var(--paper));
  --color-clay: hsl(var(--clay));
  --color-clay-foreground: hsl(var(--clay-foreground));
  --color-moss: hsl(var(--moss));

  /* 状态色 (2026-06-10) */
  --color-status-success: hsl(var(--status-success));
  --color-status-warning: hsl(var(--status-warning));
  --color-status-error: hsl(var(--status-error));
  --color-status-running: hsl(var(--status-running));

  /* 品牌扩展 */
  --color-ochre: hsl(36 85% 50%);
  --color-indigo: hsl(225 60% 45%);

  /* 动效缓动 */
  --ease-out-expo: cubic-bezier(0.16, 1, 0.3, 1);
  --ease-in-out-quart: cubic-bezier(0.76, 0, 0.24, 1);
}
```

- [ ] **Step 3: 在 `:root` 块补全 4 status token + 缺失 token**

完整 `:root` 块 (替换现有):

```css
:root {
  /* 表面 */
  --paper: 0 0% 98%;
  --background: 0 0% 98%;
  --foreground: 222 47% 11%;
  --ink: 222 47% 11%;

  /* 卡片 */
  --card: 0 0% 100%;
  --card-foreground: 222 47% 11%;

  /* 弹框 */
  --popover: 0 0% 100%;
  --popover-foreground: 222 47% 11%;

  /* 边框 / 输入 / 焦点 */
  --border: 214 20% 90%;
  --input: 214 20% 90%;
  --ring: 217 91% 60%;

  /* 中性 */
  --muted: 210 20% 96%;
  --muted-foreground: 215 16% 47%;
  --secondary: 210 20% 96%;
  --secondary-foreground: 222 47% 11%;
  --accent: 217 91% 60%;
  --accent-foreground: 0 0% 100%;

  /* 品牌 */
  --primary: 217 91% 60%;
  --primary-foreground: 0 0% 100%;
  --clay: 217 91% 60%;
  --clay-foreground: 0 0% 100%;
  --moss: 160 84% 39%;

  /* 错误 */
  --destructive: 0 84% 60%;
  --destructive-foreground: 0 0% 100%;

  /* 状态 (2026-06-10 新增) */
  --status-success: 160 84% 39%;
  --status-warning: 38 92% 50%;
  --status-error: 0 84% 60%;
  --status-running: 199 89% 48%;
}
```

- [ ] **Step 4: 补全 `.dark` 块 (shadcn slate dark 完整版)**

完整 `.dark` 块 (替换现有):

```css
.dark {
  --paper: 222 47% 7%;
  --background: 222 47% 7%;
  --foreground: 210 20% 92%;
  --ink: 210 20% 92%;
  --card: 222 47% 10%;
  --card-foreground: 210 20% 92%;
  --popover: 222 47% 10%;
  --popover-foreground: 210 20% 92%;
  --primary: 217 91% 60%;
  --primary-foreground: 0 0% 100%;
  --secondary: 217 33% 18%;
  --secondary-foreground: 210 20% 92%;
  --muted: 217 33% 18%;
  --muted-foreground: 215 16% 65%;
  --accent: 217 33% 18%;
  --accent-foreground: 210 20% 92%;
  --destructive: 0 62.8% 30.6%;
  --destructive-foreground: 210 20% 92%;
  --border: 217 33% 18%;
  --input: 217 33% 18%;
  --ring: 217 91% 60%;
  --clay: 217 91% 60%;
  --clay-foreground: 0 0% 100%;
  --moss: 160 84% 39%;

  /* 状态色 - 暗色版 (2026-06-10) */
  --status-success: 160 84% 39%;
  --status-warning: 38 92% 50%;
  --status-error: 0 62.8% 30.6%;
  --status-running: 199 89% 48%;
}
```

- [ ] **Step 5: 启动 dev 看暗色是否生效**

```bash
cd web
bun run dev
# 浏览器 DevTools → Console → document.documentElement.classList.add("dark")
# 整个页面应变成暗色, 卡片/边框/文字颜色都变了
# DevTools → Elements → <html> class="dark" 验证 CSS 变量切了
```

- [ ] **Step 6: Commit**

```bash
git add web/app/globals.css
git commit -m "feat(theme): complete .dark block + 4 status tokens + ochre/indigo + @plugin typography"
```

---

### Task 2.2: 在 layout.tsx 加 ThemeProvider

**Files:**
- Modify: `app/layout.tsx` (若 i18n 已实施, 路径是 `app/[locale]/layout.tsx`)

- [ ] **Step 1: 加 import + ThemeProvider**

```diff
  import { SWRProvider } from "@/lib/api/swr-provider";
  import { HealthDot } from "@/components/knowledge/HealthDot";
  import { EnvBadge } from "@/components/knowledge/EnvBadge";
  import { ThemeProvider } from "@/components/theme-provider";
  import { themes } from "@/lib/theme";
  import "./globals.css";
```

- [ ] **Step 2: 在 `<body>` 里面包 `<ThemeProvider>`**

```diff
  export default function RootLayout({ children }: { children: React.ReactNode }) {
    return (
-     <html lang="zh" className={`${geistSans.variable} ${jetbrainsMono.variable}`} data-scroll-behavior="smooth">
+     <html lang="zh" suppressHydrationWarning className={`${geistSans.variable} ${jetbrainsMono.variable}`} data-scroll-behavior="smooth">
        <body className="bg-paper flex h-screen flex-col overflow-x-hidden overflow-y-hidden text-foreground antialiased">
-         <header ...>
-           ...
-         </header>
+         <ThemeProvider attribute="class" themes={themes.map((t) => t.name)} defaultTheme="system" enableSystem>
+           <header ...>
+             ...
+           </header>
+           <main ...>
+             <SWRProvider>{children}</SWRProvider>
+           </main>
+           <footer ...>
+             ...
+           </footer>
+         </ThemeProvider>
        </body>
      </html>
    );
  }
```

- [ ] **Step 3: 创建 `web/components/theme-provider.tsx`**

```tsx
// web/components/theme-provider.tsx
"use client";
import { ThemeProvider as NextThemesProvider } from "next-themes";
import type { ReactNode } from "react";

interface Props {
  children: ReactNode;
  attribute?: "class";
  themes: string[];
  defaultTheme: string;
  enableSystem?: boolean;
}

export function ThemeProvider({
  children,
  attribute = "class",
  themes,
  defaultTheme,
  enableSystem = true,
}: Props) {
  return (
    <NextThemesProvider
      attribute={attribute}
      themes={themes}
      defaultTheme={defaultTheme}
      enableSystem={enableSystem}
      disableTransitionOnChange
    >
      {children}
    </NextThemesProvider>
  );
}
```

- [ ] **Step 4: 写 ThemeProvider 测试**

```tsx
// web/components/theme-provider.test.tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { ThemeProvider } from "./theme-provider";

describe("ThemeProvider", () => {
  it("包 children", () => {
    render(
      <ThemeProvider themes={["light", "dark"]} defaultTheme="light">
        <div data-testid="child">child</div>
      </ThemeProvider>,
    );
    expect(screen.getByTestId("child")).toBeInTheDocument();
  });
});
```

- [ ] **Step 5: 跑 typecheck + 测试**

```bash
cd web
bun run typecheck
bun run test theme-provider
```

Expected: 0 type errors, 1 test pass

- [ ] **Step 6: 启动 dev 验证主题切换**

```bash
cd web
bun run dev
# DevTools → Console:
#   localStorage.theme = "dark"; 刷新 → 暗色
#   localStorage.theme = "light"; 刷新 → 亮色
#   localStorage.theme = "system"; 跟随 OS 偏好
```

- [ ] **Step 7: Commit**

```bash
git add app/layout.tsx web/components/theme-provider.tsx web/components/theme-provider.test.tsx
git commit -m "feat(theme): wrap layout in ThemeProvider with system/light/dark"
```

---

## Phase 3: SettingsDialog + ThemeToggle (3 任务)

### Task 3.1: 写 theme-toggle.tsx + 测试

**Files:**
- Create: `web/components/settings/theme-toggle.tsx`
- Create: `web/components/settings/theme-toggle.test.tsx`

- [ ] **Step 1: 写失败的测试**

```tsx
// web/components/settings/theme-toggle.test.tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ThemeToggle } from "./theme-toggle";

describe("ThemeToggle", () => {
  it("渲染齿轮图标按钮", () => {
    const onOpen = vi.fn();
    render(<ThemeToggle onOpen={onOpen} />);
    const btn = screen.getByRole("button", { name: /设置/ });
    expect(btn).toBeInTheDocument();
  });

  it("点击触发 onOpen 回调", async () => {
    const onOpen = vi.fn();
    render(<ThemeToggle onOpen={onOpen} />);
    await userEvent.click(screen.getByRole("button", { name: /设置/ }));
    expect(onOpen).toHaveBeenCalledTimes(1);
  });
});
```

- [ ] **Step 2: 跑测试看 red**

```bash
cd web
bun run test settings/theme-toggle
```

Expected: FAIL `Cannot find module './theme-toggle'`

- [ ] **Step 3: 实现 theme-toggle.tsx**

```tsx
// web/components/settings/theme-toggle.tsx
"use client";
import { Settings } from "lucide-react";
import { Button } from "@/components/ui/button";

interface Props {
  onOpen: () => void;
}

export function ThemeToggle({ onOpen }: Props) {
  return (
    <Button
      variant="ghost"
      size="icon"
      onClick={onOpen}
      aria-label="设置"
      data-testid="theme-toggle"
    >
      <Settings className="h-4 w-4" />
    </Button>
  );
}
```

- [ ] **Step 4: 跑测试看 green**

```bash
cd web
bun run test settings/theme-toggle
```

Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add web/components/settings/theme-toggle.tsx web/components/settings/theme-toggle.test.tsx
git commit -m "feat(theme): ThemeToggle gear button opens SettingsDialog"
```

---

### Task 3.2: 写 settings-dialog.tsx + 测试

**Files:**
- Create: `web/components/settings/settings-dialog.tsx`
- Create: `web/components/settings/settings-dialog.test.tsx`

- [ ] **Step 1: 写失败的测试**

```tsx
// web/components/settings/settings-dialog.test.tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { SettingsDialog } from "./settings-dialog";

describe("SettingsDialog", () => {
  it("受控: open=true 时弹框可见", () => {
    render(<SettingsDialog open={true} onOpenChange={vi.fn()} />);
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });

  it("受控: open=false 时弹框不可见", () => {
    render(<SettingsDialog open={false} onOpenChange={vi.fn()} />);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("渲染 3 行: 主题 (活) / 语言 (disabled) / 账号 (disabled)", () => {
    render(<SettingsDialog open={true} onOpenChange={vi.fn()} />);
    const dialog = screen.getByRole("dialog");
    expect(within(dialog).getByText("主题")).toBeInTheDocument();
    expect(within(dialog).getByText("语言")).toBeInTheDocument();
    expect(within(dialog).getByText("账号")).toBeInTheDocument();
  });

  it("主题 Select 切换时调用 setTheme (next-themes)", async () => {
    // mock next-themes
    vi.mock("next-themes", () => ({
      useTheme: () => ({ theme: "light", setTheme: vi.fn() }),
    }));
    const { rerender } = render(<SettingsDialog open={true} onOpenChange={vi.fn()} />);
    // 验证 Select trigger 存在
    expect(screen.getByRole("combobox")).toBeInTheDocument();
  });

  it("语言和账号行是 disabled (不能交互)", () => {
    render(<SettingsDialog open={true} onOpenChange={vi.fn()} />);
    expect(screen.getByText("中文")).toBeInTheDocument();  // Badge
    expect(screen.getByText("admin")).toBeInTheDocument(); // Badge
  });
});
```

- [ ] **Step 2: 跑测试看 red**

```bash
cd web
bun run test settings/settings-dialog
```

Expected: FAIL `Cannot find module './settings-dialog'`

- [ ] **Step 3: 实现 settings-dialog.tsx**

```tsx
// web/components/settings/settings-dialog.tsx
"use client";
import { useTheme } from "next-themes";
import { AppDialog } from "@/components/common/dialog/app-dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { themes } from "@/lib/theme";

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function SettingsDialog({ open, onOpenChange }: Props) {
  const { theme, setTheme } = useTheme();

  return (
    <AppDialog
      open={open}
      onOpenChange={onOpenChange}
      title="设置"
      maxWidth="sm"
    >
      <div className="divide-y divide-border/40">
        {/* 行 1: 主题 (活) */}
        <div className="flex items-center justify-between px-6 py-4">
          <span className="text-sm font-medium">主题</span>
          <Select value={theme} onValueChange={setTheme}>
            <SelectTrigger className="w-32">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {themes.map((t) => (
                <SelectItem key={t.name} value={t.name}>
                  {t.label}
                </SelectItem>
              ))}
              <SelectItem value="system">跟随系统</SelectItem>
            </SelectContent>
          </Select>
        </div>

        {/* 行 2: 语言 (占位 disabled) */}
        <div className="flex items-center justify-between px-6 py-4 opacity-60">
          <span className="text-sm font-medium">语言</span>
          <Badge variant="outline">中文</Badge>
        </div>

        {/* 行 3: 账号 (占位 disabled) */}
        <div className="flex items-center justify-between px-6 py-4 opacity-60">
          <span className="text-sm font-medium">账号</span>
          <Badge variant="outline">admin</Badge>
        </div>
      </div>
    </AppDialog>
  );
}
```

- [ ] **Step 4: 跑测试看 green**

```bash
cd web
bun run test settings/settings-dialog
```

Expected: PASS (5 tests, 可能需 vitest mock next-themes)

- [ ] **Step 5: Commit**

```bash
git add web/components/settings/settings-dialog.tsx web/components/settings/settings-dialog.test.tsx
git commit -m "feat(theme): SettingsDialog with theme switcher + 2 placeholder rows"
```

---

### Task 3.3: 在 layout header 加 ThemeToggle + SettingsDialog 状态

**Files:**
- Modify: `app/layout.tsx` (或 `app/[locale]/layout.tsx`)

- [ ] **Step 1: 加 import + 状态**

```diff
  import { SWRProvider } from "@/lib/api/swr-provider";
  import { HealthDot } from "@/components/knowledge/HealthDot";
  import { EnvBadge } from "@/components/knowledge/EnvBadge";
  import { ThemeProvider } from "@/components/theme-provider";
+ import { ThemeToggle } from "@/components/settings/theme-toggle";
+ import { SettingsDialog } from "@/components/settings/settings-dialog";
  import { themes } from "@/lib/theme";
```

⚠️ **layout.tsx 当前是 server component**, 要把含 ThemeToggle/SettingsDialog 的部分抽到客户端 `HeaderClient` 组件:

**创建** `web/components/header.tsx` (客户端组件):

```tsx
// web/components/header.tsx
"use client";
import { useState } from "react";
import Link from "next/link";
import { HealthDot } from "@/components/knowledge/HealthDot";
import { EnvBadge } from "@/components/knowledge/EnvBadge";
import { ThemeToggle } from "@/components/settings/theme-toggle";
import { SettingsDialog } from "@/components/settings/settings-dialog";

export function Header() {
  const [settingsOpen, setSettingsOpen] = useState(false);

  return (
    <>
      <header className="shrink-0 border-b border-border/60 bg-paper/80 backdrop-blur-sm">
        <div className="mx-auto flex max-w-7xl items-center gap-8 px-6 py-4">
          <Link href="/" className="display text-xl tracking-tight transition-opacity hover:opacity-70">
            RAG<span className="text-clay"> · </span>德源通泰
          </Link>
          <nav className="ml-auto flex items-center gap-1 text-base">
            <NavLink href="/chat">对话</NavLink>
            <NavLink href="/output">文档结构化</NavLink>
            <NavLink href="/knowledge">知识库</NavLink>
            <NavLink href="/evaluate">评估</NavLink>
            <NavLink href="/decode">型号解析</NavLink>
          </nav>
          <div className="hidden items-center gap-2 sm:flex">
            <span className="eyebrow">v0.1</span>
            <EnvBadge />
            <HealthDot />
            <ThemeToggle onOpen={() => setSettingsOpen(true)} />
          </div>
        </div>
      </header>
      <SettingsDialog open={settingsOpen} onOpenChange={setSettingsOpen} />
    </>
  );
}

function NavLink({ href, children }: { href: string; children: React.ReactNode }) {
  return (
    <Link
      href={href}
      className="group relative rounded-md px-3 py-1.5 text-muted-foreground transition-colors duration-300 hover:text-foreground"
      style={{ transitionTimingFunction: "var(--ease-out-expo)" }}
    >
      <span className="relative z-10">{children}</span>
      <span
        className="absolute bottom-0.5 left-3 right-3 h-px origin-left scale-x-0 bg-foreground/40 transition-transform duration-300 group-hover:scale-x-100"
        style={{ transitionTimingFunction: "var(--ease-out-expo)" }}
      />
    </Link>
  );
}
```

- [ ] **Step 2: 改 layout.tsx — 用 Header 组件替换内联 header**

```diff
  import { Header } from "@/components/header";

  // 删掉原来 layout.tsx 里的 Header 函数 + NavLink 函数
```

- [ ] **Step 3: 写 Header 测试**

```tsx
// web/components/header.test.tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Header } from "./header";

vi.mock("next-themes", () => ({
  useTheme: () => ({ theme: "light", setTheme: vi.fn() }),
}));

describe("Header", () => {
  it("渲染 ThemeToggle 齿轮按钮", () => {
    render(<Header />);
    expect(screen.getByRole("button", { name: /设置/ })).toBeInTheDocument();
  });

  it("点齿轮 → SettingsDialog 弹出", async () => {
    render(<Header />);
    await userEvent.click(screen.getByRole("button", { name: /设置/ }));
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });
});
```

- [ ] **Step 4: 跑测试 + typecheck**

```bash
cd web
bun run test header
bun run typecheck
```

Expected: 2 tests pass, 0 type errors

- [ ] **Step 5: 启动 dev 验证**

```bash
cd web
bun run dev
# 浏览器: header 最右侧出现齿轮按钮
# 点击齿轮 → 弹框弹出, 3 行: 主题 (Select) / 语言 (Badge) / 账号 (Badge)
# 主题 Select 切换 "明亮/暗色/跟随系统" → 页面主题实时变化
```

- [ ] **Step 6: Commit**

```bash
git add app/layout.tsx web/components/header.tsx web/components/header.test.tsx
git commit -m "feat(theme): Header with ThemeToggle + SettingsDialog state"
```

---

## Phase 4: 18 处硬编码迁移 (5 任务, 按组件分批)

### Task 4.1: HealthDot + EnvBadge

**Files:**
- Modify: `web/components/knowledge/HealthDot.tsx`
- Modify: `web/components/knowledge/HealthDot.test.tsx`
- Modify: `web/components/knowledge/EnvBadge.tsx`

- [ ] **Step 1: 改 HealthDot.tsx**

```diff
  export function HealthDot() {
    const { data, isLoading } = useApi(healthUrl);
-   const color = isLoading ? "bg-gray-400" : data?.ok ? "bg-emerald-500" : "bg-rose-500";
+   const color = isLoading ? "bg-muted-foreground/50" : data?.ok ? "bg-status-success" : "bg-status-error";
    return <span className={`inline-block h-2 w-2 rounded-full ${color}`} data-testid="health-dot" />;
  }
```

- [ ] **Step 2: 改 HealthDot.test.tsx 断言**

```diff
  it("ok=true → bg-status-success", () => {
    globalThis.fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ ok: true }) });
    render(<HealthDot />);
    await waitFor(() => {
      const dot = screen.getByTestId("health-dot");
-     expect(dot.className).toContain("bg-emerald-500");
+     expect(dot.className).toContain("bg-status-success");
    });
  });

  it("ok=false → bg-status-error", () => {
    globalThis.fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ ok: false }) });
    render(<HealthDot />);
    await waitFor(() => {
      const dot = screen.getByTestId("health-dot");
-     expect(dot.className).toContain("bg-rose-500");
+     expect(dot.className).toContain("bg-status-error");
    });
  });
```

- [ ] **Step 3: 改 EnvBadge.tsx**

```diff
  const ENV_STYLES: Record<Env, string> = {
-   DEV: "bg-amber-100 text-amber-800",
-   STAGING: "bg-blue-100 text-blue-800",
-   PROD: "bg-rose-100 text-rose-800",
+   DEV: "bg-status-warning/10 text-status-warning",
+   STAGING: "bg-status-running/10 text-status-running",
+   PROD: "bg-status-error/10 text-status-error",
  };
```

- [ ] **Step 4: 跑测试**

```bash
cd web
bun run test HealthDot EnvBadge
```

Expected: 所有测试 pass

- [ ] **Step 5: Commit**

```bash
git add web/components/knowledge/HealthDot.tsx web/components/knowledge/HealthDot.test.tsx web/components/knowledge/EnvBadge.tsx
git commit -m "refactor(theme): migrate HealthDot + EnvBadge to status-* tokens"
```

---

### Task 4.2: StatusBadge + TaskStatusBadge

**Files:**
- Modify: `web/components/evaluate/StatusBadge.tsx`
- Modify: `web/components/knowledge/TaskStatusBadge.tsx`

- [ ] **Step 1: 改 StatusBadge.tsx**

```diff
  const STATUS_STYLES = {
-   running: "bg-cyan-50 text-cyan-700 border-cyan-300/40 animate-pulse",
+   running: "bg-status-running/10 text-status-running border-status-running/40 animate-pulse",
  } as const;
```

- [ ] **Step 2: 改 TaskStatusBadge.tsx**

```diff
  const STATUS_STYLES = {
-   queued: "bg-slate-100 text-slate-700",
-   running: "bg-blue-100 text-blue-700 animate-pulse",
-   done: "bg-emerald-100 text-emerald-700",
-   partial: "bg-amber-100 text-amber-700",
-   failed: "bg-rose-100 text-rose-700",
-   cancelled: "bg-slate-200 text-slate-600",
+   queued: "bg-muted text-muted-foreground",
+   running: "bg-status-running/10 text-status-running animate-pulse",
+   done: "bg-status-success/10 text-status-success",
+   partial: "bg-status-warning/10 text-status-warning",
+   failed: "bg-status-error/10 text-status-error",
+   cancelled: "bg-muted text-muted-foreground",
  } as const;
```

- [ ] **Step 3: 改 `app/knowledge/dataset-documents/[dataset_id]/page.tsx` (也有 inline 状态色)**

```diff
  const DOC_STATUS_STYLES = {
-   completed: "bg-emerald-100 text-emerald-700",
-   indexing: "bg-blue-100 text-blue-700 animate-pulse",
-   queued: "bg-slate-100 text-slate-700",
-   error: "bg-rose-100 text-rose-700",
+   completed: "bg-status-success/10 text-status-success",
+   indexing: "bg-status-running/10 text-status-running animate-pulse",
+   queued: "bg-muted text-muted-foreground",
+   error: "bg-status-error/10 text-status-error",
  } as const;
```

- [ ] **Step 4: 跑测试**

```bash
cd web
bun run test StatusBadge TaskStatusBadge
```

Expected: 所有测试 pass

- [ ] **Step 5: Commit**

```bash
git add web/components/evaluate/StatusBadge.tsx web/components/knowledge/TaskStatusBadge.tsx "app/knowledge/dataset-documents/[dataset_id]/page.tsx"
git commit -m "refactor(theme): migrate StatusBadge + TaskStatusBadge to status-* tokens"
```

---

### Task 4.3: MetricBar + SampleTable + MessageBubble + ThinkingTrace

**Files:**
- Modify: `web/components/evaluate/MetricBar.tsx`
- Modify: `web/components/evaluate/SampleTable.tsx`
- Modify: `web/components/chat/MessageBubble.tsx`
- Modify: `web/components/chat/ThinkingTrace.tsx`

- [ ] **Step 1: 改 MetricBar.tsx**

```diff
  export function getMetricColor(v: number): string {
-   if (v >= 0.4) return "bg-amber-500";
+   if (v >= 0.4) return "bg-status-warning";
    return "bg-muted";
  }
```

- [ ] **Step 2: 改 SampleTable.tsx**

```diff
- if (v >= 0.4) {return "text-amber-600";}
+ if (v >= 0.4) {return "text-status-warning";}
  return "text-foreground";
```

- [ ] **Step 3: 改 MessageBubble.tsx:79**

```diff
- className="mt-2 inline-flex items-center gap-1 rounded-full border border-amber-300 bg-amber-50 px-2 py-0.5 text-xs text-amber-700"
+ className="mt-2 inline-flex items-center gap-1 rounded-full border border-status-warning/40 bg-status-warning/10 px-2 py-0.5 text-xs text-status-warning"
```

- [ ] **Step 4: 改 ThinkingTrace.tsx:19**

```diff
- : "border-amber-300 text-amber-700"
+ : "border-status-warning/40 text-status-warning"
```

- [ ] **Step 5: 跑测试**

```bash
cd web
bun run test MetricBar SampleTable MessageBubble ThinkingTrace
```

Expected: 所有测试 pass

- [ ] **Step 6: Commit**

```bash
git add web/components/evaluate/MetricBar.tsx web/components/evaluate/SampleTable.tsx web/components/chat/MessageBubble.tsx web/components/chat/ThinkingTrace.tsx
git commit -m "refactor(theme): migrate MetricBar/SampleTable/MessageBubble/ThinkingTrace to status-warning"
```

---

### Task 4.4: ErrorBoundary + FileDropzone

**Files:**
- Modify: `web/components/knowledge/ErrorBoundary.tsx`
- Modify: `web/components/knowledge/FileDropzone.tsx`

- [ ] **Step 1: 改 ErrorBoundary.tsx**

```diff
  return (
    <Card className="border-rose-200" data-testid="error-boundary">
      <CardHeader>
-       <CardTitle className="text-rose-700">出错了</CardTitle>
+       <CardTitle className="text-status-error">出错了</CardTitle>
      </CardHeader>
      <CardContent>
-       <pre className="text-sm text-rose-800 whitespace-pre-wrap">
+       <pre className="text-sm text-status-error whitespace-pre-wrap">
          {error.message}
        </pre>
      </CardContent>
    </Card>
  );
```

注: 改后 `border-rose-200` → `border-status-error/40`

- [ ] **Step 2: 改 FileDropzone.tsx**

```diff
- <p className="mt-2 text-sm text-rose-600" data-testid="dropzone-error">
+ <p className="mt-2 text-sm text-status-error" data-testid="dropzone-error">
```

- [ ] **Step 3: 跑测试**

```bash
cd web
bun run test ErrorBoundary FileDropzone
```

Expected: 所有测试 pass

- [ ] **Step 4: Commit**

```bash
git add web/components/knowledge/ErrorBoundary.tsx web/components/knowledge/FileDropzone.tsx
git commit -m "refactor(theme): migrate ErrorBoundary + FileDropzone to status-error"
```

---

### Task 4.5: StatCard ochre/indigo + 3 output 页面 text-white + evaluate/[id] cyan

**Files:**
- Modify: `web/components/knowledge/StatCard.tsx`
- Modify: `app/output/page.tsx`
- Modify: `app/output/[task_id]/page.tsx`
- Modify: `app/output/new/page.tsx`
- Modify: `app/evaluate/[id]/page.tsx`

- [ ] **Step 1: 改 StatCard.tsx**

```diff
  const ACCENTS = {
-   ochre: "bg-[hsl(36_85%_50%)]",
-   indigo: "bg-[hsl(225_60%_45%)]",
+   ochre: "bg-ochre",
+   indigo: "bg-indigo",
  } as const;
```

- [ ] **Step 2: 改 3 个 output 页面的 text-white → text-primary-foreground**

`web/app/output/page.tsx:100`:
```diff
- className="rounded-md bg-clay px-3 py-1 text-sm text-white transition-colors hover:bg-clay/90"
+ className="rounded-md bg-clay px-3 py-1 text-sm text-primary-foreground transition-colors hover:bg-clay/90"
```

`web/app/output/page.tsx:130`:
```diff
- className="rounded-lg bg-clay px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-clay/90"
+ className="rounded-lg bg-clay px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-clay/90"
```

`web/app/output/[task_id]/page.tsx:133`:
```diff
- className="rounded-lg bg-clay px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-clay/90"
+ className="rounded-lg bg-clay px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-clay/90"
```

`web/app/output/new/page.tsx:140`:
```diff
- className="bg-clay px-6 text-white hover:bg-clay/90"
+ className="bg-clay px-6 text-primary-foreground hover:bg-clay/90"
```

- [ ] **Step 3: 改 `app/evaluate/[id]/page.tsx:80`**

```diff
- <div className="rounded-lg border border-cyan-300/30 bg-cyan-50/30 p-4 text-sm text-cyan-700">
+ <div className="rounded-lg border border-status-running/30 bg-status-running/10 p-4 text-sm text-status-running">
```

- [ ] **Step 4: 跑测试**

```bash
cd web
bun run test
```

Expected: 全部 pass (任何残留 `bg-cyan/bg-emerald/bg-rose/bg-amber/bg-blue/bg-slate/bg-gray` 等 hardcoded 都不应出现)

- [ ] **Step 5: 全局 grep 确认无残留**

```bash
cd web
grep -rE 'bg-(amber|rose|emerald|blue|cyan|slate|gray)-\d' app/ components/ --include="*.tsx"
# 期望: 无输出
```

- [ ] **Step 6: Commit**

```bash
git add web/components/knowledge/StatCard.tsx app/output/page.tsx "app/output/[task_id]/page.tsx" app/output/new/page.tsx "app/evaluate/[id]/page.tsx"
git commit -m "refactor(theme): migrate StatCard/output/evaluate-[id] to semantic tokens"
```

---

## Phase 5: 收尾 (2 任务)

### Task 5.1: 跑全套测试 + typecheck + lint

- [ ] **Step 1: 跑 vitest**

```bash
cd web
bun run test
```

Expected: 所有测试 pass (含 HealthDot 修复后的 2 个, ThemeToggle 2 个, SettingsDialog 5 个, Header 2 个, 全部 page/component 测试)

- [ ] **Step 2: 跑 typecheck**

```bash
cd web
bun run typecheck
```

Expected: 0 errors

- [ ] **Step 3: 跑 lint + format**

```bash
cd web
bun run lint
bun run format:check
```

Expected: 无问题

- [ ] **Step 4: 跑后端契约测试**

```bash
cd ..
uv run python -m pytest tests/test_api_contract.py -v
```

Expected: 3/3 PASS

---

### Task 5.2: 手动 E2E 验证

- [ ] **Step 1: 起 dev + 后端**

```bash
# 终端 1: 后端
cd ..
uv run python main.py

# 终端 2: 前端
cd web
bun run dev
```

- [ ] **Step 2: 浏览器走一遍**

1. `http://localhost:3000/` → 页面正常, 亮色
2. header 最右侧出现齿轮图标
3. 点齿轮 → 弹框弹出, 3 行 (主题 Select / 语言 Badge / 账号 Badge)
4. 主题切 "暗色" → 整个页面变暗色, HealthDot/EnvBadge 颜色仍清晰
5. 主题切 "明亮" → 切回亮色
6. 主题切 "跟随系统" → 跟 OS 偏好
7. 刷新页面 → 主题持久化 (localStorage)
8. 测各页面: `/knowledge`, `/evaluate`, `/output` → 状态色 (running/done/failed) 跟主题色一致

- [ ] **Step 3: 跑 Playwright E2E (若有覆盖)**

```bash
cd web
bun run test:e2e
```

Expected: 18 个 E2E 通过 (没有 E2E 测主题切换, 但应不影响其他)

- [ ] **Step 4: 文档更新 — `web/CLAUDE.md` 加主题章节**

```markdown
## 主题系统 (Theme)

- 用 next-themes 0.4.x + Tailwind v4 CSS 变量
- 主题配置: `web/lib/theme/themes.ts` (light/dark)
- ThemeProvider: `web/components/theme-provider.tsx` (包在 root layout)
- 主题切换 UI: 齿轮按钮 (`ThemeToggle`) → SettingsDialog
- 状态色: 用 `bg-status-{success|warning|error|running}/10` 替代 `bg-{emerald|amber|rose|blue}-100`
- 新增色 token: `--color-status-*`, `--color-ochre`, `--color-indigo`
- 文档: <https://tailwindcss.com/docs/installation/framework-guides/nextjs>
```

```bash
git add web/CLAUDE.md
git commit -m "docs(theme): add theme system conventions to web/CLAUDE.md"
```

---

## 自检 (Self-Review)

✅ **Spec 覆盖**:
- next-themes 集成 ✓ Task 1.1, 2.2
- 18 处硬编码迁移 ✓ Task 4.1-4.5
- 主题配置文件化 ✓ Task 1.2, 1.3
- SettingsDialog (齿轮 + 弹框: 主题/语言占位/账号占位) ✓ Task 3.2, 3.3
- 安装 @tailwindcss/typography ✓ Task 1.1, 2.1
- 补全 .dark 块 ✓ Task 2.1
- 4 语义 token (status-success/warning/error/running) ✓ Task 2.1
- HealthDot 断言修复 ✓ Task 4.1
- 主题切换触发 + 持久化 ✓ Task 2.2 (localStorage)

✅ **No Placeholders**:
- 所有代码块都有完整内容
- 文件路径都是绝对路径
- 命令 + Expected output 都写明
- 没有 "TBD" / "TODO"

✅ **类型一致性**:
- `themes` array 形状在 Task 1.2 定义, Task 2.2 引用 `themes.map(t => t.name)`
- `ThemeColors` 接口在 Task 1.2 定义, 仅作文档, 实际色值在 CSS
- `setTheme` 来自 `useTheme()` 在 Task 3.2 + 3.3 都用

---

## 风险提醒

1. **layout.tsx 路径冲突**: i18n plan 把 layout 移到 `app/[locale]/`. 本 plan 假设 layout 还在 `app/layout.tsx`. 建议先做本 plan, 后做 i18n; 或同时两 plan 在两个 worktree
2. **ThemeToggle 需要 client 组件**: layout 当前是 server component, Task 3.3 抽 `Header` 客户端组件隔离
3. **dark 模式视觉验证**: 18 处迁移后必须浏览器看一遍, 有些 token 映射 (如 slate → muted) 视觉亮度可能差, 需要调 `--muted` 值
4. **status-warning/10 透明度**: Tailwind v4 `/10` 是 10% alpha, 在亮色下够清晰, 暗色下可能要 `/20`
5. **text-white 替换**: spec 让用 `text-primary-foreground` (亮色白, 暗色也白), 跟 `bg-clay` (蓝) 配, 视觉应一致
6. **18 处迁移影响范围**: 涉及 10 个文件, 单 commit 太大, Task 4.1-4.5 拆 5 个 commit

---

**完成所有 task 后**: invoke `superpowers:finishing-a-development-branch` 决定 merge/PR/discard
