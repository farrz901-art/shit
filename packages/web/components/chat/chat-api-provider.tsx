/**
 * TanStack Query 客户端 provider (2026-06-19 chat spec §3)
 * 跟 ThemeProvider / I18nProvider 嵌套一致, 放在 layout.tsx 包裹.
 * UseState 初始化 QueryClient 防 SSR 跨请求泄漏 (每个 tab 1 个 client, 避免状态污染).
 * Default: staleTime 1 min (跟后端 Redis 60s 对齐), retry 1 次, refetchOnWindowFocus true
 */

"use client";
import { ONE, ONE_MINUTE_MS } from "@/const";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { type ReactNode, useState } from "react";

const REFETCH_ON_FOCUS = true;

/**
 * Chat 模块 TanStack Query Provider — 跟 RootQueryClient 区别是放 chat layout 而非 root layout
 * (chat 模块是可选功能, 不污染全局 QueryClient)
 */
export const ChatApiProvider = ({ children }: { children: ReactNode }) => {
  // 1 个 QueryClient per 浏览器 tab, useState 防 SSR 跨请求泄漏
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            refetchOnWindowFocus: REFETCH_ON_FOCUS,
            retry: ONE,
            staleTime: ONE_MINUTE_MS, // 跟 Redis 60s 对齐,
          },
        },
      }),
  );
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
};
