"use client";
/**
 * 子项串行动画容器 — staggerChildren 控制子项逐个入场
 * reduce 模式下 staggerChildren=0 所有子项同时显示
 * @param props.children 子节点
 * @param props.className 容器类名
 * @param props.delay 子项间隔秒数
 * @param props.as 渲染标签
 * @returns JSX 元素
 * @client-bff
 */
//   reduce 模式下 staggerChildren=0 → 所有子项同时显示, 不串行延迟.
//   配合 StaggerItem 自身的 reduce 分支, 整套 stagger 序列在 a11y 模式下瞬时呈现.
import { type ReactNode } from "react";
import { motion } from "motion/react";
import { stagger as staggerVariant } from "@/lib/motion";
import { ZERO } from "@/const";
import { useReducedMotionSafe } from "./use-reduced-motion-safe";

const STAGGER_DEFAULT_DELAY = 0.06;
const STAGGER_REDUCED_DELAY = ZERO;

/**
 * Stagger — 子项串行动画容器, staggerChildren 控制子项逐个入场
 * @param props.children 子节点
 * @param props.className 容器类名
 * @param props.delay 子项间隔秒数
 * @param props.as 渲染标签
 * @returns JSX 元素
 * @client-bff
 */
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
  const effectiveDelay = reduced ? STAGGER_REDUCED_DELAY : delay;
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
