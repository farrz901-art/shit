"use client";
/**
 * Button 悬浮包装 — motion.div + whileHover y:-1 + whileTap scale:0.98
 * 用于下载按钮/链接的微反馈, 替代多处内联 motion.div
 * @param props.children 子节点
 * @param props.className 容器类名
 * @returns JSX 元素
 * @client-bff
 */
import { type ReactNode } from "react";
import { motion } from "motion/react";
import { useReducedMotionSafe } from "./use-reduced-motion-safe";
import { LIFT, PRESS } from "@/lib/motion";

/** ButtonLift 组件的属性 */
export interface ButtonLiftProps {
  children: ReactNode;
  className?: string;
}

/**
 * ButtonLift — Button 悬浮抬升包装, whileHover y:-1 + whileTap scale:0.98
 * @param props.children 子节点
 * @param props.className 容器类名
 * @returns JSX 元素
 * @client-bff
 */
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
