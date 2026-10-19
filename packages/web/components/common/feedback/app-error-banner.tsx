// Shadcn Alert 包装 (2026-06-14): 16 处 destructive 错误条 + success/warning 统一
//   用法: <ErrorBanner variant="destructive" description="..." />
//   5 variant: destructive | warning | info | success | loading
//   Shadcn Alert 只有 destructive + default 2 variant, 其他 4 variant 用 className 模拟
// (2026-06-29 P2) CVA 化: bannerVariants 强类型化, 1 个 cva() 替代 2 Record lookup + 三元
//   - 改前: defaultIcon (5 LucideIcon) + variantColorClass (5 string) + 内联三元 (loading animate-spin) 3 处同步
//   - 改后: bannerVariants 1 个 cva() + iconVariants 1 个 Map + CompoundVariants 处理 loading animate-spin
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import {
  AlertCircle,
  AlertTriangle,
  CheckCircle2,
  Info,
  Loader2,
  type LucideIcon,
} from "lucide-react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

/** 错误提示条变体: destructive/warning/info/success/loading */
export type ErrorBannerVariant = "destructive" | "warning" | "info" | "success" | "loading";

/**
 * ErrorBanner 属性接口 — 变体、标题、描述、操作按钮及 icon
 * @client-bff
 */
export interface ErrorBannerProps extends Omit<VariantProps<typeof bannerVariants>, "variant"> {
  /** 变体: destructive/warning/info/success/loading */
  variant?: ErrorBannerVariant;
  title?: string;
  description: string; // 必填 (跟 descriptionNode 二选一, 同时传优先 descriptionNode)
  /** (2026-06-29 P1) descriptionNode 替代 description 用于复杂子节点 (e.g. <ul> 错误列表) */
  descriptionNode?: React.ReactNode;
  action?: React.ReactNode; // 右侧按钮 (例 "重试" / "复制")
  icon?: LucideIcon;
  className?: string;
  dataTestid?: string;
}

// 强类型变体: 1 个 cva 替代 2 个 Record lookup + loading 的内联 animate-spin 三元
// 新增 variant 只需在 variants.variant 加 1 个 key, color class + icon 同步收口
/**
 * 横幅变体 CVA 配置 — 1 个 cva 替代 2 个 Record lookup + loading 内联 animate-spin 三元
 * 新增 variant 只需在 variants.variant 加 1 个 key
 */
const bannerVariants = cva("", {
  compoundVariants: [
    // loading 走 Alert default variant + spin 图标
    { className: "[&>svg]:animate-spin", variant: "loading" },
  ],
  defaultVariants: { variant: "destructive" },
  variants: {
    variant: {
      destructive: "border-destructive/50 text-destructive [&>svg]:text-destructive",
      info: "border-blue-500/50 text-blue-700 dark:text-blue-300 [&>svg]:text-blue-500",
      loading: "",
      success:
        "border-emerald-500/50 text-emerald-700 dark:text-emerald-300 [&>svg]:text-emerald-500",
      warning: "border-amber-500/50 text-amber-700 dark:text-amber-300 [&>svg]:text-amber-500",
    },
  },
});

/** 变体 — 默认图标映射表 */
const defaultIcon: Record<ErrorBannerVariant, LucideIcon> = {
  destructive: AlertCircle,
  info: Info,
  loading: Loader2,
  success: CheckCircle2,
  warning: AlertTriangle,
};

/**
 * 错误提示条 — Alert 包装, 5 种变体 (destructive/warning/info/success/loading)
 * @param props.variant 变体 (默认 destructive)
 * @param props.description 必填描述文案 (或 descriptionNode 复杂子节点)
 * @param props.action 右侧操作按钮 (例 "重试" / "复制")
 * @returns ErrorBanner JSX
 */
export const ErrorBanner = ({
  variant = "destructive",
  title,
  description,
  descriptionNode,
  action,
  icon,
  className,
  dataTestid,
}: ErrorBannerProps) => {
  const Icon = icon ?? defaultIcon[variant];
  // Destructive 透传 shadcn variant; 其他 4 variant 用 className 模拟颜色
  const shadcnVariant = variant === "destructive" ? "destructive" : "default";
  // descriptionNode 优先 (用于 <ul> 等复杂子节点, 见 P1 batch/triples-form)
  const descriptionContent = descriptionNode ?? description;
  return (
    <Alert
      variant={shadcnVariant}
      className={cn(bannerVariants({ variant }), className)}
      data-testid={dataTestid}
    >
      <Icon className="h-4 w-4" />
      {title && <AlertTitle>{title}</AlertTitle>}
      <AlertDescription className="flex items-center justify-between gap-3">
        {descriptionContent}
        {action}
      </AlertDescription>
    </Alert>
  );
};
