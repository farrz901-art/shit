"use client";
/**
 * 字符 chunks 高亮预览 — decode-input-bar 下文字逐块进入动效
 * @param props.chunks 字符块数组
 * @param props.model 当前模型标识
 * @returns JSX 元素
 * @client-bff
 */
// 拆到 components/decode/ 让 decode-input-bar.tsx ≤100 行 + 业务组件复用
// motion.span 内联保留: stagger 入场跟 lib/motion.pulse 节奏不同, 不抽 Pulse
import { motion } from "motion/react";
import { BreathingDot } from "@/components/common/display/app-breathing-dot";
import { CSS_EASE, DUR } from "@/components/motion/animated";

/** 字符块入场逐块延时 (秒) */
const CHUNK_STAGGER_DELAY = 0.03;

/**
 * ChunksPreview — 字符 chunks 高亮预览
 * decode-input-bar 下文字逐块进入动效
 * @param props.chunks - 字符块数组
 * @param props.model - 当前模型标识
 * @returns JSX 元素
 * @client-bff
 */
export const ChunksPreview = ({ chunks, model }: { chunks: string[]; model: string }) => (
  <div className="flex flex-wrap items-center gap-1.5 border-b border-border/40 bg-muted/30 px-6 py-3">
    {chunks.map((chunk, idx) => (
      <motion.span
        key={`${chunk}-${idx}`}
        initial={{ opacity: 0, scale: 0.8, translateY: 4 }}
        animate={{ opacity: 1, scale: 1, translateY: 0 }}
        transition={{
          delay: idx * CHUNK_STAGGER_DELAY,
          duration: DUR.normal,
          ease: CSS_EASE.outQuint,
        }}
        className="num rounded-md bg-ink/5 px-2 py-0.5 text-base font-medium text-foreground"
      >
        {chunk}
      </motion.span>
    ))}
    {model && !model.endsWith("-") && <BreathingDot color="clay" className="ml-1" />}
  </div>
);
