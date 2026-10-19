"use client";
/**
 * Stagger 子项 — 配合 Stagger 容器实现逐个入场
 * reduce 模式下 initial={false} 直接呈现终态
 * @param props.children 子节点
 * @param props.className 容器类名
 * @param props.as 渲染标签
 * @param props.variant 入场动画变体: fadeUp / fadeIn / scaleIn
 * @returns JSX 元素
 * @client-bff
 */
//   reduce 模式下 initial={false} → 直接呈现 show 终态, 不做 hidden→show 过渡.
//   配合 Stagger 容器 (staggerChildren=0) 让整套 stagger 序列瞬时完成.
import { type ReactNode } from "react";
import { type Variants, motion } from "motion/react";
import { fadeUp, fadeIn, scaleIn } from "@/lib/motion";
import { useReducedMotionSafe } from "./use-reduced-motion-safe";

const DEFAULT_ANIM_VARIANT = "fadeUp";

// 单一查找表 — 替代 if/else 链, 同时避免 init-declarations lint warning
const VARIANT_MAP: Readonly<Record<"fadeUp" | "fadeIn" | "scaleIn", Variants>> = {
  fadeIn,
  fadeUp,
  scaleIn,
};

/**
 * StaggerItem — Stagger 子项, 配合 Stagger 容器实现逐个入场
 * @param props.children 子节点
 * @param props.className 容器类名
 * @param props.as 渲染标签
 * @param props.variant 入场动画变体
 * @returns JSX 元素
 * @client-bff
 */
export const StaggerItem = ({
  children,
  className,
  as = "div",
  variant = DEFAULT_ANIM_VARIANT,
}: {
  children: ReactNode;
  className?: string;
  as?: "div" | "li" | "article";
  variant?: "fadeUp" | "fadeIn" | "scaleIn";
}) => {
  const reduced = useReducedMotionSafe();
  const Tag = motion[as] as typeof motion.div;
  const currentVariant = VARIANT_MAP[variant];
  return (
    <Tag className={className} variants={currentVariant} initial={reduced ? false : undefined}>
      {children}
    </Tag>
  );
};
