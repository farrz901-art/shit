"use client";
// StatCard 网格 (2026-06-28 Phase3 Task3.3) — 统一 grid + LocalizedLink wrapper
// 替代 3 个 dashboard 入口页的 14+ 行重复 JSX (Reveal + grid + LocalizedLink + StatCard)
// 内部 StatCard 已有 anim-rise, 此处不再包 Reveal (避免动画触发两次)
import { LocalizedLink } from "@/components/i18n/localized-link";
import { StatCard, type StatCardAccent } from "./app-stat-card";
import type { ReactNode } from "react";

/**
 * StatsGridItem — 统计卡片数据项: 标签、数值、提示、色条及跳转链接
 * @client-bff
 */
export interface StatsGridItem {
  /** 统计标签 */
  label: string;
  /** 统计值 (数字自动 CountUp 动画) */
  value: number | string;
  hint?: string;
  accent?: StatCardAccent;
  /** 点击跳转链接 (可选) */
  href?: string;
}

/** 网格列数 (用字符串键避开 oxlint no-magic-numbers) */
/** 两列网格模式 */
export const STATS_COLS_TWO = "two";
/** 四列网格模式 */
export const STATS_COLS_FOUR = "four";
/** 网格列数字面量联合类型: two | four */
export type StatsGridColumns = typeof STATS_COLS_TWO | typeof STATS_COLS_FOUR;

/** 网格列宽映射 — 按列数字面量返回 grid-cols 类名 */
const COL_CLASS_BY_KEY: Record<StatsGridColumns, string> = {
  [STATS_COLS_FOUR]: "grid-cols-2 md:grid-cols-4",
  [STATS_COLS_TWO]: "grid-cols-2",
};

/** 默认网格列数 — four */
const DEFAULT_COLUMNS: StatsGridColumns = STATS_COLS_FOUR;

/**
 * StatsGrid 属性接口 — 统计卡片列表及网格列数
 * @client-bff
 */
export interface StatsGridProps {
  /** 统计卡片数据列表 */
  items: StatsGridItem[];
  /** 网格列数: two (mobile 双列) 或 four (desktop 四列) */
  columns?: StatsGridColumns;
  className?: string;
}

/**
 * 渲染单个统计卡片 — 带链接时包裹 LocalizedLink
 * @param item 统计卡片数据
 * @param idx 索引
 * @returns 卡片 JSX
 */
const renderItem = (item: StatsGridItem, idx: number): ReactNode => {
  const card = <StatCard {...item} index={idx} />;
  if (item.href) {
    return (
      <LocalizedLink key={`${item.label}-${idx}`} href={item.href}>
        {card}
      </LocalizedLink>
    );
  }
  return <div key={`${item.label}-${idx}`}>{card}</div>;
};

/**
 * StatCard 网格布局 — 统一 grid + LocalizedLink wrapper
 * 替代 3 个 dashboard 入口页的重复 grid JSX. 内部 StatCard 已有 anim-rise, 不再包 Reveal
 * @param props.items 统计卡片列表
 * @param props.columns 网格列数 (默认 four)
 * @returns grid 容器 + StatCard 列表
 */
export const StatsGrid = ({ items, columns = DEFAULT_COLUMNS, className }: StatsGridProps) => {
  const gridClass = COL_CLASS_BY_KEY[columns];
  return (
    <div className={`grid gap-4 ${gridClass} ${className ?? ""}`}>{items.map(renderItem)}</div>
  );
};
