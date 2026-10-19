// HealthServiceCard — Mission Control 风格服务卡片 (2026-06-15)
// 用 shadcn Card + Badge 替代手写 div, 跟项目 shadcn 体系统一
// 纯展示组件, 不持有 state, 由父组件传数据
// (2026-06-18) Badge 等宽 (min-w 4.5rem 居中) + error 状态 Tooltip 显示 result.error
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { CheckCircle2, type LucideIcon, XCircle } from "lucide-react";
import { AppTooltip } from "@/components/common/overlay/app-tooltip";
import { Badge } from "@/components/ui/badge";
import type { CheckResult } from "@/lib/api/health";

/** HealthServiceCardProps - 健康检查服务卡片属性 */
export interface HealthServiceCardProps {
  /** 服务名称标题 */
  title: string;
  /** 服务类型图标 */
  icon: LucideIcon;
  /** 健康检查结果数据 */
  result: CheckResult;
  /** 主指标数值 */
  primaryMetric: string;
  /** 主指标单位 */
  primaryUnit: string;
  /** 次指标数值 (可选) */
  secondaryMetric?: string;
  /** 次指标单位 (可选) */
  secondaryUnit?: string;
  /** 提示文案 (可选) */
  hint?: string;
}

/** STATUS_BADGE_MIN_W - 状态 Badge 最小宽度 */
const STATUS_BADGE_MIN_W = "min-w-[4.5rem]";

/** resolveStatusVisuals - 根据服务状态解析对应的视觉样式
 * @param ok 是否正常
 * @returns 图标类名、数字色、状态图标、Badge 变体、状态条类名
 * @shared
 */
const resolveStatusVisuals = (
  ok: boolean,
): {
  iconClass: string;
  heroNumberClass: string;
  StatusIcon: LucideIcon;
  badgeVariant: "default" | "destructive" | "secondary";
  statusBarClass: string;
} => {
  if (ok) {
    return {
      StatusIcon: CheckCircle2,
      badgeVariant: "secondary",
      heroNumberClass: "text-foreground",
      iconClass: "text-moss",
      statusBarClass: "bg-moss",
    };
  }
  return {
    StatusIcon: XCircle,
    badgeVariant: "destructive",
    heroNumberClass: "text-destructive",
    iconClass: "text-destructive",
    statusBarClass: "bg-destructive",
  };
};

/** HealthServiceCard - Mission Control 风格服务卡片组件 */
export const HealthServiceCard = ({
  title,
  icon: Icon,
  result,
  primaryMetric,
  primaryUnit,
  secondaryMetric,
  secondaryUnit,
  hint,
}: HealthServiceCardProps) => {
  const ok = result.status === "ok";
  const { statusBarClass, iconClass, heroNumberClass, StatusIcon, badgeVariant } =
    resolveStatusVisuals(ok);
  const badgeEl = (
    <Badge variant={badgeVariant} className={`justify-center gap-1 px-1.5 ${STATUS_BADGE_MIN_W}`}>
      <StatusIcon className="h-3 w-3" strokeWidth={1.5} />
      {result.status}
    </Badge>
  );
  return (
    <Card
      data-testid="health-section"
      data-section-title={title}
      className="group relative flex h-full flex-col overflow-hidden border-border/60 bg-card/40 transition-all duration-500 hover:border-ink/30 hover:shadow-[0_8px_32px_-12px_hsl(0_0%_0%/0.12)]"
    >
      {/* 顶 status bar: 4px 厚, 跟状态色 */}
      <div className={`h-1 w-full shrink-0 transition-colors duration-500 ${statusBarClass}`} />

      <CardHeader className="flex flex-row items-start justify-between space-y-0 px-5 pt-4 pb-2">
        <div className="flex items-center gap-2">
          <Icon
            className={`h-4 w-4 transition-colors duration-500 ${iconClass}`}
            strokeWidth={1.5}
          />
          <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">
            {title}
          </span>
        </div>
        {ok || !result.error ? (
          badgeEl
        ) : (
          <AppTooltip content={result.error} variant="error">
            {badgeEl}
          </AppTooltip>
        )}
      </CardHeader>

      <CardContent className="flex-1 px-5 pb-4 pt-0">
        <div className="flex items-baseline gap-1.5">
          <span
            className={`num text-4xl font-medium tabular-nums tracking-tight ${heroNumberClass}`}
          >
            {primaryMetric}
          </span>
          <span className="num text-sm text-muted-foreground">{primaryUnit}</span>
        </div>
        {secondaryMetric !== undefined && (
          <div className="num mt-1 text-xs tabular-nums text-muted-foreground">
            {secondaryMetric}
            {secondaryUnit && <span> {secondaryUnit}</span>}
          </div>
        )}
        {hint && <p className="text-xs text-muted-foreground/70">{hint}</p>}
      </CardContent>
    </Card>
  );
};
