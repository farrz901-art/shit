// useBuyersColumns (2026-06-29 refactor)
// 抽自 buyers/page.tsx 的 buildProfileColumn (switch 5 case) + activeFields 排序
// 改用 Record lookup (FIELD_TYPE_RENDERERS), 消除 if/else / switch 多分支 (A-08, A-09)

"use client";

import { type ReactNode } from "react";
import type { ColumnDef } from "@/components/common/table/data-table";
import { Badge } from "@/components/ui/badge";
import type {
  BuyerProfile,
  ProfileFieldConfig,
} from "@/app/[locale]/buyers/_lib/buyer-profile/types";

/** 空值占位符 @shared */
const EMPTY_PLACEHOLDER = "—";
/** 画像列最小宽度 @shared */
const PROFILE_COL_MIN = 120;
/** 画像列最大宽度 @shared */
const PROFILE_COL_MAX = 240;
/** 数字常量零 @shared */
const ZERO = 0;

/** 字段类型 → cell 渲染器
 * @param row - 客户画像行
 * @param code - 字段编码
 * @param translate - i18n 翻译函数
 * @returns React 节点
 * @shared
 */
type FieldTypeRenderer = (
  row: BuyerProfile,
  code: string,
  translate: (key: string) => string,
) => ReactNode;

/** 从 profile_data[code] 提取 value, 缺失返回 undefined
 * @param row - 客户画像行
 * @param code - 字段编码
 * @returns 字段值或 undefined
 * @shared
 */
const getProfileFieldValue = (row: BuyerProfile, code: string): unknown => {
  const field = row.profile_data[code];
  if (field === undefined) {
    return undefined;
  }
  return field.value;
};

/** 判断值是否为空 (null/undefined)
 * @param value - 待检测值
 * @returns 是否为空
 * @shared
 */
const isEmptyValue = (value: unknown): boolean => value === null || value === undefined;

/** 下拉选择类型列渲染
 * @param row - 客户画像行
 * @param code - 字段编码
 * @returns React 节点
 * @shared
 */
const renderSelectCell = (row: BuyerProfile, code: string): ReactNode => {
  const value = getProfileFieldValue(row, code);
  if (isEmptyValue(value)) {
    return EMPTY_PLACEHOLDER;
  }
  return <Badge variant="secondary">{String(value)}</Badge>;
};

/** 标签类型列渲染
 * @param row - 客户画像行
 * @param code - 字段编码
 * @returns React 节点
 * @shared
 */
const renderTagsCell = (row: BuyerProfile, code: string): ReactNode => {
  const value = getProfileFieldValue(row, code);
  if (!Array.isArray(value) || value.length === ZERO) {
    return EMPTY_PLACEHOLDER;
  }
  const tags = value.filter((tag): tag is string => typeof tag === "string");
  if (tags.length === ZERO) {
    return EMPTY_PLACEHOLDER;
  }
  return (
    <div className="flex flex-wrap gap-1">
      {tags.map((tag) => (
        <Badge key={tag} variant="secondary">
          {tag}
        </Badge>
      ))}
    </div>
  );
};

/** 数字类型列渲染
 * @param row - 客户画像行
 * @param code - 字段编码
 * @returns React 节点
 * @shared
 */
const renderNumberCell = (row: BuyerProfile, code: string): ReactNode => {
  const value = getProfileFieldValue(row, code);
  if (isEmptyValue(value)) {
    return EMPTY_PLACEHOLDER;
  }
  return <span className="num text-sm">{String(value)}</span>;
};

/** 布尔类型列渲染
 * @param row - 客户画像行
 * @param code - 字段编码
 * @param translate - i18n 翻译函数
 * @returns React 节点
 * @shared
 */
const renderBooleanCell = (
  row: BuyerProfile,
  code: string,
  translate: (key: string) => string,
): ReactNode => {
  const value = getProfileFieldValue(row, code);
  if (isEmptyValue(value)) {
    return EMPTY_PLACEHOLDER;
  }
  if (value === true || value === "true") {
    return translate("是");
  }
  return translate("否");
};

/** 文本类型列渲染
 * @param row - 客户画像行
 * @param code - 字段编码
 * @returns React 节点
 * @shared
 */
const renderTextCell = (row: BuyerProfile, code: string): ReactNode => {
  const value = getProfileFieldValue(row, code);
  if (isEmptyValue(value)) {
    return EMPTY_PLACEHOLDER;
  }
  return <span className="text-sm">{String(value)}</span>;
};

/** 字段类型 → 渲染器映射 @shared */
const FIELD_TYPE_RENDERERS: Record<string, FieldTypeRenderer> = {
  boolean: renderBooleanCell,
  number: renderNumberCell,
  select: renderSelectCell,
  tags: renderTagsCell,
  text: renderTextCell,
};

/** 默认渲染器 (文本) @shared */
const DEFAULT_RENDERER: FieldTypeRenderer = renderTextCell;

/** 按 sort_order 排序活跃字段
 * @param configs - 字段配置列表
 * @returns 排序后活跃字段数组
 * @shared
 */
const sortBySortOrder = (configs: ProfileFieldConfig[]): ProfileFieldConfig[] =>
  configs
    .filter((cfg) => cfg.is_active)
    .toSorted((cfgA, cfgB) => cfgA.sort_order - cfgB.sort_order);

/** 客户画像列配置生成 hook
 * @param configs - 活跃字段配置列表
 * @param translate - i18n 翻译函数
 * @returns DataTable 列定义数组
 * @client-bff
 */
export const useBuyersColumns = (
  configs: ProfileFieldConfig[],
  translate: (key: string) => string,
): ColumnDef<BuyerProfile>[] => {
  const activeFields = sortBySortOrder(configs);
  return activeFields.map<ColumnDef<BuyerProfile>>((cfg) => ({
    header: () => cfg.label,
    id: `profile_${cfg.code}`,
    meta: { width: { max: PROFILE_COL_MAX, min: PROFILE_COL_MIN } },
    cell: (ctx) => {
      const renderer = FIELD_TYPE_RENDERERS[cfg.field_type] ?? DEFAULT_RENDERER;
      return renderer(ctx.row.original, cfg.code, translate);
    },
  }));
};
