"use client";
/**
 * 可点击按压反馈包装 — whileTap scale:0.97 + whileHover y:-1
 * reduce / disabled 时取消所有 motion 反馈
 * @param props.children 子节点
 * @param props.className 容器类名
 * @param props.onClick 点击回调
 * @param props.disabled 禁用状态
 * @param props.type button 类型
 * @returns JSX 元素
 * @client-bff
 */
//   reduce 模式 || disabled 时, whileTap/whileHover 设为 undefined → 取消所有视觉反馈,
//   满足 WCAG 2.2.2 (暂停/隐藏/停止动画). framer-motion y 属性属于其 CSS key,
//   id-length 例外白名单里已经包含 y, 不需要 eslint-disable.
import { type ReactNode } from "react";
import { motion } from "motion/react";
import { SPRING } from "@/lib/motion";
import { useReducedMotionSafe } from "./use-reduced-motion-safe";

// reduce / disabled 时统一 undefined, 取消视觉反馈
const NO_ANIMATION = undefined;
const TAP_SCALE = 0.97;
const HOVER_Y = -1;

/**
 * Pressable — 可点击按压反馈包装, whileTap scale:0.97 + whileHover y:-1
 * @param props.children 子节点
 * @param props.className 容器类名
 * @param props.onClick 点击回调
 * @param props.disabled 禁用状态
 * @param props.type button 类型
 * @returns JSX 元素
 * @client-bff
 */
export const Pressable = ({
  children,
  className,
  onClick,
  disabled,
  type = "button",
}: {
  children: ReactNode;
  className?: string;
  onClick?: () => void;
  disabled?: boolean;
  type?: "button" | "submit" | "reset";
}) => {
  const reduced = useReducedMotionSafe();
  // reduce / disabled 时取消所有 motion 反馈
  const isStill = reduced || disabled;
  const tapAnimation = isStill ? NO_ANIMATION : { scale: TAP_SCALE };
  const hoverAnimation = isStill ? NO_ANIMATION : { y: HOVER_Y };

  return (
    <motion.button
      className={className}
      onClick={onClick}
      disabled={disabled}
      type={type}
      whileTap={tapAnimation}
      whileHover={hoverAnimation}
      transition={SPRING.snappy}
    >
      {children}
    </motion.button>
  );
};
