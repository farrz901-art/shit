"use client";
/**
 * Hover 抬升包装 — whileHover y:-N + whileTap 归位
 * reduce 模式: 用 CSS shadow 替代 transform, 不触发位移
 * @param props.children 子节点
 * @param props.className 容器类名
 * @param props.lift 抬升像素数
 * @returns JSX 元素
 * @client-bff
 */
//   reduce 模式: whileHover/whileTap 设为 undefined, transition 不传 (用 CSS 阴影 hover 反馈替代 transform 抬升).
//   满足 WCAG 2.3.3: 取消非用户主动触发的位移动画, 但保留 :hover 视觉反馈 (shadow), 不丢 affordance.
import { type ReactNode } from "react";
import { motion } from "motion/react";
import { SPRING } from "@/lib/motion";
import { FOUR } from "@/const";
import { cn } from "@/lib/utils";
import { useReducedMotionSafe } from "./use-reduced-motion-safe";

/**
 * HoverLift — Hover 抬升包装, whileHover y:-N + whileTap 归位
 * @param props.children 子节点
 * @param props.className 容器类名
 * @param props.lift 抬升像素数
 * @returns JSX 元素
 * @client-bff
 */
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
