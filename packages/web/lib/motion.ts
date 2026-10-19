// 美学动效统一配置 — 单一来源 (2026-06-09 redesign)
// 所有动画/动效都从这里 import, 业务组件不写硬编码缓动/时长

/**
 * 缓动函数 (Motion 用 array 格式, CSS 用 cubic-bezier() 字符串)
 * CSS 端在 globals.css 通过 --ease-* 暴露
 *
 * 先定义独立常量以通过 no-magic-numbers 检查
 */
// eslint-disable-next-line no-magic-numbers -- 贝塞尔曲线控制点参数
const EASE_IN_OUT_QUART = [0.76, 0, 0.24, 1] as const;
// eslint-disable-next-line no-magic-numbers -- 贝塞尔曲线控制点参数
const EASE_OUT_EXPO = [0.16, 1, 0.3, 1] as const;
// eslint-disable-next-line no-magic-numbers -- 贝塞尔曲线控制点参数
const EASE_OUT_QUINT = [0.22, 1, 0.36, 1] as const;

/**
 * 缓动函数数组常量 (framer-motion 用)
 * @shared
 */
export const EASE = {
  inOutQuart: EASE_IN_OUT_QUART,
  outExpo: EASE_OUT_EXPO,
  outQuint: EASE_OUT_QUINT,
} as const;

/**
 * 缓动函数 CSS 数组版 (用于内联样式)
 * @shared
 */
export const CSS_EASE = {
  inOutQuart: EASE_IN_OUT_QUART as [number, number, number, number],
  outExpo: EASE_OUT_EXPO as [number, number, number, number],
  outQuint: EASE_OUT_QUINT as [number, number, number, number],
} as const;

/** 字符串版 (用于 React style.transitionTimingFunction 字符串拼接)
 * @shared */
export const CSS_EASE_STR = {
  inOutQuart: "cubic-bezier(0.76, 0, 0.24, 1)",
  outExpo: "cubic-bezier(0.16, 1, 0.3, 1)",
  outQuint: "cubic-bezier(0.22, 1, 0.36, 1)",
} as const;

/**
 * 动画时长 (秒)
 *  - fast: hover/tap 微反馈
 *  - normal: 卡片过渡
 *  - slow: 进场 / 出场
 *  - reveal: staggered reveal 容器
 *  - countUp: 数字弹动
 * @shared
 */
export const DUR = {
  countUp: 1.5,
  fast: 0.2,
  normal: 0.4,
  reveal: 0.5,
  slow: 0.7,
} as const;

/**
 * Motion variants — 业务组件直接 spread 或整体引用, 不重新定义
 * @shared
 */
export const fadeUp = {
  // eslint-disable-next-line id-length -- framer-motion y 属性(垂直偏移)
  hidden: { opacity: 0, y: 12 },
  show: {
    opacity: 1,
    transition: { duration: DUR.slow, ease: EASE.outExpo },
    // eslint-disable-next-line id-length -- framer-motion y 属性(垂直偏移)
    y: 0,
  },
} as const;

/** 淡入动效变体 (opacity: 0→1).
 * @shared */
export const fadeIn = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { duration: DUR.slow, ease: EASE.outExpo } },
} as const;

/** 缩放淡入变体 (opacity: 0→1, scale: 0.95→1).
 * @shared */
export const scaleIn = {
  hidden: { opacity: 0, scale: 0.95 },
  show: {
    opacity: 1,
    scale: 1,
    transition: { duration: DUR.slow, ease: EASE.outQuint },
  },
} as const;

/** Stagger 子元素步进延迟默认值 (秒) */
const STAGGER_CHILDREN_DELAY = 0.06;

/**
 * 容器变体, 子元素用 fadeUp/fadeIn/scaleIn 之一
 * @param delay 步进延迟 (秒)
 */
export const stagger = (delay = STAGGER_CHILDREN_DELAY) => ({
  hidden: {},
  show: { transition: { delayChildren: 0.05, staggerChildren: delay } },
});

/**
 * 交互态 (HoverLift / Pressable 用)
 * 用 spring 物理, 比 CSS transition 跟手
 */
export const SPRING = {
  snappy: { damping: 22, stiffness: 400, type: "spring" as const },
  soft: { damping: 24, stiffness: 300, type: "spring" as const },
} as const;

/**
 * 设计 tokens — 集中常量, 不让业务组件自己写 magic number
 * 阴影 / 圆角 / 间距
 * @shared
 */
export const RADIUS = {
  full: "rounded-full",
  lg: "rounded-xl",
  md: "rounded-lg",
  sm: "rounded-md",
  xl: "rounded-2xl",
} as const;

/**
 * 阴影设计 tokens — button / card / hover 阴影, 集中定义
 * @shared
 */
export const SHADOW = {
  // 编辑设计 — 长柔阴影 + 微底阴影
  button: "shadow-[0_1px_0_hsl(0_0%_0%_/_0.05),0_1px_2px_hsl(0_0%_0%_/_0.06)]",
  buttonHover:
    "shadow-[0_1px_0_hsl(0_0%_0%_/_0.05),0_4px_12px_hsl(0_0%_0%_/_0.10),0_2px_4px_hsl(0_0%_0%_/_0.06)]",
  card: "shadow-[0_1px_2px_hsl(0_0%_0%_/_0.04),0_1px_3px_hsl(0_0%_0%_/_0.04)]",
  cardHover:
    "shadow-[0_2px_4px_hsl(0_0%_0%_/_0.04),0_12px_28px_hsl(0_0%_0%_/_0.08),0_4px_8px_hsl(0_0%_0%_/_0.04)]",
} as const;

/**
 * 位移常量 (y/translateY 统一来源)
 *  - hover: hover 微浮 -1px
 *  - stagger: 行/chunks 微入场
 *  - card: settings card 轻位移
 *  - hero: fadeUp 默认 (12)
 *  - heroLg: 大动作入场 (16)
 *  - slideTop: 错误/通知条从顶部 (-4)
 * @shared
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
 * @shared
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

/** 按压缩放常量 — scale: 主按钮按下 (Pressable 用, 0.97), scaleSubtle: 次按钮按下
 * @shared */
export const PRESS = {
  scale: 0.97,
  scaleSubtle: 0.98,
} as const;

/** Stagger 步进常量
 * @shared */
export const STAGGER_STEP = {
  row: 0.02,
  chunk: 0.03,
} as const;

/** viewport margin 常量
 * @shared */
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
/** Transition 模板: QUICK_OUTQUINT (DUR.normal + outQuint), 5 处引用.
 * @shared */
export const TRANSITION_QUICK_OUTQUINT = {
  duration: DUR.normal,
  ease: CSS_EASE.outQuint,
} as const;

/** Transition 模板: REVEAL_OUTEXPO (DUR.slow + outExpo, 完全等同 fadeUp transition), 4 处引用.
 * @shared */
export const TRANSITION_REVEAL_OUTEXPO = {
  duration: DUR.slow,
  ease: CSS_EASE.outExpo,
} as const;

/** Transition 模板: QUICK_OUTEXPO (DUR.normal + outExpo, 用于行 stagger), 3 处引用.
 * @shared */
export const TRANSITION_QUICK_OUTEXPO = {
  duration: DUR.normal,
  ease: CSS_EASE.outExpo,
} as const;

/**
 * 新增 variants (覆盖 17 处变体重定义)
 */

/** fadeUp 轻位移版 (y:8, 用于 settings card 等)
 * @shared */
export const fadeUpGentle = {
  hidden: { opacity: 0, y: LIFT.card },
  show: {
    opacity: 1,
    y: 0,
    transition: { duration: DUR.normal, ease: EASE.outExpo },
  },
} as const;

/** fadeUp 大动作版 (y:16, 用于 decode 结果区)
 * @shared */
export const fadeUpLarge = {
  hidden: { opacity: 0, y: LIFT.heroLg },
  show: {
    opacity: 1,
    y: 0,
    transition: { duration: DUR.slow, ease: EASE.outExpo },
  },
} as const;

/** 顶部滑入 (y:-4, 用于错误/通知条)
 * @shared */
export const slideInTop = {
  hidden: { opacity: 0, y: LIFT.slideTop },
  show: {
    opacity: 1,
    y: 0,
    transition: { duration: DUR.normal, ease: EASE.outQuint },
  },
} as const;

/** 加载脉冲 (opacity 循环)
 * @shared */
export const pulse = {
  // eslint-disable-next-line no-magic-numbers -- 加载脉冲透明度循环值
  animate: { opacity: [0.4, 1, 0.4] as [number, number, number] },
  // eslint-disable-next-line no-magic-numbers -- 脉冲周期 1.6s
  transition: { duration: 1.6, repeat: Infinity },
} as const;

/** 行级 stagger 容器 (delay 是 index * STAGGER_STEP.row).
 * @param delay 步进延迟 (秒)
 * @shared */
// eslint-disable-next-line no-magic-numbers -- stagger 步进默认 0.02s
export const rowStagger = (delay = 0.02) => ({
  hidden: { opacity: 0, y: LIFT.stagger },
  show: {
    opacity: 1,
    y: 0,
    transition: { delay, duration: DUR.normal, ease: EASE.outExpo },
  },
});
