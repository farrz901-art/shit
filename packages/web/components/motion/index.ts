/**
 * Motion 动画组件 barrel (2026-06-25 Task 5) — 业务页动画的统一入口
 *
 * 组件按"何时用 / 怎么动"分 4 类, 选择指南:
 *
 * 1) 入场 (mount 时动一次):
 *    - <FadeUp show={open} />           受控 show, true → 隐→显, false 不渲染
 *    - <Reveal>                          滚动入场 (initial=hidden → animate=show)
 *    - <Stagger> + <StaggerItem>         列表逐项延迟入场
 *    - <CountUp value={n} />            数字 0 → target 滚动到位
 *
 * 2) 进出都动 (mount + unmount 都动画):
 *    - <AnimateUp show={open} />        FadeUp + AnimatePresence, 有退场动画
 *    - <FadePresence mode="wait">        AnimatePresence 子组件, mode 控制是否等旧退出再入新
 *    - 常用于: toast / 通知条 / dialog body
 *
 * 3) 持续 / 触发型动画 (有交互时动):
 *    - <Pulse />                         持续脉冲 (常驻指示器, e.g. "处理中" 红点)
 *    - <HoverLift>                       悬停上浮 (卡片)
 *    - <ButtonLift>                      悬停 + 按下反馈 (按钮)
 *    - <Pressable>                       按下弹簧反馈 (iOS 风格)
 *
 * 4) 工具:
 *    - useReducedMotionSafe()           自动尊重 prefers-reduced-motion, 全部组件已内嵌
 *    - DUR / EASE / SPRING / CSS_EASE   时长 + 缓动常量 (从 @/lib/motion 引)
 *    - fadeIn / fadeUp / scaleIn / stagger  variants 工厂
 *
 * a11y: 全部组件 reduce-motion 模式下跳过动画 (WCAG 2.3.3 motion-from-essential).
 *       root layout 已 MotionConfig reducedMotion="user", 不用每个调用方操心.
 */
// Motion 组件 barrel (2026-06-25 Task 5)
export * from "./animated";
