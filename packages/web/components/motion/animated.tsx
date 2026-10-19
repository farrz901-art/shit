"use client";
// 动画原子组件 barrel 文件 (2026-06-09 redesign)
// 各组件已拆分到独立文件, 从此文件统一重新导出

export {
  CSS_EASE,
  CSS_EASE_STR,
  DUR,
  EASE,
  SPRING,
  fadeIn,
  fadeUp,
  scaleIn,
  stagger,
} from "@/lib/motion";
export { CountUp } from "./count-up";
export { FadePresence, type FadePresenceMode, type FadePresenceProps } from "./fade-presence";
export { AnimateUp, type AnimateUpProps } from "./animate-up";
export { ButtonLift, type ButtonLiftProps } from "./button-lift";
export { FadeUp, type FadeUpProps } from "./fade-up";
export { HoverLift } from "./hover-lift";
export { Pressable } from "./pressable";
export { Pulse } from "./pulse";
export { Reveal } from "./reveal";
export { Stagger } from "./stagger";
export { StaggerItem } from "./stagger-item";
export { useReducedMotionSafe } from "./use-reduced-motion-safe";
