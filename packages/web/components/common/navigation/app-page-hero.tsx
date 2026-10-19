"use client";
// 页面级 hero 头 (2026-06-15) — 从 components/knowledge/KnowledgeHero 升 common/ + 改名 PageHero
// 通用 slot 模式: eyebrow + meta (刷新间隔等) + display title + 标题右侧 actions 插槽 + description 副标题
// (2026-06-28) Phase3 Task3.1: 新增 backHref/backLabel, 在 h1 行内联 BackLink (向后兼容: 不传 backHref 时行为不变)
// 调用方跨 knowledge / dataset / documents / graph / dashboard / chat / submissions / decode — 通用页面头
// ClassName: 透传给 Stagger 外层, 调用方可加 shrink-0 pb-6 等
import { BackLink } from "./app-back-link";
import { Stagger, StaggerItem } from "@/components/motion/animated";
import type { ReactNode } from "react";

/**
 * PageHero 属性接口 — 分类标签、标题、元信息、操作区及后退链接
 * @client-bff
 */
export interface PageHeroProps {
  /** 分类标签 (e.g. "KNOWLEDGE" / "GRAPH") */
  eyebrow: string;
  /** 页面标题 (支持 ReactNode) */
  title: ReactNode;
  /** 元信息 (刷新间隔等) */
  meta?: ReactNode;
  /** 副标题 */
  description?: ReactNode;
  /** 标题右侧操作区 */
  actions?: ReactNode;
  /** 自定义类名 */
  className?: string;
  /** 后退链接 href (可选). 提供后自动在 h1 同一行渲染 BackLink. */
  backHref?: string;
  /** 后退链接文字 (i18n key). 默认 "返回" */
  backLabel?: string;
  /** 后退链接是否用 history.back() 模式 (默认 true, 跟旧 BackLink 默认行为一致) */
  backUseHistory?: boolean;
}

/**
 * 页面级 Hero 头 — Stagger 入场动画 + eyebrow + title + meta + actions + backLink
 * 跨 knowledge / dataset / documents / graph / dashboard / chat 等通用页面头
 * @param props.eyebrow 分类标签
 * @param props.title 页面标题 (支持 ReactNode)
 * @param props.meta 元信息
 * @param props.description 副标题
 * @param props.actions 标题右侧操作区
 * @param props.backHref 后退链接
 * @returns PageHero JSX
 */
export const PageHero = ({
  eyebrow,
  title,
  meta,
  description,
  actions,
  className = "",
  backHref,
  backLabel,
  backUseHistory = true,
}: PageHeroProps) => (
  <Stagger className={`space-y-2 ${className}`} delay={0.08}>
    <StaggerItem>
      <div className="flex items-center gap-3">
        <span className="eyebrow">{eyebrow}</span>
        <span className="h-px flex-1 bg-border" />
        {meta && <span className="num text-sm text-muted-foreground/60">{meta}</span>}
      </div>
    </StaggerItem>
    <StaggerItem>
      <div className="flex items-center justify-between gap-4">
        <div className="flex items-baseline gap-3">
          <h1 className="display text-5xl tracking-tight md:text-5xl">{title}</h1>
          {backHref && (
            <BackLink
              href={backHref}
              useHistory={backUseHistory}
              label={backLabel ?? "返回"}
              data-testid="page-hero-back-link"
            />
          )}
        </div>
        {actions}
      </div>
    </StaggerItem>
    {description && (
      <StaggerItem>
        <p className="max-w-xl text-lg text-muted-foreground">{description}</p>
      </StaggerItem>
    )}
  </Stagger>
);
