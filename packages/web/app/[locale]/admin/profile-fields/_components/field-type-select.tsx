"use client";
// (2026-06-29) 字段类型 Select 封装 — create-field-dialog / edit-field-dialog 共用
// 包含 5 个选项 (Text/Select/Tags/Number/Boolean), 消除重复代码

import { AppSelect } from "@/components/common/input/app-select";

/** 字段类型选项列表 (Text/Select/Tags/Number/Boolean) */
const FIELD_TYPE_OPTIONS = [
  { label: "Text", value: "text" },
  { label: "Select", value: "select" },
  { label: "Tags", value: "tags" },
  { label: "Number", value: "number" },
  { label: "Boolean", value: "boolean" },
];

/**
 * 字段类型 Select 封装 — create-field-dialog / edit-field-dialog 共用
 * @param props.onChange - 选中值变更回调
 * @param props.value - 当前选中值
 * @returns 字段类型选择器
 * @client-bff
 */
export const FieldTypeSelect = ({
  onChange,
  value,
}: {
  onChange: (value: string) => void;
  value: string;
}) => (
  <AppSelect className="w-full" onChange={onChange} options={FIELD_TYPE_OPTIONS} value={value} />
);
