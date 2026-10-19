"use client";
// B 档专属: 包 QueryClientProvider, 让 /output 与 /output/[task_id] 共享同一个 RQ client.
// 放在 output/layout.tsx 范围内, A 档 (RSC 化) 页面不会加载 RQ 库, 减小首屏 bundle.
// (2026-06-14) QueryClient 工厂抽到 lib/api/query-client.ts: 集中 onError → sonner toast
import { type ReactNode, useState } from "react";
import { QueryClientProvider } from "@tanstack/react-query";
import { createBrowserQueryClient } from "@/lib/api/query-client";

/**
 * OutputLayout - /output 专属 layout (包 QueryClientProvider, 共享 RQ client)
 * @param props.children - 子页面内容
 * @client-bff
 */
export default function OutputLayout({ children }: { children: ReactNode }) {
  // UseState 工厂: 整个 layout 生命周期内保持单例, 避免每次 render 都 new QueryClient.
  const [qc] = useState(() => createBrowserQueryClient());
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}
