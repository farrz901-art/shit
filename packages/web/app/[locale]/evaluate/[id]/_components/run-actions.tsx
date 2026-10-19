// (2026-06-29) RunActions 子组件 — 抽自 run-detail-view.tsx 的 PageHeader actions 内联
// 严重度 LOW (A-15) — 抽命名子组件替 inline 2 Button + Fragment
"use client";

import { Button } from "@/components/ui/button";
import { StatusBadge } from "@/components/evaluate/status-badge";
import type { EvaluationStatus } from "@/lib/evaluate/types";

/** RunActions 组件 props
 * @property isPending - 是否正在执行
 * @property onCancel - 取消回调
 * @property onDelete - 删除回调
 * @property status - 评估运行状态
 * @property translate - i18n 翻译函数
 * @shared
 */
interface RunActionsProps {
  isPending: boolean;
  onCancel: () => void;
  onDelete: () => void;
  status: EvaluationStatus;
  translate: (key: string) => string;
}

/** 终态列表 (不再可取消, 只可删除) @shared */
const TERMINAL_STATUSES: EvaluationStatus[] = ["completed", "failed", "cancelled"];

/** RunActions - 评估运行操作按钮组 (状态徽标 + 取消/删除)
 * @param isPending - 是否正在执行
 * @param onCancel - 取消回调
 * @param onDelete - 删除回调
 * @param status - 评估运行状态
 * @param translate - i18n 翻译函数
 * @returns 操作按钮组 JSX
 * @client-bff
 */
export const RunActions = ({
  isPending,
  onCancel,
  onDelete,
  status,
  translate,
}: RunActionsProps) => {
  const isTerminal = TERMINAL_STATUSES.includes(status);
  return (
    <>
      <StatusBadge status={status} />
      {status === "running" && (
        <Button
          className="border-destructive/40 px-3 py-1 text-xs text-destructive hover:bg-destructive/5"
          disabled={isPending}
          onClick={onCancel}
          size="sm"
          type="button"
          variant="outline"
        >
          {translate("取消")}
        </Button>
      )}
      {isTerminal && (
        <Button
          className="border-border/60 px-3 py-1 text-xs"
          disabled={isPending}
          onClick={onDelete}
          size="sm"
          type="button"
          variant="outline"
        >
          {translate("删除")}
        </Button>
      )}
    </>
  );
};
