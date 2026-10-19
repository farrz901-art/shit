"use client";
// B 档 layout 共享的 QueryClient 工厂 (2026-06-14 抽出来)
// 集中配置 + 集中错误处理:
//   - QueryCache.onError 捕获所有 useQuery 失败 → sonner toast.error
//   - 失败不再 throw 让 React error boundary 兜, 避免整页 500
//   - RSC 端 prefetchQuery 失败已在 lib/api/rsc-queries.ts 吞掉 + console.warn,
//     HydrationBoundary 拿到空 cache → 客户端 useQuery 重拉 → 这里 onError 弹错
import { getErrorMessage } from "./errors";
import { QueryCache, QueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

/**
 * 单例 QueryClient 工厂.
 * 整个 layout 生命周期内保持单例, 避免每次 render 都 new.
 * 跟 lib/api/rsc-queries.ts getRscQueryClient() 默认配置对齐:
 *   - staleTime: Infinity → RSC 预取视为新鲜, 客户端接管不立即重拉
 *   - gcTime: 0       → SSR 端不缓存, 避免污染下个 request
 *   - retry: false    → 失败由 onError 弹错, 不静默重试
 */
export const createBrowserQueryClient = (): QueryClient =>
  new QueryClient({
    defaultOptions: {
      queries: { gcTime: 0, retry: false, staleTime: Infinity },
    },
    queryCache: new QueryCache({
      onError: (error) => {
        // 全局兜底: useQuery 失败都弹 toast, 组件无需各自 try/catch.
        // 不 throw → React error boundary 不会触发, 整页不挂.
        toast.error(getErrorMessage(error));
      },
    }),
  });
