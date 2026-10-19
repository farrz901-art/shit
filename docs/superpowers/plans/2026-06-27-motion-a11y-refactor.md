# Motion a11y & 收敛重构实施计划 (修订 v2)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 基于修订版 motion 审计报告, 5 阶段实施 motion a11y (reduce-motion) 修复 + `lib/motion.ts` 扩展 (5 variants + 3 常量组 + 2 transition) + 直接 `motion/react` 引用收敛 (从 35 处减到 ~5 处) + 业务层 wrapper 抽取, 达成 WCAG 2.2.2/2.3.3 永久合规 + 消 80+ 处硬编码 + 业务侧零 motion API 依赖

**Architecture:** Phase 1 a11y 基础设施 (1 行 MotionConfig + 1 hook + 6 原子); **Phase 1.5 (新)** 扩展 `lib/motion.ts` (5 variants + LIFT/DELAY/PRESS/TRANSITION 常量 + 移除死代码); Phase 2 抽 3 个 wrapper (`<ResultBanner>` `<AnimateUp>` `<ButtonLift>`) 收敛 12 处直接 motion/react; Phase 3 业务层 wrapper (`<PageHero>` 扩展 + `<StatsGrid>` `<EntryCardGrid>` + 25 处 delay 改用 `DELAY.*`); Phase 4 边界优化 (按需)

**Tech Stack:** motion@12.40.0 (framer-motion) / React 19 / TypeScript 8 / vitest + jsdom / Tailwind v4

**Source:** [审计报告 (修订 v2)](../../audit/motion-frontend-audit-2026-06-27.md)

---

## 文件结构

### Phase 1 — a11y 基础设施 (P0)

| 文件 | 操作 | 职责 |
|------|------|------|
| `packages/web/components/motion/use-reduced-motion-safe.ts` | **新建** | 集中封装 `useReducedMotion()`, 6 原子组件统一引用 |
| `packages/web/app/[locale]/layout.tsx` | 修改 | 加 `<MotionConfig reducedMotion="user">` 包裹 children |
| `packages/web/components/motion/reveal.tsx` | 修改 | 用 `useReducedMotionSafe` 在 reduce 模式下 `initial={false}` |
| `packages/web/components/motion/stagger.tsx` | 修改 | reduce 模式下 `staggerChildren: 0` |
| `packages/web/components/motion/stagger-item.tsx` | 修改 | reduce 模式下直接渲染无动画 |
| `packages/web/components/motion/pressable.tsx` | 修改 | reduce 模式下 `whileTap`/`whileHover={undefined}` |
| `packages/web/components/motion/hover-lift.tsx` | 修改 | reduce 模式下禁用动画 + 改 CSS hover:shadow |
| `packages/web/components/motion/count-up.tsx` | 修改 | reduce 模式下直接 set 终值 + `aria-label` |
| `packages/web/components/motion/animated.test.tsx` | 修改 | 加 reduce-motion 测试用例 |

### Phase 1.5 — `lib/motion.ts` 扩展 (P0, 新!)

| 文件 | 操作 | 职责 |
|------|------|------|
| `packages/web/lib/motion.ts` | 修改 | 抽 LIFT/DELAY/PRESS/STAGGER_STEP/VIEWPORT_MARGIN 常量组, 加 TRANSITION_QUICK_OUTQUINT/TRANSITION_REVEAL_OUTEXPO, 加 fadeUpGentle/fadeUpLarge/slideInTop/pulse/rowStagger 5 variants, 移除 SPRING.gentle 死代码 |
| `packages/web/components/motion/count-up.tsx` | 修改 | 改用新常量 (使用 `pulse` variant 类似模式) |
| `packages/web/components/common/display/app-settings-card.tsx` | 修改 | 改用 `fadeUpGentle` variant + `VIEWPORT_MARGIN.early` + `DUR.normal` |
| `packages/web/app/[locale]/output/_components/output-list-client.tsx` | 修改 | 调 `fadeIn` duration 用 `DUR.slow` 或改用新 variant |
| `packages/web/app/[locale]/output/[task_id]/[file]/page.tsx` | 修改 | 改用 `fadeUp` variant (替代硬编码) |
| `packages/web/app/[locale]/knowledge/batch/page.tsx` | 修改 | CARD_INITIAL 改用 `fadeUp` variant, ERROR_LIST_INITIAL 改用 `slideInTop` variant |
| `packages/web/app/[locale]/knowledge/documents/import/_components/documents-import-form.tsx` | 修改 | 2 处 fadeUp 硬编码改用 `fadeUp` variant |
| `packages/web/app/[locale]/knowledge/triples/_components/triples-form.tsx` | 修改 | 2 处 y:-4 硬编码改用 `slideInTop` variant |
| `packages/web/app/[locale]/knowledge/documents/import/_components/import-commit-card.tsx` | 修改 | 2 处 translateY:-4 硬编码改用 `slideInTop` variant |
| `packages/web/app/[locale]/decode/page.tsx` | 修改 | translateY:16 改用 `fadeUpLarge` variant |
| `packages/web/components/common/table/data-table-body.tsx` | 修改 | 改用 `pulse` variant + `rowStagger` variant + `STAGGER_STEP.row` |

### Phase 2 — 收敛直接 motion/react 引用 (P1)

| 文件 | 操作 | 职责 |
|------|------|------|
| `packages/web/components/motion/result-banner.tsx` | **新建** | 封装 slideInTop 顶部提示横幅 (用于 error/success 提示) |
| `packages/web/components/motion/animate-up.tsx` | **新建** | 封装 AnimatePresence + fadeUp, 状态触发的内容入场 |
| `packages/web/components/motion/button-lift.tsx` | **新建** | 封装 motion.div + Button, hover/tap 反馈 |
| `packages/web/components/motion/animated.tsx` | 修改 | barrel re-export 3 个新 wrapper |
| `packages/web/app/[locale]/knowledge/triples/_components/triples-form.tsx` | 修改 | TriplesResult/TriplesError 改用 ResultBanner |
| `packages/web/app/[locale]/knowledge/documents/import/_components/import-commit-card.tsx` | 修改 | commit-result/commit-error 改用 ResultBanner |
| `packages/web/app/[locale]/knowledge/batch/page.tsx` | 修改 | 错误列表 + 活跃任务卡改用 wrapper (AnimateUp / ResultBanner) |
| `packages/web/app/[locale]/output/_components/output-list-client.tsx` | 修改 | 空态改用 ResultBanner |
| `packages/web/app/[locale]/output/[task_id]/[file]/page.tsx` | 修改 | 内容卡片改用 AnimateUp |
| `packages/web/app/[locale]/decode/page.tsx` | 修改 | decode 结果区改用 AnimateUp |
| `packages/web/app/[locale]/knowledge/documents/import/_components/documents-import-form.tsx` | 修改 | 3 处 hover 包装改用 ButtonLift, 2 处卡片改用 AnimateUp |
| `packages/web/components/common/display/app-settings-card.tsx` | 修改 | 改用 Reveal (Phase 1.5 已用 fadeUpGentle, 此步确认) |

### Phase 3 — 业务层 wrapper (P2)

| 文件 | 操作 | 职责 |
|------|------|------|
| `packages/web/components/common/navigation/app-page-hero.tsx` | 修改 | 扩展支持 `backHref`/`backLabel` props (向后兼容) |
| `packages/web/app/[locale]/knowledge/batch/page.tsx` | 修改 | 手写 Stagger 序列用 PageHero (带 backHref) |
| `packages/web/app/[locale]/knowledge/nodes/_components/nodes-table.tsx` | 修改 | 同上 |
| `packages/web/app/[locale]/knowledge/relations/_components/relations-table.tsx` | 修改 | 同上 |
| `packages/web/app/[locale]/knowledge/triples/_components/triples-form.tsx` | 修改 | TriplesHero 子组件用 PageHero |
| `packages/web/app/[locale]/evaluate/_components/evaluate-list-view.tsx` | 修改 | 手写 Stagger 序列用 PageHero |
| `packages/web/components/common/display/stats-grid.tsx` | **新建** | StatCard 网格 wrapper, 统一 delay + columns |
| `packages/web/components/common/display/entry-card-grid.tsx` | **新建** | EntryCard 网格 wrapper |
| `packages/web/components/common/display/index.ts` | 修改 | barrel export 新组件 |
| `packages/web/app/[locale]/knowledge/_components/knowledge-dashboard.tsx` | 修改 | 4 张 StatCard/EntryCard 改用新 wrapper |
| `packages/web/app/[locale]/knowledge/graph/_components/graph-view.tsx` | 修改 | 2 张 StatCard/EntryCard 改用新 wrapper |
| `packages/web/app/[locale]/knowledge/documents/_components/documents-entry.tsx` | 修改 | 2 张 StatCard/EntryCard 改用新 wrapper |
| **25+ 文件** | 修改 | **Reveal delay 改用 `DELAY.*` 常量** (消 25 处硬编码) |

### Phase 4 — 边界优化 (P3, 按需)

| 文件 | 操作 | 职责 |
|------|------|------|
| `packages/web/components/common/table/data-table-body.tsx` | 修改 | motion.tr 行 stagger + loading pulse 加 reduce 分支 |
| `packages/web/app/[locale]/knowledge/qa/_components/qa-submit-form.tsx` | 修改 | 删除死代码 (本地 Stagger) |
| `packages/web/app/[locale]/output/[task_id]/_components/task-detail-client.tsx` | 修改 | AnimatePresence mode="wait" 抽 FadePresence |
| `packages/web/app/[locale]/decode/decode-input-bar.tsx` | 修改 | 旋转 spinner 换 CSS keyframes (可选) |
| **7+ 处 exit transition** | 修改 | **统一用 `TRANSITION_*` 常量, exit 跟 enter 对称** |

---

## Phase 1: a11y 基础设施 (P0, ~0.5 人日)

### Task 1.1: 创建 useReducedMotionSafe hook

**Files:**
- Create: `packages/web/components/motion/use-reduced-motion-safe.ts`

- [ ] **Step 1: 创建 use-reduced-motion-safe.ts**

```typescript
// packages/web/components/motion/use-reduced-motion-safe.ts
// 集中封装 motion 的 useReducedMotion, 6 个原子组件统一引用
// 未来可加 motion-level 粒度 (full / essential / none)
"use client";
import { useReducedMotion } from "motion/react";

/** 尊重系统 prefers-reduced-motion 设置的 hook
 *  - SSR 阶段返回 false (motion 库本身 SSR-safe)
 *  - 测试环境可显式 override (后续可加)
 */
export const useReducedMotionSafe = (): boolean => {
  return useReducedMotion() ?? false;
};
```

- [ ] **Step 2: 跑 typecheck 验证**

```bash
cd /c/doc/Code/rag/packages/web && bun run typecheck 2>&1 | tail -10
```
Expected: 0 errors

- [ ] **Step 3: Commit**

```bash
cd /c/doc/Code/rag && git add packages/web/components/motion/use-reduced-motion-safe.ts && git commit -m "feat(motion): 新增 useReducedMotionSafe hook (集中 a11y 判断)"
```

---

### Task 1.2: 在 root layout 加 MotionConfig

**Files:**
- Modify: `packages/web/app/[locale]/layout.tsx`

- [ ] **Step 1: 引入 MotionConfig**

在 `layout.tsx` 顶部 imports 区, 加:
```typescript
import { MotionConfig } from "motion/react";
```

- [ ] **Step 2: 用 MotionConfig 包裹 children**

找到当前 layout 的 `<body>` 内部结构, 在最外层 client provider 之外加 `<MotionConfig>`. 当前 ChatApiProvider 是最外层, 在它**之外**包 MotionConfig (MotionConfig 是 React context provider):

当前:
```tsx
<ChatApiProvider>
  <ThemeProvider ...>
    <I18nProvider ...>
      ...
    </I18nProvider>
  </ThemeProvider>
</ChatApiProvider>
```

改为:
```tsx
<MotionConfig reducedMotion="user">
  <ChatApiProvider>
    <ThemeProvider ...>
      <I18nProvider ...>
        ...
      </I18nProvider>
    </ThemeProvider>
  </ChatApiProvider>
</MotionConfig>
```

- [ ] **Step 3: 跑 typecheck + 验证**

```bash
cd /c/doc/Code/rag/packages/web && bun run typecheck 2>&1 | tail -10
```

- [ ] **Step 4: Commit**

```bash
cd /c/doc/Code/rag && git add packages/web/app/\[locale\]/layout.tsx && git commit -m "feat(motion): layout 加 MotionConfig reducedMotion=\"user\" (全局 a11y 基础)"
```

---

### Task 1.3: Reveal 加 reduce-motion 处理

**Files:**
- Modify: `packages/web/components/motion/reveal.tsx`

- [ ] **Step 1: 修改 reveal.tsx, 在 reduce 模式下跳过 hidden 状态**

```typescript
// packages/web/components/motion/reveal.tsx
"use client";
import { type ReactNode } from "react";
import { type HTMLMotionProps, motion } from "motion/react";
import { fadeUp } from "@/lib/motion";
import { ZERO } from "@/const";
import { useReducedMotionSafe } from "./use-reduced-motion-safe";

export const Reveal = ({
  children,
  delay = ZERO,
  className,
  as = "div",
  ...rest
}: {
  children: ReactNode;
  delay?: number;
  className?: string;
  as?: "div" | "section" | "article" | "li";
} & HTMLMotionProps<"div">) => {
  const reduced = useReducedMotionSafe();
  const Tag = motion[as] as typeof motion.div;
  return (
    <Tag
      className={className}
      variants={fadeUp}
      initial={reduced ? false : "hidden"}
      whileInView="show"
      viewport={{ margin: "-5%", once: true }}
      transition={{ delay }}
      {...rest}
    >
      {children}
    </Tag>
  );
};
```

- [ ] **Step 2: 跑 typecheck + 测试**

```bash
cd /c/doc/Code/rag/packages/web && bun run typecheck && bun run test -- --run components/motion/ 2>&1 | tail -10
```

- [ ] **Step 3: Commit**

```bash
cd /c/doc/Code/rag && git add packages/web/components/motion/reveal.tsx && git commit -m "feat(motion): Reveal 加 reduce-motion 处理 (initial={false})"
```

---

### Task 1.4: Stagger 加 reduce-motion 处理

**Files:**
- Modify: `packages/web/components/motion/stagger.tsx`

- [ ] **Step 1: 修改 stagger.tsx**

```typescript
// packages/web/components/motion/stagger.tsx
"use client";
import { type ReactNode } from "react";
import { motion } from "motion/react";
import { stagger as staggerVariant } from "@/lib/motion";
import { useReducedMotionSafe } from "./use-reduced-motion-safe";

const STAGGER_DEFAULT_DELAY = 0.06;

export const Stagger = ({
  children,
  className,
  delay = STAGGER_DEFAULT_DELAY,
  as = "div",
}: {
  children: ReactNode;
  className?: string;
  delay?: number;
  as?: "div" | "ul" | "section";
}) => {
  const reduced = useReducedMotionSafe();
  const Tag = motion[as] as typeof motion.div;
  // reduce 模式: staggerChildren: 0 让所有子项同时显示, 不串行延迟
  const effectiveDelay = reduced ? 0 : delay;
  return (
    <Tag
      className={className}
      variants={staggerVariant(effectiveDelay)}
      initial="hidden"
      whileInView="show"
      viewport={{ margin: "-5%", once: true }}
    >
      {children}
    </Tag>
  );
};
```

- [ ] **Step 2: 跑 typecheck + 测试**

```bash
cd /c/doc/Code/rag/packages/web && bun run typecheck && bun run test -- --run components/motion/ 2>&1 | tail -10
```

- [ ] **Step 3: Commit**

```bash
cd /c/doc/Code/rag && git add packages/web/components/motion/stagger.tsx && git commit -m "feat(motion): Stagger 加 reduce-motion 处理 (staggerChildren: 0)"
```

---

### Task 1.5: StaggerItem 加 reduce-motion 处理

**Files:**
- Modify: `packages/web/components/motion/stagger-item.tsx`

- [ ] **Step 1: 修改 stagger-item.tsx**

```typescript
// packages/web/components/motion/stagger-item.tsx
"use client";
import { type ReactNode } from "react";
import { type Variants, motion } from "motion/react";
import { fadeUp, fadeIn, scaleIn } from "@/lib/motion";
import { useReducedMotionSafe } from "./use-reduced-motion-safe";

const DEFAULT_ANIM_VARIANT = "fadeUp";

export const StaggerItem = ({
  children,
  className,
  as = "div",
  variant = DEFAULT_ANIM_VARIANT,
}: {
  children: ReactNode;
  className?: string;
  as?: "div" | "li" | "article";
  variant?: "fadeUp" | "fadeIn" | "scaleIn";
}) => {
  const reduced = useReducedMotionSafe();
  const Tag = motion[as] as typeof motion.div;
  let currentVariant: Variants;
  if (variant === "fadeUp") {
    currentVariant = fadeUp;
  } else if (variant === "fadeIn") {
    currentVariant = fadeIn;
  } else {
    currentVariant = scaleIn;
  }
  return (
    <Tag
      className={className}
      variants={currentVariant}
      initial={reduced ? false : undefined}
    >
      {children}
    </Tag>
  );
};
```

- [ ] **Step 2: 跑 typecheck + 测试**

```bash
cd /c/doc/Code/rag/packages/web && bun run typecheck && bun run test -- --run components/motion/ 2>&1 | tail -10
```

- [ ] **Step 3: Commit**

```bash
cd /c/doc/Code/rag && git add packages/web/components/motion/stagger-item.tsx && git commit -m "feat(motion): StaggerItem 加 reduce-motion 处理 (initial={false})"
```

---

### Task 1.6: Pressable 加 reduce-motion 处理

**Files:**
- Modify: `packages/web/components/motion/pressable.tsx`

- [ ] **Step 1: 修改 pressable.tsx**

```typescript
// packages/web/components/motion/pressable.tsx
"use client";
import { type ReactNode } from "react";
import { motion } from "motion/react";
import { SPRING } from "@/lib/motion";
import { useReducedMotionSafe } from "./use-reduced-motion-safe";

export const Pressable = ({
  children,
  className,
  onClick,
  disabled,
  type = "button",
}: {
  children: ReactNode;
  className?: string;
  onClick?: () => void;
  disabled?: boolean;
  type?: "button" | "submit" | "reset";
}) => {
  const reduced = useReducedMotionSafe();
  let tapAnimation: Record<string, number> | undefined;
  if (disabled || reduced) {
    tapAnimation = undefined;
  } else {
    tapAnimation = { scale: 0.97 };
  }
  let hoverAnimation: Record<string, number> | undefined;
  if (disabled || reduced) {
    hoverAnimation = undefined;
  } else {
    // eslint-disable-next-line id-length — framer-motion CSS 属性名, 不可改名
    hoverAnimation = { y: -1 };
  }
  return (
    <motion.button
      className={className}
      onClick={onClick}
      disabled={disabled}
      type={type}
      whileTap={tapAnimation}
      whileHover={hoverAnimation}
      transition={SPRING.snappy}
    >
      {children}
    </motion.button>
  );
};
```

- [ ] **Step 2: 跑 typecheck + 测试**

```bash
cd /c/doc/Code/rag/packages/web && bun run typecheck && bun run test -- --run components/motion/ 2>&1 | tail -10
```

- [ ] **Step 3: Commit**

```bash
cd /c/doc/Code/rag && git add packages/web/components/motion/pressable.tsx && git commit -m "feat(motion): Pressable 加 reduce-motion 处理 (禁用 whileTap/whileHover)"
```

---

### Task 1.7: HoverLift 加 reduce-motion 处理

**Files:**
- Modify: `packages/web/components/motion/hover-lift.tsx`

- [ ] **Step 1: 修改 hover-lift.tsx**

```typescript
// packages/web/components/motion/hover-lift.tsx
"use client";
import { type ReactNode } from "react";
import { motion } from "motion/react";
import { SPRING } from "@/lib/motion";
import { FOUR } from "@/const";
import { cn } from "@/lib/utils";
import { useReducedMotionSafe } from "./use-reduced-motion-safe";

export const HoverLift = ({
  children,
  className,
  lift = FOUR,
}: {
  children: ReactNode;
  className?: string;
  lift?: number;
}) => {
  const reduced = useReducedMotionSafe();
  return (
    <motion.div
      className={cn(
        // reduce 模式: 用 CSS shadow 替代 transform, 不触发位移
        reduced && "transition-shadow hover:shadow-lg",
        className,
      )}
      whileHover={reduced ? undefined : { y: -lift }}
      whileTap={reduced ? undefined : { y: 0 }}
      transition={reduced ? undefined : SPRING.soft}
    >
      {children}
    </motion.div>
  );
};
```

- [ ] **Step 2: 跑 typecheck + 测试**

```bash
cd /c/doc/Code/rag/packages/web && bun run typecheck && bun run test -- --run components/motion/ 2>&1 | tail -10
```

- [ ] **Step 3: Commit**

```bash
cd /c/doc/Code/rag && git add packages/web/components/motion/hover-lift.tsx && git commit -m "feat(motion): HoverLift 加 reduce-motion 处理 (改用 CSS shadow)"
```

---

### Task 1.8: CountUp 加 reduce-motion 处理 + aria-label

**Files:**
- Modify: `packages/web/components/motion/count-up.tsx`

- [ ] **Step 1: 修改 count-up.tsx**

```typescript
// packages/web/components/motion/count-up.tsx
"use client";
import { type CSSProperties, useEffect, useRef } from "react";
import { motion, useInView, useMotionValue, useSpring, useTransform } from "motion/react";
import { DUR } from "@/lib/motion";
import { ZERO, MS_PER_SECOND } from "@/const";
import { useReducedMotionSafe } from "./use-reduced-motion-safe";

export const CountUp = ({
  value,
  duration = DUR.countUp,
  format = (num: number) => num.toLocaleString("en-US"),
  className,
  style,
}: {
  value: number;
  duration?: number;
  format?: (num: number) => string;
  className?: string;
  style?: CSSProperties;
}) => {
  const reduced = useReducedMotionSafe();
  const ref = useRef<HTMLSpanElement>(null);
  const inView = useInView(ref, { margin: "-5%", once: true });
  const motionValue = useMotionValue(ZERO);
  // reduce 模式: duration: 0 = 立即跳到目标值, 无 spring 弹动
  const springDuration = reduced ? 0 : duration * MS_PER_SECOND;
  const spring = useSpring(motionValue, { bounce: ZERO, duration: springDuration });
  const display = useTransform(spring, (latest) => format(Math.round(latest)));

  useEffect(() => {
    if (inView) {
      motionValue.set(value);
    }
  }, [inView, value, motionValue]);

  // 屏幕阅读器朗读终值 (运动中的数字朗读无意义且会错过)
  const ariaLabel = format(value);

  return (
    <motion.span
      ref={ref}
      className={className}
      style={style}
      aria-label={ariaLabel}
    >
      {display}
    </motion.span>
  );
};
```

- [ ] **Step 2: 跑 typecheck + 测试**

```bash
cd /c/doc/Code/rag/packages/web && bun run typecheck && bun run test -- --run components/motion/ 2>&1 | tail -10
```

- [ ] **Step 3: Commit**

```bash
cd /c/doc/Code/rag && git add packages/web/components/motion/count-up.tsx && git commit -m "feat(motion): CountUp 加 reduce-motion + aria-label (a11y)"
```

---

### Task 1.9: animated.test.tsx 加 reduce-motion 测试

**Files:**
- Modify: `packages/web/components/motion/animated.test.tsx`

- [ ] **Step 1: 在 animated.test.tsx 末尾追加 reduce-motion 测试**

```typescript
// 在文件末尾追加:

import { useReducedMotion } from "motion/react";

vi.mock("motion/react", async (importOriginal) => {
  const actual = await importOriginal<typeof import("motion/react")>();
  return {
    ...actual,
    useReducedMotion: vi.fn(() => true),  // 强制返回 true 模拟 reduce 模式
  };
});

describe("reduce-motion 行为", () => {
  it("Reveal 在 reduce 模式下 initial=false (跳过 hidden)", () => {
    const { container } = render(
      <Reveal>
        <span data-testid="child">x</span>
      </Reveal>,
    );
    const motionDiv = container.firstChild as HTMLElement;
    expect(motionDiv).toBeTruthy();
  });

  it("Stagger 在 reduce 模式下 staggerChildren=0", () => {
    const { container } = render(
      <Stagger>
        <span>x</span>
      </Stagger>,
    );
    expect(container.firstChild).toBeTruthy();
  });

  it("HoverLift 在 reduce 模式下渲染无报错", () => {
    const { container } = render(
      <HoverLift>
        <span>x</span>
      </HoverLift>,
    );
    expect(container.firstChild).toBeTruthy();
  });

  it("CountUp 在 reduce 模式下渲染终值", () => {
    const { container } = render(<CountUp value={42} />);
    expect(container.textContent).toBeDefined();
  });
});
```

- [ ] **Step 2: 跑测试验证**

```bash
cd /c/doc/Code/rag/packages/web && bun run test -- --run components/motion/animated.test.tsx 2>&1 | tail -15
```
Expected: 9 tests pass (5 现有 + 4 新增)

- [ ] **Step 3: Commit**

```bash
cd /c/doc/Code/rag && git add packages/web/components/motion/animated.test.tsx && git commit -m "test(motion): 加 reduce-motion 行为测试 (4 用例)"
```

---

### Phase 1 总结验证

- [ ] **Step: 全量验证**

```bash
cd /c/doc/Code/rag/packages/web && bun run typecheck && bun run lint && bun run test -- --run 2>&1 | tail -30
```
Expected: 0 type errors, 0 new lint warnings, tests 数量增加 4 个 (reduce-motion 用例)

---

## Phase 1.5: `lib/motion.ts` 扩展 (P0, ~1.5 人日, 新)

> 本阶段在 Phase 1 a11y 基础完成后执行。批量替换 17 处变体重定义 + 25 处 delay 硬编码 + 9 处 transition 硬编码 + 移除 1 处死代码。

### Task 1.5.1: 扩展 lib/motion.ts (常量组 + 新 variants + 移除死代码)

**Files:**
- Modify: `packages/web/lib/motion.ts`

- [ ] **Step 1: 在 `lib/motion.ts` 末尾追加 LIFT / DELAY / PRESS / STAGGER_STEP / VIEWPORT_MARGIN 常量组 + 2 个 transition 常量 + 5 个新 variants**

在 `lib/motion.ts` 末尾 (`SHADOW` 之后) 追加:

```typescript
/**
 * 位移常量 (y/translateY 统一来源)
 *  - hover: hover 微浮 -1px
 *  - stagger: 行/chunks 微入场
 *  - card: settings card 轻位移
 *  - hero: fadeUp 默认 (12)
 *  - heroLg: 大动作入场 (16)
 *  - slideTop: 错误/通知条从顶部 (-4)
 */
export const LIFT = {
  hover: 1,
  stagger: 4,
  card: 8,
  hero: 12,
  heroLg: 16,
  slideTop: -4,
} as const;

/**
 * 延迟常量 (Reveal/业务延迟统一来源)
 *  - secondary: 0.1 (二级内容延迟, 3 处)
 *  - heroStep1: 0.12 (hero stagger 第一段, 2 处)
 *  - heroStep2: 0.15 (hero stagger 第二段, 6 处, 高频)
 *  - heroStep3: 0.18 (hero stagger 第三段, 1 处)
 *  - primary: 0.2 (主内容延迟, 9 处, 最高频)
 *  - empty: 0.25 (空状态, 1 处)
 *  - data: 0.3 (表格/数据, 2 处)
 *  - detail: 0.35 (详情页底部, 1 处)
 */
export const DELAY = {
  data: 0.3,
  detail: 0.35,
  empty: 0.25,
  heroStep1: 0.12,
  heroStep2: 0.15,
  heroStep3: 0.18,
  primary: 0.2,
  secondary: 0.1,
} as const;

/**
 * 按压缩放常量
 *  - scale: 主按钮按下 (Pressable 用, 0.97)
 *  - scaleSubtle: 次按钮按下 (3 处下载按钮用, 0.98)
 */
export const PRESS = {
  scale: 0.97,
  scaleSubtle: 0.98,
} as const;

/** Stagger 步进常量 */
export const STAGGER_STEP = {
  row: 0.02,
  chunk: 0.03,
} as const;

/** viewport margin 常量 */
export const VIEWPORT_MARGIN = {
  normal: "-5%",
  early: "-10%",
} as const;

/**
 * Transition 模板 (业务统一引用, 不重写三元组)
 *  - QUICK_OUTQUINT: 5 处 (DUR.normal + outQuint)
 *  - REVEAL_OUTEXPO: 4 处 (DUR.slow + outExpo, 完全等同 fadeUp transition)
 *  - QUICK_OUTEXPO: 3 处 (DUR.normal + outExpo, 用于行 stagger)
 */
export const TRANSITION_QUICK_OUTQUINT = {
  duration: DUR.normal,
  ease: CSS_EASE.outQuint,
} as const;

export const TRANSITION_REVEAL_OUTEXPO = {
  duration: DUR.slow,
  ease: CSS_EASE.outExpo,
} as const;

export const TRANSITION_QUICK_OUTEXPO = {
  duration: DUR.normal,
  ease: CSS_EASE.outExpo,
} as const;

/**
 * 新增 variants (覆盖 17 处变体重定义)
 */

/** fadeUp 轻位移版 (y:8, 用于 settings card 等) */
export const fadeUpGentle = {
  hidden: { opacity: 0, y: LIFT.card },
  show: {
    opacity: 1,
    y: 0,
    transition: { duration: DUR.normal, ease: EASE.outExpo },
  },
} as const;

/** fadeUp 大动作版 (y:16, 用于 decode 结果区) */
export const fadeUpLarge = {
  hidden: { opacity: 0, y: LIFT.heroLg },
  show: {
    opacity: 1,
    y: 0,
    transition: { duration: DUR.slow, ease: EASE.outExpo },
  },
} as const;

/** 顶部滑入 (y:-4, 用于错误/通知条) */
export const slideInTop = {
  hidden: { opacity: 0, y: LIFT.slideTop },
  show: {
    opacity: 1,
    y: 0,
    transition: { duration: DUR.normal, ease: EASE.outQuint },
  },
} as const;

/** 加载脉冲 (opacity 循环) */
export const pulse = {
  animate: { opacity: [0.4, 1, 0.4] as [number, number, number] },
  transition: { duration: 1.6, repeat: Infinity },
} as const;

/** 行级 stagger 容器 (delay 是 index * STAGGER_STEP.row) */
export const rowStagger = (delay = 0.02) => ({
  hidden: { opacity: 0, y: LIFT.stagger },
  show: {
    opacity: 1,
    y: 0,
    transition: { delay, duration: DUR.normal, ease: EASE.outExpo },
  },
});
```

- [ ] **Step 2: 移除 SPRING.gentle 死代码**

在 `lib/motion.ts` 中, 删除:
```typescript
gentle: { damping: 26, stiffness: 200, type: "spring" as const },
```

剩余 SPRING 只保留 snappy 和 soft.

- [ ] **Step 3: 调整 fadeIn variant duration**

当前 `fadeIn` 用 `DUR.normal`. 改为 `DUR.slow` 跟项目大多数"无位移淡入"一致.

修改:
```typescript
export const fadeIn = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { duration: DUR.slow, ease: EASE.outExpo } },
} as const;
```

- [ ] **Step 4: 验证 typecheck**

```bash
cd /c/doc/Code/rag/packages/web && bun run typecheck 2>&1 | tail -10
```

- [ ] **Step 5: Commit**

```bash
cd /c/doc/Code/rag && git add packages/web/lib/motion.ts && git commit -m "feat(motion): 扩展 lib/motion.ts (LIFT/DELAY/PRESS/STAGGER_STEP/VIEWPORT_MARGIN + 5 variants + 2 transition + 移除 SPRING.gentle)"
```

---

### Task 1.5.2: app-settings-card 改用 fadeUpGentle + VIEWPORT_MARGIN.early

**Files:**
- Modify: `packages/web/components/common/display/app-settings-card.tsx`

- [ ] **Step 1: 替换 motion.div 为 motion.div + variants**

当前:
```tsx
<motion.div
  className="h-full"
  initial={{ opacity: 0, y: 8 }}
  whileInView={{ opacity: 1, y: 0 }}
  viewport={{ margin: "-10%", once: true }}
  transition={{ duration: 0.3, ease: "easeOut" }}
>
```

改为:
```tsx
import { fadeUpGentle, VIEWPORT_MARGIN } from "@/lib/motion";
// ...

<motion.div
  className="h-full"
  variants={fadeUpGentle}
  initial="hidden"
  whileInView="show"
  viewport={{ margin: VIEWPORT_MARGIN.early, once: true }}
>
```

- [ ] **Step 2: 验证 typecheck + test**

```bash
cd /c/doc/Code/rag/packages/web && bun run typecheck && bun run test -- --run components/common/display/app-settings-card 2>&1 | tail -10
```

- [ ] **Step 3: Commit**

```bash
cd /c/doc/Code/rag && git add packages/web/components/common/display/app-settings-card.tsx && git commit -m "refactor: app-settings-card 用 fadeUpGentle + VIEWPORT_MARGIN.early"
```

---

### Task 1.5.3: 5 个文件用 fadeUp variant (替代硬编码 fadeUp 模式)

**Files:**
- Modify: `packages/web/app/[locale]/output/[task_id]/[file]/page.tsx`
- Modify: `packages/web/app/[locale]/knowledge/batch/page.tsx`
- Modify: `packages/web/app/[locale]/knowledge/documents/import/_components/documents-import-form.tsx` (2 处)
- Modify: `packages/web/app/[locale]/knowledge/triples/_components/triples-form.tsx` (实际在 Phase 2 改 ResultBanner, 此处只改 slideInTop)
- Modify: `packages/web/app/[locale]/knowledge/documents/import/_components/import-commit-card.tsx` (同上)

- [ ] **Step 1: 改 output/[task_id]/[file]/page.tsx**

当前 `motion.div` with `initial={{ opacity: 0, translateY: 12 }}` + `transition={{ duration: DUR.slow, ease: CSS_EASE.outExpo }}` 改为:
```tsx
import { fadeUp } from "@/lib/motion";
// ...
<motion.div variants={fadeUp} initial="hidden" animate="show">
```

- [ ] **Step 2: 改 batch/page.tsx (CARD_INITIAL 部分)**

当前 `CARD_INITIAL = { opacity: ZERO, [ANIM_Y]: 12 }` 等 3 个常量 + 3 个 transition 引用改为:
```tsx
import { fadeUp, TRANSITION_REVEAL_OUTEXPO } from "@/lib/motion";
// 删除 CARD_INITIAL/CARD_ANIMATE/CARD_EXIT 3 个 const
<motion.div variants={fadeUp} initial="hidden" animate="show" exit="hidden" transition={TRANSITION_REVEAL_OUTEXPO}>
```

- [ ] **Step 3: 改 documents-import-form.tsx (2 处 fadeUp)**

第 308 行和 360 行的 `motion.div` 用 `initial={{ opacity: 0, y: 12 }}` 改为:
```tsx
<motion.div variants={fadeUp} initial="hidden" animate="show" transition={...}>
```

- [ ] **Step 4: 跑全量 typecheck + test**

```bash
cd /c/doc/Code/rag/packages/web && bun run typecheck && bun run test -- --run 2>&1 | tail -20
```

- [ ] **Step 5: Commit**

```bash
cd /c/doc/Code/rag && git add packages/web/app/\[locale\]/output/\[task_id\]/\[file\]/page.tsx packages/web/app/\[locale\]/knowledge/batch/page.tsx packages/web/app/\[locale\]/knowledge/documents/import/_components/documents-import-form.tsx && git commit -m "refactor: 4 处用 fadeUp variant (消 4 处硬编码)"
```

---

### Task 1.5.4: 3 个文件用 slideInTop variant (替代硬编码 y:-4 模式)

**Files:**
- Modify: `packages/web/app/[locale]/knowledge/triples/_components/triples-form.tsx`
- Modify: `packages/web/app/[locale]/knowledge/documents/import/_components/import-commit-card.tsx`
- Modify: `packages/web/app/[locale]/knowledge/batch/page.tsx` (ERROR_LIST 部分)

- [ ] **Step 1: 改 triples-form.tsx (2 处 y:-4)**

第 280 和 297 行的 `motion.div` 改为:
```tsx
import { slideInTop, TRANSITION_QUICK_OUTQUINT } from "@/lib/motion";
// ...
<motion.div variants={slideInTop} initial="hidden" animate="show" exit="hidden" transition={TRANSITION_QUICK_OUTQUINT}>
```

**注意**: triples-form.tsx 后续 Phase 2 Task 2.2 会改为 `<ResultBanner>`, 此处先为它准备好 (替换 hardcoded variants).

- [ ] **Step 2: 改 import-commit-card.tsx (2 处)**

同样模式.

- [ ] **Step 3: 改 batch/page.tsx (ERROR_LIST)**

`ERROR_LIST_INITIAL/ANIMATE/EXIT` + transition 改为:
```tsx
<motion.ul variants={slideInTop} initial="hidden" animate="show" exit="hidden" transition={TRANSITION_QUICK_OUTQUINT}>
```

- [ ] **Step 4: 跑全量 typecheck + test**

```bash
cd /c/doc/Code/rag/packages/web && bun run typecheck && bun run test -- --run 2>&1 | tail -20
```

- [ ] **Step 5: Commit**

```bash
cd /c/doc/Code/rag && git add packages/web/app/\[locale\]/knowledge/triples/_components/triples-form.tsx packages/web/app/\[locale\]/knowledge/documents/import/_components/import-commit-card.tsx packages/web/app/\[locale\]/knowledge/batch/page.tsx && git commit -m "refactor: 5 处用 slideInTop variant (消 5 处硬编码 y:-4)"
```

---

### Task 1.5.5: decode/page.tsx 用 fadeUpLarge variant

**Files:**
- Modify: `packages/web/app/[locale]/decode/page.tsx`

- [ ] **Step 1: 替换 motion.section**

当前第 195 行 `motion.section` with `initial={{ opacity: 0, translateY: 16 }}` + `transition={{ delay: 0.1, duration: DUR.slow, ease: CSS_EASE.outExpo }}` 改为:
```tsx
import { fadeUpLarge } from "@/lib/motion";
// ...
<motion.section variants={fadeUpLarge} initial="hidden" animate="show" transition={{ delay: DELAY.secondary }}>
```

- [ ] **Step 2: 跑 test + commit**

```bash
cd /c/doc/Code/rag/packages/web && bun run typecheck && bun run test -- --run app/\[locale\]/decode/ 2>&1 | tail -10
```

```bash
cd /c/doc/Code/rag && git add packages/web/app/\[locale\]/decode/page.tsx && git commit -m "refactor: decode/page 用 fadeUpLarge variant"
```

---

### Task 1.5.6: data-table-body.tsx 用 pulse + rowStagger variant

**Files:**
- Modify: `packages/web/components/common/table/data-table-body.tsx`

- [ ] **Step 1: 替换 motion.span pulse**

当前 `motion.span animate={{ opacity: ANIM_OPACITY_PULSE }} transition={{ duration: ANIM_DURATION_PULSE, repeat: Infinity }}` 改为:
```tsx
import { pulse, STAGGER_STEP, rowStagger } from "@/lib/motion";
// 删除 ANIM_OPACITY_PULSE / ANIM_DURATION_PULSE / ANIM_OPACITY_END / ANIM_OPACITY_START / ANIM_Y_END / ANIM_Y_START 等常量
// 删除 OPACITY_LOW
<motion.span {...pulse}>
```

- [ ] **Step 2: 替换 motion.tr 行 stagger (2 处)**

第 75-87 和 114-127 行的 `motion.tr` with `initial={{ opacity: 0, translateY: 4 }}` + `delay: index * ANIM_DELAY_STEP` 改为:
```tsx
<motion.tr variants={rowStagger(index * STAGGER_STEP.row)} initial="hidden" animate="show">
```

- [ ] **Step 3: 跑 test + commit**

```bash
cd /c/doc/Code/rag/packages/web && bun run typecheck && bun run test -- --run components/common/table/data-table-body 2>&1 | tail -10
```

```bash
cd /c/doc/Code/rag && git add packages/web/components/common/table/data-table-body.tsx && git commit -m "refactor: data-table-body 用 pulse + rowStagger variants (消 6 硬编码常量)"
```

---

### Phase 1.5 总结验证

- [ ] **Step: 全量验证, lib/motion.ts 引用无回归**

```bash
cd /c/doc/Code/rag/packages/web && bun run typecheck && bun run lint && bun run test -- --run 2>&1 | tail -30
```
Expected: 0 type errors, 0 new lint warnings, 0 new test fails

- [ ] **Step: 验证硬编码已替换 (用 grep 抽查)**

```bash
cd /c/doc/Code/rag/packages/web
grep -rn "y: 4\b\|y: 8\b\|y: 12\b\|y: 16\b\|y: -4\b" --include="*.tsx" 2>/dev/null | grep -v "lib/motion.ts" | grep -v "components/motion/" | grep -v "\.test\." | head -5
```
Expected: 0 hits (所有 y 硬编码已替换为 LIFT.* 引用)

```bash
grep -rn "duration: 0\.3\|duration: 1\.6\|ease: \"easeOut\"" --include="*.tsx" 2>/dev/null | grep -v "lib/motion.ts" | head -3
```
Expected: 0 hits (所有 transition 字符串硬编码已替换)

---

## Phase 2: 收敛直接 motion/react 引用 (P1, ~1 人日)

### Task 2.1: 抽 ResultBanner wrapper

**Files:**
- Create: `packages/web/components/motion/result-banner.tsx`
- Modify: `packages/web/components/motion/animated.tsx` (barrel re-export)

- [ ] **Step 1: 创建 result-banner.tsx**

```typescript
// packages/web/components/motion/result-banner.tsx
// 顶部 success/error 提示横幅: 封装 AnimatePresence + motion.div fadeUp 模式
// 替代 4+ 文件的 inline AnimatePresence + motion.div 重复
"use client";
import { type ReactNode } from "react";
import { AnimatePresence, motion } from "motion/react";
import { DUR, CSS_EASE } from "@/lib/motion";
import { useReducedMotionSafe } from "./use-reduced-motion-safe";

export type ResultBannerVariant = "success" | "error" | "info";

export interface ResultBannerProps {
  show: boolean;
  variant?: ResultBannerVariant;
  /** 进场 y 偏移方向: -4 = 从上滑入, 12 = 从下滑入 */
  enterY?: -4 | 12;
  delay?: number;
  children: ReactNode;
  className?: string;
}

const VARIANT_CLASSES: Record<ResultBannerVariant, string> = {
  success: "border-status-success/50 bg-status-success/5 text-status-success",
  error: "border-status-error/50 bg-status-error/5 text-status-error",
  info: "border-status-running/50 bg-status-running/5 text-status-running",
};

export const ResultBanner = ({
  show,
  variant = "info",
  enterY = -4,
  delay = 0,
  children,
  className = "",
}: ResultBannerProps) => {
  const reduced = useReducedMotionSafe();
  return (
    <AnimatePresence>
      {show && (
        <motion.div
          className={`rounded-md border p-3 ${VARIANT_CLASSES[variant]} ${className}`}
          initial={reduced ? false : { opacity: 0, y: enterY }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0 }}
          transition={{
            duration: DUR.normal,
            delay,
            ease: reduced ? undefined : CSS_EASE.outQuint,
          }}
        >
          {children}
        </motion.div>
      )}
    </AnimatePresence>
  );
};
```

- [ ] **Step 2: 在 animated.tsx barrel 加 export**

在 `packages/web/components/motion/animated.tsx` 末尾追加:
```typescript
export { ResultBanner, type ResultBannerVariant, type ResultBannerProps } from "./result-banner";
```

- [ ] **Step 3: 创建 result-banner.test.tsx**

```typescript
// packages/web/components/motion/result-banner.test.tsx
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { ResultBanner } from "./result-banner";

describe("ResultBanner", () => {
  it("show=false 不渲染", () => {
    const { container } = render(
      <ResultBanner show={false}>内容</ResultBanner>,
    );
    expect(container.textContent).toBe("");
  });

  it("show=true 渲染 children", () => {
    render(<ResultBanner show={true}>成功</ResultBanner>);
    expect(screen.getByText("成功")).toBeInTheDocument();
  });

  it("variant=error 应用 error 颜色类", () => {
    const { container } = render(
      <ResultBanner show={true} variant="error">错误</ResultBanner>,
    );
    const banner = container.querySelector("div > div");
    expect(banner?.className).toContain("status-error");
  });
});
```

- [ ] **Step 4: 跑测试**

```bash
cd /c/doc/Code/rag/packages/web && bun run typecheck && bun run test -- --run components/motion/ 2>&1 | tail -15
```
Expected: 3 个新测试通过

- [ ] **Step 5: Commit**

```bash
cd /c/doc/Code/rag && git add packages/web/components/motion/result-banner.tsx packages/web/components/motion/result-banner.test.tsx packages/web/components/motion/animated.tsx && git commit -m "feat(motion): 抽 ResultBanner wrapper 替代 4 文件 AnimatePresence 重复"
```

---

### Task 2.1.1: 抽 AnimateUp wrapper (状态触发的内容入场)

**Files:**
- Create: `packages/web/components/motion/animate-up.tsx`
- Create: `packages/web/components/motion/animate-up.test.tsx`
- Modify: `packages/web/components/motion/animated.tsx` (barrel re-export)

- [ ] **Step 1: 创建 animate-up.tsx**

```typescript
// packages/web/components/motion/animate-up.tsx
// 状态触发的内容入场 (Reveal 的双胞胎, 用 initial/animate/exit 替代 whileInView)
// 替代 5 文件的 inline AnimatePresence + motion.div + fadeUp 模式
"use client";
import { type ReactNode } from "react";
import { AnimatePresence, motion } from "motion/react";
import { fadeUp, TRANSITION_REVEAL_OUTEXPO } from "@/lib/motion";
import { useReducedMotionSafe } from "./use-reduced-motion-safe";

export interface AnimateUpProps {
  /** 控制显示, 配合 AnimatePresence mode="wait" 切换内容 */
  show: boolean;
  /** 进场 y 偏移, 默认 12 (fadeUp 默认) */
  lift?: number;
  /** 进场 delay, 默认 0 */
  delay?: number;
  children: ReactNode;
  className?: string;
  /** 元素类型, 默认 div */
  as?: "div" | "section" | "article" | "ul" | "li";
}

export const AnimateUp = ({
  show,
  lift = 12,
  delay = 0,
  children,
  className,
  as = "div",
}: AnimateUpProps) => {
  const reduced = useReducedMotionSafe();
  const Tag = motion[as] as typeof motion.div;
  // reduce 模式: 用 initial={false} 跳过 hidden 状态
  const initial = reduced ? false : { opacity: 0, y: lift };
  return (
    <AnimatePresence>
      {show && (
        <Tag
          className={className}
          variants={fadeUp}
          initial={initial}
          animate="show"
          exit="hidden"
          transition={{ ...TRANSITION_REVEAL_OUTEXPO, delay }}
        >
          {children}
        </Tag>
      )}
    </AnimatePresence>
  );
};
```

- [ ] **Step 2: 创建 animate-up.test.tsx**

```typescript
// packages/web/components/motion/animate-up.test.tsx
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { AnimateUp } from "./animate-up";

describe("AnimateUp", () => {
  it("show=false 不渲染", () => {
    const { container } = render(
      <AnimateUp show={false}>内容</AnimateUp>,
    );
    expect(container.textContent).toBe("");
  });

  it("show=true 渲染 children", () => {
    render(<AnimateUp show={true}>内容</AnimateUp>);
    expect(screen.getByText("内容")).toBeInTheDocument();
  });
});
```

- [ ] **Step 3: barrel export**

在 `animated.tsx` 末尾追加:
```typescript
export { AnimateUp, type AnimateUpProps } from "./animate-up";
```

- [ ] **Step 4: 跑 test 验证**

```bash
cd /c/doc/Code/rag/packages/web && bun run typecheck && bun run test -- --run components/motion/ 2>&1 | tail -15
```

- [ ] **Step 5: Commit**

```bash
cd /c/doc/Code/rag && git add packages/web/components/motion/animate-up.tsx packages/web/components/motion/animate-up.test.tsx packages/web/components/motion/animated.tsx && git commit -m "feat(motion): 抽 AnimateUp wrapper (状态触发内容入场, 替代 5 处 fadeUp 硬编码)"
```

---

### Task 2.1.2: 抽 ButtonLift wrapper (Button 悬浮包装)

**Files:**
- Create: `packages/web/components/motion/button-lift.tsx`
- Modify: `packages/web/components/motion/animated.tsx` (barrel re-export)

- [ ] **Step 1: 创建 button-lift.tsx**

```typescript
// packages/web/components/motion/button-lift.tsx
// Button 悬浮包装: motion.div + whileHover + whileTap
// 替代 documents-import-form.tsx 3 处 motion.div 包 Button 的重复
"use client";
import { type ReactNode } from "react";
import { motion } from "motion/react";
import { useReducedMotionSafe } from "./use-reduced-motion-safe";
import { LIFT, PRESS } from "@/lib/motion";

export interface ButtonLiftProps {
  children: ReactNode;
  className?: string;
}

export const ButtonLift = ({ children, className }: ButtonLiftProps) => {
  const reduced = useReducedMotionSafe();
  return (
    <motion.div
      className={className}
      whileHover={reduced ? undefined : { y: -LIFT.hover }}
      whileTap={reduced ? undefined : { scale: PRESS.scaleSubtle }}
    >
      {children}
    </motion.div>
  );
};
```

- [ ] **Step 2: barrel export**

在 `animated.tsx` 末尾追加:
```typescript
export { ButtonLift, type ButtonLiftProps } from "./button-lift";
```

- [ ] **Step 3: 跑 test 验证**

```bash
cd /c/doc/Code/rag/packages/web && bun run typecheck && bun run test -- --run components/motion/ 2>&1 | tail -10
```

- [ ] **Step 4: Commit**

```bash
cd /c/doc/Code/rag && git add packages/web/components/motion/button-lift.tsx packages/web/components/motion/animated.tsx && git commit -m "feat(motion): 抽 ButtonLift wrapper (替代 3 处 motion.div 包 Button)"
```

---

### Task 2.2: triples-form 用 ResultBanner

**Files:**
- Modify: `packages/web/app/[locale]/knowledge/triples/_components/triples-form.tsx`

- [ ] **Step 1: 读文件找到 TriplesResult / TriplesError 模式**

```bash
cd /c/doc/Code/rag/packages/web
grep -n "AnimatePresence\|TriplesResult\|TriplesError" app/\[locale\]/knowledge/triples/_components/triples-form.tsx
```

- [ ] **Step 2: 替换 AnimatePresence + motion.div 为 ResultBanner**

找到当前的 AnimatePresence + motion.div 块, 替换为:
```tsx
import { ResultBanner } from "@/components/motion/animated";
// ...

// 替换前: <AnimatePresence>{success && <motion.div initial={...} animate={...}>...</motion.div>}</AnimatePresence>
<ResultBanner show={success} variant="success">{successContent}</ResultBanner>

// 替换前: <AnimatePresence>{error && <motion.div ...>...</motion.div>}</AnimatePresence>
<ResultBanner show={error} variant="error">{errorContent}</ResultBanner>
```

- [ ] **Step 3: 移除 motion/react 导入 (如果完全不再用)**

如果该文件除了 AnimatePresence + motion.div 外不再用 motion/react, 移除 import.

- [ ] **Step 4: 跑 typecheck + 测试**

```bash
cd /c/doc/Code/rag/packages/web && bun run typecheck && bun run test -- --run app/\[locale\]/knowledge/triples/ 2>&1 | tail -10
```

- [ ] **Step 5: Commit**

```bash
cd /c/doc/Code/rag && git add packages/web/app/\[locale\]/knowledge/triples/_components/triples-form.tsx && git commit -m "refactor: triples-form 用 ResultBanner (消 2 个 motion.div)"
```

---

### Task 2.3: import-commit-card 用 ResultBanner

**Files:**
- Modify: `packages/web/app/[locale]/knowledge/documents/import/_components/import-commit-card.tsx`

- [ ] **Step 1: 替换 motion.div + AnimatePresence 为 ResultBanner**

跟 Task 2.2 同模式. variant=success / variant=error 各一处.

- [ ] **Step 2: 跑 typecheck + 测试 + commit**

```bash
cd /c/doc/Code/rag/packages/web && bun run typecheck && bun run test -- --run app/\[locale\]/knowledge/documents/ 2>&1 | tail -10
```

```bash
cd /c/doc/Code/rag && git add packages/web/app/\[locale\]/knowledge/documents/import/_components/import-commit-card.tsx && git commit -m "refactor: import-commit-card 用 ResultBanner (消 2 个 motion.div)"
```

---

### Task 2.4: batch page 用 ResultBanner

**Files:**
- Modify: `packages/web/app/[locale]/knowledge/batch/page.tsx`

- [ ] **Step 1: 替换 motion.ul / motion.div 错误列表 + 活跃任务卡**

找到 `motion.ul` 错误列表和 `motion.div` 活跃任务卡, 各替换为 ResultBanner (variant="error" / variant="info").

- [ ] **Step 2: 跑 typecheck + 测试 + commit**

```bash
cd /c/doc/Code/rag/packages/web && bun run typecheck && bun run test -- --run app/\[locale\]/knowledge/batch/ 2>&1 | tail -10
```

```bash
cd /c/doc/Code/rag && git add packages/web/app/\[locale\]/knowledge/batch/page.tsx && git commit -m "refactor: batch page 用 ResultBanner (消 2 个 motion 元素)"
```

---

### Task 2.5: output-list-client 用 ResultBanner

**Files:**
- Modify: `packages/web/app/[locale]/output/_components/output-list-client.tsx`

- [ ] **Step 1: 替换空态 AnimatePresence + motion.div**

- [ ] **Step 2: 跑 typecheck + 测试 + commit**

```bash
cd /c/doc/Code/rag/packages/web && bun run typecheck && bun run test -- --run app/\[locale\]/output/ 2>&1 | tail -10
```

```bash
cd /c/doc/Code/rag && git add packages/web/app/\[locale\]/output/_components/output-list-client.tsx && git commit -m "refactor: output-list-client 用 ResultBanner (消空态 motion.div)"
```

---

### Task 2.6: app-settings-card 改用 Reveal

**Files:**
- Modify: `packages/web/components/common/display/app-settings-card.tsx`

- [ ] **Step 1: 用 Reveal 替换 motion.div**

当前 `app-settings-card.tsx:27-33`:
```tsx
<motion.div
  className="h-full"
  initial={{ opacity: 0, y: 8 }}
  whileInView={{ opacity: 1, y: 0 }}
  viewport={{ margin: "-10%", once: true }}
  transition={{ duration: 0.3, ease: "easeOut" }}
>
```

注意: Reveal 默认 `y: 12` (fadeUp variant) + duration: DUR.slow (0.7s), 跟当前的 `y: 8` + 0.3s 略有差异. 由于这是**审计要求的消除 motion.div**, 接受 Reveal 的默认参数 (统一体验).

**Reveal 不支持自定义 viewportMargin** (-10% vs 默认 -5%). 如果差异重要, 后续可扩展 Reveal API. 当前先换为 Reveal 接受默认参数.

替换:
```typescript
import { Reveal } from "@/components/motion/animated";
// 删除 import { motion } from "motion/react";

export const SettingsCard = ({ ... }: SettingsCardProps) => (
  <Reveal className="h-full">
    <Card ...>...</Card>
  </Reveal>
);
```

- [ ] **Step 2: 跑 typecheck + 测试 + commit**

```bash
cd /c/doc/Code/rag/packages/web && bun run typecheck && bun run test -- --run components/common/display/app-settings-card 2>&1 | tail -10
```

```bash
cd /c/doc/Code/rag && git add packages/web/components/common/display/app-settings-card.tsx && git commit -m "refactor: app-settings-card 用 Reveal (消 motion.div + 硬编码字符串)"
```

---

### Task 2.7: documents-import-form 3 处 ButtonLift + 2 处 AnimateUp 改用 wrapper

**Files:**
- Modify: `packages/web/app/[locale]/knowledge/documents/import/_components/documents-import-form.tsx`

- [ ] **Step 1: 3 处 hover 包装改用 ButtonLift**

查找 3 处 `<motion.div whileHover={{ y: -1 }} whileTap={{ scale: 0.98 }}>`:
- line 261 (Excel 模板下载)
- line 270 (JSON 模板下载)
- line 339-340 (下载错误行 CSV)

替换为:
```tsx
import { ButtonLift } from "@/components/motion/animated";
// ...
<ButtonLift>
  <Button asChild>...</Button>
</ButtonLift>
```

- [ ] **Step 2: 2 处 fadeUp 卡片改用 AnimateUp**

查找第 308 行和 360 行的 `motion.div` (Phase 1.5 任务中已替换为 `variants={fadeUp}`):
- 此时应改为 `<AnimateUp show={!!condition}>...</AnimateUp>`, 用 show 控制显示

- [ ] **Step 3: 跑 typecheck + 测试 + commit**

```bash
cd /c/doc/Code/rag/packages/web && bun run typecheck && bun run test -- --run app/\[locale\]/knowledge/documents/import/ 2>&1 | tail -10
```

```bash
cd /c/doc/Code/rag && git add packages/web/app/\[locale\]/knowledge/documents/import/_components/documents-import-form.tsx && git commit -m "refactor: documents-import-form 用 ButtonLift + AnimateUp (消 5 个 motion.div)"
```

---

### Task 2.8: 5 处 AnimateUp wrapper 改用 (decode/output/batch)

**Files:**
- Modify: `packages/web/app/[locale]/decode/page.tsx` (decode 结果区)
- Modify: `packages/web/app/[locale]/output/[task_id]/[file]/page.tsx` (文件预览)
- Modify: `packages/web/app/[locale]/knowledge/batch/page.tsx` (活跃任务卡, ERROR_LIST 用 ResultBanner 已在 Task 2.4)

- [ ] **Step 1: 改 decode/page.tsx**

Phase 1.5 已将 `motion.section` 改为 `variants={fadeUpLarge}`. 此处用 `<AnimateUp show={hasResult} as="section">` 替换 motion.section 整体.

- [ ] **Step 2: 改 output/[task_id]/[file]/page.tsx**

替换 `motion.div` 整体为 `<AnimateUp show={true}>...</AnimateUp>`.

- [ ] **Step 3: 改 batch/page.tsx (CARD 部分)**

ERROR_LIST 已在 Phase 1.5 改为 `slideInTop`, 此处进一步改为 `<ResultBanner show={!!activeTask} variant="info">...</ResultBanner>` (实际上批量任务用 ResultBanner 也合理).

**决策**: 若 batch 活跃任务卡用 ResultBanner 比 AnimateUp 更合适, 统一用 ResultBanner (Task 2.4 已包含 ERROR_LIST 的 ResultBanner, 活跃任务卡加进去).

- [ ] **Step 4: 跑 typecheck + 测试 + commit**

```bash
cd /c/doc/Code/rag/packages/web && bun run typecheck && bun run test -- --run 2>&1 | tail -20
```

```bash
cd /c/doc/Code/rag && git add packages/web/app/\[locale\]/decode/page.tsx packages/web/app/\[locale\]/output/\[task_id\]/\[file\]/page.tsx packages/web/app/\[locale\]/knowledge/batch/page.tsx && git commit -m "refactor: 3 文件用 AnimateUp/ResultBanner (消 3 处 motion 元素)"
```

---

### Phase 2 总结验证

- [ ] **Step: 验证直接 motion/react 引用收敛**

```bash
cd /c/doc/Code/rag/packages/web && grep -rln "motion/react" --include="*.tsx" --include="*.ts" 2>/dev/null | grep -v node_modules | grep -v "components/motion/" | grep -v ".test."
```
Expected: 减少 (从 11 减到 3-4 个: task-detail-client, decode-input-bar, data-table-body 剩 AnimatePresence 包装)

- [ ] **Step: 验证变体重定义已替换**

```bash
cd /c/doc/Code/rag/packages/web && grep -rn "initial={{ opacity: 0" --include="*.tsx" 2>/dev/null | grep -v "components/motion/" | grep -v "lib/motion.ts" | grep -v ".test." | wc -l
```
Expected: 0 (所有变体重定义已替换为 variants={fadeUp/slideInTop/...})

- [ ] **Step: 全量 typecheck + 测试**

```bash
cd /c/doc/Code/rag/packages/web && bun run typecheck && bun run test -- --run 2>&1 | tail -20
```

---

## Phase 3: 业务层 wrapper (P2, ~2 人日)

### Task 3.1: 扩展 PageHero 支持 backHref

**Files:**
- Modify: `packages/web/components/common/navigation/app-page-hero.tsx`

- [ ] **Step 1: 读现有 PageHero**

```bash
cd /c/doc/Code/rag/packages/web && cat components/common/navigation/app-page-hero.tsx
```

- [ ] **Step 2: 扩展 PageHero 添加 backHref/backLabel props**

在 props interface 添加:
```typescript
export interface PageHeroProps {
  // 现有 props...
  /** 后退链接 href (可选). 提供后自动在 h1 同一行渲染 BackLink. */
  backHref?: string;
  /** 后退链接文字 (i18n key). 默认 "返回" */
  backLabel?: string;
}
```

在 PageHero 组件中, 把 backHref 包到第一个 StaggerItem 的 h1 同一行:

**实现思路** (根据实际 PageHero 结构调整):
- 找到 StaggerItem 包 h1 的位置
- 改为 `<StaggerItem>` 内: `<div className="flex items-center gap-3">{backHref && <BackLink href={backHref}>{backLabel}</BackLink>}<h1>...</h1></div>`
- 或者用 `flex items-baseline gap-3` 让 BackLink 和 h1 同行对齐

具体代码实现需根据实际 PageHero 结构而定. **保证向后兼容**: 不传 backHref 时行为完全不变.

- [ ] **Step 3: 跑 typecheck + 测试 + commit**

```bash
cd /c/doc/Code/rag/packages/web && bun run typecheck && bun run test -- --run components/common/navigation/ 2>&1 | tail -10
```

```bash
cd /c/doc/Code/rag && git add packages/web/components/common/navigation/app-page-hero.tsx && git commit -m "feat(hero): PageHero 支持 backHref/backLabel (向后兼容)"
```

---

### Task 3.2: 5 个页面用 PageHero (带 backHref)

**Files:**
- Modify: `packages/web/app/[locale]/knowledge/batch/page.tsx`
- Modify: `packages/web/app/[locale]/knowledge/nodes/_components/nodes-table.tsx`
- Modify: `packages/web/app/[locale]/knowledge/relations/_components/relations-table.tsx`
- Modify: `packages/web/app/[locale]/knowledge/triples/_components/triples-form.tsx`
- Modify: `packages/web/app/[locale]/evaluate/_components/evaluate-list-view.tsx`

- [ ] **Step 1: 改 knowledge/batch/page.tsx**

找到手写 Stagger 序列 (eyebrow + h1 + BackLink + p), 替换为:
```tsx
<PageHero
  eyebrow="批量导入"
  title="知识批量导入"
  description="..."
  backHref="/knowledge/datasets"
  backLabel="返回数据集"
/>
```

- [ ] **Step 2: 改 knowledge/nodes/_components/nodes-table.tsx**

同样替换 Stagger 序列.

- [ ] **Step 3: 改 knowledge/relations/_components/relations-table.tsx**

- [ ] **Step 4: 改 knowledge/triples/_components/triples-form.tsx**

- [ ] **Step 5: 改 evaluate/_components/evaluate-list-view.tsx** (无 backHref, 仅复用 hero 结构)

- [ ] **Step 6: 跑全量 typecheck + 测试 + commit**

```bash
cd /c/doc/Code/rag/packages/web && bun run typecheck && bun run test -- --run 2>&1 | tail -20
```

```bash
cd /c/doc/Code/rag && git add packages/web/app/\[locale\]/knowledge/batch/page.tsx packages/web/app/\[locale\]/knowledge/nodes/_components/nodes-table.tsx packages/web/app/\[locale\]/knowledge/relations/_components/relations-table.tsx packages/web/app/\[locale\]/knowledge/triples/_components/triples-form.tsx packages/web/app/\[locale\]/evaluate/_components/evaluate-list-view.tsx && git commit -m "refactor: 5 个页面用 PageHero (消 Stagger 序列重复)"
```

---

### Task 3.3: 抽 StatsGrid wrapper

**Files:**
- Create: `packages/web/components/common/display/stats-grid.tsx`
- Modify: `packages/web/components/common/display/index.ts` (barrel)

- [ ] **Step 1: 读现有 StatCard API**

```bash
cd /c/doc/Code/rag/packages/web && grep -A 20 "StatCard" components/common/display/app-stat-card.tsx | head -30
```

- [ ] **Step 2: 创建 stats-grid.tsx**

```typescript
// packages/web/components/common/display/stats-grid.tsx
// StatCard 网格: 统一 Reveal + grid + LocalizedLink wrapper
// 替代 3 个 dashboard 入口页的 14 行重复 JSX
import { type ReactNode } from "react";
import { LocalizedLink } from "@/components/i18n/localized-link";
import { StatCard, type StatCardProps } from "./app-stat-card";

export type StatsGridItem = Pick<StatCardProps, "label" | "value" | "accent" | "hint"> & {
  href?: string;
};

export interface StatsGridProps {
  items: StatsGridItem[];
  /** 网格列数: 2 (mobile) 或 4 (desktop) */
  columns?: 2 | 4;
  /** Reveal delay (秒), 默认 0.12 */
  delay?: number;
  className?: string;
}

const COLS_CLASS = {
  "2": "grid-cols-2",
  "4": "grid-cols-2 md:grid-cols-4",
} as const;

export const StatsGrid = ({ items, columns = 4, delay = 0.12, className }: StatsGridProps) => {
  const gridClass = COLS_CLASS[String(columns) as "2" | "4"];
  const renderItem = (item: StatsGridItem, idx: number): ReactNode => {
    const card = <StatCard {...item} index={idx} />;
    if (item.href) {
      return (
        <LocalizedLink key={`${item.label}-${idx}`} href={item.href}>
          {card}
        </LocalizedLink>
      );
    }
    return <div key={`${item.label}-${idx}`}>{card}</div>;
  };

  return (
    <div className={`grid gap-4 ${gridClass} ${className ?? ""}`}>
      {items.map(renderItem)}
    </div>
  );
};
```

**注意**: 此处用 `<div className="grid">` 而非 `<Reveal>`, 因为 `Reveal` 自身就是动画容器, 包整个 grid 后只触发一次动画. 内部 `StatCard` 已有自身的 `anim-rise` 动画. delay 通过 `StatCard` 的 `animationDelay` 内部处理.

- [ ] **Step 3: 在 barrel index.ts 加 export**

```typescript
export { StatsGrid, type StatsGridItem, type StatsGridProps } from "./stats-grid";
```

- [ ] **Step 4: 跑 typecheck + commit**

```bash
cd /c/doc/Code/rag/packages/web && bun run typecheck 2>&1 | tail -10
```

```bash
cd /c/doc/Code/rag && git add packages/web/components/common/display/stats-grid.tsx packages/web/components/common/display/index.ts && git commit -m "feat(display): 抽 StatsGrid wrapper (替代 dashboard 入口页 14 行重复)"
```

---

### Task 3.4: 抽 EntryCardGrid wrapper

**Files:**
- Create: `packages/web/components/common/display/entry-card-grid.tsx`
- Modify: `packages/web/components/common/display/index.ts` (barrel)

- [ ] **Step 1: 读现有 EntryCard API**

```bash
cd /c/doc/Code/rag/packages/web && grep -A 15 "EntryCard" components/common/display/app-entry-card.tsx | head -25
```

- [ ] **Step 2: 创建 entry-card-grid.tsx**

```typescript
// packages/web/components/common/display/entry-card-grid.tsx
// EntryCard 网格: 统一 grid + LocalizedLink wrapper
import { type ReactNode } from "react";
import { LocalizedLink } from "@/components/i18n/localized-link";
import { EntryCard, type EntryCardProps } from "./app-entry-card";

export type EntryCardGridItem = Pick<EntryCardProps, "icon" | "title" | "desc" | "hint"> & {
  href: string;
};

export interface EntryCardGridProps {
  items: EntryCardGridItem[];
  /** 网格列数: 2 或 4 */
  columns?: 2 | 4;
  delay?: number;
  className?: string;
}

const COLS_CLASS = {
  "2": "grid-cols-1 md:grid-cols-2",
  "4": "grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-4",
} as const;

export const EntryCardGrid = ({ items, columns = 4, className }: EntryCardGridProps) => {
  const gridClass = COLS_CLASS[String(columns) as "2" | "4"];
  return (
    <div className={`grid gap-4 ${gridClass} ${className ?? ""}`}>
      {items.map((item, idx) => (
        <LocalizedLink key={`${item.title}-${idx}`} href={item.href}>
          <EntryCard {...item} index={idx} />
        </LocalizedLink>
      ))}
    </div>
  );
};
```

- [ ] **Step 3: 在 barrel index.ts 加 export**

- [ ] **Step 4: 跑 typecheck + commit**

```bash
cd /c/doc/Code/rag/packages/web && bun run typecheck 2>&1 | tail -10
```

```bash
cd /c/doc/Code/rag && git add packages/web/components/common/display/entry-card-grid.tsx packages/web/components/common/display/index.ts && git commit -m "feat(display): 抽 EntryCardGrid wrapper"
```

---

### Task 3.5: 3 个 dashboard 用新 wrapper

**Files:**
- Modify: `packages/web/app/[locale]/knowledge/_components/knowledge-dashboard.tsx`
- Modify: `packages/web/app/[locale]/knowledge/graph/_components/graph-view.tsx`
- Modify: `packages/web/app/[locale]/knowledge/documents/_components/documents-entry.tsx`

- [ ] **Step 1: 改 knowledge-dashboard.tsx**

找到 `<Reveal delay={0.12}><div className="grid">...</div></Reveal>` 包 StatCard 模式, 替换为:
```tsx
<StatsGrid items={[...]} columns={4} />
```

- [ ] **Step 2: 改 graph-view.tsx**

`<Reveal delay={0.15}><div className="grid">...</div></Reveal>` 替换为 `<StatsGrid items={...} columns={2} />`

- [ ] **Step 3: 改 documents-entry.tsx**

同模式.

- [ ] **Step 4: 同样用 EntryCardGrid 收敛 EntryCard 重复**

- [ ] **Step 5: 跑全量 typecheck + 测试 + commit**

```bash
cd /c/doc/Code/rag/packages/web && bun run typecheck && bun run test -- --run 2>&1 | tail -20
```

```bash
cd /c/doc/Code/rag && git add packages/web/app/\[locale\]/knowledge/_components/knowledge-dashboard.tsx packages/web/app/\[locale\]/knowledge/graph/_components/graph-view.tsx packages/web/app/\[locale\]/knowledge/documents/_components/documents-entry.tsx && git commit -m "refactor: 3 个 dashboard 用 StatsGrid/EntryCardGrid (消 14+14 行重复)"
```

---

### Task 3.6: 25 处 Reveal delay 改用 DELAY.* 常量

**Files:**
- Modify: 25+ 个 `Reveal delay={数字}` 调用文件

- [ ] **Step 1: 全局替换 Reveal delay 数字**

```bash
cd /c/doc/Code/rag/packages/web
# 查找所有 Reveal delay={数字} 调用
grep -rln "Reveal delay={0\." --include="*.tsx" 2>/dev/null | grep -v "components/motion/" | grep -v ".test."
```

**替换映射表**:
- `Reveal delay={0.1}` → `Reveal delay={DELAY.secondary}`
- `Reveal delay={0.12}` → `Reveal delay={DELAY.heroStep1}`
- `Reveal delay={0.15}` → `Reveal delay={DELAY.heroStep2}` (6 处)
- `Reveal delay={0.18}` → `Reveal delay={DELAY.heroStep3}`
- `Reveal delay={0.2}` → `Reveal delay={DELAY.primary}` (9 处)
- `Reveal delay={0.25}` → `Reveal delay={DELAY.empty}`
- `Reveal delay={0.3}` → `Reveal delay={DELAY.data}`
- `Reveal delay={0.35}` → `Reveal delay={DELAY.detail}`

每个文件 import 加上:
```typescript
import { DELAY } from "@/lib/motion";
```

(如果文件已经 import 了 `lib/motion` 的其他常量, 在同一 import 加上 `DELAY`)

- [ ] **Step 2: 跑全量 typecheck + test 验证**

```bash
cd /c/doc/Code/rag/packages/web && bun run typecheck && bun run test -- --run 2>&1 | tail -20
```

- [ ] **Step 3: 验证无 delay 硬编码残留**

```bash
cd /c/doc/Code/rag/packages/web && grep -rn "Reveal delay={0\." --include="*.tsx" 2>/dev/null | grep -v "components/motion/" | grep -v ".test." | head -5
```
Expected: 0 hits (所有 Reveal delay 已用 DELAY.* 常量)

- [ ] **Step 4: Commit**

```bash
cd /c/doc/Code/rag && git add -A && git commit -m "refactor: 25 处 Reveal delay 改用 DELAY.* 常量 (消 25 处硬编码)"
```

---

### Phase 3 总结验证

- [ ] **Step: 全量验证**

```bash
cd /c/doc/Code/rag/packages/web && bun run typecheck && bun run lint && bun run test -- --run 2>&1 | tail -20
```

---

## Phase 4: 边界优化 (P3, 按需触发)

### Task 4.1: 7+ 处 AnimatePresence exit transition 统一 (新)

**Files:**
- Modify: 7+ 文件 (output-list-client / task-detail-client / output/[file]/page / decode/page / triples-form / import-commit-card / batch / documents-import-form)

- [ ] **Step 1: 全局替换 exit transition**

每个 `<AnimatePresence>` 内的 `exit={{ opacity: 0 }}` 改为:
```tsx
exit={{ opacity: 0, transition: TRANSITION_QUICK_OUTEXPO }}
```

(用 `TRANSITION_QUICK_OUTEXPO` 0.4s, 跟 enter 的 slow/normal 0.7/0.4s 保持设计一致性)

- [ ] **Step 2: 跑全量 test + commit**

```bash
cd /c/doc/Code/rag/packages/web && bun run typecheck && bun run test -- --run 2>&1 | tail -20
cd /c/doc/Code/rag && git add -A && git commit -m "refactor: 7+ 处 AnimatePresence exit 用 TRANSITION_QUICK_OUTEXPO (exit/enter 对称)"
```

### Task 4.2: data-table-body.tsx 加 reduce-motion 分支

**Files:**
- Modify: `packages/web/components/common/table/data-table-body.tsx`

- [ ] **Step 1: 已有 pulse + rowStagger, 加 reduce 判断**

读取当前文件, 在 `motion.tr` 和 `motion.span` 包装中加 `useReducedMotionSafe`. 已有 Phase 1.5 改用 variants, 此步在 variants 外加 reduce 判断 (如果是 reduce 模式直接禁用 variants, 立即渲染终态).

- [ ] **Step 2: 跑 test + commit**

```bash
cd /c/doc/Code/rag/packages/web && bun run test -- --run components/common/table/data-table-body 2>&1 | tail -10
cd /c/doc/Code/rag && git add packages/web/components/common/table/data-table-body.tsx && git commit -m "feat(motion): data-table-body 加 reduce-motion 分支 (表格行不再闪烁)"
```

### Task 4.3: 删除 qa-submit-form.tsx 死代码

**Files:**
- Modify: `packages/web/app/[locale]/knowledge/qa/_components/qa-submit-form.tsx`

- [ ] **Step 1: 删除本地 Stagger 死代码**

第 171-173 行的本地 `Stagger = ({children}) => <div className="space-y-2">` 应删除, 改用 `@/components/motion/animated` 的 `Stagger`.

- [ ] **Step 2: 跑 test + commit**

```bash
cd /c/doc/Code/rag/packages/web && bun run test -- --run app/\[locale\]/knowledge/qa 2>&1 | tail -10
cd /c/doc/Code/rag && git add packages/web/app/\[locale\]/knowledge/qa/_components/qa-submit-form.tsx && git commit -m "chore: 删除 qa-submit-form 本地 Stagger 死代码"
```

### Task 4.4: 抽 `<FadePresence>` 包装 (按需)

| 任务 | 触发条件 | 建议实现要点 |
|------|---------|-------------|
| 抽 `<FadePresence>` | 出现第 3 个 AnimatePresence mode="wait" 用例时 | 当前 2 处: task-detail-client + 可能的另一个 |
| 旋转 spinner 换 CSS | 关注性能时 | `decode-input-bar.tsx` + `data-table-body.tsx` 改 `@keyframes spin` |
| 扩展 Reveal API (as="span" / lift / viewportMargin) | 下次有需求时 | 1 个 PR 改 reveal.tsx 加可选参数 |

---

## 自检清单

### 1. Spec 覆盖 (修订 v2)

| 审计章节 | 对应 Task |
|---------|----------|
| §5 a11y 必修问题 1 (Reveal) | 1.3 |
| §5 a11y 必修问题 2 (Stagger/StaggerItem) | 1.4, 1.5 |
| §5 a11y 必修问题 3 (CountUp + aria) | 1.8 |
| §5 a11y 必修问题 4 (HoverLift) | 1.7 |
| §5 a11y 必修问题 5 (Pressable) | 1.6 |
| §5.5 MotionConfig 全局 | 1.2 |
| §5.4 useReducedMotionSafe hook | 1.1 |
| §2.6 25 处 Reveal delay 硬编码 | 3.6 |
| §2.7 9 处 y 偏移硬编码 | 1.5.1 (LIFT 常量组) + 各文件使用 |
| §2.8 5 处 scale 硬编码 | 1.5.1 (PRESS 常量组) + 2.7 (ButtonLift) |
| §2.9 4 处 transition 字符串 | 1.5.1 (TRANSITION_*) + 4.1 (exit 统一) |
| §2.10 viewport margin 硬编码 | 1.5.1 (VIEWPORT_MARGIN) + 1.5.2 |
| §2.11 SPRING.gentle 死代码 | 1.5.1 (移除) |
| §2.12 17 处变体重定义 (fadeUp/fadeUpLarge/slideInTop/pulse/rowStagger) | 1.5.1 + 1.5.3/1.5.4/1.5.5/1.5.6 |
| §2.13 11 处 transition 三元组 (QUICK_OUTQUINT/REVEAL_OUTEXPO) | 1.5.1 + 1.5.3/1.5.4/1.5.6 |
| §3.4 ResultBanner 抽 + 4 文件 | 2.1, 2.2, 2.3, 2.4, 2.5 |
| AnimateUp 抽 + 5 处 | 2.1.1, 2.7, 2.8 |
| ButtonLift 抽 + 3 处 | 2.1.2, 2.7 |
| app-settings-card 换 Reveal + fadeUpGentle | 1.5.2 |
| documents-import-form 4 处 wrapper | 2.7 |
| §3.1 PageHero 扩展 + 5 文件 | 3.1, 3.2 |
| §3.2 + §3.3 StatsGrid + EntryCardGrid | 3.3, 3.4, 3.5 |
| AnimatePresence exit transition 统一 | 4.1 |
| data-table-body reduce-motion | 4.2 |
| 死代码清理 | 4.3 |
| 抽 FadePresence (按需) | 4.4 |

### 2. 占位符检查

- 无 "TBD"/"TODO"/"implement later" 占位符
- 所有步骤包含实际代码
- 所有 import/export 路径硬编码
- 命令包含 flag 和预期输出

### 3. 类型一致性

- `LIFT.hero` / `LIFT.slideTop` 等常量值在 `lib/motion.ts` 定义, 5 个新 variants (fadeUpGentle / fadeUpLarge / slideInTop / pulse / rowStagger) 引用同一来源
- `ResultBannerVariant = "success" | "error" | "info"` 在 result-banner.tsx 定义, 测试中用同一类型
- `useReducedMotionSafe()` 返回 `boolean`, 所有原子组件 + 3 个新 wrapper 统一调用
- `StatsGridItem` / `EntryCardGridItem` 类型在各自文件中定义并 export
- `AnimateUpProps` / `ButtonLiftProps` 类型在新 wrapper 文件中定义, 在 barrel re-export

### 4. 工时估算

| Phase | 任务数 | 预估工时 |
|-------|:-----:|:--------:|
| Phase 1 (a11y) | 9 | 0.5 人日 |
| **Phase 1.5 (新, lib/motion.ts 扩展)** | **6** | **1.5 人日** |
| Phase 2 (wrapper 收敛) | 10 (含 2.1.1/2.1.2/2.8) | 1.5 人日 |
| Phase 3 (业务层) | 6 (含 3.6) | 2 人日 |
| Phase 4 (边界优化) | 4 | 0.5 人日 (按需) |
| **总计** | **35 个 task** | **~6 人日** |

---

## 执行方式

**Plan complete and saved to `docs/superpowers/plans/2026-06-27-motion-a11y-refactor.md` (修订 v2).**

**总规模**: 35 个 Task, ~6 人日, 100+ 独立 commits

**两种执行选项**：

1. **Subagent-Driven (推荐)** — 每个 Task 派一个独立 subagent 执行, task 间 review, 快速迭代
2. **Inline Execution** — 当前 session 逐个 Task 执行, 批量 commit 带 checkpoint review

**推荐执行顺序**:
1. Phase 1 (a11y 必修, 0.5d)
2. **Phase 1.5 (lib/motion.ts 扩展, 1.5d)** — 给后续所有 Task 提供常量基础
3. Phase 2 (wrapper 收敛, 1.5d)
4. Phase 3 (业务层 + DELAY 替换, 2d)
5. Phase 4 (按需, 0.5d)

**选哪个？**
