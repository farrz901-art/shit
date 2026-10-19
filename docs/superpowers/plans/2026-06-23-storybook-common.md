# Storybook 设计系统组件浏览器 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan phase-by-phase. Each phase produces a working, testable result. Steps use checkbox (`- [ ]`) syntax.
>
> **Base spec:** `docs/superpowers/specs/2026-06-23-storybook-common-design.md`

**Goal:** 搭建 Storybook 开发环境，为 `components/common/` 层 25+ 公共组件提供可视化浏览和文档

**Architecture:** 4 个 Phase 顺序执行。Phase 1（安装配置）是后续 Phase 的基础；Phase 2（启用已有）验证配置正确；Phase 3-4 分批补充 stories。每个 Phase 产出可独立验证（`bun run storybook` 可查看）。

**Scope:** 仅覆盖 `packages/web/components/common/`，不碰 `app/` 页面组件。

**Not in scope:** CI 视觉回归（保留 Playwright 截图路径，当前不做）、Chromatic、CSF args 式 stories、i18n decorator

**Tech Stack:** @storybook/react + @storybook/addon-essentials + @storybook/react-vite / Vite / Tailwind CSS 4 / motion / React 19

---

## 执行统计

| Phase | 内容 | 预计文件数 |
|-------|------|-----------|
| P1 | 安装依赖 + 配置文件 + scripts | 3 新建 |
| P2 | 启用已有 4 个 stories | 0 新建 |
| P3 | P1 批次 stories（motion 6 + DataTable + AppSelect + AppToggle） | 9 新建 |
| P4 | P2 批次 stories（剩余 12 个组件） | 12 新建 |

---

### Phase 1: 安装 + 配置（预计 10 min）

**Files:**
- New: `packages/web/.storybook/main.ts`
- New: `packages/web/.storybook/preview.ts`
- Modify: `packages/web/package.json`
- Modify: `packages/web/.gitignore`

- [ ] **1a: 安装依赖**

```bash
cd packages/web
bun add -D @storybook/react @storybook/addon-essentials @storybook/react-vite
```

- [ ] **1b: 创建 .storybook/main.ts**

```typescript
import type { StorybookConfig } from "@storybook/react-vite";
import path from "node:path";

const config: StorybookConfig = {
  stories: ["../components/common/**/*.stories.@(ts|tsx)"],
  addons: ["@storybook/addon-essentials"],
  framework: { name: "@storybook/react-vite", options: {} },
  viteFinal: async (config) => {
    config.resolve = config.resolve ?? {};
    config.resolve.alias = {
      ...config.resolve.alias,
      "@": path.resolve(__dirname, ".."),
      "server-only": path.resolve(__dirname, "../test-shims/server-only-empty.ts"),
      zod: path.resolve(__dirname, "../node_modules/zod/index.cjs"),
    };
    return config;
  },
};
export default config;
```

- [ ] **1c: 创建 .storybook/preview.ts**

```typescript
import type { Preview } from "@storybook/react";
import "../app/globals.css";

const preview: Preview = {
  parameters: {
    controls: { expanded: true },
    backgrounds: {
      default: "light",
      values: [
        { name: "light", value: "hsl(0 0% 98%)" },
        { name: "dark", value: "hsl(222 47% 7%)" },
      ],
    },
    options: {
      storySort: { method: "alphabetical" },
    },
  },
  decorators: [
    (Story) => (
      <div className="p-8 bg-background text-foreground min-h-screen font-sans antialiased">
        <Story />
      </div>
    ),
  ],
};
export default preview;
```

- [ ] **1d: package.json 加 scripts**

```json
"storybook": "storybook dev -p 6006",
"storybook:build": "storybook build"
```

加在 `"test:e2e:ui"` 和 `"typecheck"` 之间（按字母排序）。

- [ ] **1e: .gitignore 追加**

```
# storybook
storybook-static/
```

- [ ] **1f: 验证**

```bash
cd packages/web
bun run storybook:build   # 构建通过
```

---

### Phase 2: 启用已有 4 个 stories（预计 5 min）

已有 4 个 `.stories.tsx` 文件，代码已经满足 Phase 1 的配置规则（使用 function-component 导出模式，无 CSF args），理论直接可用。

**Files:** 0 新建，仅验证

- [ ] **2a: 确认 4 个已有 stories 文件存在**

```
components/common/dialog/app-dialog.stories.tsx
components/common/confirm/app-confirm.stories.tsx
components/common/drawer/app-drawer.stories.tsx
components/common/form/form.stories.tsx
```

- [ ] **2b: 验证启动**

```bash
cd packages/web
bun run storybook
```

浏览器打开 `http://localhost:6006`，确认：
- Sidebar 能看到 "app-dialog" / "app-confirm" / "app-drawer" / "form" 4 个组件
- 每个组件下能看到对应 story（Basic / WithFooter / MaxWidth 等）
- 点击 story 能正常渲染

- [ ] **2c: 验证 lint**

```bash
cd packages/web
bun run lint   # 确认 0 error（stories 文件应遵守项目 lint 规则）
```

---

### Phase 3: P1 批次 — 高优先级 stories（预计 2 小时）

**Files:** 9 新建

| # | 文件 | stories 内容 |
|---|------|-------------|
| 1 | `motion/reveal.stories.tsx` | Default（两个元素不同 delay 对比）+ AsSection |
| 2 | `motion/stagger.stories.tsx` | 列表顺次进入 |
| 3 | `motion/stagger-item.stories.tsx` | fadeUp / fadeIn / scaleIn 三种变体 |
| 4 | `motion/count-up.stories.tsx` | 不同数值演示 |
| 5 | `motion/hover-lift.stories.tsx` | hover 浮动效果 |
| 6 | `motion/pressable.stories.tsx` | 按钮按压 + disabled 状态 |
| 7 | `data-table/data-table.stories.tsx` | 空态 / 有数据分页 / loading |
| 8 | `app-select.stories.tsx` | 单选 / 禁用项 |
| 9 | `app-toggle.stories.tsx` | 组切换 |

- [ ] **3a: 编写 motion/ 6 个 stories**

```bash
cd packages/web

# 先创建 motion 目录下的 6 个 stories 文件
```

各文件内容（使用 function-component 模式，见 spec §9.1 示例）：

**reveal.stories.tsx** — 演示默认 fadeUp、delay 参数、as="section"
**stagger.stories.tsx** — 3 个 StaggerItem 子元素顺次进入
**stagger-item.stories.tsx** — 3 个 StaggerItem 分别用 fadeUp / fadeIn / scaleIn
**count-up.stories.tsx** — 3 个 CountUp（42 / 9999 / 1234567）对比
**hover-lift.stories.tsx** — 单卡片 hover 浮动
**pressable.stories.tsx** — 启用/禁用两个按钮

- [ ] **3b: 编写 data-table.stories.tsx**

```bash
# 创建 data-table.stories.tsx
```

三个 story：Empty（空态 + DataEmpty）/ WithData（3 行数据）/ Loading（loading 态）
见 spec §9.2 示例。

- [ ] **3c: 编写 app-select.stories.tsx**

两个 story：Default（options 列表）、WithDisabled（含禁用项）

- [ ] **3d: 编写 app-toggle.stories.tsx**

一个 story：GroupToggle 演示

- [ ] **3e: 验证 Phase 3**

```bash
cd packages/web
bun run storybook:build   # 构建通过
bun run lint              # 0 error
```

---

### Phase 4: P2 批次 — 中优先级 stories（预计 1.5 小时）

**Files:** 12 新建

| # | 文件 | stories 数 | 内容 |
|---|------|:---------:|------|
| 1 | `app-tabs.stories.tsx` | 1 | 标签切换 |
| 2 | `app-tooltip.stories.tsx` | 1 | 提示方向（top / bottom） |
| 3 | `error-banner.stories.tsx` | 4 | info / success / warning / destructive |
| 4 | `copy-button.stories.tsx` | 1 | 复制演示 |
| 5 | `file-dropzone.stories.tsx` | 1 | 拖拽区域 |
| 6 | `page-hero.stories.tsx` | 1 | 页面头部标题+描述 |
| 7 | `entry-card.stories.tsx` | 1 | 卡片展示 |
| 8 | `stat-card.stories.tsx` | 1 | 统计卡片（配合 CountUp） |
| 9 | `back-link.stories.tsx` | 1 | 返回链接 |
| 10 | `submit-button.stories.tsx` | 1 | loading 状态 |
| 11 | `dialog/app-dialog.stories.tsx` 补充 | +1 | icon 演示 |
| 12 | `drawer/app-drawer.stories.tsx` 补充 | +1 | 补充更多交互演示 |

- [ ] **4a: 编写 10 个普通组件 stories**

各文件模式：

```tsx
// error-banner.stories.tsx
"use client";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { ErrorBanner } from "./error-banner";

export const Variants = () => (
  <div className="space-y-4">
    <ErrorBanner variant="info" description="提示信息" />
    <ErrorBanner variant="success" description="操作成功" />
    <ErrorBanner variant="warning" description="请注意" />
    <ErrorBanner variant="destructive" description="发生错误" />
  </div>
);

export const Dismissible = () => {
  const [visible, setVisible] = useState(true);
  return visible ? (
    <ErrorBanner variant="warning" description="可关闭" action={<Button size="sm" onClick={() => setVisible(false)}>关闭</Button>} />
  ) : null;
};
```

- [ ] **4b: 补充已有 dialog/drawer stories**

在 `app-dialog.stories.tsx` 追加 `export const WithIconStory = () => { ... }`，演示 `icon` prop。
在 `app-drawer.stories.tsx` 根据情况补充。

- [ ] **4c: 最终验证**

```bash
cd packages/web
bun run storybook:build   # 构建通过
bun run lint              # 0 error
```

---

## Stories 编写模板

### 标准模式（多数组件用）

```tsx
"use client";
// ComponentName — 一句话说明 (2026-06-23)
import { ComponentName } from "./component-name";

export const Default = () => <ComponentName>默认内容</ComponentName>;

export const VariantA = () => <ComponentName prop1="val1">变体 A</ComponentName>;

export const VariantB = () => <ComponentName prop1="val2">变体 B</ComponentName>;
```

### 交互模式（弹框/确认框用）

```tsx
"use client";
// ComponentName — 交互演示 (2026-06-23)
import { useState } from "react";
import { ComponentName } from "./component-name";
import { Button } from "@/components/ui/button";

export const Interactive = () => {
  const [open, setOpen] = useState(false);
  return (
    <>
      <Button onClick={() => setOpen(true)}>打开</Button>
      <ComponentName open={open} onOpenChange={setOpen} title="标题">
        <p>内容</p>
      </ComponentName>
    </>
  );
};
```

### 多状态模式（变体系列用）

```tsx
"use client";
// ComponentName — variant 演示 (2026-06-23)
import { ComponentName } from "./component-name";

export const AllVariants = () => (
  <div className="space-y-4">
    <ComponentName variant="info" description="信息" />
    <ComponentName variant="success" description="成功" />
    <ComponentName variant="warning" description="警告" />
    <ComponentName variant="destructive" description="错误" />
  </div>
);
```

---

## 质量检查清单（每个 Phase 后执行）

- [ ] `bun run storybook:build` 通过，无报错
- [ ] `bun run lint` 0 error（stories 文件包含在扫描范围内）
- [ ] 新 stories 在 dev 模式 (`bun run storybook`) 下正常渲染
- [ ] 已有测试 (`bun run test`) 未被影响

## 不做事项

- 不加 `@storybook/addon-interactions` / `@storybook/test` / `@storybook/testing-library`
- 不加 i18n decorator（common 层组件 props 传文案）
- 不加 Chromatic CI 集成
- 不加 `app/` 页面组件的 stories
- 不迁移已有 4 个 stories 到 CSF args 格式
