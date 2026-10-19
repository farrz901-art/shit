"use client";
/**
 * 呼吸动画包装 — opacity 循环 [0.4, 1, 0.4] + 1.6s + repeat Infinity
 * reduce 模式: 直接显示文字, 无动画
 * @param props.children 子节点
 * @param props.className 容器类名
 * @returns JSX 元素
 * @client-bff
 */
import { type ReactNode } from "react";
import { motion } from "motion/react";
import { pulse } from "@/lib/motion";
import { useReducedMotionSafe } from "./use-reduced-motion-safe";

/** Pulse 组件的属性 */
export interface PulseProps {
  children: ReactNode;
  className?: string;
}

/**
 * Pulse — 呼吸动画包装, opacity 循环 [0.4, 1, 0.4]
 * @param props.children 子节点
 * @param props.className 容器类名
 * @returns JSX 元素
 * @client-bff
 */
export const Pulse = ({ children, className }: PulseProps) => {
  const reduced = useReducedMotionSafe();
  if (reduced) {
    return <span className={className}>{children}</span>;
  }
  return (
    <motion.span className={className} {...pulse}>
      {children}
    </motion.span>
  );
};
