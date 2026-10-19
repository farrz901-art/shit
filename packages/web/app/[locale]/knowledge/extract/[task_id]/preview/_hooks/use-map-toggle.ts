// useMapToggle — 通用 Map 状态 + toggle / toggleAll / edit handlers
// 给 PreviewTable 子组件用, 处理 entity / relation 两类数据共用逻辑
"use client";
import { useCallback, useState } from "react";
/* oxlint-disable id-length -- T 是 TypeScript 泛型惯例单字母 */

/**
 * MapToggleActions - Map 勾选/编辑操作合集
 * @property toggle - 切换单条 selected 状态
 * @property toggleAll - 批量切换所有 selected
 * @property edit - 编辑单条字段 (保留 selected, 改其他字段)
 * @property setAll - 整体 setState (useEffect 同步服务端数据用)
 */
export interface MapToggleActions<T> {
  /** 切换单条 selected 状态 */
  toggle: (id: number, selected: boolean) => void;
  /** 批量切换所有 selected */
  toggleAll: (selected: boolean) => void;
  /** 编辑单条字段 (保留 selected, 改其他字段) */
  edit: (id: number, patch: Partial<T>) => void;
  /** 整体 setState (useEffect 同步服务端数据用) */
  setAll: (items: T[]) => void;
}

/**
 * MapToggleResult - useMapToggle 返回值
 * @property map - 数据 Map
 * @property actions - 操作合集
 * @property allSelected - 是否全选
 * @property size - 数据数量
 */
export interface MapToggleResult<T> {
  map: Map<number, T>;
  actions: MapToggleActions<T>;
  allSelected: boolean;
  size: number;
}

/**
 * 通用 Map 状态管理 hook, 提供 toggle / toggleAll / edit / setAll 操作
 * @param initial - 初始数据数组
 * @returns MapToggleResult 状态和操作方法
 * @client-bff
 */
export const useMapToggle = <T extends { id: number }>(initial: T[] = []): MapToggleResult<T> => {
  const [map, setMap] = useState<Map<number, T>>(
    () => new Map(initial.map((item) => [item.id, item])),
  );

  const toggle = useCallback((id: number, selected: boolean): void => {
    setMap((prev) => {
      const next = new Map(prev);
      const item = next.get(id);
      if (item) {
        next.set(id, { ...item, selected } as T);
      }
      return next;
    });
  }, []);

  const toggleAll = useCallback((selected: boolean): void => {
    setMap((prev) => {
      const next = new Map(prev);
      for (const [id, item] of next) {
        next.set(id, { ...item, selected } as T);
      }
      return next;
    });
  }, []);

  const edit = useCallback((id: number, patch: Partial<T>): void => {
    setMap((prev) => {
      const next = new Map(prev);
      const item = next.get(id);
      if (item) {
        next.set(id, { ...item, ...patch } as T);
      }
      return next;
    });
  }, []);

  const setAll = useCallback((items: T[]): void => {
    setMap(new Map(items.map((item) => [item.id, item])));
  }, []);

  const { size } = map;
  /* oxlint-disable prefer-destructuring -- 保持链式可读性 */
  /* oxlint-disable no-magic-numbers -- 0 是边界值, 用 ZERO 反而绕弯 */
  const allSelected =
    size > 0 &&
    [...map.values()].every((item) => (item as unknown as { selected: boolean }).selected);
  /* oxlint-enable prefer-destructuring */
  /* oxlint-enable no-magic-numbers */

  return { map, actions: { toggle, toggleAll, edit, setAll }, allSelected, size };
};
/* oxlint-enable id-length */
