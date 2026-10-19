"use client";
// 统计卡 (2026-06-09 redesign) — 用统一 CountUp 弹数字
// (2026-06-29 P2) CVA 化: 5 accent (ink/clay/moss/ochre/indigo) 从内联对象字面量 → accentBarVariants cva()
//   改前: 5 行 `clay: "bg-clay" / ...` 重复 + 写 .accent 调取, 改后 1 个 cva 强类型
import { CountUp } from "@/components/motion/animated";
import { SECONDS_PER_MINUTE, ZERO } from "@/const";
import { cva } from "class-variance-authority";
import { cn } from "@/lib/utils";

/** 统计卡顶部色条颜色变体: ink (黑) / clay (赤陶红) / moss (苔藓绿) / ochre (赭石) / indigo (靛蓝)
 * @client-bff
 */
export type StatCardAccent = "ink" | "clay" | "moss" | "ochre" | "indigo";

/** 顶部细色条 (1px 高的 accent bar) 颜色变体 @shared */
const accentBarVariants = cva("", {
  defaultVariants: { accent: "ink" },
  variants: {
    accent: {
      clay: "bg-clay",
      indigo: "bg-indigo",
      ink: "bg-ink",
      moss: "bg-moss",
      ochre: "bg-ochre",
    },
  },
});

/**
 * 统计卡 — 顶部细色条 + CountUp 弹数字 + hover 阴影效果
 * @client-bff
 * @param props.label 统计标签
 * @param props.value 数值 (数字自动 CountUp 动画) 或字符串
 * @param props.hint 底部附加说明
 * @param props.accent 色条变体: ink/clay/moss/ochre/indigo
 * @param props.index 进场 stagger 步进索引
 * @param props.onClick 点击回调 (传了就变可点击: cursor-pointer + button role)
 * @param props.testId 测试 id (data-testid 注入根元素, 区分同页多个卡片)
 * @returns 统计卡 JSX
 */
export const StatCard = ({
  label,
  value,
  hint,
  accent = "ink",
  index = ZERO,
  onClick,
  testId,
}: {
  label: string;
  value: number | string;
  hint?: string;
  /** Ink (黑) / clay (赤陶红) / moss (苔藓绿) / ochre (赭石) / indigo (靛蓝) */
  accent?: StatCardAccent;
  /** 进场 stagger 步进 */
  index?: number;
  /** (2026-07-09) 点击回调 — 传了就变可点击卡片 (cursor-pointer + button role + keyboard) */
  onClick?: () => void;
  /** (2026-07-09) data-testid 注入根元素 */
  testId?: string;
}) => {
  const isNumber = typeof value === "number";
  const clickable = onClick !== undefined;

  return (
    <div
      className={cn(
        "anim-rise group relative overflow-hidden rounded-xl border border-border/60 bg-card p-5 transition-shadow duration-500",
        clickable
          ? "cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/60 focus-visible:ring-offset-2 hover:shadow-[0_2px_4px_hsl(0_0%_0%/0.04),0_12px_28px_hsl(0_0%_0%/0.08),0_4px_8px_hsl(0_0%_0%/0.04)]"
          : "hover:shadow-[0_2px_4px_hsl(0_0%_0%/0.04),0_12px_28px_hsl(0_0%_0%/0.08),0_4px_8px_hsl(0_0%_0%/0.04)]",
      )}
      data-testid={testId}
      onClick={onClick}
      onKeyDown={
        clickable
          ? (event) => {
              if (event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                onClick();
              }
            }
          : undefined
      }
      role={clickable ? "button" : undefined}
      style={{ animationDelay: `${index * SECONDS_PER_MINUTE}ms` }}
      tabIndex={clickable ? ZERO : undefined}
    >
      {/* 顶部细色条 */}
      <div className={cn("absolute left-0 right-0 top-0 h-px", accentBarVariants({ accent }))} />
      <div className="eyebrow">{label}</div>
      <div className="mt-3 flex items-baseline gap-1.5">
        {isNumber ? (
          <CountUp
            value={value as number}
            className="num text-4xl font-medium leading-none tracking-tight text-foreground"
          />
        ) : (
          <span className="num text-4xl font-medium leading-none tracking-tight text-foreground">
            {value}
          </span>
        )}
      </div>
      {hint && <div className="mt-2 text-sm text-muted-foreground">{hint}</div>}
    </div>
  );
};
