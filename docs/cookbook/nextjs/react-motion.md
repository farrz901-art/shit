# Motion 教程

> 📅 创建日期：2026-06-28
> 📁 项目代码引用：本教程以 `c:/doc/Code/rag` 仓库当前代码为准，所有引用标注 `file_path:line_number`
> 🏷️ 类别：L-语言/框架（React 动画库）
> 🎯 读者：中高级 TS 工程师，需要理解项目现有动画体系、能扩展 `<Reveal>`/`<Stagger>` 等封装组件

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

[Motion](https://motion.dev) 是一个为 React 设计的生产级动画库（原 framer-motion，v11 重命名）。提供声明式 API（`<motion.div>`）、物理弹簧（spring）、`AnimatePresence` 进出场、`useInView` 滚动触发、`layout` 自动 FLIP 布局动画。项目用 `motion` (^12.40.0) 作为动画引擎。

**同类对比：**

| 库 | 定位 | 本项目选择理由 |
|------|------|----------------|
| **Motion** | 物理弹簧 + 声明式 React 动画 | 10+ 封装组件已落地（`<Reveal>` `<Stagger>` `<CountUp>` `<Pressable>`），是项目动画的事实引擎 |
| **CSS animations** | 原生 keyframes + transition | 仅适用极简 `hover/active`，无法做进出场 / 物理 / 编排 |
| **GSAP** | 命令式动画库 | 商业项目免费版够用，能力远超 motion；但 API 命令式，跟 React 状态系统耦合需要 worktree |
| **React Spring** | 物理弹簧动画 | 概念跟 motion 重叠，生态略小，类型推断不如 motion |
| **react-transition-group** | 老牌 transition 包装 | 无弹簧物理，API 笨重 |
| **Auto-animate** | 自动布局动画 | 只做 FLIP，复杂编排力不从心 |

**Motion 解决的核心问题**：
- **声明式 API**：`<motion.div initial={...} animate={...} exit={...}>` — 状态驱动动画
- **物理弹簧**：`type: "spring"` 配置 `stiffness` / `damping`，比 CSS transition 更跟手
- **`AnimatePresence`**：组件卸载时播退场动画，CSS 做不到
- **`useInView` / `whileInView`**：滚动到视口时触发，跟 IntersectionObserver 同款
- **手势**：`whileHover` / `whileTap` / `whileDrag` 一行接管
- **`layout` 动画**：FLIP 算法自动过渡，列表重排无感知

---

## 二、安装 & 开发环境

### 2.1 安装

项目已装（[package.json:61](../../packages/web/package.json)）：

```json
{
  "motion": "^12.40.0"
}
```

如新项目引入：

```bash
bun add motion
# 旧版 framer-motion 已弃用, motion 是继任
```

### 2.2 版本演进

| 版本 | 关键变化 |
|------|----------|
| framer-motion v10 | 经典 API，`<motion.div>` + `AnimatePresence` |
| framer-motion v11 | 重命名为 motion，部分包重组 |
| motion v12 | 当前 LTS；`motion/react` 是 subpath import，跟 `motion/dom` / `motion/mini` 分离 |

项目用 `motion/react` subpath（见 [`reveal.tsx:6`](../../packages/web/components/motion/reveal.tsx#L6)），按 React 适配的入口。

---

## 三、基础语法 & 类型系统

### 3.1 `motion.div` 替代 `div`

```tsx
import { motion } from "motion/react";

// 普通 div
<div>Hello</div>

// 动画 div
<motion.div
  initial={{ opacity: 0 }}      // 起始状态
  animate={{ opacity: 1 }}      // 目标状态
  transition={{ duration: 0.5 }}
>
  Hello
</motion.div>
```

### 3.2 variant 模式（推荐）

```tsx
const fadeUp = {
  hidden: { opacity: 0, y: 12 },
  show: { opacity: 1, y: 0, transition: { duration: 0.7, ease: [0.16, 1, 0.3, 1] } },
} as const;

<motion.div variants={fadeUp} initial="hidden" animate="show">Hello</motion.div>
```

项目用 variant 模式封装（见 [`lib/motion.ts:56-65`](../../packages/web/lib/motion.ts#L56-L65)）。

### 3.3 AnimatePresence 进出场

```tsx
import { AnimatePresence, motion } from "motion/react";

<AnimatePresence>
  {show && (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}                // 卸载时触发
    >
      内容
    </motion.div>
  )}
</AnimatePresence>
```

### 3.4 `whileInView` 滚动触发

```tsx
<motion.div
  initial={{ opacity: 0, y: 12 }}
  whileInView={{ opacity: 1, y: 0 }}
  viewport={{ margin: "-5%", once: true }}   // 提前 5% 触发，只播一次
  transition={{ duration: 0.7 }}
>
  内容
</motion.div>
```

`<Reveal>` 组件（[`reveal.tsx:11-38`](../../packages/web/components/motion/reveal.tsx#L11-L38)）就是这模式。

### 3.5 类型继承

```tsx
import { type HTMLMotionProps, motion } from "motion/react";

interface RevealProps extends HTMLMotionProps<"div"> {
  delay?: number;
}

const Reveal = (props: RevealProps) => <motion.div {...props} />;
// Reveal 自动获得 onAnimationStart, layout, transition, style 等 motion 类型
```

---

## 四、核心概念

### 4.1 spring vs tween

```tsx
transition: {
  type: "spring",
  stiffness: 300,    // 弹簧刚度
  damping: 24,       // 阻尼
  mass: 1,           // 质量
}

transition: {
  type: "tween",
  duration: 0.4,
  ease: [0.16, 1, 0.3, 1],   // cubic-bezier 控制点
}
```

| 类型 | 适用 |
|------|------|
| `spring` | hover/tap 跟手反馈、CountUp 数字弹动 |
| `tween` | 入场动画、状态过渡、有明确 duration |

项目 `SPRING.snappy`（[`lib/motion.ts:98`](../../packages/web/lib/motion.ts#L98)）和 `SPRING.soft`（[`lib/motion.ts:99`](../../packages/web/lib/motion.ts#L99)）封装两种 spring。

### 4.2 ease 函数

项目用 3 个 cubic-bezier 曲线（[`lib/motion.ts:11-15`](../../packages/web/lib/motion.ts#L11-L15)）：

| 名称 | 用途 | CSS 端 |
|------|------|--------|
| `EASE.inOutQuart` | 卡片过渡，匀速 | `--ease-in-out-quart` |
| `EASE.outExpo` | 入场，强减速感 | `--ease-out-expo` |
| `EASE.outQuint` | 退场，柔和减速 | — |

定义在单一来源，业务组件**禁止重新定义 cubic-bezier**。

### 4.3 时长 token

[`lib/motion.ts:44-50`](../../packages/web/lib/motion.ts#L44-L50)：

```ts
export const DUR = {
  countUp: 1.5,
  fast: 0.2,    // hover/tap
  normal: 0.4,  // 卡片
  reveal: 0.5,  // 容器 stagger
  slow: 0.7,    // 入场
};
```

### 4.4 位移 token

[`lib/motion.ts:133-140`](../../packages/web/lib/motion.ts#L133-L140)：

```ts
export const LIFT = {
  hover: 1,        // hover 微浮
  stagger: 4,      // 行级入场
  card: 8,         // settings card
  hero: 12,        // 默认 fadeUp
  heroLg: 16,      // 大动作
  slideTop: -4,    // 通知条
};
```

### 4.5 delay token

[`lib/motion.ts:153-162`](../../packages/web/lib/motion.ts#L153-L162)：

```ts
export const DELAY = {
  data: 0.3,
  detail: 0.35,
  empty: 0.25,
  heroStep1: 0.12,
  heroStep2: 0.15,
  heroStep3: 0.18,
  primary: 0.2,    // 最高频 (9 处)
  secondary: 0.1,
};
```

---

## 五、常用命令 & 工具链

### 5.1 Motion DevTools

```bash
bun add -d motion-devtools
```

浏览器装 [Motion Chrome DevTools](https://chrome.google.com/webstore/detail/motion-devtools) 可以可视化拖时间轴、调 spring 参数、查看 variant 树。

### 5.2 ESLint 配置

Motion 不需要额外插件，但项目已禁用 `id-length` 对 `x` / `y` 属性的限制（[`.oxlintrc.json:9`](../../packages/web/.oxlintrc.json#L9)）：

```json
{ "id-length": ["warn", { "exceptions": ["y", "x"] }] }
```

这是因为 `motion` 的 `x: 0`、`y: -1` 是高频属性，禁止单字母变量会到处 `eslint-disable`。

### 5.3 SSR / RSC

`motion/react` 标记 `"use client"`，不能在 RSC 直接用。RSC 页面调客户端 motion 组件的方式：

```tsx
// app/page.tsx (RSC)
import { Reveal } from "@/components/motion/reveal";  // 客户端组件

export default async function Page() {
  return (
    <Reveal>
      <h1>Hello</h1>
    </Reveal>
  );
}
```

`<Reveal>` 内部 `"use client"`，SSR 阶段会保留 `initial={false}` 终态，避免 hydration mismatch。

---

## 六、项目集成点

### 6.1 封装组件目录

[`packages/web/components/motion/`](../../packages/web/components/motion/) — 13 个动画原子组件：

| 组件 | 用途 | 文件 |
|------|------|------|
| `<Reveal>` | 滚动入场容器 | [`reveal.tsx`](../../packages/web/components/motion/reveal.tsx) |
| `<Stagger>` + `<StaggerItem>` | 子项串行延迟入场 | [`stagger.tsx`](../../packages/web/components/motion/stagger.tsx) + [`stagger-item.tsx`](../../packages/web/components/motion/stagger-item.tsx) |
| `<FadeUp>` | 条件渲染入场（无 exit） | [`fade-up.tsx`](../../packages/web/components/motion/fade-up.tsx) |
| `<AnimateUp>` | 条件渲染带 exit 退场 | [`animate-up.tsx`](../../packages/web/components/motion/animate-up.tsx) |
| `<FadePresence>` | AnimatePresence 模式封装 | [`fade-presence.tsx`](../../packages/web/components/motion/fade-presence.tsx) |
| `<Pressable>` | 按钮 hover + tap 反馈 | [`pressable.tsx`](../../packages/web/components/motion/pressable.tsx) |
| `<HoverLift>` | 卡片 hover 浮起 | [`hover-lift.tsx`](../../packages/web/components/motion/hover-lift.tsx) |
| `<ButtonLift>` | 按钮轻反馈 | [`button-lift.tsx`](../../packages/web/components/motion/button-lift.tsx) |
| `<Pulse>` | 加载呼吸 | [`pulse.tsx`](../../packages/web/components/motion/pulse.tsx) |
| `<CountUp>` | 数字弹动 | [`count-up.tsx`](../../packages/web/components/motion/count-up.tsx) |
| `<Animated>` | barrel re-export | [`animated.tsx`](../../packages/web/components/motion/animated.tsx) |
| `useReducedMotionSafe` | a11y reduce-motion 探测 | `use-reduced-motion-safe.ts` |

### 6.2 设计 token 单一来源

[`packages/web/lib/motion.ts`](../../packages/web/lib/motion.ts) — 全局 token：
- `EASE` / `CSS_EASE` / `CSS_EASE_STR` — 缓动函数 3 套表达（motion array / cubic-bezier array / CSS string）
- `DUR` — 5 档时长
- `LIFT` — 6 档位移
- `DELAY` — 8 档延迟
- `SPRING` — 2 档 spring 配置
- `PRESS` — 2 档按压缩放
- `STAGGER_STEP` — 行/chunk 步进
- `VIEWPORT_MARGIN` — 视口边距
- `TRANSITION_*` — 3 套 transition 模板

业务组件**必须**从这里 import，禁止硬编码 `0.4`、`[0.16, 1, 0.3, 1]` 之类的数字。

### 6.3 a11y (reduce-motion)

项目支持 `prefers-reduced-motion` 系统设置。`<MotionConfig reducedMotion="user">` 在 root layout 设置（具体见布局文件），所有组件的 reduce 行为通过 `useReducedMotionSafe` hook 控制：

| 组件 | reduce 行为 | 文件 |
|------|-------------|------|
| `<Reveal>` | `initial={false}` 直接终态 | [`reveal.tsx:29`](../../packages/web/components/motion/reveal.tsx#L29) |
| `<Stagger>` | `staggerChildren: 0` 全部同时显示 | [`stagger.tsx:28`](../../packages/web/components/motion/stagger.tsx#L28) |
| `<StaggerItem>` | `initial={false}` | [`stagger-item.tsx:34`](../../packages/web/components/motion/stagger-item.tsx#L34) |
| `<FadeUp>` | `initial={false}` | [`fade-up.tsx:30`](../../packages/web/components/motion/fade-up.tsx#L30) |
| `<AnimateUp>` | `initial={false}` + `exit={opacity: 1}` | [`animate-up.tsx:35-36`](../../packages/web/components/motion/animate-up.tsx#L35-L36) |
| `<HoverLift>` | CSS shadow 替代 transform | [`hover-lift.tsx:26`](../../packages/web/components/motion/hover-lift.tsx#L26) |
| `<Pressable>` | whileHover/whileTap 取消 | [`pressable.tsx:31-33`](../../packages/web/components/motion/pressable.tsx#L31-L33) |
| `<Pulse>` | 渲染纯 span 不动 | [`pulse.tsx:15-17`](../../packages/web/components/motion/pulse.tsx#L15-L17) |
| `<CountUp>` | spring duration: 0 瞬时跳终值 | [`count-up.tsx:32`](../../packages/web/components/motion/count-up.tsx#L32) |

> 来源 spec：[`docs/superpowers/specs/2026-06-28-motion-a11y-refactor.md`](../../superpowers/specs/2026-06-28-motion-a11y-refactor.md)（如存在）

---

## 七、项目代码示例

### 7.1 列表 stagger 入场

```tsx
import { Stagger } from "@/components/motion/stagger";
import { StaggerItem } from "@/components/motion/stagger-item";

<Stagger className="space-y-4">
  {items.map((item) => (
    <StaggerItem key={item.id} variant="fadeUp">
      <Card>{item.title}</Card>
    </StaggerItem>
  ))}
</Stagger>
```

来源：[`stagger.tsx:14-40`](../../packages/web/components/motion/stagger.tsx#L14-L40)、[`stagger-item.tsx:19-38`](../../packages/web/components/motion/stagger-item.tsx#L19-L38)

### 7.2 滚动触发 hero 动画

```tsx
import { Reveal } from "@/components/motion/reveal";

<Reveal as="section" className="py-24">
  <h1>Welcome</h1>
</Reveal>
```

来源：[`reveal.tsx:11-38`](../../packages/web/components/motion/reveal.tsx#L11-L38)

### 7.3 数字弹动

```tsx
import { CountUp } from "@/components/motion/count-up";

<CountUp
  value={totalDocs}
  format={(n) => n.toLocaleString("zh-CN")}
/>
```

来源：[`count-up.tsx:14-50`](../../packages/web/components/motion/count-up.tsx#L14-L50)

### 7.4 通知条 fade-in/out

```tsx
import { AnimateUp } from "@/components/motion/animate-up";

<AnimateUp show={isError} enterFromTop>
  <ErrorBanner>{error}</ErrorBanner>
</AnimateUp>
```

来源：[`animate-up.tsx:23-53`](../../packages/web/components/motion/animate-up.tsx#L23-L53)

### 7.5 按钮按压

```tsx
import { Pressable } from "@/components/motion/pressable";

<Pressable onClick={handleSubmit} disabled={isSubmitting}>
  <span>{isSubmitting ? "提交中…" : "提交"}</span>
</Pressable>
```

来源：[`pressable.tsx:24-49`](../../packages/web/components/motion/pressable.tsx#L24-L49)

### 7.6 自定义 variant（业务扩展）

```tsx
// app/some-page/_components/hero-block.tsx
"use client";
import { motion } from "motion/react";
import { fadeUp, LIFT, DUR, EASE, DELAY } from "@/lib/motion";

export const HeroBlock = ({ title }: { title: string }) => {
  return (
    <motion.div
      variants={fadeUp}
      initial="hidden"
      animate="show"
      transition={{ delay: DELAY.primary }}    // 0.2s, 单一 token 来源
    >
      <h1 className="text-display">{title}</h1>
    </motion.div>
  );
};
```

### 7.7 variants 工厂（参数化）

```tsx
// lib/motion.ts:88-91 已有 rowStagger 工厂
export const rowStagger = (delay = 0.02) => ({ ... });

// 业务用法: 表格行 stagger
{items.map((item, idx) => (
  <motion.div
    key={item.id}
    variants={rowStagger(idx * 0.02)}    // 0.02s 步进
    initial="hidden"
    animate="show"
  >
    {item.name}
  </motion.div>
))}
```

---

## 八、项目没用到的能力 / 进阶方向

### 8.1 `layout` 自动布局动画

```tsx
<motion.div layout>           // 自动 FLIP 过渡
  {isExpanded && <Panel />}
</motion.div>

// 列表重排
<motion.ul layout>             // 容器 FLIP
  {items.map((item) => (
    <motion.li key={item.id} layout>     // 每项也 FLIP
      {item.name}
    </motion.li>
  ))}
</motion.ul>
```

项目目前 `AnimatePresence` + 列表操作已有，但**没有用 `layout`**。适合以下场景：
- 侧边栏展开/收起
- 卡片网格重排
- Tab 切换 indicator 滑动

### 8.2 `whileDrag` + 拖拽

```tsx
const [items, setItems] = useState(initial);
const [dragging, setDragging] = useState<number | null>(null);

<Reorder.Group axis="y" values={items} onReorder={setItems}>
  {items.map((item) => (
    <Reorder.Item
      key={item.id}
      value={item}
      whileDrag={{ scale: 1.05, boxShadow: "0 8px 16px rgba(0,0,0,0.1)" }}
    >
      {item.name}
    </Reorder.Item>
  ))}
</Reorder.Group>
```

项目未用 `Reorder` — 表格拖拽排序场景（如 admin 角色优先级调整）可以引入。

### 8.3 `useScroll` / `useTransform` 滚动驱动

```tsx
import { useScroll, useTransform } from "motion/react";

const { scrollY } = useScroll();
const opacity = useTransform(scrollY, [0, 300], [1, 0]);
const scale = useTransform(scrollY, [0, 300], [1, 0.8]);

<motion.div style={{ opacity, scale }}>
  跟随滚动缩放
</motion.div>
```

适合 hero 视差、固定导航栏背景透明度切换。

### 8.4 `AnimatePresence` `mode="popLayout"`

```tsx
<AnimatePresence mode="popLayout">
  {items.map((item) => (
    <motion.div
      key={item.id}
      initial={{ opacity: 0, scale: 0.8 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 0.8 }}
      layout                  // 配合 popLayout, 重排更顺滑
    >
      {item.name}
    </motion.div>
  ))}
</AnimatePresence>
```

`<FadePresence>` 组件（[`fade-presence.tsx`](../../packages/web/components/motion/fade-presence.tsx)）已封装 `mode="wait"`，但没封装 `mode="popLayout"`。动态列表删除时 `popLayout` 更顺滑。

### 8.5 `MotionConfig` 全局配置

```tsx
// app/layout.tsx
import { MotionConfig } from "motion/react";

<MotionConfig
  reducedMotion="user"           // 尊重系统设置
  transition={{ duration: 0.4 }} // 全局默认 transition
>
  {children}
</MotionConfig>
```

`reducedMotion="user"` 让所有 `useReducedMotionSafe()` 自动读到系统偏好。

### 8.6 手势（pan / pinch / rotate）

```tsx
<motion.div
  drag                                       // 拖拽
  dragConstraints={{ left: 0, right: 100 }}  // 边界
  dragElastic={0.2}                          // 弹性
  onDragEnd={(e, info) => console.log(info.offset.x, info.velocity.x)}
>
  拖我
</motion.div>
```

适合可拖拽看板、画布、地图标记。

### 8.7 `layoutId` 共享布局

```tsx
const [selected, setSelected] = useState<string | null>(null);

{items.map((item) => (
  <motion.div
    key={item.id}
    layoutId={`card-${item.id}`}
    onClick={() => setSelected(item.id)}
  >
    {item.name}
  </motion.div>
))}

{selected && (
  <motion.div layoutId={`card-${selected}`}>
    详情
  </motion.div>
)}
```

适合 card → detail 的过渡动画（Apple Music 风格）。

---

## 九、最佳实践 & 常见坑

### 9.1 动画 token 必须用 lib/motion.ts

```tsx
// ❌ 错: 硬编码数字
transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}

// ✅ 对: 用 token
transition={TRANSITION_QUICK_OUTEXPO}
```

### 9.2 避免重复定义 variants

```tsx
// ❌ 错: 每个文件重复 fadeUp
const fadeUp = { hidden: { opacity: 0, y: 12 }, show: { ... } };

// ✅ 对: 从 lib/motion.ts import
import { fadeUp } from "@/lib/motion";
```

### 9.3 不在 JSX 内联复杂 transition

```tsx
// ❌ 错: transition={...复杂对象}
<motion.div transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1], type: "spring", stiffness: 200 }}>
  ...
</motion.div>

// ✅ 对: 提取常量或 token
<motion.div transition={TRANSITION_REVEAL_OUTEXPO}>
  ...
</motion.div>
```

### 9.4 RSC 不能用 motion

```tsx
// ❌ 错: page.tsx (默认 RSC) 直接用 motion
export default async function Page() {
  return <motion.div animate={{ opacity: 1 }}>...</motion.div>;  // 报错
}

// ✅ 对: 用项目封装组件 (内部已 "use client")
import { Reveal } from "@/components/motion/reveal";
export default async function Page() {
  return <Reveal>...</Reveal>;
}
```

### 9.5 initial={false} 谨慎使用

```tsx
// 初始不动画, 直接终态 — 用于 SSR 时避免 hydration mismatch
<motion.div initial={false} animate={{ opacity: 1 }}>...</motion.div>

// 但: 客户端首次 mount 不会触发入场动画
// 项目用 reduce-motion 时才用 initial={false} (a11y 模式)
```

### 9.6 AnimatePresence 必须有 key

```tsx
// ❌ 错: 子项无 key, 退场动画不会触发
<AnimatePresence>
  {show && <motion.div animate={{ opacity: 1 }}>...</motion.div>}
</AnimatePresence>

// ✅ 对: 加 key
<AnimatePresence>
  {show && <motion.div key="feedback" animate={{ opacity: 1 }}>...</motion.div>}
</AnimatePresence>
```

### 9.7 spring 数字参数不要硬编码

```tsx
// ❌ 错: 直接写 spring 参数
transition={{ type: "spring", stiffness: 400, damping: 22 }}

// ✅ 对: 用 SPRING token
import { SPRING } from "@/lib/motion";
transition={SPRING.snappy}    // damping: 22, stiffness: 400
```

### 9.8 `whileHover` 用 transform，不要用 layout 属性

```tsx
// ❌ 错: whileHover 改 width/height (触发回流, 卡)
whileHover={{ width: 200 }}

// ✅ 对: whileHover 改 transform (GPU 加速)
whileHover={{ scale: 1.05, y: -4 }}
```

### 9.9 不在 framer-motion 已经禁止的 path 用

```tsx
// ❌ 错: 用 motion 在 layout 计算时 (引发循环动画)
<motion.div animate={{ x: someCalc }}>...</motion.div>

// ✅ 对: 用 useTransform 派生, 不参与 layout
const x = useTransform(scrollY, [0, 100], [0, 50]);
<motion.div style={{ x }}>...</motion.div>
```

### 9.10 测试时 mock motion

```typescript
// 跟项目 mock lucide-react 同模式
vi.mock("motion/react", async (importOriginal) => ({
  ...(await importOriginal<typeof import("motion/react")>()),
  useInView: vi.fn().mockReturnValue(true),    // 强制 inView=true 触发入场
}));
```

来源：[`components/auth/auth-bootstrap.test.tsx:25`](../../packages/web/components/auth/auth-bootstrap.test.tsx#L25) 类似模式

### 9.11 版本兼容

- motion v12.x 是当前 LTS
- 避免 framer-motion v6/7/8 旧 API (`useAnimation`, `cycle`, `animate.presence` 风格已变)
- 锁版本：`"motion": "12.x"`

### 9.12 Bundle size

motion 全量 ~50KB gzip。项目用了 13 个封装组件，建议：
- 已经按需使用 `<Reveal>` 等封装，不要直接 import `motion.div`
- 避免一次页面 import 多个独立 `motion` 子模块
- 如需极致优化，可以 `bun add motion-mini`（5KB，但损失 spring/layout）

---

## 📚 参考

- [Motion 官方文档](https://motion.dev/docs/react-quick-start)
- [Motion + React](https://motion.dev/docs/react-motion-component)
- [AnimatePresence](https://motion.dev/docs/react-animate-presence)
- [Layout animation](https://motion.dev/docs/react-layout-animations)
- [Variants](https://motion.dev/docs/react-variants)
- [项目 motion-a11y-refactor spec](../../superpowers/specs/2026-06-28-motion-a11y-refactor.md)
- [项目 `lib/motion.ts`](../../packages/web/lib/motion.ts) — 动画 token 单一来源
- [项目 `components/motion/`](../../packages/web/components/motion/) — 13 个封装组件

---

**状态：** ✅ 已完成（项目主力，13 组件 + 完整 token 体系 + reduce-motion a11y）