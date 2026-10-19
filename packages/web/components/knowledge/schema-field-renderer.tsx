"use client";
/**
 * 关系选择器 — 按 source 标签过滤可选关系
 * @param props.schema 知识图谱 schema
 * @param props.fromLabel 源标签
 * @param props.value 当前选中值
 * @param props.onChange 值变更回调
 * @returns JSX 元素
 * @client-bff
 */
import { AppSelect } from "@/components/common/input/app-select";
import type { KnowledgeSchema } from "@/lib/schema-types";

/** schema-field-renderer React 组件 @client-bff */
/** schema-field-renderer @client-bff */
export const RelationPicker = ({
  schema,
  fromLabel,
  value,
  onChange,
}: {
  schema: KnowledgeSchema;
  fromLabel: string;
  value: string;
  onChange: (val: string) => void;
}) => {
  const rels = schema.relations.filter((rel) => rel.from === fromLabel);
  return (
    <AppSelect
      options={rels.map((rel) => ({ label: `${rel.name} → ${rel.to}`, value: rel.name }))}
      value={value}
      onChange={onChange}
      placeholder="选关系"
      dataTestid="rel-picker"
    />
  );
};

/**
 * 节点标签选择器 — 从 schema 节点列表选择
 * @param props.schema 知识图谱 schema
 * @param props.value 当前选中值
 * @param props.onChange 值变更回调
 * @returns JSX 元素
 * @client-bff
 */
export const LabelPicker = ({
  schema,
  value,
  onChange,
}: {
  schema: KnowledgeSchema;
  value: string;
  onChange: (val: string) => void;
}) => (
  <AppSelect
    options={schema.nodes.map((node) => ({ label: node.name, value: node.name }))}
    value={value}
    onChange={onChange}
    placeholder="选节点类型"
    dataTestid="label-picker"
  />
);
