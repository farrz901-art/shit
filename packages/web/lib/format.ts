// 文件大小格式化工具 (2026-07-03)
// 抽自 output/new/page.tsx:26 共享给 pre-analysis-upload-dialog 用.
//
// 日期时间相关的格式化函数已迁到 lib/date.ts (2026-07-07).
import { ONE, ONE_KB, ONE_MB } from "@/const";

/**
 * 字节数 → 人类可读文件大小 (B / KB / MB).
 * 1 位小数, 跟原 output/new/page.tsx:26 行为完全一致.
 *
 * @param val 字节数
 * @returns 形如 "0 B" / "15.0 KB" / "12.3 MB"
 */
export const fmtSize = (val: number): string => {
  if (val < ONE_KB) {
    return `${val} B`;
  }
  if (val < ONE_MB) {
    return `${(val / ONE_KB).toFixed(ONE)} KB`;
  }
  return `${(val / ONE_MB).toFixed(ONE)} MB`;
};
