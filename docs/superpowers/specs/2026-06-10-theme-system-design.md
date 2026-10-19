# 主题系统设计 (白/夜 + 可扩展)

> 2026-06-10 · Brainstorming → Spec
> Status: 待用户 review

## 1. 目标

加 next-themes 运行时主题切换, 补全 `.dark` CSS 块 (shadcn slate dark), 18 处硬编码颜色 token 化, 主题配置文件化 (`web/lib/theme/themes.ts`), SettingsDialog (齿轮图标 + 弹框: 主题切换 + 语言占位 + 用户信息占位), 安装 @tailwindcss/typography.

不在范围:
- 语言切换功能 (Spec D)
- 用户信息功能 (后续 spec)
- 主题配置后端下发 (后续)

## 2. 架构

```
web/lib/theme/
├── themes.ts           # 主题配置: Theme[] + type + getThemeConfig()
├── useTheme.ts         # re-export next-themes useTheme
└── index.ts            # barrel export

web/app/layout.tsx
├── <ThemeProvider attribute="class" themes={themes.map(t => t.name)} defaultTheme="system">
│   └── ...
└── header: <ThemeToggle />  (齿轮图标, 最右侧, HealthDot 右边)

web/components/settings/
├── settings-dialog.tsx      # <SettingsDialog open onOpenChange>
├── settings-dialog.test.tsx
└── theme-toggle.tsx         # 齿轮按钮
└── theme-toggle.test.tsx
```

## 3. 主题配置文件

```ts
// web/lib/theme/themes.ts
export interface ThemeColors {
  paper: string; background: string; foreground: string; ink: string;
  card: string; "card-foreground": string;
  border: string; ring: string;
  muted: string; "muted-foreground": string;
  secondary: string; "secondary-foreground": string;
  accent: string; "accent-foreground": string;
  primary: string; "primary-foreground": string;
  clay: string; "clay-foreground": string; moss: string;
  destructive: string; "destructive-foreground": string;
  "status-success": string; "status-warning": string;
  "status-error": string; "status-running": string;
}

export interface Theme {
  name: string;           // "light" | "dark" | "sepia" | ...
  label: string;          // "明亮" | "暗色" | "护眼" | ...
  icon: string;           // "sun" | "moon" | "eye" | ...
  colors: Partial<ThemeColors>;  // 只覆盖差异
}

export const themes: Theme[] = [
  { name: "light", label: "明亮", icon: "sun",
    colors: { /* 当前 :root 值原样搬过来 */ } },
  { name: "dark", label: "暗色", icon: "moon",
    colors: { /* shadcn slate dark 值 */ } },
];
```

## 4. CSS 改动 (`globals.css`)

### 4.1 补全 `.dark` 块 (shadcn slate dark)

```css
.dark {
  --background: 222.2 84% 4.9%;
  --foreground: 210 40% 98%;
  --card: 222.2 84% 4.9%;
  --card-foreground: 210 40% 98%;
  --popover: 222.2 84% 4.9%;
  --popover-foreground: 210 40% 98%;
  --primary: 217.2 91.2% 59.8%;
  --primary-foreground: 222.2 47.4% 11.2%;
  --secondary: 217.2 32.6% 17.5%;
  --secondary-foreground: 210 40% 98%;
  --muted: 217.2 32.6% 17.5%;
  --muted-foreground: 215 20.2% 65.1%;
  --accent: 217.2 32.6% 17.5%;
  --accent-foreground: 210 40% 98%;
  --destructive: 0 62.8% 30.6%;
  --destructive-foreground: 210 40% 98%;
  --border: 217.2 32.6% 17.5%;
  --input: 217.2 32.6% 17.5%;
  --ring: 224.3 76.3% 48%;
  --ink: 210 40% 98%;
  --paper: 222.2 84% 4.9%;
  --clay: 217.2 91.2% 59.8%;
  --clay-foreground: 222.2 47.4% 11.2%;
  --moss: 160 84% 39%;
  --status-success: 160 84% 39%;
  --status-warning: 38 92% 50%;
  --status-error: 0 84.2% 60.2%;
  --status-running: 199 89% 48%;
}
```

### 4.2 `:root` 新增 4 语义 token

```css
:root {
  /* ... existing ... */
  --status-success: 160 84% 39%;
  --status-warning: 38 92% 50%;
  --status-error: 0 84.2% 60.2%;
  --status-running: 199 89% 48%;
}
```

### 4.3 `@theme inline` 新增 4 色 + 2 品牌扩展

```css
--color-status-success: hsl(var(--status-success));
--color-status-warning: hsl(var(--status-warning));
--color-status-error: hsl(var(--status-error));
--color-status-running: hsl(var(--status-running));
--color-ochre: hsl(36 85% 50%);
--color-indigo: hsl(225 60% 45%);
```

### 4.4 安装 @tailwindcss/typography

```css
@plugin "@tailwindcss/typography";
```

## 5. SettingsDialog

```tsx
<SettingsDialog open={open} onOpenChange={setOpen}>
  {/* 行 1: 主题 (活) */}
  <SettingRow label="主题">
    <Select value={theme} onValueChange={setTheme}>
      <SelectItem value="light">明亮</SelectItem>
      <SelectItem value="dark">暗色</SelectItem>
      <SelectItem value="system">跟随系统</SelectItem>
    </Select>
  </SettingRow>

  {/* 行 2: 语言 (占位 disabled) */}
  <SettingRow label="语言" disabled>
    <Badge variant="outline">中文</Badge>
  </SettingRow>

  {/* 行 3: 用户信息 (占位 disabled) */}
  <SettingRow label="账号" disabled>
    <Badge variant="outline">admin</Badge>
  </SettingRow>
</SettingsDialog>
```

## 6. ThemeToggle (齿轮图标)

```tsx
// web/components/settings/theme-toggle.tsx
<Button variant="ghost" size="icon" onClick={() => setSettingsOpen(true)}>
  <Settings className="h-4 w-4" />
</Button>
```

放 `app/layout.tsx` header 最右侧, HealthDot 右边.

## 7. 安装依赖

```bash
bun add next-themes
bun add -D @tailwindcss/typography
```

## 8. 18 处硬编码颜色迁移

全部换成新语义 token:

| 原硬编码 | 换成 | 涉及文件 |
|---|---|---|
| `bg-amber-500/100`, `text-amber-600/700/800`, `border-amber-300` | `bg-status-warning`, `text-status-warning`, `border-status-warning` | MetricBar, SampleTable, EnvBadge, TaskStatusBadge, MessageBubble, ThinkingTrace |
| `bg-rose-500/100`, `text-rose-500/600/700/800`, `border-rose-200/300` | `bg-status-error`, `text-status-error`, `border-status-error` | HealthDot, EnvBadge, TaskStatusBadge, ErrorBoundary, FileDropzone |
| `bg-emerald-500/100`, `text-emerald-700` | `bg-status-success`, `text-status-success` | HealthDot, TaskStatusBadge |
| `bg-blue-100`, `text-blue-700/800` | `bg-status-running`, `text-status-running` | EnvBadge, TaskStatusBadge |
| `bg-cyan-50`, `text-cyan-700`, `border-cyan-300` | `bg-status-running/10`, `text-status-running`, `border-status-running/40` | StatusBadge, evaluate/[id] |
| `bg-slate-100/200`, `text-slate-600/700` | `bg-muted`, `text-muted-foreground` | TaskStatusBadge |
| `bg-gray-400` | `bg-muted-foreground/50` | HealthDot |
| `bg-[hsl(36_85%_50%)]`, `bg-[hsl(225_60%_45%)]` | `bg-ochre`, `bg-indigo` (新 token) | StatCard |
| `text-white` (on clay bg) | `text-primary-foreground` | 3 个 output 页面 |
| `bg-black/80` | 保留 (语义上跟主题无关) | dialog, alert-dialog |

## 9. `HealthDot.test.tsx` 断言修复

```diff
- expect(dot.className).toContain("bg-emerald-500");
+ expect(dot.className).toContain("bg-status-success");
- expect(dot.className).toContain("bg-rose-500");
+ expect(dot.className).toContain("bg-status-error");
```

## 10. 文件清单

**新建**:
- `web/lib/theme/themes.ts`
- `web/lib/theme/useTheme.ts`
- `web/lib/theme/index.ts`
- `web/components/settings/settings-dialog.tsx`
- `web/components/settings/settings-dialog.test.tsx`
- `web/components/settings/theme-toggle.tsx`
- `web/components/settings/theme-toggle.test.tsx`

**修改**:
- `web/app/layout.tsx` — ThemeProvider + ThemeToggle + suppressHydrationWarning
- `web/app/globals.css` — 补全 `.dark` + 4 语义 token + @plugin typography
- `web/package.json` — +next-themes +@tailwindcss/typography
- 18 处硬编码: MetricBar / SampleTable / StatusBadge / EnvBadge / HealthDot / TaskStatusBadge / ErrorBoundary / FileDropzone / MessageBubble / ThinkingTrace / StatCard / evaluate/[id]/page.tsx / 3 个 output 页面
- `web/components/knowledge/HealthDot.test.tsx` — 断言修复

## 11. 测试

- `theme-toggle.test.tsx`: 点齿轮 → SettingsDialog 弹出
- `settings-dialog.test.tsx`: 受控 / 3 行渲染 / 主题切换触发 / 语言 disabled / 用户 disabled
- 回归: 全 vitest 通过 / HealthDot 2 断言修复
- E2E: 暂不加

## 12. TDD 任务列表 (14 任务)

1. 安装 next-themes + @tailwindcss/typography
2. `web/lib/theme/themes.ts` 测试 + 实现
3. `web/lib/theme/useTheme.ts` + `index.ts`
4. `globals.css` 补全 `.dark` + 新增 4 语义 token + @plugin typography
5. `app/layout.tsx` 加 ThemeProvider + suppressHydrationWarning
6. `components/settings/theme-toggle.tsx` 测试 + 实现
7. `components/settings/settings-dialog.tsx` 测试 + 实现
8. `app/layout.tsx` header 加 ThemeToggle
9. 硬编码迁移: StatusBadge + HealthDot + EnvBadge
10. 硬编码迁移: TaskStatusBadge + MetricBar + SampleTable
11. 硬编码迁移: ErrorBoundary + FileDropzone + MessageBubble + ThinkingTrace
12. 硬编码迁移: StatCard ochre/indigo + 3 个 output 页面 text-white
13. 硬编码迁移: evaluate/[id] cyan 提示条
14. 回归全 vitest + typecheck + lint
