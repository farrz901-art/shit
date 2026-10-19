"use client";
/**
 * 视口可见时入场动画包装 — whileInView + fadeUp 变体
 * reduce 模式下 initial={false} 直接显示终态
 * @param props.children 子节点
 * @param props.delay 入场延迟
 * @param props.className 容器类名
 * @param props.as 渲染标签
 * @returns JSX 元素
 * @client-bff
 */
//   reduce 模式下 initial={false} → 元素直接显示终态, 不做 hidden→show 过渡,
//   配合 root layout 的 MotionConfig reducedMotion="user" 满足 WCAG 2.3.3.
import { type ReactNode } from "react";
import { type HTMLMotionProps, motion } from "motion/react";
import { fadeUp } from "@/lib/motion";
import { ZERO } from "@/const";
import { useReducedMotionSafe } from "./use-reduced-motion-safe";

/**
 * Reveal — 视口可见时入场动画包装, whileInView + fadeUp 变体
 * @param props.children 子节点
 * @param props.delay 入场延迟
 * @param props.className 容器类名
 * @param props.as 渲染标签
 * @returns JSX 元素
 * @client-bff
 */
export const Reveal = ({
  children,
  delay = ZERO,
  className,
  as = "div",
  ...rest
}: {
  children: ReactNode;
  delay?: number;
  className?: string;
  as?: "div" | "section" | "article" | "li";
} & HTMLMotionProps<"div">) => {
  const reduced = useReducedMotionSafe();
  const Tag = motion[as] as typeof motion.div;
  return (
    <Tag
      className={className}
      variants={fadeUp}
      initial={reduced ? false : "hidden"}
      whileInView="show"
      viewport={{ margin: "-5%", once: true }}
      transition={{ delay }}
      {...rest}
    >
      {children}
    </Tag>
  );
};
