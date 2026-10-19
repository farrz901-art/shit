// 集中封装 useReducedMotion() — a11y (WCAG 2.3.3) 统一判断 (2026-06-28 motion-a11y-refactor §1.1)
// motion 库的 useReducedMotion() 在 SSR/测试环境返回 null,
// 我们统一 ?? false 让调用方拿到确定的 boolean, 不用每处都 null check.
//
// 调用方: 所有 motion 原子组件 (Reveal/Stagger/Pressable/HoverLift/CountUp...) 一律引用本 hook,
// 不要再各自 useReducedMotion() 拿原始 nullable 返回值.

import { useReducedMotion } from "motion/react";

/**
 * 返回 boolean (而非 boolean | null) 的 reduce-motion 判断.
 *  - SSR 阶段返回 false (motion 库本身 SSR-safe)
 *  - 测试环境可显式 override (后续可加)
 */
export const useReducedMotionSafe = (): boolean => useReducedMotion() ?? false;
