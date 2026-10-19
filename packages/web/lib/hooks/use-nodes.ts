// Knowledge Graph Nodes 数据 hook — 封装 fetchNodes + TanStack Query
// (2026-06-27 Task 3.3) 替代 components/knowledge/nodes/page.tsx 裸 useQuery 重复模式.
// 约定: queryKey 跟 useDatasets 一致前缀 ["rag", "knowledge", ...],
//   staleTime 60s 跟项目 TanStack Query 风格保持一致.
"use client";

import { useQuery } from "@tanstack/react-query";
import { type NodeRow, fetchNodes } from "@/lib/api/knowledge";

const STALE_TIME_MS = 60_000;

/** Knowledge Graph nodes 列表 hook
 *  - 统一 queryKey + staleTime 约定
 *  - 替代组件中裸 useQuery({ queryKey: ['rag','knowledge','nodes'], queryFn: fetchNodes }) 的重复模式
 * @param limit 可选查询条数限制 (后端默认 1000)
 */
export const useNodes = (limit?: number) =>
  useQuery<NodeRow[]>({
    queryFn: () => fetchNodes(limit),
    queryKey: ["rag", "knowledge", "nodes", limit],
    staleTime: STALE_TIME_MS,
  });
