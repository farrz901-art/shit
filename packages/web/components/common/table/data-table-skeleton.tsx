// DataTable 通用 Suspense fallback — RSC use(promise) 模式下的骨架屏
// (2026-06-14) Sprint 1.6 新建
import { Skeleton } from "@/components/ui/skeleton";
import { range } from "es-toolkit";

/** 默认列数 */
const DEFAULT_COLUMNS = 3;
/** 默认行数 */
const DEFAULT_ROWS = 5;

/**
 * DataTable 骨架屏 — RSC use(promise) 模式下的 loading fallback
 * @param props.columns 列数 (默认 3)
 * @param props.rows 行数 (默认 5)
 * @returns 骨架屏 JSX
 */
export const DataTableSkeleton = ({
  columns = DEFAULT_COLUMNS,
  rows = DEFAULT_ROWS,
}: {
  columns?: number;
  rows?: number;
}) => (
  <div className="space-y-2">
    {/* 表头 */}
    <div className="flex gap-2">
      {range(columns).map((index) => (
        <Skeleton key={index} className="h-10 flex-1" />
      ))}
    </div>
    {/* 行 */}
    {range(rows).map((rowIndex) => (
      <div key={rowIndex} className="flex gap-2">
        {range(columns).map((colIndex) => (
          <Skeleton key={colIndex} className="h-12 flex-1" />
        ))}
      </div>
    ))}
  </div>
);
