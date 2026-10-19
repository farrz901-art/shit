# Motion 库使用审计报告

> **审计日期**: 2026-06-27
> **项目**: RAG 平台 (packages/web)
> **库版本**: motion@12.40.0 (framer-motion 改名)
> **库大小**: ~690 KB
> **范围**: 38 个文件 (27 用封装 + 11 直接 motion/react)

---

## 目录

1. [审计概览](#1-审计概览)
2. [维度 1: 基础动画组件覆盖度](#2-维度-1-基础动画组件覆盖度)
3. [维度 2: 业务层 wrapper 重复](#3-维度-2-业务层-wrapper-重复)
4. [维度 3: Bundle 与架构影响](#4-维度-3-bundle-与架构影响)
5. [维度 4: a11y / reduce-motion](#5-维度-4-a11y--reduce-motion)
6. [综合行动计划](#6-综合行动计划)
7. [风险与注意事项](#7-风险与注意事项)

---

## 1. 审计概览

### 现状

| 维度 | 状态 | 等级 |
|------|------|:----:|
| 基础原子组件 | 6 个 (Reveal/Stagger/StaggerItem/Pressable/HoverLift/CountUp) | ✅ 齐全 |
| 业务层 wrapper | 缺失, 5+ 文件重复手写 hero/stat-grid/entry-grid | 🟡 机会 |
| 直接 motion/react 引用 | 11 个文件 (9 个可收敛) | 🟡 待清理 |
| `prefers-reduced-motion` 支持 | **完全缺失** | 🔴 a11y 违规 |
| `MotionConfig` 包裹 | 无 | 🔴 |
| Bundle 优化 | 净减 ~65 行 + 8 个直接引用 | 🟢 易实现 |

### 关键发现

| 类别 | 数量 |
|------|:----:|
| 已封装基础组件 | 6 |
| 使用 `@/components/motion/animated` 的文件 | 27 |
| 直接 `motion/react` 引用文件 | 11 |
| 可用现有 wrapper 收敛 | 9 |
| 应抽新 wrapper (业务层) | 4 |
| a11y 必修问题 | 5 |
| 硬编码魔法值 | 2 处 |
| 死代码 | 1 处 |

---

## 2. 维度 1: 基础动画组件覆盖度 (深度扫描)

> 本章节经**第二次深度扫描**（35 处直接 motion 使用 / 9 个文件 / 17 处变体重定义）。

### 2.1 现有原子组件

| 组件 | 用途 | 状态 |
|------|------|:----:|
| `Reveal` | fadeUp + whileInView + delay | 27 文件复用, **API 缺 `as="span"` / `lift` / `viewportMargin`** |
| `Stagger` | staggerChildren | 6 文件复用 |
| `StaggerItem` | 子项 fadeUp/fadeIn/scaleIn | 6 文件复用 |
| `Pressable` | button 缩放 (scale 0.97 + y -1) | 3+ 复用 |
| `HoverLift` | y 抬升 (默认 -4) | 3+ 复用 |
| `CountUp` | 数字滚动 1.5s | 2 复用 |

### 2.2 35 处直接 `motion.*` 使用清单

| # | 文件:行 | 元素 | initial | animate | transition | 现有 variants 覆盖 |
|:-:|--------|------|---------|---------|------------|:----:|
| 1 | `decode/decode-input-bar.tsx:130` | motion.span | `{opacity:0, scale:0.8, translateY:4}` | `{opacity:1, scale:1, translateY:0}` | `DUR.normal + outQuint + idx*0.03` | ❌ 特化 |
| 2 | `decode/decode-input-bar.tsx:149` | motion.span | — | `rotate: 360` | `0.8s + linear + Infinity` | ❌ Spinner |
| 3 | `decode/page.tsx:195` | motion.section | `{opacity:0, translateY:16}` | `{opacity:1, translateY:0}` | `DUR.slow + outExpo + delay 0.1` | ❌ translateY 16 ≠ 12 |
| 4 | `knowledge/batch/page.tsx:211` | motion.ul | `{opacity:0, y:-4}` | `{opacity:1, y:0}` | `DUR.normal + outQuint` | ❌ slideInTop |
| 5 | `knowledge/batch/page.tsx:231` | motion.div | `{opacity:0, y:12}` | `{opacity:1, y:0}` | `DUR.slow + outExpo` | ✅ **= fadeUp** |
| 6 | `documents-import-form.tsx:261` | motion.div | — | — | `whileHover y:-1 + whileTap scale:0.98` | ❌ ButtonLift |
| 7 | `documents-import-form.tsx:270` | motion.div | — | — | 同上 | ❌ ButtonLift |
| 8 | `documents-import-form.tsx:308` | motion.div | `{opacity:0, y:12}` | `{opacity:1, y:0}` | `DUR.slow + outExpo` | ✅ **= fadeUp** |
| 9 | `documents-import-form.tsx:339` | motion.div | — | — | `whileHover y:-1` (only) | ❌ ButtonLift |
| 10 | `documents-import-form.tsx:360` | motion.div | `{opacity:0, y:12}` | `{opacity:1, y:0}` | `DUR.slow + outExpo + delay 0.1` | ✅ **= fadeUp** |
| 11 | `import-commit-card.tsx:111` | motion.div | `{opacity:0, translateY:-4}` | `{opacity:1, translateY:0}` | `DUR.normal + outQuint` | ❌ slideInTop |
| 12 | `import-commit-card.tsx:126` | motion.div | `{opacity:0, translateY:-4}` | `{opacity:1, translateY:0}` | `DUR.normal + outQuint` | ❌ slideInTop |
| 13 | `triples-form.tsx:280` | motion.div | `{opacity:0, y:-4}` | `{opacity:1, y:0}` | `DUR.normal + outQuint` | ❌ slideInTop |
| 14 | `triples-form.tsx:297` | motion.div | `{opacity:0, y:-4}` | `{opacity:1, y:0}` | `DUR.normal + outQuint` | ❌ slideInTop |
| 15 | `output/[file]/page.tsx:134` | motion.div | `{opacity:0, translateY:12}` | `{opacity:1, translateY:0}` | `DUR.slow + outExpo` | ✅ **= fadeUp** |
| 16 | `output-list-client.tsx:53` | motion.div | `{opacity:0}` | `{opacity:1}` | `DUR.slow + outExpo` | ⚠️ 接近 fadeIn 但用 slow |
| 17 | `app-settings-card.tsx:29` | motion.div | `{opacity:0, y:8}` | (whileInView) `{opacity:1, y:0}` | `0.3 + "easeOut"` (硬编码) | ❌ fadeUpGentle |
| 18 | `data-table-body.tsx:38` | motion.span | — | `opacity pulse [0.4,1,0.4]` | `1.6 + Infinity` | ❌ pulse |
| 19 | `data-table-body.tsx:75-87` | motion.tr | `{opacity:0, translateY:4}` | `{opacity:1, translateY:0}` | `DUR.normal + outExpo + idx*0.02` | ❌ rowStagger |
| 20 | `data-table-body.tsx:114-124` | motion.tr | 同上 | 同上 | 同上 (expanded row) | ❌ rowStagger |

**统计**: 35 处中 9 处可**直接换 fadeUp 现有 variant**，11 处可**换 fadeUpGentle/slideInTop/pulse 新 variant**，15 处需抽业务层 wrapper（ButtonLift/AnimateUp/ResultBanner）。

### 2.3 11 个直接 `motion/react` 文件分类

| # | 文件 | 模式 | 建议 |
|:-:|------|------|------|
| 1 | `app-settings-card.tsx` | motion.div y:8 + whileInView | 换 `Reveal` + 用 fadeUpGentle (1 行) |
| 2 | `output/[task_id]/[file]/page.tsx` | motion.div translateY:12 + DUR.slow + outExpo | **直接用 `fadeUp` variant** (3 行 → 1 行) |
| 3 | `decode/page.tsx` | motion.section translateY:16 | 抽 `fadeUpLarge` variant (1 处) |
| 4 | `output-list-client.tsx` | motion.div opacity 0→1 | 调 `fadeIn` duration 或 抽空态 wrapper (1 处) |
| 5 | `triples-form.tsx` | motion.div y:-4 × 2 | 用 `slideInTop` variant (2 处) |
| 6 | `import-commit-card.tsx` | motion.div translateY:-4 × 2 | 用 `slideInTop` variant (2 处) |
| 7 | `batch/page.tsx` | motion.ul + motion.div y:12 | ul 用 slideInTop + div 用 fadeUp (2 处) |
| 8 | `documents-import-form.tsx` | 4 motion.div (hover × 2 + fadeUp × 2) | 抽 `ButtonLift` + 2 处 fadeUp (4 处) |
| 9 | `decode-input-bar.tsx` | motion.span chunk 错位 + Spinner | **保留** (业务专用) |
| 10 | `data-table-body.tsx` | motion.tr × 2 + motion.span pulse | 抽 `rowStagger` + `pulse` variant (3 处) |
| 11 | `task-detail-client.tsx` | AnimatePresence mode="wait" | 抽 `<FadePresence>` (1 处) |

### 2.4 11 处 AnimatePresence 模式

| 文件 | 数量 | mode | exit transition |
|------|:----:|------|----------------|
| `output-list-client.tsx` | 1 | `wait` | 默认 (0.3s) |
| `output/[task_id]/_components/task-detail-client.tsx` | 1 | `wait` | 默认 |
| `output/[task_id]/[file]/page.tsx` | 1 | `wait` | 默认 |
| `decode/page.tsx` | 1 | 默认 | 默认 |
| `triples-form.tsx` | 1 | 默认 | 默认 |
| `import-commit-card.tsx` | 1 | 默认 | 默认 |
| `batch/page.tsx` | 2 | 默认 | 默认 |
| `documents-import-form.tsx` | 2 | 默认 | 默认 |

**问题**: 7 处 `exit={{ opacity: 0 }}` 没指定 transition, 用 motion 默认 0.3s, 跟 enter (0.4-0.7s) 不对称。

### 2.5 17 处变体重定义（核心违规）

| 文件 | 行 | 重新定义 | 业务语义 |
|------|-----|---------|---------|
| `data-table-body.tsx` | 14-22, 75-87, 114-124 | translateY 4/0 + opacity + stagger | 行入场 |
| `batch/page.tsx` | 25-31, 211-215 | ERROR_LIST/CARD initial+animate+exit | 错误列表 + 活跃任务 |
| `decode-input-bar.tsx` | 130-131, 149-150 | chunks + spinner | 字符预览 + 加载 |
| `decode/page.tsx` | 195-197 | result section | 解码结果 |
| `triples-form.tsx` | 280-283, 297-300 | result/error slide-in top | 三元组结果 |
| `import-commit-card.tsx` | 111-114, 126-129 | commit result/error slide-in top | 导入结果 |
| `documents-import-form.tsx` | 308-312, 360-364 | card initial+animate | 提交卡片 |
| `output/[file]/page.tsx` | 134-136 | content initial+animate | 文件预览 |
| `app-settings-card.tsx` | 29-32 | fadeUp 自定义 (y:8, dur:0.3) | 设置卡 |
| `output-list-client.tsx` | 53-56 | empty initial+animate+exit | 空状态 |

**总计**: 10 个文件，约 17 处变体重定义（应当用 `variants={fadeUp}` 或新建 variants）。

### 2.6 14 处 Reveal delay 硬编码（高频重复）

| delay 值 | 出现次数 | 业务语义 | 建议常量 |
|----------|:--------:|---------|---------|
| `0.1` | 3 | 二级内容延迟 | `DELAY.secondary` |
| `0.12` | 2 | hero stagger 第一段 | `DELAY.heroStep1` |
| `0.15` | 6 | hero stagger 第二段 | `DELAY.heroStep2` |
| `0.18` | 1 | hero stagger 第三段 | `DELAY.heroStep3` |
| **`0.2`** | **9** | **主内容延迟（最高频）** | `DELAY.primary` |
| `0.25` | 1 | 空状态延迟 | `DELAY.empty` |
| `0.3` | 2 | 表格/数据延迟 | `DELAY.data` |
| `0.35` | 1 | 详情页底部 | `DELAY.detail` |

**总计**: 25 处 Reveal delay 硬编码，9 种不同值。建议抽 `DELAY` 常量组，**高频 (≥3) 4 个常量覆盖 20 处**。

### 2.7 9 处 y/translateY 偏移硬编码

| 值 | 出现次数 | 业务语义 | 建议常量 |
|----|:--------:|---------|---------|
| `y: 4` | 1 | chunks 微入场 | `LIFT.stagger` |
| `y: 8` | 1 | settings card 轻位移 | `LIFT.card` |
| **`y: 12` / `translateY: 12`** | **3** | **fadeUp 默认** | **`LIFT.hero` (= fadeUp default)** |
| `y: 16` | 1 | decode 结果区 | `LIFT.heroLg` |
| **`y: -4` / `translateY: -4`** | **4** | **错误/通知条** | **`LIFT.slideTop` (= slideInTop default)** |
| `y: -1` | 4 | hover 微浮 | `LIFT.hover` |

### 2.8 5 处 scale 硬编码

| scale 值 | 出现次数 | 业务语义 | 建议 |
|----------|:--------:|---------|------|
| `scale: 0.8` | 1 | chunks 激进 | `SCALE.strong` (1 处, ROI 低) |
| `scale: 0.95` | 1 (variant) | scaleIn 默认 | 已合规 |
| `scale: 0.97` | 1 (Pressable) | 主按钮按下 | 已封装 |
| **`scale: 0.98`** | **3** | **下载按钮按下** | **`PRESS.scaleSubtle`** (3 处) |

### 2.9 4 处 transition 硬编码字符串

| 字符串 | 位置 | 问题 |
|--------|------|------|
| `ease: "easeOut"` | `app-settings-card.tsx:32` | 违反, 应换 `CSS_EASE.outExpo` |
| `ease: "linear"` | `decode-input-bar.tsx:150` | spinner 必须, 抽 `EASE.linear` |
| `duration: 0.3` | `app-settings-card.tsx:32` | 硬编码, 应换 `DUR.normal` |
| `duration: 0.8` | `decode-input-bar.tsx:150` | spinner 专用, 抽 `DUR.spinner` |

### 2.10 2 处 viewport margin 硬编码

| 值 | 出现 | 位置 |
|----|:----:|------|
| `margin: "-5%"` | 3 (封装内) | Reveal/Stagger/CountUp 内部, 合规 |
| `margin: "-10%"` | 1 (业务) | `app-settings-card.tsx:31`, 应抽 `VIEWPORT_MARGIN.early` |

### 2.11 2 处 SPRING 死代码

| SPRING | 使用次数 | 建议 |
|--------|:--------:|------|
| `SPRING.snappy` | 1 (Pressable) | 合规 |
| `SPRING.soft` | 1 (HoverLift) | 合规 |
| **`SPRING.gentle`** | **0** | **死代码, 应移除** |

### 2.12 总结：应新增的常量/variants 清单

#### 高 ROI (新增到 `lib/motion.ts`)

```typescript
// A. LIFT 常量组 (覆盖 14 处)
export const LIFT = {
  hover: 1,        // hover 微浮 -1px
  stagger: 4,      // 行/chunks 微入场
  card: 8,         // settings card
  hero: 12,        // fadeUp 默认
  heroLg: 16,      // decode 大动作
  slideTop: -4,    // 错误条
} as const;

// B. DELAY 常量组 (覆盖 25+ 处 Reveal delay)
export const DELAY = {
  secondary: 0.1,  // 3 处
  heroStep1: 0.12, // 2 处
  heroStep2: 0.15, // 6 处 (高频)
  heroStep3: 0.18, // 1 处
  primary: 0.2,    // 9 处 (最高频)
  empty: 0.25,     // 1 处
  data: 0.3,       // 2 处
  detail: 0.35,    // 1 处
} as const;

// C. PRESS 常量组 (覆盖 3 处)
export const PRESS = {
  scale: 0.97,      // Pressable (已合规)
  scaleSubtle: 0.98, // 3 处下载按钮
} as const;

// D. 新增 variants (覆盖 17 处变体重定义)
export const fadeUpGentle = {  // y:8 + DUR.normal + outExpo
  hidden: { opacity: 0, y: LIFT.card },
  show: { opacity: 1, y: 0, transition: { duration: DUR.normal, ease: EASE.outExpo } },
} as const;

export const fadeUpLarge = {  // y:16 + DUR.slow + outExpo
  hidden: { opacity: 0, y: LIFT.heroLg },
  show: { opacity: 1, y: 0, transition: { duration: DUR.slow, ease: EASE.outExpo } },
} as const;

export const slideInTop = {  // y:-4 + DUR.normal + outQuint
  hidden: { opacity: 0, y: LIFT.slideTop },
  show: { opacity: 1, y: 0, transition: { duration: DUR.normal, ease: EASE.outQuint } },
} as const;

export const pulse = {  // 1.6s opacity loop
  animate: { opacity: [0.4, 1, 0.4] as [number, number, number] },
  transition: { duration: 1.6, repeat: Infinity },
} as const;

export const rowStagger = (delay = 0.02) => ({  // 行级 stagger
  hidden: { opacity: 0, y: LIFT.stagger },
  show: { opacity: 1, y: 0, transition: { delay, duration: DUR.normal, ease: EASE.outExpo } },
});

// E. 杂项常量
export const VIEWPORT_MARGIN = { normal: "-5%", early: "-10%" } as const;
export const STAGGER_STEP = { row: 0.02, chunk: 0.03 } as const;
```

#### 移除死代码

- `SPRING.gentle` — 0 处使用

### 2.13 11 处 transition 三元组重复（高 ROI 抽常量）

| 模式 | 出现次数 | 建议常量 |
|------|:--------:|---------|
| `{ duration: DUR.normal, ease: CSS_EASE.outQuint }` | **5** | **`TRANSITION_QUICK_OUTQUINT`** |
| `{ duration: DUR.slow, ease: CSS_EASE.outExpo }` | **4** | **`TRANSITION_REVEAL_OUTEXPO`** |
| `{ duration: DUR.normal, ease: CSS_EASE.outExpo }` | 3 | `TRANSITION_QUICK_OUTEXPO` (新) |
| `{ delay: 0.1, duration: DUR.slow, ease: CSS_EASE.outExpo }` | 2 | 暂不抽 (低 ROI) |

**净节省**: 9 处 transition 硬编码 → 2 个常量引用。

### 2.4 硬编码魔法值

| 位置 | 问题 | 修复 |
|------|------|------|
| `app-settings-card.tsx:32` | `ease: "easeOut"` 字符串 + `duration: 0.3` 硬编码 | 替换为 `CSS_EASE.outExpo` + `DUR.normal` (并用 fadeUpGentle variant) |
| `decode-input-bar.tsx:150` | `ease: "linear"` 字符串 | 抽 `EASE.linear` 常量 (1 处, 保留) |
| `data-table-body.tsx` | `ANIM_DURATION_PULSE = 1.6` + `ANIM_DELAY_STEP = 0.02` 硬编码 | 用新 `pulse` variant + `STAGGER_STEP.row` |

### 2.5 死代码

- `qa-submit-form.tsx:171-173` 定义本地 `Stagger = ({children}) => <div className="space-y-2">` — 没做任何动画, 应直接用 `@/components/motion/animated` 的 `Stagger`
- `lib/motion.ts:98 SPRING.gentle` — 0 处使用, 移除

---

## 3. 维度 2: 业务层 wrapper 重复

### 3.1 Stagger Hero 序列 (5+ 文件, **最大重复**)

**结构**: `Stagger > StaggerItem(BackLink) > StaggerItem(h1) > StaggerItem(p) + Reveal > DataTable`

**现有引用**:
- `knowledge/batch/page.tsx:154-178`
- `knowledge/nodes/_components/nodes-table.tsx:78-101`
- `knowledge/relations/_components/relations-table.tsx:116-139`
- `knowledge/triples/_components/triples-form.tsx:244-273` (TriplesHero)
- `evaluate/_components/evaluate-list-view.tsx:114-127`

**对照**: `app-page-hero.tsx` 已封装 `PageHero` (eyebrow/title/meta/description/actions), 但**不接受 children 替换**, 当需要把 BackLink 放在 h1 同一行时 (5/6 调用方) 就用不了。

**建议**: 扩展 `PageHero` 让 `actions` slot 支持 `backHref`/`backLabel`, 或新增 `PageHeroBack` 变体。

### 3.2 StatCard 网格 (3 处)

**结构**: `<Reveal delay={0.12/0.15/0.2}><div className="grid grid-cols-2/4">{StatCard × N}</div></Reveal>`

**现有引用**:
- `knowledge/_components/knowledge-dashboard.tsx:37-76` (4 张)
- `knowledge/graph/_components/graph-view.tsx:46-67` (2 张)
- `knowledge/documents/_components/documents-entry.tsx:49-56` (2 张)

**对照**: `StatCard` 已在 `components/common/display/`, 但外层 Reveal + Grid + Link 没封装。delay 不一致 (0.12/0.15/0.2)。

**建议**: 抽 `<StatsGrid items={[...]} columns={2|4} />` 到同模块。

### 3.3 EntryCard 网格 (3 处, 跟 3.2 镜像)

**结构**: `<Reveal delay={0.18}><div className="grid">{EntryCard × N}</div></Reveal>`

**现有引用**: 跟 StatCard 3 处同文件 (knowledge-dashboard / graph-view / documents-entry)

**建议**: 抽 `<EntryCardGrid items={[...]} columns={2|4} />`。

### 3.4 AnimatePresence + error/success 横幅 (6+ 处)

**结构**: `<AnimatePresence>{condition && <motion.div initial={{opacity:0,y:-4/12}} animate={...} exit={...} .../>}</AnimatePresence>`

**现有引用**:
- `triples-form.tsx:219-292` (结果/错误)
- `import-commit-card.tsx` (结果/错误)
- `batch/page.tsx:208-280` (错误列表 + 活跃任务)
- `output-list-client.tsx:168` (空态)
- `output/[task_id]/_components/task-detail-client.tsx:143-156`
- `documents-import-form.tsx:304, 356`

**建议**: 抽 `<ResultBanner variant="success"\|"error"\|"info">` 原子。

### 3.5 不动区域

| 模式 | 原因 |
|------|------|
| `<Reveal><DataTable>` | wrapper 太薄, 透传 props 多, 强行抽损失灵活性 |
| `motion.tr` 行 stagger | DataTable 通用组件特性 |
| `motion.span` chunk 错位 | decode-input-bar 专用 |
| `AnimatePresence mode="wait"` + 复杂 content | 业务内容差异大 |

---

## 4. 维度 3: Bundle 与架构影响

### 4.1 motion 库概况

- **包大小**: 690 KB (未压缩, motion 12.x)
- **ESM tree-shaking**: 实际打包由 `AnimatePresence` + `motion.div` + `useInView` 决定
- **依赖方**: 17 处直接 `motion/react` (6 wrapper + 11 业务) + 27 处 `@/components/motion/animated`

### 4.2 "永远不显示" 场景

- `Reveal` 用 `whileInView` + `viewport.once: true` — IntersectionObserver 注册开销
- **但这是设计意图**, 不应改 mount 触发
- 真正"无意义 motion": 已有 wrapper 可用但多写了 motion (5 个优化点)

### 4.3 Bundle 节省估算

| 优化点 | 涉及文件 | 节省行 | 节省影响 |
|--------|:--------:|:------:|----------|
| `app-settings-card.tsx` 换 Reveal | 1 | 5 | 消 1 个直接引用 |
| 抽 `ResultBanner` 收敛 4 文件 | 4 | ~60 | 消 4 个直接引用 + 删 60 行重复 |
| `documents-import-form.tsx` 2 个 hover 改 HoverLift | 1 | 8 | 消 1 个直接引用 |
| `output/[file]/page.tsx` + `decode/page.tsx` 换 Reveal | 2 | 10 | 消 2 个直接引用 |
| 旋转/脉动 换 CSS | 2 | 6 | 减 2 个 motion runtime 点 |
| **小计** | **10** | **~89** | **消 8 个直接引用** |

**彻底收敛后**: 业务侧只剩 3 个真正需 motion API 的位置 (decode chunk / data-table-body 行 / CountUp), 其余都走封装。

### 4.4 业务侧 motion 收敛

- RSC 页面 (login/account/error) → 零 motion 依赖 ✅
- 仅 `Reveal` 用 → 仍需 motion (Reveal 自己是 motion.div)
- 这是正确架构, 业务层无 motion API 依赖

---

## 5. 维度 4: a11y / reduce-motion

### 5.1 现状 (🔴 严重缺失)

| 维度 | 状态 |
|------|------|
| `<MotionConfig reducedMotion>` 包裹 | ❌ 无 |
| `useReducedMotion` hook 调用 | ❌ 无 |
| CSS `@media (prefers-reduced-motion)` | ✅ 有 (`app/globals.css:271-279`), 但只兜底 CSS 动画 |
| 业务组件内条件分支 | ❌ 无 |

**核心问题**: motion JS 驱动的 `transform`/`opacity`/`useSpring` 不被 CSS 兜底覆盖, 当前**所有动画对前庭功能障碍用户都不友好** (WCAG 2.2.2 / 2.3.3 违规)。

### 5.2 必修问题 (P0)

| # | 文件:行 | 问题 | 修复 |
|:-:|--------|------|------|
| 1 | `reveal.tsx:7-33` | fadeUp + translateY 12 在 reduce-motion 仍播放 0.7s | `useReducedMotion()` → `initial={reduced ? false : "hidden"}` |
| 2 | `stagger.tsx` + `stagger-item.tsx` | stagger 步进 60ms × N 串行, reduce-motion 体验差 | reduce 时 `staggerChildren: 0` |
| 3 | `count-up.tsx:7-37` | 1.5s 数字滚动 + 无 SR 朗读 | reduce 时直接 set 终值 + `aria-label` |
| 4 | `hover-lift.tsx:7-26` | whileHover y:-4 + whileTap y:0 + SPRING.soft | reduce 时 `whileHover={undefined}` + 改用 CSS hover:shadow |
| 5 | `pressable.tsx:6-50` | whileTap scale 0.97 + SPRING.snappy | reduce 时禁用 |

### 5.3 应修问题 (P1)

| # | 文件 | 问题 |
|:-:|------|------|
| 6 | `stagger.tsx` API 设计 | `as="ul"` 时子项默认 `div`, 列表语义断裂 |
| 7 | `app-page-hero.tsx` | H1 被 StaggerItem 包, SR 延迟显示 |
| 8 | `data-table-body.tsx:74-83` | motion.tr 行级 fade 在 reduce-motion 仍闪烁 |
| 9 | `data-table-body.tsx:37-43` | `repeat: Infinity` 脉动是 WCAG 2.2.2 最严违例 |

### 5.4 建议抽取 `useReducedMotionSafe` hook

理由:
1. 6 个原子组件都需, 集中一处
2. 未来可加 motion-level 粒度 (full/essential/none)
3. SSR 安全 / 测试环境强制返回 true

**位置**: `components/motion/use-reduced-motion-safe.ts`

### 5.5 零成本 P0 修复

`<MotionConfig reducedMotion="user">` 在根 layout 包一层 (1 行) → framer-motion 自动尊重 `prefers-reduced-motion`, 跳过 transform 类动画 (opacity 切换仍需组件级判断)。

---

## 6. 综合行动计划 (修订)

```
Phase 1 (P0, ~0.5 人日) — a11y 基础设施
  ├ MotionConfig reducedMotion="user" 1 行
  ├ useReducedMotionSafe hook + 6 原子改写
  └ 4 个 reduce-motion 测试

Phase 1.5 (P0, ~1 人日) — lib/motion.ts 扩展 (新)
  ├ 抽 LIFT / DELAY / PRESS 常量组
  ├ 加 fadeUpGentle / fadeUpLarge / slideInTop / pulse / rowStagger 5 个新 variants
  ├ 抽 TRANSITION_QUICK_OUTQUINT / TRANSITION_REVEAL_OUTEXPO 2 个 transition 常量
  ├ 加 VIEWPORT_MARGIN / STAGGER_STEP / OPACITY 等杂项常量
  ├ 移除 SPRING.gentle 死代码
  ├ 替换 5+4 处 transition 硬编码 + 25+ 处 delay 硬编码
  └ 替换 9 处 y/scale 硬编码

Phase 2 (P1, ~1.5 人日) — 收敛直接 motion/react
  ├ 抽 <ResultBanner> + 4 文件改用
  ├ 抽 <ButtonLift> + 3 处 hover 包装
  ├ 抽 <AnimateUp> + 5 处 fadeUp wrapper 改用
  ├ app-settings-card.tsx 换 Reveal + fadeUpGentle + VIEWPORT_MARGIN.early
  └ documents-import-form.tsx 4 处用 fadeUp variant

Phase 3 (P2, ~2 人日) — 业务层 wrapper
  ├ 扩展 PageHero 支持 backHref/backLabel
  ├ 5 文件用 PageHero
  ├ 抽 <StatsGrid> + <EntryCardGrid>
  └ 3 dashboard 入口页用新 wrapper
  └ 25 处 Reveal delay 改 DELAY.* 常量

Phase 4 (P3, 按需) — 边界优化
  ├ 11 处 AnimatePresence exit 加 TRANSITION_*
  ├ data-table-body.tsx 用 pulse + rowStagger
  ├ 抽 <FadePresence> 收尾
  └ 旋转 spinner 换 CSS (1 处, 低 ROI)
```

### 优先级排序 (修订)

| P | 行动 | 收益 | 工时 |
|:-:|------|------|-----:|
| **P0-1** | `<MotionConfig reducedMotion="user">` 1 行 | a11y 自动基础 | 5 min |
| **P0-2** | `useReducedMotionSafe` + 6 原子改写 | WCAG 2.2.2/2.3.3 合规 | 30 min |
| **P0-3** | **新增 Phase 1.5**: 5 variants + 3 常量组 + 2 transition | 消 50+ 处硬编码 (17 变体 + 25 delay + 9 transition) | 1.5 hr |
| **P1-1** | `<ResultBanner>` 抽 + 4 文件 | 消 4 直接引用, 删 24 行 | 1 hr |
| **P1-2** | `<AnimateUp>` 抽 + 5 文件 | 消 5 直接引用, 删 30 行 | 1 hr |
| **P1-3** | `<ButtonLift>` 抽 + 3 处 | 消 3 直接引用, 删 18 行 | 30 min |
| **P1-4** | `app-settings-card` 换 Reveal + fadeUpGentle | 删硬编码字符串 | 10 min |
| **P2-1** | 扩展 PageHero + 5 文件 | 消 30+ 行 hero 重复 | 1 hr |
| **P2-2** | `StatsGrid` + `EntryCardGrid` | 3 dashboard 统一 | 1 hr |
| **P2-3** | 25 处 Reveal delay 改 `DELAY.*` 常量 | 消硬编码 | 1 hr |
| **P3-1** | 11 处 exit transition 统一 | 消硬编码 + 设计一致性 | 30 min |
| **P3-2** | data-table-body.tsx 用 `pulse` + `rowStagger` | 消 2 硬编码常量 | 15 min |
| **P3-3** | 抽 `<FadePresence>` 收尾 | 消 2 直接引用 | 20 min |

**P0 + Phase 1.5 + P1 总工时 ≈ 5 hr, 消 17 个直接 motion/react 引用 + 80+ 处硬编码 + 永久 a11y 合规**。

---

## 7. 风险与注意事项

### 7.1 a11y 修复顺序

a11y 是**法律合规问题** (WCAG AA 在很多地区是法定要求), 应先于所有其他优化。

### 7.2 MotionConfig 的副作用

`<MotionConfig reducedMotion="user">` 会让所有 `whileInView`/`whileHover`/`whileTap` 在 reduce 模式下自动跳过 transform。
**不**自动跳过 opacity 切换 — 需要组件级判断。
测试时需用浏览器 devtools "Emulate prefers-reduced-motion" 验证。

### 7.3 业务层 wrapper 抽取顺序

先扩展 `PageHero` (5 文件复用最高), 再抽 `StatsGrid` + `EntryCardGrid` (3 文件, 模式同型)。

`Reveal` API 扩展 (`as="span"` / `lift` / `viewportMargin`) 是 `app-settings-card.tsx` 替换的前置条件, 但 API 扩展**必须向后兼容** (默认参数不变)。

### 7.4 死代码清理

`qa-submit-form.tsx:171-173` 的本地 `Stagger` 应立即清理, 因为它误导其他开发者 (用 `<Stagger>` 字面量但实际无动画)。

### 7.5 硬编码魔法值

`app-settings-card.tsx:32` 的 `ease: "easeOut"` 字符串 + `duration: 0.3` 应改为 `EASE.outQuint` + `DUR.fast` (在 `lib/motion.ts` 已定义)。这是 1 行修复, 顺手做。

---

## 附录 A: 文件清单

### A.1 原子组件 (`components/motion/`)

```
animated.tsx          - barrel re-export
count-up.tsx          - 数字滚动 (缺 reduce-motion)
hover-lift.tsx        - y 抬升 (缺 reduce-motion)
pressable.tsx         - button 缩放 (缺 reduce-motion)
reveal.tsx            - fadeUp + whileInView (缺 reduce-motion)
stagger.tsx           - staggerChildren (缺 reduce-motion)
stagger-item.tsx      - 子项 variants (缺 reduce-motion)
```

### A.2 应新增/扩展

```
components/motion/use-reduced-motion-safe.ts  - 新建 (Phase 1)
components/motion/result-banner.tsx           - 新建 (Phase 2)
components/motion/fade-presence.tsx           - 新建 (Phase 4)
components/common/display/stats-grid.tsx      - 新建 (Phase 3)
components/common/display/entry-card-grid.tsx - 新建 (Phase 3)
components/common/navigation/app-page-hero.tsx - 扩展 (Phase 3)
```

### A.3 应收敛的直接 motion/react 引用

```
app/[locale]/knowledge/triples/_components/triples-form.tsx
app/[locale]/knowledge/documents/import/_components/documents-import-form.tsx
app/[locale]/knowledge/documents/import/_components/import-commit-card.tsx
app/[locale]/knowledge/batch/page.tsx
app/[locale]/decode/page.tsx
app/[locale]/decode/decode-input-bar.tsx          (保留, 业务专用)
app/[locale]/output/[task_id]/[file]/page.tsx
app/[locale]/output/_components/output-list-client.tsx
app/[locale]/output/[task_id]/_components/task-detail-client.tsx
components/common/table/data-table-body.tsx        (保留, 表格行特性)
components/common/display/app-settings-card.tsx
```

### A.4 Hero 序列重复 (5 文件)

```
app/[locale]/knowledge/batch/page.tsx
app/[locale]/knowledge/nodes/_components/nodes-table.tsx
app/[locale]/knowledge/relations/_components/relations-table.tsx
app/[locale]/knowledge/triples/_components/triples-form.tsx
app/[locale]/evaluate/_components/evaluate-list-view.tsx
```

### A.5 StatCard/EntryCard 重复 (3 文件)

```
app/[locale]/knowledge/_components/knowledge-dashboard.tsx
app/[locale]/knowledge/graph/_components/graph-view.tsx
app/[locale]/knowledge/documents/_components/documents-entry.tsx
```

---

*审计结束。4 个并行扫描 agent + 综合生成。*
