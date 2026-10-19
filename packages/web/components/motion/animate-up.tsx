"use client";
/**
 * 带 AnimatePresence 的入场动画包装 — 用于"提交后出现反馈" / "错误条淡出" 等场景
 * @param props.show 是否显示
 * @param props.lift 抬升距离
 * @param props.delay 入场延迟
 * @param props.enterFromTop true = 从上方进入, false = 从下方
 * @param props.children 子节点
 * @param props.className 容器类名
 * @param props.as 渲染标签
 * @returns JSX 元素 (motion 包装)
 * @client-bff
 */
import { type ReactNode } from "react";
import { AnimatePresence, motion } from "motion/react";
import { fadeUp, LIFT, TRANSITION_REVEAL_OUTEXPO } from "@/lib/motion";
import { useReducedMotionSafe } from "./use-reduced-motion-safe";

/** 从上方进入时的 offset 值 (负 = 向上滑入) */
const SLIDE_TOP_OFFSET = -LIFT.slideTop;

/** AnimateUp 组件的属性 */
export interface AnimateUpProps {
  show: boolean;
  lift?: number;
  delay?: number;
  enterFromTop?: boolean; // true = -4 (通知条), false = 12 (卡片)
  children: ReactNode;
  className?: string;
  as?: "div" | "section" | "article" | "ul" | "li";
}

/** 默认入场延迟 (0ms) */
const DEFAULT_DELAY = 0;

/**
 * AnimateUp — 带 AnimatePresence 的入场动画包装, show/hide 时自动淡入淡出
 * @param props.show 是否显示
 * @param props.lift 抬升距离
 * @param props.delay 入场延迟
 * @param props.enterFromTop 是否从上方进入
 * @param props.children 子节点
 * @param props.className 容器类名
 * @param props.as 渲染标签
 * @returns JSX 元素
 * @client-bff
 */
export const AnimateUp = ({
  show,
  lift,
  delay = DEFAULT_DELAY,
  enterFromTop = false,
  children,
  className,
  as = "div",
}: AnimateUpProps) => {
  const reduced = useReducedMotionSafe();
  const Tag = motion[as] as typeof motion.div;
  const effectiveLift = lift ?? (enterFromTop ? SLIDE_TOP_OFFSET : LIFT.hero);
  const initial = reduced ? false : { opacity: 0, y: effectiveLift };
  const exit = reduced ? { opacity: 1 } : { opacity: 0 };
  return (
    <AnimatePresence>
      {show && (
        <Tag
          className={className}
          variants={fadeUp}
          initial={initial}
          animate="show"
          exit={exit}
          transition={{ ...TRANSITION_REVEAL_OUTEXPO, delay }}
        >
          {children}
        </Tag>
      )}
    </AnimatePresence>
  );
};
