/**
 * @file 表格/卡片加载骨架屏 (2026-06-14)
 * @description 默认 3 行, 首行宽 48 高 8, 其余 4 行全宽 — 替手写 Skeleton × N
 *              DataTable / 卡片列表 loading 态用
 */
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import { range } from "es-toolkit";

/** 默认骨架行数 @shared */
const DEFAULT_SKELETON_ROWS = 3;
/** 首行索引 (header 样式) @shared */
const HEADER_ROW_INDEX = 0;

/**
 * 骨架屏组件属性接口
 * @client-bff
 */
interface LoadingSkeletonProps {
  rows?: number;
  className?: string;
}

/**
 * 渲染 rows 行骨架占位, 首行 header 样式, 其余行 content 样式
 * @param props.rows 骨架行数 (默认 3)
 * @param props.className 外层额外 className
 * @returns JSX 元素
 * @client-bff
 */
export const LoadingSkeleton = ({
  rows = DEFAULT_SKELETON_ROWS,
  className,
}: LoadingSkeletonProps) => (
  <div className={cn("space-y-6 p-6", className)}>
    {range(rows).map((idx) => (
      <Skeleton key={idx} className={idx === HEADER_ROW_INDEX ? "mb-4 h-8 w-48" : "h-4 w-full"} />
    ))}
  </div>
);
