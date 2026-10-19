"use client";
// PreviewTable — 通用预览表 (DataTable + 勾选 + 可编辑 Input)
// 给 preview page 用, 一次定义给 entity / relation 两类数据共用
import { useMemo, type ReactNode } from "react";
import { useTranslations } from "next-intl";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { DataTable, type ColumnDef } from "@/components/common/table/data-table";
import type { MapToggleActions } from "../_hooks/use-map-toggle";
/* oxlint-disable id-length -- T 是 TypeScript 泛型惯例单字母, col 字段短名 */

/**
 * EditableColumn - 可编辑 input 列配置
 * @property id - 列 ID
 * @property header - 列头渲染函数
 * @property field - 数据字段名
 * @property width - 列宽 (可选)
 */
export interface EditableColumn<T> {
  id: string;
  header: () => ReactNode;
  field: keyof T & string;
  width?: number;
}

/**
 * ReadonlyColumn - 只读列配置
 * @property id - 列 ID
 * @property header - 列头渲染函数
 * @property cell - 单元格渲染函数
 * @property width - 列宽 (可选)
 */
export interface ReadonlyColumn<T> {
  id: string;
  header: () => ReactNode;
  cell: (row: T) => ReactNode;
  width?: number;
}

/** 任意列类型 (可编辑 | 只读) */
export type AnyColumn<T> = EditableColumn<T> | ReadonlyColumn<T>;

/**
 * PreviewTableProps - 通用预览表属性
 * @property title - 中文标题 (Card title)
 * @property dataSource - DataTable 数据源
 * @property rowKey - DataTable rowKey
 * @property columns - 列定义 (可编辑 / 只读混合)
 * @property actions - 勾选 + 编辑 handlers
 * @property allSelected - 全选状态
 * @property selectedCount - 已选计数
 * @property emptyText - 空态文案
 */
export interface PreviewTableProps<T extends { id: number }> {
  /** 中文标题 (Card title) */
  title: string;
  /** DataTable 数据源 (从 Map.values() 转数组) */
  dataSource: T[];
  /** DataTable rowKey (通常是 "id") */
  rowKey: keyof T & string;
  /** 列定义 (可编辑 / 只读混合) */
  columns: AnyColumn<T>[];
  /** 勾选 + 编辑 handlers (来自 useMapToggle) */
  actions: MapToggleActions<T>;
  /** 全选状态 (来自 useMapToggle.allSelected) */
  allSelected: boolean;
  /** 已选计数 (从外部 useMemo 算) */
  selectedCount: number;
  /** 空态文案 */
  emptyText: ReactNode;
}

/**
 * 区分 editable vs readonly column 类型守卫
 * @param col - 任意列类型
 * @returns 是否为可编辑列
 */
const isEditable = <T,>(col: AnyColumn<T>): col is EditableColumn<T> => "field" in col;

/**
 * PreviewTable - 通用预览表组件 (DataTable + 勾选 + 可编辑 Input)
 * @param props - 组件属性
 * @client-bff
 */
export const PreviewTable = <T extends { id: number }>({
  title,
  dataSource,
  rowKey,
  columns,
  actions,
  allSelected,
  selectedCount,
  emptyText,
}: PreviewTableProps<T>) => {
  const tr = useTranslations();
  const dataTableColumns: ColumnDef<T>[] = useMemo(
    () => [
      {
        id: "select",
        header: () => (
          <Checkbox
            checked={allSelected}
            onCheckedChange={(value) => actions.toggleAll(Boolean(value))}
          />
        ),
        cell: (ctx) => {
          const original = ctx.row.original as unknown as { selected: boolean };
          return (
            <Checkbox
              checked={original.selected}
              onCheckedChange={(value) => actions.toggle(ctx.row.original.id, Boolean(value))}
            />
          );
        },
      },
      ...columns.map<ColumnDef<T>>((col) => {
        if (isEditable(col)) {
          return {
            id: col.id,
            header: col.header,
            cell: (ctx) => (
              <Input
                value={String(ctx.row.original[col.field] ?? "")}
                onChange={(evt) =>
                  actions.edit(ctx.row.original.id, {
                    [col.field]: evt.target.value,
                  } as Partial<T>)
                }
              />
            ),
            size: col.width,
          };
        }
        return {
          id: col.id,
          header: col.header,
          cell: (ctx) => col.cell(ctx.row.original),
          size: col.width,
        };
      }),
    ],
    [tr, columns, actions, allSelected],
  );

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle>
          {title} ({dataSource.length}){" "}
          <span className="text-sm text-muted-foreground">
            {tr("已选")} {selectedCount}
          </span>
        </CardTitle>
      </CardHeader>
      <CardContent>
        <DataTable
          dataSource={dataSource}
          columns={dataTableColumns}
          rowKey={rowKey}
          emptyText={emptyText}
        />
      </CardContent>
    </Card>
  );
};
