// 知识图谱 schema 的 zod 镜像 (2026-06-08)
// 跟 configs/knowledge-schema.yaml 同步; yaml 改了同步改这里
// 加节点/关系只需要动 yaml + 这个文件两处

import { z } from "zod";

/** 字段类型枚举: string/text/enum/ref/url/datetime.
 * @shared */
export const FieldType = z.enum(["string", "text", "enum", "ref", "url", "datetime"]);
/** FieldType 的 inferred 类型.
 * @shared */
export type FieldType = z.infer<typeof FieldType>;

/** 字段定义 Zod schema (key/label/type/options/ref/校验).
 * @shared */
export const FieldDef = z.object({
  key: z.string(),
  label: z.string(),
  multiple: z.boolean().optional(),
  options: z.array(z.string()).optional(),
  readonly: z.boolean().optional(),
  ref_to: z.string().optional(),
  required: z.boolean().optional(),
  type: FieldType,
  unique: z.boolean().optional(),
});
/** FieldDef 的 inferred 类型.
 * @shared */
export type FieldDef = z.infer<typeof FieldDef>;

/** 节点定义 Zod schema (name/color/fields).
 * @shared */
export const NodeDef = z.object({
  color: z.string().optional(),
  fields: z.array(FieldDef).default([]),
  name: z.string(),
});
/** NodeDef 的 inferred 类型.
 * @shared */
export type NodeDef = z.infer<typeof NodeDef>;

/** 关系定义 Zod schema (from/to/name/cardinality).
 * @shared */
export const RelationDef = z.object({
  cardinality: z.enum(["many_to_one", "many_to_many", "one_to_one", "one_to_many"]),
  from: z.string(),
  name: z.string(),
  to: z.string(),
});
/** RelationDef 的 inferred 类型.
 * @shared */
export type RelationDef = z.infer<typeof RelationDef>;

/** 知识图谱完整 schema (nodes + relations).
 * @shared */
export const KnowledgeSchema = z.object({
  nodes: z.array(NodeDef),
  relations: z.array(RelationDef),
});
/** KnowledgeSchema 的 inferred 类型.
 * @shared */
export type KnowledgeSchema = z.infer<typeof KnowledgeSchema>;
