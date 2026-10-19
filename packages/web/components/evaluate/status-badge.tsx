/**
 * 评估状态徽章 — 5 种状态映射为 shadcn Badge + 项目主题色
 * @param props.status 评估状态
 * @param props.className 额外类名
 * @returns JSX 元素 (Badge)
 * @shared
 */
// 5 个 evaluation 状态: cancelled/completed/failed/pending/running
// (2026-06-29 P2) CVA 化: statusVariants 强类型化, 1 个 cva() 替代 3 Record lookup
//   - 改前: CUSTOM_STYLE (弱类型 Record<string, string>) + LABEL + VARIANT 3 个 Map 同步维护
//   - 改后: statusVariants + LABEL 2 个 Map, 加新状态只改 cva 1 处
import { Badge, type BadgeProps } from "@/components/ui/badge";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";
import type { EvaluationStatus } from "@/lib/evaluate/types";

/** StatusBadge 组件属性 */
interface Props extends VariantProps<typeof statusVariants> {
  status: EvaluationStatus;
  className?: string;
}

// 强类型 status 变体: shadcn variant (destructive/secondary) + 自定义 className (moss/running)
// 改前 3 处 Record lookup 合并为 1 个 cva, 新增状态只改这里
/** 状态变体样式 — CVA 定义 */
const statusVariants = cva("", {
  defaultVariants: { status: "pending" },
  variants: {
    status: {
      // destructive 走 shadcn Badge 内建 variant
      failed: "",
      // secondary 走 shadcn Badge 内建 variant
      cancelled: "",
      pending: "",
      // moss = 苔藓绿 success, status-running = 项目 status 蓝
      completed: "bg-moss/10 text-moss border-moss/30",
      running: "bg-status-running/10 text-status-running border-status-running/40 animate-pulse",
    },
  },
});

// shadcn Badge variant 映射: failed → destructive, cancelled/pending → secondary, 其他 2 个走 className
/** shadcn Badge variant 映射: failed → destructive, cancelled/pending → secondary, 其他 2 个走 className */
const BADGE_VARIANT: Record<EvaluationStatus, BadgeProps["variant"]> = {
  cancelled: "secondary",
  completed: "default", // 用 statusVariants 的 className 覆盖
  failed: "destructive",
  pending: "secondary",
  running: "default", // 用 statusVariants 的 className 覆盖
};

// 中文 label 映射
/** 中文 label 映射 */
const LABEL: Record<EvaluationStatus, string> = {
  cancelled: "已取消",
  completed: "完成",
  failed: "失败",
  pending: "排队",
  running: "跑中",
};

/** status-badge @client-bff */
export const StatusBadge = ({ status, className }: Props) => (
  <Badge variant={BADGE_VARIANT[status]} className={cn(statusVariants({ status }), className)}>
    {LABEL[status]}
  </Badge>
);
