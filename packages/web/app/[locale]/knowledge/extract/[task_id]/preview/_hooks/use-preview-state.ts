// use-preview-state — preview page 的核心状态逻辑
// 抽 useMapToggle 双 state + useEffect 同步 + useMemo 计数
// "use client" 因为 useState / useEffect / useMemo
"use client";
/* oxlint-disable max-statements -- preview state hook 逻辑连贯, 拆分增加阅读成本 */
import { useEffect, useMemo } from "react";
import type { UseQueryResult } from "@tanstack/react-query";
import { ZERO } from "@/const";
import {
  patchExtractItems,
  type ExtractPreview,
  type ExtractPreviewEntity,
  type ExtractPreviewRelation,
  type PatchItemInput,
} from "@/lib/api/knowledge";
import { useMapToggle } from "./use-map-toggle";

/**
 * usePreviewState hook 参数
 * @property previewQuery - useQuery 返回的预览数据
 * @property taskId - 提取任务 ID
 * @property dataset - 数据集名称
 */
export interface UsePreviewStateArgs {
  previewQuery: UseQueryResult<ExtractPreview, unknown>;
  taskId: string;
  dataset: string;
}

/**
 * usePreviewState hook 返回值
 * @property entityState - entity MapToggle 状态
 * @property relationState - relation MapToggle 状态
 * @property entities - 当前 entity 列表
 * @property relations - 当前 relation 列表
 * @property selectedEntityCount - 已选 entity 数
 * @property selectedRelationCount - 已选 relation 数
 * @property totalSelected - 总选中数
 * @property hasData - 是否有数据
 * @property saveEdits - 保存编辑 (PATCH diff)
 */
export interface UsePreviewStateResult {
  entityState: ReturnType<typeof useMapToggle<ExtractPreviewEntity>>;
  relationState: ReturnType<typeof useMapToggle<ExtractPreviewRelation>>;
  entities: ExtractPreviewEntity[];
  relations: ExtractPreviewRelation[];
  selectedEntityCount: number;
  selectedRelationCount: number;
  totalSelected: number;
  hasData: boolean;
  saveEdits: () => Promise<void>;
}

/**
 * 比对本地 map 与服务端原值, 生成 PATCH diff 项
 * @param entityMap 当前 entity 状态 map
 * @param relationMap 当前 relation 状态 map
 * @param original 服务端返回的原始数据
 * @returns 待提交的 PATCH items
 */
const buildDirtyItems = (
  entityMap: Map<number, ExtractPreviewEntity>,
  relationMap: Map<number, ExtractPreviewRelation>,
  original: ExtractPreview,
): PatchItemInput[] => {
  const items: PatchItemInput[] = [];
  entityMap.forEach((entity) => {
    const found = original.entities.find((other) => other.id === entity.id);
    if (found && (found.text !== entity.text || found.selected !== entity.selected)) {
      items.push({
        id: entity.id,
        selected: entity.selected,
        corrected_payload: { text: entity.text, label: entity.label },
      });
    }
  });
  relationMap.forEach((relation) => {
    const found = original.relations.find((other) => other.id === relation.id);
    if (
      found &&
      (found.head !== relation.head ||
        found.tail !== relation.tail ||
        found.selected !== relation.selected)
    ) {
      items.push({
        id: relation.id,
        selected: relation.selected,
        corrected_payload: {
          head: relation.head,
          rel_type: relation.rel_type,
          tail: relation.tail,
          rule_type: relation.rule_type,
        },
      });
    }
  });
  return items;
};

/**
 * Preview 页面核心状态 hook — 管理 entity/relation 双 Map 状态 + diff 保存逻辑
 * @param args - hook 参数
 * @returns UsePreviewStateResult 状态和操作方法
 * @client-bff
 */
export const usePreviewState = ({
  previewQuery,
  taskId,
  dataset,
}: UsePreviewStateArgs): UsePreviewStateResult => {
  const entityState = useMapToggle<ExtractPreviewEntity>([]);
  const relationState = useMapToggle<ExtractPreviewRelation>([]);

  // useQuery 拿到数据后灌进 map state
  const { data: previewData } = previewQuery;
  useEffect(() => {
    if (!previewData) {
      return;
    }
    entityState.actions.setAll(previewData.entities);
    relationState.actions.setAll(previewData.relations);
    // entityState/relationState 在 useMapToggle 内部已稳定 (useCallback), 不加依赖
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [previewData]);

  // 解构避免 prefer-destructuring warning
  const { map: entityMap } = entityState;
  const { map: relationMap } = relationState;

  const entities = useMemo(() => [...entityMap.values()], [entityMap]);
  const relations = useMemo(() => [...relationMap.values()], [relationMap]);

  const selectedEntityCount = useMemo(
    () => entities.filter((entity) => entity.selected).length,
    [entities],
  );
  const selectedRelationCount = useMemo(
    () => relations.filter((relation) => relation.selected).length,
    [relations],
  );
  const totalSelected = selectedEntityCount + selectedRelationCount;
  const hasData = entities.length > ZERO || relations.length > ZERO;

  const saveEdits = async (): Promise<void> => {
    if (!previewData) {
      return;
    }
    const items = buildDirtyItems(entityMap, relationMap, previewData);
    if (items.length === ZERO) {
      return;
    }
    await patchExtractItems(taskId, dataset, items);
  };

  return {
    entityState,
    relationState,
    entities,
    relations,
    selectedEntityCount,
    selectedRelationCount,
    totalSelected,
    hasData,
    saveEdits,
  };
};
