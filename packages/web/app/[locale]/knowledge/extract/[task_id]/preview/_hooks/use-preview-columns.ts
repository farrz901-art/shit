// use-preview-columns — preview page 的列定义 (entity + relation)
// 从 page.tsx 抽出, 跟 usePreviewState / usePreviewActions 配套
"use client";
import { useMemo } from "react";
import { useTranslations } from "next-intl";
import { buildEntityColumns, buildRelationColumns } from "../_components/preview-columns";
import type { AnyColumn } from "../_components/preview-table";
import type { ExtractPreviewEntity, ExtractPreviewRelation } from "@/lib/api/knowledge";

/**
 * UsePreviewColumnsResult - usePreviewColumns 返回值
 * @property entityColumns - 实体列定义
 * @property relationColumns - 关系列定义
 */
export interface UsePreviewColumnsResult {
  entityColumns: AnyColumn<ExtractPreviewEntity>[];
  relationColumns: AnyColumn<ExtractPreviewRelation>[];
}

/**
 * 预览页列定义 hook, 生成 entity/relation 列配置
 * @returns UsePreviewColumnsResult
 * @client-bff
 */
export const usePreviewColumns = (): UsePreviewColumnsResult => {
  const tr = useTranslations();
  // useMemo 防止 render 期间 columns 引用变 (DataTable columns 依赖)
  const entityColumns = useMemo(() => buildEntityColumns(tr), [tr]);
  const relationColumns = useMemo(() => buildRelationColumns(tr), [tr]);
  return { entityColumns, relationColumns };
};
