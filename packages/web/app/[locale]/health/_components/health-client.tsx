"use client";
// /health 监控状态页 client 子组件 (Task 26, 2026-06-12 redesign)
// (2026-06-15) Mission Control 美学重做: NASA ops console 风格
// (2026-06-15) 拆分: hero-section / services-grid / system-resources 独立文件
//   本文件只保留: useQuery + 数据编排 + 状态分支 + 全局 helpers
// (2026-06-18) 改默认手动拉, 按钮启动/停止轮询 + 全局单例
import { Activity, Pause, Play } from "lucide-react";
import { type HealthPayload, fetchSystem } from "@/lib/api/health";
import { useEffect, useRef, useState } from "react";
import { ErrorBanner } from "@/components/common/feedback";
import { HealthStatusBoard } from "./hero-section";
import { PageHero } from "@/components/common/navigation/app-page-hero";
import { ServicesGrid } from "./services-grid";
import { SystemResourcesSection } from "./system-resources";
import { qKeys } from "@/lib/api/query-keys";
import { useQuery } from "@tanstack/react-query";
import { useTranslations } from "next-intl";

// === 常量 ===
/** 轮询间隔 (10s) */
const POLL_MS = 10_000;
/** 管理员权限错误标识 */
const ERROR_NEED_ADMIN = "need_admin";

/** 模块级轮询标志 (全局单例) */
let globalPollingActive = false;

// === 轮询 hook ===

/** useHealthPolling - 健康页轮询 Hook, 支持全局单例开关与页面卸载自动关闭
 * @returns 轮询状态与切换函数
 * @client-bff
 */
const useHealthPolling = () => {
  const [isPolling, setIsPolling] = useState(false);
  const mountedRef = useRef(true);

  const togglePolling = () => {
    if (isPolling) {
      // 停止轮询
      globalPollingActive = false;
      setIsPolling(false);
    } else {
      // 启动轮询前检查全局单例
      if (globalPollingActive) {
        // 已有其他实例在轮询, 不操作
        return;
      }
      globalPollingActive = true;
      setIsPolling(true);
    }
  };

  // 离开页面自动关闭轮询
  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      if (globalPollingActive) {
        globalPollingActive = false;
      }
    };
  }, []);

  // 同步 globalPollingActive 到组件卸载: isPolling 停时也清全局标志
  useEffect(() => {
    if (!isPolling && globalPollingActive) {
      globalPollingActive = false;
    }
  }, [isPolling]);

  return { isPolling, togglePolling };
};

// === 全局 helpers ===

/** resolveErrorMessage - 根据错误类型解析展示文案
 * @param error 原始错误对象
 * @param tr i18n 翻译函数
 * @returns 本地化错误消息
 * @shared
 */
const resolveErrorMessage = (error: Error, tr: ReturnType<typeof useTranslations>): string => {
  if (String(error.message) === ERROR_NEED_ADMIN) {
    return tr("需要管理员权限");
  }
  return tr("后端服务不可达, 请检查 main_py 是否在 8000 端口运行");
};

// === 背景网格 ===

/** BackgroundGrid - 背景网格装饰 (雷达网格视觉)
 * @shared
 */
const BackgroundGrid = () => (
  <div
    aria-hidden
    className="pointer-events-none absolute inset-0 opacity-[0.025]"
    style={{
      WebkitMaskImage: "radial-gradient(ellipse 70% 60% at 50% 30%, black 30%, transparent 80%)",
      backgroundImage:
        "linear-gradient(to right, currentColor 1px, transparent 1px), linear-gradient(to bottom, currentColor 1px, transparent 1px)",
      backgroundSize: "32px 32px",
      maskImage: "radial-gradient(ellipse 70% 60% at 50% 30%, black 30%, transparent 80%)",
    }}
  />
);

// === 状态分支 ===

/** ErrorState - 健康页错误状态展示
 * @shared
 */
const ErrorState = ({
  message,
  tr,
}: {
  message: string;
  tr: ReturnType<typeof useTranslations>;
}) => (
  <div className="flex h-full flex-col gap-6 p-8 lg:p-12">
    <h1 className="display text-4xl">{tr("监控状态")}</h1>
    <ErrorBanner variant="destructive" description={message} dataTestid="health-error" />
  </div>
);

/** LoadingState - 健康页加载占位状态
 * @shared
 */
const LoadingState = ({ tr }: { tr: ReturnType<typeof useTranslations> }) => (
  <div className="flex h-full flex-col gap-6 p-8 lg:p-12">
    <h1 className="display text-4xl">{tr("监控状态")}</h1>
    <div className="flex items-center gap-3 text-muted-foreground">
      <Activity className="h-4 w-4 animate-pulse text-status-running" strokeWidth={1.5} />
      <p className="num text-sm">{tr("数据采集中…")}</p>
    </div>
  </div>
);

// === Footer ===

/** Footer - 监控状态页底部栏 (服务总数 + 轮询状态)
 * @shared
 */
const Footer = ({ totalCount, isPolling }: { totalCount: number; isPolling: boolean }) => (
  <footer className="num flex items-center justify-between border-t border-border/60 pt-4 text-[10px] uppercase tracking-[0.2em] text-muted-foreground/60">
    <span>{totalCount} 服务 监控中</span>
    <span>{isPolling ? "10s 自动刷新" : "手动刷新"}</span>
  </footer>
);

// === 成功状态仪表板 ===

/** DashboardContent - 健康监控主仪表板内容组件
 * @shared
 */
const DashboardContent = ({
  data,
  isPolling,
  togglePolling,
  tr,
}: {
  data: HealthPayload;
  isPolling: boolean;
  togglePolling: () => void;
  tr: ReturnType<typeof useTranslations>;
}) => {
  const { python, dify, neo4j, pgvector, minio, redis, system, checked_at: rawCheckedAt } = data;
  const checkedAt = rawCheckedAt ?? "";
  const services = [python, dify, neo4j, pgvector, minio, redis, system];
  const okCount = services.filter((svc) => svc.status === "ok").length;
  const allOk = okCount === services.length;
  const uptimeS = python.extra.uptime_s as number | undefined;
  const pyVersion = python.extra.version as string | undefined;

  return (
    <div className="relative min-h-full">
      <BackgroundGrid />
      <div className="relative mx-auto flex flex-col gap-4">
        <PageHero
          eyebrow={tr("服务监控")}
          title={tr("监控状态")}
          actions={
            <button
              type="button"
              onClick={togglePolling}
              className="num flex items-center gap-1.5 rounded-md border border-border/60 px-3 py-1.5 text-xs uppercase tracking-[0.18em] text-muted-foreground transition-colors hover:border-ink/30 hover:text-foreground"
              aria-label={isPolling ? tr("停止轮询") : tr("开始轮询")}
            >
              {isPolling ? (
                <>
                  <Pause className="h-3 w-3" strokeWidth={1.5} />
                  {tr("停止轮询")}
                </>
              ) : (
                <>
                  <Play className="h-3 w-3" strokeWidth={1.5} />
                  {tr("开始轮询")}
                </>
              )}
            </button>
          }
        />
        <HealthStatusBoard
          okCount={okCount}
          totalCount={services.length}
          allOk={allOk}
          pyVersion={pyVersion}
          uptimeS={uptimeS}
          checkedAt={checkedAt}
        />
        <ServicesGrid
          python={python}
          dify={dify}
          neo4j={neo4j}
          pgvector={pgvector}
          minio={minio}
          redis={redis}
          uptimeS={uptimeS}
          pyVersion={pyVersion}
        />
        <SystemResourcesSection system={system} />
        <Footer totalCount={services.length} isPolling={isPolling} />
      </div>
    </div>
  );
};

// === 主组件 ===

/** HealthClient - 监控状态页客户端主组件, 使用 useQuery 拉取健康数据并编排各子面板
 * @client-bff
 */
export const HealthClient = () => {
  const tr = useTranslations();
  const { isPolling, togglePolling } = useHealthPolling();

  const { data, error } = useQuery<HealthPayload>({
    queryFn: () => fetchSystem(),
    queryKey: qKeys.health.system(),
    refetchInterval: isPolling ? POLL_MS : false,
  });

  if (error) {
    return <ErrorState message={resolveErrorMessage(error, tr)} tr={tr} />;
  }

  if (!data || data.checked_at === null) {
    return <LoadingState tr={tr} />;
  }

  return (
    <DashboardContent data={data} isPolling={isPolling} togglePolling={togglePolling} tr={tr} />
  );
};
