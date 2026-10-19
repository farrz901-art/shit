// UseLookup hook (2026-06-19 lookup module §5.5)
// TanStack Query 模式 (跟 lib/chat/api.ts useConversations 一致).
// 提供 items + byKey + i18n labelFor 工具方法, 业务组件直接 map 到 <Select> / <RadioGroup> 等.
// StaleTime 5 分钟, 跟后端 Redis L2 缓存对齐; 窗口聚焦不重复拉 (字典数据稳定).
"use client";

import {
  type FetchLookupOpts,
  type LookupItem,
  fetchAllLookups,
  fetchLookup,
} from "@/lib/api/lookups";
import { useQuery } from "@tanstack/react-query";
import { FIVE, MS_PER_SECOND, SECONDS_PER_MINUTE } from "@/const";

// 5 分钟 = 后端 Redis LookupCache TTL; staleTime 内不重复发请求.
const FIVE_MIN = FIVE * SECONDS_PER_MINUTE * MS_PER_SECOND;

/**
 * 查单个字典 + 业务工具方法.
 *
 * 返回值:
 *   - items: 字典项数组 (按后端 sort 排序, 已过滤 is_active=false)
 *   - byKey: items 转 {key: item} 索引, O(1) 取单项
 *   - labelFor(key, locale): 查 label_zh (默认) / label_en, 找不到返 key 兜底
 *   - isLoading / error / refresh: TanStack Query 标准字段
 *
 * 用法:
 *   const { items, labelFor } = useLookup("approval_review_status");
 *   return <Select options={items.map(i => ({ value: i.key, label: labelFor(i.key) }))} />;
 */
export const useLookup = (dictCode: string, opts: FetchLookupOpts = {}) => {
  const lang = opts.lang ?? "both";
  const onlyActive = opts.onlyActive ?? true;
  const query = useQuery({
    queryFn: () => fetchLookup(dictCode, opts),
    queryKey: ["lookup", dictCode, lang, onlyActive],
    refetchOnWindowFocus: false,
    staleTime: FIVE_MIN,
  });
  // Items 已按 sort 排, isLoading=true 时返空数组避免下游 .map 报错.
  const items: LookupItem[] = query.data?.items ?? [];
  // ByKey 索引: O(1) 取单项, 业务下拉回填常用.
  const byKey = Object.fromEntries(items.map((item) => [item.key, item])) as Record<
    string,
    LookupItem
  >;
  return {
    byKey,
    error: query.error,
    isLoading: query.isLoading,
    items,
    // 查 i18n label: 默认 zh, locale="en" 切英文. 找不到 (后端没缓存 / key 已删) 返 key 兜底.
    labelFor: (key: string, locale: "zh" | "en" = "zh"): string =>
      byKey[key]?.[`label_${locale}`] ?? key,
    refresh: query.refetch,
  };
};

/**
 * 列全部字典概要 (供 admin UI 字典选择下拉框用).
 * 跟 useLookup 共享同一 queryKey 前缀 "lookup", invalidate 统一管理.
 */
export const useAllLookups = () =>
  useQuery({
    queryFn: fetchAllLookups,
    queryKey: ["lookup", "all"],
    refetchOnWindowFocus: false,
    staleTime: FIVE_MIN,
  });
