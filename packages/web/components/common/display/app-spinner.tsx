/**
 * 旋转 loading spinner: border 旋转 360° + 0.8s + linear + repeat Infinity
 * 替代 decode-input-bar.tsx 内联 LoadingSpinner
 * Reduced motion: 退化到静态圆点 (无 rotate 动画, 避免前庭功能敏感用户眩晕)
 */
"use client";
import { motion } from "motion/react";
import { cn } from "@/lib/utils";
import { useReducedMotionSafe } from "@/components/motion/use-reduced-motion-safe";

/** 旋转动画单圈时长 (秒) @shared */
const SPIN_DURATION = 0.8;
/** 完整旋转角度 @shared */
const FULL_ROTATION = 360;

/**
 * Spinner 属性接口 — className 及边框颜色
 * @client-bff
 * @property className 自定义类名
 * @property borderClass 边框颜色, 默认 border-paper/30
 */
export interface SpinnerProps {
  className?: string;
  /** 边框颜色, 默认 border-paper/30 */
  borderClass?: string;
}

/**
 * Loading 旋转圆 — 0.8s 线性旋转无限循环
 * @client-bff
 * @param props.borderClass Tailwind border 类, 默认 "border-paper/30 border-t-paper"
 * @returns Spinner JSX
 */
export const Spinner = ({
  className,
  borderClass = "border-paper/30 border-t-paper",
}: SpinnerProps) => {
  const reduced = useReducedMotionSafe();
  if (reduced) {
    return (
      <span className={cn("inline-block h-3 w-3 rounded-full border-2", borderClass, className)} />
    );
  }
  return (
    <motion.span
      className={cn("inline-block h-3 w-3 rounded-full border-2", borderClass, className)}
      animate={{ rotate: FULL_ROTATION }}
      transition={{ duration: SPIN_DURATION, ease: "linear", repeat: Infinity }}
    />
  );
};
