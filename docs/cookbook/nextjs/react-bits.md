# React Bits 教程

> 📅 创建日期：2026-06-28
> 📁 项目代码引用：本教程以 `c:/doc/Code/rag` 仓库当前代码为准，所有引用标注 `file_path:line_number`
> 🏷️ 类别：L-语言/框架（React 动画组件素材库）
> 🎯 读者：中高级 TS 工程师，需要在 Next.js 项目里评估"现成炫酷组件"是否值得引入、能怎么跟项目 motion 体系协作

---

## 目录

- [一、是什么 & 适用场景](#一是什么--适用场景)
- [二、安装 & 开发环境](#二安装--开发环境)
- [三、基础语法 & 类型系统](#三基础语法--类型系统)
- [四、核心概念](#四核心概念)
- [五、常用命令 & 工具链](#五常用命令--工具链)
- [六、项目集成点](#六项目集成点)
- [七、项目代码示例](#七项目代码示例)
- [八、项目没用到的能力 / 进阶方向](#八项目没用到的能力--进阶方向)
- [九、最佳实践 & 常见坑](#九最佳实践--常见坑)

---

## 一、是什么 & 适用场景

[React Bits](https://www.reactbits.dev/) 是一个**开源 React 动画组件素材库**，把常见的"视觉炫酷"效果（极光背景、磁吸按钮、3D 卡片、毛玻璃面板、磁性光标）封装成 ~120 个可复制粘贴的组件。**不是 npm 包** —— 直接去官网复制源码到自己的项目。

**与 motion 的关系**：

| 库 | 定位 | 角色 |
|------|------|------|
| **motion** | 底层动画引擎 | `motion.div` + spring + AnimatePresence |
| **react-bits** | 预制组件集合 | 内部**使用** motion / GSAP / CSS |

> **React Bits ≈ shadcn/ui for animations**。Shadcn 把组件 copy 到 `components/ui/`，React Bits 把动画组件 copy 到 `components/effects/`。

**同类对比：**

| 资源 | 定位 | 本项目选择理由 |
|------|------|----------------|
| **React Bits** | 预制动画组件素材 | 适合"想要某个具体炫酷效果时"按需 copy |
| **motion** | 底层动画引擎 | 项目**主力**，所有自定义动画的引擎 |
| **shadcn/ui** | 通用 UI 组件素材 | 项目已装，但跟"动画"维度不同 |
| **Aceternity UI** | 同类炫酷组件库 | 内容偏 "Web3/暗色" 风格，更花哨 |
| **GSAP showcase** | GSAP 演示页 | 复杂编排优秀但代码量重，不适合 Next.js RSC |
| **Tailwind Animate** | CSS keyframes 集合 | 极简进入/退出，无 React 集成 |

**React Bits 适合的场景**：
- 想要某个"花哨效果"，不想从 motion 0 写
- 项目**允许 copy-paste 第三方代码**进项目（白盒修改）
- 内部 demo 页 / 营销页 / 落地页等"短期内容"，不值得投入定制组件

**不适用的场景**：
- **生产关键路径组件**（登录、支付、表单）—— 这些需要项目自有封装（`<Reveal>` `<Stagger>` `<Pressable>`）
- **bundle size 敏感场景** —— 每个组件 5-20KB，组合起来显著
- **需要 a11y reduce-motion 兼容** —— React Bits 组件普遍没处理 reduce-motion

---

## 二、安装 & 开发环境

### 2.1 "安装"流程

React Bits 不通过 npm 装。流程：

1. 浏览 <https://www.reactbits.dev/>
2. 找到想要的效果（如 "Aurora Background"）
3. 选择 "Motion" 版本（项目用 motion）或 "CSS" 版本（纯 CSS）
4. 复制源码到项目 `components/effects/<name>.tsx`
5. 按需修改 props / 颜色 / 文案

### 2.2 项目集成位置

本项目建议放置：

```
packages/web/components/
├── motion/                # 项目自有动画封装 (现有)
│   ├── reveal.tsx
│   ├── stagger.tsx
│   └── ...
└── effects/                # 新建: React Bits copy 来的炫酷组件
    ├── aurora-background.tsx
    ├── magnetic-button.tsx
    ├── glass-panel.tsx
    └── ...
```

`effects/` 是**只读素材**目录，组件从 reactbits.dev 复制，**不做大规模定制**。

---

## 三、基础语法 & 类型系统

### 3.1 典型组件结构

每个 React Bits 组件结构类似：

```tsx
"use client";
import { motion } from "motion/react";

export interface AuroraBackgroundProps {
  children: ReactNode;
  className?: string;
}

export const AuroraBackground = ({ children, className }: AuroraBackgroundProps) => {
  return (
    <div className={cn("relative overflow-hidden", className)}>
      <motion.div
        className="absolute inset-0 bg-linear-to-r from-blue-500 to-purple-500 opacity-30 blur-3xl"
        animate={{
          scale: [1, 1.2, 1],
          rotate: [0, 180, 360],
        }}
        transition={{
          duration: 20,
          repeat: Infinity,
          ease: "linear",
        }}
      />
      <div className="relative z-10">{children}</div>
    </div>
  );
};
```

### 3.2 两种实现风格

React Bits 提供两种版本：

- **Motion 版本**：用 `motion/react`，依赖项目 motion 包
- **CSS 版本**：用 Tailwind keyframes + transition，无运行时依赖

**项目推荐 Motion 版本**，因为：
- 已有 motion 作为依赖（[package.json:61](../../packages/web/package.json)）
- 复用 `lib/motion.ts` 的 token 系统
- 接入 a11y reduce-motion 一致性更高

### 3.3 Props 风格

React Bits 组件普遍遵循：

```tsx
interface ComponentProps {
  children?: ReactNode;
  className?: string;        // 容器自定义样式
  // 1-3 个最常用参数
}
```

跟项目封装组件风格一致。**不会过度 API 化**（不像 antd 一堆 props），copy 后按需扩展。

---

## 四、核心概念

### 4.1 分类（按视觉效果）

React Bits 把组件分 ~20 类：

| 类别 | 代表组件 | 适用场景 |
|------|---------|---------|
| **Backgrounds** | AuroraBackground, BeamsBackground, DotGrid, GridDistortion | hero 区背景、空状态背景 |
| **Buttons** | MagneticButton, GooeyButton, ShinyButton | CTA / hero 按钮 |
| **Cards** | TiltedCard, GlassCard, FeatureCard | 营销卡片 |
| **Text** | GradientText, ScrambledText, TrueFocus, ShinyText | hero 标题、loading 文案 |
| **Animations** | FadeIn, SlideUp, Marquee | 通用入场 |
| **Cursors** | MagnetCursor, BubbleCursor | 整站鼠标交互 |
| **Lists** | InfiniteScroll, ScrollStack | 长列表滚动 |
| **Layout** | Masonry, Dock | 特殊布局 |
| **Loaders** | OrbitingLoader, PulsatingDot | loading 状态 |

### 4.2 自定义程度

每个组件提供**基础 props + className 透传**：

```tsx
<AuroraBackground className="bg-paper/50">  // 容器颜色
  <h1>Welcome</h1>
</AuroraBackground>
```

**修改动画行为**需要直接改源码（白盒），不像 shadcn 用 CSS variables 主题化那么优雅。这是 React Bits 的取舍：**视觉炫酷 vs 主题化**。

### 4.3 性能影响

| 类别 | 性能影响 | 备注 |
|------|---------|------|
| Backgrounds | 中 - 高 | blur + 持续动画，主线程压力 |
| Buttons | 低 | 单个交互态，无持续动画 |
| Cards (tilt) | 中 | 鼠标移动重计算 |
| Text (scramble) | 中 | 字符随机化计算 |
| Animations (基础) | 低 | 类似 `lib/motion.ts` |

**原则**：
- hero / landing 页面：可以用 1-2 个炫酷背景
- 业务页面（admin / settings / knowledge）：**不要用**炫酷背景，干扰操作
- 全局组件库：**不要用**，所有页面都会用到

---

## 五、常用命令 & 工具链

React Bits 不需要专门命令。常用操作：

### 5.1 快速 fork

```bash
# 1. 浏览器打开 reactbits.dev/<effect-name>
# 2. 选 Motion 版本, 点击 "Copy Code"
# 3. 粘贴到项目
mkdir -p packages/web/components/effects
touch packages/web/components/effects/aurora-background.tsx
# 编辑器粘贴
```

### 5.2 适配项目 motion token

```tsx
// ❌ 默认: React Bits 硬编码
transition={{ duration: 20, ease: "linear" }}

// ✅ 适配: 改用项目 token
import { DUR, EASE } from "@/lib/motion";
transition={{ duration: DUR.slow * 5, ease: "linear" }}  // 仍要循环 20s, 算倍数
```

### 5.3 接入 a11y reduce-motion

```tsx
// 默认 React Bits 没处理 reduce-motion
// 加 useReducedMotionSafe 处理
import { useReducedMotionSafe } from "@/components/motion/use-reduced-motion-safe";

export const AuroraBackground = ({ children, className }: Props) => {
  const reduced = useReducedMotionSafe();

  if (reduced) {
    // reduce 模式: 静态渐变背景, 不动画
    return <div className={cn("bg-linear-to-br from-blue-500/30 to-purple-500/30", className)}>{children}</div>;
  }

  return (
    <div className={cn("relative overflow-hidden", className)}>
      <motion.div animate={...}>...</motion.div>
      {children}
    </div>
  );
};
```

### 5.4 检查组件性能

```bash
# React DevTools Profiler, 找持续动画组件
# 1. Performance tab
# 2. Record 5s
# 3. 看 FPS / 主线程占用
```

---

## 六、项目集成点

本项目**未使用 React Bits**。原因：

1. **项目已有完整 motion 体系** — [`packages/web/components/motion/`](../../packages/web/components/motion/) 13 个封装组件覆盖入场 / 退场 / 物理 / 数字弹动 / a11y
2. **业务页面克制** — 后台 admin / settings / knowledge 页需要**稳定可操作**，炫酷背景干扰
3. **bundle size 敏感** — 项目已锁定 React 19 + Next.js 16 + shadcn 全套，加 React Bits 组件会显著增加 JS 体积
4. **a11y 严格** — 项目已为 `<Reveal>` `<Stagger>` 等做了 `useReducedMotionSafe`（[reveal.tsx:29](../../packages/web/components/motion/reveal.tsx#L29)），React Bits 组件需要逐个适配

**潜在场景（理论上）**：

| 场景 | 是否引入 |
|------|---------|
| **Landing / Marketing 页** | ✅ 推荐 — 一次性页面，视觉冲击重要 |
| **About / Pricing 页** | ✅ 可选 — 营销文案需要吸引注意力 |
| **Login / Sign-up 页** | ⚠️ 谨慎 — 适度炫酷可以，但需控制不能影响输入 |
| **Admin / Settings** | ❌ 不推荐 — 干扰业务操作 |
| **Chat 页面** | ❌ 不推荐 — 需要长时间使用 |
| **Knowledge 管理页** | ❌ 不推荐 — 检索密集，视觉噪声影响 |

**结论**：本项目风格偏**专业克制**（参考 [theme-system spec](../../superpowers/specs/2026-06-10-theme-system-design.md)），不太适合 React Bits 大量引入。**若要引入，限制在 landing 页即可，且必须 a11y 兼容**。

---

## 七、项目代码示例

项目仓库内**没有任何 React Bits 调用代码**。下面给出"如果本项目要引入某个 React Bits 组件"的样例路径。

### 7.1 选择组件 + 适配

以 **Aurora Background** 为例：

**React Bits 原始代码**（简化）：
```tsx
"use client";
import { motion } from "motion/react";

export const AuroraBackground = ({ children, className }) => (
  <div className={cn("relative", className)}>
    <motion.div
      className="absolute inset-0 bg-blue-500 blur-3xl"
      animate={{ scale: [1, 1.2, 1], rotate: [0, 360] }}
      transition={{ duration: 20, repeat: Infinity }}
    />
    <div className="relative z-10">{children}</div>
  </div>
);
```

**项目适配版本**（`components/effects/aurora-background.tsx`）：
```tsx
"use client";
import { type ReactNode } from "react";
import { motion } from "motion/react";
import { cn } from "@/lib/utils";
import { useReducedMotionSafe } from "@/components/motion/use-reduced-motion-safe";

const AURORA_DURATION = 20;

export interface AuroraBackgroundProps {
  children: ReactNode;
  className?: string;
}

export const AuroraBackground = ({ children, className }: AuroraBackgroundProps) => {
  const reduced = useReducedMotionSafe();

  if (reduced) {
    // a11y: 静态渐变背景, 无动画
    return (
      <div className={cn("relative bg-linear-to-br from-status-running/10 to-status-success/10", className)}>
        <div className="relative z-10">{children}</div>
      </div>
    );
  }

  return (
    <div className={cn("relative overflow-hidden", className)}>
      <motion.div
        className="absolute inset-0 bg-status-running/20 blur-3xl"
        animate={{ scale: [1, 1.2, 1], rotate: [0, 360] }}
        transition={{ duration: AURORA_DURATION, repeat: Infinity, ease: "linear" }}
        aria-hidden
      />
      <div className="relative z-10">{children}</div>
    </div>
  );
};
```

**接入点**（landing 页 hero）：
```tsx
// app/[locale]/landing/page.tsx
import { AuroraBackground } from "@/components/effects/aurora-background";

<AuroraBackground className="h-[600px]">
  <h1 className="text-display">Welcome to RAG</h1>
</AuroraBackground>
```

### 7.2 项目类似位置的对照

| React Bits 组件 | 项目已有的等价方案 |
|----------------|-------------------|
| `<AuroraBackground>` | 项目**没有**等价背景组件 → 适合引入 |
| `<MagneticButton>` | [`<Pressable>`](../../packages/web/components/motion/pressable.tsx) — 功能重叠，**不要引入** |
| `<TiltedCard>` | 项目**没有** 3D 倾斜卡 → 适合引入（如要） |
| `<ShinyText>` | 项目**没有** 闪光文字 → 适合引入（如要） |
| `<GoeyButton>` | 项目**没有** 黏液按钮 → 适合引入（如要） |
| `<InfiniteScroll>` | 跟项目虚拟滚动方案对比后再选 |
| `<FadeIn>` / `<SlideUp>` | 完全等价于项目 `<Reveal>` `<FadeUp>`，**不要引入** |

**原则**：React Bits 组件能跟项目现有 `<Reveal>` 等替换的，**不要引入**（维护 2 套等价 API 是技术债）。**只引入项目没有的炫酷视觉组件**。

---

## 八、项目没用到的能力 / 进阶方向

### 8.1 Landing / Marketing 页效果

如果项目要做 marketing landing（[项目目前没有，但有可能扩展](https://github.com/forkai/rag)），可以考虑：

| 组件 | 效果 |
|------|------|
| `AuroraBackground` / `BeamsBackground` | hero 区渐变背景 |
| `MagneticButton` | 鼠标磁吸按钮 |
| `TiltedCard` | 3D 倾斜卡 |
| `ShinyText` / `GradientText` | 标题装饰 |
| `Marquee` | 客户 logo 横滚 |
| `ScrollStack` | 滚动堆叠 |

### 8.2 复杂编排

React Bits 不擅长复杂编排（多元素时间线联动），需要时**用项目 motion 直接写**：

```tsx
// 自定义编排: 多元素时间线
const timeline = {
  initial: {},
  animate: {
    transition: {
      staggerChildren: 0.1,
      delayChildren: 0.3,
    },
  },
};
```

### 8.3 3D / WebGL 效果

React Bits 部分组件用 WebGL（如 `WebGLBackground`），性能成本高，**仅 landing 页用**。业务页避免。

### 8.4 GSAP 替代路径

React Bits 提供 "GSAP" 版本，对复杂时间线（`gsap.timeline()`）编排优秀。但项目 GSAP **未装**，且 GSAP 跟 React 集成需要 `useLayoutEffect` + ref pattern，跟 motion 的声明式 API 风格不同。**不建议引入 GSAP 路径**。

---

## 九、最佳实践 & 常见坑

### 9.1 不要复制"未指定依赖版本"的代码

```tsx
// ❌ 错: React Bits 代码可能用 framer-motion 旧版
import { motion } from "framer-motion";

// ✅ 对: 改成项目用的 motion/react
import { motion } from "motion/react";
```

### 9.2 接入 a11y

每个 React Bits 组件必须加 `useReducedMotionSafe`：

```tsx
// 默认: React Bits 没处理 reduce-motion
animate={{ rotate: 360 }}    // 系统设置"减少动画"用户也会被强制旋转

// ✅ 适配: reduce 模式跳过持续动画
if (reduced) return <static version>;
```

### 9.3 容器布局要正确

```tsx
// ❌ 错: 容器无 relative, 背景飞到 viewport 外
<AuroraBackground>
  <h1>...</h1>
</AuroraBackground>

// ✅ 对: 容器加 relative + overflow-hidden
<AuroraBackground className="relative overflow-hidden h-[500px]">
  <h1>...</h1>
</AuroraBackground>
```

### 9.4 避免重复定义相同效果

```tsx
// ❌ 错: 同时引入 React Bits 的 ShinyText + 自己写 ShinyText
// 维护 2 套等价代码

// ✅ 对: 选定一个 (建议项目自有), 统一一个来源
```

### 9.5 测试时要 mock 动画

```typescript
vi.mock("motion/react", async (importOriginal) => ({
  ...(await importOriginal<typeof import("motion/react")>()),
  useInView: vi.fn().mockReturnValue(true),
}));

// 测试组件是否渲染, 不要真的等动画结束
it("aurora background 渲染 children", () => {
  render(<AuroraBackground><div>Hello</div></AuroraBackground>);
  expect(screen.getByText("Hello")).toBeInTheDocument();
});
```

### 9.6 项目配色 token 适配

```tsx
// ❌ 错: 用 React Bits 默认颜色 (蓝紫渐变)
className="bg-linear-to-r from-blue-500 to-purple-500"

// ✅ 对: 改成项目主题色 token
className="bg-linear-to-r from-clay to-moss"  // 项目 token
// 或
className="bg-linear-to-r from-status-running to-status-success"
```

参考 [`app/globals.css`](../../packages/web/app/globals.css) 的 `--color-clay` / `--color-moss` 等定义。

### 9.7 版权 / license

React Bits 是 MIT license（具体见官网 footer），可以商业使用、修改、闭源。但**不要直接 cp 整个组件库到项目**——按需引用，并写明出处。

### 9.8 bundle size 监控

每个 React Bits 组件引入后，看 Next.js bundle analyzer：

```bash
ANALYZE=true bun run build
```

```ts
// next.config.ts
const withBundleAnalyzer = require("@next/bundle-analyzer")({ enabled: process.env.ANALYZE === "true" });
module.exports = withBundleAnalyzer({});
```

如果某个炫酷组件占 50KB+ 但只用 1 次，**不划算**。

### 9.9 不要替换项目 `<Reveal>` `<Stagger>`

React Bits 也有 `FadeIn` / `SlideUp` 等基础动画组件。**不要用它们替换项目现有 `<Reveal>` `<Stagger>`**：

| 维度 | 项目 `<Reveal>` | React Bits `FadeIn` |
|------|-----------------|-------------------|
| RSC 友好 | ✅ | ❌（use client 限制） |
| a11y reduce-motion | ✅ 全部封装 | ❌ 需自行适配 |
| 主题 token | ✅ 走 `lib/motion.ts` | ❌ 硬编码 |
| 测试覆盖 | ✅ 5 个组件各有 .test.tsx | ❌ 无 |

---

## 📚 参考

- [React Bits 官网](https://www.reactbits.dev/)
- [React Bits GitHub](https://github.com/DavidHDev/react-bits)（官方仓库）
- [Motion 官方文档](https://motion.dev/docs) — React Bits 的底层依赖
- [项目 motion 封装目录](../../packages/web/components/motion/) — 13 个项目自有动画组件
- [项目 motion token](../../packages/web/lib/motion.ts) — 动画时长 / 缓动 / 位移单一来源
- [项目 theme 系统](../../superpowers/specs/2026-06-10-theme-system-design.md) — 颜色 token 与动画的搭配

---

**状态：** 🚧 部分完成（项目未引入 React Bits，本教程为选型评估 + 接入指南）