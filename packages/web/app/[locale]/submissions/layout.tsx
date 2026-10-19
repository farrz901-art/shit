"use client";
// /submissions B 档专属: 包 QueryClientProvider, 让 SubmissionsTabs / MySubmissionsList /
// AllApprovalsTable 共享同一个 RQ client. 跟 /health / /output layout 同型.
// 之前没 QC → useQuery 抛 "No QueryClient set", 修 2026-06-14.
import { type ReactNode, useState } from "react";
import { QueryClientProvider } from "@tanstack/react-query";
import { createBrowserQueryClient } from "@/lib/api/query-client";

/**
 * SubmissionsLayout - 提交审核页面布局
 * @param props.children - 子组件
 * @client-bff
 */
export default function SubmissionsLayout({ children }: { children: ReactNode }) {
  // UseState 工厂: 整个 layout 生命周期内保持单例, 避免每次 render 都 new QueryClient.
  const [qc] = useState(() => createBrowserQueryClient());
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}
