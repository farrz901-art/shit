// 字典管理只读 banner (2026-06-19 lookup module Task 9)
// 顶部状态条, 显示 DICTIONARY_READONLY 是否开启.
// 真实 readonly 状态以后端 /api/admin/dicts/system-info 端点为准 (T6 没建, 当前 UI 兜底默认 false).
// 跟 ErrorBanner 风格一致但语义不同: 绿色 = 正常可写, 红色 = 只读禁止写入.
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Lock, Unlock } from "lucide-react";
import { cn } from "@/lib/utils";

/** 字典只读状态条属性 */
export interface ReadonlyBannerProps {
  /** 实际 readonly 状态 (从后端 system-info 拉). 默认 false (正常状态). */
  readonly?: boolean;
  /** 字典总数 (来自 system-info), 显示在 banner 末尾 */
  dictsCount?: number;
  /** 只读状态文案 (i18n key) */
  readonlyText: string;
  /** 可写状态文案 (i18n key) */
  writableText: string;
  /** 额外 class */
  className?: string;
}

/**
 * 字典管理只读状态条
 *
 * 顶部状态条, 显示 DICTIONARY_READONLY 是否开启.
 * 红色 = 只读禁止所有写操作; 绿色 = 正常可写.
 * 与 ErrorBanner 同形态但语义不同, 用 shadcn Alert 自定义 className.
 *
 * @param props - 组件属性
 * @param props.readonly - 实际 readonly 状态 (从后端 system-info 拉)
 * @param props.dictsCount - 字典总数
 * @param props.readonlyText - 只读文案 (i18n key)
 * @param props.writableText - 可写文案 (i18n key)
 * @param props.className - 额外 class
 * @shared
 */
export const ReadonlyBanner = ({
  readonly = false,
  dictsCount,
  readonlyText,
  writableText,
  className,
}: ReadonlyBannerProps) => {
  const Icon = readonly ? Lock : Unlock;
  const colorClass = readonly
    ? "border-destructive/50 text-destructive [&>svg]:text-destructive"
    : "border-emerald-500/50 text-emerald-700 dark:text-emerald-300 [&>svg]:text-emerald-500";

  return (
    <Alert data-testid="readonly-banner" className={cn(colorClass, className)}>
      <Icon className="h-4 w-4" />
      <AlertTitle>{readonly ? readonlyText : writableText}</AlertTitle>
      {dictsCount !== undefined && (
        <AlertDescription className="text-xs">{dictsCount} dicts</AlertDescription>
      )}
    </Alert>
  );
};
