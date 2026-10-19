"use client";
// Antd 风格 Tooltip 包装 (2026-06-18): 替 shadcn Tooltip 4 子件 (Provider/Root/Trigger/Content) 模板
//   根 layout 没装 TooltipProvider, 业务手写易漏 → 抽包装强制统一, 1 行调用
//   用法: <AppTooltip content="错误信息"><Badge ... /></AppTooltip>
//   (2026-06-18) 视觉美化: 深色面板 + 左侧 3px 色条 (error/moss), max-w 20rem 自动换行
//   关联 [[feedback-encapsulate-radix-composites-app-style-needs-approval]] (2026-06-18 health tooltip 教训)
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

/**
 * AppTooltip 属性接口 — 触发器、浮层文案、位置、对齐、延迟及色条变体
 * @client-bff
 */
export interface AppTooltipProps {
  /** 触发器节点 (必须能 ref, 推荐 shadcn Badge/Button 等 Radix-aware 元素). 等价 trigger prop. */
  trigger?: ReactNode;
  /** 触发器节点 (children 写法, 跟 trigger 二选一, 推荐 children) */
  children?: ReactNode;
  /** 浮层文案 (string 或 ReactNode) */
  content: ReactNode;
  /** 浮层位置, 默认 top */
  side?: "top" | "right" | "bottom" | "left";
  /** 浮层对齐, 默认 center */
  align?: "start" | "center" | "end";
  /** 触发到打开的延迟 ms, 默认 200 (Radix 默认) */
  delayDuration?: number;
  /** 色条变体: error (红) / default (绿 moss) / none (无色条) */
  variant?: "default" | "error" | "none";
}

/**
 * 色条变体 → Tailwind before: class 映射
 * @client-bff
 */
const VARIANT_BAR: Record<"default" | "error" | "none", string> = {
  default: "before:bg-moss",
  error: "before:bg-destructive",
  none: "before:hidden",
};

/** 默认触发延迟 (ms) */
const DEFAULT_DELAY_MS = 200;

/**
 * 浮层提示 — antd 风格 Tooltip 包装, 替 shadcn Tooltip 4 子件模板
 * 自带 TooltipProvider, 业务代码无需再包 Provider
 * @param props.content 浮层文案
 * @param props.side 浮层位置 (默认 top)
 * @param props.align 对齐方式 (默认 center)
 * @param props.variant 色条变体 (default/error/none)
 * @param props.delayDuration 触发延迟 ms (默认 200)
 * @param props.children 触发器节点
 * @returns Tooltip JSX
 */
export const AppTooltip = ({
  trigger,
  content,
  side = "top",
  align = "center",
  delayDuration = DEFAULT_DELAY_MS,
  variant = "default",
  children,
}: AppTooltipProps) => {
  const node = children ?? trigger;
  if (!node) {
    throw new Error("AppTooltip: trigger 或 children 必须传一个");
  }
  const contentClass = cn(
    // 左侧 3px 色条 (用 before 伪元素)
    "relative max-w-[20rem] whitespace-pre-wrap break-words rounded-md border border-border/60 bg-popover px-3 py-2 text-xs leading-relaxed text-popover-foreground shadow-lg",
    "before:absolute before:left-0 before:top-0 before:h-full before:w-[3px] before:rounded-l-md",
    VARIANT_BAR[variant],
  );
  return (
    <TooltipProvider delayDuration={delayDuration}>
      <Tooltip>
        <TooltipTrigger asChild>{node}</TooltipTrigger>
        <TooltipContent side={side} align={align} sideOffset={6} className={contentClass}>
          {content}
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
};
