"use client";
// 独立 QueryClientProvider (2026-06-28 P3 refactor): 替 3 处 49 行重复样板
//   - components/knowledge/dataset-switcher.tsx (16 行)
//   - components/knowledge/domain-switcher.tsx (17 行)
//   - components/common/display/app-health-dot.tsx (16 行)
//
// 用法: 在 layout 外 / 不依赖根 QueryClient 的组件 (e.g. Header 内嵌 Dify 健康点)
// <StandaloneQueryProvider><MyComponent /></StandaloneQueryProvider>
//
// 默认配置 (跟 app B 档 layout 的 getQueryClient() 对齐):
//   - staleTime: Infinity (这些组件是 polling, 不需要 revalidate on focus)
//   - gcTime: 0 (短生命, 卸载即清)
//   - retry: false (Dify health 不应该重试, 直接展示不可达)
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";

/** 独立 QueryClient 默认配置: 跟 lib/api/query-client.ts 对齐 */
export const STANDALONE_QC_OPTIONS = {
  defaultOptions: {
    queries: { gcTime: 0, retry: false, staleTime: Infinity },
  },
} as const;

/**
 * StandaloneQueryProvider 属性接口 — 子组件
 * @client-bff
 */
export interface StandaloneQueryProviderProps {
  children: ReactNode;
}

/**
 * 独立 QueryClientProvider — 替 3 处 49 行重复样板
 * 内部 useState 工厂单例 QueryClient, 默认配置 staleTime=Infinity / gcTime=0 / retry=false
 * 适用场景: layout 外 / 不依赖根 QueryClient 的组件 (e.g. Header 内嵌 Dify 健康点)
 * @param props.children 子组件
 * @returns QueryClientProvider JSX
 */
export const StandaloneQueryProvider = ({ children }: StandaloneQueryProviderProps) => {
  // useState 工厂: 整个组件生命周期内保持单例 QueryClient, 避免每次 render 都 new
  const [queryClient] = useState(() => new QueryClient(STANDALONE_QC_OPTIONS));
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
};
