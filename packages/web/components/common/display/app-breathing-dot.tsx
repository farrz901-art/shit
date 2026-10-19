/**
 * 呼吸灯圆点 (2026-06-15): 替代 page.tsx / HealthDot / DecodeInputBar 散落的 ping 圆点
 *   双层结构: 外层 ping 半透明扩散, 内层实心 dot
 *   Color 用枚举 + lookup map 锁 Tailwind 类 (v4 不能动态拼 `bg-${color}`, 会被 purge)
 *   Size: sm=1.5×1.5 (默认), md=2.5×2.5 (HealthDot 用)
 */
import { cn } from "@/lib/utils";

/** 呼吸灯颜色枚举: moss (绿/健康) / clay (橙/警告) / success (绿/成功) / error (红/失败) / muted (灰/离线) */
export type BreathingDotColor = "moss" | "clay" | "success" | "error" | "muted";
/** 呼吸灯尺寸: sm=1.5x1.5 (默认) / md=2.5x2.5 (HealthDot 用) */
export type BreathingDotSize = "sm" | "md";

/**
 * BreathingDot 属性接口 — 颜色、尺寸、className 及 tooltip
 * @shared
 * @property color 颜色枚举: moss/clay/success/error/muted
 * @property size 尺寸: sm (1.5x1.5, 默认) / md (2.5x2.5)
 * @property className 自定义类名
 * @property title 鼠标悬停 tooltip
 * @property "data-testid" 测试 ID
 */
export interface BreathingDotProps {
  color?: BreathingDotColor;
  size?: BreathingDotSize;
  className?: string;
  title?: string;
  "data-testid"?: string;
}

/**
 * 颜色 lookup: ping 层用 /60 半透明便于扩散柔和, muted 状态再淡一档
 * @shared
 */
const COLOR_MAP: Record<BreathingDotColor, { ping: string; dot: string }> = {
  clay: { dot: "bg-clay", ping: "bg-clay/60" },
  error: { dot: "bg-status-error", ping: "bg-status-error/60" },
  moss: { dot: "bg-moss", ping: "bg-moss/60" },
  muted: { dot: "bg-muted-foreground/50", ping: "bg-muted-foreground/40" },
  success: { dot: "bg-status-success", ping: "bg-status-success/60" },
};

/**
 * 尺寸 lookup: 容器和实心 dot 同步
 * @shared
 */
const SIZE_MAP: Record<BreathingDotSize, string> = {
  md: "h-2.5 w-2.5",
  sm: "h-1.5 w-1.5",
};

/**
 * 呼吸灯圆点 — ping 半透明扩散 + 内部实心 dot
 * @shared
 * @param props.color 颜色枚举: moss (绿/健康) / clay (橙/警告) / success (绿/成功) / error (红/失败) / muted (灰/离线)
 * @param props.size 尺寸: sm=1.5×1.5 (默认) / md=2.5×2.5 (HealthDot 用)
 * @param props.title 鼠标 hover tooltip
 * @returns 呼吸灯圆点 JSX
 */
export const BreathingDot = ({
  color = "moss",
  size = "sm",
  className,
  title,
  "data-testid": dataTestid,
}: BreathingDotProps) => {
  const sizeCls = SIZE_MAP[size];
  const { ping, dot } = COLOR_MAP[color];
  return (
    <span
      className={cn("relative flex", sizeCls, className)}
      title={title}
      data-testid={dataTestid}
    >
      <span className={cn("absolute inset-0 animate-ping rounded-full", ping)} />
      <span className={cn("relative inline-block rounded-full", sizeCls, dot)} />
    </span>
  );
};
