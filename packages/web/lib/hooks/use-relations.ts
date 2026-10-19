// Knowledge Graph Relations 数据 hook — 封装 fetchRelations + TanStack Query
// (2026-06-27 Task 3.3) 替代 components/knowledge/relations/page.tsx 裸 useQuery 重复模式.
// 约定: queryKey 跟 useDatasets 一致前缀 ["rag", "knowledge", ...],
//   staleTime 60s 跟项目 TanStack Query 风格保持一致.
"use client";

import { useQuery } from "@tanstack/react-query";
import { type RelationRow, fetchRelations } from "@/lib/api/knowledge";

const STALE_TIME_MS = 60_000;

/** Knowledge Graph relations 列表 hook
 *  - 统一 queryKey + staleTime 约定
 *  - 替代组件中裸 useQuery({ queryKey: ['rag','knowledge','relations'], queryFn: fetchRelations }) 的重复模式
 * @param limit 可选查询条数限制 (后端默认 1000)
 */
export const useRelations = (limit?: number) =>
  useQuery<RelationRow[]>({
    queryFn: () => fetchRelations(limit),
    queryKey: ["rag", "knowledge", "relations", limit],
    staleTime: STALE_TIME_MS,
  });
