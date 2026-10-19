/**
 * 环境标识徽章 (2026-06-15) — 从 components/knowledge/ 升 common/
 * 从 process.env.NEXT_PUBLIC_ENV 读, 默认 "DEV"
 * 通用: 任何 root header / status bar 都能用, 不专属 knowledge
 * Side effect: 模块加载时读 process.env (浏览器端 NEXT_PUBLIC_ 前缀)
 */
import { Badge } from "@/components/ui/badge";

/** 当前环境标识, 默认 "DEV" @shared */
const ENV = process.env.NEXT_PUBLIC_ENV ?? "DEV";

/** 环境到 Tailwind 样式的映射 @shared */
const variant: Record<string, string> = {
  DEV: "bg-status-warning/10 text-status-warning",
  PROD: "bg-status-error/10 text-status-error",
  STAGING: "bg-status-running/10 text-status-running",
};

/**
 * 环境徽章 — DEV (黄) / STAGING (蓝) / PROD (红)
 * 默认从 NEXT_PUBLIC_ENV env 读, 缺失时 fallback DEV
 * @shared
 * @returns 环境徽章 JSX
 */
export const EnvBadge = () => <Badge className={variant[ENV] ?? variant.DEV}>{ENV}</Badge>;
