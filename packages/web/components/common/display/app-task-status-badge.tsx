// 任务状态徽章 (2026-06-15) — 从 components/knowledge/ 升 common/
// 通用异步任务状态: queued / running / done / failed / partial / cancelled
// 适合任何 job / 批处理 / 后台任务 UI. 跟 [TaskStatusBadge 旧版] 行为一致, 仅位置/命名换.
// (2026-06-29 P2) CVA 化: 6 个状态从弱类型 Record → taskStateVariants cva() 强类型
//   改前: `style: Record<string, string>` 漏写不报错, default fallback `style.queued` 隐式
//   改后: cva variants.state 强类型, defaultVariants = "queued" 兜底, 加新状态只改 1 处
// 接受 string 输入 (后端 API raw 字段), 未知 state 自动 fallback 到 default
import { Badge } from "@/components/ui/badge";
import { cva, type VariantProps } from "class-variance-authority";

/** 任务状态 CVA 变体: queued/running/done/failed/partial/cancelled, 默认 queued @shared */
const taskStateVariants = cva("", {
  defaultVariants: { state: "queued" },
  variants: {
    state: {
      cancelled: "bg-muted text-muted-foreground",
      done: "bg-status-success/10 text-status-success",
      failed: "bg-status-error/10 text-status-error",
      partial: "bg-status-warning/10 text-status-warning",
      queued: "bg-muted text-muted-foreground",
      running: "bg-status-running/10 text-status-running animate-pulse",
    },
  },
});

/** TaskState 类型 — 从 taskStateVariants 变体中推导 @shared */
type TaskState = NonNullable<VariantProps<typeof taskStateVariants>["state"]>;

/**
 * 任务状态徽章 — 6 种异步任务状态 (queued/running/done/failed/partial/cancelled)
 * 接受 string 输入, 未知 state 自动 fallback 到 queued
 * @shared
 * @param props.state 任务状态字符串 (后端 API raw 字段)
 * @param props.className 额外 className
 * @returns Badge 组件
 */
export const TaskStatusBadge = ({
  state,
  className,
}: {
  // string 兜底: 未知后端 state 自动走 cva defaultVariants "queued"
  state: string;
  className?: string;
}) => (
  <Badge
    className={taskStateVariants({ state: state as TaskState, className })}
    data-testid="task-status"
  >
    {state}
  </Badge>
);
