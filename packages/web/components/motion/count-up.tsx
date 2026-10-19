"use client";
/**
 * 数字计数动画 — 滚动到视口时从零弹动到目标值
 * reduce 模式下 spring duration = 0, 瞬时跳到终值
 * @param props.value 目标数值
 * @param props.duration 动画持续秒数
 * @param props.format 数值格式化函数
 * @param props.className 容器类名
 * @param props.style 行内样式
 * @returns JSX 元素
 * @client-bff
 */
//   reduce 模式: spring duration = 0 → 数字瞬时跳到终值, 无弹动计数.
//   aria-label 始终输出终值 (format(value)) — 屏幕阅读器朗读最终值, 跳过中间过渡数字.
import { type CSSProperties, useEffect, useRef } from "react";
import { motion, useInView, useMotionValue, useSpring, useTransform } from "motion/react";
import { DUR } from "@/lib/motion";
import { ZERO, MS_PER_SECOND } from "@/const";
import { useReducedMotionSafe } from "./use-reduced-motion-safe";

// reduce 模式 spring duration = 0 (立即跳到目标值, 无弹动)
/** reduce 模式下 spring duration = 0 (立即跳到目标值, 无弹动) */
const REDUCED_SPRING_DURATION = ZERO;

/**
 * CountUp — 数字计数动画, 滚动到视口时从零弹动到目标值
 * @param props.value 目标数值
 * @param props.duration 动画持续秒数
 * @param props.format 数值格式化函数
 * @param props.className 容器类名
 * @param props.style 行内样式
 * @returns JSX 元素
 * @client-bff
 */
export const CountUp = ({
  value,
  duration = DUR.countUp,
  format = (num: number) => num.toLocaleString("en-US"),
  className,
  style,
}: {
  value: number;
  duration?: number;
  format?: (num: number) => string;
  className?: string;
  style?: CSSProperties;
}) => {
  const reduced = useReducedMotionSafe();
  const ref = useRef<HTMLSpanElement>(null);
  const inView = useInView(ref, { margin: "-5%", once: true });
  const motionValue = useMotionValue(ZERO);
  // reduce 模式: duration: 0 = 立即跳到目标值, 无 spring 弹动
  const springDuration = reduced ? REDUCED_SPRING_DURATION : duration * MS_PER_SECOND;
  const spring = useSpring(motionValue, { bounce: ZERO, duration: springDuration });
  const display = useTransform(spring, (latest) => format(Math.round(latest)));

  useEffect(() => {
    if (inView) {
      motionValue.set(value);
    }
  }, [inView, value, motionValue]);

  // 屏幕阅读器朗读终值 (运动中的数字朗读无意义且会错过)
  const ariaLabel = format(value);

  return (
    <motion.span ref={ref} className={className} style={style} aria-label={ariaLabel}>
      {display}
    </motion.span>
  );
};
