// Dataset 列表数据 hook — 封装 fetchDatasets + TanStack Query
// (2026-06-27 Task 3.2) 替代 components/knowledge/dataset-switcher.tsx 等处
//   裸 useQuery({ queryKey: ['rag','knowledge','datasets'], queryFn: fetchDatasets }) 的重复模式.
// 约定: queryKey 跟现有 QK_DATASETS 保持一致, 避免 cache 失效重拉.
// StaleTime: 60s (1 min) — 数据集列表稳定, 默认窗口聚焦不重拉.
"use client";

import { useQuery } from "@tanstack/react-query";
import { type DatasetRow, fetchDatasets } from "@/lib/api/knowledge";

const STALE_TIME_MS = 60_000;

/**
 * 获取数据集列表 hook
 * 统一 queryKey + staleTime 约定, 替代组件中裸 useQuery 的重复模式
 * @returns  TanStack Query 结果, data 为 DatasetRow[]
 *
 * 调用边界:
 *   @client-bff  前端组件可用 (调 /api/* BFF)
 */
/** Dataset 列表 hook
 *  - 统一 queryKey + staleTime 约定
 *  - 替代组件中裸 useQuery({ queryKey: ['rag','knowledge','datasets'], queryFn: fetchDatasets }) 的重复模式
 */
export const useDatasets = () =>
  useQuery<DatasetRow[]>({
    queryFn: fetchDatasets,
    queryKey: ["rag", "knowledge", "datasets"],
    staleTime: STALE_TIME_MS,
  });
