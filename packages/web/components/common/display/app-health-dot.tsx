"use client";
// Dify 监控点 (绿/红 呼吸圆点 + 鼠标悬停提示) (Task 27, 2026-06-12 redesign, 2026-06-15 改用 BreathingDot)
// 模式: useSWR → useQuery, 5s 轮询, 自包 QueryClientProvider.
//   - HealthDot 挂在 root Header, 不在 B 档 (/output, /health) layout 下,
//     所以不能在 B 档 QC provider 下消费; 内部 useState 工厂单例自包一个 QC.
//   - 端点继续用 /api/kg/health (Dify 简单 health), 跟 system admin 端点无关.
//   - queryKey 用独立 ["rag", "health", "dot"], 不复用 qKeys.health.system() (那个是 admin 端点).
import { useQuery } from "@tanstack/react-query";
import { BreathingDot } from "@/components/common/display/app-breathing-dot";
import { StandaloneQueryProvider } from "@/components/common/providers";
import { fetchDifyHealth } from "@/lib/api/health";

/** Dify 健康检查轮询间隔 (毫秒) @shared */
const POLL_MS = 5000;
// 独立 queryKey: 跟 health/page 用 qKeys.health.system() 隔离 (端点不同, 也不应被 RSC 预取灌数据)
/** Dify 健康检查 queryKey — 独立于 admin 端点 */
const QK_DOT = ["rag", "health", "dot"] as const;

/**
 * Dify 健康状态查询组件 (内部)
 * useQuery 5s 轮询, 根据结果返回对应颜色的 BreathingDot
 * 加载中=muted, 连通=success(绿), 不可达=error(红)
 * @client-bff
 * @returns BreathingDot 组件
 */
const Dot = () => {
  const { data, isLoading } = useQuery({
    queryFn: () => fetchDifyHealth(),
    queryKey: QK_DOT,
    refetchInterval: POLL_MS,
  });
  // Loading=muted, ok=success(绿), 不可达=error(红); 全部走呼吸灯动画

  const loadingColor = "muted";
  const readyColor = data?.ok ? "success" : "error";
  const color = isLoading ? loadingColor : readyColor;

  return (
    <BreathingDot
      color={color}
      size="md"
      title={data?.ok ? "Dify 监控" : "Dify 不可达"}
      data-testid="health-dot"
    />
  );
};

/**
 * Dify 监控健康圆点 — useQuery 5s 轮询, 独立 QueryClientProvider 隔离
 * 绿色 = Dify 可达, 红色 = 不可达, 灰色 = 加载中
 * @client-bff
 * @returns BreathingDot 组件
 */
export const HealthDot = () => (
  // 用 StandaloneQueryProvider 包裹: 内部 useState 工厂单例 + 默认配置
  // (staleTime: Infinity / gcTime: 0 / retry: false) 跟 B 档 layout 隔离
  <StandaloneQueryProvider>
    <Dot />
  </StandaloneQueryProvider>
);
