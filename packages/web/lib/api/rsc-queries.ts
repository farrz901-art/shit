// Server-only RQ 工具: 单例 cache + 预取. 仅 server component 用.
// "server-only" 是 Next.js marker, 防止 client 端误 import 进来
// (在 vitest 里被 alias 成空模块, 见 vitest.config.ts)
import "server-only";
import { apiFetch } from "./config";
export { API_BASE } from "./config";
import { getErrorMessage } from "./errors";
import { QueryClient } from "@tanstack/react-query";
import { cache } from "react";
import { log } from "@/lib/log";
import { serverAuthHeaders } from "./auth.server";

/**
 * Per-request 单例 QueryClient. cache() 保证同 request 内多次调用返同实例.
 * - staleTime: Infinity → RSC 预取视为新鲜, 客户端 useQuery 接管时不会立即重拉
 * - gcTime: 0       → SSR 端不缓存, 避免污染下个 request
 * - retry: false    → server-side 失败让上层 (error.tsx) 兜, 不静默重试
 */
export const getRscQueryClient = cache(
  async (): Promise<QueryClient> =>
    new QueryClient({
      defaultOptions: {
        queries: {
          gcTime: 0,
          retry: false,
          staleTime: Infinity,
        },
      },
    }),
);

/**
 * 通用 server-side prefetch: 调 apiFetch() (拼 API_BASE + 鉴权 + 错误归一) 写入 qc cache.
 *
 * 失败 (NetworkError/ApiError) 时不抛 — log 后正常返回, 客户端 useQuery 看到 cache miss
 * 会自己重拉, 拉失败时由全局 RQ error listener 弹 toast (见 components/query/ErrorToaster.tsx).
 * 避免 "RSC 抛错 → 整页 500" 把整个布局/导航一起挂掉.
 *
 * 注意: 用 fetchQuery 不用 prefetchQuery, 后者会 .catch(noop) 吞掉错误, 我们要拿到 error 弹提示.
 *
 * @param qc        getRscQueryClient() 拿到的 QueryClient
 * @param queryKey  qKeys.* 工厂返的 RQ key, 客户端用同一 key 接管
 * @param path      要预取的相对路径 (e.g. "/api/kg/stats"), 自动拼 API_BASE
 */
// oxlint-disable-next-line id-length -- 泛型参数 T 是标准 TypeScript 约定
export const prefetchQuery = async <T>(
  queryClient: QueryClient,
  queryKey: readonly unknown[],
  path: string,
): Promise<void> => {
  try {
    await queryClient.fetchQuery({
      queryFn: async () => apiFetch<T>(path, { headers: await serverAuthHeaders() }),
      queryKey,
    });
  } catch (error) {
    // RSC 预取失败不挂整页, 留给客户端 useQuery 接管重拉 + 弹错.
    // 只打错误消息, 不打堆栈 (error 对象在 Bun/Node 下会打印完整 stack trace, 太吵)
    log.warn(`[prefetchQuery] 失败 ${path}: ${getErrorMessage(error)}`);
  }
};

/**
 * 通用 RSC 数据获取: 走 apiFetch().
 * 用于纯 RSC 页面 (无 RQ 接管), 跟 prefetchQuery (写 RQ cache) 是两条路径.
 *
 * (2026-06-14) 自动解包 `{ data: T }` 包装: 后端 list endpoint (e.g. /api/kg/datasets)
 * 统一返 Dify 风格 `{ data: T[] }`, 见 [[feedback-dify-api-returns-data-wrapper]] 扩展.
 * 调用方继续 `rscGet<DatasetRow[]>("/api/kg/datasets")` 当裸数组用, 零感知.
 * (2026-06-15) 启发式收紧成 "data 字段存在且值是数组" — Dify 真响应带 has_more/limit/total/page
 *   4 个额外字段, 旧 "Object.keys.length === 1" 漏拆, 上游拿 { data, has_more, ... } 走 .find/.map 全炸.
 *   data 是对象 (非数组) 时不拆, 避免误拆形如 { data: { foo: 1 } } 的嵌套对象.
 *
 * @param path  API 路径 (e.g. "/api/kg/nodes?limit=100"), 自动拼 API_BASE
 */
// oxlint-disable-next-line id-length -- 泛型参数 T 是标准 TypeScript 约定
export const rscGet = async <T>(path: string): Promise<T> => {
  const raw = await apiFetch<unknown>(path, { headers: await serverAuthHeaders() });
  // 仅当 data 字段值是数组时拆包装, 其它形态 ({ datasets, documents } / { data: { foo } } / 裸值) 跳过.
  if (typeof raw === "object" && raw !== null && Array.isArray((raw as { data?: unknown }).data)) {
    return (raw as { data: T }).data;
  }
  return raw as T;
};

// Re-export for callers that need the raw base (rare, e.g. constructing absolute URLs for cache keys)
