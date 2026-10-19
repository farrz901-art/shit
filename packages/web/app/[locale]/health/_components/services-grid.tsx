// ServicesGrid: 5 服务卡片网格 (2026-06-15, +MinIO 2026-06-17)
// 从 health-client.tsx 拆出, 含 AnimatedServiceCard (stagger 延迟包装)
// 视觉: lg 一行 5, md 2, 每卡 HealthServiceCard
import { Database, Globe2, HardDrive, type LucideIcon, RefreshCw, Server, Zap } from "lucide-react";
import type { CheckResult } from "@/lib/api/health";
import { HealthServiceCard } from "./health-service-card";
import { useTranslations } from "next-intl";
import { SECONDS_PER_MINUTE, ZERO } from "@/const";

// === 格式化工具 (跟 hero-section 共享, 各自内联避免循环依赖) ===

/** 每小时秒数 */
const SECONDS_PER_HOUR = 3600;
/** 零值常量 */
const ZERO_UPTIME = ZERO;
/** 延迟精度小数位 */
const DECIMAL_PLACES = 0;
/** 截取起始索引 */
const SLICE_START_INDEX = 0;
/** 截取偏移量 */
const TRIM_OFFSET = 1;

/** formatUptime - 格式化运行时长 (秒 → "Xh Ym" / "Xm" / "Xs")
 * @param seconds 秒数
 * @returns 格式化的时长字符串
 * @shared
 */
const formatUptime = (seconds: number): string => {
  const hours = Math.floor(seconds / SECONDS_PER_HOUR);
  const minutes = Math.floor((seconds % SECONDS_PER_HOUR) / SECONDS_PER_MINUTE);
  if (hours > ZERO_UPTIME) {
    return `${hours}h ${minutes}m`;
  }
  if (minutes > ZERO_UPTIME) {
    return `${minutes}m`;
  }
  return `${seconds}s`;
};

/** 延迟快速阈值上限 (ms) */
const LATENCY_FAST_MAX_MS = 80;
/** 延迟慢速阈值下限 (ms) */
const LATENCY_SLOW_MIN_MS = 200;

/** latencyLabel - 根据延迟毫秒数返回等级标签
 * @param latencyMs 延迟毫秒数 (可为 null)
 * @returns "FAST" | "OK" | "SLOW" | ""
 * @shared
 */
const latencyLabel = (latencyMs: number | null): string => {
  if (latencyMs === null) {
    return "";
  }
  if (latencyMs > LATENCY_SLOW_MIN_MS) {
    return "SLOW";
  }
  if (latencyMs > LATENCY_FAST_MAX_MS) {
    return "OK";
  }
  return "FAST";
};

/** latencyMetric - 延迟毫秒数格式化显示
 * @param latencyMs 延迟毫秒数 (可为 null)
 * @returns 格式化的延迟字符串或占位符
 * @shared
 */
const latencyMetric = (latencyMs: number | null): string => {
  if (latencyMs === null) {
    return "—";
  }
  return latencyMs.toFixed(DECIMAL_PLACES);
};

// (2026-06-17) MinIO 卡片专属: 按 backend 选渲染分支
//  - local + skipped → 显示 backend 标签 + 未启用提示
//  - minio → 显示 latency + bucket@endpoint
//  - 错误 → 跟其他服务一致 (badge=error, hint 显示 message)
/** MinIO 提示文案最大截取长度 */
const MINIO_LOCAL_HINT_MAX = 40;

/** minioSummary - MinIO 指标摘要计算 (按 backend 选渲染分支)
 * @param minio MinIO 健康检查结果
 * @param tr i18n 翻译函数
 * @returns 主指标、次指标和提示文案
 * @shared
 */
const minioSummary = (
  minio: CheckResult,
  tr: ReturnType<typeof useTranslations>,
): { primaryMetric: string; primaryUnit: string; secondaryMetric: string; hint: string } => {
  const backend = minio.extra.backend as string | undefined;
  const skipped = minio.extra.skipped === true;
  if (backend === "local" && skipped) {
    return {
      hint: tr("未启用 MinIO (本地存储)"),
      primaryMetric: "local",
      primaryUnit: "",
      secondaryMetric: "skipped",
    };
  }
  const bucket = (minio.extra.bucket as string | undefined) ?? "—";
  const endpoint = (minio.extra.endpoint as string | undefined) ?? "";
  // Endpoint 太长 (URL) 截前 30 字符 + …, 不破布局
  const endpointShort =
    endpoint.length > MINIO_LOCAL_HINT_MAX
      ? `${endpoint.slice(SLICE_START_INDEX, MINIO_LOCAL_HINT_MAX - TRIM_OFFSET)}…`
      : endpoint;
  return {
    hint: tr("延迟"),
    primaryMetric: latencyMetric(minio.latency_ms),
    primaryUnit: "ms",
    secondaryMetric: endpointShort ? `${bucket} · ${endpointShort}` : bucket,
  };
};

// === Redis 卡片专属: 延迟 + 状态 ===

/** redisSummary - Redis 指标摘要计算 (延迟 + 状态标签)
 * @param redis Redis 健康检查结果
 * @param tr i18n 翻译函数
 * @returns 主指标、次指标和提示文案
 * @shared
 */
const redisSummary = (
  redis: CheckResult,
  tr: ReturnType<typeof useTranslations>,
): { primaryMetric: string; primaryUnit: string; secondaryMetric: string; hint: string } => ({
  hint: tr("延迟"),
  primaryMetric: latencyMetric(redis.latency_ms),
  primaryUnit: "ms",
  secondaryMetric: latencyLabel(redis.latency_ms),
});

// === 延迟 stagger 常量 ===
/** Server 卡片延迟 (ms) */
const STAGGER_PYTHON_MS = 50;
/** Dify 卡片延迟 (ms) */
const STAGGER_DIFY_MS = 100;
/** Neo4j 卡片延迟 (ms) */
const STAGGER_NEO4J_MS = 150;
/** pgvector 卡片延迟 (ms) */
const STAGGER_PGVECTOR_MS = 200;
/** MinIO 卡片延迟 (ms) */
const STAGGER_MINIO_MS = 250;
/** Redis 卡片延迟 (ms) */
const STAGGER_REDIS_MS = 300;

/** AnimatedServiceCard - 带 stagger 延迟动画的服务卡片包装
 * @shared
 */
const AnimatedServiceCard = ({
  title,
  icon,
  result,
  primaryMetric,
  primaryUnit,
  secondaryMetric,
  hint,
  delayMs,
}: {
  title: string;
  icon: LucideIcon;
  result: CheckResult;
  primaryMetric: string;
  primaryUnit: string;
  secondaryMetric: string;
  hint: string;
  delayMs: number;
}) => (
  <div className="transition-all duration-500" style={{ animationDelay: `${delayMs}ms` }}>
    <HealthServiceCard
      title={title}
      icon={icon}
      result={result}
      primaryMetric={primaryMetric}
      primaryUnit={primaryUnit}
      secondaryMetric={secondaryMetric}
      secondaryUnit=""
      hint={hint}
    />
  </div>
);

// === ServicesGrid ===

/** ServicesGridProps - 服务网格面板属性 */
export interface ServicesGridProps {
  /** Python 服务检查结果 */
  python: CheckResult;
  /** Dify 服务检查结果 */
  dify: CheckResult;
  /** Neo4j 服务检查结果 */
  neo4j: CheckResult;
  /** pgvector 服务检查结果 */
  pgvector: CheckResult;
  /** MinIO 服务检查结果 */
  minio: CheckResult;
  /** Redis 服务检查结果 */
  redis: CheckResult;
  /** Python 进程运行时长 (秒) */
  uptimeS: number | undefined;
  /** Python 版本号 */
  pyVersion: string | undefined;
}

/** ServicesGrid - 服务卡片网格, 展示 6 个服务的健康状态及指标
 * @shared
 */
export const ServicesGrid = ({
  python,
  dify,
  neo4j,
  pgvector,
  minio,
  redis,
  uptimeS,
  pyVersion,
}: ServicesGridProps) => {
  const tr = useTranslations();
  const minioView = minioSummary(minio, tr);
  const redisView = redisSummary(redis, tr);
  return (
    <section
      aria-label="services"
      className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-6"
    >
      <AnimatedServiceCard
        title={"Server"}
        icon={Server}
        result={python}
        primaryMetric={uptimeS !== undefined ? formatUptime(uptimeS) : "—"}
        primaryUnit=""
        secondaryMetric={pyVersion !== undefined ? `v${pyVersion}` : ""}
        hint=""
        delayMs={STAGGER_PYTHON_MS}
      />
      <AnimatedServiceCard
        title={tr("Dify")}
        icon={Globe2}
        result={dify}
        primaryMetric={latencyMetric(dify.latency_ms)}
        primaryUnit="ms"
        secondaryMetric={latencyLabel(dify.latency_ms)}
        hint={tr("延迟")}
        delayMs={STAGGER_DIFY_MS}
      />
      <AnimatedServiceCard
        title={tr("Neo4j")}
        icon={Database}
        result={neo4j}
        primaryMetric={latencyMetric(neo4j.latency_ms)}
        primaryUnit="ms"
        secondaryMetric={latencyLabel(neo4j.latency_ms)}
        hint={tr("延迟")}
        delayMs={STAGGER_NEO4J_MS}
      />
      <AnimatedServiceCard
        title={tr("pgvector")}
        icon={Zap}
        result={pgvector}
        primaryMetric={latencyMetric(pgvector.latency_ms)}
        primaryUnit="ms"
        secondaryMetric={latencyLabel(pgvector.latency_ms)}
        hint={tr("延迟")}
        delayMs={STAGGER_PGVECTOR_MS}
      />
      <AnimatedServiceCard
        title={tr("MinIO")}
        icon={HardDrive}
        result={minio}
        primaryMetric={minioView.primaryMetric}
        primaryUnit={minioView.primaryUnit}
        secondaryMetric={minioView.secondaryMetric}
        hint={minioView.hint}
        delayMs={STAGGER_MINIO_MS}
      />
      <AnimatedServiceCard
        title={tr("Redis 缓存")}
        icon={RefreshCw}
        result={redis}
        primaryMetric={redisView.primaryMetric}
        primaryUnit={redisView.primaryUnit}
        secondaryMetric={redisView.secondaryMetric}
        hint={redisView.hint}
        delayMs={STAGGER_REDIS_MS}
      />
    </section>
  );
};
