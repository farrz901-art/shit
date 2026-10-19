"use client";
/**
 * 入口卡 (2026-06-15) — 从 components/knowledge/ 升 common/
 * Hover lift + 数字序号 + 渐变箭头, 通用 "链接到子页" 卡片
 * 3 调用方 (knowledge Dashboard/GraphView/documents Entry) — 通用, 不专属 knowledge
 * EntryCard 内部已渲染 <LocalizedLink>, 调用方别再包一层 (a 嵌 a → hydration error)
 */
import { ONE, ZERO } from "@/const";
import { ArrowRight } from "lucide-react";
import { HoverLift } from "@/components/motion/animated";
import { LocalizedLink } from "@/components/i18n/localized-link";
import type { ReactNode } from "react";
import { cn } from "@/lib/utils";
import { useTranslations } from "next-intl";

/** 每个 entry 卡片的入场 stagger 间隔 (ms) @shared */
const ENTRY_ANIM_STEP_MS = 60;
/** 序号格式化宽度 (e.g. 01, 02, 10) @shared */
const INDEX_PADDING_WIDTH = 2;
/** HoverLift 抬升幅度 (px) @shared */
const HOVER_LIFT_PX = 6;

/**
 * 入口卡 — 数字序号 + 大图标 + 标题 + 描述 + 渐变箭头
 * @client-bff
 * @param props.href 点击跳转目标, 内部已用 LocalizedLink 自动加 locale 前缀
 * @param props.index 卡片在列表中的索引, 用于 stagger 进场延迟 (60ms 步进) + 右上角 "01/02/10" 序号
 * @param props.icon 卡片左侧大图标 (建议 lucide-react 图标, h-6 w-6)
 * @returns 入口卡 JSX
 */
export const EntryCard = ({
  href,
  icon,
  title,
  desc,
  index = ZERO,
}: {
  href: string;
  icon: ReactNode;
  title: string;
  desc: string;
  index?: number;
}) => {
  const tr = useTranslations();
  return (
    <LocalizedLink
      href={href}
      className="group block focus:outline-none"
      style={{ animationDelay: `${index * ENTRY_ANIM_STEP_MS}ms` }}
    >
      <HoverLift lift={HOVER_LIFT_PX} className="h-full">
        <article
          className={cn(
            "anim-rise relative h-full overflow-hidden rounded-xl border border-border/60 bg-card p-6",
            "transition-colors duration-300 group-hover:border-clay/40",
          )}
        >
          {/* 角落序号 */}
          <span className="num absolute right-4 top-4 text-sm text-muted-foreground/60">
            {String(index + ONE).padStart(INDEX_PADDING_WIDTH, "0")}
          </span>

          {/* 大图标 */}
          <div className="mb-5 flex h-12 w-12 items-center justify-center rounded-lg bg-muted text-muted-foreground transition-colors duration-300 group-hover:bg-clay/10 group-hover:text-clay">
            {icon}
          </div>

          <h3 className="display text-2xl text-foreground">{title}</h3>
          <p className="mt-2 text-base text-muted-foreground">{desc}</p>

          {/* Hover 出现的箭头 */}
          <div className="mt-6 flex items-center gap-2 text-base text-muted-foreground transition-colors duration-300 group-hover:text-clay">
            <span className="eyebrow">{tr("Open")}</span>
            <span className="inline-block transition-transform duration-300 group-hover:translate-x-1">
              <ArrowRight />
            </span>
          </div>

          {/* 底部装饰线 */}
          <div
            className="absolute bottom-0 left-0 h-px w-0 bg-clay transition-all duration-500 group-hover:w-full"
            style={{ transitionTimingFunction: "var(--ease-out-expo)" }}
          />
        </article>
      </HoverLift>
    </LocalizedLink>
  );
};
