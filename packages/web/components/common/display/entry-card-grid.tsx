"use client";
// EntryCard 网格 (2026-06-28 Phase3 Task3.4) — 统一 grid wrapper
// 替代 3 个 dashboard 入口页的 14+ 行重复 JSX (Reveal + grid + EntryCard)
// EntryCard 自带 LocalizedLink + HoverLift, 此处只管 grid 列布局
import { EntryCard } from "./app-entry-card";
import type { ReactNode } from "react";

/**
 * EntryCardGrid 卡片数据项 — 图标、标题、描述及跳转链接
 * @client-bff
 */
export interface EntryCardGridItem {
  /** 卡片图标 (建议 lucide-react 图标) */
  icon: ReactNode;
  /** 卡片标题 */
  title: string;
  /** 卡片描述 */
  desc: string;
  /** 点击跳转链接 */
  href: string;
}

/** 网格列数 (用字符串键避开 oxlint no-magic-numbers) */
/** 两列网格模式 @shared */
export const ENTRY_COLS_TWO = "two";
/** 四列网格模式 @shared */
export const ENTRY_COLS_FOUR = "four";
/** 网格列数字面量联合类型: two | four @shared */
export type EntryCardGridColumns = typeof ENTRY_COLS_TWO | typeof ENTRY_COLS_FOUR;

/** 列模式到 grid class 的映射 @shared */
const COL_CLASS_BY_KEY: Record<EntryCardGridColumns, string> = {
  [ENTRY_COLS_FOUR]: "grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-4",
  [ENTRY_COLS_TWO]: "grid-cols-1 md:grid-cols-2",
};

/** 默认列模式: four @shared */
const DEFAULT_COLUMNS: EntryCardGridColumns = ENTRY_COLS_FOUR;

/**
 * EntryCardGrid 属性接口 — 卡片数据列表及网格列数
 * @client-bff
 */
export interface EntryCardGridProps {
  /** 卡片数据列表 */
  items: EntryCardGridItem[];
  /** 网格列数: two (mobile 单列) 或 four (desktop) */
  columns?: EntryCardGridColumns;
  className?: string;
}

/**
 * EntryCard 网格布局 — 统一 grid wrapper, 替代 3 个 dashboard 的重复 grid JSX
 * @client-bff
 * @param props.items 卡片列表
 * @param props.columns 网格列数 (默认 four)
 * @returns grid 容器 + EntryCard 列表
 */
export const EntryCardGrid = ({
  items,
  columns = DEFAULT_COLUMNS,
  className,
}: EntryCardGridProps) => {
  const gridClass = COL_CLASS_BY_KEY[columns];
  return (
    <div className={`grid gap-4 ${gridClass} ${className ?? ""}`}>
      {items.map((item, idx) => (
        <EntryCard key={`${item.title}-${idx}`} {...item} index={idx} />
      ))}
    </div>
  );
};
