// preview-columns — entity / relation 列定义, 从 page.tsx 抽出
// "use client" 不需要, 纯 const + 工厂函数
import type { useTranslations } from "next-intl";
import type { AnyColumn } from "./preview-table";
import type { ExtractPreviewEntity, ExtractPreviewRelation } from "@/lib/api/knowledge";

/** useTranslations 返回类型别名 */
type Tr = ReturnType<typeof useTranslations>;

/**
 * 构建实体列定义 (text 可编辑 + label/chunk_id 只读)
 * @param tr - useTranslations 返回值
 * @returns 实体表格列定义数组
 * @shared
 */
export const buildEntityColumns = (tr: Tr): AnyColumn<ExtractPreviewEntity>[] => [
  { id: "text", header: () => tr("文本"), field: "text", width: 200 },
  {
    id: "label",
    header: () => tr("类型"),
    cell: (row: ExtractPreviewEntity) => row.label,
    width: 96,
  },
  {
    id: "chunk_id",
    header: () => "chunk_id",
    cell: (row: ExtractPreviewEntity) => <code className="text-xs">{row.chunk_id}</code>,
    width: 192,
  },
];

/**
 * 构建关系列定义 (head/tail 可编辑 + rel_type/rule_type 只读)
 * @param tr - useTranslations 返回值
 * @returns 关系表格列定义数组
 * @shared
 */
export const buildRelationColumns = (tr: Tr): AnyColumn<ExtractPreviewRelation>[] => [
  { id: "head", header: () => tr("头"), field: "head", width: 160 },
  {
    id: "rel_type",
    header: () => tr("关系名"),
    cell: (row: ExtractPreviewRelation) => row.rel_type,
    width: 128,
  },
  { id: "tail", header: () => tr("尾"), field: "tail", width: 160 },
  {
    id: "rule_type",
    header: () => tr("规则"),
    cell: (row: ExtractPreviewRelation) => row.rule_type,
    width: 128,
  },
];
