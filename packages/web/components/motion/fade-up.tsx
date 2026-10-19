"use client";
/**
 * 通用内容入场动画 — variants fadeUp + initial/animate 控制显示
 * @param props.show 是否显示, true 时显示终态, false 不渲染
 * @param props.lift 抬升距离
 * @param props.delay 延迟
 * @param props.children 子节点
 * @param props.className 容器类名
 * @param props.as 渲染标签
 * @returns JSX 元素
 * @client-bff
 */
import { type ReactNode } from "react";
import { motion } from "motion/react";
import { fadeUp, LIFT } from "@/lib/motion";
import { useReducedMotionSafe } from "./use-reduced-motion-safe";

/** FadeUp 组件的属性 */
export interface FadeUpProps {
  show: boolean;
  lift?: number;
  delay?: number;
  children: ReactNode;
  className?: string;
  as?: "div" | "section" | "article" | "ul" | "li";
}

/** 默认入场延迟 (0ms) */
const DEFAULT_DELAY = 0;

/**
 * FadeUp — 通用内容入场动画, variants fadeUp + initial/animate 控制显示
 * @param props.show 是否显示
 * @param props.lift 抬升距离
 * @param props.delay 延迟
 * @param props.children 子节点
 * @param props.className 容器类名
 * @param props.as 渲染标签
 * @returns JSX 元素
 * @client-bff
 */
export const FadeUp = ({
  show,
  lift = LIFT.hero,
  delay = DEFAULT_DELAY,
  children,
  className,
  as = "div",
}: FadeUpProps) => {
  const reduced = useReducedMotionSafe();
  const Tag = motion[as] as typeof motion.div;
  const initial = reduced ? false : { opacity: 0, y: lift };
  if (!show) {
    return null;
  }
  return (
    <Tag
      className={className}
      variants={fadeUp}
      initial={initial}
      animate="show"
      transition={{ delay }}
    >
      {children}
    </Tag>
  );
};
