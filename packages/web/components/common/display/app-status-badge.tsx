/**
 * 7 种业务状态统一徽章 (P2 Phase 1 2026-06-28: 硬编码色阶 → status-* 主题 token, 自动响应主题切换)
 * 替散落 7+ 处 `<Badge className="bg-{emerald|amber|rose|blue}-100 ...">`
 * customLabels 未指定时直接显示 status key (e.g. status="running" → "running"), i18n 时传 customLabels 覆盖
 */
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

/** 业务状态枚举: pending/running/completed/failed/cancelled/active/archived @shared */
type StatusType =
  | "pending"
  | "running"
  | "completed"
  | "failed"
  | "cancelled"
  | "active"
  | "archived";

/** 状态到 Tailwind 样式映射 @shared */
const STATUS_COLORS: Record<StatusType, string> = {
  pending: "bg-status-warning/10 text-status-warning border-status-warning/30",
  running: "bg-status-running/10 text-status-running border-status-running/40 animate-pulse",
  completed: "bg-status-success/10 text-status-success border-status-success/30",
  failed: "bg-status-error/10 text-status-error border-status-error/30",
  cancelled: "bg-muted text-muted-foreground",
  active: "bg-status-success/10 text-status-success border-status-success/30",
  archived: "bg-muted text-muted-foreground",
};

/**
 * 任务状态徽章属性 — 状态值及自定义文案
 * @shared
 * @property status 业务状态枚举
 * @property customLabels 状态文案覆盖 (用于 i18n)
 */
interface StatusBadgeProps {
  status: StatusType;
  customLabels?: Partial<Record<StatusType, string>>;
}

/**
 * 任务状态徽章 — 7 种状态统一色阶 (status-* 主题 token)
 * @shared
 * @param props.status 业务状态枚举
 * @param props.customLabels 状态文案覆盖 (用于 i18n)
 * @returns Badge 组件
 */
export const StatusBadge = ({ status, customLabels }: StatusBadgeProps) => (
  <Badge className={cn("font-medium", STATUS_COLORS[status])} variant="outline">
    {customLabels?.[status] ?? status}
  </Badge>
);
