// Pagination updater 应用器 (2026-06-30 拆自 data-table.tsx)
//   TanStack OnChangeFn 的 updater 参数支持 T | ((old: T) => T) 两种形态,
//   抽成纯函数便于单测 + 复用.
import type { Updater } from "@tanstack/react-table";
import { ONE } from "@/const/index";

/**
 * 分页状态 — 0-based pageIndex + pageSize
 * @shared
 */
export interface PaginationState {
  pageIndex: number;
  pageSize: number;
}

/**
 * 应用 TanStack OnChangeFn updater 到当前分页状态
 * @param updater 新值或 (old) => new 更新函数
 * @param currentState 当前分页状态
 * @returns 更新后的分页状态
 * @shared
 */
// TanStack OnChangeFn 既能收值也能收函数, 两种都要兼容
export const applyPaginationUpdater = (
  updater: Updater<PaginationState>,
  currentState: PaginationState,
): PaginationState => (typeof updater === "function" ? updater(currentState) : updater);

/**
 * 受控分页参数 — 1-based current + pageSize + onChange 回调
 * @shared
 */
export interface ControlledPaginationArgs {
  current: number;
  pageSize: number;
  onChange: (page: number) => void;
}

/**
 * 构建受控分页处理器 — 1-based current 转 0-based pageIndex, onChange 回调再转回 1-based
 * @param args 受控分页参数
 * @returns TanStack OnChangeFn 处理器
 * @shared
 */
// (2026-06-30) 受控分页用: 1-based current 转 0-based pageIndex, onChange 回调再转回 1-based
export const buildControlledPaginationHandler = (
  args: ControlledPaginationArgs,
): ((updater: Updater<PaginationState>) => void) => {
  const baseState: PaginationState = {
    pageIndex: args.current - ONE,
    pageSize: args.pageSize,
  };
  return (updater) => {
    const next = applyPaginationUpdater(updater, baseState);
    args.onChange(next.pageIndex + ONE);
  };
};
