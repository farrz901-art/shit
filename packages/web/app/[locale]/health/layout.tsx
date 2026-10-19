"use client";
// B 档专属 (Task 26, 2026-06-12 redesign): 包 QueryClientProvider, 让 /health 共享同一个 RQ client.
// 跟 output/layout.tsx 同型, A 档页面不会加载 RQ 库, 减小首屏 bundle.
// (2026-06-14) QueryClient 工厂抽到 lib/api/query-client.ts: 集中 onError → sonner toast
import { type ReactNode, useState } from "react";
import { QueryClientProvider } from "@tanstack/react-query";
import { createBrowserQueryClient } from "@/lib/api/query-client";

/** HealthLayout - 健康页布局, 包 QueryClientProvider 实现 RQ 预取 + 客户端接管
 * @client-bff
 */
export default function HealthLayout({ children }: { children: ReactNode }) {
  // UseState 工厂: 整个 layout 生命周期内保持单例, 避免每次 render 都 new QueryClient.
  const [qc] = useState(() => createBrowserQueryClient());
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}
