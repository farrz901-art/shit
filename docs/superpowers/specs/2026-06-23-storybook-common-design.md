# Storybook 设计系统组件浏览器设计方案

> **日期:** 2026-06-23
> **范围:** `packages/web/components/common/` 设计系统层
> **目标:** 搭建 Storybook 开发环境，为 25+ 公共组件提供可视化浏览和文档，提升开发体验和组件复用质量
> **状态:** 待用户 review

---

## 1. 当前状态

### 1.1 组件概况

| 指标 | 值 |
|------|-----|
| `components/common/` 组件数 | 25+（含子目录 4 组） |
| 已有 `.stories.tsx` 文件 | 4 个（dialog/confirm/drawer/form） |
| 已有 `.test.tsx` 文件 | 22 个 |
| 测试覆盖率 (lines) | ~67% |
| 工具链 | oxlint 0 error / tsgo 0 error / vitest pass |

### 1.2 已有 stories 现状

项目中已有 4 个 `.stories.tsx` 文件处于"孤岛"状态——代码已写好，但因为从未接入 Storybook，无法运行：

```
components/common/
├── dialog/app-dialog.stories.tsx   ✅ 代码完善
├── confirm/app-confirm.stories.tsx  ✅ 代码完善
├── drawer/app-drawer.stories.tsx    ✅ 代码完善
└── form/form.stories.tsx            ✅ 代码完善
```

均使用 function component + `useState` 模式，无 CSF args 依赖。这意味着**接入即可用，无需重写**。

### 1.3 技术栈现状

- **构建:** Vite（vitest 已是 Vite 生态，Storybook react-vite 无缝兼容）
- **样式:** Tailwind CSS 4（CSS 配置文件 `app/globals.css`，@theme inline 模式）
- **主题:** 自实现 ThemeProvider（CSS 变量 `hsl()` 切换，:root / .dark）
- **i18n:** next-intl（但 common 层组件 props 传文案，不受影响）
- **动画:** motion（motion/react，大量动画组件）
- **alias:** `@/` → `./`（vitest 和 tsconfig 已配置）

---

## 2. 目标

### 2.1 核心目标

- 提供开发态组件浏览器，让开发者直观看到 25+ 公共组件的所有状态变体
- **不做 CI 视觉回归**（视觉回归走 Playwright 截图，见 §10）
- **不做交互测试 in Storybook**（用已有的 vitest + Testing Library）
- **不做 a11y / snapshot addon**

### 2.2 明确不做的范围

| 不做 | 理由 |
|------|------|
| ❌ `app/` 下页面组件的 stories | 页面组件重度依赖 TanStack Query / RSC / i18n API，mock 成本 > 收益 |
| ❌ `@storybook/addon-interactions` / `test` | 已有 vitest + Testing Library，不重复 |
| ❌ CSF args 对象式 stories | 与项目已有 4 个 function-component 模式不一致 |
| ❌ i18n decorator（初期） | common 层 props 传文案，不用 `t()` |
| ❌ Chromatic | 不付费 |
| ❌ CI 视觉回归（初期） | 先用开发态 Storybook，以后需加时走 Playwright |

---

## 3. 技术方案

### 3.1 包选择

| 包 | 版本约束 | 理由 |
|---|---------|------|
| `@storybook/react` | latest | React 19 兼容 |
| `@storybook/addon-essentials` | latest | 内建 Controls / Actions / Backgrounds / Docs |
| `@storybook/react-vite` | latest | 项目已用 Vite，vitest 同配置，alias 复用 |

**不装的包：** `@storybook/nextjs`（App Router 支持不完善）、`@storybook/testing-library`、`chromatic`、`@storybook/addon-interactions`、`@storybook/addon-a11y`、`@storybook/addon-storysource`

### 3.2 配置

#### `.storybook/main.ts`

继承 vitest 的 alias 配置，确保 import 路径一致：

```ts
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

#### `.storybook/preview.ts`

全局 decorator 提供 Tailwind 上下文和基础布局：

```ts
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

> **Note:** 字体 CDN 加载暂不处理。Tailwind `font-sans` fallback 系统字体，不影响组件结构和样式验证。

### 3.3 package.json scripts

```json
"storybook": "storybook dev -p 6006",
"storybook:build": "storybook build"
```

---

## 4. Stories 编写规范

### 4.1 模式

沿用项目已有 4 个 stories 的 function-component 模式，不用 CSF args：

```tsx
"use client";
// ComponentName — 一句话说明 (YYYY-MM-DD)
import { useState } from "react";
import { ComponentName } from "./component-name";

export const Default = () => <ComponentName>默认内容</ComponentName>;

export const WithCustomProps = () => <ComponentName prop1="value">自定义</ComponentName>;

export const Interactive = () => {
  const [open, setOpen] = useState(false);
  return (
    <>
      <button onClick={() => setOpen(true)}>触发</button>
      <ComponentName open={open} onOpenChange={setOpen} />
    </>
  );
};
```

### 4.2 命名约定

- 文件：`<component>.stories.tsx`
- 导出：`export const Default =`, `export const VariantName =`
- 注释：文件头注释说明组件用途

### 4.3 组织方式

stories 文件与组件同目录：

```
components/common/
├── dialog/
│   ├── app-dialog.tsx
│   ├── app-dialog.test.tsx
│   └── app-dialog.stories.tsx
├── motion/
│   ├── reveal.tsx
│   ├── reveal.test.tsx
│   └── reveal.stories.tsx    ← 新增
```

---

## 5. Stories 补齐计划

按三批推进，每批产出可独立验证（`bun run storybook` 可查）：

### 第一批（P0）：已有 4 个 stories 启用

| 文件 | 状态 |
|------|------|
| `dialog/app-dialog.stories.tsx` | 已有，接入即用 |
| `confirm/app-confirm.stories.tsx` | 已有，接入即用 |
| `drawer/app-drawer.stories.tsx` | 已有，接入即用 |
| `form/form.stories.tsx` | 已有，接入即用 |

**产出：** `bun run storybook` 打开后能看到 4 个组件 ~12 个 story。

### 第二批（P1）：高优先级新增

| 组件 | stories 数 | 演示内容 | 预估工作量 |
|------|:---------:|---------|:----------:|
| `motion/Reveal` | 2 | 默认 / 延迟 / as section | 15 min |
| `motion/Stagger` | 1 | 列表顺次进入 | 10 min |
| `motion/StaggerItem` | 1 | fadeUp / fadeIn / scaleIn 三种变体 | 10 min |
| `motion/CountUp` | 1 | 不同数值演示 | 10 min |
| `motion/HoverLift` | 1 | hover 浮动效果 | 5 min |
| `motion/Pressable` | 1 | 按钮按压 / disabled | 10 min |
| `DataTable` | 3 | 空态 / 有数据分页 / loading | 40 min |
| `AppSelect` | 2 | 单选 / 禁用项 | 15 min |
| `AppToggle` | 1 | 组切换 | 10 min |

**产出：** +13 个 stories，~2 小时。

### 第三批（P2）：中优先级

| 组件 | stories 数 | 演示内容 | 预估工作量 |
|------|:---------:|---------|:----------:|
| `AppTabs` | 1 | 标签切换 | 10 min |
| `AppTooltip` | 1 | 提示方向 | 10 min |
| `ErrorBanner` | 4-5 | 4 种 variant + 关闭交互 | 20 min |
| `CopyButton` | 1 | 复制演示 | 5 min |
| `FileDropzone` | 1 | 拖拽区域 | 15 min |
| `PageHero` | 1 | 页面头部 | 5 min |
| `EntryCard` | 1 | 卡片展示 | 5 min |
| `StatCard` | 1 | 统计卡片（配合 CountUp） | 5 min |
| `BackLink` | 1 | 返回链接 | 5 min |
| `SubmitButton` | 1 | loading 状态 | 5 min |
| `AppDialog` 补充 | +1 | icon 演示 | 5 min |

**产出：** +14-15 个 stories，~1.5 小时。

### 第四批（P3）：低优先级（按需）

`HealthDot`、`EnvBadge`、`TaskStatusBadge`、`ErrorBoundary`、`BreathingDot`、`ImagePreview`、`SettingsCard`、`DataEmpty`、`AppDrawer` 补充交互等——组件简单或测试已覆盖，stories 价值有限，等有人需要再加。

---

## 6. 调试与验证

### 6.1 开发态

```bash
cd packages/web
bun run storybook
# → http://localhost:6006
```

每次改 stories 或组件自动热更新。

### 6.2 构建验证

```bash
bun run storybook:build
# → storybook-static/ 目录，可 serve 验证
```

### 6.3 质量门禁

Storybook 配置和 stories 不进入项目已有的工具链（oxlint / tsgo / vitest），但 stories 文件应通过 lint：

```bash
# oxlint 默认扫 stories 文件
bun run lint    # 确认 0 error
```

---

## 7. 目录结构最终形态

```
packages/web/
├── .storybook/
│   ├── main.ts          # Storybook 配置
│   └── preview.ts       # 全局 preview + decorator
│
├── components/common/
│   ├── dialog/
│   │   ├── app-dialog.tsx
│   │   ├── app-dialog.test.tsx
│   │   └── app-dialog.stories.tsx      ← 已有
│   ├── confirm/
│   │   ├── app-confirm.tsx
│   │   ├── app-confirm.test.tsx
│   │   └── app-confirm.stories.tsx      ← 已有
│   ├── drawer/
│   │   ├── app-drawer.tsx
│   │   ├── app-drawer.test.tsx
│   │   └── app-drawer.stories.tsx       ← 已有
│   ├── form/
│   │   ├── form.tsx
│   │   ├── form-item.tsx
│   │   ├── form.test.tsx
│   │   └── form.stories.tsx             ← 已有
│   ├── motion/
│   │   ├── reveal.tsx
│   │   ├── reveal.test.tsx
│   │   ├── reveal.stories.tsx           ← 新增
│   │   ├── stagger.tsx
│   │   ├── stagger.stories.tsx          ← 新增
│   │   ├── stagger-item.tsx
│   │   ├── stagger-item.stories.tsx     ← 新增
│   │   ├── count-up.tsx
│   │   ├── count-up.stories.tsx         ← 新增
│   │   ├── hover-lift.tsx
│   │   ├── hover-lift.stories.tsx       ← 新增
│   │   ├── pressable.tsx
│   │   └── pressable.stories.tsx        ← 新增
│   ├── data-table/
│   │   ├── data-table.tsx
│   │   ├── data-table.test.tsx
│   │   └── data-table.stories.tsx       ← 新增
│   ├── app-select.tsx
│   ├── app-select.stories.tsx           ← 新增
│   ├── app-toggle.tsx
│   ├── app-toggle.stories.tsx           ← 新增
│   ├── app-tabs.tsx
│   ├── app-tabs.stories.tsx             ← 新增
│   ├── app-tooltip.tsx
│   ├── app-tooltip.stories.tsx          ← 新增
│   ├── error-banner.tsx
│   ├── error-banner.stories.tsx         ← 新增
│   ├── copy-button.tsx
│   ├── copy-button.stories.tsx          ← 新增
│   ├── file-dropzone.tsx
│   ├── file-dropzone.stories.tsx         ← 新增
│   ├── page-hero.tsx
│   ├── page-hero.stories.tsx            ← 新增
│   ├── entry-card.tsx
│   ├── entry-card.stories.tsx           ← 新增
│   ├── stat-card.tsx
│   ├── stat-card.stories.tsx            ← 新增
│   ├── back-link.tsx
│   ├── back-link.stories.tsx            ← 新增
│   ├── submit-button.tsx
│   └── submit-button.stories.tsx        ← 新增
```

---

## 8. 执行步骤

```
Step 1: bun add -D @storybook/react @storybook/addon-essentials @storybook/react-vite
Step 2: 创建 .storybook/main.ts + .storybook/preview.ts
Step 3: package.json 加 "storybook" / "storybook:build" scripts
Step 4: bun run storybook 验证 4 个已有 stories 能跑
Step 5: .gitignore 追加 storybook-static/
Step 6: P1 批次 stories 编写（motion 6 个 + DataTable + AppSelect + AppToggle）
Step 7: P2 批次 stories 编写（剩余 12 个组件）
Step 8: 最终验证（bun run lint 0 error + bun run storybook:build 通过）
```

---

## 9. 故事示例

### 9.1 Reveal（motion 动画演示）

```tsx
"use client";
// Reveal — 下淡入进场动画演示 (2026-06-23)
import { Reveal } from "./reveal";

export const Default = () => (
  <div className="space-y-4">
    <Reveal>
      <div className="rounded-lg border border-border bg-card p-6">
        <p className="text-lg font-medium">第一个元素</p>
      </div>
    </Reveal>
    <Reveal delay={0.3}>
      <div className="rounded-lg border border-border bg-card p-6">
        <p className="text-lg font-medium">延迟 0.3s 出现</p>
      </div>
    </Reveal>
  </div>
);

export const AsSection = () => (
  <Reveal as="section">
    <h2 className="text-xl font-bold">Section 标题</h2>
    <p className="mt-2 text-muted-foreground">用 section 标签包裹</p>
  </Reveal>
);
```

### 9.2 DataTable（多状态演示）

```tsx
"use client";
// DataTable — 表格组件多状态演示 (2026-06-23)
import { DataTable } from "./data-table";
import { DataEmpty } from "../data-empty";
import type { ColumnDef } from "@tanstack/react-table";

interface DemoItem {
  id: string;
  name: string;
  status: string;
}

const columns: ColumnDef<DemoItem>[] = [
  { accessorKey: "id", header: "ID" },
  { accessorKey: "name", header: "名称" },
  { accessorKey: "status", header: "状态" },
];

const data: DemoItem[] = [
  { id: "1", name: "文档 A", status: "完成" },
  { id: "2", name: "文档 B", status: "处理中" },
  { id: "3", name: "文档 C", status: "失败" },
];

export const Empty = () => (
  <DataTable
    dataSource={[]}
    columns={columns}
    rowKey="id"
    emptyText={<DataEmpty title="暂无数据" />}
  />
);

export const WithData = () => (
  <DataTable
    dataSource={data}
    columns={columns}
    rowKey="id"
  />
);

export const Loading = () => (
  <DataTable
    dataSource={[]}
    columns={columns}
    rowKey="id"
    loading
  />
);
```

### 9.3 ErrorBanner（variant 演示）

```tsx
"use client";
// ErrorBanner — 4 种变体演示 (2026-06-23)
import { ErrorBanner } from "./error-banner";

export const Variants = () => (
  <div className="space-y-4">
    <ErrorBanner variant="info" description="这是一条提示信息" />
    <ErrorBanner variant="success" description="操作成功完成" />
    <ErrorBanner variant="warning" description="请注意：配置尚未保存" />
    <ErrorBanner variant="destructive" description="发生错误，请重试" />
  </div>
);
```

---

## 10. 视觉回归策略（不做 Chromatic 的替代方案）

明确不做 CI 视觉回归（初期），但保留扩展路径。如未来需要，有两种方案：

### 方案 A：Playwright 截图（推荐）

利用已有的 Playwright，在 E2E 基础上加截图对比：

```ts
// e2e/specs/visual-regression.spec.ts
test("common 组件快照", async ({ page }) => {
  // 方案 A：直接截图 storybook-static/（需要先 build）
  // 方案 B：截图现有页面中的组件区域
});
```

维护成本低，不需要新依赖。但需要有人维护基准截图。

### 方案 B：Storybook 的 test-runner + Playwright

`@storybook/test-runner` 会遍历所有 stories 截图：

```bash
npx test-storybook --browsers chromium
```

但依赖 `storybook dev` 运行中，CI 配置略复杂。

**建议：** 当前不做。等 components/common/ 稳定后由维护者决定。

---

## 11. 风险与缓解

| 风险 | 影响 | 缓解方案 |
|------|------|---------|
| Tailwind v4 @theme inline 在 Storybook 不生效 | 样式错乱 | globals.css 直接 import，@theme inline 在 Vite 下工作正常 |
| `next/font` 在 Storybook 不可用 | 字体回退系统 | Tailwind font-sans fallback 系统字体，不影响组件验证 |
| motion 动画在 Docs 模式不触发 | story 无法展示动画 | 用 Canvas 模式查看，提示开发者切 Canvas tab |
| stories 增加后维护负担 | 组件改动需同步更新 stories | 约定：改组件 props 时同步更新 stories |
| `server-only` 模块在 Vite 下报错 | alias 为空模块后解决 | 已在 vitest 验证该方案可行 |
| bun run lint 扫 stories 文件报错 | oxlint 规则可能需要调整 stories 写法 | 保持 stories 符合 oxlint 规则（function-component 模式本身合规） |

---

## 12. 验收标准

- [ ] `bun run storybook` 在 dev 模式下可正常启动
- [ ] 浏览器访问 `localhost:6006` 能看到组件列表
- [ ] 已有 4 个 stories（dialog/confirm/drawer/form）正常渲染
- [ ] 新增 P1 批次 + P2 批次 stories 全部可查看
- [ ] `bun run storybook:build` 构建通过
- [ ] `bun run lint` 0 error（stories 文件含在内）
- [ ] `.gitignore` 已添加 `storybook-static/`
- [ ] 项目 README 或有关文档提及 Storybook 启动方式
